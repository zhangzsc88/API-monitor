# 🔍 DeepSeek Monitor

<p align="center">
  <b>Windows 任务栏常驻工具 — 实时监控 DeepSeek API 余额 & Token 消耗</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-Windows%2010%2F11-blue?logo=windows" alt="Platform">
  <img src="https://img.shields.io/badge/python-3.8%2B-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
</p>

---

## ✨ 功能

- 📊 **托盘图标实时显示余额** — 不用打开网页，一眼看到余额
- 💬 **悬浮 tooltip** — 鼠标悬停查看 余额 / 今日消耗 / 更新时间
- 🔢 **精准 Token 统计（v2 新增）** — 从 OpenClaw session 日志直接读取，不靠估算
- 🌐 **远程服务器模式（v2 新增）** — 监控云服务器上的 DeepSeek 消耗
- ⏱️ **可自定义刷新间隔** — 默认每 5 分钟自动刷新
- ⚠️ **余额不足警告** — 低于阈值图标变橙色，归零变红色
- 🔧 **图形化设置界面** — 支持测试 API 连接

---

## 📥 快速开始

### 下载 EXE（无需 Python）

👉 **[📦 下载最新版](https://github.com/fatemarcus-hub/deepseek-monitor/releases/latest)**

下载 `DeepSeekMonitor.exe`，双击运行。首次自动弹出设置窗口，填入 DeepSeek API Key 即可使用。

### 从源码运行

```bash
git clone https://github.com/fatemarcus-hub/deepseek-monitor.git
cd deepseek-monitor
pip install -r requirements.txt
python run.py
```

---

## 🌐 远程服务器模式（监控云服务器上的消耗）

如果你的 DeepSeek 调用跑在云服务器上（比如通过 OpenClaw 等 Agent 框架），Monitor 可以通过网络查询服务器的**实时 Token 消耗**。

### 架构

```
┌─────────────────┐        HTTP         ┌──────────────────┐
│  云服务器 (Linux) │  ←─── GET /tokens ── │  你的 Windows PC   │
│  token_server.py │  ──── JSON 响应 ──→ │  DeepSeek Monitor  │
└─────────────────┘                      └──────────────────┘
```

### 服务器端（只需 2 步）

**1. 把 `token_server.py` 上传到服务器**

```bash
scp token_server.py root@你的服务器IP:~/deepseek-monitor/
```

**2. 启动 Token API 服务**

```bash
cd ~/deepseek-monitor
nohup python3 token_server.py --port 18799 --token *** --bind 0.0.0.0 &
```

参数说明：
- `--port`：监听端口（默认 18799）
- `--token`：鉴权密钥，客户端需填入相同密钥
- `--bind`：`0.0.0.0` 允许外部访问

**3. 开放防火墙端口**

云服务器控制台安全组 → 入站规则 → 放行 TCP `你选的端口`

### 客户端（Monitor 设置）

打开 Monitor → 右键托盘图标 → 设置 → 找到「Token 统计」区域：

| 设置项 | 值 |
|--------|-----|
| 服务器地址 | `http://你的服务器IP:18799` |
| 鉴权密钥 | 与服务器 `--token` 一致 |

保存后 Monitor 自动从服务器拉取实时 Token 消耗。

### 安全建议

- ⚠️ 务必设置 `--token` 鉴权密钥
- 🔒 建议使用 SSH 隧道代替公网直连（更安全）：
  ```bash
  ssh -L 18799:127.0.0.1:18799 root@服务器IP -N
  ```
  然后 Monitor 服务器地址填 `http://127.0.0.1:18799`

---

## 🖱️ 托盘图标 & 菜单

| 图标 | 含义 |
|------|------|
| 🟢 绿色数字 | 余额正常（如 `1.2K` ≈ ¥1,200） |
| 🟠 橙色 `!` | 余额低于警告阈值（默认 < ¥10） |
| 🔴 红色 `X` | 余额为 0 或 API 连接失败 |
| ⏳ 灰色 `..` | 查询中 |

右键菜单显示：余额明细、今日 Token 消耗、状态、刷新时间、刷新/设置/退出。

---

## ⚙️ 设置项

| 设置 | 说明 | 默认 |
|------|------|------|
| API Key | DeepSeek API 密钥 | — |
| 货币单位 | CNY / USD | CNY |
| 刷新间隔 | 秒 | 300 |
| 警告阈值 | 低于此金额变橙色 | ¥10 |
| 服务器地址 | Token 统计服务器（远程模式） | 留空 |
| 鉴权密钥 | 服务器鉴权密钥 | 留空 |

---

## 🧮 Token 统计原理

### 本地模式（服务器上运行）
直接从 OpenClaw session JSONL 文件中提取每条 API 调用的 `usage.totalTokens`，精确到个位数。

### 远程模式（Windows 客户端）
通过 HTTP 查询云服务器上的 `token_server.py`，服务器端使用相同的 session 扫描逻辑，返回累计 Token 数。

> 两种模式均**不依赖余额推算**，数据直接来自 DeepSeek API 返回的 usage 字段。

---

## 📁 文件结构

```
deepseek-monitor/
├── run.py                 # 程序入口
├── token_server.py        # 🆕 Token API 服务器（部署在云服务器上）
├── requirements.txt       # Python 依赖
├── setup.bat              # 一键安装（Windows）
├── run.bat                # 无控制台启动（Windows）
├── install.py             # 安装逻辑
├── assets/
│   ├── icon.ico
│   └── screenshots/
└── src/
    ├── main.py            # 主程序
    ├── tray.py            # 系统托盘
    ├── api.py             # DeepSeek API（查询余额）
    ├── config.py          # 配置管理
    ├── settings.py        # Web 设置界面
    └── session_tracker.py # 🆕 Session 日志扫描（精准 Token 统计）
```

---

## 🙋 FAQ

**Token 消耗不准？**  
v2 已从余额推算改为 session 精准统计。如果使用远程模式，请确保服务器端 `token_server.py` 正在运行。

**怎么卸载？**  
删除程序文件夹 + 删除 `shell:startup` 中的快捷方式。

**运行日志？**  
`%APPDATA%\DeepSeekMonitor\logs\monitor.log`

**服务器端需要装什么？**  
只需要 Python 3（标准库即可，无额外依赖）。

---

## 📝 License

MIT — 随意使用、修改、分发。
