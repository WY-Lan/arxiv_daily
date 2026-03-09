"""
Agent system for multi-agent arxiv daily push.

This module provides the agent framework with MCP/Skills support.
"""
from .base import (
    AgentConfig,
    AgentContext,
    AgentRegistry,
    AgentRole,
    AgentStatus,
    BaseAgent,
    MCPServerConfig,
    SkillConfig,
    registry,
    register_agent,
)

__all__ = [
    "AgentConfig",
    "AgentContext",
    "AgentRegistry",
    "AgentRole",
    "AgentStatus",
    "BaseAgent",
    "MCPServerConfig",
    "SkillConfig",
    "registry",
    "register_agent",
]