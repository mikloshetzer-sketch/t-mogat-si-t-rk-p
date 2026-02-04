import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

import requests

YEAR = 2025
OUT_PATH = "data/top10_2025.json"

# Kulcs: ami a weben megjelenik
# Érték: donor név (amit az FTS API tipikusan elfogad)
DONORS: Dict[str, str] = {
    "EU": "European Union",
    "USA": "United States of America",
    "Germany": "Germany",
    "UK": "United Kingdom",
    "Japan": "Japan",
    "France": "France",
    "Canada": "Canada",
    "Sweden": "Sweden",
    "Norway": "Norway",
    "Netherlands": "Netherlands",
}

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "top10-map/1.0"})


def _get_json(url: str, params: Dict[str, Any], timeout: int = 30) -> Optional[Dict[str, Any]]:
    try:
        r = SESSION.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _to_number(x: Any) -> float:
    try:
        if x is None:
            return 0.0
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).replace(",", "").strip()
        return float(s) if s else 0.0
    except Exception:
        return 0.0


def _guess_amount(obj: Dict[str, Any], prefer: List[str]) -> float:
    """
    Preferencia-lista alapján keres egy USD/amount mezőt.
    Pl. prefer=['disbursement','paid','funding'] stb.
    """
    # 1) preferált kulcsszavak
    for kw in prefer:
        for k, v in obj.items():
            lk = str(k).lower()
            if kw in lk and ("usd" in lk or "amount" in lk or "value" in lk):
                val = _to_number(v)
                if val:
                    return val

    # 2) bármilyen "usd" + amount/value
    for k, v in obj.items():
        lk = str(k).lower()
        if "usd" in lk and ("amount" in lk or "value" in lk or "total" in lk):
            val = _to_number(v)
            if val:
                return val

    return 0.0


def _guess_recipient(obj: Dict[str, Any]) -> str:
    for key in ["recipient", "recipientName", "recipient_name", "destination", "destinationName", "to", "country", "name"]:
        if key in obj and obj[key]:
            return str(obj[key])
    # néha nested
    for key in ["recipient", "destination", "to"]:
        if key in obj and isinstance(obj[key], dict):
            for k2 in ["name", "title", "label"]:
                if k2 in obj[key] and obj[key][k2]:
                    return str(obj[key][k2])
    return ""


def _normalize_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Visszaad 10 sort: recipient + commitments_usd + disbursements_usd + total_usd.
    """
    agg: Dict[str, Dict[str, float]] = {}

    for r in rows:
        recipient = _guess_recipient(r).strip()
        if not recipient:
            continue

        # commitments vs disbursements: best-effort mező-felismerés
        committed = _guess_amount(r, prefer=["commit", "pledge"])
        disbursed = _guess_amount(r, prefer=["disburse", "paid", "fund", "contribution"])

        # ha csak egy értéket találunk, tegyük total-nak
        total = 0.0
        if committed or disbursed:
            total = committed + disbursed
        else:
            total = _guess_amount(r, prefer=["total"])

        if recipient not in agg:
            agg[recipient] = {"commitments_usd": 0.0, "disbursements_usd": 0.0, "total_usd": 0.0}

        agg[recipient]["commitments_usd"] += committed
        agg[recipient]["disbursements_usd"] += disbursed
        agg[recipient]["total_usd"] += (total if total else (committed + disbursed))

    # rendezés total alapján
    out = []
    for recipient, vals in agg.items():
        total = vals["total_usd"]
        if total <= 0:
            total = vals["commitments_usd"] + vals["disbursements_usd"]
        out.append(
            {
                "recipient": recipient,
                "commitments_usd": round(vals["commitments_usd"], 2),
                "disbursements_usd": round(vals["disbursements_usd"], 2),
                "total_usd": round(total, 2),
            }
        )

    out.sort(key=lambda x: x.get("total_usd", 0.0), reverse=True)
    return out[:10]


def _extract_rows_from_response(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Többféle API válaszformátumot próbál kezelni.
    """
    if not data:
        return []

    # gyakori: {"data":[...]}
    if isinstance(data.get("data"), list):
        return [x for x in data["data"] if isinstance(x, dict)]

    # néha: {"results":[...]}
    if isinstance(data.get("results"), list):
        return [x for x in data["results"] if isinstance(x, dict)]

    # néha: {"items":[...]}
    if isinstance(data.get("items"), list):
        return [x for x in data["items"] if isinstance(x, dict)]

    # fallback: ha maga lista lenne (ritkább)
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]

    return []


def fetch_top10_for_donor(donor_name: str) -> List[Dict[str, Any]]:
    """
    Több végpontot próbál (ha az egyik nem megy / üres, jön a következő).
    A cél: 2025-ben donor -> top10 recipient, commitments & disbursements külön.
    """
    endpoints = [
        # 1) HPC Tools public API (ha elérhető)
        ("https://api.hpc.tools/v1/public/fts/flow", {"year": YEAR, "donor": donor_name, "groupby": "recipient", "limit": 200}),
        ("https://api.hpc.tools/v1/public/fts/flows", {"year": YEAR, "donor": donor_name, "groupby": "recipient", "limit": 200}),
        # 2) Humdata API (ha elérhető)
        ("https://api.humdata.org/v1/fts/flows", {"year": YEAR, "donor": donor_name, "groupby": "recipient", "limit": 200}),
        # 3) UNOCHA FTS (régebbi v2 – ha engedi)
        ("https://fts.unocha.org/api/v2/flows", {"year": YEAR, "donor": donor_name, "groupBy": "recipient", "limit": 200}),
    ]

    for url, params in endpoints:
        data = _get_json(url, params=params)
        rows = _extract_rows_from_response(data) if data else []
        norm = _normalize_rows(rows)
        if norm:
            return norm

        # ha nem sikerült, várunk kicsit (rate-limit / átmeneti)
        time.sleep(1)

    return []


def main():
    result = {"year": YEAR, "updated": datetime.utcnow().isoformat() + "Z", "donors": {}}

    for label, donor_name in DONORS.items():
        print(f"Fetching {label} ({donor_name}) ...")
        result["donors"][label] = fetch_top10_for_donor(donor_name)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"Saved: {OUT_PATH}")


if __name__ == "__main__":
    main()
