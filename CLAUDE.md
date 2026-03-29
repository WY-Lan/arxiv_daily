# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Arxiv Daily Push is a multi-agent system for daily AI Agent paper recommendations. It fetches papers from arxiv, evaluates them using a 4-dimensional scoring system, and publishes curated content to multiple platforms (Notion, Xiaohongshu, WeChat Official Account).

## Key Commands

```bash
# Run full pipeline once
python main.py run

# Start scheduled daily execution (at configured SCHEDULE_HOUR:SCHEDULE_MINUTE)
python main.py schedule

# Fetch papers only (without publishing)
python main.py fetch

# Run selection only
python main.py select

# Show current configuration
python main.py config

# Install dependencies
pip install -r requirements.txt
```

### Platform-specific Testing

```bash
# Test Notion publishing
python tools/test_notion.py

# Test WeChat publishing
python tools/test_wechat_nplus1.py --mode all

# Test WeChat n+1 mode (dry run)
python tools/test_wechat_nplus1.py --mode nplus1

# Test WeChat n+1 mode (actual)
python tools/test_wechat_nplus1.py --mode nplus1 --no-dry-run
```

### WeChat Publishing Commands

```bash
# n+1 mode: n detailed posts + 1 summary (recommended)
python main.py wechat --mode nplus1

# Collection mode: single summary post
python main.py wechat --mode collection

# Check WeChat API connection
python tools/test_wechat_nplus1.py --mode connection
```

## Architecture

### Multi-Agent Pipeline Flow

```
OrchestratorAgent → PaperFetcherAgent → SelectionAgent → SummaryAgent → PublisherAgents
```

All agents are in `agents/paper_fetcher.py` except publishers which are in `agents/publishers/__init__.py`.

### Agent System

- **Base class**: `BaseAgent` in `agents/base.py`
- **Registration**: Use `@register_agent` decorator for automatic registration
- **Context**: `AgentContext` provides shared state via `context.set(key, value)` and `context.get(key)`
- **Registry**: `AgentRegistry` singleton manages agents, MCP servers, and skills

### Publisher Agents

Each publisher handles a specific platform:

| Agent | Platform | Implementation Status |
|-------|----------|----------------------|
| `NotionPublisherAgent` | Notion | Uses Notion MCP |
| `XHSPublisherAgent` | Xiaohongshu | Uses xiaohongshu-mcp, creates collection posts |
| `WeChatMPPublisherAgent` | WeChat MP | n+1 mode with PDF cover screenshots |

**WeChat n+1 Mode**: Creates n detailed articles (one per paper) + 1 summary article. The number n is dynamic, determined by selection results. Cover images use arxiv PDF screenshots.

### LLM Integration

- **Provider**: Alibaba Bailian (阿里百炼) via OpenAI-compatible API
- **Client**: `tools/llm_client.py` - `BailianClient` class
- **Models**: `qwen-max` for selection/summary, `qwen-plus` for publishing
- **Config**: `BAILIAN_API_KEY` environment variable

### Data Sources

| Source | Tool | Purpose |
|--------|------|---------|
| arXiv | `tools/arxiv_api.py` | Paper fetching |
| Semantic Scholar | `tools/semantic_scholar.py` | Citation counts |
| OpenAlex | `tools/openalex.py` | Author influence |
| Papers with Code | `tools/papers_with_code.py` | Community metrics |

### Configuration

- `config/settings.py`: Pydantic settings loaded from `.env`
- `config/prompts/`: Platform-specific prompt templates
  - `selection.txt`, `summary.txt` - Core prompts
  - `xhs_collection.txt`, `wechat_single_paper.txt` - Platform-specific formats

### Database

- SQLite with async SQLAlchemy (`storage/database.py`)
- Tables: `papers`, `publish_records`, `agent_executions`, `mcp_server_configs`, `skill_configs`
- Use the global `db` instance for all database operations

## Important Patterns

- All async operations use `asyncio`
- Database operations go through the global `db` instance from `storage/database.py`
- Prompt templates are loaded via `from config.prompts import load_prompt`
- LLM calls use `llm_client.generate_json()` for structured output

## MCP/Skills Extension

The system supports dynamic MCP server and skill configuration through the database:

```python
# Add MCP server at runtime
await db.save_mcp_server({
    "name": "custom_tool",
    "server_type": "stdio",
    "command": "python",
    "args": '["server.py"]',
    "is_enabled": True
})

# Add skill at runtime
await db.save_skill({
    "name": "custom_skill",
    "skill_type": "custom",
    "config": '{"param": "value"}',
    "is_enabled": True
})
```

## Platform Configuration

Required environment variables (see `.env.example`):

- `BAILIAN_API_KEY` - Required for LLM operations
- `NOTION_API_KEY`, `NOTION_DATABASE_ID` - For Notion publishing
- `WECHAT_APP_ID`, `WECHAT_APP_SECRET` - For WeChat MP

## PDF Cover Generation

XHS and WeChat posts use PDF screenshots as cover images:
- `tools/pdf_screenshot.py` - Downloads PDFs and captures first page
- Uses `batch_download_and_screenshot()` for parallel processing
- Falls back to `storage/cover_fallback.jpg` if PDF unavailable
- WeChat cover dimensions: 900x500 pixels