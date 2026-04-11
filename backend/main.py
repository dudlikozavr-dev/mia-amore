from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers.public.products import router as products_router

app = FastAPI(
    title="Mia-Amore API",
    version="1.0.0",
    docs_url="/docs" if settings.is_dev else None,   # Swagger только в dev
    redoc_url=None,
)

# CORS — разрешаем запросы с фронтенда
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
        "http://localhost:8080",   # локальная разработка фронтенда
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роуты
app.include_router(products_router)


@app.get("/health")
async def health():
    """Проверка что сервер живой"""
    return {"status": "ok", "env": settings.environment}
