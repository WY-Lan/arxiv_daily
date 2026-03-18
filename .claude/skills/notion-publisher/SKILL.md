---
name: notion-publisher
description: Notion数据库发布技能。当需要将AI Agent论文推送到Notion数据库时自动激活。支持结构化存储论文信息，便于后续检索和管理。
argument-hint: [single|batch] [paper_count]
user-invocable: true
---

# Notion发布技能

将AI Agent论文信息推送到Notion数据库，实现结构化存储和管理。

## 发布模式

### 模式一：单篇发布 (single)

将单篇论文信息写入Notion数据库。

**属性映射**：
```
论文标题 → Title 属性
摘要 → Rich Text 属性
作者 → Multi-select 或 Rich Text
发布日期 → Date 属性
arXiv链接 → URL 属性
GitHub链接 → URL 属性
标签 → Multi-select 属性
评分 → Number 属性
状态 → Status 属性
```

### 模式二：批量发布 (batch)

将多篇论文批量写入数据库。

**流程**：
1. 检查数据库Schema
2. 批量创建页面
3. 更新索引和统计

## 数据库Schema设计

### 推荐属性配置

| 属性名 | 类型 | 说明 |
|--------|------|------|
| 论文标题 | Title | 主标题 |
| 摘要 | Rich Text | 论文摘要 |
| 作者 | Multi-select | 作者列表 |
| 发布日期 | Date | arXiv发布日期 |
| arXiv链接 | URL | 论文原文链接 |
| 代码链接 | URL | GitHub仓库 |
| 标签 | Multi-select | 分类标签 |
| 评分 | Number | 综合评分(0-100) |
| 阅读状态 | Status | 未读/在读/已读 |
| 推送日期 | Date | 推送到Notion的日期 |
| 核心贡献 | Rich Text | 简要贡献说明 |
| 创新点 | Rich Text | 主要创新点 |
| 应用场景 | Rich Text | 潜在应用 |
| 引用数 | Number | 引用计数 |

## 写入格式

### 页面创建请求

```json
{
  "parent": {"database_id": "数据库ID"},
  "properties": {
    "论文标题": {"title": [{"text": {"content": "标题"}}]},
    "摘要": {"rich_text": [{"text": {"content": "摘要内容"}}]},
    "作者": {"multi_select": [{"name": "作者1"}, {"name": "作者2"}]},
    "发布日期": {"date": {"start": "2024-01-15"}},
    "arXiv链接": {"url": "https://arxiv.org/abs/..."},
    "代码链接": {"url": "https://github.com/..."},
    "标签": {"multi_select": [{"name": "Agent"}, {"name": "LLM"}]},
    "评分": {"number": 85},
    "阅读状态": {"status": {"name": "未读"}}
  }
}
```

## 内容组织

### 页面内容结构

```
# 论文标题

## 核心贡献
[贡献描述]

## 创新点
- 创新点1
- 创新点2
- 创新点3

## 方法概述
[方法描述]

## 实验结果
[关键数据和结果]

## 应用场景
[潜在应用]

## 相关论文
[相关论文链接]

## 参考资料
- arXiv链接
- GitHub仓库
- 项目主页
```

## 技术集成

### MCP工具
- `mcp__notion__notion-fetch` - 获取数据库信息
- `mcp__notion__notion-create-pages` - 创建页面
- `mcp__notion__notion-update-page` - 更新页面
- `mcp__notion__notion-search` - 搜索论文

### API配置
- `NOTION_API_KEY`: Integration Token
- `NOTION_DATABASE_ID`: 目标数据库ID

## 视图配置

### 推荐视图

1. **全部论文** (Table)
   - 按发布日期降序
   - 显示标题、作者、评分、状态

2. **高评分论文** (Table + Filter)
   - 筛选评分 >= 80
   - 按评分降序

3. **待阅读** (Table + Filter)
   - 筛选阅读状态 = 未读
   - 按评分降序

4. **分类视图** (Board)
   - 按标签分组
   - 显示各领域分布

## 自动化流程

1. **去重检查**：搜索是否已存在相同论文
2. **属性填充**：自动填充论文信息
3. **标签提取**：从内容中提取关键词作为标签
4. **评分计算**：基于多维评分结果

## 示例

查看 `./examples/` 目录获取完整示例。