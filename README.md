# My Toolkit

A collection of personal utility scripts and services for NixOS systems. This toolkit provides a unified interface for managing and running various shell scripts, Python utilities, and systemd services.

## Features

- **Unified Command Interface**: `my-toolkit`
- **[Shell Scripts](./shell_scripts/)** - Utility scripts for common tasks
- **[Python Scripts](./python_scripts/)** - Advanced utilities and automation
- **[Systemd Services](./systemd_services/)** - Background automation services
- **🎬 Torrent Manager** - Isolated torrent downloading and viewing with bubblewrap
- **📦 Flake Apps** - Run tools without installation using `nix run`

## Installation

> **For Development**: If you are contributing or testing changes, see the [Development](#development) section for a faster workflow using `nix develop`.

Add the toolkit to your NixOS configuration by adding the following to your `flake.nix`:

```nix
inputs = {
  my-toolkit.url = "github:kouloumos/my-toolkit";
  # ... your other inputs
};
```

Then in your `configuration.nix`:

```nix
imports = [
  inputs.my-toolkit.nixosModules.default
];

# Enable the toolkit
my-toolkit.enable = true;

# Optionally enable specific services
my-toolkit.services = {
  media-renamer = true;
  ebook-organizer = true;
};
```

After making changes to your configuration, rebuild your system:
```bash
sudo nixos-rebuild switch
```

## Usage

### Command-Line Interface

The `my-toolkit` command provides a unified interface for all your scripts:

```bash
# List all available scripts
my-toolkit list

# Run a shell script
my-toolkit video2gif input.mp4

# Run a Python script
my-toolkit book-downloader
```

### Standalone Apps (No Installation Required!)

Run tools directly without installing using `nix run`:

```bash
# Try the torrent manager instantly
nix run github:kouloumos/my-toolkit#torrent-search -- "Movie Name"

# Watch a movie (after downloading)
nix run github:kouloumos/my-toolkit#torrent-list
nix run github:kouloumos/my-toolkit#torrent-watch -- 1

# Other utilities
nix run github:kouloumos/my-toolkit#video2gif -- input.mp4 output.gif
nix run github:kouloumos/my-toolkit#find-subtitles -- movie.mkv
```

**Available apps:** `torrent-search`, `torrent-list`, `torrent-watch`, `torrent-cleanup`, `download-torrent`, `find-subtitles`, `video2gif`, `upload-to-remarkable`, `book-downloader`, `worktree`

This is perfect for:
- 🚀 Trying the tools before installing
- 🔧 One-off tasks on servers
- 📦 Sharing tools with others
- 🧪 Testing specific versions/commits

### Available Scripts

#### 🎬 Torrent Manager (NEW!)

Complete torrent management with isolated playback:

- **[`torrent-search`](./python_scripts/torrent-search.py)**: Search and download movies from YTS
- **[`torrent-list`](./python_scripts/torrent-list.py)**: List all cached movies
- **[`torrent-watch`](./python_scripts/torrent-watch.py)**: Watch movies in isolated VLC (bubblewrap sandbox, no network)
- **[`torrent-cleanup`](./python_scripts/torrent-cleanup.py)**: Remove movies and clean cache

**Quick Start:**
```bash
# Search and download
my-toolkit torrent-search "Knives Out"

# List cached movies
my-toolkit torrent-list

# Watch with isolation (VLC sandboxed, no network)
my-toolkit torrent-watch 1

# Cleanup when done
my-toolkit torrent-cleanup 1
```

#### Shell Scripts

- **[`download-torrent`](./shell_scripts/download-torrent.sh)**: Downloads torrent files or magnet links using transmission-cli, with optional automatic subtitle search
- **[`video2gif`](./shell_scripts/video2gif.sh)**: Converts video files to optimized GIF format
- **[`merge_videos`](./shell_scripts/merge_videos.sh)**: Merges multiple WebM video files
- **[`upload_to_remarkable`](./shell_scripts/upload_to_remarkable.sh)**: Uploads files (PDF, EPUB, TXT) to reMarkable tablet via USB
- **[`epub-to-kindle`](./python_scripts/epub-to-kindle.sh)**: Converts all EPUB files in a folder to Amazon Kindle format (AZW3)

#### Python Scripts

- **[`find-subtitles`](./python_scripts/find-subtitles.py)**: Finds and downloads subtitles for video files in multiple languages
- **[`book-downloader`](./python_scripts/book-downloader.py)**: Downloads e-books from various sources
- **[`txt-to-docx`](./python_scripts/txt-to-docx.py)**: Converts text files to DOCX format
- **[`worktree`](./python_scripts/worktree.py)**: Manage git worktrees interactively or scriptably (create, teardown, list)

### Systemd Services

The toolkit includes several systemd services that can be enabled individually. To see which services are available and their status:

```bash
my-toolkit list
```

For more information about each service and how to add new ones, see the [Systemd Services README](./systemd_services/README.md).

### 🔒 Security Features: Isolated Torrent Viewing

The `torrent-watch` command runs VLC in a **bubblewrap sandbox** for maximum security when watching potentially untrusted content:

**Isolation Features:**
- ✅ **Network Disabled**: VLC has no internet access (`--unshare-net`)
- ✅ **Read-Only Files**: Video files mounted read-only
- ✅ **Minimal Filesystem**: Only essential system files accessible
- ✅ **No Home Access**: Your home directory is not accessible
- ✅ **Ephemeral Runtime**: Sandbox disappears after playback

This means you can safely watch downloaded content with strong isolation between VLC and your system.

**Example:**
```bash
# Downloads to ~/.cache/my-toolkit/torrents
my-toolkit torrent-search "Movie Name"

# Watches in isolated VLC (no network, sandboxed)
my-toolkit torrent-watch 1

# Clean up when done
my-toolkit torrent-cleanup 1
```

### 🌐 Residential Proxy Setup

If your ISP blocks torrent sites, you can configure a residential proxy using Squid.

**⚠️ Security Note**

Squid is currently marked as insecure in nixpkgs. We plan to replace it with a more secure alternative in the future.

**Quick Setup:**
```bash
# 1. Configure residential proxy
my-toolkit proxy-setup configure "http://user:pass@proxy.example.com:port"

# 2. Enable in your NixOS configuration:
# Add to configuration.nix:
{
  my-toolkit = {
    enable = true;
    services.residential-proxy = true;
  };

  # Allow insecure squid (version depends on your nixpkgs)
  nixpkgs.config.permittedInsecurePackages = [
    "squid-6.8"   # For nixos-24.05 (stable)
    "squid-7.0.1" # For nixos-unstable
  ];
}

# 3. Rebuild your system
sudo nixos-rebuild switch

# 4. Test the proxy
my-toolkit proxy-setup test
```

**Alternative: Use VPN**

You can also use a VPN instead of the proxy:
```bash
# Connect to VPN first, then:
my-toolkit torrent-search "Movie Name"
```

**Features:**
- ✅ **Automatic Detection**: Scripts automatically use proxy when configured
- ✅ **Squid-based**: Industry-standard HTTP proxy
- ✅ **NixOS Service**: Managed by systemd
- ✅ **Credential Security**: Config file protected (chmod 600)

**Supported Providers:**
- DataImpulse (with country routing: `user__cr.cy,gr:pass@gw.dataimpulse.com:823`)
- Any HTTP/HTTPS proxy service

All scripts (`torrent-search`, `book-downloader`, `find-subtitles`) automatically use the proxy when configured.

**Commands:**
```bash
my-toolkit proxy-setup status      # Show proxy status
my-toolkit proxy-setup test -v     # Test with verbose output
my-toolkit proxy-setup disable     # Disable proxy
my-toolkit health-check            # Comprehensive health check
```

### 🏥 Health Check & Diagnostics

Built-in health check to verify everything is working correctly:

```bash
# Full system health check
my-toolkit health-check

# Verbose output
my-toolkit health-check -v

# Only check proxy
my-toolkit health-check --proxy

# Only check network
my-toolkit health-check --network
```

**Checks performed:**
- ✅ Configuration files and directories
- ✅ Proxy service status
- ✅ Network connectivity and IP changes
- ✅ YTS API accessibility
- ✅ Torrent cache status
- ✅ Required dependencies

**Exit codes:**
- `0` - All checks passed
- `1` - One or more checks failed (with helpful diagnostics)

Perfect for troubleshooting when things don't work as expected!

## Development

### Development Workflow

For development and testing, simply use the development environment:

```bash
# Clone the repository
git clone https://github.com/kouloumos/my-toolkit.git
cd my-toolkit

# Enter development environment
# (Squid is automatically allowed in dev mode)
nix develop

# Test scripts directly from source
my-toolkit list
my-toolkit health-check
my-toolkit torrent-search "Movie Name"

# Or run scripts without entering the shell
nix develop --command my-toolkit health-check
```

This approach provides instant feedback - any changes you make to scripts are immediately available for testing without rebuilding your system.

### Testing

The project includes a comprehensive testing framework:

```bash
# Run all tests (the Nix way)
nix flake check

# Run unit tests directly
python3 -m unittest tests/test_toolkit.py

# Run specific test class
python3 -m unittest tests.test_toolkit.TestProxyConfiguration

# Run with verbose output
python3 -m unittest tests/test_toolkit.py -v

# Health check (integration test)
my-toolkit health-check -v
```

**Test Categories:**
- **Unit tests**: Configuration, utilities, script availability
- **Integration tests**: Proxy, network, services
- **Syntax checks**: Python and shell script validation
- **Health checks**: Live system verification

### Development Guidelines

See [CLAUDE.md](./CLAUDE.md) for:
- Code conventions and patterns
- Testing requirements
- Documentation standards
- Nix-specific patterns
- Adding new features checklist

### Project Structure

```
my-toolkit/
├── shell_scripts/     # Shell script utilities
├── python_scripts/    # Python-based utilities (with toolkit_utils.py)
├── systemd_services/  # Systemd service definitions
├── tests/            # Unit and integration tests
├── default.nix       # Main package definition
├── flake.nix        # Nix flake configuration (packages, apps, modules, checks)
├── README.md        # User-facing documentation
└── CLAUDE.md        # Development guide and conventions
```

### Adding New Scripts

1. Add shell scripts to `shell_scripts/` or Python scripts to `python_scripts/`
2. Update `default.nix` with any new dependencies
3. Rebuild the package

## Distribution Models

This toolkit supports multiple distribution models to fit different use cases:

### 1. Try Before Install (Flake Apps)
Perfect for testing or one-off usage:
```bash
nix run github:kouloumos/my-toolkit#torrent-search -- "Movie Name"
```
- ✅ Zero installation
- ✅ All dependencies included
- ✅ Works on any system with Nix
- ✅ Can run specific commits/versions

### 2. User Installation (Nix Profile)
For regular use without system integration:
```bash
nix profile install github:kouloumos/my-toolkit
```
- ✅ Persistent in your PATH
- ✅ No system configuration needed
- ✅ Easy to update/remove

### 3. System Integration (NixOS Module)
For full system integration with services:
```nix
# In your NixOS configuration
imports = [ inputs.my-toolkit.nixosModules.default ];
my-toolkit.enable = true;
my-toolkit.services.media-renamer = true;
```
- ✅ System-wide availability
- ✅ Systemd service integration
- ✅ Declarative configuration

### 3b. Local Development Install (NixOS Module)
For developing the toolkit while having it system-integrated, use a local path input in your NixOS `flake.nix`:
```nix
inputs = {
  my-toolkit = {
    url = "path:/home/youruser/path/to/my-toolkit";
  };
  # ... your other inputs
};
```
Then import the module as usual in `configuration.nix`. To pick up changes after editing scripts:
```bash
sudo nixos-rebuild switch
```
No need to update the flake lock — Nix re-evaluates the local path on each rebuild.

### 4. Development (Nix Develop)
For contributing or testing changes:
```bash
nix develop
# Changes to scripts are immediately available
```
- ✅ Hot reload (no rebuilds)
- ✅ Full development environment
- ✅ All dependencies included

## Sharing Your Tools

The flake app model makes it trivial to share tools with others:

```bash
# Share a one-liner that "just works"
nix run github:yourusername/my-toolkit#torrent-search -- "Movie"

# Or add to someone else's flake
inputs.my-toolkit.url = "github:yourusername/my-toolkit";
```

This is the "nixiest" way to distribute tools - declarative, reproducible, and shareable!

## License

MIT License