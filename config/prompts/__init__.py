"""
Prompts module for loading prompt templates.
"""
from pathlib import Path
from typing import Optional

from config.settings import settings


def load_prompt(name: str) -> str:
    """
    Load a prompt template by name.

    Args:
        name: Prompt name (without .txt extension)

    Returns:
        Prompt template string
    """
    prompt_file = settings.PROMPTS_DIR / f"{name}.txt"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Prompt file not found: {prompt_file}")


def get_prompt_path(name: str) -> Path:
    """Get the path to a prompt file."""
    return settings.PROMPTS_DIR / f"{name}.txt"


def list_prompts() -> list:
    """List all available prompt templates."""
    return [f.stem for f in settings.PROMPTS_DIR.glob("*.txt") if f.is_file()]