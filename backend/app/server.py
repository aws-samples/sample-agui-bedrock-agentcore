"""
AG-UI Sample — Local server that runs the Strands agent
and streams AG-UI events via SSE and WebSocket.

Run: uvicorn backend.app.server:app --port 8000 --reload
"""

import asyncio
import json
import uuid
import time
import random
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from pathlib import Path

from strands import Agent, tool
from strands.models.bedrock import BedrockModel


# ─── Tools ──────────────────────────────────────────────────────────────────

@tool
def search(query: str, max_results: int = 3) -> dict:
    """Search for information on a given topic.
    Args:
        query: The search query
        max_results: Maximum number of results
    """
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
    """Perform mathematical calculations.
    Args:
        expression: Mathematical expression to evaluate
    """
    allowed = {"abs": abs, "round": round, "min": min, "max": max, "pow": pow}
    try:
        result = eval(expression, {"__builtins__": {}}, allowed)
        return {"expression": expression, "result": result}
    except Exception as e:
        return {"expression": expression, "error": str(e)}


@tool
def get_data(source: str, filters: dict = None) -> dict:
    """Retrieve structured data from a data source.
    Args:
        source: Data source name
        filters: Filter criteria
    """
    filters = filters or {}
    records = [
        {"id": 1, "name": "Item Alpha", "status": "active", "value": 142.50},
        {"id": 2, "name": "Item Beta", "status": "active", "value": 287.00},
        {"id": 3, "name": "Item Gamma", "status": "pending", "value": 95.75},
        {"id": 4, "name": "Item Delta", "status": "inactive", "value": 410.25},
        {"id": 5, "name": "Item Epsilon", "status": "active", "value": 63.00},
    ]
    if "status" in filters:
        records = [r for r in records if r["status"] == filters["status"]]
    return {"source": source, "records": records, "count": len(records), "retrieved_at": datetime.now().isoformat()}


@tool
def generate_report(title: str, data: dict = None, format: str = "summary") -> dict:
    """Generate a formatted report.
    Args:
        title: Report title
        data: Data to include
        format: Report format - summary, detailed, or table
    """
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
                {"heading": "Recommendations", "body": "No immediate action required."},
            ],
        },
    }


# ─── Agent ──────────────────────────────────────────────────────────────────

def create_agent():
    model = BedrockModel(
        model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
        region_name="us-east-1",
    )
    return Agent(
        model=model,
        tools=[search, calculator, get_data, generate_report],
        system_prompt=(
            "You are a helpful AI assistant. You have access to tools for searching, "
            "calculating, retrieving data, and generating reports. Use them when appropriate. "
            "Be concise."
        ),
    )


# ─── AG-UI Event Helpers ───────────────────────────────────────────────────

def agui_event(event_type: str, **data) -> str:
    payload = {
        "type": event_type,
        "eventId": str(uuid.uuid4()),
        "timestamp": time.time(),
        **data,
    }
    return f"data: {json.dumps(payload)}\n\n"


# ─── FastAPI App ────────────────────────────────────────────────────────────

app = FastAPI(title="AG-UI Sample", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"


class InvocationRequest(BaseModel):
    message: str
    thread_id: Optional[str] = None


@app.post("/invocations")
async def invoke_sse(request: InvocationRequest):
    """AG-UI SSE endpoint — streams events as the agent processes the request."""

    run_id = str(uuid.uuid4())
    thread_id = request.thread_id or str(uuid.uuid4())

    async def event_stream():
        agent = create_agent()

        # RUN_STARTED
        yield agui_event("RUN_STARTED", runId=run_id, threadId=thread_id)

        # STATE_SNAPSHOT
        yield agui_event("STATE_SNAPSHOT", snapshot={
            "status": "processing",
            "tools_invoked": [],
        })

        # STEP_STARTED — LLM call
        yield agui_event("STEP_STARTED", runId=run_id, stepName="llm_call")

        # REASONING
        reasoning_id = str(uuid.uuid4())
        yield agui_event("REASONING_START", reasoningId=reasoning_id)
        yield agui_event("REASONING_MESSAGE", reasoningId=reasoning_id, delta="Analyzing the request and determining which tools to use...")
        yield agui_event("REASONING_END", reasoningId=reasoning_id)

        try:
            # Call the Strands agent
            result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: agent(request.message)
            )

            yield agui_event("STEP_FINISHED", runId=run_id, stepName="llm_call")

            # Extract tool calls from the agent's conversation
            tools_used = []
            if hasattr(agent, 'messages'):
                for msg in agent.messages:
                    if isinstance(msg.get("content"), list):
                        for block in msg["content"]:
                            if isinstance(block, dict) and block.get("type") == "tool_use":
                                tc_id = block.get("id", str(uuid.uuid4()))
                                tool_name = block.get("name", "unknown")
                                tool_input = block.get("input", {})
                                tools_used.append(tool_name)

                                # TOOL_CALL events
                                yield agui_event("TOOL_CALL_START", toolCallId=tc_id, toolName=tool_name)

                                args_str = json.dumps(tool_input)
                                chunk_size = 30
                                for i in range(0, len(args_str), chunk_size):
                                    yield agui_event("TOOL_CALL_ARGS", toolCallId=tc_id, delta=args_str[i:i+chunk_size])
                                    await asyncio.sleep(0.02)

                                yield agui_event("TOOL_CALL_END", toolCallId=tc_id)

                            elif isinstance(block, dict) and block.get("type") == "tool_result":
                                tc_id = block.get("tool_use_id", str(uuid.uuid4()))
                                tool_result_content = block.get("content", "")
                                try:
                                    parsed = json.loads(tool_result_content) if isinstance(tool_result_content, str) else tool_result_content
                                except (json.JSONDecodeError, TypeError):
                                    parsed = {"result": str(tool_result_content)}
                                yield agui_event("TOOL_CALL_RESULT", toolCallId=tc_id, result=parsed)

            # STATE_DELTA — update with tools used
            if tools_used:
                yield agui_event("STATE_DELTA", delta={"tools_invoked": tools_used, "status": "responding"})

            # TEXT_MESSAGE — stream the final response
            response_text = str(result)
            msg_id = str(uuid.uuid4())
            yield agui_event("TEXT_MESSAGE_START", messageId=msg_id, role="assistant")

            words = response_text.split(" ")
            for i, word in enumerate(words):
                delta = word if i == 0 else f" {word}"
                yield agui_event("TEXT_MESSAGE_CONTENT", messageId=msg_id, delta=delta)
                await asyncio.sleep(0.03)

            yield agui_event("TEXT_MESSAGE_END", messageId=msg_id)

            # MESSAGES_SNAPSHOT
            yield agui_event("MESSAGES_SNAPSHOT", messages=[
                {"role": "user", "content": request.message},
                {"role": "assistant", "content": response_text},
            ])

            # STATE_DELTA — done
            yield agui_event("STATE_DELTA", delta={"status": "idle"})

            # RUN_FINISHED
            yield agui_event("RUN_FINISHED", runId=run_id)

        except Exception as e:
            yield agui_event("RUN_ERROR", runId=run_id, error={"code": "AGENT_ERROR", "message": str(e)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Thread-Id": thread_id},
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """AG-UI WebSocket endpoint."""
    await websocket.accept()
    thread_id = str(uuid.uuid4())

    await websocket.send_json({"type": "CONNECTED", "threadId": thread_id})

    try:
        while True:
            data = await websocket.receive_json()
            message = data.get("message", "")

            request = InvocationRequest(message=message, thread_id=thread_id)
            async for chunk in invoke_sse(request).body_iterator:
                line = chunk.decode() if isinstance(chunk, bytes) else chunk
                if line.startswith("data: "):
                    event = json.loads(line[6:].strip())
                    await websocket.send_json(event)

    except WebSocketDisconnect:
        pass


@app.get("/health")
async def health():
    return {"status": "healthy", "protocol": "AG-UI", "version": "0.1.0"}


@app.get("/tools")
async def list_tools():
    return {
        "tools": [
            {"name": "search", "description": "Search for information on a given topic"},
            {"name": "calculator", "description": "Perform mathematical calculations"},
            {"name": "get_data", "description": "Retrieve structured data from a data source"},
            {"name": "generate_report", "description": "Generate a formatted report"},
        ]
    }


@app.get("/")
async def serve_frontend():
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"message": "Frontend not found. Open frontend/index.html directly."}
