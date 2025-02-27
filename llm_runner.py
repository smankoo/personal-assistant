#!/usr/bin/env python3
import sys
import os
from personal_assistant.llm_clients.openai_client import OpenAIClient
from personal_assistant.llm_clients.awsbedrock_client import AWSBedrockClient


def main():
    if len(sys.argv) < 3:
        print("Usage: {} <compiled_prompt_file> <llm_provider>".format(sys.argv[0]))
        sys.exit(1)

    prompt_file = sys.argv[1]
    provider = sys.argv[2].lower()

    if not os.path.exists(prompt_file):
        print(f"[ERROR] Compiled prompt file not found: {prompt_file}")
        sys.exit(1)

    with open(prompt_file, "r", encoding="utf-8") as f:
        prompt = f.read()

    # Select the LLM client based on the provider argument.
    if provider == "openai":
        client = OpenAIClient()
    elif provider == "awsbedrock":
        client = AWSBedrockClient()
    else:
        print(f"[ERROR] Unknown LLM provider: {provider}")
        sys.exit(1)

    # Stream and print the response.
    for chunk in client.stream_response(prompt):
        print(chunk, end="", flush=True)


if __name__ == "__main__":
    main()
