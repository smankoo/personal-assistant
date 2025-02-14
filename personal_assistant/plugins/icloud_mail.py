import os
import imaplib
import email
from email.header import decode_header
from datetime import datetime, timedelta
from dotenv import load_dotenv
from personal_assistant.tools.caching import cached_output

load_dotenv()

ICLOUD_USERNAME = os.getenv("ICLOUD_USERNAME")
ICLOUD_PASSWORD = os.getenv("ICLOUD_APP_SPECIFIC_PASSWORD")
IMAP_SERVER = "imap.mail.me.com"
IMAP_PORT = 993

# Character limit for email bodies
BODY_CHAR_LIMIT = 500


def extract_email_body(msg):
    """
    Extracts the plain text or HTML email body while limiting character count.
    """
    body = None

    if msg.is_multipart():
        # Iterate over parts to find plain text
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))

            if content_type == "text/plain" and "attachment" not in content_disposition:
                body = part.get_payload(decode=True)
                break  # Prefer plain text if available
            elif content_type == "text/html" and not body:  # Use HTML as fallback
                body = part.get_payload(decode=True)

    else:
        body = msg.get_payload(decode=True)  # Handle non-multipart emails

    # Decode and clean body
    if body:
        try:
            body = body.decode("utf-8", errors="ignore")  # Decode safely
        except Exception as e:
            body = f"[Error decoding email body: {str(e)}]"

        # Trim body to character limit
        return body[:BODY_CHAR_LIMIT] + ("..." if len(body) > BODY_CHAR_LIMIT else "")

    return "[No body available]"


@cached_output(max_age_seconds=3600)  # Cache expires in 1 hour
def get_recent_emails():
    if not ICLOUD_USERNAME or not ICLOUD_PASSWORD:
        return "Error: Please set ICLOUD_USERNAME and ICLOUD_PASSWORD in your environment variables."

    try:
        # Connect to iCloud Mail
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(ICLOUD_USERNAME, ICLOUD_PASSWORD)
        mail.select("INBOX")

        # Define the time range (last 24 hours)
        since_date = (datetime.now() - timedelta(days=2)).strftime("%d-%b-%Y")
        status, messages = mail.search(None, f"(SINCE {since_date})")

        if status != "OK" or not messages[0]:
            return "No recent emails found."

        mail_ids = messages[0].split()
        email_list = []

        for num in mail_ids:
            status, data = mail.fetch(
                num, "(BODY.PEEK[])"
            )  # Fetch without marking as read
            if status != "OK" or not data:
                continue

            for response_part in data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])

                    # Extract and decode Subject
                    subject_data = msg.get("Subject", "No Subject")
                    if subject_data:
                        decoded_subject = decode_header(subject_data)
                        subject, encoding = (
                            decoded_subject[0]
                            if decoded_subject
                            else ("No Subject", None)
                        )
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding or "utf-8")
                    else:
                        subject = "No Subject"

                    sender = msg.get("From", "Unknown Sender")
                    date = msg.get("Date", "No Date")

                    # Extract email body with character limit
                    body_excerpt = extract_email_body(msg)

                    # Format extracted data
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
