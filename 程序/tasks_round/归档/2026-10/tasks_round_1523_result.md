# R1523 模型管理调用方式与安装路径修复

- 类型：§3.2 修复轮。
- 验证：专项 34 项、受影响 119 项、默认冒烟 8 项通过；架构 345 项初跑 343 通过、2 失败，修复后失败模块及自动搜寻共 13 项定向复验通过。
- 欠账：修复本轮用户报告的页面模式混淆与错误路径匹配；不修改主树既有待办和共享状态。
- 分支：`codex/model-manager-modes`；中央队列未发现对应未完成 ID，不认领无关任务。

## 根因与改动

1. 原页面按 Provider 或被编辑记录的旧 ID 推断界面，修改模型后仍可能保留旧模式。Provider 上方新增 Desktop/API/CLI 选择，按选择显示 API 字段或本机程序路径；记录保存 `call_mode`，旧记录兼容推断。
2. 原自动搜寻优先旧记录 ID，未知引擎又会进入 Claude 分支。现在只按当前模型名称和所选方式搜寻，未知引擎明确拒绝，不借用 Claude 安装路径。
3. 输入模型 ID 或切换方式时清除旧路径，450ms 防抖自动搜寻。回调读取 StringVar 当前值，避免 Entry 更新时序漏搜；关闭窗口取消待执行回调。
4. Desktop 查询匹配名称的 Windows App Paths、已安装 Store 包及常见安装目录；CLI 复用现有受支持引擎定位。只读定位，不执行候选程序；未安装时提示并保留手动浏览入口。

## 验证证据

使用项目捆绑 Python `D:/漫剧制作助手/运行环境/Python/python.exe`。

- 修改前：新增未知引擎回归失败，Google Gemini 4 未抛出错误，复现 Claude 回落问题。
- `python -m unittest tests.test_claude_program_detection tests.test_pet_ui.ModelPoolTests`：34 项通过（PYTHONPATH 包含程序和 tests）。覆盖路径匹配、桌面/CLI 分离、模式字段、保存、自动输入防抖及旧路径清空。
- `python smoke_test.py --affected pet_models_ui model_pool workflow_settings`：119 项通过、0 文件失败，冒烟汇总 9 项通过。
- `python smoke_test.py`：8 项通过。
- `git diff --check`：通过。
- `python smoke_test.py --architecture`：345 项初跑中 2 项失败。其一为新增函数导致审计行号漂移，函数移到文件尾后原 848/888 行恢复；其二为工作树缺少已登记 Git 子模块，使用主树本地仓库克隆补齐，提交 `1a43ae5a019d157eb3d45ad73e800081cb127763` 与 gitlink 一致，未修改子模块源码或版本。
- 失败闭环：`python -m unittest tests.architecture.test_skill_reference_injection tests.architecture.test_unification_ratchet tests.test_pet_ui.ModelPoolTests.test_typing_model_id_automatically_searches_after_debounce` 共 13 项通过；按增量复验规则未重复整套架构测试。
- 专项测试仍打印已有 pet_cloud 已忽略 TclError 提示；该提示不属于本轮模型管理回调，测试无失败。

## 边界与交付

- 本轮修改配置界面和程序定位，不增加新的模型执行适配器。模型名不保证存在同名桌面应用；未找到时不会猜测其他应用路径。
- 没有改动真实模型配置、密钥、主树状态文件或用户项目，没有自动启动或安装应用。
- 本分支源码需合入实际启动目录后才能在原运行应用中生效；本工作树启动应用可直接验证。
- 提交：本报告随修复源码一并收尾提交；最终提交号由 `git log -1 --format=%H -- 程序/tasks_round/tasks_round_1523_result.md` 查询，避免自引用提交号失真；未推送。

轮次说明：原领取 R1520，在提交前中央计数器已被其他任务推进；提交钩子拒绝旧号后，保存本轮改动并按正式入口重新领取 R1523，未绕过钩子。
