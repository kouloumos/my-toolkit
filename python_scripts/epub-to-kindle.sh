#!/bin/sh

# Convert EPUB files to Amazon Kindle format (AZW3)
# Reads file paths from stdin or command-line arguments
# Outputs converted file paths to stdout, errors to stderr

set -e

VERBOSE=0

usage() {
    cat >&2 <<EOF
Usage: $0 [-v] [FILE...]

Convert EPUB files to AZW3 format. If no files are provided, reads paths from stdin.

Options:
  -v    Verbose output

Examples:
  $0 book.epub
  find . -name "*.epub" | $0
  find . -name "*.epub" -print0 | xargs -0 $0
EOF
    exit 1
}

# Parse options
while [ $# -gt 0 ]; do
    case "$1" in
        -v) VERBOSE=1; shift ;;
        -h|--help) usage ;;
        -*) echo "$0: unknown option: $1" >&2; usage ;;
        *) break ;;
    esac
done

if ! command -v ebook-convert >/dev/null 2>&1; then
    echo "$0: ebook-convert not found. Please install Calibre." >&2
    exit 1
fi

# Process files from arguments or stdin
if [ $# -gt 0 ]; then
    # Process command-line arguments
    for epub_file in "$@"; do
        [ -f "$epub_file" ] || {
            echo "$0: not a file: $epub_file" >&2
            continue
        }
        
        [ "${epub_file##*.}" = "epub" ] || {
            echo "$0: not an EPUB file: $epub_file" >&2
            continue
        }
        
        dir=$(dirname "$epub_file")
        basename=$(basename "$epub_file" .epub)
        azw3_file="$dir/$basename.azw3"
        
        # Skip if already exists
        [ -f "$azw3_file" ] && {
            [ $VERBOSE -eq 1 ] && echo "$0: skipping (exists): $epub_file" >&2
            echo "$azw3_file"
            continue
        }
        
        [ $VERBOSE -eq 1 ] && echo "$0: converting: $epub_file" >&2
        
        if ebook-convert "$epub_file" "$azw3_file" >/dev/null 2>&1; then
            echo "$azw3_file"
        else
            echo "$0: conversion failed: $epub_file" >&2
            exit 1
        fi
    done
else
    # Process stdin
    while IFS= read -r epub_file; do
        [ -z "$epub_file" ] && continue
        
        [ -f "$epub_file" ] || {
            echo "$0: not a file: $epub_file" >&2
            continue
        }
        
        [ "${epub_file##*.}" = "epub" ] || {
            echo "$0: not an EPUB file: $epub_file" >&2
            continue
        }
        
        dir=$(dirname "$epub_file")
        basename=$(basename "$epub_file" .epub)
        azw3_file="$dir/$basename.azw3"
        
        # Skip if already exists
        [ -f "$azw3_file" ] && {
            [ $VERBOSE -eq 1 ] && echo "$0: skipping (exists): $epub_file" >&2
            echo "$azw3_file"
            continue
        }
        
        [ $VERBOSE -eq 1 ] && echo "$0: converting: $epub_file" >&2
        
        if ebook-convert "$epub_file" "$azw3_file" >/dev/null 2>&1; then
            echo "$azw3_file"
        else
            echo "$0: conversion failed: $epub_file" >&2
            exit 1
        fi
    done
fi



