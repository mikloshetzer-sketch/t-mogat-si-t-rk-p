const DONORS = [
  { key: "eu",     label: "EU",          mapId: "map-eu" },
  { key: "usa",    label: "USA",         mapId: "map-usa" },
  { key: "china",  label: "Kína",        mapId: "map-china" },
  { key: "russia", label: "Oroszország", mapId: "map-russia" },
];

const START = { center: [15, 0], zoom: 1.5 };

function fmtUsd(x) {
  try {
    return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(x);
  } catch {
    return `$${Math.round(x).toLocaleString("en-US")}`;
  }
}

async function loadJson(path) {
  const r = await fetch(path, { cache: "no-store" });
  if (!r.ok) throw new Error(`HTTP ${r.status} - ${path}`);
  return r.json();
}

function makeMap(divId) {
  const map = L.map(divId, { zoomControl: true, scrollWheelZoom: false })
    .setView(START.center, START.zoom);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 6,
    attribution: "&copy; OpenStreetMap"
  }).addTo(map);

  return map;
}

function bubbleRadius(amount) {
  const a = Math.max(1, amount);
  return Math.max(6, Math.min(26, Math.log10(a) * 4.2));
}

(async function main() {
  const top10 = await loadJson("./data/top10_2025.json");

  for (const d of DONORS) {
    const map = makeMap(d.mapId);
    const rows = top10[d.key] || [];

    if (!rows.length) {
      L.popup({ closeButton: false })
        .setLatLng([20, 0])
        .setContent("Nincs adat / nincs riportált TOP10 tétel.")
        .openOn(map);
      continue;
    }

    const markers = [];
    for (const r of rows) {
      const m = L.circleMarker([r.lat, r.lon], {
        radius: bubbleRadius(r.amount_usd),
        weight: 1,
        fillOpacity: 0.5
      }).addTo(map);

      m.bindTooltip(
        `<b>${r.country_name}</b><br>${fmtUsd(r.amount_usd)}<br><small>#${r.rank}</small>`,
        { sticky: true }
      );
      markers.push(m);
    }

    const group = L.featureGroup(markers);
    map.fitBounds(group.getBounds(), { padding: [10, 10] });
  }
})().catch(err => {
  console.error(err);
  alert("Hiba a térkép betöltésekor – nézd meg a konzolt.");
});
