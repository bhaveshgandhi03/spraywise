"""SprayWise API and static site (single FastAPI service)."""
from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import engine, llm, samples
from .config import load_settings
from .security import (
    SECURITY_HEADERS, DailyBudget, RateLimiter, client_key, sniff_image, today_ist,
)

log = logging.getLogger("spraywise")
settings = load_settings()
app = FastAPI(title="SprayWise", version="1.0.0", docs_url=None, redoc_url=None, openapi_url=None)

limit_analyze = RateLimiter(settings.rate_analyze_per_min)
limit_other = RateLimiter(settings.rate_other_per_min)
budget = DailyBudget(settings.max_llm_calls_per_day)

CropName = Literal["tomato", "groundnut", "paddy", "other"]
Lang = Literal["en", "hi", "te", "ta"]


class ApiError(Exception):
    def __init__(self, status: int, code: str) -> None:
        self.status, self.code = status, code


@app.exception_handler(ApiError)
async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse({"error": {"code": exc.code}}, status_code=exc.status)


@app.middleware("http")
async def _headers(request: Request, call_next):
    resp = await call_next(request)
    for k, v in SECURITY_HEADERS.items():
        resp.headers.setdefault(k, v)
    if request.url.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


def _guard(request: Request, limiter: RateLimiter) -> None:
    key = client_key(request.headers, request.client.host if request.client else "")
    if not limiter.allow(key):
        raise ApiError(429, "rate")


# ---------------------------------------------------------------- models
class IngredientIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    percent: str | None = Field(default=None, max_length=30)


class LabelIn(BaseModel):
    product_name: str | None = Field(default=None, max_length=80)
    ingredients: list[IngredientIn] = Field(min_length=1, max_length=6)
    formulation: str | None = Field(default=None, max_length=30)
    toxicity_color: Literal["red", "yellow", "blue", "green"] | None = None
    toxicity_words: str | None = Field(default=None, max_length=60)
    printed_crops: list[str] = Field(default_factory=list, max_length=15)
    printed_dose: str | None = Field(default=None, max_length=120)
    printed_waiting_period: str | None = Field(default=None, max_length=120)
    registration_number: str | None = Field(default=None, max_length=60)
    batch_number: str | None = Field(default=None, max_length=40)
    expiry_date: str | None = Field(default=None, max_length=30)
    manufacturer: str | None = Field(default=None, max_length=80)
    precautions: list[str] = Field(default_factory=list, max_length=8)


class CheckIn(BaseModel):
    label: LabelIn
    crop: CropName = "other"
    lang: Lang = "en"


class PlanItem(BaseModel):
    label: LabelIn
    crop: CropName = "other"
    spray_date: date


class PlanIn(BaseModel):
    items: list[PlanItem] = Field(min_length=1, max_length=12)


# ---------------------------------------------------------------- helpers
def _finish(label: dict[str, Any], crop: str, lang: str, source: str, with_summary: bool) -> dict[str, Any]:
    result = engine.analyze({**label, "source": source}, crop)
    result["source"] = source
    result["summary"] = None
    if with_summary and settings.api_key and settings.enable_explanation and label.get("ingredients"):
        if budget.consume():
            result["summary"] = llm.explain(engine.facts_for_summary(result), lang, settings)
    return result


# ---------------------------------------------------------------- routes
@app.get("/api/health")
def health() -> dict[str, Any]:
    ref = engine.load_reference()
    return {
        "status": "ok",
        "photo_reading": bool(settings.api_key),
        "products": len(ref["products"]),
        "banned_entries": len(ref["banned"]),
        "llm_calls_today": budget.used,
    }


@app.get("/api/meta")
def meta(request: Request) -> dict[str, Any]:
    _guard(request, limit_other)
    ref = engine.load_reference()
    return {
        "crops": list(engine.CROPS),
        "ingredients": engine.suggestions(),
        "photo_reading": bool(settings.api_key),
        "sources": ref["sources"],
        "known_gaps": ref["pest_meta"]["known_gaps"],
        "products": len(ref["products"]),
        "banned_entries": len(ref["banned"]),
    }


@app.get("/api/samples")
def list_samples(request: Request) -> list[dict[str, str]]:
    _guard(request, limit_other)
    return [{"id": k, "title": v["title"], "crop": v["default_crop"]} for k, v in samples.build(today_ist()).items()]


@app.get("/api/sample/{sample_id}")
def sample(sample_id: str, request: Request, crop: CropName | None = None, lang: Lang = "en") -> dict[str, Any]:
    _guard(request, limit_other)
    s = samples.build(today_ist()).get(sample_id)
    if not s:
        raise ApiError(404, "notfound")
    res = _finish(s["label"], crop or s["default_crop"], lang, "sample", with_summary=False)
    res["sample_title"] = s["title"]
    return res


@app.post("/api/check")
def check(body: CheckIn, request: Request) -> dict[str, Any]:
    _guard(request, limit_other)
    return _finish(body.label.model_dump(), body.crop, body.lang, "manual", with_summary=True)


@app.post("/api/plan")
def make_plan(body: PlanIn, request: Request) -> dict[str, Any]:
    _guard(request, limit_other)
    today = today_ist()
    for it in body.items:
        if abs((it.spray_date - today).days) > 400:
            raise ApiError(422, "baddate")
    return engine.plan(
        [{"label": it.label.model_dump(), "crop": it.crop, "spray_date": it.spray_date} for it in body.items], today
    )


@app.post("/api/analyze")
async def analyze_photo(
    request: Request,
    image: UploadFile = File(...),
    crop: CropName = Form("other"),
    lang: Lang = Form("en"),
) -> dict[str, Any]:
    _guard(request, limit_analyze)
    if not settings.api_key:
        raise ApiError(503, "nollm")

    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > settings.max_image_bytes + 200_000:
        raise ApiError(413, "toolarge")
    data = await image.read(settings.max_image_bytes + 1)  # read into memory only; never written to disk
    if len(data) > settings.max_image_bytes:
        raise ApiError(413, "toolarge")
    media_type = sniff_image(data)
    if not media_type:
        raise ApiError(415, "badimage")

    if not budget.consume():
        raise ApiError(503, "budget")
    try:
        label = llm.extract_label(data, media_type, settings)
    except llm.LLMUnavailable:
        raise ApiError(503, "nollm")
    except llm.LLMError as exc:
        log.warning("label extraction failed: %s", exc)
        raise ApiError(502, "llm")
    finally:
        del data  # drop the photo as soon as it has been read

    if not label["readable"] or not label["ingredients"]:
        raise ApiError(422, "unreadable")
    return _finish(label, crop, lang, "scan", with_summary=True)


# Static site last, so /api/* wins.
STATIC = Path(__file__).resolve().parent.parent / "static"
app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
