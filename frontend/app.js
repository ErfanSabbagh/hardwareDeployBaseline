/**
 * Two-slide Hardware Deploy UI
 * Slide A: pin config → generate/compile
 * Slide B: serial monitor + telemetry
 *
 * Chrome / Edge / Opera, HTTPS or localhost for Web Serial.
 */

const API_BASE =
  window.location.port === "8080" || window.location.port === "5500"
    ? "http://localhost:8000"
    : "";

let editor = null;
let port = null;
let reader = null;
let keepReading = false;
let hexBlobUrl = null;
let boards = [];
let components = [];
let lastGenerate = null;
let telemetry = {};

const $ = (sel) => document.querySelector(sel);

function api(path) {
  return API_BASE + path;
}

require.config({
  paths: { vs: "https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.45.0/min/vs" },
});

require(["vs/editor/editor.main"], () => {
  editor = monaco.editor.create(document.getElementById("editor"), {
    value: "// Generate & compile to fill this editor\n",
    language: "cpp",
    theme: "vs-dark",
    automaticLayout: true,
    minimap: { enabled: false },
    fontSize: 13,
    fontFamily: "'JetBrains Mono', 'Fira Code', Consolas, monospace",
    scrollBeyondLastLine: false,
    padding: { top: 12 },
  });
});

function currentBoard() {
  return boards.find((b) => b.id === $("#board-select").value);
}

function componentsFor(kind) {
  return components.filter((c) => c.kind === kind);
}

function logPipe(msg) {
  const el = $("#pipeline-log");
  el.textContent += msg + (msg.endsWith("\n") ? "" : "\n");
  el.scrollTop = el.scrollHeight;
  $("#pipeline-log-copy").textContent = el.textContent;
}

function setStatus(text, cls = "") {
  const el = $("#connection-status");
  el.textContent = text;
  el.className = "status " + cls;
}

function appendMonitor(text, type = "out") {
  const out = $("#serial-output");
  const span = document.createElement("span");
  span.className = "line-" + type;
  span.textContent = text + (text.endsWith("\n") ? "" : "\n");
  out.appendChild(span);
  if ($("#auto-scroll").checked) out.scrollTop = out.scrollHeight;
  parseTelemetry(text);
}

function parseTelemetry(text) {
  const re = /\b([A-Z][A-Z0-9_]*)=(-?\d+(?:\.\d+)?|[^\s]+)/g;
  let m;
  while ((m = re.exec(text))) {
    telemetry[m[1]] = m[2];
  }
  renderChips();
}

function renderChips() {
  const box = $("#telemetry-chips");
  box.innerHTML = Object.entries(telemetry)
    .map(
      ([k, v]) =>
        `<span class="chip"><span class="k">${k}</span>=<span class="v">${v}</span></span>`
    )
    .join("");
}

function showSlide(which) {
  const config = which === "config";
  $("#slide-config").classList.toggle("hidden", !config);
  $("#slide-dash").classList.toggle("hidden", config);
  $("#nav-config").classList.toggle("active", config);
  $("#nav-dash").classList.toggle("active", !config);
}

$("#nav-config").addEventListener("click", () => showSlide("config"));
$("#nav-dash").addEventListener("click", () => showSlide("dash"));
$("#btn-back-config").addEventListener("click", () => showSlide("config"));

function pinOptions(board) {
  return (board?.pins || [])
    .map((p) => `<option value="${p.id}">${p.label}</option>`)
    .join("");
}

function componentOptions(kind) {
  return componentsFor(kind)
    .map((c) => `<option value="${c.id}">${c.name}</option>`)
    .join("");
}

function addPinRow(listEl, kind, preset) {
  const board = currentBoard();
  const row = document.createElement("div");
  row.className = "pin-row";
  row.innerHTML = `
    <select class="pin-id">${pinOptions(board)}</select>
    <select class="pin-comp">${componentOptions(kind)}</select>
    <input type="text" class="pin-role" placeholder="role" />
    <button type="button" class="pin-remove">Remove</button>
  `;
  if (preset) {
    if (preset.pin) row.querySelector(".pin-id").value = preset.pin;
    if (preset.component) row.querySelector(".pin-comp").value = preset.component;
    if (preset.role) row.querySelector(".pin-role").value = preset.role;
  }
  row.querySelector(".pin-remove").addEventListener("click", () => row.remove());
  listEl.appendChild(row);
}

function readRows(listEl) {
  return [...listEl.querySelectorAll(".pin-row")].map((row) => ({
    pin: row.querySelector(".pin-id").value,
    component: row.querySelector(".pin-comp").value,
    role: row.querySelector(".pin-role").value,
  }));
}

function refreshPinSelects() {
  const board = currentBoard();
  document.querySelectorAll(".pin-id").forEach((sel) => {
    const prev = sel.value;
    sel.innerHTML = pinOptions(board);
    if ([...sel.options].some((o) => o.value === prev)) sel.value = prev;
  });
}

function onBoardChange() {
  const board = currentBoard();
  $("#board-notes").textContent = board?.notes || "";
  const flashBtn = $("#btn-flash");
  if (board?.flashProfile) flashBtn.setAttribute("board", board.flashProfile);
  const isPi = board?.family === "raspberry-pi";
  $("#pi-fields").hidden = !isPi;
  $("#btn-deploy-pi").disabled = !isPi;
  if (board?.defaultBaud) $("#baud-select").value = String(board.defaultBaud);
  refreshPinSelects();
}

async function loadCatalog() {
  const [bRes, cRes] = await Promise.all([
    fetch(api("/api/boards")),
    fetch(api("/api/components")),
  ]);
  if (!bRes.ok) throw new Error("Cannot reach backend /api/boards — start the FastAPI server.");
  boards = (await bRes.json()).boards;
  components = (await cRes.json()).components;
  const sel = $("#board-select");
  sel.innerHTML = boards.map((b) => `<option value="${b.id}">${b.name}</option>`).join("");
  sel.value = "uno";
  $("#inputs-list").innerHTML = "";
  $("#outputs-list").innerHTML = "";
  addPinRow($("#outputs-list"), "output", { pin: "13", component: "led", role: "status" });
  onBoardChange();
}

$("#board-select").addEventListener("change", onBoardChange);
$("#btn-add-input").addEventListener("click", () => addPinRow($("#inputs-list"), "input"));
$("#btn-add-output").addEventListener("click", () => addPinRow($("#outputs-list"), "output"));

function buildConfig() {
  return {
    boardId: $("#board-select").value,
    inputs: readRows($("#inputs-list")),
    outputs: readRows($("#outputs-list")),
    intent: $("#intent").value,
  };
}

function setHexFromText(text) {
  if (hexBlobUrl) {
    URL.revokeObjectURL(hexBlobUrl);
    hexBlobUrl = null;
  }
  const blob = new Blob([text], { type: "text/plain" });
  hexBlobUrl = URL.createObjectURL(blob);
  const flashBtn = $("#btn-flash");
  flashBtn.setAttribute("hex-href", hexBlobUrl);
  const board = currentBoard();
  flashBtn.disabled = !(board?.flashProfile || $("#simulate-flash").checked);
  $("#flash-progress").textContent = "Hex ready";
}

function setEditorSource(content, language) {
  if (!editor) return;
  const model = editor.getModel();
  monaco.editor.setModelLanguage(model, language === "python" ? "python" : "cpp");
  editor.setValue(content);
}

async function runPipeline() {
  logPipe("— generate & compile —");
  $("#btn-pipeline").disabled = true;
  try {
    const res = await fetch(api("/api/pipeline"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ config: buildConfig() }),
    });
    const data = await res.json();
    lastGenerate = data.generate;
    if (data.generate?.files?.[0]) {
      setEditorSource(data.generate.files[0].content, data.generate.language);
    }
    if (!data.generate?.ok) {
      logPipe((data.generate?.errors || data.errors || ["generate failed"]).join("\n"));
      return;
    }
    logPipe("Generated " + data.generate.files.map((f) => f.path).join(", "));
    if (data.generate.notes) logPipe(data.generate.notes);
    if (data.compile) {
      logPipe(data.compile.logs || "(no compiler logs)");
      if (data.compile.mock) logPipe("Note: MOCK_COMPILE=1 — hex is not flashable.");
      if (data.compile.ok && data.compile.hex) {
        setHexFromText(data.compile.hex);
        logPipe("Compile OK — hex loaded for Web Serial flash.");
      } else {
        $("#btn-flash").disabled = true;
        logPipe("Compile failed.");
      }
    } else {
      logPipe("No compile step (Raspberry Pi artefact is Python).");
      $("#btn-flash").disabled = !$("#simulate-flash").checked;
      $("#btn-deploy-pi").disabled = false;
    }
  } catch (err) {
    logPipe(String(err));
  } finally {
    $("#btn-pipeline").disabled = false;
  }
}

$("#btn-pipeline").addEventListener("click", runPipeline);

$("#btn-clear-pipeline").addEventListener("click", () => {
  $("#pipeline-log").textContent = "";
  $("#pipeline-log-copy").textContent = "";
});

function goToMonitor(reason) {
  logPipe(reason);
  showSlide("dash");
  logSys("[System] " + reason);
}

const flashBtn = $("#btn-flash");

flashBtn.addEventListener(
  "click",
  async (e) => {
    if ($("#simulate-flash").checked) {
      e.preventDefault();
      e.stopImmediatePropagation();
      goToMonitor("Simulated flash — skipped Web Serial.");
      return;
    }
    if (!hexBlobUrl) {
      e.preventDefault();
      e.stopImmediatePropagation();
      alert("Generate & compile (or load a .hex) first.");
      return;
    }
    const board = currentBoard();
    if (!board?.flashProfile) {
      e.preventDefault();
      e.stopImmediatePropagation();
      alert("This board has no STK500v1 flash profile. Enable simulated flash or use avrdude.");
      return;
    }
    if (port) {
      logPipe("Closing serial monitor so the flasher can take the port…");
      await closePort();
    }
    logPipe("Starting flash… select the same USB port when prompted.");
    const progress = $("#flash-progress");
    const start = Date.now();
    const timer = setInterval(() => {
      const t = progress.textContent || "";
      if (t.includes("Done")) {
        clearInterval(timer);
        goToMonitor("Flash finished. Connect serial to monitor telemetry.");
      } else if (t.includes("Error") && Date.now() - start > 500) {
        clearInterval(timer);
        logPipe("Flash error.");
      }
    }, 400);
  },
  true
);

$("#hex-file").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const text = await file.text();
  setHexFromText(text);
  logPipe("Loaded hex: " + file.name);
});

$("#btn-download").addEventListener("click", () => {
  const src = editor ? editor.getValue() : lastGenerate?.files?.[0]?.content;
  if (!src) return;
  const board = currentBoard();
  const name = board?.family === "raspberry-pi" ? "app.py" : "sketch.ino";
  const blob = new Blob([src], { type: "text/plain" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
});

$("#btn-load-sample").addEventListener("click", () => {
  if (!editor) return;
  monaco.editor.setModelLanguage(editor.getModel(), "cpp");
  editor.setValue(`const int ledPin = LED_BUILTIN;

void setup() {
  pinMode(ledPin, OUTPUT);
  Serial.begin(115200);
  Serial.println("Blink sketch started");
}

void loop() {
  digitalWrite(ledPin, HIGH);
  Serial.println("LED=1");
  delay(500);
  digitalWrite(ledPin, LOW);
  Serial.println("LED=0");
  delay(500);
}
`);
});

$("#btn-deploy-pi").addEventListener("click", async () => {
  const source = editor ? editor.getValue() : "";
  if (!source) {
    alert("Generate first.");
    return;
  }
  logPipe("SSH deploy…");
  try {
    const res = await fetch(api("/api/deploy/pi"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source,
        host: $("#pi-host").value || null,
        user: $("#pi-user").value || null,
        password: $("#pi-password").value || null,
      }),
    });
    const data = await res.json();
    logPipe(data.logs || JSON.stringify(data));
    if (data.downloadHint) logPipe(data.downloadHint);
    if (data.ok) goToMonitor("Pi deploy started. Serial monitor is for Arduino USB; Pi logs are on the device (hw-deploy.log).");
  } catch (err) {
    logPipe(String(err));
  }
});

function logSys(msg) {
  appendMonitor(msg, "sys");
}

$("#btn-connect").addEventListener("click", async () => {
  if (!("serial" in navigator)) {
    alert("Web Serial API is not supported. Use Chrome, Edge or Opera on desktop.");
    return;
  }
  try {
    port = await navigator.serial.requestPort();
    const baud = parseInt($("#baud-select").value, 10);
    await port.open({ baudRate: baud });
    setStatus("Connected", "connected");
    $("#btn-connect").disabled = true;
    $("#btn-disconnect").disabled = false;
    $("#serial-input").disabled = false;
    $("#btn-send").disabled = false;
    logSys(`[System] Port opened @ ${baud} baud`);
    startReading();
  } catch (err) {
    console.error(err);
    setStatus("Error", "error");
    logSys(`[Error] ${err.message}`);
  }
});

$("#btn-disconnect").addEventListener("click", async () => {
  await closePort();
});

async function closePort() {
  keepReading = false;
  try {
    if (reader) {
      await reader.cancel();
      reader = null;
    }
    if (port) {
      await port.close();
      port = null;
    }
  } catch (e) {
    console.warn(e);
  }
  setStatus("Disconnected");
  $("#btn-connect").disabled = false;
  $("#btn-disconnect").disabled = true;
  $("#serial-input").disabled = true;
  $("#btn-send").disabled = true;
  logSys("[System] Port closed");
}

async function startReading() {
  keepReading = true;
  const decoder = new TextDecoder();
  try {
    while (port && port.readable && keepReading) {
      reader = port.readable.getReader();
      try {
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          appendMonitor(decoder.decode(value), "out");
        }
      } catch (err) {
        if (keepReading) logSys(`[Read error] ${err.message}`);
      } finally {
        reader.releaseLock();
        reader = null;
      }
    }
  } catch (err) {
    console.error(err);
  }
}

async function sendSerial() {
  const input = $("#serial-input");
  let data = input.value;
  if ($("#send-newline").checked) data += "\n";
  if (!port || !port.writable) return;
  const writer = port.writable.getWriter();
  await writer.write(new TextEncoder().encode(data));
  writer.releaseLock();
  appendMonitor(data, "in");
  input.value = "";
}

$("#btn-send").addEventListener("click", sendSerial);
$("#serial-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    sendSerial();
  }
});

$("#btn-clear-monitor").addEventListener("click", () => {
  $("#serial-output").innerHTML = "";
  telemetry = {};
  renderChips();
});

$("#baud-select").addEventListener("change", async () => {
  if (!port) return;
  logSys("[System] Baud rate change requires reconnect. Disconnecting…");
  await closePort();
});

loadCatalog().catch((err) => {
  logPipe(String(err));
});
