# -*- coding: utf-8 -*-
"""
tjc_sim.py —— 本地模拟验证工具（真实主控接入前使用）

作用：
    1. 把 display_ctrl.c 会发出的指令序列，按字节级（含 3 个 0xFF）打印出来，
       用于肉眼核对协议与控件名。
    2. 用指定串口把整段序列真实发出去，直接喂给串口屏，验证屏幕响应，
       无需 STM32 主控参与。
    3. --capture 模式：监听屏的 TX（若已接 PA3），打印屏回传内容。

用法：
    # 只看指令（不连硬件）
    python tjc_sim.py --dry-run

    # 发到串口屏（把 USB-TTL 的 TX 接屏 RX、GND 共地）
    python tjc_sim.py --port COM5 --scenario full

    # 只发开机画面
    python tjc_sim.py --port COM5 --scenario splash

    # 只发一件分拣结果（序号 3 / 类别 BOTTLE / 累计 3）
    python tjc_sim.py --port COM5 --scenario item --seq 3 --cat 1 --total 3

依赖：pyserial（仅 --port 模式需要）
    <managed venv>/Scripts/pip install pyserial
"""

import argparse
import sys

# ------------------------------------------------------------------ 常量
BAUD_DEFAULT = 9600
END = b"\xff\xff\xff"          # 淘晶驰指令结束符，缺一不可

TJC_BLACK = 0
TJC_GREEN = 2016
TJC_RED = 63488
TJC_WHITE = 65535
TJC_YELLOW = 65504

# 控件对象名（须与 display_ctrl.h 的 SCR_OBJ_* 一致）
SCR_OBJ_TITLE = "main.t0"
SCR_OBJ_NAME = "main.t1"
SCR_OBJ_STATUS = "main.t2"
SCR_OBJ_SEQ = "main.n0"
SCR_OBJ_TOTAL = "main.n1"
SCR_OBJ_IMAGE = "main.p0"

# 货物类别表（须与 display_ctrl.c 的 cat_table 一致）
CAT_TABLE = [
    ("BOTTLE", 0),
    ("CAN", 1),
    ("PAPER", 2),
    ("GLASS", 3),
    ("BATTERY", 4),
    ("OTHER", 5),
]


def cmd(s):
    """把一条指令编码成完整字节流（正文 + 3×0xFF）。"""
    return s.encode("ascii") + END


# ------------------------------------------------------------------ 场景

def scenario_splash():
    """Display_ShowSplash() 的等价指令序列。"""
    return [
        (cmd("page main"), "跳转到 main 页"),
        (cmd('%s.txt="SMART SORTER"' % SCR_OBJ_TITLE), "标题"),
        (cmd("%s.pco=%d" % (SCR_OBJ_TITLE, TJC_WHITE)), "标题色=白"),
        (cmd("%s.val=0" % SCR_OBJ_SEQ), "序号清零"),
        (cmd('%s.txt="READY"' % SCR_OBJ_NAME), "名称区"),
        (cmd("%s.pic=0" % SCR_OBJ_IMAGE), "默认图片"),
        (cmd("%s.val=0" % SCR_OBJ_TOTAL), "累计清零"),
        (cmd('%s.txt="PRESS KEY"' % SCR_OBJ_STATUS), "状态行"),
        (cmd("%s.pco=%d" % (SCR_OBJ_STATUS, TJC_GREEN)), "状态色=绿"),
    ]


def scenario_item(seq, cat, total):
    """Display_ShowItem() 的等价指令序列（四要素一次刷出）。"""
    idx = cat - 1 if 1 <= cat <= len(CAT_TABLE) else len(CAT_TABLE) - 1
    name, pic = CAT_TABLE[idx]
    return [
        (cmd("%s.val=%d" % (SCR_OBJ_SEQ, seq)), "① 序号 -> %d" % seq),
        (cmd('%s.txt="%s"' % (SCR_OBJ_NAME, name)), "② 货物名称 -> %s" % name),
        (cmd("%s.pic=%d" % (SCR_OBJ_IMAGE, pic)), "③ 货物图片 -> ID %d" % pic),
        (cmd("%s.val=%d" % (SCR_OBJ_TOTAL, total)), "④ 累计数量 -> %d" % total),
    ]


def scenario_full(max_items=6):
    """完整一轮：开机画面 + 逐件结果 + 结束状态。"""
    out = []
    out.append(("# 开机 / 界面复位", scenario_splash()))
    for i in range(1, max_items + 1):
        cat = (i - 1) % len(CAT_TABLE) + 1
        out.append(("# 第 %d 件（类别 %d / %s）"
                    % (i, cat, CAT_TABLE[cat - 1][0]),
                    scenario_item(i, cat, i)))
    out.append(("# 全部完成",
                [(cmd('%s.txt="ALL DONE"' % SCR_OBJ_STATUS), "状态行"),
                 (cmd("%s.pco=%d" % (SCR_OBJ_STATUS, TJC_GREEN)), "状态色=绿")]))
    out.append(("# 超时演示",
                [(cmd("%s.pco=%d" % (SCR_OBJ_STATUS, TJC_RED)), "状态色=红"),
                 (cmd('%s.txt="TIMEOUT"' % SCR_OBJ_STATUS), "状态行")]))
    return out


# ------------------------------------------------------------------ 输出

def dump(groups, show_hex=True):
    """打印指令序列（文本 + 字节）。"""
    total = 0
    for title, cmds in groups:
        print(title)
        for blob, desc in cmds:
            total += len(blob)
            txt = blob[:-3].decode("ascii", "replace")
            print("   %-30s  %-40s  %2d B"
                  % (txt, desc, len(blob)))
            if show_hex:
                print("       %s" % " ".join("%02X" % b for b in blob))
        print()
    print("合计 %d 条指令 / %d 字节" % (
        sum(len(c) for _, cs in groups for c in cs), total))
    if total:
        # 9600 8N1 = 10 bit/byte
        secs = total * 10 / BAUD_DEFAULT
        print("在 %d bps 下约需 %.0f ms 才能发完（可用于估算显示延迟）"
              % (BAUD_DEFAULT, secs * 1000))


def send(groups, port, baud, delay):
    try:
        import serial          # pyserial
    except ImportError:
        print("需要 pyserial：请在该 venv 中执行 pip install pyserial")
        return 2
    import time

    with serial.Serial(port, baud, bytesize=8, parity="N",
                       stopbits=1, timeout=0.2) as ser:
        print("已打开 %s @ %d 8N1" % (port, baud))
        for title, cmds in groups:
            print(title)
            for blob, desc in cmds:
                ser.write(blob)
                ser.flush()
                print("   -> %-28s %s" % (desc, desc))
                time.sleep(delay)
        print("\n发送完毕。若屏上无变化，按 README 的排查表逐项检查。")
    return 0


def capture(port, baud, seconds):
    try:
        import serial
    except ImportError:
        print("需要 pyserial：pip install pyserial")
        return 2
    import time

    print("监听 %s @ %d，%d 秒…（屏的 TX 需接到 USB-TTL 的 RX）"
          % (port, baud, seconds))
    with serial.Serial(port, baud, timeout=0.2) as ser:
        t0 = time.time()
        while time.time() - t0 < seconds:
            data = ser.read(256)
            if data:
                print("  [RX] %s | %s"
                      % (" ".join("%02X" % b for b in data),
                         data.decode("ascii", "replace")))
    return 0


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser(description="淘晶驰串口屏本地模拟验证工具")
    ap.add_argument("--port", help="串口号，如 COM5；不填则只打印指令")
    ap.add_argument("--baud", type=int, default=BAUD_DEFAULT)
    ap.add_argument("--scenario", default="full",
                    choices=["splash", "item", "full"])
    ap.add_argument("--seq", type=int, default=3)
    ap.add_argument("--cat", type=int, default=1)
    ap.add_argument("--total", type=int, default=3)
    ap.add_argument("--delay", type=float, default=0.15,
                    help="两条指令之间的间隔秒数（9600 下建议 >=0.1）")
    ap.add_argument("--dry-run", action="store_true", help="只打印不发送")
    ap.add_argument("--capture", action="store_true",
                    help="监听屏回传而非发送")
    ap.add_argument("--seconds", type=int, default=10,
                    help="--capture 模式的监听时长")
    args = ap.parse_args()

    if args.capture:
        if not args.port:
            print("--capture 需要 --port")
            return 2
        return capture(args.port, args.baud, args.seconds)

    if args.scenario == "splash":
        groups = [("# Display_ShowSplash()", scenario_splash())]
    elif args.scenario == "item":
        groups = [("# Display_ShowItem(seq=%d, cat=%d, total=%d)"
                   % (args.seq, args.cat, args.total),
                   scenario_item(args.seq, args.cat, args.total))]
    else:
        groups = scenario_full()

    if args.port and not args.dry_run:
        return send(groups, args.port, args.baud, args.delay)

    dump(groups)
    return 0


if __name__ == "__main__":
    sys.exit(main())
