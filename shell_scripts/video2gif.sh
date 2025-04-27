#!/bin/sh

# Default configuration
fps=15
width=""
speed=1
max_frames=1000

# Help function
function show_help {
    echo "Usage: $0 input_file [output_file] [options]"
    echo ""
    echo "Positional arguments:"
    echo "  input_file           Input video file (required)"
    echo "  output_file          Output GIF file (default: input filename with .gif extension)"
    echo ""
    echo "Options:"
    echo "  -f, --fps NUMBER       Frames per second (default: 15)"
    echo "  -w, --width NUMBER     Output width in pixels (default: original width)"
    echo "  -s, --speed NUMBER     Speed multiplier (default: 1, 2 = 2x speed, 0.5 = half speed)"
    echo "  -m, --max-frames NUMBER Maximum number of frames (default: 1000)"
    echo "  -h, --help            Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 video.mp4"
    echo "  $0 video.mp4 output.gif -f 20 -w 800 -s 1.5 -m 2000"
    echo "  $0 video.mp4 -f 30 -w 600"
    exit 0
}

# Get input file (first argument)
input="$1"
shift

# Get output file (second argument) if provided
if [ -n "$1" ] && [ "${1:0:1}" != "-" ]; then
    output="$1"
    shift
else
    output="${input%.*}.gif"
fi

# Parse remaining command line arguments
while [ "$#" -gt 0 ]; do
    case "$1" in
        -f|--fps)
            if [ -n "$2" ] && [ "${2:0:1}" != "-" ]; then
                fps="$2"
                shift 2
            else
                echo "Error: Missing value for $1"
                show_help
            fi
            ;;
        -w|--width)
            if [ -n "$2" ] && [ "${2:0:1}" != "-" ]; then
                width="$2"
                shift 2
            else
                echo "Error: Missing value for $1"
                show_help
            fi
            ;;
        -s|--speed)
            if [ -n "$2" ] && [ "${2:0:1}" != "-" ]; then
                speed="$2"
                shift 2
            else
                echo "Error: Missing value for $1"
                show_help
            fi
            ;;
        -m|--max-frames)
            if [ -n "$2" ] && [ "${2:0:1}" != "-" ]; then
                max_frames="$2"
                shift 2
            else
                echo "Error: Missing value for $1"
                show_help
            fi
            ;;
        -h|--help)
            show_help
            ;;
        *)
            echo "Unknown parameter: $1"
            show_help
            ;;
    esac
done

# Validate required parameters
if [ -z "$input" ]; then
    echo "Error: Input file is required"
    show_help
fi

# Validate numeric parameters
if ! [ "$fps" -gt 0 ] 2>/dev/null; then
    echo "Error: FPS must be a positive number"
    show_help
fi

if [ -n "$width" ] && ! [ "$width" -gt 0 ] 2>/dev/null; then
    echo "Error: Width must be a positive number"
    show_help
fi

if ! [ "$speed" -gt 0 ] 2>/dev/null; then
    echo "Error: Speed must be a positive number"
    show_help
fi

if ! [ "$max_frames" -gt 0 ] 2>/dev/null; then
    echo "Error: Max frames must be a positive number"
    show_help
fi

# Get video duration
duration=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$input" | awk '{print int($1)}')
if [ -z "$duration" ] || [ "$duration" -le 0 ]; then
    echo "Error: Could not determine video duration"
    exit 1
fi

total_frames=$((duration * fps))

# Adjust FPS if needed to stay under max_frames
if [ $total_frames -gt $max_frames ]; then
    # Calculate new FPS, ensuring it's at least 1
    new_fps=$((max_frames / duration))
    if [ $new_fps -lt 1 ]; then
        echo "Warning: Video is too long for the specified max frames. Using minimum FPS of 1."
        new_fps=1
    else
        echo "Adjusting fps to $new_fps to stay under $max_frames frames"
    fi
    fps=$new_fps
    total_frames=$((duration * fps))
fi

# Add setpts filter for speed adjustment
filters="setpts=PTS/$speed,fps=$fps${width:+,scale=$width:-1:flags=lanczos}"

# Print conversion settings
echo "Conversion Settings:"
echo "------------------"
echo "Input: $input"
echo "Output: $output"
echo "FPS: $fps"
echo "Width: ${width:-original}"
echo "Speed: ${speed}x"
echo "Max Frames: $max_frames"
echo "Duration: ${duration}s"
echo "Total Frames: $total_frames"
echo ""

# Generate palette and create GIF
if ! ffmpeg -i "$input" -vf "$filters,palettegen=stats_mode=diff" -y palette.png; then
    echo "Error: Failed to generate palette"
    exit 1
fi

if ! ffmpeg -i "$input" -i palette.png -lavfi "$filters,paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" -y "$output"; then
    echo "Error: Failed to create GIF"
    rm -f palette.png
    exit 1
fi

rm -f palette.png
echo "✨ Conversion complete! Output saved as: $output"