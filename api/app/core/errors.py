"""Error handling.

Every error response has the same shape as the Node server's:
    {"success": false, "message": "..."}
so the React client works with either backend during the migration.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Raise from any route to return an error with a status code."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _error(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"success": False, "message": message})


def _validation_message(exc: RequestValidationError) -> str:
    first = exc.errors()[0]
    # loc looks like ("body", "prompt"); skip the "body"/"query" part.
    field = ".".join(str(part) for part in first["loc"][1:])
    return f"{field}: {first['msg']}" if field else first["msg"]


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return _error(exc.status_code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # 400 instead of FastAPI's default 422, to match the existing API.
        return _error(400, _validation_message(exc))

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _error(exc.status_code, str(exc.detail))

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # Log the details, but never send them to the client.
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return _error(500, "Something went wrong. Please try again.")
