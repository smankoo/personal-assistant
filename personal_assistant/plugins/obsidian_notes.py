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


def parse_front_matter(content):
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


def simple_summary_to_xml(summary_text: str, metadata: dict) -> str:
    """
    Wrap the summary file content in a <summary> element.
    Metadata (such as filename and date info) is added as attributes.
    A CDATA section is used so that the content is preserved exactly.
    """
    # Build attributes string from metadata
    attributes = " ".join(f'{k}="{v}"' for k, v in metadata.items())
    # Wrap the summary text in CDATA
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
        parsed_day, original_header = day_info  # Unpack the tuple
        if (
            parsed_day.year == today.year
            and parsed_day.isocalendar()[1] == current_week
        ):
            # Use the original header to preserve the format.
            day_md = f"## {original_header}\n"
            for time_str, entry_text in entries:
                day_md += f"- **{time_str}** {entry_text}\n"
            current_week_entries.append(day_md)

    if current_week_entries:
        current_week_markdown = "\n".join(current_week_entries)
        # Convert the filtered markdown back to XML.
        return DiaryConverter(current_week_markdown).convert()
    return ""


def process_summaries(summary_dir: str, summary_type: str) -> str:
    """
    Read all markdown files in the given summary directory,
    and wrap each file's raw content in a <summary> element with metadata.

    For weekly summaries, filenames are expected to be like "2025-W02.md".
    For monthly summaries, filenames are expected to be like "2025-02.md".
    """
    xml_parts = []
    if os.path.isdir(summary_dir):
        for file in sorted(os.listdir(summary_dir)):
            if file.endswith(".md"):
                summary_path = os.path.join(summary_dir, file)
                with open(summary_path, "r", encoding="utf-8") as f:
                    summary_text = f.read()
                # Build metadata from filename
                metadata = {"filename": file, "summary_type": summary_type}
                if summary_type == "weekly":
                    # Expect format like "YYYY-W02.md"
                    try:
                        parts = file.split("-")
                        year = parts[0]
                        week = parts[1].replace("W", "").replace(".md", "")
                        metadata["year"] = year
                        metadata["week"] = week
                    except Exception:
                        pass
                elif summary_type == "monthly":
                    # Expect format like "YYYY-02.md"
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


def get_output():
    # Build a combined XML document with three sections.
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
        # Wrap the weekly summaries as multiple <summary> elements.
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
