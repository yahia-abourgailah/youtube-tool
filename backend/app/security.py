"""Optional API-key protection.

Set ``API_KEY`` to require an ``X-API-Key`` header (or ``Authorization: Bearer``
or ``?api_key=``) on every request. When it is unset the API stays open, which
keeps local development unchanged.
"""

import hmac
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

PUBLIC_PATHS = {"/", "/health", "/docs", "/redoc", "/openapi.json"}


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        expected = os.getenv("API_KEY", "").strip()
        if not expected or request.method == "OPTIONS" or request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        provided = request.headers.get("X-API-Key") or request.query_params.get("api_key")
        if not provided:
            authorization = request.headers.get("Authorization", "")
            if authorization.lower().startswith("bearer "):
                provided = authorization[7:].strip()

        if provided and hmac.compare_digest(provided, expected):
            return await call_next(request)

        return JSONResponse({"detail": "Invalid or missing API key"}, status_code=401)
