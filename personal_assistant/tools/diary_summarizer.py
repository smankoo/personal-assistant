# File: personal_assistant/tools/diary_summarizer.py

import os
import sys
import datetime
from personal_assistant.tools.diary_to_xml import DiaryConverter
from personal_assistant.llm_clients.openai_client import OpenAIClient

# Define the base folder for storing summaries (using OBSIDIAN_VAULT_PATH)
# If not set, defaults to the current directory.
DAY_LOG_PATH = "/Users/sumeet/Library/Mobile Documents/iCloud~md~obsidian/Documents/Sumeet Personal Notes/2 Areas/Day Log.md"
SUMMARY_BASE_DIR = os.path.join(os.path.dirname(DAY_LOG_PATH), "Day Log Summaries")
WEEKLY_SUMMARY_DIR = os.path.join(SUMMARY_BASE_DIR, "Weekly Summaries")
MONTHLY_SUMMARY_DIR = os.path.join(SUMMARY_BASE_DIR, "Monthly Summaries")
DEBUG_MODE = os.getenv("DEBUG_GENAI", "false").lower() in ["true", "1"]
FORCE_REFRESH = os.getenv("FORCE_REFRESH", "true").lower() in ["true", "1"] or any(
    arg.lower() in ["refresh", "force"] for arg in sys.argv
)
# Ensure that summary directories exist
os.makedirs(WEEKLY_SUMMARY_DIR, exist_ok=True)
os.makedirs(MONTHLY_SUMMARY_DIR, exist_ok=True)


def genai_summarize(text: str) -> str:
    client = OpenAIClient()  # Ensure your OPENAI_API_KEY is set in .env

    template = (
        "You are a professional assistant tasked with summarizing personal daily logs. "
        "IMPORTANT: Base your summary ONLY on the text provided. Do not fabricate or infer details not present. "
        "If the provided text does not include any detailed log entries (for example, if it only contains dates or headers), "
        "please respond with 'No log entries available for this period.'\n\n"
        "Follow these guidelines:\n"
        "1. Start with a brief title summarizing the period. For example - ## February 11-16, 2025: A Week of Challenges and Joys\n"
        "2. Provide 3-5 bullet points outlining the key events and highlights from the text.\n"
        "3. Conclude with a short overall summary paragraph.\n\n"
        "Here is the text to summarize:\n\n{text}\n\n"
        "Summary:"
    )
    prompt = template.format(text=text)

    summary = ""
    try:
        for chunk in client.stream_response(prompt):
            summary += chunk
    except Exception as e:
        summary = f"[Error in summarization: {e}]"

    if DEBUG_MODE:
        summary += "\n\n---DEBUG PROMPT SENT TO GENAI---\n" + prompt

    return summary.strip()


def load_summary(summary_path: str) -> str:
    with open(summary_path, "r", encoding="utf-8") as f:
        return f.read()


def write_summary(summary_path: str, header: str, summary: str):
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(f"{header}\n\n{summary}")
    print(f"[DEBUG] Wrote summary to: {summary_path}")


def summarize_day_log(markdown_text: str) -> str:
    """
    Parse the Day Log entries and group them as follows:
      - Keep full entries for days in the current week.
      - Group entries older than this week but within 30 days by ISO week.
      - Group entries older than 30 days by month.
    For each weekly or monthly group, check if a summary file already exists
    in the Obsidian vault. If it does, load it; otherwise, summarize using GenAI,
    save the summary, and then include it.
    Returns a markdown-formatted summary.
    """
    converter = DiaryConverter(markdown_text)
    days = converter.parse()  # List of tuples: (day_date, entries)

    today = datetime.date.today()
    current_week = today.isocalendar()[1]

    current_week_entries = []
    weekly_groups = {}  # key: (year, week)
    monthly_groups = {}  # key: (year, month)

    for day_date, entries in days:
        if hasattr(day_date, "date"):
            day_as_date = day_date.date()
        else:
            day_as_date = day_date

        day_md = f"## {day_as_date.strftime('%Y-%m-%d (%A)')}\n"
        for time_str, entry_text in entries:
            day_md += f"- **{time_str}** {entry_text}\n"

        if (
            day_as_date.year == today.year
            and day_as_date.isocalendar()[1] == current_week
        ):
            current_week_entries.append(day_md)
        else:
            delta_days = (today - day_as_date).days
            if delta_days <= 30:
                key = (day_as_date.year, day_as_date.isocalendar()[1])
                weekly_groups.setdefault(key, []).append(day_md)
            else:
                key = (day_as_date.year, day_as_date.month)
                monthly_groups.setdefault(key, []).append(day_md)

    summarized_weekly = []
    for (year, week), day_md_list in weekly_groups.items():
        summary_filename = os.path.join(WEEKLY_SUMMARY_DIR, f"{year}-W{week:02d}.md")
        if os.path.exists(summary_filename) and not FORCE_REFRESH:
            summary = load_summary(summary_filename)
            print(f"[DEBUG] Loaded existing weekly summary: {summary_filename}")
        else:
            combined_text = "\n".join(day_md_list)
            summary = genai_summarize(combined_text)
            header = f"# Weekly Summary for {year}-W{week:02d}"
            write_summary(summary_filename, header, summary)
        summarized_weekly.append(load_summary(summary_filename))

    summarized_monthly = []
    for (year, month), day_md_list in monthly_groups.items():
        summary_filename = os.path.join(MONTHLY_SUMMARY_DIR, f"{year}-{month:02d}.md")
        if os.path.exists(summary_filename) and not FORCE_REFRESH:
            summary = load_summary(summary_filename)
            print(f"[DEBUG] Loaded existing monthly summary: {summary_filename}")
        else:
            combined_text = "\n".join(day_md_list)
            summary = genai_summarize(combined_text)
            header = f"# Monthly Summary for {year}-{month:02d}"
            write_summary(summary_filename, header, summary)
        summarized_monthly.append(load_summary(summary_filename))

    output_lines = ["# Day Log Summaries\n"]
    if current_week_entries:
        output_lines.append("## Current Week Entries\n")
        output_lines.append("\n".join(current_week_entries))
    if summarized_weekly:
        output_lines.append("\n## Weekly Summaries (Past Month)\n")
        output_lines.append("\n\n".join(summarized_weekly))
    if summarized_monthly:
        output_lines.append("\n## Monthly Summaries (Older than 1 Month)\n")
        output_lines.append("\n\n".join(summarized_monthly))

    return "\n".join(output_lines)


# ------------------------
# Test Block
# ------------------------
if __name__ == "__main__":
    # Default mode is real; use 'raw' argument for test mode.
    mode = "real"
    if len(sys.argv) > 1 and sys.argv[1].lower() == "raw":
        mode = "raw"

    if mode == "raw":
        # Raw mode: use a sample markdown and a temporary test vault.
        os.environ["OBSIDIAN_VAULT_PATH"] = "./test_vault"
        test_vault_path = os.environ["OBSIDIAN_VAULT_PATH"]
        os.makedirs(test_vault_path, exist_ok=True)
        print(f"[DEBUG] Using test vault at: {os.path.abspath(test_vault_path)}")

        test_markdown = """
## Sun Feb 2, 2025 

- 10:30 AM
    - woke up at 9 am. had breakfast, played with Tegh for 5 mins, now watching TV.
- 11:30 AM
    - Finished showering.
- 12:33 PM
    - Worked on personal assistant project.
"""
        summary_output = summarize_day_log(test_markdown)
        print("==== Generated Summary (Raw/Test Mode) ====")
        print(summary_output)
    else:
        # Real mode: process the actual Day Log.md file.
        vault_path = os.getenv("OBSIDIAN_VAULT_PATH")
        if not vault_path:
            print("Error: OBSIDIAN_VAULT_PATH is not set in the environment.")
            sys.exit(1)
        # Update this path as needed for your actual Day Log.md location.
        day_log_path = "/Users/sumeet/Library/Mobile Documents/iCloud~md~obsidian/Documents/Sumeet Personal Notes/2 Areas/Day Log.md"
        if not os.path.exists(day_log_path):
            print(f"Error: Day Log.md not found at {day_log_path}")
            sys.exit(1)
        with open(day_log_path, "r", encoding="utf-8") as f:
            markdown_text = f.read()
        summary_output = summarize_day_log(markdown_text)
        print("==== Generated Summary for Actual Day Log ====")
        print(summary_output)
