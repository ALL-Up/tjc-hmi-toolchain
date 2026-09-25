# -*- coding: utf-8 -*-
"""
draw_assets.py —— 中文化 + 全不透明素材（修复 .i 黑边）

背景：.i 屏显格式（RGB565）没有 alpha，透明像素转 0x0000 = 黑 → v16 及之前
所有透明底素材在画布上四边/四角带黑边。
方案：全部素材不透明；按钮四角直接填背景图对应位置的【切片色】（精确无缝）。
尺寸与 v2 完全一致（166x62 / 98x50 / 60x60 / 80x80 / 480x272），控件表不用改。
"""
import os
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out", "assets")
os.makedirs(OUT, exist_ok=True)

W, H = 480, 272
SS = 4                                    # 图标超采样倍数（抗锯齿）
CT_TOP, CT_BOT = (10, 27, 62), (22, 62, 122)      # 欢迎页渐变
CS_TOP, CS_BOT = (234, 242, 248), (208, 228, 242) # 分类页渐变


def font_cn(size):
    return ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", size, index=0)


def vgrad(size, c_top, c_bot):
    w, h = size
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(1, h - 1)
        d.line([(0, y), (w, y)],
               fill=tuple(int(a + (b - a) * t) for a, b in zip(c_top, c_bot)))
    return img


def centered_text(d, cx, y, text, f, fill):
    bb = d.textbbox((0, 0), text, font=f)
    d.text((cx - (bb[2] - bb[0]) // 2 - bb[0], y - bb[1]), text, font=f, fill=fill)


def glow_text(d, x0, y, text, f, main, glow):
    bb = d.textbbox((0, 0), text, font=f)
    for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2), (0, 3)):
        d.text((x0 + ox - bb[0], y + oy - bb[1]), text, font=f, fill=glow)
    d.text((x0 - bb[0], y - bb[1]), text, font=f, fill=main)


def iso_cube(draw, cx, cy, s, light, mid, dark):
    """等距立方体：light=顶面 mid=左面 dark=右面"""
    dx, dy = int(s * 0.87), s // 2
    top = (cx, cy - s)
    right = (cx + dx, cy - s + dy)
    left = (cx - dx, cy - s + dy)
    midp = (cx, cy - s + 2 * dy)
    draw.polygon([top, right, midp, left], fill=light)
    draw.polygon([left, midp, (cx, cy + s), (cx - dx, cy + s - dy)], fill=mid)
    draw.polygon([midp, right, (cx + dx, cy + s - dy), (cx, cy + s)], fill=dark)


def iso_cyl(draw, cx, cy, r, hgt, light, mid, dark):
    """等距圆柱"""
    ry = r // 3
    top_y = cy - hgt // 2
    bot_y = cy + hgt // 2
    draw.rectangle([cx - r, top_y, cx + r, bot_y], fill=mid)
    draw.ellipse([cx - r, bot_y - ry, cx + r, bot_y + ry], fill=dark)
    draw.ellipse([cx - r, top_y - ry, cx + r, top_y + ry], fill=light)


def icon_card(size, painter):
    """白底圆角小卡（不透明）+ 4x 超采样图形"""
    w = h = size
    card = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=8,
                        outline=(205, 215, 225), width=2)
    big = Image.new("RGB", (w * SS, h * SS), (255, 255, 255))
    dbig = ImageDraw.Draw(big)
    painter(dbig, w * SS // 2, h * SS // 2)
    card.paste(big.resize((w, h), Image.LANCZOS), (0, 0))
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=8,
                        outline=(205, 215, 225), width=2)
    return card


def btn_on_slice(slice_img, text, c_top, c_bot, fs):
    """背景切片上叠圆角渐变按钮 + 中文（整幅不透明，无黑边）"""
    w, h = slice_img.size
    img = slice_img.copy()
    d = ImageDraw.Draw(img)
    body = vgrad((w, h), c_top, c_bot)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([2, 2, w - 3, h - 3],
                                           radius=h // 2 - 2, fill=255)
    img.paste(body, (0, 0), mask)
    d.rounded_rectangle([2, 2, w - 3, h - 3], radius=h // 2 - 2,
                        outline=(255, 255, 255), width=2)
    centered_text(d, w // 2, (h - fs) // 2 - 1, text, font_cn(fs), (255, 255, 255))
    return img


# ================= 欢迎页背景（中文） =================
bg0 = vgrad((W, H), CT_TOP, CT_BOT)
d = ImageDraw.Draw(bg0)
d.line([(0, 2), (W, 2)], fill=(0, 200, 255), width=3)
d.line([(0, H - 3), (W, H - 3)], fill=(0, 200, 255), width=2)
glow_text(d, (W - 6 * 44) // 2, 56, "智能分拣系统", font_cn(44),
          (255, 255, 255), (0, 190, 255))
centered_text(d, W // 2, 116, "视觉识别 · 自动分类 · 实时计数", font_cn(18),
              (160, 200, 235))
for i, col in enumerate([(230, 80, 80), (80, 140, 240), (90, 200, 110)]):
    cx = W // 2 - 40 + i * 40
    d.ellipse([cx - 5, 148 - 5, cx + 5, 148 + 5], fill=col)
d.ellipse([140, 160, 340, 250], outline=(0, 200, 255), width=2)
centered_text(d, W // 2, 243, "STM32F407VET6 × 淘晶驰 4.3 寸串口屏", font_cn(12),
              (120, 150, 185))
bg0.save(os.path.join(OUT, "welcome_bg.png"))

# ================= 分类页背景（中文） =================
bg1 = vgrad((W, H), CS_TOP, CS_BOT)
d = ImageDraw.Draw(bg1)
d.rectangle([0, 0, W, 40], fill=(11, 29, 58))
d.line([(0, 40), (W, 40)], fill=(0, 200, 255), width=2)
centered_text(d, W // 2, 9, "分类监控", font_cn(20), (255, 255, 255))
for y in (44, 114, 182):
    d.rounded_rectangle([8, y, 170, y + 64], radius=10,
                        fill=(255, 255, 255), outline=(180, 200, 220), width=2)
d.rounded_rectangle([183, 44, 297, 158], radius=10,
                    fill=(255, 255, 255), outline=(180, 200, 220), width=2)
centered_text(d, 240, 134, "识别结果", font_cn(13), (120, 140, 160))
d.rounded_rectangle([305, 44, 472, 100], radius=10,
                    fill=(255, 255, 255), outline=(180, 200, 220), width=2)
d.text((318, 52), "状态", font=font_cn(13), fill=(120, 140, 160))
d.rounded_rectangle([305, 108, 472, 164], radius=10,
                    fill=(255, 255, 255), outline=(180, 200, 220), width=2)
d.text((318, 118), "总数", font=font_cn(18), fill=(60, 80, 100))
d.line([(180, 176), (472, 176)], fill=(160, 180, 200), width=2)
d.rectangle([0, 250, W, H], fill=(11, 29, 58))
centered_text(d, W // 2, 253, "分类计数实时更新 · 按主页键返回欢迎页", font_cn(12),
              (150, 180, 210))
bg1.save(os.path.join(OUT, "sorting_bg.png"))

# ================= 按钮（背景切片打底 -> 无缝无黑边） =================
btn_start = bg0.crop((157, 175, 157 + 166, 175 + 62))
btn_on_slice(btn_start, "开 始", (52, 199, 89), (32, 145, 62), 22).save(
    os.path.join(OUT, "btn_start.png"))
slices = [bg1.crop((x, 190, x + 98, 190 + 50)) for x in (180, 280, 380)]
btn_on_slice(slices[0], "停 止", (231, 76, 60), (176, 48, 38), 17).save(
    os.path.join(OUT, "btn_stop.png"))
btn_on_slice(slices[1], "复 位", (243, 156, 18), (198, 120, 12), 17).save(
    os.path.join(OUT, "btn_reset.png"))
btn_on_slice(slices[2], "主 页", (93, 109, 126), (52, 73, 94), 17).save(
    os.path.join(OUT, "btn_home.png"))

# ================= 图标（白底不透明） =================
def painter_red(d, cx, cy):
    s = 26 * SS
    iso_cube(d, cx, cy, s, (255, 120, 120), (214, 60, 60), (160, 34, 34))

def painter_blue(d, cx, cy):
    s = 26 * SS
    iso_cube(d, cx, cy, s, (130, 180, 255), (60, 120, 230), (34, 78, 160))

def painter_cyl(d, cx, cy):
    r, hgt = 18 * SS, 34 * SS
    iso_cyl(d, cx, cy, r, hgt, (150, 230, 150), (70, 190, 90), (40, 130, 60))

icon_card(60, painter_red).save(os.path.join(OUT, "icon_red_60.png"))
icon_card(60, painter_blue).save(os.path.join(OUT, "icon_blue_60.png"))
icon_card(60, painter_cyl).save(os.path.join(OUT, "icon_cyl_60.png"))

# ================= 大图（白底不透明） =================
def painter_idle(d, cx, cy):
    f = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 40 * SS, index=0)
    bb = d.textbbox((0, 0), "?", font=f)
    d.text((cx - (bb[2] - bb[0]) // 2 - bb[0], cy - (bb[3] - bb[1]) // 2 - bb[1] - 8 * SS),
           "?", font=f, fill=(170, 180, 190))
    f2 = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 11 * SS, index=0)
    bb2 = d.textbbox((0, 0), "待机", font=f2)
    d.text((cx - (bb2[2] - bb2[0]) // 2 - bb2[0], cy + 18 * SS),
           "待机", font=f2, fill=(150, 160, 170))

def painter_big_red(d, cx, cy):
    iso_cube(d, cx, cy, 30 * SS, (255, 120, 120), (214, 60, 60), (160, 34, 34))

def painter_big_blue(d, cx, cy):
    iso_cube(d, cx, cy, 30 * SS, (130, 180, 255), (60, 120, 230), (34, 78, 160))

def painter_big_cyl(d, cx, cy):
    iso_cyl(d, cx, cy, 22 * SS, 42 * SS, (150, 230, 150), (70, 190, 90), (40, 130, 60))

icon_card(80, painter_idle).save(os.path.join(OUT, "big_idle_80.png"))
icon_card(80, painter_big_red).save(os.path.join(OUT, "big_red_80.png"))
icon_card(80, painter_big_blue).save(os.path.join(OUT, "big_blue_80.png"))
icon_card(80, painter_big_cyl).save(os.path.join(OUT, "big_cyl_80.png"))

print("中文不透明素材完成 →", OUT)
for f in sorted(os.listdir(OUT)):
    p = os.path.join(OUT, f)
    img = Image.open(p)
    corner = img.convert("RGBA").getpixel((0, 0))
    print("  %-18s %s  左上角=%s" % (f, img.size, corner))
