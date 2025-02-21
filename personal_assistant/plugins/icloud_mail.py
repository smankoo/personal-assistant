import os
import re
import imaplib
import email
from email.header import decode_header
from datetime import datetime, timedelta
from dotenv import load_dotenv

# For debugging, we’re not using caching here.
# from personal_assistant.tools.caching import cached_output
from bs4 import BeautifulSoup

from personal_assistant.tools.caching import cached_output  # pip install beautifulsoup4

load_dotenv()

# Toggle debug prints for cleaning steps
DEBUG_CLEANING = False

ICLOUD_USERNAME = os.getenv("ICLOUD_USERNAME")
ICLOUD_PASSWORD = os.getenv("ICLOUD_APP_SPECIFIC_PASSWORD")
IMAP_SERVER = "imap.mail.me.com"
IMAP_PORT = 993

# Character limit for email bodies (applied after all cleaning steps)
BODY_CHAR_LIMIT = 500


def debug_print(label, content):
    if DEBUG_CLEANING:
        print(f"DEBUG: {label}:\n{content}\n{'='*40}")


def extract_email_body(msg, debug=False):
    """
    Extracts the email body by:
      1. Decoding the raw payload,
      2. Converting HTML to plain text (if applicable) via BeautifulSoup,
      3. Removing CSS rule blocks,
      4. Normalizing whitespace,
      5. Removing inline CSS-like sequences (e.g. ".bg-mobile, .sub-item-img-1, 96"),
      6. Finally applying the character limit.

    Debug prints show the state after each cleaning step.
    """
    body = None
    body_is_html = False

    # Step 0: Extract raw body from email parts
    if msg.is_multipart():
        # Prefer plain text part if available
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            if content_type == "text/plain" and "attachment" not in content_disposition:
                body = part.get_payload(decode=True)
                body_is_html = False
                break
        # Fallback: use HTML part if no plain text is found
        if body is None:
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/html":
                    body = part.get_payload(decode=True)
                    body_is_html = True
                    break
    else:
        body = msg.get_payload(decode=True)
        if msg.get_content_type() == "text/html":
            body_is_html = True

    if not body:
        return "[No body available]"

    # Step 1: Decode the body
    try:
        body = body.decode("utf-8", errors="ignore")
    except Exception as e:
        body = f"[Error decoding email body: {str(e)}]"
    debug_print("After decoding", body)

    # Step 2: Process HTML if applicable
    if body_is_html or re.search(r"<[^>]+>", body):
        soup = BeautifulSoup(body, "html.parser")
        # Remove <style> tags (which contain CSS rules)
        for style in soup.find_all("style"):
            style.decompose()
        # Extract text using newline as separator to preserve formatting
        text = soup.get_text(separator="\n")
        # Remove extra whitespace and blank lines
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        body = "\n".join(lines)
        debug_print("After BeautifulSoup processing", body)

    # Step 3: Remove CSS rule blocks (i.e. selectors followed by '{...}')
    css_pattern = re.compile(r"([.#][\w\-,\s]+)\s*\{.*?\}", flags=re.DOTALL)
    body = css_pattern.sub("", body)
    debug_print("After removing CSS blocks", body)

    # Step 4: Normalize whitespace (collapse multiple spaces/newlines)
    body = re.sub(r"\s{2,}", " ", body).strip()
    debug_print("After whitespace normalization", body)

    # Step 5: Remove inline CSS-like sequences
    # This regex targets sequences that look like a list of CSS classes:
    # e.g. ".bg-mobile, .sub-item-img-1, 96"
    css_inline_pattern = re.compile(
        r"\s*(\.[\w-]+(?:\s*,\s*\.[\w-]+)+(?:\s*,\s*\d+)?)\s*"
    )
    body = css_inline_pattern.sub(" ", body)
    debug_print("After removing inline CSS sequences", body)

    # (Optional) Normalize whitespace again after removal
    body = re.sub(r"\s{2,}", " ", body).strip()
    debug_print("After final whitespace normalization", body)

    # Step 6: Apply character limit after cleaning
    if len(body) > BODY_CHAR_LIMIT:
        body = body[:BODY_CHAR_LIMIT] + "..."
    debug_print("Final cleaned body", body)

    return body


# For debugging, caching is disabled.
@cached_output(max_age_seconds=60)
def get_recent_emails():
    if not ICLOUD_USERNAME or not ICLOUD_PASSWORD:
        return "Error: Please set ICLOUD_USERNAME and ICLOUD_PASSWORD in your environment variables."

    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(ICLOUD_USERNAME, ICLOUD_PASSWORD)
        mail.select("INBOX")

        # Define time range (last 2 days)
        since_date = (datetime.now() - timedelta(days=2)).strftime("%d-%b-%Y")
        status, messages = mail.search(None, f"(SINCE {since_date})")
        if status != "OK" or not messages[0]:
            return "No recent emails found."

        mail_ids = messages[0].split()
        email_list = []

        for num in mail_ids:
            status, data = mail.fetch(num, "(BODY.PEEK[])")
            if status != "OK" or not data:
                continue

            for response_part in data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])

                    # Decode Subject
                    subject_data = msg.get("Subject", "No Subject")
                    if subject_data:
                        decoded_subject = decode_header(subject_data)
                        subject, encoding = (
                            decoded_subject[0]
                            if decoded_subject
                            else ("No Subject", None)
                        )
                        if isinstance(subject, bytes):
                            subject = subject.decode(
                                encoding or "utf-8", errors="ignore"
                            )
                    else:
                        subject = "No Subject"

                    sender = msg.get("From", "Unknown Sender")
                    date = msg.get("Date", "No Date")
                    # Extract email body with debugging enabled
                    body_excerpt = extract_email_body(msg, debug=DEBUG_CLEANING)

                    formatted_email = (
                        f"📩 From: {sender}\n"
                        f"📝 Subject: {subject}\n"
                        f"📅 Date: {date}\n"
                        f"📜 Body: {body_excerpt}\n"
                        f"{'='*40}"
                    )
                    email_list.append(formatted_email)
        mail.logout()
        return "\n\n".join(email_list) if email_list else "No recent emails found."
    except Exception as e:
        return f"Error: {str(e)}"


def get_output():
    emails = get_recent_emails()
    return {
        "plugin_name": "icloud_mail",
        "output": emails,
    }


if __name__ == "__main__":
    result = get_output()
    print(result["output"])
