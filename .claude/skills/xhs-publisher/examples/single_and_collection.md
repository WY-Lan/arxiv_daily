# 小红书发布示例

## 示例1：单篇发布 (single) - 学术化风格

### 输入
论文信息：
- 标题：MemDLM: Memory-Enhanced Diffusion Language Model Training
- 作者：香港中文大学、华为团队
- arXiv ID：2503.xxxxx
- 摘要：扩散语言模型(DLM)相比自回归模型具有优势，但存在训练-推理不一致问题。本文提出MemDLM，通过双层优化...

### 输出
```json
{
  "title": "港中文&华为推出「记忆增强」扩散语言模型🔥",
  "content": "相比自回归（AR）模型，扩散语言模型（DLM）在全注意力并行解码和灵活生成方式等方面具有明显优势。\n\n然而，DLM 存在明显的训练-推理不一致问题：在训练时采用静态的单步掩码预测目标，但在部署时却通过多步渐进式去噪轨迹运行。💡\n\n在这项工作中，香港中文大学、华为团队提出了 MemDLM（记忆增强扩散语言模型），通过双层优化将模拟去噪过程嵌入训练中，从而缩小这一差距。🎯\n\n其中，内层循环更新一组快速权重，形成参数化记忆，捕捉每个样本的局部轨迹经验；外层循环则以该记忆为条件更新基础模型。\n\n通过将记忆压力从 token 表示转移至参数，MemDLM 实现了更快的收敛速度和更低的训练损失。⚡️\n\npaper：MemDLM: Memory-Enhanced DLM Training",
  "tags": ["#AI论文", "#扩散模型", "#语言模型", "#华为", "#港中文", "#论文分享"]
}
```

---

## 示例2：合集发布 (collection)

### 输入
今日5篇论文：
1. MemDLM - 记忆增强扩散语言模型
2. AgentVerse - 多Agent协作框架
3. CADSmith - 多Agent CAD生成
4. MetaGPT - 软件开发多Agent
5. ChatDev - 对话式开发Agent

### 输出
```json
{
  "title": "今日5篇Agent论文精选📚",
  "content": "今天的Agent论文来啦！5篇高质量论文，建议收藏👇\n\n1️⃣ 港中文&华为推出「记忆增强」扩散语言模型\nMemDLM通过双层优化解决DLM训练-推理不一致问题\n\n2️⃣ AgentVerse\n多Agent协作框架，支持任务分解和角色分配\n创新点：动态角色匹配机制\n\n3️⃣ CADSmith\n多Agent CAD生成，带几何验证\n创新点：程序化验证闭环\n\n4️⃣ MetaGPT\n让Agent团队像软件公司一样工作\n创新点：软件工程流程融入\n\n5️⃣ ChatDev\n通过对话开发软件的Agent团队\n创新点：自然语言驱动开发\n\n💡 今日洞察\n多Agent协作和记忆机制成为主流方向！\n\n需要论文链接的评论区留言～\n\n#AI论文 #Agent #大模型 #论文分享 #学术",
  "tags": ["AI论文", "Agent", "大模型", "论文分享", "学术"]
}
```

---

## 示例3：高影响力论文发布

### 输入
论文：ReAct: Synergizing Reasoning and Acting in Language Models
- 引用数：5000+
- GitHub Stars：12000+
- 标签：Reasoning, Agent, LLM

### 输出
```json
{
  "title": "ReAct🔥推理+行动的开山之作",
  "content": "这篇论文太经典了！引用5000+，GitHub星标12k+\n\n📖 论文：ReAct\nReasoning + Acting = 更聪明的AI\n\n🔑 为什么重要？\n传统LLM只会\"想\"不会\"做\"\nReAct让模型边思考边行动\n\n💡 核心思想\n• 推理(Reasoning)：生成思考过程\n• 行动(Acting)：执行具体操作\n• 交替进行，相互增强\n\n📊 效果如何？\n在HotpotQA等任务上，准确率提升10-30%！\n\n这也是现在Agent系统的基石思想，CoT、ToT都是在此基础上的发展。\n\n#AI论文 #Agent #大模型 #推理 #论文分享",
  "tags": ["AI论文", "Agent", "大模型", "推理", "论文分享", "经典论文"]
}
```

---

## 注意事项

1. **标题控制在20字以内**（不含emoji）
2. **正文400-800字为宜**
3. **使用emoji**（标题1-2个，正文可以多几个突出重点）
4. **标签5-8个**
5. **单篇发布不需要互动引导**，保持学术化风格
6. **合集发布可以适当引导互动**