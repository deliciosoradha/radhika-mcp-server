"""Ejemplo: agente LangChain que descubre y compra recursos x402 de RadhikaChain.

    pip install 'radhika-mcp[langchain]'

El agente usa las herramientas MCP convertidas a LangChain tools. Para que
pueda liquidar pagos x402, exporta tu clave privada de wallet (solo local,
jamás se persiste ni se sube a ningún repo):

    export RADHIKA_PRIVATE_KEY=0x...   # wallet del agente con USDC en Base

Sin la clave, `comprar_recurso` devuelve el challenge 402 y el agente puede
informar el precio y los requisitos de pago en lugar de comprar.
"""

import asyncio

from radhika_mcp.langchain_adapter import get_radhika_tools_async


async def main() -> None:
    tools = await get_radhika_tools_async()
    print("Herramientas RadhikaChain disponibles para el agente LangChain:")
    for t in tools:
        print(f"  - {t.name}: {t.description.splitlines()[0][:70]}")

    # Integración con un LLM cualquiera (ejemplo con LangGraph react agent):
    #
    #   from langchain_openai import ChatOpenAI
    #   from langgraph.prebuilt import create_react_agent
    #
    #   llm = ChatOpenAI(model="gpt-4o")
    #   agent = create_react_agent(llm, tools)
    #   result = await agent.ainvoke(
    #       {"messages": [("user", "muestra el precio de /zk/stark y cómpralo")]}
    #   )

    # Invocación directa de una herramienta (sin LLM) para demostrar el flujo:
    listar = next(t for t in tools if t.name == "listar_recursos")
    resultado = await listar.ainvoke({"categoria": "zero_knowledge"})
    print("\nlistar_recursos(zero_knowledge) ->")
    print(resultado[:400])


if __name__ == "__main__":
    asyncio.run(main())
