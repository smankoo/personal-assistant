import os
import yaml
import xml.etree.ElementTree as ET
import xml.dom.minidom
from datetime import date
from personal_assistant.tools.caching import cached_output
from personal_assistant.tools.diary_to_xml import DiaryConverter
from dotenv import load_dotenv

load_dotenv()

OBSIDIAN_VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH", "")


def parse_front_matter(content: str):
    """Extract and parse YAML front matter from Markdown content."""
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) > 2:
            try:
                front_matter = yaml.safe_load(parts[1])
                return front_matter
            except yaml.YAMLError:
                return None
    return None


def is_ai_context_enabled(front_matter: dict) -> bool:
    """
    Determine if a note has 'ai-context-enabled' set to a truthy value.
    Accepts booleans or strings (e.g. "true", "True", etc.).
    """
    value = front_matter.get("ai-context-enabled")
    if isinstance(value, bool):
        return value
    elif isinstance(value, str):
        return value.lower() == "true"
    elif isinstance(value, (int, float)):
        return value == 1
    return False


def simple_summary_to_xml(summary_text: str, metadata: dict) -> str:
    """
    Wrap the summary file content in a <summary> element.
    Metadata (such as filename and date info) is added as attributes.
    A CDATA section is used so that the content is preserved exactly.
    """
    attributes = " ".join(f'{k}="{v}"' for k, v in metadata.items())
    return f"<summary {attributes}><![CDATA[{summary_text}]]></summary>"


def process_current_week(day_log_path: str) -> str:
    """
    Read the raw Day Log.md, filter for current week entries,
    and convert them to XML using the existing DiaryConverter.
    """
    with open(day_log_path, "r", encoding="utf-8") as f:
        day_log_content = f.read()
    converter = DiaryConverter(day_log_content)
    days = (
        converter.parse()
    )  # Each element is ((parsed_date, original_header), entries)
    current_week_entries = []
    today = date.today()
    current_week = today.isocalendar()[1]

    for day_info, entries in days:
        parsed_day, original_header = day_info
        if (
            parsed_day.year == today.year
            and parsed_day.isocalendar()[1] == current_week
        ):
            day_md = f"## {original_header}\n"
            for time_str, entry_text in entries:
                day_md += f"- **{time_str}** {entry_text}\n"
            current_week_entries.append(day_md)

    if current_week_entries:
        current_week_markdown = "\n".join(current_week_entries)
        return DiaryConverter(current_week_markdown).convert()
    return ""


def process_summaries(summary_dir: str, summary_type: str) -> str:
    """
    Read all markdown files in the given summary directory,
    and wrap each file's raw content in a <summary> element with metadata.
    """
    xml_parts = []
    if os.path.isdir(summary_dir):
        for file in sorted(os.listdir(summary_dir)):
            if file.endswith(".md"):
                summary_path = os.path.join(summary_dir, file)
                with open(summary_path, "r", encoding="utf-8") as f:
                    summary_text = f.read()
                metadata = {"filename": file, "summary_type": summary_type}
                if summary_type == "weekly":
                    try:
                        parts = file.split("-")
                        year = parts[0]
                        week = parts[1].replace("W", "").replace(".md", "")
                        metadata["year"] = year
                        metadata["week"] = week
                    except Exception:
                        pass
                elif summary_type == "monthly":
                    try:
                        parts = file.split("-")
                        year = parts[0]
                        month = parts[1].replace(".md", "")
                        metadata["year"] = year
                        metadata["month"] = month
                    except Exception:
                        pass
                xml_text = simple_summary_to_xml(summary_text, metadata)
                xml_parts.append(xml_text)
    return "\n".join(xml_parts)


def process_plain_notes(vault_path: str) -> str:
    """
    Recursively scan the vault for Markdown files (excluding Day Log.md and
    files within the 'Day Log Summaries' directory). For each file that has
    front matter with 'ai-context-enabled' set to a truthy value, include the note
    as plain text with a header indicating the file path.
    Each note is wrapped in a <note> element with an attribute for the file path.
    """
    plain_notes = []
    for root, dirs, files in os.walk(vault_path):
        # Exclude the summaries directory from being scanned.
        if "Day Log Summaries" in dirs:
            dirs.remove("Day Log Summaries")
        for file in files:
            if file.endswith(".md"):
                # Skip the Day Log file
                if file == "Day Log.md":
                    continue
                file_path = os.path.join(root, file)
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                front_matter = parse_front_matter(content)
                if front_matter and is_ai_context_enabled(front_matter):
                    # Prepend the file path as a header to the note content.
                    note_content = f"File: {file_path}\n\n{content}"
                    # Wrap this note in a <note> element with a file attribute.
                    note_xml = (
                        f'<note file="{file_path}"><![CDATA[{note_content}]]></note>'
                    )
                    plain_notes.append(note_xml)
    return "\n".join(plain_notes)


def get_output():
    # Build a combined XML document with sections for current week, summaries, and plain notes.
    root = ET.Element("journal")

    # Determine the path to the Day Log.md file.
    day_log_path = os.getenv("DAY_LOG_PATH")
    if not day_log_path:
        for r, d, f in os.walk(OBSIDIAN_VAULT_PATH):
            if "Day Log.md" in f:
                day_log_path = os.path.join(r, "Day Log.md")
                break

    # Process current week raw entries.
    if day_log_path and os.path.exists(day_log_path):
        current_week_xml_str = process_current_week(day_log_path)
    else:
        current_week_xml_str = ""

    # Derive summary directories from the Day Log.md location.
    if day_log_path:
        summary_base_dir = os.path.join(
            os.path.dirname(day_log_path), "Day Log Summaries"
        )
    else:
        summary_base_dir = os.path.join(OBSIDIAN_VAULT_PATH, "Day Log Summaries")
    weekly_summary_dir = os.path.join(summary_base_dir, "Weekly Summaries")
    monthly_summary_dir = os.path.join(summary_base_dir, "Monthly Summaries")

    weekly_xml_str = process_summaries(weekly_summary_dir, "weekly")
    monthly_xml_str = process_summaries(monthly_summary_dir, "monthly")

    # Insert current week XML.
    current_elem = ET.SubElement(root, "current_week")
    if current_week_xml_str:
        try:
            cw_elem = ET.fromstring(current_week_xml_str)
            current_elem.append(cw_elem)
        except Exception:
            current_elem.text = current_week_xml_str
    else:
        current_elem.text = "No current week entries found."

    # Insert weekly summaries XML.
    weekly_elem = ET.SubElement(root, "weekly_summaries")
    if weekly_xml_str:
        try:
            dummy = f"<container>{weekly_xml_str}</container>"
            container_elem = ET.fromstring(dummy)
            for child in container_elem:
                weekly_elem.append(child)
        except Exception:
            weekly_elem.text = weekly_xml_str
    else:
        weekly_elem.text = "No weekly summaries found."

    # Insert monthly summaries XML.
    monthly_elem = ET.SubElement(root, "monthly_summaries")
    if monthly_xml_str:
        try:
            dummy = f"<container>{monthly_xml_str}</container>"
            container_elem = ET.fromstring(dummy)
            for child in container_elem:
                monthly_elem.append(child)
        except Exception:
            monthly_elem.text = monthly_xml_str
    else:
        monthly_elem.text = "No monthly summaries found."

    # Process and insert plain notes (notes with ai-context-enabled enabled).
    plain_notes_xml_str = process_plain_notes(OBSIDIAN_VAULT_PATH)
    plain_notes_elem = ET.SubElement(root, "plain_notes")
    if plain_notes_xml_str:
        try:
            dummy = f"<container>{plain_notes_xml_str}</container>"
            container_elem = ET.fromstring(dummy)
            for child in container_elem:
                plain_notes_elem.append(child)
        except Exception:
            plain_notes_elem.text = plain_notes_xml_str
    else:
        plain_notes_elem.text = "No plain notes found."

    # Pretty-print the combined XML.
    rough_string = ET.tostring(root, "utf-8")
    reparsed = xml.dom.minidom.parseString(rough_string)
    final_xml = reparsed.toprettyxml(indent="  ")

    return {
        "plugin_name": "obsidian_ai_context",
        "output": final_xml,
    }


if __name__ == "__main__":
    result = get_output()
    print(result["output"])
