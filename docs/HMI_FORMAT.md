# `.HMI` / `.pa` 文件格式规范

本文档是本项目所有格式结论的汇总。**每一条都经过与上位机真值样本的字节级比对验证**，
不是推测。凡标注「实测」的均为已验证；凡标注「⚠ 待定」的为已知不确定项。

真值样本定义：
- **真值工程** `reference/truth_project.HMI`（7,341,339 B）—— 上位机保存的 3 成员工程
- **真值页** `reference/truth/truth_0_pa.bin`（769 B）—— 空白页
- **含控件页** `reference/truth/truth_controls.pa`（3,096 B）—— 手拖 文本/数字/图片 各 1 个
- **真值清单** `reference/truth/truth_main_HMI.bin`（112 B）

---

## 一、CRC 算法

淘晶驰的 CRC **不是**标准 CRC32，有两套变体，均为多项式 `0x04C11DB7`、
**MSB-first（左移）查表法、无反射、无最终异或**。

```python
# 查表生成（与上位机内嵌表逐项一致，已核对 256/256）
_t = []
for i in range(256):
    c = i << 24
    for _ in range(8):
        c = ((c << 1) ^ 0x04C11DB7) & 0xFFFFFFFF if (c & 0x80000000) else (c << 1) & 0xFFFFFFFF
    _t.append(c)
# _t[0] == 0x00000000, _t[1] == 0x04C11DB7
```

### 1.1 `tjc_crc32` —— 逐字节

```python
def tjc_crc32(data, init=0xFFFFFFFF):
    c = init
    for b in data:
        c ^= b
        for _ in range(4):
            c = ((c << 8) & 0xFFFFFFFF) ^ TAB[(c >> 24) & 0xFF]
    return c
```

用于：`.pa` 头部校验值、`main.HMI` 头部校验值、各资源成员头部。

### 1.2 `crc7950` —— 逐 32 位字

```python
def crc7950(crc, buf):
    for i in range(0, len(buf), 4):
        crc ^= int.from_bytes(buf[i:i+4], "little")   # 每次吃 4 字节
        for _ in range(4):
            crc = ((crc << 8) & 0xFFFFFFFF) ^ TAB[(crc >> 24) & 0xFF]
    return crc
```

用于：**CFS 容器目录表 CRC**，且需附加 4 字节盐。

```python
dir_crc = crc7950(0xFFFFFFFF, count_4B + all_entries)
dir_crc = crc7950(dir_crc, b"ADEC")     # 盐，按 32 位字累积
```

> 🚨 用逐字节的 `tjc_crc32` 去算目录 CRC 会得到一个「看起来像」的值，
> 但上位机必定报「错误的资源文件或者资源文件已经受损」——这是最容易踩的坑。

### 1.3 `.pa` 头部校验值 = 5 段累积

```python
c = tjc_crc32(pa[4:])                    # 段1：第 4 字节起到文件末尾
c = tjc_crc32(pack("<I", datasize), c)   # 段2：累积 +0x04 字段
c = tjc_crc32(pack("<I", nobj), c)       # 段3：累积 +0x0C 字段
c = tjc_crc32(bytes([pagelock]), c)      # 段4：累积 +0x14 低字节
c = tjc_crc32(bytes([mark]), c)          # 段5：累积 +0x15（恒 0x55）
# c 写入 +0x00
```

实测：空白页 `0x2364D04F`、含控件页 `0xAD75A33D`，**双样本逐字节命中**。

### 1.4 `main.HMI` 头部 = 5 段累积（字段顺序不同）

```python
crc = tjc_crc32(file[4:])
crc = tjc_crc32(file[0x10:0x14], crc)        # +0x10 Modelcrc
crc = tjc_crc32(file[0x04:0x08], crc)        # +0x04 datasize
crc = tjc_crc32(file[0x0A:0x0B], crc)        # +0x0A filever 低位（1 字节）
crc = tjc_crc32(file[0x0E:0x0F], crc)        # +0x0E mark（1 字节，=0x55）
```

> 注：段2/段3 顺序为先 `+0x10` 后 `+0x04`。实测 `+0x04` 与 `+0x18` 同值无法区分，
> 两种写法等价。

---

## 二、CFS v2 容器（`.HMI` 文件本身）

`.HMI` 是一个自定义文件系统容器，**不是平铺归档**。上位机加载链路：
`OpenFileHmi → CFSOpenSystem(path, 1)`，失败则兜底旧格式解析 → 报「资源文件受损」。
**只要目录 CRC 算对，`CFSOpenSystem` 就能成功** —— 这是能否打开的唯一容器级门槛。

### 2.1 物理布局

| 偏移 | 内容 |
|---|---|
| `0x000000` | **主目录**：`u32 count` + `count × 28B 条目` + `u32 目录CRC` |
| `0x080000` | **目录完整副本**，与主目录逐字节相同（含 CRC） |
| `0x380000` | `FF FF FF FF` 无效标记 |
| `0x6FFFF8` | 字面串 `"ver21234"`（8 字节固定魔数） |
| `0x700000` | **数据区**：成员首尾相接、无填充；末成员结束即 EOF |

> 🚨 目录**必须写两份**，且逐字节相同。只改一份就会被判「资源受损」。

### 2.2 目录条目（28 B）

```
+0x00  u8[16]  名称（ASCII，0 填充，如 "Program.s" / "0.pa" / "main.HMI"）
+0x10  u32     数据绝对偏移 = 0x700000 + 前面成员大小累积
+0x14  u32     成员字节数
+0x18  u32     类型标记
```

**类型标记与成员内容无关**（实测：不同内容同值）。照抄真值常数即可：

| 成员类型 | 类型标记 |
|---|---|
| `Program.s` / `main.HMI` | `0x0BA20900` |
| `N.pa` | `0x00000300` |
| `N.i` | `0xFFFFFF00` |
| `N.is` | `0x05276900` |
| `N.ib` | `0x0098D400` |
| `0.zi` | `0x42B37C00` |

---

## 三、`.pa` 页面文件

### 3.1 整体布局

```
0x00..0x43   头部 0x44 字节
0x44..       控件索引块：每控件 12 字节 [组相对偏移+12, 组长度, 0]，基准 0x44
             （不含页面组；控件数 N 时占 12N 字节）
其后         组数据：页面组在前，随后依次各控件组，首尾相接
             页面组起点 = 0x44 + 12 × 控件数
每组末尾     4 个 NUL
```

> 🚨 **索引块自身占位必须计入组偏移**：`索引项[0] = 12N + len(页面组) + 12`。
> 真值验证：`0x44 + 749 - 12 = 0x325` = 第一个控件组真实起点 ✅

### 3.2 头部字段

| 偏移 | 类型 | 空白页 | 含控件页 | 含义 |
|---|---|---|---|---|
| `+0x00` | u32 | `0x2364D04F` | `0xAD75A33D` | **校验值**（见 §1.3） |
| `+0x04` | u32 | 769 | 3096 | 本页总长度 |
| `+0x08` | u32 | `0x38` | `0x38` | 固定 |
| `+0x0C` | u32 | 1 | 4 | **对象总数**（页面 + 控件数） |
| `+0x10` | u32 | 0 | 0 | |
| `+0x14` | u32 | `0x00215500` | 同 | 固定（低字节为 pagelock） |
| `+0x15` | u8 | `0x55` | `0x55` | mark |
| `+0x18` | char[4] | `"page"` | 同 | 页名前 4 字节 |
| `+0x1C` | u32 | `0x30` | `0x30 + page_no` | 低字节 = `'0' + 页号` |
| `+0x28` | u32 | `0x02014401` | 同 | 固定 |
| `+0x38` | u32 | `0x0C` | `0x30` | **= 12 × nobj** |
| `+0x3C` | u32 | 701 | 701 | 固定 701 |
| `+0x40` | u32 | 0 | 0 | |

> ⚠ `+0x38` **不是常数**，等于 `12 × nobj`（空白页 1 对象 → `0x0C`；
> 4 对象 → `0x30`；10 对象 → `0x78`；3 对象 → `0x24`）。
> 照抄别的工程的值会导致对象槽数不匹配。

### 3.3 记录结构

```
u32 payload_len + payload
payload = name(ASCII) + value
  若 payload_len <= 16：名称**不补齐**，无 value（如 att-28 → plen=6）
  若 payload_len >  16：名称**补齐至 16 字节**，value 从第 16 字节起
推进步长 = 4 + payload_len（无额外对齐）
```

### 3.4 组类型与属性数

| 对象 | 组头 | 属性条数 | 事件槽 |
|---|---|---|---|
| **页面** | `att-28` | 28 | **5 个**：`codesload` `codesloadend` `codesdown` `codesup` `codesunload` |
| **文本** | `att-39` | 39 | **2 个**：`codesdown` `codesup` |
| **数字** | `att-39` | 39 | 2 个 |
| **图片** | `att-22` | 22 | 2 个 |
| **按钮** | `att-42` | 42 | 2 个 |

> 🚨 **控件组头与页面完全不同**，且**控件只有 2 个事件槽**。
> 误以为所有组都是 `att-28` 是生成被拒的核心原因之一。

### 3.5 属性序列（实测）

```
PAGE(att-28, 28 条):
  type id objname vscope drag sendkey aph movex movey x y w h endx endy
  effect first time lockobj groupid0 groupid1
  up down left right sta bco pic

TEXT(att-39, 39 条):
  type id objname vscope drag sendkey aph movex movey x y w h endx endy
  effect first time lockobj groupid0 groupid1
  sta style key borderc borderw font bco picc pic pco xcen ycen pw
  txt txt_maxl isbr spax spay

NUM(att-39, 39 条):
  type id objname vscope drag sendkey aph movex movey x y w h endx endy
  effect first time lockobj groupid0 groupid1
  sta style key borderc borderw font bco picc pic pco xcen ycen
  val lenth format isbr spax spay

PIC(att-22, 22 条):
  type id objname vscope drag sendkey aph movex movey x y w h endx endy
  effect first time lockobj groupid0 groupid1 pic

BTN(att-42, 42 条):
  type id objname vscope drag sendkey aph movex movey x y w h endx endy
  effect first time lockobj groupid0 groupid1
  sta style borderc borderw font pic picc bco pic2 picc2 bco2 pco pco2
  xcen ycen val txt txt_maxl isbr spax spay
```

> TEXT / NUM 在 `groupid1` 之后**跳过** `up/down/left/right`，直接进 `sta`（页面才有那四个）。

### 3.6 属性值宽度

| 宽度 | 属性 |
|---|---|
| **BYTE**(1) | `type id vscope drag sendkey aph effect first lockobj up down left right sta style key borderw font xcen ycen pw lenth format isbr spax spay` + **按钮的 `val`** |
| **WORD**(2) | `movex movey x y w h endx endy time bco pic borderc picc pco txt_maxl pic2 picc2 bco2 pco2` |
| **DWORD**(4) | `groupid0 groupid1` + **数字控件的 `val`** |
| **RAW** | `objname txt` |

> ⚠ `time` 是 WORD 不是 DWORD；数字控件 `val` 是 DWORD，但**按钮 `val` 是 1 字节 BYTE**。

### 3.7 控件 type 代号

| 类型 | 代号 |
|---|---|
| 页面 | `0x79` |
| 文本 | `0x74` |
| **数字** | **`0x36`** ← **不是 `0x6E`！** |
| 图片 | `0x70` |
| 按钮 | `0x62` |

### 3.8 控件默认值（真值）

```
vscope=0  drag=0  sendkey=0  aph=0x7F  movex=0 movey=0  effect=0  first=0
time=300  lockobj=0  groupid0=0 groupid1=0  sta=1  style=0  key=0xFF
borderc=0x0000  borderw=2  font=0
bco=0xFFFF  picc=0xFFFF  pic=0xFFFF  pco=0x0000
xcen=1  ycen=1  pw=0  txt=b""  txt_maxl=10  isbr=0（文本）/1（数字）  spax=0 spay=0
val=0  lenth=0  format=0
id 递增：page=0, 第一个控件=1, ...
endx = x + w - 1 ; endy = y + h - 1（自动算）
```

按钮额外默认值：`sta=1 style=4 borderw=2 bco=0xC618 bco2=0x0400 pco=0 pco2=0xFFFF`
`pic/picc/pic2/picc2 = 0xFFFF  val=0  txt=""  txt_maxl=10`

### 3.9 事件代码存储格式

```
槽名后缀 = 该槽的代码行数
  codesdown-0  → 0 行（空槽）
  codesdown-1  → 1 行代码

代码行 = 独立的纯名记录：plen = len(行文本)，无 NUL 无换行
        （如 "page 1" → plen=6），紧跟在槽标记记录之后
多行 = 多条连续记录

槽顺序：codesdown-N → 其代码行们 → codesup-N → 其代码行们 → 组尾 4 NUL
```

❌ 错误猜测：把代码内嵌到值区（`plen = 16 + len`、名称补齐）。
编辑器读不出，事件框显示为空。

跳页写在**按下事件**（`codesdown`）。推断 `-N` 的 N 就是行数计数，
**未验证 2 行以上的样本**。

---

## 四、图片成员：`.i` / `.is` / `.ib`

一张图需要 **3 个成员**，且 **`main.HMI` 名字表必须登记 `.i` 条目**。

### 4.1 `.i` —— 屏显格式（画布渲染的真正入口）

```
24B 头：0A 60 01 03 | u32 0 | u32 24 | u16 宽 u16 高 | u32 payload大小 | u32 0
payload：20B 全零（未压缩 flag=0） + 宽×高×2 原始 RGB565（小端）
tag = 0xFFFFFF00
```

> 另有一种压缩变体（payload 前 20B = `01 00 00 00 | u32 大小 | 12B 零`，RLE 风格），
> **不必破解** —— 未压缩模式编辑器自己就认。

### 4.2 `.is`（PNG 原件）/ `.ib`（图库）

格式同构 = **27B 头 + 完整 PNG**：

```
0A 64 01 01 | u32 0 | u32 27 | u16 宽 u16 高 | u32 PNG大小 | u32 0 | "png"
```

tag：`.is` = `0x05276900`，`.ib` = `0x0098D400`

### 4.3 名字表登记规则（关键）

`main.HMI` 尾部名字表**只登记 `.i` / `.zi` / `.pa` 三类**。
`.is` / `.ib` 在容器里存在但**名字表不登记**。

实测名字表样例：`0.i / 1.i / 0.zi / 0.pa`（四条）

> 🚨 **名字表没有 `.i` 条目 → 画布图片全不显示。**
> 这是最隐蔽的坑：容器里有图片成员、控件 `pic=N` 也对，但屏上就是空白。
> 生成顺序参照真值：所有 `.i` 在最前，然后 `.zi`，最后 `.pa`。
> 图片编号 = 成员名序号（`0.i` = 图 0），控件 `pic=N` 引用。

### 4.4 ⚠ 黑边问题

**`.i` 是 RGB565，没有 alpha 通道。** 透明像素被转成 `0x0000` = 黑，
画布上所有透明底图片四角/四周带黑边。

**解法：素材必须全不透明。** 按钮圆角四角填背景图对应位置的切片色可做到视觉无缝；
图标/大图用白底卡片。

---

## 五、`main.HMI` 项目清单成员

```
112 B = 96 B 头 + 16 B × N 名字条
```

| 偏移 | 含义 |
|---|---|
| `+0x00` | 头部 CRC（5 段累积，见 §1.4） |
| `+0x04` | datasize（= 文件长度） |
| `+0x0A` | filever 低位 |
| `+0x0C` | 高半字节含 filever；低字节 `+0x0E` = mark = `0x55` |
| `+0x10` | Modelcrc |
| `+0x1C` | **尾部名字表条目数** |
| `+0x24` | 页面数 |
| `+0x40` | 恒 `0x300`（与页面尺寸无关） |
| `0x60..` | 名字表：每条 16 B = 8 B 类型短名 + 8 B 文件名 |

名字条示例：`"pa" + "0.pa"`、`"zi" + "0.zi"`、`"i" + "0.i"`

> 只改页面内容（`0.pa`）不需要动 `main.HMI`。
> **增删成员 / 改成员大小**才需要重建 `main.HMI` 并重算此 CRC。
>
> 实测：`+0x24` 即使双页工程也写 `1`，语义待定 —— **生成时以编辑器写法为准**。

---

## 六、字库 `.zi`

**工程必须实际包含字库成员 `0.zi`**，否则编译报
「**font 初始值无效:字库ID无效**」（每个带 `font` 的控件一条错误）。

- `font` 只能引用**工程实际拥有的字体索引**。无字库工程只有内置字体 0；
  `font=1..4` 会让上位机加载时弹「**索引超出了数组界限**」。
- 最快解法：**整块借用**其他工程现成的合法 `.zi`
  （本项目 `reference/ascii.zi` 是一个 7175 B 全 ASCII 字库，头部 `+0x0C` = 字符数 = 95 = `0x20`–`0x7E`），
  tag 照抄原值；同时 `main.HMI` 尾部名字表加 `"zi" + "0.zi"` 条目（8B + 8B，zi 排在 pa 前）、
  `+0x1C` 加 1、重算五段 CRC。

---

## 七、已知不确定项

| 项 | 状态 |
|---|---|
| 事件槽 `-N` 中 N 的含义 | 推断为代码行数，仅验证过 0 行与 1 行样本 |
| `main.HMI` `+0x24` 页面数字段 | 双页工程编辑器仍写 1，语义待定；生成时跟编辑器写法 |
| `main.HMI` `+0x18` 字段 | 与 `+0x04` 同值，无法区分 |
| `.i` 压缩变体的 RLE 细节 | 未破解，也不需要（未压缩模式足够） |
| 目录条目「历史成员」 | 编辑器只按 `main.HMI` 名字表加载，乱码名条目无害但不建议留 |
| `.pa` `+0x3C` = 701 的含义 | 实测恒 701，与页面尺寸无关，照抄即可 |

## 八、编辑器保存后的行为（实测）

打开生成的文件并在编辑器里保存后，容器被重排：

- 成员顺序变为：`main.HMI` 最前 + 图片按序 + `zi` + `Program.s` + `pa`
- tag 高位变化：`main.HMI`/`Program.s` → `0x0AC7xxxx`，`0.pa` → `0x00000800`，`1.pa` → `0x00002500`
- `main.HMI` 的 `+0x24` 写回 1
- `.i` / `.is` / `.ib` / `0.zi` 原样保留（tag 是类型常数）
- `Program.s` 内容被原样接受（字节数微变是行尾/注释处理）

> **重要**：编辑器保存过的文件是**高价值真值**（编辑器回写的即官方格式）。
> diff「生成版」vs「保存版」能一次看清编辑器改了什么 —— 按钮组格式与事件格式
> 都是这样破解的。
