"""All investigation and control calls cross a real stdio MCP session."""
import json
import os
import sys
from contextlib import asynccontextmanager
from datetime import timedelta

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@asynccontextmanager
async def connect(scenario, mode, run_id):
    # Do not pass the hosted model credential into the evidence server.
    env = {k: v for k, v in os.environ.items() if k.upper() in {
        "PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE"}}
    env["PYTHONIOENCODING"] = "utf-8"
    params = StdioServerParameters(command=sys.executable,
        args=["-m", "soc_guard.server", "--scenario", scenario, "--mode", mode, "--run-id", run_id], env=env)
    with open(os.devnull, "w") as errors:
        async with stdio_client(params, errlog=errors) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=15)) as session:
                await session.initialize()
                yield session


async def invoke(session, name, args):
    response = await session.call_tool(name, args)
    text = "".join(c.text for c in response.content if c.type == "text")
    if len(text) > 16000:
        raise RuntimeError("MCP output limit")
    if response.isError:
        raise RuntimeError("MCP protocol tool error")
    return json.loads(text)
