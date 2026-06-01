import json
import asyncio
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from ollama import chat

class MCPClientBot:
    def __init__(self, server_script="server_mcp.py"):
        self.server_params = StdioServerParameters(
            command="python",
            args=[server_script],
            env=None
        )
        self.exit_stack = AsyncExitStack()
        self.session = None

    async def connect(self):
        read_stream, write_stream = await self.exit_stack.enter_async_context(
            stdio_client(self.server_params)
        )
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await self.session.initialize()

    async def run_agent(self, user_content):
        if not self.session:
            await self.connect()
            
        tools_response = await self.session.list_tools()
        resources_response = await self.session.list_resources()
            
        tools_list = tools_response.tools
        resources_list = resources_response.resources

        system_prompt = f"""
Tu es un assistant spécialisé dans les transports.
RÈGLES STRICTES :
1. ANALYSE la demande de l'utilisateur.
2. Si la demande concerne un trajet (bus, travail, maison), tu DOIS utiliser un outil de type 'call_tool'.
3. Ne lis JAMAIS les ressources (config://app) sauf si tu ne peux ABSOLUMENT PAS répondre à la question sans lire la configuration.
4. Si tu hésites, privilégie toujours l'action 'call_tool'.
5. Réponds UNIQUEMENT en JSON.

OUTILS DISPONIBLES :
{[{"name": t.name, "description": t.__doc__, "parameters": t.inputSchema} for t in tools_list]}
"""

        response = chat(
            model='batiai/qwen3.5-9b',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_content}
            ],
            format='json',
            options={
                "temperature": 0,
                "num_predict": 4000,
                "num_ctx": 8192,
                "think": False
            }
        )
        # print(response)
        decision = json.loads(response.message.content)
        
        # On essaie d'extraire les informations de manière flexible
        action = decision.get("action")
        # On accepte "name" ou "tool"
        name = decision.get("name") or decision.get("tool")
        # On accepte "arguments" ou "parameters"
        args = decision.get("arguments") or decision.get("parameters") or {}

        # Logique d'exécution
        if action == "call_tool" or name:
            print(f"--- Calling Tool: {name} ---")
            # Appel de l'outil avec les arguments extraits
            result = await self.session.call_tool(name, arguments=args)
            
            # Extraction propre du contenu (la plupart des MCP renvoient une liste de TextContent)
            text_result = ""
            if result.content and hasattr(result.content[0], 'text'):
                text_result = result.content[0].text
            else:
                text_result = str(result.content)
                
            print(f"Result: {text_result}")
            return text_result

        elif action == "read_resource":
            uri = decision.get("uri")
            print(f"--- Reading Resource: {uri} ---")
            content = await self.session.read_resource(uri)
            return content.contents[0].text

    async def close(self):
        await self.exit_stack.aclose()

async def main():
    bot = MCPClientBot()
    await bot.connect()
    
    # Exécution séquentielle
    # print(await bot.run_agent("stp additionne 15 et 27"))
    # print(await bot.run_agent("stp soustrait 1058 et 888"))
    print(await bot.run_agent("bus notification to go work"))
    print(await bot.run_agent("Querry bus notification to go home"))
    # print(await bot.run_agent('Quelle est la météo actuellement'))
    # print(await bot.run_agent("il fera quel temp pendant cette journée"))
    # print(await bot.run_agent("c'est quoi la méteo demain ?"))
    
    await bot.close()

if __name__ == "__main__":
    asyncio.run(main())