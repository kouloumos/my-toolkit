# CLAUDE.md - Development Guide for My Toolkit

This document provides guidelines and patterns for developing My Toolkit. It's designed to help AI assistants (like Claude) and human developers maintain consistency and quality.

## Project Philosophy

### Core Principles

1. **Nixie First**: Solutions should be declarative, reproducible, and Nix-native
2. **Don't Reinvent the Wheel**: Use established tools (Squid, Transmission, VLC, Subliminal)
3. **Reusable & Maintainable**: Create shared utilities, avoid duplication
4. **Security by Design**: Isolate untrusted content, protect credentials
5. **User-Friendly**: Clear error messages, helpful diagnostics, good documentation

### Design Goals

- **Shareable**: Tools can be run without installation via `nix run`
- **Modular**: Scripts are independent but share common utilities
- **Testable**: All components have health checks and tests
- **Documented**: READMEs, help text, and inline documentation

## Project Structure

```
my-toolkit/
├── shell_scripts/          # Shell utilities (video2gif, upload_to_remarkable, etc.)
├── python_scripts/         # Python utilities with shared toolkit_utils.py
├── systemd_services/       # Background services (media-renamer, ebook-organizer)
├── tests/                  # Unit and integration tests
├── default.nix             # Package build definition
├── flake.nix              # Flake configuration (packages, apps, modules)
├── README.md              # User-facing documentation
└── CLAUDE.md              # This file - development guide
```

## Code Conventions

### Python Scripts

#### File Structure Pattern

```python
#!/usr/bin/env python3

"""
Brief description of what this script does.
"""

import argparse
import sys
from pathlib import Path
from typing import Optional, List, Dict

# Import shared utilities
try:
    from toolkit_utils import ProxyConfig, SSLConfig, get_requests_kwargs
except ImportError:
    # Graceful fallback if running outside toolkit environment
    pass

try:
    import requests
except ImportError:
    print("Error: requests is not installed")
    sys.exit(1)


class Config:
    """Centralized configuration for the script"""
    DEFAULT_VALUE = "value"
    CACHE_DIR = Path.home() / ".cache" / "my-toolkit"


class MainClass:
    """Main logic class"""

    def __init__(self):
        self.config = Config()

    def main_method(self, args):
        """Main logic"""
        pass


def main():
    parser = argparse.ArgumentParser(
        description="Brief description",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  script-name.py example-usage
  script-name.py --option value

Additional help text.
        """
    )

    parser.add_argument("required_arg", help="Required argument")
    parser.add_argument("-o", "--optional", help="Optional argument")

    args = parser.parse_args()

    # Run main logic
    instance = MainClass()
    instance.main_method(args)


if __name__ == "__main__":
    main()
```

#### Naming Conventions

- **Files**: `kebab-case.py` (e.g., `torrent-search.py`, `proxy-setup.py`)
- **Classes**: `PascalCase` (e.g., `ProxyConfig`, `TorrentManager`)
- **Functions/Methods**: `snake_case` (e.g., `load_config()`, `search_movies()`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_PORT`, `CACHE_DIR`)

#### Required Features

1. **Help Text**: All scripts must support `--help` with examples
2. **Error Handling**: User-friendly error messages with troubleshooting hints
3. **Shared Utilities**: Use `toolkit_utils.py` for proxy and SSL
4. **Config Class**: Centralize configuration in a `Config` class
5. **Type Hints**: Use type hints for function signatures
6. **Docstrings**: Document all classes and non-trivial functions

### Shell Scripts

#### File Structure Pattern

```bash
#!/bin/sh

# Configuration
DEFAULT_VALUE="value"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/my-toolkit"

show_help() {
    cat << EOF
Usage: script-name.sh [OPTIONS] <arguments>

Brief description.

OPTIONS:
    -o, --option <value>    Option description
    -h, --help              Show this help message

EXAMPLES:
    script-name.sh example
    script-name.sh --option value

DEPENDENCIES:
    - dependency1
    - dependency2
EOF
}

check_dependencies() {
    if ! command -v dependency >/dev/null 2>&1; then
        echo "Error: dependency is not installed"
        exit 1
    fi
}

main() {
    # Parse arguments
    # Run logic
}

main "$@"
```

#### Shell Script Patterns

- Always use `#!/bin/sh` for portability (not `#!/bin/bash` unless Bash-specific)
- Check dependencies with `check_dependencies()` function
- Provide `show_help()` with examples
- Use proper exit codes (0 = success, 1+ = error)

### Shared Utilities (`toolkit_utils.py`)

All Python scripts should use shared utilities for common functionality:

```python
from toolkit_utils import ProxyConfig, SSLConfig, get_requests_kwargs
import requests

# Method 1: Simple (recommended)
response = requests.get(url, **get_requests_kwargs())

# Method 2: Advanced (when you need control)
proxy_config = ProxyConfig()
ssl_config = SSLConfig()

if proxy_config.enabled:
    print(f"Using proxy: {proxy_config.url}")

response = requests.get(
    url,
    proxies=proxy_config.proxies,
    verify=ssl_config.verify
)
```

#### When to Add to `toolkit_utils.py`

Add utilities when:
- Used by 2+ scripts
- Handles cross-cutting concerns (proxy, SSL, caching)
- Provides reusable configuration logic

Don't add:
- Script-specific business logic
- One-off utilities

## Nix Patterns

### Adding Dependencies

#### System Dependencies (in `default.nix`)

```nix
dependencies = with pkgs; [
    existing-package
    new-package  # for script-name.sh
];
```

#### Python Dependencies (in `default.nix`)

```nix
pythonEnv = pkgs.python311.withPackages (ps: with ps; [
    existing-package
    new-package  # for script-name.py
]);
```

### Creating Flake Apps

For shareable scripts, add to `flake.nix`:

```nix
apps = let
    mkApp = scriptName: { ... };
in {
    existing-app = mkApp "existing-app";
    new-app = mkApp "new-app";  # New app
};
```

### Adding Systemd Services

For background services, add to `flake.nix` in `nixosModules.default`:

```nix
options = {
    my-toolkit = {
        services = {
            existing-service = lib.mkEnableOption "...";
            new-service = lib.mkEnableOption "Enable new-service systemd service";
        };
    };
};

# In config section:
systemd.user.services = lib.mkMerge [
    # ... existing services ...

    (lib.mkIf config.my-toolkit.services.new-service {
        new-service = {
            description = "Description of new service";
            wantedBy = [ "default.target" ];

            path = [ pkgs.dependency1 pkgs.dependency2 ];

            serviceConfig = {
                ExecStart = "${pkgs.callPackage ./default.nix {}}/bin/new-service";
                Restart = "always";
                RestartSec = "5";
            };
        };
    })
];
```

## Security Patterns

### Credential Management

1. **Never hardcode credentials** in scripts or configs
2. **Use secure permissions** for config files (`chmod 600`)
3. **Store in user home** (`~/.config/my-toolkit/`) not in repo
4. **Add to .gitignore** if configuration files may contain secrets

### Security-Sensitive Dependencies

**⚠️ Squid Security Notice**

Squid is currently marked as insecure in nixpkgs due to unresolved vulnerabilities. We're using it temporarily and plan to replace it.

**Current approach:**
1. Dev shell automatically allows insecure packages (`NIXPKGS_ALLOW_INSECURE=1`)
2. Users must explicitly opt-in for production via `permittedInsecurePackages`
3. Documented in README with security warnings
4. TODO: Replace with alternative (Privoxy, Tinyproxy, or custom solution)

**Future replacement candidates:**
- **Privoxy**: Lightweight, better security track record
- **Tinyproxy**: Minimal, simpler codebase
- **Custom Go/Rust proxy**: Small, purpose-built for our use case
- **HAProxy**: More secure, modern alternative

When adding dependencies, always check:
- Is the package marked insecure? (`nix-env -qa --json squid | jq`)
- Are there alternatives without security issues?
- Can the feature be optional?
- Document temporary usage and replacement plan

Example:
```python
config_file = Path.home() / ".config" / "my-toolkit" / "config.json"
config_file.chmod(0o600)  # User read/write only
```

### Isolation Patterns

When handling untrusted content:

```bash
# Use bubblewrap for isolation
bwrap \
    --ro-bind /path/to/file /path/to/file \
    --unshare-net \
    --tmpfs /tmp \
    command args
```

## Testing Requirements

### Unit Tests

All new utilities in `toolkit_utils.py` must have unit tests in `tests/test_toolkit.py`:

```python
class TestNewFeature(unittest.TestCase):
    """Test new feature"""

    def test_basic_functionality(self):
        """Test basic functionality works"""
        result = new_feature()
        self.assertTrue(result)
```

### Health Checks

Services and network-dependent features should have health checks in `health-check.py`:

```python
def check_new_feature(self) -> str:
    """Check if new feature is working"""
    try:
        # Test logic
        return "Feature working"
    except Exception as e:
        raise Exception(f"Feature failed: {e}")

# Add to run_all_checks():
self.check("New feature", self.check_new_feature)
```

### Testing Commands

```bash
# Run unit tests
python3 -m unittest tests/test_toolkit.py

# Run specific test class
python3 -m unittest tests.test_toolkit.TestConfiguration

# Run with pytest (if available)
pytest tests/

# Health check
my-toolkit health-check -v
```

## Documentation Requirements

### README Updates

When adding a new feature, update:

1. **Main README.md**: Add to "Available Scripts" or relevant section
2. **Directory README** (`shell_scripts/README.md` or `python_scripts/README.md`)
3. **Script help text**: `--help` output with examples

### Documentation Pattern

```markdown
### [script-name.py](./script-name.py)

Brief description of what the script does.

Dependencies:
- dependency1
- dependency2

Usage:
\`\`\`bash
# Basic usage
script-name.py argument

# With options
script-name.py --option value argument

# Advanced example
script-name.py -v --complex-option argument
\`\`\`

Options:
- `-o, --option`: Option description
- `-v, --verbose`: Verbose output

Features:
- Feature 1
- Feature 2

Note: Additional important information.
```

## Adding New Features

### Checklist for New Scripts

- [ ] Script created with proper structure (see patterns above)
- [ ] Uses `toolkit_utils.py` for shared functionality
- [ ] Help text with examples (`--help`)
- [ ] Error handling with user-friendly messages
- [ ] Added to appropriate directory (`shell_scripts/` or `python_scripts/`)
- [ ] Made executable (`chmod +x`)
- [ ] Dependencies added to `default.nix`
- [ ] Flake app created (if shareable)
- [ ] Unit tests added (if reusable logic)
- [ ] Health check added (if service-dependent)
- [ ] Documentation updated (main README + directory README)
- [ ] Tested in development mode (`nix develop`)

### Checklist for New Services

- [ ] Service script created
- [ ] Added to `systemd_services/` directory
- [ ] Dependencies added to `default.nix`
- [ ] Service definition added to `flake.nix` in `nixosModules.default`
- [ ] Enable option added to `my-toolkit.services`
- [ ] Documentation updated
- [ ] Tested with `systemctl --user status service-name`

## Common Patterns & Solutions

### Network Requests with Proxy & SSL

Always use toolkit utilities:

```python
from toolkit_utils import get_requests_kwargs
import requests

response = requests.get(url, **get_requests_kwargs())
```

### Configuration Files

Store in `~/.config/my-toolkit/`:

```python
config_dir = Path.home() / ".config" / "my-toolkit"
config_dir.mkdir(parents=True, exist_ok=True)

config_file = config_dir / "config.json"
```

### CLI Argument Parsing

Use argparse with rich help:

```python
parser = argparse.ArgumentParser(
    description="Brief description",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""
Examples with context...
    """
)
```

### Error Messages

Provide actionable guidance:

```python
print("Error: Configuration not found")
print("\nRun: my-toolkit setup-command")
print("Or: See documentation at ...")
```

## Troubleshooting Guidelines

When users report issues, check:

1. **Health check first**: `my-toolkit health-check -v`
2. **Service status**: `systemctl --user status service-name`
3. **Logs**: `journalctl -u service-name -n 50`
4. **Configuration**: Check files in `~/.config/my-toolkit/`
5. **Dependencies**: Verify all packages available in environment

## Version Control

### .gitignore Pattern

```gitignore
# Configuration files with potential secrets
**/squid.conf
**/*credentials*.json
**/.env

# Cache and runtime
**/__pycache__/
**/*.pyc
**/result

# IDE
**/.vscode/
**/.idea/
```

### Commit Message Guidelines

- Use imperative mood: "Add feature" not "Added feature"
- Reference script/component: "torrent-watch: Add subtitle support"
- Explain why, not just what
- **Never add Co-Authored-By or any AI attribution to commits**

Good examples:
```
feat: Add residential proxy support with Squid

Allows users to bypass ISP blocks by routing through residential proxies.
Includes auto-detection in all scripts via toolkit_utils.

fix: Resolve SSL certificate verification on NixOS

OpenSSL 3.x has issues finding certs. Disable verification for known-safe
APIs like YTS with option to force enable via FORCE_SSL_VERIFY=1.

docs: Add proxy setup guide to README
```

## Performance Considerations

- **Lazy imports**: Import heavy modules only when needed
- **Caching**: Use cache directories for API responses
- **Timeouts**: Always set timeouts on network requests (default: 5-10s)
- **Connection pooling**: Reuse requests sessions for multiple calls

## Future Considerations

### Features to Consider

- [ ] Automatic proxy rotation (multiple providers)
- [ ] VPN integration for additional security
- [ ] Torrent scheduling (download at specific times)
- [ ] Bandwidth limiting for downloads
- [ ] Notification system for completed downloads

### Refactoring Opportunities

- [ ] Extract YTS API client to separate module
- [ ] Create torrent client abstraction (support multiple backends)
- [ ] Centralize all configuration in single TOML/YAML file
- [ ] Add plugin system for extending functionality

---

## Quick Reference

### File a Script Should Import

```python
from toolkit_utils import ProxyConfig, SSLConfig, get_requests_kwargs
```

### Test a New Feature

```bash
nix develop
my-toolkit health-check -v
python3 -m unittest tests/test_toolkit.py
```

### Deploy a Change

```bash
# Development testing
nix develop
my-toolkit new-command --test

# System deployment
sudo nixos-rebuild switch
```

---

**Last Updated**: 2026-01-25
**Document Version**: 1.0.0

This document should be updated whenever new patterns are established or conventions change.
