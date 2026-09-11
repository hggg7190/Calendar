# 🍎 Apple Calendar MCP

让 AI 访问你的 iCloud 日历和提醒事项。

## 功能

- 📅 查看日程
- 🔍 搜索日程
- ➕ 添加日程
- ➖ 删除日程
- ✅ 查看提醒

## 部署到 Railway

1. Fork 本仓库
2. 在 [appleid.apple.com](https://appleid.apple.com/) 生成 App 专用密码
3. 在 Railway 部署，添加环境变量：
 - `ICLOUD_USERNAME` - 你的 Apple ID
 - `ICLOUD_APP_PASSWORD` - App 专用密码
 - `MCP_PORT` - `8080`
4. 生成公开域名

MCP 端点：`https://你的域名.railway.app/mcp`
