// Save a page as a PDF that looks like the site (backgrounds printed), with headless Chromium.
//   node --experimental-websocket tests/cdp_pdf.mjs URL OUT.pdf [js to run before printing]
// e.g. to open the collapsed year blocks of a profile:
//   "document.querySelectorAll('details.profile-year').forEach(d => d.open = true)"
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
const [url, out, pre = ""] = process.argv.slice(2);
const port = 9300 + Math.floor(Math.random() * 500);
const prof = mkdtempSync(join(tmpdir(), "cdp-"));
const chrome = spawn("chromium", ["--headless", "--disable-gpu", "--no-sandbox",
  `--remote-debugging-port=${port}`, `--user-data-dir=${prof}`, "about:blank"], { stdio: "ignore" });
const sleep = ms => new Promise(r => setTimeout(r, ms));
let targets;
for (let i = 0; i < 50; i++) { try { targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); break; } catch { await sleep(200); } }
const ws = new WebSocket(targets.find(t => t.type === "page").webSocketDebuggerUrl);
await new Promise(r => ws.onopen = r);
let id = 0; const pending = new Map();
ws.onmessage = m => { const d = JSON.parse(m.data); if (pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id); } };
const send = (method, params = {}) => new Promise(r => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
await send("Emulation.setDeviceMetricsOverride", { width: 1100, height: 1400, deviceScaleFactor: 1, mobile: false });
await send("Emulation.setEmulatedMedia", { media: "screen" });
await send("Page.navigate", { url });
await sleep(3000);
if (pre) await send("Runtime.evaluate", { expression: pre });
await send("Runtime.evaluate", { expression: "document.querySelectorAll('img[loading=lazy]').forEach(i => i.loading = 'eager')" });
await sleep(2500);
const pdf = await send("Page.printToPDF", { printBackground: true, paperWidth: 8.27, paperHeight: 11.69,
  marginTop: 0.3, marginBottom: 0.3, marginLeft: 0.3, marginRight: 0.3, scale: 0.8 });
writeFileSync(out, Buffer.from(pdf.result.data, "base64"));
const exited = new Promise(r => chrome.once("exit", r));
chrome.kill(); await exited;
for (let i = 0; i < 20; i++) { try { rmSync(prof, { recursive: true, force: true }); break; } catch { await sleep(200); } }
process.exit(0);
