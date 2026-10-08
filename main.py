"""Анти-Дроп MVP — FastAPI-бэкенд.

Запуск:  .venv/bin/uvicorn main:app --reload   ->  http://localhost:8000
Документация API (Swagger, локальные ассеты): http://localhost:8000/docs

Исправления по аудиту:
- T17: Tailwind и Swagger UI — локальные файлы из static/, внешнего JS нет.
- T14/E21: CORS '*' убран — фронт same-origin, кросс-доменные вызовы не нужны.
- T02: обращение в поддержку — серверный sandbox-кейс POST /api/cases
  с устойчивым case_id и идемпотентностью (учебный, не банковское действие).
- Наблюдаемость-минимум: X-Request-ID в ответах, rules_version в analyze/health.
"""
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
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
from src.cases import create_case, get_case
from src.detector import analyze_transactions
from src.policy import RULES_VERSION, UTC
from src.quiz import QUIZ, STORIES, check_quiz
from src.sim_security import start_number_change

BASE_DIR = Path(__file__).resolve().parent
VERSION = "0.3.0"

app = FastAPI(
    title="Анти-Дроп API",
    description="Учебный демонстратор: объяснимый детектор транзита, Стоп-Дроп алерты, квизы, тренажёр смены номера. Только синтетика, без банковских действий.",
    version=VERSION,
    docs_url=None,  # T17: Swagger из локальных файлов, не CDN
    redoc_url=None,
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.middleware("http")
async def request_id_middleware(request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
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
    res = analyze_transactions(
        [t.model_dump() for t in req.transactions],
        now=req.analysis_at,
    )
    alert = None
    if res["level"] == "RED":
        m = res["metrics"]
        alert = StopDropAlert(
            **build_stop_drop_alert(
                req.lang,
                m.get("small_incoming_60m_sum", 0),
                m.get("small_incoming_60m_senders", 0),
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


@app.post("/api/quiz", response_model=QuizResponse, summary="Проверить квиз (учебный приз, без выплат)")
def quiz(req: QuizRequest) -> QuizResponse:
    return QuizResponse(**check_quiz(req.answers))


@app.post("/api/sim", response_model=SimChangeResponse, summary="Тренажёр смены номера (SMS не отправляются)")
def sim_change(req: SimChangeRequest) -> SimChangeResponse:
    out = start_number_change(req.old_phone, req.new_phone, req.otp_ok_old, req.otp_ok_new)
    if not out["ok"]:
        return SimChangeResponse(ok=False, errors=out["errors"])
    return SimChangeResponse(ok=True, **{k: v for k, v in out.items() if k != "ok"})


@app.post("/api/cases", response_model=SupportCase, summary="Создать учебный кейс обращения (sandbox)")
def create_support_case(req: CaseCreateRequest) -> SupportCase:
    case = create_case(req.summary, req.lang, req.score, req.idempotency_key)
    return SupportCase(**{k: v for k, v in case.items() if k != "deduped"})


@app.get("/api/cases/{case_id}", response_model=SupportCase, summary="Статус учебного кейса")
def case_status(case_id: str) -> SupportCase:
    case = get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Кейс не найден (хранилище — память одного процесса)")
    return SupportCase(**case)
