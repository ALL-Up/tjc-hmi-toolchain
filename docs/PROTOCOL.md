# MCU ↔ 串口屏 通信协议

## 一、五条铁律

违反任意一条，屏就不动（且多数情况**没有任何报错**）。

1. **每条指令末尾必须补 3 个 `0xFF`** —— 缺一不可。
2. 参数只用**十进制或颜色代号**，**不支持 `0x` 前缀**。
3. 写字符串**必须带双引号**：`main.t1.txt="BOTTLE"`。
4. 控件名**大小写敏感**，建议带页面前缀（`main.t1` 而非 `t1`）。
5. **数字控件用 `.val=`，文本控件用 `.txt=`** —— 用错类型指令静默失效。

```c
static void tjc_send(const char *cmd)
{
    HAL_UART_Transmit(&huart, (uint8_t *)cmd, strlen(cmd), 100);
    uint8_t end[3] = {0xFF, 0xFF, 0xFF};
    HAL_UART_Transmit(&huart, end, 3, 100);
}
```

---

## 二、颜色代号（RGB565 十进制）

| 名 | 值 | 名 | 值 |
|---|---|---|---|
| BLACK | 0 | RED | 63488 (`0xF800`) |
| BLUE | 31 | YELLOW | 65504 (`0xFFE0`) |
| GREEN | 2016 (`0x07E0`) | WHITE | 65535 |
| GRAY | 33840 | BROWN | 48192 |

校验：`GREEN=0x07E0`、`RED=0xF800`、`YELLOW=0xFFE0`。

---

## 三、常用指令

### 3.1 刷新类

```
n0.val=7                      # 数字控件赋值
t1.txt="BOTTLE"               # 文本控件赋值（GBK 编码）
p0.pic=3                      # 图片控件切图（N = 成员编号）
t1.pco=63488                  # 改文字颜色为红
t1.bco=65535                  # 改背景色为白
dim=100                       # 背光 0-100
```

### 3.2 页面与控件

```
page 1                        # 跳转到第 1 页
vis b_start,0                 # 隐藏控件
vis b_start,1                 # 显示控件
tsw b_start,0                 # 禁用触摸
```

### 3.3 回读（调试用）

```
get n0.val                    # 屏回 n0.val=7 + FF FF FF
```

### 3.4 上电初始化（写在 `Program.s`）

```
int sys0=0
baud=9600
bkcmd=0
dim=100
page 0
```

> `Program.s` 是上电脚本，每条语句**以换行结尾**（不是 `0xFF`）。
> 全局变量只能在此定义。

---

## 四、触摸事件回传（`sendkey`）

控件设 `sendkey=1` 后，触摸时屏往串口发 **7 字节包**：

```
0x65  页号  控件号  事件  0xFF 0xFF 0xFF
```

- 事件：`0x01` = 按下，`0x00` = 抬起
- **这不等于跳页**：屏只是把触摸上报给 MCU，**跳页要 MCU 收包后发 `page N` 回来**。
- 调试模式（未接 MCU）点这类控件看起来「没反应」，这是正常的。

### 屏内自跳页

若不想让 MCU 参与，直接在控件**事件代码**里写 `page N`：

- 跳页写在**按下事件**（`codesdown`）
- 事件代码的二进制存储格式见 `docs/HMI_FORMAT.md` §3.9

---

## 五、控件命名约定

**控件名必须与 MCU 侧头文件里的宏逐字一致**，否则指令无效
（屏收不到对应控件，静默忽略）。

建议在 MCU 侧统一维护一份宏表：

```c
/* display_ctrl.h —— 必须与 .pa 里的 objname 逐字一致 */
#define SCR_OBJ_TITLE   "main.t0"
#define SCR_OBJ_NAME    "main.t1"
#define SCR_OBJ_STATUS  "main.t2"
#define SCR_OBJ_SEQ     "main.n0"
#define SCR_OBJ_TOTAL   "main.n1"
#define SCR_OBJ_IMAGE   "main.p0"
```

生成 `.pa` 时的 `objname` 就是这个字符串（不带引号，直接写进二进制）。
生成脚本里的 `PAGE0_WIDGETS` / `PAGE1_WIDGETS` 就是这份契约的另一半。

---

## 六、带宽与刷新延迟

串口波特率 9600 8N1 = 10 bit/byte，即 **960 B/s**。

一条 `n0.val=7` + 3 个 `0xFF` = 12 字节 ≈ 12.5 ms。

刷新频率高时注意：**逐条发送并留间隔**（建议 ≥100 ms，9600 下）。
需要更快时提高 `baud`（上位机与 `Program.s` 都要改）。

`tjc_sim.py` 的 `dump()` 会统计总字节数与预估耗时。

---

## 七、接线

```
USB-TTL / MCU TX  ──→  屏 RX
USB-TTL / MCU RX  ←──  屏 TX（需要回读时才接）
GND               ────  GND   ← 必须共地
```

- 屏**单独 5V 供电**，不要从 USB-TTL 模块取电（电流不够会导致花屏/重启）。
- 屏的 TX 一般接 MCU 的 RX（如需接收 `sendkey` 包或 `get` 回读）。

---

## 八、下载/烧录

| 方式 | 说明 |
|---|---|
| 串口下载 | 上位机选串口，**下载波特率 115200**（与运行波特率无关） |
| TF 卡 | 把 `.tft` 放卡根目录，断电插卡上电自动烧 |

**必须刷掉出厂 demo**，否则它会与 MCU 指令抢屏。

图片/字库在**下载时**随工程写入屏内 Flash —— 改了资源要**整体重新下载**。
