import unittest
from unittest.mock import patch, MagicMock
import hashlib
import io
import http.client
import json
import tempfile
import os
import urllib.parse
import auto_connect_inet as app


class WindowsLogicTests(unittest.TestCase):
    def test_generic_http_success_is_not_wan_proof(self):
        with patch.object(app, "probe_http", return_value=False) as probe:
            self.assertFalse(app.check_internet("192.0.2.5"))
        self.assertEqual(probe.call_count, 2)

    def test_probe_uses_exact_independent_endpoint_expectations(self):
        with patch.object(app, "probe_http", side_effect=[False, True]) as probe:
            self.assertTrue(app.check_internet("192.0.2.5"))
        self.assertEqual(probe.call_args_list[0].args, ("192.0.2.5", "detectportal.firefox.com", "/success.txt", b"success"))
        self.assertEqual(probe.call_args_list[1].args, ("192.0.2.5", "www.msftconnecttest.com", "/connecttest.txt", b"Microsoft Connect Test"))

    def test_unknown_gateway_never_posts(self):
        with patch.object(app, "portal_login_page", return_value=False), patch.object(app, "do_login_cloud") as cloud:
            self.assertEqual(app.recover_portal("ip", "gw"), "suspect")
        cloud.assert_not_called()

    def test_cached_login_unknown_preserves_credentials_and_skips_cloud(self):
        app.creds_cache.update(username="u", password="p")
        with patch.object(app, "portal_login_page", return_value=True), patch.object(app, "do_login_cached", return_value=None), patch.object(app, "do_login_cloud") as cloud:
            self.assertEqual(app.recover_portal("ip", "gw"), "suspect")
        cloud.assert_not_called()
        self.assertEqual(app.creds_cache["password"], "p")

    def test_cached_rejection_falls_back_to_cloud(self):
        app.creds_cache.update(username="u", password="p")
        with patch.object(app, "portal_login_page", return_value=True), patch.object(app, "do_login_cached", return_value=False), patch.object(app, "clear_cache") as clear, patch.object(app, "do_login_cloud", return_value=(False, None)) as cloud:
            self.assertEqual(app.recover_portal("ip", "gw"), "failed")
        clear.assert_called_once(); cloud.assert_called_once()

    def test_malformed_chap_keeps_cache_without_post_or_cloud_request(self):
        cached = {"username": "u", "password": "p"}
        for malformed in (r"\999", r"\777", "\u0100"):
            html = (f'<input id="chap-id" value="{malformed}">'
                    '<input id="chap-challenge" value="\\002">'
                    '<input id="serial" value="s">'
                    '<input id="client_mac" value="00:11:22:33:44:55">'
                    '<input id="client_ip" value="192.0.2.2">'
                    '<input id="login_url" value="http://192.0.2.1/login">')
            with self.subTest(malformed=malformed), patch.object(app, "query_local_gateway", return_value=html), patch.object(app, "post_local_gateway") as post, patch.object(app.urllib.request, "build_opener") as cloud:
                self.assertIsNone(app.do_login_cached("ip", "gw", cached))
                self.assertEqual(app.do_login_cloud("ip", "gw"), (False, None))
            self.assertEqual(cached, {"username": "u", "password": "p"})
            post.assert_not_called()
            cloud.assert_not_called()

    def test_cached_login_posts_fresh_chap_and_requires_wan(self):
        html = '<input id="chap-id" value="\\001"><input id="chap-challenge" value="\\002">'
        with patch.object(app, "query_local_gateway", return_value=html), patch.object(app, "post_local_gateway", return_value="ok") as post, patch.object(app, "wait_until_online", return_value=True):
            self.assertTrue(app.do_login_cached("ip", "gw", {"username":"u", "password":"p"}))
        fields = urllib.parse.parse_qs(post.call_args.args[2])
        self.assertEqual(fields["password"], [hashlib.md5(b"\x01p\x02").hexdigest()])

    def test_portal_inputs_allow_reordered_quoted_attributes_and_decode_entities(self):
        html = "<input value='a&amp;b' name = 'password'><input value='user' name='username'>"
        self.assertEqual(app.parse_input_fields(html, "name"), {"password": "a&b", "username": "user"})

    def test_windows_ipv4_gateway_after_ipv6_gateway_line(self):
        fixture = "Ethernet adapter Wi-Fi:\n   IPv4 Address. . . . . . . . . . . : 192.0.2.4\n   Default Gateway . . . . . . . . . : fe80::1%12\n                                       192.0.2.1\n"
        with patch.object(app.subprocess, "run", return_value=MagicMock(stdout=fixture)):
            self.assertEqual(app.get_interface_details("Wi-Fi"), ("192.0.2.4", "192.0.2.1"))

    def test_unknown_post_reply_still_waits_for_wan_proof(self):
        html = '<input id="chap-id" value="\\001"><input id="chap-challenge" value="\\002">'
        with patch.object(app, "query_local_gateway", return_value=html), patch.object(app, "post_local_gateway", return_value=None), patch.object(app, "wait_until_online", return_value=True) as wait:
            self.assertTrue(app.do_login_cached("ip", "gw", {"username": "u", "password": "p"}))
        wait.assert_called_once_with("ip", "gw")

    def test_chunked_http_response_decodes_and_oversize_rejected(self):
        class SocketFixture:
            def __init__(self, data): self.data = io.BytesIO(data)
            def makefile(self, mode): return self.data
        response = http.client.HTTPResponse(SocketFixture(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n7\r\nsuccess\r\n0\r\n\r\n"))
        response.begin()
        self.assertEqual(response.read(16385), b"success")
        oversize = http.client.HTTPResponse(SocketFixture(b"HTTP/1.1 200 OK\r\nContent-Length: 16385\r\n\r\n" + b"x" * 16385))
        oversize.begin()
        with self.assertRaises(ValueError):
            app.read_limited(oversize, 16384)

    def test_cache_optional_fields_validated_and_save_failure_keeps_memory(self):
        with tempfile.TemporaryDirectory() as directory:
            cache_path = os.path.join(directory, "cache")
            with patch.object(app, "CACHE_FILE", cache_path):
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump({"username": "u", "password": "p", "dst": []}, f)
                self.assertFalse(app.load_cache())
                with patch.object(app, "CACHE_FILE", os.path.join(directory, "missing", "cache")), patch.object(app, "do_login_cloud", return_value=(True, {"username": "fresh", "password": "secret"})), patch.object(app, "portal_login_page", return_value=True), patch.object(app, "log_message"):
                    app.creds_cache.clear()
                    with patch.object(app, "do_login_cached", return_value=False):
                        self.assertEqual(app.recover_portal("ip", "gw"), "online")
                    self.assertEqual(app.creds_cache["password"], "secret")

    def test_post_has_body_framing_source_bind_and_closes(self):
        conn = MagicMock(); conn.getresponse.return_value.read.return_value = b"ok"
        with patch.object(app.http.client, "HTTPConnection", return_value=conn) as factory:
            self.assertEqual(app.post_local_gateway("10.0.0.2", "10.0.0.1", "a=%C3%A9"), "ok")
        self.assertEqual(factory.call_args.kwargs["source_address"], ("10.0.0.2", 0))
        self.assertEqual(conn.request.call_args.kwargs["headers"]["Content-Length"], str(len("a=%C3%A9".encode())))
        conn.close.assert_called_once()

    def test_main_respects_backoff_and_prunes_disconnected_interfaces(self):
        app.interface_states.clear()
        clock = [0.0]
        loops = [0]
        def sleep(delay):
            clock[0] += delay
            loops[0] += 1
            if loops[0] == 8:
                raise KeyboardInterrupt
        with patch.object(app.socket, "socket", return_value=MagicMock()), patch.object(app, "load_cache"), patch.object(app, "log_message"), patch.object(app, "get_connected_inet_interfaces", side_effect=[["Wi-Fi"]] * 3 + [[]]), patch.object(app, "get_interface_details", return_value=("ip", "gw")), patch.object(app, "is_interface_online", return_value=False) as online, patch.object(app, "recover_portal", return_value="failed") as recover, patch.object(app.time, "monotonic", side_effect=lambda: clock[0]), patch.object(app.time, "sleep", side_effect=sleep):
            with self.assertRaises(KeyboardInterrupt): app.main()
        self.assertEqual(recover.call_count, 1)
        self.assertEqual(online.call_count, 2)  # one failed probe plus confirmation; deadline blocks retries
        self.assertNotIn("Wi-Fi", app.interface_states)

    def test_main_schedules_backoff_after_slow_authentication(self):
        app.interface_states.clear()
        clock = [0.0]
        loops = [0]
        def sleep(delay):
            clock[0] += delay
            loops[0] += 1
            if loops[0] == 5:
                raise KeyboardInterrupt
        def recover(*args):
            clock[0] += 7
            return "failed"
        with patch.object(app.socket, "socket", return_value=MagicMock()), patch.object(app, "load_cache"), patch.object(app, "log_message"), patch.object(app, "get_connected_inet_interfaces", return_value=["Wi-Fi"]), patch.object(app, "get_interface_details", return_value=("ip", "gw")), patch.object(app, "is_interface_online", return_value=False), patch.object(app, "recover_portal", side_effect=recover), patch.object(app.time, "monotonic", side_effect=lambda: clock[0]), patch.object(app.time, "sleep", side_effect=sleep):
            with self.assertRaises(KeyboardInterrupt): app.main()
        self.assertEqual(app.interface_states["Wi-Fi"]["next_check"], 14.0)
        self.assertEqual(app.interface_states["Wi-Fi"]["failures"], 1)

    def test_main_identity_change_bypasses_old_deadline(self):
        app.interface_states.clear()
        clock = [100.0]
        loops = [0]
        def sleep(delay):
            clock[0] += delay
            loops[0] += 1
            if loops[0] == 3: raise KeyboardInterrupt
        app.interface_states["Wi-Fi"] = {"identity": ("old", "gw"), "failures": 4, "next_check": 1000, "is_online": False}
        with patch.object(app.socket, "socket", return_value=MagicMock()), patch.object(app, "load_cache"), patch.object(app, "log_message"), patch.object(app, "get_connected_inet_interfaces", return_value=["Wi-Fi"]), patch.object(app, "get_interface_details", return_value=("new", "gw")), patch.object(app, "is_interface_online", return_value=True), patch.object(app.time, "monotonic", side_effect=lambda: clock[0]), patch.object(app.time, "sleep", side_effect=sleep):
            with self.assertRaises(KeyboardInterrupt): app.main()
        self.assertEqual(app.interface_states["Wi-Fi"]["failures"], 0)

    def test_main_leaves_unchanged_identity_deadline_intact(self):
        app.interface_states.clear()
        app.interface_states["Wi-Fi"] = {"identity": ("ip", "gw"), "failures": 3, "next_check": 1000, "is_online": False}
        with patch.object(app.socket, "socket", return_value=MagicMock()), patch.object(app, "load_cache"), patch.object(app, "log_message"), patch.object(app, "get_connected_inet_interfaces", return_value=["Wi-Fi"]), patch.object(app, "get_interface_details", return_value=("ip", "gw")), patch.object(app.time, "monotonic", return_value=100), patch.object(app.time, "sleep", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt): app.main()
        self.assertEqual(app.interface_states["Wi-Fi"]["next_check"], 1000)

    def test_cache_schema_rejects_malformed(self):
        self.assertFalse(app.save_cache({"username":"only"}))

    def test_windows_discovery_commands_have_timeout(self):
        with patch.object(app.subprocess, "run", return_value=MagicMock(stdout="")) as run:
            app.get_connected_inet_interfaces()
        self.assertIn("timeout", run.call_args.kwargs)


    def test_gateway_rejects_oversized_html(self):
        conn = MagicMock()
        conn.getresponse.return_value.status = 200
        conn.getresponse.return_value.read.return_value = b"x" * 65537
        with patch.object(app.http.client, "HTTPConnection", return_value=conn):
            self.assertEqual(app.query_local_gateway("ip", "gw"), "")
        conn.close.assert_called_once()

    def test_probe_parses_real_chunked_and_rejects_captive_200(self):
        class SocketFixture:
            def __init__(self, data):
                self.data = io.BytesIO(data)
            def makefile(self, mode):
                return self.data
        for raw, expected in [
            (b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n7\r\nsuccess\r\n0\r\n\r\n", True),
            (b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nlogin", False),
            (b"HTTP/1.1 302 Found\r\nContent-Length: 7\r\n\r\nsuccess", False),
            (b"HTTP/1.1 200 OK\r\nContent-Length: 16385\r\n\r\n" + b"x" * 16385, False),
        ]:
            response = http.client.HTTPResponse(SocketFixture(raw))
            response.begin()
            conn = MagicMock()
            conn.getresponse.return_value = response
            with patch.object(app.http.client, "HTTPConnection", return_value=conn) as factory:
                self.assertEqual(app.probe_http("192.0.2.2", "probe.invalid", "/", b"success"), expected)
            self.assertEqual(factory.call_args.kwargs["source_address"], ("192.0.2.2", 0))
            conn.close.assert_called_once()

    def test_probe_timeout_closes_connection(self):
        conn = MagicMock()
        conn.request.side_effect = TimeoutError
        with patch.object(app.http.client, "HTTPConnection", return_value=conn):
            self.assertFalse(app.probe_http("ip", "host", "/", b"success"))
        conn.close.assert_called_once()

    def test_main_transient_failure_does_not_authenticate(self):
        with patch.object(app.socket, "socket", return_value=MagicMock()), patch.object(app, "load_cache"), patch.object(app, "log_message"), patch.object(app, "get_connected_inet_interfaces", return_value=["Wi-Fi"]), patch.object(app, "get_interface_details", return_value=("ip", "gw")), patch.object(app, "is_interface_online", side_effect=[False, True]), patch.object(app, "recover_portal") as recover, patch.object(app.time, "sleep", side_effect=[None, KeyboardInterrupt]):
            with self.assertRaises(KeyboardInterrupt):
                app.main()
        recover.assert_not_called()
        self.assertTrue(app.interface_states["Wi-Fi"]["is_online"])

    def test_cache_atomic_failure_preserves_previous_file(self):
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cache"
            path.write_text('{"username":"old","password":"old"}')
            before = path.read_bytes()
            with patch.object(app, "CACHE_FILE", str(path)), patch.object(app.os, "replace", side_effect=OSError("fixture")):
                self.assertFalse(app.save_cache({"username": "new", "password": "new"}))
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual([p.name for p in Path(directory).iterdir()], ["cache"])

    def test_windows_multiple_interfaces_match_ssid_not_bssid(self):
        fixture = """    Name                   : Wi-Fi
    State                  : connected
    SSID                   : INET - Free WiFi
    BSSID                  : 01:02:03:04:05:06
    Name                   : USB Wi-Fi
    State                  : connected
    SSID                   : Home
    BSSID                  : 01:02:03:04:05:07
"""
        with patch.object(app.subprocess, "run", return_value=MagicMock(stdout=fixture)):
            self.assertEqual(app.get_connected_inet_interfaces(), ["Wi-Fi"])

    def test_https_handler_binds_source_and_preserves_tls_defaults(self):
        handler = app.BoundHTTPSHandler("192.0.2.2")
        def open_connection(factory, request):
            return factory("example.invalid", timeout=2)
        with patch.object(handler, "do_open", side_effect=open_connection), patch.object(app.http.client, "HTTPSConnection") as factory:
            handler.https_open(app.urllib.request.Request("https://example.invalid/"))
        self.assertEqual(factory.call_args.kwargs["source_address"], ("192.0.2.2", 0))

    def test_cloud_full_handshake_uses_bound_sockets_and_cookie_without_env_proxy(self):
        import http.server
        import socket
        import threading
        from urllib.parse import parse_qs
        requests = []
        password = "p&fixture"
        gateway_page = """<input value='serial' id='serial'><input id='client_mac' value='00:11:22:33:44:55'><input value='127.0.0.2' id='client_ip'><input id='login_url' value='http://192.0.2.1/login'><input value='\\001' id='chap-id'><input value='\\002' id='chap-challenge'>"""
        form = "<input value='fixture-user' name='username'><input value='p&amp;fixture' name='password'>"
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def reply(self, body, headers=()):
                self.send_response(200)
                for key, value in headers:
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def do_GET(self):
                requests.append((self.command, self.headers.get("Host"), self.path, self.headers.get("Cookie"), b""))
                if self.headers.get("Host") == "192.0.2.1":
                    self.reply(gateway_page.encode())
                elif self.headers.get("Host") == "v1.awingconnect.vn":
                    self.reply(b"fixture", [("Set-Cookie", "ingresscookie=fixture-session; Path=/")])
                else:
                    self.reply(b"success")
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                requests.append((self.command, self.headers.get("Host"), self.path, self.headers.get("Cookie"), body))
                if self.path == "/Home/VerifyUrl":
                    if self.headers.get("Cookie") != "ingresscookie=fixture-session":
                        self.send_error(403)
                        return
                    self.reply(json.dumps({"captiveContext": {"contentAuthenForm": form}}).encode())
                else:
                    self.send_response(302)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        server.timeout = 2
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
        thread.start()
        create_connection = socket.create_connection
        sources = []
        def connect(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None, **kwargs):
            sources.append((address, source_address))
            return create_connection(server.server_address, timeout, source_address, **kwargs)
        try:
            with patch.object(socket, "create_connection", side_effect=connect), patch.dict(os.environ, {"http_proxy": "http://127.0.0.1:1", "HTTP_PROXY": "http://127.0.0.1:1", "no_proxy": "", "NO_PROXY": ""}):
                ok, creds = app.do_login_cloud("127.0.0.2", "192.0.2.1")
            self.assertTrue(ok)
            self.assertEqual(creds["password"], password)
            self.assertTrue(all(source == ("127.0.0.2", 0) for _, source in sources))
            self.assertFalse(any(address[1] == 1 for address, _ in sources))
            posted = next(body for method, host, path, cookie, body in requests if method == "POST" and host == "192.0.2.1")
            self.assertEqual(parse_qs(posted.decode())["password"], [hashlib.md5(b"\x01" + password.encode() + b"\x02").hexdigest()])
        finally:
            server.shutdown()
            thread.join(timeout=3)
            server.server_close()

    def tearDown(self):
        app.creds_cache.clear()
        app.interface_states.clear()


if __name__ == "__main__":
    unittest.main()
