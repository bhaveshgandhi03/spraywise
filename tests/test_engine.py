from datetime import date

import pytest

from app import engine as e

TODAY = date(2026, 10, 10)


def label(name, pct=None, form=None, **kw):
    return {"ingredients": [{"name": name, "percent": pct}], "formulation": form, **kw}


def codes(res):
    return [a["code"] for a in res["alerts"]]


# ---- names and formulation -------------------------------------------------
def test_name_normalisation_and_synonyms():
    assert e.norm_name("Hexaconazole 5% EC") == "hexaconazole"
    assert e.norm_name("Chlorpyriphos 20 % w/w EC") == "chlorpyrifos"
    assert e.norm_name("Paraquat Dichloride 24% SL") == "paraquat dichloride"
    assert e.norm_name("2,4,5-T") == "245t"


def test_similar_conazoles_are_not_confused():
    names = ["hexaconazole", "tebuconazole", "propiconazole", "difenoconazole"]
    for a in names:
        for b in names:
            if a != b:
                assert e.same_ai(a, b) is None, (a, b)


def test_formulation_parsing():
    assert e.parse_formulation("18.50 % SC") == ("18.5", "%", "sc")
    assert e.parse_formulation("300 g/L SC") == ("300", "g/l", "sc")
    assert e.formulation_key("5%", "EC") == ("5", "%", "ec")
    assert e.formulation_key(None, "EC") is None


@pytest.mark.parametrize("raw,expected", [
    ("08/2026", date(2026, 8, 31)), ("Exp: Aug-2025", date(2025, 8, 31)), ("03.2027", date(2027, 3, 31)),
    ("2026-11", date(2026, 11, 30)), ("15/09/2026", date(2026, 9, 15)), ("08/26", date(2026, 8, 31)),
    ("garbage", None), (None, None),
])
def test_expiry_parsing(raw, expected):
    assert e.parse_expiry(raw) == expected


def test_parse_days():
    assert e.parse_days("7 days") == 7
    assert e.parse_days("5-6") == 6
    assert e.parse_days("Tomato 3 days, Brinjal 5 days") == 5
    assert e.parse_days("-") is None
    assert e.parse_days(None) is None


# ---- banned and restricted --------------------------------------------------
def test_banned_ingredient_is_danger():
    res = e.analyze(label("Endosulfan", "35%", "EC"), "paddy", TODAY)
    assert res["verdict"] == "danger" and "BANNED" in codes(res)


def test_misspelling_in_official_list_still_matches():
    assert "BANNED" in codes(e.analyze(label("Endosulfron"), "paddy", TODAY))
    assert "BANNED" in codes(e.analyze(label("Dichlorovos"), "paddy", TODAY))


def test_crop_claim_removed_only_for_affected_crop():
    assert "CROP_CLAIM_REMOVED" in codes(e.analyze(label("Oxyfluorfen", "23.5%", "EC"), "groundnut", TODAY))
    assert "CROP_CLAIM_REMOVED" not in codes(e.analyze(label("Oxyfluorfen", "23.5%", "EC"), "paddy", TODAY))
    assert "CROP_CLAIM_REMOVED" in codes(e.analyze(label("Malathion", "50%", "EC"), "tomato", TODAY))


def test_monocrotophos_restricted_on_vegetables_so_tomato_is_danger():
    res = e.analyze(label("Monocrotophos", "36%", "SL"), "tomato", TODAY)
    assert "RESTRICTED_CROP" in codes(res) and res["verdict"] == "danger"
    assert "RESTRICTED_CROP" not in codes(e.analyze(label("Monocrotophos", "36%", "SL"), "paddy", TODAY))


def test_carbofuran_only_3pct_cg_keeps_claims():
    assert "ONLY_3CG" not in codes(e.analyze(label("Carbofuran", "3%", "CG"), "paddy", TODAY))
    assert "ONLY_3CG" in codes(e.analyze(label("Carbofuran", "50%", "SP"), "paddy", TODAY))
    assert "ONLY_3CG" in codes(e.analyze(label("Carbofuran"), "paddy", TODAY))


def test_possible_match_is_a_warning_not_a_ban():
    res = e.analyze(label("Paraquat"), "paddy", TODAY)
    assert "POSSIBLE_MATCH" in codes(res) and "BANNED" not in codes(res)


def test_clean_product_has_no_ban_alerts():
    res = e.analyze(label("Hexaconazole", "5%", "EC", expiry_date="08/2030", printed_crops=["Paddy"]), "paddy", TODAY)
    assert not {"BANNED", "RESTRICTED_CROP", "CROP_CLAIM_REMOVED", "REFUSED", "WITHDRAWN"} & set(codes(res))


def test_thiophanate_methyl_is_not_flagged_as_methyl_bromide():
    res = e.analyze(label("Thiophanate methyl", "41.7%", "SC"), "groundnut", TODAY)
    assert "POSSIBLE_MATCH" not in codes(res) and "RESTRICTED" not in codes(res)


# ---- reference match and waiting period --------------------------------------
def test_exact_match_gives_waiting_period():
    res = e.analyze(label("Hexaconazole", "5%", "EC"), "paddy", TODAY)
    assert res["reference"]["match"] == "exact" and res["waiting"]["days"] == 40
    assert res["coverage"] == {
        "status": "use_in_reference",
        "product_in_reference": True,
        "crop_in_reference": True,
    }


def test_unlisted_product_is_never_presented_as_verified():
    res = e.analyze(label("Unknown pesticide", "10%", "EC", printed_waiting_period="14 days"), "paddy", TODAY)
    assert res["coverage"]["status"] == "product_unverified"
    assert res["coverage"]["product_in_reference"] is False
    assert res["verdict"] == "warning" and "NOT_IN_REFERENCE" in codes(res)
    assert res["waiting"]["days"] == 14 and res["waiting"]["source"] == "label"


def test_known_product_on_unsupported_crop_is_not_presented_as_verified():
    res = e.analyze(label("Hexaconazole", "5%", "EC"), "other", TODAY)
    assert res["coverage"]["status"] == "crop_unverified"
    assert res["coverage"]["product_in_reference"] is True
    assert res["coverage"]["crop_in_reference"] is False


def test_known_product_with_label_crop_mismatch_is_not_presented_as_verified():
    res = e.analyze(label("Hexaconazole", "5%", "EC", printed_crops=["Groundnut"]), "paddy", TODAY)
    assert res["coverage"]["status"] == "crop_unverified"
    assert res["coverage"]["crop_in_reference"] is False
    assert "LABEL_CROP_MISSING" in codes(res)


def test_waiting_not_borrowed_from_another_formulation():
    res = e.analyze(label("Hexaconazole", "75%", "WG"), "paddy", TODAY)
    assert res["reference"]["match"] == "formulation_not_in_reference"
    assert res["waiting"]["days"] is None and "WAIT_UNKNOWN" in codes(res)


def test_unknown_formulation_offers_candidates():
    res = e.analyze(label("Propiconazole"), "groundnut", TODAY)
    assert res["reference"]["match"] == "formulation_unknown" and res["reference"]["candidates"]


def test_combination_product_is_never_given_a_borrowed_waiting_period():
    lab = {"ingredients": [{"name": "Azoxystrobin", "percent": "18.2%"}, {"name": "Difenoconazole", "percent": "11.4%"}], "formulation": "SC"}
    res = e.analyze(lab, "tomato", TODAY)
    assert res["reference"]["match"] == "combination" and res["waiting"]["days"] is None


def test_combined_name_typed_in_one_box_is_split():
    res = e.analyze(label("Azoxystrobin 18.2% + Difenoconazole 11.4%", None, "SC"), "tomato", TODAY)
    assert len(res["label"]["ingredients"]) == 2


def test_longer_of_reference_and_label_waiting_period_is_used():
    res = e.analyze(label("Hexaconazole", "5%", "EC", printed_waiting_period="50 days"), "paddy", TODAY)
    assert res["waiting"]["days"] == 50 and "WAIT_MISMATCH" in codes(res)
    res = e.analyze(label("Hexaconazole", "5%", "EC", printed_waiting_period="10 days"), "paddy", TODAY)
    assert res["waiting"]["days"] == 40


def test_crop_not_in_reference_and_label_crop_missing():
    res = e.analyze(label("Tricyclazole", "75%", "WP"), "tomato", TODAY)
    assert "CROP_NOT_IN_REFERENCE" in codes(res)
    res = e.analyze(label("Hexaconazole", "5%", "EC", printed_crops=["Groundnut"]), "paddy", TODAY)
    assert "LABEL_CROP_MISSING" in codes(res)


def test_misspelt_name_is_flagged_not_trusted():
    res = e.analyze(label("Tebuconazol", "25.9%", "EC"), "paddy", TODAY)
    assert res["reference"]["match"] in {"exact", "name_unsure"}


# ---- expiry, toxicity --------------------------------------------------------
def test_expired_expiring_valid():
    assert "EXPIRED" in codes(e.analyze(label("Hexaconazole", "5%", "EC", expiry_date="08/2026"), "paddy", TODAY))
    assert "EXPIRING" in codes(e.analyze(label("Hexaconazole", "5%", "EC", expiry_date="11/2026"), "paddy", TODAY))
    res = e.analyze(label("Hexaconazole", "5%", "EC", expiry_date="08/2028"), "paddy", TODAY)
    assert res["expiry"]["status"] == "valid" and "EXPIRED" not in codes(res)


def test_toxicity_from_colour_or_words():
    assert e.analyze(label("Hexaconazole", toxicity_color="red"), "paddy", TODAY)["toxicity"]["class"] == "extremely_toxic"
    assert e.analyze(label("Hexaconazole", toxicity_words="Moderately toxic"), "paddy", TODAY)["toxicity"]["color"] == "blue"
    assert e.analyze(label("Hexaconazole"), "paddy", TODAY)["toxicity"] is None


def test_verdict_never_claims_safe():
    res = e.analyze(label("Hexaconazole", "5%", "EC", expiry_date="08/2030", printed_waiting_period="40 days", printed_crops=["Paddy"]), "paddy", TODAY)
    assert res["verdict"] in {"info", "warning"}


# ---- plan ----------------------------------------------------------------------
def test_plan_takes_the_longest_waiting_period_and_flags_duplicates():
    items = [
        {"label": label("Hexaconazole", "5%", "EC"), "crop": "paddy", "spray_date": date(2026, 10, 10)},
        {"label": label("Tricyclazole", "75%", "WP"), "crop": "paddy", "spray_date": date(2026, 10, 12)},
        {"label": label("Hexaconazole", "5%", "EC"), "crop": "paddy", "spray_date": date(2026, 10, 20)},
    ]
    res = e.plan(items, TODAY)
    assert res["earliest_safe_harvest"] == "2026-11-29"  # 20 Oct + 40 days
    assert any(a["code"] == "DUP_AI" for a in res["alerts"])


def test_plan_with_unknown_waiting_is_flagged():
    items = [{"label": label("Mystery"), "crop": "paddy", "spray_date": TODAY}]
    res = e.plan(items, TODAY)
    assert res["some_unknown"] and res["earliest_safe_harvest"] is None


def test_reference_data_integrity():
    ref = e.load_reference()
    assert len(ref["products"]) >= 30 and len(ref["banned"]) >= 90
    for p in ref["products"]:
        assert p["source"] in ref["sources"] and p["_fkey"] is not None, p["name"]
        assert p["safety_notes"] is None  # never invented
    ids = [p["id"] for p in ref["products"]]
    assert len(ids) == len(set(ids))
