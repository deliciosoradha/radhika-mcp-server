"""Prueba E2E del adaptador LangChain: carga tools MCP -> LangChain y las invoca.

    python tests/langchain_test.py
"""

from __future__ import annotations

import asyncio
import json
import sys

sys.path.insert(0, ".")

from radhika_mcp.langchain_adapter import get_radhika_tools_async

EXPECTED_TOOLS = {
    "listar_recursos",
    "listar_categorias",
    "buscar_recursos",
    "ver_esquema",
    "obtener_muestra",
    "comprar_recurso",
    "saldo_agente",
}


async def main() -> None:
    tools = await get_radhika_tools_async()
    names = {t.name for t in tools}
    print(f"[{'PASS' if EXPECTED_TOOLS <= names else 'FAIL'}] langchain.tools_load — {len(tools)} LangChain tools: {sorted(names)}")
    if not EXPECTED_TOOLS <= names:
        sys.exit(1)

    # verificación de que son LangChain BaseTools reales
    from langchain_core.tools import BaseTool

    assert all(isinstance(t, BaseTool) for t in tools), "las tools no son langchain BaseTool"
    print("[PASS] langchain.base_tools — todas las tools son langchain_core.tools.BaseTool")

    # invocación real: catálogo filtrado por categoría
    listar = next(t for t in tools if t.name == "listar_recursos")
    out = await listar.ainvoke({"categoria": "zero_knowledge"})
    data = json.loads(out) if isinstance(out, str) else out
    if isinstance(data, list) and data and isinstance(data[0], dict) and "text" in data[0]:
        data = json.loads(data[0]["text"])
    ids = [r["id"] for r in data]
    ok = "/zk/stark" in ids and len(ids) >= 4
    print(f"[{'PASS' if ok else 'FAIL'}] langchain.invoke_listar_recursos — zero_knowledge: {ids}")
    if not ok:
        sys.exit(1)

    # invocación real: challenge 402 vía tool LangChain
    esquema = next(t for t in tools if t.name == "ver_esquema")
    out = await esquema.ainvoke({"recurso": "/zk/stark"})
    data = json.loads(out) if isinstance(out, str) else out
    if isinstance(data, list) and data and isinstance(data[0], dict) and "text" in data[0]:
        data = json.loads(data[0]["text"])
    ok = data.get("status") == 402 and data.get("precio", {}).get("network") == "eip155:8453"
    print(f"[{'PASS' if ok else 'FAIL'}] langchain.invoke_ver_esquema — status={data.get('status')} precio={data.get('precio', {}).get('price_usdc')} USDC")
    if not ok:
        sys.exit(1)

    print("\nLANGCHAIN E2E: 4/4 PASS")


if __name__ == "__main__":
    asyncio.run(main())
