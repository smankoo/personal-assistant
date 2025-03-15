#!/usr/bin/env python3
"""
Meeting Mode Module with Full Personality Configuration, Participant Awareness, and Real-Time Progress Printing

This script implements the meeting mode which:
- Loads the meeting configuration (objective and a list of personality identifiers) from meeting.yml.
- Retrieves each personality’s full configuration from personalities.yml.
- Retrieves the plugin-generated context.
- Iterates through a fixed number of rounds in which each personality is informed of:
    • Their role and configuration,
    • The meeting objective,
    • The user's name,
    • And the names of the other participants.
- Each personality’s response is printed as soon as it is generated.
- After all rounds, an additional GenAI call extracts a final meeting plan.
- The complete transcript (including the final plan) is printed and then saved for later debugging.
"""

import os
import yaml
import getpass
from datetime import datetime
from personal_assistant.llm_clients.openai_client import OpenAIClient

# Define configuration and log paths.
MEETING_CONFIG_FILE = "meeting.yml"
PERSONALITIES_CONFIG_FILE = os.path.join("personal_assistant", "personalities.yml")
CONTEXT_FILE = os.path.join("personal_assistant", ".plugins_output", "0_all.output.txt")
MEETING_LOG_DIR = os.path.join("personal_assistant", ".meeting_logs")
os.makedirs(MEETING_LOG_DIR, exist_ok=True)


def load_yaml_file(filepath):
    with open(filepath, "r") as f:
        return yaml.safe_load(f)


def load_meeting_config():
    return load_yaml_file(MEETING_CONFIG_FILE)


def load_personalities_config():
    data = load_yaml_file(PERSONALITIES_CONFIG_FILE)
    return data.get("personalities", [])


def get_personality_config(input_value):
    """
    Given an input (which might be a string or a dict) from meeting.yml,
    return the full personality configuration from personalities.yml.
    """
    if isinstance(input_value, dict):
        name = input_value.get("name", "")
    else:
        name = input_value

    personalities = load_personalities_config()
    for p in personalities:
        if p.get("name", "").lower() == name.lower():
            return p
    return {"name": name, "role": "participant", "task": "", "description": ""}


def get_plugin_context():
    with open(CONTEXT_FILE, "r") as f:
        return f.read()


def call_genai(prompt):
    client = OpenAIClient()  # Adjust if you want to support other providers.
    response = ""
    for chunk in client.stream_response(prompt):
        response += chunk
    return response.strip()


def run_meeting():
    # Load meeting configuration from meeting.yml.
    meeting_config = load_meeting_config()
    objective = meeting_config.get("objective", "No objective provided.")
    meeting_personality_inputs = meeting_config.get("personalities", [])
    max_rounds = meeting_config.get("max_rounds", 5)

    # Enrich the meeting personalities with full config from personalities.yml.
    meeting_personalities = [
        get_personality_config(item) for item in meeting_personality_inputs
    ]

    # Get the user's name.
    user_name = getpass.getuser()

    # List of participant names for reference.
    participant_names = [p.get("name", "Unknown") for p in meeting_personalities]

    # Load initial plugin context.
    context = get_plugin_context()

    # Initialize transcript.
    transcript = []
    transcript.append("=== Meeting Objective ===")
    transcript.append(objective)
    transcript.append("\n=== User ===")
    transcript.append(f"User: {user_name}")
    transcript.append("\n=== Initial Plugin Context ===")
    transcript.append(context)
    transcript.append("\n=== Meeting Conversation Start ===")
    conversation_so_far = "\n".join(transcript)

    print("\n".join(transcript))  # Print initial meeting info

    # Meeting rounds.
    current_round = 1
    while current_round <= max_rounds:
        round_header = f"\n--- Round {current_round} ---"
        transcript.append(round_header)
        print(round_header)
        for personality in meeting_personalities:
            name = personality.get("name", "Unknown")
            role = personality.get("role", "participant")
            # List other participants.
            others = [n for n in participant_names if n.lower() != name.lower()]
            others_str = ", ".join(others) if others else "None"
            # Build prompt with additional meeting context.
            prompt = (
                f"You are {name}, a {role} participating in a meeting for {user_name}. "
                f"The meeting objective is:\n\n{objective}\n\n"
                f"You are here along with the following participants: {others_str}.\n\n"
                f"Your full profile details are:\n{yaml.dump(personality, default_flow_style=False)}\n\n"
                f"Here is the conversation so far:\n{conversation_so_far}\n\n"
                "Please provide your next insight, keeping in mind that you are working together with the others "
                "to develop a final actionable plan:"
            )
            response = call_genai(prompt)
            response_line = f"{name}: {response}"
            transcript.append(response_line)
            print(response_line)  # Print each personality's response
            conversation_so_far = "\n".join(transcript)
        current_round += 1

    transcript.append("\n=== Final Plan Extraction ===")
    print("\n=== Final Plan Extraction ===")
    # Build final prompt to extract a final plan.
    final_plan_prompt = (
        f"The conversation above represents a meeting with the objective:\n\n{objective}\n\n"
        "Based on the conversation, please extract a concise final plan with actionable steps for "
        f"{user_name} to achieve the objective. Provide your answer as bullet points only.\n\n"
        "Meeting Conversation:\n"
        f"{conversation_so_far}\n\n"
        "Final Plan:"
    )
    final_plan = call_genai(final_plan_prompt)
    transcript.append("Final Plan:")
    transcript.append(final_plan)
    print("\nFinal Plan:")
    print(final_plan)
    transcript.append("\n=== Meeting Transcript End ===")
    conversation_so_far = "\n".join(transcript)

    # Print complete transcript.
    print("\n=== Complete Meeting Transcript ===")
    print(conversation_so_far)

    # Save the transcript to a log file.
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(MEETING_LOG_DIR, f"meeting_{timestamp}.txt")
    with open(log_path, "w") as f:
        f.write(conversation_so_far)
    print(f"\nMeeting transcript saved to {log_path}")


if __name__ == "__main__":
    run_meeting()
