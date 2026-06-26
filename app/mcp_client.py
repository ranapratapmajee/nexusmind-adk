# filepath: app/mcp_client.py
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# MCP Configurations pointing to your flat local server toolkit
mcp_config = StdioServerParameters(
    command="uv",
    args=[
        "--directory",
        "/Users/rana/Sigma/CodeLab/MyProject/omega-tools-mcp",
        "run",
        "src/omega_mcp/server.py"
    ],
    # ADD YOUR ENV DETAILS HERE:
    env={
        "OMEGA_SEARCH_MAX_RESULTS": "5",
        "OMEGA_ENV": "dev",

    #     # Neo4j Container Settings
    #     "NEO4J_URI": "bolt://localhost:7687",
    #     "NEO4J_USER": "neo4j",
    #     "NEO4J_PASSWORD": "rana1234",
        
    #     # ChromaDB HTTP Service Settings
    #     "CHROMA_HOST": "localhost",
    #     "CHROMA_PORT": "8000",
        
    #     # Keep your system path alive so uv can find commands
         "PATH": os.environ.get("PATH", "")
    }
)

# MCP Tool Clients
async def web_search(query: str) -> str:
    """Executes a live internet query via the local omega-tools MCP server over stdio."""
    async with stdio_client(mcp_config) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool("web_search", arguments={"query": query})
            return "\n".join([b.text for b in result.content if hasattr(b, 'text')])

async def hybrid_kg_vector_search(query: str) -> str:
    """
    Performs a dual-engine semantic vector and full-text keyword search 
    fused via relative scoring algorithms across Neo4j and Chroma DB.
    """
    async with stdio_client(mcp_config) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool("hybrid_kg_vector_search", arguments={"query": query})
            return "\n".join([b.text for b in result.content if hasattr(b, 'text')])
        