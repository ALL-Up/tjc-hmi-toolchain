# -*- coding: utf-8 -*-
"""
pa_codec_v5.py —— 严格按「上位机真值」实现的 .pa 编码器

真值来源：sorter1.HMI（用户在上位机拖入 文本/数字/图片 三个控件后保存）
          提取出 out/truth_controls.pa (3096 B)

核心修正（v4 -> v5）：
  1. **控件组头不是 att-28**：文本/数字 = att-39，图片 = att-22
     数字 = 该对象的属性个数（含 att 自身？不，= 后续属性条数 + 1）
  2. 控件属性列表与页面**完全不同**，见 TEXT_ATTRS / NUM_ATTRS / PIC_ATTRS
  3. 控件只有 2 个事件槽：codesdown-0 / codesup-0（页面有 5 个）
  4. id 递增：page=0, t0=1, n0=2, p0=3 ...
  5. 控件 vscope = 0
  6. 取值：bco=0xFFFF(未设) / picc=0xFFFF / pic=0xFFFF / pco=0
"""
import struct

# --- 文件级 ---------------------------------------------------------------
PA_HEAD_LEN = 0x44
NAME_FIELD = 16
TAIL_PAD = b"\x00\x00\x00\x00"

# --- 淘晶驰自定义 CRC32（来自 hmiapp_old.Kuozhan 反编译真值）--------------
# 算法：MSB-first 查表法，多项式 0x04C11DB7（标准 CRC-32/MPEG-2 无反射）
#   crc ^= byte
#   4 次: crc = (crc<<8) ^ tab256[(crc>>24)&0xFF]
# 查表由 tjc_crc 现场生成（与上位机内嵌表逐项一致），不依赖 DLL。
from tjc_crc import TAB256 as _TAB256, tjc_crc32  # noqa: F401


def page_checksum(pa):
    """
    计算 .pa 头部 +0x00 的校验值（来自 hmiapp_old 反编译真值）：

        crc = tjc_crc32(pa[4:])                      # 段1：第 4 字节起到文件尾
        crc = tjc_crc32(datasize(4B LE), crc)        # 段2：累积 datasize
        crc = tjc_crc32(nobj(4B LE), crc)            # 段3：累积对象数
        crc = tjc_crc32(pagelock(1B), crc)           # 段4：累积 pagelock
        crc = tjc_crc32(mark(1B), crc)               # 段5：累积 mark(0x55)

    已用真值页(0xAD75A33D)与空白页(0x2364D04F)双样本验证，**逐字节命中**。
    """
    datasize = struct.unpack_from("<I", pa, 0x04)[0]
    nobj = struct.unpack_from("<I", pa, 0x0C)[0]
    pagelock = pa[0x14]
    mark = pa[0x15]
    c = tjc_crc32(pa[4:])
    c = tjc_crc32(struct.pack("<I", datasize), c)
    c = tjc_crc32(struct.pack("<I", nobj), c)
    c = tjc_crc32(bytes([pagelock]), c)
    c = tjc_crc32(bytes([mark]), c)
    return c


# --- 属性值宽度（真值实测）-------------------------------------------------
BYTE_ATTRS = {
    "type", "id", "vscope", "drag", "sendkey", "aph", "effect",
    "first", "lockobj", "up", "down", "left", "right", "sta",
    "style", "key", "borderw", "font", "xcen", "ycen", "pw",
    "lenth", "format", "isbr", "spax", "spay",
}
WORD_ATTRS = {
    "movex", "movey", "x", "y", "w", "h", "endx", "endy",
    "time", "bco", "pic", "borderc", "picc", "pco", "txt_maxl",
    "pic2", "picc2", "bco2", "pco2",
}
DWORD_ATTRS = {"groupid0", "groupid1", "val"}
RAW_ATTRS = {"objname", "txt", "txts"}

# --- 页面属性（att-28，34 条记录）------------------------------------------
PAGE_ATTRS = [
    "type", "id", "objname", "vscope", "drag", "sendkey", "aph",
    "movex", "movey", "x", "y", "w", "h", "endx", "endy",
    "effect", "first", "time", "lockobj", "groupid0", "groupid1",
    "up", "down", "left", "right", "sta", "bco", "pic",
]
PAGE_SLOTS = ["codesload-0", "codesloadend-0", "codesdown-0",
              "codesup-0", "codesunload-0"]
PAGE_DEFAULTS = {
    "type": 0x79, "id": 0, "objname": b"page0", "vscope": 0, "drag": 0,
    "sendkey": 0, "aph": 0x7F, "movex": 0, "movey": 0,
    "x": 0, "y": 0, "w": 480, "h": 272, "endx": 479, "endy": 271,
    "effect": 0, "first": 0, "time": 300, "lockobj": 0,
    "groupid0": 0, "groupid1": 0,
    "up": 0xFF, "down": 0xFF, "left": 0xFF, "right": 0xFF,
    "sta": 1, "bco": 0xFFFF, "pic": 0xFFFF,
}

# --- 文本控件（att-39，42 条记录）------------------------------------------
TEXT_ATTRS = [
    "type", "id", "objname", "vscope", "drag", "sendkey", "aph",
    "movex", "movey", "x", "y", "w", "h", "endx", "endy",
    "effect", "first", "time", "lockobj", "groupid0", "groupid1",
    "sta", "style", "key", "borderc", "borderw", "font",
    "bco", "picc", "pic", "pco", "xcen", "ycen", "pw",
    "txt", "txt_maxl", "isbr", "spax", "spay",
]
TEXT_DEFAULTS = {
    "type": 0x74, "vscope": 0, "drag": 0, "sendkey": 0, "aph": 0x7F,
    "movex": 0, "movey": 0, "effect": 0, "first": 0, "time": 300,
    "lockobj": 0, "groupid0": 0, "groupid1": 0,
    "sta": 1, "style": 0, "key": 0xFF,
    "borderc": 0x0000, "borderw": 2, "font": 0,
    "bco": 0xFFFF, "picc": 0xFFFF, "pic": 0xFFFF, "pco": 0x0000,
    "xcen": 1, "ycen": 1, "pw": 0,
    "txt": b"", "txt_maxl": 10, "isbr": 0, "spax": 0, "spay": 0,
}

# --- 数字控件（att-39，42 条记录）------------------------------------------
NUM_ATTRS = [
    "type", "id", "objname", "vscope", "drag", "sendkey", "aph",
    "movex", "movey", "x", "y", "w", "h", "endx", "endy",
    "effect", "first", "time", "lockobj", "groupid0", "groupid1",
    "sta", "style", "key", "borderc", "borderw", "font",
    "bco", "picc", "pic", "pco", "xcen", "ycen",
    "val", "lenth", "format", "isbr", "spax", "spay",
]
NUM_DEFAULTS = {
    "type": 0x36, "vscope": 0, "drag": 0, "sendkey": 0, "aph": 0x7F,
    "movex": 0, "movey": 0, "effect": 0, "first": 0, "time": 300,
    "lockobj": 0, "groupid0": 0, "groupid1": 0,
    "sta": 1, "style": 0, "key": 0xFF,
    "borderc": 0x0000, "borderw": 2, "font": 0,
    "bco": 0xFFFF, "picc": 0xFFFF, "pic": 0xFFFF, "pco": 0x0000,
    "xcen": 1, "ycen": 1,
    "val": 0, "lenth": 0, "format": 0, "isbr": 1, "spax": 0, "spay": 0,
}

# --- 图片控件（att-22，25 条记录）------------------------------------------
PIC_ATTRS = [
    "type", "id", "objname", "vscope", "drag", "sendkey", "aph",
    "movex", "movey", "x", "y", "w", "h", "endx", "endy",
    "effect", "first", "time", "lockobj", "groupid0", "groupid1",
    "pic",
]
PIC_DEFAULTS = {
    "type": 0x70, "vscope": 0, "drag": 0, "sendkey": 0, "aph": 0x7F,
    "movex": 0, "movey": 0, "effect": 0, "first": 0, "time": 300,
    "lockobj": 0, "groupid0": 0, "groupid1": 0,
    "pic": 0xFFFF,
}

# --- 按钮控件（att-42，45 条记录）—— 真值来源：用户在编辑器 page0 手拖按钮（2026-09-20）---
BTN_ATTRS = [
    "type", "id", "objname", "vscope", "drag", "sendkey", "aph",
    "movex", "movey", "x", "y", "w", "h", "endx", "endy",
    "effect", "first", "time", "lockobj", "groupid0", "groupid1",
    "sta", "style", "borderc", "borderw", "font",
    "pic", "picc", "bco", "pic2", "picc2", "bco2", "pco", "pco2",
    "xcen", "ycen", "val", "txt", "txt_maxl", "isbr", "spax", "spay",
]
BTN_DEFAULTS = {
    "type": 0x62, "vscope": 0, "drag": 0, "sendkey": 0, "aph": 0x7F,
    "movex": 0, "movey": 0, "effect": 0, "first": 0, "time": 300,
    "lockobj": 0, "groupid0": 0, "groupid1": 0,
    "sta": 1, "style": 4, "borderc": 0x0000, "borderw": 2, "font": 0,
    "pic": 0xFFFF, "picc": 0xFFFF, "bco": 0xC618,
    "pic2": 0xFFFF, "picc2": 0xFFFF, "bco2": 0x0400,
    "pco": 0x0000, "pco2": 0xFFFF,
    "xcen": 1, "ycen": 1,
    "val": 0, "txt": b"", "txt_maxl": 10, "isbr": 0, "spax": 0, "spay": 0,
}
# 按钮的 val 是 1 字节（数字控件 val 是 4 字节 DWORD）—— 真值 vlen=1 实测
BTN_WIDTH_OVER = {"val": "<B"}

# 控件事件槽只有 2 个
WIDGET_SLOTS = ["codesdown-0", "codesup-0"]

# 组件类型 -> (属性表, 默认值, 组头属性数, 宽度覆盖表)
# 真值实测：
#   0x74 't' 文本 -> att-39
#   0x36 '6' 数字 -> att-39   （不是 0x6E！）
#   0x70 'p' 图片 -> att-22
#   0x62 'b' 按钮 -> att-42   （双态：pic/pic2 bco/bco2 pco/pco2）
WIDGET_KINDS = {
    0x74: (TEXT_ATTRS, TEXT_DEFAULTS, 39, {}),
    0x36: (NUM_ATTRS, NUM_DEFAULTS, 39, {}),
    0x70: (PIC_ATTRS, PIC_DEFAULTS, 22, {}),
    0x62: (BTN_ATTRS, BTN_DEFAULTS, 42, BTN_WIDTH_OVER),
}


def encode_val(key, v, over=None):
    if isinstance(v, (bytes, bytearray)):
        return bytes(v)
    if isinstance(v, str):
        return v.encode("ascii")
    if over and key in over:
        fmt = over[key]
        return struct.pack(fmt, v & _mask(fmt))
    if key in BYTE_ATTRS:
        return struct.pack("<B", v & 0xFF)
    if key in WORD_ATTRS:
        return struct.pack("<H", v & 0xFFFF)
    if key in DWORD_ATTRS:
        return struct.pack("<I", v & 0xFFFFFFFF)
    raise ValueError("unknown width for %r" % key)


def _mask(fmt):
    return {"<B": 0xFF, "<H": 0xFFFF, "<I": 0xFFFFFFFF}[fmt]


def emit(name, value=b"", padded=True):
    nb = name.encode("ascii")
    payload = (nb.ljust(NAME_FIELD, b"\x00") if padded else nb) + (value or b"")
    return struct.pack("<I", len(payload)) + payload


def emit_group(header, attr_list, attrs, slots, over=None):
    """生成一个对象组。header 如 'att-28' / 'att-39' / 'att-22' / 'att-42'

    真值实测（三处铁证）：
      - 'att-28' plen = 6  （不补齐）
      - 事件槽 'codesdown-0' plen = 11（不补齐）
      - 组尾恒有 4 个 NUL 字节
    即：只有当名称短于 16 字节时**才补齐到 16**，名称本身 ≥16 字节时原样。

    slots：元素为 str（空槽 "codesdown-0"）或 (name, code)。
    ✅ 事件代码真值格式（2026-09-20 双样本定案：用户补写事件保存版 + main.HMI 第三方按钮）：
       - **槽名后缀 = 代码行数**：codesdown-0=0 行；有 1 行代码 → codesdown-1，
         代码行是独立纯名记录（plen=len(行文本)，无 NUL 无换行）紧跟槽标记后；
       - 槽顺序：codesdown-<n> → 其代码行们 → codesup-<n> → 其代码行们；
       - main.HMI 第三方按钮按下事件写 page 1（跳页用按下事件，跟真值）。
    """
    out = bytearray()
    out += emit(header, padded=False)
    for k in attr_list:
        if k not in attrs:
            raise KeyError("group missing %r" % k)
        out += emit(k, encode_val(k, attrs[k], over))
    for s in slots:
        if isinstance(s, tuple):
            nm, code = s                            # nm 形如 "codesdown"
            text = code.decode("gbk") if isinstance(code, (bytes, bytearray)) else code
            lines = [ln.strip() for ln in text.replace("\r\n", "\n").split("\n") if ln.strip()]
            out += emit("%s-%d" % (nm, len(lines)), padded=False)
            for ln in lines:
                out += emit(ln, padded=False)       # 代码行 = 独立纯名记录
        else:
            out += emit(s, padded=False)
    out += b"\x00\x00\x00\x00"       # 组尾 4 个 NUL
    return bytes(out)


def build_page(widgets, page_over=None, page_no=0):
    """
    真值结构（sorter1.HMI 的 0.pa，3096 B）：
      0x00..0x43  头部 0x44 字节
      0x44..0x67  控件索引：3 项 × 12 字节 [组相对偏移+12, 组长度, 0]
      0x68..      组数据（页面组 + 各控件组，首尾相接）
      末尾 4 个 NUL

    索引项 = 每个控件组一条；组相对偏移以 0x44 为基准。
    page_no：页号（0 → 页名 "page0"、+0x1C 低字节 '0'；1 → "page1"）
    """
    # 1) 先生成各组
    groups = []
    # 页面组
    pa = dict(PAGE_DEFAULTS)
    if page_over:
        pa.update(page_over)
    pa["id"] = 0
    pg_slots = []
    for s in PAGE_SLOTS:
        short = s.split("-")[0]                # codesload-0 -> codesload
        key = short
        if page_over and key in page_over:
            pg_slots.append((short, page_over[key]))
        else:
            pg_slots.append(s)
    groups.append(emit_group("att-28", PAGE_ATTRS, pa, pg_slots))

    # 控件组（id 从 1 递增）
    for idx, w in enumerate(widgets, start=1):
        t = w["type"]
        attr_list, defaults, nattr, over = WIDGET_KINDS[t]
        a = dict(defaults)
        a.update(w)
        a["id"] = idx
        a["endx"] = a["x"] + a["w"] - 1
        a["endy"] = a["y"] + a["h"] - 1
        if "txt" in a and isinstance(a["txt"], str):
            a["txt"] = a["txt"].encode("gbk")
        # txt_maxl 必须 ≥ txt 实际长度，否则编辑器报「objedit ref error! 参数无效」
        if "txt" in a:
            a["txt_maxl"] = max(a.get("txt_maxl", 10), len(a["txt"]))
        # 事件代码：widget dict 里 codesdown / codesup（短名，行数由 emit_group 编号）
        slots = []
        for s in WIDGET_SLOTS:
            short = s.split("-")[0]                # codesdown-0 -> codesdown
            v = w.get(short) or w.get(short + "_0")
            if v:
                slots.append((short, v))
            else:
                slots.append(s)
        groups.append(emit_group("att-%d" % nattr, attr_list, a, slots, over))

    # 2) 索引块（只含控件组，不含页面组）
    #    索引项 = [组起始相对偏移(基准 0x44) + 12, 组长度, 0]
    #    组相对偏移 = 索引块长度 + 页面组长度 + 前面控件组长度之和
    INDEX_BASE = 0x44
    INDEX_ENTRY = 12
    index_size = INDEX_ENTRY * len(groups[1:])
    index = bytearray()
    cursor = index_size + len(groups[0])   # 索引块自身 + 页面组
    for g in groups[1:]:
        index += struct.pack("<III", cursor + INDEX_ENTRY, len(g), 0)
        cursor += len(g)

    # 3) 组装（组自带尾部 NUL，此处不再额外补）
    body = bytes(index) + b"".join(groups)
    total = PA_HEAD_LEN + len(body)

    hdr = bytearray(PA_HEAD_LEN)
    struct.pack_into("<I", hdr, 0x00, 0)                  # 校验值，稍后回填
    struct.pack_into("<I", hdr, 0x04, total)
    struct.pack_into("<I", hdr, 0x08, 0x38)
    struct.pack_into("<I", hdr, 0x0C, len(widgets) + 1)
    struct.pack_into("<I", hdr, 0x10, 0)
    struct.pack_into("<I", hdr, 0x14, 0x00215500)
    hdr[0x18:0x1C] = b"page"
    struct.pack_into("<I", hdr, 0x1C, 0x30 + page_no)     # 页名第5字节：'0'+page_no
    struct.pack_into("<I", hdr, 0x28, 0x02014401)
    struct.pack_into("<I", hdr, 0x38, 12 * (len(widgets) + 1))   # = 12×nobj（空白页0x0C / sorter1 4对象0x30 实测规律）
    struct.pack_into("<I", hdr, 0x3C, 701)
    struct.pack_into("<I", hdr, 0x40, 0)
    pa = bytes(hdr) + body
    # 回填校验值（上位机硬校验，缺了会报「资源文件受损」）
    ck = page_checksum(pa)
    pa = struct.pack("<I", ck) + pa[4:]
    return pa


def parse_header(pa):
    """回读 .pa 头部关键字段，用于自检。"""
    (ck,) = struct.unpack_from("<I", pa, 0x00)
    (tot,) = struct.unpack_from("<I", pa, 0x04)
    (f08,) = struct.unpack_from("<I", pa, 0x08)
    (nobj,) = struct.unpack_from("<I", pa, 0x0C)
    (f14,) = struct.unpack_from("<I", pa, 0x14)
    (f1C,) = struct.unpack_from("<I", pa, 0x1C)
    (f38,) = struct.unpack_from("<I", pa, 0x38)
    (f3C,) = struct.unpack_from("<I", pa, 0x3C)
    return {
        "checksum": "0x%08X" % ck,
        "total_size": tot,
        "actual_len": len(pa),
        "len_ok": tot == len(pa),
        "f08": "0x%08X" % f08,
        "nobj": nobj,
        "f14": "0x%08X" % f14,
        "f1C": "0x%08X" % f1C,
        "f38": "0x%08X" % f38,
        "f3C": f3C,
    }


def decode_groups(pa):
    """
    把 .pa 解码为 [(header_name, {attr: raw_value}), ...]，用于自检。

    布局（真值实测）：
      0x00..0x43  头部 0x44 字节
      0x44..     控件索引块：每控件 12 字节 [组相对偏移+12, 组长度, 0]
      其后       组数据：**页面组在前**，随后依次是各控件组
    页面组起点 = 0x44 + 12*控件数
    """
    (nobj,) = struct.unpack_from("<I", pa, 0x0C)
    nw = max(0, nobj - 1)
    start = PA_HEAD_LEN + 12 * nw
    groups = []
    cur = None
    o = start
    while o + 4 <= len(pa):
        (plen,) = struct.unpack_from("<I", pa, o)
        if plen == 0:
            # 组尾 4 个 NUL —— 跳到下一组的 4 字节边界
            o += 4
            if o + 4 > len(pa):
                break
            (plen2,) = struct.unpack_from("<I", pa, o)
            if plen2 == 0:
                break
            continue
        payload = pa[o + 4:o + 4 + plen]
        nm = payload[:16].split(b"\x00")[0].decode("ascii", "replace") if plen > 16 else \
            payload.split(b"\x00")[0].decode("ascii", "replace")
        val = payload[16:] if plen > 16 else b""
        if nm.startswith("att-"):
            cur = (nm, {})
            groups.append(cur)
        elif cur is not None:
            cur[1][nm] = val
        o += 4 + plen
    return groups


def verify_against_truth(truth_path):
    """用真值文件反向验证：解码后再按本模块重建，应逐字节相同。"""
    pa = open(truth_path, "rb").read()
    # 直接按组重建
    STARTS = []
    o = 0
    while True:
        o = pa.find(b"att-", o)
        if o < 0:
            break
        STARTS.append(o - 4)
        o += 1
    groups = []
    for si, s in enumerate(STARTS):
        end = STARTS[si + 1] if si + 1 < len(STARTS) else len(pa)
        recs = []
        p = s
        while p + 4 <= end:
            (plen,) = struct.unpack_from("<I", pa, p)
            if plen == 0:
                break
            payload = pa[p + 4:p + 4 + plen]
            k = payload.find(b"\x00")
            nm = payload[:k].decode("ascii") if k >= 0 else payload.decode("ascii")
            val = payload[16:] if plen > 16 else b""
            recs.append((nm, val, plen))
            p += 4 + plen
        groups.append(recs)
    return groups
