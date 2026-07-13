# NodeSeek 自动签到脚本

这是一个用于 NodeSeek 论坛的自动化脚本，签到功能。使用 Selenium 和 undetected-chromedriver 实现自动化操作。


## 功能特点

- 自动签到（点击签到图标）
- 自动点击"试试手气"或"鸡腿 x 5"按钮（可配置）
- 支持 GitHub Actions 自动运行
- 多账号支持

## 环境变量配置



## GitHub Actions 自动运行

1. Fork 本仓库
2. 在仓库的 Settings -> Secrets 中添加 `NS_COOKIE`
3. 可选：添加 `NS_RANDOM` 设置是否随机选择奖励
4. Actions 会在每天 UTC 16:00（北京时间 00:00）自动运行

## 注意事项

- 请确保 Cookie 有效且具有足够的权限
