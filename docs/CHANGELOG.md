# API Monitor - 开发日志

> 项目基于 [DeepSeek Monitor](https://github.com/zhangzsc88/API-monitor) 二开

## v2.1.0 - 2026-06-14

### 新增

- MiMo Cookie 配置改为**分字段填写**（userId / serviceToken / api-platform_serviceToken），不再需要手动拼接 Cookie 字符串
- MiMo Provider 兼容旧格式 `extra.cookie`，自动迁移

### 变更

- 删除 `src/providers/minimax_coding.py`（MiniMax Coding Plan 已并入 Token Plan，产品不再存在）
- `ALL_PROVIDERS` 移除 `minimax_coding`，仅保留 deepseek / minimax_token / mimo
- MiniMax Token 显示改为**剩余百分比**（与网页一致）
- 配置/日志路径改为与 EXE 同目录的 `data/` 子目录（优先级：`APIMONITOR_HOME` > `<exe_dir>/data/` > `CWD/data/`）

---

## v2.0.0 - 2026-06-14

### 变更概述

从单平台（DeepSeek）监控工具重构为多平台 API 余额监控工具。

### 新增功能

- **多平台支持**：MiniMax Token Plan、小米 MiMo、DeepSeek（多账号）
- **Provider 抽象层**：统一接口 `fetch() -> ProviderResult`，新增平台只需 3 步
- **多账号管理**：每个平台支持独立 API Key、独立启用/禁用、独立预警阈值
- **图标渲染策略**：worst（最差状态）/ primary（首个账号）可选
- **Web 设置界面**：本地 HTTP 服务 + 浏览器配置，支持添加/编辑/删除/测试账号
- **配置自动迁移**：检测旧版 DeepSeek Monitor 配置，首次启动自动迁移

### 架构变更

| 原项目 | 新项目 | 说明 |
|--------|--------|------|
| `api.py`（单平台） | `providers/`（多平台） | Provider 抽象层 + 注册表模式 |
| `config.py`（单账号） | `config.py`（多账号） | v2 格式 accounts[] 数组 |
| `tray.py`（含图标渲染） | `tray.py` + `icon_renderer.py` | 渲染逻辑解耦 |
| 无核心类 | `app.py` | App 类协调 Provider/Tray/Settings |
| 无数据模型 | `models.py` | ProviderResult/AccountConfig/StatusLevel |

### 已知限制

- 京东云 Coding Plan 无公开 API，暂不支持
- MiniMax 按量计费（积分）余额无公开查询 API
- 小米 MiMo Cookie 有效期约 24 小时，需手动刷新
- 无历史数据记录/趋势图
