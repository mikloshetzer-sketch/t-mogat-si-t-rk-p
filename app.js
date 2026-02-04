/* app.js
   - Betölti: data/top10_2025.json
   - Kezeli mindkét formátumot:
       donors[donor] = []                         (régi)
       donors[donor] = {commitments:[], disbursements:[]}  (új)
   - Mindkét értéket külön megjeleníti (commitments + disbursements)
   - Akkor is kirajzolja a térképet, ha nincs adat (ne legyen "üres fehér")
*/

const DATA_URL = "data/top10_2025.json";

const DONOR_ORDER = [
  "EU", "USA", "China", "Russia", "Germany", "UK", "Japan", "France",
  "Canada", "Sweden", "Norway", "Netherlands"
];

function fmtUSD(x) {
  if (x === null || x === undefined || isNaN(Number(x))) return "–";
  const n = Number(x);
  // rövid, érthető formátum
  return n.toLocaleString(undefined, { maximumFractionDigits: 0 }) + " USD";
}

// Normalizálás: mindig egy lista legyen, ahol elem:
// { recipient, commitments, disbursements }
function normalizeDonorData(raw) {
  // Új formátum
  if (raw && typeof raw === "object" && !Array.isArray(raw)) {
    const c = Array.isArray(raw.commitments) ? raw.commitments : [];
    const d = Array.isArray(raw.disbursements) ? raw.disbursements : [];

    // Ha a build script eleve így adja vissza: [{recipient, amount}, ...]
    // akkor összefésüljük recipient szerint.
    const byRecipient = new Map();

    for (const it of c) {
      const recipient = it.recipient || it.location || it.country || it.name || it.recipient_name || it.to || "Unknown";
      const amount = it.amount ?? it.value ?? it.total ?? it.usd ?? it.funding ?? 0;
      if (!byRecipient.has(recipient)) byRecipient.set(recipient, { recipient, commitments: 0, disbursements: 0 });
      byRecipient.get(recipient).commitments += Number(amount) || 0;
    }

    for (const it of d) {
      const recipient = it.recipient || it.location || it.country || it.name || it.recipient_name || it.to || "Unknown";
      const amount = it.amount ?? it.value ?? it.total ?? it.usd ?? it.funding ?? 0;
      if (!byRecipient.has(recipient)) byRecipient.set(recipient, { recipient, commitments: 0, disbursements: 0 });
      byRecipient.get(recipient).disbursements += Number(amount) || 0;
    }

    return Array.from(byRecipient.values())
      .sort((a, b) => (b.disbursements + b.commitments) - (a.disbursements + a.commitments))
      .slice(0, 10);
  }

  // Régi formátum: tömb (feltételezzük, hogy amount van benne)
  if (Array.isArray(raw)) {
    return raw.slice(0, 10).map(it => {
      const recipient = it.recipient || it.location || it.country || it.name || it.recipient_name || it.to || "Unknown";
      const amount = it.amount ?? it.value ?? it.total ?? it.usd ?? it.funding ?? 0;
      return { recipient, commitments: 0, disbursements: Number(amount) || 0 };
    });
  }

  return [];
}

function ensureBaseLayout() {
  // Ha van #app, oda dolgozunk, különben létrehozzuk
  let root = document.getElementById("app");
  if (!root) {
    root = document.createElement("div");
    root.id = "app";
    document.body.appendChild(root);
  }

  // Minimál stílus inline (ne kelljen CSS-t piszkálni)
  root.style.maxWidth = "1200px";
  root.style.margin = "16px auto";
  root.style.padding = "0 12px";
  root.style.fontFamily = "system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif";

  return root;
}

function createDonorSection(root, donorName) {
  const section = document.createElement("section");
  section.style.margin = "24px 0";
  section.style.padding = "12px 0";
  section.style.borderTop = "1px solid rgba(0,0,0,0.08)";

  const h2 = document.createElement("h2");
  h2.textContent = donorName;
  h2.style.margin = "0 0 10px 0";

  const row = document.createElement("div");
  row.style.display = "grid";
  row.style.gridTemplateColumns = "1.2fr 1fr";
  row.style.gap = "12px";
  row.style.alignItems = "start";

  const mapBox = document.createElement("div");
  mapBox.style.height = "260px";
  mapBox.style.borderRadius = "12px";
  mapBox.style.overflow = "hidden";
  mapBox.style.border = "1px solid rgba(0,0,0,0.12)";

  const mapId = "map_" + donorName.replace(/\W+/g, "_");
  mapBox.id = mapId;

  const listBox = document.createElement("div");
  listBox.style.border = "1px solid rgba(0,0,0,0.12)";
  listBox.style.borderRadius = "12px";
  listBox.style.padding = "10px 12px";
  listBox.style.minHeight = "260px";

  const note = document.createElement("div");
  note.style.fontSize = "13px";
  note.style.opacity = "0.8";
  note.style.marginBottom = "8px";
  note.textContent = "Commitments és Disbursements külön értékként.";

  const ul = document.createElement("ol");
  ul.style.margin = "0";
  ul.style.paddingLeft = "18px";

  listBox.appendChild(note);
  listBox.appendChild(ul);

  row.appendChild(mapBox);
  row.appendChild(listBox);

  section.appendChild(h2);
  section.appendChild(row);

  root.appendChild(section);

  // Leaflet map: akkor is legyen alaptérkép, ha nincs marker
  const map = L.map(mapId, { zoomControl: true }).setView([20, 0], 2);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 6,
    attribution: '&copy; OpenStreetMap'
  }).addTo(map);

  return { ul, map };
}

function fillList(ul, items) {
  ul.innerHTML = "";

  if (!items || items.length === 0) {
    const li = document.createElement("li");
    li.textContent = "Nincs adat / nincs riportált TOP10 tétel.";
    ul.appendChild(li);
    return;
  }

  for (const it of items) {
    const li = document.createElement("li");
    li.style.margin = "6px 0";
    li.innerHTML =
      `<strong>${escapeHtml(it.recipient)}</strong><br>` +
      `<span style="opacity:.85">Commitments:</span> ${fmtUSD(it.commitments)} &nbsp; | &nbsp; ` +
      `<span style="opacity:.85">Disbursements:</span> ${fmtUSD(it.disbursements)}`;
    ul.appendChild(li);
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  }[c]));
}

async function main() {
  const root = ensureBaseLayout();

  // Fejléc / cím
  const title = document.createElement("div");
  title.style.margin = "10px 0 18px 0";
  title.style.fontSize = "16px";
  title.textContent = "Adat: OCHA Financial Tracking Service (FTS) – humanitárius finanszírozás (reported)";
  root.prepend(title);

  const url = DATA_URL + "?cb=" + Date.now(); // cache bust
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error("Nem sikerült betölteni: " + DATA_URL);

  const data = await res.json();
  const donors = (data && data.donors) ? data.donors : {};

  // Ha a JSON-ban más donorok vannak, ezt is vegyük fel
  const donorNames = Array.from(new Set([
    ...DONOR_ORDER.filter(d => donors[d] !== undefined),
    ...Object.keys(donors)
  ]));

  for (const donor of donorNames) {
    const { ul } = createDonorSection(root, donor);
    const items = normalizeDonorData(donors[donor]);
    fillList(ul, items);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  main().catch(err => {
    console.error(err);
    const root = ensureBaseLayout();
    const box = document.createElement("pre");
    box.style.whiteSpace = "pre-wrap";
    box.style.padding = "12px";
    box.style.border = "1px solid rgba(0,0,0,0.2)";
    box.style.borderRadius = "12px";
    box.textContent = "Hiba: " + (err && err.message ? err.message : String(err));
    root.appendChild(box);
  });
});
