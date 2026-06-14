"""
API Monitor - Web 设置界面
本地 HTTP 服务 + 浏览器自动打开，支持多平台配置
"""
import json
import threading
import webbrowser
import socket
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

from .models import AccountConfig
from .providers import ALL_PROVIDERS, create_provider, get_provider_label

logger = logging.getLogger("api-monitor")


def find_free_port():
    """找一个空闲端口"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def mask_api_key(key: str) -> str:
    """API Key 脱敏：只显示前4位和后4位"""
    if not key or len(key) <= 10:
        return "****"
    return key[:4] + "****" + key[-4:]


SETTINGS_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>API Monitor - 设置</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif; background: #f0f2f5; color: #333; min-height: 100vh; padding: 20px; }
.container { max-width: 720px; margin: 0 auto; }
h1 { font-size: 22px; margin-bottom: 4px; }
.subtitle { color: #888; font-size: 13px; margin-bottom: 24px; }
.card { background: #fff; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); padding: 24px; margin-bottom: 16px; }
.section-title { font-size: 14px; font-weight: 600; color: #555; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
label { display: block; font-size: 13px; color: #555; margin-bottom: 4px; font-weight: 500; }
input, select { width: 100%; padding: 9px 12px; border: 1.5px solid #d9d9d9; border-radius: 8px; font-size: 14px; transition: border-color .2s; outline: none; font-family: inherit; }
input:focus, select:focus { border-color: #1677ff; box-shadow: 0 0 0 2px rgba(22,119,255,0.1); }
.row { display: flex; gap: 8px; align-items: center; }
.row input { flex: 1; }
.helper { font-size: 11px; color: #999; margin-top: 4px; }
.btn { padding: 8px 16px; border-radius: 8px; font-size: 13px; cursor: pointer; border: none; font-weight: 500; transition: all .2s; }
.btn-primary { background: #1677ff; color: #fff; }
.btn-primary:hover { background: #4096ff; }
.btn-danger { background: #ff4d4f; color: #fff; }
.btn-danger:hover { background: #ff7875; }
.btn-sm { padding: 5px 12px; font-size: 12px; }
.btn-outline { background: #fff; color: #1677ff; border: 1.5px solid #1677ff; }
.btn-outline:hover { background: #e6f0ff; }
.btn-ghost { background: #f5f5f5; color: #555; }
.btn-ghost:hover { background: #e8e8e8; }
.actions { margin-top: 16px; display: flex; gap: 8px; justify-content: flex-end; }
.account-card { border: 1px solid #e8e8e8; border-radius: 10px; padding: 16px; margin-bottom: 12px; position: relative; }
.account-card.disabled { opacity: 0.6; }
.account-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.account-name { font-size: 15px; font-weight: 600; }
.account-type { font-size: 12px; color: #888; background: #f0f0f0; padding: 2px 8px; border-radius: 4px; }
.account-actions { display: flex; gap: 6px; }
.toggle { position: relative; width: 40px; height: 22px; }
.toggle input { opacity: 0; width: 0; height: 0; }
.toggle .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background: #ccc; border-radius: 22px; transition: .3s; }
.toggle .slider:before { position: absolute; content: ""; height: 18px; width: 18px; left: 2px; bottom: 2px; background: #fff; border-radius: 50%; transition: .3s; }
.toggle input:checked + .slider { background: #1677ff; }
.toggle input:checked + .slider:before { transform: translateX(18px); }
.field-group { margin-bottom: 8px; }
.test-status { font-size: 13px; margin-left: 8px; }
.test-status.ok { color: #52c41a; }
.test-status.fail { color: #ff4d4f; }
.toast { position: fixed; top: 20px; right: 20px; padding: 12px 24px; border-radius: 8px; font-size: 14px; color: #fff; animation: slideIn .3s ease; z-index: 1000; }
.toast.success { background: #52c41a; }
.toast.error { background: #ff4d4f; }
@keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
.add-form { display: none; margin-top: 12px; padding: 16px; background: #fafafa; border-radius: 8px; border: 1px dashed #d9d9d9; }
.add-form.visible { display: block; }
.edit-form { display: none; margin-top: 8px; }
.edit-form.visible { display: block; }
</style>
</head>
<body>
<div class="container">
<h1>API Monitor</h1>
<p class="subtitle">多平台 API 监控设置</p>

<!-- 全局设置 -->
<div class="card">
<div class="section-title">全局设置</div>
<div class="field-group">
<label>自动刷新间隔（秒）</label>
<input type="number" id="refreshInterval" min="30" max="3600" step="30">
<div class="helper">建议 300 秒（5 分钟），最短 30 秒</div>
</div>
<div class="field-group">
<label>百分比类平台预警阈值（剩余 %）</label>
<input type="number" id="warnPercent" min="0" max="100" step="1">
<div class="helper">剩余百分比低于此值时显示橙色警告</div>
</div>
<div class="field-group">
<label>百分比类平台严重阈值（剩余 %）</label>
<input type="number" id="critPercent" min="0" max="100" step="1">
<div class="helper">剩余百分比低于此值时显示红色错误</div>
</div>
<div class="field-group">
<label>金额类平台预警阈值（元）</label>
<input type="number" id="warnBalance" min="0" step="1">
<div class="helper">余额低于此金额时显示橙色警告</div>
</div>
<div class="field-group">
<label>图标显示策略</label>
<select id="iconDisplay">
<option value="worst">最差状态（推荐）</option>
<option value="primary">首个账号</option>
</select>
</div>
</div>

<!-- 账号列表 -->
<div class="card">
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
<div class="section-title" style="margin-bottom:0;">账号列表</div>
<button class="btn btn-outline btn-sm" onclick="toggleAddForm()">+ 添加账号</button>
</div>

<div id="accountList"></div>

<div id="addForm" class="add-form">
<div class="field-group">
<label>平台类型</label>
<select id="addType" onchange="onTypeChange()">
</select>
</div>
<div class="field-group">
<label>显示名称</label>
<input type="text" id="addName" placeholder="如: 我的 DeepSeek 账号">
</div>
<div class="field-group">
<label id="addKeyLabel">API Key</label>
<input type="text" id="addApiKey" placeholder="sk-...">
<div class="helper" id="addKeyHelper"></div>
</div>
<div class="field-group" id="addCookieGroup" style="display:none;">
<label style="font-weight:600;margin-bottom:8px;">Cookie 字段（从浏览器 DevTools 获取）</label>
<div class="field-group">
<label>userId</label>
<input type="text" id="addCookieUserId" placeholder="从 Cookie 中获取 userId 的值">
</div>
<div class="field-group">
<label>serviceToken</label>
<input type="text" id="addCookieServiceToken" placeholder="从 Cookie 中获取 serviceToken 的值">
</div>
<div class="field-group">
<label>api-platform_serviceToken</label>
<input type="text" id="addCookieApiPlatformST" placeholder="从 Cookie 中获取 api-platform_serviceToken 的值">
</div>
<div class="helper">打开 platform.xiaomimimo.com → F12 → Application → Cookies，复制对应字段的值填入即可</div>
</div>
<div class="field-group">
<label>自定义预警阈值（可选，留空使用全局设置）</label>
<input type="number" id="addThreshold" placeholder="" step="0.1">
</div>
<div class="actions">
<button class="btn btn-ghost btn-sm" onclick="toggleAddForm()">取消</button>
<button class="btn btn-primary btn-sm" onclick="addAccount()">添加</button>
</div>
</div>
</div>

<!-- 保存 -->
<div class="card">
<div class="actions">
<button class="btn btn-primary" onclick="saveSettings()">保存设置</button>
</div>
</div>
</div>

<script>
var config = __CONFIG__;
var providerTypes = __PROVIDERS__;

// 初始化全局设置
var g = config.global || {};
document.getElementById('refreshInterval').value = g.refresh_interval || 300;
document.getElementById('warnPercent').value = g.warning_threshold_percent || 20;
document.getElementById('critPercent').value = g.critical_threshold_percent || 5;
document.getElementById('warnBalance').value = g.warning_threshold_balance || 10;
document.getElementById('iconDisplay').value = g.icon_display || 'worst';

// 初始化平台类型下拉
var typeSelect = document.getElementById('addType');
providerTypes.forEach(function(p) {
    var opt = document.createElement('option');
    opt.value = p.type;
    opt.textContent = p.label;
    typeSelect.appendChild(opt);
});

// 渲染账号列表
function renderAccounts() {
    var list = document.getElementById('accountList');
    list.innerHTML = '';
    var accounts = config.accounts || [];
    if (accounts.length === 0) {
        list.innerHTML = '<div style="text-align:center;color:#999;padding:20px;">暂无账号，点击上方按钮添加</div>';
        return;
    }
    accounts.forEach(function(acc, idx) {
        var providerLabel = acc.type;
        providerTypes.forEach(function(p) { if (p.type === acc.type) providerLabel = p.label; });
        var maskedKey = acc.api_key ? acc.api_key.substring(0,4) + '****' + acc.api_key.substring(acc.api_key.length-4) : '****';

        var card = document.createElement('div');
        card.className = 'account-card' + (acc.enabled ? '' : ' disabled');
        card.innerHTML =
            '<div class="account-header">' +
                '<div>' +
                    '<span class="account-name">' + escHtml(acc.name) + '</span> ' +
                    '<span class="account-type">' + escHtml(providerLabel) + '</span>' +
                '</div>' +
                '<div class="account-actions">' +
                    '<label class="toggle"><input type="checkbox" ' + (acc.enabled ? 'checked' : '') + ' onchange="toggleAccount(' + idx + ', this.checked)"><span class="slider"></span></label>' +
                    '<button class="btn btn-outline btn-sm" onclick="toggleEdit(' + idx + ')">编辑</button>' +
                    '<button class="btn btn-danger btn-sm" onclick="deleteAccount(' + idx + ')">删除</button>' +
                '</div>' +
            '</div>' +
            '<div style="font-size:13px;color:#666;">' + (acc.type === 'mimo' && acc.extra ? ('Cookie: ' + escHtml(_mimoCookiePreview(acc.extra))) : 'API Key: ' + escHtml(maskedKey)) + '</div>' +
            (acc.warning_threshold != null ? '<div style="font-size:12px;color:#888;">自定义阈值: ' + acc.warning_threshold + '</div>' : '') +
            '<div id="editForm_' + idx + '" class="edit-form">' +
                '<div class="field-group"><label>名称</label><input type="text" id="editName_' + idx + '" value="' + escAttr(acc.name) + '"></div>' +
                '<div class="field-group"><label>' + (acc.type === 'mimo' ? 'API Key（仅标识）' : 'API Key') + '</label><input type="text" id="editKey_' + idx + '" value="' + escAttr(acc.api_key) + '" placeholder="留空保持不变"></div>' +
                (acc.type === 'mimo' ? '<div class="field-group"><label style="font-weight:600;">Cookie 字段</label><div class="field-group"><label>userId</label><input type="text" id="editCookie_userId_' + idx + '" value="' + escAttr(acc.extra && acc.extra.cookie_userId ? acc.extra.cookie_userId : '') + '" placeholder="userId 的值"></div><div class="field-group"><label>serviceToken</label><input type="text" id="editCookie_serviceToken_' + idx + '" value="' + escAttr(acc.extra && acc.extra.cookie_serviceToken ? acc.extra.cookie_serviceToken : '') + '" placeholder="serviceToken 的值"></div><div class="field-group"><label>api-platform_serviceToken</label><input type="text" id="editCookie_api_platform_serviceToken_' + idx + '" value="' + escAttr(acc.extra && acc.extra.cookie_api_platform_serviceToken ? acc.extra.cookie_api_platform_serviceToken : '') + '" placeholder="api-platform_serviceToken 的值"></div><div class="helper">Cookie 有效期约 24 小时，过期需重新获取</div></div>' : '') +
                '<div class="field-group"><label>自定义预警阈值（留空使用全局）</label><input type="number" id="editThreshold_' + idx + '" value="' + (acc.warning_threshold != null ? acc.warning_threshold : '') + '" step="0.1"></div>' +
                '<div class="row" style="margin-top:8px;">' +
                    '<button class="btn btn-primary btn-sm" onclick="saveEdit(' + idx + ')">保存</button>' +
                    '<button class="btn btn-sm btn-ghost" onclick="toggleEdit(' + idx + ')">取消</button>' +
                    '<button class="btn btn-outline btn-sm" onclick="testAccount(' + idx + ')">测试连接</button>' +
                    '<span id="testStatus_' + idx + '" class="test-status"></span>' +
                '</div>' +
            '</div>';
        list.appendChild(card);
    });
}

renderAccounts();

function toggleAddForm() {
    var f = document.getElementById('addForm');
    f.classList.toggle('visible');
}

function onTypeChange() {
    var type = document.getElementById('addType').value;
    var label = type;
    providerTypes.forEach(function(p) { if (p.type === type) label = p.label; });
    document.getElementById('addName').placeholder = label + ' 账号';

    // MiMo 使用 Cookie 认证，其他使用 API Key
    var isCookie = (type === 'mimo');
    document.getElementById('addKeyLabel').textContent = isCookie ? 'API Key（仅标识用）' : 'API Key';
    document.getElementById('addApiKey').placeholder = isCookie ? 'tp-... (仅用于标识)' : 'sk-...';
    document.getElementById('addKeyHelper').textContent = isCookie ? 'MiMo 用量查询需要 Cookie，请在下方填写' : '';
    document.getElementById('addCookieGroup').style.display = isCookie ? 'block' : 'none';
}

function addAccount() {
    var type = document.getElementById('addType').value;
    var name = document.getElementById('addName').value.trim();
    var apiKey = document.getElementById('addApiKey').value.trim();
    var threshold = document.getElementById('addThreshold').value;

    if (!name) { showToast('请输入名称', 'error'); return; }
    if (!apiKey && type !== 'mimo') { showToast('请输入 API Key', 'error'); return; }

    // MiMo Cookie 分字段验证
    if (type === 'mimo') {
        var st = document.getElementById('addCookieServiceToken').value.trim();
        var uid = document.getElementById('addCookieUserId').value.trim();
        if (!st && !uid) { showToast('请至少填写一个 Cookie 字段', 'error'); return; }
    }

    // 生成唯一 ID
    var existing = (config.accounts || []).filter(function(a) { return a.type === type; });
    var id = type + '_' + (existing.length + 1);

    var acc = { id: id, type: type, name: name, api_key: apiKey, enabled: true, warning_threshold: null, extra: {} };
    // MiMo: 存储分字段 Cookie
    if (type === 'mimo') {
        var cookieFields = {
            cookie_userId: document.getElementById('addCookieUserId').value.trim(),
            cookie_serviceToken: document.getElementById('addCookieServiceToken').value.trim(),
            cookie_api_platform_serviceToken: document.getElementById('addCookieApiPlatformST').value.trim()
        };
        Object.keys(cookieFields).forEach(function(k) {
            if (cookieFields[k]) acc.extra[k] = cookieFields[k];
        });
    }
    if (threshold !== '') {
        acc.warning_threshold = parseFloat(threshold);
    }

    config.accounts = config.accounts || [];
    config.accounts.push(acc);

    document.getElementById('addName').value = '';
    document.getElementById('addApiKey').value = '';
    document.getElementById('addCookieUserId').value = '';
    document.getElementById('addCookieServiceToken').value = '';
    document.getElementById('addCookieApiPlatformST').value = '';
    document.getElementById('addThreshold').value = '';
    toggleAddForm();
    renderAccounts();
    showToast('账号已添加', 'success');
}

function deleteAccount(idx) {
    if (!confirm('确定删除此账号？')) return;
    config.accounts.splice(idx, 1);
    renderAccounts();
    showToast('已删除', 'success');
}

function toggleAccount(idx, enabled) {
    config.accounts[idx].enabled = enabled;
    renderAccounts();
}

function toggleEdit(idx) {
    var form = document.getElementById('editForm_' + idx);
    if (form) form.classList.toggle('visible');
}

function saveEdit(idx) {
    var acc = config.accounts[idx];
    var name = document.getElementById('editName_' + idx).value.trim();
    var key = document.getElementById('editKey_' + idx).value.trim();
    var threshold = document.getElementById('editThreshold_' + idx).value;

    if (!name) { showToast('名称不能为空', 'error'); return; }
    acc.name = name;
    if (key) acc.api_key = key;
    acc.warning_threshold = threshold !== '' ? parseFloat(threshold) : null;

    // MiMo Cookie 编辑（分字段）
    if (acc.type === 'mimo') {
        if (!acc.extra) acc.extra = {};
        var cookieFieldIds = [
            ['cookie_userId', 'editCookie_userId_'],
            ['cookie_serviceToken', 'editCookie_serviceToken_'],
            ['cookie_api_platform_serviceToken', 'editCookie_api_platform_serviceToken_']
        ];
        cookieFieldIds.forEach(function(pair) {
            var el = document.getElementById(pair[1] + idx);
            if (el) {
                var val = el.value.trim();
                if (val) {
                    acc.extra[pair[0]] = val;
                } else {
                    delete acc.extra[pair[0]];
                }
            }
        });
        // 清理旧格式 cookie 字段（迁移后不再需要）
        delete acc.extra.cookie;
    }

    renderAccounts();
    showToast('已更新', 'success');
}

function testAccount(idx) {
    var acc = config.accounts[idx];
    var key = document.getElementById('editKey_' + idx);
    var apiKey = key ? key.value.trim() : acc.api_key;
    if (!apiKey) apiKey = acc.api_key;
    var statusEl = document.getElementById('testStatus_' + idx);
    statusEl.textContent = 'Testing...';
    statusEl.className = 'test-status';

    // MiMo 需要传 Cookie（分字段拼成字符串）
    var cookie = '';
    if (acc.type === 'mimo') {
        var cookieParts = [];
        var cookieFieldIds = [
            ['cookie_userId', 'editCookie_userId_'],
            ['cookie_serviceToken', 'editCookie_serviceToken_'],
            ['cookie_api_platform_serviceToken', 'editCookie_api_platform_serviceToken_']
        ];
        cookieFieldIds.forEach(function(pair) {
            var el = document.getElementById(pair[1] + idx);
            var val = el ? el.value.trim() : (acc.extra && acc.extra[pair[0]] ? acc.extra[pair[0]] : '');
            if (val) {
                // pair[0] 形如 cookie_userId → Cookie key 是 userId
                var cookieKey = pair[0].replace(/^cookie_/, '').replace(/_/, '_');
                // cookie_api_platform_serviceToken → api-platform_serviceToken
                if (cookieKey === 'api_platform_serviceToken') cookieKey = 'api-platform_serviceToken';
                cookieParts.push(cookieKey + '=' + val);
            }
        });
        // 兼容：如果没有分字段但旧格式 cookie 存在
        if (!cookieParts.length && acc.extra && acc.extra.cookie) {
            cookie = acc.extra.cookie;
        } else {
            cookie = cookieParts.join('; ');
        }
    }

    var testBody = {type: acc.type, api_key: apiKey, cookie: cookie};
    // MiMo: 同时传递分字段（优先级高于 cookie 字符串）
    if (acc.type === 'mimo') {
        var fieldMap = [
            ['cookie_userId', 'editCookie_userId_'],
            ['cookie_serviceToken', 'editCookie_serviceToken_'],
            ['cookie_api_platform_serviceToken', 'editCookie_api_platform_serviceToken_']
        ];
        fieldMap.forEach(function(pair) {
            var el = document.getElementById(pair[1] + idx);
            var val = el ? el.value.trim() : (acc.extra && acc.extra[pair[0]] ? acc.extra[pair[0]] : '');
            if (val) testBody[pair[0]] = val;
        });
    }

    fetch('/api/test', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify(testBody)
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.ok) {
            statusEl.textContent = 'OK';
            statusEl.className = 'test-status ok';
        } else {
            statusEl.textContent = data.error || 'Failed';
            statusEl.className = 'test-status fail';
        }
    })
    .catch(function() {
        statusEl.textContent = 'Error';
        statusEl.className = 'test-status fail';
    });
}

function saveSettings() {
    config.global = {
        refresh_interval: parseInt(document.getElementById('refreshInterval').value) || 300,
        warning_threshold_percent: parseFloat(document.getElementById('warnPercent').value) || 20,
        critical_threshold_percent: parseFloat(document.getElementById('critPercent').value) || 5,
        warning_threshold_balance: parseFloat(document.getElementById('warnBalance').value) || 10,
        icon_display: document.getElementById('iconDisplay').value,
    };
    config.version = 2;

    fetch('/api/config', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify(config)
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.ok) {
            showToast('设置已保存', 'success');
            setTimeout(function() { window.close(); }, 800);
        } else {
            showToast('保存失败: ' + (data.error || ''), 'error');
        }
    })
    .catch(function() { showToast('保存失败', 'error'); });
}

function escHtml(s) { var d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
function escAttr(s) { return String(s).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function _mimoCookiePreview(extra) {
    if (!extra) return '(未设置)';
    var parts = [];
    if (extra.cookie_userId) parts.push('userId=已填');
    if (extra.cookie_serviceToken) parts.push('serviceToken=已填');
    if (extra.cookie_api_platform_serviceToken) parts.push('api-platform_serviceToken=已填');
    if (parts.length) return parts.join(', ');
    if (extra.cookie) return extra.cookie.substring(0, 20) + '...';
    return '(未设置)';
}

function showToast(msg, type) {
    var t = document.createElement('div'); t.className = 'toast ' + type; t.textContent = msg;
    document.body.appendChild(t); setTimeout(function(){ t.remove(); }, 2500);
}
</script>
</body>
</html>"""


class SettingsHandler(BaseHTTPRequestHandler):
    """设置页面的 HTTP 请求处理器"""
    config = None
    on_save = None

    def log_message(self, format, *args):
        pass  # 静默日志

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._serve_html()
        elif parsed.path == "/api/config":
            self._serve_config()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._json_response({"ok": False, "error": "Invalid JSON"}, 400)
            return

        parsed = urlparse(self.path)
        if parsed.path == "/api/config":
            self._handle_save(data)
        elif parsed.path == "/api/test":
            self._handle_test(data)
        else:
            self._json_response({"ok": False, "error": "Unknown path"}, 404)

    def _serve_html(self):
        """提供设置页面 HTML"""
        providers_info = [
            {"type": t, "label": cls.PROVIDER_LABEL}
            for t, cls in ALL_PROVIDERS.items()
        ]

        # 脱敏配置用于前端显示
        safe_config = json.loads(json.dumps(self.config))
        for acc in safe_config.get("accounts", []):
            if acc.get("api_key"):
                acc["api_key_masked"] = mask_api_key(acc["api_key"])

        html = SETTINGS_HTML.replace(
            "__CONFIG__", json.dumps(safe_config, ensure_ascii=False)
        ).replace(
            "__PROVIDERS__", json.dumps(providers_info, ensure_ascii=False)
        )

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _serve_config(self):
        """返回当前配置（API Key 脱敏）"""
        safe_config = json.loads(json.dumps(self.config))
        for acc in safe_config.get("accounts", []):
            if acc.get("api_key"):
                acc["api_key_masked"] = mask_api_key(acc["api_key"])
                del acc["api_key"]
        self._json_response(safe_config)

    def _handle_save(self, data: dict):
        """保存配置"""
        try:
            new_config = data
            new_config["first_run"] = False
            if self.on_save:
                self.on_save(new_config)
            self._json_response({"ok": True})
            # 异步关闭服务器
            srv = self.server
            threading.Thread(target=srv.shutdown, daemon=True).start()
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            self._json_response({"ok": False, "error": str(e)}, 500)

    def _handle_test(self, data: dict):
        """测试 API Key 连通性"""
        provider_type = data.get("type", "")
        api_key = data.get("api_key", "")
        cookie = data.get("cookie", "")
        # MiMo 分字段格式
        cookie_userId = data.get("cookie_userId", "")
        cookie_serviceToken = data.get("cookie_serviceToken", "")
        cookie_api_platform_serviceToken = data.get("cookie_api_platform_serviceToken", "")

        if not provider_type:
            self._json_response({"ok": False, "error": "缺少参数"})
            return

        try:
            # 临时创建 Provider 实例测试连接
            extra = {}
            if cookie:
                extra["cookie"] = cookie
            if cookie_userId:
                extra["cookie_userId"] = cookie_userId
            if cookie_serviceToken:
                extra["cookie_serviceToken"] = cookie_serviceToken
            if cookie_api_platform_serviceToken:
                extra["cookie_api_platform_serviceToken"] = cookie_api_platform_serviceToken

            temp_account = AccountConfig(
                id="test",
                type=provider_type,
                name="Test",
                api_key=api_key,
                extra=extra,
            )
            provider = create_provider(temp_account)
            ok, msg = provider.test_connection()
            self._json_response({"ok": ok, "error": "" if ok else msg})
        except Exception as e:
            self._json_response({"ok": False, "error": str(e)})

    def _json_response(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))


def open_settings_window(config: dict, on_save_callback, is_first_run=False):
    """打开设置窗口（启动本地 HTTP 服务 + 打开浏览器）"""
    port = find_free_port()
    server = HTTPServer(("127.0.0.1", port), SettingsHandler)
    SettingsHandler.config = config.copy()
    SettingsHandler.on_save = on_save_callback

    def serve():
        try:
            server.serve_forever()
        except Exception:
            pass

    t = threading.Thread(target=serve, daemon=True)
    t.start()

    webbrowser.open(f"http://127.0.0.1:{port}")
    logger.info(f"设置页面已启动: http://127.0.0.1:{port}")
