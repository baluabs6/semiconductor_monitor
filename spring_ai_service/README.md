# Spring AI service

A Java / Spring Boot service that adds Claude-powered analysis **on top of** the existing
Python backend. The C DAQ, C++ anomaly engine and Python backends are unchanged.

```
C (daq) -> C++ (anomaly) -> Python engine + REST/WS API (:8001)  <--HTTP--  Spring AI service (:8080) --> Claude
```

## Endpoints

| Endpoint | What it does |
|---|---|
| `GET /ai/analyze?minutes=5` | Typed root-cause hypothesis (`IncidentAnalysis`) for recent alerts |
| `GET /ai/report?hours=8&source=FAB` | Typed shift-handoff report (`ShiftReport`) |
| `POST /ai/chat` `{"question": "...", "conversationId": "optional"}` | Free-form Q&A with per-conversation memory; Claude calls read-only tools (`MonitorTools`) to fetch live data |
| `POST /ai/chat/stream` | Same, streamed as Server-Sent Events (masked line by line) |
| `GET /sse` + `POST /mcp/message` | MCP server exposing the same read-only tools to Claude Desktop / Claude Code |
| `GET /actuator/prometheus` | Metrics, including Spring AI token usage |

## Run

Requires Java 17+ and Maven.

```bash
# 1) start the C/C++/Python side
./build.sh
cd backend && pip install -r requirements.txt
uvicorn fastapi_app:app --port 8001

# 2) start the Spring AI service
export ANTHROPIC_API_KEY=****
cd ../spring_ai_service
mvn spring-boot:run
```

Environment variables: `RUNBOOKS_DIR` (optional, see Runbook retrieval), `ANTHROPIC_API_KEY` (required), `SERVICE_API_KEY` (optional; when set, `/ai/**`, `/sse` and `/mcp/**` require an `X-API-Key` header), `ANTHROPIC_MODEL` (default `claude-sonnet-5-5`),
`MONITOR_BASE_URL` (default `http://localhost:8001`).

```bash
curl "localhost:8080/ai/analyze?minutes=5"
curl -X POST localhost:8080/ai/chat -H 'Content-Type: application/json' \
     -d '{"question":"Are there any critical FAB alerts right now, and what could cause them?"}'
```

## Notes

- Uses Spring AI 1.1.x (Spring Boot 3.5). Spring AI 2.0 is also stable; the `ChatClient` / `@Tool`
  code here should carry over, but check its upgrade notes (it targets a newer Spring Boot).
- Tools are read-only, and alert text is treated as untrusted input (prompt-injection guard in the system prompt).
- The existing Python `/alerts/analyze` and `/alerts/report` endpoints still work; this service is additive.

## Behaviour and limits

- Backend calls have 2 s connect / 5 s read timeouts and 2 retries (connection errors and 5xx only).
- `/ai/analyze` accepts at most 60 minutes and `/ai/report` at most 72 hours. Prompts hold at most 200 alerts (highest severity first, then most recent) and say how many were omitted.
- Chat memory keeps the last 20 messages per `conversationId` **in memory**: it is lost on restart and not size-limited across ids, so use a JDBC/Redis-backed `ChatMemoryRepository` before exposing this publicly.
- The MCP endpoint and Actuator are only as protected as your network: set `SERVICE_API_KEY` and keep them off the public internet. `/actuator/prometheus` is not covered by the key.
- Tests: `mvn test` (no API key needed). Docker: `docker build -t semiconductor-spring-ai .`

## Advisors

Every `ChatClient` call passes through this chain (lowest order runs first):

| Order | Advisor | What it does |
|---|---|---|
| +10 | `AuditAdvisor` | One log line per call on logger `monitor.ai.audit` (conversation, model, tokens, latency, whether input was redacted, which runbooks were used). **Metadata only: never prompt or answer text.** Metrics: `monitor_ai_calls_total`, `monitor_ai_tokens_total{type}`, `monitor_ai_latency_seconds` |
| +100 | `RedactionAdvisor` | Masks sensitive data in user messages before they reach the model or chat memory, and in the reply. For streamed answers `StreamRedactor` masks line by line |
| +1000 | chat memory (chat only) | Per-conversation history |
| 0 | `RetrievalAugmentationAdvisor` | Adds runbook excerpts to the user message |

## Runbook retrieval (RAG)

`/ai/analyze`, `/ai/report` and `/ai/chat` add the most relevant runbook sections to the prompt, and Claude cites them by name, e.g. `[cooling_failure]`.

- **Where runbooks come from:** `RUNBOOKS_DIR` (a directory of `*.md` files; headings define sections). If unset, five **sample** runbooks bundled in `src/main/resources/runbooks/` are used. The samples are illustrative placeholders written for this project, **not real fab procedures**. Replace them before relying on any answer.
- **How matching works:** an in-memory BM25 keyword index, with no embedding model and no vector database. It is good at exact terms such as `WDT_RESET` or `Leakage_Current`, but it will miss synonyms ("cooling" vs "chiller" only match if both words appear). Anthropic offers no embeddings API, so semantic search would need a separate embedding model; `RunbookRetriever` is a `DocumentRetriever`, so swapping in a `VectorStoreDocumentRetriever` is a one-bean change.
- **Tuning:** `monitor.rag.top-k` (3), `min-score` (2.0), `relative-cutoff` (0.5), and `monitor.rag.enabled=false` to switch it off.
- **Privacy:** excerpts are sent to the Anthropic API and are run through the same masking as everything else, so an e-mail address or IP written in a runbook will appear as `****`.
- **Not reloaded at runtime:** restart the service after editing runbooks.
