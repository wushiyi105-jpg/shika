"""看名片：视觉模型只负责把字读出来，字段归位和合法性交给本地。

这里最要紧的一道关叫「出处核对」：模型给每个字段报一个行号，
程序回头去那一行里找这个值。找不到就说明这个字段是它猜的——猜的字段一律清空，
不能在通讯录里留下一个查无实据的手机号。
"""

from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request

from . import contacts, llm

DEFAULT_PROMPT = """看这张名片照片，分两步做。

第一步，逐行把卡片上的字读出来，一行一行来，别合并、别改写、别翻译。
第二步，把信息填进字段，每个字段必须写出它来自第几行（从 0 开始数）。

要求：
- 只填卡片上真有的。读不出来就留空，不要按常理补一个
- 手机号、邮箱照抄原文，不要自己整理格式
- 姓名不要带「先生/女士」，公司写全称
- 拿不准的字段就留空，confidence 写 low

只输出 JSON：
{"lines": ["第一行的字", "第二行的字"],
 "fields": {"name": {"value": "", "line": 0},
            "company": {"value": "", "line": 0},
            "title": {"value": "", "line": 0},
            "mobile": {"value": "", "line": 0},
            "tel": {"value": "", "line": 0},
            "email": {"value": "", "line": 0},
            "address": {"value": "", "line": 0},
            "note": {"value": "", "line": 0}},
 "confidence": "high|medium|low",
 "note": "一句话：这张卡是什么场合的"}"""

MAX_BYTES = 900_000
_SPACE = re.compile(r"[\s\u3000]+")


def vision_config() -> dict:
    llm.load_dotenv()
    key = os.environ.get("VISION_API_KEY") or os.environ.get("LLM_API_KEY")
    base = os.environ.get("VISION_BASE_URL") or os.environ.get("LLM_BASE_URL") or \
        "https://open.bigmodel.cn/api/paas/v4"
    model = os.environ.get("VISION_MODEL") or "glm-4.6v-flashx"
    return {"api_key": key, "base_url": base, "model": model}


def encode_image(path: str) -> str:
    """读图转 data URL。超过 900KB 用 Pillow 缩一下（它是可选依赖）。"""
    with open(path, "rb") as f:
        raw = f.read()
    ext = os.path.splitext(path)[1].lstrip(".").lower() or "jpeg"
    if len(raw) > MAX_BYTES:
        try:
            import io

            from PIL import Image

            img = Image.open(io.BytesIO(raw)).convert("RGB")
            scale = (MAX_BYTES / len(raw)) ** 0.5
            size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
            img = img.resize(size)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=82)
            raw = buf.getvalue()
            ext = "jpeg"
        except Exception:  # noqa: BLE001
            pass
    if ext == "jpg":
        ext = "jpeg"
    return f"data:image/{ext};base64," + base64.b64encode(raw).decode("ascii")


def _post(url: str, payload: dict, key: str, timeout: int = 120) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + key,
                 "User-Agent": "shika/0.1"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8")[:300]
        except Exception:  # noqa: BLE001
            pass
        raise llm.LLMError(f"视觉接口返回 {e.code}: {detail or e.reason}") from e
    except urllib.error.URLError as e:
        raise llm.LLMError(f"连不上视觉接口 {url}: {e.reason}") from e


def _flat(text: str) -> str:
    """比对用：去掉所有空白、统一大小写、全角转半角。"""
    s = _SPACE.sub("", str(text or ""))
    out = []
    for ch in s:
        code = ord(ch)
        if 0xFF01 <= code <= 0xFF5E:
            ch = chr(code - 0xFEE0)
        out.append(ch.lower())
    return "".join(out)


def verify_fields(fields: dict, lines: list[str]) -> tuple[dict, list[dict]]:
    """核对每个字段的出处。返回 (可信字段, 问题清单)。"""
    flat_lines = [_flat(x) for x in lines]
    good, issues = {}, []
    for key in contacts.FIELDS:
        row = fields.get(key)
        if isinstance(row, str):
            row = {"value": row}
        if not isinstance(row, dict):
            continue
        value = str(row.get("value") or "").strip()
        if not value:
            continue
        flat = _flat(value)
        line_no = row.get("line")
        try:
            line_no = int(line_no)
        except (TypeError, ValueError):
            line_no = -1

        if 0 <= line_no < len(flat_lines) and flat and flat in flat_lines[line_no]:
            good[key] = value
            continue
        # 行号错了但全文里确实有这段字：降级为「有出处，但行号不对」
        if flat and any(flat in line for line in flat_lines):
            good[key] = value
            continue
        issues.append({"field": key, "value": value,
                       "reason": "卡片上找不到这行字" if flat_lines else "一个字都没读出来"})
    return good, issues


def extract(raw_text: str) -> dict:
    """把模型输出整理成 {lines, fields, confidence, note, issues}。"""
    try:
        parsed = llm.extract_json(raw_text)
    except llm.LLMError as e:
        return {"lines": [], "fields": {}, "confidence": "low", "note": "",
                "issues": [{"field": "", "value": "", "reason": str(e)}]}
    if not isinstance(parsed, dict):
        return {"lines": [], "fields": {}, "confidence": "low", "note": "",
                "issues": [{"field": "", "value": "", "reason": "返回不是对象"}]}

    lines = []
    for x in parsed.get("lines") or []:
        s = str(x or "").strip()
        if s:
            lines.append(re.sub(r"\s+", " ", s)[:120])

    fields = parsed.get("fields") or {}
    if not isinstance(fields, dict):
        fields = {}
    good, issues = verify_fields(fields, lines)
    conf = parsed.get("confidence")
    note = str(parsed.get("note") or "").strip()
    # 模型爱把提示词里的标签一起抄回来：「一句话：这张卡是商务场合的」
    for prefix in ("一句话：", "一句话:", "场景：", "场景:"):
        if note.startswith(prefix):
            note = note[len(prefix):].strip()
    return {
        "lines": lines,
        "fields": good,
        "confidence": conf if conf in ("high", "medium", "low") else "medium",
        "note": note[:80],
        "issues": issues,
    }


def read_card(image_path: str, prompt: str = DEFAULT_PROMPT, config: dict | None = None,
              timeout: int = 120) -> dict:
    """读出名片。返回 {lines, fields, confidence, note, issues, error}，失败不抛。"""
    cfg = {**vision_config(), **(config or {})}
    err = {"lines": [], "fields": {}, "confidence": "low", "note": "", "issues": [],
           "error": ""}
    if not cfg.get("api_key"):
        return {**err, "error": "未配置 VISION_API_KEY"}
    if not os.path.isfile(image_path):
        return {**err, "error": f"找不到图片：{image_path}"}

    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": "你是名片录入员。只读卡片上有的字，读不出来就留空。"},
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": encode_image(image_path)}},
            ]},
        ],
        "temperature": 0.1,
        "max_tokens": 1200,
    }
    try:
        body = _post(cfg["base_url"].rstrip("/") + "/chat/completions", payload, cfg["api_key"], timeout)
        content = (body["choices"][0]["message"].get("content") or "").strip()
    except (llm.LLMError, KeyError, IndexError, TypeError) as e:
        return {**err, "error": str(e)}
    if not content:
        return {**err, "error": "模型返回空正文"}

    out = extract(content)
    out["error"] = ""
    out["raw"] = content
    return out


def to_entry(result: dict) -> tuple[dict, list[str]]:
    """识别结果 → 可以入库的卡片 + 问题清单（含出处不符）。"""
    raw_fields = result.get("fields") or {}
    flat = {}
    for key, row in raw_fields.items():
        if isinstance(row, dict):
            flat[key] = str(row.get("value") or "").strip()
        else:
            flat[key] = str(row or "").strip()

    card = contacts.normalize(flat)
    card["email_raw"] = flat.get("email") or ""
    card["mobile_raw"] = flat.get("mobile") or ""
    card["tel_raw"] = flat.get("tel") or ""
    problems = contacts.validate(card)
    dropped = {i.get("field") for i in (result.get("issues") or [])}
    for key in dropped:
        # 出处对不上的字段一律清掉：宁可不记，也不能在通讯录里留一个查无实据的号码
        card[key] = ""
    for issue in result.get("issues") or []:
        label = contacts.LABELS.get(issue.get("field"), issue.get("field") or "输出")
        problems.append(f"{label}「{issue.get('value')}」{issue.get('reason')}，已丢弃")
    return card, problems
