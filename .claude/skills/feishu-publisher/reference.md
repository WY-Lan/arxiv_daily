# 飞书群消息卡片参考文档

## 平台特性

### 使用场景
- 团队内部通知
- 工作信息同步
- 知识分享传播

### 消息特点
- 即时触达
- 格式美观
- 支持交互
- 可追溯查阅

## 卡片元素详解

### Header（标题头）
```json
{
  "tag": "header",
  "template": "blue",
  "title": {
    "tag": "plain_text",
    "content": "📚 每日论文精选"
  }
}
```

支持的模板颜色：
- `blue`：默认，信息类
- `red`：重要，警告类
- `green`：成功，完成类
- `yellow`：提醒，注意类
- `purple`：特殊标记

### Div（文本块）
```json
{
  "tag": "div",
  "text": {
    "tag": "lark_md",
    "content": "**标题**\n内容描述"
  }
}
```

支持Markdown格式：
- `**粗体**`
- `*斜体*`
- `~~删除线~~`
- `[链接](url)`
- `` `代码` ``
- `> 引用`

### Hr（分割线）
```json
{
  "tag": "hr"
}
```

注意：使用`"tag": "hr"`，不是`"tag": "divider"`

### Action（操作按钮）
```json
{
  "tag": "action",
  "actions": [
    {
      "tag": "button",
      "text": {
        "tag": "plain_text",
        "content": "查看论文"
      },
      "url": "https://arxiv.org/abs/xxx",
      "type": "primary"
    },
    {
      "tag": "button",
      "text": {
        "tag": "plain_text",
        "content": "代码"
      },
      "url": "https://github.com/xxx",
      "type": "default"
    }
  ]
}
```

按钮类型：
- `primary`：主要按钮（蓝色）
- `default`：默认按钮（灰色）
- `danger`：危险按钮（红色）

### Note（备注）
```json
{
  "tag": "note",
  "elements": [
    {
      "tag": "plain_text",
      "content": "预计阅读时间：10分钟"
    }
  ]
}
```

## 卡片模板

### 模板1：论文推送卡片
```json
{
  "msg_type": "interactive",
  "card": {
    "config": {
      "wide_screen_mode": true
    },
    "header": {
      "title": {"tag": "plain_text", "content": "📚 每日论文精选"},
      "template": "blue"
    },
    "elements": [
      {"tag": "div", "text": {"tag": "lark_md", "content": "**论文信息**"}},
      {"tag": "hr"},
      {"tag": "div", "text": {"tag": "lark_md", "content": "**核心贡献**"}},
      {"tag": "hr"},
      {"tag": "action", "actions": [...]}
    ]
  }
}
```

### 模板2：重要通知卡片
```json
{
  "msg_type": "interactive",
  "card": {
    "config": {"wide_screen_mode": true},
    "header": {
      "title": {"tag": "plain_text", "content": "🔥 重要通知"},
      "template": "red"
    },
    "elements": [...]
  }
}
```

### 模板3：合集卡片
```json
{
  "msg_type": "interactive",
  "card": {
    "config": {"wide_screen_mode": true},
    "header": {
      "title": {"tag": "plain_text", "content": "📚 今日N篇论文"},
      "template": "blue"
    },
    "elements": [
      {"tag": "div", "text": {"tag": "lark_md", "content": "概览信息"}},
      {"tag": "hr"},
      {"tag": "div", "text": {"tag": "lark_md", "content": "论文1"}},
      {"tag": "div", "text": {"tag": "lark_md", "content": "论文2"}},
      ...
    ]
  }
}
```

## Webhook推送

### 发送消息
```python
import requests
import json

def send_feishu_card(webhook_url, card_content):
    headers = {"Content-Type": "application/json"}
    data = {
        "msg_type": "interactive",
        "card": card_content
    }
    response = requests.post(webhook_url, headers=headers, data=json.dumps(data))
    return response.json()
```

### 响应处理
```json
// 成功响应
{
  "code": 0,
  "msg": "success"
}

// 失败响应
{
  "code": 10001,
  "msg": "invalid card content"
}
```

## 设计原则

### 信息层次
1. 标题：一目了然
2. 摘要：核心信息
3. 详情：展开说明
4. 行动：明确按钮

### 视觉设计
- 合理使用颜色区分
- 分割线划分区域
- 保持简洁不冗余
- 重要信息突出显示

### 交互设计
- 按钮数量：1-3个为宜
- 按钮文字：明确操作含义
- 链接有效：确保URL正确
- 无代码链接时只显示"查看论文"按钮

## 常见问题

### Q: 卡片发送失败？
A: 检查JSON格式、字段名称、URL有效性

### Q: 如何添加图片？
A: 使用img标签，需要先上传获取图片key

### Q: 按钮跳转不生效？
A: 确保URL完整（包含https://）