import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.logging import log_event


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, **extra):
        super().__init__(code)
        self.status, self.code, self.message, self.extra = status, code, message, extra


_HTTP_DEFAULTS = {
    401: ("UNAUTHENTICATED", "Entre com seu usuário e senha."),
    403: ("FORBIDDEN", "Você não tem permissão para esta ação."),
    404: ("NOT_FOUND", "Não encontrado."),
    405: ("METHOD_NOT_ALLOWED", "Ação não permitida."),
}


def _body(code: str, message: str, **extra) -> dict:
    return {"error_code": code, "message": message, **extra}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error(_: Request, exc: AppError):
        return JSONResponse(_body(exc.code, exc.message, **exc.extra), status_code=exc.status)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException):
        code, message = _HTTP_DEFAULTS.get(exc.status_code, ("HTTP_ERROR", "Não foi possível concluir a ação."))
        return JSONResponse(_body(code, message), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        fields = [".".join(str(p) for p in e["loc"][1:]) for e in exc.errors()]
        return JSONResponse(_body("VALIDATION", "Confira os dados informados.", fields=fields),
                            status_code=422)


class CatchUnhandledMiddleware:
    """Responde 500 no formato da API sem relançar a exceção.

    Um handler de `Exception` do Starlette responde, mas o ServerErrorMiddleware relança a
    exceção e o uvicorn loga o traceback com `str(exc)` (no SQLAlchemy, `[parameters: {...}]`
    traz nomes e hashes). Aqui a exceção morre: só `error_type` vai para o log.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def tracked_send(message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, tracked_send)
        except Exception as exc:  # noqa: BLE001 - fronteira final: nada escapa para o uvicorn
            log_event("unhandled_error", level=logging.ERROR, error_type=type(exc).__name__)
            if not started:
                response = JSONResponse(_body("INTERNAL", "Algo deu errado. Tente novamente."), status_code=500)
                await response(scope, receive, send)
