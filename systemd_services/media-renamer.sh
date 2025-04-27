#!/bin/sh

SCREENSHOT_DIR="$HOME/Pictures/Screenshots"
SCREENCAST_DIR="$HOME/Videos/Screencasts"
CHECK_INTERVAL=5  # Time in seconds between file size checks
STABILIZE_COUNT=2  # Number of times size must remain stable to consider recording finished

log() {
    echo "$1"
}

rename_file() {
    local DIR="$1"
    local FILENAME="$2"
    local FILE_TYPE="$3"
    
    log "Renaming $FILE_TYPE: $FILENAME"
    NEW_NAME=$(zenity --entry --title="Rename $FILE_TYPE" --text="Enter new name for $FILENAME:")
    if [ -n "$NEW_NAME" ]; then
        # Preserve the original file extension
        EXTENSION="${FILENAME##*.}"
        mv "$DIR/$FILENAME" "$DIR/$NEW_NAME.$EXTENSION"
        log "Renamed to: $NEW_NAME.$EXTENSION"
    else
        log "No name provided, kept original filename"
    fi
}

handle_screencast() {
    local DIR="$1"
    local FILENAME="$2"
    
    log "Screencast detected: $FILENAME. Waiting for file size to stabilize."
    
    local prev_size=0
    local current_size=0
    local stable_count=0

    while true; do
        current_size=$(stat -c %s "$DIR/$FILENAME" 2>/dev/null)
        
        if [ $? -ne 0 ]; then
            log "File no longer exists: $FILENAME. Exiting."
            return
        fi

        if [ "$current_size" = "$prev_size" ] && [ "$current_size" != "0" ]; then
            stable_count=$((stable_count + 1))
            if [ $stable_count -ge $STABILIZE_COUNT ]; then
                log "File size stabilized at $current_size bytes for $STABILIZE_COUNT checks. Proceeding with rename."
                rename_file "$DIR" "$FILENAME" "Screencast"
                return
            fi
        else
            stable_count=0
        fi

        prev_size=$current_size
        sleep $CHECK_INTERVAL
    done
}

log "Script started. Watching directories: $SCREENSHOT_DIR and $SCREENCAST_DIR"

for DIR in "$SCREENSHOT_DIR" "$SCREENCAST_DIR"; do
    if [ ! -d "$DIR" ]; then
        log "Error: $DIR does not exist. Creating it."
        mkdir -p "$DIR"
    fi
done

# Use a single inotifywait command and process events one at a time
inotifywait -m -e create -e moved_to --format '%w%f' "$SCREENSHOT_DIR" "$SCREENCAST_DIR" |
while read -r FULLPATH
do
    DIR=$(dirname "$FULLPATH")
    FILENAME=$(basename "$FULLPATH")
    
    case "$DIR" in
        "$SCREENSHOT_DIR")
            if [[ "$FILENAME" == Screenshot* ]]; then
                rename_file "$DIR" "$FILENAME" "Screenshot"
            fi
            ;;
        "$SCREENCAST_DIR")
            if [[ "$FILENAME" == Screencast* ]]; then
                handle_screencast "$DIR" "$FILENAME"
            fi
            ;;
    esac
done

log "Script exited unexpectedly"