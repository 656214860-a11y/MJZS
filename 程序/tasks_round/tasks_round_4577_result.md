# R4577 轮次结果（PB-B2：S04 分镜预演只读优先复用 S05 已入库正式资产图）
<!-- round-evidence: {"commit_base": "edf3dc709", "credential_hits": 0, "evidence_sha256": "34ff281bb02b4420", "exit": 0, "failed": 0, "passed": 40, "round": 4577, "tests": "run_selftests.py -k animatic_references animatic_service"} -->

- **本轮属于 §3 哪种类型**：3.1 功能轮（在保持 13 阶段顺序与 `04分镜预演` 目录契约不变的前提下，为 S04 分镜预演接入只读优先复用 S05 正式资产图链路，并同步状态栏计数与 `REQ-S04-113`／`DES-S04-36`）。
- **测试跑了吗、三个基线过了吗**：已运行——定向＋核心架构套件 76/76 通过（含 `test_animatic_references` 21 条、`test_animatic_service`、`test_copy_rules`、`test_layer_relations`、`test_module_size_ratchet`、`test_requirement_traceability`、`test_static_hygiene`）；隐藏桌面 `test_animatic_page` 83/83 通过；默认冒烟 9/9 通过；`smoke_test.py --affected animatic_references` 10/10（21/21 用例，1.1s）通过；完整全量安全回归留待本任务书收尾轮统一执行。
- **欠账少了吗**：`REQ-S04-113`／`DES-S04-36` 闭环并翻绿为 ✅，零新增 L2 同层导入边（LR-03），零新增模块行数超限（`stage_execution_service.py` 979/1000、`ui/animatic_page.py` 944/1000），零新增欠账。

## 改动清单

- `程序/domain/animatic_references.py`：
  - 新增 `formal_asset_entries(plan, registry, base)`（纯函数，无任何新增 L2 同层 import）：仅采信图片登记表 `<资产库>/assets.json` 中路径安全、非空、合法扩展名（`.png`/`.jpg`/`.jpeg`/`.webp`）且文件真实存在的角色与场景正式资产图，排除 `requires_asset=False` 及 `background`／`bg` 条目，按精确编号（`CHAR_###`／`LOC_###`）与规范化名称／别名（`aliases`）建索引，杜绝同姓氏或 `CHAR_001`／`CHAR_002` 串图。
  - 扩展 `refs_for_shot(shot, lib, *, formal_assets=None)`：按「S05 正式资产图 > 共享参考库（角色／场景）> 全部风格图 > 未分类回退」优先级自动配图，去重保序；无 `formal_assets` 时行为与既有完全一致。
- `程序/orchestrator/stage_animatic_gateways.py`：
  - 新增 `formal_animatic_assets(project)`（严格只读）：通过 `domain.asset_context.library_dir` 与 `file_cache.read_json` 读取资产清单与图片登记表，调用 `formal_asset_entries`；S05 未建库、缺文件或 JSON 损坏时静默降级返回空结构，绝不创建或改写 S05 目录与文件。
  - `refs_for_animatic_shot(project, shot)` 自动传入 `formal_assets=formal_animatic_assets(project)`。
- `程序/stage_execution_service.py`：
  - 向 L4 转发 `formal_animatic_assets`（行内合并至现有 import 行，文件保持 979/1000 行）。
- `程序/ui/animatic_view_state.py`：
  - `format_status_summary(..., formal_count=0)`：`formal_count == 0` 时与既有文案字节级一致；`formal_count > 0` 时显示 `参考图 {total} 张（含资产 {formal_count} 张）`。
- `程序/ui/animatic_page.py`：
  - `_update_summary` 读取 `stage_execution_service.formal_animatic_assets(self.project)` 计数并传入 `format_status_summary`。
- `程序/tests/test_animatic_references.py`：
  - 新增 `FormalAssetReuseTests`（4 条，锚定 `REQ-S04-113`）：覆盖编号隔离与无效图过滤、同镜正式图优先＋共享库回退＋风格图附加、网关严格只读与缺库降级、状态栏合并计数与零资产兼容。
- `程序/docs/stages/S04_分镜预演.md`：
  - `REQ-S04-113` 与 `DES-S04-36` 翻绿为 ✅，同步更新 `测试锚定`。

## 先红后绿证据

改动产品代码前先新增 `FormalAssetReuseTests` 并运行 `tests.test_animatic_references.FormalAssetReuseTests`，实测 4 条用例均未通过：
- `test_req_s04_113_formal_asset_entries_distinguish_ids_names_aliases_and_filter_invalid`：`ImportError: cannot import name 'formal_asset_entries' from 'domain.animatic_references'`
- `test_req_s04_113_formal_assets_take_priority_with_shared_fallback_and_styles`：`ImportError`／`TypeError`（`refs_for_shot` 尚未支持 `formal_assets` 参数）
- `test_req_s04_113_gateway_reuses_s05_read_only_and_degrades_when_missing`：`AssertionError`（网关尚未自动读取 S05 正式图）
- `test_req_s04_113_status_summary_counts_reusable_formal_assets`：`TypeError: format_status_summary() got an unexpected keyword argument 'formal_count'`

改动后全部通过：
- 定向与核心架构门禁（7 模块）：76/76 通过（30.96s）
- 隐藏桌面 `tests.test_animatic_page`：83/83 通过（20.97s）
- `smoke_test.py`：9/9 通过（含隐藏桌面探针）
- `smoke_test.py --affected animatic_references`：10/10 通过（21/21 用例，1.1s）

## 提交状态

- 分支：`codex/pb-s04-s05-decouple`
- 提交方式：经 `scripts/dev.py commit` 提交（含证据文件 `tasks_round/evidence/R4577.json`）。
