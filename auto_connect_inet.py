import os
import sys
import re
import time
import socket
import json
import urllib.request
import urllib.parse
import subprocess
import threading
import atexit
import hashlib
import http.cookiejar

SSID_NAME = "INET - Free WiFi"
LOCK_PORT = 49999

# Directory paths
if getattr(sys, 'frozen', False):
    SCRIPT_DIR = os.path.dirname(sys.executable)
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(SCRIPT_DIR, ".creds_cache.json")
LOG_FILE = os.path.join(SCRIPT_DIR, "auto_connect_inet.log")

# Optimized intervals: check less aggressively to prevent AP block/blacklist
KEEPALIVE_INTERVAL = 3.0    # Check authentication status every 3 seconds
KEEPALIVE_TIMEOUT = 2.0     # 2 seconds connection timeout

interface_states = {}
creds_cache = {}
cache_lock = threading.Lock()
block_event = threading.Event()


def log_message(msg):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    formatted_msg = f"[{timestamp}] {msg}"
    print(formatted_msg, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted_msg + "\n")
    except:
        pass


def load_cache():
    global creds_cache
    try:
        with open(CACHE_FILE, 'r') as f:
            creds_cache = json.load(f)
            log_message(f"[*] Loaded cached credentials for gateway")
            return True
    except:
        creds_cache = {}
        return False


def save_cache(data):
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(data, f)
        return True
    except:
        return False


def get_interface_details(interface_name):
    try:
        res = subprocess.run("ipconfig", shell=True, capture_output=True, text=True)
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
                    m = re.search(r"Default Gateway[ .:]+([\d.]+)", line)
                    if m:
                        gw = m.group(1)
        return ip, gw
    except Exception as e:
        log_message(f"[-] Error running ipconfig for {interface_name}: {e}")
        return None, None


def get_connected_inet_interfaces(target_ssid=SSID_NAME):
    try:
        res = subprocess.run("netsh wlan show interfaces", shell=True, capture_output=True, text=True)
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


def check_gateway_authenticated(ip, gw):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((ip, 0))
        s.settimeout(1.0)
        s.connect((gw, 80))
        req = (
            "GET /status HTTP/1.1\r\n"
            f"Host: {gw}\r\n"
            "User-Agent: Mozilla/5.0\r\n"
            "Connection: close\r\n\r\n"
        )
        s.sendall(req.encode('utf-8'))
        res = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            res += chunk
        s.close()
        res_text = res.decode('utf-8', errors='ignore')
        
        if "inetcenter.vn" in res_text.lower() or "Success" in res_text:
            return True
        if "login" in res_text.lower() or 'id="serial"' in res_text or 'name="username"' in res_text:
            return False
        
        if "http/1.1 200" in res_text.lower() or "http/1.1 302" in res_text.lower():
            return True
            
        return False
    except Exception:
        return False


def is_interface_online(ip, gw):
    return check_gateway_authenticated(ip, gw)


def do_login_local_mikrotik(bind_ip, gateway_ip, username, chap_password):
    """Directly POST login details to the local Mikrotik Hotspot gateway."""
    try:
        # Construct raw HTTP POST
        post_params = {
            'username': username,
            'password': chap_password,
            'dst': 'http://v1.awingconnect.vn/Success',
            'popup': 'false'
        }
        post_data = urllib.parse.urlencode(post_params)
        
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((bind_ip, 0))
        s.settimeout(3.0)
        s.connect((gateway_ip, 80))
        req_body = (
            "POST /login HTTP/1.1\r\n"
            f"Host: {gateway_ip}\r\n"
            "Content-Type: application/x-www-form-urlencoded\r\n"
            f"Content-Length: {len(post_data)}\r\n"
            "User-Agent: Mozilla/5.0\r\n"
            "Connection: close\r\n\r\n"
            f"{post_data}"
        )
        s.sendall(req_body.encode('utf-8'))
        res = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            res += chunk
        s.close()
        return True
    except Exception as e:
        log_message(f"[-] Local gateway login post failed: {e}")
        return False


def do_login_cloud(ip, gw):
    """Authenticate through Awing cloud API and register on the local gateway."""
    try:
        # 1. Fetch current login page parameters from local gateway
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((ip, 0))
        s.settimeout(3.0)
        s.connect((gw, 80))
        req = (
            "GET /login HTTP/1.1\r\n"
            f"Host: {gw}\r\n"
            "User-Agent: Mozilla/5.0\r\n"
            "Connection: close\r\n\r\n"
        )
        s.sendall(req.encode('utf-8'))
        res = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            res += chunk
        s.close()
        html = res.decode('utf-8', errors='ignore')
        
        serial_m = re.search(r'id=\"serial\"\s+value=\"([^\"]*)\"', html)
        client_mac_m = re.search(r'id=\"client_mac\"\s+value=\"([^\"]*)\"', html)
        client_ip_m = re.search(r'id=\"client_ip\"\s+value=\"([^\"]*)\"', html)
        login_url_m = re.search(r'id=\"login_url\"\s+value=\"([^\"]*)\"', html)
        chap_id_raw_m = re.search(r'id=\"chap-id\"\s+value=\"([^\"]*)\"', html)
        chap_challenge_raw_m = re.search(r'id=\"chap-challenge\"\s+value=\"([^\"]*)\"', html)
        
        if not (serial_m and client_mac_m and client_ip_m and login_url_m and chap_id_raw_m and chap_challenge_raw_m):
            log_message("[-] Could not extract Mikrotik variables from gateway page.")
            return False, None
            
        serial = serial_m.group(1)
        client_mac = client_mac_m.group(1)
        client_ip = client_ip_m.group(1)
        login_url = login_url_m.group(1)
        chap_id_raw = chap_id_raw_m.group(1)
        chap_challenge_raw = chap_challenge_raw_m.group(1)
        
        chap_id_bytes = parse_octal_string(chap_id_raw)
        chap_challenge_bytes = parse_octal_string(chap_challenge_raw)
        
        # 2. Call Awing Cloud API over default route (WAN)
        params = {
            'serial': serial,
            'client_mac': client_mac,
            'client_ip': client_ip,
            'userurl': 'http://www.msftconnecttest.com/redirect',
            'login_url': login_url,
            'chap-id': chap_id_bytes.decode('latin1'),
            'chap-challenge': chap_challenge_bytes.decode('latin1')
        }
        
        query_str = urllib.parse.urlencode(params)
        login_referer = f'http://v1.awingconnect.vn/login?{query_str}'
        
        cj = http.cookiejar.CookieJar()
        wan_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        
        resp_ad = wan_opener.open(login_referer, timeout=5)
        cookies = list(cj)
        cookie_val = None
        for c in cookies:
            if c.name == 'ingresscookie':
                cookie_val = c.value
                break
                
        if not cookie_val:
            log_message("[-] ingresscookie was not returned by Awing cloud.")
            return False, None
            
        # Verify URL on Awing
        v_req = urllib.request.Request(
            'http://v1.awingconnect.vn/Home/VerifyUrl',
            data=b'',
            headers={
                'User-Agent': 'Mozilla/5.0',
                'Referer': login_referer,
                'X-Requested-With': 'XMLHttpRequest',
                'Cookie': f'ingresscookie={cookie_val}'
            }
        )
        v_resp = wan_opener.open(v_req, timeout=5)
        res_json = json.loads(v_resp.read().decode('utf-8'))
        
        form_html = res_json.get('captiveContext', {}).get('contentAuthenForm', '')
        if not form_html:
            log_message("[-] contentAuthenForm was empty in Awing response.")
            return False, None
            
        username = re.search(r'name=\"username\"\s+value=\"([^\"]*)\"', form_html).group(1)
        password_plain = re.search(r'name=\"password\"\s+value=\"([^\"]*)\"', form_html).group(1)
        
        # 3. Compute local CHAP password
        to_hash = chap_id_bytes + password_plain.encode('utf-8') + chap_challenge_bytes
        h = hashlib.md5()
        h.update(to_hash)
        chap_password = h.hexdigest()
        
        # 4. POST authentication to local gateway
        success = do_login_local_mikrotik(ip, gw, username, chap_password)
        if success:
            # Short sleep to let the gateway process authorization
            time.sleep(1.0)
            if is_interface_online(ip, gw):
                return True, {'username': username, 'password': password_plain}
        return False, None
    except Exception as e:
        log_message(f"[-] do_login_cloud exception: {e}")
        return False, None


def keepalive_worker(stop_event):
    """Daemon thread: monitors connected iNet interfaces."""
    while not stop_event.is_set():
        try:
            inet_interfaces = get_connected_inet_interfaces()
            for iface in inet_interfaces:
                ip, gw = get_interface_details(iface)
                if ip and gw:
                    online = is_interface_online(ip, gw)
                    if not online:
                        block_event.set()
                        break
        except:
            pass
        stop_event.wait(KEEPALIVE_INTERVAL)


def main():
    try:
        import psutil
        p = psutil.Process(os.getpid())
        p.nice(psutil.HIGH_PRIORITY_CLASS)
    except:
        pass

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

    stop_event = threading.Event()
    keepalive_thread = threading.Thread(target=keepalive_worker, args=(stop_event,), daemon=True)
    keepalive_thread.start()
    atexit.register(lambda: stop_event.set())
    
    log_message(f"[*] INET Auto-Connect v4.0 (Safe Mode) — Monitoring '{SSID_NAME}'")
    log_message(f"[*] Keepalive: every 3s | Cache: {creds_status}")

    while True:
        try:
            was_blocked = block_event.wait(timeout=2.0)
            if was_blocked:
                block_event.clear()
            
            current_time = time.time()
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

                if was_blocked or current_time >= state["next_check"]:
                    ip, gw = get_interface_details(iface)
                    if ip and gw:
                        online = is_interface_online(ip, gw)
                        if online:
                            if not state["is_online"]:
                                log_message(f"[+] Interface '{iface}' (IP: {ip}) is ONLINE.")
                            state["is_online"] = True
                            state["failures"] = 0
                            state["next_check"] = current_time + 10  # Check every 10 seconds if online
                        else:
                            state["is_online"] = False
                            log_message(f"[*] Interface '{iface}' blocked. Authenticating...")

                            success = False

                            # Try cloud registration
                            success, new_creds = do_login_cloud(ip, gw)
                            if success:
                                log_message(f"[+] Authenticated via cloud API successfully.")
                                save_cache(new_creds)
                                with cache_lock:
                                    creds_cache.clear()
                                    creds_cache.update(new_creds)
                            else:
                                log_message(f"[-] Cloud API authentication failed.")

                            if success:
                                state["failures"] = 0
                                state["is_online"] = True
                                state["next_check"] = current_time + 10
                            else:
                                state["failures"] += 1
                                # Safe Mode Backoff: prevent spamming the gateway and getting MAC-banned
                                backoff = min(15.0 * (2 ** (state["failures"] - 1)), 300.0)
                                log_message(f"[-] Retrying authentication in {backoff}s...")
                                state["next_check"] = current_time + backoff
                    else:
                        state["next_check"] = current_time + 5

        except Exception as e:
            log_message(f"[-] Error in daemon loop: {e}")

        time.sleep(0.5)


if __name__ == "__main__":
    main()
