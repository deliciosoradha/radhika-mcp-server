"""RadhikaChain x402 MCP Server — servidor MCP limpio, sin secretos.

Herramientas de consulta + liquidación x402 con el SDK oficial (x402.org).
La clave privada del agente NUNCA se almacena: el usuario la provee via
RADHIKA_PRIVATE_KEY (env efímera) y solo se usa para firmar el EIP-3009.
"""

from __future__ import annotations

import json
import os
import sys

import httpx

if sys.version_info >= (3, 10):
    from typing import Optional
else:  # pragma: no cover
    from typing import Optional

try:
    # MCP SDK v1 (mcp 1.x)
    from mcp.server.fastmcp import FastMCP
except ImportError:  # pragma: no cover
    # MCP SDK v2 renombró FastMCP -> MCPServer
    from mcp.server.mcpserver import MCPServer as FastMCP

from .catalog import (
    CATALOG,
    CATALOG_GENERATED,
    CATEGORIES,
    GATEWAY_URL,
    SETTLEMENT_ASSET,
    SETTLEMENT_ASSET_CONTRACT,
    SETTLEMENT_CHAIN_ID,
    SETTLEMENT_NETWORK,
    X402_VERSION,
)
from .payments import (
    free_sample,
    obtain_paid_resource,
    payment_required_response,
    price_from_challenge,
    wallet_balances,
)

mcp = FastMCP("radhika-x402-server")

_TIMEOUT = httpx.Timeout(30.0)


# ---------------------------------------------------------------------------
# Discovery (gratis, sin pago)
# ---------------------------------------------------------------------------


@mcp.tool()
def listar_recursos(categoria: Optional[str] = None) -> str:
    """Devuelve el catálogo de recursos x402 de RadhikaChain con precios en USDC.

    Cada entrada incluye id (ruta), método HTTP, categoría, precio_usd,
    price_atomic_usdc, description, sample_url y resource_url.
    Pasa `categoria` para filtrar (ver categorías con listar_categorias).
    """
    if categoria:
        filtrados = [r for r in CATALOG if r.get("category") == categoria]
        if not filtrados:
            return json.dumps(
                {"error": f"categoría desconocida: {categoria!r}", "categorias": CATEGORIES},
                indent=2,
            )
        return json.dumps(filtrados, indent=2, ensure_ascii=False)
    return json.dumps(CATALOG, indent=2, ensure_ascii=False)


@mcp.tool()
def listar_categorias() -> str:
    """Devuelve las categorías de recursos disponibles y cuántos recursos hay por categoría."""
    counts: dict[str, int] = {}
    for r in CATALOG:
        counts[r["category"]] = counts.get(r["category"], 0) + 1
    payload = {
        "gateway": GATEWAY_URL,
        "catalog_generated": CATALOG_GENERATED,
        "total_recursos": len(CATALOG),
        "categorias": sorted(counts.items()),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


@mcp.tool()
def buscar_recursos(consulta: str) -> str:
    """Busca recursos por texto libre en id, descripción o categoría (insensible a mayúsculas)."""
    q = consulta.lower()
    hits = [
        r
        for r in CATALOG
        if q in r["id"].lower() or q in r["description"].lower() or q in r["category"].lower()
    ]
    return json.dumps(hits, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Inspección sin pagar
# ---------------------------------------------------------------------------


@mcp.tool()
def ver_esquema(recurso: str) -> str:
    """Inspecciona un recurso SIN pagar: devuelve el challenge 402 con el esquema
    de salida (extensions.bazaar.info), precio real y requisitos de pago (accepts).

    El challenge 402 del recurso es la fuente de verdad del precio — no el catálogo.
    """
    return payment_required_response(GATEWAY_URL, recurso, _TIMEOUT)


@mcp.tool()
def obtener_muestra(recurso: str, payer: str) -> str:
    """Descarga UNA muestra gratis del recurso (1 por wallet). Requiere `payer`:
    la dirección de la wallet del agente (header X-Payer). Sin secretos."""
    return free_sample(GATEWAY_URL, recurso, payer, _TIMEOUT)


# ---------------------------------------------------------------------------
# Pago y liquidación x402
# ---------------------------------------------------------------------------


@mcp.tool()
def comprar_recurso(recurso: str, body: Optional[dict] = None) -> str:
    """Compra un recurso vía x402 y devuelve el contenido pagado.

    Requiere la env RADHIKA_PRIVATE_KEY (efímera, jamás persistida). Con la clave
    el flujo es automático: 402 challenge -> firma EIP-3009/Permit2 con el SDK
    oficial x402 -> retry con PAYMENT header -> contenido + asentamiento USDC Base.

    Sin RADHIKA_PRIVATE_KEY devuelve el challenge 402 (HTTP 402 Payment Required)
    para que el agente/callador lo liquide con su propia wallet.
    """
    return obtain_paid_resource(GATEWAY_URL, recurso, body, _TIMEOUT)


@mcp.tool()
def saldo_agente(wallet_address: str) -> str:
    """Consulta el balance real de USDC (Base 8453) de una wallet vía RPC público read-only.
    Incluye PRANA/credit info settlement_rail cuando aplica."""
    return wallet_balances(wallet_address, _TIMEOUT)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
