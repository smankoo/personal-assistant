#!/usr/bin/env python3
"""
Diary Markdown to XML Converter (Improved)

Rules:
  - A line starting with "##" marks a new day. The rest of the line is parsed as a date.
    The parser uses common formats (e.g. "Sun Feb 2, 2025", "Tue Feb 11", "Feb 14") and,
    if the year is missing, defaults to the previous day’s year (or 2025 if none).
    Also, if a new date appears not to be after the previous one, it “rolls forward.”
  - Each diary entry starts with a bullet point ("-") immediately followed by a time stamp
    (e.g. "10:30 AM" or "5:13PM"). The entry’s text includes everything from that line until
    the next bullet or the end of that day.

Usage:
    python diary_to_xml.py input.md
"""

import re
import sys
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import xml.dom.minidom

# Use dateutil if available for flexible date parsing.
try:
    from dateutil import parser as date_parser
except ImportError:
    date_parser = None


class DiaryConverter:
    def __init__(self, markdown_text):
        self.markdown_text = markdown_text

    def parse_day_header(self, header_line, last_date=None):
        """
        Given a header line that starts with "##", attempt to parse it as a date.
        Uses common sense: if the year is missing, default to last_date's year (or 2025).
        If the resulting date is not later than last_date, assume it is the next occurrence.
        """
        header_str = header_line.lstrip("#").strip()
        if not header_str:
            return None

        # Determine default year from last_date or use 2025 as fallback.
        default_year = last_date.year if last_date else 2025
        default_date = datetime(default_year, 1, 1)
        try:
            if date_parser:
                # dateutil uses the default date for missing fields.
                parsed = date_parser.parse(header_str, default=default_date)
            else:
                # Fallback: try a common format like "Sun Feb 2, 2025"
                try:
                    parsed = datetime.strptime(header_str, "%a %b %d, %Y")
                except:
                    parsed = datetime.strptime(header_str, "%b %d")
                    parsed = parsed.replace(year=default_year)
        except Exception:
            # If parsing fails, return None.
            return None

        # If we have a last_date and the new date is not after it, roll forward.
        if last_date and parsed.date() <= last_date.date():
            try:
                parsed = parsed.replace(year=parsed.year + 1)
            except ValueError:
                parsed = parsed + timedelta(days=365)
        return parsed

    def parse(self):
        """
        Parses the markdown into a list of days.
        Each day is a tuple: (date_object, list_of_entries).
        Each entry is a tuple: (time_string, entry_text).
        """
        lines = self.markdown_text.splitlines()
        days = []
        current_day_date = None
        entries = []
        current_entry_time = None
        current_entry_lines = []

        # A regex to detect a bullet point that begins with a time stamp.
        time_pattern = re.compile(r"^- *(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))\b")
        last_date = None

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("## "):
                # New day marker found.
                # Flush any pending entry.
                if current_entry_time is not None:
                    entry_text = "\n".join(current_entry_lines).strip()
                    entries.append((current_entry_time, entry_text))
                    current_entry_time = None
                    current_entry_lines = []
                # If we already have a day, save it.
                if current_day_date is not None:
                    days.append((current_day_date, entries))
                    entries = []
                # Parse the new day header.
                parsed_day = self.parse_day_header(stripped, last_date)
                if parsed_day:
                    current_day_date = parsed_day
                    last_date = parsed_day
                else:
                    # If parsing fails, skip this header.
                    continue
                continue

            # Check if the line starts with a bullet point and a time stamp.
            m = time_pattern.match(stripped)
            if m:
                # Flush previous entry if any.
                if current_entry_time is not None:
                    entry_text = "\n".join(current_entry_lines).strip()
                    entries.append((current_entry_time, entry_text))
                current_entry_time = m.group(1).upper()
                # Save any content on the same line after the time stamp.
                remainder = stripped[m.end() :].strip()
                current_entry_lines = [remainder] if remainder else []
            else:
                # Otherwise, it's part of the current entry.
                current_entry_lines.append(stripped)

        # Flush any remaining entry and day.
        if current_entry_time is not None:
            entry_text = "\n".join(current_entry_lines).strip()
            entries.append((current_entry_time, entry_text))
        if current_day_date is not None:
            days.append((current_day_date, entries))
        return days

    def build_xml(self, days):
        diary = ET.Element("diary")
        for day_date, entries in days:
            # Format the date as an ISO string.
            day_el = ET.SubElement(
                diary,
                "day",
                {
                    "date": day_date.strftime("%Y-%m-%d"),
                    "weekday": day_date.strftime("%A"),
                },
            )

            for time_str, entry_text in entries:
                entry_el = ET.SubElement(day_el, "entry", {"time": time_str})
                text_el = ET.SubElement(entry_el, "text")
                text_el.text = entry_text
        return diary

    def prettify(self, elem):
        rough_string = ET.tostring(elem, "utf-8")
        reparsed = xml.dom.minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")

    def convert(self):
        days = self.parse()
        xml_tree = self.build_xml(days)
        return self.prettify(xml_tree)


def main():
    # if len(sys.argv) < 2:
    #     print("Usage: python diary_to_xml.py input.md")
    #     sys.exit(1)
    # input_file = sys.argv[1]
    input_file = "/Users/sumeet/Library/Mobile Documents/iCloud~md~obsidian/Documents/Sumeet Personal Notes/2 Areas/Day Log Orig.md"
    with open(input_file, "r", encoding="utf-8") as f:
        markdown_text = f.read()
    converter = DiaryConverter(markdown_text)
    xml_output = converter.convert()
    print(xml_output)


if __name__ == "__main__":
    main()
