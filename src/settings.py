"""
DeepSeek Monitor - 设置模块（Web 界面，无 tkinter 依赖）
"""
import json
import os
import sys
import threading
import webbrowser
import socket
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from .api import DeepSeekAPI
from .config import DEFAULT_CONFIG

SETTINGS_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DeepSeek Monitor - 设置</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif; background: #f0f2f5; color: #333; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
.card { background: #fff; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); padding: 32px; width: 100%; max-width: 480px; margin: 20px; }
h1 { font-size: 22px; margin-bottom: 4px; }
.subtitle { color: #888; font-size: 13px; margin-bottom: 24px; }
.section { margin-bottom: 20px; }
.section-title { font-size: 13px; font-weight: 600; color: #555; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; }
label { display: block; font-size: 13px; color: #555; margin-bottom: 4px; font-weight: 500; }
input, select { width: 100%; padding: 10px 12px; border: 1.5px solid #d9d9d9; border-radius: 8px; font-size: 14px; transition: border-color .2s; outline: none; font-family: inherit; }
input:focus, select:focus { border-color: #1677ff; box-shadow: 0 0 0 2px rgba(22,119,255,0.1); }
.row { display: flex; gap: 8px; align-items: center; }
.row input { flex: 1; }
.eye-btn { background: none; border: none; cursor: pointer; font-size: 18px; padding: 4px 8px; }
.test-btn { padding: 8px 16px; border: 1.5px solid #1677ff; background: #fff; color: #1677ff; border-radius: 8px; cursor: pointer; font-size: 13px; white-space: nowrap; }
.test-btn:hover { background: #e6f0ff; }
.test-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.test-status { font-size: 13px; margin-left: 8px; }
.test-status.ok { color: #52c41a; }
.test-status.fail { color: #ff4d4f; }
.helper { font-size: 11px; color: #999; margin-top: 4px; }
.actions { margin-top: 28px; display: flex; gap: 12px; justify-content: flex-end; }
.btn { padding: 10px 24px; border-radius: 8px; font-size: 14px; cursor: pointer; border: none; font-weight: 500; transition: all .2s; }
.btn-primary { background: #1677ff; color: #fff; }
.btn-primary:hover { background: #4096ff; }
.btn-cancel { background: #f5f5f5; color: #555; }
.btn-cancel:hover { background: #e8e8e8; }
.toast { position: fixed; top: 20px; right: 20px; padding: 12px 24px; border-radius: 8px; font-size: 14px; color: #fff; animation: slideIn .3s ease; z-index: 1000; }
.toast.success { background: #52c41a; }
.toast.error { background: #ff4d4f; }
@keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
</style>
</head>
<body>
<div class="card">
<h1>⚙️ DeepSeek Monitor</h1>
<p class="subtitle" id="pageSubtitle">设置</p>

<div class="section">
<div class="section-title">API 密钥</div>
<label>DeepSeek API Key</label>
<div class="row">
<input type="password" id="apiKey" placeholder="sk-..." autocomplete="off">
<button class="eye-btn" onclick="toggleKey()" title="显示/隐藏">👁</button>
<button class="test-btn" id="testBtn" onclick="testConnection()">🔍 测试连接</button>
</div>
<span class="test-status" id="testStatus"></span>
<div class="helper">在 <a href="https://platform.deepseek.com/api_keys" target="_blank">platform.deepseek.com/api_keys</a> 创建</div>
</div>

<div class="section">
<div class="section-title">显示设置</div>
<label>货币单位</label>
<select id="currency"><option value="CNY">CNY (¥)</option><option value="USD">USD ($)</option></select>
</div>

<div class="section">
<div class="section-title">刷新设置</div>
<label>自动刷新间隔（秒）</label>
<input type="number" id="interval" min="30" max="3600" step="30">
<div class="helper">建议 300 秒（5 分钟），最短 30 秒</div>
</div>

<div class="section">
<div class="section-title">警告设置</div>
<label>余额不足警告阈值</label>
<input type="number" id="warning" min="1" max="10000" step="1">
<div class="helper">低于此金额时任务栏图标变橙色</div>
</div>

<div class="actions">
<button class="btn btn-cancel" onclick="window.close()" id="cancelBtn">取消</button>
<button class="btn btn-primary" onclick="saveSettings()" id="saveBtn">💾 保存设置</button>
</div>
</div>

<script>
var config = __CONFIG__;
var isFirstRun = __FIRST_RUN__;

document.getElementById('apiKey').value = config.api_key || '';
document.getElementById('currency').value = config.currency || 'CNY';
document.getElementById('interval').value = config.refresh_interval || 300;
document.getElementById('warning').value = config.low_balance_warning || 10;

if (isFirstRun) {
document.getElementById('pageSubtitle').textContent = '首次使用，请设置 DeepSeek API Key';
document.getElementById('cancelBtn').style.display = 'none';
document.getElementById('saveBtn').textContent = '🚀 开始使用';
}

function toggleKey() {
var el = document.getElementById('apiKey');
el.type = el.type === 'password' ? 'text' : 'password';
}

function testConnection() {
var key = document.getElementById('apiKey').value.trim();
var btn = document.getElementById('testBtn');
var status = document.getElementById('testStatus');
if (!key) { status.textContent = '请先输入 API Key'; status.className = 'test-status fail'; return; }
btn.disabled = true; btn.textContent = '测试中...';
status.textContent = '⏳ 测试中...'; status.className = 'test-status';
fetch('/test', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({api_key: key}) })
.then(r => r.json())
.then(data => {
if (data.ok) { status.textContent = '✅ 连接成功'; status.className = 'test-status ok'; }
else { status.textContent = '❌ ' + (data.error || '连接失败'); status.className = 'test-status fail'; }
})
.catch(e => { status.textContent = '❌ 请求失败'; status.className = 'test-status fail'; })
.finally(() => { btn.disabled = false; btn.textContent = '🔍 测试连接'; });
}

function saveSettings() {
var payload = {
api_key: document.getElementById('apiKey').value.trim(),
currency: document.getElementById('currency').value,
refresh_interval: parseInt(document.getElementById('interval').value) || 300,
low_balance_warning: parseFloat(document.getElementById('warning').value) || 10,
};
if (!payload.api_key) { showToast('请输入 API Key', 'error'); return; }
fetch('/save', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) })
.then(r => r.json())
.then(data => {
if (data.ok) { showToast('✅ 设置已保存', 'success'); setTimeout(function(){ window.close(); }, 800); }
else { showToast('保存失败: ' + (data.error || ''), 'error'); }
})
.catch(e => { showToast('保存失败', 'error'); });
}

function showToast(msg, type) {
var t = document.createElement('div'); t.className = 'toast ' + type; t.textContent = msg;
document.body.appendChild(t); setTimeout(function(){ t.remove(); }, 2500);
}
</script>
</body>
</html>"""


def find_free_port():
    """找一个空闲端口"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class SettingsHandler(BaseHTTPRequestHandler):
    """设置页面的 HTTP 请求处理器"""
    config = None
    on_save = None
    is_first_run = False

    def log_message(self, format, *args):
        pass  # 静默日志

    def do_GET(self):
        if self.path == "/":
            html = SETTINGS_HTML.replace(
                "__CONFIG__", json.dumps(self.config)
            ).replace(
                "__FIRST_RUN__", "true" if self.is_first_run else "false"
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        data = json.loads(body)

        if self.path == "/test":
            api = DeepSeekAPI(data["api_key"])
            ok = api.test_connection()
            resp = {"ok": ok}
            if not ok:
                resp["error"] = "API Key 无效或网络不通"
            self._json_response(resp)

        elif self.path == "/save":
            new_config = {**self.config, **data}
            new_config["first_run"] = False
            self.on_save(new_config)
            self._json_response({"ok": True})
            # 异步关闭服务器（不能从请求线程调用 shutdown）
            srv = self.server
            threading.Thread(target=srv.shutdown, daemon=True).start()

        else:
            self._json_response({"ok": False, "error": "unknown path"}, 404)

    def _json_response(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))



def open_settings_window(config, on_save_callback, is_first_run=False):
    """打开设置窗口（启动本地 HTTP 服务 + 打开浏览器）"""

    port = find_free_port()
    server = HTTPServer(("127.0.0.1", port), SettingsHandler)
    SettingsHandler.config = config.copy()
    SettingsHandler.on_save = on_save_callback
    SettingsHandler.is_first_run = is_first_run
    SettingsHandler._server = server

    def serve():
        try:
            server.serve_forever()
        except Exception:
            pass

    t = threading.Thread(target=serve, daemon=True)
    t.start()

    # 打开浏览器
    webbrowser.open(f"http://127.0.0.1:{port}")
