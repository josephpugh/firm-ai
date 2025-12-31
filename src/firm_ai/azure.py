"""Azure OpenAI helpers shared by tools."""

from __future__ import annotations

import os
from typing import Optional

DEFAULT_SCOPE = "https://cognitiveservices.azure.com/.default"


class AzureDependencyError(RuntimeError):
    pass


def get_bearer_token(scope: str = DEFAULT_SCOPE) -> str:
    """Return an Azure AD bearer token for Azure OpenAI."""

    try:
        from azure.identity import DefaultAzureCredential
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise AzureDependencyError(
            "azure-identity is required for get_bearer_token()"
        ) from exc

    credential = DefaultAzureCredential()
    token = credential.get_token(scope)
    return token.token


def get_azure_openai_client(
    *,
    endpoint: Optional[str] = None,
    api_version: Optional[str] = None,
    token: Optional[str] = None,
):
    """Create an AzureOpenAI client using environment or provided settings."""

    try:
        from openai import AzureOpenAI
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise AzureDependencyError(
            "openai is required for get_azure_openai_client()"
        ) from exc

    endpoint = endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
    api_version = api_version or os.getenv("AZURE_OPENAI_API_VERSION")

    if not endpoint:
        raise ValueError("Azure OpenAI endpoint is required")
    if not api_version:
        raise ValueError("Azure OpenAI api_version is required")

    if token is None:
        token = get_bearer_token()

    return AzureOpenAI(
        azure_endpoint=endpoint,
        api_version=api_version,
        azure_ad_token=token,
    )
