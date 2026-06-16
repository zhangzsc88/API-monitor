# DeepSeekMonitor API 端点与认证方式完整分析

> 项目: jasmine889966/DeepSeekMonitor (GitHub)
> 版本: 1.2.1 (最新 release)
> 分析日期: 2026-06-16

---

## 一、API 端点总览

所有 API 请求的基础 URL 为: `https://platform.deepseek.com`

| # | 端点路径 | 方法 | 用途 | 需要认证 |
|---|---------|------|------|---------|
| 1 | `/auth-api/v0/users/current` | GET | 获取当前用户信息(含 token 刷新) | 是 (Bearer) |
| 2 | `/api/v0/users/get_user_summary` | GET | 获取账户摘要(余额、月度用量等) | 是 (Bearer) |
| 3 | `/api/v0/usage/amount` | GET | 获取 Token 用量明细(按模型、按天) | 是 (Bearer) |
| 4 | `/api/v0/usage/cost` | GET | 获取费用明细(按模型、按天) | 是 (Bearer) |
| 5 | `/api/v0/client/settings?scope=banner` | GET | 获取客户端 banner 设置 | 否 |
| 6 | `/api/v0/client/settings?did=<device_id>` | GET | 获取客户端设置(带设备 ID) | 是 (Bearer) |
| 7 | `https://status.deepseek.com/` | GET | 服务状态页面(HTML 抓取) | 否 |
| 8 | `https://status.deepseek.com/history.atom` | GET | 服务状态历史(Atom feed) | 否 |

### 端点详细说明

#### 1. `/auth-api/v0/users/current` -- 当前用户验证
- **认证**: Bearer Token(必须)
- **查询参数**: 无
- **响应**: 包含 `CurrentUserDTO`(id, email, token, currency, cookie_header, app_version, balance_alert)
- **特殊**: 这是唯一使用 `/auth-api/` 前缀的端点; 响应可能返回新 token, 用于自动刷新会话

#### 2. `/api/v0/users/get_user_summary` -- 账户摘要
- **认证**: Bearer Token(必须)
- **查询参数**: 无
- **响应**: `UserSummaryDTO`(current_token, monthly_usage, total_usage, normal_wallets, bonus_wallets, total_available_token_estimation, monthly_costs, monthly_token_usage)

#### 3. `/api/v0/usage/amount` -- Token 用量
- **认证**: Bearer Token(必须)
- **查询参数**: `month` (Int), `year` (Int)
- **示例**: `/api/v0/usage/amount?month=6&year=2026`
- **响应**: `UsageDTO`(total: 模型汇总, days: 每日明细)
- **用量类型**: PROMPT_TOKEN, PROMPT_CACHE_HIT_TOKEN, PROMPT_CACHE_MISS_TOKEN, RESPONSE_TOKEN, REQUEST

#### 4. `/api/v0/usage/cost` -- 费用明细
- **认证**: Bearer Token(必须)
- **查询参数**: `month` (Int), `year` (Int)
- **示例**: `/api/v0/usage/cost?month=6&year=2026`
- **响应**: `[CostDTO]` 数组(注意: 返回数组, 取第一个元素)

#### 5. `/api/v0/client/settings?scope=banner` -- Banner 设置
- **认证**: 不需要
- **查询参数**: `scope=banner`
- **用途**: 获取客户端 banner 配置

#### 6. `/api/v0/client/settings?did=<device_id>` -- 设备设置
- **认证**: Bearer Token(必须)
- **查询参数**: `did` (设备 ID, UUID 格式)
- **用途**: 上报设备信息

---

## 二、认证方式详解

### 双重认证: Bearer Token + Cookie

DeepSeekMonitor 使用 **Bearer Token + Cookie** 双重认证机制:

```
Authorization: Bearer <token>
Cookie: <cookie_header_string>
```

#### Token 来源
Token 通过 **浏览器内嵌 WebView** 捕获, 具体流程:

1. 应用内嵌 WKWebView 加载 `https://platform.deepseek.com/usage`
2. 用户在 WebView 中登录 DeepSeek 账号
3. 注入的 JavaScript Hook 拦截页面内的 `fetch()` 和 `XMLHttpRequest` 请求
4. 从请求的 `Authorization` header 中提取 Bearer Token
5. 同时主动调用 `/auth-api/v0/users/current` 端点获取 token
6. 通过 WKWebView 的 `httpCookieStore` 提取所有 `deepseek.com` 域名的 Cookie

#### Token 格式
- 长度: 40~256 个字符
- 字符集: `A-Za-z0-9+/._~-` 加末尾可选 `=`
- 不是 JWT(无三段式结构)
- 更像是服务端生成的 opaque session token

#### Cookie 内容
- 从 WebView 的 Cookie Store 中获取
- 过滤条件: `domain.contains("deepseek.com")`
- 序列化为标准 Cookie header 格式: `name1=value1; name2=value2; ...`

---

## 三、HTTP 请求头完整列表

### 需要认证的请求 (includeAuth=true, includeFetchDest=true)

```
GET /api/v0/... HTTP/1.1
Host: platform.deepseek.com
Accept: */*
Accept-Language: zh-CN,zh-Hans;q=0.9        (中文) / en-US,en;q=0.9 (英文)
Accept-Encoding: gzip, deflate, br, zstd
Authorization: Bearer <token>
Cookie: <cookie_header>
Connection: keep-alive
Priority: u=3, i
Referer: https://platform.deepseek.com/usage
Sec-Fetch-Site: same-origin
Sec-Fetch-Mode: cors
Sec-Fetch-Dest: empty
User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.5 Mobile/15E148 Safari/604.1
x-app-version: 1.2.1
```

### 不需要认证的请求 (includeAuth=false)

Banner 设置请求不包含 `Authorization` 和 `Sec-Fetch-Dest` header。

### 服务状态请求 (OfficialStatusClient)

```
GET / HTTP/1.1
Host: status.deepseek.com
Accept: */*
User-Agent: DeepSeekMonitor/1.2.1
```

---

## 四、API 响应结构

所有 DeepSeek API 响应使用统一的三层信封结构:

```json
{
  "code": 0,           // 外层状态码, 0 = 成功
  "msg": "",           // 外层消息
  "data": {
    "biz_code": 0,     // 业务层状态码, 0 = 成功
    "biz_msg": "",     // 业务层消息
    "biz_data": {      // 实际业务数据
      // ... 具体数据
    }
  }
}
```

### 错误判定逻辑
- HTTP 状态码 401/403 -> unauthorized(会话过期)
- `code != 0` -> API 错误
- `biz_code != 0` -> 业务逻辑错误
- 特定消息关键词: `authorization failed`, `invalid token`, `token expired`, `unauthorized`

---

## 五、能否仅用 Cookie 直接调用 API?

### 简短回答: 不能仅用 Cookie, 必须同时有 Bearer Token

### 详细分析

DeepSeek 平台的 API 认证依赖 **Bearer Token**, 而非 Cookie:

1. **Token 是必须的**: DeepSeekClient 在 `rawRequest()` 中检查 `session.token.isEmpty`, 如果为空直接抛出 `missingToken` 错误
2. **Cookie 是辅助的**: Cookie header 仅在 `!session.cookieHeader.isEmpty` 时才添加, 属于可选字段
3. **实际验证靠 Token**: 服务端通过 `Authorization: Bearer <token>` 验证身份

### 但有一个关键路径...

在 LoginSheet.swift 的主动捕获脚本中, 它通过 WebView 内的 JavaScript 调用:

```javascript
const response = await fetch('/auth-api/v0/users/current', {
    method: 'GET',
    credentials: 'include',  // 浏览器自动携带 Cookie
    cache: 'no-store',
    headers: { 'Accept': '*/*', 'x-app-version': '1.2.1' }
});
```

这个调用**不需要**显式传 Bearer Token, 因为 `credentials: 'include'` 让浏览器自动携带 Cookie。**但是**这只能在浏览器上下文中工作(因为浏览器会自动管理 session cookie), 不能通过 curl 等命令行工具仅用 Cookie header 复现。

### 可行的直接调用方式

如果你有一个有效的 Bearer Token, 可以直接用 curl 调用:

```bash
# 获取账户摘要
curl -X GET "https://platform.deepseek.com/api/v0/users/get_user_summary" \
  -H "Authorization: Bearer <your_token>" \
  -H "Cookie: <your_cookie_header>" \
  -H "Accept: */*" \
  -H "Accept-Language: zh-CN,zh-Hans;q=0.9" \
  -H "Referer: https://platform.deepseek.com/usage" \
  -H "x-app-version: 1.2.1" \
  -H "User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15" \
  -H "Sec-Fetch-Site: same-origin" \
  -H "Sec-Fetch-Mode: cors" \
  -H "Sec-Fetch-Dest: empty"

# 获取月度用量
curl -X GET "https://platform.deepseek.com/api/v0/usage/amount?month=6&year=2026" \
  -H "Authorization: Bearer <your_token>" \
  -H "Cookie: <your_cookie_header>" \
  -H "Accept: */*" \
  -H "Referer: https://platform.deepseek.com/usage" \
  -H "x-app-version: 1.2.1"

# 获取月度费用
curl -X GET "https://platform.deepseek.com/api/v0/usage/cost?month=6&year=2026" \
  -H "Authorization: Bearer <your_token>" \
  -H "Cookie: <your_cookie_header>" \
  -H "Accept: */*" \
  -H "Referer: https://platform.deepseek.com/usage" \
  -H "x-app-version: 1.2.1"
```

---

## 六、Token 获取方式

### 方式 1: 通过浏览器 DevTools 手动获取

1. 登录 https://platform.deepseek.com/usage
2. 打开 DevTools (F12) -> Network 标签
3. 刷新页面, 找到任意 API 请求
4. 在请求头中复制 `Authorization: Bearer xxx` 的 token 值
5. 同时复制 `Cookie` header 的完整值

### 方式 2: 通过浏览器控制台

在已登录的 platform.deepseek.com 页面的控制台执行:

```javascript
// 方法 A: 直接调用 API 获取
fetch('/auth-api/v0/users/current', {
    method: 'GET',
    credentials: 'include',
    headers: { 'Accept': '*/*', 'x-app-version': '1.2.1' }
}).then(r => r.json()).then(d => {
    console.log('Token:', d.data?.bizData?.token || d.data?.biz_data?.token);
});

// 方法 B: 检查 localStorage/sessionStorage
for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (/token|auth|bearer|session/i.test(key)) {
        console.log(key, localStorage.getItem(key));
    }
}
```

### 方式 3: 通过 DeepSeekMonitor 应用

1. 安装 DeepSeekMonitor macOS 应用
2. 通过内嵌 WebView 登录
3. 凭证自动保存至 `~/Library/Application Support/DeepSeekMonitor/credentials.json`

---

## 七、Token 生命周期

1. **获取**: 通过 WebView 登录捕获
2. **存储**: 保存到本地 `credentials.json`(token + cookieHeader)
3. **使用**: 每次请求附加 `Authorization: Bearer <token>` + `Cookie` header
4. **自动刷新**: 调用 `/auth-api/v0/users/current` 时, 响应可能包含新 token, 应用自动保存
5. **过期检测**: HTTP 401/403 或 API 返回 `authorization failed`/`invalid token`/`token expired` 消息
6. **过期处理**: 标记为 `expired` 状态, 提示用户重新登录

---

## 八、服务状态 API(无需认证)

DeepSeek 服务状态通过 HTML 页面抓取实现, 不走 JSON API:

- **状态页**: `https://status.deepseek.com/` -- 解析 HTML 获取组件健康状态
- **历史 Atom**: `https://status.deepseek.com/history.atom` -- 解析 Atom feed 获取事件历史

监控的组件:
1. API 服务 (API Service)
2. 网页对话服务 (Web Chat Service)

---

## 九、关键源文件索引

| 文件 | GitHub 路径 | 作用 |
|------|-----------|------|
| DeepSeekClient.swift | Sources/DeepSeekMonitor/Services/ | API 客户端, 定义所有端点和请求逻辑 |
| OfficialStatusClient.swift | Sources/DeepSeekMonitor/Services/ | 服务状态页面抓取 |
| CredentialStore.swift | Sources/DeepSeekMonitor/Services/ | Token/Cookie 持久化存储 |
| MonitorStore.swift | Sources/DeepSeekMonitor/Stores/ | 业务逻辑, 编排 API 调用 |
| LoginSheet.swift | Sources/DeepSeekMonitor/Views/ | WebView 登录 + Token 捕获 |
| DeepSeekAPIResponses.swift | Sources/DeepSeekMonitor/Models/ | API 响应 DTO 定义 |
| DeepSeekModels.swift | Sources/DeepSeekMonitor/Models/ | 业务模型定义 |
