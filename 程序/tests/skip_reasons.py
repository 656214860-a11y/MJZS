"""测试跳过原因的唯一枚举。

每个值都说明跳过原因，以及在什么条件下应恢复执行；测试模块只能引用本文件
的常量，避免把临时文字理由变成无法审计的永久豁免。
"""

PLATFORM_TKINTER = "平台限制：当前环境没有可用 tkinter；安装可用 Tk 后应恢复执行"
PLATFORM_TK_DISPLAY = "平台限制：当前环境没有可用 Tk display；可创建窗口时应恢复执行"
PLATFORM_DIRECTORY_LINK = "平台限制：当前环境不支持目录链接；支持目录链接时应恢复执行"
PLATFORM_WORKING_SET = "平台限制：当前系统无法读取工作集；支持该系统接口时应恢复执行"
MISSING_NODE = "缺外部程序：当前机器未安装 node；安装 node 后应恢复执行"
REQUIRES_BUNDLED_SKILL = "需实机复验：发行包未包含受测 bundled skill；打包产物具备该技能后应恢复执行"
MISSING_FFMPEG = "缺外部程序：当前机器没有可用的 FFmpeg／FFprobe；装好编码器后应恢复执行"
PLATFORM_WINDOWS_ONLY = "平台限制：受测功能只在 Windows 上存在（如系统托盘）；在 Windows 上运行时应恢复执行"

ALL_SKIP_REASONS = {
    PLATFORM_TKINTER,
    PLATFORM_TK_DISPLAY,
    PLATFORM_DIRECTORY_LINK,
    PLATFORM_WORKING_SET,
    MISSING_NODE,
    REQUIRES_BUNDLED_SKILL,
    MISSING_FFMPEG,
    PLATFORM_WINDOWS_ONLY,
}
