import os
from openai import OpenAI
from personal_assistant.llm_clients.base_client import LLMClient  # Use absolute import


class OpenAIClient(LLMClient):
    def __init__(self, model_name="gpt-4o"):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not set in environment variables.")
        # Default to "gpt-4o-mini" or override with OPENAI_MODEL env variable.
        self.model = model_name
        self.client = OpenAI(api_key=self.api_key)

    def stream_response(self, prompt: str):
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                stream=True,
            )
            for chunk in stream:
                # Using the new dot-notation for attribute access.
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            yield f"[Error] OpenAIClient encountered an error: {e}"


if __name__ == "__main__":
    # Test block: When run directly, send a test prompt and print the streamed output.
    test_prompt = "List three creative ideas for a novel."
    print("Sending test prompt to OpenAI...\n")
    client = OpenAIClient()
    for chunk in client.stream_response(test_prompt):
        print(chunk, end="", flush=True)
