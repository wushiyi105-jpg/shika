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
<title>识卡 · 半小时清完一叠名片</title>
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

:root{--maxw:1060px;--bg:#f2ebdf;--card:#fffdf8;--ink:#28231d;--text:#28231d;--dim:#71675b;--line:#d8ccbb;--accent:#9b6234;--muted:#71675b}
.wrap{max-width:1060px}
body{background:#f2ebdf;color:#28231d;font-family:"PingFang SC","Microsoft YaHei",sans-serif}
h1{color:#28231d}
header{max-width:1060px;margin:0 auto}
input,textarea,select{background:#fff;color:#28231d;border-color:#d8ccbb;border-radius:2px}
button:not(.ghost):not(.tab){background:#9b6234;color:#fff;border-radius:2px}
button.ghost{background:transparent!important;color:#9b6234!important;border:1px solid #d8ccbb!important}
h2,h3{color:#9b6234}
pre{background:#fafaf6;color:#28231d;border-color:#d8ccbb}
.item,.card{border-color:#d8ccbb;background:#fffdf8}
.k,.empty,.hint{color:#71675b}

h1{font-size:clamp(31px,5vw,39px);line-height:1.26}
.prod{display:block;font-size:11px;line-height:1.4;letter-spacing:.18em;font-weight:650;margin-bottom:8px;opacity:.72}
.lede,.sub{max-width:62ch;line-height:1.75}
.route{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1px;margin:16px auto 20px;border:1px solid var(--line);background:var(--line);max-width:var(--maxw)}
.route span{padding:11px 13px;background:var(--card);font-size:12px;line-height:1.5}
.route b{display:block;font-size:10px;letter-spacing:.1em;margin-bottom:3px;opacity:.66}
button{min-height:46px}
input,select{min-height:44px}
pre{white-space:pre-wrap}
@media(max-width:680px){
  .wrap{padding:20px 16px 56px}
  .route{grid-template-columns:1fr}
  h1{font-size:30px!important}
  .row>div{min-width:100%!important}
  button{width:100%}
}

body{background:#f2ebdf;color:#28231d}
header{display:block!important;max-width:1060px;margin:0 auto;padding:24px 20px 0;background:transparent;border:0}
header h1{color:#28231d;font-size:38px;line-height:1.24;letter-spacing:-.02em}
header .sub{display:block;color:#71675b;font-size:14px;margin-top:6px}
main{max-width:1060px;margin:0 auto;background:#fffdf8;border-left:1px solid #d8ccbb;border-right:1px solid #d8ccbb;grid-template-columns:350px 1fr;min-height:calc(100vh - 150px)}
aside{background:#f8f2e8;border-right:1px solid #d8ccbb}
section{background:#fffdf8}
input,textarea,select{background:#fff;color:#28231d;border-color:#d3c5b2;border-radius:2px}
input:focus,textarea:focus,select:focus{border-color:#9b6234;box-shadow:0 0 0 2px #eadfce}
button{background:#9b6234;color:#fff;border-radius:2px}
button:hover{background:#84522a}
.drop{border:1px dashed #b89a75;background:#fff;color:#71675b;border-radius:2px}
.drop:hover{border-color:#9b6234;color:#28231d}
h2{color:#7a4b26;font-size:14px;letter-spacing:.06em}
.item,.card{border-color:#d8ccbb;background:#fff}
.empty,.k{color:#71675b}


/* mobile-32 */
input[type=text],input[type=number],input[type=email]{background:#fff;color:#28231d;border-color:#d8ccbb}

@media(max-width:760px){
  main{grid-template-columns:1fr!important}
  aside{border-right:0!important;border-bottom:1px solid #d8ccbb;width:auto!important}
  section{padding:16px!important}
  .row{flex-wrap:wrap!important}
  .row>div{min-width:100%!important}
  h1{font-size:30px!important}
  .route{grid-template-columns:1fr!important}
  button{min-height:48px}
  pre{overflow-x:auto}
}

/* mobile-height */
@media(max-width:760px){main{min-height:auto!important}aside{min-height:0!important}}

/* mobile-sticky-cta */
.mobile-cta{display:none}
@media(max-width:760px){
  body{padding-bottom:88px}
  .route{grid-template-columns:repeat(3,minmax(0,1fr))!important}
  .route span{padding:8px 8px!important;font-size:11px!important;line-height:1.35!important}
  .route b{font-size:9px!important;margin-bottom:1px!important}
  .mobile-cta{position:fixed;left:12px;right:12px;bottom:12px;z-index:80;display:flex;
    padding:8px;border:1px solid rgba(0,0,0,.08);border-radius:12px;
    background:rgba(255,255,255,.94);backdrop-filter:blur(10px);
    box-shadow:0 10px 28px rgba(16,24,40,.18)}
  .mobile-cta button{width:100%;min-height:52px;margin:0!important;font-size:15px}
}
</style></head><body>
<header><h1><span class="prod">识卡</span>这叠名片，半小时清完</h1><p class="lede">给展会后要整理联系人的人：批量拍名片，逐张确认姓名、公司、电话、邮箱并定位原图；疑似重复可合并，也可分别存。</p></header>
  <div class="route" aria-label="任务步骤"><span><b>01</b>批量拍名片</span><span><b>02</b>逐张确认字段</span><span><b>03</b>导出 vCard / CSV</span></div>

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
</script>
<script>
(function(){
  var want = "存进通讯录";
  function norm(t){ return String(t||'').replace(/\s+/g,''); }
  var all=[].slice.call(document.querySelectorAll('button'));
  var src=null, fallback=null;
  for(var i=0;i<all.length;i++){
    var b=all[i];
    if(b.offsetParent===null||b.disabled) continue;
    if(!fallback) fallback=b;
    if(norm(b.textContent).indexOf(norm(want))>=0){ src=b; break; }
  }
  if(!src) src=fallback;
  if(!src) return;
  var bar=document.createElement('div'); bar.className='mobile-cta';
  var btn=src.cloneNode(true); btn.removeAttribute('id'); btn.type='button';
  btn.addEventListener('click',function(e){e.preventDefault(); src.click();});
  bar.appendChild(btn); document.body.appendChild(bar);
})();
</script>
</body></html>"""


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
