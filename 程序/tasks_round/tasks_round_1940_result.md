# R1940 结果：结构治理轮（八维度清理 · 第二批）

- 本轮类型：结构治理轮（瘦身）。分支 `codex/wip-R1940`，从 master `f8cd6420` 切出。断言未动。

## 改动及等价理由

- 删除 `platform_tools.window_outer_rect`、`platform_tools.outer_rect_for_client`（共 27 行）。依据：全仓（含 tests、skills、文档、`.json`／`.pyw`）该名字只出现在定义处，无任何调用；仅 R1411 启动画面用过，后续被摘掉调用，R1788 死代码清理时漏网。无动态导入路径引用。

## 八维度摸底（本批新增结论）

- 合并类型定义：模块级 `set/tuple/dict` 常量按 ast 内容比对，跨模块**无完全相同者**，本维度无安全可合并项。
- 死代码：顶层函数／类按全仓标识符计数，仅这 2 个零引用，其余均至少被引用一次（“被引用”不等于“被用到”，更深的死代码需人工）。

## 测试

- `py_compile platform_tools.py`、`run_selftests.py -k platform static_names splash startup`：50 条全绿。
- `--layer architecture --all`：4 个文件红，**均不是本轮造成**：`test_agents_md`、`test_skill_reference_injection`（工作树缺未入库文件）；`test_complexity_ratchet`（`Desktop` 1303 行 > 上限 1302 等，来自别的会话的会员账号页改动）；`test_copy_entry_boundary`（`desktop_account_page.py` 直写剪贴板，同源）。后两条属 master 现有红，待账号页那条线处理。
- `--all --safe` 未运行。
