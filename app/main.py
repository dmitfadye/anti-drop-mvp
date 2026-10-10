"""Анти-Дроп MVP — FastAPI-бэкенд.

Запуск:  .venv/bin/uvicorn main:app --reload   ->  http://localhost:8000
Документация API (Swagger, локальные ассеты): http://localhost:8000/docs

Исправления по аудиту:
- T17: Tailwind и Swagger UI — локальные файлы из static/, внешнего JS нет.
- T14/E21: CORS '*' убран — фронт same-origin, кросс-доменные вызовы не нужны.
- T02: обращение в поддержку — серверный sandbox-кейс POST /api/cases
  с устойчивым case_id и идемпотентностью (учебный, не банковское действие).
- Наблюдаемость-минимум: X-Request-ID в ответах, rules_version в analyze/health.

MVP-слой sandbox-кейсов (зона ответственности):
- Хранилище PostgreSQL через src/db.py (PG_DSN), SQLite — fallback для локальной
  разработки без Docker. Кейсы переживают перезапуск сервера.
- Субъект только из заголовка X-Sandbox-Subject (src/identity.py); в теле он запрещён.
- Идемпотентность по Idempotency-Key + payload_hash (src/sandbox_cases.py).
- Единый error envelope: error_code / message / request_id (src/errors.py).
- Машиночитаемые reason_codes в /api/analyze без изменения score (src/reason_codes.py).

P1-слой (feature flags, по умолчанию выключено):
- /api/v1/communication/* — строгий снимок -> решение, язык, шаблон (демо/sandbox);
- /api/operator/*        — локальный экран оператора (loopback, без auth, только synthetic);
- /api/v1/risk/advisory   — pre-transfer advisory (advisory_only, не блокировка);
- /api/locales           — каталог локализаций и их честный статус проверки.
Ни один маршрут не выполняет банковское действие.
"""
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from models import (
    AnalyzeRequest,
    AnalyzeResponse,
    QuizRequest,
    QuizResponse,
    SandboxCaseCreate,
    SandboxCaseListResponse,
    SandboxCaseResponse,
    SimChangeRequest,
    SimChangeResponse,
    StopDropAlert,
)
from src.advisory import PlannedTransferAdvisoryV1, advise
from src.alerts import SUPPORTED_LANGS, build_stop_drop_alert
from src.communication import router as communication_router
from src.config import (
    DATABASE_PATH,
    DEFAULT_LIST_LIMIT,
    MAX_LIST_LIMIT,
    NOTICES,
    SANDBOX_MODE,
    configure_logging,
    get_logger,
)
from src.db import get_db, init_db
from src.detector import analyze_transactions
from src.errors import ApiError, ErrorDetail, error_body, router_error
from src.flags import SANDBOX_BANNER, current_flags
from src.identity import get_sandbox_subject, subject_hash_prefix
from src.operator import require_operator_enabled
from src.operator import router as operator_router
from src.policy import RULES_VERSION, UTC
from src.quiz import QUIZ, STORIES, check_quiz
from src.sandbox_cases import compute_payload_hash, create_case as create_sandbox_case, \
    get_case_for_subject, get_idempotency_key, list_cases_for_subject
from src.sim_security import start_number_change
from anti_drop_ml.adapter import evaluate_snapshot
from anti_drop_ml.contracts import RiskDecisionV1, RiskSnapshotV1

configure_logging()
log = get_logger("anti_drop")

BASE_DIR = Path(__file__).resolve().parent
VERSION = "0.4.0-p1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Схема БД создаётся до первого запроса. on_event устарел — lifespan уместнее.

    PG_DSN задан — поднимается пул psycopg2 к PostgreSQL, иначе SQLite-файл.
    """
    init_db()
    log.info("startup app_version=%s database_path=%s sandbox_mode=%s",
             VERSION, DATABASE_PATH.resolve(), SANDBOX_MODE)
    yield
    log.info("shutdown app_version=%s", VERSION)

app = FastAPI(
    title="Анти-Дроп API",
    description="Учебный демонстратор: объяснимый детектор транзита, локализованные предупреждения, sandbox-кейсы и локальный экран оператора. Только синтетика, без банковских действий.",
    version=VERSION,
    lifespan=lifespan,
    docs_url=None,  # T17: Swagger из локальных файлов, не CDN
    redoc_url=None,
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.include_router(communication_router)
app.include_router(operator_router)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex}"
    request.state.request_id = request_id
    started = datetime.now(UTC)
    try:
        response = await call_next(request)
    except Exception:
        # Обработчик ниже не всегда успевает проставить заголовок — дублируем здесь.
        log.exception("request_id=%s method=%s endpoint=%s status=500 unhandled=true",
                      request_id, request.method, request.url.path)
        response = JSONResponse(
            status_code=500,
            content=error_body(request_id, ApiError(
                500, "INTERNAL_ERROR", "Внутренняя ошибка сервиса. Повторите попытку позже.")),
            headers={"X-Request-ID": request_id},
        )
    latency_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
    response.headers["X-Request-ID"] = request_id
    log.info("request_id=%s method=%s endpoint=%s status=%s latency_ms=%d",
             request_id, request.method, request.url.path, response.status_code, latency_ms)
    return response


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or f"req_{uuid.uuid4().hex}"


def _log_error(request: Request, exc: ApiError) -> None:
    subject = request.headers.get("X-Sandbox-Subject")
    # Логируем хеш субъекта, а не сам идентификатор: в логах он не нужен, а восстановить его нельзя.
    subject_hash = subject_hash_prefix(subject) if subject else None
    log.error("request_id=%s method=%s endpoint=%s status=%s error_code=%s subject_hash=%s",
              _request_id(request), request.method, request.url.path,
              exc.status_code, exc.error_code, subject_hash)


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    _log_error(request, exc)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(_request_id(request), exc),
        headers={**exc.headers, "X-Request-ID": _request_id(request)} if exc.headers
        else {"X-Request-ID": _request_id(request)},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Pydantic-ошибки -> тот же envelope, чтобы клиент видел error_code и field."""
    if request.url.path == '/api/v1/risk/evaluate':
        # Не отдаём отправленное тело обратно через ошибки валидации — только тип и путь.
        return JSONResponse(status_code=422, content={'detail': [{'type': error['type'], 'loc': error['loc']} for error in exc.errors()]})
    details = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", ()) if p != "body") or None
        details.append(ErrorDetail(field=loc, message=err.get("msg")))
    err = ApiError(422, "VALIDATION_ERROR", "Проверьте переданные данные.", details=details)
    _log_error(request, err)
    return JSONResponse(status_code=422, content=error_body(_request_id(request), err),
                        headers={"X-Request-ID": _request_id(request)})


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Покрывает и FastAPI HTTPException, и роутерные 404/405: FastAPI HTTPException
    наследуется от Starlette HTTPException, а обработчик на базовом класове ловит оба."""
    err = router_error(exc.status_code, exc.detail)
    _log_error(request, err)
    return JSONResponse(status_code=err.status_code, content=error_body(_request_id(request), err),
                        headers={"X-Request-ID": _request_id(request), **(exc.headers or {})})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Клиенту не отдаём traceback; в лог — request_id для разбора."""
    request_id = _request_id(request)
    log.exception("request_id=%s method=%s endpoint=%s unhandled=%s",
                  request_id, request.method, request.url.path, type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content=error_body(request_id, ApiError(
            500, "INTERNAL_ERROR", "Внутренняя ошибка сервиса. Повторите попытку позже.")),
        headers={"X-Request-ID": request_id},
    )


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
    evaluation_id = "eval_" + uuid.uuid4().hex
    return AnalyzeResponse(
        score=res["score"],
        level=res["level"],
        reasons=res["reasons"],
        reason_codes=res.get("reason_codes", []),
        metrics=res["metrics"],
        alert=alert,
        rules_version=res["metrics"].get("rules_version", RULES_VERSION),
        evaluation_id=evaluation_id,
    )


@app.post("/api/v1/risk/evaluate", response_model=RiskDecisionV1, summary="Strict synthetic risk snapshot (score is not probability)")
def evaluate_risk(req: RiskSnapshotV1) -> RiskDecisionV1:
    return evaluate_snapshot(req)


@app.post("/api/quiz", response_model=QuizResponse, summary="Проверить квиз (учебный приз, без выплат)")
def quiz(req: QuizRequest) -> QuizResponse:
    return QuizResponse(**check_quiz(req.answers))


@app.post("/api/sim", response_model=SimChangeResponse, summary="Тренажёр смены номера (SMS не отправляются)")
def sim_change(
    req: SimChangeRequest,
    subject: str = Header(..., alias="X-Sandbox-Subject"),
    db=Depends(get_db),
) -> SimChangeResponse:
    from src.sim_security import canonical_phone

    # Проверить, что старый номер принадлежит subject
    row = db.execute("SELECT phone FROM users WHERE user_id=?", (subject,)).fetchone()
    if not row or canonical_phone(row["phone"]) != canonical_phone(req.old_phone):
        return SimChangeResponse(ok=False, errors=["Номер не принадлежит вам или неверный"])

    out = start_number_change(req.old_phone, req.new_phone, req.otp_ok_old, req.otp_ok_new)
    if not out["ok"]:
        return SimChangeResponse(ok=False, errors=out["errors"])

    # Обновляем телефон в БД
    new_c = canonical_phone(req.new_phone)
    db.execute(
        "UPDATE users SET phone=?, phone_verified_at=datetime('now') WHERE user_id=?",
        (new_c, subject)
    )
    db.commit()
    return SimChangeResponse(ok=True, **{k: v for k, v in out.items() if k != "ok"})


@app.post("/api/cases", include_in_schema=False, deprecated=True)
def create_support_case() -> None:
    """Legacy-путь отключён: хранил кейсы в памяти процесса и не знал про субъект.

    Тело намеренно не принимается: иначе FastAPI проверит его раньше тела роута
    и вернул бы 422 вместо однозначного 410.
    """
    raise ApiError(410, "LEGACY_CASES_DISABLED",
                   "Этот учебный эндпоинт отключён. Используйте /sandbox/cases.",
                   headers={"Deprecation": "true"})


@app.get("/api/cases/{case_id}", include_in_schema=False, deprecated=True)
def case_status(case_id: str) -> None:
    raise ApiError(410, "LEGACY_CASES_DISABLED",
                   "Этот учебный эндпоинт отключён. Используйте /sandbox/cases/{case_id}.",
                   headers={"Deprecation": "true"})


# ---------------------------------------------------------------------------
# Sandbox cases: подтверждённое обращение вместо имитации «поддержки».
# Всё здесь — песочница. Реальной блокировки, SMS, выплаты и тикета в
# банковскую систему не происходит.
# ---------------------------------------------------------------------------


def _notice(lang: str) -> str:
    return NOTICES.get(lang, NOTICES["ru"])


def _to_response(case: dict) -> SandboxCaseResponse:
    return SandboxCaseResponse(**case, notice=_notice(case["selected_language"]))


REQUIRED_SANDBOX_HEADERS = ("X-Sandbox-Subject", "Idempotency-Key")


def custom_openapi() -> dict:
    """Помечает sandbox-заголовки обязательными в схеме.

    В зависимостях они объявлены как Header(default=None), иначе FastAPI отвечал бы
    своим 422 вместо наших SUBJECT_REQUIRED/MISSING_IDEMPOTENCY_KEY с error_code.
    Схема при этом должна честно показывать, что заголовки обязательны.
    """
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title, version=app.version, description=app.description, routes=app.routes
    )
    for path, item in schema.get("paths", {}).items():
        if not path.startswith("/sandbox/cases"):
            continue
        for operation in item.values():
            for param in operation.get("parameters", []):
                if param.get("name") in REQUIRED_SANDBOX_HEADERS and param.get("in") == "header":
                    param["required"] = True
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi


@app.post("/sandbox/cases", response_model=SandboxCaseResponse,
          status_code=201,
          summary="Создать sandbox-кейс обращения (идемпотентно, без банковского действия)")
def create_sandbox_case_endpoint(
    request: Request,
    response: Response,
    body: SandboxCaseCreate,
    subject_ref: Annotated[str, Depends(get_sandbox_subject)],
    idempotency_key: Annotated[str, Depends(get_idempotency_key)],
    conn=Depends(get_db),
) -> SandboxCaseResponse:
    if not SANDBOX_MODE:
        raise ApiError(503, "SANDBOX_DISABLED", "Песочница отключена конфигурацией (SANDBOX_MODE=false).")

    case, replayed = create_sandbox_case(
        conn,
        subject_ref=subject_ref,
        idempotency_key=idempotency_key,
        evaluation_id=body.evaluation_id,
        selected_language=body.selected_language,
        contact_reason=body.contact_reason,
        payload_hash=compute_payload_hash(body.normalized()),
    )
    response.headers["Idempotency-Replayed"] = "true" if replayed else "false"
    if replayed:
        # Тот же ключ + то же тело = тот же ресурс, а не новый кейс.
        response.status_code = 200
    log.info("request_id=%s endpoint=POST /sandbox/cases subject_hash=%s case_id=%s replayed=%s",
             _request_id(request), subject_hash_prefix(subject_ref), case["case_id"], replayed)
    return _to_response(case)


@app.get("/sandbox/cases", response_model=SandboxCaseListResponse,
         summary="Список sandbox-кейсов текущего субъекта (только свои)")
def list_sandbox_cases(
    request: Request,
    subject_ref: Annotated[str, Depends(get_sandbox_subject)],
    limit: Annotated[int, Query(ge=1, le=MAX_LIST_LIMIT,
                                description="Размер страницы (1-100)")] = DEFAULT_LIST_LIMIT,
    offset: Annotated[int, Query(ge=0, description="Смещение от начала выборки")] = 0,
    conn=Depends(get_db),
) -> SandboxCaseListResponse:
    # limit/offset валидируются Query: отрицательные значения -> 422, а не молчаливая починка.
    items, total = list_cases_for_subject(conn, subject_ref, limit, offset)
    log.info("request_id=%s endpoint=GET /sandbox/cases subject_hash=%s total_count=%d",
             _request_id(request), subject_hash_prefix(subject_ref), total)
    return SandboxCaseListResponse(items=[_to_response(c) for c in items],
                                   limit=limit, offset=offset, total_count=total)


@app.get("/sandbox/cases/{case_id}", response_model=SandboxCaseResponse,
         summary="Статус своего sandbox-кейса (чужой кейс неразличим от отсутствующего)")
def get_sandbox_case(
    request: Request,
    case_id: str,
    subject_ref: Annotated[str, Depends(get_sandbox_subject)],
    conn=Depends(get_db),
) -> SandboxCaseResponse:
    case = get_case_for_subject(conn, case_id, subject_ref)
    if case is None:
# 404, а не 403: иначе по коду ответа можно проверить существование чужого кейса.
        raise ApiError(404, "CASE_NOT_FOUND", "Кейс не найден.")
    return _to_response(case)


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
