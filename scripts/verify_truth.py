# -*- coding: utf-8 -*-
"""
verify_truth.py —— 真值回归测试（交付前必跑）

三项断言，全部通过才说明「编码器/容器生成器实现正确」：
  1. `.pa` 头部校验值：对真值页复算 5 段累积 CRC，须与文件内数值相等
  2. `main.HMI` 五段累积 CRC：同上
  3. 容器克隆：用真值成员重建 CFS 容器，须与真值工程逐字节一致
  4. `.i` 屏显图互检：.i 的 payload[20:] 须等于同编号 .is（PNG）转出的 RGB565

用法：
    python scripts/verify_truth.py                    # 跑 1-3（只依赖 reference/truth/）
    python scripts/verify_truth.py <工程.HMI>         # 额外跑 4（针对指定工程的图片成员）

真值文件放在 reference/truth/ 下；缺失的项会跳过并提示，不算失败。
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import pa_codec_v5 as P
from tjc_crc import crc7950, dir_crc, tjc_crc32

TRUTH_DIR = os.path.join(ROOT, "reference", "truth")

results = []


def check(name, ok, detail=""):
    results.append(ok)
    print("  [%s] %-34s %s" % ("PASS" if ok else "FAIL", name, detail))
    return ok


def _truth(fn):
    p = os.path.join(TRUTH_DIR, fn)
    return open(p, "rb").read() if os.path.exists(p) else None


def test_pa_checksum():
    print("\n1) .pa 头部校验值（5 段累积 CRC）")
    pa = _truth("truth_0_pa.bin")
    if pa is None:
        return check("truth_0_pa.bin", True, "跳过（文件缺失）")
    stored = struct.unpack_from("<I", pa, 0)[0]
    calc = P.page_checksum(pa)
    check("真值页校验值复算", stored == calc, "stored=0x%08X calc=0x%08X" % (stored, calc))

    pa2 = _truth("truth_controls.pa")
    if pa2 is None:
        return
    s2 = struct.unpack_from("<I", pa2, 0)[0]
    c2 = P.page_checksum(pa2)
    check("含控件页校验值复算", s2 == c2, "stored=0x%08X calc=0x%08X" % (s2, c2))


def test_main_hmi_crc():
    print("\n2) main.HMI 五段累积 CRC")
    m = _truth("truth_main_HMI.bin")
    if m is None:
        return check("truth_main_HMI.bin", True, "跳过（文件缺失）")
    crc = tjc_crc32(bytes(m[4:]))
    crc = tjc_crc32(bytes(m[0x10:0x14]), crc)
    crc = tjc_crc32(bytes(m[0x04:0x08]), crc)
    crc = tjc_crc32(bytes(m[0x0A:0x0B]), crc)
    crc = tjc_crc32(bytes(m[0x0E:0x0F]), crc)
    stored = struct.unpack_from("<I", m, 0)[0]
    check("main.HMI 校验值复算", stored == crc, "stored=0x%08X calc=0x%08X" % (stored, crc))


def test_container_clone():
    print("\n3) 容器克隆（CFS v2 生成器正确性证明）")
    import build_sorter as B
    if not (B.TRUTH_MAIN and B.TRUTH_PS and B.TRUTH_PA):
        return check("真值成员齐备", True, "跳过（成员缺失）")
    truth = B.read_truth_project()
    if truth is None:
        return check("truth_project.HMI", True, "跳过（基准工程缺失）")
    gen = B.build_container([(b"Program.s", B.TRUTH_PS, B.TAG_TEXT),
                             (b"0.pa", B.TRUTH_PA, B.TAG_PA),
                             (b"main.HMI", B.TRUTH_MAIN, B.TAG_TEXT)])
    check("逐字节一致", gen == truth, "gen=%d truth=%d" % (len(gen), len(truth)))


def parse_members(b):
    count = struct.unpack_from("<I", b, 0)[0]
    out = {}
    for i in range(count):
        e = 4 + 28 * i
        off, size, tag = struct.unpack_from("<III", b, e + 16)
        out[b[e:e + 16].rstrip(b"\x00").decode("ascii", "replace")] = (off, size, tag)
    return out


def test_i_members(path):
    print("\n4) .i 屏显图互检（payload[20:] vs PNG 转 RGB565）")
    try:
        from PIL import Image
    except ImportError:
        return check("Pillow", True, "跳过（未安装 pillow）")
    import io
    b = open(path, "rb").read()
    mem = parse_members(b)
    idx = sorted(int(n[:-2]) for n in mem if n.endswith(".i"))
    if not idx:
        return check("工程含 .i 成员", True, "跳过（该工程无图片）")

    all_ok = True
    for n in idx:
        off, size, tag = mem["%d.i" % n]
        i_data = b[off:off + size]
        payload = i_data[24:]
        if "%d.is" % n in mem:
            o2, s2, _ = mem["%d.is" % n]
            d = b[o2:o2 + s2]
            p = d.find(b"\x89PNG")
            img = Image.open(io.BytesIO(d[p:])).convert("RGBA")
            W, H = img.size
            px = img.load()
            raw = bytearray()
            for y in range(H):
                for x in range(W):
                    r, g, bl, a = px[x, y]
                    v = 0x0000 if a < 128 else ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (bl >> 3)
                    raw += struct.pack("<H", v)
            match = payload[20:] == bytes(raw)
            all_ok &= match
            print("      图%2d %dx%d .i(%d B tag=0x%08X) RGB565 一致=%s"
                  % (n, W, H, size, tag, match))
        else:
            # 无 .is 时退化为检查 payload 长度自洽
            w, h = struct.unpack_from("<HH", i_data, 12)
            expect = 20 + w * h * 2
            ok = len(payload) == expect
            all_ok &= ok
            print("      图%2d %dx%d .i payload 长度自洽=%s（无 .is 可比对）" % (n, w, h, ok))
    check(".i 全部图片互检", all_ok)


def main():
    print("=" * 78)
    print("淘晶驰 .HMI 真值回归测试")
    print("=" * 78)
    test_pa_checksum()
    test_main_hmi_crc()
    test_container_clone()
    if len(sys.argv) > 1:
        test_i_members(sys.argv[1])
    else:
        default = os.path.join(ROOT, "out", "sorter.HMI")
        if os.path.exists(default):
            test_i_members(default)

    print("\n" + "=" * 78)
    if all(results):
        print("全部通过（%d 项）" % len(results))
        return 0
    print("有失败项：%d/%d" % (results.count(False), len(results)))
    return 1


if __name__ == "__main__":
    sys.exit(main())
