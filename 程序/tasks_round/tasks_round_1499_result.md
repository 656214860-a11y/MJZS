# R1499 结构治理轮：拆分 desktop.py 步骤 3（第 1 页：剧本准备页 `writing`）

1. **本轮类型？** 结构治理轮（只搬代码，不改逻辑；一页一轮）。
2. **测试与基线？** 默认冒烟 8/8；架构门禁中与本轮相关的全部通过（首次 10 项红，均为“被检代码换了文件／缺登记”，处理见下，断言未动）；全量与 `.wt/ci` 干净检出验证见提交后记录。
3. **是否欠账？** 改了层级登记表（风险路径），须全量转绿。

## 改动

- 新增 `desktop_writing_page.py`（L4）：`WritingPageMixin` 原样承载 `writing`（剧本准备页构建，576 行）及只被它使用的 `TALK_MIN_LINES／TALK_MAX_LINES`；`Desktop(WritingPageMixin, IdeaChatMixin, AutoFlowsMixin)`；`desktop.py` 5906 → 5328 行（累计自 7820 降 2492 行）。
- **补丁兼容**：`writing` 的方法体用到 `confirm／open_path／ContextMenu／confirm_project_removal_from_last_script`，测试按 `desktop.<名字>` 打补丁。新模块里这四个名字是转发函数，调用时取 `desktop` 里的当前值；`desktop` 在模块级调用 `bind_host(sys.modules[__name__])` 登记自身。新模块不导入 `desktop`，没有导入环（第一版用函数内 `import desktop`，被 `test_no_circular_import` 判为环，改成登记方式）。
- 补充：`desktop.py` 加 `import sys`（`bind_host` 用）。

## 架构门禁的调整（断言未动）

- `test_data_table_boundary`、`test_script_rename_boundary`：被检的 `writing`／`continuity_page`／`assets` 等方法改在“Desktop 全部类成员”里找（`parse_desktop()`）；`test_shortcut_registry_boundary`：改查 `desktop_text()`。
- `test_startup_budget`：`writing` 在启动链上，原清单里 `desktop.py` 项去掉 `writing`，新增 `desktop_writing_page.py: (WritingPageMixin, writing)`，启动链覆盖不变。
- `_scan.DESKTOP_PARTS` 加入新模块；`_layers.py` 登记 `desktop_writing_page`（L4）；`test_module_size_ratchet`：`desktop.py` 上限 6000 → 5400；TODO 注释快照按原分类更新；`architecture.md`、`PROJECT_MAP.md` 同步。

## 与本轮无关的红（别的车道刚合入）

R1496–R1498（SKILL 升级、制作锁）合入后，架构门禁另有 3 项红：`test_layers`（新模块 `production_lock_fields` 未登记层级）、`test_skip_hygiene`（skip 台账 226 对源码 227）、`test_skill_reference_injection`（`production_lock_fields` 相关）。均不涉及 `desktop*.py`，不在本轮处理，请对应车道补登记。

## 提交

已提交，见 git log 标题 `R1499:`。

## 补记：全量暴露的第二批（已并入本提交）

- `test_ui_edges`（3 项）读 `desktop.TALK_MIN_LINES／TALK_MAX_LINES`：`desktop` 重新导入这两个常量。
- `test_script_workspace_results`（2）、`test_writing_restart`（1）：从 `desktop.py` 源码里取出嵌套的 `rename_script`／`script_menu`／`writing` 来执行，改指 `desktop_writing_page.py`（类名 `WritingPageMixin`）；`test_perf_baseline`：`inspect.getsource(Desktop)` 改为按整条继承链取源码。断言未动。
- 这批和步骤 2 一样是“按文件读 `desktop.py`”的测试；先 `grep -rn "desktop.py" tests` 只找到 import 式读取，**漏掉了 `with_name('desktop.py')`／`inspect.getsource(Desktop)` 这类写法**，以后用 `Desktop` 方法名反查测试更可靠。
