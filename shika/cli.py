"""命令行入口。"""

from __future__ import annotations

import argparse
import csv
import json
import os

from . import contacts, reader, store

_OPENED: list = []


def _open(args):
    conn = store.connect(args.db)
    _OPENED.append(conn)
    return conn


def _print_result(result: dict, card: dict, problems: list[str], args) -> None:
    if args.show_lines:
        print("卡片上的字：")
        for i, line in enumerate(result.get("lines") or []):
            print(f"  {i}: {line}")
        print()
    print(contacts.render_card(card, problems))
    print(f"\n把握：{result.get('confidence') or '没给'}"
          + (f" · {result.get('note')}" if result.get("note") else ""))
    if result.get("issues"):
        print(f"出处对不上、已丢弃的字段：{len(result['issues'])} 个")


def cmd_read(args) -> int:
    """只识别，不入库。"""
    result = reader.read_card(args.image)
    if result["error"]:
        print(f"✗ 没读成：{result['error']}")
        return 1
    card, problems = reader.to_entry(result)
    _print_result(result, card, problems, args)
    if args.json:
        print(json.dumps({"card": card, "problems": problems,
                          "lines": result["lines"], "confidence": result["confidence"]},
                         ensure_ascii=False, indent=2))
    return 0


def cmd_add(args) -> int:
    conn = _open(args)
    result = reader.read_card(args.image)
    if result["error"]:
        print(f"✗ 没读成：{result['error']}")
        return 1
    card, problems = reader.to_entry(result)
    _print_result(result, card, problems, args)
    if not (card.get("name") or card.get("mobile") or card.get("email")):
        print("\n✗ 姓名和联系方式都是空的，这张卡没东西可存")
        return 1
    saved = store.save_card(conn, card, image=os.path.basename(args.image),
                            lines=result["lines"], confidence=result["confidence"],
                            note=result["note"], problems=problems)
    print(f"\n· [{saved['id']}] {contacts.display_name(saved)} "
          + ("已新建" if saved.get("created") else "已并入原有联系人（同一手机/邮箱/同名同公司）"))
    if problems:
        print(f"  {len(problems)} 个字段有问题，建议去通讯录里修一下：python -m shika show {saved['id']}")
    return 0


def cmd_list(args) -> int:
    conn = _open(args)
    rows = store.list_contacts(conn, args.keyword or "")
    if not rows:
        print("通讯录还是空的。先读一张：python -m shika add samples/card-1.jpg")
        return 0
    for r in rows:
        who = contacts.display_name(r)
        way = r["mobile"] or r["tel"] or r["email"] or "没有联系方式"
        print(f"{r['id']:<4}{who:<28}{way}")
    return 0


def cmd_show(args) -> int:
    conn = _open(args)
    row = store.get_contact(conn, args.id)
    if not row:
        print(f"✗ 没有 id={args.id} 的联系人")
        return 1
    print(contacts.render_card(row))
    cards = store.cards_of(conn, args.id)
    print(f"\n来源：{len(cards)} 张卡")
    for c in cards:
        print(f"  [{c['id']}] {c['created_at']} · {c['image'] or '没记图'} · 把握 {c['confidence'] or '没给'}")
        for p in c["problems"]:
            print(f"      ! {p}")
        if args.lines:
            for i, line in enumerate(c["lines"]):
                print(f"      {i}: {line}")
    return 0


def cmd_export(args) -> int:
    conn = _open(args)
    rows = store.list_contacts(conn, args.keyword or "")
    if not rows:
        print("没有可导出的联系人。")
        return 1
    ext = "csv" if args.csv else "vcf"
    out = args.out or f"contacts.{ext}"
    if args.csv:
        header, data = contacts.to_csv_rows(rows)
        with open(out, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(data)
    else:
        with open(out, "w", encoding="utf-8", newline="") as f:
            f.write("\r\n".join(contacts.to_vcard(r) for r in rows) + "\r\n")
    print(f"· 导出 {len(rows)} 条 → {out}")
    return 0


def cmd_rm(args) -> int:
    conn = _open(args)
    if not store.get_contact(conn, args.id):
        print(f"✗ 没有 id={args.id} 的联系人")
        return 1
    store.delete_contact(conn, args.id)
    print(f"· [{args.id}] 已删除（连它的识别记录一起）")
    return 0


def cmd_stats(args) -> int:
    conn = _open(args)
    print("统计：", store.stats(conn))
    return 0


def cmd_serve(args) -> int:
    from . import web

    conn = _open(args)
    web.serve(conn, host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="shika", description="名片识别：模型读字，程序判字段。")
    p.add_argument("--db", default="data/shika.db")
    p.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    p.add_argument("--api-key")
    p.add_argument("--base-url")
    p.add_argument("--model")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("read", help="读一张卡但不入库")
    r.add_argument("image")
    r.add_argument("--lines", dest="show_lines", action="store_true", help="把读到的原文行也打出来")
    r.add_argument("--json", action="store_true")
    r.set_defaults(func=cmd_read)

    a = sub.add_parser("add", help="读一张卡并入库")
    a.add_argument("image")
    a.add_argument("--lines", dest="show_lines", action="store_true")
    a.add_argument("--json", action="store_true")
    a.set_defaults(func=cmd_add)

    lst = sub.add_parser("list", help="通讯录")
    lst.add_argument("keyword", nargs="?", default="")
    lst.set_defaults(func=cmd_list)

    s = sub.add_parser("show", help="看一个联系人和他的来源卡")
    s.add_argument("id", type=int)
    s.add_argument("--lines", action="store_true", help="连识别原文一起看")
    s.set_defaults(func=cmd_show)

    e = sub.add_parser("export", help="导出通讯录")
    g = e.add_mutually_exclusive_group()
    g.add_argument("--csv", action="store_true", help="导 CSV（默认导 vCard）")
    g.add_argument("--vcf", action="store_true", help="导 vCard（默认）")
    e.add_argument("--out")
    e.add_argument("keyword", nargs="?", default="")
    e.set_defaults(func=cmd_export)

    rm = sub.add_parser("rm", help="删一个联系人")
    rm.add_argument("id", type=int)
    rm.set_defaults(func=cmd_rm)

    sub.add_parser("stats", help="统计").set_defaults(func=cmd_stats)

    sv = sub.add_parser("serve", help="起 Web")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8773)
    sv.set_defaults(func=cmd_serve)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    finally:
        while _OPENED:
            try:
                _OPENED.pop().close()
            except Exception:  # noqa: BLE001
                pass
