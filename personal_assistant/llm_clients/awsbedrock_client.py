import os
import json
import boto3
from botocore.exceptions import ClientError
from personal_assistant.llm_clients.base_client import LLMClient  # use absolute import


class AWSBedrockClient(LLMClient):
    def __init__(self):
        # Use AWS_REGION and AWS_BEDROCK_MODEL_ID from environment variables.
        self.aws_region = os.getenv("AWS_REGION", "us-east-1")
        self.model_id = os.getenv(
            "AWS_BEDROCK_MODEL_ID", "us.anthropic.claude-3-5-sonnet-20240620-v1:0"
        )
        try:
            self.client = boto3.client("bedrock-runtime", region_name=self.aws_region)
        except Exception as e:
            raise ValueError(f"Error creating boto3 client for Bedrock: {e}")

    def stream_response(self, prompt: str):
        # Convert the prompt to the expected messages format.
        messages = [{"role": "user", "content": [{"text": prompt}]}]
        # Optionally use a system prompt from environment variables.
        system_prompt = os.getenv("AWS_BEDROCK_SYSTEM_PROMPT", "")
        system_prompts = [{"text": system_prompt}] if system_prompt else []
        # Default inference configuration and additional fields.
        inference_config = {
            "temperature": 0.1,
            "maxTokens": 8192,
        }
        additional_model_fields = {"top_k": 200}
        try:
            response = self.client.converse_stream(
                modelId=self.model_id,
                messages=messages,
                system=system_prompts,
                inferenceConfig=inference_config,
                additionalModelRequestFields=additional_model_fields,
            )
            stream = response.get("stream")
            if stream:
                for event in stream:
                    # For simplicity, yield only contentBlockDelta text.
                    if "contentBlockDelta" in event:
                        delta_text = event["contentBlockDelta"]["delta"].get("text", "")
                        yield delta_text
                    # Optionally, you could process messageStart, messageStop, or metadata.
            else:
                yield "[Error] No stream found in response."
        except Exception as e:
            yield f"[Error] AWSBedrockClient encountered an error: {e}"


if __name__ == "__main__":
    # Test block: When running this file directly, use a test prompt.
    test_prompt = "Create a list of 3 pop songs."
    print("Sending test prompt to AWS Bedrock using Converse Stream API...\n")
    client = AWSBedrockClient()
    for chunk in client.stream_response(test_prompt):
        print(chunk, end="", flush=True)
