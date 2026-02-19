import fastmcp
from pydantic import Field

# Official prompt parameters annotation example from the docs:


mcp = fastmcp.FastMCP()


@mcp.prompt(
    name="analyze_data_request",  # Custom prompt name
    description="Creates a request to analyze data with specific parameters",  # Custom description
    tags={"analysis", "data"},  # Optional categorization tags
    meta={"version": "1.1", "author": "data-team"},  # Custom metadata
)
def data_analysis_prompt(
    data_uri: str = Field(description="The URI of the resource containing the data."),
    analysis_type: str = Field(
        default="a default value", description="Type of analysis."
    ),
) -> str:
    """This docstring is ignored when description is provided."""
    return (
        f"Please perform a '{analysis_type}' analysis on the data found at {data_uri}."
    )
