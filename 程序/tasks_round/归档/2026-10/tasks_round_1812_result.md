# R1812：结构治理轮——模型管理窗 open_manager 由 493 行闭包改写成类并切段（批次 C-4）＋补它的 Tk 差分测试（批次 D-2）

1. 本轮类型：§3 结构治理轮（只重构，不改行为）。这是批次 C 里用户点名、上一轮我自行放弃的一项；放弃理由是“块间要传的变量太多”，本轮改用“先把闭包状态变成实例属性，再切段”的路线，变量传递的问题消失。

2. 测试与基线：
   - **先补测试**：`tests/test_open_manager_equivalence.py`——旧 `open_manager` 原样内嵌，用同一份脚本驱动两个真 Tk 窗口，每一步对照可观察状态：表单 31 个控件的文本／勾选／显隐、列表行、提示语、密钥状态行、`_pet_*` 句柄集合、模型池落盘内容、宠物被调用的记录、关闭后窗口是否销毁。脚本走完整条链：打开→新建→填表→换 Provider→保存→选中改名→保存→测试连接（无模型 ID／有模型 ID）→切 Desktop（延时自动搜寻线程跑一轮）→自动搜寻→保存（路径无效）→切 CLI→切回 API→输入密钥自动保存→清除→空框保存→删除（未选／选中）→刷新→关闭。注册表搜寻、DPAPI 本机密钥、连接探测用替身。
   - **测试自身有牙**：先用旧实现对自己比对通过（确认脚本无随机性）；改写后故意把“已删除「%s」。”改成“已删除了「%s」。”，差分测试立即红（报出两边提示语不同），还原后转绿。
   - 改写后：差分 + `ui_batch7`（原有的模型窗口几何／按钮顺序／错误不锁屏等）+ 架构门禁 + `static_names` + token 边界等共 615 条（含 GUI）：除 `test_round_number_continuous`（分支上状态页轮次头只能在 master 更新）外全绿。完整安全全量：本轮未跑。

3. project_status.md 欠账：本轮改源码 +1。

## 改了什么
| 位置 | 内容 |
|---|---|
| `pet_models_ui.open_manager` | 493→3 行薄函数：`return _ModelManager(pet).build()` |
| `pet_models_ui._ModelManager`（新类） | 改写工具按 AST 作用域分析自动完成：被嵌套函数共享的 32 个局部名（`entries`／`tree`／`hint`／`mode`／`pending`／`state`…）成了 `self.<名>`；23 个嵌套函数成了方法；`from queue import Queue, Empty` 等被共享的函数内导入在语句后补 `self.X = X`；`build()` 再按三个自然段切成 `_build_window_and_table`（33 行）、`_build_form_fields`（55 行）、`_build_program_row`（61 行），尾部 12 行发布 `_pet_*` 句柄 |
| `test_function_size_ratchet.py` | 删 `open_manager` 登记 |
| `维护记录/skip台账.json` | 登记新测试的 Tk 不可用跳过（平台限制） |

## 工具
改写工具是脚本（不入库）：按“外层局部名 / 被嵌套作用域引用的自由名”分类，遇到 global、嵌套 class、带装饰器或默认值引用外层局部的嵌套 def、`except as` 共享名、藏在语句块里又被别处引用的 def 一律中止，不猜。后续其余长 Tk 函数沿用同一路线。
