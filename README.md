# 🔍 API Monitor

<p align="center">
  <b>Windows 任务栏常驻工具 — 实时监控多平台 API 余额 & Token 用量</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-Windows%2010%2F11-blue?logo=windows" alt="Platform">
  <img src="https://img.shields.io/badge/python-3.8%2B-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
</p>

---

## ✨ 功能

- 🖥️ **多平台监控** — DeepSeek、MiniMax、小米 MiMo，一个托盘全掌握
- 📊 **托盘图标实时显示** — 不用打开网页，一眼看到余额/剩余百分比
- 💬 **悬浮 Tooltip** — 鼠标悬停查看各账号详情、更新时间
- ⏱️ **自动刷新** — 可自定义间隔（默认 5 分钟）
- ⚠️ **余额不足预警** — 低于阈值图标变色提醒（橙色 → 红色）
- 🔧 **Web 设置界面** — 浏览器中管理多账号，支持连接测试
- 🔌 **Provider 架构** — 新增平台只需实现一个 Python 类

## 📡 支持平台

| 平台 | 认证方式 | 显示内容 | 备注 |
|------|---------|---------|------|
| **DeepSeek** | API Key | 余额（¥） | 支持多账号 |
| **MiniMax Token Plan** | Subscription Key (sk-cp-) | 剩余百分比 | 5h池 + 周池详情 |
| **小米 MiMo** | Cookie | 剩余百分比 | Cookie 有效期约 24h |

> 💡 京东云 Coding Plan 暂无公开 API，MiniMax 按量计费（积分）余额无法通过 API 查询。

## 📥 快速开始

### 下载 EXE（无需 Python）

👉 **[📦 下载最新版](https://github.com/zhangzsc88/API-monitor/releases/latest)**

下载 `APIMonitor.exe`，双击运行。首次自动弹出设置页面，添加账号即可使用。

### 从源码运行

```bash
git clone https://github.com/zhangzsc88/API-monitor.git
cd API-monitor
pip install -r requirements.txt
python run.py
```

## 🖱️ 托盘图标

| 图标 | 含义 |
|------|------|
| 🟢 绿色数字 | 余额/剩余正常 |
| 🟠 橙色 `!` | 低于警告阈值 |
| 🔴 红色 `X` | 余额归零或连接失败 |
| ⏳ 灰色 `..` | 查询中 |

右键菜单：各账号余额明细、刷新、设置、退出。

## ⚙️ 各平台配置

### DeepSeek

1. 登录 [DeepSeek Platform](https://platform.deepseek.com/api_keys) → 创建 API Key
2. 设置页面选择 **DeepSeek** → 填入 API Key → 保存

### MiniMax Token Plan

1. 登录 [MiniMax Platform](https://platform.minimaxi.com/) → 获取 Subscription Key（`sk-cp-` 开头）
2. 设置页面选择 **MiniMax Token** → 填入 Key → 保存
3. Tooltip 显示：5h 池剩余 + 周池剩余

### 小米 MiMo

1. 打开 [MiMo Platform](https://platform.xiaomimimo.com/) → F12 → Application → Cookies
2. 找到以下 3 个字段，复制值：
   - `userId`
   - `serviceToken`
   - `api-platform_serviceToken`
3. 设置页面选择 **MiMo** → 分别填入 3 个字段 → 保存

> ⚠️ Cookie 有效期约 24 小时，过期需重新获取。API Key（tp-xxxxx）仅用于调用模型，不支持用量查询。

## 📁 文件结构

```
src/
├── main.py              # 入口，日志初始化
├── app.py               # 应用核心类 App
├── tray.py              # 托盘图标 + 右键菜单
├── icon_renderer.py     # 图标渲染（多平台颜色/文字）
├── config.py            # 配置管理（v1→v2 自动迁移）
├── settings.py          # Web 设置界面
├── models.py            # 数据模型
├── providers/
│   ├── __init__.py      # 注册表 + 工厂函数
│   ├── base.py          # Provider 抽象基类
│   ├── deepseek.py      # DeepSeek 余额查询
│   ├── minimax_token.py # MiniMax Token Plan
│   └── mimo.py          # 小米 MiMo（Cookie 认证）
└── session_tracker.py   # Session 日志（暂未使用）
```

## 🔌 新增平台

1. 在 `src/providers/` 新建 `your_platform.py`，继承 `BaseProvider`
2. 实现 `fetch()` → 返回 `ProviderResult`
3. 在 `__init__.py` 注册到 `ALL_PROVIDERS`
4. 在 `settings.py` HTML 模板中添加对应 UI

详见 [架构文档](docs/architecture.md)。

## 🔒 安全说明

- **所有密钥仅存储在本地** `data/config.json`，不会上传到任何服务器
- EXE 打包**不含任何硬编码凭证**
- 配置文件与 EXE 同目录的 `data/` 子目录，方便管理

## 📝 License

MIT — 基于 [DeepSeek Monitor](https://github.com/zhangzsc88/API-monitor) 二开。
