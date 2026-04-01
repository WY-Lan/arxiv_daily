# 抖音发布功能开发进度

## 当前状态

抖音发布功能已基本完成开发，MCP 服务器测试正常，等待扫码登录后即可进行实际发布测试。

---

## 已完成的工作

### 1. MCP 服务器测试 (Phase 1) ✅

- **项目位置**: `/Users/wuyang.lan/Downloads/douyin-upload-mcp-skill`
- **状态**: MCP 服务器正常运行，浏览器自动化框架工作正常
- **测试结果**:
  - ✅ Daemon 自动启动
  - ✅ 浏览器启动与 CDP 连接
  - ✅ 抖音创作者平台访问
  - ✅ 登录状态检测
  - ⏳ 等待扫码登录

### 2. arxiv-daily 集成 (Phase 2) ✅

新增文件：
| 文件 | 用途 |
|------|------|
| `.claude/skills/douyin-publisher/SKILL.md` | 抖音发布 skill 定义 |
| `config/prompts/douyin_style.txt` | 抖音内容生成模板 |
| `tools/douyin_cover.py` | 竖版封面生成器（1080x1920） |
| `agents/publishers/__init__.py` | 添加 `DouyinPublisherAgent` 类 |
| `config/settings.py` | 添加 `DOUYIN_MCP_PATH`, `DOUYIN_MCP_ENABLED` 配置 |

### 3. 关键配置

**settings.py 新增配置**:
```python
DOUYIN_MCP_PATH: str = Field(default="", description="Path to douyin-upload-mcp-skill directory")
DOUYIN_MCP_ENABLED: bool = Field(default=True, description="Enable Douyin publishing via MCP")
```

---

## 待完成的工作

### Phase 3: 验证与上线 ⏳

#### Step 1: 完成抖音登录

1. 查看登录二维码：
   ```bash
   open /Users/wuyang.lan/Downloads/douyin-upload-mcp-skill/temp/qrcode_*.png
   ```

2. 用抖音 App 扫码登录

3. 如需短信验证，修改 `src/demo-imagetext.js` 中的 `smsCode` 变量后重新运行

#### Step 2: 测试 MCP 发布

```bash
cd /Users/wuyang.lan/Downloads/douyin-upload-mcp-skill
node src/demo-imagetext.js
```

预期结果：图文发布成功，显示 `✅ 图文发布成功`

#### Step 3: 配置 MCP 到 Claude Code

编辑 `~/.claude/settings.json`，添加：

```json
{
  "mcpServers": {
    "douyin": {
      "command": "node",
      "args": ["/Users/wuyang.lan/Downloads/douyin-upload-mcp-skill/src/mcp-server.js"]
    }
  }
}
```

#### Step 4: 测试 arxiv-daily 集成

```bash
cd /Users/wuyang.lan/Downloads/arxiv_daily

# 测试抖音发布（dry run，仅生成内容不发布）
python -c "
import asyncio
from agents.publishers import DouyinPublisherAgent
from agents.base import AgentContext

async def test():
    agent = DouyinPublisherAgent()
    context = AgentContext()
    # 需要先有 summaries 数据
    result = await agent.run(context)
    print(result)

asyncio.run(test())
"

# 完整 pipeline 测试
python main.py run
```

#### Step 5: 更新 .env 配置（可选）

```bash
# 在 arxiv_daily/.env 中添加
DOUYIN_MCP_PATH=/Users/wuyang.lan/Downloads/douyin-upload-mcp-skill
DOUYIN_MCP_ENABLED=true
```

---

## 关键文件路径

### MCP 项目

```
/Users/wuyang.lan/Downloads/douyin-upload-mcp-skill/
├── src/
│   ├── mcp-server.js       # MCP 服务器入口
│   ├── demo-imagetext.js   # 图文发布测试脚本
│   ├── douyin-ops.js       # 抖音操作逻辑
│   ├── browser.js          # 浏览器连接
│   └── daemon/             # Daemon 服务
├── temp/                   # 临时文件（二维码等）
├── douyin-output/          # 输出目录
└── .env                    # 配置文件
```

### arxiv-daily 项目

```
/Users/wuyang.lan/Downloads/arxiv_daily/
├── .claude/skills/douyin-publisher/
│   └── SKILL.md            # 抖音发布 skill
├── agents/publishers/__init__.py  # DouyinPublisherAgent
├── tools/douyin_cover.py   # 竖版封面生成器
├── config/
│   ├── prompts/douyin_style.txt  # 内容模板
│   └── settings.py         # 配置（已添加 DOUYIN_* 字段）
└── storage/douyin_covers/  # 抖音封面输出目录
```

---

## 技术要点

### 抖音图文发布流程

1. **内容生成**: 使用 `douyin_style.txt` 模板，LLM 生成适合抖音的图文内容
2. **封面制作**: `tools/douyin_cover.py` 生成 1080x1920 竖版封面
3. **MCP 发布**: 调用 `douyin_publish_imagetext` 工具发布

### MCP 工具列表

| 工具 | 说明 |
|------|------|
| `douyin_publish_imagetext` | 发布图文（多图 + 标题 + 简介） |
| `douyin_publish_video` | 发布视频 |
| `douyin_check_login` | 检查/推进登录流程 |
| `douyin_screenshot` | 页面截图（调试用） |
| `douyin_probe` | 探测页面元素状态 |

### 登录流程说明

MCP 登录需要多次调用 `douyin_check_login` 推进：

```
第 1 次调用 → phase: qrcode           → 截图保存二维码，用户扫码
第 2 次调用 → phase: sms_verification → 自动点击「接收短信验证码」
第 3 次调用 → phase: sms_code_input   → 提示输入验证码
第 4 次调用 → phase: logged_in        → 传入 smsCode 完成登录
```

---

## 常见问题

### Q: 浏览器启动失败？

```bash
# 重新安装 Chrome
npx puppeteer browsers install chrome
```

### Q: 登录过期？

```bash
# 清除登录数据重新登录
cd /Users/wuyang.lan/Downloads/douyin-upload-mcp-skill
rm -rf ~/.wjz_browser_data
node src/demo-imagetext.js
```

### Q: 发布失败？

1. 检查登录状态：运行 `douyin_check_login`
2. 检查图片路径：确保图片文件存在
3. 查看错误日志：检查终端输出的错误信息

---

## 参考资料

- MCP 项目原仓库: https://github.com/WJZ-P/douyin-upload-mcp-skill
- 抖音创作者平台: https://creator.douyin.com/
- 设计计划: `/Users/wuyang.lan/.claude/plans/ticklish-watching-wigderson.md`