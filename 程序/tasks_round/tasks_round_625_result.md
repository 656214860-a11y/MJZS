# R625 功能轮结果：桌面引擎安装状态标注

## 开工三问（AGENTS.md 第 7 节）

1. 本轮是功能轮：为模型池与阶段配置中的桌面引擎增加只读展示标注。
2. 已运行默认冒烟与架构基线：默认 `smoke_test.py` 为 8/8，`smoke_test.py --architecture` 为 101/101。全量安全基线不在本轮必跑范围，未运行；受影响门禁的既存失败见“验证”。
3. `project_status.md` 的已知欠账未减少；本轮只完成用户选择的 UI 可见性改进。

## 改动文件与标注形式

- `model_pool.py`：`options()` 与 `label_of()` 新增可选展示标签回调；默认返回原标签，模型 ID、候选集合、保存/读取逻辑均不变。
- `workflow_settings.py`：新增进程内 `_DESKTOP_INSTALLATION_CACHE` 与 `desktop_model_label()`；该函数复用既有 `find_program()`，失败（包括异常）统一返回原显示名加 `（未安装）`。
- `skill_panel.py`：阶段配置模型下拉传入上述展示回调。
- `pet_models_ui.py`：模型池设置页候选和当前显示名传入同一展示回调。
- `tests/test_model_pool.py`、`tests/test_workflow.py`：新增安装、未安装、探测异常、缓存次数，以及已选未安装模型保存/执行边界回归。
- `project_status.md`：按连续轮次台账将待执行轮次推进至 R625（本结果写入后推进至 R626）。

标注采用显示名后缀，例如 `ChatGPT Desktop · Codex（未安装）`。底层值仍为 `chatgpt-desktop` / `claude-desktop`；`id_of_label()` 根据当前展示候选反查原 ID，因此既有选择的保存和读取不受影响。

## 探测入口与边界

只调用既有 `workflow_settings.find_program({'engine': engine, 'program': ''})`：该入口本来就使用命令名检查、固定 Codex 安装目录和固定 Claude 路径。没有新增探测实现、没有启动时调用、没有递归扫描（无 `rglob`/`os.walk`）、没有落盘。

查询是首次构造模型池或阶段配置候选时按需发生；缓存键为引擎名 `codex` / `claude`，同一进程每个引擎最多一次。探测异常被捕获为“未安装”，不会传入 Tk UI。清空函数仅供测试/本进程维护使用，不写任何配置。

`workflow_settings.current()` 的桌面模型映射、已有项目的模型 ID 和 `workflow_engines.launch_interactive()` 对未找到程序抛出的既有 `ValueError` 均未修改。

## 新增/调整回归断言

1. mock `find_program()` 成功时，两个桌面模型显示名均不含 `未安装`。
2. mock `find_program()` 抛 `ValueError` 时，两个显示名均含 `未安装`。
3. mock 探测抛任意 `RuntimeError` 时，同样标注且异常不冒泡。
4. 同一引擎重复构造显示标签只探测一次；两种引擎合计两次，防止 UI 重复访问磁盘。
5. 已选 `chatgpt-desktop` 的阶段配置读取后仍是 `codex` 引擎，写回的模型 ID 仍为 `chatgpt-desktop`；mock 未安装时阶段执行仍抛原有受控 `ValueError`。
6. 原精确显示名断言调整为前缀断言，以允许仅 UI 层附加状态后缀；原显示名、模型 ID 与执行路由仍被断言。

定向新增回归：

```text
python -m unittest tests.test_model_pool.RecordTests tests.test_workflow.DesktopModelPoolTests
Ran 16 tests ... OK
```

## 验证

```text
python smoke_test.py
8/8 passed

python smoke_test.py --architecture
101/101 passed
```

```text
python smoke_test.py --affected model_pool workflow_settings skill_panel pet_models_ui
定向门禁覆盖 test_model_pool、test_pet_settings、test_skills；本轮新增的 16 条专项均通过。
```

该受影响门禁未全绿，且失败均非本轮引入：

- `tests.test_model_pool.NamedKeyTests.test_save_and_read_back_by_name` 与 `test_the_same_name_overwrites_instead_of_appending`：`model_secrets.protect()` 报 `Windows 无法读取或保存模型 API Key`，是当前运行账户 DPAPI 可用性问题，和桌面程序安装标注无调用关系。
- `tests.test_skills.ToolTests.test_every_tool_in_the_registry_is_known`：缺 18 个工具注册项；与本轮模块无关。
- `tests.test_skills.SkillTests.test_the_skill_boxes_follow_the_flow_order`：当前音频阶段多出 `pipeline-audio-subtitle`，属于既存 SKILL 清单/顺序基线漂移；与模型池无关。

手工启动（受控）：以项目内置解释器启动 `app.py`，进程在 8 秒后仍存活（PID 9392），说明启动未崩溃；因本自动化环境没有可操作的 Windows 应用表面，无法截图读取下拉文字，随后用 `Stop-Process -Force` 结束该临时实例，未留下进程。代码路径与专项回归已覆盖模型池、阶段配置的标签构造。

## 用户数据确认

本轮没有调用任何项目配置写入接口，也没有修改 `skill_config.json`、工作流调用设置、密钥或用户项目数据。标签只在候选展示时计算，缓存仅在 Python 进程内存中。

## J 后续

- 待办 B：单独诊断 `workflow_settings.current()` 是否在读取阶段配置时自动改走桌面引擎；本轮未触碰该逻辑。
- 待办 C：单独盘点 `token_saver`、`codex_paste`、`codex_tasks` 的可见性与外部 Codex 安装状态的关系；本轮未触碰。

## 自审

- 只改模型池/阶段配置的 UI 展示标签与必要回归；没有隐藏、禁用、移除模型，也没有改变执行行为。
- 复用了唯一既有 `find_program()` 入口；没有引入第三套探测或启动时扫描。
- 未新增落盘缓存，未修改用户数据、配置、密钥。
