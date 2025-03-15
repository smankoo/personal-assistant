#!/usr/bin/env python3
"""
Meeting Mode Module with a Dedicated Leader and Tailored Participant Calls

This script implements a meeting mode that:
1. Loads the meeting configuration from meeting.yml, which includes:
   - An overall objective.
   - A designated meeting leader (by name).
   - A list of participant identifiers.
2. Retrieves each personality’s full configuration from personalities.yml.
   - Any occurrence of "{NAME_OF_USER}" in personality strings is replaced with the actual user name.
3. The meeting leader opens the meeting.
4. For each participant, the leader first uses GenAI to generate a tailored question that asks for advice in their field (including conversation context), then prompts GenAI to simulate the participant’s answer.
5. Finally, the leader integrates all responses into one final plan that directly meets the objective (using the full conversation as context).
6. All steps are printed in real time and the complete transcript is saved to a log file.
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
    Given an input (which might be a string or a dict) from meeting.yml,
    return the full personality configuration from personalities.yml with placeholders replaced.
    """
    if isinstance(input_value, dict):
        name = input_value.get("name", "")
    else:
        name = input_value

    personalities = load_personalities_config()
    for p in personalities:
        if p.get("name", "").lower() == name.lower():
            return substitute_user_in_personality(p, user_name)
    # If not found, return a default configuration.
    return {"name": name, "role": "participant", "task": "", "description": ""}


def get_plugin_context():
    with open(CONTEXT_FILE, "r") as f:
        return f.read()


def call_genai(prompt):
    client = OpenAIClient()  # Adjust for other providers if needed.
    response = ""
    for chunk in client.stream_response(prompt):
        response += chunk
    return response.strip()


def run_meeting():
    # Get the user's name immediately.
    user_name = getpass.getuser()

    # Load meeting configuration.
    meeting_config = load_meeting_config()
    objective = meeting_config.get("objective", "No objective provided.")
    leader_name = meeting_config.get("leader", "")
    participant_inputs = meeting_config.get("personalities", [])
    max_rounds = meeting_config.get(
        "max_rounds", 1
    )  # Typically one round per participant in leader-driven meetings

    if not leader_name:
        print("Error: No meeting leader specified in meeting.yml")
        return

    # Retrieve full configuration for the leader (with substitution).
    leader_config = get_personality_config(leader_name, user_name)

    # Retrieve full configurations for participants.
    participants = [
        get_personality_config(item, user_name) for item in participant_inputs
    ]

    # Get initial plugin context.
    context = get_plugin_context()

    # Initialize transcript.
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
        "Below are the profiles of the participants:\n"
    )
    for participant in participants:
        opening_prompt += f"- {participant.get('name')}: {yaml.dump(participant, default_flow_style=False)}\n"
    opening_prompt += (
        f"\nThe initial context is:\n{context}\n\n"
        "Please open the meeting by outlining the requirements and explaining what expert advice you expect from each participant."
    )
    leader_opening = call_genai(opening_prompt)
    transcript.append(f"{leader_config.get('name')} (Leader): {leader_opening}")
    print(f"\n{leader_config.get('name')} (Leader): {leader_opening}")
    conversation_so_far = "\n".join(transcript)

    # --- Leader Calls on Each Participant in Turn ---
    participant_responses = {}
    for participant in participants:
        pname = participant.get("name")
        # Generate a tailored question for the participant using GenAI.
        tailored_question_prompt = (
            f"You are {leader_config.get('name')}, the meeting leader. Based on the profile of {pname} below, "
            "generate a concise, tailored question to ask them for their expert advice in their field. "
            f"Meeting Objective: {objective}\n\n"
            f"Profile of {pname}:\n{yaml.dump(participant, default_flow_style=False)}\n\n"
            f"Here is the conversation so far:\n{conversation_so_far}\n\n"
            "The question should prompt them to share advice specific to their domain of expertise."
        )
        tailored_question = call_genai(tailored_question_prompt)
        transcript.append(
            f"{leader_config.get('name')} (Leader) asks {pname}: {tailored_question}"
        )
        print(
            f"\n{leader_config.get('name')} (Leader) asks {pname}: {tailored_question}"
        )

        # Now generate the participant's response, including the conversation context.
        response_prompt = (
            f"You are {pname}, a {participant.get('role')} with expertise in "
            f"{', '.join(participant.get('specialties', [])) if participant.get('specialties') else participant.get('role')}. "
            f"Here is the conversation so far:\n{conversation_so_far}\n\n"
            f"Respond to the following question from the meeting leader regarding the meeting objective:\n\n"
            f"Question: {tailored_question}\n\n"
            f"Meeting Objective: {objective}\n\n"
            "Please provide a thoughtful and concise answer based on your area of expertise."
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
    integration_prompt = (
        f"As the meeting leader {leader_config.get('name')}, your task is to develop a final plan that directly addresses the meeting objective:\n\n"
        f"Objective: {objective}\n\n"
        "Based on the conversation below and the participant inputs provided, please propose a final plan with concrete, actionable steps to achieve this objective. "
        "Do not merely summarize the conversation—focus on meeting the objective.\n\n"
        "Meeting Conversation:\n"
        f"{conversation_so_far}\n\n"
        "Final Plan:"
    )
    final_plan = call_genai(integration_prompt)
    transcript.append("\n=== Final Plan (Provided by Leader) ===")
    transcript.append(final_plan)
    print("\n=== Final Plan (Provided by Leader) ===")
    print(final_plan)
    transcript.append("\n=== Meeting Transcript End ===")
    conversation_so_far = "\n".join(transcript)

    # Print complete transcript.
    print("\n=== Complete Meeting Transcript ===")
    print(conversation_so_far)

    # Save transcript to log file.
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(MEETING_LOG_DIR, f"meeting_{timestamp}.txt")
    with open(log_path, "w") as f:
        f.write(conversation_so_far)
    print(f"\nMeeting transcript saved to {log_path}")


if __name__ == "__main__":
    run_meeting()
