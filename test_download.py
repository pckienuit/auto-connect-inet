import os
import sys
import re
import time
import socket
import urllib.request
import urllib.parse
import subprocess

SSID_NAME = "INET - Free WiFi"
TEST_URL = "http://ipv4.download.thinkbroadband.com/10MB.zip"

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
        print(f"[-] Error running ipconfig: {e}")
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

class BoundHTTPConnection(urllib.request.http.client.HTTPConnection):
    def __init__(self, host, port=None, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None, blocksize=8192):
        super().__init__(host, port, timeout, source_address, blocksize)

class BoundHTTPHandler(urllib.request.HTTPHandler):
    def __init__(self, source_ip):
        super().__init__()
        self.source_ip = source_ip

    def http_open(self, req):
        def build(host, port=None, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None, blocksize=8192):
            return BoundHTTPConnection(host, port, timeout, (self.source_ip, 0), blocksize)
        return self.do_open(build, req)

def download_test(interface_name, source_ip):
    opener = urllib.request.build_opener(BoundHTTPHandler(source_ip))
    opener.addheaders = [('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')]
    
    print(f"\n[*] Starting download test bound to interface '{interface_name}' (IP: {source_ip})")
    print(f"[*] Downloading file: {TEST_URL}")
    print("[*] Press Ctrl+C to stop the test.\n")
    
    chunk_size = 1024 * 32  # 32KB chunks
    total_bytes = 0
    start_time = time.time()
    
    attempt = 1
    
    while True:
        try:
            req = urllib.request.Request(TEST_URL)
            with opener.open(req, timeout=5) as response:
                content_len = response.getheader('Content-Length')
                if content_len:
                    content_len = int(content_len)
                
                content_type = response.getheader('Content-Type') or ""
                if "text/html" in content_type.lower() or (content_len and content_len < 100000):
                    print(f"\n[!] Connection intercepted by captive portal (HTTP 302/Redirect). Waiting for daemon to auto-reconnect...")
                    time.sleep(3)
                    continue
                
                print(f"[+] Download started (Attempt {attempt}). Size: {content_len / (1024*1024):.2f} MB" if content_len else "[+] Download started...")
                
                last_report = time.time()
                bytes_in_interval = 0
                
                while True:
                    try:
                        chunk = response.read(chunk_size)
                    except (socket.timeout, socket.error) as e:
                        print(f"\n[!] Socket error during download: {e}. Reconnecting...")
                        break
                    
                    if not chunk:
                        print(f"\n[+] Finished downloading file. Restarting loop to continue testing stability...")
                        time.sleep(2)
                        break
                    
                    total_bytes += len(chunk)
                    bytes_in_interval += len(chunk)
                    
                    now = time.time()
                    if now - last_report >= 1.0:
                        speed = bytes_in_interval / (1024 * 1024 * (now - last_report)) # MB/s
                        elapsed = now - start_time
                        print(f"\rDownloaded: {total_bytes / (1024*1024):.2f} MB | Speed: {speed:.2f} MB/s | Running time: {elapsed:.0f}s", end="", flush=True)
                        bytes_in_interval = 0
                        last_report = now
                        
            attempt += 1
            
        except urllib.error.URLError as e:
            print(f"\n[!] Connection error: {e.reason}. Captive portal might be blocking. Retrying in 3 seconds...")
            time.sleep(3)
        except Exception as e:
            print(f"\n[-] Unexpected error: {e}. Retrying in 3 seconds...")
            time.sleep(3)

def main():
    interfaces = get_connected_inet_interfaces()
    if not interfaces:
        print(f"[-] No interfaces connected to '{SSID_NAME}' found.")
        sys.exit(1)
        
    # Use the first active interface connected to INET
    iface = interfaces[0]
    ip, gw = get_interface_details(iface)
    if not ip:
        print(f"[-] Could not find active IP for interface '{iface}'.")
        sys.exit(1)
        
    try:
        download_test(iface, ip)
    except KeyboardInterrupt:
        print("\n[*] Test stopped by user.")

if __name__ == "__main__":
    main()
