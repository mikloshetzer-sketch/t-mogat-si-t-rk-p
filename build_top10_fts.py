import json
import os
import requests
from collections import defaultdict

YEAR = 2025
BASE = "https://api.hpc.tools/v1"

DONORS = {
    "eu": ["European Union", "European Commission"],
    "usa": ["United States"],
    "china": ["China"],
    "russia": ["Russian Federation", "Russia"],
}

RESTCOUNTRIES = "https://restcountries.com/v3.1/alpha/{}"


def get_json(url, params=None):
    r = requests.get(url, params=params, timeout=60, headers={"User-Agent": "github-actions"})
    r.raise_for_status()
    return r.json()


def get_centroid(iso3):
    try:
        data = get_json(RESTCOUNTRIES.format(iso3))
        lat, lon = data[0]["latlng"]
        return float(lat), float(lon)
    except Exception:
        return 0.0, 0.0


def find_donors():
    donors = get_json(f"{BASE}/public/fts/donor")
    rows = donors.get("data", donors)
    ids = {}

    for key, patterns in DONORS.items():
        for d in rows:
            name = (d.get("name") or "")
            if any(p.lower() in name.lower() for p in patterns):
                ids[key] = d.get("id")
                break

    return ids


def top10_for_donor(donor_id):
    flows = []
    offset = 0
    limit = 500

    while True:
        params = {
            "donor": donor_id,
            "year": YEAR,
            "limit": limit,
            "offset": offset,
            "currency": "USD",
        }
        data = get_json(f"{BASE}/public/fts/flow", params)
        rows = data.get("data", data)
        if not rows:
            break
        flows.extend(rows)
        offset += limit

    agg = defaultdict(lambda: {"amount": 0.0, "name": ""})

    for r in flows:
        iso3 = (r.get("destinationIso3") or "").upper()
        if not iso3:
            continue
        agg[iso3]["amount"] += float(r.get("amountUSD") or 0.0)
        agg[iso3]["name"] = r.get("destinationName") or iso3

    items = sorted(agg.items(), key=lambda x: x[1]["amount"], reverse=True)[:10]

    result = []
    for i, (iso3, info) in enumerate(items, start=1):
        lat, lon = get_centroid(iso3)
        result.append(
            {
                "rank": i,
                "iso3": iso3,
                "country_name": info["name"],
                "amount_usd": round(info["amount"], 2),
                "lat": lat,
                "lon": lon,
            }
        )

    return result


def main():
    donor_ids = find_donors()
    out = {}

    for key, did in donor_ids.items():
        if did:
            out[key] = top10_for_donor(did)
        else:
            out[key] = []

    os.makedirs("data", exist_ok=True)
    with open("data/top10_2025.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("TOP10 data updated")


if __name__ == "__main__":
    main()
