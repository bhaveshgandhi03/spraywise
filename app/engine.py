"""Deterministic rules engine.

Every safety-relevant statement (banned, restricted, waiting period, expiry, duplicates) is computed
here in plain Python from the curated reference files. The language model never decides these facts;
it only reads the photo and, optionally, rephrases what this module already established.
"""
from __future__ import annotations

import calendar
import json
import re
import unicodedata
from datetime import date, timedelta
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CROPS = ("tomato", "groundnut", "paddy")

CROP_WORDS = {
    "tomato": ("tomato", "vegetable"),
    "groundnut": ("groundnut", "peanut"),
    "paddy": ("paddy", "rice"),
}
LABEL_CROP_MAP = {
    "tomato": "tomato", "tomatoes": "tomato",
    "groundnut": "groundnut", "groundnuts": "groundnut", "peanut": "groundnut", "peanuts": "groundnut",
    "paddy": "paddy", "rice": "paddy",
}

# Spelling variants seen on Indian labels and in the official lists.
SYNONYMS = {
    "chlorpyriphos": "chlorpyrifos",
    "dichlorovos": "dichlorvos",
    "carbofuron": "carbofuran",
    "endosulfron": "endosulfan",
    "nicotin sulfate": "nicotine sulfate",
    "thiophanatemethyl": "thiophanate methyl",
    "copper oxy chloride": "copper oxychloride",
    "monocrotofos": "monocrotophos",
    "hexaconazol": "hexaconazole",
    "tebuconazol": "tebuconazole",
    "propiconazol": "propiconazole",
}

# Words that describe the product form, not the ingredient.
_NOISE = {
    "ec", "sc", "wp", "wg", "wdg", "sl", "sp", "sg", "df", "dp", "gr", "cg", "cs", "ew", "ow", "os",
    "fs", "ws", "ds", "se", "od", "ls", "g", "w", "v", "l", "technical", "tech", "ai", "liquid",
    "powder", "granules", "granule", "suspension", "concentrate", "emulsifiable", "soluble",
    "wettable", "dispersible", "flowable", "min",
}

TOXICITY = {
    "red": {"class": "extremely_toxic", "oral_ld50_mg_per_kg": "1-50"},
    "yellow": {"class": "highly_toxic", "oral_ld50_mg_per_kg": "51-500"},
    "blue": {"class": "moderately_toxic", "oral_ld50_mg_per_kg": "501-5000"},
    "green": {"class": "slightly_toxic", "oral_ld50_mg_per_kg": ">5000"},
}
_TOX_WORDS = (
    ("extremely", "red"), ("highly", "yellow"), ("moderately", "blue"), ("slightly", "green"),
)

BAN_CODES = {"BANNED", "EXPORT_ONLY", "WITHDRAWN", "REFUSED", "REPORTED_BAN", "RESTRICTED_CROP", "CROP_CLAIM_REMOVED", "ONLY_3CG"}
LOGISTICS_CODES = {
    "NOT_IN_REFERENCE", "WAIT_UNKNOWN", "FORM_UNKNOWN", "FORM_NOT_IN_REFERENCE", "COMBINATION", "NAME_UNSURE",
    "EXPIRY_UNKNOWN", "NO_REG", "CROP_NOT_IN_REFERENCE", "LABEL_CROP_MISSING", "WAIT_PARTIAL", "WAIT_LONGEST",
}

DANGER_STATUSES = {
    "banned_manufacture_import_use",
    "banned_use_manufacture_for_export_only",
    "withdrawn",
    "refused_registration",
    "prohibited_reported_unverified",
}


# ----------------------------------------------------------------------------- name handling
def norm_name(raw: str | None) -> str:
    s = unicodedata.normalize("NFKD", raw or "").lower()
    compact = re.sub(r"[^a-z0-9]", "", s)  # fallback for names such as 2,4,5-T
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"[\d.,]+\s*(%|g\s*/\s*l|gm\s*/\s*l|g\s*/\s*kg|ml\s*/\s*l)?", " ", s)
    s = s.replace("sulphate", "sulfate").replace("sulphur", "sulfur")
    s = re.sub(r"[^a-z ]+", " ", s)
    toks = [t for t in s.split() if t not in _NOISE]
    s = " ".join(toks)
    s = SYNONYMS.get(s, s)
    s = SYNONYMS.get(s.replace(" ", ""), s)
    if len(s) < 3:
        s = compact
    return s


def _tokens(name: str) -> set[str]:
    return set(name.split())


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def same_ai(a: str, b: str) -> str | None:
    """'exact', 'approx' or None. Used for reference products, where a wrong match would give a wrong waiting period."""
    if not a or not b:
        return None
    if a == b:
        return "exact"
    if min(len(a), len(b)) >= 8 and _ratio(a, b) >= 0.93:
        return "approx"
    return None


# ----------------------------------------------------------------------------- formulation
_FORM_RE = re.compile(
    r"^\s*([\d.]+)\s*(%|g\s*/\s*l|g\s*/\s*kg)?\s*(?:w\s*/\s*[wv])?\s*([a-z]{1,4})\s*$", re.I
)


def parse_formulation(text: str | None) -> tuple[str, str, str] | None:
    """'18.50 % SC' -> ('18.5', '%', 'sc'). Returns None when it cannot be read as strength + form."""
    if not text:
        return None
    m = _FORM_RE.match(str(text).strip())
    if not m:
        return None
    try:
        num = f"{float(m.group(1)):g}"
    except ValueError:
        return None
    unit = (m.group(2) or "%").lower().replace(" ", "")
    return num, unit, m.group(3).lower()


def formulation_key(percent: str | None, formulation: str | None) -> tuple[str, str, str] | None:
    full = parse_formulation(formulation)
    if full:
        return full
    if percent and formulation:
        return parse_formulation(f"{percent} {formulation}")
    return None


# ----------------------------------------------------------------------------- numbers and dates
def parse_days(text: Any) -> int | None:
    """Longest number of days printed in a waiting-period string, or None."""
    if text is None:
        return None
    t = str(text).lower()
    m = re.search(r"(\d+)\s*(?:-|–|to)\s*(\d+)", t)
    if m:
        return max(int(m.group(1)), int(m.group(2)))
    nums = [int(x) for x in re.findall(r"(\d+)\s*(?:days?|d\b|दिन|రోజులు|நாள்)", t)]
    if nums:
        return max(nums)
    m = re.fullmatch(r"\s*(\d+)\s*", t)
    return int(m.group(1)) if m else None


_MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_abbr) if m}
_MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_name) if m})


def _end_of_month(y: int, m: int) -> date | None:
    if not (1 <= m <= 12 and 2000 <= y <= 2100):
        return None
    return date(y, m, calendar.monthrange(y, m)[1])


def parse_expiry(raw: str | None) -> date | None:
    """Last day of the printed expiry month (or the exact day when printed). None when unclear."""
    if not raw:
        return None
    t = str(raw).strip().lower()
    t = re.sub(r"^(exp(iry)?|expires?|use before|best before|date of expiry)[\s.:\-]*", "", t)
    m = re.search(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})", t)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return date(y, mo, d)
        except ValueError:
            return None
    m = re.search(r"(\d{4})[/\-.](\d{1,2})(?![\d])", t)
    if m:
        return _end_of_month(int(m.group(1)), int(m.group(2)))
    m = re.search(r"(?<!\d)(\d{1,2})[/\-.](\d{4})", t)
    if m:
        return _end_of_month(int(m.group(2)), int(m.group(1)))
    m = re.search(r"(\d{1,2})?\s*([a-z]{3,9})[\s,.\-/]*(\d{4})", t)
    if m and m.group(2) in _MONTHS:
        y, mo = int(m.group(3)), _MONTHS[m.group(2)]
        if m.group(1):
            try:
                return date(y, mo, int(m.group(1)))
            except ValueError:
                return None
        return _end_of_month(y, mo)
    m = re.search(r"(?<!\d)(\d{1,2})[/\-.](\d{2})(?!\d)", t)
    if m:
        return _end_of_month(2000 + int(m.group(2)), int(m.group(1)))
    return None


# ----------------------------------------------------------------------------- reference data
@lru_cache(maxsize=1)
def load_reference() -> dict[str, Any]:
    pest = json.loads((DATA_DIR / "pesticides.json").read_text(encoding="utf-8"))
    ban = json.loads((DATA_DIR / "banned.json").read_text(encoding="utf-8"))
    products = []
    for p in pest["pesticides"]:
        q = dict(p)
        q["_ai"] = norm_name(p["active_ingredient"])
        q["_fkey"] = parse_formulation(p.get("formulation"))
        products.append(q)
    entries = []
    for e in ban["entries"]:
        raw_names = [e["active_ingredient"], *e.get("aliases", [])]
        names: set[str] = set()
        for rn in raw_names:
            for part in re.split(r"[/]", rn):
                n = norm_name(part)
                if n:
                    names.add(n)
        q = dict(e)
        q["_names"] = names
        entries.append(q)
    return {
        "products": products,
        "banned": entries,
        "sources": pest["sources"],
        "pest_meta": pest["_meta"],
        "ban_meta": ban["_meta"],
    }


def suggestions() -> list[str]:
    ref = load_reference()
    names = {p["active_ingredient"].title() for p in ref["products"]}
    names |= {e["active_ingredient"] for e in ref["banned"] if e["status"] != "crop_claims_removed"}
    return sorted(names)


def product_by_id(pid: str) -> dict[str, Any] | None:
    return next((p for p in load_reference()["products"] if p["id"] == pid), None)


# ----------------------------------------------------------------------------- banned / restricted
def _name_match(a: str, names: set[str]) -> str | None:
    if a in names:
        return "exact"
    ta = _tokens(a)
    for n in names:
        if min(len(a), len(n)) >= 8 and _ratio(a, n) >= 0.93:
            return "possible"
        tn = _tokens(n)
        small, big = (ta, tn) if len(ta) <= len(tn) else (tn, ta)
        if small and small <= big and len(next(iter(sorted(small, key=len, reverse=True)))) >= 6:
            return "possible"
    return None


def _crop_in(crops: list[str] | None, crop: str) -> bool:
    if not crops or crop not in CROP_WORDS:
        return False
    blob = " ".join(crops).lower()
    if "all except" in blob:
        return True
    return any(w in blob for w in CROP_WORDS[crop])


def banned_alerts(ai_name: str, crop: str, fkey: tuple[str, str, str] | None) -> list[dict[str, Any]]:
    """Alerts for one ingredient against banned.json."""
    a = norm_name(ai_name)
    out: list[dict[str, Any]] = []
    possibles: list[dict[str, Any]] = []
    exact_any = False
    if not a:
        return out
    for e in load_reference()["banned"]:
        match = _name_match(a, e["_names"])
        if not match:
            continue
        if match == "exact":
            exact_any = True
        status = e["status"]
        shown = e["active_ingredient"]
        ref = e.get("notification") or "CIB&RC list"
        base = {"name": shown, "notification": ref, "detail": e.get("detail") or ""}

        if match == "possible":
            if status in DANGER_STATUSES or status == "restricted":
                possibles.append({"code": "POSSIBLE_MATCH", "level": "warning", "params": {**base, "status": status}})
            continue

        if status in ("banned_manufacture_import_use",):
            out.append({"code": "BANNED", "level": "danger", "params": base})
        elif status == "banned_use_manufacture_for_export_only":
            out.append({"code": "EXPORT_ONLY", "level": "danger", "params": base})
        elif status == "withdrawn":
            out.append({"code": "WITHDRAWN", "level": "danger", "params": base})
        elif status == "refused_registration":
            out.append({"code": "REFUSED", "level": "danger", "params": base})
        elif status == "prohibited_reported_unverified":
            out.append({"code": "REPORTED_BAN", "level": "danger", "params": base})
        elif status == "banned_formulation":
            if fkey is None:
                out.append({"code": "ONLY_3CG", "level": "warning", "params": base})
            elif fkey == ("50", "%", "sp"):
                out.append({"code": "ONLY_3CG", "level": "danger", "params": base})
        elif status == "restricted":
            if _crop_in(e.get("crops_affected"), crop):
                out.append({"code": "RESTRICTED_CROP", "level": "danger", "params": {**base, "crop": crop}})
            else:
                out.append({"code": "RESTRICTED", "level": "warning", "params": base})
        elif status == "crop_claims_removed":
            affected = e.get("crops_affected") or []
            if shown.lower() == "carbofuran":
                if fkey != ("3", "%", "cg"):
                    out.append({"code": "ONLY_3CG", "level": "warning" if fkey is None else "danger", "params": base})
            elif shown.lower() == "dimethoate":
                if crop == "tomato":
                    out.append({"code": "RAW_FOOD", "level": "warning", "params": base})
            elif crop in CROP_WORDS and any(
                w in " ".join(affected).lower() for w in CROP_WORDS[crop]
            ):
                out.append({"code": "CROP_CLAIM_REMOVED", "level": "danger", "params": {**base, "crop": crop}})
    if not exact_any:
        out.extend(possibles)
    # de-duplicate (same code and name)
    seen, uniq = set(), []
    for al in out:
        k = (al["code"], al["params"]["name"], al["level"])
        if k not in seen:
            seen.add(k)
            uniq.append(al)
    return uniq


# ----------------------------------------------------------------------------- reference product match
def match_reference(ai_names: list[str], fkey: tuple[str, str, str] | None) -> dict[str, Any]:
    ais = [norm_name(a) for a in ai_names if norm_name(a)]
    if not ais:
        return {"match": "not_found", "product": None, "candidates": []}
    if len(ais) > 1:
        return {"match": "combination", "product": None, "candidates": []}
    ai = ais[0]
    cands = []
    for p in load_reference()["products"]:
        conf = same_ai(p["_ai"], ai)
        if conf:
            cands.append((p, conf))
    if not cands:
        return {"match": "not_found", "product": None, "candidates": []}
    summaries = [{"id": p["id"], "name": p["name"], "formulation": p["formulation"]} for p, _ in cands]
    if any(c == "approx" for _, c in cands):
        return {"match": "name_unsure", "product": None, "candidates": summaries}
    if fkey is None:
        return {"match": "formulation_unknown", "product": None, "candidates": summaries}
    exact = [p for p, _ in cands if p["_fkey"] == fkey]
    if exact:
        return {"match": "exact", "product": exact[0], "candidates": summaries}
    return {"match": "formulation_not_in_reference", "product": None, "candidates": summaries}


def reference_waiting(product: dict[str, Any], crop: str) -> dict[str, Any]:
    claims = [c for c in product["crop_claims"] if c["crop"] == crop]
    if not claims:
        return {"status": "no_claim", "days": None, "targets": []}
    vals, missing = [], 0
    for c in claims:
        d = c.get("waiting_period_days")
        if d is None:
            d = parse_days(c.get("waiting_period_as_printed"))
        if d is None:
            missing += 1
        else:
            vals.append(d)
    targets = sorted({c["target"] for c in claims})
    if not vals:
        return {"status": "blank", "days": None, "targets": targets}
    return {
        "status": "ok",
        "days": max(vals),
        "different_values": len(set(vals)) > 1,
        "partial": missing > 0,
        "targets": targets,
    }


# ----------------------------------------------------------------------------- label -> analysis
def _toxicity(label: dict[str, Any]) -> dict[str, Any] | None:
    color = (label.get("toxicity_color") or "").lower() or None
    if color not in TOXICITY:
        color = None
        words = (label.get("toxicity_words") or "").lower()
        for w, c in _TOX_WORDS:
            if w in words:
                color = c
                break
    if not color:
        return None
    return {"color": color, **TOXICITY[color]}


def _label_crops(label: dict[str, Any]) -> set[str]:
    out = set()
    for c in label.get("printed_crops") or []:
        for tok in re.findall(r"[a-z]+", str(c).lower()):
            if tok in LABEL_CROP_MAP:
                out.add(LABEL_CROP_MAP[tok])
    return out


def split_ingredients(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """'Azoxystrobin 18.2% + Difenoconazole 11.4%' typed as one string becomes two ingredients."""
    out: list[dict[str, Any]] = []
    for i in raw:
        name = (i.get("name") or "").strip()
        if not name:
            continue
        parts = [p.strip() for p in re.split(r"\s*(?:\+|&|,|\band\b)\s*", name) if p.strip()]
        if len(parts) > 1:
            out.extend({"name": p, "percent": None} for p in parts)
        else:
            out.append({"name": name, "percent": i.get("percent")})
    return out


def analyze(label: dict[str, Any], crop: str = "other", today: date | None = None) -> dict[str, Any]:
    """Turn a (scanned or typed) label into the full, deterministic safety analysis."""
    from .security import today_ist

    today = today or today_ist()
    crop = crop if crop in CROPS else "other"
    ings = split_ingredients(label.get("ingredients") or [])
    names = [i["name"] for i in ings]
    pct = ings[0].get("percent") if ings else None
    fkey = formulation_key(pct, label.get("formulation"))

    alerts: list[dict[str, Any]] = []

    if label.get("readable") is False or not ings:
        alerts.append({"code": "UNREADABLE", "level": "warning", "params": {}})

    for n in names:
        alerts.extend(banned_alerts(n, crop, fkey))

    # ---- reference match and waiting period
    ref = match_reference(names, fkey)
    product = ref["product"]
    waiting: dict[str, Any] = {"days": None, "source": None, "reference_days": None, "label_days": None}
    crop_check = "unknown"

    if ref["match"] == "combination":
        alerts.append({"code": "COMBINATION", "level": "warning", "params": {}})
    elif ref["match"] == "not_found" and ings:
        alerts.append({"code": "NOT_IN_REFERENCE", "level": "warning", "params": {}})
    elif ref["match"] == "formulation_unknown":
        alerts.append({"code": "FORM_UNKNOWN", "level": "warning", "params": {}})
    elif ref["match"] == "formulation_not_in_reference":
        alerts.append({"code": "FORM_NOT_IN_REFERENCE", "level": "warning", "params": {}})
    elif ref["match"] == "name_unsure":
        alerts.append({"code": "NAME_UNSURE", "level": "warning", "params": {}})

    if product and crop in CROPS:
        rw = reference_waiting(product, crop)
        if rw["status"] == "no_claim":
            crop_check = "not_in_reference"
            alerts.append({"code": "CROP_NOT_IN_REFERENCE", "level": "warning", "params": {"crop": crop}})
        else:
            crop_check = "listed"
            waiting["reference_days"] = rw["days"]
            waiting["targets"] = rw["targets"]
            if rw.get("different_values"):
                alerts.append({"code": "WAIT_LONGEST", "level": "info", "params": {}})
            if rw.get("partial"):
                alerts.append({"code": "WAIT_PARTIAL", "level": "info", "params": {}})

    # ---- label-printed crops
    printed = _label_crops(label)
    if crop in CROPS and printed and crop not in printed:
        crop_check = "label_missing"
        alerts.append({"code": "LABEL_CROP_MISSING", "level": "warning", "params": {"crop": crop}})

    product_in_reference = ref["match"] == "exact" and product is not None
    use_in_reference = product_in_reference and crop_check == "listed"
    coverage_status = (
        "use_in_reference" if use_in_reference
        else "crop_unverified" if product_in_reference
        else "product_unverified"
    )

    # ---- waiting period: the longer of reference and label is used
    waiting["label_days"] = parse_days(label.get("printed_waiting_period"))
    rd, ld = waiting["reference_days"], waiting["label_days"]
    if rd is not None and ld is not None:
        waiting["days"] = max(rd, ld)
        waiting["source"] = "both"
        if rd != ld:
            alerts.append({"code": "WAIT_MISMATCH", "level": "warning", "params": {"ref": rd, "label": ld}})
    elif rd is not None:
        waiting["days"], waiting["source"] = rd, "reference"
    elif ld is not None:
        waiting["days"], waiting["source"] = ld, "label"
    else:
        alerts.append({"code": "WAIT_UNKNOWN", "level": "warning", "params": {}})

    # ---- expiry
    exp_raw = label.get("expiry_date")
    exp = parse_expiry(exp_raw)
    expiry: dict[str, Any] = {"raw": exp_raw, "date": exp.isoformat() if exp else None, "status": "unknown"}
    if exp:
        if exp < today:
            expiry["status"] = "expired"
            alerts.append({"code": "EXPIRED", "level": "danger", "params": {"date": exp.isoformat()}})
        elif exp <= today + timedelta(days=60):
            expiry["status"] = "expiring"
            alerts.append({"code": "EXPIRING", "level": "warning", "params": {"date": exp.isoformat()}})
        else:
            expiry["status"] = "valid"
    elif ings:
        alerts.append({"code": "EXPIRY_UNKNOWN", "level": "warning", "params": {}})

    if ings and not (label.get("registration_number") or "").strip() and label.get("source") == "scan":
        alerts.append({"code": "NO_REG", "level": "warning", "params": {}})

    # ---- a confirmed ban makes the "not in our list / waiting period unknown" notes irrelevant
    if any(a["level"] == "danger" and a["code"] in BAN_CODES for a in alerts):
        alerts = [a for a in alerts if a["code"] not in LOGISTICS_CODES]

    # ---- order alerts: danger first
    order = {"danger": 0, "warning": 1, "info": 2}
    alerts.sort(key=lambda a: order[a["level"]])
    verdict = alerts[0]["level"] if alerts else "info"

    result = {
        "crop": crop,
        "label": {
            "product_name": label.get("product_name"),
            "ingredients": ings,
            "formulation": label.get("formulation"),
            "toxicity_color": label.get("toxicity_color"),
            "toxicity_words": label.get("toxicity_words"),
            "printed_waiting_period": label.get("printed_waiting_period"),
            "expiry_date": label.get("expiry_date"),
            "registration_number": label.get("registration_number"),
            "batch_number": label.get("batch_number"),
            "manufacturer": label.get("manufacturer"),
            "printed_crops": label.get("printed_crops") or [],
            "printed_dose": label.get("printed_dose"),
            "precautions": label.get("precautions") or [],
        },
        "toxicity": _toxicity(label),
        "reference": {
            "match": ref["match"],
            "product": (
                {"id": product["id"], "name": product["name"], "source": product["source"]}
                if product else None
            ),
            "candidates": ref["candidates"],
        },
        "coverage": {
            "status": coverage_status,
            "product_in_reference": product_in_reference,
            "crop_in_reference": crop_check == "listed",
        },
        "crop_check": crop_check,
        "waiting": waiting,
        "expiry": expiry,
        "alerts": alerts,
        "verdict": verdict,
        "today": today.isoformat(),
    }
    return result


def facts_for_summary(result: dict[str, Any]) -> dict[str, Any]:
    """Only the checked facts an AI summary is allowed to talk about."""
    return {
        "product": result["label"]["product_name"],
        "active_ingredients": [i["name"] for i in result["label"]["ingredients"]],
        "crop": result["crop"],
        "verdict": result["verdict"],
        "toxicity_class": (result["toxicity"] or {}).get("class"),
        "waiting_days": result["waiting"]["days"],
        "expiry_status": result["expiry"]["status"],
        "alerts": [{"code": a["code"], "name": a["params"].get("name")} for a in result["alerts"]],
    }


# ----------------------------------------------------------------------------- spray plan
def safe_harvest(spray: date, days: int | None) -> date | None:
    return spray + timedelta(days=days) if days is not None else None


def plan(items: list[dict[str, Any]], today: date | None = None) -> dict[str, Any]:
    from .security import today_ist

    today = today or today_ist()
    rows, all_ai = [], {}
    for it in items:
        res = analyze(it["label"], it.get("crop", "other"), today)
        spray = it["spray_date"]
        harvest = safe_harvest(spray, res["waiting"]["days"])
        rows.append({
            "analysis": res,
            "spray_date": spray.isoformat(),
            "safe_harvest": harvest.isoformat() if harvest else None,
            "days_left": (harvest - today).days if harvest else None,
        })
        for ing in res["label"]["ingredients"]:
            n = norm_name(ing["name"])
            if n:
                all_ai.setdefault(n, set()).add(id(it))
    alerts = []
    for n, owners in all_ai.items():
        if len(owners) > 1:
            alerts.append({"code": "DUP_AI", "level": "warning", "params": {"name": n.title()}})
    dates = [date.fromisoformat(r["safe_harvest"]) for r in rows if r["safe_harvest"]]
    unknown = any(r["safe_harvest"] is None for r in rows)
    earliest = max(dates) if dates else None
    return {
        "items": rows,
        "earliest_safe_harvest": earliest.isoformat() if earliest else None,
        "all_uses_in_reference": all(
            r["analysis"]["coverage"]["status"] == "use_in_reference" for r in rows
        ),
        "some_unknown": unknown,
        "alerts": alerts,
        "today": today.isoformat(),
    }
