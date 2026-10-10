import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from google.genai import client as genai_client

from app import llm, main
from app.config import Settings

ROOT = Path(__file__).resolve().parent.parent
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64
GOOD_LABEL = {
    "readable": True, "product_name": "Test", "ingredients": [{"name": "Hexaconazole", "percent": "5%"}],
    "formulation": "EC", "toxicity_color": "blue", "toxicity_words": None, "printed_crops": ["Paddy"],
    "printed_dose": None, "printed_waiting_period": "40 days", "registration_number": "CIR-1",
    "batch_number": None, "manufacture_date": None, "expiry_date": "08/2030", "manufacturer": None, "precautions": [],
}


@pytest.fixture()
def client(monkeypatch):
    s = Settings(api_key="test-key", model="m", llm_timeout_s=5, max_llm_calls_per_day=50,
                 max_image_bytes=1024 * 1024, rate_analyze_per_min=100, rate_other_per_min=1000, enable_explanation=True)
    monkeypatch.setattr(main, "settings", s)
    monkeypatch.setattr(main, "budget", main.DailyBudget(50))
    monkeypatch.setattr(main, "limit_analyze", main.RateLimiter(100))
    monkeypatch.setattr(main, "limit_other", main.RateLimiter(1000))
    monkeypatch.setattr(llm, "extract_label", lambda img, mt, st: dict(GOOD_LABEL))
    monkeypatch.setattr(llm, "explain", lambda facts, lang, st: None)
    return TestClient(main.app)


def post_photo(client, data=JPEG, name="a.jpg", ctype="image/jpeg"):
    return client.post("/api/read-label", files={"image": (name, data, ctype)})


def test_health_and_static_site(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok" and r.json()["photo_reading"] is True
    assert r.json()["products"] >= 30
    home = client.get("/")
    assert home.status_code == 200 and "SprayWise" in home.text and "KisanRakshak" not in home.text
    assert client.get("/i18n.json").status_code == 200


def test_metadata_exposes_source_dates_and_coverage_gaps(client):
    r = client.get("/api/meta")
    assert r.status_code == 200
    body = r.json()
    assert body["known_gaps"]
    assert body["ban_verification_notes"]
    assert body["sources"]["S1"]["as_on"] == "2024-03-31"
    assert "coverage_note" in body["sources"]["S2"]


def test_gemini_client_uses_api_key(monkeypatch):
    seen = {}

    def fake_client(**kwargs):
        seen.update(kwargs)
        return object()

    monkeypatch.setattr(genai_client, "Client", fake_client)
    settings = Settings(api_key="test-key", model="gemini-2.5-flash", llm_timeout_s=5,
                        max_llm_calls_per_day=50, max_image_bytes=1024, rate_analyze_per_min=6,
                        rate_other_per_min=40, enable_explanation=True)

    assert llm._client(settings) is not None
    assert seen == {"api_key": "test-key"}


def test_extract_label_sends_sdk_image_part(monkeypatch):
    seen = {}

    class Models:
        def generate_content(self, **kwargs):
            seen.update(kwargs)
            return SimpleNamespace(text=json.dumps(GOOD_LABEL))

    monkeypatch.setattr(genai_client, "Client", lambda **kwargs: SimpleNamespace(models=Models()))
    settings = Settings(api_key="test-key", model="gemini-2.5-flash", llm_timeout_s=5,
                        max_llm_calls_per_day=50, max_image_bytes=1024, rate_analyze_per_min=6,
                        rate_other_per_min=40, enable_explanation=True)

    result = llm.extract_label(b"image-bytes", "image/jpeg", settings)

    assert result["readable"] is True
    image_part = seen["contents"][1]
    assert image_part.inline_data.mime_type == "image/jpeg"
    assert image_part.inline_data.data == b"image-bytes"


def test_security_headers_everywhere(client):
    for path in ("/", "/api/health"):
        h = client.get(path).headers
        assert "default-src 'self'" in h["content-security-policy"]
        assert h["x-content-type-options"] == "nosniff"
    assert client.get("/api/health").headers["cache-control"] == "no-store"


def test_no_inline_script_or_style_in_html():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    assert not re.search(r"<script(?![^>]*\bsrc=)", html)
    assert "<style" not in html and " style=" not in html and " onclick=" not in html


def test_confirmed_scan_flow(client):
    read = post_photo(client)
    assert read.status_code == 200
    label = read.json()["label"]
    checked = client.post("/api/check", json={
        "label": label, "crop": "paddy", "scan_confirmed": True,
    })
    assert checked.status_code == 200
    body = checked.json()
    assert body["reference"]["match"] == "exact" and body["waiting"]["days"] == 40
    assert body["source"] == "scan"
    assert body["coverage"]["status"] == "use_in_reference"


def test_legacy_analyze_requires_confirmation_flow(client):
    r = client.post("/api/analyze", files={"image": ("a.jpg", JPEG, "image/jpeg")})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "confirmation_required"


def test_read_label_returns_fields_before_safety_check(client):
    r = post_photo(client)
    assert r.status_code == 200
    body = r.json()
    assert body["label"]["ingredients"] == GOOD_LABEL["ingredients"]
    assert "reference" not in body and "verdict" not in body


def test_read_label_rejects_non_image(client):
    r = post_photo(client, data=b"%PDF-not-image")
    assert r.status_code == 415 and r.json()["error"]["code"] == "badimage"


def test_confirmed_scan_keeps_scan_specific_checks(client):
    r = client.post("/api/check", json={
        "scan_confirmed": True,
        "label": {"ingredients": [{"name": "Hexaconazole", "percent": "5%"}], "formulation": "EC"},
        "crop": "paddy",
    })
    assert r.status_code == 200
    assert r.json()["source"] == "scan"
    assert "NO_REG" in {alert["code"] for alert in r.json()["alerts"]}


def test_read_label_rejects_non_image_and_oversize(client):
    assert post_photo(client, data=b"%PDF-1.4 not an image").status_code == 415
    assert post_photo(client, data=JPEG + b"0" * (1024 * 1024)).status_code == 413


def test_analyze_without_key_is_clean_503(client, monkeypatch):
    monkeypatch.setattr(main, "settings", main.settings.__class__(**{**main.settings.__dict__, "api_key": None}))
    r = post_photo(client)
    assert r.status_code == 503 and r.json()["error"]["code"] == "nollm"


def test_analyze_provider_failure_is_clean_502(client, monkeypatch):
    def boom(*a, **k):
        raise llm.LLMError("APIConnectionError")
    monkeypatch.setattr(llm, "extract_label", boom)
    r = post_photo(client)
    assert r.status_code == 502 and r.json()["error"]["code"] == "llm"


def test_unreadable_label(client, monkeypatch):
    monkeypatch.setattr(llm, "extract_label", lambda *a: {**GOOD_LABEL, "readable": False, "ingredients": []})
    r = post_photo(client)
    assert r.status_code == 422 and r.json()["error"]["code"] == "unreadable"


def test_daily_budget_stops_paid_calls(client, monkeypatch):
    monkeypatch.setattr(main, "budget", main.DailyBudget(0))
    r = post_photo(client)
    assert r.status_code == 503 and r.json()["error"]["code"] == "budget"
    # the free, rule-based path still works
    assert client.post("/api/check", json={"label": {"ingredients": [{"name": "Hexaconazole", "percent": "5%"}], "formulation": "EC"}, "crop": "paddy"}).status_code == 200


def test_rate_limit(client, monkeypatch):
    monkeypatch.setattr(main, "limit_analyze", main.RateLimiter(2))
    codes = [post_photo(client).status_code for _ in range(4)]
    assert codes[:2] == [200, 200] and codes[2:] == [429, 429]


def test_check_banned_without_any_ai(client):
    r = client.post("/api/check", json={"label": {"ingredients": [{"name": "Endosulfan"}]}, "crop": "tomato"})
    assert r.status_code == 200 and r.json()["verdict"] == "danger"


def test_check_validation(client):
    assert client.post("/api/check", json={"label": {"ingredients": []}}).status_code == 422
    assert client.post("/api/check", json={"label": {"ingredients": [{"name": "x" * 500}]}}).status_code == 422
    assert client.post("/api/check", json={"label": {"ingredients": [{"name": "a"}]}, "crop": "wheat"}).status_code == 422


def test_samples_work_without_a_key(client, monkeypatch):
    monkeypatch.setattr(main, "settings", main.settings.__class__(**{**main.settings.__dict__, "api_key": None}))
    ids = [s["id"] for s in client.get("/api/samples").json()]
    assert len(ids) >= 4
    expired = client.get("/api/sample/groundnut-expired").json()
    assert expired["expiry"]["status"] == "expired" and expired["verdict"] == "danger"
    assert client.get("/api/sample/tomato-monocrotophos").json()["verdict"] == "danger"
    assert client.get("/api/sample/nope").status_code == 404


def test_plan_endpoint(client):
    lab = {"ingredients": [{"name": "Hexaconazole", "percent": "5%"}], "formulation": "EC"}
    from app.security import today_ist
    today = today_ist().isoformat()
    r = client.post("/api/plan", json={"items": [{"label": lab, "crop": "paddy", "spray_date": today}]})
    assert r.status_code == 200 and r.json()["earliest_safe_harvest"] is not None
    bad = client.post("/api/plan", json={"items": [{"label": lab, "crop": "paddy", "spray_date": "2020-01-01"}]})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "baddate"


def test_plan_does_not_claim_all_uses_are_in_reference(client):
    lab = {"ingredients": [{"name": "Unknown pesticide"}], "formulation": "EC", "printed_waiting_period": "14 days"}
    from app.security import today_ist
    today = today_ist().isoformat()
    r = client.post("/api/plan", json={"items": [{"label": lab, "crop": "paddy", "spray_date": today}]})
    assert r.status_code == 200
    assert r.json()["all_uses_in_reference"] is False


# ---- AI safety ---------------------------------------------------------------------
def test_summary_with_invented_number_is_rejected():
    facts = {"waiting_days": 40, "verdict": "info"}
    assert llm.grounded("Wait 40 days before harvest.", facts)
    assert not llm.grounded("Wait 14 days before harvest.", facts)
    assert not llm.grounded("Use 2 ml per litre.", facts)


def test_sanitize_label_bounds_and_cleans():
    raw = {"readable": True, "ingredients": [{"name": "A\x00" + "b" * 500, "percent": "5%"}] * 20,
           "toxicity_color": "PURPLE", "printed_crops": ["x"] * 99, "expiry_date": "08/2030"}
    out = llm.sanitize_label(raw)
    assert len(out["ingredients"]) == 6 and len(out["ingredients"][0]["name"]) <= 80
    assert "\x00" not in out["ingredients"][0]["name"]
    assert out["toxicity_color"] is None and len(out["printed_crops"]) <= 15


def test_parse_json_object_handles_chatty_replies():
    assert llm.parse_json_object('Here you go: {"readable": true}')["readable"] is True
    with pytest.raises(llm.LLMError):
        llm.parse_json_object("no json here")


# ---- i18n and secrets -----------------------------------------------------------------
def test_translations_are_complete_and_consistent():
    d = json.loads((ROOT / "static" / "i18n.json").read_text(encoding="utf-8"))
    for lang in ("hi", "te", "ta"):
        assert set(d[lang]) == set(d["en"])
        for k, v in d["en"].items():
            assert sorted(re.findall(r"\{\w+\}", v)) == sorted(re.findall(r"\{\w+\}", d[lang][k])), (lang, k)


def test_every_alert_code_has_text_in_every_language():
    src = (ROOT / "app" / "engine.py").read_text(encoding="utf-8")
    used = set(re.findall(r'"code": "([A-Z_0-9]+)"', src))
    d = json.loads((ROOT / "static" / "i18n.json").read_text(encoding="utf-8"))
    for lang in d:
        for code in used:
            assert f"al.{code}" in d[lang], (lang, code)


def test_no_secrets_committed():
    pattern = re.compile(r"sk-ant-[A-Za-z0-9_\-]{10,}")
    for path in ROOT.rglob("*"):
        if path.is_file() and path.name != ".env" and ".git" not in path.parts and "__pycache__" not in path.parts and path.suffix in {
            ".py", ".js", ".json", ".md", ".html", ".css", ".yaml", ".yml", ".txt", ".example", ""}:
            assert not pattern.search(path.read_text(encoding="utf-8", errors="ignore")), path
    assert ".env" in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
