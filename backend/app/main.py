import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded

from app.api.v1 import (
    addresses, admin, auth, cart, locations, offers, orders, owner, owner_extra,
    payments, product_extras, products,
)
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.core.rate_limit import limiter
from app.services.order_service import run_expiry_job

logger = logging.getLogger("fruithub")


async def _expiry_loop():
    while True:
        try:
            await asyncio.to_thread(run_expiry_job)
        except Exception:
            logger.exception("Expiry loop error")
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_expiry_loop())
    yield
    task.cancel()


app = FastAPI(title="FruitHub API", version="1.0", lifespan=lifespan)
app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


register_error_handlers(app)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"success": False, "error": {
            "code": "TOO_MANY_REQUESTS",
            "message": "Too many attempts. Please wait a minute and try again.",
        }},
    )


os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# Public and customer
app.include_router(auth.router, prefix="/api/v1")
app.include_router(products.router, prefix="/api/v1")
app.include_router(product_extras.router, prefix="/api/v1")
app.include_router(offers.router, prefix="/api/v1")
app.include_router(locations.router, prefix="/api/v1")
app.include_router(addresses.router, prefix="/api/v1")
app.include_router(cart.router, prefix="/api/v1")
app.include_router(orders.router, prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")
# Owner
app.include_router(owner.router, prefix="/api/v1")
app.include_router(owner_extra.router, prefix="/api/v1")
# Admin
app.include_router(admin.router, prefix="/api/v1")


@app.get("/api/v1/health")
def health():
    return {"success": True, "status": "FruitHub is running"}