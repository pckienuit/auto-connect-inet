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

SSID_NAME = "INET - Free WiFi"
LOCK_PORT = 49999
PROACTIVE_REFRESH_INTERVAL = 840  # 14 minutes in seconds

# Directory paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(SCRIPT_DIR, ".creds_cache.json")
LOG_FILE = os.path.join(SCRIPT_DIR, "auto_connect_inet.log")

# Keepalive settings (Optimized for Gaming Mode)
KEEPALIVE_INTERVAL = 0.5    # Background check every 500ms
KEEPALIVE_TIMEOUT = 0.3     # 300ms per ping/check

interface_states = {}
creds_cache = {}
cache_lock = threading.Lock()
block_event = threading.Event()
force_reauth = False


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
            
            if state == "connected" and current_ssid == target_ssid:
                connected_interfaces.append(name)
        return connected_interfaces
    except Exception as e:
        log_message(f"[-] Error listing connected interfaces: {e}")
        return []


def ensure_secondary_connections():
    """Detects any secondary wireless interfaces that are disconnected or on wrong SSID and connects them."""
    try:
        res = subprocess.run("netsh wlan show interfaces", shell=True, capture_output=True, text=True)
        parts = res.stdout.split("Name                   :")
        for part in parts[1:]:
            lines = part.splitlines()
            name = lines[0].strip()
            
            # Ignore primary interface if configured as "wifi" (case-insensitive)
            if name.lower() == "wifi":
                continue
                
            state_match = re.search(r"State\s+:\s+(\w+)", part)
            ssid_match = re.search(r"SSID\s+:\s+(.+)", part)
            
            state = state_match.group(1) if state_match else ""
            current_ssid = ssid_match.group(1).strip() if ssid_match else ""
            
            # Only connect if disconnected or connected to wrong network (ignore associating/authenticating)
            if state == "disconnected" or (state == "connected" and current_ssid != SSID_NAME):
                log_message(f"[*] Interface '{name}' is disconnected or wrong SSID ({current_ssid}). Reconnecting to '{SSID_NAME}'...")
                subprocess.run(f'netsh wlan connect name="{SSID_NAME}" interface="{name}"', shell=True, capture_output=True)
    except Exception as e:
        log_message(f"[-] Error in ensure_secondary_connections: {e}")


def query_local_gateway(bind_ip, gateway_ip):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((bind_ip, 0))
    s.settimeout(2)
    try:
        s.connect((gateway_ip, 80))
        req = (
            "GET /login HTTP/1.1\r\n"
            f"Host: {gateway_ip}\r\n"
            "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36\r\n"
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
        return res.decode('utf-8', errors='ignore')
    except Exception:
        return ""


def post_local_gateway(bind_ip, gateway_ip, post_data):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((bind_ip, 0))
    s.settimeout(2)
    try:
        s.connect((gateway_ip, 80))
        req_body = (
            "POST /login HTTP/1.1\r\n"
            f"Host: {gateway_ip}\r\n"
            "Content-Type: application/x-www-form-urlencoded\r\n"
            f"Content-Length: {len(post_data)}\r\n"
            "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36\r\n"
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
        return res.decode('utf-8', errors='ignore')
    except Exception:
        return ""


def logout_local_gateway(bind_ip, gateway_ip):
    """Actively logs out from the local gateway to clear the session before proactive re-auth."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((bind_ip, 0))
    s.settimeout(2)
    try:
        s.connect((gateway_ip, 80))
        req = (
            "GET /logout HTTP/1.1\r\n"
            f"Host: {gateway_ip}\r\n"
            "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36\r\n"
            "Connection: close\r\n\r\n"
        )
        s.sendall(req.encode('utf-8'))
        # Read the first chunk to ensure the request is processed
        s.recv(1024)
        s.close()
        log_message("[*] Successfully sent /logout to local gateway.")
        return True
    except Exception as e:
        log_message(f"[-] Error logging out from gateway: {e}")
        return False


def check_gateway_authenticated(ip, gw):
    """Local check: verify if the gateway has authenticated the MAC/IP without using WAN routing."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((ip, 0))
        s.settimeout(1.5)
        s.connect((gw, 80))
        req = (
            "GET /status HTTP/1.1\r\n"
            f"Host: {gw}\r\n"
            "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36\r\n"
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
        
        # Precise check of the gateway response:
        if "inetcenter.vn" in res_text.lower():
            return True
        if "login" in res_text.lower() or 'id="serial"' in res_text or 'name="username"' in res_text:
            return False
            
        # Fallback: if we got a valid HTTP response but it's a redirect/ok without any login markers
        if "http/1.1 200" in res_text.lower() or "http/1.1 302" in res_text.lower():
            return True
            
        return False
    except Exception:
        return False


def is_interface_online(ip, gw):
    """Robust check that handles Windows multi-NIC routing and VPN/Tailscale interception issues."""
    return check_gateway_authenticated(ip, gw)


def do_login_cached(ip, gw, cached):
    """Try cached credentials directly (no cloud API). Spam the gateway to force fast authorization."""
    post_params = {
        'username': cached['username'],
        'password': cached['password'],
        'dst': cached['dst'],
        'popup': cached['popup']
    }
    post_data = urllib.parse.urlencode(post_params)
    
    # Aggressive: Spam gateway 3 times with 100ms intervals to overcome packet drops or busy gateway
    for i in range(3):
        post_local_gateway(ip, gw, post_data)
        if i < 2:
            time.sleep(0.1)
            
    return is_interface_online(ip, gw)


def do_login_cloud(ip, gw):
    """Login via cloud API, cache successful creds. Returns (success, creds_or_None)."""
    html = query_local_gateway(ip, gw)
    if not html:
        return False, None
    
    try:
        serial_m = re.search(r'id="serial"\s+value="([^"]*)"', html)
        client_mac_m = re.search(r'id="client_mac"\s+value="([^"]*)"', html)
        client_ip_m = re.search(r'id="client_ip"\s+value="([^"]*)"', html)
        userurl_m = re.search(r'id="userurl"\s+value="([^"]*)"', html)
        login_url_m = re.search(r'id="login_url"\s+value="([^"]*)"', html)
        chap_id_m = re.search(r'id="chap-id"\s+value="([^"]*)"', html)
        chap_challenge_m = re.search(r'id="chap-challenge"\s+value="([^"]*)"', html)

        if not all([serial_m, client_mac_m, client_ip_m, userurl_m, login_url_m, chap_id_m, chap_challenge_m]):
            return False, None

        serial = serial_m.group(1)
        client_mac = client_mac_m.group(1)
        client_ip = client_ip_m.group(1)
        userurl = userurl_m.group(1)
        login_url = login_url_m.group(1)
        chap_id = chap_id_m.group(1)
        chap_challenge = chap_challenge_m.group(1)
    except Exception:
        return False, None

    params = {
        'serial': serial,
        'client_mac': client_mac,
        'client_ip': client_ip,
        'userurl': userurl,
        'login_url': login_url,
        'chap_id': chap_id,
        'chap_challenge': chap_challenge
    }
    query_str = urllib.parse.urlencode(params)
    login_referer = f"http://v1.awingconnect.vn/login?{query_str}"
    
    url = "http://v1.awingconnect.vn/Home/VerifyUrl"
    req = urllib.request.Request(
        url,
        data=b"",
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': login_referer
        }
    )

    try:
        # Awing's VerifyUrl requires setting Cookie to the ingresscookie returned by /login
        session_req = urllib.request.Request(login_referer, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(session_req, timeout=3) as session_resp:
            cookie = session_resp.info().get('Set-Cookie', '')
        if cookie:
            req.add_header('Cookie', cookie)
            
        with urllib.request.urlopen(req, timeout=3) as response:
            res_data = json.loads(response.read().decode('utf-8'))
    except Exception:
        return False, None

    form_html = res_data.get('captiveContext', {}).get('contentAuthenForm', '')
    if not form_html:
        return False, None

    try:
        username = re.search(r'name="username"\s+value="([^"]*)"', form_html).group(1)
        password = re.search(r'name="password"\s+value="([^"]*)"', form_html).group(1)
        dst = re.search(r'name="dst"\s+value="([^"]*)"', form_html).group(1)
        popup = re.search(r'name="popup"\s+value="([^"]*)"', form_html).group(1)
    except Exception:
        return False, None

    creds = {'username': username, 'password': password, 'dst': dst, 'popup': popup}
    
    post_params = dict(creds)
    post_data = urllib.parse.urlencode(post_params)
    post_local_gateway(ip, gw, post_data)
    
    success = is_interface_online(ip, gw)
    return success, creds if success else None


def keepalive_worker(stop_event):
    """Background thread: checks gateway authentication every 500ms. Sets block_event on failure."""
    while not stop_event.is_set():
        try:
            # Auto-connect disconnected interfaces
            ensure_secondary_connections()
            
            inet_interfaces = get_connected_inet_interfaces()
            for iface in inet_interfaces:
                ip, gw = get_interface_details(iface)
                if ip and gw:
                    online = is_interface_online(ip, gw)
                    if not online:
                        block_event.set()
                        break
        except Exception:
            pass
        stop_event.wait(KEEPALIVE_INTERVAL)


def trigger_listener(lock_socket):
    """Listens for manual refresh commands from secondary execution instances."""
    global force_reauth
    while True:
        try:
            conn, addr = lock_socket.accept()
            data = conn.recv(1024).decode('utf-8', errors='ignore').strip()
            if data == "refresh":
                log_message("[*] Manual refresh command received via local socket. Activating re-auth sequence...")
                force_reauth = True
                block_event.set()  # Wake up main loop immediately
            conn.close()
        except Exception:
            time.sleep(0.5)


def main():
    global force_reauth

    # Set high process priority if possible
    try:
        import psutil
        p = psutil.Process(os.getpid())
        p.nice(psutil.HIGH_PRIORITY_CLASS)
    except:
        pass

    # Single instance lock & trigger check
    try:
        lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lock_socket.bind(('127.0.0.1', LOCK_PORT))
        lock_socket.listen(5)
    except socket.error:
        # If another instance is running, check if the user wanted to trigger a refresh
        if len(sys.argv) > 1 and sys.argv[1] == "--refresh":
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect(('127.0.0.1', LOCK_PORT))
                s.sendall(b"refresh\n")
                s.close()
                print("[+] Successfully sent manual refresh command to the running daemon.")
            except Exception as e:
                print("[-] Failed to contact running daemon:", e)
        else:
            print("[*] Another instance is already running. Run with '--refresh' to trigger proactive re-auth.")
        sys.exit(0)

    # Load cached credentials from disk
    load_cache()
    creds_status = f"Loaded cached creds" if creds_cache else "No cached creds (first run)"

    # Start keepalive daemon thread
    stop_event = threading.Event()
    keepalive_thread = threading.Thread(target=keepalive_worker, args=(stop_event,), daemon=True)
    keepalive_thread.start()
    
    # Start manual refresh trigger listener thread
    listener_thread = threading.Thread(target=trigger_listener, args=(lock_socket,), daemon=True)
    listener_thread.start()
    
    atexit.register(lambda: stop_event.set())
    
    log_message(f"[*] INET Auto-Connect v3.3 (Gaming & Proactive Mode) — Monitoring '{SSID_NAME}'")
    log_message(f"[*] Keepalive: every 0.5s | Cache: {creds_status}")
    log_message(f"[*] Re-auth target: ~300ms | Log file: {LOG_FILE}")

    while True:
        try:
            # Block here until keepalive detects an outage or a refresh is forced
            was_blocked = block_event.wait(timeout=1.5)
            if was_blocked:
                block_event.clear()
            
            current_time = time.time()
            inet_interfaces = get_connected_inet_interfaces()

            # Clean up stale interfaces
            for iface in list(interface_states.keys()):
                if iface not in inet_interfaces:
                    del interface_states[iface]

            for iface in inet_interfaces:
                if iface not in interface_states:
                    interface_states[iface] = {
                        "failures": 0,
                        "next_check": 0,
                        "is_online": False,
                        "last_auth_time": current_time
                    }

                state = interface_states[iface]
                
                # Proactive refresh trigger: check if 14 minutes have elapsed since last successful auth
                if current_time - state.get("last_auth_time", 0) >= PROACTIVE_REFRESH_INTERVAL:
                    log_message(f"[*] {PROACTIVE_REFRESH_INTERVAL // 60} minutes elapsed. Proactively refreshing session for '{iface}'...")
                    force_reauth = True

                if was_blocked or force_reauth or current_time >= state["next_check"]:
                    ip, gw = get_interface_details(iface)
                    if ip and gw:
                        online = is_interface_online(ip, gw)
                        
                        # Active Refresh flow: Terminate session first to get new inputs
                        if force_reauth:
                            log_message(f"[*] Terminating session on '{iface}' for active refresh...")
                            logout_local_gateway(ip, gw)
                            time.sleep(0.5)  # Let gateway process the log out
                            online = False   # Force re-authentication
                            force_reauth = False
                        
                        if online:
                            if not state["is_online"]:
                                log_message(f"[+] Interface '{iface}' (IP: {ip}) is ONLINE.")
                            state["is_online"] = True
                            state["failures"] = 0
                            state["next_check"] = current_time + 5
                        else:
                            state["is_online"] = False
                            log_message(f"[*] Interface '{iface}' blocked. Authenticating...")

                            success = False

                            # Path 1: cached creds (~300ms, no cloud API)
                            if creds_cache:
                                success = do_login_cached(ip, gw, creds_cache)
                                if success:
                                    log_message(f"[+] Authenticated via cached credentials!")

                            # Path 2: fallback to cloud API (~1-3s)
                            if not success:
                                log_message(f"[*] Fetching fresh credentials from cloud API...")
                                success, new_creds = do_login_cloud(ip, gw)
                                if success:
                                    log_message(f"[+] Authenticated via cloud API (cached for next time).")
                                    save_cache(new_creds)
                                    with cache_lock:
                                        creds_cache.clear()
                                        creds_cache.update(new_creds)
                                else:
                                    log_message(f"[-] Cloud API authentication failed.")

                            if success:
                                state["failures"] = 0
                                state["is_online"] = True
                                state["last_auth_time"] = time.time()  # Reset proactive refresh timer
                                state["next_check"] = current_time + 5
                            else:
                                state["failures"] += 1
                                # Gaming Mode: No backoff! Retry instantly (every 1 second)
                                backoff = 1.0
                                log_message(f"[-] Retrying in {backoff}s...")
                                state["next_check"] = current_time + backoff
                    else:
                        state["next_check"] = current_time + 3

        except Exception as e:
            log_message(f"[-] Error in daemon loop: {e}")

        time.sleep(0.1)


if __name__ == "__main__":
    main()
