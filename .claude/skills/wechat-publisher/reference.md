# 微信公众号发布参考文档

## 平台特性

### 用户画像
- 年龄：25-45岁为主
- 职业：职场人士、技术人员
- 阅读场景：通勤、午休、睡前
- 阅读深度：愿意深度阅读

### 内容偏好
- 专业深度：技术文章要求准确
- 逻辑清晰：结构化的内容更受欢迎
- 实用价值：能解决实际问题
- 原创性：优质原创内容有流量扶持

## 文章结构设计

### 标题设计
```
专业型：让AI学会思考：Chain-of-Thought技术详解
问题型：大模型推理能力差？思维链来帮忙
数字型：5篇Agent论文：从入门到精通
对比型：ReAct vs CoT：推理增强技术对比
```

### 摘要规范
```
✅ 100字以内
✅ 包含核心观点
✅ 吸引点击
✅ 使用关键词

示例：
思维链提示技术详解：通过中间推理步骤，让大模型在数学、常识推理等任务上实现质的飞跃。
```

### 目录设计
```
## 一、引言
## 二、背景知识
## 三、核心方法
  ### 3.1 方法概述
  ### 3.2 关键技术
  ### 3.3 创新点分析
## 四、实验结果
## 五、应用场景
## 六、总结与展望
```

## 排版规范

### 标题层级
```markdown
# 一级标题（文章标题）
## 二级标题（章节）
### 三级标题（小节）
#### 四级标题（要点）
```

### 段落规范
```
- 段落间空一行
- 每段不超过150字
- 开头不缩进
- 使用短句为主
```

### 强调方式
```markdown
**加粗**：重要概念
`代码`：术语、变量名
> 引用：名言、定义
- 列表：要点列举
```

### 代码块
````markdown
```python
def attention(query, key, value):
    scores = torch.matmul(query, key.transpose(-2, -1))
    weights = torch.softmax(scores, dim=-1)
    return torch.matmul(weights, value)
```
````

### 表格格式
```markdown
| 方法 | 准确率 | F1分数 |
|------|--------|--------|
| Baseline | 75.2% | 0.72 |
| Ours | 89.3% | 0.87 |
```

## 配图建议

### 封面图
- 尺寸：900×383px（2.35:1）
- 格式：JPG/PNG
- 内容：与文章主题相关
- 避免文字过多

### 文中配图
| 位置 | 类型 | 说明 |
|------|------|------|
| 开头 | 概念图 | 帮助理解主题 |
| 方法部分 | 流程图/架构图 | 展示方法原理 |
| 实验部分 | 结果图/对比图 | 数据可视化 |
| 结尾 | 总结图 | 概括核心要点 |

## API集成

### 获取Access Token
```python
import requests

def get_access_token(app_id, app_secret):
    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={app_id}&secret={app_secret}"
    response = requests.get(url)
    return response.json()['access_token']
```

### 创建草稿
```python
def create_draft(access_token, articles):
    url = f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={access_token}"
    data = {
        "articles": articles
    }
    response = requests.post(url, json=data)
    return response.json()
```

### 文章数据结构
```python
article = {
    "title": "文章标题",
    "author": "作者",
    "digest": "摘要",
    "content": "正文HTML",
    "thumb_media_id": "封面图片media_id",
    "need_open_comment": 1,
    "only_fans_can_comment": 0
}
```

## 发布时间建议

| 时间段 | 效果 | 适合内容 |
|--------|------|----------|
| 7:00-8:30 | 较好 | 轻量资讯、早报 |
| 12:00-13:00 | 一般 | 午休阅读 |
| 18:00-20:00 | 最佳 | 深度文章 |
| 21:00-22:00 | 较好 | 技术文章 |

## 注意事项

### 内容审核
- 避免敏感话题
- 数据引用需标注来源
- 图片确保版权合规

### 排版技巧
- 段落不宜过长
- 适当使用分隔线
- 重点内容高亮
- 图文比例适当

### 互动引导
- 文末设置讨论话题
- 引导关注公众号
- 提供联系方式或群二维码