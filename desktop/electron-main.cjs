const { app, BrowserWindow } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");

const DEV_ROOT = path.resolve(__dirname, "..");
const ROOT = app.isPackaged ? path.dirname(process.execPath) : DEV_ROOT;
const DEV_PYTHON = path.join(ROOT, ".venv", "Scripts", "python.exe");
const DEV_API = path.join(ROOT, "desktop", "api_server.py");
const PACKAGED_API = path.join(process.resourcesPath, "backend", "FridayAPI", "FridayAPI.exe");

let api = null;
let ownsApi = false;
let win = null;

async function apiAlreadyRunning() {
  try {
    const response = await fetch("http://127.0.0.1:8080/api/v1/health");
    return response.ok;
  } catch {
    return false;
  }
}

function startApi() {
  const executable = app.isPackaged ? PACKAGED_API : DEV_PYTHON;
  const args = app.isPackaged ? [] : [DEV_API];
  const cwd = app.isPackaged ? path.dirname(PACKAGED_API) : DEV_ROOT;

  if (!fs.existsSync(executable)) {
    throw new Error(`Friday API runtime not found: ${executable}`);
  }

  api = spawn(executable, args, {
    cwd,
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"],
    detached: true,
    shell: false,
  });
  ownsApi = true;

  api.stdout?.on("data", data => console.log("Friday API:", data.toString().trim()));
  api.stderr?.on("data", data => console.error("Friday API STDERR:", data.toString().trim()));
  api.on("error", error => console.error("Friday API error:", error));
}

async function ensureApi() {
  if (await apiAlreadyRunning()) return;

  startApi();
  const started = Date.now();
  while (Date.now() - started < 60000) {
    if (await apiAlreadyRunning()) return;
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  throw new Error("Friday API did not become ready on port 8080.");
}

async function createWindow() {
  await ensureApi();

  win = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 900,
    minHeight: 600,
    title: "Friday",
    backgroundColor: "#111111",
    webPreferences: { contextIsolation: true, nodeIntegration: false },
  });

  if (app.isPackaged) {
    await win.loadFile(path.join(app.getAppPath(), "dist", "index.html"));
  } else {
    await win.loadURL("http://127.0.0.1:5173/");
  }
}

function cleanup() {
  if (ownsApi && api && !api.killed) {
    try { api.kill(); } catch {}
  }
}

app.whenReady().then(async () => {
  try {
    await createWindow();
  } catch (error) {
    console.error("Friday startup failed:", error);
    cleanup();
    app.quit();
  }
});

app.on("before-quit", cleanup);
app.on("window-all-closed", () => app.quit());
