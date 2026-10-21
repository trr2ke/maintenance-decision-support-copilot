import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import sys
from threading import Thread

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def test_stdio_discovery_and_real_tool_invocation():
    class FixtureHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps([{"depot_id": "FIXTURE", "name": "Independent depot"}]).encode())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    async def exercise():
        # Independent HTTP fixtures; disable exporting test traces in the child.
        script = "\n".join([
            "from contextlib import contextmanager",
            "from types import SimpleNamespace",
            "from copilot import mcp_server",
            "@contextmanager",
            "def quiet_trace(name):",
            "    yield SimpleNamespace(set_attribute=lambda *a: None, set_status=lambda *a: None)",
            "mcp_server.trace_operation = quiet_trace",
            "mcp_server.mcp.run(transport='stdio')",
        ])
        env = {**os.environ, "PARTS_API_URL": f"http://127.0.0.1:{server.server_port}", "PYTHONDONTWRITEBYTECODE": "1"}
        params = StdioServerParameters(command=sys.executable, args=["-B", "-c", script], env=env)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert {tool.name for tool in tools.tools} == {
                    "query_parts", "query_fleet_data", "search_documents", "query_knowledge_graph",
                }
                result = await session.call_tool("query_parts", {})
                assert not result.isError
                body = result.structuredContent
                assert body["status"] == "ok"
                assert body["data"][0]["records"][0]["depot_id"] == "FIXTURE"

    try:
        asyncio.run(asyncio.wait_for(exercise(), timeout=20))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
