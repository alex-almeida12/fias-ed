import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

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

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception):
        log_event("unhandled_error", level=logging.ERROR, error_type=type(exc).__name__)
        return JSONResponse(_body("INTERNAL", "Algo deu errado. Tente novamente."), status_code=500)
