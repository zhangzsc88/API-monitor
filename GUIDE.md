# DeepSeek Monitor 操作手册

## 一、项目简介

DeepSeek Monitor 是一个 Windows 任务栏常驻工具，用于实时监控 DeepSeek API 的：

- **余额**：通过 API 直接查询
- **今日 Token 消耗**：从 OpenClaw session 日志精准统计（非估算）

支持两种模式：

| 模式 | 适用场景 |
|------|----------|
| 本地模式 | Monitor 和 OpenClaw 在同一台服务器上 |
| 远程模式 | OpenClaw 在云服务器，Monitor 在你的 Windows 电脑上 |

---

## 二、快速开始（本地模式）

### 1. 下载

从 [Releases](https://github.com/fatemarcus-hub/deepseek-monitor/releases) 下载 `DeepSeekMonitor.exe`。

### 2. 获取 API Key

登录 [DeepSeek Platform](https://platform.deepseek.com/api_keys) → 创建 API Key。

### 3. 启动

双击 EXE → 首次自动弹出设置页面 → 填入 API Key → 保存。

托盘图标显示余额，右键菜单查看余额明细和 Token 消耗。

---

## 三、远程服务器模式（监控云服务器）

当你的 DeepSeek 调用跑在远程 Linux 服务器上时，通过以下方式让 Monitor 查询服务器上的实时数据。

### 架构说明

```
┌─────────────────────┐          HTTP           ┌──────────────────────┐
│  远程 Linux 服务器    │  ←───── 请求 Token ──── │  你的 Windows 电脑     │
│  token_server.py     │  ────── 返回 JSON ────→ │  DeepSeek Monitor.exe │
│  (监听 18799 端口)    │                         │  (设置里填入服务器地址)  │
└─────────────────────┘                          └──────────────────────┘
```

### 服务器端部署（只需做一次）

**步骤 1：上传文件**

将 `token_server.py` 拷贝到服务器上：

```bash
scp token_server.py root@你的服务器IP:~/deepseek-monitor/
```

或者在服务器上直接 `git clone` 本项目。

**步骤 2：启动服务**

```bash
cd ~/deepseek-monitor
nohup python3 token_server.py \
  --port 18799 \
  --token *** \
  --bind 0.0.0.0 \
  > /tmp/token_server.log 2>&1 &
```

参数说明：

| 参数 | 作用 | 建议 |
|------|------|------|
| `--port` | 监听端口 | 默认 18799 |
| `--token` | 鉴权密钥 | **必填**，自己设一个复杂密码 |
| `--bind` | 绑定地址 | `0.0.0.0` 允许外网访问 |

> 服务只需 Python 3 标准库，无额外依赖。

**步骤 3：开放防火墙端口**

去云服务器控制台（腾讯云/阿里云等）→ 安全组 → 入站规则 → 添加规则：

- 协议：TCP
- 端口：你设置的端口（如 18799）
- 来源：建议先设为 `0.0.0.0/0`，确认可用后再改为你的 IP

**步骤 4：验证服务**

在服务器上运行：

```bash
curl -H "Authorization: Bearer ***" http://127.0.0.1:18799/tokens
```

应返回类似 `{"date":"2026-05-29","total_tokens":123456789}`。

### Windows 客户端配置

打开 Monitor → 右键托盘图标 → 设置 → 找到「Token 统计」：

| 字段 | 填写 |
|------|------|
| 服务器地址 | `http://你的服务器IP:18799` |
| 鉴权密钥 | 与服务器 `--token` 一致 |

保存后 Monitor 自动连接到服务器，托盘即可看到实时 Token 消耗。

---

## 四、安全建议

### 强烈推荐：使用 SSH 隧道（代替公网直连）

SSH 隧道比开放公网端口更安全，流量全程加密：

**Windows 端（需安装 OpenSSH 或 PuTTY）：**

```bash
ssh -L 18799:127.0.0.1:18799 root@你的服务器IP -N
```

隧道建立后，Monitor 服务器地址填 `http://127.0.0.1:18799`。

此时可以**关闭**云服务器安全组中的 18799 端口。

> 如果 Windows 没有 SSH，安装 [PuTTY](https://www.putty.org)，在 Connection → SSH → Tunnels 中设置 Source port `18799`，Destination `127.0.0.1:18799`。

### 使用方式对比

| 方式 | 安全性 | 难度 | 需要开端口 |
|------|--------|------|-----------|
| 公网直连 | 中（依赖 Token 鉴权） | 低 | 是 |
| SSH 隧道 | 高（SSH 加密） | 中 | 否 |

---

## 五、设置项说明

| 设置 | 说明 | 默认 |
|------|------|------|
| API Key | DeepSeek API 密钥，用于查余额 | 必填 |
| 货币单位 | CNY（人民币）或 USD（美元） | CNY |
| 刷新间隔 | 自动刷新频率（秒） | 300（5分钟） |
| 警告阈值 | 余额低于此值变橙色（元） | 10 |
| 服务器地址 | Token 统计服务器（远程模式用） | 留空=本地模式 |
| 鉴权密钥 | 服务器鉴权密钥 | 与服务器一致 |

---

## 六、常见问题

**Q: 为什么 Token 消耗显示"收集中..."？**

A: 检查以下三项：
1. 服务器端 `token_server.py` 是否在运行？（`pgrep -f token_server`）
2. 防火墙端口是否开放？
3. Monitor 设置中的服务器地址和鉴权密钥是否正确？

**Q: Token 消耗和 DeepSeek 后台不一致？**

A: 本项目只统计**通过 OpenClaw** 的 DeepSeek 调用。如果 API Key 也被其他程序使用（如直接调 API 的脚本），那些消耗不会被计入。

**Q: 服务器重启后需要手动启动 token_server.py 吗？**

A: 是的。可以注册为 systemd 服务实现开机自启：
```bash
# 可选：创建 /etc/systemd/system/token-server.service
# 然后 systemctl enable token-server
```

**Q: 没有 OpenClaw 能用吗？**

A: Token 统计功能依赖 OpenClaw 的 session 日志格式。不运行 OpenClaw 的服务器只能用余额查询功能。

**Q: Monitor 日志在哪里？**

A: Windows 上：`%APPDATA%\DeepSeekMonitor\logs\monitor.log`

---

## 七、项目文件说明

| 文件 | 用途 | 在哪运行 |
|------|------|----------|
| `run.py` / `.exe` | Monitor 主程序 | Windows |
| `src/tray.py` | 系统托盘界面 | Windows |
| `src/api.py` | DeepSeek API 交互 | Windows |
| `src/settings.py` | Web 设置界面 | Windows |
| `src/config.py` | 配置管理 | Windows |
| `src/session_tracker.py` | Session 日志扫描 | 服务器端 |
| `token_server.py` | Token API 服务 | 服务器端 |
