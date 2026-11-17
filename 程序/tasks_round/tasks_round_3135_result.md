# R3135 功能轮结果：文件卡片与 HITL·轮 7/8——引用溯源 + 资产悬浮卡
<!-- round-evidence: {"commit_base": "1f1fbe57", "credential_hits": 0, "evidence_sha256": "7e7d03ed7c1fdda6", "exit": 0, "failed": 0, "passed": 4, "round": 3135, "tests": "run_selftests.py -k citation asset_hovercard"} -->

## 三问

1. **本轮属于 §3 哪种类型？** §3.1 功能轮（任务书《文件卡片与 HITL 交互任务书》轮 7/8）。
2. **测试跑了吗、三个基线过了吗？** 跑了：`test_citation.py`（2/2）、`test_asset_hovercard.py`（2/2）、六类 UI 边界（60/60）、默认冒烟、架构门禁（见下）。未跑全量 `--all --safe`（非 master 提交点）。
3. **欠账少了吗？** 无新增欠账；引用标记与资产悬浮卡两块知识-资产联动组件落地。

## 改动

- 新增 `ui/ui_citation.py`（L4）：
  - `insert_citations(box, name, text, on_open=, markers=)`：把正文里的 `[n]` 标记着色、绑定点击定位，返回标记数；
  - `citations_of(sources)`：source part 列表 → `{序号: source}`；
  - 引用上下文走独立字段（source part / markers），不原地改历史消息（A3）。
- 新增 `ui/ui_asset_card.py`（L4）：
  - `highlight_assets(box, name, text, assets, on_hover=)`：资产名最长优先匹配、加下划线并绑定悬浮，返回命中数；
  - `show_asset_hovercard/hide_asset_hovercard`：`BaseDialog`（非模态、无 chrome）显示正典图（`asset_thumbs`）与属性字段，鼠标离开即关。
- 新增测试 `tests/test_citation.py`（2 条）、`tests/test_asset_hovercard.py`（2 条，真 Tk）。
- 基线同步：覆盖率基线 542→544；skip 台账 +2；`runbook §11` 同步。

## 测试证据

- `python -B tests/test_citation.py` → `Ran 2 tests ... OK`（`[n]` 标记、tag 绑定、序号映射）。
- `python -B tests/test_asset_hovercard.py` → `Ran 2 tests ... OK`（最长名称优先、悬浮卡弹出/关闭）。
- `python -B -m unittest tests.architecture.test_button_boundary ... test_data_table_boundary` → 60 tests OK。
- `python -B smoke_test.py` → `通过：9 项`、`失败：0 项`（退出码 0）。
- `python -B smoke_test.py --architecture` → `Ran 483 tests ... OK`（`✅ 架构治理测试：tests/architecture`；覆盖率基线 544、skip 台账 303 口径同步）。

## 契约变更（§2.4）

- 新增 L4 `ui/ui_citation.py`、`ui/ui_asset_card.py`；弹窗走 `BaseDialog`、图片走 `asset_thumbs`、间距/颜色取 token。
- 零第三方依赖不变。

## 范围外 / 已知缺口

- 引用点击后的「侧栏/弹窗定位到原剧本片段」与资产悬浮卡的「正典图真实路径」由调用方注入（组件已提供回调位与 `asset_thumbs` 取图）。
- 悬浮卡的悬停延迟/防抖（`HOVERCARD_GAP_MS`）未做计时器，当前是即时弹出；接线 UI 时可加。
- 未跑全量 `--all --safe`（非 master 提交点）。

## 提交

- 分支 `codex/wip-R3135`；commit hash 见回填。
