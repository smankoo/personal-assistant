import os
import yaml
from personal_assistant.tools.caching import cached_output
from personal_assistant.tools.diary_to_xml import DiaryConverter

import os
from dotenv import load_dotenv

load_dotenv()

OBSIDIAN_VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH", "")

if not OBSIDIAN_VAULT_PATH:
    print("[Error] OBSIDIAN_VAULT_PATH environment variable not set.")
    exit(1)


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


def fetch_ai_context_enabled_notes():
    """Scan Obsidian vault for notes with 'ai-context-enabled: true' in the front matter."""
    all_notes_content = ""

    for root, dirs, files in os.walk(OBSIDIAN_VAULT_PATH):
        for file in files:
            if file.endswith(".md"):
                file_path = os.path.join(root, file)
                with open(file_path, "r") as f:
                    content = f.read()

                    front_matter = parse_front_matter(content)

                    if (
                        front_matter
                        and front_matter.get("ai-context-enabled")
                        and front_matter.get("ai-context-enabled").lower() == "true"
                    ):
                        all_notes_content += (
                            f"# File: .{file_path.removeprefix(OBSIDIAN_VAULT_PATH)}\n"
                        )

                        if file == "Day Log.md":
                            all_notes_content += DiaryConverter(content).convert()
                        else:
                            all_notes_content += content

                        all_notes_content += "\n" + "=" * 30 + "\n"

    return all_notes_content or "No AI-context-enabled notes found."


def get_output():
    """Return plugin output in a structured format."""
    notes_content = fetch_ai_context_enabled_notes()
    return {
        "plugin_name": "obsidian_ai_context",
        "output": notes_content,
    }


# Allow standalone testing
if __name__ == "__main__":
    result = get_output()
    print(result["output"])
