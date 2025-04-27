# My Toolkit

A collection of personal utility scripts and services for NixOS systems. This toolkit provides a unified interface for managing and running various shell scripts, Python utilities, and systemd services.

## Features

- **Unified Command Interface**: `my-toolkit`
- **[Shell Scripts](./shell_scripts/)**
- **[Python Scripts](./python_scripts/)**
- **[Systemd Services](./systemd_services/)**

## Installation

Add the toolkit to your NixOS configuration by adding the following to your `configuration.nix`:

```nix
let
  scriptsFlake = builtins.getFlake "path:/path/to/my-toolkit";
in 
{
  imports = [
    scriptsFlake.nixosModules.default
  ];

  # Enable the toolkit
  my-toolkit.enable = true;

  # Optionally enable specific services
  my-toolkit.services = {
    media-renamer = true;
    ebook-organizer = true;
  };
}
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

### Available Scripts

#### Shell Scripts

- **[`video2gif`](./shell_scripts/video2gif.sh)**: Converts video files to optimized GIF format
- **[`merge_videos`](./shell_scripts/merge_videos.sh)**: Merges multiple WebM video files

#### Python Scripts

- **[`book-downloader`](./python_scripts/book-downloader.py)**: Downloads e-books from various sources
- **[`txt-to-docx`](./python_scripts/txt-to-docx.py)**: Converts text files to DOCX format

### Systemd Services

The toolkit includes several systemd services that can be enabled individually. To see which services are available and their status:

```bash
my-toolkit list
```

For more information about each service and how to add new ones, see the [Systemd Services README](./systemd_services/README.md).

## Development

### Project Structure

```
my-toolkit/
├── shell_scripts/     # Shell script utilities
├── python_scripts/    # Python-based utilities
├── systemd_services/  # Systemd service definitions
├── default.nix        # Main package definition
└── flake.nix         # Nix flake configuration
```

### Adding New Scripts

1. Add shell scripts to `shell_scripts/` or Python scripts to `python_scripts/`
2. Update `default.nix` with any new dependencies
3. Rebuild the package

## License

MIT License