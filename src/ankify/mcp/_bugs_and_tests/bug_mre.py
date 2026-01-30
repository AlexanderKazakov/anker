import asyncio
from fastmcp import FastMCP, Client
from pydantic import Field

mcp = FastMCP()

@mcp.prompt()
def analyze_data(
    data_uri: str = Field(description="The URI of the data."),
    analysis_type: str = Field(default="summary", description="Type of analysis.")
) -> str:
    return f"Perform '{analysis_type}' analysis on {data_uri}."

async def demo():
    async with Client(mcp) as client:
        # Call prompt WITHOUT providing analysis_type (should use default "summary")
        result = await client.get_prompt("analyze_data", {"data_uri": "data.csv"})
        print(result.messages[0].content.text)
        # Expected: "Perform 'summary' analysis on data.csv."
        # Actual:   "Perform 'annotation=NoneType required=False default='summary' description='Type of analysis.'' analysis on data.csv."

if __name__ == "__main__":
    asyncio.run(demo())
