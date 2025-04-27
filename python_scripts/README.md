# Python Scripts

Collection of personal Python scripts for various tasks.

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
