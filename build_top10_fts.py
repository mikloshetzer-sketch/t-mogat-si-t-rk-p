import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests

YEAR = 2025
OUT_PATH = "data/top10_2025.json"

# Kulcs: ami a weben megjelenik (a te oldalon)
# Érték: donor név, amit az FTS nagy eséllyel elfogad
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

# Az előző hibád itt volt: api.humdata.org -> NEM jó.
# Az FTS API tipikusan ezen megy:
BASE_URLS = [
    "https://api.hpc.tools/v1/fts/flows",
    # tartalék (ha valamiért átirányít / változik):
    "https://fts.unocha.org/api/v1/flows",
]

# Ha az API paraméter neve eltér, több variációt próbálunk.
FLOWTYPE_PARAM_CANDIDATES = ["flowType", "flowtype", "type"]
GROUPBY_PARAM_CANDIDATES = ["groupby", "groupBy"]

# A két “féle támogatás”
FLOW_TYPES = {
    "commitments": "commitment",
    "disbursements": "disbursement",
}


def _as_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def _pick_amount(item: Dict[str, Any]) -> Optional[float]:
    # Sokféle kulcsnév előfordulhat, ezért több mezőt is nézünk
    for k in [
        "amountUSD",
        "amountUsd",
        "amount",
        "total",
        "totalAmount",
        "total_amount",
        "value",
        "valueUsd",
        "originalAmount",
    ]:
        if k in item:
            v = _as_float(item.get(k))
            if v is not None:
                return v
    return None


def _pick_name_and_iso(item: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    # Recipient/destination mezők is sokféleképp jöhetnek
    for name_key in ["recipient", "recipientName", "destination", "destinationName", "locationName", "countryName", "name"]:
        if name_key in item and item.get(name_key):
            name = str(item.get(name_key))
            iso = None
            for iso_key in ["iso2", "ISO2", "countryCode", "recipientIso2", "destinationIso2", "code"]:
                if iso_key in item and item.get(iso_key):
                    iso = str(item.get(iso_key))
                    break
            return name, iso
    return None, None


def _extract_rows(payload: Any) -> List[Dict[str, Any]]:
    # Várhatóan dict és benne "data" lista, de legyen robust
    if isinstance(payload, dict):
        if isinstance(payload.get("data"), list):
            return payload["data"]
        if isinstance(payload.get("results"), list):
            return payload["results"]
        # néha a top-szint maga a lista:
    if isinstance(payload, list):
        return payload
    return []


def fetch_top10_for_donor(donor_query: str, flow_type_value: str) -> List[Dict[str, Any]]:
    """
    Visszaad TOP10 recipient listát:
    [
      { "recipient": "...", "iso2": "UA", "amount_usd": 12345.67 },
      ...
    ]
    """
    session = requests.Session()
    session.headers.update({"User-Agent": "top10-fts-bot/1.0"})

    # Próbáljuk több URL-lel és több paraméter variációval
    last_error = None

    for base_url in BASE_URLS:
        for flowtype_param in FLOWTYPE_PARAM_CANDIDATES:
            for groupby_param in GROUPBY_PARAM_CANDIDATES:
                params = {
                    "year": YEAR,
                    "donor": donor_query,
                    groupby_param: "recipient",
                    "limit": 10,
                    "sort": "desc",
                    flowtype_param: flow_type_value,
                }

                try:
                    r = session.get(base_url, params=params, timeout=30)
                    if r.status_code >= 400:
                        last_error = f"{base_url} -> HTTP {r.status_code}: {r.text[:200]}"
                        continue

                    payload = r.json()
                    rows = _extract_rows(payload)

                    out: List[Dict[str, Any]] = []
                    for row in rows:
                        if not isinstance(row, dict):
                            continue

                        name, iso2 = _pick_name_and_iso(row)
                        amt = _pick_amount(row)

                        if name and (amt is not None):
                            out.append(
                                {
                                    "recipient": name,
                                    "iso2": (iso2.upper() if isinstance(iso2, str) else None),
                                    "amount_usd": amt,
                                }
                            )

                    # Ha kaptunk értelmes adatot, visszaadjuk
                    if len(out) > 0:
                        return out

                except Exception as e:
                    last_error = f"{base_url} -> {type(e).__name__}: {e}"
                    continue

    print(f"[WARN] No data for donor='{donor_query}' flowType='{flow_type_value}'. Last error: {last_error}")
    return []


def merge_commitments_disbursements(
    commitments: List[Dict[str, Any]], disbursements: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Egy listába összefésüli a két típust recipient alapján,
    hogy a térkép egyből tudjon dolgozni vele, és külön látszódjon mindkettő.
    """
    by_key: Dict[str, Dict[str, Any]] = {}

    def key_of(x: Dict[str, Any]) -> str:
        # iso2 ha van, különben név
        iso2 = (x.get("iso2") or "").strip().upper()
        if iso2:
            return f"ISO:{iso2}"
        return f"NAME:{(x.get('recipient') or '').strip().lower()}"

    for row in commitments:
        k = key_of(row)
        by_key.setdefault(k, {"recipient": row.get("recipient"), "iso2": row.get("iso2"), "commitment_usd": 0.0, "disbursement_usd": 0.0})
        by_key[k]["commitment_usd"] = float(row.get("amount_usd") or 0.0)

    for row in disbursements:
        k = key_of(row)
        by_key.setdefault(k, {"recipient": row.get("recipient"), "iso2": row.get("iso2"), "commitment_usd": 0.0, "disbursement_usd": 0.0})
        by_key[k]["disbursement_usd"] = float(row.get("amount_usd") or 0.0)

    # A térképhez “alap” amount mezőnek tegyük a disbursement-et (legtöbbször ezt akarod látni),
    # de a popupban majd külön kiírható mindkettő.
    merged = list(by_key.values())
    for x in merged:
        x["amount_usd"] = x.get("disbursement_usd", 0.0)

    # Rendezés: disbursement szerint csökkenő, és TOP10
    merged.sort(key=lambda z: float(z.get("disbursement_usd") or 0.0), reverse=True)
    return merged[:10]


def main() -> None:
    result: Dict[str, Any] = {
        "year": YEAR,
        "updated": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "donors": {},
    }

    for donor_key, donor_query in DONORS.items():
        print(f"Fetching donor={donor_key} ({donor_query}) year={YEAR} ...")

        comm = fetch_top10_for_donor(donor_query, FLOW_TYPES["commitments"])
        time.sleep(0.4)  # kicsi udvariasság

        disb = fetch_top10_for_donor(donor_query, FLOW_TYPES["disbursements"])
        time.sleep(0.4)

        merged = merge_commitments_disbursements(comm, disb)
        result["donors"][donor_key] = merged

        print(f"  -> {len(merged)} merged recipients")

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"OK: wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
