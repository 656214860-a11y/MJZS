# R2081 修 R2076 合并后遗留的 3 个红项：本机模型池隔离、假侧栏缺 exists、聊天历史回填时序（修复轮）

轮次类型：修复轮。日期：2026-10-30。分支 `claude/fix-test-isolation`，基于 master `4bbf8411`。 先领 R2079，提交时中央计数器已被其他会话推进到 R2080，改领 R2081。

- 本轮运行：`run_selftests -k test_core test_idea_chat test_writing_api`（335 条，连跑 2 次，0 红）、默认 `smoke_test.py`（8/8）。未运行 `--all --safe`，由提交后的后台全量补跑。`project_status.md` 债务未减少：这 3 个红项此前未单独登记为待办。
- 运行环境：worktree 缺 `skills/00全流程SKILL/AIGC创作全流程` 子模块，所以测试在临时基线目录 `D:\tmp_r2079`（`HEAD` 的 detached worktree，补入子模块内容和主目录 `配置/宠物/配置.json`）里跑。先在该目录用未修改的测试复现了 `test_writing_api` 和 `test_core` 红项，再换上修复后的测试文件。
- 只改测试同步，断言未动。

## 修复

1. `tests/test_writing_api.py::test_api_formal_script_reuses_download_path_and_versions_changed_text`
   - 原因：`idea_document_paths.storage_identity` 经 `legacy_compat.optional_model_identity` 读真实程序目录下的 `配置/宠物/配置.json` 模型池。本机配置把「DeepSeek V4 Flash」解析成「自定义」，正式稿文件名变成 `proj_自然剧本_自定义_<日期>.md`。
   - 修复：用例内 `patch('model_pool.pool', return_value=model_pool.default_pool())`，与同文件其他用例的隔离方式一致。
2. `tests/test_core.py::test_script_stage_project_loads_without_storyboard_json`
   - 原因：R2056／R2058 让 `Desktop.load` 先调用 `self.list.exists()` 再判断分组是否展开；用例手搭的假侧栏 `ProjectList` 只有 `selection_set` 和 `see`。
   - 修复：假侧栏补 `exists` 并返回 False，对应“项目不在侧栏列表”。属契约变更后同步 mock。
3. `tests/test_idea_chat.py` 的 8 条气泡用例（`BubbleLayoutTests` 中读取历史气泡的用例）
   - 原因：聊天历史在首绘后由 `desktop_idea_deferred` 延迟回填；这些用例在 `show(0)` 后只调用一次 `win.update()`，偶发读到「正在读取聊天记录…」、`bubble_0` 标签未定义或 `_bubble_edit` 不存在。
   - 修复：改为调用同文件已有的 `self.settle_script_page(win)` 等回填完成（R2071 已让它等 `_idea_page_update_job`）。

## 未处理

- 10-26 后台全量里的 `test_leak_teardown`、`architecture.test_round_baselines` 本轮未复核，留给提交后的后台全量判断。
- 未 push。
