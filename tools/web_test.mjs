// Opens the page in headless Chrome, waits for Jw_cad to come up, draws a
// line with two clicks, and writes screenshots to tmp/.
//   node tools/web_test.mjs
// Serves the repository root with the COOP/COEP headers itself (coi-sw.js is
// what does that on GitHub Pages).  CHROME=... picks the browser.
import http from 'http';
import fs from 'fs';
import path from 'path';
import os from 'os';
import cp from 'child_process';

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Z]:)/, '$1')), '..');
const chrome = process.env.CHROME || ['C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', '/usr/bin/google-chrome'].find((p) => fs.existsSync(p));
if (!chrome) { console.log('SKIP no Chrome or Edge'); process.exit(0); }
const OUT = path.join(root, 'tmp');
fs.mkdirSync(OUT, {recursive: true});
const PORT = process.env.CDP_PORT || '9344';
const types = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.wasm': 'application/wasm', '.data': 'application/octet-stream'};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let fails = 0;
const check = (c, m) => { console.log((c ? 'ok   ' : 'BAD  ') + m); if (!c) fails++; };

const server = http.createServer((req, res) => {
  let p = decodeURIComponent(req.url.split('?')[0]);
  if (p === '/') p = '/index.html';
  const f = path.join(root, p);
  if (!f.startsWith(root) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, {'content-type': types[path.extname(f)] || 'application/octet-stream',
    'Cross-Origin-Opener-Policy': 'same-origin', 'Cross-Origin-Embedder-Policy': 'require-corp'});
  fs.createReadStream(f).pipe(res);
});

await new Promise((r) => server.listen(0, '127.0.0.1', r));
const port = server.address().port;
const prof = fs.mkdtempSync(path.join(os.tmpdir(), 'jwemu-chrome-'));
const proc = cp.spawn(chrome, ['--headless=new', '--remote-debugging-port=' + PORT, '--user-data-dir=' + prof,
  '--no-first-run', '--disable-gpu', '--window-size=1400,1500', 'about:blank'], {stdio: 'ignore'});
let targets = [];
for (let i = 0; i < 50; i++) {
  try { targets = await (await fetch('http://127.0.0.1:' + PORT + '/json')).json(); if (targets.length) break; } catch (e) {}
  await sleep(200);
}
const pageT = targets.find((t) => t.type === 'page');
const ws = new WebSocket(pageT.webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));
let id = 0;
const waiting = new Map();
const logs = [];
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data);
  if (m.method === 'Runtime.consoleAPICalled') logs.push(m.params.args.map((a) => a.value).join(' '));
  if (m.method === 'Runtime.exceptionThrown') logs.push('EXC ' + JSON.stringify(m.params.exceptionDetails.text));
  if (m.id && waiting.has(m.id)) { waiting.get(m.id)(m); waiting.delete(m.id); }
};
const send = (method, params = {}) => new Promise((r) => { const n = ++id; waiting.set(n, r); ws.send(JSON.stringify({id: n, method, params})); });
const ev = async (expr) => (await send('Runtime.evaluate', {expression: expr, returnByValue: true})).result.result.value;
const shot = async (name) => {
  const d = (await send('Page.captureScreenshot', {format: 'png'})).result.data;
  fs.writeFileSync(path.join(OUT, name), Buffer.from(d, 'base64'));
};
const mouse = (type, x, y) => send('Input.dispatchMouseEvent', {type, x, y, button: 'left', buttons: type === 'mouseReleased' ? 0 : 1, clickCount: 1});

try {
  await send('Page.enable');
  await send('Runtime.enable');
  await send('Emulation.setDeviceMetricsOverride', {width: 1400, height: 1500, deviceScaleFactor: 1, mobile: false});
  await send('Page.navigate', {url: process.env.URL || ('http://127.0.0.1:' + port + '/')});
  // On GitHub Pages the first load installs coi-sw.js and reloads once.
  let isolated = false;
  for (let i = 0; i < 40 && !isolated; i++) { await sleep(500); isolated = !!(await ev('window.crossOriginIsolated')); }
  check(isolated, 'cross-origin isolated');
  await sleep(10000);
  await shot('web_start.png');
  console.log('status: ' + await ev("document.getElementById('status').textContent"));
  // Where the canvas is, and how screen pixels map to page pixels.
  const rc = await ev("(() => { const b = document.getElementById('screen').getBoundingClientRect(); return [b.left, b.top, b.width / 1280]; })()");
  const at = (x, y) => [rc[0] + x * rc[2], rc[1] + y * rc[2]];
  // Two clicks in the drawing area: a line.
  const [x1, y1] = at(300, 300), [x2, y2] = at(600, 400);
  await send('Input.dispatchMouseEvent', {type: 'mouseMoved', x: x1, y: y1});
  await mouse('mousePressed', x1, y1); await mouse('mouseReleased', x1, y1);
  await sleep(300);
  await send('Input.dispatchMouseEvent', {type: 'mouseMoved', x: x2, y: y2});
  await mouse('mousePressed', x2, y2); await mouse('mouseReleased', x2, y2);
  await sleep(1500);
  await shot('web_line.png');
  // A file through the panel's file input, then look for it in the listing.
  const doc = (await send('DOM.getDocument')).result.root.nodeId;
  const inp = (await send('DOM.querySelector', {nodeId: doc, selector: '#upload'})).result.nodeId;
  await send('DOM.setFileInputFiles', {nodeId: inp, files: [path.join(root, 'tests', 'WINDEPTH.DAT')]});
  await sleep(4000);
  const listed = await ev("[...document.querySelectorAll('#files td.name')].map((t) => t.textContent).join(',')");
  check(listed.includes('WINDEPTH.DAT'), 'an uploaded file appears in the panel');
  check(await ev("(() => { const f = document.getElementById('filelist'); return f.scrollHeight > f.clientHeight + 50 && f.clientHeight < 400; })()"),
        'the file list scrolls inside the panel');
  console.log('note: ' + await ev("document.getElementById('note').textContent"));
  // Jw_cad's own 開く, a line, then 上書: the saved drawing should come back
  // to the panel marked as the user's (kept in IndexedDB).
  const click = async (sx, sy, n = 1) => {
    const [x, y] = at(sx, sy);
    await send('Input.dispatchMouseEvent', {type: 'mouseMoved', x, y});
    for (let i = 1; i <= n; i++) {
      await send('Input.dispatchMouseEvent', {type: 'mousePressed', x, y, button: 'left', buttons: 1, clickCount: i});
      await send('Input.dispatchMouseEvent', {type: 'mouseReleased', x, y, button: 'left', buttons: 0, clickCount: i});
    }
  };
  await click(940, 146); await sleep(4000);
  await click(410, 330, 2); await sleep(3000);
  await click(639, 448); await sleep(4000);  // いいえ to keeping the earlier line
  await click(85, 124); await sleep(300);
  await click(200, 200); await sleep(300);
  await click(800, 250); await sleep(500);
  await click(940, 168); await sleep(6000);
  await shot('web_save.png');
  const users = await ev("[...document.querySelectorAll('#files tr.user td.name')].map((t) => t.textContent).join(',')");
  check(users.includes('木造平面例.jww'), 'a drawing saved by Jw_cad is marked in the panel');
  // 文字: the input box's font list drops right under its combo box.
  await click(85, 192); await sleep(2500);
  await click(700, 154); await sleep(1500);
  await shot('web_fontlist.png');
  await send('Input.dispatchKeyEvent', {type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27});
  await send('Input.dispatchKeyEvent', {type: 'keyUp', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27});
  await sleep(500);
  await click(85, 121); await sleep(1000);  // back to ／
  // 印刷: the printer dialog's OK, then 印刷(L) in print mode.  The PDF should
  // arrive as a download.
  const dl = path.join(OUT, 'downloads');
  fs.rmSync(dl, {recursive: true, force: true});
  fs.mkdirSync(dl, {recursive: true});
  await send('Browser.setDownloadBehavior', {behavior: 'allow', downloadPath: dl});
  await click(940, 216); await sleep(2500);
  await click(660, 481); await sleep(2500);
  await click(66, 89);
  let pdfs = [];
  for (let i = 0; i < 60 && !pdfs.length; i++) {
    await sleep(1000);
    pdfs = fs.readdirSync(dl).filter((f) => f.endsWith('.pdf'));
  }
  await shot('web_print.png');
  check(pdfs.length === 1 && fs.readFileSync(path.join(dl, pdfs[0])).subarray(0, 5).toString() === '%PDF-',
        'printing downloads a PDF (' + pdfs.join(',') + ')');
  console.log('note: ' + await ev("document.getElementById('note').textContent"));
  // Other formats: ファイル → DXF形式で保存 / SFC形式で保存, 新規, OK.  The SFC
  // goes through common_lib.dll, a guest DLL loaded from the virtual C:.
  for (const [y, ext] of [[255, 'dxf'], [308, 'sfc']]) {
    await click(66, 60); await sleep(800);
    await click(95, y); await sleep(4000);
    await click(412, 131); await sleep(2000);
    await click(295, 290);
    let names = '';
    for (let i = 0; i < 60 && !names.includes('木造平面例.' + ext); i++) {
      await sleep(1000);
      names = await ev("[...document.querySelectorAll('#files tr.user td.name')].map((t) => t.textContent).join(',')");
    }
    await shot('web_save_' + ext + '.png');
    check(names.includes('木造平面例.' + ext), 'saving as ' + ext.toUpperCase() + ' puts 木造平面例.' + ext + ' in the panel');
  }
  console.log(logs.slice(-15).join('\n'));
} finally {
  ws.close();
  proc.kill();
  server.close();
}
process.exit(fails ? 1 : 0);
