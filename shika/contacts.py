"""名片的字段：归一化、校验、合并、导出。

模型负责「这行字是什么」，这里负责「它到底合不合法」——
手机号是不是 11 位、邮箱有没有 @、姓名里有没有混进公司名。
"""

from __future__ import annotations

import re

FIELDS = ("name", "company", "title", "mobile", "tel", "email", "address", "note")

LABELS = {
    "name": "姓名",
    "company": "公司",
    "title": "职位",
    "mobile": "手机",
    "tel": "座机",
    "email": "邮箱",
    "address": "地址",
    "note": "备注",
}

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
_MOBILE_RE = re.compile(r"^1[3-9]\d{9}$")


def normalize_phone(text: str) -> str:
    """把 +86 138-0013-8000 / (010) 8888 6666 收成统一写法。认不出返回空串。"""
    if not text:
        return ""
    raw = str(text)
    raw = raw.replace("＋", "+").replace("—", "-").replace("－", "-")
    raw = re.sub(r"(?i)\b(tel|mobile|phone|手机|电话|座机)\b[:：]?", "", raw)
    digits = re.sub(r"[^\d]", "", raw.split("转")[0])
    if digits.startswith("0086"):
        digits = digits[4:]
    elif digits.startswith("86") and len(digits) == 13:
        digits = digits[2:]
    if len(digits) == 11 and _MOBILE_RE.match(digits):
        return digits
    if 10 <= len(digits) <= 12:
        # 座机带区号：01088886666 / 075512345678
        return digits
    return ""


def is_mobile(phone: str) -> bool:
    return bool(_MOBILE_RE.match(phone or ""))


def normalize_email(text: str) -> str:
    if not text:
        return ""
    s = str(text).strip().strip("<>").strip()
    s = s.replace("＠", "@").replace("。", ".")
    s = re.sub(r"\s+", "", s)
    # 名片上常见 "lin.zhiyuan(at)xingye.com" 这种防爬写法
    s = re.sub(r"\(at\)|\[at\]|（at）", "@", s, flags=re.IGNORECASE)
    return s.lower() if _EMAIL_RE.match(s) else ""


def clean_name(text: str) -> str:
    s = re.sub(r"\s+", "", str(text or ""))
    s = re.sub(r"(先生|女士|小姐|老师|经理|总监)$", "", s)
    if not s or len(s) > 20:
        return ""
    if re.search(r"\d|公司|有限|科技|集团|大学|银行", s):
        return ""
    return s


def clean_text(text: str, limit: int = 60) -> str:
    s = re.sub(r"\s+", " ", str(text or "")).strip()
    return s[:limit]


def normalize(fields: dict) -> dict:
    """把原始字段收干净，顺便把手机/座机放对位置。"""
    out = {k: clean_text(fields.get(k)) for k in FIELDS}
    out["name"] = clean_name(fields.get("name"))
    out["email"] = normalize_email(fields.get("email"))

    mobile = normalize_phone(fields.get("mobile"))
    tel = normalize_phone(fields.get("tel"))
    if not mobile and tel and is_mobile(tel):
        mobile, tel = tel, ""
    elif mobile and not is_mobile(mobile) and not tel:
        # 填在 mobile 里但其实是座机
        mobile, tel = "", mobile
    out["mobile"], out["tel"] = mobile, tel

    out["company"] = clean_text(fields.get("company"), 40)
    out["title"] = clean_text(fields.get("title"), 30)
    out["address"] = clean_text(fields.get("address"), 80)
    out["note"] = clean_text(fields.get("note"), 80)
    return out


def validate(card: dict) -> list[str]:
    """硬校验。返回问题清单，空列表表示没问题。"""
    problems = []
    raw_email = card.get("email_raw") or ""
    if raw_email and not card.get("email"):
        problems.append(f"邮箱格式不对：{raw_email}")
    raw_phone = card.get("mobile_raw") or card.get("tel_raw") or ""
    if raw_phone and not (card.get("mobile") or card.get("tel")):
        problems.append(f"电话位数不对：{raw_phone}")
    if not card.get("name"):
        problems.append("没读到姓名")
    if not (card.get("mobile") or card.get("tel") or card.get("email")):
        problems.append("一条联系方式都没有，这张卡等于用不上")
    return problems


def contact_key(card: dict) -> str:
    """判断「是不是同一个人」用的键：手机优先，其次邮箱，最后公司+姓名。"""
    if card.get("mobile"):
        return "m:" + card["mobile"]
    if card.get("email"):
        return "e:" + card["email"]
    if card.get("name"):
        return "n:" + (card.get("company") or "") + "|" + card["name"]
    return ""


def _longer(a: str, b: str) -> str:
    return a if len(a or "") >= len(b or "") else b


def merge(old: dict, new: dict) -> dict:
    """把新读到的卡并进旧记录：空的不覆盖，短的让位给长的。"""
    out = dict(old)
    for key in FIELDS:
        if key == "note":
            continue
        nv = (new.get(key) or "").strip()
        ov = (out.get(key) or "").strip()
        if not nv:
            continue
        if not ov:
            out[key] = nv
        elif nv != ov:
            out[key] = _longer(ov, nv)
    notes = [x for x in (old.get("note"), new.get("note")) if x]
    if notes:
        out["note"] = "；".join(dict.fromkeys(notes))[:80]
    return out


def display_name(card: dict) -> str:
    name = card.get("name") or "没名字"
    company = card.get("company") or ""
    return f"{name}（{company}）" if company else name


def to_csv_rows(cards: list[dict]) -> tuple[list[str], list[list[str]]]:
    header = ["姓名", "公司", "职位", "手机", "座机", "邮箱", "地址", "备注"]
    rows = []
    for c in cards:
        rows.append([c.get(k) or "" for k in
                     ("name", "company", "title", "mobile", "tel", "email", "address", "note")])
    return header, rows


def to_vcard(card: dict) -> str:
    """vCard 3.0。手机上导进去就能加联系人。"""
    name = card.get("name") or ""
    lines = ["BEGIN:VCARD", "VERSION:3.0", f"FN:{name}", f"N:{name};;;;"]
    if card.get("company"):
        lines.append(f"ORG:{card['company']}")
    if card.get("title"):
        lines.append(f"TITLE:{card['title']}")
    if card.get("mobile"):
        lines.append(f"TEL;TYPE=CELL:{card['mobile']}")
    if card.get("tel"):
        lines.append(f"TEL;TYPE=WORK:{card['tel']}")
    if card.get("email"):
        lines.append(f"EMAIL;TYPE=WORK:{card['email']}")
    if card.get("address"):
        lines.append(f"ADR;TYPE=WORK:;;{card['address']};;;;")
    if card.get("note"):
        lines.append(f"NOTE:{card['note']}")
    lines.append("END:VCARD")
    return "\r\n".join(lines)


def render_card(card: dict, problems: list[str] | None = None) -> str:
    lines = [display_name(card)]
    for key in ("title", "mobile", "tel", "email", "address", "note"):
        if card.get(key):
            lines.append(f"  {LABELS[key]}：{card[key]}")
    for p in problems or []:
        lines.append(f"  ! {p}")
    return "\n".join(lines)
