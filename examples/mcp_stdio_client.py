"""Cliente mínimo del MCP server de RadhikaChain via stdio, sin LangChain."""

import asyncio
import json

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    server = StdioServerParameters(command="python", args=["-m", "radhika_mcp.server"])
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("herramientas:", [t.name for t in tools.tools])

            result = await session.call_tool("listar_categorias", {})
            payload = json.loads(result.content[0].text)
            print("total recursos:", payload["total_recursos"])
            print("categorías:", payload["categorias"])


if __name__ == "__main__":
    asyncio.run(main())
