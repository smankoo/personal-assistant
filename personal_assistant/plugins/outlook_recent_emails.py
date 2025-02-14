#!/usr/bin/env python3
"""
Plugin: Outlook Recent Emails
This plugin fetches recent emails from Microsoft Outlook's inbox that were received 
since the last working day (Monday-Friday). It returns a formatted string of email details.

Caching is implemented for 30 minutes to avoid repeated API calls.
"""

from appscript import app, k
from datetime import datetime, timedelta
import re
import os
from html.parser import HTMLParser

# Import caching decorator from project tools
from personal_assistant.tools.caching import cached_output

# Access Microsoft Outlook
outlook = app("Microsoft Outlook")

# Constant for email body character limit
EMAIL_BODY_CHAR_LIMIT = 50000

def get_last_working_day():
    """Returns the last working day (Mon-Fri) before today."""
    today = datetime.now().date()
    if today.weekday() == 0:  # Monday: last working day is Friday
        return today - timedelta(days=3)
    else:
        return today - timedelta(days=1)

class HTMLStripper(HTMLParser):
    """Helper class to strip HTML tags from a string."""
    def __init__(self):
        super().__init__()
        self.reset()
        self.fed = []
    
    def handle_data(self, d):
        self.fed.append(d)
    
    def get_data(self):
        return " ".join(self.fed).strip()

def strip_html(html):
    """Strips HTML tags, removes styles/scripts, and returns plain text."""
    if not html:
        return "No details provided."
    # Remove style and script sections
    html = re.sub(r"<(script|style).*?>.*?</\1>", "", html, flags=re.DOTALL)
    stripper = HTMLStripper()
    stripper.feed(html)
    return stripper.get_data()

def get_clean_body(input_text):
    """Cleans the email body by removing extra spacing and duplicate line breaks."""
    input_text = strip_html(input_text)
    cleaned_body = re.sub(r'\s+', ' ', input_text).strip()
    cleaned_body = re.sub(r'\n+', '\n', cleaned_body).strip()
    return cleaned_body

def get_recipient_string(rec):
    """Safely retrieves recipient details from Outlook's dictionary-like recipient object."""
    try:
        if isinstance(rec, dict):
            name = rec.get(k.name, "Unknown")
            email_addr = rec.get(k.address, "Unknown")
            return f"{name} <{email_addr}>"
        else:
            return "Unknown"
    except Exception as e:
        return f"Error retrieving recipient: {e}"

def get_sender_string(email):
    """Safely retrieves sender details from Outlook's dictionary-like sender object."""
    try:
        sender = email.sender()
        if isinstance(sender, dict):
            name = sender.get(k.name, "Unknown")
            email_addr = sender.get(k.address, "Unknown")
            return f"{name} <{email_addr}>"
        else:
            return "Unknown"
    except Exception as e:
        return f"Error retrieving sender: {e}"

def fetch_emails():
    """Fetches emails from Outlook since the last working day."""
    last_working_day = get_last_working_day()
    emails_list = []
    inbox = outlook.inbox()
    
    for email in inbox.messages():
        try:
            received_time = email.time_received()
            if received_time.date() >= last_working_day:
                sender_str = get_sender_string(email)
                
                # Retrieve recipients safely
                try:
                    recipients = email.to_recipients()
                    recipient_list = ", ".join(get_recipient_string(rec) for rec in recipients)
                except Exception:
                    recipient_list = "Error retrieving recipients"
                
                raw_body = email.content() if email.content() else "No details provided."
                clean_body = get_clean_body(raw_body)
                
                email_details = {
                    "Subject": email.subject(),
                    "Received Time": received_time,
                    "Sender": sender_str,
                    "Recipients": recipient_list,
                    "Body": clean_body[:EMAIL_BODY_CHAR_LIMIT] + ("..." if len(clean_body) > EMAIL_BODY_CHAR_LIMIT else ""),
                }
                emails_list.append(email_details)
        except Exception as e:
            print(f"Error retrieving email details: {e}")
    
    return emails_list

@cached_output(max_age_seconds=1800)
def get_outlook_emails_text():
    """
    Compiles and returns a formatted string of recent Outlook emails.
    This function is cached for 30 minutes.
    """
    emails_list = fetch_emails()
    if not emails_list:
        return "No emails found since the last working day."
    
    output_lines = ["[[ Recent Outlook Emails ]]"]
    for email in emails_list:
        for attr, value in email.items():
            output_lines.append(f"{attr}: {value}")
        output_lines.append("")  # Blank line between emails
    return "\n".join(output_lines)

def get_output():
    """Plugin entry point for Outlook Recent Emails. Returns formatted email details."""
    try:
        output = get_outlook_emails_text()
    except Exception as e:
        output = f"Error fetching Outlook emails: {e}"
    return {"plugin_name": "outlook_recent_emails", "output": output}

if __name__ == "__main__":
    result = get_output()
    print(result["output"])
