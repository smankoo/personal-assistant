#!/usr/bin/env python3
"""
compile_prompt.py

This script compiles the full prompt text by:
  - Loading one of two prompt templates (for "ask" mode or "direct" mode)
  - Loading personality definitions from a YAML file (with unconstrained keys)
  - Processing each personality value to substitute placeholders (e.g. {NAME_OF_USER})
  - Formatting the complete personality configuration into a text block
  - Merging all substitutions (including a dump of the personality configuration)
  - Loading plugin-generated context (from a file)
  - Combining the template and substitutions into the final prompt

No LLM calls are made.
"""

import argparse
import getpass
import subprocess
import sys
from pathlib import Path
import yaml


def load_yaml(file_path: Path) -> dict:
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_full_name() -> str:
    """
    Attempt to obtain the full name of the user.
    On macOS, try using 'dscl'; otherwise, fall back to getpass.
    """
    try:
        result = subprocess.run(
            ["dscl", ".", "-read", f"/Users/{getpass.getuser()}", "RealName"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            lines = result.stdout.strip().splitlines()
            if lines:
                return lines[-1].strip()
    except Exception:
        pass
    return getpass.getuser()


def load_file(file_path: Path) -> str:
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    return file_path.read_text(encoding="utf-8")


def process_value(value, subs: dict) -> str:
    """
    If value is a string, substitute placeholders; if a list, process each element.
    """
    if isinstance(value, str):
        return value.format(**subs)
    elif isinstance(value, list):
        return ", ".join(process_value(item, subs) for item in value)
    else:
        return str(value)


def process_personality(personality: dict, base_subs: dict) -> dict:
    """
    Process each key in the personality dictionary by substituting placeholders
    using the base substitutions (e.g. {NAME_OF_USER}).
    Returns a new dictionary.
    """
    processed = {}
    for key, value in personality.items():
        processed[key] = process_value(value, base_subs)
    return processed


def format_personality_config(personality: dict) -> str:
    """
    Dump the entire personality dictionary in a nicely formatted YAML block.
    """
    return yaml.dump(personality, default_flow_style=False, sort_keys=False)


def compile_prompt(template: str, substitutions: dict) -> str:
    """
    Substitute placeholders in the template using the substitutions dictionary.
    """
    try:
        prompt = template.format(**substitutions)
    except KeyError as e:
        raise ValueError(f"Missing placeholder in substitutions: {e}")
    return prompt


def main():
    parser = argparse.ArgumentParser(
        description="Compile an LLM prompt using a personality configuration and context."
    )
    parser.add_argument(
        "--mode",
        choices=["ask", "direct"],
        default="ask",
        help="Prompt mode: 'ask' (first show the query then request a response) or 'direct' (immediately request a response).",
    )
    parser.add_argument(
        "--personality",
        "-p",
        type=str,
        required=True,
        help="Name of the personality to use (as defined in personalities.yml).",
    )
    parser.add_argument(
        "--personalities_file",
        type=str,
        default="personalities.yml",
        help="Path to the YAML file with personality definitions.",
    )
    parser.add_argument(
        "--context_file",
        type=str,
        default="personal_assistant/.plugins_output/0_all.output.txt",
        help="Path to the file containing generated context from plugins.",
    )
    parser.add_argument(
        "--template_file",
        type=str,
        default="",
        help="Optional: Override the default prompt template file path.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="",
        help="Optional output file to save the compiled prompt (if not provided, prints to stdout).",
    )
    args = parser.parse_args()

    # Use pathlib throughout.
    base_dir = Path(__file__).parent.resolve()
    templates_dir = base_dir / "prompt_templates"
    if not templates_dir.exists():
        print(f"Templates directory not found: {templates_dir}", file=sys.stderr)
        return

    personalities_file = Path(args.personalities_file)
    if not personalities_file.exists():
        print(f"Personalities file not found: {personalities_file}", file=sys.stderr)
        return

    context_file = Path(args.context_file)
    if not context_file.exists():
        print(f"Context file not found: {context_file}", file=sys.stderr)
        return

    if args.mode not in ["ask", "direct"]:
        print(f"Invalid mode: {args.mode}", file=sys.stderr)
        return

    # Select template based on mode (unless overridden by --template_file)
    if args.template_file:
        template_path = Path(args.template_file)
    elif args.mode == "ask":
        template_path = templates_dir / "ask.txt"
        if not template_path.exists():
            print(f"Template file not found: {template_path}", file=sys.stderr)
            return
    else:
        template_path = templates_dir / "direct.txt"
        if not template_path.exists():
            print(f"Template file not found: {template_path}", file=sys.stderr)
            return

    try:
        template_text = load_file(template_path)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return

    try:
        context_text = load_file(context_file)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return

    # Base substitutions (e.g. the user's name)
    base_subs = {"NAME_OF_USER": get_full_name()}

    # Load personalities
    try:
        personalities_data = load_yaml(personalities_file)
    except Exception as e:
        print(f"Error loading personalities: {e}", file=sys.stderr)
        return

    personalities = personalities_data.get("personalities", [])
    # -- Case-insensitive personality matching --
    chosen = next(
        (
            p
            for p in personalities
            if p.get("name", "").lower() == args.personality.lower()
        ),
        None,
    )
    if chosen is None:
        print(
            f"Personality '{args.personality}' not found in {personalities_file}",
            file=sys.stderr,
        )
        return

    # Process the personality so that placeholders (like {NAME_OF_USER}) are replaced.
    processed_personality = process_personality(chosen, base_subs)
    personality_config_str = format_personality_config(processed_personality)
    personality_name = processed_personality.get("name", "Your assistant")
    personality_role = processed_personality.get("role", "Your assistant")
    personality_task = processed_personality.get("task", "Help")

    # Build full substitutions.
    full_subs = base_subs.copy()
    full_subs.update(
        {
            "personality_config": personality_config_str,
            "PERSONALITY_NAME": personality_name,
            "PERSONALITY_ROLE": personality_role,
            "PERSONALITY_TASK": personality_task,
        }
    )
    # Inject the plugin-generated context as {context}
    full_subs["context"] = context_text

    try:
        compiled_prompt = compile_prompt(template_text, full_subs)
    except ValueError as e:
        print(e, file=sys.stderr)
        return

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(compiled_prompt, encoding="utf-8")
        print(f"Compiled prompt written to: {out_path}", file=sys.stderr)
    else:
        # When used in the end-to-end process, the compiled prompt is sent to stdout.
        print(compiled_prompt)


if __name__ == "__main__":
    main()
