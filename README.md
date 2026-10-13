# radhika-mcp-server

Servidor MCP (Model Context Protocol) público para el gateway x402 de
**RadhikaChain** — permite a agentes autónomos descubrir, inspeccionar y
**comprar recursos de datos on-chain con USDC en Base** (x402 v2,
liquidación EIP-3009).

- Gateway vivo: https://x402.radhikachain.xyz
- Catálogo: https://x402.radhikachain.xyz/.well-known/x402
- Protocolos: MCP (stdio / streamable HTTP) + x402 v2 (pay-per-call)

Este repositorio es **público y sanitizado**: no contiene secretos, claves,
cadenas de conexión a bases de datos ni infraestructura interna. La clave
privada del agente que paga **nunca** se almacena: se provee via la variable
de entorno efímera `RADHIKA_PRIVATE_KEY` y solo se usa para firmar la
autorización de pago EIP-3009 (el paquete no la transmite a nadie más que
al propio gateway en el header `PAYMENT` firmado).

## Instalación

```bash
pip install radhika-mcp            # core: servidor MCP (mcp, httpx, pydantic)
pip install 'radhika-mcp[settlement]'  # + SDK x402 oficial (liquidación real)
pip install 'radhika-mcp[langchain]'   # + adaptador LangChain
pip install 'radhika-mcp[all]'         # todo
```

## Uso como servidor MCP (stdio)

Configura tu cliente MCP (Claude Desktop, Cursor, Hermes, cualquier cliente
del protocolo):

```json
{
  "mcpServers": {
    "radhika-x402-server": {
      "command": "radhika-mcp",
      "env": {
        "RADHIKA_PRIVATE_KEY": "0x..."
      }
    }
  }
}
```

Sin `RADHIKA_PRIVATE_KEY` el servidor funciona en modo solo-lectura:
`comprar_recurso` devuelve el challenge 402 (precio, red, payTo) para que
decidas antes de pagar.

## Herramientas

| Herramienta | Paga | Descripción |
| --- | --- | --- |
| `listar_recursos(categoria=None)` | no | Catálogo completo: 56 recursos con precios en USDC |
| `listar_categorias()` | no | Categorías y conteo de recursos |
| `buscar_recursos(consulta)` | no | Búsqueda por texto en id/descripción/categoría |
| `ver_esquema(recurso)` | no | Challenge 402 real del recurso: precio, red, esquema de salida |
| `obtener_muestra(recurso, payer)` | no | Una muestra gratis por wallet (header `X-Payer`) |
| `comprar_recurso(recurso, body=None)` | sí | Flujo x402 completo: challenge → firma EIP-3009 → contenido |
| `saldo_agente(wallet_address)` | no | Balance USDC real de la wallet vía RPC Base (read-only) |

## Integración LangChain

```python
from radhika_mcp.langchain_adapter import get_radhika_tools_async

tools = await get_radhika_tools_async()      # stdio; o get_radhika_tools(url="http://host/mcp")

# con cualquier LLM:
# from langchain_openai import ChatOpenAI
# from langgraph.prebuilt import create_react_agent
# agent = create_react_agent(ChatOpenAI(model="gpt-4o"), tools)
```

Ejemplo completo: [`examples/langchain_agent.py`](examples/langchain_agent.py)

## Ejemplos

- [`examples/mcp_stdio_client.py`](examples/mcp_stdio_client.py) — cliente MCP mínimo via stdio
- [`examples/langchain_agent.py`](examples/langchain_agent.py) — agente LangChain con tools x402

## Tests

```bash
pip install -e '.[all]'
python tests/e2e_test.py                # E2E contra el gateway vivo (9 tests)
python tests/langchain_test.py         # adaptador LangChain (4 tests)
python tests/settlement_offline_test.py  # firma EIP-3009 offline (4 tests)
```

## Flujo de pago x402

```
agente → GET /amenazas/vivas
       ← 402 + header PAYMENT-REQUIRED (challenge: 0.825 USDC, eip155:8453, exact)
agente → firma EIP-3009 transferWithAuthorization con su wallet (SDK x402 oficial)
agente → GET /amenazas/vivas + header PAYMENT (payload firmado)
       ← 200 + contenido pagado (USDC asentado on-chain en Base)
```

## Seguridad

- Cero secretos en el repo (auditoría con grep en CI: ver `tests/leak_audit.py`).
- La clave privada vive solo en el entorno del proceso del agente.
- `saldo_agente` es read-only contra un RPC público; no hay acceso a nodos internos.
- El catálogo se genera desde el endpoint público `/.well-known/x402`.

## Licencia

MIT — ver [LICENSE](LICENSE).
