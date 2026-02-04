// app.js
// Render donor TOP10 maps from data/top10_2025.json
// Supports BOTH schemas:
// 1) old: donors: { "EU": [ ... ] }
// 2) new: donors: { "EU": { commitments: [...], disbursements: [...] } }

const DATA_URL = "./data/top10_2025.json";

// Donor display names (HU)
const DONOR_LABELS = {
  EU: "EU",
  USA: "USA",
  Germany: "Németország",
  UK: "Egyesült Királyság",
  Japan: "Japán",
  France: "Franciaország",
  Canada: "Kanada",
  Sweden: "Svédország",
  Norway: "Norvégia",
  Netherlands: "Hollandia",
  China: "Kína",
  Russia: "Oroszország",
};

// Map center/zoom per donor (approx.)
const DONOR_MAP_VIEW = {
  EU: { center: [50.5, 10.0], zoom: 4 },
  USA: { center: [39.0, -98.0], zoom: 4 },
  Germany: { center: [51.0, 10.0], zoom: 5 },
  UK: { center: [54.5, -3.0], zoom: 5 },
  Japan: { center: [36.2, 138.2], zoom: 5 },
  France: { center: [46.5, 2.0], zoom: 5 },
  Canada: { center: [56.0, -106.0], zoom: 3 },
  Sweden: { center: [62.0, 15.0], zoom: 4 },
  Norway: { center: [64.5, 11.0], zoom: 4 },
  Netherlands: { center: [52.2, 5.3], zoom: 6 },
  China: { center: [35.9, 104.2], zoom: 4 },
  Russia: { center: [61.5, 105.3], zoom: 3 },
};

// Format numbers to nice USD-like
function fmtAmount(v) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return "-";
  const n = Number(v);
  try {
    return n.toLocaleString("en-US", { maximumFractionDigits: 0 });
  } catch {
    return String(Math.round(n));
  }
}

// A single item formatter (safe)
function itemLine(x) {
  // expect fields like: destination, amountUSD, amount, value, flowType, etc.
  const dest =
    x?.destination ||
    x?.destination_name ||
    x?.recipient ||
    x?.country ||
    x?.location ||
    "Ismeretlen cél";
  const amount =
    x?.amountUSD ?? x?.amount_usd ?? x?.amount ?? x?.value ?? x?.total ?? null;
  const extra = x?.appeal ? ` (${x.appeal})` : "";
  return `${dest}${extra}: <b>${fmtAmount(amount)}</b>`;
}

// Normalize donor data to { commitments: [], disbursements: [] }
function normalizeDonorNode(node) {
  if (!node) return { commitments: [], disbursements: [] };

  // old schema: array -> treat as "commitments" (or generic)
  if (Array.isArray(node)) {
    return { commitments: node, disbursements: [] };
  }

  // new schema: object with commitments/disbursements arrays
  const c = Array.isArray(node.commitments) ? node.commitments : [];
  const d = Array.isArray(node.disbursements) ? node.disbursements : [];
  return { commitments: c, disbursements: d };
}

function ensureMapContainerHeight(el) {
  // If CSS got lost, Leaflet map can be "invisible"
  const h = el.getBoundingClientRect().height;
  if (h < 120) el.style.height = "360px";
}

// Create a map into container id
function createLeafletMap(containerId, view) {
  const el = document.getElementById(containerId);
  if (!el) return null;

  ensureMapContainerHeight(el);

  // If Leaflet isn't loaded, show a readable error
  if (typeof L === "undefined") {
    el.innerHTML =
      '<div style="padding:12px;border:1px solid #ddd;border-radius:10px;">Hiba: a Leaflet könyvtár nem töltődött be (L undefined). Ellenőrizd az index.html-ben a Leaflet CSS/JS linkeket.</div>';
    return null;
  }

  const map = L.map(containerId, {
    zoomControl: true,
    attributionControl: true,
  });

  const center = view?.center ?? [20, 0];
  const zoom = view?.zoom ?? 2;
  map.setView(center, zoom);

  // OSM tiles
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap',
  }).addTo(map);

  return map;
}

function addPopupBox(map, html, atLatLng) {
  if (!map) return;
  const pos = atLatLng || map.getCenter();
  L.popup({ closeButton: false, autoClose: false, closeOnClick: false })
    .setLatLng(pos)
    .setContent(html)
    .openOn(map);
}

function renderDonorBlock(rootEl, donorKey, donorData) {
  const label = DONOR_LABELS[donorKey] || donorKey;

  const block = document.createElement("section");
  block.style.margin = "18px 0 34px 0";

  const title = document.createElement("h2");
  title.textContent = label;
  title.style.margin = "10px 0 10px 0";
  block.appendChild(title);

  const mapId = `map_${donorKey.replace(/\W+/g, "_")}`;
  const mapDiv = document.createElement("div");
  mapDiv.id = mapId;
  mapDiv.style.width = "100%";
  mapDiv.style.height = "360px";
  mapDiv.style.borderRadius = "14px";
  mapDiv.style.overflow = "hidden";
  mapDiv.style.border = "1px solid #eee";
  block.appendChild(mapDiv);

  rootEl.appendChild(block);

  const view = DONOR_MAP_VIEW[donorKey] || { center: [20, 0], zoom: 2 };
  const map = createLeafletMap(mapId, view);

  const c = donorData.commitments || [];
  const d = donorData.disbursements || [];

  const hasAny = (c.length || 0) + (d.length || 0) > 0;

  if (!hasAny) {
    addPopupBox(
      map,
      `<div style="font-family:system-ui;padding:10px 12px;border-radius:12px;">
        <b>Nincs adat / nincs riportált TOP10 tétel.</b>
      </div>`,
      null
    );
    return;
  }

  const cHtml =
    c.length > 0
      ? `<div style="margin-top:8px;"><b>Commitments (vállalások)</b><br>${c
          .slice(0, 10)
          .map(itemLine)
          .join("<br>")}</div>`
      : `<div style="margin-top:8px;"><b>Commitments</b><br>Nincs adat</div>`;

  const dHtml =
    d.length > 0
      ? `<div style="margin-top:10px;"><b>Disbursements (kifizetések)</b><br>${d
          .slice(0, 10)
          .map(itemLine)
          .join("<br>")}</div>`
      : `<div style="margin-top:10px;"><b>Disbursements</b><br>Nincs adat</div>`;

  addPopupBox(
    map,
    `<div style="font-family:system-ui;font-size:13px;line-height:1.35;padding:10px 12px;border-radius:12px;max-width:360px;">
      ${cHtml}
      ${dHtml}
    </div>`,
    null
  );
}

async function main() {
  const root = document.getElementById("app");
  if (!root) {
    document.body.innerHTML =
      "<div style='padding:14px'>Hiányzik az #app konténer az index.html-ből.</div>";
    return;
  }

  // Clear
  root.innerHTML = "";

  // Title
  const h1 = document.createElement("h1");
  h1.textContent = "2025 – TOP10 pénzügyi támogatások országonként";
  h1.style.margin = "8px 0 6px 0";
  root.appendChild(h1);

  const p = document.createElement("p");
  p.textContent =
    "Adat: OCHA Financial Tracking Service (FTS) – humanitárius finanszírozás";
  p.style.margin = "0 0 18px 0";
  root.appendChild(p);

  let data;
  try {
    const res = await fetch(DATA_URL, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status} for ${DATA_URL}`);
    data = await res.json();
  } catch (e) {
    root.innerHTML += `<div style="padding:12px;border:1px solid #ddd;border-radius:10px;">
      Nem sikerült betölteni a JSON-t: <b>${DATA_URL}</b><br>
      ${String(e)}
    </div>`;
    return;
  }

  const donorsNode = data?.donors || {};
  const donorKeys = Object.keys(donorsNode);

  if (donorKeys.length === 0) {
    root.innerHTML += `<div style="padding:12px;border:1px solid #ddd;border-radius:10px;">
      A JSON üres: nincs donors kulcs.
    </div>`;
    return;
  }

  // Render in a 2-column grid (like your screenshots)
  const grid = document.createElement("div");
  grid.style.display = "grid";
  grid.style.gridTemplateColumns = "1fr 1fr";
  grid.style.gap = "26px";
  grid.style.alignItems = "start";
  root.appendChild(grid);

  // Keep a stable order (common donors first)
  const preferredOrder = [
    "EU",
    "USA",
    "China",
    "Russia",
    "Germany",
    "UK",
    "Japan",
    "France",
    "Canada",
    "Sweden",
    "Norway",
    "Netherlands",
  ];

  const ordered = [
    ...preferredOrder.filter((k) => donorKeys.includes(k)),
    ...donorKeys.filter((k) => !preferredOrder.includes(k)),
  ];

  for (const k of ordered) {
    const norm = normalizeDonorNode(donorsNode[k]);
    renderDonorBlock(grid, k, norm);
  }
}

main();
