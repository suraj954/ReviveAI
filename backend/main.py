from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.dashboard import router as dashboard_router
from app.api.orders import router as orders_router
from app.api.webhooks import router as webhooks_router


app = FastAPI(
    title="ReviveAI",
    description="AI-powered revenue recovery orchestration platform",
    version="0.1.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(orders_router)
app.include_router(webhooks_router)
app.include_router(dashboard_router)


@app.get("/")
def root():
    return {
        "name": "ReviveAI",
        "status": "running",
        "version": "0.1.0",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
    }