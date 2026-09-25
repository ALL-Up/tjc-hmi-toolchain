/**
 * tjc_screen.c —— 淘晶驰串口屏通信模块（STM32F407VET6 HAL）
 * 配套工程：sorter_v12.HMI（双页美化版）。详见 tjc_screen.h 头部协议说明。
 *
 * 移植要点：
 *   1. CubeMX 里把接屏的 UART 配好（如 USART2 PA2/PA3，9600-8-N1），
 *      并开启该 UART 的 NVIC 中断。
 *   2. 调用 TJC_Init(&huart2, MyButtonCB) 后，在主循环里周期调 TJC_Poll()。
 *   3. HAL_UART_ReceiveIT 单字节中断接收由本模块自行管理，无需用户干预。
 */
#include "tjc_screen.h"
#include <string.h>
#include <stdio.h>

#define TJC_PKT_HDR   0x65          /* 触摸上报包头 */
#define TJC_PKT_LEN   7             /* 65 page comp event FF FF FF */

static UART_HandleTypeDef *s_huart = NULL;
static tjc_button_cb       s_cb    = NULL;

static uint8_t s_rx;                        /* 单字节中断接收缓冲 */
static uint8_t s_pkt[TJC_PKT_LEN];          /* 正在拼装的包 */
static uint8_t s_idx = 0;

/* ---------------- 发送 ---------------- */

void TJC_SendCmd(const char *cmd)
{
    static const uint8_t tail[3] = {0xFF, 0xFF, 0xFF};
    if (s_huart == NULL || cmd == NULL) return;
    HAL_UART_Transmit(s_huart, (uint8_t *)cmd, (uint16_t)strlen(cmd), 100);
    HAL_UART_Transmit(s_huart, (uint8_t *)tail, 3, 100);
}

void TJC_GotoPage(uint8_t page)
{
    char buf[16];
    snprintf(buf, sizeof(buf), "page %u", (unsigned)page);
    TJC_SendCmd(buf);
}

/* 类别计数 +1，并同步总数。mat: 0=红方块 1=蓝方块 2=绿圆柱 */
void TJC_Count(uint8_t mat)
{
    static const uint8_t ncomp[3] = {3, 5, 7};   /* n0/n1/n2 的控件 id */
    char buf[16];
    if (mat > 2) return;
    snprintf(buf, sizeof(buf), "n%u.val++", (unsigned)((ncomp[mat] - 3) / 2));
    TJC_SendCmd(buf);                            /* n0/n1/n2 */
    TJC_SendCmd("n3.val++");                     /* 总数（控件 id=10） */
}

/* 识别结果大图：3=待机 4=红 5=蓝 6=绿（图片库 .ib 编号） */
void TJC_ShowMaterial(uint8_t mat)
{
    char buf[16];
    if (mat > 2) { TJC_SendCmd("p0.pic=3"); return; }   /* 非法值 → 待机 */
    snprintf(buf, sizeof(buf), "p0.pic=%u", (unsigned)(mat + 4));
    TJC_SendCmd(buf);
}

void TJC_SetStatus(const char *txt)
{
    char buf[48];
    snprintf(buf, sizeof(buf), "t1.txt=\"%s\"", txt);
    TJC_SendCmd(buf);
}

/* 回欢迎页且计数清零（页面重载后所有控件回初始态） */
void TJC_ResetAll(void)
{
    TJC_GotoPage(TJC_PAGE_WELCOME);
}

/* ---------------- 接收（0x65 包状态机） ---------------- */

static void dispatch_button(void)
{
    if (s_cb != NULL)
        s_cb(s_pkt[1], s_pkt[2], s_pkt[3]);   /* page, comp_id, event */
}

void TJC_Poll(void)
{
    /* HAL 中断接收是异步的；保留统一心跳入口（超时/心跳可在此扩展） */
}

/* HAL 接收完成回调（与用户代码中共用，用 huart 判断归属） */
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart != s_huart) return;

    uint8_t b = s_rx;

    if (s_idx == 0) {
        if (b == TJC_PKT_HDR) s_pkt[s_idx++] = b;      /* 等包头 */
    } else {
        s_pkt[s_idx++] = b;
        if (s_idx == TJC_PKT_LEN) {
            /* 校验结束符 FF FF FF */
            if (s_pkt[4] == 0xFF && s_pkt[5] == 0xFF && s_pkt[6] == 0xFF)
                dispatch_button();
            s_idx = 0;
        }
        if (s_idx >= TJC_PKT_LEN) s_idx = 0;            /* 包长溢出保护 */
    }

    HAL_UART_Receive_IT(s_huart, &s_rx, 1);             /* 续接下一字节 */
}

void TJC_Init(UART_HandleTypeDef *huart, tjc_button_cb cb)
{
    s_huart = huart;
    s_cb    = cb;
    s_idx   = 0;
    HAL_UART_Receive_IT(s_huart, &s_rx, 1);
}
