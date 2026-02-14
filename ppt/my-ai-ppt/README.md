# my-ai-ppt

AI-native PPT project with editable web slides and export pipeline.

## Repo structure
- `apps/web`: React + Vite editor
- `apps/api`: FastAPI API and services
- `packages/shared-types`: shared DSL contracts
- `docker-compose.yml`: local orchestration template

## Local run (without Docker)
1. Copy env:
   - `cp .env.example .env`
2. Start API:
   - `cd apps/api`
   - `python3 -m venv .venv`
   - `source .venv/bin/activate`
   - `pip install -r requirements.txt`
   - `uvicorn app.main:app --reload --port 8000`
3. Start Web (new terminal):
   - `cd apps/web`
   - `npm install`
   - `npm run dev -- --host --port 5173`
4. Open:
   - Web: `http://127.0.0.1:5173`
   - API docs: `http://127.0.0.1:8000/docs`

## Current implemented scope
- Project create/list
- DSL generate/read (LLM two-stage: semantic outline -> per-slide content/layout; no default rule fallback)
- Slide content update
- Slide-level regenerate with user instruction + locked fields
- Async task APIs for regenerate/export with status polling
- Slide operations: add/delete/reorder/change layout
- Snapshot create/list/restore
- Layout registry based slide rendering
- Export task API (`editable_text` / `image_fallback`) + downloadable `.pptx`

## API base override
Set `VITE_API_BASE` in `apps/web/.env` if API host/port changes.

## LLM required
This project now requires LLM for slide planning (default: DeepSeek, OpenAI-compatible API).
- `LLM_ENABLED=true`
- `OPENAI_API_KEY=sk-01935545a1264cb0a0bbdc53387bbd33`
- `OPENAI_BASE_URL=https://api.deepseek.com`
- `OPENAI_MODEL=deepseek-chat`

Prompt templates:
- `apps/api/app/services/llm/prompts.py`
  - `OUTLINE_SYSTEM_PROMPT`: semantic pagination outline
  - `DETAIL_SYSTEM_PROMPT`: per-slide content+layout mapping

Prompt version APIs:
- `GET /api/v1/prompts/current`
- `PUT /api/v1/prompts/current`
- `GET /api/v1/prompts/history`
- `POST /api/v1/prompts/restore`

Task APIs:
- `POST /api/v1/projects/{project_id}/tasks/generate-dsl`
- `POST /api/v1/projects/{project_id}/tasks/export-pptx`
- `GET /api/v1/projects/{project_id}/tasks/{task_id}`
