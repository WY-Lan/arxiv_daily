# 微信公众号监控配置指南

## 概述

微信公众号是国内AI论文传播的重要渠道，许多优质的论文解读和技术分析都在公众号上发布。本模块支持监控微信公众号文章，发现热点论文。

## 实现方式

由于微信没有提供公开的文章搜索API，系统提供三种监控方式：

| 方式 | 成本 | 稳定性 | 适用场景 |
|------|------|--------|----------|
| **搜狗微信搜索** | 免费 | 中（需处理反爬） | 个人/小规模使用 |
| **新榜API** | 付费 | 高 | 商业/大规模使用 |
| **自定义数据源** | 视情况 | 视情况 | 已有数据源的用户 |

## 快速配置

### 方式一：搜狗微信搜索（推荐，免费）

```bash
# 启用微信公众号监控
ENABLE_WECHAT_MONITORING=true
WECHAT_MONITOR_SOURCE=sogou
WECHAT_SIGNAL_WEIGHT=0.15
```

**注意事项：**
- ✅ 免费使用
- ⚠️ 搜狗有反爬机制，可能触发验证码
- ⚠️ 每天搜索次数有限制（建议 < 100次/天）
- ⚠️ 搜索间隔建议 > 3秒

**触发验证码处理：**
如果触发验证码，会输出警告日志：
```
搜狗微信搜索触发验证码，请手动访问 https://weixin.sogou.com 验证
```

解决方法：
1. 浏览器访问 https://weixin.sogou.com
2. 搜索任意关键词触发验证码
3. 手动完成验证码
4. 复制页面Cookie到配置文件（可选）

### 方式二：新榜API（付费，稳定）

```bash
# 切换到新榜数据源
WECHAT_MONITOR_SOURCE=xinbang
XINBANG_API_KEY=your_api_key_here
```

**申请流程：**
1. 访问 https://www.newrank.cn
2. 注册企业账号
3. 申请数据服务API权限
4. 获取API Key

**优势：**
- ✅ 数据全面，覆盖10万+公众号
- ✅ 稳定可靠，不受反爬影响
- ✅ 可获取阅读量、点赞数等数据

**费用参考：**
- 基础版：约 ¥500-2000/月
- 专业版：约 ¥5000+/月
- 具体价格需咨询新榜销售

### 方式三：自定义数据源

如果你已有微信公众号数据源，可以通过回调函数接入：

```python
from tools.social_monitor_wechat import CustomWechatDataSource, WechatArticle

async def my_data_source(keyword: str, days: int, limit: int) -> List[WechatArticle]:
    # 你的数据源查询逻辑
    articles = await query_your_database(keyword, days, limit)
    return articles

# 配置使用自定义数据源
custom_source = CustomWechatDataSource(data_callback=my_data_source)
```

## 数据源对比

### 搜狗微信搜索

**监控范围：**
- 搜狗索引的公众号文章
- 时效性：通常延迟1-3天
- 覆盖率：约70%的公众号

**可获取数据：**
- ✅ 文章标题、摘要
- ✅ 公众号名称
- ✅ 发布时间（相对时间）
- ❌ 阅读量、点赞数（不可获取）

**反爬策略：**
- User-Agent轮换
- 请求间隔3秒以上
- Cookie持久化
- 验证码检测

### 新榜API

**监控范围：**
- 新榜监测的公众号（10万+）
- 时效性：实时更新
- 覆盖率：约90%的头部公众号

**可获取数据：**
- ✅ 文章完整信息
- ✅ 阅读量、点赞数、在看数
- ✅ 公众号粉丝数预估
- ✅ 传播路径分析

### 自定义数据源

**适用场景：**
- 自建爬虫系统
- 购买其他数据服务
- 人工录入数据
- 企业内部数据源

## 监控关键词

系统默认监控以下关键词组合：

```python
keywords = [
    "arxiv AI",
    "论文解读",
    "大模型论文",
    "机器学习论文",
    "AI最新研究",
]
```

如需自定义关键词，可修改 `tools/social_monitor_wechat.py` 中的 `search_papers` 方法。

## 影响力账号识别

系统内置了知名AI/技术公众号列表：

```python
influential_accounts = {
    "机器之心", "量子位", "AI科技评论", "新智元",
    "PaperWeekly", "CVer", "深度学习自然语言处理",
    "李沐", "张俊林", "刘知远", "邱锡鹏"
}
```

被这些账号提及的论文会获得额外加分。

## 评分机制

微信公众号信号融入评分系统：

```python
# 基础评分
scores["wechat_signal"] = wechat_data.get("trending_score", 0.0)

# 热点论文额外 boost
if wechat_data.get("is_hot_on_wechat"):
    wechat_boost = scores["wechat_signal"] * WECHAT_SIGNAL_WEIGHT
    total_score += wechat_boost
```

**热点判断标准：**
- 多账号讨论（≥3个不同公众号）
- 知名账号提及（机器之心、量子位等）
- 文章数量多（≥5篇）

## 常见问题

### Q: 搜狗搜索返回空结果？

A: 可能原因：
1. 触发了验证码，需要手动验证
2. 搜索关键词无结果
3. IP被临时封禁，等待一段时间
4. 搜狗页面结构变更，需要更新解析代码

### Q: 如何验证搜狗监控是否工作？

A: 运行测试：
```bash
python -c "
import asyncio
from tools.social_monitor_wechat import SogouWechatMonitor

async def test():
    monitor = SogouWechatMonitor()
    articles = await monitor.search_articles('arxiv', days=7, limit=5)
    print(f'找到 {len(articles)} 篇文章')
    for a in articles[:3]:
        print(f'  - {a.title[:50]}...')

asyncio.run(test())
"
```

### Q: 新榜API是否值得购买？

A: 建议根据需求决定：
- **个人使用/小规模**：搜狗即可满足
- **商业项目/大规模**：新榜更稳定可靠
- **预算有限**：可先用搜狗，遇到问题时再考虑新榜

### Q: 可以监控特定公众号吗？

A: 当前版本不支持指定公众号监控，只支持关键词搜索。
如需此功能，可以考虑：
1. 使用新榜的公众号监控API
2. 自建爬虫定向抓取
3. 联系作者添加此功能

### Q: 数据更新频率是多少？

A: 取决于数据源：
- 搜狗：每次运行pipeline时实时搜索
- 新榜：取决于API调用频率
- 建议：每天运行1-2次pipeline即可

## 最佳实践

### 个人/小团队（推荐）

```bash
# .env配置
ENABLE_WECHAT_MONITORING=true
WECHAT_MONITOR_SOURCE=sogou
WECHAT_SIGNAL_WEIGHT=0.15

# 每天运行次数控制
SCHEDULE_HOUR=9
SCHEDULE_MINUTE=0
```

### 商业/大规模

```bash
# .env配置
ENABLE_WECHAT_MONITORING=true
WECHAT_MONITOR_SOURCE=xinbang
XINBANG_API_KEY=your_key
WECHAT_SIGNAL_WEIGHT=0.20  # 权重更高

# 配合其他监控
ENABLE_CN_SOCIAL_MONITORING=true
CN_SOCIAL_SIGNAL_WEIGHT=0.15
```

## 依赖安装

搜狗搜索需要安装BeautifulSoup4：

```bash
pip install beautifulsoup4
```

其他数据源无额外依赖。

## 故障排查

### 查看监控日志

```bash
# 查看微信公众号相关日志
grep "微信" logs/app.log
grep "搜狗" logs/app.log
grep "wechat" logs/app.log
```

### 测试数据源

```python
# test_wechat_monitor.py
import asyncio
from tools.social_monitor_wechat import WechatArticleAggregator

async def test():
    aggregator = WechatArticleAggregator(use_sogou=True)
    signals = await aggregator.search_papers(hours=24)
    print(f"发现 {len(signals)} 篇论文")
    for signal in signals:
        print(f"- {signal.arxiv_id}: {signal.paper_title[:50]}")
        print(f"  文章数: {signal.mention_count}, 账号数: {len(set(a.account_name for a in signal.articles))}")

asyncio.run(test())
```

## 更新计划

未来可能支持：
- 指定公众号监控
- 微信文章情感分析
- 微信阅读/点赞数据（配合新榜）
- 微信群/朋友圈传播分析
- 小程序数据接入
