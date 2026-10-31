let catalog = { cpus: [], gpus: [], motherboards: [], games: [] };
let mode = "forward";
let selectedGame = null;

const $ = (id) => document.getElementById(id);

function optionList(select, values) {
  select.innerHTML = "";
  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  });
}

function gameIcon(title, initials) {
  const safeTitle = title.replace(/[&<>]/g, "");
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='64' height='64'>
    <rect width='64' height='64' rx='14' fill='#03050a'/>
    <rect x='4' y='4' width='56' height='56' rx='12' fill='#071a56' stroke='#ff1e35' stroke-width='3'/>
    <text x='32' y='39' text-anchor='middle' font-family='Arial' font-size='18' fill='#ffffff'>${initials}</text>
    <title>${safeTitle}</title>
  </svg>`;
  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
}

function showPopup(message) {
  $("popup-message").textContent = message;
  $("popup").classList.remove("hidden");
}

function clearErrors() {
  ["ram-error", "storage-error", "psu-error", "game-error"].forEach((id) => {
    $(id).textContent = "";
  });
}

function parseNumber(id, label, min, max, integer = false) {
  const value = $(id).value.trim();
  const parsed = integer ? Number.parseInt(value, 10) : Number.parseFloat(value);
  const errorId = id === "ram-capacity" ? "ram-error" : id === "storage-free" ? "storage-error" : "psu-error";
  if (!value || Number.isNaN(parsed)) {
    $(errorId).textContent = `${label} must be numeric.`;
    return null;
  }
  if (integer && String(parsed) !== value) {
    $(errorId).textContent = `${label} must be a whole number.`;
    return null;
  }
  if (parsed < min || parsed > max) {
    $(errorId).textContent = `${label} must be between ${min} and ${max}.`;
    return null;
  }
  return parsed;
}

function validateForm() {
  clearErrors();
  const ram = parseNumber("ram-capacity", "RAM capacity", 4, 128, true);
  const storage = parseNumber("storage-free", "Storage free space", 0, 10000, false);
  const psu = parseNumber("psu-wattage", "PSU wattage", 200, 1600, true);
  if (mode === "backward" && !selectedGame) {
    $("game-error").textContent = "Select a game from the suggestions.";
    return null;
  }
  if (ram === null || storage === null || psu === null) {
    return null;
  }
  return {
    mode,
    cpu: $("cpu").value,
    gpu: $("gpu").value,
    motherboard: $("motherboard").value,
    ram_capacity: ram,
    ram_gen: $("ram-gen").value,
    drive_type: $("drive-type").value,
    storage_free: storage,
    psu_wattage: psu,
    game_id: selectedGame ? selectedGame.id : "",
  };
}

function scoreGame(query, title) {
  const q = query.toLowerCase();
  const t = title.toLowerCase();
  if (t.startsWith(q)) return 1000 - t.length;
  if (t.includes(q)) return 700 - t.indexOf(q);
  let qi = 0;
  for (const ch of t) {
    if (ch === q[qi]) qi += 1;
    if (qi === q.length) break;
  }
  return qi > 0 ? qi * 20 : 0;
}

function renderSuggestions() {
  selectedGame = null;
  const query = $("game-search").value.trim();
  const box = $("game-suggestions");
  box.innerHTML = "";
  if (!query) return;

  catalog.games
    .map((game) => ({ game, score: scoreGame(query, game.title) }))
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 6)
    .forEach(({ game }) => {
      const row = document.createElement("button");
      row.type = "button";
      row.className = "suggestion";
      row.innerHTML = `<img alt="${game.title} icon" src="${gameIcon(game.title, game.icon)}"><span>${game.title}</span>`;
      row.addEventListener("click", () => {
        selectedGame = game;
        $("game-search").value = game.title;
        box.innerHTML = "";
        $("game-error").textContent = "";
      });
      box.appendChild(row);
    });
}

function setMode(nextMode) {
  mode = nextMode;
  document.querySelectorAll(".mode-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.mode === mode);
  });
  $("game-panel").classList.toggle("hidden", mode !== "backward");
  if (mode === "forward") {
    selectedGame = null;
    $("game-search").value = "";
    $("game-suggestions").innerHTML = "";
  }
}

function stage0Html(rows) {
  if (!rows.length) return "<h3>Stage 0 Pre-checks</h3><p>No Stage 0 output was captured.</p>";
  const items = rows.map((row) => {
    const statusClass = row.status === "PASS" ? "ok-text" : "bad-text";
    const outcome = row.status === "PASS" ? "Passed" : "Failed";
    return `<li><strong>${escapeHtml(row.rule)}</strong><br>${escapeHtml(row.explanation)}<br>
      Check performed: <code>${escapeHtml(row.check)}</code><br>
      Result: <span class="${statusClass}">${outcome}</span></li>`;
  }).join("");
  return `<h3>Stage 0 Pre-checks</h3><ul>${items}</ul>`;
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function finalHtml(text) {
  if (!text) return "";
  return `<h3>Final Diagnostic</h3><pre>${escapeHtml(text)}</pre>`;
}

async function runSynapse() {
  const payload = validateForm();
  if (!payload) {
    showPopup("Please fix the highlighted inputs before running SYNAPSE.");
    return;
  }
  $("loader").classList.remove("hidden");
  $("run-button").disabled = true;
  $("output").classList.add("hidden");

  try {
    const response = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok && data.error) {
      showPopup(data.error);
    }
    $("stage0-output").innerHTML = stage0Html(data.stage0 || []);
    $("final-output").innerHTML = data.precheck_passed
      ? finalHtml(data.final_text)
      : `<h3>Execution Stopped</h3><p>Stage 0 failed. The frontend flow cannot continue.</p>${finalHtml(data.final_text)}`;
    $("output").classList.remove("hidden");
    $("reset-button").classList.remove("hidden");
    $("output").scrollIntoView({ behavior: "smooth" });
  } catch (error) {
    showPopup(`Frontend error: ${error.message}`);
  } finally {
    $("loader").classList.add("hidden");
    $("run-button").disabled = false;
  }
}

function clearInputs() {
  ["ram-capacity", "storage-free", "psu-wattage", "game-search"].forEach((id) => {
    $(id).value = "";
  });
  $("ram-gen").value = "";
  $("drive-type").value = "SSD";
  selectedGame = null;
  $("game-suggestions").innerHTML = "";
  clearErrors();
}

function setupReveal() {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      entry.target.classList.toggle("in-view", entry.isIntersecting);
    });
  }, { threshold: 0.28 });
  document.querySelectorAll(".reveal").forEach((el) => observer.observe(el));
}

async function init() {
  setupReveal();
  const response = await fetch("/api/catalog");
  catalog = await response.json();
  optionList($("cpu"), catalog.cpus);
  optionList($("gpu"), catalog.gpus);
  optionList($("motherboard"), catalog.motherboards);
  document.querySelectorAll(".mode-button").forEach((button) => {
    button.addEventListener("click", () => setMode(button.dataset.mode));
  });
  $("game-search").addEventListener("input", renderSuggestions);
  $("run-button").addEventListener("click", runSynapse);
  $("clear-inputs").addEventListener("click", clearInputs);
  $("reset-button").addEventListener("click", () => window.location.reload());
  $("close-popup").addEventListener("click", () => $("popup").classList.add("hidden"));
}

init();
