/**
 * main 用法示例 —— 演示 sorter_v12.HMI（双页美化版）+ tjc_screen 模块的接线方式
 * 只展示与串口屏相关的部分，整合进你现有工程即可。
 */
#include "stm32f4xx_hal.h"
#include "tjc_screen.h"

extern UART_HandleTypeDef huart2;      /* 接屏的 UART（CubeMX 生成） */

static volatile uint8_t sorting = 0;   /* 分拣进行中标志 */

/* 按钮回调：page=页面号 comp=控件ID event=1按下/0松开 */
static void MyButtonCB(uint8_t page, uint8_t comp_id, uint8_t event)
{
    if (event != 0x01) return;         /* 只响应"按下" */

    if (page == TJC_PAGE_WELCOME) {
        switch (comp_id) {
        case TJC_COMP_P0_START:        /* 欢迎页 START (id=1) */
            TJC_GotoPage(TJC_PAGE_SORTING);   /* 跳转分类页 */
            TJC_SetStatus("READY");
            /* 也可以在这里直接 sorting=1 自动开始分拣；
             * 若希望进入分类页后另有"开始"动作，把 sorting=1 挪到需要的地方 */
            break;
        }
    }
    else if (page == TJC_PAGE_SORTING) {
        switch (comp_id) {
        case TJC_COMP_P1_STOP:         /* 分类页 STOP (id=11) */
            sorting = 0;
            TJC_SetStatus("PAUSED");
            TJC_ShowMaterial(9);       /* 大图回待机（>2 的值都会落到待机图） */
            /* TODO: 停传送带 */
            break;
        case TJC_COMP_P1_RESET:        /* 分类页 RESET (id=12) */
            TJC_SetStatus("READY");
            TJC_ResetAll();            /* 计数清零：跳回欢迎页再进，或改为发
                                          n0.val=0 / n1.val=0 / n2.val=0 / n3.val=0 */
            break;
        case TJC_COMP_P1_HOME:         /* 分类页 HOME (id=13) */
            sorting = 0;
            TJC_GotoPage(TJC_PAGE_WELCOME);
            break;
        }
    }
}

int main(void)
{
    HAL_Init();
    SystemClock_Config();              /* CubeMX 生成 */
    MX_GPIO_Init();
    MX_USART2_UART_Init();             /* 9600-8-N1，与屏端 baud=9600 一致 */

    TJC_Init(&huart2, MyButtonCB);
    TJC_GotoPage(TJC_PAGE_WELCOME);    /* 上电对齐到欢迎页（可选，屏端 Program.s 已 page 0） */

    while (1) {
        TJC_Poll();

        /* ===== 分拣逻辑示例 =====
         * START 后 sorting=1，视觉/传感器判定物料类别 mat（0=红 1=蓝 2=绿）：
         *
         *   TJC_ShowMaterial(mat);  // 分类页大图切换为该物料图片
         *   TJC_Count(mat);         // 对应分类计数 +1，总数同步 +1
         *
         * 节拍提示：一条指令约 10 字节 @9600bps ≈ 10ms，
         * 不要在中断里连续发太密，主循环里发即可。 */
    }
}
