import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers.public.products import router as products_router
from app.routers.public.buyers import router as buyers_router
from app.routers.public.orders import router as orders_router
from app.routers.admin.categories import router as admin_categories_router
from app.routers.admin.products import router as admin_products_router
from app.routers.admin.orders import router as admin_orders_router
from app.routers.admin.broadcast import router as admin_broadcast_router
from app.routers.webhook import router as webhook_router, initialize_bot, shutdown_bot
from tasks.scheduler import setup_scheduler

BASE_DIR = os.path.dirname(__file__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown: бот + планировщик."""
    scheduler = setup_scheduler()
    scheduler.start()
    await initialize_bot()

    yield

    scheduler.shutdown(wait=False)
    await shutdown_bot()


app = FastAPI(
    title="Mia-Amore API",
    version="1.0.0",
    docs_url="/docs" if settings.is_dev else None,
    redoc_url=None,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Публичные API (каталог, заказы, покупатели) ───────────────────────────────
app.include_router(products_router)
app.include_router(buyers_router)
app.include_router(orders_router)

# ── Админские API ─────────────────────────────────────────────────────────────
app.include_router(admin_categories_router)
app.include_router(admin_products_router)
app.include_router(admin_orders_router)
app.include_router(admin_broadcast_router)

# ── Telegram webhook ──────────────────────────────────────────────────────────
app.include_router(webhook_router)

# ── Статика: загруженные фото (локальная разработка) ─────────────────────────
static_uploads = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(static_uploads, exist_ok=True)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# ── Веб-панель администратора ─────────────────────────────────────────────────
admin_panel_dir = os.path.join(BASE_DIR, "admin_panel")
if os.path.isdir(admin_panel_dir):
    app.mount("/admin", StaticFiles(directory=admin_panel_dir, html=True), name="admin_panel")


@app.get("/health")
async def health():
    """Проверка что сервер живой"""
    return {"status": "ok", "env": settings.environment}
