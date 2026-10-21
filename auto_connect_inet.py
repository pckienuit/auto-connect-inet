import os
import sys
import re
import time
import socket
import json
import urllib.request
import urllib.parse
import subprocess

import hashlib
import http.cookiejar
import http.client
import tempfile
from html.parser import HTMLParser

SSID_NAME = "INET - Free WiFi"
LOCK_PORT = 49999

# Directory paths
if getattr(sys, 'frozen', False):
    SCRIPT_DIR = os.path.dirname(sys.executable)
else:
    SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
CACHE_FILE = os.path.join(SCRIPT_DIR, ".creds_cache.json")
LOG_FILE = os.path.join(SCRIPT_DIR, "auto_connect_inet.log")

# Optimized intervals: check less aggressively to prevent AP block/blacklist
KEEPALIVE_INTERVAL = 2.0
ONLINE_CHECK_INTERVAL = 2.0
KEEPALIVE_TIMEOUT = 2.0     # 2 seconds connection timeout
BACKOFF_MAX = 30.0

interface_states = {}
creds_cache = {}


def log_message(msg):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    formatted_msg = f"[{timestamp}] {msg}"
    print(formatted_msg, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted_msg + "\n")
    except OSError:
        pass


def load_cache():
    global creds_cache
    try:
        with open(os.path.realpath(CACHE_FILE), 'r', encoding='utf-8') as f:
            loaded = json.load(f)
            if not isinstance(loaded, dict) or not all(isinstance(loaded.get(k), str) and loaded[k] for k in ('username', 'password')):
                raise ValueError("invalid credential cache")
            if any(k in loaded and not isinstance(loaded[k], str) for k in ('dst', 'popup')):
                raise ValueError("invalid optional cache field")
            creds_cache = loaded
            log_message(f"[*] Loaded cached credentials for gateway")
            return True
    except (OSError, ValueError, TypeError):
        creds_cache = {}
        return False


class InputFields(HTMLParser):
    def __init__(self, attribute):
        super().__init__()
        self.attribute = attribute
        self.fields = {}

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "input":
            values = dict(attrs)
            key = values.get(self.attribute)
            if key:
                self.fields[key] = values.get("value", "")


def parse_input_fields(html, attribute="id"):
    parser = InputFields(attribute)
    parser.feed(html)
    return parser.fields


def read_limited(response, limit):
    body = response.read(limit + 1)
    if len(body) > limit:
        raise ValueError("HTTP response exceeds size limit")
    return body


def save_cache(data):
    """Atomically replace valid cache; keep previous file intact on failure."""
    if not isinstance(data, dict) or not all(isinstance(data.get(k), str) and data[k] for k in ('username', 'password')) or any(k in data and not isinstance(data[k], str) for k in ('dst', 'popup')):
        return False
    path = os.path.realpath(CACHE_FILE)
    tmp = None
    fd = None
    try:
        fd, tmp = tempfile.mkstemp(prefix='.creds-', dir=os.path.dirname(path))
        if os.name != 'nt':
            os.chmod(tmp, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            fd = None
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        return True
    except (OSError, ValueError, TypeError):
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass
        return False


def clear_cache():
    global creds_cache
    creds_cache.clear()
    try:
        os.unlink(os.path.realpath(CACHE_FILE))
    except OSError:
        pass


def get_interface_details(interface_name):
    try:
        res = subprocess.run("ipconfig", shell=True, capture_output=True, text=True, timeout=5)
        lines = res.stdout.splitlines()
        target_section = False
        ip = None
        gw = None
        header_pattern = rf"adapter\s+{re.escape(interface_name)}\s*:"
        
        for line in lines:
            if re.search(header_pattern, line, re.IGNORECASE):
                target_section = True
                continue
            if target_section:
                if line.strip() == "":
                    continue
                if not line.startswith("   "):
                    break
                if "IPv4 Address" in line:
                    m = re.search(r"IPv4 Address[ .:]+([\d.]+)", line)
                    if m:
                        ip = m.group(1)
                elif "Default Gateway" in line:
                    m = re.search(r"Default Gateway[ .:]+(\d+(?:\.\d+){3})", line)
                    if m:
                        gw = m.group(1)
                elif gw is None and re.fullmatch(r"\s+[\d.]+\s*", line):
                    gw = line.strip()
        return ip, gw
    except Exception as e:
        log_message(f"[-] Error running ipconfig for {interface_name}: {e}")
        return None, None


def get_connected_inet_interfaces(target_ssid=SSID_NAME):
    try:
        res = subprocess.run("netsh wlan show interfaces", shell=True, capture_output=True, text=True, timeout=5)
        parts = res.stdout.split("Name                   :")
        connected_interfaces = []
        for part in parts[1:]:
            lines = part.splitlines()
            name = lines[0].strip()
            state_match = re.search(r"State\s+:\s+(\w+)", part)
            ssid_match = re.search(r"SSID\s+:\s+(.+)", part)
            
            state = state_match.group(1) if state_match else ""
            current_ssid = ssid_match.group(1).strip() if ssid_match else ""
            
            if state == "connected" and current_ssid.lower() == target_ssid.lower():
                connected_interfaces.append(name)
        return connected_interfaces
    except Exception as e:
        log_message(f"[-] Error listing connected interfaces: {e}")
        return []


def parse_octal_string(s):
    parts = s.split(chr(92))
    res = bytearray()
    if parts[0]:
        res.extend(parts[0].encode('latin1'))
    for part in parts[1:]:
        if not part:
            continue
        digits = []
        for char in part:
            if char.isdigit() and len(digits) < 3:
                digits.append(char)
            else:
                break
        digit_str = ''.join(digits)
        if digit_str:
            res.append(int(digit_str, 8))
            res.extend(part[len(digit_str):].encode('latin1'))
        else:
            res.extend(bytes([92]))
            res.extend(part.encode('latin1'))
    return bytes(res)


def probe_http(bind_ip, host, path, expected):
    """Require exact HTTP 200 response body on source-bound Windows socket."""
    conn = http.client.HTTPConnection(host, timeout=KEEPALIVE_TIMEOUT, source_address=(bind_ip, 0))
    try:
        conn.request("GET", path, headers={"Host": host, "Connection": "close"})
        response = conn.getresponse()
        body = response.read(16385)
        return response.status == 200 and len(body) <= 16384 and body.strip() == expected
    except (OSError, ValueError, http.client.HTTPException):
        return False
    finally:
        conn.close()


def check_internet(bind_ip):
    return (probe_http(bind_ip, "detectportal.firefox.com", "/success.txt", b"success")
            or probe_http(bind_ip, "www.msftconnecttest.com", "/connecttest.txt", b"Microsoft Connect Test"))


def is_interface_online(ip, gw):
    """WAN probes are sole online proof; gateway response cannot stand in for WAN."""
    return check_internet(ip)


def query_local_gateway(ip, gw):
    conn = http.client.HTTPConnection(gw, timeout=KEEPALIVE_TIMEOUT, source_address=(ip, 0))
    try:
        conn.request("GET", "/login", headers={"Host": gw, "Connection": "close"})
        response = conn.getresponse()
        return read_limited(response, 65536).decode("utf-8", errors="replace") if response.status == 200 else ""
    except (OSError, ValueError, http.client.HTTPException):
        return ""
    finally:
        conn.close()


def post_local_gateway(ip, gw, post_data):
    conn = http.client.HTTPConnection(gw, timeout=KEEPALIVE_TIMEOUT, source_address=(ip, 0))
    try:
        body = post_data.encode("utf-8")
        conn.request("POST", "/login", body=body, headers={"Host": gw, "Content-Type": "application/x-www-form-urlencoded", "Content-Length": str(len(body)), "Connection": "close"})
        response = conn.getresponse()
        body = response.read(16385)
        return body.decode("utf-8", errors="replace") if len(body) <= 16384 else None
    except (OSError, ValueError, http.client.HTTPException):
        return ""
    finally:
        conn.close()


def portal_login_page(ip, gw):
    html = query_local_gateway(ip, gw)
    fields = parse_input_fields(html)
    return all(fields.get(key) for key in ("serial", "chap-id", "chap-challenge"))


def do_login_cached(ip, gw, cached):
    html = query_local_gateway(ip, gw)
    if not html:
        return None
    fields = parse_input_fields(html)
    if not fields.get("chap-id") or not fields.get("chap-challenge"):
        return None
    try:
        chap = hashlib.md5(parse_octal_string(fields["chap-id"]) + cached["password"].encode() + parse_octal_string(fields["chap-challenge"])).hexdigest()
    except ValueError:
        return None
    reply = post_local_gateway(ip, gw, urllib.parse.urlencode({"username": cached["username"], "password": chap, "dst": cached.get("dst", "http://v1.awingconnect.vn/Success"), "popup": cached.get("popup", "false")}))
    if reply is not None and re.search(r"invalid (?:username|password)|invalid credentials|user (?:not found|does not exist)", reply, re.I):
        return False
    return True if wait_until_online(ip, gw) else None


def wait_until_online(ip, gw, attempts=5, delay=1.0):
    for n in range(attempts):
        if is_interface_online(ip, gw):
            return True
        if n + 1 < attempts:
            time.sleep(delay)
    return False


def do_login_cloud(ip, gw):
    """Authenticate through Awing cloud API and register on the local gateway."""
    html = query_local_gateway(ip, gw)
    fields = parse_input_fields(html)
    if not all(fields.get(k) for k in ("serial", "client_mac", "client_ip", "login_url", "chap-id", "chap-challenge")):
        return False, None
    try:
        chap_id = parse_octal_string(fields["chap-id"])
        challenge = parse_octal_string(fields["chap-challenge"])
    except ValueError:
        return False, None
    params = {"serial": fields["serial"], "client_mac": fields.get("client_mac", ""), "client_ip": fields.get("client_ip", ip), "userurl": "http://www.msftconnecttest.com/redirect", "login_url": fields.get("login_url", ""), "chap-id": chap_id.decode("latin1"), "chap-challenge": challenge.decode("latin1")}
    referer = "http://v1.awingconnect.vn/login?" + urllib.parse.urlencode(params)
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(cj), BoundHTTPHandler(ip), BoundHTTPSHandler(ip))
    try:
        with opener.open(referer, timeout=5) as response:
            read_limited(response, 65536)
        req = urllib.request.Request("http://v1.awingconnect.vn/Home/VerifyUrl", data=b"", headers={"Referer": referer, "X-Requested-With": "XMLHttpRequest"})
        with opener.open(req, timeout=5) as response:
            payload = json.loads(read_limited(response, 65536).decode("utf-8"))
        form = payload.get("captiveContext", {}).get("contentAuthenForm", "")
        vals = parse_input_fields(form, "name")
        if not vals.get("username") or not vals.get("password"):
            return False, None
        vals.setdefault("dst", "http://v1.awingconnect.vn/Success")
        vals.setdefault("popup", "false")
        chap = hashlib.md5(chap_id + vals["password"].encode() + challenge).hexdigest()
        body = urllib.parse.urlencode({"username": vals["username"], "password": chap, "dst": vals["dst"], "popup": vals["popup"]})
        post_local_gateway(ip, gw, body)
        if not wait_until_online(ip, gw):
            return False, None
        return True, vals
    except Exception as e:
        log_message(f"[-] AWing authentication request failed ({type(e).__name__})")
        return False, None


class BoundHTTPHandler(urllib.request.HTTPHandler):
    def __init__(self, source_ip):
        super().__init__()
        self.source_ip = source_ip
    def http_open(self, req):
        def build(host, **kwargs):
            kwargs["source_address"] = (self.source_ip, 0)
            return http.client.HTTPConnection(host, **kwargs)
        return self.do_open(build, req)


class BoundHTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(self, source_ip):
        super().__init__()
        self.source_ip = source_ip
    def https_open(self, req):
        def build(host, **kwargs):
            kwargs["source_address"] = (self.source_ip, 0)
            return http.client.HTTPSConnection(host, **kwargs)
        return self.do_open(build, req)


def recover_portal(ip, gw):
    global creds_cache
    if not portal_login_page(ip, gw):
        return "suspect"
    if creds_cache:
        result = do_login_cached(ip, gw, creds_cache)
        if result is True:
            return "online"
        if result is None:
            return "suspect"
        clear_cache()
    success, creds = do_login_cloud(ip, gw)
    if success:
        creds_cache.clear()
        creds_cache.update(creds)
        if not save_cache(creds):
            log_message("[-] Credentials kept in memory; cache save failed.")
        return "online"
    return "failed"


def main():
    # Single instance lock
    try:
        lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lock_socket.bind(('127.0.0.1', LOCK_PORT))
        lock_socket.listen(1)
    except socket.error:
        log_message("[*] Another instance is already running. Exiting.")
        sys.exit(0)

    load_cache()
    creds_status = "Loaded cached creds" if creds_cache else "No cached creds"

    log_message(f"[*] INET Auto-Connect — Monitoring '{SSID_NAME}'")
    log_message(f"[*] Keepalive: every 2s | Cache: {creds_status}")

    while True:
        try:
            inet_interfaces = get_connected_inet_interfaces()

            # Clean stale states
            for iface in list(interface_states.keys()):
                if iface not in inet_interfaces:
                    del interface_states[iface]

            for iface in inet_interfaces:
                if iface not in interface_states:
                    interface_states[iface] = {
                        "failures": 0,
                        "next_check": 0,
                        "is_online": False
                    }

                state = interface_states[iface]

                ip, gw = get_interface_details(iface)
                if state.get("identity") != (ip, gw):
                    state.update(identity=(ip, gw), failures=0, next_check=0, is_online=False)
                if time.monotonic() >= state["next_check"]:
                    if ip and gw:
                        online = is_interface_online(ip, gw)
                        if not online:
                            time.sleep(KEEPALIVE_INTERVAL)
                            online = is_interface_online(ip, gw)
                        if online:
                            if not state["is_online"]:
                                log_message(f"[+] Interface '{iface}' (IP: {ip}) is ONLINE.")
                            state["is_online"] = True
                            state["failures"] = 0
                            state["next_check"] = time.monotonic() + ONLINE_CHECK_INTERVAL
                        else:
                            state["is_online"] = False
                            log_message(f"[*] Interface '{iface}' WAN suspect; checking captive portal evidence.")

                            recovery = recover_portal(ip, gw)
                            if recovery == "online":
                                state["failures"] = 0
                                state["is_online"] = True
                                state["next_check"] = time.monotonic() + ONLINE_CHECK_INTERVAL
                            elif recovery == "suspect":
                                state["next_check"] = time.monotonic() + KEEPALIVE_INTERVAL
                            else:
                                state["failures"] += 1
                                backoff = min(5.0 * (2 ** min(state["failures"] - 1, 6)), BACKOFF_MAX)
                                log_message(f"[-] Retrying authentication in {backoff}s...")
                                state["next_check"] = time.monotonic() + backoff
                    else:
                        state["next_check"] = time.monotonic() + 5

        except Exception as e:
            log_message(f"[-] Error in daemon loop: {e}")

        time.sleep(KEEPALIVE_INTERVAL)


if __name__ == "__main__":
    main()
