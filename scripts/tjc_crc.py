# -*- coding: utf-8 -*-
"""
tjc_crc.py —— 淘晶驰自定义 CRC32 实现

两种变体，都是 MSB-first（左移）查表法、多项式 0x04C11DB7、无反射、无最终异或，
与标准 zlib.crc32 不兼容：

  tjc_crc32(data, init)  —— 逐字节，用于 `.pa` 头部校验值 / `main.HMI` 与各成员头部
  crc7950(crc, buf)      —— 逐 32 位字（小端），用于 CFS 目录表，且需附加盐 "ADEC"

查表值 TAB 由多项式 0x04C11DB7 现场生成，与上位机内嵌表逐项一致（已核对 256/256）。
因此本库不依赖任何上位机 DLL 文件。
"""
import struct

_POLY = 0x04C11DB7


def _build_tab256():
    t = []
    for i in range(256):
        c = i << 24
        for _ in range(8):
            c = ((c << 1) ^ _POLY) & 0xFFFFFFFF if (c & 0x80000000) else (c << 1) & 0xFFFFFFFF
        t.append(c)
    return t


TAB256 = _build_tab256()


def tjc_crc32(data, init=0xFFFFFFFF):
    """逐字节 CRC32（淘晶驰 `Kuozhan.getcrc` 等价实现）。"""
    c = init & 0xFFFFFFFF
    for b in data:
        c ^= b
        for _ in range(4):
            c = ((c << 8) & 0xFFFFFFFF) ^ TAB256[(c >> 24) & 0xFF]
    return c


def crc7950(crc, buf):
    """逐 32 位字 CRC32（CFS 目录表用）。buf 长度应为 4 的倍数。"""
    for i in range(0, len(buf), 4):
        crc ^= int.from_bytes(buf[i:i + 4], "little")
        for _ in range(4):
            crc = ((crc << 8) & 0xFFFFFFFF) ^ TAB256[(crc >> 24) & 0xFF]
    return crc


DIR_SALT = b"ADEC"


def dir_crc(count_plus_entries):
    """CFS 目录 CRC = crc7950(0xFFFFFFFF, count+entries) 再累积盐 b"ADEC"。"""
    return crc7950(crc7950(0xFFFFFFFF, count_plus_entries), DIR_SALT)


def parse_tab_from_dll(path, offset=0x9A00 + (0xBE60 - 0xB000)):
    """（仅用于复核）从上位机 DLL 中提取内嵌表，与生成的 TAB256 比对。"""
    b = open(path, "rb").read()
    return list(struct.unpack_from("<256I", b, offset))


if __name__ == "__main__":
    assert TAB256[0] == 0x00000000 and TAB256[1] == 0x04C11DB7
    print("TAB256 自检通过：TAB[0]=0x%08X TAB[1]=0x%08X" % (TAB256[0], TAB256[1]))
