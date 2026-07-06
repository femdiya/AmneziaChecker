import os
import subprocess
import ctypes
import urllib.request
import json
import time
import re
import platform
import shutil
import tempfile

BIN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.cache', 'bin')
CACHE_INFO_FILE = os.path.join(BIN_DIR, 'version.json')

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def get_system_arch():
    machine = platform.machine().lower()
    if machine in ['amd64', 'x86_64']:
        return 'amd64'
    elif machine in ['arm64', 'aarch64']:
        return 'arm64'
    else:
        return 'x86'

def ensure_binaries():
    if not os.path.exists(BIN_DIR):
        os.makedirs(BIN_DIR, exist_ok=True)
    
    print("Checking for AmneziaWG CLI updates...")
    
    # Check latest version
    try:
        req = urllib.request.Request("https://api.github.com/repos/amnezia-vpn/amneziawg-windows-client/releases/latest")
        with urllib.request.urlopen(req, timeout=10) as response:
            release_data = json.loads(response.read().decode())
    except Exception as e:
        print(f"Failed to check updates: {e}")
        if os.path.exists(os.path.join(BIN_DIR, 'amneziawg.exe')):
            print("Using cached binaries.")
            return
        else:
            raise Exception("No cached binaries and failed to download.")
    
    latest_version = release_data['tag_name']
    
    # Check current version
    current_version = None
    if os.path.exists(CACHE_INFO_FILE):
        try:
            with open(CACHE_INFO_FILE, 'r') as f:
                info = json.load(f)
                current_version = info.get('version')
        except:
            pass
            
    if current_version == latest_version and os.path.exists(os.path.join(BIN_DIR, 'amneziawg.exe')) and os.path.exists(os.path.join(BIN_DIR, 'awg.exe')):
        print(f"AmneziaWG binaries are up to date (v{latest_version}).")
        return
        
    print(f"Downloading AmneziaWG v{latest_version}...")
    arch = get_system_arch()
    
    download_url = None
    for asset in release_data.get('assets', []):
        if arch in asset['name'] and asset['name'].endswith('.msi') and 'windows7' not in asset['name']:
            download_url = asset['browser_download_url']
            break
            
    if not download_url:
        raise Exception(f"Could not find a suitable MSI for architecture {arch}")
        
    msi_path = os.path.join(BIN_DIR, 'amneziawg.msi')
    urllib.request.urlretrieve(download_url, msi_path)
    
    print("Extracting MSI...")
    extract_dir = os.path.join(BIN_DIR, 'extracted')
    if os.path.exists(extract_dir):
        shutil.rmtree(extract_dir)
    
    # Execute msiexec to extract
    cmd = f'msiexec /a "{msi_path}" /qb TARGETDIR="{extract_dir}"'
    subprocess.run(cmd, check=True, shell=True)
    
    # Find the executables
    amneziawg_exe = None
    awg_exe = None
    wintun_dll = None
    
    for root, _, files in os.walk(extract_dir):
        for file in files:
            if file.lower() == 'amneziawg.exe':
                amneziawg_exe = os.path.join(root, file)
            elif file.lower() == 'awg.exe':
                awg_exe = os.path.join(root, file)
            elif file.lower() == 'wintun.dll':
                wintun_dll = os.path.join(root, file)
                
    if not amneziawg_exe or not awg_exe or not wintun_dll:
        raise Exception("Failed to locate required binaries (amneziawg.exe, awg.exe, or wintun.dll) inside the extracted MSI")
        
    shutil.copy2(amneziawg_exe, os.path.join(BIN_DIR, 'amneziawg.exe'))
    shutil.copy2(awg_exe, os.path.join(BIN_DIR, 'awg.exe'))
    shutil.copy2(wintun_dll, os.path.join(BIN_DIR, 'wintun.dll'))
    
    # Cleanup
    os.remove(msi_path)
    shutil.rmtree(extract_dir)
    
    with open(CACHE_INFO_FILE, 'w') as f:
        json.dump({'version': latest_version}, f)
        
    print("Binaries updated successfully.")

class WGRunner:
    def __init__(self):
        self.amneziawg_path = os.path.join(BIN_DIR, 'amneziawg.exe')
        self.awg_path = os.path.join(BIN_DIR, 'awg.exe')
        
    def install_tunnel(self, conf_path):
        subprocess.run([self.amneziawg_path, '/installtunnelservice', conf_path], check=True)
        
    def uninstall_tunnel(self, tunnel_name):
        subprocess.run([self.amneziawg_path, '/uninstalltunnelservice', tunnel_name], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
    def get_latest_handshake(self, tunnel_name):
        try:
            result = subprocess.run([self.awg_path, 'show', tunnel_name, 'latest-handshakes'], 
                                    capture_output=True, text=True, check=True)
            output = result.stdout.strip()
            if output:
                # Format is "public_key\ttimestamp"
                parts = output.split('\t')
                if len(parts) >= 2:
                    ts = int(parts[1])
                    return ts
            return 0
        except subprocess.CalledProcessError:
            return 0
            
    def wait_for_handshake(self, tunnel_name, timeout=12):
        start_time = time.time()
        while time.time() - start_time < timeout:
            ts = self.get_latest_handshake(tunnel_name)
            if ts > 0:
                return True
            time.sleep(1)
        return False
        
    def dump_log(self):
        try:
            result = subprocess.run([self.amneziawg_path, '/dumplog'], capture_output=True, text=True, check=False)
            return result.stdout
        except Exception as e:
            return f"Failed to dump log: {e}"

    def check_traffic(self, ips, retries=1, delay=1.0):
        """Pings a list of IPs and returns True if ANY ping succeeds."""
        for attempt in range(retries):
            for ip in ips:
                # -n 1 = 1 ping, -w 1000 = 1000ms timeout
                result = subprocess.run(['ping', '-n', '1', '-w', '1000', ip], capture_output=True, text=True)
                if result.returncode == 0:
                    return True
            if attempt < retries - 1:
                time.sleep(delay)
        return False
