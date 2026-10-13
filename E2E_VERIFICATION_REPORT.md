# RADHIKACHAIN MCP SERVER — REPORTE DE VERIFICACIÓN E2E

- **Fecha:** 2026-10-13 (CST, UTC-06:00)
- **Componente:** `radhika-mcp` v1.1.0 (MCP SDK 2.3.0, FastMCP/MCPServer, stdio)
- **Gateway:** `https://x402.radhikachain.xyz` (x402 v2, vivo)
- **Veredicto:** **17/17 TESTS PASS** (9 E2E + 4 LangChain + 4 settlement offline) · 0 secretos · producción intacta.

## Resultados

### Suite MCP E2E (`tests/e2e_test.py`) — 9/9 PASS

1. [PASS] `mcp.initialize` — handshake stdio OK; server `radhika-x402-server`, protocol `2025-11-25`.
2. [PASS] `mcp.tools_list` — 7 herramientas registradas: `listar_recursos`, `listar_categorias`, `buscar_recursos`, `ver_esquema`, `obtener_muestra`, `comprar_recurso`, `saldo_agente`.
3. [PASS] `listar_recursos` — catálogo completo: **56 recursos** con precios USDC (generado desde `/.well-known/x402` vivo).
4. [PASS] `listar_categorias` — 56 recursos en 11 categorías.
5. [PASS] `buscar_recursos("stark")` — encuentra `/zk/stark`.
6. [PASS] `ver_esquema("/amenazas/vivas")` — challenge 402 real decodificado: 0.825 USDC, `eip155:8453`, scheme exact, payTo `0xf513...32c0`, esquema de salida incluido.
7. [PASS] `comprar_recurso` sin `RADHIKA_PRIVATE_KEY` — 402 canónico con chain_id 8453 y challenge embebido; **no se paga nada**.
8. [PASS] `saldo_agente` — RPC Base read-only: burn address = 0.0 USDC (valida path `balanceOf`).
9. [PASS] `obtener_muestra` con `X-Payer` — semántica 1-por-wallet del gateway verificada (200 + `ok:false` para wallet que ya consumió su muestra).

### Suite LangChain (`tests/langchain_test.py`) — 4/4 PASS

10. [PASS] `langchain.tools_load` — 7 herramientas MCP convertidas a LangChain tools via `langchain-mcp-adapters` 0.3.2.
11. [PASS] `langchain.base_tools` — todas son `langchain_core.tools.BaseTool` reales.
12. [PASS] `langchain.invoke_listar_recursos` — invocación vía LangChain: categoría `zero_knowledge` → `['/zk/capas', '/zk/fold', '/zk/merkle', '/zk/prove', '/zk/stark']`.
13. [PASS] `langchain.invoke_ver_esquema` — challenge 402 de `/zk/stark` via LangChain: 1.48 USDC, `eip155:8453`.

### Suite Settlement offline (`tests/settlement_offline_test.py`) — 4/4 PASS

14. [PASS] decode del challenge 402 real (fixture capturado del gateway vivo; verificado idéntico al challenge en vivo en network/scheme/amount/asset/payTo).
15. [PASS] payload x402 v2 firmado con wallet efímera — authorization EIP-3009: `from, nonce, to, validAfter, validBefore, value`.
16. [PASS] firma `transferWithAuthorization` presente (firmada offline, sin transmisión).
17. [PASS] header `PAYMENT` codificado (2276 chars) listo para retry al gateway.

## Auditoría de fuga de secretos (`tests/leak_audit.py`) — PASS

- Grep de patrones sobre 13 archivos del repo: **0 claves privadas EVM, 0 DSNs de BD (PG/Mongo/MySQL), 0 tokens HMAC, 0 IPs internas**.
- El único material sensible del paquete es la env `RADHIKA_PRIVATE_KEY`, leída en runtime del entorno del agente, jamás persistida ni incluida en el repo.
- Todo el tráfico opera contra el endpoint público `https://x402.radhikachain.xyz` y RPC público `https://mainnet.base.org` (read-only).

## Notas de infra detectadas durante la verificación (no bloqueantes para el MCP)

- `/muestra/*` para wallets NUEVAS devolvió 502 intermitente durante la ventana
  de pruebas (write-path degradado); wallets con muestra ya consumida responden
  200 con `{"ok": false, "paga": true}`. El server MCP maneja ambos estados.
- El catálogo `.well-known/x402` es el inventario; el challenge 402 del recurso
  individual es la fuente de verdad del precio (p.ej. `/zk/stark` catálogo 1.48 = challenge 1.48; `/amenazas/vivas` 0.825).

## Cómo reproducir

```bash
pip install -e '.[all]'
python tests/leak_audit.py            # [PASS] 0 secretos
python tests/e2e_test.py              # 9/9 PASS
python tests/langchain_test.py       # 4/4 PASS
python tests/settlement_offline_test.py  # 4/4 PASS
```
