# -*- coding: utf-8 -*-
"""
i_to_png.py —— 把 .HMI 里的 `.i`（屏显图，RGB565）解出来渲染成 PNG，供人肉眼看

为什么需要它
    控件的 `pic=N` 只是一个数字。N 到底画的是"红方块"还是"绿圆柱"，
    光看控件属性是**看不出来**的 —— 只能把图解出来看。
    命名（货物名称/类别表）和图片 ID 的映射一旦错，屏上就会出现
    "名称写 CUBE、图却是圆柱"这种一眼假的结果。

用法
    python i_to_png.py <file.HMI> [输出目录]
    python i_to_png.py <file.HMI> out/ 0 1 2 3 4 5 6      # 只解指定编号
    python i_to_png.py <file.HMI> out/ --montage          # 额外拼一张对照图（需 Pillow）

格式要点（`.i` 成员，已验证）
    24B 头： 0A 60 01 03 | u32 0 | u32 24 | u16 宽 | u16 高 | u32 payload大小 | u32 0
    payload：20B 全零（未压缩 flag=0） + 宽×高×2 字节原始 RGB565 **小端**
    透明像素被写成 0x0000（黑），所以图上会有黑边 —— 那是素材透明底导致的，不是解错了。

依赖
    只用标准库就能出 PNG；`--montage` 需要 Pillow（pip install pillow）。
"""
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hmi_inspect as H          # noqa: E402  复用它的 load()/parse_members()（含共享读绕过）


def rgb565_to_png_bytes(w, h, pix):
    """RGB565 小端 -> PNG 文件字节。纯标准库实现。"""
    rows = []
    for y in range(h):
        row = bytearray([0])                 # PNG filter type 0
        base = y * w * 2
        for x in range(w):
            v = pix[base + x * 2] | (pix[base + x * 2 + 1] << 8)
            r = (v >> 11) & 0x1F
            g = (v >> 5) & 0x3F
            b = v & 0x1F
            row += bytes([(r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)])
        rows.append(bytes(row))
    raw = b"".join(rows)

    def chunk(typ, data):
        c = typ + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def decode_i(data):
    """返回 (w, h, rgb565_bytes) 或 None（数据不足时）。"""
    if len(data) < 44:
        return None
    w, h = struct.unpack_from("<HH", data, 12)
    pix = data[24 + 20:]                     # 跳过 24B 头 + 20B 未压缩标志区
    need = w * h * 2
    if len(pix) < need:
        return None
    return w, h, pix[:need]


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    src = sys.argv[1]
    outdir = "i_png_out"
    want = []
    montage = False
    for a in sys.argv[2:]:
        if a == "--montage":
            montage = True
        elif a.isdigit():
            want.append(int(a))
        elif not a.startswith("-"):
            outdir = a

    os.makedirs(outdir, exist_ok=True)
    b = H.load(src)
    members = H.parse_members(b)

    got = []
    for name in sorted(m for m in members if m.endswith(".i")):
        idx = int(name[:-2])
        if want and idx not in want:
            continue
        off, size, _ = members[name]
        r = decode_i(b[off:off + size])
        if r is None:
            print("  %-6s 数据不足，跳过" % name)
            continue
        w, h, pix = r
        p = os.path.join(outdir, "%d.png" % idx)
        open(p, "wb").write(rgb565_to_png_bytes(w, h, pix))
        got.append((idx, w, h, p))
        print("  %-6s %3dx%-4d -> %s" % (name, w, h, p))

    print("\n共 %d 张。**请打开 PNG 亲眼看一遍**，再决定控件的 pic= 该填几、"
          "类别名该怎么起。" % len(got))
    print("提示：图上四角/四周的黑边是素材透明底（.i 没有 alpha 通道），不是解析错误。")

    if montage and got:
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            print("\n（--montage 需要 Pillow：pip install pillow）")
            return 0
        S = 3
        imgs = [(i, Image.open(p).resize((w * S, h * S), Image.NEAREST))
                for i, w, h, p in got]
        W = sum(im.width for _, im in imgs) + 10 * (len(imgs) + 1)
        Hh = max(im.height for _, im in imgs) + 30
        c = Image.new("RGB", (W, Hh), (40, 40, 40))
        dr = ImageDraw.Draw(c)
        x = 10
        for i, im in imgs:
            c.paste(im, (x, 22))
            dr.text((x + 4, 6), "%d.i" % i, fill=(255, 255, 0))
            x += im.width + 10
        mp = os.path.join(outdir, "montage.png")
        c.save(mp)
        print("已拼对照图 -> %s" % mp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
