#!/usr/bin/env python3
"""
personality_helper.py

This helper script performs two functions:
  1. "list" – lists available personality names along with role and task from the specified YAML file in a formatted table.
  2. "check" – checks whether a given personality exists (case‑insensitive). If not,
     it uses difflib to suggest similar names.
     
Usage:
    python3 personality_helper.py list [--file <personalities_file>]
    python3 personality_helper.py check --personality <name> [--file <personalities_file>]
"""
import sys
import yaml
import difflib
import argparse


def load_personalities(filename):
    try:
        with open(filename, "r") as f:
            data = yaml.safe_load(f)
        return data.get("personalities", [])
    except Exception as e:
        print(f"[ERROR] Could not load personalities from {filename}: {e}")
        sys.exit(1)


def list_personalities(filename):
    personalities = load_personalities(filename)
    # Collect rows: each row is [Name, Role, Task]
    rows = []
    for p in personalities:
        name = p.get("name", "").strip()
        role = p.get("role", "").strip() if p.get("role") else ""
        task = p.get("task", "").strip() if p.get("task") else ""
        rows.append([name, role, task])
    # Define headers
    header = ["Name", "Role", "Task"]
    # Determine column widths based on header and content
    col_widths = [len(h) for h in header]
    for row in rows:
        for i, col in enumerate(row):
            col_widths[i] = max(col_widths[i], len(col))
    # Print header and separator
    header_line = " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(header))
    separator = "-+-".join("-" * col_widths[i] for i in range(len(header)))
    print(header_line)
    print(separator)
    # Print each row
    for row in rows:
        print(" | ".join(row[i].ljust(col_widths[i]) for i in range(len(row))))


def check_personality(filename, personality):
    personalities = load_personalities(filename)
    names = [p.get("name", "").strip() for p in personalities if p.get("name")]
    # Look for an exact (case-insensitive) match.
    for name in names:
        if name.lower() == personality.lower():
            sys.exit(0)
    # Not found: suggest similar names.
    suggestions = difflib.get_close_matches(personality, names, n=3, cutoff=0.6)
    if suggestions:
        print(f"The personality '{personality}' was not found. Did you mean:")
        for s in suggestions:
            print(f" - {s}")
    else:
        print(
            f"The personality '{personality}' was not found, and no similar personalities were detected."
        )
    sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Helper for managing personalities.")
    parser.add_argument(
        "command", choices=["list", "check"], help="Command: list or check"
    )
    parser.add_argument("--personality", "-p", help="Personality name to check")
    parser.add_argument(
        "--file",
        "-f",
        default="personalities.yml",
        help="Path to personalities YAML file",
    )
    args = parser.parse_args()

    if args.command == "list":
        list_personalities(args.file)
    elif args.command == "check":
        if not args.personality:
            print(
                "You must specify a personality using --personality or -p when using the 'check' command."
            )
            sys.exit(1)
        check_personality(args.file, args.personality)
