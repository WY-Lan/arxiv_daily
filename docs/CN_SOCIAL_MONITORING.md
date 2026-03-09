# 国内社交媒体监控配置指南

## 概述

针对国内部署环境（阿里云 ECS 等），系统支持监控国内社交媒体平台的 AI 论文讨论：

| 平台 | 状态 | 说明 |
|------|------|------|
| **知乎** | ✅ 可用 | 热榜监控，无需认证 |
| **掘金** | ✅ 可用 | 开发者社区，API 较开放 |
| **CSDN** | ⚠️ 有限 | 需要登录，支持较弱 |
| **小红书** | ⚠️ 可选 | 需要 Cookie |
| **即刻** | ⚠️ 可选 | 需要 API Token |

## 快速配置

### 1. 启用国内社交媒体监控

编辑 `.env` 文件：

```bash
# 设置为国内模式
SOCIAL_MEDIA_REGION=china

# 启用国内社交媒体监控
ENABLE_CN_SOCIAL_MONITORING=true
CN_SOCIAL_SIGNAL_WEIGHT=0.15
```

### 2. 基础配置（推荐）

无需额外配置，系统会自动监控知乎和掘金：

```bash
# 保持默认即可
SOCIAL_MEDIA_REGION=china
ENABLE_CN_SOCIAL_MONITORING=true
```

### 3. 高级配置（可选）

#### 小红书监控（需要 Cookie）

小红书反爬严格，需要手动获取 Cookie：

1. 登录小红书网页版：https://www.xiaohongshu.com
2. 打开浏览器开发者工具（F12）
3. 切换到 Network/网络 标签
4. 刷新页面，找到任意请求
5. 复制 Cookie 字段

```bash
XIAOHONGSHU_COOKIE=your_cookie_here
```

**注意**：Cookie 会过期，需要定期更新。

#### 即刻监控（需要 API Token）

即刻需要申请开发者 API：

1. 访问即刻开发者平台：https://developer.okjike.com
2. 申请 API 权限
3. 获取 Access Token

```bash
JIKE_API_TOKEN=your_token_here
```

## 平台特性

### 知乎
- **优势**：讨论质量高，技术氛围好
- **监控方式**：热榜 + 搜索
- **无需认证**：可直接访问
- **限制**：反爬策略可能变化

### 掘金
- **优势**：开发者社区，技术文章多
- **监控方式**：API 搜索
- **无需认证**：公开 API
- **特点**：论文解读文章较多

### 小红书
- **优势**：论文解读内容丰富，传播力强
- **监控方式**：搜索 API（需登录）
- **需要**：Cookie
- **注意**：内容质量参差不齐

### 即刻
- **优势**：高质量 AI 圈子讨论
- **监控方式**：API（需认证）
- **需要**：API Token
- **特点**：讨论深度好

## 防火墙注意事项

### 国内部署优势
- ✅ 知乎：国内访问快，无墙
- ✅ 掘金：国内 CDN，速度快
- ✅ 小红书：国内服务，稳定
- ✅ 即刻：国内服务，速度快

### 国际平台限制
- ❌ Twitter：国内无法访问
- ❌ Reddit：国内无法访问
- ❌ Hacker News：国内可访问但较慢

## 部署建议

### 方案一：纯国内监控（推荐）

适合完全部署在国内的场景：

```bash
SOCIAL_MEDIA_REGION=china
ENABLE_CN_SOCIAL_MONITORING=true
ENABLE_SOCIAL_MONITORING=false  # 关闭国际监控
CN_SOCIAL_SIGNAL_WEIGHT=0.15
```

**监控平台**：知乎、掘金、CSDN

### 方案二：混合监控

适合有海外代理的场景：

```bash
SOCIAL_MEDIA_REGION=global
ENABLE_SOCIAL_MONITORING=true
ENABLE_CN_SOCIAL_MONITORING=true  # 同时启用国内监控
```

需要在代码中修改支持同时监控两种平台。

### 方案三：最小化监控

节省资源，仅用基础功能：

```bash
ENABLE_CN_SOCIAL_MONITORING=false
ENABLE_SOCIAL_MONITORING=false
```

## 常见问题

### Q: 知乎热榜获取失败？

A: 知乎可能更新了 API 或加强了反爬。可以尝试：
1. 增加请求间隔
2. 使用代理池
3. 降低监控频率

### Q: 小红书 Cookie 频繁过期？

A: 这是正常现象。建议：
1. 设置定期提醒更新 Cookie
2. 使用自动化登录方案（较复杂）
3. 不启用小红书监控（其他平台已足够）

### Q: 掘金返回空结果？

A: 检查：
1. 关键词是否太宽泛
2. 是否触发了频率限制
3. 网络连接是否正常

### Q: 国内平台监控不到最新的论文？

A: 国内平台讨论有一定滞后性（1-3天），这是正常现象。系统会结合 arXiv 最新发布进行筛选。

## 监控效果评估

### 信号质量排序

1. **知乎** - 技术讨论质量最高
2. **即刻** - 深度讨论多（如果有 Token）
3. **掘金** - 技术文章较专业
4. **小红书** - 传播力强但质量参差
5. **CSDN** - 辅助参考

### 建议权重配置

```bash
# 知乎权重最高
CN_SOCIAL_SIGNAL_WEIGHT=0.20

# 小红书次之（如果启用）
XHS_SIGNAL_WEIGHT=0.10
```

## 更新计划

未来可能支持的平台：
- 微信公众号（需要爬虫）
- B 站（视频论文解读）
- 抖音（短视频传播）
- 知识星球（付费社区）

## 技术支持

如遇到平台 API 变更，请：
1. 查看工具代码中的 TODO 注释
2. 更新 User-Agent 和请求头
3. 检查平台官方 API 文档
