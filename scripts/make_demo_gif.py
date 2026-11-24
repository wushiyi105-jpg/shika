"""生成 assets/demo.gif：960×600 的终端风演示动图。

只用 Pillow（开发期依赖，不进 requirements）。跑法：
    python scripts/make_demo_gif.py

画面里的字段都是真读出来的：一张 1200×800 的名片样例，0 个出处对不上的字段。
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

W, H = 960, 600
BG = "#0b0f14"
BAR = "#161b22"
LINE = "#21262d"
GREEN = "#7ee787"
TEXT = "#c9d1d9"
DIM = "#8b949e"
BLUE = "#79c0ff"
YELLOW = "#e3b341"
RED = "#ff7b72"

FONT_PATH = r"C:\Windows\Fonts\msyh.ttc"

LINE_H = 25
MAX_W = W - 56

COLORS = {"cmd": GREEN, "out": TEXT, "dim": DIM, "cite": BLUE, "warn": YELLOW, "bad": RED}


def font(size: int):
    return ImageFont.truetype(FONT_PATH, size)


_MEASURE = ImageDraw.Draw(Image.new("RGB", (1, 1)))


def clip(text: str, size: int = 16) -> str:
    f = font(size)
    if _MEASURE.textlength(text, font=f) <= MAX_W:
        return text
    while text and _MEASURE.textlength(text + "…", font=f) > MAX_W:
        text = text[:-1]
    return text + "…"


def render(rows, cursor_row=None):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 36], fill=BAR)
    for i, color in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        d.ellipse([16 + i * 22, 12, 28 + i * 22, 24], fill=color)
    d.text((92, 9), "shika — 名片进通讯录，每个字段都能追到那一行", font=font(15), fill=DIM)
    d.line([0, 36, W, 36], fill=LINE)

    y = 54
    for idx, (style, text) in enumerate(rows):
        shown = clip(text)
        d.text((26, y), shown, font=font(16), fill=COLORS[style])
        if cursor_row == idx:
            w = _MEASURE.textlength(shown, font=font(16))
            d.rectangle([26 + w + 4, y + 2, 26 + w + 12, y + 19], fill=GREEN)
        y += LINE_H
        if y > H - 16:
            break
    return img


SCRIPT = [
    ("cmd", "> python -m shika read samples/card-1.jpg --lines"),
    ("dim", "卡片上的字："),
    ("dim", "  0: 星野科技      1: 林知远      2: 产品总监"),
    ("dim", "  3: 手机 138 0013 8000"),
    ("dim", "  4: 邮箱 lin.zhiyuan@xingye.com"),
    ("dim", "  5: 深圳市南山区科苑路8号12层"),
    ("out", "林知远（星野科技）"),
    ("out", "  职位：产品总监   手机：13800138000"),
    ("cite", "  邮箱：lin.zhiyuan@xingye.com"),
    ("out", "  地址：深圳市南山区科苑路8号12层"),
    ("out", "把握：high · 这是一张商务联系的名片"),
    ("cmd", "> python -m shika add samples/card-1.jpg"),
    ("out", "· [1] 林知远（星野科技） 已新建"),
    ("cmd", "> python -m shika add samples/card-1.jpg   # 同一张卡再读一次"),
    ("out", "· [1] 林知远（星野科技） 已并入原有联系人（同一手机/邮箱/同名同公司）"),
    ("cmd", "> python -m shika export --vcf"),
    ("out", "· 导出 1 条 → contacts.vcf"),
]
TAIL = [
    ("warn", "模型有时候会给一个卡片上没有的手机号 —— 每个字段都报行号，"),
    ("dim", "程序回头去那一行找，找不到就清空：宁可不记，也不留假号码。"),
]


def build():
    frames, shown = [], []
    for style, text in SCRIPT:
        if style == "cmd":
            for i in range(6, len(text) + 1, 6):
                frames.append(render(shown + [("cmd", text[:i])], cursor_row=len(shown)))
        shown = shown + [(style, text)]
        frames.append(render(shown))
    for _ in range(12):
        frames.append(render(shown + TAIL))

    frames = [f.quantize(colors=20, method=Image.MEDIANCUT) for f in frames]
    os.makedirs("assets", exist_ok=True)
    out = os.path.join("assets", "demo.gif")
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=140, loop=0, optimize=True)
    print(f"ok -> {out}  {len(frames)} 帧  {os.path.getsize(out) / 1024:.1f} KB")


if __name__ == "__main__":
    build()
