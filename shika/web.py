"""Web：上传一张名片，看着字段自己确认一遍再入库。

识别完不直接存——先把「读到的原文行」和「填进去的字段」一起摆出来。
你能看见它是从哪一行抠出来的，有问题当场就知道。
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import contacts, reader, store

MAX_BODY = 12 * 1024 * 1024
UPLOAD_DIR = os.path.join("data", "uploads")

PAGE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>识卡 · 名片进通讯录</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#0b0f14;color:#c9d1d9;font:15px/1.65 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
header{padding:16px 24px;border-bottom:1px solid #21262d;display:flex;gap:12px;align-items:baseline}
h1{margin:0;font-size:18px;color:#79c0ff}
.sub{color:#8b949e;font-size:13px}
main{display:grid;grid-template-columns:minmax(320px,380px) 1fr;min-height:calc(100vh - 60px)}
aside{border-right:1px solid #21262d;padding:16px}
section{padding:18px 24px}
h2{font-size:15px;margin:20px 0 8px}
.drop{border:1px dashed #30363d;border-radius:10px;padding:22px;text-align:center;color:#8b949e;cursor:pointer}
.drop:hover{border-color:#79c0ff;color:#c9d1d9}
button{background:#1f6feb;color:#fff;border:0;border-radius:6px;padding:8px 14px;font:14px inherit;cursor:pointer}
button.ghost{background:#21262d;color:#c9d1d9}
button:disabled{opacity:.45;cursor:default}
.card{border:1px solid #21262d;border-radius:8px;padding:12px;margin-bottom:10px}
.k{color:#8b949e;font-size:13px}
.row{display:flex;justify-content:space-between;gap:12px;padding:5px 0;border-bottom:1px solid #161b22}
.row span:last-child{color:#c9d1d9}
.bad{color:#ff7b72}
.ok{color:#7ee787}
pre{background:#161b22;border-radius:8px;padding:10px;overflow:auto;font-size:12.5px;color:#8b949e;margin:6px 0}
img.prev{max-width:100%;border-radius:8px;border:1px solid #21262d}
.item{padding:8px 10px;border-radius:6px;cursor:pointer}
.item:hover{background:#161b22}
</style></head><body>
<header><h1>识卡</h1><span class="sub">拍一张名片，字段进通讯录——每个字段都能追到卡片上的那一行</span></header>
<main>
<aside>
  <h2>新名片</h2>
  <div class="drop" id="drop">点这里选图，或把名片照片拖进来</div>
  <input type="file" id="file" accept="image/*" style="display:none">
  <div id="prev"></div>
  <h2>通讯录 <span class="k" id="count"></span></h2>
  <div id="list"></div>
  <h2>导出</h2>
  <button class="ghost" id="exp-csv">CSV</button>
  <button class="ghost" id="exp-vcf">vCard</button>
</aside>
<section>
  <div style="display:flex;gap:8px;align-items:center;margin-bottom:14px">
    <button id="save" disabled>存进通讯录</button>
    <span class="k" id="status">先选一张名片</span>
  </div>
  <div id="out"><p class="k">读完之后，左边会出来这张卡上的每一行字，以及每个字段来自哪一行。</p></div>
</section>
</main>
<script>
const $ = s => document.querySelector(s);
const esc = s => String(s==null?'':s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
let current = null;

$('#drop').onclick = () => $('#file').click();
$('#drop').ondragover = e => { e.preventDefault(); };
$('#drop').ondrop = e => { e.preventDefault(); if(e.dataTransfer.files[0]) upload(e.dataTransfer.files[0]); };
$('#file').onchange = e => { if(e.target.files[0]) upload(e.target.files[0]); };

function upload(file){
  const fr = new FileReader();
  fr.onload = async () => {
    $('#status').textContent = '模型在读…十几秒';
    $('#save').disabled = true;
    $('#prev').innerHTML = `<img class="prev" src="${fr.result}">`;
    const b64 = String(fr.result).split(',')[1];
    const r = await fetch('/api/read', {method:'POST', body: JSON.stringify({image_b64: b64, filename: file.name})});
    const d = await r.json();
    $('#status').textContent = '';
    if(d.error){ $('#out').innerHTML = `<p class="bad">✗ ${esc(d.error)}</p>`; return; }
    current = d;
    render(d);
    $('#save').disabled = false;
  };
  fr.readAsDataURL(file);
}

function render(d){
  const c = d.card, p = d.problems || [];
  let html = `<img class="prev" src="${d.image_url || ''}" style="max-height:240px">`;
  html += `<h2>${esc(c.name || '没读到姓名')} ${c.company? '· '+esc(c.company):''}</h2>`;
  const rows = [['职位','title'],['手机','mobile'],['座机','tel'],['邮箱','email'],['地址','address'],['备注','note']];
  html += rows.map(([label,key]) => c[key]
     ? `<div class="row"><span class="k">${label}</span><span>${esc(c[key])}</span></div>` : '').join('');
  html += `<p class="k">把握：${esc(d.confidence || '没给')}${d.note? ' · '+esc(d.note):''}</p>`;
  if(p.length) html += `<div class="card"><b class="bad">${p.length} 个问题</b>` +
     p.map(x=>`<div class="k">${esc(x)}</div>`).join('') + `</div>`;
  else html += `<p class="ok">字段都对得上，没发现问题。</p>`;
  html += `<h2>卡片上读到的字</h2><pre>${esc((d.lines||[]).map((l,i)=>i+': '+l).join('\\n'))}</pre>`;
  $('#out').innerHTML = html;
}

$('#save').onclick = async () => {
  if(!current) return;
  const r = await fetch('/api/save', {method:'POST', body: JSON.stringify({card: current.card,
     problems: current.problems, lines: current.lines, confidence: current.confidence,
     note: current.note, image: current.image_name})});
  const d = await r.json();
  if(d.error){ alert(d.error); return; }
  $('#status').textContent = d.created ? '已新建联系人' : '并进了已有的联系人';
  loadList();
};

async function loadList(){
  const r = await fetch('/api/contacts');
  const items = (await r.json()).items;
  $('#count').textContent = items.length ? `${items.length} 人` : '';
  $('#list').innerHTML = items.map(m => `<div class="item" data-id="${m.id}">
    <b>${esc(m.name || '没名字')}</b> <span class="k">${esc(m.company)}</span>
    <div class="k">${esc(m.mobile || m.tel || m.email || '没有联系方式')}</div></div>`).join('')
    || '<p class="k">还没有</p>';
  document.querySelectorAll('.item').forEach(el => el.onclick = async () => {
    const r = await fetch('/api/contact?id=' + el.dataset.id);
    const d = await r.json();
    if(d.contact) render({card: d.contact, problems: [], lines: [], confidence: '', image_url: ''});
  });
}

$('#exp-csv').onclick = () => location.href = '/api/export?fmt=csv';
$('#exp-vcf').onclick = () => location.href = '/api/export?fmt=vcf';
loadList();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    conn = None

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        if parsed.path == "/":
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
            return
        if parsed.path == "/api/contacts":
            rows = store.list_contacts(self.conn)
            self._json({"items": [{k: r[k] for k in ("id", "name", "company", "mobile", "tel", "email")}
                                  for r in rows]})
            return
        if parsed.path == "/api/contact":
            try:
                cid = int((qs.get("id") or ["0"])[0])
            except ValueError:
                self._json({"error": "id 不合法"}, 400)
                return
            self._json({"contact": store.get_contact(self.conn, cid),
                        "cards": store.cards_of(self.conn, cid)})
            return
        if parsed.path == "/api/export":
            fmt = (qs.get("fmt") or ["vcf"])[0]
            rows = store.list_contacts(self.conn)
            if fmt == "csv":
                header, data = contacts.to_csv_rows(rows)
                lines = [",".join(header)] + [",".join('"' + str(x).replace('"', '""') + '"' for x in r)
                                              for r in data]
                body = "\ufeff" + "\r\n".join(lines) + "\r\n"
                self._send(200, body.encode("utf-8"), "text/csv; charset=utf-8")
            else:
                body = "\r\n".join(contacts.to_vcard(r) for r in rows) + "\r\n"
                self._send(200, body.encode("utf-8"), "text/vcard; charset=utf-8")
            return
        if parsed.path.startswith("/uploads/"):
            name = os.path.basename(parsed.path)
            path = os.path.join(UPLOAD_DIR, name)
            if not os.path.isfile(path):
                self._json({"error": "没有这张图"}, 404)
                return
            ext = os.path.splitext(name)[1].lower()
            ctype = {".png": "image/png", ".webp": "image/webp"}.get(ext, "image/jpeg")
            with open(path, "rb") as f:
                self._send(200, f.read(), ctype)
            return
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            self._json({"error": "图太大了，超过 12MB"}, 413)
            return
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._json({"error": "请求体不是合法 JSON"}, 400)
            return

        if parsed.path == "/api/read":
            image_b64 = body.get("image_b64") or ""
            if not image_b64:
                self._json({"error": "没有图片"}, 400)
                return
            try:
                raw = base64.b64decode(image_b64, validate=True)
            except (ValueError, TypeError):
                self._json({"error": "图片 base64 解不开"}, 400)
                return
            if len(raw) < 24:
                self._json({"error": "图片内容为空或太短"}, 400)
                return

            os.makedirs(UPLOAD_DIR, exist_ok=True)
            filename = os.path.basename(body.get("filename") or "card.jpg")
            ext = os.path.splitext(filename)[1].lower() or ".jpg"
            if ext not in (".jpg", ".jpeg", ".png", ".webp"):
                ext = ".jpg"
            digest = hashlib.sha256(raw).hexdigest()[:16]
            path = os.path.join(UPLOAD_DIR, f"{digest}{ext}")
            with open(path, "wb") as f:
                f.write(raw)

            result = reader.read_card(path)
            if result["error"]:
                self._json({"error": result["error"]}, 502)
                return
            card, problems = reader.to_entry(result)
            self._json({"card": card, "problems": problems, "lines": result["lines"],
                        "confidence": result["confidence"], "note": result["note"],
                        "image_url": "/uploads/" + os.path.basename(path),
                        "image_name": os.path.basename(path)})
            return

        if parsed.path == "/api/save":
            card = body.get("card") or {}
            if not isinstance(card, dict) or not (card.get("name") or card.get("mobile")
                                                 or card.get("email")):
                self._json({"error": "姓名和联系方式不能都是空的"}, 400)
                return
            saved = store.save_card(self.conn, contacts.normalize(card),
                                    image=body.get("image") or "",
                                    lines=body.get("lines") or [],
                                    confidence=body.get("confidence") or "",
                                    note=body.get("note") or "",
                                    problems=body.get("problems") or [])
            self._json({"id": saved["id"], "created": saved.get("created", True)})
            return

        self._json({"error": "not found"}, 404)


def make_server(conn, host: str = "127.0.0.1", port: int = 8773) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"conn": conn})
    return ThreadingHTTPServer((host, port), handler)


def serve(conn, host: str = "127.0.0.1", port: int = 8773):
    httpd = make_server(conn, host, port)
    print(f"识卡已起：http://{host}:{port}  （Ctrl+C 退出）")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n再见。")
    finally:
        httpd.server_close()
