#!/usr/bin/env python3
"""
Meeting Mode Module with a Dedicated Leader, Enhanced Context, and Full Personality Configuration Passing

This script implements a meeting mode that:
1. Loads meeting configuration from meeting.yml, which includes:
   - An overall meeting objective.
   - A designated meeting leader (by name).
   - A list of participant identifiers.
2. Retrieves each personality’s full configuration from personal_assistant/personalities.yml,
   replacing any "{NAME_OF_USER}" placeholder with the actual user name.
3. Uses the detailed original context (e.g., TODOs, Calendar events) from the plugin output.
4. The meeting leader opens the meeting and then calls on each participant:
   - The leader generates a tailored question via GenAI that asks the participant for expert advice in their field,
     passing along the full personality configuration.
   - The participant’s response is then generated via another GenAI call, again receiving their entire configuration.
   - The leader thanks the participant.
5. Finally, the leader integrates all expert inputs into a final plan that directly meets the objective.
   The integration prompt instructs the leader to use their own style dynamically (based on their configuration).
6. All responses are streamed and printed in real time, and the complete transcript is saved to a log file.
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


def substitute_user_in_personality(personality, user_name):
    """
    Replace occurrences of "{NAME_OF_USER}" in all string fields with the actual user_name.
    """
    new_config = {}
    for key, value in personality.items():
        if isinstance(value, str):
            new_config[key] = value.replace("{NAME_OF_USER}", user_name)
        else:
            new_config[key] = value
    return new_config


def get_personality_config(input_value, user_name):
    """
    Given an input (string or dict) from meeting.yml, return the full personality configuration
    from personal_assistant/personalities.yml, with any {NAME_OF_USER} placeholders replaced.
    """
    if isinstance(input_value, dict):
        name = input_value.get("name", "")
    else:
        name = input_value

    personalities = load_personalities_config()
    for p in personalities:
        if p.get("name", "").lower() == name.lower():
            return substitute_user_in_personality(p, user_name)
    return {"name": name, "role": "participant", "task": "", "description": ""}


def get_plugin_context():
    with open(CONTEXT_FILE, "r") as f:
        return f.read()


def call_genai(prompt):
    """
    Call the GenAI client to stream a response.
    Each chunk is printed immediately for a better user experience.
    """
    client = OpenAIClient()  # Using OpenAIClient as default.
    response = ""
    print("\n[GenAI Response Streaming]:", flush=True)
    for chunk in client.stream_response(prompt):
        print(chunk, end="", flush=True)
        response += chunk
    print()  # Newline after streaming.
    return response.strip()


def run_meeting():
    # Determine the user's name.
    user_name = getpass.getuser()

    # Load meeting configuration.
    meeting_config = load_meeting_config()
    objective = meeting_config.get("objective", "No objective provided.")
    leader_name = meeting_config.get("leader", "")
    participant_inputs = meeting_config.get("personalities", [])
    max_rounds = meeting_config.get(
        "max_rounds", 1
    )  # Typically one round for leader-driven meetings

    if not leader_name:
        print("Error: No meeting leader specified in meeting.yml")
        return

    # Retrieve full configurations for the leader and participants.
    leader_config = get_personality_config(leader_name, user_name)
    participants = [
        get_personality_config(item, user_name) for item in participant_inputs
    ]

    # Get the original detailed context from plugin output.
    context = get_plugin_context()

    # Initialize the transcript.
    transcript = []
    transcript.append("=== Meeting Objective ===")
    transcript.append(objective)
    transcript.append("\n=== User ===")
    transcript.append(f"User: {user_name}")
    transcript.append("\n=== Initial Plugin Context ===")
    transcript.append(context)
    transcript.append("\n=== Meeting Begins ===")
    conversation_so_far = "\n".join(transcript)
    print("\n".join(transcript))

    # --- Meeting Leader Opens the Meeting ---
    opening_prompt = (
        f"You are {leader_config.get('name')}, a {leader_config.get('role')} and the designated meeting leader. "
        f"Your task is to lead a meeting for {user_name} with the following objective:\n\n{objective}\n\n"
        "Below are the detailed profiles of the participants (complete configuration provided):\n"
    )
    for participant in participants:
        opening_prompt += f"- {participant.get('name')}: {yaml.dump(participant, default_flow_style=False)}\n"
    opening_prompt += (
        f"\nThe original detailed context (including TODOs, Calendar events, etc.) is:\n{context}\n\n"
        "Please open the meeting by outlining the requirements and specifying what expert advice you expect from each participant."
    )
    leader_opening = call_genai(opening_prompt)
    transcript.append(f"{leader_config.get('name')} (Leader): {leader_opening}")
    print(f"\n{leader_config.get('name')} (Leader): {leader_opening}")
    conversation_so_far = "\n".join(transcript)

    # --- Leader Calls on Each Participant in Turn ---
    participant_responses = {}
    for participant in participants:
        pname = participant.get("name")
        # Generate a tailored question for the participant.
        tailored_question_prompt = (
            f"You are {leader_config.get('name')}, the meeting leader. Based on the full profile of {pname} below, "
            "generate a concise, tailored question to ask them for expert advice in their specific field. "
            f"Meeting Objective: {objective}\n\n"
            f"Full Profile of {pname}:\n{yaml.dump(participant, default_flow_style=False)}\n\n"
            f"Conversation so far:\n{conversation_so_far}\n\n"
            "The question should prompt them to share advice specific to their area of expertise."
        )
        tailored_question = call_genai(tailored_question_prompt)
        transcript.append(
            f"{leader_config.get('name')} (Leader) asks {pname}: {tailored_question}"
        )
        print(
            f"\n{leader_config.get('name')} (Leader) asks {pname}: {tailored_question}"
        )

        # Generate the participant's response.
        response_prompt = (
            f"You are {pname}, a {participant.get('role')} with expertise in "
            f"{', '.join(participant.get('specialties', [])) if participant.get('specialties') else participant.get('role')}. "
            f"Your full profile is as follows:\n{yaml.dump(participant, default_flow_style=False)}\n\n"
            f"Here is the conversation so far:\n{conversation_so_far}\n\n"
            f"Respond to the following question regarding the meeting objective:\n\n"
            f"Question: {tailored_question}\n\n"
            f"Meeting Objective: {objective}\n\n"
            "Please provide a thoughtful, context-aware answer that reflects your expertise, while taking into account the conversation so far."
        )
        participant_response = call_genai(response_prompt)
        transcript.append(f"{pname}'s response: {participant_response}")
        print(f"{pname}'s response: {participant_response}")
        participant_responses[pname] = participant_response

        # Leader thanks the participant.
        thank_you = f"Thank you, {pname}, for your valuable input."
        transcript.append(f"{leader_config.get('name')} (Leader): {thank_you}")
        print(f"{leader_config.get('name')} (Leader): {thank_you}")
        conversation_so_far = "\n".join(transcript)

    # --- Leader Integrates All Advice into a Final Plan ---
    # Use leader's tone from configuration dynamically.
    leader_tone = leader_config.get("tone", "engaging")
    integration_prompt = (
        f"As the meeting leader {leader_config.get('name')}, your task is to develop a final plan that directly meets the meeting objective "
        "by integrating all the expert inputs. Do NOT simply summarize the conversation; instead, produce a coherent final plan with concrete, actionable steps. "
        "Ensure you incorporate all key details from the original detailed context (including TODOs and Calendar events).\n\n"
        f"Meeting Objective: {objective}\n\n"
        f"Original Detailed Context:\n{context}\n\n"
        "Participant Inputs:\n"
    )
    for pname, response in participant_responses.items():
        integration_prompt += f"- {pname}: {response}\n"
    integration_prompt += (
        f"\nNow, using your personal style (as defined in your configuration with tone: '{leader_tone}'), "
        "produce the final plan as a set of bullet points that directly fulfills the meeting objective."
        "\n\nFinal Plan:"
    )
    final_plan = call_genai(integration_prompt)
    transcript.append("\n=== Final Plan (Provided by Leader) ===")
    transcript.append(final_plan)
    print("\n=== Final Plan (Provided by Leader) ===")
    print(final_plan)
    transcript.append("\n=== Meeting Transcript End ===")
    conversation_so_far = "\n".join(transcript)

    # Save transcript to a log file.
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(MEETING_LOG_DIR, f"meeting_{timestamp}.txt")
    with open(log_path, "w") as f:
        f.write(conversation_so_far)
    print(f"\nMeeting transcript saved to {log_path}")


if __name__ == "__main__":
    run_meeting()
