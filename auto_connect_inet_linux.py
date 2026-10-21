#!/usr/bin/env python3
"""Auto Connect & Authenticate for INET - Free WiFi (AWing Captive Portal) on Linux.
Designed for Ubuntu / NetworkManager with background keepalive & sub-second re-auth.
"""

import argparse
import hashlib
import http.client
import http.cookiejar
import json
import os
import re
import socket
import subprocess
import threading
import sys
import time
import urllib.parse
import urllib.request

DEFAULT_SSID = "INET - Free WiFi"
LOCK_PORT = 49999
BACKOFF_MAX = 30

# Directory paths
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
CACHE_FILE = os.path.join(SCRIPT_DIR, ".creds_cache.json")
LOG_FILE = os.path.join(SCRIPT_DIR, "auto_connect_inet.log")

KEEPALIVE_INTERVAL = 2.0  # Ping every 2s in background
ONLINE_CHECK_INTERVAL = 2.0  # Check WAN often; never POST without portal evidence
KEEPALIVE_TIMEOUT = 2.0   # 2.0s timeout per probe

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
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            creds_cache = json.load(f)
            log_message("[*] Loaded cached credentials for gateway")
            return True
    except Exception:
        creds_cache = {}
        return False


def save_cache(data):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.chmod(CACHE_FILE, 0o600)
        return True
    except OSError:
        return False


def clear_cache():
    global creds_cache
    creds_cache = {}
    try:
        if os.path.exists(CACHE_FILE):
            os.remove(CACHE_FILE)
            log_message("[*] Cleared invalid/expired credentials cache")
    except OSError:
        pass


def get_connected_inet_interfaces(target_ssid=DEFAULT_SSID):
    """Detect devices by the actual AP SSID, not NetworkManager profile name."""
    connected = []
    try:
        res = subprocess.run(
            ["nmcli", "-t", "--escape", "no", "-f", "ACTIVE,SSID,DEVICE", "dev", "wifi", "list", "--rescan", "no"],
            capture_output=True,
            text=True,
            timeout=5
        )
        for line in res.stdout.splitlines():
            parts = line.strip().rsplit(":", 1)
            if len(parts) != 2:
                continue
            active_ssid, dev = parts
            if active_ssid.startswith("yes:") and active_ssid[4:] == target_ssid and dev not in connected:
                connected.append(dev)
    except Exception as e:
        log_message(f"[-] Error querying nmcli devices: {e}")
    return connected


def wifi_interface_modes():
    """Read nl80211 interface modes; fail closed if unavailable."""
    try:
        output = subprocess.run(["iw", "dev"], capture_output=True, text=True, timeout=3, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    return dict(re.findall(r"Interface\s+(\S+)\s+.*?\btype\s+(\S+)", output, re.S))


def get_all_wifi_interfaces():
    """Only NetworkManager-managed station interfaces, never hotspot APs."""
    wifi_devs = []
    modes = wifi_interface_modes()
    try:
        res = subprocess.run(
            ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "dev"],
            capture_output=True,
            text=True,
            timeout=5
        )
        for line in res.stdout.splitlines():
            parts = line.strip().split(":")
            if (len(parts) >= 3 and parts[1] == "wifi" and parts[2] != "unmanaged"
                    and not parts[0].startswith("p2p-") and modes.get(parts[0]) != "AP"):
                wifi_devs.append(parts[0])
    except Exception:
        pass
    return wifi_devs


def get_interface_details(interface_name):
    """Retrieve IPv4 and default gateway for given network interface on Linux."""
    ip = None
    gw = None
    try:
        # 1. Get IPv4 address
        addr_res = subprocess.run(
            ["ip", "-4", "-o", "addr", "show", "dev", interface_name],
            capture_output=True,
            text=True,
            timeout=3
        )
        for line in addr_res.stdout.splitlines():
            m = re.search(r"inet\s+([\d.]+)/\d+", line)
            if m:
                ip = m.group(1)
                break

        # 2. Get default gateway for this interface
        route_res = subprocess.run(
            ["ip", "-4", "route", "show", "dev", interface_name],
            capture_output=True,
            text=True,
            timeout=3
        )
        for line in route_res.stdout.splitlines():
            m = re.search(r"default via ([\d.]+)", line)
            if m:
                gw = m.group(1)
                break

        # Fallback: check global default route via interface
        if not gw:
            g_route = subprocess.run(
                ["ip", "-4", "route", "show"],
                capture_output=True,
                text=True,
                timeout=3
            )
            for line in g_route.stdout.splitlines():
                if f"dev {interface_name}" in line and "default via" in line:
                    m = re.search(r"default via ([\d.]+)", line)
                    if m:
                        gw = m.group(1)
                        break

    except Exception as e:
        log_message(f"[-] Error querying IP/GW for {interface_name}: {e}")

    return ip, gw


def multiple_gateways_exist():
    """Match the Windows behavior: gateway fallback is only valid with >1 defaults."""
    try:
        res = subprocess.run(
            ["ip", "-4", "route", "show", "default"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        gateways = set()
        for line in res.stdout.splitlines():
            match = re.search(r"default via ([\d.]+) dev (\S+)", line)
            if match:
                gateways.add((match.group(1), match.group(2)))
        return len(gateways) > 1
    except Exception:
        return False


last_reconnect_time = {}

def ensure_secondary_connections(target_ssid=DEFAULT_SSID, force_primary=False):
    """
    Connect secondary wireless interfaces to target_ssid if disconnected or on wrong SSID.
    Primary Wi-Fi is protected unless force_primary=True or there are multiple Wi-Fi cards.
    """
    global last_reconnect_time
    now = time.time()
    try:
        wifi_devs = get_all_wifi_interfaces()
        if not wifi_devs:
            return

        # If only 1 interface and force_primary is False, do not kick user off other networks
        if len(wifi_devs) <= 1 and not force_primary:
            return

        res = subprocess.run(
            ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "dev"],
            capture_output=True,
            text=True,
            timeout=5
        )
        for line in res.stdout.splitlines():
            parts = line.strip().split(":")
            if len(parts) >= 4:
                dev, dev_type, state, conn = parts[0], parts[1], parts[2], parts[3]
                if dev_type == "wifi" and not dev.startswith("p2p-"):
                    # Protect primary if multiple Wi-Fi exist unless instructed
                    if len(wifi_devs) > 1 and dev == wifi_devs[0] and not force_primary:
                        continue

                    if state != "connected" or conn != target_ssid:
                        # Throttle reconnect attempts to once per 30s per dev
                        if now - last_reconnect_time.get(dev, 0) < 30.0:
                            continue
                        last_reconnect_time[dev] = now

                        log_message(f"[*] Secondary interface '{dev}' not on '{target_ssid}' ({conn or 'disconnected'}). Connecting...")
                        subprocess.run(
                            ["nmcli", "dev", "wifi", "connect", target_ssid, "ifname", dev],
                            capture_output=True,
                            timeout=15
                        )
    except Exception as e:
        log_message(f"[-] Error in ensure_secondary_connections: {e}")


class BoundHTTPHandler(urllib.request.HTTPHandler):
    def __init__(self, source_ip):
        super().__init__()
        self.source_ip = source_ip

    def http_open(self, req):
        def build(host, **kwargs):
            if self.source_ip:
                kwargs["source_address"] = (self.source_ip, 0)
            return http.client.HTTPConnection(host, **kwargs)
        return self.do_open(build, req)


class BoundHTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(self, source_ip):
        super().__init__()
        self.source_ip = source_ip

    def https_open(self, req):
        def build(host, **kwargs):
            if self.source_ip:
                kwargs["source_address"] = (self.source_ip, 0)
            return http.client.HTTPSConnection(host, **kwargs)
        return self.do_open(build, req)


def parse_octal_string(value: str) -> bytes:
    """Parse octal-escaped byte sequences (e.g. '\\001\\123') from Mikrotik hotspot."""
    out = bytearray()
    i = 0
    while i < len(value):
        c = value[i]
        if c != "\\":
            out.append(ord(c) & 0xFF)
            i += 1
            continue
        i += 1
        if i >= len(value):
            break
        end = i
        while end < len(value) and end - i < 3 and value[end] in "01234567":
            end += 1
        if end == i:
            out.append(ord("\\") & 0xFF)
            continue
        val = int(value[i:end], 8)
        if val > 255:
            raise ValueError(f"Octal out of range: {val}")
        out.append(val)
        i = end
    return bytes(out)


def calculate_chap_password(chap_id_bytes: bytes, password: str, chap_challenge_bytes: bytes) -> str:
    """Compute Mikrotik MD5 CHAP hash: MD5(chap_id + password + chap_challenge)."""
    h = hashlib.md5()
    h.update(chap_id_bytes + password.encode("utf-8") + chap_challenge_bytes)
    return h.hexdigest()


def query_local_gateway(bind_ip, gateway_ip):
    """Fetch initial captive portal login page from gateway."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((bind_ip, 0))
        s.settimeout(3.0)
        s.connect((gateway_ip, 80))
        req = (
            "GET /login HTTP/1.1\r\n"
            f"Host: {gateway_ip}\r\n"
            "User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36\r\n"
            "Connection: close\r\n\r\n"
        )
        s.sendall(req.encode("utf-8"))
        res = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            res += chunk
        return res.decode("utf-8", errors="ignore")
    except Exception as e:
        log_message(f"[-] Error querying gateway login page ({gateway_ip}:80): {e}")
        return ""
    finally:
        s.close()


def post_local_gateway(bind_ip, gateway_ip, post_data):
    """Submit credentials to gateway."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((bind_ip, 0))
        s.settimeout(3.0)
        s.connect((gateway_ip, 80))
        req_body = (
            "POST /login HTTP/1.1\r\n"
            f"Host: {gateway_ip}\r\n"
            "Content-Type: application/x-www-form-urlencoded\r\n"
            f"Content-Length: {len(post_data)}\r\n"
            "User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36\r\n"
            "Connection: close\r\n\r\n"
            f"{post_data}"
        )
        s.sendall(req_body.encode("utf-8"))
        res = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            res += chunk
        return res.decode("utf-8", errors="ignore")
    except Exception as e:
        log_message(f"[-] Error posting to gateway ({gateway_ip}:80): {e}")
        return ""
    finally:
        s.close()


def probe_http(bind_ip, host, path, expected):
    """Require exact HTTP 200 body on an interface-bound connection."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((bind_ip, 0))
        s.settimeout(KEEPALIVE_TIMEOUT)
        s.connect((host, 80))
        s.sendall((f"GET {path} HTTP/1.1\r\nHost: {host}\r\n"
                   "User-Agent: Mozilla/5.0\r\nConnection: close\r\n\r\n").encode("ascii"))
        res = b""
        while len(res) < 16384:
            chunk = s.recv(4096)
            if not chunk:
                break
            res += chunk
        header, _, body = res.partition(b"\r\n\r\n")
        status_line = header.split(b"\r\n", 1)[0]
        return bool(re.fullmatch(rb"HTTP/\d(?:\.\d)? 200(?: [^\r\n]*)?", status_line)) and body.strip() == expected
    except (OSError, ValueError):
        return False
    finally:
        s.close()


def check_internet(bind_ip):
    """Independent WAN proof if one endpoint stalls; both bound to Wi-Fi IP."""
    return (probe_http(bind_ip, "detectportal.firefox.com", "/success.txt", b"success")
            or probe_http(bind_ip, "www.msftconnecttest.com", "/connecttest.txt", b"Microsoft Connect Test"))


def check_gateway_authenticated(ip, gw):
    """Check if gateway considers this MAC/IP authorized."""
    # 1. Probe /status page
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((ip, 0))
        s.settimeout(2.0)
        s.connect((gw, 80))
        req = (
            "GET /status HTTP/1.1\r\n"
            f"Host: {gw}\r\n"
            "User-Agent: Mozilla/5.0\r\n"
            "Connection: close\r\n\r\n"
        )
        s.sendall(req.encode("utf-8"))
        res = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            res += chunk
        text = res.decode("utf-8", errors="ignore")
        # Only portal-specific success markers count. Generic word "status" is unsafe.
        if "inetcenter.vn" in text.lower() or "logout" in text.lower() or "refresh" in text.lower():
            return True
    except Exception:
        pass
    finally:
        s.close()

    # 2. Probe /login page (if login form exists, we are unauthenticated)
    s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s2.bind((ip, 0))
        s2.settimeout(2.0)
        s2.connect((gw, 80))
        req = (
            "GET /login HTTP/1.1\r\n"
            f"Host: {gw}\r\n"
            "User-Agent: Mozilla/5.0\r\n"
            "Connection: close\r\n\r\n"
        )
        s2.sendall(req.encode("utf-8"))
        res2 = b""
        while True:
            chunk = s2.recv(4096)
            if not chunk:
                break
            res2 += chunk
        text2 = res2.decode("utf-8", errors="ignore")
        if 'id="serial"' in text2 or 'name="username"' in text2:
            return False
    except Exception:
        # A failed local probe is unknown, never proof of authentication.
        return False
    finally:
        s2.close()

    return False


def is_interface_online(ip, gw):
    """Preserve original semantics: gateway fallback only in multi-default setups."""
    if check_internet(ip):
        return True
    if multiple_gateways_exist():
        return check_gateway_authenticated(ip, gw)
    return False


def wait_until_online(ip, gw, attempts=5, delay=1.0):
    """Wait briefly for the captive gateway to apply authorization."""
    for attempt in range(attempts):
        if is_interface_online(ip, gw):
            return True
        if attempt + 1 < attempts:
            time.sleep(delay)
    return False


def portal_login_page(ip, gw):
    """Status branding is not WAN proof; login challenge decides authentication."""
    html = query_local_gateway(ip, gw)
    return bool(html and all(re.search(r'id=["\']' + field + r'["\']', html, re.I)
                             for field in ("serial", "chap-id", "chap-challenge")))


def do_login_cached(ip, gw, cached):
    """Return None on gateway failure; never POST stale CHAP or invalidate cache."""
    html = query_local_gateway(ip, gw)
    if not html:
        return None
    chap_id_m = re.search(r'id="chap-id"\s+value="([^"]*)"', html, re.I)
    chap_challenge_m = re.search(r'id="chap-challenge"\s+value="([^"]*)"', html, re.I)
    if not (chap_id_m and chap_challenge_m):
        return None
    chap_id_bytes = parse_octal_string(chap_id_m.group(1))
    chap_challenge_bytes = parse_octal_string(chap_challenge_m.group(1))
    password_to_post = calculate_chap_password(chap_id_bytes, cached["password"], chap_challenge_bytes)

    post_params = {
        "username": cached["username"],
        "password": password_to_post,
        "dst": cached.get("dst", "http://v1.awingconnect.vn/Success"),
        "popup": cached.get("popup", "false")
    }
    post_data = urllib.parse.urlencode(post_params)
    response = post_local_gateway(ip, gw, post_data)
    if not response:
        return None
    if re.search(r"invalid (?:username|password)|invalid credentials|user (?:not found|does not exist)", response, re.I):
        return False
    if wait_until_online(ip, gw):
        return True
    return None


def do_login_cloud(ip, gw):
    """Perform full handshake via AWing cloud API."""
    html = query_local_gateway(ip, gw)
    if not html:
        log_message(f"[-] Could not reach local gateway login page at {gw}")
        return False, None

    try:
        serial_m = re.search(r'id="serial"\s+value="([^"]*)"', html, re.I)
        client_mac_m = re.search(r'id="client_mac"\s+value="([^"]*)"', html, re.I)
        client_ip_m = re.search(r'id="client_ip"\s+value="([^"]*)"', html, re.I)
        userurl_m = re.search(r'id="userurl"\s+value="([^"]*)"', html, re.I)
        login_url_m = re.search(r'id="login_url"\s+value="([^"]*)"', html, re.I)
        chap_id_m = re.search(r'id="chap-id"\s+value="([^"]*)"', html, re.I)
        chap_challenge_m = re.search(r'id="chap-challenge"\s+value="([^"]*)"', html, re.I)

        if not (serial_m and client_mac_m and client_ip_m and login_url_m and chap_id_m and chap_challenge_m):
            missing = [k for k, v in [
                ("serial", serial_m), ("client_mac", client_mac_m), ("client_ip", client_ip_m),
                ("login_url", login_url_m), ("chap-id", chap_id_m), ("chap-challenge", chap_challenge_m)
            ] if not v]
            log_message(f"[-] Gateway form missing required fields: {missing}")
            return False, None

        serial = serial_m.group(1)
        client_mac = client_mac_m.group(1)
        client_ip = client_ip_m.group(1)
        userurl = userurl_m.group(1) if userurl_m else "http://www.msftconnecttest.com/redirect"
        login_url = login_url_m.group(1)
        chap_id_raw = chap_id_m.group(1)
        chap_challenge_raw = chap_challenge_m.group(1)
    except Exception as e:
        log_message(f"[-] Regex error parsing gateway form: {e}")
        return False, None

    chap_id_bytes = parse_octal_string(chap_id_raw)
    chap_challenge_bytes = parse_octal_string(chap_challenge_raw)

    params = {
        "serial": serial,
        "client_mac": client_mac,
        "client_ip": client_ip,
        "userurl": userurl,
        "login_url": login_url,
        "chap-id": chap_id_bytes.decode("latin1"),
        "chap-challenge": chap_challenge_bytes.decode("latin1")
    }
    query_str = urllib.parse.urlencode(params)
    login_referer = f"http://v1.awingconnect.vn/login?{query_str}"

    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cj),
        BoundHTTPHandler(ip),
        BoundHTTPSHandler(ip)
    )

    try:
        req_ad = urllib.request.Request(
            login_referer,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        )
        with opener.open(req_ad, timeout=5) as resp_ad:
            _ = resp_ad.read()
    except Exception as e:
        log_message(f"[-] AWing login page request failed: {e}")
        return False, None

    cookie_val = None
    for c in cj:
        if c.name.lower() == "ingresscookie":
            cookie_val = c.value
            break

    url = "http://v1.awingconnect.vn/Home/VerifyUrl"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": login_referer,
        "X-Requested-With": "XMLHttpRequest"
    }
    if cookie_val:
        headers["Cookie"] = f"ingresscookie={cookie_val}"

    req = urllib.request.Request(url, data=b"", headers=headers)
    try:
        with opener.open(req, timeout=5) as response:
            res_data = json.loads(response.read().decode("utf-8"))
    except Exception as e:
        log_message(f"[-] Cloud API request failed: {e}")
        return False, None

    form_html = res_data.get("captiveContext", {}).get("contentAuthenForm", "")
    if not form_html:
        log_message("[-] contentAuthenForm empty in AWing response")
        return False, None

    u_m = re.search(r'name="username"\s+value="([^"]*)"', form_html, re.I)
    p_m = re.search(r'name="password"\s+value="([^"]*)"', form_html, re.I)
    d_m = re.search(r'name="dst"\s+value="([^"]*)"', form_html, re.I)
    pop_m = re.search(r'name="popup"\s+value="([^"]*)"', form_html, re.I)
    if not (u_m and p_m):
        log_message("[-] Username or password missing in AWing auth form")
        return False, None

    username = u_m.group(1)
    password = p_m.group(1)
    dst = d_m.group(1) if d_m else "http://v1.awingconnect.vn/Success"
    popup = pop_m.group(1) if pop_m else "false"

    chap_password = calculate_chap_password(chap_id_bytes, password, chap_challenge_bytes)

    post_params = {
        "username": username,
        "password": chap_password,
        "dst": dst,
        "popup": popup
    }
    post_data = urllib.parse.urlencode(post_params)
    if not post_local_gateway(ip, gw, post_data):
        log_message("[-] Local gateway login post failed")
        return False, None

    success = wait_until_online(ip, gw)
    raw_creds = {"username": username, "password": password, "dst": dst, "popup": popup}
    return success, raw_creds if success else None


def recover_portal(ip, gw):
    """Return online/suspect/failed; only submit after confirmed portal challenge."""
    if not portal_login_page(ip, gw):
        log_message("[*] WAN suspect, no portal challenge; skipping authentication")
        return "suspect"
    log_message("[*] Portal challenge confirmed. Authenticating...")
    if creds_cache:
        result = do_login_cached(ip, gw, creds_cache)
        if result is True:
            log_message("[+] Authenticated via cached credentials!")
            return "online"
        if result is None:
            log_message("[*] Cached login inconclusive; preserving cache")
            return "suspect"
        log_message("[-] Cached credentials rejected. Clearing cache...")
        clear_cache()
    success, new_creds = do_login_cloud(ip, gw)
    if success:
        log_message("[+] Authenticated via cloud API! Saved to cache.")
        save_cache(new_creds)
        creds_cache.clear()
        creds_cache.update(new_creds)
        return "online"
    log_message("[-] Cloud API authentication flow failed.")
    return "failed"


def signal_network_events(lines, event):
    """Wake only; daemon alone owns probes, POSTs and cache."""
    for line in lines:
        if line:
            event.set()


def watch_network_events(event):
    """NetworkManager device changes shorten wake latency; poll remains fallback."""
    while True:
        try:
            proc = subprocess.Popen(["nmcli", "device", "monitor"], stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL, text=True, bufsize=1)
            try:
                signal_network_events(proc.stdout, event)
            finally:
                proc.wait(timeout=3)
        except (OSError, subprocess.SubprocessError):
            pass
        time.sleep(5)


def run_daemon(target_ssid=DEFAULT_SSID, force_primary=False):
    # Single instance lock
    try:
        lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lock_socket.bind(("127.0.0.1", LOCK_PORT))
        lock_socket.listen(1)
    except socket.error:
        log_message("[*] Another instance is already running on port 49999. Exiting.")
        sys.exit(0)

    load_cache()
    creds_status = "Loaded cached creds" if creds_cache else "No cached creds (first run)"

    log_message(f"[*] INET Auto-Connect Linux — Monitoring '{target_ssid}'")
    log_message(f"[*] Keepalive: every 2s | Cache: {creds_status}")
    log_message(f"[*] Monitoring WAN and portal; recovery timing depends on network")
    network_event = threading.Event()
    threading.Thread(target=watch_network_events, args=(network_event,), daemon=True).start()

    while True:
        inet_interfaces = []
        try:
            current_time = time.monotonic()
            event_seen = network_event.is_set()
            network_event.clear()
            ensure_secondary_connections(target_ssid, force_primary=force_primary)
            inet_interfaces = get_connected_inet_interfaces(target_ssid)

            # Prune disconnected devices
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

                if (event_seen and state["is_online"]) or time.monotonic() >= state["next_check"]:
                    ip, gw = get_interface_details(iface)
                    if ip and gw:
                        online = is_interface_online(ip, gw)
                        # A single short probe can fail while DNS/routes settle. Confirm
                        # captive state before sending credentials to the gateway.
                        if not online:
                            time.sleep(KEEPALIVE_INTERVAL)
                            online = is_interface_online(ip, gw)
                        if online:
                            if not state["is_online"]:
                                log_message(f"[+] Interface '{iface}' (IP: {ip}, GW: {gw}) is ONLINE.")
                            state["is_online"] = True
                            state["failures"] = 0
                            state["next_check"] = time.monotonic() + ONLINE_CHECK_INTERVAL
                        else:
                            state["is_online"] = False
                            log_message(f"[*] Interface '{iface}' WAN probe failed twice; checking portal...")
                            recovery = recover_portal(ip, gw)
                            if recovery == "online":
                                state["failures"] = 0
                                state["is_online"] = True
                                state["next_check"] = time.monotonic() + ONLINE_CHECK_INTERVAL
                            elif recovery == "suspect":
                                state["next_check"] = time.monotonic() + KEEPALIVE_INTERVAL
                            else:
                                state["failures"] += 1
                                backoff = min(5 * (2 ** (state["failures"] - 1)), BACKOFF_MAX)
                                log_message(f"[-] Retrying in {backoff}s...")
                                state["next_check"] = time.monotonic() + backoff
                    else:
                        state["next_check"] = time.monotonic() + 5.0

        except Exception as e:
            log_message(f"[-] Daemon loop error: {e}")

        network_event.wait(3.0 if not inet_interfaces else KEEPALIVE_INTERVAL)


def run_once(target_ssid=DEFAULT_SSID):
    """Run a single check & authenticate pass."""
    load_cache()
    interfaces = get_connected_inet_interfaces(target_ssid)
    if not interfaces:
        print(f"[-] No interface connected to '{target_ssid}'. Checking available Wi-Fi devices...")
        wifi_devs = get_all_wifi_interfaces()
        print(f"    Available devices: {wifi_devs or 'None'}")
        return

    for iface in interfaces:
        ip, gw = get_interface_details(iface)
        print(f"[*] Interface: {iface} | IP: {ip} | GW: {gw}")
        if not ip or not gw:
            print(f"[-] Could not retrieve IP/GW for {iface}")
            continue

        if is_interface_online(ip, gw):
            print(f"✅ Interface '{iface}' is already ONLINE.")
        else:
            result = recover_portal(ip, gw)
            print(f"[*] Recovery state: {result}")


def check_status(target_ssid=DEFAULT_SSID):
    """Inspect current network status."""
    wifi_devs = get_all_wifi_interfaces()
    connected = get_connected_inet_interfaces(target_ssid)
    print("=== INET Connection Status ===")
    print(f"Target SSID:         {target_ssid}")
    print(f"Wi-Fi Interfaces:    {', '.join(wifi_devs) or 'None'}")
    print(f"Connected to SSID:   {', '.join(connected) or 'None'}")
    for iface in wifi_devs:
        ip, gw = get_interface_details(iface)
        online = is_interface_online(ip, gw) if (ip and gw) else False
        status_str = "🟢 Online" if online else ("🟡 Captive/Blocked" if ip else "⚪ Disconnected")
        print(f"  - {iface}: IP={ip or 'None'}, GW={gw or 'None'} -> {status_str}")


def install_systemd_service(target_ssid=DEFAULT_SSID, force_primary=False):
    """Install and enable user systemd service."""
    service_dir = os.path.expanduser("~/.config/systemd/user")
    os.makedirs(service_dir, exist_ok=True)
    service_file = os.path.join(service_dir, "auto-connect-inet.service")

    script_path = os.path.realpath(__file__)
    python_path = sys.executable

    force_flag = " --force-connect" if force_primary else ""
    content = f"""[Unit]
Description=INET Free WiFi Auto Connect & Captive Portal Login
After=network.target network-online.target

[Service]
Type=simple
ExecStart={python_path} {script_path} --daemon --ssid "{target_ssid}"{force_flag}
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
"""
    with open(service_file, "w", encoding="utf-8") as f:
        f.write(content)

    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", "--now", "auto-connect-inet.service"], check=True)
    print(f"✅ Systemd user service installed: {service_file}")
    print("   Service enabled and started! Use 'systemctl --user status auto-connect-inet' to inspect.")


def main():
    parser = argparse.ArgumentParser(description="INET Free WiFi Auto Connect for Linux")
    parser.add_argument("--daemon", action="store_true", help="Run background monitor daemon (default)")
    parser.add_argument("--once", action="store_true", help="Run a single authentication check and exit")
    parser.add_argument("--status", action="store_true", help="Show current status of interfaces and exit")
    parser.add_argument("--install-service", action="store_true", help="Install systemd user service for auto-start")
    parser.add_argument("--force-connect", action="store_true", help="Force reconnect primary Wi-Fi even if connected to another network")
    parser.add_argument("--ssid", type=str, default=DEFAULT_SSID, help=f"Target SSID name (default: '{DEFAULT_SSID}')")

    args = parser.parse_args()

    if args.status:
        check_status(args.ssid)
    elif args.once:
        run_once(args.ssid)
    elif args.install_service:
        install_systemd_service(args.ssid, force_primary=args.force_connect)
    else:
        run_daemon(args.ssid, force_primary=args.force_connect)


if __name__ == "__main__":
    main()
