"""ClaimLens AI Model Providers."""
import os
from .mock import MockModelProvider
from .sagemaker import SageMakerModelProvider


def get_model_provider():
    provider_type = os.getenv("AI_MODEL_PROVIDER", "mock").lower()
    if provider_type == "sagemaker":
        return SageMakerModelProvider()
    return MockModelProvider()


__all__ = [
    "MockModelProvider",
    "SageMakerModelProvider",
    "get_model_provider",
]
