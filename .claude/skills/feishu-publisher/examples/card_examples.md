# 飞书群消息卡片示例

## 示例1：单篇论文推送

### 输入
论文：Transformer-XL: Attentive Language Models Beyond a Fixed-Length Context
- 作者：Zihang Dai et al.
- 核心贡献：突破Transformer固定长度限制，实现超长文本建模
- 关键数据：在WikiText-103上perplexity降低42%
- arXiv：https://arxiv.org/abs/1901.02860
- GitHub：https://github.com/kimiyoung/transformer-xl

### 输出
```json
{
  "msg_type": "interactive",
  "card": {
    "config": {
      "wide_screen_mode": true
    },
    "header": {
      "title": {
        "tag": "plain_text",
        "content": "📚 每日论文精选"
      },
      "template": "blue"
    },
    "elements": [
      {
        "tag": "div",
        "text": {
          "tag": "lark_md",
          "content": "**🔍 论文：Transformer-XL**\n突破Transformer固定长度限制，实现超长文本建模"
        }
      },
      {
        "tag": "div",
        "text": {
          "tag": "lark_md",
          "content": "**👥 作者**\nZihang Dai et al."
        }
      },
      {
        "tag": "div",
        "text": {
          "tag": "lark_md",
          "content": "**🏷️ 标签**\n`Transformer` `Long-Context` `Language-Model`"
        }
      },
      {
        "tag": "hr"
      },
      {
        "tag": "div",
        "text": {
          "tag": "lark_md",
          "content": "**💡 核心贡献**\n• 提出片段级递归机制，突破固定长度限制\n• 引入相对位置编码，解决位置混淆问题\n• 实现超长文本的有效建模"
        }
      },
      {
        "tag": "div",
        "text": {
          "tag": "lark_md",
          "content": "**📊 关键数据**\n• WikiText-103 perplexity: 降低42%\n• 平均推理速度: 提升1800+倍\n• 支持上下文长度: 无限（理论上）"
        }
      },
      {
        "tag": "hr"
      },
      {
        "tag": "action",
        "actions": [
          {
            "tag": "button",
            "text": {
              "tag": "plain_text",
              "content": "查看论文"
            },
            "url": "https://arxiv.org/abs/1901.02860",
            "type": "primary"
          },
          {
            "tag": "button",
            "text": {
              "tag": "plain_text",
              "content": "代码"
            },
            "url": "https://github.com/kimiyoung/transformer-xl",
            "type": "default"
          }
        ]
      },
      {
        "tag": "div",
        "text": {
          "tag": "lark_md",
          "content": "💭 **今日思考**：Transformer-XL的思想如何应用到Agent的记忆系统中？"
        }
      }
    ]
  }
}
```

---

## 示例2：合集推送

### 输入
今日5篇论文：
1. AutoGen - 微软多Agent框架
2. LangGraph - LangChain Agent构建工具
3. CrewAI - 角色扮演多Agent系统
4. MetaGPT - 软件开发多Agent
5. AutoAgents - 自主Agent框架

### 输出
```json
{
  "msg_type": "interactive",
  "card": {
    "config": {
      "wide_screen_mode": true
    },
    "header": {
      "title": {
        "tag": "plain_text",
        "content": "📚 每日AI Agent论文精选"
      },
      "template": "blue"
    },
    "elements": [
      {
        "tag": "div",
        "text": {
          "tag": "lark_md",
          "content": "**📅 日期：2024-01-15**\n**📊 今日精选：5篇论文**\n\n今日主题：多Agent系统与协作框架"
        }
      },
      {
        "tag": "hr"
      },
      {
        "tag": "div",
        "text": {
          "tag": "lark_md",
          "content": "**1️⃣ AutoGen**\n微软开源的多Agent对话框架\n创新点：支持人机协作、自定义Agent\n🔗 arxiv.org/abs/2308.08155"
        }
      },
      {
        "tag": "div",
        "text": {
          "tag": "lark_md",
          "content": "**2️⃣ LangGraph**\nLangChain官方Agent构建工具\n创新点：状态机+图结构流程\n🔗 github.com/langchain-ai/langgraph"
        }
      },
      {
        "tag": "div",
        "text": {
          "tag": "lark_md",
          "content": "**3️⃣ CrewAI**\n角色扮演风格的多Agent框架\n创新点：团队角色分工、任务协作\n🔗 github.com/joaomdmoura/crewAI"
        }
      },
      {
        "tag": "div",
        "text": {
          "tag": "lark_md",
          "content": "**4️⃣ MetaGPT**\n软件公司式的多Agent系统\n创新点：SOP流程、角色专业化\n🔗 github.com/geekan/MetaGPT"
        }
      },
      {
        "tag": "div",
        "text": {
          "tag": "lark_md",
          "content": "**5️⃣ AutoAgents**\n动态生成Agent的系统\n创新点：Agent自动生成与优化\n🔗 github.com/Link-AGI/AutoAgents"
        }
      },
      {
        "tag": "hr"
      },
      {
        "tag": "div",
        "text": {
          "tag": "lark_md",
          "content": "**💡 今日洞察**\n多Agent框架正在从\"实验\"走向\"工程化\"，企业级应用可期。"
        }
      },
      {
        "tag": "div",
        "text": {
          "tag": "lark_md",
          "content": "**💬 讨论话题**\n哪个框架更适合我们的业务场景？欢迎留言讨论～"
        }
      }
    ]
  }
}
```

---

## 示例3：高优先级论文推送

### 输入
论文：GPT-4 Technical Report
- 重要程度：极高（OpenAI官方）
- 核心贡献：多模态大模型技术报告
- 引用预期：将成为经典

### 输出
```json
{
  "msg_type": "interactive",
  "card": {
    "config": {
      "wide_screen_mode": true
    },
    "header": {
      "title": {
        "tag": "plain_text",
        "content": "🔥 重磅论文"
      },
      "template": "red"
    },
    "elements": [
      {
        "tag": "div",
        "text": {
          "tag": "lark_md",
          "content": "**🚨 重要性：极高**\n建议全员阅读！"
        }
      },
      {
        "tag": "hr"
      },
      {
        "tag": "div",
        "text": {
          "tag": "lark_md",
          "content": "**📄 GPT-4 Technical Report**\nOpenAI官方技术报告"
        }
      },
      {
        "tag": "div",
        "text": {
          "tag": "lark_md",
          "content": "**💡 核心亮点**\n• 多模态能力：文本+图像输入\n• 模型规模：参数量未公开，但性能惊人\n• 安全性：6个月的红队测试\n• 推理能力：Bar Exam前10%水平"
        }
      },
      {
        "tag": "div",
        "text": {
          "tag": "lark_md",
          "content": "**📊 关键数据**\n• MMLU: 86.4%（人类水平87%）\n• HumanEval: 67%（SOTA）\n• 多语言能力：覆盖26种语言"
        }
      },
      {
        "tag": "hr"
      },
      {
        "tag": "action",
        "actions": [
          {
            "tag": "button",
            "text": {
              "tag": "plain_text",
              "content": "查看论文"
            },
            "url": "https://arxiv.org/abs/2303.08774",
            "type": "primary"
          }
        ]
      },
      {
        "tag": "note",
        "elements": [
          {
            "tag": "plain_text",
            "content": "预计阅读时间：30分钟 | 建议收藏后阅读"
          }
        ]
      }
    ]
  }
}
```

---

## 卡片设计要点

1. **信息优先**：重要信息放前面
2. **视觉层次**：用分割线区分区域
3. **行动引导**：按钮要明确（查看论文、代码）
4. **互动促进**：结尾提问或讨论话题
5. **简洁有力**：每篇论文描述控制在100字内