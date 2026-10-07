"""Анти-Дроп MVP — FastAPI-бэкенд.

Запуск:  .venv/bin/uvicorn main:app --reload   ->  http://localhost:8000
Документация API (Swagger): http://localhost:8000/docs
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from models import (
    AnalyzeRequest,
    AnalyzeResponse,
    QuizRequest,
    QuizResponse,
    SimChangeRequest,
    SimChangeResponse,
    StopDropAlert,
)
from src.alerts import SUPPORTED_LANGS, build_stop_drop_alert
from src.detector import analyze_transactions
from src.quiz import QUIZ, STORIES, check_quiz
from src.sim_security import start_number_change

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="Анти-Дроп API",
    description="Защита нерезидентов от вербовки в дропы: детектор транзита, Стоп-Дроп алерты, квизы, безопасная смена номера.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # MVP для хакатона; в проде ограничить доменами банка
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "anti-drop", "version": "0.2.0"}


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
    }


@app.post("/api/analyze", response_model=AnalyzeResponse, summary="Проверить транзакции на дроп-схему")
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    res = analyze_transactions([t.model_dump() for t in req.transactions])
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
        score=res["score"], level=res["level"], reasons=res["reasons"], metrics=res["metrics"], alert=alert
    )


@app.post("/api/quiz", response_model=QuizResponse, summary="Проверить квиз, начислить кешбэк")
def quiz(req: QuizRequest) -> QuizResponse:
    return QuizResponse(**check_quiz(req.answers))


@app.post("/api/sim", response_model=SimChangeResponse, summary="Безопасная смена номера")
def sim_change(req: SimChangeRequest) -> SimChangeResponse:
    out = start_number_change(req.old_phone, req.new_phone, req.otp_ok_old, req.otp_ok_new)
    if not out["ok"]:
        return SimChangeResponse(ok=False, errors=out["errors"])
    return SimChangeResponse(ok=True, **{k: v for k, v in out.items() if k != "ok"})
