"""
Prompts module for loading prompt templates and skills.
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


# ============================================================================
# Skills Integration
# ============================================================================

SKILLS_DIR = Path(__file__).parent.parent.parent / ".claude" / "skills"


def load_skill(skill_name: str, include_examples: bool = True, include_reference: bool = True) -> str:
    """
    Load a skill's content from SKILL.md and optional resources.

    Skills are modular markdown files that provide platform-specific guidance
    for content generation. They support progressive disclosure:
    - SKILL.md: Core instructions (always loaded)
    - examples/: Example outputs (optional)
    - reference.md: Reference documentation (optional)

    Args:
        skill_name: Name of the skill (e.g., "xhs-publisher", "wechat-publisher")
        include_examples: Whether to include examples from examples/ directory
        include_reference: Whether to include reference.md

    Returns:
        Combined skill content as a string

    Example:
        >>> skill_content = load_skill("xhs-publisher")
        >>> # Returns SKILL.md + examples + reference.md content
    """
    skill_dir = SKILLS_DIR / skill_name
    if not skill_dir.exists():
        raise FileNotFoundError(f"Skill not found: {skill_dir}")

    parts = []

    # 1. Load main SKILL.md
    skill_file = skill_dir / "SKILL.md"
    if skill_file.exists():
        content = skill_file.read_text(encoding="utf-8")
        # Remove YAML frontmatter for LLM consumption
        if content.startswith("---"):
            end_idx = content.find("---", 3)
            if end_idx != -1:
                content = content[end_idx + 3:].strip()
        parts.append(content)

    # 2. Load examples
    if include_examples:
        examples_dir = skill_dir / "examples"
        if examples_dir.exists():
            example_files = sorted(examples_dir.glob("*.md"))
            if example_files:
                parts.append("\n\n## Examples\n")
                for ef in example_files:
                    example_content = ef.read_text(encoding="utf-8")
                    parts.append(f"### {ef.stem}\n\n{example_content}\n")

    # 3. Load reference
    if include_reference:
        ref_file = skill_dir / "reference.md"
        if ref_file.exists():
            ref_content = ref_file.read_text(encoding="utf-8")
            parts.append(f"\n\n## Reference\n\n{ref_content}")

    return "\n".join(parts)


def load_skill_prompt(skill_name: str) -> str:
    """
    Load skill as a ready-to-use system prompt.

    This is a convenience function that formats the skill content
    as a system prompt for LLM calls.

    Args:
        skill_name: Name of the skill

    Returns:
        Formatted system prompt string
    """
    skill_content = load_skill(skill_name)

    # Add context about the skill
    header = f"""You are an expert content creator following the {skill_name} skill guidelines.

Follow the instructions below to generate high-quality platform-specific content.

"""
    return header + skill_content


def list_skills() -> list[str]:
    """
    List all available skills.

    Returns:
        List of skill names
    """
    if not SKILLS_DIR.exists():
        return []
    return [d.name for d in SKILLS_DIR.iterdir() if d.is_dir() and (d / "SKILL.md").exists()]


def get_skill_metadata(skill_name: str) -> dict:
    """
    Extract metadata from a skill's YAML frontmatter.

    Args:
        skill_name: Name of the skill

    Returns:
        Dict with skill metadata (name, description, argument-hint, etc.)
    """
    skill_file = SKILLS_DIR / skill_name / "SKILL.md"
    if not skill_file.exists():
        raise FileNotFoundError(f"Skill not found: {skill_file}")

    content = skill_file.read_text(encoding="utf-8")

    # Parse YAML frontmatter
    metadata = {}
    if content.startswith("---"):
        end_idx = content.find("---", 3)
        if end_idx != -1:
            yaml_content = content[3:end_idx].strip()
            for line in yaml_content.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    metadata[key.strip()] = value.strip().strip('"').strip("'")

    return metadata