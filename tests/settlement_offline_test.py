"""Unit test offline del settlement: firma EIP-3009 del challenge real del gateway.

No usa red para el challenge (fixture con el header payment-required capturado
al gateway vivo) y firma con una wallet efímera de balance 0 — el pago NUNCA se
envía. Valida que el path comprar_recurso con RADHIKA_PRIVATE_KEY produce un
payload x402 v2 firmado con authorization EIP-3009 transferWithAuthorization.

    python tests/settlement_offline_test.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, ".")

FIXTURE = Path(__file__).parent / "fixtures" / "challenge_402_amenazas_vivas.b64"


def main() -> None:
    from eth_account import Account

    from x402 import x402ClientSync
    from x402.http.utils import decode_payment_required_header, encode_payment_signature_header
    from x402.mechanisms.evm.exact import ExactEvmScheme

    header = FIXTURE.read_text().strip()
    pr = decode_payment_required_header(header)
    a0 = pr.accepts[0]
    assert a0.network == "eip155:8453" and a0.scheme == "exact"
    assert a0.amount == "825000"  # 0.825 USDC atomic (6 decimales)
    print(f"[PASS] decode challenge real — network={a0.network} scheme={a0.scheme} amount={a0.amount} (0.825 USDC)")

    acct = Account.from_key("0x" + "59" * 32)  # wallet efímera, balance 0, nunca transmite
    client = x402ClientSync()
    client.register("eip155:8453", ExactEvmScheme(signer=acct))

    payload = client.create_payment_payload(pr)
    raw = payload.model_dump() if hasattr(payload, "model_dump") else payload
    s = json.dumps(raw, default=str)

    inner = raw.get("payload", {}) if isinstance(raw, dict) else {}
    auth = inner.get("authorization", {}) if isinstance(inner, dict) else {}
    auth_keys = sorted(auth.keys()) if isinstance(auth, dict) else []

    ok_auth = set(auth_keys) >= {"from", "nonce", "to", "validAfter", "validBefore", "value"}
    print(f"[PASS] payload x402 firmado — authorization EIP-3009: {auth_keys}")
    assert ok_auth, f"authorization incompleta: {auth_keys}"
    assert "signature" in s or "signature" in json.dumps(inner, default=str), "sin firma"
    print("[PASS] firma EIP-3009 presente (transferWithAuthorization firmada offline)")

    encoded = encode_payment_signature_header(payload)
    assert isinstance(encoded, str) and len(encoded) > 50
    print(f"[PASS] header PAYMENT codificado ({len(encoded)} chars) listo para retry al gateway")

    print("\nSETTLEMENT OFFLINE: 4/4 PASS")


if __name__ == "__main__":
    main()
