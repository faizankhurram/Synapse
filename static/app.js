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
      row.textContent = game.title;
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

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function prettyLabel(value) {
  return String(value || "None").replaceAll("_", " ");
}

function stage0Html(rows) {
  const failedRows = rows.filter((row) => row.status !== "PASS");
  if (!failedRows.length) return "";
  const items = failedRows.map((row) => {
    const title = row.rule.replace(/^Rule\s+\d+\.\d+\s+/, "");
    return `<div class="fail-card">
      <h4>${escapeHtml(prettyLabel(title))}</h4>
      <p>${escapeHtml(row.explanation)}</p>
      <span class="bad-text">Failed</span>
    </div>`;
  }).join("");
  return `<div class="result-section stage0-fail">
    <h3>Stage 0 Compatibility Failure</h3>
    <p>Your hardware configuration is not physically valid. Fix the issues below before running game compatibility checks.</p>
    <div class="fail-grid">${items}</div>
  </div>`;
}

function verdictClass(verdict) {
  if (verdict === "RECOMMENDED") return "verdict-rec";
  if (verdict === "MINIMUM ONLY") return "verdict-min";
  return "verdict-bad";
}

function parseDiagnostics(lines) {
  const start = lines.findIndex((line) => line.trim() === "System diagnostics");
  if (start === -1) return {};
  const data = {};
  for (let i = start + 1; i < lines.length; i += 1) {
    const line = lines[i].trim();
    if (!line || line.includes("Requested game") || line === "Game compatibility verdicts") break;
    if (!line.includes(":")) continue;
    const [key, ...rest] = line.split(":");
    data[key.trim()] = prettyLabel(rest.join(":").trim() || "None");
  }
  return data;
}

function systemDiagnosticsHtml(lines) {
  const data = parseDiagnostics(lines);
  if (!Object.keys(data).length) return "";
  const rows = Object.entries(data).map(([key, value]) => (
    `<div class="kv-row"><span>${escapeHtml(key)}</span><strong>${escapeHtml(value)}</strong></div>`
  )).join("");
  return `<div class="result-section"><h3>System Diagnostics</h3><div class="kv-grid">${rows}</div></div>`;
}

function splitTitleNotes(rest) {
  const sorted = [...catalog.games].sort((a, b) => b.title.length - a.title.length);
  for (const game of sorted) {
    if (rest === game.title) return { title: game.title, notes: "None" };
    if (rest.startsWith(`${game.title} `)) {
      return { title: game.title, notes: rest.slice(game.title.length).trim() || "None" };
    }
  }
  const parts = rest.split(/\s{2,}/);
  if (parts.length >= 2) return { title: parts[0].trim(), notes: parts.slice(1).join(" ").trim() || "None" };
  return { title: rest, notes: "None" };
}

function forwardFinalHtml(text) {
  const lines = text.split("\n");
  const diagnostics = systemDiagnosticsHtml(lines);
  const gameStart = lines.findIndex((line) => line.trim() === "Game compatibility verdicts");
  const summaryLine = lines.find((line) => line.trim().startsWith("Summary:")) || "";
  const rows = [];
  if (gameStart !== -1) {
    for (let i = gameStart + 3; i < lines.length; i += 1) {
      const line = lines[i].trim();
      if (!line || line.startsWith("Summary:")) continue;
      const match = line.match(/^(G\d+)\s+(RECOMMENDED|MINIMUM ONLY|UNPLAYABLE)\s+(.+)$/);
      if (!match) continue;
      const { title, notes } = splitTitleNotes(match[3].trim());
      rows.push(`<tr>
        <td>${escapeHtml(title)}</td>
        <td><span class="verdict ${verdictClass(match[2])}">${escapeHtml(match[2])}</span></td>
        <td>${escapeHtml(notes)}</td>
      </tr>`);
    }
  }
  return `${diagnostics}
    <div class="result-section">
      <h3>Game Compatibility Verdicts</h3>
      <div class="table-wrap">
        <table class="verdict-table">
          <thead><tr><th>Game Name</th><th>Verdict</th><th>Notes</th></tr></thead>
          <tbody>${rows.join("")}</tbody>
        </table>
      </div>
    </div>
    <div class="result-section summary-card"><h3>Summary</h3><p>${escapeHtml(summaryLine.replace(/^Summary:\s*/, "").trim())}</p></div>`;
}

function gameNameOnly(rawLabel) {
  if (selectedGame && selectedGame.title) return selectedGame.title;
  const label = String(rawLabel || "").trim();
  const withoutId = label.replace(/^G\d+\s*[-–:]\s*/i, "").trim();
  const match = catalog.games.find((game) => (
    withoutId === game.title
    || label === game.title
    || label.endsWith(` - ${game.title}`)
    || label.includes(game.title)
  ));
  return match ? match.title : (withoutId || label || "Selected game");
}

function backwardFinalHtml(text) {
  const lines = text.split("\n");
  const diagnostics = systemDiagnosticsHtml(lines);
  const requestedIndex = lines.findIndex((line) => line.trim().startsWith("Requested game evaluation"));
  const requestedRaw = requestedIndex >= 0
    ? lines[requestedIndex].trim().replace(/^Requested game evaluation:\s*/, "")
    : "Selected game";
  const requested = gameNameOnly(requestedRaw);
  const details = {};
  let outlook = "";
  let capturingOutlook = false;
  for (let i = requestedIndex + 1; i < lines.length; i += 1) {
    const line = lines[i].trim();
    if (!line) {
      capturingOutlook = false;
      continue;
    }
    if (line.startsWith("Performance outlook:")) {
      outlook = line.replace(/^Performance outlook:\s*/, "").trim();
      capturingOutlook = true;
      continue;
    }
    if (capturingOutlook && !line.includes(":")) {
      outlook = `${outlook} ${line}`.trim();
      continue;
    }
    capturingOutlook = false;
    if (line.includes(":")) {
      const [key, ...rest] = line.split(":");
      details[key.trim()] = rest.join(":").trim() || "None";
    }
  }
  const verdict = prettyLabel(details.Verdict || details.verdict || "Unknown");
  const notes = prettyLabel(details.Notes || details.notes || "None");
  const warnings = prettyLabel(details["Game warnings"] || "None");
  return `${diagnostics}
    <div class="result-section focused-game">
      <h3>Requested Game Evaluation</h3>
      <div class="kv-grid">
        <div class="kv-row"><span>Game</span><strong>${escapeHtml(requested)}</strong></div>
        <div class="kv-row"><span>Verdict</span><strong><span class="verdict ${verdictClass(verdict)}">${escapeHtml(verdict)}</span></strong></div>
        <div class="kv-row"><span>Notes</span><strong>${escapeHtml(notes)}</strong></div>
        <div class="kv-row"><span>Game Warnings</span><strong>${escapeHtml(warnings)}</strong></div>
      </div>
      ${outlook ? `<div class="outlook-card"><h4>Performance Outlook</h4><p>${escapeHtml(outlook)}</p></div>` : ""}
    </div>`;
}

function finalHtml(text) {
  if (!text) return "";
  if (text.includes("Game compatibility verdicts")) return forwardFinalHtml(text);
  if (text.includes("Requested game evaluation")) return backwardFinalHtml(text);
  return "";
}

function showReset() {
  $("reset-row").classList.remove("hidden");
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
  $("reset-row").classList.add("hidden");

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

    const stage0 = stage0Html(data.stage0 || []);
    $("stage0-output").innerHTML = stage0;
    $("stage0-output").classList.toggle("hidden", !stage0);

    if (data.precheck_passed) {
      $("final-output").innerHTML = finalHtml(data.final_text);
      $("final-output").classList.remove("hidden");
    } else {
      $("final-output").innerHTML = "";
      $("final-output").classList.add("hidden");
    }

    $("output").classList.remove("hidden");
    showReset();
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

async function init() {
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
