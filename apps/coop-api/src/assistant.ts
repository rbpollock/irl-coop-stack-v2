import type { FastifyInstance } from "fastify";
import { verifyBearer } from "./verify-jwt";

// Server-mediated inference — the coop-run CPU fallback tier for the dashboard
// assistant (apps/web/irl-dashboard AssistantPanel). The browser holds only the
// coop JWT; THIS route holds the provider key and talks to llm-inference over
// the docker bridge. It is the provider seam the BYO tiers plug into
// (docs/design/byo-inference-and-group-scoped-agents.md): the harness asks for
// "a completion" and the platform tier answers — a member's own key later
// answers the same call without the harness changing.
//
// Deliberately NOT the MCP gateway: that is tools-only by contract (mcp.ts —
// "No LLM tokens stream through here"). Generation does not belong in it.
//
// On-device generation (Chrome Prompt API) stays in the browser and never
// reaches this route; it is the preferred path because the prompt never leaves
// the device. This is the fallback for Firefox/Safari/older Chrome and
// low-power devices, where the Prompt API is absent.
//
// Two shapes, one route:
//   {messages:[…]}              -> {text, model}             (buffered)
//   {messages:[…], stream:true} -> text/event-stream of {delta} … {done}
// Streaming matters at CPU speed: ~12 tok/s makes a 300-token answer ~25s of
// dead air when buffered, and responsive when streamed.

const INFERENCE_URL = process.env.INFERENCE_URL ?? "http://172.17.0.1:8002";
const INFERENCE_MODEL = process.env.INFERENCE_MODEL ?? "irl-coop-fallback";
const MAX_TOKENS = 512;
// CPU generation is slow (~12 tok/s on the dev box) — allow for the full 512.
const GENERATION_TIMEOUT_MS = 180_000;

type ChatMessage = { role: string; content: string };

export default async function assistantRoutes(fastify: FastifyInstance): Promise<void> {
  // POST /api/v1/assistant/chat {messages:[{role,content}]} -> {text}
  fastify.post("/api/v1/assistant/chat", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;

    const body = (request.body ?? {}) as {
      messages?: ChatMessage[];
      stream?: boolean;
    };
    const messages = body.messages;
    if (!Array.isArray(messages) || messages.length === 0) {
      return reply.code(400).send({ error: "messages_required" });
    }

    const key = process.env.INFERENCE_API_KEY;
    if (!key) {
      request.log.error("INFERENCE_API_KEY unset — is llm-inference configured?");
      return reply.code(503).send({ error: "inference_unconfigured" });
    }

    // ---- streamed -------------------------------------------------------
    if (body.stream) {
      // Open the upstream first: a failure is still a normal JSON error reply,
      // because hijacking the reply commits us to 200 + SSE headers.
      let upstream: Response;
      try {
        upstream = await fetch(`${INFERENCE_URL}/v1/chat/completions`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${key}`,
          },
          body: JSON.stringify({
            model: INFERENCE_MODEL,
            messages,
            temperature: 0.2,
            max_tokens: MAX_TOKENS,
            stream: true,
          }),
          signal: AbortSignal.timeout(GENERATION_TIMEOUT_MS),
        });
      } catch (err) {
        request.log.error({ err: (err as Error).message }, "inference unreachable");
        return reply.code(502).send({ error: "inference_unreachable" });
      }
      if (!upstream.ok || !upstream.body) {
        const detail = await upstream.text().catch(() => "");
        request.log.error(
          { status: upstream.status, detail: detail.slice(0, 300) },
          "inference failed"
        );
        return reply.code(502).send({ error: "inference_failed" });
      }

      reply.hijack();
      const res = reply.raw;
      // hijack() bypasses Fastify's onSend hooks (incl. the cors plugin), so set
      // the CORS headers this response needs manually (bearer-token auth, no
      // cookies — echoing the request Origin is fine). See notifications.ts.
      const origin = request.headers.origin;
      if (origin) {
        res.setHeader("Access-Control-Allow-Origin", origin);
        res.setHeader("Vary", "Origin");
      }
      res.writeHead(200, {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
        "X-Accel-Buffering": "no",
      });

      // Re-emit llama-server's SSE as a smaller event shape: {delta} … {done}.
      // Watch for client disconnect on the RESPONSE: for a POST the request
      // stream is already consumed, so request.raw "close" can fire at once.
      const reader = upstream.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      let closed = false;
      res.on("close", () => {
        closed = true;
        reader.cancel().catch(() => {});
      });

      try {
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          const lines = buf.split("\n");
          buf = lines.pop() ?? ""; // keep the trailing partial line
          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith("data:")) continue;
            const payload = trimmed.slice(5).trim();
            if (!payload || payload === "[DONE]") continue;
            try {
              const delta = (JSON.parse(payload) as any)?.choices?.[0]?.delta?.content;
              if (delta && !closed) res.write(`data: ${JSON.stringify({ delta })}\n\n`);
            } catch {
              // partial or non-JSON line — skip
            }
          }
        }
        if (!closed) {
          res.write(`data: ${JSON.stringify({ done: true, model: INFERENCE_MODEL })}\n\n`);
          res.end();
        }
      } catch (err) {
        request.log.error({ err: (err as Error).message }, "stream relay failed");
        if (!closed) {
          res.write(`data: ${JSON.stringify({ error: "inference_stream_failed" })}\n\n`);
          res.end();
        }
      }
      return;
    }

    try {
      const res = await fetch(`${INFERENCE_URL}/v1/chat/completions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${key}`,
        },
        body: JSON.stringify({
          model: INFERENCE_MODEL,
          messages,
          temperature: 0.2,
          max_tokens: MAX_TOKENS,
        }),
        signal: AbortSignal.timeout(GENERATION_TIMEOUT_MS),
      });
      if (!res.ok) {
        const detail = await res.text().catch(() => "");
        request.log.error(
          { status: res.status, detail: detail.slice(0, 300) },
          "inference failed"
        );
        return reply.code(502).send({ error: "inference_failed" });
      }

      const data = (await res.json()) as any;
      const text = data?.choices?.[0]?.message?.content ?? "";
      return reply.send({ text, model: INFERENCE_MODEL });
    } catch (err) {
      request.log.error({ err: (err as Error).message }, "inference unreachable");
      return reply.code(502).send({ error: "inference_unreachable" });
    }
  });
}