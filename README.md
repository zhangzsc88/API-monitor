# 🔍 API Monitor

<p align="center">
  <b>Windows 任务栏常驻工具 — 实时监控多平台 API 余额</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-Windows%2010%2F11-blue?logo=windows" alt="Platform">
  <img src="https://img.shields.io/badge/python-3.8%2B-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
</p>

---

## ✨ 功能

- 🖥️ **多平台监控** — DeepSeek、MiniMax、小米 MiMo、京东云 JoyBuilder、讯飞星辰，一个托盘全掌握
- 📊 **托盘图标实时显示** — 不用打开网页，一眼看到余额/剩余百分比
- 🪟 **悬浮窗** — 白底黑字半透明窗口，5档透明度可调，启动自动弹出
- 💬 **悬浮 Tooltip** — 鼠标悬停查看各账号详情、更新时间
- 📈 **DeepSeek 用量详情** — 平台 Token 模式查今日按模型输入/输出/命中/费用
- ⏱️ **自动刷新** — 可自定义间隔（默认 5 分钟）
- ⚠️ **余额不足预警** — 低于阈值图标变色提醒（橙色 → 红色）
- 🔧 **Web 设置界面** — 浏览器中管理多账号，支持连接测试
- 🔌 **Provider 架构** — 新增平台只需实现一个 Python 类

## 📡 支持平台

| 平台 | 认证方式 | 显示内容 | 备注 |
|------|---------|---------|------|
| **DeepSeek** | API Key + 平台 Token | 余额（¥）+ 今日用量详情 | 平台 Token 可查按模型命中/费用 |
| **MiniMax Token Plan** | Subscription Key (sk-cp-) | 剩余百分比 | 5h池 + 周池详情 |
| **京东云 JoyBuilder** | Cookie (thor + pin) | 剩余百分比 | 5h/7天/月多周期 |
| **讯飞星辰** | Cookie (ssoSessionId) | 剩余百分比 | 5h/周/月多周期，支持无忧版 |
| **小米 MiMo** | Cookie (3字段) | 剩余百分比 | 套餐积分 + 补偿积分 + 月度用量 |

## 📥 快速开始

### 下载 EXE（无需 Python）

👉 **[📦 下载最新版](https://github.com/katseven-zhang/API-monitor/releases/latest)**

下载 `APIMonitor.exe`，双击运行。首次自动弹出设置页面，添加账号即可使用。

### 从源码运行

```bash
git clone https://github.com/katseven-zhang/API-monitor.git
cd API-monitor
pip install -r requirements.txt
python run.py
```

## 🖱️ 托盘图标

| 图标 | 含义 |
|------|------|
| 🟢 绿色 **M** | 余额/剩余正常 |
| 🟠 橙色 `!` | 低于警告阈值 |
| 🔴 红色 `X` | 余额归零或连接失败 |
| ⏳ 灰色 `..` | 查询中 |

右键菜单：各账号余额明细、刷新、设置、退出。

## ⚙️ 各平台配置

### DeepSeek

1. 登录 [DeepSeek Platform](https://platform.deepseek.com/api_keys) → 创建 API Key
2. 设置页面选择 **DeepSeek** → 填入 API Key → 保存
3. **（可选）填入平台 Token 可查看今日用量详情**：
   - 打开 [DeepSeek 平台](https://platform.deepseek.com/usage) → F12 → Console
   - 输入 `JSON.parse(localStorage.getItem('userToken')).value` → 复制返回的 Token
   - 粘贴到设置页面的"平台 Token"输入框

> 💡 不填平台 Token 仅查余额；填了可额外查看今日按模型的输入/输出/命中率/费用

### MiniMax Token Plan

1. 登录 [MiniMax Platform](https://platform.minimaxi.com/) → 获取 Subscription Key（`sk-cp-` 开头）
2. 设置页面选择 **MiniMax Token** → 填入 Key → 保存
3. Tooltip 显示：5h 池剩余 + 周池剩余

### 硅基流动 SiliconFlow

> ⚠️ 暂时隐藏：API 返回余额与网页端不一致，待后续修复

<!--

1. 登录 [SiliconFlow](https://cloud.siliconflow.cn/) → 获取 API Key
2. 设置页面选择 **硅基流动** → 填入 API Key → 保存
3. Tooltip 显示：总余额、可用余额、充值余额

-->

### 小米 MiMo

1. 打开 [MiMo Platform](https://platform.xiaomimimo.com/) → F12 → Application → Cookies
2. 找到以下 3 个字段，复制值：
   - `userId`
   - `serviceToken`
   - `api-platform_serviceToken`
3. 设置页面选择 **MiMo** → 分别填入 3 个字段 → 保存

> ⚠️ Cookie 有效期约 24 小时，过期需重新获取。API Key（tp-xxxxx）仅用于调用模型，不支持用量查询。

### 京东云 JoyBuilder

1. 打开 [JoyBuilder 控制台](https://joybuilder-console.jdcloud.com/system/subscribe/list) → F12 → Application → Cookies
2. 找到以下 2 个字段，复制值：
   - `thor`
   - `pin`
3. 设置页面选择 **京东云 JoyBuilder** → 分别填入 2 个字段 → 保存

> ⚠️ Cookie 有效期较长（通常几周），过期需重新登录获取。只需 `thor` 和 `pin` 两个字段即可。

### 讯飞星辰

1. 打开 [讯飞星辰 MaaS 套餐订阅](https://maas.xfyun.cn/packageSubscription) → F12 → Application → Cookies
2. 找到以下字段，复制值：
   - `ssoSessionId`
3. 设置页面选择 **讯飞星辰** → 填入 ssoSessionId → 保存

> ⚠️ 只需 `ssoSessionId` 一个字段即可。Cookie 与登录会话一致，过期需重新获取。

## 📁 文件结构

```
src/
├── main.py              # 入口，全局异常捕获
├── app.py               # 应用核心类 App
├── tray.py              # 托盘图标 + 右键菜单 + 悬浮窗联动
├── floating.py          # 悬浮窗（白底黑字，5档透明度）
├── icon_renderer.py     # 图标渲染（多平台颜色/文字）
├── config.py            # 配置管理（v1→v2 自动迁移）
├── settings.py          # Web 设置界面
├── models.py            # 数据模型
└── providers/
    ├── __init__.py      # 注册表 + 工厂函数
    ├── base.py          # Provider 抽象基类
    ├── deepseek.py      # DeepSeek 余额 + 用量（双模式）
    ├── jdcloud.py       # 京东云 JoyBuilder（Cookie 认证）
    ├── minimax_token.py # MiniMax Token Plan
    ├── siliconflow.py   # 硅基流动（隐藏，代码保留）
    ├── xfyun.py         # 讯飞星辰（Cookie 认证）
    └── mimo.py          # 小米 MiMo（Cookie 认证）
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

## 🙏 致谢

- **[fatemarcus-hub/deepseek-monitor](https://github.com/fatemarcus-hub/deepseek-monitor)** — 原始项目作者，DeepSeek Monitor 核心基础
- 本项目基于原项目 Fork 后二开，扩展为多平台 API 余额监控工具

## 📝 License

MIT — 本项目基于 [fatemarcus-hub/deepseek-monitor](https://github.com/fatemarcus-hub/deepseek-monitor)（MIT License）二次开发。
