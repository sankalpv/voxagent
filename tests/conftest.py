"""
Shared fixtures for the VoxAgent test suite.
"""

import os
import sys
import pytest

# Ensure the project root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def load_api_key() -> str:
    """Load GEMINI_API_KEY from .env file."""
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("GEMINI_API_KEY=") and not line.startswith("#"):
                    return line.split("=", 1)[1].strip()
    return os.environ.get("GEMINI_API_KEY", "")


@pytest.fixture(scope="session")
def gemini_api_key():
    """Provide the Gemini API key, skip if not available."""
    key = load_api_key()
    if not key:
        pytest.skip("GEMINI_API_KEY not found in .env")
    return key