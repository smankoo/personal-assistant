#!/usr/bin/env python3
"""
Plugin: Outlook Calendar
This plugin fetches events from Microsoft Outlook for a specified date range (default: next 30 days)
and returns formatted event details as output.

Caching is implemented for 30 minutes to avoid repeated API calls.
"""

from appscript import app
from datetime import datetime, timedelta
import re
import icalendar
import os
import time
from html.parser import HTMLParser

# Import caching decorator from your project's tools
from personal_assistant.tools.caching import cached_output

# Constants
EVENT_BODY_CHAR_LIMIT = 50000
EVENT_ATTENDEE_LIMIT = 10

# Access Microsoft Outlook
outlook = app("Microsoft Outlook")


def get_date_range(option="this week", custom_start=None, custom_end=None):
    """Returns a start and end date based on the selected option."""
    today = datetime.now().date()
    
    if option == "this week":
        start_date = today - timedelta(days=today.weekday())  # Monday of this week
        end_date = start_date + timedelta(days=4)  # Friday of this week

    elif option == "rest of the week":
        start_date = today
        end_date = today + timedelta(days=(4 - today.weekday()))  # Up to Friday

    elif option == "today":
        start_date = today
        end_date = today

    elif option == "next 7 days":
        start_date = today
        end_date = today + timedelta(days=7)

    elif option == "next 30 days":
        start_date = today
        end_date = today + timedelta(days=30)

    elif option == "custom":
        if custom_start and custom_end:
            start_date = custom_start
            end_date = custom_end
        else:
            raise ValueError("Custom option requires start and end dates")
    else:
        raise ValueError("Invalid option selected")

    return start_date, end_date


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


def parse_ical_string(ics_string):
    """Parses an iCalendar string and returns an icalendar.Calendar object."""
    if isinstance(ics_string, str):
        ics_string = ics_string.encode('utf-8')
    return icalendar.Calendar.from_ical(ics_string)


def get_clean_body(input_text):
    """Cleans the body of an event by removing extra spacing and duplicate line breaks."""
    input_text = strip_html(input_text)
    cleaned_body = re.sub(r'\s+', ' ', input_text).strip()
    cleaned_body = re.sub(r'\n+', '\n', cleaned_body).strip()
    return cleaned_body


def get_attendee_string(attendee):
    """Formats an attendee object into a human-readable string."""
    params = attendee.params if hasattr(attendee, 'params') else {}
    if params:
        email = str(attendee).replace('MAILTO:', '')
        name = params.get('CN', 'No Name')
        attendee_string = f"{name} <{email}>"
    else:
        attendee_string = str(attendee).removeprefix('MAILTO:')
    return attendee_string


def fetch_events(option="next 30 days", custom_start=None, custom_end=None):
    """Fetches events from Outlook based on the selected date range."""
    start_date, end_date = get_date_range(option, custom_start, custom_end)
    events_list = []
    for calendar in outlook.calendars():
        for event in calendar.calendar_events():
            start_time = event.start_time()
            end_time = event.end_time()

            if start_time and end_time:
                event_start_date = start_time.date()
                event_end_date = end_time.date()

                # Include event if any part falls within the range
                if event_start_date <= end_date and event_end_date >= start_date:
                    try:
                        organizer = event.organizer()
                        total_attendees_count = len(event.attendees())
                        icalendar_data = event.icalendar_data()
                        cal = parse_ical_string(icalendar_data)

                        attendee_limit = EVENT_ATTENDEE_LIMIT
                        attendees = []
                        all_attendees_string = ""
                        # Process only the first VEVENT component
                        for component in cal.walk('VEVENT'):
                            attendee_list = component.get('attendee', [])
                            if isinstance(attendee_list, icalendar.prop.vCalAddress):
                                attendee_list = [attendee_list]

                            attendee_ctr = 0
                            for attendee in attendee_list:
                                attendee_ctr += 1
                                attendee_string = get_attendee_string(attendee)
                                attendees.append(attendee_string)
                                if attendee_ctr >= attendee_limit:
                                    break
                            break

                        if attendees:
                            all_attendees_string = ", ".join(attendees)
                            if total_attendees_count > attendee_limit:
                                all_attendees_string += f" and {total_attendees_count - attendee_limit} more..."
                        else:
                            all_attendees_string = "No attendees listed"

                        raw_body = event.content() if event.content() else "No details provided."
                        clean_body = get_clean_body(raw_body)

                        event_details = {
                            "Subject": event.subject(),
                            "Start": start_time,
                            "End": end_time,
                            "Location": event.location() if event.location() else "-",
                            "Organizer": organizer,
                            "Attendees": all_attendees_string,
                            "Total Attendees": total_attendees_count,
                            "Body": clean_body[:EVENT_BODY_CHAR_LIMIT] + ("..." if len(clean_body) > EVENT_BODY_CHAR_LIMIT else ""),
                        }
                    except Exception as e:
                        event_details = {
                            "Subject": event.subject(),
                            "Start": start_time,
                            "End": end_time,
                            "Location": event.location() if event.location() else "-",
                            "Organizer": "Unknown",
                            "Attendees": "Unable to retrieve attendees",
                            "Body": "Unable to retrieve details."
                        }
                    events_list.append(event_details)
    return events_list


@cached_output(max_age_seconds=1800)
def get_outlook_calendar_text():
    """
    Compiles and returns a formatted string of Outlook events.
    This function is cached for 30 minutes.
    """
    events_list = fetch_events(option="next 30 days")
    if not events_list:
        return "No events found in the specified date range."
    output_lines = ["[[ Outlook Calendar ]]"]
    for event in events_list:
        for attr, value in event.items():
            output_lines.append(f"{attr}: {value}")
        output_lines.append("")  # Blank line between events
    return "\n".join(output_lines)


def get_output():
    """Plugin entry point for Outlook Calendar. Returns formatted event details."""
    try:
        output = get_outlook_calendar_text()
    except Exception as e:
        output = f"Error fetching Outlook events: {e}"
    return {"plugin_name": "outlook_calendar", "output": output}


if __name__ == "__main__":
    result = get_output()
    print(result["output"])
