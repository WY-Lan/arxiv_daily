---
name: feishu-publisher
description: 飞书群消息发布技能。当需要将AI Agent论文推送到飞书群时自动激活。生成卡片式消息，支持交互按钮和快速阅读。
argument-hint: [single|collection] [paper_count]
user-invocable: true
---

# 飞书发布技能

将AI Agent论文转化为飞书群消息卡片，简洁高效，便于团队讨论和协作。

## 发布模式

### 模式一：单篇发布 (single)

适用于重点论文的推送通知。

**输出格式**：
```json
{
  "card_title": "卡片标题",
  "card_header": {
    "title": "论文标题",
    "subtitle": "作者、机构信息"
  },
  "elements": [
    {"type": "markdown", "content": "内容块"},
    {"type": "divider"},
    {"type": "action", "actions": [...]}
  ],
  "summary_text": "消息预览摘要"
}
```

### 模式二：合集发布 (collection)

适用于每日多篇论文的汇总推送。

**输出格式**：
```json
{
  "card_title": "每日 AI Agent 论文精选",
  "card_header": {
    "title": "今日精选 N 篇论文",
    "subtitle": "日期：2024-01-15"
  },
  "elements": [
    {"type": "markdown", "content": "开场白"},
    {"type": "divider"},
    {"type": "markdown", "content": "论文1简介"},
    {"type": "action", "actions": [...]},
    ...
  ],
  "summary_text": "简短摘要"
}
```

## 卡片结构设计

### 消息区域
1. **标题区**：日期 + 论文数量
2. **概览区**：一句话总结今日主题
3. **论文区**：每篇包含标题、作者、贡献、链接
4. **结尾区**：讨论引导或互动提示

### 单篇论文卡片
```
📚 【每日精选】AI Agent论文推送

🔍 论文：[标题]
👥 作者：[作者列表]
🏷️ 标签：Agent | Planning | LLM

💡 核心贡献：
• 贡献点1
• 贡献点2
• 贡献点3

📊 关键数据：
• 指标1: 数值
• 指标2: 数值

🔗 链接：
[论文] [代码] [解读]

💭 今日思考：[引发讨论的问题]
```

## 写作风格指南

### 信息优先
- 先说结论
- 再展细节
- 最后行动

### 视觉清晰
- 使用 emoji 分类
- 列表要点化
- 重要内容高亮

### 促进讨论
- 提出开放问题
- 设置讨论引导
- 关联团队项目

## 飞书卡片元素

### 支持的元素类型
| 类型 | 说明 | 使用场景 |
|------|------|----------|
| `markdown` | Markdown内容块 | 正文、列表 |
| `divider` | 分割线 | 区域分隔 |
| `action` | 操作按钮 | 链接跳转 |
| `header` | 标题头 | 卡片顶部 |

### 按钮配置
```json
{
  "type": "action",
  "actions": [
    {"text": "查看论文", "url": "arxiv链接"},
    {"text": "代码", "url": "github链接"}
  ]
}
```

## 技术集成

### Webhook推送
- 使用自定义机器人 Webhook
- 支持消息卡片格式
- 支持 interactive 消息类型

### 消息类型
```json
{
  "msg_type": "interactive",
  "card": {
    "config": {"wide_screen_mode": true},
    "header": {...},
    "elements": [...]
  }
}
```

## 注意事项

- 标题控制在 50 字以内
- 每篇论文描述控制在 100 字以内
- 没有代码链接时只显示"查看论文"按钮
- 使用中文输出
- 分割线使用 `"tag": "hr"`

## 示例

查看 `./examples/` 目录获取完整示例。