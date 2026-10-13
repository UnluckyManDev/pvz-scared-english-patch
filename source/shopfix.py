"""English versions of the shop images (background, checkout button, 14 tabs)."""
import os
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
SRC, OUT = os.path.join(HERE, "tex"), os.path.join(HERE, "tex_en")
F = r"C:\Windows\Fonts"
font = lambda n: os.path.join(F, n)


def fit(draw, text, path, w, h, spacing=0.15, stroke=0):
    lo, hi = 4, 300
    while lo < hi:
        mid = (lo + hi + 1) // 2
        f = ImageFont.truetype(path, mid)
        l, t, r, b = draw.multiline_textbbox((0, 0), text, font=f, spacing=int(mid * spacing), stroke_width=stroke, align="center")
        if r - l <= w and b - t <= h:
            lo = mid
        else:
            hi = mid - 1
    return ImageFont.truetype(path, lo), lo


def draw_centered(im, box, text, path, fill, stroke=0, stroke_fill=None, spacing=0.15, size=None):
    d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = box
    if size:
        f = ImageFont.truetype(path, size)
    else:
        f, size = fit(d, text, path, x1 - x0, y1 - y0, spacing, stroke)
    l, t, r, b = d.multiline_textbbox((0, 0), text, font=f, spacing=int(size * spacing), stroke_width=stroke, align="center")
    d.multiline_text(((x0 + x1) / 2 - (l + r) / 2, (y0 + y1) / 2 - (t + b) / 2), text, font=f, fill=fill,
                     spacing=int(size * spacing), stroke_width=stroke, stroke_fill=stroke_fill, align="center")


def erase(arr, box, is_text, grow=3):
    """Inpaint pixels inside box where is_text(rgb) is true."""
    x0, y0, x1, y1 = box
    rgb = arr[..., :3].astype(int)
    m = np.zeros(arr.shape[:2], np.uint8)
    sub = is_text(rgb[y0:y1, x0:x1])
    m[y0:y1, x0:x1] = sub.astype(np.uint8)
    m = cv2.dilate(m, np.ones((grow, grow), np.uint8), iterations=2)
    m[:y0 - 2 if y0 > 2 else 0, :] = 0
    bgr = cv2.cvtColor(arr[..., :3].copy(), cv2.COLOR_RGB2BGR)
    fixed = cv2.inpaint(bgr, m * 255, 7, cv2.INPAINT_TELEA)
    arr[..., :3] = cv2.cvtColor(fixed, cv2.COLOR_BGR2RGB)


lum = lambda c: 0.299 * c[..., 0] + 0.587 * c[..., 1] + 0.114 * c[..., 2]


def shop_background():
    im = Image.open(os.path.join(SRC, "1959.png")).convert("RGBA")
    arr = np.array(im)
    dark_or_red = lambda c: (lum(c) < 165) | ((c[..., 0] - c[..., 1]) > 40)
    for box in [(410, 60, 525, 130), (60, 336, 345, 442), (80, 468, 325, 512)]:
        erase(arr, box, dark_or_red)
    erase(arr, (1398, 166, 1494, 212), lambda c: lum(c) > 170)          # white text on the red cart header
    im = Image.fromarray(arr)
    draw_centered(im, (414, 68, 640, 124), "STORE", font("georgiab.ttf"), (112, 12, 14, 255))
    draw_centered(im, (58, 340, 345, 440), "Zomboss Institute of\nSupernatural Phenomena", font("times.ttf"),
                  (24, 24, 24, 255), spacing=0.25)
    draw_centered(im, (70, 470, 335, 510), "Control · Cleanse · Protect", font("times.ttf"), (150, 28, 28, 255))
    draw_centered(im, (1402, 176, 1462, 202), "Cart", font("segoeui.ttf"), (250, 245, 245, 255))
    im.save(os.path.join(OUT, "1959.png"))


def shop_finish():
    im = Image.open(os.path.join(SRC, "3211.png")).convert("RGBA")
    arr = np.array(im)
    erase(arr, (1440, 792, 1540, 850), lambda c: lum(c) > 120)
    im = Image.fromarray(arr)
    draw_centered(im, (1410, 806, 1570, 840), "Checkout", font("seguisb.ttf"), (228, 228, 228, 255))
    im.save(os.path.join(OUT, "3211.png"))


TABS = {  # pid: (text, selected-style)
    2842: ("Items", False), 2047: ("Items", True),
    2419: ("Seeds", False), 2721: ("Seeds", True),
    3351: ("Upgrades", False), 2449: ("Upgrades", True),
    3237: ("Gear", False), 2345: ("Gear", True),
    2754: ("Garden", False), 2311: ("Garden", True),
    2520: ("Shards", False), 2425: ("Shards", True),
    2840: ("Vouchers", False), 3297: ("Vouchers", True),
}


TAB_SIZE = None


def tab_font_size():
    d = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    return min(fit(d, t, font("ariblk.ttf"), 119 - 16, 49 - 16, stroke=2)[1] for t, _ in TABS.values())


def tab(pid, text, selected):
    im = Image.open(os.path.join(SRC, f"{pid}.png")).convert("RGBA")
    arr = np.array(im).astype(int)
    h, w = arr.shape[:2]
    # wipe the inside row by row with that row's typical background colour (keeps the gradient, drops the lettering)
    x0, x1, y0, y1 = 4, w - 4, 3, h - 3
    cols = {}
    for y in range(y0, y1):
        row = arr[y, x0:x1, :3]
        l = lum(row)
        bgpx = row[(l > (70 if selected else 140)) & (l < (200 if selected else 240)) & (np.abs(row[:, 0] - 39) > 25)]
        if len(bgpx) >= 0.45 * len(row):          # enough clean background in this row
            cols[y] = np.median(bgpx, axis=0)
    good = sorted(cols)
    for y in range(y0, y1):
        if y not in cols:                         # mostly lettering: borrow from the nearest clean rows
            above = max([g for g in good if g < y], default=None)
            below = min([g for g in good if g > y], default=None)
            if above is not None and below is not None:
                t = (y - above) / (below - above)
                cols[y] = cols[above] * (1 - t) + cols[below] * t
            else:
                cols[y] = cols[above if above is not None else below]
        arr[y, x0:x1, :3] = cols[y]
    im = Image.fromarray(arr.astype(np.uint8))
    blue = (39, 81, 119, 255)
    if selected:
        draw_centered(im, (8, 7, w - 8, h - 7), text, font("ariblk.ttf"), blue, stroke=2, stroke_fill=(255, 255, 255, 255), size=TAB_SIZE)
    else:
        draw_centered(im, (8, 7, w - 8, h - 7), text, font("ariblk.ttf"), blue, size=TAB_SIZE)
    im.save(os.path.join(OUT, f"{pid}.png"))


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    shop_background()
    shop_finish()
    TAB_SIZE = tab_font_size()
    for pid, (t, sel) in TABS.items():
        tab(pid, t, sel)
    # preview
    bg = Image.open(os.path.join(OUT, "1959.png")).convert("RGBA")
    fin = Image.open(os.path.join(OUT, "3211.png")).convert("RGBA")
    comp = bg.copy(); comp.alpha_composite(fin)
    d = comp
    x = 450
    for pid, (t, sel) in list(TABS.items()):
        if sel:
            continue
        d.alpha_composite(Image.open(os.path.join(OUT, f"{pid}.png")).convert("RGBA"), (x, 160)); x += 124
    x = 450
    for pid, (t, sel) in list(TABS.items()):
        if not sel:
            continue
        d.alpha_composite(Image.open(os.path.join(OUT, f"{pid}.png")).convert("RGBA"), (x, 215)); x += 124
    comp.convert("RGB").resize((1254, 706)).save(os.path.join(HERE, "shop_preview.png"))
    print("done")
