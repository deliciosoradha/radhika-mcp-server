"""Capa de pagos x402 de RadhikaChain — sin secretos, usando el SDK oficial.

Flujo de compra:
1. GET al recurso -> 402 con header PAYMENT-REQUIRED (x402 v2, base64).
2. Sin RADHIKA_PRIVATE_KEY -> devolver el challenge tal cual (decisión humana).
3. Con RADHIKA_PRIVATE_KEY -> x402ClientSync + ExactEvmScheme firman EIP-3009/
   Permit2, retry con header PAYMENT, y el gateway asienta USDC on-chain (Base 8453).
"""

from __future__ import annotations

import base64
import json
import os
from typing import Any, Optional

import httpx

BASE_CHAIN_ID = 8453
BASE_RPC_URL = "https://mainnet.base.org"
USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
USDC_DECIMALS = 6

PRANA_INFO = {
    "settlement_rail": "USDC_BASE_8453",
    "note": "PRANA burn rail y créditos internos no se exponen en el paquete público.",
}


def _normalize_resource(recurso: str) -> str:
    path = recurso.strip()
    if not path.startswith("/"):
        path = "/" + path
    # acepta tanto "amenazas/vivas" como "/amenazas/vivas"
    return path


def _lookup_catalog(path: str) -> Optional[dict]:
    try:
        from .catalog import CATALOG

        for r in CATALOG:
            if r["id"] == path:
                return r
    except Exception:
        pass
    return None


def _json_default(obj: Any) -> str:
    return str(obj)


def _dumps(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False, default=_json_default)


# ---------------------------------------------------------------------------
# Challenge 402 / esquema (gratis)
# ---------------------------------------------------------------------------


def price_from_challenge(challenge: dict) -> dict:
    """Extrae datos de precio legibles del challenge 402."""
    accepts = challenge.get("accepts") or []
    out: dict[str, Any] = {"accepts": accepts}
    if accepts:
        a = accepts[0]
        amount_atomic = int(a.get("amount", "0"))
        out.update(
            {
                "price_usdc": amount_atomic / (10**USDC_DECIMALS),
                "price_atomic_usdc": amount_atomic,
                "network": a.get("network"),
                "scheme": a.get("scheme"),
                "pay_to": a.get("payTo"),
                "asset_contract": a.get("asset"),
                "settlement": "USDC on Base (chainId 8453) via EIP-3009 transferWithAuthorization",
            }
        )
    return out


def payment_required_response(gateway: str, recurso: str, timeout: httpx.Timeout) -> str:
    """GET sin pagar -> devuelve el challenge 402 decodificado + precio + esquema."""
    path = _normalize_resource(recurso)
    url = f"{gateway}{path}"
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url)
    except Exception as e:  # pragma: no cover - error de red
        return _dumps({"error": f"error conectando al gateway: {e}"})

    challenge = _decode_payment_required(resp)
    if challenge is None:
        return _dumps(
            {
                "error": "el recurso no emitió challenge 402",
                "status": resp.status_code,
                "hint": "verifica la ruta con listar_recursos",
            }
        )

    payload: dict[str, Any] = {
        "status": 402,
        "recurso": path,
        "url": url,
        "challenge": challenge,
        "precio": price_from_challenge(challenge),
    }
    ext = (challenge.get("extensions") or {}).get("bazaar", {}).get("info", {})
    if ext:
        payload["esquema_salida"] = ext
    return _dumps(payload)


def _decode_payment_required(resp: httpx.Response) -> Optional[dict]:
    """Decodifica el challenge desde header PAYMENT-REQUIRED (v2) o body (v1)."""
    header = resp.headers.get("payment-required")
    if header:
        try:
            pad = header + "=" * (-len(header) % 4)
            return json.loads(base64.b64decode(pad))
        except Exception:
            return None
    try:
        body = resp.json()
        if isinstance(body, dict) and "accepts" in body:
            return body
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Muestra gratis (1 por wallet, header X-Payer)
# ---------------------------------------------------------------------------


def free_sample(gateway: str, recurso: str, payer: str, timeout: httpx.Timeout) -> str:
    path = _normalize_resource(recurso)
    url = f"{gateway}/muestra{path}"
    if not payer or not payer.startswith("0x") or len(payer) != 42:
        return _dumps(
            {
                "error": "payer inválido",
                "hint": "pasa la dirección 0x... de la wallet del agente (header X-Payer). 1 muestra por wallet.",
            }
        )
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url, headers={"X-Payer": payer})
    except Exception as e:  # pragma: no cover
        return _dumps({"error": f"error conectando al gateway: {e}"})
    if resp.status_code == 200:
        contenido = _try_json(resp.text)
        # Semántica del gateway: 200 + {"ok": false, "paga": true} = muestra ya usada
        ya_usada = isinstance(contenido, dict) and contenido.get("ok") is False
        cat = _lookup_catalog(path)
        payload = {
            "status": 200,
            "recurso": path,
            "sample_url": f"{gateway}/muestra{path}",
            "price_usd": (cat or {}).get("price_usd"),
            "muestra_ya_usada": ya_usada,
            "contenido": contenido,
        }
        if ya_usada:
            payload["hint"] = "esta wallet ya consumió su muestra gratis; usa comprar_recurso para el contenido completo."
        return _dumps(payload)
    return _dumps(
        {
            "status": resp.status_code,
            "recurso": path,
            "error": "muestra no disponible",
            "detail": _try_json(resp.text),
            "hint": "límite de 1 muestra gratis por wallet; usa comprar_recurso para el contenido completo.",
        }
    )


def _try_json(text: str) -> Any:
    try:
        return json.loads(text)
    except Exception:
        return text[:2000]


# ---------------------------------------------------------------------------
# Compra con liquidación x402 (SDK oficial)
# ---------------------------------------------------------------------------


def obtain_paid_resource(
    gateway: str,
    recurso: str,
    body: Optional[dict],
    timeout: httpx.Timeout,
) -> str:
    path = _normalize_resource(recurso)
    url = f"{gateway}{path}"
    cat = _lookup_catalog(path)

    private_key = os.getenv("RADHIKA_PRIVATE_KEY")

    # Primer intento sin pago: esperamos 402 con challenge.
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url, json=body) if body is not None else client.get(url)
    except Exception as e:  # pragma: no cover
        return _dumps({"error": f"error conectando al gateway: {e}"})

    if resp.status_code != 402:
        # Recurso gratuito o error: devolver tal cual.
        return _dumps(
            {
                "status": resp.status_code,
                "recurso": path,
                "contenido": _try_json(resp.text),
            }
        )

    challenge = _decode_payment_required(resp)
    if challenge is None:
        return _dumps({"error": "402 sin challenge parseable", "recurso": path})

    if not private_key:
        # Sin clave: devolver el challenge para decisión humana / liquidación externa.
        payload: dict[str, Any] = {
            "status": 402,
            "error": "Payment Required",
            "recurso": path,
            "message": (
                "x402 payment required. Configura RADHIKA_PRIVATE_KEY para auto-liquidar "
                "via USDC en Base (chainId 8453), o liquida este challenge con tu propia wallet."
            ),
            "network": "base",
            "chain_id": BASE_CHAIN_ID,
            "precio": price_from_challenge(challenge),
            "challenge": challenge,
        }
        if cat:
            payload["catalog_price_usd"] = cat.get("price_usd")
        return _dumps(payload)

    # Con clave: liquidar con el SDK oficial x402 (firma EIP-3009/Permit2).
    try:
        settled = _settle_with_sdk(resp, url, body, timeout)
    except Exception as e:
        return _dumps(
            {
                "status": "settlement_error",
                "recurso": path,
                "error": f"fallo liquidando el pago x402: {e}",
            }
        )

    if settled is None:
        return _dumps(
            {
                "status": "settlement_error",
                "recurso": path,
                "error": "el SDK no pudo crear el payload de pago (revisa acepta eip155:8453)",
            }
        )

    paid_resp, payload_obj = settled
    if paid_resp.status_code == 200:
        return _dumps(
            {
                "status": 200,
                "recurso": path,
                "pagado": True,
                "payment_header_enviado": True,
                "settlement": {
                    "network": "base",
                    "chain_id": BASE_CHAIN_ID,
                    "asset": "USDC",
                    "scheme": "exact",
                },
                "contenido": _try_json(paid_resp.text),
            }
        )
    return _dumps(
        {
            "status": paid_resp.status_code,
            "recurso": path,
            "error": "el pago fue enviado pero el gateway no entregó el contenido",
            "detalle": _try_json(paid_resp.text),
        }
    )


def _settle_with_sdk(
    resp_402: httpx.Response,
    url: str,
    body: Optional[dict],
    timeout: httpx.Timeout,
):
    """Usa x402ClientSync + ExactEvmScheme para firmar y reintentar con PAYMENT."""
    from eth_account import Account

    from x402 import x402ClientSync
    from x402.http.utils import encode_payment_signature_header
    from x402.mechanisms.evm.exact import ExactEvmScheme

    account = Account.from_key(os.environ["RADHIKA_PRIVATE_KEY"])
    client = x402ClientSync()
    client.register("eip155:8453", ExactEvmScheme(signer=account))

    headers = dict(resp_402.headers)
    body_bytes = resp_402.content
    payment_headers, payment_payload = client.handle_402_response(
        headers, body_bytes, url
    )

    payment_value = (
        payment_headers.get("PAYMENT")
        if isinstance(payment_headers, dict)
        else encode_payment_signature_header(payment_payload)
    )
    retry_headers = {"PAYMENT": payment_value}
    with httpx.Client(timeout=timeout) as client_http:
        if body is not None:
            paid = client_http.post(url, json=body, headers=retry_headers)
        else:
            paid = client_http.get(url, headers=retry_headers)
    return paid, payment_payload


# ---------------------------------------------------------------------------
# saldo_agente (read-only, RPC público Base)
# ---------------------------------------------------------------------------


def wallet_balances(wallet_address: str, timeout: httpx.Timeout) -> str:
    addr = (wallet_address or "").strip()
    if not addr.startswith("0x") or len(addr) != 42:
        return _dumps({"error": "wallet_address inválida", "hint": "formato esperado: 0x + 40 hex"})
    data = "0x70a08231" + "0" * 24 + addr[2:].lower()  # balanceOf(address)
    try:
        with httpx.Client(timeout=timeout) as client:
            rpc = client.post(
                BASE_RPC_URL,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "eth_call",
                    "params": [{"to": USDC_BASE, "data": data}, "latest"],
                },
            ).json()
        raw = rpc.get("result")
        if raw is None:
            return _dumps({"error": "RPC Base sin resultado", "detail": rpc})
        balance_atomic = int(raw, 16)
        payload = {
            "wallet": addr,
            "network": "base",
            "chain_id": BASE_CHAIN_ID,
            "usdc_base": {
                "contract": USDC_BASE,
                "balance": balance_atomic / (10**USDC_DECIMALS),
                "balance_atomic": balance_atomic,
                "decimals": USDC_DECIMALS,
            },
            "prana": PRANA_INFO,
            "note": "Suficiente saldo USDC (Base) permite liquidar cualquier challenge x402 del catálogo.",
        }
        return _dumps(payload)
    except Exception as e:  # pragma: no cover
        return _dumps({"error": f"error consultando RPC Base: {e}"})
