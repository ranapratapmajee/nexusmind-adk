# filepath: app/mcp_client.py
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# MCP Confugarations
mcp_config = StdioServerParameters(
    command="uv",
    args=[
        "--directory",
        "/Users/rana/Sigma/CodeLab/MyProject/omega-tools-mcp",
        "run",
        "src/omega_mcp/server.py"
    ]
)

# Turned into a singular async tool definition that plugs directly into the running loop
async def web_search(query: str) -> str:
    """Executes a live internet query via the local omega-tools MCP server over stdio."""
    async with stdio_client(mcp_config) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool("web_search", arguments={"query": query})
            return "\n".join([b.text for b in result.content if hasattr(b, 'text')])
