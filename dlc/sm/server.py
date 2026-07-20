"""DLC v3.0 MCP Server — 三工具接口。

暴露 execute / get_state / reset 三个 MCP 工具。
状态机纯计算，输出叙事编号；叙事组装走独立的 Python 脚本。

Usage (MCP config):
    "dlc-card": {
        "command": "python",
        "args": ["-m", "dlc.sm.server", "--card", "cards/my-card"]
    }
"""
from __future__ import annotations

import os, sys, json, argparse
from pathlib import Path

# Ensure dlc is importable
_skill_dir = Path(__file__).resolve().parent.parent.parent
if str(_skill_dir) not in sys.path:
    sys.path.insert(0, str(_skill_dir))

from dlc.sm.engine import StateMachineEngine

# Global engine instance (persistent across MCP calls)
_engine: StateMachineEngine | None = None


def _get_engine(card_path: str) -> StateMachineEngine:
    global _engine
    if _engine is None or _engine.card_path != card_path:
        _engine = StateMachineEngine(card_path)
    return _engine


# ═══════════════════════════════════════════════════════════════
# CLI Entry (for MCP stdio protocol)
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="DLC v3.0 MCP Server")
    parser.add_argument("--card", required=True, help="卡片路径")
    parser.add_argument("--port", type=int, help="HTTP 模式端口（可选，默认 stdio）")
    args = parser.parse_args()

    card_path = os.path.abspath(args.card)

    if args.port:
        _run_http(card_path, args.port)
    else:
        _run_stdio(card_path)


def _run_stdio(card_path: str):
    """MCP stdio 协议（默认模式）。"""
    import sys as _sys

    engine = _get_engine(card_path)

    for line in _sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = request.get("method", "")
        req_id = request.get("id")

        if method == "tools/list":
            response = _handle_list(req_id)
        elif method == "tools/call":
            tool_name = request.get("params", {}).get("name", "")
            tool_args = request.get("params", {}).get("arguments", {})
            response = _handle_call(req_id, tool_name, tool_args, engine)
        elif method == "initialize":
            response = {"jsonrpc": "2.0", "id": req_id, "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "dlc-v3", "version": "3.0.0"},
            }}
        else:
            response = {"jsonrpc": "2.0", "id": req_id,
                        "error": {"code": -32601, "message": f"Unknown method: {method}"}}

        _sys.stdout.write(json.dumps(response) + "\n")
        _sys.stdout.flush()


def _run_http(card_path: str, port: int):
    """HTTP API 模式（开发调试用）。"""
    from http.server import HTTPServer, BaseHTTPRequestHandler

    engine = _get_engine(card_path)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            try:
                req = json.loads(body)
            except json.JSONDecodeError:
                self._send_json(400, {"error": "Invalid JSON"})
                return

            tool_name = req.get("tool", req.get("name", ""))
            tool_args = req.get("arguments", req.get("args", {}))

            result = _dispatch_tool(tool_name, tool_args, engine)
            self._send_json(200, result)

        def do_GET(self):
            if self.path == "/health":
                self._send_json(200, {"status": "ok", "card": card_path})
            elif self.path == "/state":
                self._send_json(200, engine.get_state())
            else:
                self._send_json(404, {"error": "Not found"})

        def _send_json(self, code, data):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            pass  # Silent

    print(f"DLC v3.0 MCP Server (HTTP) — {card_path} :{port}")
    server = HTTPServer(("127.0.0.1", port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


def _handle_list(req_id) -> dict:
    tools = [
        {
            "name": "execute",
            "description": "执行命令，返回叙事编号和状态变更。状态机纯计算，零自然语言。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "command": {"type": "string",
                                 "description": "命令 ID（如 act/move/use）"},
                    "params": {"type": "object",
                                "description": "可选参数（如 {\"count\": 2}）"},
                },
                "required": ["command"],
            },
        },
        {
            "name": "get_state",
            "description": "获取当前实体状态快照（纯数据，无叙事）。",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "reset",
            "description": "重置所有实体状态到初始值。",
            "inputSchema": {"type": "object", "properties": {}},
        },
    ]
    return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}}


def _handle_call(req_id: str, tool_name: str, tool_args: dict,
                  engine: StateMachineEngine) -> dict:
    result = _dispatch_tool(tool_name, tool_args, engine)
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
        },
    }


def _dispatch_tool(tool_name: str, tool_args: dict,
                    engine: StateMachineEngine) -> dict:
    if tool_name == "execute":
        cmd = tool_args.get("command", "")
        params = tool_args.get("params", {})
        return engine.execute(cmd, params)

    elif tool_name == "get_state":
        return engine.get_state()

    elif tool_name == "reset":
        return engine.reset()

    else:
        return {"error": f"Unknown tool: {tool_name}"}


if __name__ == "__main__":
    main()
