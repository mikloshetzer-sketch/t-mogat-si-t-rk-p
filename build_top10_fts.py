import requests
import json
from datetime import datetime

API_URL = "https://api.humdata.org/v1/fts/flows"

DONORS = {
    "EU": "European Union",
    "USA": "United States of America",
    "China": "China",
    "Russia": "Russian Federation"
}

YEAR = 2025
TOP_N = 10

def get_top10(donor_name):
    params = {
        "donor": donor_name,
        "year": YEAR
    }

    r = requests.get(API_URL, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()

    country_totals = {}

    for flow in data.get("data", []):
        country = flow.get("destination", {}).get("name")
        amount = flow.get("amountUSD", 0)

        if not country:
            continue

        country_totals[country] = country_totals.get(country, 0) + amount

    top = sorted(
        country_totals.items(),
        key=lambda x: x[1],
        reverse=True
    )[:TOP_N]

    return [
        {"country": c, "amount": round(a, 2)}
        for c, a in top
    ]

def main():
    result = {
        "year": YEAR,
        "updated": datetime.utcnow().isoformat() + "Z",
        "donors": {}
    }

    for key, name in DONORS.items():
        print(f"Fetching {key} data...")
        result["donors"][key] = get_top10(name)

    with open("data/top10_2025.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print("Data updated: data/top10_2025.json")

if __name__ == "__main__":
    main()
