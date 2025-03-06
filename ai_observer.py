# Make a call to GenAI to Observe and record patterns and any other useful information about the user
from personal_assistant.llm_clients.openai_client import OpenAIClient
import os


OBSIDIAN_VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH")
if not OBSIDIAN_VAULT_PATH:
    raise ValueError("OBSIDIAN_VAULT_PATH environment variable not set.")

OBSERVATIONS_FILE_PATH = os.path.join(
    OBSIDIAN_VAULT_PATH, "2 Areas", "Notes by AI", "Observations.md"
)


def get_observation(user_data: str, known_observations: str) -> str:
    """
    Make a call to GenAI to Observe and record patterns and any other useful information about the user
    """
    client = OpenAIClient()
    template = """
You are a helpful assistant that identifies new, meaningful, and practically useful patterns or insights about the user from the provided data.

You will receive:
1. User's latest input data (`<input_data>`).
2. Previously known observations (`<known_observations>`).

**Rules to Follow:**
- Only generate observations that are genuinely new and not explicitly or implicitly covered by existing known observations.
- Do NOT rephrase or slightly modify known observations; this is NOT useful.
- Observations must have clear, practical value for future reference or decision-making. Avoid trivial, mundane, or one-off occurrences.
- If no genuinely new or valuable insights can be confidently identified, explicitly return an empty observations tag: `<new_observations></new_observations>`.
- Refer to the user by name, if known, not 'the user'.

**Criteria for useful observations:**
- Recurring actions not previously identified.
- Important changes in behavior or routines.
- Notable trends in user habits, preferences, or decision-making.
- Information that significantly impacts health, scheduling, finances, or family logistics and has not been recorded before.
- Highly specific details that substantially enhance understanding beyond prior general observations.

Use the following output structure exactly:

<new_observations>
- [Each distinct, meaningful, and specific observation as a markdown-formatted bullet]
</new_observations>

Input data:
<input_data>
{user_data}
</input_data>

Already known observations (do NOT repeat or rephrase these):
<known_observations>
{known_observations}
</known_observations>
"""
    prompt = template.format(user_data=user_data, known_observations=known_observations)
    # print(f"---Known Observations---\n{known_observations}")

    observation_stream = client.stream_response(prompt)

    # compile all output stream into a single string
    observation = ""
    for chunk in observation_stream:
        observation += chunk

    return observation


def ensure_dir_file_structure():
    try:
        if not os.path.exists(OBSERVATIONS_FILE_PATH):
            os.makedirs(os.path.dirname(OBSERVATIONS_FILE_PATH), exist_ok=True)
            with open(OBSERVATIONS_FILE_PATH, "w") as f:
                initial_content = """---
ai-context-enabled: "true"
---
# Observations

"""
                f.write(initial_content)
    except Exception as e:
        print(f"Error creating directory structure: {e}")
        exit(1)


def save_observation(observation: str, file_path: str):
    """
    Save the observation to a file in the Obsidian vault.
    """
    ensure_dir_file_structure()
    with open(file_path, "a") as f:
        f.write(observation + "\n\n")


def get_and_save_observations(user_data):
    # Read observations file, if it exists
    known_observations = ""
    if os.path.exists(OBSERVATIONS_FILE_PATH):
        with open(OBSERVATIONS_FILE_PATH, "r") as f:
            known_observations = f.read()

    new_observation_xml = get_observation(user_data, known_observations)
    # print(f"---New Observations---\n{new_observation_xml}")

    new_observation = (
        new_observation_xml.replace("<new_observations>", "")
        .replace("</new_observations>", "")
        .strip()
    )

    if new_observation:
        save_observation(new_observation, OBSERVATIONS_FILE_PATH)
        print(f"Saved observation to {OBSERVATIONS_FILE_PATH}")


if __name__ == "__main__":
    test_user_data = "I go to the gym every day and run for at leaft 5 minutes. I am watching 'waqt hamara hai' now"

    # get user data file name as the first argument
    import sys

    if len(sys.argv) < 2:
        raise ValueError("No user data file provided.")

    user_data = sys.argv[1]
    if not user_data:
        raise ValueError("No user data provided.")
    if not os.path.exists(user_data):
        raise ValueError(f"File {user_data} does not exist.")
    with open(user_data, "r") as f:
        user_data = f.read()

    if not user_data:
        raise ValueError("User data file is empty.")

    get_and_save_observations(user_data)
