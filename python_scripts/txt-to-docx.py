import os
import sys
from pathlib import Path
from docx import Document
import argparse

def convert_txt_to_docx(txt_path):
    """
    Convert a text file to DOCX format
    """
    try:
        # Create a new Document
        doc = Document()
        
        # Read the text file
        with open(txt_path, 'r', encoding='utf-8') as file:
            text = file.read()
        
        # Add the content to the document
        doc.add_paragraph(text)
        
        # Create the output filename
        docx_path = txt_path.with_suffix('.docx')
        
        # Save the document
        doc.save(docx_path)
        
        print(f"Converted: {txt_path} -> {docx_path}")
        return True
    except Exception as e:
        print(f"Error converting {txt_path}: {e}")
        return False

def process_directory(directory):
    """
    Process a directory recursively, converting TXT files to DOCX
    if a DOCX with the same name doesn't already exist
    """
    converted_count = 0
    skipped_count = 0
    error_count = 0
    
    # Walk through the directory structure
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith('.txt'):
                txt_path = Path(root) / file
                docx_path = txt_path.with_suffix('.docx')
                
                # Check if a DOCX with the same name already exists
                if docx_path.exists():
                    print(f"Skipped: {txt_path} (DOCX already exists)")
                    skipped_count += 1
                else:
                    if convert_txt_to_docx(txt_path):
                        converted_count += 1
                    else:
                        error_count += 1
    
    return converted_count, skipped_count, error_count

def main():
    parser = argparse.ArgumentParser(description='Convert TXT files to DOCX recursively')
    parser.add_argument('directory', help='The directory to process')
    args = parser.parse_args()
    
    directory = Path(args.directory)
    
    if not directory.is_dir():
        print(f"Error: {directory} is not a valid directory")
        sys.exit(1)
    
    print(f"Processing directory: {directory}")
    
    converted, skipped, errors = process_directory(directory)
    
    print("\nSummary:")
    print(f"  Converted: {converted}")
    print(f"  Skipped (DOCX already exists): {skipped}")
    print(f"  Errors: {errors}")
    print(f"  Total TXT files found: {converted + skipped + errors}")

if __name__ == "__main__":
    main()