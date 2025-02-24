#!/usr/bin/env python3
"""
Diary Markdown to XML Converter (Improved)

Rules:
  - A line starting with "##" marks a new day. The rest of the line is parsed as a date.
  - Each diary entry starts with a bullet point ("-") or an indented line (4 spaces),
    immediately followed by a time stamp (e.g. "10:30 AM" or "5:13PM").
  - The entry’s text includes everything from that line until the next entry or the end of that day.

Usage:
    python diary_to_xml.py input.md
"""

import re
import sys
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import xml.dom.minidom

try:
    from dateutil import parser as date_parser
except ImportError:
    date_parser = None


class DiaryConverter:
    def __init__(self, markdown_text):
        self.markdown_text = markdown_text

    def parse_day_header(self, header_line, last_date=None):
        header_str = header_line.lstrip("#").strip()
        if not header_str:
            return None

        default_year = last_date.year if last_date else 2025
        default_date = datetime(default_year, 1, 1)
        try:
            if date_parser:
                parsed = date_parser.parse(header_str, default=default_date)
            else:
                try:
                    parsed = datetime.strptime(header_str, "%a %b %d, %Y")
                except:
                    parsed = datetime.strptime(header_str, "%b %d")
                    parsed = parsed.replace(year=default_year)
        except Exception:
            return None

        if last_date and parsed.date() <= last_date.date():
            try:
                parsed = parsed.replace(year=parsed.year + 1)
            except ValueError:
                parsed = parsed + timedelta(days=365)
        return parsed

    def parse(self):
        lines = self.markdown_text.splitlines()
        days = []
        current_day_date = None
        entries = []
        current_entry_time = None
        current_entry_lines = []

        time_pattern = re.compile(
            r"^(?:-\s*| {4})(?:\*\*)?(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))(?:\*\*)?\b"
        )
        last_date = None

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("## "):
                if current_entry_time is not None:
                    entry_text = "\n".join(current_entry_lines).strip()
                    entries.append((current_entry_time, entry_text))
                    current_entry_time = None
                    current_entry_lines = []
                if current_day_date is not None:
                    days.append((current_day_date, entries))
                    entries = []
                parsed_day = self.parse_day_header(stripped, last_date)
                if parsed_day:
                    current_day_date = parsed_day
                    last_date = parsed_day
                continue

            m = time_pattern.match(line)
            if m:
                if current_entry_time is not None:
                    entry_text = "\n".join(current_entry_lines).strip()
                    entries.append((current_entry_time, entry_text))
                current_entry_time = m.group(1).upper()
                remainder = stripped[m.end() :].strip()
                current_entry_lines = [remainder] if remainder else []
            else:
                current_entry_lines.append(stripped)

        if current_entry_time is not None:
            entry_text = "\n".join(current_entry_lines).strip()
            entries.append((current_entry_time, entry_text))
        if current_day_date is not None:
            days.append((current_day_date, entries))
        return days

    def build_xml(self, days):
        diary = ET.Element("diary")
        for day_date, entries in days:
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


def xmlize_file(markdown_file):
    with open(markdown_file, "r", encoding="utf-8") as f:
        markdown_text = f.read()
    converter = DiaryConverter(markdown_text)
    xml_output = converter.convert()
    return xml_output


if __name__ == "__main__":
    xmlize_file(sys.argv[1])
