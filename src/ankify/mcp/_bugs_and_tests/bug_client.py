import asyncio
from fastmcp import Client


# Run the server with `fastmcp run bug_server.py --transport http --port 8000`

# Run the client normally with `python bug_client.py`
client = Client("http://localhost:8000/mcp")


async def get_prompt__analyze_data_request():
    async with client:
        result = await client.get_prompt_mcp(
            "analyze_data_request",
            {
                "data_uri": "https://example.com/data.csv",
                # BUG: when a value is not sent, instead of the field.default, the field itself is substituted by FastMCP.
                # The returned result is:
                # [PromptMessage(role='user', content=TextContent(type='text', text="Please perform a 'annotation=NoneType required=False default='a default value' description='Type of analysis.'' analysis on the data found at https://example.com/data.csv.", annotations=None, meta=None))]
                # "analysis_type": "summary",
            },
        )
        print(result.messages)
        print()


async def main():
    await get_prompt__analyze_data_request()


if __name__ == "__main__":
    asyncio.run(main())
