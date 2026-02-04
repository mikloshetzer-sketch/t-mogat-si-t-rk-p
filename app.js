// app.js — donor TOP10 map renderer (commitments + disbursements)
// Expects: data/top10_2025.json with structure:
// { year, updated, donors: { "EU": { commitments: [...], disbursements: [...] }, ... } }

const DATA_URL = "./data/top10_2025.json";

const DONOR_ORDER = [
  "EU",
  "USA",
  "Germany",
  "UK",
  "Japan",
  "France",
  "Canada",
  "Sweden",
  "Norway",
  "Netherlands",
  "China",
  "Russia",
];

const DEFAULT_CENTER = [20, 10];
const DEFAULT_ZOOM = 2;

function el(tag, attrs = {}, ...children) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === "class") n.className = v;
    else if (k === "style") Object.assign(n.style, v);
    else n.setAttribute(k, v);
  }
  for (const c of children) {
    if (c == null) continue;
    if (typeof c === "string") n.appendChild(document.createTextNode(c));
    else n.appendChild(c);
  }
  return n;
}

function safeNum(x) {
  const n = Number(x);
  return Number.isFinite(n) ? n : 0;
}

function pick(obj, keys, fallback = null) {
  for (const k of keys) {
    if (obj && obj[k] != null) return obj[k];
  }
  return fallback;
}

function fmtUSD(v) {
  const n = safeNum(v);
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0,
    }).format(n);
  } catch {
    return `$${Math.round(n).toLocaleString("en-US")}`;
  }
}

function normalizeItem(item) {
  // Try to support multiple possible field names
  const lat = pick(item, ["lat", "latitude", "y"]);
  const lon = pick(item, ["lon", "lng", "longitude", "x"]);
  const amount = pick(item, ["amount_usd", "amount", "value", "total_usd", "total"]);
  const country = pick(item, ["country", "country_name", "recipient", "location"], "Unknown");
  const iso3 = pick(item, ["iso3", "country_iso3"], null);

  const latN = Number(lat);
  const lonN = Number(lon);
  if (!Number.isFinite(latN) || !Number.isFinite(lonN)) return null;

  return {
    country,
    iso3,
    lat: latN,
    lon: lonN,
    amount: safeNum(amount),
    raw: item,
  };
}

function radiusFromAmount(amount) {
  // Nice-ish scaling: sqrt to reduce extremes
  const a = Math.max(0, safeNum(amount));
  const r = Math.sqrt(a) / 800; // tweak factor
  return Math.min(28, Math.max(4, r));
}

function sumAmounts(list) {
  return (list || []).reduce((acc, it) => acc + safeNum(it.amount), 0);
}

async function loadData() {
  const res = await fetch(DATA_URL, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to load ${DATA_URL}: ${res.status}`);
  return res.json();
}

function ensureLeafletReady() {
  if (!window.L) {
    throw new Error("Leaflet (window.L) not found. Check Leaflet JS include in index.html.");
  }
}

function buildDonorSection(root, donorKey, donorObj) {
  const title = el("h2", { class: "donor-title" }, donorKey);

  const card = el("div", { class: "donor-card" });
  const headerRow = el("div", { class: "donor-header" }, title);

  const mapDiv = el("div", {
    class: "map",
    id: `map-${donorKey.replace(/\s+/g, "-")}`,
    style: { height: "360px", width: "100%", borderRadius: "12px" },
  });

  const info = el("div", { class: "donor-info", style: { margin: "10px 0 0 0" } });

  card.appendChild(headerRow);
  card.appendChild(mapDiv);
  card.appendChild(info);
  root.appendChild(card);

  const commitmentsRaw = (donorObj && donorObj.commitments) || [];
  const disbursementsRaw = (donorObj && donorObj.disbursements) || [];

  const commitments = commitmentsRaw.map(normalizeItem).filter(Boolean);
  const disbursements = disbursementsRaw.map(normalizeItem).filter(Boolean);

  const totalC = sumAmounts(commitments);
  const totalD = sumAmounts(disbursements);

  // Header totals (külön-külön látszik mindkettő)
  info.appendChild(
    el(
      "div",
      { class: "totals" },
      `Commitments: ${fmtUSD(totalC)}  |  Disbursements: ${fmtUSD(totalD)}`
    )
  );

  ensureLeafletReady();

  const map = L.map(mapDiv, { scrollWheelZoom: false }).setView(DEFAULT_CENTER, DEFAULT_ZOOM);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 8,
    attribution: '&copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a>',
  }).addTo(map);

  const layerCommit = L.layerGroup();
  const layerDisb = L.layerGroup();

  function addMarkers(items, layer, label) {
    for (const it of items) {
      const r = radiusFromAmount(it.amount);
      const marker = L.circleMarker([it.lat, it.lon], {
        radius: r,
        weight: 1,
        fillOpacity: 0.55,
      });

      const nameLine = it.iso3 ? `${it.country} (${it.iso3})` : `${it.country}`;
      const html =
        `<b>${nameLine}</b><br/>` +
        `<b>${label}:</b> ${fmtUSD(it.amount)}`;

      marker.bindPopup(html);
      marker.addTo(layer);
    }
  }

  addMarkers(commitments, layerCommit, "Commitments");
  addMarkers(disbursements, layerDisb, "Disbursements");

  // Default: both shown, but elkülöníthető (Layer control)
  layerCommit.addTo(map);
  layerDisb.addTo(map);

  L.control
    .layers(
      {},
      {
        Commitments: layerCommit,
        Disbursements: layerDisb,
      },
      { collapsed: false }
    )
    .addTo(map);

  // Fit bounds if any data exists
  const allPts = [...commitments, ...disbursements];
  if (allPts.length > 0) {
    const bounds = L.latLngBounds(allPts.map((p) => [p.lat, p.lon]));
    map.fitBounds(bounds.pad(0.2));
  } else {
    // No data bubble
    const msg = el(
      "div",
      {
        class: "no-data",
        style: {
          position: "absolute",
          top: "12px",
          left: "50%",
          transform: "translateX(-50%)",
          background: "white",
          padding: "10px 14px",
          borderRadius: "12px",
          boxShadow: "0 6px 18px rgba(0,0,0,0.15)",
          zIndex: 500,
          fontSize: "14px",
        },
      },
      "Nincs adat / nincs riportált TOP10 tétel."
    );
    mapDiv.style.position = "relative";
    mapDiv.appendChild(msg);
  }
}

async function main() {
  const root = document.getElementById("app");
  if (!root) throw new Error('Missing root element: <div id="app"></div>');

  const data = await loadData();

  // Header line
  const header = document.getElementById("meta");
  if (header) {
    header.textContent = `Adat: OCHA Financial Tracking Service (FTS) – humanitárius finanszírozás (reported) | Year: ${data.year} | Updated: ${data.updated}`;
  }

  const donors = (data && data.donors) || {};

  // Render in a 2-column grid if you already have CSS; otherwise it will stack.
  for (const key of DONOR_ORDER) {
    if (donors[key]) buildDonorSection(root, key, donors[key]);
  }

  // Render any extra donors not in the list (just in case)
  for (const [key, obj] of Object.entries(donors)) {
    if (!DONOR_ORDER.includes(key)) buildDonorSection(root, key, obj);
  }
}

main().catch((err) => {
  console.error(err);
  const root = document.getElementById("app");
  if (root) {
    root.innerHTML = `<pre style="color:#b00020;white-space:pre-wrap">APP ERROR:\n${String(
      err && err.stack ? err.stack : err
    )}</pre>`;
  }
});
