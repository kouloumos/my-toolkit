#!/bin/sh

# Configuration
DOWNLOAD_DIR="${TORRENT_DOWNLOAD_DIR:-$HOME/Downloads/torrents}"
AUTO_SUBTITLES="${TORRENT_AUTO_SUBTITLES:-true}"

show_help() {
    cat << EOF
Usage: download-torrent.sh [OPTIONS] <torrent-file-or-magnet-link>

Downloads a torrent file using transmission-cli.

OPTIONS:
    -d, --dir <directory>       Download directory (default: $DOWNLOAD_DIR)
    -s, --subtitles             Automatically find subtitles after download (default: enabled)
    -S, --no-subtitles          Don't automatically find subtitles
    -w, --watch                 Watch download progress
    -h, --help                  Show this help message

EXAMPLES:
    download-torrent.sh movie.torrent
    download-torrent.sh -d ~/Videos "magnet:?xt=urn:btih:..."
    download-torrent.sh --no-subtitles movie.torrent

ENVIRONMENT VARIABLES:
    TORRENT_DOWNLOAD_DIR        Default download directory
    TORRENT_AUTO_SUBTITLES      Auto-find subtitles (true/false)

DEPENDENCIES:
    - transmission-cli          For downloading torrents
    - find-subtitles.py         For automatic subtitle discovery (optional)
EOF
}

check_dependencies() {
    if ! command -v transmission-cli >/dev/null 2>&1; then
        echo "Error: transmission-cli is not installed"
        echo "Install it with: nix-shell -p transmission"
        exit 1
    fi
}

find_video_files() {
    local dir="$1"
    find "$dir" -type f \( -iname "*.mkv" -o -iname "*.mp4" -o -iname "*.avi" -o -iname "*.mov" -o -iname "*.wmv" -o -iname "*.flv" -o -iname "*.webm" \) 2>/dev/null
}

download_torrent() {
    local torrent="$1"
    local download_dir="$2"
    local watch="$3"

    echo "Starting torrent download..."
    echo "Download directory: $download_dir"
    echo "Torrent: $torrent"
    echo ""

    # Create download directory if it doesn't exist
    mkdir -p "$download_dir"

    # Build transmission-cli command
    local cmd="transmission-cli"
    cmd="$cmd -w \"$download_dir\""

    if [ "$watch" = "false" ]; then
        cmd="$cmd -D"  # Run in background without progress display
    fi

    cmd="$cmd \"$torrent\""

    # Execute download
    if eval "$cmd"; then
        echo ""
        echo "Download completed successfully!"
        return 0
    else
        echo ""
        echo "Download failed!"
        return 1
    fi
}

auto_find_subtitles() {
    local download_dir="$1"

    echo ""
    echo "Searching for video files..."

    local video_files
    video_files=$(find_video_files "$download_dir")

    if [ -z "$video_files" ]; then
        echo "No video files found in download directory"
        return 0
    fi

    local video_count
    video_count=$(echo "$video_files" | wc -l)
    echo "Found $video_count video file(s)"

    # Check if find-subtitles.py is available
    if command -v my-toolkit >/dev/null 2>&1; then
        echo "Automatically searching for subtitles..."
        echo ""

        echo "$video_files" | while IFS= read -r video_file; do
            echo "Processing: $(basename "$video_file")"
            my-toolkit find-subtitles "$video_file"
            echo ""
        done
    else
        echo "Note: my-toolkit command not found, skipping automatic subtitle search"
        echo "You can manually search for subtitles using: my-toolkit find-subtitles <video-file>"
    fi
}

main() {
    local torrent=""
    local download_dir="$DOWNLOAD_DIR"
    local auto_subs="$AUTO_SUBTITLES"
    local watch="false"

    # Parse arguments
    while [ $# -gt 0 ]; do
        case "$1" in
            -h|--help)
                show_help
                exit 0
                ;;
            -d|--dir)
                download_dir="$2"
                shift 2
                ;;
            -s|--subtitles)
                auto_subs="true"
                shift
                ;;
            -S|--no-subtitles)
                auto_subs="false"
                shift
                ;;
            -w|--watch)
                watch="true"
                shift
                ;;
            -*)
                echo "Error: Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
            *)
                torrent="$1"
                shift
                ;;
        esac
    done

    # Validate input
    if [ -z "$torrent" ]; then
        echo "Error: No torrent file or magnet link provided"
        echo "Use --help for usage information"
        exit 1
    fi

    # Check if torrent file exists (skip check for magnet links and URLs)
    case "$torrent" in
        magnet:*|http://*|https://*)
            # Magnet links and URLs are handled by transmission-cli directly
            ;;
        *)
            if [ ! -f "$torrent" ]; then
                echo "Error: Torrent file not found: $torrent"
                exit 1
            fi
            ;;
    esac

    # Check dependencies
    check_dependencies

    # Download torrent
    if download_torrent "$torrent" "$download_dir" "$watch"; then
        # Automatically find subtitles if enabled
        if [ "$auto_subs" = "true" ]; then
            auto_find_subtitles "$download_dir"
        fi
        exit 0
    else
        exit 1
    fi
}

main "$@"
