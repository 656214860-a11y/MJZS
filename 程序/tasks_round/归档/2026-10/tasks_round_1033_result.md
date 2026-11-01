# R1033 三虎聊天框瞬间消失：授权临时取证

1. 本轮是诊断取证，不是功能修复；用户明确允许临时诊断记录。
2. 实机取证及最小红色复现已执行；默认冒烟 8/8。架构与全量未运行，不冒用历史绿色凭据。
3. 根因已定位，功能欠账未消除；下一轮须另行授权修复。

## A 范围
只记录窗口状态、相对时间与源码调用位置，不记录聊天正文、密钥或项目内容。
临时 scripts/diagnose_pet_cloud.py 通过内存包装调用正常单实例启动器，生产 .py 未修改；取证后已移除脚本并正常重启无诊断版本。

## B 实机操作
computer-use 操作当前助手：单击与双击三虎、右键提问入口。接口只提供截图，未生成视频。
诊断进程以随附 Python 的 -B 参数运行。没有强杀进程，没有发送消息、启动制作或直接修改用户数据。
正常启动/退出仍会执行应用既有持久化及维护流程，不能据 Git 状态宣称所有运行数据逐字节不变。

## C 确认根因
pet_ui.py:4215 step → pet_ui.py:4223 _schedule → pet_ui.py:4240 stop → Cloud.close。
重新排定动画下一帧复用了完整停止函数，而 stop 不仅取消动画回调，还关闭聊天框并取消待执行点击。

## D 原始取证摘要
同一次双击的单调时钟时间（秒，自诊断进程起算）：

| 时间 | 事件 | 状态 |
|---|---|---|
|106.138|Pet.open_chat enter|此前隐藏|
|106.167|Cloud.show return|visible=True, state=normal, mapped=1, grab=False|
|106.180|Pet.open_chat return|visible=True|
|106.182|Cloud.close enter|由 step/_schedule/stop 调用|
|106.183|Cloud.close return|visible=False，开始淡出|
|106.313|Cloud._hide_now return|state=withdrawn, mapped=0|

显示后 15ms 开始关闭，146ms 后撤下窗口；不是正常最少 9000ms 阅读停留超时。
原始关闭调用栈（仅位置，无正文）：
`__init__.py:1613:mainloop > __init__.py:2089:__call__ > __init__.py:876:callit > pet_ui.py:4215:step > pet_ui.py:4223:_schedule > pet_ui.py:4240:stop`

## E 最小验证
随附 Python -B 从 pet_ui.py AST 提取真实 _schedule、stop、cancel_click，注入内存假窗口与记录型 cloud.close；不导入配置或读取用户项目。
调用一次 _schedule 后：cloud_close_calls=1，pending_click_cancelled=True。
断言“排下一帧不关闭聊天”按预期失败：`AssertionError: REPRODUCED: scheduling the next animation frame closes chat`。
这是缺陷复现信号，不是已经修复通过的回归测试。

## F 排除与限制
该次实机关闭栈不是 guard_cloud_away、guard_chat_grab 或 _expire；不排除其他条件也会按原设计关闭。
双击明确复现瞬时关闭；单击的待处理 after 还可能被同一 stop 的 cancel_click 撤销，最小验证已确认撤销机制，但未统计单击失败概率。
诊断打印可能改变毫秒级时序；关闭调用归属由实机栈与无打印最小验证共同确认，不把实测毫秒数当恒定值。

## G 文件与清理
最终仅保留本结果报告和状态页轮次/诊断事实。临时诊断脚本已受控移除（本轮新增、可由会话补丁恢复），生产源码未修改，无运行日志暂存。

## H 验证
默认冒烟：随附 Python -B smoke_test.py，8/8，零失败。
架构门禁：未运行；全量：未运行；不引用 R1032 的结果作为本轮实测。

## I 自审
授权仅为取证，未顺手修复。保留真实失败证据、不补造验收。正常应用生命周期的运行态副作用单独说明。

## J 整改路线（待授权）
J1：将动画重排所需的“仅取消旧动画 after”与 stop 的完整退出/卸载清理解耦。不得简单删除 stop 的云朵关闭，否则会回归退出后的延迟回调清理。
J2：核对 pending-click 的取消归属，确保正常动画重排不吞单击；退出和双击仍正确取消。

## K 测试计划
不迁移、不删除现有测试。新增真实调度链回归：打开聊天后跨多次 step 仍可读；220ms 单击回调不被动画重排撤销；关闭/销毁仍取消位置重试与定时器；保留前台切换、模态抓取和重复停止用例。修复轮运行定向、默认冒烟、适用架构及 Tk 生命周期完整安全回归。

## L 后续边界
本轮不修功能；诊断脚本不留在正常启动路径。用户确认下一轮修复后再实施 J1/J2。

## M 提交
报告随 R1033 收尾提交；提交哈希见 Git 回执。提交仅含诊断结果及状态页，不含日志、配置、缓存、密钥或用户数据。
