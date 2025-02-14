import os
from datetime import datetime, timedelta
from calendar import monthrange
from dotenv import load_dotenv
from tzlocal import get_localzone_name
from pyicloud import PyiCloudService
from pyicloud.services import calendar as calendar_service
from personal_assistant.tools.caching import cached_output

from dotenv import load_dotenv

load_dotenv()

import keyring
import keyring.backends.macOS

keyring.set_keyring(keyring.backends.macOS.Keyring())


# --- Begin Monkey Patch ---
def patched_refresh_client(self, from_dt=None, to_dt=None):
    today = datetime.today()
    first_day, last_day = monthrange(today.year, today.month)
    if not from_dt:
        from_dt = datetime(today.year, today.month, first_day)
    if not to_dt:
        to_dt = datetime(today.year, today.month, last_day)
    params = dict(self.params)
    params.update(
        {
            "lang": "en-us",
            "usertz": get_localzone_name(),
            "startDate": from_dt.strftime("%Y-%m-%d"),
            "endDate": to_dt.strftime("%Y-%m-%d"),
            "dsid": self.session.service.data["dsInfo"]["dsid"],
        }
    )
    req = self.session.get(self._calendar_refresh_url, params=params)
    self.response = req.json()


# Apply the monkey patch
calendar_service.CalendarService.refresh_client = patched_refresh_client
# --- End Monkey Patch ---

# Load environment variables
load_dotenv()
ICLOUD_USERNAME = os.getenv("ICLOUD_USERNAME")
ICLOUD_PASSWORD = os.getenv("ICLOUD_PASSWORD")


def parse_icloud_date(value):
    """
    Parse an iCloud date value.
    Expected format: [YYYYMMDD, year, month, day, hour, minute, minute_of_day]
    """
    if isinstance(value, list) and len(value) >= 6:
        year, month, day, hour, minute = value[1:6]
        # Construct a naive datetime (adjust for timezone if needed)
        return datetime(year, month, day, hour, minute)
    elif isinstance(value, (int, float)):
        return datetime.fromtimestamp(value)
    elif isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%f%z")
        except ValueError:
            return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z")
    else:
        raise ValueError(f"Unsupported date format: {value}")


@cached_output(max_age_seconds=3600)  # Cache expires in 1 hour
def get_calendar_text():
    if not ICLOUD_USERNAME or not ICLOUD_PASSWORD:
        return "Error: Please set ICLOUD_USERNAME and ICLOUD_PASSWORD in your environment variables."

    api = PyiCloudService(ICLOUD_USERNAME, ICLOUD_PASSWORD)

    # Handle 2FA: Interactive input is not ideal in plugin mode.
    if api.requires_2fa:
        return (
            "Error: Two-factor authentication required. Please complete 2FA manually."
        )

    if not api.is_trusted_session:
        api.trust_session()

    # Define the current week timeframe
    start_of_week = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_week = start_of_week + timedelta(days=6, hours=23, minutes=59)

    # Fetch calendar events for the week
    events = api.calendar.events(start_of_week, end_of_week)

    def get_timestamp(value):
        return value[0] if isinstance(value, list) else value

    if not events:
        return "No events found for this week."

    complete_calendar_text = "### Calendar Events ###\n"

    api.calendar.calendars

    # Updated event loop:
    for event in sorted(events, key=lambda e: parse_icloud_date(e["startDate"])):
        start_dt = parse_icloud_date(event["startDate"])
        end_dt = parse_icloud_date(event["endDate"])
        title = event.get("title", "No Title")
        location = event.get("location", "No Location")

        complete_calendar_text += f"Event: {title}\n"
        complete_calendar_text += (
            f"Start: {start_dt.strftime('%A, %B %d %Y %I:%M %p')}\n"
        )
        complete_calendar_text += f"End: {end_dt.strftime('%A, %B %d %Y %I:%M %p')}\n"
        complete_calendar_text += f"Location: {location}\n\n"

    return complete_calendar_text


def get_output():
    calendar_text = get_calendar_text()

    return {
        "plugin_name": "icloud_calendar",
        "output": calendar_text,
    }


if __name__ == "__main__":
    result = get_output()
    print(result["output"])
