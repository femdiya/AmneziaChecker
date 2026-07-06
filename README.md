# AmneziaWG Obfuscation Parameter Finder

A Windows CLI tool that methodically tests AmneziaWG obfuscation parameters to find a profile that bypasses DPI (Deep Packet Inspection) for a given WireGuard endpoint.

## Features

- **Automated sweep** — tests all combinations of obfuscation parameters defined in `config.cfg`.
- **Zero dependencies** — uses only the Python standard library.
- **Auto-downloads binaries** — fetches and caches the latest `amneziawg.exe` / `awg.exe` on first run.
- **Handshake + connectivity check** — verifies both a successful handshake and real traffic (ICMP ping).
- **Safe routing** — applies localized routes so system traffic isn't hijacked during tests.
- **Ready-to-use output** — exports a `winning.conf` when a working profile is found.

## Requirements

- Windows 10 / 11 (x64 or ARM64)
- Python 3.8+

## Quick Start

1. Copy `config.cfg.example` to `config.cfg` and adjust the parameter ranges you want to sweep.

2. Open an **Administrator** Command Prompt or PowerShell (required for installing the temporary Windows service).
   > The script will auto-prompt for elevation if run without admin rights.

3. Run:
   ```cmd
   python main.py
   ```
   A file-picker dialog will appear for you to select your base WireGuard `.conf` file, or pass it directly:
   ```cmd
   python main.py path\to\your_config.conf
   ```

4. Preview the test matrix without making system changes:
   ```cmd
   python main.py path\to\your_config.conf --dry-run
   ```

## Configuration (`config.cfg`)

The sweep parameters are defined in `config.cfg`. Each parameter accepts a **single value**, a **comma-separated list**, or a **range** (`min-max`).

```ini
Jc   = 3, 4, 5
JMin = 10-50
JMax = 50, 100

Mimic_DNS = Yes
Obfuscation_Domain = www.yahoo.com
```

See [`config.cfg.example`](config.cfg.example) for all available options and documentation.

## Output

| Path | Description |
|---|---|
| `trials_log.csv` | Log of every tested combination and its result. |
| `results/` | Contains generated `.conf` files for each tested parameter combination, organized by run. |
| `Logs/` | Timestamped log files with detailed output from each run. |

## A Note on DPI Bypass

Parameter tuning defeats **signature-based** DPI (WireGuard blocked because it *looks like* WireGuard). It does **not** defeat **destination-based** blocking (censor allowlists specific providers/ASNs and throttles everything else).

If a full sweep produces zero successful handshakes, try a server on a different hosting provider — packet obfuscation cannot fix IP-level blocking.

## License

This project is licensed under the [MIT License](LICENSE).
