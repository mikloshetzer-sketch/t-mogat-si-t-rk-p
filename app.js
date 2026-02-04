const DATA_URL = "data/top10_2025.json";

// Alap térkép beállítás
function createMap(containerId) {
  const map = L.map(containerId).setView([20, 0], 2);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "© OpenStreetMap contributors"
  }).addTo(map);

  return map;
}

// Koordináták országonként
const COUNTRY_COORDS = {
  "Ukraine": [48.3794, 31.1656],
  "Israel": [31.0461, 34.8516],
  "Gaza": [31.5, 34.47],
  "Yemen": [15.5527, 48.5164],
  "Syria": [34.8021, 38.9968],
  "Iraq": [33.2232, 43.6793],
  "Afghanistan": [33.9391, 67.71],
  "Sudan": [12.8628, 30.2176]
};

// Buborék megjelenítés
function showEmptyPopup(map) {
  L.popup()
    .setLatLng([20, 0])
    .setContent("Nincs adat / nincs riportált TOP10 tétel.")
    .openOn(map);
}

// Donor térkép kirajzolása
function renderDonorMap(map, donorName, entries) {
  if (!entries || entries.length === 0) {
    showEmptyPopup(map);
    return;
  }

  entries.forEach(item => {
    const coords = COUNTRY_COORDS[item.country];
    if (!coords) return;

    const marker = L.circleMarker(coords, {
      radius: Math.min(20, 5 + item.value / 100),
      fillColor: "#e63946",
      color: "#000",
      weight: 1,
      opacity: 1,
      fillOpacity: 0.8
    });

    marker.bindPopup(`
      <b>${donorName}</b><br>
      Célország: ${item.country}<br>
      Támogatás: ${item.value} millió USD
    `);

    marker.addTo(map);
  });
}

// Fő betöltés
async function loadData() {
  try {
    const response = await fetch(DATA_URL);
    const data = await response.json();

    const donors = data.donors;

    Object.keys(donors).forEach(donor => {
      const containerId = donor.toLowerCase().replace(/\s+/g, "-");
      const map = createMap(containerId);
      renderDonorMap(map, donor, donors[donor]);
    });

  } catch (err) {
    console.error("Hiba az adatok betöltésekor:", err);
  }
}

// Indítás
document.addEventListener("DOMContentLoaded", loadData);
