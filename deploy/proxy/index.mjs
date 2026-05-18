// Streaming proxy: browser -> Lambda Function URL -> AgentCore Runtime.
//
// Uses the Lambda Node.js runtime's `awslambda.streamifyResponse` to pipe
// AgentCore's SSE response body to the caller without buffering. The caller
// sees each AG-UI event as soon as the agent emits it.

import {
  BedrockAgentCoreClient,
  InvokeAgentRuntimeCommand,
} from "@aws-sdk/client-bedrock-agentcore";

const AGENT_RUNTIME_ARN = process.env.AGENT_RUNTIME_ARN;
const REGION = process.env.REGION || "us-east-1";

const client = new BedrockAgentCoreClient({ region: REGION });

const SSE_HEADERS = {
  "Content-Type": "text/event-stream",
  "Cache-Control": "no-cache, no-transform",
  Connection: "keep-alive",
  "X-Accel-Buffering": "no", // Tells nginx-style intermediaries not to buffer
  "Access-Control-Allow-Origin": "*",
};

function sseError(code, message) {
  return `data: ${JSON.stringify({
    type: "RUN_ERROR",
    error: { code, message },
  })}\n\n`;
}

export const handler = awslambda.streamifyResponse(
  async (event, responseStream, _context) => {
    // Function URL events have body as a string; decode if base64-encoded.
    let prompt = "";
    try {
      const raw = event.isBase64Encoded
        ? Buffer.from(event.body || "", "base64").toString("utf8")
        : event.body || "{}";
      const body = JSON.parse(raw);
      prompt = body.prompt || body.message || "";
    } catch (e) {
      const meta = awslambda.HttpResponseStream.from(responseStream, {
        statusCode: 400,
        headers: { "Content-Type": "application/json" },
      });
      meta.write(JSON.stringify({ error: "invalid JSON body" }));
      meta.end();
      return;
    }

    if (!AGENT_RUNTIME_ARN || AGENT_RUNTIME_ARN === "NONE") {
      const meta = awslambda.HttpResponseStream.from(responseStream, {
        statusCode: 500,
        headers: SSE_HEADERS,
      });
      meta.write(
        sseError(
          "PROXY_NOT_CONFIGURED",
          "AGENT_RUNTIME_ARN env var is not set. Run the wire-frontend cell."
        )
      );
      meta.end();
      return;
    }

    // Establish the SSE response. After this, every responseStream.write() flushes
    // to the client immediately.
    const out = awslambda.HttpResponseStream.from(responseStream, {
      statusCode: 200,
      headers: SSE_HEADERS,
    });

    try {
      const cmd = new InvokeAgentRuntimeCommand({
        agentRuntimeArn: AGENT_RUNTIME_ARN,
        qualifier: "DEFAULT",
        payload: new TextEncoder().encode(JSON.stringify({ prompt })),
      });
      const resp = await client.send(cmd);

      // resp.response is an async iterable / Readable of bytes for SSE responses.
      // We forward each chunk verbatim.
      const body = resp.response;
      if (body && typeof body[Symbol.asyncIterator] === "function") {
        for await (const chunk of body) {
          // chunk is a Uint8Array
          out.write(chunk);
        }
      } else if (body) {
        // Fallback: treat as a single buffer
        out.write(body);
      }
      out.end();
    } catch (err) {
      out.write(sseError("AGENT_INVOKE_ERROR", err.message || String(err)));
      out.end();
    }
  }
);
