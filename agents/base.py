"""
Agent system configuration and base classes.

This module provides the foundation for the multi-agent architecture,
including MCP server and Skills configuration support.
"""
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

from loguru import logger
from pydantic import BaseModel, Field


class AgentRole(Enum):
    """Agent role types."""
    FETCHER = "fetcher"
    SELECTOR = "selector"
    SUMMARIZER = "summarizer"
    PUBLISHER = "publisher"
    ORCHESTRATOR = "orchestrator"


class AgentStatus(Enum):
    """Agent execution status."""
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class AgentContext:
    """Shared context for agent execution."""
    session_id: str
    timestamp: str
    config: Dict[str, Any] = field(default_factory=dict)
    shared_data: Dict[str, Any] = field(default_factory=dict)

    def set(self, key: str, value: Any):
        """Set shared data."""
        self.shared_data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get shared data."""
        return self.shared_data.get(key, default)


class MCPServerConfig(BaseModel):
    """Configuration for an MCP server."""
    name: str = Field(..., description="Unique name for the MCP server")
    server_type: str = Field(default="stdio", description="Type: stdio, sse, or http")
    command: Optional[str] = Field(None, description="Command for stdio servers")
    args: List[str] = Field(default_factory=list, description="Arguments for the command")
    env: Dict[str, str] = Field(default_factory=dict, description="Environment variables")
    url: Optional[str] = Field(None, description="URL for sse/http servers")
    is_enabled: bool = Field(default=True, description="Whether the server is enabled")
    description: str = Field(default="", description="Description of the server")

    def to_claude_code_config(self) -> dict:
        """Convert to Claude Code MCP configuration format."""
        if self.server_type == "stdio":
            return {
                "command": self.command,
                "args": self.args,
                "env": self.env if self.env else None
            }
        elif self.server_type == "sse":
            return {"url": self.url}
        elif self.server_type == "http":
            return {"url": self.url, "transport": "http"}
        return {}


class SkillConfig(BaseModel):
    """Configuration for a skill."""
    name: str = Field(..., description="Unique name for the skill")
    skill_type: str = Field(default="custom", description="Type: builtin or custom")
    description: str = Field(default="", description="Description of what the skill does")
    config: Dict[str, Any] = Field(default_factory=dict, description="Skill-specific configuration")
    is_enabled: bool = Field(default=True, description="Whether the skill is enabled")
    trigger_keywords: List[str] = Field(default_factory=list, description="Keywords that trigger this skill")

    def matches_trigger(self, text: str) -> bool:
        """Check if text matches any trigger keywords."""
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in self.trigger_keywords)


class AgentConfig(BaseModel):
    """Configuration for an agent."""
    name: str = Field(..., description="Agent name")
    role: AgentRole = Field(..., description="Agent role")
    model: str = Field(default="claude-sonnet-4-6", description="Claude model to use")
    system_prompt: str = Field(default="", description="System prompt for the agent")
    tools: List[str] = Field(default_factory=list, description="Available tools")
    mcp_servers: List[str] = Field(default_factory=list, description="MCP server names to use")
    skills: List[str] = Field(default_factory=list, description="Skill names to use")
    max_tokens: int = Field(default=4096, description="Maximum output tokens")
    temperature: float = Field(default=0.7, description="Temperature for responses")


class AgentRegistry:
    """Registry for managing agents, MCP servers, and skills."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._agents = {}
            cls._instance._mcp_servers = {}
            cls._instance._skills = {}
            cls._instance._tools = {}
        return cls._instance

    # Agent management
    def register_agent(self, agent_class: Type["BaseAgent"]):
        """Register an agent class."""
        self._agents[agent_class.name] = agent_class
        logger.info(f"Registered agent: {agent_class.name}")

    def get_agent(self, name: str) -> Optional[Type["BaseAgent"]]:
        """Get an agent class by name."""
        return self._agents.get(name)

    def list_agents(self) -> List[str]:
        """List all registered agent names."""
        return list(self._agents.keys())

    # MCP Server management
    def register_mcp_server(self, config: MCPServerConfig):
        """Register an MCP server configuration."""
        self._mcp_servers[config.name] = config
        logger.info(f"Registered MCP server: {config.name}")

    def get_mcp_server(self, name: str) -> Optional[MCPServerConfig]:
        """Get an MCP server configuration by name."""
        return self._mcp_servers.get(name)

    def get_mcp_servers(self, names: List[str] = None) -> Dict[str, MCPServerConfig]:
        """Get MCP server configurations."""
        if names:
            return {n: self._mcp_servers[n] for n in names if n in self._mcp_servers}
        return self._mcp_servers.copy()

    def load_mcp_servers_from_db(self):
        """Load MCP server configurations from database."""
        from storage.database import db
        import asyncio

        async def _load():
            servers = await db.get_enabled_mcp_servers()
            for server in servers:
                config = MCPServerConfig(
                    name=server.name,
                    server_type=server.server_type,
                    command=server.command,
                    args=json.loads(server.args) if server.args else [],
                    env=json.loads(server.env) if server.env else {},
                    url=server.url,
                    is_enabled=server.is_enabled,
                    description=server.description or "",
                )
                self.register_mcp_server(config)

        asyncio.run(_load())

    # Skill management
    def register_skill(self, config: SkillConfig):
        """Register a skill configuration."""
        self._skills[config.name] = config
        logger.info(f"Registered skill: {config.name}")

    def get_skill(self, name: str) -> Optional[SkillConfig]:
        """Get a skill configuration by name."""
        return self._skills.get(name)

    def get_skills(self, names: List[str] = None) -> Dict[str, SkillConfig]:
        """Get skill configurations."""
        if names:
            return {n: self._skills[n] for n in names if n in self._skills}
        return self._skills.copy()

    def get_matching_skills(self, text: str) -> List[SkillConfig]:
        """Get skills that match trigger keywords in text."""
        return [s for s in self._skills.values() if s.is_enabled and s.matches_trigger(text)]

    def load_skills_from_db(self):
        """Load skill configurations from database."""
        from storage.database import db
        import asyncio

        async def _load():
            skills = await db.get_enabled_skills()
            for skill in skills:
                config = SkillConfig(
                    name=skill.name,
                    skill_type=skill.skill_type,
                    description=skill.description or "",
                    config=json.loads(skill.config) if skill.config else {},
                    is_enabled=skill.is_enabled,
                )
                self.register_skill(config)

        asyncio.run(_load())

    # Tool management
    def register_tool(self, name: str, func: Callable):
        """Register a tool function."""
        self._tools[name] = func
        logger.info(f"Registered tool: {name}")

    def get_tool(self, name: str) -> Optional[Callable]:
        """Get a tool function by name."""
        return self._tools.get(name)


# Global registry instance
registry = AgentRegistry()


class BaseAgent(ABC):
    """Base class for all agents."""

    name: str = "base_agent"
    description: str = "Base agent class"
    role: AgentRole = AgentRole.FETCHER

    def __init__(self, config: AgentConfig = None):
        self.config = config or AgentConfig(name=self.name, role=self.role)
        self.status = AgentStatus.IDLE
        self.last_error: Optional[str] = None
        self.registry = registry

    @abstractmethod
    async def execute(self, context: AgentContext) -> Any:
        """Execute the agent's main task."""
        pass

    async def run(self, context: AgentContext) -> Any:
        """Run the agent with error handling and logging."""
        self.status = AgentStatus.RUNNING
        logger.info(f"Agent {self.name} starting execution")

        try:
            result = await self.execute(context)
            self.status = AgentStatus.SUCCESS
            logger.info(f"Agent {self.name} completed successfully")
            return result
        except Exception as e:
            self.status = AgentStatus.FAILED
            self.last_error = str(e)
            logger.error(f"Agent {self.name} failed: {e}")
            raise

    def get_mcp_tools(self) -> List[dict]:
        """Get tools from configured MCP servers."""
        tools = []
        for server_name in self.config.mcp_servers:
            server = self.registry.get_mcp_server(server_name)
            if server:
                # MCP tools will be discovered at runtime
                tools.append({
                    "type": "mcp",
                    "server": server_name
                })
        return tools

    def get_skill_tools(self) -> List[dict]:
        """Get tools from configured skills."""
        return [{"type": "skill", "name": name} for name in self.config.skills]


def register_agent(cls):
    """Decorator to automatically register an agent class."""
    registry.register_agent(cls)
    return cls