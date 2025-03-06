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
You are a helpful assistant that observes and records patterns and any other useful information about the user.
The user's data is provided below. Please observe and record patterns and any other useful information about the user.
Only output useful observations and those that you are confident about.
For example, if you notice a repeat pattern of the user waking up at a certain time, then it is useful to note that the user typically wakes up at that time.
However, if there's is a one-off, such as the user ate bananas or something, that is not useful. On the other hand, if the user eats bananas every single day, then that is a confident observation.
Not all observations need to be based on repeat occurrences, for example, if the user mentions a chronic disease they are managing, or any other health condition, or a permanent change of any sort in their lives (moving houses, childbirth, etc), those would also be good observations.
You may also have to infer observations, such as, if the user says they ate paratha, then they say they had chai, then at some point they say they had butter chicken, then the user eats Indian food.
Also, address the user by name, not 'The user'.
Also, only make observations that are not already known. If there are no new observations, it is completely ok to return a blank xml tag <observations></observations>
Output Template:
<observations>
- [observations go here...] (each observation should be a bullet point in markdown format)
</observations>

Here is the input data:
<input_data>
{user_data}
</input_data>

Here are observations already known about the user:
<known_observations>
{known_observations}
</known_observations>
"""
    prompt = template.format(user_data=user_data, known_observations=known_observations)
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

    new_observation = (
        new_observation_xml.replace("<observations>", "")
        .replace("</observations>", "")
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
