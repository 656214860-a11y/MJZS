# R1807：结构治理轮——切 app.App.__init__ 为 7 个 _build_* 方法（批次 C-1）＋修复 R1801 恢复启动画面时漏的导入

1. 本轮类型：§3 结构治理轮（切分不改行为）＋一处修复。

2. 测试与基线：
   - 切分由数据流分析脚本完成：按指定行号切块，自动算出每块需要的参数和要返回的局部变量；遇到 `return`／`yield`／`global`、或“闭包使用了后面块才赋值的局部名”（晚绑定）就拒绝。本函数分析结果很干净——7 个块之间只有两个局部变量跨块：`table_shell`（镜头表外壳，白模滚动联动要用）和 `prompt_box`（提示词按钮行 `before=` 要用），其余都靠 `self` 与 `window` 参数。语句顺序、内容一字未改，只是挪进方法并在 `__init__` 里按原顺序调用。
   - 架构门禁 + `test_video*`／`test_app*`／`static_names`／`splash`／`shot_`／`ui_widgets` 共 730 条（含 GUI）：除 `test_round_number_continuous`（分支上状态页轮次头只能在 master 更新）外全绿。
   - 完整安全全量：本轮未跑。

3. project_status.md 欠账：本轮改源码 +1。

## 改了什么
| 位置 | 内容 |
|---|---|
| `app.App.__init__` | 267→36 行；拆出 `_build_shot_table`（74 行）、`_build_audio_options`、`_build_prompt_box`、`_build_prompt_actions`、`_build_white_model_cells`、`_build_video_actions`（61 行）、`_build_progress_and_log`；`__init__` 的参数列表不变（仍是 11 个，PARAM_CAPS 登记不动） |
| `test_function_size_ratchet.py` | 删 `app.py::__init__` 登记 |
| `test_complexity_ratchet.py` | `App` 类上限 1358→1388（多出的是 7 个方法头与文档串，共 +30 行） |

## 修复：R1801 恢复 Splash 时漏了 APP_NAME 导入
R1801 恢复被 master 的 R1788 误删的 `ui_widgets.Splash` 时，只恢复了类与令牌，漏了 R1788 一并删掉的 `from app_metadata import APP_NAME`。`Splash._draw` 因此会 NameError（`test_static_names` 与 `test_app_metadata.test_display_producers_import_the_shared_name` 都报红）。这两条当时没在 R1801 的验证集里——我选的是架构门禁加 UI 相关子集，没带静态名门禁。本轮补回该导入，两条转绿。教训：恢复被删代码时要把同一提交里删掉的导入一并核对。
