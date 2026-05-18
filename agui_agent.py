"""AG-UI Agent Server - real AG-UI events from Strands agent execution."""
import asyncio, json, uuid, time, random, os
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from strands import Agent, tool
from strands.models import BedrockModel

@tool
def search_knowledge_base(query: str, category: str = "all") -> dict:
    """Search the knowledge base for information on a topic.
    Args:
        query: The search query
        category: Category - all, technical, business, research
    """
    db = {
        "technical": [{"title": "Microservices Patterns", "snippet": "Best practices for distributed systems.", "relevance": 0.95},
                      {"title": "Event-Driven Design", "snippet": "Event sourcing and CQRS for scalability.", "relevance": 0.91},
                      {"title": "Container Orchestration", "snippet": "K8s and ECS strategies.", "relevance": 0.88}],
        "business": [{"title": "Digital Transformation ROI", "snippet": "Measuring cloud migration returns.", "relevance": 0.93},
                     {"title": "Cost Optimization", "snippet": "Reducing cloud spend 30-40%.", "relevance": 0.90}],
        "research": [{"title": "LLM Agent Architectures", "snippet": "ReAct, CoT, tool-use patterns.", "relevance": 0.97},
                     {"title": "RAG Patterns", "snippet": "Grounding LLMs with knowledge bases.", "relevance": 0.94}],
    }
    results = [] if category == "all" else db.get(category, db["technical"])
    if category == "all":
        for v in db.values(): results.extend(v)
        random.shuffle(results); results = results[:5]
    for r in results: r["relevance"] = round(random.uniform(0.75, 0.99), 2); r["title"] = f"{r['title']}: {query}"
    return {"query": query, "category": category, "results": results, "total_found": len(results)}

@tool
def calculator(expression: str) -> dict:
    """Perform mathematical calculations.
    Args:
        expression: Math expression to evaluate
    """
    allowed = {"abs": abs, "round": round, "min": min, "max": max, "pow": pow}
    try: return {"expression": expression, "result": eval(expression, {"__builtins__": {}}, allowed)}
    except Exception as e: return {"expression": expression, "error": str(e)}

@tool
def get_inventory(source: str, status_filter: str = "all") -> dict:
    """Retrieve inventory data from a warehouse or store.
    Args:
        source: Warehouse or store name
        status_filter: Filter - all, active, low_stock, out_of_stock
    """
    inv = [{"sku": "SKU-1001", "name": "Wireless Headphones", "status": "active", "quantity": 342, "price": 79.99, "reorder_point": 100},
           {"sku": "SKU-1002", "name": "USB-C Hub", "status": "active", "quantity": 156, "price": 49.99, "reorder_point": 50},
           {"sku": "SKU-1003", "name": "Mechanical Keyboard", "status": "low_stock", "quantity": 23, "price": 129.99, "reorder_point": 50},
           {"sku": "SKU-1004", "name": "4K Monitor", "status": "active", "quantity": 89, "price": 399.99, "reorder_point": 30},
           {"sku": "SKU-1005", "name": "Webcam HD", "status": "out_of_stock", "quantity": 0, "price": 59.99, "reorder_point": 75},
           {"sku": "SKU-1006", "name": "Laptop Stand", "status": "low_stock", "quantity": 12, "price": 34.99, "reorder_point": 40},
           {"sku": "SKU-1007", "name": "Wireless Mouse", "status": "active", "quantity": 501, "price": 29.99, "reorder_point": 100},
           {"sku": "SKU-1008", "name": "Noise Cancelling Earbuds", "status": "active", "quantity": 210, "price": 149.99, "reorder_point": 80}]
    if status_filter != "all": inv = [i for i in inv if i["status"] == status_filter]
    return {"source": source, "filter": status_filter, "items": inv, "count": len(inv),
            "total_inventory_value": round(sum(i["quantity"]*i["price"] for i in inv), 2), "retrieved_at": datetime.now().isoformat()}

@tool
def analyze_trends(data_type: str, period: str = "7d") -> dict:
    """Analyze trends in sales or errors.
    Args:
        data_type: Type - sales, errors
        period: Time period - 24h, 7d, 30d
    """
    n = {"24h": 24, "7d": 7, "30d": 30}.get(period, 7)
    if data_type == "sales":
        pts = [{"date": (datetime.now()-timedelta(days=i)).strftime("%Y-%m-%d"), "value": round(15000+random.uniform(-3000,5000),2)} for i in range(n)]
        return {"data_type": "sales", "period": period, "data_points": pts[:5], "trend": "increasing" if pts[0]["value"]>pts[-1]["value"] else "decreasing",
                "average": round(sum(d["value"] for d in pts)/len(pts),2)}
    elif data_type == "errors":
        pts = [{"date": (datetime.now()-timedelta(days=i)).strftime("%Y-%m-%d"), "count": random.randint(2,45), "severity": random.choice(["low","medium","high"])} for i in range(n)]
        return {"data_type": "errors", "period": period, "data_points": pts[:5], "total_errors": sum(d["count"] for d in pts)}
    return {"error": "Unknown type", "available": ["sales", "errors"]}

@tool
def lookup_customer(customer_id: str) -> dict:
    """Look up customer information.
    Args:
        customer_id: Customer ID (CUST-001, CUST-002, CUST-003)
    """
    db = {"CUST-001": {"name": "Acme Corp", "tier": "Enterprise", "annual_spend": 125000, "satisfaction_score": 4.8, "open_tickets": 1},
          "CUST-002": {"name": "TechStart Inc", "tier": "Growth", "annual_spend": 45000, "satisfaction_score": 4.2, "open_tickets": 3},
          "CUST-003": {"name": "Global Retail Co", "tier": "Enterprise", "annual_spend": 280000, "satisfaction_score": 4.9, "open_tickets": 0}}
    return db.get(customer_id, {"error": "Not found", "available": list(db.keys())})

@tool
def generate_report(title: str, report_type: str = "summary") -> dict:
    """Generate a business report.
    Args:
        title: Report title
        report_type: Type - summary, executive, action_items
    """
    return {"title": title, "report_type": report_type, "generated_at": datetime.now().isoformat(),
            "recommendations": [{"priority": "high", "action": "Restock low inventory", "impact": "Prevent $12K lost sales"},
                                {"priority": "medium", "action": "Review open tickets", "impact": "Maintain satisfaction > 4.5"}], "status": "generated"}

@tool
def send_alert(channel: str, message: str, severity: str = "info") -> dict:
    """Send an alert notification.
    Args:
        channel: Channel - email, slack, pagerduty
        message: Alert message
        severity: Severity - info, warning, critical
    """
    return {"alert_id": f"ALERT-{random.randint(10000,99999)}", "channel": channel, "severity": severity,
            "message": message, "status": "sent", "sent_at": datetime.now().isoformat()}

REGION = os.environ.get('AWS_DEFAULT_REGION', os.environ.get('AWS_REGION', 'us-east-1'))
MODEL_ID = os.environ.get('MODEL_ID', 'global.anthropic.claude-sonnet-4-6')
SYSTEM_PROMPT = os.environ.get(
    'SYSTEM_PROMPT',
    'You are a business operations assistant. Use multiple tools when needed. Always look up data before recommending. Calculate numbers, dont estimate. If you find issues, send alerts. Be concise.'
)


def create_agent():
    model = BedrockModel(model_id=MODEL_ID, region_name=REGION)
    return Agent(
        model=model,
        tools=[search_knowledge_base, calculator, get_inventory, analyze_trends, lookup_customer, generate_report, send_alert],
        system_prompt=SYSTEM_PROMPT,
    )

def agui_event(t, **d):
    return f'data: {json.dumps({"type": t, "eventId": str(uuid.uuid4()), "timestamp": time.time(), **d})}\n\n'


def extract_tool_results(message_obj):
    """Extract toolResult entries from a message event payload.

    Strands yields {'message': <Message>} when a message is appended to history.
    The Message can be a dict or a string repr depending on serialization;
    we accept the dict form here and look for toolResult blocks.
    """
    if not isinstance(message_obj, dict):
        return []
    if message_obj.get('role') != 'user':
        return []  # tool results live in user-role messages from the agent loop
    out = []
    for block in message_obj.get('content', []) or []:
        if isinstance(block, dict) and 'toolResult' in block:
            tr = block['toolResult']
            content = tr.get('content', [])
            txt = content[0]['text'] if isinstance(content, list) and content and isinstance(content[0], dict) and 'text' in content[0] else str(content)
            try:
                parsed = json.loads(txt)
            except Exception:
                parsed = {'result': txt}
            out.append((tr.get('toolUseId', ''), parsed))
    return out


app = FastAPI()


@app.get('/ping')
async def ping():
    return JSONResponse({'status': 'healthy'})


@app.post('/invocations')
async def invocations(request: Request):
    body = await request.json()
    prompt = body.get('prompt', body.get('message', ''))
    run_id = str(uuid.uuid4())

    async def stream():
        agent = create_agent()
        yield agui_event('RUN_STARTED', runId=run_id)
        yield agui_event('STATE_SNAPSHOT', snapshot={'status': 'processing', 'tools_invoked': []})

        # State tracked across the Strands event stream so we know when to open/close
        # AG-UI text messages and tool calls.
        active_text_msg_id = None     # set when we're in the middle of a TEXT_MESSAGE_*
        active_tool_call_id = None    # set when we're in the middle of a TOOL_CALL_*
        seen_tool_args = {}            # toolUseId -> last serialized input we yielded args-delta for
        tools_invoked = []

        try:
            async for event in agent.stream_async(prompt):
                # ── Tool-use streaming ───────────────────────────────────
                if event.get('type') == 'tool_use_stream':
                    tu = event.get('current_tool_use') or {}
                    tu_id = tu.get('toolUseId')
                    tu_name = tu.get('name', '')
                    tu_input = tu.get('input', '')

                    if not tu_id:
                        continue

                    # Close any open text message before the tool call begins
                    if active_text_msg_id is not None:
                        yield agui_event('TEXT_MESSAGE_END', messageId=active_text_msg_id)
                        active_text_msg_id = None

                    # New tool call: emit START
                    if active_tool_call_id != tu_id:
                        if active_tool_call_id is not None:
                            yield agui_event('TOOL_CALL_END', toolCallId=active_tool_call_id)
                        active_tool_call_id = tu_id
                        tools_invoked.append(tu_name)
                        yield agui_event('TOOL_CALL_START', toolCallId=tu_id, toolName=tu_name)

                    # Stream incremental args. Strands gives us the *cumulative* input each time
                    # (not just the delta), so we compute the delta ourselves.
                    cumulative = tu_input if isinstance(tu_input, str) else json.dumps(tu_input)
                    prev = seen_tool_args.get(tu_id, '')
                    if cumulative.startswith(prev) and len(cumulative) > len(prev):
                        delta = cumulative[len(prev):]
                        yield agui_event('TOOL_CALL_ARGS', toolCallId=tu_id, delta=delta)
                        seen_tool_args[tu_id] = cumulative
                    elif cumulative != prev:
                        # Non-prefix change — emit the full new value as a delta
                        yield agui_event('TOOL_CALL_ARGS', toolCallId=tu_id, delta=cumulative)
                        seen_tool_args[tu_id] = cumulative
                    continue

                # ── Text token streaming ─────────────────────────────────
                if 'data' in event and isinstance(event['data'], str) and event['data']:
                    # Close any open tool call before resuming text
                    if active_tool_call_id is not None:
                        yield agui_event('TOOL_CALL_END', toolCallId=active_tool_call_id)
                        active_tool_call_id = None

                    if active_text_msg_id is None:
                        active_text_msg_id = str(uuid.uuid4())
                        yield agui_event('TEXT_MESSAGE_START', messageId=active_text_msg_id, role='assistant')

                    yield agui_event('TEXT_MESSAGE_CONTENT', messageId=active_text_msg_id, delta=event['data'])
                    continue

                # ── Completed message added to history (carries toolResult blocks) ──
                if 'message' in event:
                    msg = event['message']
                    # Strands sometimes serializes message as str — try to coerce
                    if isinstance(msg, str):
                        try:
                            msg = json.loads(msg.replace("'", '"'))
                        except Exception:
                            msg = None
                    for tu_id, parsed in extract_tool_results(msg):
                        # Closing the in-flight tool call now that we have its result
                        if active_tool_call_id == tu_id:
                            yield agui_event('TOOL_CALL_END', toolCallId=tu_id)
                            active_tool_call_id = None
                        yield agui_event('TOOL_CALL_RESULT', toolCallId=tu_id, result=parsed)
                    continue

            # ── Stream finished — close any open spans and emit lifecycle ──
            if active_tool_call_id is not None:
                yield agui_event('TOOL_CALL_END', toolCallId=active_tool_call_id)
            if active_text_msg_id is not None:
                yield agui_event('TEXT_MESSAGE_END', messageId=active_text_msg_id)
            if tools_invoked:
                yield agui_event('STATE_DELTA', delta={'tools_invoked': tools_invoked, 'status': 'idle'})
            else:
                yield agui_event('STATE_DELTA', delta={'status': 'idle'})
            yield agui_event('RUN_FINISHED', runId=run_id)

        except Exception as e:
            yield agui_event('RUN_ERROR', runId=run_id, error={'code': 'AGENT_ERROR', 'message': str(e)})

    return StreamingResponse(stream(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'Connection': 'keep-alive'})

if __name__ == '__main__':
    import uvicorn
    # NOTE: 0.0.0.0 binds to all interfaces — required for AgentCore container routing.
    # For local development, use '127.0.0.1' to restrict to localhost.
    uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', '8080')))
