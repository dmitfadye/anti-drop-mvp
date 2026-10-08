"""Synthetic FastAPI backend with owned PostgreSQL sandbox cases.

Local Swagger assets, bounded/redacted input and server request IDs.
Legacy analysis remains available; unscoped memory cases are retired.
No bank actions or external inference calls are performed.
"""
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import SQLAlchemyError
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from models import (
    AnalyzeRequest,
    AnalyzeResponse,
    CaseCreateRequest,
    QuizRequest,
    QuizResponse,
    SimChangeRequest,
    SimChangeResponse,
    StopDropAlert,
    SupportCase,
)
from src.alerts import SUPPORTED_LANGS, build_stop_drop_alert
from src.database import DatabaseNotConfigured
from src.http_boundary import RequestBoundary
from src.sandbox import ErrorModel, router as sandbox_router
from src.detector import analyze_transactions
from src.policy import RULES_VERSION, UTC
from src.quiz import QUIZ, STORIES, check_quiz
from src.sim_security import start_number_change
from anti_drop_ml.adapter import evaluate_snapshot
from anti_drop_ml.contracts import RiskDecisionV1, RiskSnapshotV1

BASE_DIR = Path(__file__).resolve().parent
VERSION = "0.4.0"

app = FastAPI(
    title="Анти-Дроп API",
    description="Учебный демонстратор: объяснимый детектор транзита, Стоп-Дроп алерты, квизы, тренажёр смены номера. Только синтетика, без банковских действий.",
    version=VERSION,
    docs_url=None,  # T17: Swagger из локальных файлов, не CDN
    redoc_url=None,
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.include_router(sandbox_router, responses={code: {'model': ErrorModel} for code in (401, 403, 404, 409, 410, 413, 422, 503)})


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    errors = [{'type': error['type'], 'loc': error['loc'][:-1] + ('[unknown_field]',) if error['type'] == 'extra_forbidden' else error['loc']} for error in exc.errors()]
    return JSONResponse(status_code=422, content={'error_code': 'VALIDATION_ERROR',
        'field': '.'.join(str(part) for part in errors[0]['loc']) if errors else None,
        'detail': 'Request validation failed', 'errors': errors, 'request_id': request.state.request_id})


@app.exception_handler(StarletteHTTPException)
async def http_error(request, exc):
    return JSONResponse(status_code=exc.status_code, content={'error_code': {
        401: 'UNAUTHORIZED', 403: 'FORBIDDEN', 404: 'NOT_FOUND', 409: 'IDEMPOTENCY_CONFLICT',
        410: 'LEGACY_CASE_API_RETIRED', 422: 'VALIDATION_ERROR', 503: 'SERVICE_UNAVAILABLE',
    }.get(exc.status_code, 'REQUEST_REJECTED'), 'field': None, 'detail': exc.detail,
        'request_id': request.state.request_id}, headers=exc.headers)


@app.exception_handler(SQLAlchemyError)
@app.exception_handler(DatabaseNotConfigured)
async def database_error(request, exc):
    # Never expose SQL, connection credentials, bind parameters or raw submitted data.
    return JSONResponse(status_code=503, content={'error_code': 'DATABASE_UNAVAILABLE',
        'field': None, 'detail': 'Persistent sandbox is unavailable; no success was confirmed',
        'request_id': request.state.request_id})


@app.middleware("http")
async def request_id_middleware(request, call_next):
    request_id = getattr(request.state, 'request_id', uuid.uuid4().hex)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/docs", include_in_schema=False)
def docs():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="Анти-Дроп API",
        swagger_js_url="/static/swagger/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger/swagger-ui.css",
        swagger_favicon_url="/static/swagger/favicon.png",
    )


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "anti-drop",
        "version": VERSION,
        "rules_version": RULES_VERSION,
        "server_time_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "demo_mode": True,
    }


@app.get("/api/langs")
def langs() -> dict[str, str]:
    return SUPPORTED_LANGS


@app.get("/api/content")
def content() -> dict:
    """Публичный контент онбординга. Правильные ответы НЕ отдаём — проверка на сервере."""
    return {
        "stories": STORIES,
        "quiz": [{"q": item["q"], "options": item["options"]} for item in QUIZ],
        "cashback": 100,
        "pass_threshold": 4,
        "reward_note": "Учебный приз: в демо деньги не начисляются.",
        "demo_mode": True,
    }


@app.post("/api/analyze", response_model=AnalyzeResponse, summary="Проверить транзакции одного клиента на дроп-схему")
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    # Compatibility replay uses latest historical event, capped at boundary time.
    # Strict snapshots always require an explicit deterministic analysis_at.
    analysis_at = req.analysis_at or min(max((t.ts for t in req.transactions), default=datetime.now(UTC)), datetime.now(UTC))
    res = analyze_transactions(
        [t.model_dump() for t in req.transactions],
        now=analysis_at,
    )
    alert = None
    if res["level"] == "RED":
        m = res["metrics"]
        alert = StopDropAlert(
            **build_stop_drop_alert(
                req.lang,
                m.get("small_incoming_60m_sum", 0),
                m.get("small_incoming_60m_senders", 0) if "large_outbound_after_inbound" in m.get("score_contributions", {}) else 0,
                res["score"],
            )
        )
    return AnalyzeResponse(
        score=res["score"],
        level=res["level"],
        reasons=res["reasons"],
        metrics=res["metrics"],
        alert=alert,
        rules_version=res["metrics"].get("rules_version", RULES_VERSION),
    )


@app.post("/api/v1/risk/evaluate", response_model=RiskDecisionV1, summary="Strict synthetic risk snapshot (score is not probability)")
def evaluate_risk(req: RiskSnapshotV1) -> RiskDecisionV1:
    return evaluate_snapshot(req)


@app.post("/api/quiz", response_model=QuizResponse, summary="Проверить квиз (учебный приз, без выплат)")
def quiz(req: QuizRequest) -> QuizResponse:
    return QuizResponse(**check_quiz(req.answers))


@app.post("/api/sim", response_model=SimChangeResponse, summary="Тренажёр смены номера (SMS не отправляются)")
def sim_change(req: SimChangeRequest) -> SimChangeResponse:
    out = start_number_change(req.old_phone, req.new_phone, req.otp_ok_old, req.otp_ok_new)
    if not out["ok"]:
        return SimChangeResponse(ok=False, errors=out["errors"])
    return SimChangeResponse(ok=True, **{k: v for k, v in out.items() if k != "ok"})


@app.post("/api/cases", response_model=SupportCase, deprecated=True, responses={410: {'model': ErrorModel}}, summary="Устаревший API кейсов: заменён /sandbox/cases")
def create_support_case(req: CaseCreateRequest) -> SupportCase:
    raise HTTPException(410, 'Unscoped memory cases retired; use authenticated POST /sandbox/cases with a persisted evaluation')


@app.get("/api/cases/{case_id}", response_model=SupportCase, deprecated=True, responses={410: {'model': ErrorModel}}, summary="Устаревший API кейсов: заменён /sandbox/cases/{id}")
def case_status(case_id: str) -> SupportCase:
    raise HTTPException(410, 'Unscoped memory cases retired; use authenticated GET /sandbox/cases/{case_id}')


app.add_middleware(RequestBoundary)
