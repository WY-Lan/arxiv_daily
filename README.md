# Arxiv Daily Push - AI Agent 论文每日推送系统

基于多智能体的 arxiv 每日推送系统，专注于 AI Agent 方向的论文推荐。

## ✨ 特性

- 🤖 **多智能体架构**: 使用 Claude Agent SDK 构建平台专家模式
- 📊 **四维评估体系**: 引用数 + 作者影响力 + AI质量评估 + 社区热度
- 🎯 **精准筛选**: 每日精选 Top 5 高质量论文
- 📱 **多平台发布**: 支持 Notion、飞书、小红书、微信公众号
- 🔧 **MCP/Skills 支持**: 可扩展的 MCP 服务器和 Skills 配置
- 🔄 **混合调度**: 定时获取 + 审核后自动发布

## 🚀 快速开始

### 1. 安装依赖

```bash
cd arxiv_daily
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填入您的 API Keys
```

**必需配置:**
- `BAILIAN_API_KEY`: 阿里百炼 API Key

**可选配置:**
- `NOTION_API_KEY`: Notion API Key
- `FEISHU_APP_ID/SECRET`: 飞书应用凭证
- `WECHAT_APP_ID/SECRET`: 微信公众号凭证

### 3. 运行

```bash
# 运行一次完整流程
python main.py run

# 启动定时调度
python main.py schedule

# 仅获取论文
python main.py fetch

# 查看配置
python main.py config
```

### 4. 单篇论文发布

支持将指定的单篇论文发布到小红书平台：

```bash
# 发布单篇论文到小红书（指定 arxiv_id）
python main.py xhs --arxiv-id 2603.28052

# 批量发布（5+1模式：5篇详细 + 1篇汇总）
python main.py xhs
```

论文获取优先级：本地数据库 → selected_papers.json → arxiv API

## 📁 项目结构

```
arxiv_daily/
├── agents/                 # 智能体模块
│   ├── base.py            # Agent 基类和注册系统
│   ├── paper_fetcher.py   # 论文获取和筛选 Agent
│   └── publishers/        # 平台发布 Agent
│       └── __init__.py    # Notion/飞书/小红书/公众号
├── tools/                  # 工具模块
│   ├── arxiv_api.py       # arxiv API 客户端
│   ├── semantic_scholar.py # 引用数据
│   ├── openalex.py        # 作者影响力数据
│   ├── papers_with_code.py # 社区热度数据
│   └── llm_client.py      # LLM 客户端（阿里百炼）
├── config/                 # 配置模块
│   ├── settings.py        # 配置管理
│   └── prompts/           # 提示词模板
├── storage/               # 存储模块
│   └── database.py        # SQLite 数据库
├── scheduler/             # 调度模块
│   └── jobs.py            # 定时任务
├── main.py                # 主入口
└── requirements.txt       # 依赖列表
```

## 🤖 Agent 架构

系统采用**平台专家模式**，每个 Agent 专注于特定任务：

```
Orchestrator Agent (编排调度)
    │
    ├── Paper Fetcher Agent (论文获取)
    │       └── 从 arxiv 获取 AI Agent 相关论文
    │
    ├── Selection Agent (论文筛选)
    │       └── 四维评估选出 Top N
    │
    ├── Summary Agent (内容生成)
    │       └── 生成结构化摘要
    │
    └── Publisher Agents (平台发布)
            ├── Notion Agent
            ├── Feishu Agent
            ├── XHS Agent
            └── WeChat MP Agent
```

## 📊 四维评估体系

| 维度 | 权重 | 数据来源 |
|------|------|----------|
| 引用数量 | 25% | Semantic Scholar API |
| 作者影响力 | 25% | OpenAlex API |
| 内容质量 | 30% | LLM 评估 (qwen-max) |
| 社区热度 | 20% | Papers with Code |

## 🔌 MCP/Skills 扩展

系统支持配置 MCP 服务器和 Skills：

### 配置 MCP Server

在数据库中添加配置：

```python
from storage.database import db, MCPServerConfig

await db.save_mcp_server({
    "name": "custom_tool",
    "server_type": "stdio",
    "command": "python",
    "args": '["path/to/server.py"]',
    "is_enabled": True
})
```

### 配置 Skill

```python
from storage.database import db, SkillConfig

await db.save_skill({
    "name": "custom_skill",
    "skill_type": "custom",
    "description": "自定义技能",
    "config": '{"param": "value"}',
    "is_enabled": True
})
```

## 📱 平台适配策略

### 小红书
- 标题：20字内 + emoji
- 正文：300-500字，轻松口语化
- 配图：AI 生成封面

### Notion
- 结构化数据库条目
- 完整元数据 + Markdown 总结
- 长期归档和检索

### 飞书
- 富文本卡片消息
- 即时通知团队
- 支持多人@提醒

### 微信公众号
- 深度解读文章（2000-3000字）
- Markdown 转富文本排版
- 支持定时发布

## 🔧 阿里百炼模型配置

推荐使用以下模型：

| Agent | 推荐模型 | 说明 |
|-------|---------|------|
| 论文筛选 | qwen-max | 需要深度分析 |
| 内容生成 | qwen-max | 高质量输出 |
| 平台发布 | qwen-plus | 平衡性能和速度 |

## 📝 开发计划

- [x] 项目基础架构
- [x] arxiv API 集成
- [x] 论文获取 Agent
- [x] 四维评估筛选
- [x] 内容生成 Agent
- [x] MCP/Skills 支持
- [x] Notion MCP 集成
- [x] 飞书 API 集成 (Webhook)
- [x] 小红书 MCP 集成
- [x] 微信公众号 API
- [x] 单篇论文发布（指定 arxiv_id）
- [ ] 审核流程 UI

## 📄 License

MIT License