#!/usr/bin/env python3
"""
Plain Text Email Plugin with Caching

This plugin connects to an IMAP server using credentials defined in your environment
variables, retrieves recent emails (within the specified lookback period), and returns
a formatted string that includes the sender, subject, date, and email body of each email.

The output of fetching and formatting emails is cached for 5 minutes.
"""

import imaplib
import email
from bs4 import BeautifulSoup
import re
import os
import datetime
from datetime import timezone
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Configuration from environment variables (or defaults)
IMAP_HOST = os.getenv("PROTONMAIL_IMAP_HOST", "127.0.0.1")
IMAP_PORT = int(os.getenv("PROTONMAIL_IMAP_PORT", 1143))
USERNAME = os.getenv("PROTONMAIL_USERNAME")
PASSWORD = os.getenv("PROTONMAIL_PASSWORD")
LOOKBACK_HOURS = int(os.getenv("EMAIL_LOOKBACK_HOURS", 48))
EMAIL_BODY_CHAR_LIMIT = int(os.getenv("EMAIL_BODY_CHAR_LIMIT", 1000))

# Import caching decorator from your project
from personal_assistant.tools.caching import cached_output


class PlainTextEmailClient:
    """
    A plain text email client that connects to an IMAP server,
    retrieves recent emails, and extracts a cleaned, plain-text version of the email body.
    """

    def __init__(
        self,
        imap_host,
        imap_port,
        username,
        password,
        lookback_hours=48,
        char_limit=1000,
    ):
        self.imap_host = imap_host
        self.imap_port = imap_port
        self.username = username
        self.password = password
        self.lookback_hours = lookback_hours
        self.char_limit = char_limit

    def clean_text(self, text):
        """
        Clean the text while preserving newline characters.
        Splits the text into lines, cleans up extra spaces on each line,
        and rejoins them with newline characters.
        """
        lines = text.splitlines()
        cleaned_lines = [re.sub(r"[ \t]+", " ", line).strip() for line in lines]
        return "\n".join(cleaned_lines)

    def separate_quotes(self, text):
        """
        Inserts an extra newline before common quoted text markers.
        For example, text like "On Tue, Sep 17, 2024 at ... wrote:".
        """
        pattern = re.compile(r"( ?on\s+.+wrote:)", re.IGNORECASE)
        return pattern.sub(r"\n\n\1", text)

    def _is_html(self, text):
        """
        Check if the provided text looks like HTML.
        """
        text = text.lstrip().lower()
        return text.startswith("<!doctype html") or text.startswith("<html")

    def parse_html(self, html_content):
        """
        Parse HTML content and extract the visible text.
        Unwanted elements (script, style, etc.) are removed.
        """
        soup = BeautifulSoup(html_content, "html.parser")
        for tag in soup(["script", "style", "head", "title", "meta", "[document]"]):
            tag.decompose()
        body_tag = soup.find("body")
        if body_tag:
            text = body_tag.get_text(separator="\n", strip=True)
        else:
            text = soup.get_text(separator="\n", strip=True)
        return text

    def extract_body(self, msg):
        """
        Given an email.message.Message object, extract the best available plain-text body.
        Prefers a text/plain part; if that part appears to be HTML (or is missing),
        it falls back to a text/html part.
        """
        body = None

        if msg.is_multipart():
            # First try to find a text/plain part.
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disp = part.get("Content-Disposition", "")
                if content_type == "text/plain" and "attachment" not in content_disp:
                    try:
                        candidate = part.get_payload(decode=True).decode(
                            errors="ignore"
                        )
                    except Exception:
                        continue
                    if self._is_html(candidate):
                        candidate = self.parse_html(candidate)
                    body = candidate
                    if body:
                        break
            # Fallback to text/html part if needed.
            if not body:
                for part in msg.walk():
                    if part.get_content_type() == "text/html":
                        try:
                            html_content = part.get_payload(decode=True)
                            body = self.parse_html(html_content)
                        except Exception:
                            continue
                        if body:
                            break
        else:
            # Non-multipart: process based on content type.
            try:
                payload = msg.get_payload(decode=True)
                candidate = payload.decode(errors="ignore") if payload else ""
            except Exception:
                candidate = str(msg.get_payload())
            if msg.get_content_type() == "text/html" or self._is_html(candidate):
                body = self.parse_html(candidate)
            else:
                body = candidate

        if not body:
            return "(No content available)"
        # Limit characters, clean text, and separate quoted content.
        cleaned = self.clean_text(body[: self.char_limit])
        cleaned = self.separate_quotes(cleaned)
        return cleaned

    def fetch_emails(self):
        """
        Connect to the IMAP server, search for emails within the lookback period,
        and return a list of dictionaries with keys: 'from', 'subject', 'date', and 'body'.
        """
        emails = []
        try:
            mail = imaplib.IMAP4(self.imap_host, self.imap_port)
            mail.starttls()
            mail.login(self.username, self.password)
            mail.select("inbox")

            date_filter = (
                datetime.datetime.now(timezone.utc)
                - datetime.timedelta(hours=self.lookback_hours)
            ).strftime("%d-%b-%Y")
            result, data = mail.search(None, f"SINCE {date_filter}")
            if result != "OK":
                raise Exception("Failed to search emails")

            mail_ids = data[0].split()

            for mail_id in mail_ids:
                result, msg_data = mail.fetch(mail_id, "(RFC822)")
                if result != "OK":
                    continue
                for response in msg_data:
                    if isinstance(response, tuple):
                        msg = email.message_from_bytes(response[1])
                        try:
                            email_date = email.utils.parsedate_to_datetime(
                                msg.get("Date")
                            ).astimezone(timezone.utc)
                        except Exception:
                            email_date = datetime.datetime.now(timezone.utc)
                        cutoff = datetime.datetime.now(
                            timezone.utc
                        ) - datetime.timedelta(hours=self.lookback_hours)
                        if email_date >= cutoff:
                            body_text = self.extract_body(msg)
                            emails.append(
                                {
                                    "from": msg.get("From"),
                                    "subject": msg.get("Subject"),
                                    "date": msg.get("Date"),
                                    "body": body_text,
                                }
                            )
            mail.logout()
        except Exception as e:
            return [
                {
                    "from": "",
                    "subject": "Error",
                    "date": "",
                    "body": f"Error fetching emails: {e}",
                }
            ]
        return emails


@cached_output(max_age_seconds=300)  # Cache expires in 5 minutes
def get_emails_text():
    """
    Fetch and format emails using PlainTextEmailClient.
    The output of this function is cached for 5 minutes.
    """
    # Check if required credentials are set
    if not USERNAME or not PASSWORD:
        return "Email credentials not set in environment variables."

    client = PlainTextEmailClient(
        imap_host=IMAP_HOST,
        imap_port=IMAP_PORT,
        username=USERNAME,
        password=PASSWORD,
        lookback_hours=LOOKBACK_HOURS,
        char_limit=EMAIL_BODY_CHAR_LIMIT,
    )

    emails = client.fetch_emails()
    output_lines = [f"### Inbox (Last {LOOKBACK_HOURS} Hours) ###\n"]

    for mail_data in emails:
        output_lines.append(f"From: {mail_data.get('from', 'Unknown')}")
        output_lines.append(f"Subject: {mail_data.get('subject', 'No Subject')}")
        output_lines.append(f"Date: {mail_data.get('date', 'No Date')}")
        output_lines.append("Body:")
        output_lines.append(mail_data.get("body", ""))
        output_lines.append("-" * 40)

    return "\n".join(output_lines)


def get_output():
    """
    Plugin entry point.
    Returns a dictionary with the plugin name and the cached email output.
    """
    output_text = get_emails_text()
    return {"plugin_name": "Plain Text Email", "output": output_text}


if __name__ == "__main__":
    # Allow standalone testing
    result = get_output()
    print(result["output"])
