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
| `POST /ai/chat` `{"question": "..."}` | Free-form Q&A; Claude calls read-only tools (`MonitorTools`) to fetch live data |

## Run

Requires Java 17+ and Maven.

```bash
# 1) start the C/C++/Python side
./build.sh
cd backend && pip install -r requirements.txt
uvicorn fastapi_app:app --port 8001

# 2) start the Spring AI service
export ANTHROPIC_API_KEY=your-key
cd ../spring_ai_service
mvn spring-boot:run
```

Environment variables: `ANTHROPIC_API_KEY` (required), `ANTHROPIC_MODEL` (default `claude-sonnet-5-5`),
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
