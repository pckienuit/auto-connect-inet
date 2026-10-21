import importlib.util
import subprocess
import unittest
from unittest.mock import patch
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("auto_connect_inet_linux.py")
spec = importlib.util.spec_from_file_location("inet_linux", MODULE_PATH)
assert spec and spec.loader
inet = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inet)


def completed(stdout="", returncode=0):
    return subprocess.CompletedProcess([], returncode, stdout, "")


class LinuxLogicTests(unittest.TestCase):
    def test_actual_ssid_not_connection_profile(self):
        output = "yes:INET - Free WiFi:wlan1\nno:other:wlan1\n"
        with patch.object(inet.subprocess, "run", return_value=completed(output)):
            self.assertEqual(inet.get_connected_inet_interfaces(), ["wlan1"])

    def test_ssid_with_colon(self):
        output = "yes:INET: Guest:wlan1\n"
        with patch.object(inet.subprocess, "run", return_value=completed(output)):
            self.assertEqual(inet.get_connected_inet_interfaces("INET: Guest"), ["wlan1"])

    def test_single_gateway_no_false_fallback(self):
        with patch.object(inet, "check_internet", return_value=False), \
             patch.object(inet, "multiple_gateways_exist", return_value=False), \
             patch.object(inet, "check_gateway_authenticated") as gateway:
            self.assertFalse(inet.is_interface_online("10.0.0.2", "10.0.0.1"))
            gateway.assert_not_called()

    def test_multiple_gateway_uses_local_fallback(self):
        with patch.object(inet, "check_internet", return_value=False), \
             patch.object(inet, "multiple_gateways_exist", return_value=True), \
             patch.object(inet, "check_gateway_authenticated", return_value=True):
            self.assertTrue(inet.is_interface_online("10.0.0.2", "10.0.0.1"))

    def test_login_waits_for_gateway_authorization(self):
        with patch.object(inet, "is_interface_online", side_effect=[False, False, True]), \
             patch.object(inet.time, "sleep") as sleep:
            self.assertTrue(inet.wait_until_online("10.0.0.2", "10.0.0.1"))
            self.assertEqual(sleep.call_count, 2)

    def test_cached_login_post_timeout_preserves_cache(self):
        cached = {"username": "u", "password": "p"}
        html = '<input id="chap-id" value="\\001"><input id="chap-challenge" value="\\002">'
        with patch.object(inet, "query_local_gateway", return_value=html), \
             patch.object(inet, "post_local_gateway", return_value=""), \
             patch.object(inet, "wait_until_online") as wait:
            self.assertIsNone(inet.do_login_cached("10.0.0.2", "10.0.0.1", cached))
            wait.assert_not_called()

    def test_cached_login_unverified_response_preserves_cache(self):
        cached = {"username": "u", "password": "p"}
        html = '<input id="chap-id" value="\\001"><input id="chap-challenge" value="\\002">'
        with patch.object(inet, "query_local_gateway", return_value=html), \
             patch.object(inet, "post_local_gateway", return_value="HTTP/1.1 302 Found\\r\\n\\r\\n"), \
             patch.object(inet, "wait_until_online", return_value=False):
            self.assertIsNone(inet.do_login_cached("10.0.0.2", "10.0.0.1", cached))

    def test_cached_login_explicit_rejection_is_not_cached(self):
        cached = {"username": "u", "password": "p"}
        html = '<input id="chap-id" value="\\001"><input id="chap-challenge" value="\\002">'
        with patch.object(inet, "query_local_gateway", return_value=html), \
             patch.object(inet, "post_local_gateway", return_value="HTTP/1.1 200 OK\\r\\n\\r\\ninvalid username or password"), \
             patch.object(inet, "wait_until_online") as wait:
            self.assertFalse(inet.do_login_cached("10.0.0.2", "10.0.0.1", cached))
            wait.assert_not_called()

    def test_secondary_probe_requires_exact_body_not_captive_200(self):
        class FakeSocket:
            def __init__(self):
                self.replies = iter([b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nlogin", b""])
                self.bound = None
            def bind(self, address):
                self.bound = address
            def settimeout(self, value):
                pass
            def connect(self, address):
                pass
            def sendall(self, request):
                pass
            def recv(self, count):
                return next(self.replies)
            def close(self):
                pass
        sock = FakeSocket()
        with patch.object(inet.socket, "socket", return_value=sock):
            self.assertFalse(inet.probe_http("10.0.0.2", "www.msftconnecttest.com", "/connecttest.txt", b"Microsoft Connect Test"))
            self.assertEqual(sock.bound, ("10.0.0.2", 0))

    def test_secondary_wan_probe_recovers_when_firefox_probe_fails(self):
        with patch.object(inet, "probe_http", side_effect=[False, True]) as probe:
            self.assertTrue(inet.check_internet("10.0.0.2"))
            self.assertEqual(probe.call_count, 2)
            self.assertTrue(all(c.args[0] == "10.0.0.2" for c in probe.call_args_list))

    def test_secondary_wan_probe_rejects_captive_redirect(self):
        with patch.object(inet, "probe_http", side_effect=[False, False]) as probe:
            self.assertFalse(inet.check_internet("10.0.0.2"))
            self.assertEqual(probe.call_count, 2)

    def test_online_probe_interval_is_shorter_than_old_ten_seconds(self):
        self.assertLessEqual(inet.ONLINE_CHECK_INTERVAL, 3)

    def test_ap_is_skipped_even_when_managed(self):
        status = "wlan0:wifi:connected:INET - Free WiFi\nap0:wifi:disconnected:\n"
        with patch.object(inet.subprocess, "run", return_value=completed(status)) as run, \
             patch.object(inet, "wifi_interface_modes", return_value={"wlan0": "managed", "ap0": "AP"}):
            self.assertEqual(inet.get_all_wifi_interfaces(), ["wlan0"])
            inet.ensure_secondary_connections()
            self.assertFalse(any(c.args[0][:4] == ["nmcli", "dev", "wifi", "connect"] for c in run.call_args_list))

    def test_virtual_ap_never_reconnected(self):
        status = "wlan0:wifi:connected:INET - Free WiFi\nap0:wifi:unmanaged:\n"
        with patch.object(inet.subprocess, "run", return_value=completed(status)) as run:
            self.assertEqual(inet.get_all_wifi_interfaces(), ["wlan0"])
            inet.ensure_secondary_connections()
            self.assertFalse(any(c.args[0][:4] == ["nmcli", "dev", "wifi", "connect"] for c in run.call_args_list))

    def test_gateway_timeout_keeps_cache_and_skips_post(self):
        cached = {"username": "u", "password": "p"}
        with patch.object(inet, "query_local_gateway", return_value=""), \
             patch.object(inet, "post_local_gateway") as post:
            self.assertIsNone(inet.do_login_cached("10.0.0.2", "10.0.0.1", cached))
            post.assert_not_called()

    def test_suspected_outage_with_status_marker_still_checks_login_challenge(self):
        with patch.object(inet, "check_gateway_authenticated", return_value=True), \
             patch.object(inet, "query_local_gateway", return_value="") as login:
            self.assertFalse(inet.portal_login_page("10.0.0.2", "10.0.0.1"))
            login.assert_called_once()

    def test_unreachable_portal_never_logs_in(self):
        with patch.object(inet, "check_gateway_authenticated", return_value=False), \
             patch.object(inet, "query_local_gateway", return_value=""):
            self.assertFalse(inet.portal_login_page("10.0.0.2", "10.0.0.1"))

    def test_login_page_requires_mikrotik_fields(self):
        with patch.object(inet, "check_gateway_authenticated", return_value=False), \
             patch.object(inet, "query_local_gateway", side_effect=['<input id="serial">', '<input id="serial"><input id="chap-id"><input id="chap-challenge">']):
            self.assertFalse(inet.portal_login_page("10.0.0.2", "10.0.0.1"))
            self.assertTrue(inet.portal_login_page("10.0.0.2", "10.0.0.1"))

    def test_stale_status_does_not_hide_visible_login_challenge(self):
        # /status can contain branded text even after portal session expires.
        page = '<input id="serial"><input id="chap-id"><input id="chap-challenge">'
        with patch.object(inet, "check_gateway_authenticated", return_value=True), \
             patch.object(inet, "query_local_gateway", return_value=page):
            self.assertTrue(inet.portal_login_page("10.0.0.2", "10.0.0.1"))

    def test_gateway_authenticated_suspect_does_not_login(self):
        with patch.object(inet, "check_internet", return_value=False), \
             patch.object(inet, "check_gateway_authenticated", return_value=True), \
             patch.object(inet, "do_login_cloud") as cloud:
            self.assertEqual(inet.recover_portal("10.0.0.2", "10.0.0.1"), "suspect")
            cloud.assert_not_called()

    def test_gateway_unreachable_suspect_does_not_login(self):
        with patch.object(inet, "check_gateway_authenticated", return_value=False), \
             patch.object(inet, "query_local_gateway", return_value=""), \
             patch.object(inet, "do_login_cloud") as cloud:
            self.assertEqual(inet.recover_portal("10.0.0.2", "10.0.0.1"), "suspect")
            cloud.assert_not_called()

    def test_portal_confirmed_cached_timeout_keeps_cache(self):
        inet.creds_cache.clear()
        inet.creds_cache.update({"username": "u", "password": "p"})
        page = '<input id="serial"><input id="chap-id"><input id="chap-challenge">'
        with patch.object(inet, "check_gateway_authenticated", return_value=False), \
             patch.object(inet, "query_local_gateway", return_value=page), \
             patch.object(inet, "do_login_cached", return_value=None), \
             patch.object(inet, "do_login_cloud") as cloud, \
             patch.object(inet, "clear_cache") as clear:
            self.assertEqual(inet.recover_portal("10.0.0.2", "10.0.0.1"), "suspect")
            clear.assert_not_called()
            cloud.assert_not_called()
        inet.creds_cache.clear()

    def test_portal_confirmed_cache_rejection_uses_cloud(self):
        inet.creds_cache.clear()
        inet.creds_cache.update({"username": "u", "password": "p"})
        page = '<input id="serial"><input id="chap-id"><input id="chap-challenge">'
        with patch.object(inet, "check_gateway_authenticated", return_value=False), \
             patch.object(inet, "query_local_gateway", return_value=page), \
             patch.object(inet, "do_login_cached", return_value=False), \
             patch.object(inet, "do_login_cloud", return_value=(True, {"username":"fresh","password":"fresh"})) as cloud, \
             patch.object(inet, "clear_cache"), patch.object(inet, "save_cache"):
            self.assertEqual(inet.recover_portal("10.0.0.2", "10.0.0.1"), "online")
            cloud.assert_called_once()
        inet.creds_cache.clear()

    def test_network_event_wakes_single_owner(self):
        import threading
        event = threading.Event()
        inet.signal_network_events(["wlp0s20f3: connected\n"], event)
        self.assertTrue(event.is_set())

    def test_run_once_uses_same_safe_recovery_gate(self):
        with patch.object(inet, "load_cache"), \
             patch.object(inet, "get_connected_inet_interfaces", return_value=["wlan0"]), \
             patch.object(inet, "get_interface_details", return_value=("10.0.0.2", "10.0.0.1")), \
             patch.object(inet, "is_interface_online", return_value=False), \
             patch.object(inet, "recover_portal", return_value="suspect") as recover, \
             patch.object(inet, "do_login_cloud") as cloud:
            inet.run_once()
            recover.assert_called_once_with("10.0.0.2", "10.0.0.1")
            cloud.assert_not_called()

    def test_single_wifi_does_not_switch_primary(self):
        with patch.object(inet, "get_all_wifi_interfaces", return_value=["wlan0"]), \
             patch.object(inet.subprocess, "run") as run:
            inet.ensure_secondary_connections(force_primary=False)
            run.assert_not_called()

    def test_multiple_wifi_only_switches_secondary(self):
        status = "wlan0:wifi:connected:Home\nwlan1:wifi:disconnected:\n"
        calls = []
        def fake_run(args, **kwargs):
            calls.append(args)
            return completed(status)
        inet.last_reconnect_time.clear()
        with patch.object(inet, "get_all_wifi_interfaces", return_value=["wlan0", "wlan1"]), \
             patch.object(inet.subprocess, "run", side_effect=fake_run):
            inet.ensure_secondary_connections()
        connect_calls = [x for x in calls if x[:4] == ["nmcli", "dev", "wifi", "connect"]]
        self.assertEqual(connect_calls, [["nmcli", "dev", "wifi", "connect", inet.DEFAULT_SSID, "ifname", "wlan1"]])

    def test_octal_parser_golden_vectors(self):
        self.assertEqual(list(inet.parse_octal_string(r"\001ABC\377")), [1, 65, 66, 67, 255])
        self.assertEqual(list(inet.parse_octal_string(r"\x")), [92, 120])
        self.assertEqual(list(inet.parse_octal_string(chr(92))), [])
        self.assertEqual(list(inet.parse_octal_string(r"\200")), [128])
        with self.assertRaises(ValueError):
            inet.parse_octal_string(r"\777")

    def test_chap_password_calculation(self):
        # Known MD5 golden vector
        self.assertEqual(
            inet.calculate_chap_password(b"", "password", b""),
            "5f4dcc3b5aa765d61d8327deb882cf99"
        )
        self.assertEqual(
            len(inet.calculate_chap_password(bytes([1]), "pass", bytes([128, 2]))),
            32
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
