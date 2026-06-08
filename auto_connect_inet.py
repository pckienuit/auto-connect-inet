import os
import sys
import re
import time
import socket
import json
import urllib.request
import urllib.parse
import subprocess

SSID_NAME = "INET - Free WiFi"
LOCK_PORT = 49999
BASE_CHECK_INTERVAL = 10  # Check every 10 seconds for online interfaces
BACKOFF_MAX = 300  # Max backoff of 5 minutes

# Keep track of interface states to prevent spam
# structure: { interface_name: { "failures": 0, "next_check": 0, "is_online": False } }
interface_states = {}

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
        print(f"[-] Error running ipconfig for {interface_name}: {e}")
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
        print(f"[-] Error listing connected interfaces: {e}")
        return []

def query_local_gateway(bind_ip, gateway_ip):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((bind_ip, 0))
    s.settimeout(5)
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
    except Exception as e:
        # Silently return empty string on error to avoid console spam
        return ""

def post_local_gateway(bind_ip, gateway_ip, post_data):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((bind_ip, 0))
    s.settimeout(5)
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
    except Exception as e:
        return ""

def check_internet(bind_ip):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((bind_ip, 0))
        s.settimeout(3)
        s.connect(('detectportal.firefox.com', 80))
        req = (
            "GET /success.txt HTTP/1.1\r\n"
            "Host: detectportal.firefox.com\r\n"
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
        response_text = res.decode('utf-8', errors='ignore')
        if "HTTP/1.1 200 OK" in response_text and "success" in response_text.lower():
            return True
        return False
    except Exception:
        return False

def do_login(ip, gw):
    html = query_local_gateway(ip, gw)
    if not html:
        return False
    
    try:
        serial_m = re.search(r'id="serial"\s+value="([^"]*)"', html)
        client_mac_m = re.search(r'id="client_mac"\s+value="([^"]*)"', html)
        client_ip_m = re.search(r'id="client_ip"\s+value="([^"]*)"', html)
        userurl_m = re.search(r'id="userurl"\s+value="([^"]*)"', html)
        login_url_m = re.search(r'id="login_url"\s+value="([^"]*)"', html)
        chap_id_m = re.search(r'id="chap-id"\s+value="([^"]*)"', html)
        chap_challenge_m = re.search(r'id="chap-challenge"\s+value="([^"]*)"', html)

        if not all([serial_m, client_mac_m, client_ip_m, userurl_m, login_url_m, chap_id_m, chap_challenge_m]):
            return False

        serial = serial_m.group(1)
        client_mac = client_mac_m.group(1)
        client_ip = client_ip_m.group(1)
        userurl = userurl_m.group(1)
        login_url = login_url_m.group(1)
        chap_id = chap_id_m.group(1)
        chap_challenge = chap_challenge_m.group(1)
    except Exception:
        return False

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
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode('utf-8'))
    except Exception:
        return False

    form_html = res_data.get('captiveContext', {}).get('contentAuthenForm', '')
    if not form_html:
        return False

    try:
        username = re.search(r'name="username"\s+value="([^"]*)"', form_html).group(1)
        password = re.search(r'name="password"\s+value="([^"]*)"', form_html).group(1)
        dst = re.search(r'name="dst"\s+value="([^"]*)"', form_html).group(1)
        popup = re.search(r'name="popup"\s+value="([^"]*)"', form_html).group(1)
    except Exception:
        return False

    post_params = {
        'username': username,
        'password': password,
        'dst': dst,
        'popup': popup
    }
    post_data = urllib.parse.urlencode(post_params)
    
    post_local_gateway(ip, gw, post_data)
    
    return check_internet(ip)

def main():
    try:
        lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lock_socket.bind(('127.0.0.1', LOCK_PORT))
        lock_socket.listen(1)
    except socket.error:
        print("[*] Another instance of auto_connect_inet.py is already running. Exiting.")
        sys.exit(0)

    print(f"[*] Robust Dynamic Daemon started. Monitoring SSID '{SSID_NAME}'...")

    while True:
        try:
            current_time = time.time()
            inet_interfaces = get_connected_inet_interfaces()
            
            # Clean up states for disconnected interfaces
            for iface in list(interface_states.keys()):
                if iface not in inet_interfaces:
                    del interface_states[iface]

            for iface in inet_interfaces:
                # Initialize state if not exists
                if iface not in interface_states:
                    interface_states[iface] = {
                        "failures": 0,
                        "next_check": 0,
                        "is_online": False
                    }

                state = interface_states[iface]
                
                # Check if it's time to check this interface
                if current_time >= state["next_check"]:
                    ip, gw = get_interface_details(iface)
                    if ip and gw:
                        online = check_internet(ip)
                        if online:
                            if not state["is_online"]:
                                print(f"[+] Interface '{iface}' (IP: {ip}) is ONLINE.")
                            state["is_online"] = True
                            state["failures"] = 0
                            # Check again in 30 seconds if online
                            state["next_check"] = current_time + 30
                        else:
                            state["is_online"] = False
                            print(f"[*] Interface '{iface}' (IP: {ip}) is blocked. Authenticating...")
                            
                            success = do_login(ip, gw)
                            if success:
                                print(f"[+] Interface '{iface}' successfully authenticated.")
                                state["failures"] = 0
                                state["is_online"] = True
                                state["next_check"] = current_time + 30
                            else:
                                state["failures"] += 1
                                # Exponential backoff for failures: 10s, 20s, 40s, 80s, 160s, up to 300s
                                backoff = min(10 * (2 ** (state["failures"] - 1)), BACKOFF_MAX)
                                print(f"[-] Authentication failed for '{iface}'. Retrying in {backoff} seconds...")
                                state["next_check"] = current_time + backoff
                    else:
                        # No IP/Gateway, check again in 5 seconds
                        state["next_check"] = current_time + 5
                        
        except Exception as e:
            print(f"[-] Error in daemon loop: {e}")
            
        time.sleep(1)

if __name__ == "__main__":
    main()
