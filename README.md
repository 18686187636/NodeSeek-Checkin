# NodeSeek 多账号自动签到

基于 GitHub Actions 的 NodeSeek 每日自动签到脚本，支持多账号、签到模式选择、Telegram 通知以及 Cookie 到期剩余天数显示。

## ✨ 功能特点

- ✅ 多账号支持：可同时签到多个 NodeSeek 账号
- 🎲 签到模式：支持固定鸡腿或“试试手气”随机模式
- 📅 到期提醒：自动计算并显示每个账号的 Cookie 剩余天数
- 📱 Telegram 通知：签到结果实时推送至 Telegram
- ⏰ 自动执行：每天北京时间 8:00 自动运行，支持手动触发
- 🔒 安全存储：Cookie 通过 GitHub Secrets 加密保存

## 📋 准备工作

1. 一个 GitHub 账号
2. 需要签到的 NodeSeek 账号（一个或多个）
3. （可选）Telegram Bot Token 和 Chat ID 用于接收通知

## 🚀 快速开始

### 1. Fork 本仓库
点击右上角的 **Fork** 按钮，将本仓库复制到你的 GitHub 账号下。

### 2. 获取 NodeSeek Cookie
- 在浏览器中登录 NodeSeek
- 按 `F12` 打开开发者工具 → Network 标签
- 刷新页面，找到任意 `www.nodeseek.com` 的请求
- 在 Request Headers 中复制完整的 `Cookie` 值（包含所有键值对）

### 3. 配置 GitHub Secrets
进入你 Fork 的仓库，点击 **Settings** → **Secrets and variables** → **Actions** → **New repository secret**，依次添加：

| Secret 名称 | 说明 |
|------------|------|
| `NS_COOKIES` | 多账号 Cookie 列表，每行一个账号，格式见下方 |
| `TG_BOT_TOKEN` | Telegram Bot Token（可选） |
| `TG_CHAT_ID` | Telegram Chat ID（可选） |

#### `NS_COOKIES` 格式
每行一个账号，使用竖线 `|` 分隔三个字段：
例如：
深蓝|cf_clearance=...; session=...; pjwt=...; ...|2026-07-31
Deepblue|cf_clearance=...; session=...; pjwt=...; ...|2026-07-31


- **用户名**：任意标识，用于显示（可为中文）
- **Cookie 字符串**：从浏览器复制的完整 Cookie
- **到期日期**：格式 `YYYY-MM-DD`，脚本将计算剩余天数

> 如果某行不含到期日期（只有用户名和 Cookie），则显示“未知”。

### 4. 调整签到模式（可选）
在工作流文件 `.github/workflows/daily_checkin.yml` 中，修改 `NS_RANDOM` 环境变量：
- `true`：试试手气（随机鸡腿）
- `false`：固定鸡腿

```yaml
env:
  NS_RANDOM: true   # 或 false
5. 手动触发测试
进入仓库的 Actions 选项卡

选择 Daily NodeSeek Check-In 工作流

点击 Run workflow → Run workflow

查看运行日志和 Telegram 通知（如果配置）

⏰ 自动运行
工作流默认每天 UTC 0:00（北京时间 8:00）自动执行，你也可以手动触发。

📱 Telegram 通知示例
text
📅 NodeSeek 签到汇总
深蓝: ✅ 签到成功，获得5鸡腿 | 获得 5 鸡腿 | cookie到期剩余 17 天
Deepblue: ✅ 签到成功，获得3鸡腿 | 获得 3 鸡腿 | cookie到期剩余 17 天
📁 项目结构
text
├── .github/
│   └── workflows/
│       └── daily_checkin.yml   # GitHub Actions 工作流
├── checkin.py                  # 签到主脚本
└── README.md                   # 项目说明
⚠️ 注意事项
Cookie 有效期：Cookie 过期后签到会失败，请定期更新 NS_COOKIES 中的 Cookie 和到期日期。

到期日期格式：务必使用 YYYY-MM-DD，如 2026-07-31。

隐私安全：Cookie 包含登录凭证，请勿泄露给他人。建议将仓库设为 Private。

Cloudflare 防护：如果遇到 403 错误，可能需要重新获取包含 cf_clearance 的 Cookie。

📄 许可证
本项目采用 MIT 许可证，详情请见 LICENSE 文件。

🤝 贡献
欢迎提交 Issue 和 Pull Request！

Happy Check-in! 🎉

