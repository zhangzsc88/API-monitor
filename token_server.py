#!/usr/bin/env python3
"""
DeepSeek Monitor - Token API Server
运行在云服务器上，提供 HTTP 接口供 Windows Monitor 查询今日 Token 消耗
用法: python3 token_server.py [--port 18799] [--token my_secret]

安全: 建议用 --token 设置简单的鉴权密钥
"""
import json
import sys
import os
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import date, timezone, timedelta

CST = timezone(timedelta(hours=8))

# 添加 src 到 path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from session_tracker import scan_today_tokens, get_cached_total


class TokenHandler(BaseHTTPRequestHandler):
    auth_token = None

    def log_message(self, format, *args):
        pass  # 静默

    def _check_auth(self):
        if not self.auth_token:
            return True
        auth = self.headers.get("Authorization", "")
        return auth == f"Bearer {self.auth_token}"

    def _json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def do_GET(self):
        if not self._check_auth():
            self._json({"error": "unauthorized"}, 401)
            return

        if self.path == "/tokens" or self.path == "/":
            now = date.today().isoformat()
            # 增量扫描收集新数据，返回缓存的累计总额
            scan_today_tokens()
            cached = get_cached_total()
            data = {
                "date": now,
                "total_tokens": cached,
            }
            self._json(data)

        elif self.path == "/refresh":
            result = scan_today_tokens(full_scan=True)
            data = {
                "date": date.today().isoformat(),
                "total_tokens": result["total_tokens"],
                "scan_time_ms": result["scan_time_ms"],
            }
            self._json(data)

        elif self.path == "/health":
            self._json({"status": "ok", "timestamp": date.today().isoformat()})

        else:
            self._json({"error": "not found"}, 404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization")
        self.end_headers()


def main():
    parser = argparse.ArgumentParser(description="DeepSeek Monitor Token API Server")
    parser.add_argument("--port", type=int, default=18799, help="监听端口 (默认 18799)")
    parser.add_argument("--token", type=str, default="", help="鉴权密钥（Bearer Token）")
    parser.add_argument("--bind", type=str, default="0.0.0.0", help="绑定地址 (默认 0.0.0.0)")
    args = parser.parse_args()

    TokenHandler.auth_token = args.token

    server = HTTPServer((args.bind, args.port), TokenHandler)
    print(f"🔍 DeepSeek Monitor Token API")
    print(f"   监听: http://{args.bind}:{args.port}")
    print(f"   端点: GET /tokens")
    if args.token:
        print(f"   鉴权: Bearer {args.token[:8]}...")
    else:
        print(f"   ⚠️  未设置鉴权密钥，任何人可以访问")
    print(f"   按 Ctrl+C 停止")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n停止服务")
        server.shutdown()


if __name__ == "__main__":
    main()
