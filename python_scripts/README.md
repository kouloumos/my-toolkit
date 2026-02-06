# Python Scripts

Collection of personal Python scripts for various tasks.

## Scripts

### 🎬 Torrent Manager Suite (NEW!)

A complete torrent management system with isolated playback for safe movie viewing.

#### [torrent-search.py](./torrent-search.py)

Search and download movies from YTS API.

Dependencies:
- requests

Usage:
```bash
# Interactive search
torrent-search.py "Knives Out"

# Auto-download first result
torrent-search.py -a "Matrix"

# Prefer specific quality
torrent-search.py -q 1080p "Inception"

# Limit results
torrent-search.py --limit 10 "Star Wars"
```

Options:
- `-a, --auto`: Automatically download first result
- `-q, --quality`: Preferred quality (720p, 1080p, 2160p, 3D)
- `-l, --limit`: Maximum results to show (default: 20)

Note: Uses YTS API for movie torrents only. Downloads to `~/.cache/my-toolkit/torrents/`

#### [torrent-list.py](./torrent-list.py)

List all movies in the torrent cache with metadata.

Dependencies:
- None (uses standard library)

Usage:
```bash
# List all cached movies
torrent-list.py

# Show detailed information
torrent-list.py -v
```

Options:
- `-v, --verbose`: Show detailed information including file paths and sizes

#### [torrent-watch.py](./torrent-watch.py)

Watch movies in an isolated VLC environment using bubblewrap for security.

Dependencies:
- bubblewrap
- vlc
- subliminal (optional, for subtitles)

Usage:
```bash
# Watch movie by cache ID
torrent-watch.py 1

# Skip subtitle search
torrent-watch.py --no-subtitles 2

# Manually select video file
torrent-watch.py --select-file 3
```

Options:
- `-S, --no-subtitles`: Skip automatic subtitle search
- `-s, --select-file`: Manually select which video file to play

Security Features:
- Network access disabled (`--unshare-net`)
- Read-only access to video files
- Isolated filesystem (minimal bindings)
- No access to home directory

#### [torrent-cleanup.py](./torrent-cleanup.py)

Manage torrent cache by removing movies.

Dependencies:
- None (uses standard library)

Usage:
```bash
# Remove specific movie
torrent-cleanup.py 1

# Remove all movies
torrent-cleanup.py --all

# Clean orphaned directories
torrent-cleanup.py --orphans

# Force remove without confirmation
torrent-cleanup.py -f 2
```

Options:
- `-a, --all`: Remove all movies from cache
- `-o, --orphans`: Remove orphaned directories
- `-f, --force`: Skip confirmation prompt

---

### 🌐 Residential Proxy Setup (NEW!)

Configure a residential proxy to bypass ISP blocks.

#### [proxy-setup.py](./proxy-setup.py)

Manage residential proxy configuration for all toolkit scripts.

Dependencies:
- requests
- squid (system service)

Usage:
```bash
# Configure proxy
proxy-setup.py configure "http://user:pass@proxy.example.com:port"

# Test connection
proxy-setup.py test
proxy-setup.py test -v  # Verbose with YTS test

# Show status
proxy-setup.py status

# Disable proxy
proxy-setup.py disable
```

**Features:**
- Generates Squid configuration automatically
- Tests proxy connection and IP change
- Saves configuration securely (chmod 600)
- Auto-detected by all scripts

**Proxy URL Format:**
```
http://username:password@hostname:port
```

**Example with DataImpulse (with country routing):**
```bash
proxy-setup.py configure "http://YOUR_USER__cr.cy,gr:YOUR_PASS@gw.dataimpulse.com:823"
```

After configuration:
1. Enable in NixOS: `my-toolkit.services.residential-proxy = true;`
2. Rebuild: `sudo nixos-rebuild switch`
3. Test: `my-toolkit proxy-setup test`

All scripts automatically use the proxy when configured.

#### [health-check.py](./health-check.py)

Comprehensive health check for all My Toolkit services and configuration.

Dependencies:
- requests
- toolkit_utils

Usage:
```bash
# Full health check
health-check.py

# Verbose output
health-check.py -v

# Only check proxy
health-check.py --proxy

# Only check network
health-check.py --network
```

**Checks performed:**
- Configuration files (proxy, squid, toolkit)
- Service status (residential-proxy)
- Network connectivity through proxy
- IP address changes
- YTS API accessibility
- Torrent cache status
- Required dependencies (transmission, vlc, bubblewrap, squid)

**Output:**
- ✓ Passed checks (green)
- ⚠ Warnings (yellow)
- ✗ Failed checks (red)
- Helpful recommendations for fixing issues

**Exit codes:**
- `0` - All checks passed or only warnings
- `1` - One or more checks failed

**Example output:**
```
====================================
My Toolkit Health Check
====================================

📋 Configuration:
  ✓ Toolkit config directory: Exists (3 files)
  ✓ Proxy configuration: Configured (http://127.0.0.1:3128)
  ✓ Squid configuration file: Exists (secure permissions)
  ✓ Torrent cache: 2 movie(s) cached

⚙️  Services:
  ✓ Proxy service status: Running

🌐 Network:
  ✓ Proxy connectivity: Connected (IP: 93.184.216.34)
  ✓ IP address change: IP changed: 192.168.1.100 → 93.184.216.34
  ✓ YTS API access: Accessible (yts.mx)

📦 Dependencies:
  ✓ Required packages: All dependencies available

====================================
Summary:
  ✓ Passed: 10
  ⚠ Warnings: 0
  ✗ Failed: 0
====================================
```

---

## Shared Utilities

### [toolkit_utils.py](./toolkit_utils.py)

Shared utilities for all Python scripts in the toolkit. Provides:

- **ProxyConfig**: Auto-detect and manage proxy configuration
- **SSLConfig**: Handle SSL certificate verification
- **setup_requests_environment()**: One-call setup for both
- **get_requests_kwargs()**: Get ready-to-use kwargs for requests

**Usage in your scripts:**
```python
from toolkit_utils import get_requests_kwargs
import requests

# All requests will automatically use proxy and correct SSL settings
response = requests.get(url, **get_requests_kwargs())
```

**Advanced usage:**
```python
from toolkit_utils import ProxyConfig, SSLConfig

proxy = ProxyConfig()
ssl = SSLConfig()

if proxy.enabled:
    print(f"Using proxy: {proxy.url}")

response = requests.get(
    url,
    proxies=proxy.proxies,
    verify=ssl.verify
)
```

---

### 🌳 Quick Worktree Launcher

#### [wt.py](./wt.py)

Fast worktree creation with progressive prompting. Start working on any project from anywhere.

Dependencies:
- fzf (optional, for fuzzy project selection)
- git

**First-time setup:**
```bash
# Add directories containing your git repositories
wt config add-dir ~/code
wt config add-dir ~/projects

# Create aliases for frequently used projects
wt config alias btc bitcoin
wt config alias tk my-toolkit
```

**Usage:**
```bash
# Full interactive mode - prompts for everything
wt

# Partial - specify project, prompt for branch
wt bitcoin

# Direct - no prompts, create immediately
wt bitcoin feature-x

# Using aliases
wt btc feature-x

# Reuse last project
wt --last feature-x
wt -l bugfix

# Specify base branch
wt bitcoin feature-x --base develop
```

**Configuration commands:**
```bash
wt config                       # Show current configuration
wt config add-dir ~/code        # Add code directory to scan
wt config rm-dir ~/code         # Remove code directory
wt config alias btc bitcoin     # Create shortcut alias
wt config rm-alias btc          # Remove alias
```

**List worktrees across all projects:**
```bash
wt list
```

**Features:**
- **Progressive prompting**: Only asks for what you don't provide
- **Project auto-discovery**: Scans configured directories for git repos
- **Fuzzy selection**: Uses fzf when available (falls back to numbered menu)
- **Aliases**: Create shortcuts for frequently used projects
- **Last project memory**: `--last` flag reuses the previous project
- **Partial matching**: `wt bit` finds `bitcoin`

**Config file:** `~/.config/my-toolkit/wt.json`

Note: This is a frontend for [`worktree.py`](./worktree.py) - use that directly for more advanced operations like `land` and `teardown`.

---

## Scripts

### [book_downloader.py](./book-downloader.py)

Downloads books from Z-Library. Stores credentials in `~/.zlibrary_credentials.json` and downloads to `~/Books` by default.

Dependencies:
- requests

Usage:
```bash
# Interactive mode
python book_downloader.py

# Auto-download first result
python book_downloader.py -q "Book Title"

# Custom download directory
python book_downloader.py -d ~/CustomBooks

# Search in specific languages
python book_downloader.py -l "english,greek"

# Search for specific formats
python book_downloader.py -f "epub,pdf"

# Combine options
python book_downloader.py -q "Book Title" -l "english,greek" -f "epub"
```

Options:
- `-q, --query`: Search query for automatic download of first result
- `-d, --download-dir`: Set custom download directory
- `-l, --languages`: Comma-separated list of languages to search for (e.g., 'english,greek,french')
- `-f, --formats`: Comma-separated list of formats to search for (e.g., 'epub,pdf')

Note: Requires [`Zlibrary.py`](./Zlibrary.py) to be in the same directory.

### [find-subtitles.py](./find-subtitles.py)

Finds and downloads subtitles for video files using subliminal. Supports multiple languages and subtitle providers.

Dependencies:
- subliminal

Usage:
```bash
# Find subtitles for a single video
find-subtitles.py movie.mp4

# Search for multiple languages
find-subtitles.py -l eng spa movie.mkv

# Recursively process all videos in a directory
find-subtitles.py -r ~/Videos

# Only list available subtitles without downloading
find-subtitles.py --list-only movie.mp4

# Verbose mode for detailed information
find-subtitles.py -v movie.mp4
```

Options:
- `-l, --languages`: Subtitle languages (ISO 639-3 codes, e.g., eng, spa, fra)
- `-r, --recursive`: Recursively process all video files in directory
- `--list-only`: Only list available subtitles without downloading
- `-v, --verbose`: Show detailed information

Environment Variables:
- `SUBTITLE_LANGUAGES`: Default languages (comma-separated, e.g., "eng,spa")

Supported video formats: .mkv, .mp4, .avi, .mov, .wmv, .flv, .webm, .m4v

Note: Automatically called by `download-torrent.sh` after torrent downloads complete.

### [txt-to-docx.py](./txt-to-docx.py)

Converts TXT files to DOCX format recursively. Skips files that already have a corresponding DOCX file.

Dependencies:
- python-docx

Usage:
```bash
# Convert all TXT files in a directory
python txt-to-docx.py /path/to/directory
```

## Adding New Scripts

To add a new script to this collection:

1. Create your Python script in the `python_scripts` directory
2. Add a section to this README.md with:
   - A brief description of what the script does
   - Required dependencies
   - Usage examples with command-line options
   - Any additional notes or requirements
