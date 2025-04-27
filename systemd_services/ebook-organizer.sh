#!/bin/sh

EBOOK_DIR="$HOME/Books"
TEMP_FILE="/tmp/ebook_organizer_notifications.tmp"
WAIT_TIME=1  # Time in seconds to wait after file creation before processing

log() {
    echo "$1"
}

cleanup() {
    log "Cleaning up..."
    
    # Kill any existing dbus-monitor processes for this script
    if pgrep -f "dbus-monitor.*org.freedesktop.Notifications" > /dev/null; then
        log "Killing existing dbus-monitor processes"
        pkill -f "dbus-monitor.*org.freedesktop.Notifications"
    else
        log "No existing dbus-monitor processes found"
    fi

    # Remove temporary files
    if [ -f "$TEMP_FILE" ]; then
        log "Removing temporary file: $TEMP_FILE"
        rm "$TEMP_FILE"
    fi

    log "Cleanup completed"
}

# Run cleanup at the start
cleanup

# Trap to ensure cleanup runs on exit
trap cleanup EXIT

start_notification_listener() {
    log "Starting notification action listener"
    dbus-monitor --session "type='signal',interface='org.freedesktop.Notifications',member='ActionInvoked'" |
    while read -r line; do
        log "Received dbus-monitor line: $line"
        if echo "$line" | grep -q "uint32"; then
            notification_id=$(echo "$line" | awk '{print $2}')
            log "Extracted notification ID: $notification_id"
            read -r action_line
            log "Received action line: $action_line"
            if echo "$action_line" | grep -q "string \"open\""; then
                log "Detected 'open' action for notification ID: $notification_id"
                log "Attempting to read from temp file: $TEMP_FILE"
                folder_path=$(awk -F'[:,]' -v id="$notification_id" '$1 == id {print $3}' "$TEMP_FILE")
                if [ -n "$folder_path" ]; then
                    log "Found folder path: $folder_path"
                    open_folder "$folder_path"
                    cleanup
                else
                    log "Error: Unable to find folder path for notification ID: $notification_id"
                    log "Current contents of temp file:"
                    log "$(cat "$TEMP_FILE")"
                fi
            fi
        fi
    done &
}

notify() {
    local title="E-book Organizer"
    local message="$1"
    local folder_path="$2"

    # Start the notification listener just before sending the notification
    start_notification_listener

    log "Sending notification: Message: '$message', Folder: '$folder_path'"
    
    notification_id=$(gdbus call --session \
        --dest=org.freedesktop.Notifications \
        --object-path=/org/freedesktop/Notifications \
        --method=org.freedesktop.Notifications.Notify \
        "E-book Organizer" 0 "dialog-information" "$title" "$message" \
        "['open', 'Open folder']" \
        "{}" \
        5000 | awk '{print $2}' | tr -d '()')

    log "Sent notification: ID: $notification_id, Message: '$message' | Folder: '$folder_path'"
    echo "$notification_id:$folder_path" >> "$TEMP_FILE"
}

open_folder() {
    local folder_path="$1"
    log "Opening folder: '$folder_path'"
    
    if [ ! -d "$folder_path" ]; then
        log "Error: Folder not found: '$folder_path'"
        return 1
    fi

    # Try xdg-open
    if command -v xdg-open &> /dev/null; then
        xdg-open "$folder_path" &
        log "Opened folder using xdg-open: '$folder_path'"
        return 0
    fi

    # Try gio
    if command -v gio &> /dev/null; then
        gio open "$folder_path" &
        log "Opened folder using gio: '$folder_path'"
        return 0
    fi

    # Try dbus-send
    if command -v dbus-send &> /dev/null; then
        dbus-send --session --print-reply --dest=org.freedesktop.FileManager1 \
            /org/freedesktop/FileManager1 \
            org.freedesktop.FileManager1.ShowFolders \
            array:string:"file://$folder_path" string:"" &> /dev/null
        log "Opened folder using dbus-send: '$folder_path'"
        return 0
    fi

    log "Error: Unable to open folder: '$folder_path'. No suitable method found."
    return 1
}

rename_and_organize() {
    local FILENAME="$1"
    local BASENAME="${FILENAME%.*}"
    
    log "New e-book detected: $FILENAME"
    NEW_NAME=$(zenity --entry --title="Rename E-book" --text="Enter new name for $FILENAME:" --entry-text="$BASENAME")
    
    if [ -n "$NEW_NAME" ]; then
        # Create a folder for the book
        FOLDER_NAME="${NEW_NAME// /_}"
        FULL_FOLDER_PATH="$EBOOK_DIR/$FOLDER_NAME"
        mkdir -p "$FULL_FOLDER_PATH"
        
        # Move the original EPUB file
        mv "$EBOOK_DIR/$FILENAME" "$FULL_FOLDER_PATH/$NEW_NAME.epub"
        
        # Convert to AZW3
        ebook-convert "$FULL_FOLDER_PATH/$NEW_NAME.epub" "$FULL_FOLDER_PATH/$NEW_NAME.azw3"
        
        log "Organized and converted: $NEW_NAME"
        notify "E-book '$NEW_NAME' has been organized and converted." "$FULL_FOLDER_PATH"
    else
        log "No name provided, kept original filename"
        notify "E-book organization cancelled." "$EBOOK_DIR"
    fi
}

handle_new_file() {
    local FILENAME="$1"
    
    log "New file detected: $FILENAME. Waiting $WAIT_TIME seconds before processing."
    
    # Wait for WAIT_TIME seconds
    sleep $WAIT_TIME
    
    # Check if the file still exists after waiting
    if [ -f "$EBOOK_DIR/$FILENAME" ]; then
        rename_and_organize "$FILENAME"
    else
        log "File no longer exists: $FILENAME. Skipping."
    fi
}

log "Script started. Watching directory: $EBOOK_DIR"

if [ ! -d "$EBOOK_DIR" ]; then
    log "Error: $EBOOK_DIR does not exist. Creating it."
    mkdir -p "$EBOOK_DIR"
fi

# Check for required commands
if ! command -v ebook-convert &> /dev/null; then
    log "Error: ebook-convert command not found. Please install Calibre."
    notify "Error: Calibre is not installed. Please install it to use this script." "$EBOOK_DIR"
    exit 1
fi

if ! command -v zenity &> /dev/null; then
    log "Error: zenity command not found. Please install zenity."
    notify "Error: zenity is not installed. Please install it to use this script." "$EBOOK_DIR"
    exit 1
fi

if ! command -v inotifywait &> /dev/null; then
    log "Error: inotifywait command not found. Please install inotify-tools."
    notify "Error: inotify-tools is not installed. Please install it to use this script." "$EBOOK_DIR"
    exit 1
fi

# Create a temporary file to store notification IDs and folder paths
touch "$TEMP_FILE"

# Use inotifywait to monitor the directory
inotifywait -m -e create -e moved_to --format '%f' "$EBOOK_DIR" |
while read -r FILENAME
do
    if [[ "$FILENAME" == *.epub ]]; then
        handle_new_file "$FILENAME"
    fi
done

log "Script exited unexpectedly"