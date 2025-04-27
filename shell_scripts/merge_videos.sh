#!/bin/sh

# Check if ffmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    echo "FFmpeg is not installed. Install it with:"
    echo "nix-env -iA nixos.ffmpeg"
    # Or add it to configuration.nix:
    # environment.systemPackages = with pkgs; [ ffmpeg ];
    exit 1
fi

# Create a temporary file for the list of videos
temp_file="videos_to_merge.txt"
# Remove any existing temp file
rm -f "$temp_file"

# Check if we have any input files
if [ "$#" -eq 0 ]; then
    echo "Usage: $0 video1.webm video2.webm video3.webm"
    exit 1
fi

# Check if input files exist and are WebM format
for file in "$@"; do
    if [ ! -f "$file" ]; then
        echo "Error: File $file does not exist"
        exit 1
    fi
    
    # Check if file is WebM
    mime_type=$(file -b --mime-type "$file")
    if [[ "$mime_type" != "video/webm" ]]; then
        echo "Warning: $file is not a WebM file (detected: $mime_type)"
        echo "This might cause issues during merging"
    fi
    
    # Write file path to the temporary list
    echo "file '$file'" >> "$temp_file"
done

output_file="merged_output.webm"

echo "Starting to merge videos..."

# Merge the videos using WebM format
# Using libvpx-vp9 for video and libopus for audio, which are commonly used in WebM
ffmpeg -f concat -safe 0 -i "$temp_file" \
    -c:v copy -c:a copy \
    -f webm \
    "$output_file"

# Check if the merge was successful
if [ $? -eq 0 ]; then
    echo "Videos have been successfully merged into $output_file"
else
    echo "Error occurred during merging. Trying alternative method..."
    
    # Alternative method with re-encoding if direct copy fails
    ffmpeg -f concat -safe 0 -i "$temp_file" \
        -c:v libvpx-vp9 -c:a libopus \
        -b:v 2M -b:a 128k \
        -f webm \
        "$output_file"
    
    if [ $? -eq 0 ]; then
        echo "Videos have been successfully merged using re-encoding into $output_file"
    else
        echo "Error: Failed to merge videos"
        exit 1
    fi
fi

# Clean up the temporary file
rm -f "$temp_file"