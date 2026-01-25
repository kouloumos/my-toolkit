# Shell Scripts

Collection of personal shell scripts for various tasks.

## Scripts

### [download-torrent.sh](./download-torrent.sh)

Downloads torrent files or magnet links using transmission-cli. Optionally searches for subtitles automatically after download completes.

Dependencies:
- transmission

Usage:
```bash
# Download a torrent file
download-torrent.sh movie.torrent

# Download from magnet link
download-torrent.sh "magnet:?xt=urn:btih:..."

# Custom download directory
download-torrent.sh -d ~/Videos movie.torrent

# Disable automatic subtitle search
download-torrent.sh --no-subtitles movie.torrent

# Watch download progress
download-torrent.sh -w movie.torrent
```

Options:
- `-d, --dir <directory>`: Download directory (default: `$HOME/Downloads/torrents`)
- `-s, --subtitles`: Automatically find subtitles after download (default: enabled)
- `-S, --no-subtitles`: Don't automatically find subtitles
- `-w, --watch`: Watch download progress
- `-h, --help`: Show help message

Environment Variables:
- `TORRENT_DOWNLOAD_DIR`: Default download directory
- `TORRENT_AUTO_SUBTITLES`: Auto-find subtitles (true/false)

Note: Automatically integrates with `find-subtitles.py` to search for video subtitles after download.

### [merge_videos.sh](./merge_videos.sh)

Merges multiple WebM video files.

### [upload_to_remarkable.sh](./upload_to_remarkable.sh)

Uploads files (PDF, EPUB, TXT) to reMarkable tablet.

Dependencies:
- curl
- ping

### [video2gif.sh](./video2gif.sh)

Converts video files to optimized GIF format.

Dependencies:
- ffmpeg
- ffprobe

Usage:
```bash
# Basic conversion
video2gif.sh input.mp4 output.gif

# Custom FPS
video2gif.sh --fps 15 input.mp4 output.gif

# Custom width
video2gif.sh --width 480 input.mp4 output.gif

# Adjust speed
video2gif.sh --speed 1.5 input.mp4 output.gif

# Limit maximum frames
video2gif.sh --max-frames 200 input.mp4 output.gif
```

## Adding New Scripts

To add a new script to this collection:

1. Create your shell script in the `shell_scripts` directory
2. Make it executable: `chmod +x your-script.sh`
3. Add a section to this README.md with:
   - A brief description of what the script does
   - Required dependencies
   - Usage examples with command-line options
   - Any additional notes or requirements
