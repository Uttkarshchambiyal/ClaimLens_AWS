"""SageMaker AI inference model provider for production deployment."""
from __future__ import annotations

import json
import os
from typing import Any


class SageMakerModelProvider:
    def __init__(
        self,
        endpoint_name: str | None = None,
        region_name: str | None = None,
        model_name: str | None = None,
    ):
        self.endpoint_name = endpoint_name or os.getenv("SAGEMAKER_ENDPOINT_NAME", "claimlens-assistant-endpoint")
        self.region_name = region_name or os.getenv("AWS_REGION", "ap-south-1")
        self.model_name = model_name or os.getenv("SAGEMAKER_MODEL_NAME", "meta-llama-3-8b-instruct")
        self._client = None

    def _get_client(self):
        if self._client is None:
            import boto3
            self._client = boto3.client("sagemaker-runtime", region_name=self.region_name)
        return self._client

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> str:
        """Invoke SageMaker endpoint with formatted prompt and generation parameters."""
        client = self._get_client()

        # Format input for standard instruction-following models on SageMaker
        formatted_input = f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n{system_prompt or ''}<|eot_id|><|start_header_id|>user<|end_header_id|>\n{prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n"

        payload = {
            "inputs": formatted_input,
            "parameters": {
                "max_new_tokens": max_tokens,
                "temperature": temperature,
                "top_p": 0.9,
                "return_full_text": False,
            },
        }

        try:
            response = client.invoke_endpoint(
                EndpointName=self.endpoint_name,
                ContentType="application/json",
                Accept="application/json",
                Body=json.dumps(payload),
            )
            body = response["Body"].read().decode("utf-8")
            result = json.loads(body)
            if isinstance(result, list) and result and "generated_text" in result[0]:
                return result[0]["generated_text"].strip()
            elif isinstance(result, dict) and "generated_text" in result:
                return result["generated_text"].strip()
            elif isinstance(result, dict) and "outputs" in result:
                return result["outputs"].strip()
            return str(result)
        except Exception as exc:
            raise RuntimeError(f"SageMaker endpoint invocation failed: {exc}") from exc
