# 论文筛选机制升级说明

## 概述

本次升级对论文筛选机制进行了全面改进，实现了六个核心方向：

1. **PDF 全文内容分析** - 不再只看摘要，深入分析 Introduction、Method、Experiments
2. **动态权重系统** - 根据论文年龄（新论文/成熟论文）使用不同评估权重
3. **作者历史质量分析** - 分析作者过往发表论文的质量和影响力
4. **社交媒体热点监控** - 监控国内外社交平台的热点讨论
5. **国内部署优化** - 支持国内社交媒体平台（知乎、掘金、小红书等）
6. **微信公众号监控** - 监控微信公众号上的论文解读和讨论

## 新增文件

### 1. `tools/paper_analyzer.py`
PDF 全文分析工具，包含：
- `PDFDownloader` - 从 arXiv 下载 PDF
- `PDFTextExtractor` - 提取 PDF 文本和章节结构
- `PaperContentAnalyzer` - 使用 LLM 深度分析方法、实验、创新性
  - `_analyze_method()` - 分析方法创新性和严谨性
  - `_analyze_experiments()` - 分析实验设计和可复现性
  - `_analyze_novelty()` - 分析真实创新贡献
- `PaperComparisonAnalyzer` - 与已有工作进行对比分析

### 2. `tools/author_analyzer.py`
作者历史分析工具，包含：
- `SemanticScholarAuthorClient` - 获取作者数据
- `AuthorHistoryAnalyzer` - 分析作者发表历史
  - 计算 h-index、总引用数
  - 评估发表 venues 质量
  - 分析研究一致性和近期活跃度
- `PaperAuthorsAnalyzer` - 综合评估论文所有作者的质量

### 3. `tools/social_monitor.py`
国际社交媒体监控工具，包含：
- `HackerNewsMonitor` - 监控 Hacker News 讨论
- `RedditMonitor` - 监控 Reddit（需要 API 配置）
- `TwitterXMonitor` - 监控 Twitter/X（需要 API Token）
- `SocialMediaAggregator` - 聚合多平台信号
- `SocialSignalIntegrator` - 将社交信号融入评分

### 5. `tools/social_monitor_cn.py` ⭐ 新增
国内社交媒体监控工具，包含：
- `ZhihuMonitor` - 知乎热榜监控
- `JuejinMonitor` - 掘金社区监控
- `CSDNMonitor` - CSDN 博客监控
- `XiaoHongShuMonitor` - 小红书监控（需要 Cookie）
- `JikeMonitor` - 即刻 App 监控（需要 Token）
- `CNSocialMediaAggregator` - 聚合国内平台信号
- `CNSocialSignalIntegrator` - 整合国内社交信号

### 6. `tools/social_monitor_wechat.py` ⭐ 新增
微信公众号监控工具，包含：
- `SogouWechatMonitor` - 基于搜狗微信搜索的免费监控
- `XinbangMonitor` - 基于新榜API的付费监控
- `CustomWechatDataSource` - 自定义数据源接入
- `WechatArticleAggregator` - 聚合多数据源
- `WechatSignalIntegrator` - 整合微信信号到评分系统

## 修改的文件

### 1. `config/settings.py`
新增配置项：
```python
# 动态权重 - 新论文（<30天）
SELECTION_WEIGHTS_NEW = {
    "citations": 0.05,        # 太新，引用数不可靠
    "author_history": 0.20,   # 作者历史质量
    "content_quality": 0.45,  # 全文内容质量（最重要）
    "community_heat": 0.10,   # 早期社区热度
    "novelty": 0.20           # 创新性评估
}

# 动态权重 - 成熟论文（>30天）
SELECTION_WEIGHTS_MATURE = {
    "citations": 0.20,        # 引用数已可靠
    "citation_quality": 0.15, # 引用质量
    "author_history": 0.15,
    "content_quality": 0.30,
    "community_heat": 0.10,
    "novelty": 0.10
}

# 功能开关
ENABLE_FULL_PDF_ANALYSIS=true
ENABLE_AUTHOR_HISTORY_ANALYSIS=true
ENABLE_PAPER_COMPARISON=true
ENABLE_SOCIAL_MONITORING=true

# ⭐ 国内社交媒体配置
SOCIAL_MEDIA_REGION=china  # "global" or "china"
ENABLE_CN_SOCIAL_MONITORING=true
CN_SOCIAL_SIGNAL_WEIGHT=0.15
XIAOHONGSHU_COOKIE=your_cookie  # 可选
JIKE_API_TOKEN=your_token       # 可选

# ⭐ 微信公众号监控配置
ENABLE_WECHAT_MONITORING=true
WECHAT_MONITOR_SOURCE=sogou     # "sogou", "xinbang", or "custom"
WECHAT_SIGNAL_WEIGHT=0.15
XINBANG_API_KEY=                # 如使用新榜
```

### 2. `agents/paper_fetcher.py`
`SelectionAgent` 完全重写，新的执行流程：

```
阶段 0a: 微信公众号监控
  ↓ 发现公众号热门论文
阶段 0b: 其他社交媒体监控
  ↓ 发现社交媒体热点论文
阶段 1: 粗筛
  ↓ 基于元数据快速过滤
阶段 2: 深度分析
  ↓ PDF 全文分析 + 作者历史分析
阶段 3: 对比分析
  ↓ 与已有工作进行对比
阶段 4: 添加社交信号
  ↓ 融入社交媒体讨论热度
阶段 4b: 添加微信公众号信号
  ↓ 融入公众号传播热度
阶段 5: 动态评分
  ↓ 基于论文年龄使用不同权重
阶段 6: 选出 Top N
```

### 3. `requirements.txt`
新增依赖：
```
pymupdf>=1.23.0      # PDF 处理
pdfplumber>=0.10.0   # PDF 文本提取
```

### 4. `.env.example`
新增配置项说明

## 评分机制详解

### 新论文（<30天）评分公式
```
total_score = (
    0.05 * citations_score +
    0.20 * author_history_score +
    0.45 * content_quality_score +
    0.10 * community_heat_score +
    0.20 * novelty_score +
    social_boost  # 额外加分项
)
```

### 成熟论文（>30天）评分公式
```
total_score = (
    0.20 * citations_score +
    0.15 * citation_quality_score +
    0.15 * author_history_score +
    0.30 * content_quality_score +
    0.10 * community_heat_score +
    0.10 * novelty_score +
    social_boost
)
```

### 内容质量评分组成
```
content_quality = 0.40 * novelty_score +
                  0.35 * method_score +
                  0.25 * experiment_score
```

## 使用说明

### 1. 安装新依赖
```bash
pip install -r requirements.txt
```

### 2. 配置环境变量
编辑 `.env` 文件：

**国内部署（阿里云 ECS）完整配置：**
```bash
SOCIAL_MEDIA_REGION=china
ENABLE_CN_SOCIAL_MONITORING=true
ENABLE_WECHAT_MONITORING=true
ENABLE_FULL_PDF_ANALYSIS=true
ENABLE_AUTHOR_HISTORY_ANALYSIS=true
ENABLE_PAPER_COMPARISON=true

# 微信公众号（搜狗免费版）
WECHAT_MONITOR_SOURCE=sogou
WECHAT_SIGNAL_WEIGHT=0.15

# 或微信公众号（新榜付费版）
# WECHAT_MONITOR_SOURCE=xinbang
# XINBANG_API_KEY=your_key

# API Keys
SEMANTIC_SCHOLAR_API_KEY=your_key
```

**海外部署：**
```bash
SOCIAL_MEDIA_REGION=global
ENABLE_SOCIAL_MONITORING=true
TWITTER_BEARER_TOKEN=your_token  # 可选
```

### 3. 运行筛选
```bash
python main.py run
# 或只运行筛选
python main.py select
```

## 优势对比

| 维度 | 旧机制 | 新机制 |
|------|--------|--------|
| 内容分析 | 仅看摘要 | PDF 全文深度分析 |
| 权重系统 | 固定权重 | 动态权重（按论文年龄） |
| 作者评估 | 影响力分数 | 历史发表质量分析 |
| 创新识别 | 摘要自评 | 与已有工作对比分析 |
| 热点发现 | 仅依赖 arXiv | 整合国内外社交媒体 |
| 实验评估 | 无 | 实验设计和可复现性分析 |
| 国内部署 | 需翻墙 | 原生支持国内平台 |
| 微信监控 | 无 | 支持公众号热点发现 |

## 注意事项

1. **PDF 下载**：全文分析需要下载 PDF，可能较慢（每篇 1-3 秒）
2. **API 限制**：
   - Semantic Scholar API 有速率限制（免费版 100 请求/5分钟）
   - 国内平台 API 较为稳定
3. **Cookie 过期**：小红书 Cookie 需要定期更新
4. **成本考虑**：全文分析消耗更多 LLM Token
5. **防火墙**：国内部署时自动屏蔽无法访问的国际平台

## 文档索引

- [CN_SOCIAL_MONITORING.md](CN_SOCIAL_MONITORING.md) - 国内社交媒体监控详细指南
- [WECHAT_MONITORING.md](WECHAT_MONITORING.md) - 微信公众号监控配置指南 ⭐ 新增
- [IMPROVED_SELECTION.md](IMPROVED_SELECTION.md) - 本文件（筛选机制升级说明）

## 未来改进方向

1. **PDF 缓存**：实现 PDF 本地缓存，避免重复下载
2. **增量分析**：只分析新章节或修改部分
3. **多语言支持**：分析非英文论文
4. **图表分析**：使用多模态模型分析论文图表
5. **引用网络分析**：分析论文的引用网络质量
6. **更多国内平台**：微信公众号、B站、抖音等
