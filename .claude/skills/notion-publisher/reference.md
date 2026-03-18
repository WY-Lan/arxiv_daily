# Notion数据库发布参考文档

## Notion API基础

### 认证方式
- 使用Integration Token
- 需要在Notion中授权数据库访问
- Token以`ntn_`或`secret_`开头

### API基础URL
```
https://api.notion.com/v1
```

### 请求头
```python
headers = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}
```

## 数据库Schema设计

### 属性类型映射

| Notion类型 | API格式 | 说明 |
|------------|---------|------|
| Title | `{"title": [...]}` | 必须有一个 |
| Rich Text | `{"rich_text": [...]}` | 长文本 |
| Number | `{"number": 85}` | 数字 |
| Select | `{"select": {"name": "选项"}}` | 单选 |
| Multi-select | `{"multi_select": [...]}` | 多选 |
| Date | `{"date": {"start": "2024-01-15"}}` | 日期 |
| URL | `{"url": "https://..."}` | 链接 |
| Status | `{"status": {"name": "未读"}}` | 状态 |
| People | `{"people": [...]}` | 人员 |
| Checkbox | `{"checkbox": true}` | 复选框 |

### 推荐数据库属性

```python
DATABASE_SCHEMA = {
    "论文标题": {"type": "title"},
    "摘要": {"type": "rich_text"},
    "作者": {"type": "multi_select"},
    "发布日期": {"type": "date"},
    "arXiv链接": {"type": "url"},
    "代码链接": {"type": "url"},
    "标签": {"type": "multi_select"},
    "评分": {"type": "number", "number": {"format": "number"}},
    "阅读状态": {
        "type": "status",
        "status": {"options": [
            {"name": "未读", "color": "gray"},
            {"name": "在读", "color": "blue"},
            {"name": "已读", "color": "green"}
        ]}
    },
    "推送日期": {"type": "date"},
    "核心贡献": {"type": "rich_text"},
    "创新点": {"type": "rich_text"},
    "应用场景": {"type": "rich_text"},
    "引用数": {"type": "number"}
}
```

## MCP工具使用

### 获取数据库信息
```python
result = await mcp__notion__notion_fetch(
    id="8660dd41cc5947dfbe2a702ea54cad84"
)
# 返回数据库schema和data_source_id
```

### 创建页面
```python
result = await mcp__notion__notion_create_pages(
    parent={"database_id": "xxx"},
    pages=[{
        "properties": {
            "论文标题": {"title": [{"text": {"content": "标题"}}]},
            "评分": {"number": 85},
            ...
        },
        "content": "页面正文内容"
    }]
)
```

### 搜索论文
```python
result = await mcp__notion__notion_search(
    query="Transformer",
    query_type="internal"
)
# 搜索是否已存在相同论文，用于去重
```

### 更新页面
```python
result = await mcp__notion__notion_update_page(
    page_id="页面ID",
    command="update_properties",
    properties={
        "阅读状态": {"status": {"name": "已读"}}
    }
)
```

## 页面内容格式

### Markdown支持
```markdown
## 一级标题
### 二级标题

**粗体** *斜体* ~~删除线~~

- 无序列表项1
- 无序列表项2

1. 有序列表项1
2. 有序列表项2

> 引用文本

`行内代码`

​```python
代码块
​```

[链接文字](URL)

| 表头 | 表头 |
|------|------|
| 内容 | 内容 |
```

### 特殊块类型

#### Callout（提示框）
```markdown
> 💡 这是一条重要提示
```

#### Toggle（折叠块）
```markdown
<details>
<summary>点击展开</summary>

隐藏的内容

</details>
```

#### 分割线
```markdown
---
```

## 视图配置

### 创建视图
```python
result = await mcp__notion__notion_create_view(
    database_id="xxx",
    data_source_id="collection://xxx",
    name="高评分论文",
    type="table",
    configure="FILTER \"评分\" >= 80; SORT BY \"评分\" DESC"
)
```

### 视图配置DSL
```
# 筛选
FILTER "评分" >= 80
FILTER "阅读状态" = "未读"

# 排序
SORT BY "发布日期" DESC
SORT BY "评分" DESC

# 分组
GROUP BY "标签"

# 显示属性
SHOW "论文标题", "评分", "阅读状态"

# 日历视图配置
CALENDAR BY "发布日期"

# 时间线视图配置
TIMELINE BY "开始日期" TO "结束日期"
```

## 去重逻辑

### 检查论文是否已存在
```python
async def check_duplicate(arxiv_url: str) -> bool:
    # 1. 搜索数据库
    results = await mcp__notion__notion_search(
        query=arxiv_url,
        query_type="internal",
        data_source_url=f"collection://{DATABASE_ID}"
    )

    # 2. 检查结果
    if results and len(results) > 0:
        return True  # 已存在
    return False  # 不存在
```

### 批量去重
```python
async def filter_duplicates(papers: list) -> list:
    unique_papers = []
    for paper in papers:
        if not await check_duplicate(paper['arxiv_url']):
            unique_papers.append(paper)
    return unique_papers
```

## 错误处理

### 常见错误码

| 错误码 | 说明 | 解决方案 |
|--------|------|----------|
| 400 | 请求格式错误 | 检查JSON格式 |
| 401 | 未授权 | 检查Token有效性 |
| 404 | 资源不存在 | 检查数据库ID |
| 409 | 冲突（重复） | 检查是否已创建 |

### 错误处理示例
```python
async def create_page_safe(page_data):
    try:
        result = await mcp__notion__notion_create_pages(**page_data)
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

## 性能优化

### 批量创建
- 使用`pages`数组一次创建多页
- 单次最多100页

### 并发处理
```python
import asyncio

async def batch_create(pages, batch_size=10):
    results = []
    for i in range(0, len(pages), batch_size):
        batch = pages[i:i+batch_size]
        result = await mcp__notion__notion_create_pages(pages=batch, ...)
        results.extend(result)
    return results
```

### 缓存Schema
```python
# 缓存数据库Schema避免重复请求
_schema_cache = {}

async def get_schema_cached(database_id):
    if database_id not in _schema_cache:
        result = await mcp__notion__notion_fetch(id=database_id)
        _schema_cache[database_id] = result['schema']
    return _schema_cache[database_id]
```