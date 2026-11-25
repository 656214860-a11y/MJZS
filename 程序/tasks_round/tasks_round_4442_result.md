# tasks_round_4442_result — EC-5B 错误代码界面查表接线（ui_status_bus＋video_progress）
<!-- round-evidence: {"commit_base": "ee2066ee3", "credential_hits": 0, "evidence_sha256": "fb5382668d7d4efa", "exit": 0, "failed": 0, "passed": 188, "round": 4442, "tests": "run_selftests.py -k ui_status_bus ui_status_bar video_task_status video_ui startup_selfcheck"} -->

- 本轮属于 §3.1 功能轮（EC-5 错误代码统一任务书 §4.5 L4 UI 查表接线子卡；只动 L4 显示与对应测试，不动 L0 登记表与四张映射表）。
- 测试跑了吗、三个基线过了吗：跑了卡面 3 条验收命令，全部退出码 0——定向 `run_selftests.py -k ui_status_bus ui_status_bar video_task_status video_ui startup_selfcheck`（188 条 0 红）；`smoke_test.py --affected ui_status_bus video_progress`（前置 10/10，23 个测试文件 0 红）；`smoke_test.py --architecture`（708 条 OK）。
- 欠账少了吗：两处用户可见错误文案改经 EC-5 映射表→`contract.error_codes.describe()` 统一出口，登记表成为唯一文案源；未新增欠账。

## 缺陷复现方式与改前红

按卡面先写测试：`tests/test_startup_selfcheck.py` 的 `StartupAnnounceTests` 断言改为 `describe(SELFCHECK_TO_CODE[...])` 契约并新增 `test_items_render_via_error_code_registry`（断言 `[E-`、`（建议：`、`describe('E-UNKNOWN')`、原始自检 code 不上屏）；`tests/test_video_task_status.py` 的 `test_detail_adds_error_class_and_action` 改为 `describe(VIDEO_FAILURE_TO_CODE[...])` 契约。

改产品前运行 `run_selftests.py -k ui_status_bus ui_status_bar video_task_status video_ui startup_selfcheck`，退出码 1，共 5 条红，红因与缺陷一致（显示点仍输出旧手写文案，未走登记表）：

1. `test_detail_adds_error_class_and_action`：`status_detail` 输出旧标签「鉴权/模型协议/本机磁盘」，不含 `describe(...)`/`[E-`。
2. `test_degraded_items_become_one_warning_with_prefix`：状态栏输出 `disk-space-low：…` 原文，不含 `describe(SELFCHECK_TO_CODE['disk-space-low'])`。
3. `test_items_render_via_error_code_registry`（新增）：输出不含 `[E-`/`（建议：`/`describe('E-UNKNOWN')`。
4. `test_same_code_is_announced_once_per_launch`：`text.count(describe('E-IO-WRITE'))` 为 0（旧文案不含登记表文字）。
5. `test_install_false_records_degraded_and_status_warning`：总线文本含 `app-log-unavailable` 原文，不含 `describe('E-UNKNOWN')`。

## 改了哪几处

- `ui/ui_status_bus.py:170-201` `publish_startup_warnings`：在既有 `try` 内懒加载 `contract.selfcheck.SELFCHECK_TO_CODE` 与 `contract.error_codes.describe`；逐项由自检 code 经 `SELFCHECK_TO_CODE.get(code, 'E-UNKNOWN')` 映射后以 `describe(mapped)` 生成 `[E-XX] 说明（建议：…）`。保留原契约不变：`【警告】启动自检：` 前缀、按**原始自检 code** 去重、最多显示 4 条、超出折叠 `等 N 项`、`；处理建议见诊断导出` 尾缀、空/None 静默、`app_logging.swallowed()` 异常兜底（import 失败也只吞掉播报，不影响启动）。
- `ui/video_progress.py:5-7,150`：顶部新增 `VIDEO_FAILURE_TO_CODE`（L2 `domain.video_task_state`）与 `describe`（L0 `contract.error_codes`）导入；`status_detail` 错误分类段由 `'错误分类：'+ERROR_LABELS[kind]+'，'+ERROR_NEXT[kind]` 改为 `'错误分类：'+describe(VIDEO_FAILURE_TO_CODE.get(kind,'E-UNKNOWN'))+'，'+ERROR_NEXT[kind]`。`（下一步：…）`、可行动作指引（`补配置`/`重做`/`不要重投` 等 `ERROR_NEXT` 原文）、`provider_failure_reason(version)` 的「已取消/已过期/原因未知」原文分支全部保留；`ERROR_LABELS` 常量保留（`tests/test_error_codes.py` AST 解析其键集作 A3 闭集权威枚举，该文件不在允许清单），仅不再驱动显示。
- `tests/test_startup_selfcheck.py`：顶部导入 `describe`/`SELFCHECK_TO_CODE`；`StartupAnnounceTests` 三条断言按新契约同步并新增 1 条登记表断言（逐条依据见下）；`AppLogInstallFailureTests` 子进程 wrap.py 桩在 `contract_pkg` 上补挂 `_load_real` 的 `contract.error_codes` 与 `contract.selfcheck`——桩只加载了 `contract.diagnostics`/`ui_status_bus`，不补则函数内 `from contract.selfcheck import …` 抛 ImportError 被兜底吞掉、总线恒空，测试变成恒真空转；两条 bus 断言同步（依据见下）。`selfcheck_records`/`window_degraded` 仍断言原自检码 `app-log-unavailable`，未动。
- `tests/test_video_task_status.py`：导入扩 `VIDEO_FAILURE_TO_CODE`/`describe`；`test_detail_adds_error_class_and_action` 断言改为 `describe(VIDEO_FAILURE_TO_CODE[kind])`＋`[E-`/`（建议：`＋原有动作文案（`补配置`/`重做`/`不要重投`）断言。

## 前后文案对照

### 接线点 1 — 状态栏启动自检警告（`publish_startup_warnings`）

入参 `Diagnostic(code='disk-space-low', message='磁盘不足')` 与 `('model-pool-empty', '模型池为空')` 为例：

- 改前：`【警告】启动自检：disk-space-low：磁盘不足；model-pool-empty：模型池为空；处理建议见诊断导出`
- 改后：`【警告】启动自检：[E-IO-WRITE] 写入文件失败（建议：检查磁盘空间与目录权限）；[E-CONFIG-INVALID] 配置无效或缺失（建议：检查对应配置项后重试）；处理建议见诊断导出`
- 未进表码（如 `app-log-unavailable`）：`SELFCHECK_TO_CODE.get(code,'E-UNKNOWN')` → `[E-UNKNOWN] 发生了未分类的错误（建议：查看日志中的详细信息后重试）`，原始 code 不再上屏。

### 接线点 2 — 视频页错误分类（`status_detail`，`{'state':'failed','error':'401 invalid api key'}` → kind='auth'）

- 改前：`失败（下一步：看错误后显式重做） · 错误分类：鉴权，补配置：检查密钥 · 原因：…`
- 改后：`失败（下一步：看错误后显式重做） · 错误分类：[E-AUTH-REJECTED] 凭据被服务拒绝（建议：检查密钥是否有效、是否过期），补配置：检查密钥 · 原因：…`
- `kind='disk'`：`本机磁盘` → `[E-IO-WRITE] 写入文件失败（建议：检查磁盘空间与目录权限）`，后随 `清理本机磁盘后重新取回` 动作原文。

## 契约变更依据（逐条）

按 §2.4，显示文案契约经 EC-5B 有意变更，同步以下断言；行为断言（去重、折叠、静默、动作指引）保持原样：

1. `test_degraded_items_become_one_warning_with_prefix`：`'disk-space-low' in text`/`'model-pool-empty' in text` → `describe(SELFCHECK_TO_CODE[...]) in text`。依据：自检 code 不再直接上屏，改经映射表→describe()。
2. `test_same_code_is_announced_once_per_launch`：`count('disk-space-low')==1` → `count(describe('E-IO-WRITE'))==1`。依据：去重仍按原自检 code（实现未变），显示文案变为 mapped describe()。
3. `test_install_false_records_degraded_and_status_warning`：bus 断言 `'app-log-unavailable' in text` → `describe('E-UNKNOWN') in text`。依据：该码不在 `SELFCHECK_TO_CODE`，兜底 `E-UNKNOWN`；`selfcheck_records`/`window_degraded` 的原码断言不动。
4. `test_install_retry_success_stays_silent`：无 `app-log-unavailable` 上屏 → 无任何以 `【警告】启动自检：` 开头的文本。依据：旧断言在新文案下无法触达（原码不上屏），改为等价的「无自检警告」语义，非放宽。
5. `test_detail_adds_error_class_and_action`：`鉴权`/`模型协议`/`本机磁盘` → `describe(VIDEO_FAILURE_TO_CODE[...])`＋`[E-`/`（建议：`；`补配置`/`重做`/`不要重投` 动作断言保留。依据：手写中文标签由登记表文案统一替换。
6. wrap.py 桩补挂 `contract.error_codes`/`contract.selfcheck`：按 §2.4 契约变更可同步 mock/导入路径；属测试基建修正（否则被测函数 ImportError 被吞），非断言弱化。

## 不接线范围（卡面指明，未触碰）

A1 致命弹窗（L5-E3，`fatal_diagnostics_text`）、A2 模型路由 reason 显示、A4/A5 三虎气泡、A6 账户页 `desktop_account_page.py`——本卡只接 A1 状态栏逐项与 A3 视频页错误分类两个 L4 点；上述显示点仍输出各自原文案。

## 改后验收命令输出尾部（原文）

### 命令1 `run_selftests.py -k ui_status_bus ui_status_bar video_task_status video_ui startup_selfcheck` → 退出码 0

```
共 188 条用例，29.4 秒；0 个文件有红
实际跳过 0 条用例：本机没有任何登记位被跳过
ALL TESTS PASSED
```

### 命令2 `smoke_test.py --affected ui_status_bus video_progress` → 退出码 0

```
✅ 门禁 run_selftests.py（定向：ui_status_bus、video_progress）：87 秒 → 0 个文件有红
通过：10 项
失败：0 项
✅ 冒烟测试通过，可以进入下一轮
```

`--affected` 选定 23 个消费者测试文件（含 test_video、test_video_revision、test_media_page_controller、test_usage_indicator_ui、test_ui_status_bar 等），全部绿。

### 命令3 `smoke_test.py --architecture` → 退出码 0

```
Ran 708 tests in 332.296s
✅ 架构治理测试：tests/architecture
OK
```

## 三个基线数

- 冒烟前置检查：10/10 项通过（命令2 实测）。
- 架构门禁：708 条全过、失败集合为空（改后实测；改前基线 ee2066ee3 同口径 708 条，见 tasks_round_4417_result.md，本卡未触碰架构登记、层级边或 L0/L2 文件）。
- 全量回归 `--all --safe`：未跑（分支不累计；`full-safe-receipts.json` 无本卡新增欠账）。

## 没有验证的地方 / 卡外发现（不顺手修）

- 真机启动一次看状态栏渲染效果未人工核验；文案由 `describe()` 单元契约与 `test_items_render_via_error_code_registry` 断言覆盖。
- `test_ui_status_bar.py`、`test_video_ui.py` 在允许清单内但无需改动：status_bar 只渲染总线文本、video_ui 断言层级不触及错误分类文案，定向与 --affected 均已证绿。
- 基线缺陷 `test_distribution_selfcheck.test_manifest_covers_every_file`（R4417 已登记）在本轮 `--tests` 关键词命中范围外，不影响三条验收命令。
