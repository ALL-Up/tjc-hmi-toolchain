# -*- coding: utf-8 -*-
"""
build_sorter.py —— 从零生成一个完整可用的多页 `.HMI` 工程（参考实现）

本脚本演示本项目的完整生成链路，可直接改写用于自己的工程：
  Program.s 上电脚本 + 多页 .pa + 图片三件套(.i/.is/.ib) + 字库 + main.HMI 清单
  → CFS v2 容器组装 → 自检 → 真值克隆回归

运行前准备：
    pip install pillow
    python scripts/draw_assets.py          # 生成 out/assets/ 素材

运行：
    python scripts/build_sorter.py         # 生成 out/sorter.HMI 并自检

目录约定（脚本按 __file__ 向上定位仓库根，可整体搬到任意路径）：
    <repo>/scripts/build_sorter.py         本文件
    <repo>/out/assets/*.png                素材（draw_assets.py 产出）
    <repo>/out/sorter.HMI                  输出
    <repo>/reference/truth/                真值样本（回归基准）
    <repo>/reference/truth_project.HMI     真值容器（容器级回归基准，可选）

⚠ 真值文件缺失时，脚本仍会生成工程，但会跳过对应的回归断言并明确提示。
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import pa_codec_v5 as P
from tjc_crc import TAB256, crc7950, dir_crc, tjc_crc32

OUT = os.path.join(ROOT, "out")
ASSETS = os.path.join(OUT, "assets")
TRUTH_DIR = os.path.join(ROOT, "reference", "truth")
# 真值工程（7 MB）在仓库里以 .gz 存放，避免大文件；也支持未压缩的同名文件。
TRUTH_PROJECT = os.path.join(ROOT, "reference", "truth_project.HMI")
TRUTH_PROJECT_GZ = TRUTH_PROJECT + ".gz"
os.makedirs(OUT, exist_ok=True)


def read_truth_project():
    """读取真值工程（优先未压缩，其次 .gz）。不存在则返回 None。"""
    if os.path.exists(TRUTH_PROJECT):
        return open(TRUTH_PROJECT, "rb").read()
    if os.path.exists(TRUTH_PROJECT_GZ):
        import gzip
        with gzip.open(TRUTH_PROJECT_GZ, "rb") as f:
            return f.read()
    return None

# --- CFS 目录条目的「类型标记」：实测与成员内容无关，照抄真值工程的常数 --------
TAG_TEXT = 0x0BA20900        # Program.s / main.HMI
TAG_PA = 0x00000300          # 0.pa / 1.pa
TAG_I = 0xFFFFFF00           # .i  屏显 RGB565 图
TAG_IS = 0x05276900          # .is PNG 原件
TAG_IB = 0x0098D400          # .ib 图库
TAG_ZI = 0x42B37C00          # .zi 字库


def _load(name):
    p = os.path.join(TRUTH_DIR, name)
    if not os.path.exists(p):
        return None
    return open(p, "rb").read()


TRUTH_MAIN = _load("truth_main_HMI.bin")
TRUTH_PS = _load("truth_Program_s.bin")
TRUTH_PA = _load("truth_0_pa.bin")


# ============================================================ main.HMI 清单

# main.HMI 的 96B 头模板（真值）：直接沿用，只改名字表与两个计数字段后重算 CRC。
# 头里 +0x04=datasize、+0x0C=文件版本、+0x10=Modelcrc、+0x40=0x300 等字段保持真值。
def build_main_hmi(name_entries, header_template=None):
    """
    name_entries: [(b"i", b"0.i"), (b"zi", b"0.zi"), (b"pa", b"0.pa"), ...]
                  ⚠ 名字表只登记 .i / .zi / .pa 三类；.is/.ib 在容器里存在但不登记。
    header_template: 96B 头；缺省用真值头，缺失则用内置最小头。
    """
    if header_template is not None:
        m = bytearray(header_template[:0x60])
    else:
        # 内置最小头的字段值来自真值 main.HMI（112B = 96B 头 + 16B×1 名字条）。
        # 建议优先提供 reference/truth/truth_main_HMI.bin，直接沿用上位机原始头最稳。
        m = bytearray(0x60)
        struct.pack_into("<I", m, 0x04, 0x60)          # datasize
        struct.pack_into("<I", m, 0x08, 0x64214401)
        struct.pack_into("<H", m, 0x0A, 0x0002)        # 见 +0x0C 高半字节
        struct.pack_into("<H", m, 0x0C, 0x0055)        # filever 低位 + mark(0x55)
        struct.pack_into("<I", m, 0x10, 0x187F7CCA)    # Modelcrc
        struct.pack_into("<I", m, 0x14, 0x00000000)
        struct.pack_into("<I", m, 0x18, 0x00000060)
        struct.pack_into("<I", m, 0x24, 1)             # 页面数
        struct.pack_into("<I", m, 0x40, 0x300)

    tail = b"".join(n.ljust(8, b"\x00") + f.ljust(8, b"\x00") for n, f in name_entries)
    m = m[:0x60] + tail
    struct.pack_into("<I", m, 0x1C, len(name_entries))   # +0x1C = 名字表条目数
    struct.pack_into("<I", m, 0x24, 1)                   # +0x24 = 页面数

    # 五段累积 CRC（与 .pa 头部同构，逐字节 tjc_crc32）
    crc = tjc_crc32(bytes(m[4:]))
    crc = tjc_crc32(bytes(m[0x10:0x14]), crc)
    crc = tjc_crc32(bytes(m[0x04:0x08]), crc)
    crc = tjc_crc32(bytes(m[0x0A:0x0B]), crc)
    crc = tjc_crc32(bytes(m[0x0E:0x0F]), crc)
    struct.pack_into("<I", m, 0x00, crc)
    return bytes(m)


# ============================================================ 图片三件套

def build_i_member(png_path):
    """.i —— 屏显格式（画布渲染的真正入口）：24B 头 + 20B 零 + 宽×高×2 原始 RGB565(LE)。

    🚨 RGB565 没有 alpha：透明像素被转成 0x0000 = 黑，画布上会显出黑边。
       素材必须全不透明（按钮四角填背景切片色即可视觉无缝）。
    """
    from PIL import Image
    img = Image.open(png_path).convert("RGBA")
    w, h = img.size
    px = img.load()
    raw = bytearray()
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            v = 0x0000 if a < 128 else ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            raw += struct.pack("<H", v)
    payload = b"\x00" * 20 + bytes(raw)
    hdr = bytes([0x0A, 0x60, 0x01, 0x03]) + struct.pack("<IIHHII", 0, 24, w, h, len(payload), 0)
    return hdr + payload, w, h


def build_png_member(png_path):
    """.is / .ib —— 27B 头（末尾 "png"）+ 完整 PNG 原文。两者格式同构，仅 tag 不同。"""
    png = open(png_path, "rb").read()
    w, h = struct.unpack_from(">II", png, 0x10)     # PNG IHDR 宽高（大端）
    hdr = (bytes([0x0A, 0x64, 0x01, 0x01])
           + struct.pack("<IIHHII", 0, 27, w, h, len(png), 0) + b"png")
    return hdr + png, w, h


# ============================================================ CFS v2 容器

def build_container(entries):
    """
    entries: [(name: bytes, blob: bytes, tag: int), ...] —— 顺序即容器成员顺序。

    布局（真值实测）：
        0x000000  主目录  = u32 count + count×28B 条目 + u32 目录CRC
        0x080000  目录完整副本（必须逐字节相同，只写一份会被判「资源文件受损」）
        0x380000  FF FF FF FF 无效标记
        0x6FFFF8  "ver21234" 固定魔数
        0x700000  数据区，成员首尾相接无填充，末成员结束即 EOF
    """
    count = len(entries)
    dirbuf = bytearray(struct.pack("<I", count))
    acc = 0
    for name, blob, tag in entries:
        if len(name) > 16:
            raise ValueError("成员名超过 16 字节: %r" % name)
        dirbuf += name + b"\x00" * (16 - len(name))
        dirbuf += struct.pack("<III", 0x700000 + acc, len(blob), tag)
        acc += len(blob)
    dirbuf += struct.pack("<I", dir_crc(bytes(dirbuf)))

    out = bytearray(0x700000)
    out[0:len(dirbuf)] = dirbuf
    out[0x80000:0x80000 + len(dirbuf)] = dirbuf
    out[0x380000:0x380004] = b"\xFF\xFF\xFF\xFF"
    out[0x6FFFF8:0x700000] = b"ver21234"
    pos = 0x700000
    for _, blob, _ in entries:
        out[pos:pos + len(blob)] = blob
        pos += len(blob)
    return bytes(out[:pos])


def selfcheck_container(path, verbose=True):
    """交付前必过的容器自检：目录 CRC / 双副本一致 / 成员偏移连续 / EOF 对齐。"""
    b = open(path, "rb").read()
    count = struct.unpack_from("<I", b, 0)[0]
    dirbuf = b[0:4 + 28 * count]
    stored = struct.unpack_from("<I", b, 4 + 28 * count)[0]
    crc_ok = dir_crc(dirbuf) == stored
    copy_ok = b[0:4 + 28 * count + 4] == b[0x80000:0x80000 + 4 + 28 * count + 4]
    acc = 0x700000
    off_ok = True
    for i in range(count):
        e = 4 + 28 * i
        off, size, _ = struct.unpack_from("<III", b, e + 16)
        off_ok &= (off == acc)
        acc += size
    eof_ok = (len(b) == acc)
    if verbose:
        print("      [自检] 目录CRC=%s 双副本=%s 偏移连续=%s EOF=%s 成员数=%d"
              % (crc_ok, copy_ok, off_ok, eof_ok, count))
    return crc_ok and copy_ok and off_ok and eof_ok


def regress_truth_clone():
    """真值克隆回归：用真值成员重建容器，应与真值工程逐字节一致。

    这是「生成器 100% 正确」的证明 —— 只有它通过，才允许替换内容生成正式工程。
    """
    if not (TRUTH_MAIN and TRUTH_PS and TRUTH_PA):
        print("[回归] 跳过：真值成员缺失")
        return None
    truth = read_truth_project()
    if truth is None:
        print("[回归] 跳过：reference/truth_project.HMI(.gz) 缺失")
        return None
    gen = build_container([(b"Program.s", TRUTH_PS, TAG_TEXT),
                           (b"0.pa", TRUTH_PA, TAG_PA),
                           (b"main.HMI", TRUTH_MAIN, TAG_TEXT)])
    same = gen == truth
    print("[回归] 真值克隆逐字节一致 = %s" % same)
    return same


# ============================================================ 工程定义

PROGRAM_S = (
    "// 上电初始化脚本\r\n"
    "int sys0=0\r\n"
    "baud=9600\r\n"          # 运行波特率
    "bkcmd=0\r\n"
    "dim=100\r\n"            # 背光 100%
    "page 0\r\n"             # 上电停在第 0 页
)

TYPE_TXT, TYPE_NUM, TYPE_PIC, TYPE_BTN = 0x74, 0x36, 0x70, 0x62
BLACK, WHITE, BLUE = 0, 65535, 31

# 图片顺序 = 成员编号（0.i=图0 …），控件用 pic=N 引用
IMAGE_FILES = [
    "icon_red_60.png", "icon_blue_60.png", "icon_cyl_60.png",       # 0 1 2
    "big_idle_80.png", "big_red_80.png", "big_blue_80.png",         # 3 4 5
    "big_cyl_80.png", "welcome_bg.png", "sorting_bg.png",           # 6 7 8
    "btn_start.png", "btn_stop.png", "btn_reset.png", "btn_home.png",  # 9 10 11 12
]

# page0：欢迎页 —— 背景 + START 按钮（sta=2 图片模式；按下事件跳分类页）
PAGE0_WIDGETS = [
    dict(type=TYPE_PIC, objname=b"p_bg", pic=7, x=0, y=0, w=480, h=272),
    dict(type=TYPE_BTN, objname=b"b_start", sta=2, pic=9, pic2=9, sendkey=1,
         codesdown="page 1", x=157, y=175, w=166, h=62),
]

# page1：分类页 —— 三组「图标 + 数字」、识别结果大图、状态文本、四个按钮
PAGE1_WIDGETS = [
    dict(type=TYPE_PIC, objname=b"p_bg", pic=8, x=0, y=0, w=480, h=272),
    dict(type=TYPE_PIC, objname=b"p1", pic=0, x=14, y=48, w=60, h=60),
    dict(type=TYPE_NUM, objname=b"n0", val=0, x=76, y=56, w=90, h=44, bco=WHITE, pco=BLACK),
    dict(type=TYPE_PIC, objname=b"p2", pic=1, x=14, y=118, w=60, h=60),
    dict(type=TYPE_NUM, objname=b"n1", val=0, x=76, y=126, w=90, h=44, bco=WHITE, pco=BLACK),
    dict(type=TYPE_PIC, objname=b"p3", pic=2, x=14, y=186, w=60, h=60),
    dict(type=TYPE_NUM, objname=b"n2", val=0, x=76, y=194, w=90, h=44, bco=WHITE, pco=BLACK),
    dict(type=TYPE_PIC, objname=b"p0", pic=3, x=200, y=61, w=80, h=80),
    dict(type=TYPE_TXT, objname=b"t1", txt=b"READY", x=313, y=56, w=150, h=32,
         bco=WHITE, pco=BLUE),
    dict(type=TYPE_NUM, objname=b"n3", val=0, x=400, y=120, w=64, h=32, bco=WHITE, pco=BLACK),
    dict(type=TYPE_BTN, objname=b"b_stop", sta=2, pic=10, pic2=10, sendkey=1,
         x=180, y=190, w=98, h=50),
    dict(type=TYPE_BTN, objname=b"b_reset", sta=2, pic=11, pic2=11, sendkey=1,
         x=280, y=190, w=98, h=50),
    dict(type=TYPE_BTN, objname=b"b_home", sta=2, pic=12, pic2=12, sendkey=1,
         codesdown="page 0", x=380, y=190, w=98, h=50),
]


def main():
    print("=" * 78)
    print("生成多页 .HMI 工程（欢迎页 + 分类页 / 14 图 / 真按钮 / 屏内跳页）")
    print("=" * 78)

    # ---- 1. 图片三件套 ----
    missing = [f for f in IMAGE_FILES if not os.path.exists(os.path.join(ASSETS, f))]
    if missing:
        print("缺少素材，请先运行 python scripts/draw_assets.py：")
        for f in missing:
            print("   -", f)
        return 1

    img_members = []
    for n, fn in enumerate(IMAGE_FILES):
        p = os.path.join(ASSETS, fn)
        i_blob, iw, ih = build_i_member(p)
        s_blob, sw, sh = build_png_member(p)
        assert (iw, ih) == (sw, sh), "尺寸不一致: %s" % fn
        img_members.append((b"%d.i" % n, i_blob, TAG_I))
        img_members.append((b"%d.is" % n, s_blob, TAG_IS))
        img_members.append((b"%d.ib" % n, s_blob, TAG_IB))
    print("[img] %d 张图 -> %d 个成员" % (len(IMAGE_FILES), len(img_members)))

    # ---- 2. 页面 ----
    pa0 = P.build_page(PAGE0_WIDGETS, page_no=0)
    pa1 = P.build_page(PAGE1_WIDGETS, page_no=1)
    for tag, pa, n in (("0.pa", pa0, len(PAGE0_WIDGETS)), ("1.pa", pa1, len(PAGE1_WIDGETS))):
        ok = P.page_checksum(pa) == struct.unpack_from("<I", pa, 0)[0]
        pname = pa[0x18:0x1E].rstrip(b"\x00").decode()
        print("[%s] 页名=%r 控件=%d 长度=%d 校验=%s"
              % (tag, pname, n, len(pa), "OK" if ok else "FAIL"))

    # ---- 3. 按钮断言：sta / pic / 事件行结构 ----
    g0 = P.decode_groups(pa0)
    bs = dict(g0[2][1])
    assert bs["objname"] == b"b_start" and bs["type"] == bytes([0x62])
    assert bs["sta"] == bytes([2]), "sta != 2（会被当色块模式，pic 被忽略）"
    assert bs["pic"] == struct.pack("<H", 9)
    assert "codesdown-1" in bs and "page 1" in bs, "事件槽/代码行结构不对"
    print("[btn] b_start: sta=2 pic=9 codesdown-1 + 代码行 'page 1'  OK")
    bh = dict(P.decode_groups(pa1)[13][1])
    assert bh["objname"] == b"b_home" and bh["sta"] == bytes([2])
    assert "codesdown-1" in bh and "page 0" in bh, "事件槽/代码行结构不对"
    print("[btn] b_home : sta=2 pic=12 codesdown-1 + 代码行 'page 0'  OK")

    # ---- 4. main.HMI 清单（只登记 .i / .zi / .pa）----
    name_entries = [(b"i", b"%d.i" % n) for n in range(len(IMAGE_FILES))]
    name_entries += [(b"zi", b"0.zi"), (b"pa", b"0.pa"), (b"pa", b"1.pa")]
    mhmi = build_main_hmi(name_entries, TRUTH_MAIN)
    print("[main.HMI] 长度=%d 名字表=%d条  +0x24=%d"
          % (len(mhmi), struct.unpack_from("<I", mhmi, 0x1C)[0],
             struct.unpack_from("<I", mhmi, 0x24)[0]))

    # ---- 5. 容器组装 ----
    # ⚠ 字库 0.zi 必须实际存在，否则编译报「font 初始值无效:字库ID无效」。
    #   最省事的做法是整块借用其他工程现成的合法 .zi（放 reference/ 下）。
    zi_path = os.path.join(ROOT, "reference", "ascii.zi")
    if not os.path.exists(zi_path):
        print("\n[警告] 缺少字库 %s —— 工程会缺少 0.zi 成员，" % zi_path)
        print("       上位机编译将报「font 初始值无效:字库ID无效」。")
        print("       请从任一已有工程导出合法字库放入该路径，或在下面跳过 0.zi 条目。")
        return 1
    zi = open(zi_path, "rb").read()

    entries = [(b"Program.s", PROGRAM_S.encode("gbk"), TAG_TEXT),
               (b"0.pa", pa0, TAG_PA),
               (b"1.pa", pa1, TAG_PA)]
    entries += img_members
    entries += [(b"0.zi", zi, TAG_ZI), (b"main.HMI", mhmi, TAG_TEXT)]

    path = os.path.join(OUT, "sorter.HMI")
    open(path, "wb").write(build_container(entries))
    ok = selfcheck_container(path)

    print()
    truth_ok = regress_truth_clone()

    if ok and truth_ok is not False:
        print("\n已生成：%s（%d 字节）" % (path, os.path.getsize(path)))
        print("下一步：上位机打开 → 编译 → 下载；接屏前可先跑 scripts/tjc_sim.py 验证指令。")
        return 0
    print("\n自检未通过，请勿交付！")
    return 1


if __name__ == "__main__":
    sys.exit(main())
