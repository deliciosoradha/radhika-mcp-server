"""Suite E2E del MCP server RadhikaChain x402 — se ejecuta contra el gateway vivo.

Cubre: handshake MCP stdio, registro de 8 herramientas, catálogo completo,
challenge 402 real (precio + esquema), muestra gratis con X-Payer, challenge
de compra sin clave (no paga), saldo read-only RPC Base, y adaptador LangChain.

    pip install -e '.[all]'
    python tests/e2e_test.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    tag = "PASS" if ok else "FAIL"
    print(f"[{tag}] {name}" + (f" — {detail}" if detail else ""))
    (PASS if ok else FAIL).append(name)


async def main() -> None:
    server = StdioServerParameters(command=sys.executable, args=["-m", "radhika_mcp.server"])
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            # 1. initialize handshake
            init = await session.initialize()
            sinfo = getattr(init, "serverInfo", None) or getattr(init, "server_info", None)
            proto = getattr(init, "protocolVersion", None) or getattr(init, "protocol_version", None)
            check(
                "mcp.initialize",
                sinfo.name == "radhika-x402-server",
                f"server={sinfo.name} protocol={proto}",
            )

            # 2. tools list
            tools = await session.list_tools()
            names = sorted(t.name for t in tools.tools)
            expected = sorted(
                [
                    "listar_recursos",
                    "listar_categorias",
                    "buscar_recursos",
                    "ver_esquema",
                    "obtener_muestra",
                    "comprar_recurso",
                    "saldo_agente",
                ]
            )
            # langchain_adapter es módulo, no herramienta
            check(
                "mcp.tools_list",
                names == expected,
                f"{len(names)} herramientas: {names}",
            )

            # 3. catálogo completo
            r = await session.call_tool("listar_recursos", {})
            cat = json.loads(r.content[0].text)
            check(
                "listar_recursos",
                len(cat) >= 50,
                f"{len(cat)} recursos en catálogo",
            )

            # 4. categorías
            r = await session.call_tool("listar_categorias", {})
            cats = json.loads(r.content[0].text)
            check(
                "listar_categorias",
                cats["total_recursos"] == len(cat) and len(cats["categorias"]) >= 10,
                f"{cats['total_recursos']} recursos, {len(cats['categorias'])} categorías",
            )

            # 5. búsqueda
            r = await session.call_tool("buscar_recursos", {"consulta": "stark"})
            hits = json.loads(r.content[0].text)
            check(
                "buscar_recursos",
                any(h["id"] == "/zk/stark" for h in hits),
                f"{len(hits)} coincidencias para 'stark'",
            )

            # 6. challenge 402 real (precio + esquema)
            r = await session.call_tool("ver_esquema", {"recurso": "/amenazas/vivas"})
            esquema = json.loads(r.content[0].text)
            precio_ok = (
                esquema.get("precio", {}).get("price_usdc") == 0.825
                and esquema.get("precio", {}).get("network") == "eip155:8453"
                and esquema.get("esquema_salida")
            )
            check(
                "ver_esquema (challenge 402 real)",
                precio_ok,
                f"precio={esquema.get('precio', {}).get('price_usdc')} USDC, red={esquema.get('precio', {}).get('network')}",
            )

            # 7. compra SIN clave privada -> challenge 402, no paga
            os.environ.pop("RADHIKA_PRIVATE_KEY", None)
            r = await session.call_tool("comprar_recurso", {"recurso": "/amenazas/vivas"})
            compra = json.loads(r.content[0].text)
            check(
                "comprar_recurso sin clave -> 402 canónico",
                compra.get("status") == 402
                and compra.get("chain_id") == 8453
                and "challenge" in compra,
                f"status={compra.get('status')} chain_id={compra.get('chain_id')}",
            )

            # 8. saldo_agente read-only (RPC Base público, burn address = 0)
            r = await session.call_tool("saldo_agente", {"wallet_address": "0x0000000000000000000000000000000000000000"})
            saldo = json.loads(r.content[0].text)
            check(
                "saldo_agente (RPC Base read-only)",
                saldo.get("usdc_base", {}).get("balance") == 0.0,
                f"balance burn addr = {saldo.get('usdc_base', {}).get('balance')} USDC",
            )

            # 9. muestra gratis con X-Payer (semántica del gateway, estado vivo del backend)
            r = await session.call_tool(
                "obtener_muestra",
                {"recurso": "/amenazas/vivas", "payer": "0xf5132dacfe1fc1847dc808391791d3bf605532c0"},
            )
            muestra = json.loads(r.content[0].text)
            # wallet 0xf513... ya consumió su muestra: el gateway responde 200 + ok:false
            ok9 = (
                muestra.get("status") == 200
                and muestra.get("muestra_ya_usada") is True
                and isinstance(muestra.get("contenido"), dict)
            )
            check(
                "obtener_muestra (X-Payer, semántica 1-por-wallet)",
                ok9,
                f"status={muestra.get('status')} ya_usada={muestra.get('muestra_ya_usada')} "
                f"gateway={str(muestra.get('contenido'))[:80]}",
            )

    print()
    print(f"RESULTADO: {len(PASS)}/{len(PASS) + len(FAIL)} PASS")
    if FAIL:
        print("FALLOS:", FAIL)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
