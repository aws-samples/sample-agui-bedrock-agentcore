"""
AG-UI Sample — Deploy agent to Amazon Bedrock AgentCore Runtime.

AgentCore Runtime natively supports AG-UI protocol. Once deployed:
  - SSE endpoint:  POST /invocations?qualifier=DEFAULT
  - WebSocket:     GET  /ws?qualifier=DEFAULT
  - Events are streamed in AG-UI format automatically

Usage:
    export AWS_DEFAULT_REGION=us-east-1
    python setup_agentcore.py --create
    python setup_agentcore.py --status
    python setup_agentcore.py --delete
"""

import argparse
import json
import sys
import time
import zipfile
import os
import io
import boto3


AGENT_NAME = "agui-bedrock-agentcore-agent"
REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")


def get_clients():
    runtime_client = boto3.client("bedrock-agentcore", region_name=REGION)
    iam_client = boto3.client("iam", region_name=REGION)
    sts_client = boto3.client("sts", region_name=REGION)
    account_id = sts_client.get_caller_identity()["Account"]
    return runtime_client, iam_client, account_id


def create_agent_runtime_role(iam_client, account_id):
    """Create IAM role for AgentCore Runtime execution."""
    role_name = f"{AGENT_NAME}-runtime-role"

    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "bedrock.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }

    bedrock_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "BedrockInvoke",
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                    "bedrock:Converse",
                    "bedrock:ConverseStream",
                ],
                "Resource": [
                    f"arn:aws:bedrock:{REGION}::foundation-model/anthropic.*",
                    f"arn:aws:bedrock:{REGION}::foundation-model/amazon.*",
                ],
            },
            {
                "Sid": "CloudWatchLogs",
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                "Resource": f"arn:aws:logs:{REGION}:{account_id}:*",
            },
        ],
    }

    # Create role
    try:
        response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="AgentCore Runtime execution role for AG-UI sample",
            Tags=[{"Key": "project", "Value": "agui-bedrock-agentcore"}],
        )
        role_arn = response["Role"]["Arn"]
        print(f"  Created IAM role: {role_arn}")
    except iam_client.exceptions.EntityAlreadyExistsException:
        role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"
        print(f"  IAM role exists: {role_arn}")

    # Attach inline policy
    iam_client.put_role_policy(
        RoleName=role_name,
        PolicyName="bedrock-access",
        PolicyDocument=json.dumps(bedrock_policy),
    )
    print("  Attached Bedrock access policy")

    # Wait for role propagation
    print("  Waiting for IAM role propagation...")
    time.sleep(10)

    return role_arn


def package_agent_code():
    """Package the agent code into a zip for AgentCore deployment."""
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # Main agent entry point
        zf.writestr("agent.py", '''
"""AgentCore Runtime entry point for AG-UI sample."""
from strands import Agent, tool
from strands.models.bedrock import BedrockModel


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
    from datetime import datetime
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
    from datetime import datetime
    data = data or {}
    return {
        "title": title,
        "format": format,
        "generated_at": datetime.now().isoformat(),
        "content": {
            "summary": f"Report \\'{title}\\' generated successfully.",
            "sections": [
                {"heading": "Overview", "body": f"This report covers: {title}"},
                {"heading": "Data Summary", "body": f"Processed {len(data)} data points."},
                {"heading": "Recommendations", "body": "No immediate action required."},
            ],
        },
    }


def handler():
    """Create and return the Strands agent. Called by AgentCore Runtime."""
    model = BedrockModel(model_id="anthropic.claude-sonnet-4-20250514")
    agent = Agent(
        model=model,
        tools=[search, calculator, get_data, generate_report],
        system_prompt=(
            "You are a helpful AI assistant. You have access to tools for searching, "
            "calculating, retrieving data, and generating reports. Use them when appropriate. "
            "Be concise."
        ),
    )
    return agent
''')

        # Requirements
        zf.writestr("requirements.txt", "strands-agents>=0.1.0\nstrands-agents-bedrock>=0.1.0\n")

    buffer.seek(0)
    return buffer.read()


def create_agent(runtime_client, iam_client, account_id):
    """Create the AgentCore Runtime agent with AG-UI protocol."""

    print("\n>>> Step 1: Creating IAM role...")
    role_arn = create_agent_runtime_role(iam_client, account_id)

    print("\n>>> Step 2: Packaging agent code...")
    code_zip = package_agent_code()
    print(f"  Package size: {len(code_zip)} bytes")

    print("\n>>> Step 3: Creating AgentCore Runtime agent...")
    try:
        response = runtime_client.create_agent_runtime(
            agentRuntimeName=AGENT_NAME,
            description="AG-UI sample agent — demonstrates AG-UI protocol with AgentCore Runtime",
            roleArn=role_arn,
            agentRuntimeArtifact={
                "containerConfiguration": {
                    "containerUri": None,  # Use managed runtime
                },
            },
            protocolConfiguration={
                "protocol": "AGUI",  # Enable AG-UI protocol
            },
            authorizerConfiguration={
                "authorizerType": "IAM",  # Use IAM SigV4 auth
            },
            networkConfiguration={
                "networkMode": "PUBLIC",  # Internet-accessible endpoints
            },
            tags={"project": "agui-bedrock-agentcore", "protocol": "agui"},
        )
        agent_runtime_id = response["agentRuntimeId"]
        print(f"  Created agent runtime: {agent_runtime_id}")

    except runtime_client.exceptions.ConflictException:
        print(f"  Agent '{AGENT_NAME}' already exists. Use --delete first to recreate.")
        return

    except Exception as e:
        # AgentCore API may differ — fall back to alternative creation flow
        print(f"  Note: AgentCore API call format may need adjustment for your SDK version.")
        print(f"  Error: {e}")
        print()
        print("  Alternative: Use the AWS Console:")
        print("  1. Go to Amazon Bedrock > AgentCore > Agent Runtimes")
        print("  2. Click 'Create agent runtime'")
        print("  3. Configure:")
        print(f"     - Name: {AGENT_NAME}")
        print("     - Protocol: AG-UI")
        print("     - Auth: IAM")
        print(f"     - Role: {role_arn}")
        print("  4. Upload the agent code (agent.py with Strands tools)")
        print("  5. Deploy")
        return

    print("\n>>> Step 4: Waiting for agent to be ready...")
    for i in range(30):
        status_response = runtime_client.get_agent_runtime(agentRuntimeId=agent_runtime_id)
        status = status_response.get("status", "UNKNOWN")
        print(f"  Status: {status} ({i+1}/30)")
        if status == "ACTIVE":
            break
        time.sleep(10)

    print_endpoints(runtime_client, agent_runtime_id)


def print_endpoints(runtime_client, agent_runtime_id=None):
    """Print the AG-UI endpoints."""
    if not agent_runtime_id:
        # Look up by name
        response = runtime_client.list_agent_runtimes()
        for rt in response.get("agentRuntimes", []):
            if rt.get("agentRuntimeName") == AGENT_NAME:
                agent_runtime_id = rt["agentRuntimeId"]
                break

    if not agent_runtime_id:
        print(f"  Agent '{AGENT_NAME}' not found.")
        return

    response = runtime_client.get_agent_runtime(agentRuntimeId=agent_runtime_id)
    endpoint = response.get("agentRuntimeEndpoint", {}).get("url", "N/A")
    status = response.get("status", "UNKNOWN")

    print()
    print("=============================================")
    print("AGENTCORE RUNTIME — AG-UI ENDPOINTS")
    print("=============================================")
    print()
    print(f"  Status:     {status}")
    print(f"  Runtime ID: {agent_runtime_id}")
    print()
    print(f"  AG-UI SSE:       POST {endpoint}/invocations?qualifier=DEFAULT")
    print(f"  AG-UI WebSocket: GET  {endpoint}/ws?qualifier=DEFAULT")
    print()
    print("  Auth: IAM SigV4 (use aws-sigv4 in requests)")
    print()
    print("  Test with curl (SSE):")
    print(f'  aws curl --service bedrock-agentcore --region {REGION} \\')
    print(f'    -X POST "{endpoint}/invocations?qualifier=DEFAULT" \\')
    print(f'    -H "Content-Type: application/json" \\')
    print(f'    -d \'{{"message": "Search for information about cloud computing"}}\'')
    print()
    print("  Update frontend/index.html:")
    print(f"  const API_BASE = '{endpoint}';")
    print("=============================================")


def get_status(runtime_client):
    """Get agent status and endpoints."""
    print(f"\n>>> Looking up agent: {AGENT_NAME}")
    try:
        response = runtime_client.list_agent_runtimes()
        for rt in response.get("agentRuntimes", []):
            if rt.get("agentRuntimeName") == AGENT_NAME:
                print_endpoints(runtime_client, rt["agentRuntimeId"])
                return
        print(f"  Agent '{AGENT_NAME}' not found.")
    except Exception as e:
        print(f"  Error: {e}")


def delete_agent(runtime_client):
    """Delete the agent runtime."""
    print(f"\n>>> Deleting agent: {AGENT_NAME}")
    try:
        response = runtime_client.list_agent_runtimes()
        for rt in response.get("agentRuntimes", []):
            if rt.get("agentRuntimeName") == AGENT_NAME:
                runtime_client.delete_agent_runtime(agentRuntimeId=rt["agentRuntimeId"])
                print(f"  Deleted: {rt['agentRuntimeId']}")
                return
        print(f"  Agent '{AGENT_NAME}' not found.")
    except Exception as e:
        print(f"  Error: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy AG-UI agent to AgentCore Runtime")
    parser.add_argument("--create", action="store_true", help="Create the agent runtime")
    parser.add_argument("--status", action="store_true", help="Get agent status and endpoints")
    parser.add_argument("--delete", action="store_true", help="Delete the agent runtime")
    args = parser.parse_args()

    runtime_client, iam_client, account_id = get_clients()

    if args.create:
        create_agent(runtime_client, iam_client, account_id)
    elif args.status:
        get_status(runtime_client)
    elif args.delete:
        delete_agent(runtime_client)
    else:
        parser.print_help()
