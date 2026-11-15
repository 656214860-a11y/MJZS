# R2925 结果：合并门禁三处确定性红修复（copy_rules 文案／project_menu 注入面／<Map> 误冲屧）
<!-- round-evidence: {"commit_base": "1286bc3a", "credential_hits": 0, "evidence_sha256": "3c8b1a632a916e3e", "exit": 0, "failed": 0, "passed": 26, "round": 2925, "tests": "run_selftests.py -k copy_rules project_page_services window_resize_coalescing"} -->

## 三问

1. **轮次类型**：修复轮（§3.2）。master 全量凭据连续被 3 个确定性红阻断（`test_copy_rules`、`test_project_page_services`、`test_window_resize_coalescing`），按「阻断当前验收的历史欠账」就地闭环，只改根因所在模块。
2. **测试跑了吗、三个基线过了吗**：跑了。默认冒烟 8/8 绿；三处定向全绿——`test_copy_rules` 14/14、`test_project_page_services` 5/5、`test_window_resize_coalescing` 7/7（证据 `evidence/R2925.json`）；未跑全量（合入 master 前由合并门禁按凭据口径执行）。
3. **欠账少了吗**：是。全量自检恢复可绿条件，R2924 合并轮后的源码轮次欠账重新具备闭环路径。

## 根因与修复

| 红项 | 根因 | 修复 |
|---|---|---|
| `test_copy_rules` | R2911 侧栏改版把项目新建按钮 Tooltip 写回全角「＋ 新建项目」，违反 ONE_NAME  canonical「+ 新建项目」。 | `desktop_project_pages.py` Tooltip 改回半角加号，文案回到唯一写法。 |
| `test_project_page_services.test_project_menu_uses_injected_context_menu` | R2911 把 `project_menu` 改为「先取 `_project_home_tree`、再委托 `_project_item_menu`」；测试的 SimpleNamespace 替身两者皆缺，`project_menu` 提前 return，注入的 `context_menu` 永远走不到。生产路径不受影响（真 Desktop 两者俱全）。 | 测试替身补 `_project_home_tree=tree` 与 `_project_item_menu` 委托接线；断言原样（仍断言 `context_menu` 以 `host.win` 恰好调用一次）。属 §2.4 允许的 mock 同步，结果文件注明。 |
| `test_window_resize_coalescing.test_quit_event_during_drag_is_not_deferred` | `on_window_map` 在判 `event.widget is self.win` **之前**就 `coalescer.flush()`；`<Map>` 经 bindtags 会把内容区整批后代控件的映射事件冒到顶层绑定，拖动冻结/解冻引发的 remap 风暴（实测一次拖动约 63 个后代 `<Map>`）把挂起的拖动合并逐次撤销，静默补做必然丢失。R2897 侧栏改版扩大了映射面后变成确定性红。 | `desktop_layout.py` 把「非本窗口事件直接 return」提到 `flush()` 之前：只有顶层窗口自己的 `<Map>`（最小化恢复）才撤销合并并重排，与函数 docstring 语义一致。 |

## 验证记录

- `smoke_test.py`：8/8 通过。
- 定向：`run_selftests.py -k copy_rules project_page_services` → 19 条全绿；`-k window_resize_coalescing` → 7 条全绿（修复前同环境确定性红，复现脚本确认 `<Map>` 风暴逐次 `flush()` 清空 `_pending`）。
- 未跑：`--all --safe` 全量（合入 master 前由合并门禁按 `full-safe-receipts.json` 凭据口径执行）。

## 过程损耗（如实）

- `test_project_page_services` 首轮修复仍红：漏掉 `project_menu` 先查 `_project_home_tree` 的前置条件，补上后转绿。
- 排查中确认 `<Map>` 误冲屧为 R1751 引入、R1792 冻结/解冻放大、R2897 改版后暴露的存量缺陷，非本轮新引入。
