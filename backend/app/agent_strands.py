"""
AG-UI Agent using Strands Agents SDK (Amazon Bedrock AgentCore).

Strands is the open-source SDK that powers AgentCore Runtime.
When deployed to AgentCore with protocol='AGUI', the runtime
automatically handles AG-UI event streaming.

This file defines the agent + tools using the Strands SDK.
"""

from strands import Agent, tool
from strands.models.bedrock import BedrockModel


# ─── Tool Definitions ────────────────────────────────────────────────────────
# Strands uses the @tool decorator to define tools.
# These are automatically exposed via AG-UI TOOL_CALL events when
# running on AgentCore Runtime.

@tool
def search(query: str, max_results: int = 3) -> dict:
    """Search for information on a given topic. Returns relevant results.

    Args:
        query: The search query
        max_results: Maximum number of results (default 3)
    """
    import random

    topics = [
        ("Understanding the Basics", "A comprehensive overview of the fundamentals."),
        ("Advanced Techniques", "Deep dive into advanced methods and best practices."),
        ("Practical Applications", "Real-world examples and case studies."),
        ("Recent Developments", "Latest research and industry trends."),
        ("Getting Started Guide", "Step-by-step tutorial for beginners."),
    ]
    results = []
    for i in range(min(max_results, len(topics))):
        title, desc = topics[i]
        results.append({
            "title": f"{title}: {query}",
            "snippet": f"{desc} Covers key aspects of {query}.",
            "relevance_score": round(random.uniform(0.75, 0.99), 2),
        })

    return {"query": query, "results": results, "total_found": len(results)}


@tool
def calculator(expression: str) -> dict:
    """Perform mathematical calculations. Supports basic arithmetic.

    Args:
        expression: Mathematical expression to evaluate
    """
    allowed_names = {"abs": abs, "round": round, "min": min, "max": max, "pow": pow}
    try:
        result = eval(expression, {"__builtins__": {}}, allowed_names)
        return {"expression": expression, "result": result}
    except Exception as e:
        return {"expression": expression, "error": str(e)}


@tool
def get_data(source: str, filters: dict = None) -> dict:
    """Retrieve structured data from a data source. Returns JSON records.

    Args:
        source: Data source name
        filters: Filter criteria
    """
    from datetime import datetime

    filters = filters or {}
    sample_records = [
        {"id": 1, "name": "Item Alpha", "status": "active", "value": 142.50},
        {"id": 2, "name": "Item Beta", "status": "active", "value": 287.00},
        {"id": 3, "name": "Item Gamma", "status": "pending", "value": 95.75},
        {"id": 4, "name": "Item Delta", "status": "inactive", "value": 410.25},
        {"id": 5, "name": "Item Epsilon", "status": "active", "value": 63.00},
    ]

    if "status" in filters:
        sample_records = [r for r in sample_records if r["status"] == filters["status"]]

    return {
        "source": source,
        "records": sample_records,
        "count": len(sample_records),
        "retrieved_at": datetime.now().isoformat(),
    }


@tool
def generate_report(title: str, data: dict = None, format: str = "summary") -> dict:
    """Generate a formatted report based on provided data.

    Args:
        title: Report title
        data: Data to include in the report
        format: Report format - summary, detailed, or table
    """
    from datetime import datetime

    data = data or {}
    return {
        "title": title,
        "format": format,
        "generated_at": datetime.now().isoformat(),
        "content": {
            "summary": f"Report '{title}' generated successfully.",
            "sections": [
                {"heading": "Overview", "body": f"This report covers: {title}"},
                {"heading": "Data Summary", "body": f"Processed {len(data)} data points."},
                {"heading": "Recommendations", "body": "Based on the analysis, no immediate action required."},
            ],
        },
    }


# ─── Agent Definition ────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a helpful AI assistant. You have access to tools for searching, \
calculating, retrieving data, and generating reports. Use them when appropriate \
to provide accurate and helpful responses. Be concise."""


def create_agent(model_id: str = "anthropic.claude-sonnet-4-20250514", region: str = "us-east-1") -> Agent:
    """Create a Strands agent with all tools registered."""

    model = BedrockModel(
        model_id=model_id,
        region_name=region,
    )

    agent = Agent(
        model=model,
        tools=[search, calculator, get_data, generate_report],
        system_prompt=SYSTEM_PROMPT,
    )

    return agent


# ─── Local Testing ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    agent = create_agent()
    response = agent("Search for information about AG-UI protocol and summarize the results")
    print(response)
