# R859 结果｜TODO 注释 AST 快照

缺陷台账的 TODO／暂时／待补／后续再／先这样检索，现以 AST 所属函数和 tokenize 注释位置生成可复验快照。生产顶层代码当前匹配 3 条：`asset_detail.py:346`、`desktop.py:2403`、`pet_ui.py:2784`；均分类为 C 类“已实现行为说明”，不把注释文字误判为真实缺陷。后续新增或移动关键词必须先进入快照并写明分类、处置与理由。

验证：`tests.architecture.test_todo_comment_snapshot` 2 条／0 红；`run_selftests.py --layer architecture --all --safe` 228 条／81.8 秒／0 红；`run_selftests.py --layer service --all --safe` 1,661 条／71.9 秒／0 红；`run_selftests.py --layer gui-short --all --safe` 1,141 条／320.4 秒／0 红；`run_selftests.py --layer gui-e2e --all --safe` 673 条／341.3 秒／0 红，均输出 `ALL TESTS PASSED`。默认 `smoke_test.py` 8/8 通过。

`[TASK_COMPLETE]`：TODO 注释已具位置、范围和处置的冻结快照；本轮全量安全分层与默认烟测均通过。
