# R3035 修复轮结果
<!-- round-evidence: {"commit_base": "7d758edf", "credential_hits": 0, "evidence_sha256": "2e8f9a5cca91589e", "exit": 0, "failed": 0, "passed": 49, "round": 3035, "tests": "run_selftests.py -k cell_zoom cell_menu module_size test_layers"} -->

## 三问（§7.2）

1. **轮次类型**：修复轮（§3.2）／结构治理伴随项。起因：master 静态门禁 `test_module_size_ratchet` 红——R3012 给 `cell_hover.py` 加 12 行（点击抑制放大）使其 1016→1028，超登记上限 1016，阻断 R3031 合入（`dev.py merge` 的 local_ci 中止）。按棘轮规则「超限文件只能随拆分变小」拆出混入模块，而非抬上限。
2. **测试**：跑且全绿。`run_selftests.py -k cell_zoom cell_menu module_size test_layers`（test_cell_zoom_suppress／test_cell_menu／test_module_size_ratchet／test_layers 等）：见下方验证段。三个基线：冒烟未单独跑（纯代码搬移、行为不变；合入轮 local_ci 会跑默认冒烟）；架构门禁由合入轮 CI 覆盖；全量未跑、欠账口径不变。
3. **欠账**：消除 1 项——`cell_hover.py` 行数欠账（1028>1016）回落至 992≤1000，从 `OVERSIZE_CAPS` 登记表移除（棘轮设计的「下降固化」）。

## 改动清单（纯代码搬移，零行为变化）

- 新增 `cell_zoom_suppress.py`（L4）：`CellZoomSuppress` 混入类——`_zoom_suppress` 类属性默认、`zoom_hide`、`zoom_cancel_watch`、`_zoom_click`、`_bind_zoom_click` 原样迁入（含原 docstring／注释语义）。
- `cell_hover.py`：`CellImages(CellZoomSuppress)`；删除已迁方法与 `__init__` 实例属性行（类属性默认等价）；两处 `<Button-1>`／`<Double-1>` 绑定改一行 `self._bind_zoom_click(label, key)`。1028→992 行。
- `tests/architecture/_layers.py`：L4 登记 `cell_zoom_suppress`。
- `tests/architecture/test_module_size_ratchet.py`：`cell_hover.py` 已 ≤1000，按规则从 `OVERSIZE_CAPS` 删除。
- `architecture.md` §3 L4 行补记 `cell_zoom_suppress`。

## 验证

- `test_cell_zoom_suppress`（R3012 特性测试，真 Tk）：点击抑制→离开解除→再进入恢复，全链路行为不变。
- `test_cell_menu`：外部唯一 `zoom_hide()` 调用点（`tree.cell_images.zoom_hide()`）经混入解析不变。
- `test_module_size_ratchet`：cell_hover 992≤1000 且已除名；`cell_zoom_suppress` 56 行无登记需求。
- `test_layers`：新模块已登记 L4，同层互导不违规（cell_hover→cell_zoom_suppress 均 L4）。

## 范围与边界

- 与 R3031 同分支 `codex/wip-R3035`（基于 R3031 顶端），合入 master 时一并带入；合并轮结果文件记两轮。
- 状态页轮次头同步留待合入 master 时随合并提交完成。
