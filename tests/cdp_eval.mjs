// Open a URL in headless Chromium and poll a JS expression until it returns a truthy string.
//   node --experimental-websocket cdp_eval.mjs URL 'EXPR' [timeout_s] [pre-expr run once after load]
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
const [url, expr, tmo = "40", pre = ""] = process.argv.slice(2);
const port = 9300 + Math.floor(Math.random() * 500);
const prof = mkdtempSync(join(tmpdir(), "cdp-"));
process.on("exit", () => { for (let i = 0; i < 50; i++) { try { rmSync(prof, { recursive: true, force: true }); break; } catch {} } });
const chrome = spawn("chromium", ["--headless", "--disable-gpu", "--no-sandbox", `--remote-debugging-port=${port}`,
  `--user-data-dir=${prof}`, "about:blank"], { stdio: "ignore" });
const sleep = ms => new Promise(r => setTimeout(r, ms));
let targets;
for (let i = 0; i < 50; i++) { try { targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); break; } catch { await sleep(200); } }
const ws = new WebSocket(targets.find(t => t.type === "page").webSocketDebuggerUrl);
await new Promise(r => ws.onopen = r);
let id = 0; const pending = new Map();
ws.onmessage = m => { const d = JSON.parse(m.data); if (pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id); } };
const send = (method, params = {}) => new Promise(r => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const evaluate = async e => (await send("Runtime.evaluate", { expression: e, awaitPromise: true, returnByValue: true })).result?.result?.value;
await send("Page.navigate", { url });
await sleep(1000);
if (pre) await evaluate(pre);
const end = Date.now() + Number(tmo) * 1000; let v;
while (Date.now() < end) { v = await evaluate(expr); if (v) break; await sleep(500); }
console.log(v || "TIMEOUT");
const exited = new Promise(r => chrome.once("exit", r));
chrome.kill(); await exited; process.exit(v ? 0 : 1);
