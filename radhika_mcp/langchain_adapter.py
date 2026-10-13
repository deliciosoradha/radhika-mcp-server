"""Adaptador LangChain para el MCP server de RadhikaChain x402.

Convierte las herramientas MCP en LangChain tools via langchain-mcp-adapters,
sin exponer ningún secreto. El agente LangChain paga con su propia wallet
via la env RADHIKA_PRIVATE_KEY (solo lectura del entorno por el subprocess).

Uso mínimo (stdio — sube el server como subprocess del agente):

    from radhika_mcp.langchain_adapter import get_radhika_tools

    tools = get_radhika_tools()            # lista de LangChain BaseTools
    for t in tools:
        print(t.name, "-", t.description[:60])

Uso con un agente LangGraph/LangChain:

    from langchain_openai import ChatOpenAI
    from langgraph.prebuilt import create_react_agent

    llm = ChatOpenAI(model="gpt-4o")
    agent = create_react_agent(llm, get_radhika_tools())
    result = agent.invoke(
        {"messages": [("user", "muestra el precio de /zk/stark y cómpralo")]}
    )

Transporte remoto (streamable HTTP) cuando el server esté desplegado:

    tools = get_radhika_tools(url="http://localhost:8808/mcp")

En entornos con event loop activo (Jupyter), usa la variante async:

    tools = await get_radhika_tools_async()
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any


def _client_config(url: str | None) -> dict[str, Any]:
    if url is None:
        return {
            "radhika-x402-server": {
                "transport": "stdio",
                "command": sys.executable,
                "args": ["-m", "radhika_mcp.server"],
            }
        }
    return {
        "radhika-x402-server": {
            "transport": "streamable_http",
            "url": url,
        }
    }


async def get_radhika_tools_async(url: str | None = None) -> list[Any]:
    """Carga las herramientas del MCP server como LangChain tools (coroutine)."""
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError as e:
        raise ImportError(
            "langchain-mcp-adapters no está instalado. "
            "Instálalo con: pip install 'radhika-mcp[langchain]'"
        ) from e

    client = MultiServerMCPClient(connections=_client_config(url))
    return await client.get_tools()


def get_radhika_tools(url: str | None = None) -> list[Any]:
    """Carga las herramientas del MCP server como LangChain tools (bloqueante)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(get_radhika_tools_async(url))
    # Hay un loop activo (Jupyter): devuelve una tarea para await
    return asyncio.ensure_future(get_radhika_tools_async(url))  # type: ignore[return-value]
