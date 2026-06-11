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
import select
import struct

SSID_NAME = "INET - Free WiFi"
LOCK_PORT = 49998
SOCKS_PORT = 1080
KEEPALIVE_INTERVAL = 1.0
KEEPALIVE_TIMEOUT = 0.5

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(SCRIPT_DIR, ".creds_cache.json")

creds_cache = {}
interface_pool = []  # list of {name, ip, gw, online, failures, next_check}
pool_lock = threading.Lock()


# ──── credential cache ────

def load_cache():
    global creds_cache
    try:
        with open(CACHE_FILE, 'r') as f:
            creds_cache = json.load(f)
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


# ──── low-level network ────

def get_interface_details(interface_name):
    try:
        res = subprocess.run("ipconfig", shell=True, capture_output=True, text=True)
        lines = res.stdout.splitlines()
        target = False
        ip = gw = None
        for line in lines:
            if re.search(rf"adapter\s+{re.escape(interface_name)}\s*:", line, re.IGNORECASE):
                target = True
                continue
            if target:
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
    except:
        return None, None


def get_inet_interfaces(target_ssid=SSID_NAME):
    try:
        res = subprocess.run("netsh wlan show interfaces", shell=True, capture_output=True, text=True)
        parts = res.stdout.split("Name                   :")
        results = []
        for part in parts[1:]:
            name = part.splitlines()[0].strip()
            state_m = re.search(r"State\s+:\s+(\w+)", part)
            ssid_m = re.search(r"SSID\s+:\s+(.+)", part)
            if state_m and ssid_m and state_m.group(1) == "connected" and ssid_m.group(1).strip() == target_ssid:
                results.append(name)
        return results
    except:
        return []


def http_get(bind_ip, gw, path="/login", timeout=3):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((bind_ip, 0))
    s.settimeout(timeout)
    try:
        s.connect((gw, 80))
        req = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {gw}\r\n"
            "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36\r\n"
            "Connection: close\r\n\r\n"
        )
        s.sendall(req.encode())
        res = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            res += chunk
        s.close()
        return res.decode('utf-8', errors='ignore')
    except:
        return ""


def http_post(bind_ip, gw, path, body, timeout=3):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((bind_ip, 0))
    s.settimeout(timeout)
    try:
        s.connect((gw, 80))
        req = (
            f"POST {path} HTTP/1.1\r\n"
            f"Host: {gw}\r\n"
            "Content-Type: application/x-www-form-urlencoded\r\n"
            f"Content-Length: {len(body)}\r\n"
            "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36\r\n"
            "Connection: close\r\n\r\n"
            f"{body}"
        )
        s.sendall(req.encode())
        res = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            res += chunk
        s.close()
        return res.decode('utf-8', errors='ignore')
    except:
        return ""


def check_internet(bind_ip):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((bind_ip, 0))
        s.settimeout(KEEPALIVE_TIMEOUT)
        s.connect(('detectportal.firefox.com', 80))
        req = (
            "GET /success.txt HTTP/1.1\r\n"
            "Host: detectportal.firefox.com\r\n"
            "User-Agent: Mozilla/5.0\r\n"
            "Connection: close\r\n\r\n"
        )
        s.sendall(req.encode())
        res = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            res += chunk
        s.close()
        return b"200 OK" in res and b"success" in res.lower()
    except:
        return False


# ──── interface authentication ────

def auth_interface(ip, gw):
    """Try to authenticate a single INET interface. Returns True/False."""
    # Path 1: cached credentials
    if creds_cache:
        body = urllib.parse.urlencode(creds_cache)
        http_post(ip, gw, "/login", body)
        if check_internet(ip):
            return True

    # Path 2: cloud API
    html = http_get(ip, gw)
    if not html:
        return False

    try:
        serial_m = re.search(r'id="serial"\s+value="([^"]*)"', html)
        cmac_m = re.search(r'id="client_mac"\s+value="([^"]*)"', html)
        cip_m = re.search(r'id="client_ip"\s+value="([^"]*)"', html)
        uurl_m = re.search(r'id="userurl"\s+value="([^"]*)"', html)
        lurl_m = re.search(r'id="login_url"\s+value="([^"]*)"', html)
        cid_m = re.search(r'id="chap-id"\s+value="([^"]*)"', html)
        chall_m = re.search(r'id="chap-challenge"\s+value="([^"]*)"', html)
        if not all([serial_m, cmac_m, cip_m, uurl_m, lurl_m, cid_m, chall_m]):
            return False
    except:
        return False

    params = urllib.parse.urlencode({
        'serial': serial_m.group(1), 'client_mac': cmac_m.group(1),
        'client_ip': cip_m.group(1), 'userurl': uurl_m.group(1),
        'login_url': lurl_m.group(1), 'chap_id': cid_m.group(1),
        'chap_challenge': chall_m.group(1)
    })
    login_ref = f"http://v1.awingconnect.vn/login?{params}"

    req = urllib.request.Request(
        "http://v1.awingconnect.vn/Home/VerifyUrl",
        data=b"",
        headers={'User-Agent': 'Mozilla/5.0', 'Referer': login_ref}
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except:
        return False

    form = data.get('captiveContext', {}).get('contentAuthenForm', '')
    if not form:
        return False

    try:
        username = re.search(r'name="username"\s+value="([^"]*)"', form).group(1)
        password = re.search(r'name="password"\s+value="([^"]*)"', form).group(1)
        dst = re.search(r'name="dst"\s+value="([^"]*)"', form).group(1)
        popup = re.search(r'name="popup"\s+value="([^"]*)"', form).group(1)
    except:
        return False

    new_creds = {'username': username, 'password': password, 'dst': dst, 'popup': popup}
    body = urllib.parse.urlencode(new_creds)
    http_post(ip, gw, "/login", body)

    if check_internet(ip):
        # Cache for future use
        creds_cache.clear()
        creds_cache.update(new_creds)
        save_cache(new_creds)
        return True
    return False


# ──── keepalive + reauth ────

def keepalive_worker(stop_event):
    """Background thread: ping every interface every 1s, re-auth if needed."""
    while not stop_event.is_set():
        with pool_lock:
            for iface in interface_pool:
                online = check_internet(iface['ip'])
                if not online:
                    iface['online'] = False
                    print(f"[!] '{iface['name']}' ({iface['ip']}) offline. Re-authenticating...")
                    ok = auth_interface(iface['ip'], iface['gw'])
                    if ok:
                        iface['online'] = True
                        print(f"[+] '{iface['name']}' re-authenticated.")
                    else:
                        print(f"[-] '{iface['name']}' auth failed.")
                elif not iface['online']:
                    iface['online'] = True
                    print(f"[+] '{iface['name']}' ({iface['ip']}) back online.")
        stop_event.wait(KEEPALIVE_INTERVAL)


def interface_scanner(stop_event):
    """Background thread: detect new INET interfaces joining the network."""
    known = set()
    while not stop_event.is_set():
        now = time.time()
        names = get_inet_interfaces()
        current = set(names)

        # Add new interfaces
        for name in current - known:
            ip, gw = get_interface_details(name)
            if ip and gw:
                print(f"[*] New INET interface detected: '{name}' ({ip})")
                with pool_lock:
                    # Check if already in pool (avoid dups)
                    if not any(x['name'] == name for x in interface_pool):
                        interface_pool.append({
                            'name': name, 'ip': ip, 'gw': gw,
                            'online': False, 'next_check': now
                        })
                # Try to auth immediately
                ok = auth_interface(ip, gw)
                with pool_lock:
                    for x in interface_pool:
                        if x['name'] == name:
                            x['online'] = ok
                if ok:
                    print(f"[+] '{name}' authenticated and added to pool.")
                else:
                    print(f"[-] '{name}' auth failed, will retry.")
            else:
                print(f"[*] New INET interface '{name}' — no IP yet, will retry.")

        # Remove stale interfaces
        for name in known - current:
            print(f"[*] INET interface gone: '{name}'")
            with pool_lock:
                interface_pool[:] = [x for x in interface_pool if x['name'] != name]

        known = current
        stop_event.wait(5)


# ──── SOCKS5 proxy ────

SOCKS_CMD_CONNECT = 0x01
SOCKS_ATYP_IPV4 = 0x01
SOCKS_ATYP_DOMAIN = 0x03
SOCKS_ATYP_IPV6 = 0x04

pool_index = 0
pool_index_lock = threading.Lock()


def pick_interface():
    """Round-robin pick an online interface."""
    global pool_index
    with pool_lock:
        online = [x for x in interface_pool if x['online']]
    if not online:
        return None
    with pool_index_lock:
        idx = pool_index % len(online)
        pool_index += 1
    return online[idx]


def handle_socks5(client, addr):
    """Handle a single SOCKS5 client connection."""
    try:
        # Greeting
        data = client.recv(3)
        if len(data) < 3 or data[0] != 0x05:
            return
        nmethods = data[1]
        methods = client.recv(nmethods)
        if 0x00 not in methods:
            client.send(b'\x05\xff')
            return
        client.send(b'\x05\x00')  # No auth

        # Request
        data = client.recv(4)
        if len(data) < 4 or data[0] != 0x05 or data[1] != SOCKS_CMD_CONNECT:
            return
        atyp = data[3]

        if atyp == SOCKS_ATYP_IPV4:
            host = socket.inet_ntoa(client.recv(4))
        elif atyp == SOCKS_ATYP_DOMAIN:
            dlen = client.recv(1)[0]
            host = client.recv(dlen).decode()
        elif atyp == SOCKS_ATYP_IPV6:
            host = socket.inet_ntop(socket.AF_INET6, client.recv(16))
        else:
            return
        port = struct.unpack('>H', client.recv(2))[0]

        # Pick interface and connect
        iface = pick_interface()
        if not iface:
            client.send(b'\x05\x01\x00\x01\x00\x00\x00\x00\x00\x00')
            return

        remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        remote.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        remote.bind((iface['ip'], 0))
        remote.settimeout(10)

        try:
            remote.connect((host, port))
        except:
            client.send(b'\x05\x04\x00\x01\x00\x00\x00\x00\x00\x00')
            return

        # Send success response
        bind_addr = remote.getsockname()
        resp = b'\x05\x00\x00\x01'
        resp += socket.inet_aton(bind_addr[0])
        resp += struct.pack('>H', bind_addr[1])
        client.send(resp)

        # Relay
        remote.setblocking(True)
        client.setblocking(True)
        while True:
            r, _, _ = select.select([client, remote], [], [], 60)
            if not r:
                break
            for sock in r:
                data = sock.recv(32768)
                if not data:
                    raise ConnectionError
                if sock is client:
                    remote.sendall(data)
                else:
                    client.sendall(data)
    except:
        pass
    finally:
        try:
            client.close()
        except:
            pass


def socks_server(stop_event):
    """Main SOCKS5 proxy server thread."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind(('127.0.0.1', SOCKS_PORT))
        server.listen(50)
        server.settimeout(1.0)
        print(f"[*] SOCKS5 proxy listening on 127.0.0.1:{SOCKS_PORT}")
    except Exception as e:
        print(f"[-] Cannot start SOCKS proxy on port {SOCKS_PORT}: {e}")
        return

    while not stop_event.is_set():
        try:
            client, addr = server.accept()
            t = threading.Thread(target=handle_socks5, args=(client, addr), daemon=True)
            t.start()
        except socket.timeout:
            continue
        except:
            break


# ──── main ────

def main():
    # Single instance lock
    try:
        lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lock.bind(('127.0.0.1', LOCK_PORT))
        lock.listen(1)
    except:
        print("[*] Another bonding daemon is already running. Exiting.")
        sys.exit(0)

    load_cache()

    stop = threading.Event()
    atexit.register(lambda: stop.set())

    # Start interface scanner (finds new WiFi adapters)
    scanner = threading.Thread(target=interface_scanner, args=(stop,), daemon=True)
    scanner.start()

    # Wait a moment for initial discovery
    time.sleep(3)

    # Start keepalive thread
    keepalive = threading.Thread(target=keepalive_worker, args=(stop,), daemon=True)
    keepalive.start()

    # Start SOCKS5 proxy
    socks = threading.Thread(target=socks_server, args=(stop,), daemon=True)
    socks.start()

    print(f"[*] INET Bonding Daemon — pooling INET interfaces via SOCKS5 :{SOCKS_PORT}")
    print(f"[*] Set your browser/system proxy to 127.0.0.1:{SOCKS_PORT} (SOCKS5)")

    # Block forever
    try:
        while not stop.is_set():
            with pool_lock:
                online_count = sum(1 for x in interface_pool if x['online'])
                total = len(interface_pool)
            if total > 0:
                status = f"[*] Interfaces: {online_count}/{total} online | Proxy: :{SOCKS_PORT}"
            else:
                status = f"[*] Waiting for INET interfaces... | Proxy: :{SOCKS_PORT}"
            print(f"\r{status:<60}", end='', flush=True)
            stop.wait(5)
    except KeyboardInterrupt:
        print("\n[*] Shutting down.")
        stop.set()


if __name__ == "__main__":
    main()
