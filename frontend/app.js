/**
 * Arduino Uno Web IDE
 * - Monaco editor for sketches
 * - Web Serial based flashing (via arduino-web-uploader / STK500v1 declarative API)
 * - Live serial monitor
 *
 * Requirements: Chrome / Edge / Opera, HTTPS or localhost
 */

let editor = null;
let port = null;
let reader = null;
let keepReading = false;
let hexBlobUrl = null; // blob: URL of the loaded .hex

const $ = (sel) => document.querySelector(sel);

// ---------- Monaco Editor ----------
require.config({
  paths: { vs: "https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.45.0/min/vs" },
});

require(["vs/editor/editor.main"], () => {
  editor = monaco.editor.create(document.getElementById("editor"), {
    value: getBlinkSample(),
    language: "cpp",
    theme: "vs-dark",
    automaticLayout: true,
    minimap: { enabled: false },
    fontSize: 14,
    fontFamily: "'JetBrains Mono', 'Fira Code', Consolas, monospace",
    scrollBeyondLastLine: false,
    padding: { top: 12 },
  });
});

function getBlinkSample() {
  return `// Blink for Arduino Uno
// Compile this in the Arduino IDE (or arduino-cli) for board "Arduino Uno"
// then use Sketch → Export compiled Binary to get the .hex file.

const int ledPin = LED_BUILTIN;   // pin 13 on Uno

void setup() {
  pinMode(ledPin, OUTPUT);
  Serial.begin(115200);
  while (!Serial) { ; }           // wait for serial (optional on Uno)
  Serial.println("Blink sketch started");
}

void loop() {
  digitalWrite(ledPin, HIGH);
  Serial.println("LED ON");
  delay(500);
  digitalWrite(ledPin, LOW);
  Serial.println("LED OFF");
  delay(500);
}
`;
}

// ---------- UI helpers ----------
function setStatus(text, cls = "") {
  const el = $("#connection-status");
  el.textContent = text;
  el.className = "status " + cls;
}

function logSys(msg) {
  appendMonitor(msg, "sys");
}

function appendMonitor(text, type = "out") {
  const out = $("#serial-output");
  const span = document.createElement("span");
  span.className = "line-" + type;
  span.textContent = text + (text.endsWith("\n") ? "" : "\n");
  out.appendChild(span);
  if ($("#auto-scroll").checked) {
    out.scrollTop = out.scrollHeight;
  }
}

// ---------- Connect / Disconnect (for Serial Monitor only) ----------
$("#btn-connect").addEventListener("click", async () => {
  if (!("serial" in navigator)) {
    alert("Web Serial API is not supported in this browser.\nUse Chrome, Edge or Opera on desktop.");
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

// ---------- Serial reading loop ----------
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
          const text = decoder.decode(value);
          appendMonitor(text, "out");
        }
      } catch (err) {
        if (keepReading) {
          console.error(err);
          logSys(`[Read error] ${err.message}`);
        }
      } finally {
        reader.releaseLock();
        reader = null;
      }
    }
  } catch (err) {
    console.error(err);
  }
}

// ---------- Send data ----------
async function sendSerial() {
  const input = $("#serial-input");
  let data = input.value;
  if ($("#send-newline").checked) data += "\n";
  if (!port || !port.writable) return;

  const writer = port.writable.getWriter();
  const encoder = new TextEncoder();
  await writer.write(encoder.encode(data));
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
});

// ---------- Hex file loading + wire up declarative flash button ----------
const flashBtn = $("#btn-flash");

$("#hex-file").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;

  // Revoke previous blob URL if any
  if (hexBlobUrl) {
    URL.revokeObjectURL(hexBlobUrl);
    hexBlobUrl = null;
  }

  const text = await file.text();
  const blob = new Blob([text], { type: "text/plain" });
  hexBlobUrl = URL.createObjectURL(blob);

  // Update the attributes the library reads on click
  flashBtn.setAttribute("hex-href", hexBlobUrl);
  flashBtn.disabled = false;

  logSys(`[System] Loaded hex: ${file.name} (${text.length} chars)`);
  $("#flash-progress").textContent = "Hex ready";
});

// Keep the board attribute in sync with the selector
$("#board-select").addEventListener("change", () => {
  flashBtn.setAttribute("board", $("#board-select").value);
});

// When the user clicks Flash, the library (arduino-uploader attribute)
// will open its own serial port, program the board, then close it.
// We must release our own port first so the library can claim it.
flashBtn.addEventListener("click", async (e) => {
  if (!hexBlobUrl) {
    e.preventDefault();
    e.stopPropagation();
    alert("Please load a .hex file first.");
    return;
  }

  // Close our monitor connection so the uploader can open the port exclusively
  if (port) {
    logSys("[System] Closing serial monitor so the flasher can take the port…");
    await closePort();
  }

  // Let the library's own click handler (attached on DOMContentLoaded) run.
  // After flash finishes the library shows "Done!" or "Error!" in .upload-progress.
  // User must click Connect again for the serial monitor.
  logSys("[System] Starting flash… (select the same port when prompted)");
});

// ---------- Editor helpers ----------
$("#btn-load-sample").addEventListener("click", () => {
  if (editor) editor.setValue(getBlinkSample());
});

$("#btn-download-ino").addEventListener("click", () => {
  if (!editor) return;
  const code = editor.getValue();
  const blob = new Blob([code], { type: "text/plain" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "sketch.ino";
  a.click();
  URL.revokeObjectURL(a.href);
});

// ---------- Baud change while connected ----------
$("#baud-select").addEventListener("change", async () => {
  if (!port) return;
  logSys("[System] Baud rate change requires reconnect. Disconnecting…");
  await closePort();
});
