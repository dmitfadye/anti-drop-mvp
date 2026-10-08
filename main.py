"""Анти-Дроп MVP — FastAPI-бэкенд.

Запуск:  .venv/bin/uvicorn main:app --reload   ->  http://localhost:8000
Документация API (Swagger, локальные ассеты): http://localhost:8000/docs

Исправления по аудиту:
- T17: Tailwind и Swagger UI — локальные файлы из static/, внешнего JS нет.
- T14/E21: CORS '*' убран — фронт same-origin, кросс-доменные вызовы не нужны.
- T02: обращение в поддержку — серверный sandbox-кейс POST /api/cases
  с устойчивым case_id и идемпотентностью (учебный, не банковское действие).
- Наблюдаемость-минимум: X-Request-ID в ответах, rules_version в analyze/health.

P1-слой (feature flags, по умолчанию выключено):
- /api/v1/communication/* — строгий снимок -> решение, язык, шаблон (демо/sandbox);
- /api/operator/*        — локальный экран оператора (loopback, без auth, только synthetic);
- /api/v1/risk/advisory   — pre-transfer advisory (advisory_only, не блокировка);
- /api/locales           — каталог локализаций и их честный статус проверки.
Ни один маршрут не выполняет банковское действие.
"""
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
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
from src.advisory import PlannedTransferAdvisoryV1, advise
from src.alerts import SUPPORTED_LANGS, build_stop_drop_alert
from src.cases import create_case, get_case
from src.communication import router as communication_router
from src.detector import analyze_transactions
from src.flags import SANDBOX_BANNER, current_flags
from src.operator import require_operator_enabled
from src.operator import router as operator_router
from src.policy import RULES_VERSION, UTC
from src.quiz import QUIZ, STORIES, check_quiz
from src.sim_security import start_number_change
from anti_drop_ml.adapter import evaluate_snapshot
from anti_drop_ml.contracts import RiskDecisionV1, RiskSnapshotV1

BASE_DIR = Path(__file__).resolve().parent
VERSION = "0.4.0-p1"

app = FastAPI(
    title="Анти-Дроп API",
    description="Учебный демонстратор: объяснимый детектор транзита, локализованные предупреждения, sandbox-кейсы и локальный экран оператора. Только синтетика, без банковских действий.",
    version=VERSION,
    docs_url=None,  # T17: Swagger из локальных файлов, не CDN
    redoc_url=None,
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.include_router(communication_router)
app.include_router(operator_router)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    if request.url.path == '/api/v1/risk/evaluate':
        # Do not echo a mistakenly submitted raw payload through validation errors.
        return JSONResponse(status_code=422, content={'detail': [{'type': error['type'], 'loc': error['loc']} for error in exc.errors()]})
    return await request_validation_exception_handler(request, exc)


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
    flags = current_flags()
    return {
        "status": "ok",
        "service": "anti-drop",
        "version": VERSION,
        "rules_version": RULES_VERSION,
        "server_time_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "demo_mode": flags.demo_mode,
        "p1_features": {
            "localization_enabled": flags.localization_enabled,
            "operator_ui_enabled": flags.operator_ui_enabled,
            "operator_export_enabled": flags.operator_export_enabled,
            "experiment_enabled": flags.experiment_enabled,
            "experiment_allow_draft_treatment": flags.experiment_allow_draft_treatment,
            "advisory_enabled": flags.advisory_enabled,
            "experiment_id": flags.experiment_id,
            "target_locale": flags.target_locale,
            "event_sink": bool(flags.operator_log_path),
        },
        "limitations": [
            "Sandbox demonstrator: no transfer is blocked, no money is frozen, no OTP or SMS is used.",
            "Score is a deterministic rule score, not a probability of fraud.",
            "The operator surface is loopback-only local demo without authentication.",
            SANDBOX_BANNER,
        ],
    }


@app.get("/api/locales", summary="Каталог локализаций P1: статус проверки перевода")
def locales() -> dict:
    from src.localization import registry

    flags = current_flags()
    packs = registry()
    return {
        "schema_version": "LocaleCatalogV1",
        "enabled": flags.localization_enabled,
        "control_locale": "ru-RU",
        "target_locale": flags.target_locale,
        "locales": packs.describe(),
        "load_errors": packs.load_errors,
        "statement": "Ровно один целевой языковой пакет. Всё, что ниже approved, помечается в UI как непроверенное.",
        "synthetic": True,
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


@app.post("/api/v1/risk/advisory", summary="Pre-transfer advisory: подсказка, НЕ блокировка перевода")
def pre_transfer_advisory(req: PlannedTransferAdvisoryV1) -> dict:
    """Advisory-only. Ничего не блокирует, не замораживает и не отклоняет.

    Возвращает status=advisory_only и banking_action='none'. Реальный банк
    должен подтвердить сигнал; в MVP это synthetic/draft.
    """
    flags = current_flags()
    if not flags.demo_mode:
        raise HTTPException(status_code=503, detail="advisory requires ANTI_DROP_DEMO_MODE=true")
    if not flags.advisory_enabled:
        raise HTTPException(status_code=503, detail="pre-transfer advisory выключен; set ANTI_DROP_ADVISORY_ENABLED=true")
    return advise(req).model_dump(mode="json")


@app.get("/operator", include_in_schema=False)
def operator_dashboard(request: Request) -> FileResponse:
    """Локальный экран наблюдения. Включается только при явных флагах + loopback."""
    require_operator_enabled(request)
    return FileResponse(BASE_DIR / "static" / "operator.html")
