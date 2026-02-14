#!/usr/bin/env python3

"""
Health check for My Toolkit services and configuration.

Verifies that all components are working correctly:
- Proxy configuration and connectivity
- Torrent manager setup
- Service status
- Network connectivity
"""

import argparse
import sys
import subprocess
from pathlib import Path
from typing import Dict, List
import json

try:
    import requests
except ImportError:
    print("Error: requests is not installed")
    sys.exit(1)

try:
    from toolkit_utils import ProxyConfig, SSLConfig
except ImportError:
    print("Warning: toolkit_utils not available")
    ProxyConfig = None
    SSLConfig = None


class HealthCheck:
    """Comprehensive health check for My Toolkit"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results = []
        self.warnings = []
        self.errors = []

    def check(self, name: str, func, *args, **kwargs) -> bool:
        """
        Run a health check and record result

        Args:
            name: Check name
            func: Function to run
            *args, **kwargs: Arguments for function

        Returns:
            True if check passed
        """
        try:
            result = func(*args, **kwargs)
            if result:
                self.results.append({"name": name, "status": "✓ PASS", "message": result if isinstance(result, str) else ""})
                # Always print results, verbose adds extra detail
                msg = result if isinstance(result, str) else 'OK'
                print(f"  ✓ {name}: {msg}")
                return True
            else:
                self.warnings.append({"name": name, "status": "⚠ WARN", "message": "Check returned false"})
                print(f"  ⚠ {name}: Not configured")
                return False
        except Exception as e:
            self.errors.append({"name": name, "status": "✗ FAIL", "message": str(e)})
            if self.verbose:
                # Verbose shows full error message
                print(f"  ✗ {name}: {e}")
            else:
                # Non-verbose shows brief error
                print(f"  ✗ {name}: Failed")
            return False

    def check_proxy_config(self) -> str:
        """Check if proxy is configured"""
        if not ProxyConfig:
            return False

        proxy_config = ProxyConfig()
        if proxy_config.enabled:
            return f"Configured ({proxy_config.url})"
        else:
            return False

    def check_proxy_service(self) -> str:
        """Check if proxy systemd service is running"""
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "residential-proxy"],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                return "Running"
            else:
                return False
        except subprocess.TimeoutExpired:
            return False
        except FileNotFoundError:
            # systemctl not available
            return "Cannot check (systemctl not found)"

    def check_proxy_connectivity(self) -> str:
        """Check if proxy is responding"""
        if not ProxyConfig:
            return False

        proxy_config = ProxyConfig()
        if not proxy_config.enabled:
            return False

        try:
            # Try to connect through proxy
            response = requests.get(
                "https://api.ipify.org",
                proxies=proxy_config.proxies,
                timeout=5
            )
            proxy_ip = response.text
            return f"Connected (IP: {proxy_ip})"
        except requests.exceptions.ProxyError as e:
            raise Exception(f"Proxy not responding: {e}")
        except Exception as e:
            raise Exception(f"Connection failed: {e}")

    def check_ip_change(self) -> str:
        """Check if proxy actually changes IP"""
        if not ProxyConfig:
            return False

        proxy_config = ProxyConfig()
        if not proxy_config.enabled:
            return False

        try:
            # Get local IP
            local_response = requests.get("https://api.ipify.org", timeout=5)
            local_ip = local_response.text

            # Get proxy IP
            proxy_response = requests.get(
                "https://api.ipify.org",
                proxies=proxy_config.proxies,
                timeout=5
            )
            proxy_ip = proxy_response.text

            if local_ip != proxy_ip:
                return f"IP changed: {local_ip} → {proxy_ip}"
            else:
                raise Exception(f"IP did not change (still {local_ip})")
        except requests.exceptions.ProxyError:
            # Already caught by connectivity check
            return False
        except Exception as e:
            raise Exception(str(e))

    def check_yts_access(self) -> str:
        """Check if YTS API is accessible"""
        if not ProxyConfig or not SSLConfig:
            return False

        proxy_config = ProxyConfig()
        ssl_config = SSLConfig()

        # Disable SSL warnings
        if not ssl_config.verify:
            ssl_config.disable_warnings()

        yts_urls = [
            "https://yts.mx/api/v2/list_movies.json",
            "https://yts.lt/api/v2/list_movies.json",
        ]

        for url in yts_urls:
            try:
                response = requests.get(
                    url,
                    params={"query_term": "test", "limit": 1},
                    proxies=proxy_config.proxies if proxy_config.enabled else None,
                    verify=ssl_config.verify,
                    timeout=5
                )

                # Check if response is JSON (not ISP block page)
                content_type = response.headers.get('content-type', '')
                if 'json' in content_type.lower():
                    data = response.json()
                    if data.get("status") == "ok":
                        domain = url.split('/')[2]
                        return f"Accessible ({domain})"
                else:
                    continue  # Try next mirror
            except Exception:
                continue

        raise Exception("All YTS mirrors blocked or unreachable")

    def check_torrent_cache(self) -> str:
        """Check torrent cache status"""
        metadata_file = Path.home() / ".cache" / "my-toolkit" / "torrents" / "metadata.json"

        if not metadata_file.exists():
            return "Empty (no downloads yet)"

        try:
            with open(metadata_file, 'r') as f:
                data = json.load(f)
                movies = data.get("movies", [])
                if not movies:
                    return "Empty"

                valid = 0
                invalid = 0
                downloading = 0
                for movie in movies:
                    status = movie.get("status", "downloaded")
                    if status == "downloading":
                        downloading += 1
                    else:
                        movie_path = movie.get("path", "")
                        if movie_path and Path(movie_path).exists():
                            valid += 1
                        else:
                            invalid += 1

                parts = [f"{len(movies)} movie(s)"]
                if valid:
                    parts.append(f"{valid} valid")
                if invalid:
                    parts.append(f"{invalid} missing")
                if downloading:
                    parts.append(f"{downloading} downloading")
                return ", ".join(parts)
        except Exception:
            return "Metadata corrupted"

    def check_squid_config(self) -> str:
        """Check if Squid configuration exists"""
        squid_conf = Path.home() / ".config" / "my-toolkit" / "squid.conf"

        if squid_conf.exists():
            # Check file permissions
            mode = squid_conf.stat().st_mode & 0o777
            if mode == 0o600:
                return f"Exists (secure permissions)"
            else:
                return f"Exists (permissions: {oct(mode)})"
        else:
            return False

    def check_toolkit_config(self) -> str:
        """Check toolkit configuration directory"""
        config_dir = Path.home() / ".config" / "my-toolkit"

        if config_dir.exists():
            files = list(config_dir.glob("*"))
            return f"Exists ({len(files)} files)"
        else:
            return False

    def check_dependencies(self) -> str:
        """Check if required dependencies are available"""
        deps = {
            "transmission-cli": "transmission",
            "vlc": "vlc",
            "bwrap": "bubblewrap",
            "squid": "squid",
        }

        missing = []
        for cmd, pkg in deps.items():
            try:
                subprocess.run([cmd, "--version"], capture_output=True, timeout=1)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                missing.append(pkg)

        if not missing:
            return "All dependencies available"
        else:
            return f"Missing: {', '.join(missing)}"

    def run_all_checks(self):
        """Run all health checks"""
        print("=" * 60)
        print("My Toolkit Health Check")
        print("=" * 60)
        print()

        # Configuration checks
        print("📋 Configuration:")
        self.check("Toolkit config directory", self.check_toolkit_config)
        self.check("Proxy configuration", self.check_proxy_config)
        self.check("Squid configuration file", self.check_squid_config)
        self.check("Torrent cache", self.check_torrent_cache)
        print()

        # Service checks
        print("⚙️  Services:")
        self.check("Proxy service status", self.check_proxy_service)
        print()

        # Network checks
        print("🌐 Network:")
        proxy_configured = self.check("Proxy connectivity", self.check_proxy_connectivity)
        if proxy_configured:
            self.check("IP address change", self.check_ip_change)
        self.check("YTS API access", self.check_yts_access)
        print()

        # Dependencies
        print("📦 Dependencies:")
        self.check("Required packages", self.check_dependencies)
        print()

        # Summary
        print("=" * 60)
        print("Summary:")
        print(f"  ✓ Passed: {len(self.results)}")
        print(f"  ⚠ Warnings: {len(self.warnings)}")
        print(f"  ✗ Failed: {len(self.errors)}")
        print()

        if self.errors:
            print("Errors:")
            for error in self.errors:
                print(f"  ✗ {error['name']}: {error['message']}")
            print()

        if self.warnings:
            print("Warnings:")
            for warning in self.warnings:
                print(f"  ⚠ {warning['name']}: {warning['message']}")
            print()

        # Recommendations
        if self.errors or self.warnings:
            print("Recommendations:")

            # Proxy-related issues
            proxy_issues = [e for e in self.errors + self.warnings if 'proxy' in e['name'].lower()]
            if proxy_issues:
                print("  Proxy issues detected:")
                print("    1. Check if proxy is configured: my-toolkit proxy-setup status")
                print("    2. Test proxy connection: my-toolkit proxy-setup test -v")
                print("    3. Check service logs: journalctl -u residential-proxy")
                print()

            # YTS access issues
            yts_issues = [e for e in self.errors if 'yts' in e['name'].lower()]
            if yts_issues:
                print("  YTS access blocked:")
                print("    1. Configure residential proxy: my-toolkit proxy-setup configure <url>")
                print("    2. Or use a VPN")
                print()

            # Dependency issues
            dep_issues = [e for e in self.errors + self.warnings if 'dependencies' in e['name'].lower()]
            if dep_issues:
                print("  Missing dependencies:")
                print("    1. Enter development shell: nix develop")
                print("    2. Or rebuild your system with my-toolkit enabled")
                print()

        print("=" * 60)

        # Exit code
        if self.errors:
            return 1
        else:
            return 0


def main():
    parser = argparse.ArgumentParser(
        description="Health check for My Toolkit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This command checks:
  - Proxy configuration and connectivity
  - Service status (residential-proxy)
  - Network connectivity and IP changes
  - YTS API accessibility
  - Torrent cache status
  - Required dependencies

Examples:
  health-check.py              # Run all checks
  health-check.py -v           # Verbose output
  health-check.py --proxy      # Only check proxy
  health-check.py --network    # Only check network

Exit codes:
  0 - All checks passed or only warnings
  1 - One or more checks failed
        """
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed output for each check"
    )

    parser.add_argument(
        "--proxy",
        action="store_true",
        help="Only run proxy-related checks"
    )

    parser.add_argument(
        "--network",
        action="store_true",
        help="Only run network-related checks"
    )

    args = parser.parse_args()

    checker = HealthCheck(verbose=args.verbose)

    if args.proxy:
        print("Running proxy checks only...")
        print()
        print("📋 Configuration:")
        checker.check("Proxy configuration", checker.check_proxy_config)
        checker.check("Squid configuration file", checker.check_squid_config)
        print()
        print("⚙️  Service:")
        checker.check("Proxy service status", checker.check_proxy_service)
        print()
        print("🌐 Network:")
        checker.check("Proxy connectivity", checker.check_proxy_connectivity)
        checker.check("IP address change", checker.check_ip_change)
        print()
        exit_code = 1 if checker.errors else 0
    elif args.network:
        print("Running network checks only...")
        print()
        checker.check("Proxy connectivity", checker.check_proxy_connectivity)
        checker.check("IP address change", checker.check_ip_change)
        checker.check("YTS API access", checker.check_yts_access)
        print()
        exit_code = 1 if checker.errors else 0
    else:
        exit_code = checker.run_all_checks()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
