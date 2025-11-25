#!/bin/sh

# Upload files to reMarkable tablet
# Usage: upload_to_remarkable.sh file1.pdf file2.epub file3.pdf
#
# Based on the reference implementation by Benjamin Schieder:
# https://benjamin-schieder.de/blog/2024/03/20/upload-files-to-remarkable-from-console-via-curl.html

# reMarkable's default IP address when connected via USB
REMARKABLE_IP="10.11.99.1"
UPLOAD_URL="http://${REMARKABLE_IP}/upload"

# Check if required dependencies are installed
check_dependencies() {
    if ! command -v curl &> /dev/null; then
        echo "Error: curl is not installed. Install it with:"
        echo "nix-env -iA nixos.curl"
        echo "Or add it to your configuration.nix:"
        echo "environment.systemPackages = with pkgs; [ curl ];"
        exit 1
    fi

    if ! command -v ping &> /dev/null; then
        echo "Error: ping is not installed. Install it with:"
        echo "nix-env -iA nixos.iputils"
        echo "Or add it to your configuration.nix:"
        echo "environment.systemPackages = with pkgs; [ iputils ];"
        exit 1
    fi
}

# Function to detect MIME type for file
get_mime_type() {
    local file="$1"
    local extension="${file##*.}"
    
    case "${extension,,}" in
        pdf)
            echo "application/pdf"
            ;;
        epub)
            echo "application/epub+zip"
            ;;
        txt)
            echo "text/plain"
            ;;
        *)
            # Default to PDF if unknown
            echo "application/pdf"
            ;;
    esac
}

# Function to check reMarkable connectivity
check_remarkable_connection() {
    echo "Checking connection to reMarkable (${REMARKABLE_IP})..."
    if ! ping -c 1 -W 3 "${REMARKABLE_IP}" > /dev/null 2>&1; then
        echo "Error: Cannot reach reMarkable tablet at ${REMARKABLE_IP}" >&2
        echo "Make sure your reMarkable is:" >&2
        echo "  1. Connected via USB cable" >&2
        echo "  2. USB web interface is enabled in Settings > Storage" >&2
        echo "  3. The tablet is powered on and unlocked" >&2
        return 1
    fi
    echo "✓ reMarkable tablet is reachable"
    return 0
}

# Function to upload a single file
upload_file() {
    local file="$1"
    local mime_type
    local filename
    
    # Get just the filename without path
    filename=$(basename "${file}")
    
    # Get appropriate MIME type
    mime_type=$(get_mime_type "${file}")
    
    echo "Uploading: ${filename} (${mime_type})"
    
    # Upload the file using curl
    if curl "${UPLOAD_URL}" \
        -X POST \
        --header "Content-Type: multipart/form-data" \
        -F "name=file" \
        -F "file=@${file};type=${mime_type}" \
        -F "filename=${filename}" \
        --connect-timeout 10 \
        --max-time 300 \
        --progress-bar \
        --fail-with-body; then
        echo "✓ Successfully uploaded: ${filename}"
        return 0
    else
        echo "✗ Failed to upload: ${filename}" >&2
        return 1
    fi
}

# Main function
main() {
    # Check for help flag
    if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
        echo "Upload files to reMarkable tablet"
        echo ""
        echo "Usage: $0 [file1] [file2] ..."
        echo ""
        echo "Supported file types:"
        echo "  - PDF (.pdf)"
        echo "  - EPUB (.epub)"
        echo "  - Text files (.txt)"
        echo ""
        echo "Requirements:"
        echo "  - reMarkable connected via USB"
        echo "  - USB web interface enabled in Settings > Storage"
        echo "  - curl and ping utilities installed"
        echo ""
        echo "Examples:"
        echo "  $0 document.pdf"
        echo "  $0 *.epub"
        echo "  $0 book1.pdf book2.epub notes.txt"
        exit 0
    fi

    # Check if we have input files
    if [ "$#" -eq 0 ]; then
        echo "Usage: $0 [file1] [file2] ..."
        echo "Use $0 --help for more information"
        exit 1
    fi

    # Check dependencies
    check_dependencies

    # Check reMarkable connection
    if ! check_remarkable_connection; then
        exit 1
    fi

    # Validate all files exist before starting uploads
    echo "Validating files..."
    for file in "$@"; do
        if [ ! -f "${file}" ]; then
            echo "Error: File '${file}' does not exist" >&2
            exit 1
        fi
        
        # Check file size (reMarkable has limits)
        file_size=$(stat -f%z "${file}" 2>/dev/null || stat -c%s "${file}" 2>/dev/null)
        if [ "${file_size}" -gt 104857600 ]; then  # 100MB limit
            echo "Warning: File '${file}' is larger than 100MB and might fail to upload"
        fi
    done

    # Upload each file
    echo ""
    echo "Starting uploads..."
    total_files="$#"
    success_count=0
    failed_files=""

    for file in "$@"; do
        echo ""
        if upload_file "${file}"; then
            success_count=$((success_count + 1))
        else
            failed_files="${failed_files} '$(basename "${file}")'"
        fi
    done

    # Summary
    echo ""
    echo "=== Upload Summary ==="
    echo "Total files: ${total_files}"
    echo "Successful: ${success_count}"
    echo "Failed: $((total_files - success_count))"

    if [ "${success_count}" -eq "${total_files}" ]; then
        echo "✓ All files uploaded successfully!"
        exit 0
    elif [ "${success_count}" -gt 0 ]; then
        echo "⚠ Some files failed to upload:${failed_files}"
        exit 1
    else
        echo "✗ All uploads failed"
        exit 1
    fi
}

# Run main function with all arguments
main "$@"
