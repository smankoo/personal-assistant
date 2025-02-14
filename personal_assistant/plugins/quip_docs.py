#!/usr/bin/env python3
"""
Plugin: Quip Documents Downloader
This plugin retrieves recent Quip document threads using the Quip API,
processes the HTML content (converting it to Markdown and adding YAML front matter),
saves each document as a text file under the "output" directory, and returns
a summary of the processing. 

Caching is implemented for 7 days (604800 seconds) to avoid repeated API calls.
"""

import os
import re
import time
import requests
import json
import html2text
import yaml
from dotenv import load_dotenv

# Load environment variables from the .env file.
load_dotenv()

# Get the Quip API token from the environment.
ACCESS_TOKEN = os.getenv("QUIP_PERSONAL_ACCESS_TOKEN")
if not ACCESS_TOKEN:
    raise ValueError(
        "Quip API token not found. Please add QUIP_PERSONAL_ACCESS_TOKEN to your .env file."
    )

# Base URL for Quip's platform.
BASE_URL = os.getenv("QUIP_BASE_URL")
if not BASE_URL:
    raise ValueError(
        "Quip base URL not found. Please add QUIP_BASE_URL to your .env file."
    )

# Adjustable number of recent documents to fetch.
NUM_RECENT_DOCS = 1

###############################################################################
# RateLimiter class to track API calls made in the last 60 seconds.
###############################################################################


class RateLimiter:
    def __init__(self, max_calls=49, safe_threshold=45, window=60, wait_time=10):
        """
        Args:
            max_calls: When the count reaches this number, the script will pause.
            safe_threshold: Resume API calls only when the count has dropped to this value or lower.
            window: Time window in seconds over which calls are counted.
            wait_time: How long (in seconds) to sleep before re-checking the count.
        """
        self.max_calls = max_calls
        self.safe_threshold = safe_threshold
        self.window = window
        self.wait_time = wait_time
        self.timestamps = []  # List of UNIX timestamps of recent API calls.

    def record_call(self):
        now = time.time()
        self.timestamps.append(now)
        self.clean_old_calls()

    def clean_old_calls(self):
        now = time.time()
        # Keep only timestamps within the window.
        self.timestamps = [ts for ts in self.timestamps if now - ts < self.window]

    def get_count(self):
        self.clean_old_calls()
        return len(self.timestamps)

    def wait_if_necessary(self):
        """
        Check the running count of API calls in the last minute.
        If the count is >= max_calls, pause until the count drops to safe_threshold or below.
        """
        self.clean_old_calls()
        count = self.get_count()
        if count >= self.max_calls:
            print(
                f"[RateLimiter] Rate limit reached: {count} calls in the last {self.window} seconds. Waiting {self.wait_time} seconds..."
            )
        while count >= self.max_calls:
            time.sleep(self.wait_time)
            self.clean_old_calls()
            count = self.get_count()
            print(
                f"[RateLimiter] After waiting, {count} calls in the last {self.window} seconds."
            )
        if count > self.safe_threshold:
            print(
                f"[RateLimiter] Proceeding with caution; current API call count is {count} (safe threshold is {self.safe_threshold})."
            )


# Create a global rate limiter instance.
rate_limiter = RateLimiter()


def make_api_call(url: str, headers: dict) -> requests.Response:
    """
    Wraps requests.get with rate limiting.
    Before making the API call, it waits if the number of API calls in the last
    minute is too high. After the call, it records the call timestamp.
    """
    rate_limiter.wait_if_necessary()
    response = requests.get(url, headers=headers)
    rate_limiter.record_call()
    return response


###############################################################################
# Helper Functions for Quip API Calls
###############################################################################


def sanitize_filename(name: str) -> str:
    """
    Sanitize a string so it is safe to use as a filename.
    Removes characters not allowed in filenames and replaces spaces with underscores.
    """
    sanitized = re.sub(r'[\\/*?:"<>|]', "", name)
    return re.sub(r"\s+", "_", sanitized.strip())


def convert_html_to_markdown(html: str) -> str:
    """
    Convert HTML content to Markdown while preserving the document's structure.
    """
    converter = html2text.HTML2Text()
    converter.ignore_links = False  # Keep links
    converter.ignore_images = False  # Keep images if needed
    converter.ignore_emphasis = False  # Preserve emphasis
    converter.body_width = 0  # Prevent line wrapping
    return converter.handle(html)


def get_user_name(user_id: str) -> str:
    """
    Retrieve the user details for a given user_id using the /1/users/{user_id} endpoint,
    and return the user's name. If an error occurs, return the user_id as a fallback.
    """
    url = f"{BASE_URL}/1/users/{user_id}"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    response = make_api_call(url, headers)
    if response.status_code == 200:
        data = response.json()
        return data.get("name", user_id)
    else:
        print(
            f"[User] Error fetching details for user {user_id}: {response.status_code} - {response.text}"
        )
        return user_id


def get_thread_metadata(thread_id: str) -> dict:
    """
    Retrieve metadata for a single thread using the v2 endpoint.
    Returns a dictionary containing the thread metadata or None if an error occurs.
    """
    url = f"{BASE_URL}/2/threads/{thread_id}"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    response = make_api_call(url, headers)
    if response.status_code == 200:
        return response.json().get("thread", {})
    else:
        print(
            f"[Metadata] Error fetching metadata for thread {thread_id}: {response.status_code} - {response.text}"
        )
        return None


def get_all_thread_metadata() -> list:
    """
    Retrieves all thread IDs from the current user's threads endpoint (with pagination)
    and obtains metadata for each thread using the v2 endpoint.
    Returns a list of metadata dictionaries.
    """
    metadata_list = []
    cursor = None
    while True:
        url = f"{BASE_URL}/1/users/current/threads"
        if cursor:
            url += f"&cursor={cursor}"
        headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
        response = make_api_call(url, headers)
        if response.status_code != 200:
            print(
                f"[UserThreads] Error fetching threads: {response.status_code} - {response.text}"
            )
            break
        data = response.json()
        threads_data = data.get("threads", {})
        for thread_id in threads_data.keys():
            meta = get_thread_metadata(thread_id)
            if meta:
                meta.setdefault("id", thread_id)
                metadata_list.append(meta)
        # Check for pagination
        response_metadata = data.get("response_metadata", {})
        cursor = response_metadata.get("next_cursor")
        if not cursor:
            break
    return metadata_list


def get_recent_documents_recent_api(num_docs: int) -> list:
    """
    Retrieves the most recent threads using the /1/threads/recent endpoint,
    obtains full metadata for each thread using the v2 endpoint, filters for DOCUMENT-type threads
    authored by the current user, and returns the top `num_docs` sorted by update time.

    Returns a list of tuples: (thread_id, title, updated_usec, author_id)
    """
    url = f"{BASE_URL}/1/threads/recent?count=50"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    response = make_api_call(url, headers)
    if response.status_code != 200:
        print(
            f"[Recent] Error fetching recent threads: {response.status_code} - {response.text}"
        )
        return []
    recent_threads = response.json()  # A dict mapping thread IDs to thread info.
    metadata_list = []
    # Retrieve current user ID from metadata of one thread (fallback if needed)
    current_user_id = None
    for thread_id in recent_threads.keys():
        meta = get_thread_metadata(thread_id)
        if meta and "author_id" in meta:
            current_user_id = meta.get("author_id")
            break
    if not current_user_id:
        print("[Recent] Unable to determine current user's ID.")
        return []
    for thread_id in recent_threads.keys():
        meta = get_thread_metadata(thread_id)
        if meta and meta.get("type", "").upper() == "DOCUMENT":
            meta.setdefault("id", thread_id)
            metadata_list.append(meta)
    # Filter so that only documents authored by the current user are included.
    metadata_list = [m for m in metadata_list if m.get("author_id") == current_user_id]
    if not metadata_list:
        print("[Recent] No document threads authored by the current user were found.")
        return []
    metadata_list.sort(key=lambda m: int(m.get("updated_usec", 0)), reverse=True)
    return [
        (
            m.get("id"),
            m.get("title", "Untitled Document"),
            m.get("updated_usec", "0"),
            m.get("author_id", "Unknown"),
        )
        for m in metadata_list[:num_docs]
    ]


def get_thread_html(thread_id: str) -> str:
    """
    Fetch the HTML content of a document thread using the v2 endpoint.
    Returns the HTML content as a string, or None if an error occurs.
    """
    url = f"{BASE_URL}/2/threads/{thread_id}/html"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    response = make_api_call(url, headers)
    if response.status_code == 200:
        data = response.json()
        return data.get("html", "")
    else:
        print(
            f"[HTML] Error fetching HTML for thread {thread_id}: {response.status_code} - {response.text}"
        )
        return None


def save_document_to_file(title: str, content: str, output_dir: str = "output") -> None:
    """
    Save the provided content into a file whose name is based on the document title.
    The file is named as 'quip_<sanitized_title>.txt' and stored under the specified output directory.
    """
    os.makedirs(output_dir, exist_ok=True)
    sanitized_title = sanitize_filename(title)
    filename = f"quip_{sanitized_title}.txt"
    filepath = os.path.join(output_dir, filename)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[Save] Document '{title}' saved to '{filepath}'.")
    except IOError as e:
        print(f"[Save] Error saving file {filepath}: {e}")


def generate_front_matter(meta: dict) -> str:
    """
    Convert the metadata dictionary to a YAML-formatted string.
    """
    return yaml.dump(meta, default_flow_style=False, sort_keys=False)


def format_metadata(meta: dict) -> dict:
    """
    Convert metadata values to human-readable form.
    For example, convert timestamps (in microseconds) to readable strings,
    and resolve user IDs to names for 'author_id' and 'creator_id'.
    """
    formatted = {}
    formatted["id"] = meta.get("id", "Unknown")
    formatted["title"] = meta.get("title", "Untitled Document")
    formatted["type"] = meta.get("type", "Unknown")

    if "updated_usec" in meta:
        try:
            formatted["last_modified"] = time.ctime(
                int(meta["updated_usec"]) // 1000000
            )
        except Exception:
            formatted["last_modified"] = meta["updated_usec"]
    if "created_usec" in meta:
        try:
            formatted["created"] = time.ctime(int(meta["created_usec"]) // 1000000)
        except Exception:
            formatted["created"] = meta["created_usec"]

    if "author_id" in meta:
        formatted["last_modified_by"] = get_user_name(meta["author_id"])
    if "creator_id" in meta:
        formatted["author"] = get_user_name(meta["creator_id"])
    else:
        if "author_id" in meta:
            formatted["author"] = get_user_name(meta["author_id"])

    return formatted


###############################################################################
# Plugin Main Functionality with Caching
###############################################################################

# Import the caching decorator from our project tools.
from personal_assistant.tools.caching import cached_output


# Cache the compiled output for 7 days (604800 seconds).
@cached_output(max_age_seconds=604800)
def compile_quip_documents_output() -> str:
    """
    Compiles recent Quip document data:
      - Retrieves the most recent document threads (authored by the current user)
      - For each document, fetches the HTML content, converts it to Markdown,
        adds YAML front matter (based on thread metadata), and saves the document to a file.
      - Returns a summary of the processed documents.
    """
    recent_docs = get_recent_documents_recent_api(NUM_RECENT_DOCS)
    if not recent_docs:
        return "No recent documents found."

    summary_lines = []
    total_docs = len(recent_docs)
    summary_lines.append(f"Found {total_docs} recent document(s).")

    for idx, doc in enumerate(recent_docs, start=1):
        thread_id, title, updated_usec, author_id = doc
        summary_lines.append(
            f"[{idx}/{total_docs}] Processing document: '{title}' (ID: {thread_id})"
        )
        html_content = get_thread_html(thread_id)
        if html_content is None:
            summary_lines.append(
                f"[{idx}/{total_docs}] Skipped document '{title}' due to error fetching content."
            )
            continue
        markdown_content = convert_html_to_markdown(html_content)
        meta = get_thread_metadata(thread_id)
        if meta is None:
            summary_lines.append(
                f"[{idx}/{total_docs}] Skipped document '{title}' due to missing metadata."
            )
            continue
        formatted_meta = format_metadata(meta)
        front_matter = generate_front_matter(formatted_meta)
        content_with_front_matter = f"---\n{front_matter}---\n\n{markdown_content}"
        save_document_to_file(title, content_with_front_matter)
        summary_lines.append(f"[{idx}/{total_docs}] Completed processing '{title}'.")

    return "\n".join(summary_lines)


###############################################################################
# Plugin Entry Point
###############################################################################


def get_output():
    """
    Plugin entry point.
    Returns a dictionary with the plugin name and the compiled output summary.
    """
    try:
        output = compile_quip_documents_output()
    except Exception as e:
        output = f"Error processing Quip documents: {e}"
    return {"plugin_name": "quip_documents", "output": output}


if __name__ == "__main__":
    result = get_output()
    print(result["output"])
