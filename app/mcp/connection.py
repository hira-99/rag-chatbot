"""Subprocess/stdio transport connection handling.

The MCP SDK's client API is async; the rest of this app is sync (Gradio
handlers, the agent loop). This runs one persistent asyncio event loop in
a background thread per server and bridges sync calls into it with
run_coroutine_threadsafe -- reconnecting a subprocess for every tool call
would be slow and pointless when the server can just stay up for the
app's lifetime.
"""
import asyncio
import threading

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPConnection:
    def __init__(self, command, args):
        self._command = command
        self._args = args
        self._loop = None
        self._session = None
        self._stop_event = None
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        """Returns True once the server has responded to initialize(),
        False if it failed to start or connect -- a bad/missing server
        shouldn't take the rest of the assistant down (Step 24's item 10)."""
        self._thread.start()
        self._ready.wait(timeout=15)
        return self._session is not None

    def _run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._connect_and_serve())

    async def _connect_and_serve(self):
        params = StdioServerParameters(command=self._command, args=self._args)
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    self._session = session
                    self._stop_event = asyncio.Event()
                    self._ready.set()
                    await self._stop_event.wait()
        except Exception as exc:
            print(f"[mcp] connection failed: {exc}")
            self._ready.set()

    def call(self, coro_fn, *args, **kwargs):
        """Runs coro_fn(session, *args, **kwargs) on the connection's own
        loop and blocks the calling (sync) thread for the result."""
        if self._session is None:
            raise RuntimeError("MCP connection not started")
        future = asyncio.run_coroutine_threadsafe(coro_fn(self._session, *args, **kwargs), self._loop)
        return future.result(timeout=30)

    def stop(self):
        if self._loop and self._stop_event:
            self._loop.call_soon_threadsafe(self._stop_event.set)
