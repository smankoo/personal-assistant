#!/usr/bin/env python3
"""
Diary Markdown to XML Converter (Compact Structure, Preserving Entry Text)

Rules:
  - A line starting with "##" marks a new day. The rest of the line is parsed as a date,
    but its original text is preserved.
  - Each diary entry starts with a bullet point ("-") or an indented line (4 spaces),
    immediately followed by a time stamp (e.g. "10:30 AM" or "5:13PM").
  - The entry’s text includes everything from that line until the next entry or the end of that day.
  - The XML structure is pretty‑printed (with indentation) without altering the text content.

Usage:
    python diary_to_xml.py input.md
"""

import re
import sys
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

try:
    from dateutil import parser as date_parser
except ImportError:
    date_parser = None


class DiaryConverter:
    def __init__(self, markdown_text):
        self.markdown_text = markdown_text

    def parse_day_header(self, header_line, last_date=None):
        # Preserve the original header text (after the "##")
        original_header = header_line.lstrip("#").strip()
        if not original_header:
            return None, None

        default_year = last_date.year if last_date else 2025
        default_date = datetime(default_year, 1, 1)
        try:
            if date_parser:
                parsed = date_parser.parse(original_header, default=default_date)
            else:
                try:
                    parsed = datetime.strptime(original_header, "%a %b %d, %Y")
                except:
                    parsed = datetime.strptime(original_header, "%b %d")
                    parsed = parsed.replace(year=default_year)
        except Exception:
            return None, original_header

        if last_date and parsed.date() <= last_date.date():
            try:
                parsed = parsed.replace(year=parsed.year + 1)
            except ValueError:
                parsed = parsed + timedelta(days=365)
        return parsed, original_header

    def parse(self):
        lines = self.markdown_text.splitlines()
        days = []
        current_day_info = None  # Tuple (parsed_date, original_header)
        entries = []
        current_entry_time = None
        current_entry_lines = []

        time_pattern = re.compile(
            r"^(?:-\s*| {4})(?:\*\*)?(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))(?:\*\*)?"
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
                if current_day_info is not None:
                    days.append((current_day_info, entries))
                    entries = []
                parsed_day, original_header = self.parse_day_header(stripped, last_date)
                if parsed_day:
                    current_day_info = (parsed_day, original_header)
                    last_date = parsed_day
                continue

            m = time_pattern.match(line)
            if m:
                if current_entry_time is not None:
                    entry_text = "\n".join(current_entry_lines)
                    entries.append((current_entry_time, entry_text))
                current_entry_time = m.group(1).upper()
                remainder = stripped[m.end() :].strip()
                current_entry_lines = [remainder] if remainder else []
            else:
                current_entry_lines.append(line)  # preserve original line breaks

        if current_entry_time is not None:
            entry_text = "\n".join(current_entry_lines)
            entries.append((current_entry_time, entry_text))
        if current_day_info is not None:
            days.append((current_day_info, entries))
        return days

    def build_xml(self, days):
        diary = ET.Element("diary")
        for (day_date, original_header), entries in days:
            day_el = ET.SubElement(
                diary,
                "day",
                {
                    "header": original_header,
                    "date": day_date.strftime("%Y-%m-%d"),
                    "weekday": day_date.strftime("%A"),
                },
            )
            for time_str, entry_text in entries:
                # Do not alter entry_text; preserve its internal newlines and spaces.
                entry_el = ET.SubElement(day_el, "entry", {"time": time_str})
                entry_el.text = entry_text
        return diary

    def custom_prettify(self, elem, level=0):
        """Recursively pretty-print XML without modifying text nodes."""
        indent = "  " * level
        lines = []
        # Open tag with attributes.
        attrs = " ".join(f'{k}="{v}"' for k, v in elem.attrib.items())
        if attrs:
            open_tag = f"{indent}<{elem.tag} {attrs}>"
        else:
            open_tag = f"{indent}<{elem.tag}>"
        lines.append(open_tag)

        # If element has text, preserve it exactly.
        if elem.text is not None:
            # Do not change internal newlines.
            text_lines = elem.text.splitlines()
            for t in text_lines:
                lines.append(f"{indent}  {t}")
        # Process children.
        for child in elem:
            lines.append(self.custom_prettify(child, level + 1))
        lines.append(f"{indent}</{elem.tag}>")
        return "\n".join(lines)

    def convert(self):
        days = self.parse()
        xml_tree = self.build_xml(days)
        return self.custom_prettify(xml_tree)


def xmlize_file(markdown_file):
    with open(markdown_file, "r", encoding="utf-8") as f:
        markdown_text = f.read()
    converter = DiaryConverter(markdown_text)
    return converter.convert()


if __name__ == "__main__":
    print(xmlize_file(sys.argv[1]))
