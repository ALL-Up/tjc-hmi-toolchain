/**
 * tjc_screen.h —— 淘晶驰串口屏通信模块（STM32F407VET6 HAL）
 *
 * 配套工程：sorter_v15.HMI（真按钮控件版：欢迎页 → 分类页）
 * 波特率：9600（与 Program.s 中 baud=9600 一致，可改 115200，两边同步改）
 *
 * 通信协议：
 *   屏 → MCU（触摸自动上报，sendkey=1 的按钮控件）：
 *         0x65 <页面ID> <控件ID> <事件:01按下/00松开> FF FF FF   （7 字节定长）
 *   MCU → 屏（recmod=0 主动解析模式）：指令文本 + FF FF FF
 *         "n0.val++"             A 类(红方块)计数 +1
 *         "n1.val++"             B 类(蓝方块)计数 +1
 *         "n2.val++"             C 类(绿圆柱)计数 +1
 *         "n3.val++"             总数 +1
 *         "p0.pic=4"             识别结果大图：3=待机 4=红 5=蓝 6=绿
 *         "t1.txt=\"RUNNING\""   状态文字（分类页）
 *         "page 0"               回欢迎页 / 整页复位（计数清零）
 *   注意：v15 起页面跳转由屏内事件完成（START 弹起→page 1、HOME 弹起→page 0），
 *         MCU 无需再发 page 指令做跳转。
 *
 * 控件 ID 对照（sorter_v15.HMI）：
 *   页面 0：1  = 背景图   2 = START 大按钮
 *   页面 1：11 = STOP   12 = RESET   13 = HOME
 *           3 = n0 A类  5 = n1 B类   7 = n2 C类  10 = n3 总数
 *           8 = p0 识别大图   9 = t1 状态
 */
#ifndef TJC_SCREEN_H
#define TJC_SCREEN_H

#include "stm32f4xx_hal.h"

/* 页面编号 */
#define TJC_PAGE_WELCOME   0
#define TJC_PAGE_SORTING   1

/* 按钮控件 ID（按页面区分） */
#define TJC_COMP_P0_START  2     /* 欢迎页 START（v15：背景图占 id=1，按钮=2） */
#define TJC_COMP_P1_STOP   11    /* 分类页 STOP  */
#define TJC_COMP_P1_RESET  12    /* 分类页 RESET */
#define TJC_COMP_P1_HOME   13    /* 分类页 HOME  */

/* 物料类别（与图片库编号对应） */
#define TJC_MAT_RED      0
#define TJC_MAT_BLUE     1
#define TJC_MAT_GREEN    2

/* 按钮事件回调：page=页面号 comp=控件ID event 1=按下 0=松开 */
typedef void (*tjc_button_cb)(uint8_t page, uint8_t comp_id, uint8_t event);

void TJC_Init(UART_HandleTypeDef *huart, tjc_button_cb cb);
void TJC_Poll(void);                 /* 放主循环，预留心跳入口 */
void TJC_SendCmd(const char *cmd);   /* 发送指令（自动补 FF FF FF） */
void TJC_GotoPage(uint8_t page);     /* 页面跳转 */
void TJC_Count(uint8_t mat);         /* 对应类别计数 +1（0/1/2），总数同步 +1 */
void TJC_ShowMaterial(uint8_t mat);  /* 识别结果大图显示对应物料图片 */
void TJC_SetStatus(const char *txt); /* 更新 t1 状态文字（分类页） */
void TJC_ResetAll(void);             /* page 0 整页复位（回欢迎页且计数清零） */

#endif
