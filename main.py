import os
import sys
import ctypes
import argparse
import time
import csv
import traceback
import tempfile
import tkinter as tk
from tkinter import filedialog
import datetime
import socket

class Logger(object):
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log = open(filename, "a", encoding="utf-8")
        
    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()

    def flush(self):
        self.terminal.flush()
        self.log.flush()

from config_parser import WGConfig
from wg_runner import WGRunner, ensure_binaries, is_admin

def parse_range_list(value_str: str) -> list:
    results = set()
    for part in str(value_str).split(','):
        part = part.strip()
        if not part: continue
        if '-' in part:
            try:
                start, end = part.split('-', 1)
                results.update(range(int(start.strip()), int(end.strip()) + 1))
            except ValueError:
                pass
        else:
            try:
                results.add(int(part))
            except ValueError:
                results.add(part)
    try:
        return sorted(list(results))
    except TypeError:
        return list(results)

import itertools

def generate_trials_from_config(manual_params):
    from protocol_masker import generate_dns_mimic
    
    # Create a case-insensitive lookup dictionary
    params_lower = {k.lower(): v for k, v in manual_params.items()}
    
    keys = ['Jc', 'Jmin', 'Jmax', 'S1', 'S2', 'S3', 'S4', 'H1', 'H2', 'H3', 'H4']
    parsed_lists = []
    for k in keys:
        val = params_lower.get(k.lower(), '0')
        parsed_lists.append(parse_range_list(str(val)))
        
    mimic_dns = params_lower.get('mimic_dns', 'no').lower() in ['yes', 'y', 'true', '1']
    obfuscation_domain = params_lower.get('obfuscation_domain', 'www.yahoo.com')
    
    for combination in itertools.product(*parsed_lists):
        params = dict(zip(keys, combination))
        
        # Jmax must be >= Jmin
        if params.get('Jmax', 0) < params.get('Jmin', 0):
            continue
            
        if mimic_dns:
            params['I1'] = generate_dns_mimic(obfuscation_domain)
            
        trial_name = f"Sweep_Jc{params['Jc']}_Jmin{params['Jmin']}_Jmax{params['Jmax']}"
        yield trial_name, params

def request_elevation():
    print("Admin rights required. Attempting to elevate...")
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    sys.exit()

def get_file_picker():
    root = tk.Tk()
    root.withdraw() # Hide main window
    file_path = filedialog.askopenfilename(
        title="Select WireGuard Configuration",
        filetypes=[("WireGuard config files", "*.conf"), ("All files", "*.*")]
    )
    return file_path

def main():
    if not os.path.exists("Logs"):
        os.makedirs("Logs")
    log_filename = os.path.join("Logs", f"awg_finder_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    sys.stdout = Logger(log_filename)
    sys.stderr = sys.stdout

    parser = argparse.ArgumentParser(description="AmneziaWG Obfuscation Parameter Finder")
    parser.add_argument("config", nargs="?", help="Path to base WireGuard .conf file")
    parser.add_argument("--dry-run", action="store_true", help="Print trials without executing them")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between trials in seconds")
    parser.add_argument("-d", "--debug", action="store_true", help="Print AmneziaWG logs for each trial")
    args = parser.parse_args()

    print(f"Command line arguments: {' '.join(sys.argv[1:])}")

    if not args.dry_run and not is_admin():
        request_elevation()
        return

    conf_path = args.config
    if not conf_path:
        print("No configuration file provided. Opening file picker...")
        conf_path = get_file_picker()
        if not conf_path:
            print("No file selected. Exiting.")
            sys.exit(0)

    if not os.path.exists(conf_path):
        print(f"Error: File '{conf_path}' not found.")
        sys.exit(1)

    print("--- AmneziaWG Obfuscation Parameter Finder ---")
    
    if not args.dry_run:
        try:
            ensure_binaries()
        except Exception as e:
            print(f"Error ensuring binaries: {e}")
            sys.exit(1)

    print(f"\nParsing config: {conf_path}")
    base_config = WGConfig.parse(conf_path)

    runner = WGRunner() if not args.dry_run else None



    log_file = "trials_log.csv"
    best_trial = None
    best_handshake_time = float('inf')
    winning_params = None

    print(f"\nReading configuration from config.cfg...")
    try:
        manual_params = {}
        with open("config.cfg", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'): continue
                if '=' in line:
                    k, v = [x.strip() for x in line.split('=', 1)]
                    manual_params[k] = v
        
        # Parse IPs from config
        params_lower = {k.lower(): v for k, v in manual_params.items()}
        config_ips_str = params_lower.get('ips', '')
        config_domains_str = params_lower.get('domains', '')
        
        ping_targets = []
        for ip in config_ips_str.split(','):
            ip = ip.strip()
            if ip and ip not in ping_targets: ping_targets.append(ip)
            
        for domain in config_domains_str.split(','):
            domain = domain.strip()
            if domain and domain not in ping_targets: ping_targets.append(domain)
                    
        if not ping_targets:
            ping_targets = ['1.1.1.1', '8.8.8.8']
            
        print(f"Will verify traffic by pinging: {', '.join(ping_targets)}")
        
        trials = list(generate_trials_from_config(manual_params))
        print(f"\nLoaded {len(trials)} trials from config. Beginning sweep...\n")
    except Exception as e:
        print(f"Error parsing config.cfg: {e}")
        sys.exit(1)

    with open(log_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Trial Name', 'Jc', 'Jmin', 'Jmax', 'I1', 'Handshake Success', 'Ping Success'])

    trial_idx = 0
    try:
        for trial_name, params in trials:
            trial_idx += 1
            print(f"Trial {trial_idx}/{len(trials)}: {trial_name}")
            
            if args.dry_run:
                print(f"  Params: {params}")
                continue

            # We use a specific, predictable name for the trial
            # Use temp directory so we don't clutter
            temp_conf_fd, temp_conf_path = tempfile.mkstemp(prefix="awgtest_", suffix=".conf", dir=".")
            os.close(temp_conf_fd)
            
            tunnel_name = os.path.splitext(os.path.basename(temp_conf_path))[0]
            
            base_config.write_variant(temp_conf_path, params, testing_mode=True)

            handshake_ok = False
            ping_ok = False
            
            try:
                print(f"  Installing service {tunnel_name}...")
                runner.install_tunnel(temp_conf_path)
                
                start_wait = time.time()
                handshake_ok = False
                ping_ok = False
                
                for retry in range(1, 4):
                    print(f"  Handshake attempt {retry}/3 (waiting up to 5s)...")
                    
                    # WireGuard automatically fires a new handshake packet every 5 seconds if unanswered.
                    # Waiting 5s per loop perfectly aligns with its internal retry timer.
                    hs_ok = runner.wait_for_handshake(tunnel_name, timeout=5)
                    
                    if hs_ok:
                        print(f"  Handshake SUCCESS on attempt {retry}.")
                        handshake_ok = True
                        
                        print(f"  Verifying traffic (up to 8s)...")
                        if runner.check_traffic(ping_targets, retries=8, delay=1.0):
                            print(f"  Traffic verification SUCCESS.")
                            ping_ok = True
                        else:
                            print(f"  Traffic verification FAILED.")
                        break
                    else:
                        print(f"  Handshake FAILED on attempt {retry}.")
                    
                elapsed = time.time() - start_wait
                
                if handshake_ok and ping_ok:
                    if elapsed < best_handshake_time:
                        best_handshake_time = elapsed
                        best_trial = trial_name
                        winning_params = params

                if args.debug:
                    print(f"  AmneziaWG log dump:")
                    print("-" * 40)
                    print(runner.dump_log().strip())
                    print("-" * 40)
                    
            except Exception as e:
                print(f"  Error during trial: {e}")
                traceback.print_exc()
            finally:
                # Cleanup
                print(f"  Uninstalling service...")
                runner.uninstall_tunnel(tunnel_name)
                # Small wait to ensure service is fully gone before deleting file
                time.sleep(1)
                try:
                    os.remove(temp_conf_path)
                except Exception as e:
                    print(f"  Failed to remove temporary config: {e}")

            # Write log
            with open(log_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    trial_name, 
                    params.get('Jc', ''), params.get('Jmin', ''), params.get('Jmax', ''), params.get('I1', ''),
                    handshake_ok, ping_ok
                ])

            if trial_idx < len(trials):
                print(f"  Waiting {args.delay}s before next trial...\n")
                time.sleep(args.delay)

    except KeyboardInterrupt:
        print("\nSweep interrupted by user.")
    finally:
        print("\n--- Sweep Completed ---")
        if not args.dry_run:
            if best_trial:
                print(f"\nWINNER: {best_trial} (Handshake time: {best_handshake_time:.1f}s)")
                
                import re
                safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', best_trial).lower()
                
                results_dir = "results"
                if not os.path.exists(results_dir):
                    os.makedirs(results_dir)
                    
                run_num = 1
                while os.path.exists(os.path.join(results_dir, f"run{run_num}")):
                    run_num += 1
                
                run_dir = os.path.join(results_dir, f"run{run_num}")
                os.makedirs(run_dir)
                
                winning_path = os.path.join(run_dir, f"{safe_name}.conf")
                base_config.write_winning(winning_path, winning_params)
                print(f"Winning configuration exported to: {winning_path}")
            else:
                print("\nNO WORKING CONFIGURATION FOUND.")

if __name__ == "__main__":
    main()
