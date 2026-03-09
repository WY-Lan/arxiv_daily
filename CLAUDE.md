# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Arxiv Daily Push is a multi-agent system for daily AI Agent paper recommendations. It fetches papers from arxiv, evaluates them using a 4-dimensional scoring system, and publishes curated content to multiple platforms (Notion, Feishu, Xiaohongshu, WeChat Official Account).

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
# Test Feishu webhook
python tools/test_feishu.py --webhook <webhook_url>

# Test Notion publishing
python tools/test_notion.py

# Test WeChat publishing
python tools/test_wechat_final.py
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
| `FeishuPublisherAgent` | Feishu | Webhook-based (`tools/feishu_webhook.py`) |
| `XHSPublisherAgent` | Xiaohongshu | Uses xiaohongshu-mcp, creates collection posts |
| `WeChatMPPublisherAgent` | WeChat MP | Draft creation via API |

Publishers use **collection mode** - aggregating all papers into one post rather than publishing individually.

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
  - `xhs_collection.txt`, `feishu_collection.txt` - Platform-specific formats

### Database

- SQLite with async SQLAlchemy (`storage/database.py`)
- Tables: `papers`, `publish_records`, `agent_executions`, `mcp_server_configs`, `skill_configs`
- Use the global `db` instance for all database operations

## Important Patterns

- All async operations use `asyncio`
- Database operations go through the global `db` instance from `storage/database.py`
- Prompt templates are loaded via `from config.prompts import load_prompt`
- LLM calls use `llm_client.generate_json()` for structured output
- Feishu cards use `"tag": "hr"` for dividers (not `"divider"`)

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
- `FEISHU_WEBHOOK_URL` - For Feishu publishing
- `NOTION_API_KEY`, `NOTION_DATABASE_ID` - For Notion publishing
- `WECHAT_APP_ID`, `WECHAT_APP_SECRET` - For WeChat MP

## PDF Cover Generation

XHS posts use PDF screenshots as cover images:
- `tools/pdf_screenshot.py` - Downloads PDFs and captures first page
- Uses `batch_download_and_screenshot()` for parallel processing
- Falls back to `storage/cover_fallback.jpg` if PDF unavailable