import os
import sys
import re
import socket
import time
import subprocess
import threading

TARGET_HOST = "1.1.1.1"  # Cloudflare DNS (TCP Port 53 is open and extremely fast)
TARGET_PORT = 53
PING_INTERVAL = 0.2     # 200ms (Gaming rate)
TIMEOUT = 0.5           # 500ms timeout for packet loss detection
SSID_NAME = "INET - Free WiFi"

def get_connected_inet_ip():
    """Finds the IP of the interface connected to INET - Free WiFi."""
    try:
        res = subprocess.run("netsh wlan show interfaces", shell=True, capture_output=True, text=True)
        parts = res.stdout.split("Name                   :")
        for part in parts[1:]:
            lines = part.splitlines()
            name = lines[0].strip()
            state_match = re.search(r"State\s+:\s+(\w+)", part)
            ssid_match = re.search(r"SSID\s+:\s+(.+)", part)
            
            state = state_match.group(1) if state_match else ""
            current_ssid = ssid_match.group(1).strip() if ssid_match else ""
            
            if state == "connected" and current_ssid == SSID_NAME:
                # Find IP from ipconfig
                ip_res = subprocess.run("ipconfig", shell=True, capture_output=True, text=True)
                ip_lines = ip_res.stdout.splitlines()
                target_section = False
                header_pattern = rf"adapter\s+{re.escape(name)}\s*:"
                for line in ip_lines:
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
                                return m.group(1), name
        return None, None
    except Exception:
        return None, None

def main():
    bind_ip, iface_name = get_connected_inet_ip()
    
    print("==========================================================")
    print("      INET WiFi Stability & Jitter Monitor (Gaming Test)  ")
    print("==========================================================")
    
    if bind_ip:
        print(f"[*] Monitoring interface: {iface_name}")
        print(f"[*] Bound to Local IP: {bind_ip}")
    else:
        print("[!] No active adapter connected to 'INET - Free WiFi' found.")
        print("[*] Testing using default OS routing...")
        bind_ip = None
        
    print(f"[*] Ping Target: {TARGET_HOST}:{TARGET_PORT} (TCP)")
    print(f"[*] Rate: 1 ping every {int(PING_INTERVAL * 1000)}ms | Timeout: {int(TIMEOUT * 1000)}ms")
    print("[*] Press Ctrl+C to stop and view final statistics.")
    print("==========================================================\n")

    # Statistics
    total_sent = 0
    total_received = 0
    latencies = []
    outages = []
    
    current_outage_start = None
    consecutive_failures = 0
    
    # Real-time indicators
    print("Legend: [.] Success  [X] Timeout/Drop  [!] Outage Recovered")
    print("Running monitor...\n")
    
    try:
        while True:
            t0 = time.time()
            success = False
            latency = 0.0
            
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                if bind_ip:
                    # Bind to the target IP so we only measure latency on this specific interface
                    s.bind((bind_ip, 0))
                s.settimeout(TIMEOUT)
                
                # Measure connection handshake time
                start_conn = time.time()
                s.connect((TARGET_HOST, TARGET_PORT))
                latency = (time.time() - start_conn) * 1000 # convert to ms
                s.close()
                success = True
            except Exception:
                success = False

            total_sent += 1
            
            if success:
                total_received += 1
                latencies.append(latency)
                
                # Check if we just recovered from an outage
                if current_outage_start is not None:
                    outage_duration = time.time() - current_outage_start
                    outages.append(outage_duration)
                    sys.stdout.write(f"\n[!] OUTAGE RECOVERED: lasted {outage_duration:.2f}s ({consecutive_failures} drops)\n")
                    sys.stdout.flush()
                    current_outage_start = None
                    consecutive_failures = 0
                
                # Print dot indicator with latency
                sys.stdout.write(".")
                sys.stdout.flush()
            else:
                consecutive_failures += 1
                if current_outage_start is None:
                    current_outage_start = time.time()
                    sys.stdout.write("\nX")
                else:
                    sys.stdout.write("X")
                sys.stdout.flush()

            # Sleep to maintain ping interval
            elapsed = time.time() - t0
            sleep_time = max(0.0, PING_INTERVAL - elapsed)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\n\n==========================================================")
        print("                  FINAL STABILITY REPORT                  ")
        print("==========================================================")
        
        loss_pct = ((total_sent - total_received) / total_sent * 100) if total_sent > 0 else 100
        
        print(f"Packets: Sent = {total_sent}, Received = {total_received}")
        print(f"Packet Loss = {loss_pct:.2f}%")
        
        if latencies:
            min_lat = min(latencies)
            max_lat = max(latencies)
            avg_lat = sum(latencies) / len(latencies)
            
            # Calculate Jitter (Average difference between consecutive latencies)
            diffs = [abs(latencies[i] - latencies[i-1]) for i in range(1, len(latencies))]
            jitter = (sum(diffs) / len(diffs)) if diffs else 0.0
            
            print(f"Latency: Min = {min_lat:.1f}ms, Max = {max_lat:.1f}ms, Avg = {avg_lat:.1f}ms")
            print(f"Jitter (RTT variation): {jitter:.1f}ms (lower is better for gaming)")
            
            # Evaluate suitability for fighting games
            print("----------------------------------------------------------")
            print("Gaming Evaluation:")
            if loss_pct > 2.0:
                print("[-] Status: BAD. High packet loss will cause rollbacks or disconnects.")
            elif jitter > 15.0:
                print("[-] Status: JITTERY. High jitter will cause inconsistent game speed.")
            elif avg_lat > 80.0:
                print("[!] Status: PLAYABLE BUT LAGGY (High Base Latency).")
            else:
                print("[+] Status: EXCELLENT! Stable latency and low loss.")
        else:
            print("No packets received. Internet connection is down.")
            
        if outages:
            print(f"Total Outages Detected: {len(outages)}")
            print(f"Max Outage Duration: {max(outages):.2f}s")
            print(f"Avg Outage Recovery Time: {sum(outages)/len(outages):.2f}s")
        else:
            if total_sent - total_received > 0 and current_outage_start is not None:
                duration = time.time() - current_outage_start
                print(f"Currently in an active outage for {duration:.2f}s")
            else:
                print("No network outages detected (100% micro-stable).")
                
        print("==========================================================")

if __name__ == "__main__":
    main()
