from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.prompts import router as prompts_router
from app.routers.projects import router as projects_router

app = FastAPI(title="my-ai-ppt api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects_router)
app.include_router(prompts_router)


@app.get("/health")
def health() -> dict:
    return {"ok": True}
