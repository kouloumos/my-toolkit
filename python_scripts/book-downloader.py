# related: https://github.com/famotime/ebook_toolbox
from Zlibrary import Zlibrary
import os
import json
from getpass import getpass
import argparse


class Config:
    """Centralized configuration for the BookDownloader"""
    DEFAULT_DOWNLOAD_DIR = os.path.expanduser("~/Books")
    DEFAULT_CREDENTIALS_FILE = os.path.expanduser("~/.zlibrary_credentials.json")
    DEFAULT_LANGUAGES = ["english"]
    DEFAULT_FORMATS = ["epub","pdf"]
    DEFAULT_SEARCH_LIMIT = 5


class BookDownloader:
    def __init__(self):
        self.config = Config()
        self.download_dir = self.config.DEFAULT_DOWNLOAD_DIR
        self.credentials_file = self.config.DEFAULT_CREDENTIALS_FILE
        self.z = None
        self.languages = self.config.DEFAULT_LANGUAGES
        self.formats = self.config.DEFAULT_FORMATS

    def set_languages(self, languages):
        """Set the languages to search for"""
        if isinstance(languages, str):
            self.languages = [lang.strip() for lang in languages.split(",")]
        else:
            self.languages = languages

    def set_formats(self, formats):
        """Set the formats to search for"""
        if isinstance(formats, str):
            self.formats = [fmt.strip() for fmt in formats.split(",")]
        else:
            self.formats = formats

    def load_credentials(self):
        """Load saved credentials if they exist"""
        if os.path.exists(self.credentials_file):
            try:
                with open(self.credentials_file, "r") as f:
                    creds = json.load(f)
                return creds.get("remix_userid"), creds.get("remix_userkey")
            except json.JSONDecodeError:
                return None, None
        return None, None

    def save_credentials(self, remix_userid, remix_userkey):
        """Save credentials to file"""
        with open(self.credentials_file, "w") as f:
            json.dump({"remix_userid": remix_userid, "remix_userkey": remix_userkey}, f)

    def login(self):
        """Handle login process"""
        # First try to load saved credentials
        remix_userid, remix_userkey = self.load_credentials()

        if remix_userid and remix_userkey:
            try:
                self.z = Zlibrary(
                    remix_userid=remix_userid, remix_userkey=remix_userkey
                )
                if self.z.isLoggedIn():
                    print("Successfully logged in using saved credentials!")
                    return True
            except Exception:
                print("Saved credentials are invalid. Please log in again.")

        # If no saved credentials or they're invalid, ask for email and password
        while True:
            email = input("Enter your email: ").strip()
            password = getpass("Enter your password: ")

            try:
                self.z = Zlibrary(email=email, password=password)
                if self.z.isLoggedIn():
                    # Get and save remix values for future use
                    user_profile = self.z.getProfile()["user"]
                    self.save_credentials(
                        user_profile["id"], user_profile["remix_userkey"]
                    )
                    print("Login successful! Credentials saved for future use.")
                    return True
                else:
                    print("Login failed. Please try again.")
            except Exception as e:
                print(f"Login error: {str(e)}")
                retry = input("Would you like to try again? (y/n): ").lower()
                if retry != "y":
                    return False

    def search_and_show_results(self, query, limit=None):
        """Search for books and display results"""
        if limit is None:
            limit = self.config.DEFAULT_SEARCH_LIMIT
            
        results = self.z.search(
            message=query,
            limit=limit,
            languages=self.languages,
            extensions=self.formats
        )
        
        if not results.get("books"):
            print(f"No books found for query: {query}")
            return None

        print("\nFound books:")
        for i, book in enumerate(results["books"], 1):
            print(f"\n{i}. {book.get('title', 'No title')}")
            print(f"   Author: {book.get('author', 'Unknown')}")
            print(f"   Format: {book.get('extension', 'Unknown')} ({book.get('filesizeString', 'Unknown size')})")
            print(f"   Size: {book.get('size', 'Unknown')}")
            print(f"   Language: {book.get('language', 'Unknown')}")

        return results["books"]

    def download_book(self, book):
        """Download the selected book"""
        # Create downloads directory if it doesn't exist
        os.makedirs(self.download_dir, exist_ok=True)

        print(f"\nDownloading: {book.get('title', 'Unknown book')}")
        try:
            filename, content = self.z.downloadBook(book)
            filepath = os.path.join(self.download_dir, filename)

            with open(filepath, "wb") as f:
                f.write(content)

            print(f"Successfully downloaded to: {filepath}")
            return filepath
        except Exception as e:
            print(f"Error downloading book: {str(e)}")
            return None

    def auto_download_first_result(self, query):
        """Search and automatically download the first result"""
        results = self.z.search(
            message=query,
            limit=1,
            languages=self.languages,
            extensions=self.formats
        )
        
        if not results.get("books"):
            print(f"No books found for query: {query}")
            return None

        book = results["books"][0]
        print(f"Found book: {book.get('title', 'Unknown book')}")
        return self.download_book(book)


def main():
    parser = argparse.ArgumentParser(description="Download books from Z-Library")
    parser.add_argument(
        "--query", "-q", help="Search query for automatic download of first result"
    )
    parser.add_argument(
        "--download-dir", "-d",
        help="Set custom download directory",
        default=Config.DEFAULT_DOWNLOAD_DIR
    )
    parser.add_argument(
        "--languages", "-l",
        help="Comma-separated list of languages to search for (e.g., 'english,greek,french')",
        default=",".join(Config.DEFAULT_LANGUAGES)
    )
    parser.add_argument(
        "--formats", "-f",
        help="Comma-separated list of formats to search for (e.g., 'epub,pdf')",
        default=",".join(Config.DEFAULT_FORMATS)
    )

    args = parser.parse_args()

    downloader = BookDownloader()

    # Update download directory if specified
    if args.download_dir:
        downloader.download_dir = os.path.expanduser(args.download_dir)

    # Set languages and formats
    downloader.set_languages(args.languages)
    downloader.set_formats(args.formats)

    # Try to login first
    if not downloader.login():
        print("Unable to log in. Exiting...")
        return

    # Non-interactive mode
    if args.query:
        downloader.auto_download_first_result(args.query)
        return

    # Interactive mode
    while True:
        query = input("\nEnter book title to search (or 'quit' to exit): ").strip()
        if query.lower() == "quit":
            break

        books = downloader.search_and_show_results(query)
        if not books:
            continue

        while True:
            try:
                choice = input(
                    "\nEnter the number of the book to download (or 0 to search again): "
                )
                if choice == "0":
                    break

                book_index = int(choice) - 1
                if 0 <= book_index < len(books):
                    selected_book = books[book_index]
                    downloader.download_book(selected_book)
                    break
                else:
                    print("Invalid selection. Please try again.")
            except ValueError:
                print("Please enter a valid number.")


if __name__ == "__main__":
    main()
