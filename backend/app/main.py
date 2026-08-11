from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.routes import admin, areas, auth, dashboard, inventory, operations, payments, retailers, sales, stock_requests
from app.core.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin], allow_credentials=True, allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"], allow_headers=["Content-Type", "Accept"])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    if settings.environment == "production": response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": {"message": exc.detail, "status": exc.status_code}})


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    errors = [{"field": ".".join(str(part) for part in item["loc"][1:]), "message": item["msg"]} for item in exc.errors()]
    return JSONResponse(status_code=422, content={"error": {"message": "Request validation failed", "status": 422, "details": errors}})


@app.exception_handler(Exception)
async def server_error(_: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": {"message": "An unexpected error occurred", "status": 500}})


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok"}


app.include_router(auth.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(areas.router, prefix="/api/v1")
app.include_router(operations.router, prefix="/api/v1")
app.include_router(inventory.router, prefix="/api/v1")
app.include_router(retailers.router, prefix="/api/v1")
app.include_router(sales.router, prefix="/api/v1")
app.include_router(stock_requests.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")
