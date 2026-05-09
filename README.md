# AG-UI with Amazon Bedrock AgentCore

Real-time AI agent interfaces using the [AG-UI protocol](https://docs.ag-ui.com) and [Amazon Bedrock AgentCore](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html). Stream every reasoning step, tool call, and state change from your agent to the browser.

## Overview

Most agent-powered applications show a loading spinner and a final answer. This project implements the AG-UI (Agent-User Interaction Protocol) to stream the full agent execution pipeline — reasoning, tool invocations with arguments, tool results, and state changes — to a frontend in real time.

The agent is built with the [Strands Agents SDK](https://github.com/strands-agents/sdk-python) and deployed on AgentCore Runtime. A FastAPI server extracts AG-UI events from the Strands message history and streams them via Server-Sent Events.

## Architecture

```
Browser ──► CloudFront ──► API Gateway ──► Lambda Proxy (SigV4) ──► AgentCore Runtime
                │                                                        │
                └── S3 (frontend)                              Strands Agent + FastAPI
                                                               (AG-UI event streaming)
```

- **AgentCore Runtime** — Strands agent with 7 tools (search, calculator, inventory, trends, customer lookup, report generation, alerts) running as a managed container. Calls Bedrock Claude via the Converse API.
- **Lambda Proxy** — Signs requests with IAM SigV4 and passes through the AG-UI event stream to the browser.
- **API Gateway** — HTTP API routing `/invocations` to the Lambda proxy.
- **S3 + CloudFront** — Single HTML frontend served from a private S3 bucket via CloudFront with Origin Access Control. API and static content on one domain — no CORS.

## AG-UI Event Flow

The protocol defines 16 event types in three streaming patterns:

| Pattern | Events | Description |
|---------|--------|-------------|
| Start-Content-End | `TEXT_MESSAGE_START` → `TEXT_MESSAGE_CONTENT` → `TEXT_MESSAGE_END` | Token-by-token text streaming |
| Start-Content-End | `TOOL_CALL_START` → `TOOL_CALL_ARGS` → `TOOL_CALL_END` → `TOOL_CALL_RESULT` | Tool invocation with arguments and results |
| Snapshot-Delta | `STATE_SNAPSHOT` / `STATE_DELTA` | Full state then incremental updates |
| Lifecycle | `RUN_STARTED` / `RUN_FINISHED` / `RUN_ERROR` | Execution boundaries |

## Agent Tools

| Tool | Description |
|------|-------------|
| `search_knowledge_base` | Search internal knowledge bases |
| `calculator` | Evaluate mathematical expressions |
| `get_inventory` | Query warehouse inventory by status |
| `analyze_trends` | Analyze business trends over time |
| `lookup_customer` | Look up customer records |
| `generate_report` | Generate formatted reports |
| `send_alert` | Send notifications via Slack, email, or PagerDuty |

## Getting Started

### 1. Deploy the supporting infrastructure

Clone the repo and deploy the CloudFormation stack. Pass your public IP to restrict access via CloudFront:

```bash
# Clone the repo
git clone <REPO_URL>
cd agui-with-amazon-bedrock-agentcore

# Deploy the stack (replace with your IP)
aws cloudformation create-stack \
  --stack-name agui-bedrock-agentcore \
  --template-body file://deploy/cloudformation.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-west-2 \
  --parameters ParameterKey=AllowedIPv4CIDR,ParameterValue=$(curl -s https://checkip.amazonaws.com)/32
```

This creates the Lambda proxy, API Gateway, S3 bucket, CloudFront distribution, ECR repo, and IAM roles. CloudFront takes ~5 minutes.

### 2. Upload the frontend and notebook to S3

Once the stack is created, upload the frontend and the deployment notebook to the S3 bucket:

```bash
BUCKET_NAME=$(aws cloudformation describe-stacks \
  --stack-name agui-bedrock-agentcore --region us-west-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`FrontendBucketName`].OutputValue' --output text)

aws s3 cp frontend/index.html s3://${BUCKET_NAME}/index.html --content-type "text/html"
aws s3 cp agui_bedrock_agentcore_deploy.ipynb s3://${BUCKET_NAME}/agui_bedrock_agentcore_deploy.ipynb
```

Alternatively, `deploy/deploy.sh` does both uploads automatically.

### 3. Run the notebook in SageMaker AI Studio

Copy the notebook from S3 into your SageMaker AI Studio environment:

```bash
aws s3 cp s3://${BUCKET_NAME}/agui_bedrock_agentcore_deploy.ipynb .
```

Open `agui_bedrock_agentcore_deploy.ipynb` in SageMaker AI Studio and run through the cells. The notebook walks through the full lifecycle:

1. **Install dependencies** — Installs the Strands SDK, AgentCore CLI, and supporting packages
2. **Write agent code** — `%%writefile agui_agent.py` creates the FastAPI server with the Strands agent and all 7 tools
3. **Test locally** — Runs a lightweight agent invocation to verify Bedrock connectivity and tool execution
4. **Configure and deploy** — Uses `agentcore create` to scaffold the project, copies the agent code in, and runs `agentcore deploy` to package and deploy to AgentCore Runtime
5. **Test on AgentCore** — Invokes the deployed agent via `agentcore invoke` (CLI) and boto3 (SDK), inspecting the raw SSE event stream
6. **Wire up the frontend** — Updates the Lambda proxy with the new agent ARN and prints the CloudFront URL to open in a browser
7. **Cleanup** — Commented-out cells to destroy the AgentCore deployment and delete the CloudFormation stack

The AgentCore CLI (`@aws/agentcore`) handles project scaffolding, packaging, and deployment via CDK — no Docker needed.

Supporting infrastructure (Lambda, API Gateway, S3, CloudFront) is deployed once and reused across agent iterations.

## Example Queries

- "Check warehouse-east for low stock items, calculate restock cost, and send a Slack alert"
- "Look up customer CUST-001 and CUST-003, compare their spend"
- "Analyze error trends for 7 days and sales trends for 30 days, generate a report"

## Project Structure

```
├── backend/app/          # FastAPI server with Strands agent and AG-UI event extraction
├── deploy/               # CloudFormation template, deploy script, AgentCore setup
├── frontend/index.html   # Single-page AG-UI frontend
├── agui_bedrock_agentcore_deploy.ipynb  # End-to-end deployment notebook (run in SageMaker AI Studio)
├── Dockerfile            # Container definition for AgentCore Runtime
└── README.md
```

## Prerequisites

- AWS account with access to Amazon Bedrock (Claude models) and AgentCore
- Amazon SageMaker AI Studio (for notebook-based deployment)
- Python 3.12+

### Key Dependencies

- `strands-agents` / `strands-agents-tools` / `strands-agents-bedrock`
- `fastapi` / `uvicorn`
- `@aws/agentcore` CLI (for deployment, install via `npm install -g @aws/agentcore`)
- Node.js 20+

## Tags

`#agentic-ai` `#amazon-bedrock-agentcore` `#strands-agents` `#ag-ui` `#real-time-streaming`
