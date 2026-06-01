import json
import asyncio
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from ollama import chat

class MCPClientBot:
    """MCP Client Bot for Transport Assistant
    
    Role: Manages MCP (Model Context Protocol) client connections and executes transport-related agent tasks.
    
    Methods:
        __init__(self, server_script="server_mcp.py") : Initialize the bot with MCP server script path.
        connect(self) : Establish connection to the MCP server.
        run_agent(self, user_content) : Execute agent with user content and handle tool calls.
        close(self) : Close the MCP connection and cleanup resources.
    """
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

        system_prompt = self._build_system_prompt(tools_list)

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
        
        action = self._get_action(decision)
        name = self._get_tool_name(decision)
        args = self._get_tool_args(decision)

        if action == "call_tool" or name:
            print(f"--- Calling Tool: {name} ---")
            result = await self.session.call_tool(name, arguments=args)
            
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

    def _build_system_prompt(self, tools_list):
        tools_info = []
        for tool in tools_list:
            tools_info.append({
                "name": tool.name,
                "description": tool.__doc__,
                "parameters": tool.inputSchema
            })
        
        prompt_text = """
You are a specialized transport assistant.
STRICT RULES:
1. ANALYZE the user's request.
2. If the request concerns a trip (bus, work, home), you MUST use a 'call_tool' tool.
3. NEVER read resources (config://app) unless you ABSOLUTELY CANNOT answer the question without reading the configuration.
4. If you hesitate, always prioritize the 'call_tool' action.
5. Respond ONLY in JSON.

AVAILABLE TOOLS:
"""
        prompt_text += str(tools_info)
        return prompt_text

    def _get_action(self, decision):
        return decision.get("action")

    def _get_tool_name(self, decision):
        name = decision.get("name")
        if name is None:
            name = decision.get("tool")
        return name

    def _get_tool_args(self, decision):
        args = decision.get("arguments")
        if args is None:
            args = decision.get("parameters")
        if args is None:
            args = {}
        return args

    async def close(self):
        await self.exit_stack.aclose()

async def main():
    bot = MCPClientBot()
    await bot.connect()

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
