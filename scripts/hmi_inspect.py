# -*- coding: utf-8 -*-
"""
hmi_inspect.py —— .HMI 工程通用检查器（逆向/调试期高频动作三合一）
用法：
    python hmi_inspect.py <file.HMI>                # 成员表 + main.HMI 名字表 + 页面组摘要
    python hmi_inspect.py <file.HMI> 0.pa           # 只打印指定页
    python hmi_inspect.py <file.HMI> 0.pa full      # 附带该页全部属性（含默认值）
    python hmi_inspect.py <file.HMI> --mcu          # 追加 MCU 侧指令骨架 + 触摸包对照
                                                    # （工作流第 5 步「给 MCU 指令」的自动化）
诊断动作覆盖：
  1. CFS v2 容器成员表（名称/偏移/大小/tag）——tag 应为类型常数
  2. main.HMI 尾部名字表（.i/.zi/.pa 条目，图片是否登记在此 = 画布能否渲染的关键）
  3. .pa 页面组结构（组头 att-NN / 控件类型 / objname / 坐标 / 事件代码**内容**）
  4. --mcu：把控件翻译成 <obj>.txt=/.val=/.pic= 模板与 0x65 触摸包对照表
"""
import struct
import sys
import ctypes

TYPE_NAME = {0x79: "页面", 0x74: "文本", 0x36: "数字", 0x70: "图片", 0x62: "按钮"}


def load(path):
    """普通读失败时用共享读绕过上位机独占锁定（FILE_SHARE_READ|WRITE|DELETE）。"""
    try:
        return open(path, "rb").read()
    except PermissionError:
        k32 = ctypes.windll.kernel32
        k32.CreateFileW.restype = ctypes.c_void_p
        h = k32.CreateFileW(path, 0x80000000, 1 | 2 | 4, None, 3, 0, None)
        if h in (0, 0xFFFFFFFFFFFFFFFF):
            raise
        try:
            size = k32.GetFileSize(ctypes.c_void_p(h), None)
            buf = ctypes.create_string_buffer(size)
            got = ctypes.c_ulong(0)
            k32.ReadFile(ctypes.c_void_p(h), buf, size, ctypes.byref(got), None)
            return buf.raw[:got.value]
        finally:
            k32.CloseHandle(ctypes.c_void_p(h))


def parse_members(b):
    count = struct.unpack_from("<I", b, 0)[0]
    members = {}
    for i in range(count):
        e = 4 + 28 * i
        off, size, tag = struct.unpack_from("<III", b, e + 16)
        name = b[e:e + 16].rstrip(b"\x00").decode("ascii", "replace")
        members[name] = (off, size, tag)
    return members


def dump_nametable(b, members):
    if "main.HMI" not in members:
        print("(无 main.HMI 成员)")
        return
    off, size, _ = members["main.HMI"]
    m = b[off:off + size]
    n = struct.unpack_from("<I", m, 0x1C)[0]
    pages = struct.unpack_from("<I", m, 0x24)[0]
    print("main.HMI: %dB  名字表=%d条  +0x24=%d" % (size, n, pages))
    nt = size - 16 * n
    for i in range(n):
        e = m[nt + 16 * i: nt + 16 * (i + 1)]
        print("  [%2d] %-17s | %s" % (i, e[:8].hex(" "),
                                      e[8:].rstrip(b"\x00").decode("ascii", "replace")))


def parse_groups(pa):
    groups = []
    nobj = struct.unpack_from("<I", pa, 0x0C)[0]
    pos = 0x44 + 12 * max(0, nobj - 1)
    while pos + 4 <= len(pa):
        plen = struct.unpack_from("<I", pa, pos)[0]
        if plen == 0:
            pos += 4
            continue
        recs = []
        while pos + 4 <= len(pa):
            pl2 = struct.unpack_from("<I", pa, pos)[0]
            if pl2 == 0:
                pos += 4
                break
            py = pa[pos + 4: pos + 4 + pl2]
            key = py.split(b"\x00")[0].decode("ascii", "replace")
            val = py[16:] if pl2 > 16 else (py[len(key):] if pl2 > len(key) else b"")
            recs.append((key, val))
            pos += 4 + pl2
        groups.append(recs)
    return groups


def dump_pa(b, members, paname, full=False):
    if paname not in members:
        print("(无 %s 成员)" % paname)
        return
    off, size, tag = members[paname]
    pa = b[off:off + size]
    nobj = struct.unpack_from("<I", pa, 0x0C)[0]
    pname = pa[0x18:0x1E].rstrip(b"\x00").decode("ascii", "replace")
    print("%s: %dB  nobj=%d  页名=%r  +0x38=0x%X(应=12×nobj)  tag=0x%08X"
          % (paname, size, nobj, pname,
             struct.unpack_from("<I", pa, 0x38)[0], tag))
    for g in parse_groups(pa):
        attrs = dict(g)
        head = g[0][0]
        t = attrs.get("type", b"")
        tc = t[0] if t else 0
        obj = attrs.get("objname", b"?")
        if head == "att-28":
            print("  [%s] 页面" % head)
        else:
            # 接 MCU 时最关心的三个字段：文本长度上限 / 数字当前值 / 会不会自动上报
            extra = ""
            if tc == 0x74:                                  # 文本
                extra = " txt_maxl=%d pco=%d" % (
                    struct.unpack("<H", attrs.get("txt_maxl", b"\x00\x00"))[0],
                    struct.unpack("<H", attrs.get("pco", b"\x00\x00"))[0])
            elif tc == 0x36:                                # 数字
                extra = " val=%d" % struct.unpack(
                    "<I", attrs.get("val", b"\x00\x00\x00\x00"))[0]
            elif tc == 0x62:                                # 按钮
                extra = " sendkey=%d" % struct.unpack(
                    "<B", attrs.get("sendkey", b"\x00"))[0]
            print("  [%s] %s objname=%r id=%s pos=(%s,%s %sx%s) pic=%s sta=%s%s" % (
                head, TYPE_NAME.get(tc, hex(tc)), obj,
                struct.unpack("<B", attrs.get("id", b"\x00"))[0],
                struct.unpack("<H", attrs.get("x", b"\x00\x00"))[0],
                struct.unpack("<H", attrs.get("y", b"\x00\x00"))[0],
                struct.unpack("<H", attrs.get("w", b"\x00\x00"))[0],
                struct.unpack("<H", attrs.get("h", b"\x00\x00"))[0],
                struct.unpack("<H", attrs.get("pic", b"\xff\xff"))[0],
                attrs.get("sta", b"?").hex(), extra))
        # 事件区：槽名记录 + 紧随的代码行记录
        # 槽名后缀 = 该槽代码行数（codesup-0 = 空，codesup-1 = 1 行）；
        # 代码行本身是紧跟其后的独立记录（plen = 行文本长度，纯名记录）。
        # 直接把内容打出来 —— 不知道哪个按钮跳哪一页，MCU 侧就没法对齐。
        for i, (key, val) in enumerate(g):
            if key.startswith("codes"):
                suffix = key.rsplit("-", 1)[-1]
                try:
                    nline = int(suffix)
                except ValueError:
                    nline = 0
                if nline:
                    rows = [g[i + 1 + j][0] for j in range(nline)
                            if i + 1 + j < len(g)]
                    print("      %s -> %s" % (key, " ; ".join(rows)))
        if full:
            for key, val in g:
                if not key.startswith("codes"):
                    print("      %-14s %s" % (key, val.hex(" ") if val else "0"))


def dump_mcu(b, members, targets):
    """输出 MCU 侧可直接抄进 C 代码的寻址表 + 指令模板 + 触摸包对照。

    这是工作流第 5 步「给 MCU 指令」的自动化：逐个页面把控件翻译成
        <对象名>.txt= / .val= / .pic=        （MCU -> 屏）
        0x65 <页> <控件> <事件> FF FF FF      （屏 -> MCU）
    注意末尾 3 个 0xFF 是铁律，模板里已标注。
    """
    print("\n=== MCU 侧指令骨架（TJC 指令 + 3 个 0xFF；参数只能十进制）===")
    btns = []
    for pn in targets:
        if pn not in members:
            continue
        off, size, _ = members[pn]
        pa = b[off:off + size]
        pname = pa[0x18:0x1E].rstrip(b"\x00").decode("ascii", "replace")
        try:
            pageno = int(pn.split(".")[0])
        except ValueError:
            pageno = 0
        print("\n-- %s（页名 %s / page 指令用 page %d）--" % (pn, pname, pageno))
        for g in parse_groups(pa):
            attrs = dict(g)
            t = attrs.get("type", b"")
            if not t:
                continue
            tc = t[0]
            obj = attrs.get("objname", b"?").split(b"\x00")[0].decode("ascii", "replace")
            try:
                cid = struct.unpack("<B", attrs.get("id", b"\x00"))[0]
            except struct.error:
                cid = 0
            if tc == 0x74:                       # 文本
                mx = struct.unpack("<H", attrs.get("txt_maxl", b"\x00\x00"))[0]
                cur = attrs.get("txt", b"").rstrip(b"\x00").decode("ascii", "replace")
                print('   %s.txt="<字符串，<= %d 字符>"    # 初值 %r' % (obj, mx, cur))
            elif tc == 0x36:                     # 数字
                print("   %s.val=<整数>                # 必须 .val，.txt 无效" % obj)
            elif tc == 0x70:                     # 图片
                cur = struct.unpack("<H", attrs.get("pic", b"\xff\xff"))[0]
                print("   %s.pic=<图片ID>               # 初值 %d" % (obj, cur))
            elif tc == 0x62:                     # 按钮
                sk = struct.unpack("<B", attrs.get("sendkey", b"\x00"))[0]
                btns.append((pageno, cid, obj, sk))
    if btns:
        print("\n-- 屏 -> MCU 触摸包（sendkey=1 的按钮被触摸时屏自动发出）--")
        for pageno, cid, obj, sk in btns:
            mark = "会发" if sk else "★不会发 sendkey=0，只能靠屏内事件"
            print("   0x65 %-2d %-2d 01 FF FF FF      # %-10s %s"
                  % (pageno, cid, obj, mark))
        print("   （event 01=按下 00=松开；一次点击会发两个包，业务一般只认 01）")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    b = load(sys.argv[1])
    members = parse_members(b)
    print("=== 成员表（count=%d）===" % len(members))
    for n, (o, s, t) in sorted(members.items(), key=lambda kv: kv[1][0]):
        print("  %-10s off=0x%06X size=%-8d tag=0x%08X" % (n, o, s, t))
    print()
    dump_nametable(b, members)

    args = [a for a in sys.argv[2:] if not a.startswith("--")]
    full = "full" in args
    want_mcu = "--mcu" in sys.argv[2:]
    args = [a for a in args if a != "full"]
    targets = args if args else sorted(n for n in members if n.endswith(".pa"))

    for t in targets:
        print()
        dump_pa(b, members, t, full)
    if want_mcu:
        dump_mcu(b, members, targets)


if __name__ == "__main__":
    main()
