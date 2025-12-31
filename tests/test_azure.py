from __future__ import annotations

import os
import sys
import types
import unittest
from unittest.mock import patch

import tests

from firm_ai import azure


class DummyToken:
    def __init__(self, token: str):
        self.token = token


class DummyCredential:
    def __init__(self) -> None:
        self.scopes: list[str] = []

    def get_token(self, scope: str) -> DummyToken:
        self.scopes.append(scope)
        return DummyToken("token-value")


class DummyAzureOpenAI:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class TestAzureAuth(unittest.TestCase):
    def test_get_bearer_token_success(self) -> None:
        identity_module = types.ModuleType("azure.identity")
        identity_module.DefaultAzureCredential = DummyCredential
        azure_module = types.ModuleType("azure")
        azure_module.identity = identity_module

        with patch.dict(
            sys.modules, {"azure": azure_module, "azure.identity": identity_module}
        ):
            token = azure.get_bearer_token("scope")

        self.assertEqual(token, "token-value")

    def test_get_bearer_token_missing_dependency(self) -> None:
        real_import = __import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "azure.identity":
                raise ImportError("missing azure")
            return real_import(name, globals, locals, fromlist, level)

        with patch("builtins.__import__", side_effect=fake_import):
            with self.assertRaises(azure.AzureDependencyError):
                azure.get_bearer_token()


class TestAzureClient(unittest.TestCase):
    def test_get_azure_openai_client_missing_dependency(self) -> None:
        real_import = __import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "openai":
                raise ImportError("missing openai")
            return real_import(name, globals, locals, fromlist, level)

        with patch("builtins.__import__", side_effect=fake_import):
            with self.assertRaises(azure.AzureDependencyError):
                azure.get_azure_openai_client(
                    endpoint="https://example.com",
                    api_version="2024-01-01",
                    token="token",
                )

    def test_get_azure_openai_client_requires_endpoint(self) -> None:
        openai_module = types.ModuleType("openai")
        openai_module.AzureOpenAI = DummyAzureOpenAI

        with patch.dict(sys.modules, {"openai": openai_module}):
            with self.assertRaises(ValueError):
                azure.get_azure_openai_client(api_version="2024-01-01", token="token")

    def test_get_azure_openai_client_requires_api_version(self) -> None:
        openai_module = types.ModuleType("openai")
        openai_module.AzureOpenAI = DummyAzureOpenAI

        with patch.dict(sys.modules, {"openai": openai_module}):
            with self.assertRaises(ValueError):
                azure.get_azure_openai_client(endpoint="https://example.com", token="t")

    def test_get_azure_openai_client_uses_env_and_token(self) -> None:
        openai_module = types.ModuleType("openai")
        openai_module.AzureOpenAI = DummyAzureOpenAI

        with patch.dict(sys.modules, {"openai": openai_module}), patch.dict(
            os.environ,
            {"AZURE_OPENAI_ENDPOINT": "https://example.com", "AZURE_OPENAI_API_VERSION": "2024-01-01"},
        ), patch("firm_ai.azure.get_bearer_token", return_value="tok") as get_token:
            client = azure.get_azure_openai_client()

        self.assertIsInstance(client, DummyAzureOpenAI)
        self.assertEqual(
            client.kwargs,
            {
                "azure_endpoint": "https://example.com",
                "api_version": "2024-01-01",
                "azure_ad_token": "tok",
            },
        )
        get_token.assert_called_once()

    def test_get_azure_openai_client_honors_provided_token(self) -> None:
        openai_module = types.ModuleType("openai")
        openai_module.AzureOpenAI = DummyAzureOpenAI

        with patch.dict(sys.modules, {"openai": openai_module}), patch(
            "firm_ai.azure.get_bearer_token"
        ) as get_token:
            client = azure.get_azure_openai_client(
                endpoint="https://example.com",
                api_version="2024-01-01",
                token="explicit",
            )

        self.assertIsInstance(client, DummyAzureOpenAI)
        self.assertEqual(client.kwargs["azure_ad_token"], "explicit")
        get_token.assert_not_called()
