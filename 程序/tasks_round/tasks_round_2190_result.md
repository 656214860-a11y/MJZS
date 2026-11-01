# R2190 结果：合入 claude/model-deletion-issue-6e8e80（R2166 删掉的模型不再被补回、R2174 模型列表加「调用方式」列）到 master（合并轮）

## 三问
- 轮次类型：合并轮（§3）。用户要求把分支 `claude/model-deletion-issue-6e8e80` 合入 master。
- 测试和三个基线：在主检出 master 合并后的树上运行（合并前 master 为 04abbdfd），都经 `工作流任务/gui_hidden.py`。
  - 定向自检 `run_selftests.py -k <59 个关键词>`：共 1830 条用例，1 个文件有红：`test_client_profiles.ProfileLoadingTests.test_req_s01_56_builtin_catalog_covers_every_known_client`（多出 `claude-2/3/4/5`、`node` 五个档案）。原因是主检出 `程序/data/客户端档案.json`（被 .gitignore 忽略的本机用户数据，11-01 11:12 写入）里有这五条用户档案，测试读真实用户档案文件而不是只读内置目录；与本轮改动无关，不属于本轮范围，未改测试。把 `client_profiles.USER_FILE` 指向空临时文件后单跑 `test_client_profiles` 24 条全过。其余全绿，之前 worktree 里缺子模块造成的 20 个红文件在主检出不再出现
    - 关键词里有 57 个取自 `smoke_test._affected_test_plan(['pet_models_ui', 'model_pool', 'skill_panel_support', 'stage_config', 'pet_ui_settings'])`，即 `smoke_test.py --affected` 对这 5 个改动模块会跑的全部消费者测试，另加 `button_consistency`、`storyboard_page_controller`。
    - 没有直接用 `--affected`：它走串行门禁，整批超时 `GATE_TIMEOUT = 900` 秒，而这批测试各文件用时相加约 900 秒，串行跑不完。改用并行的 `run_selftests.py`，选中的测试文件相同。
  - 默认冒烟：8 项全过
  - `smoke_test.py --architecture`：411 项全过（含模块行数上限、轮次连续性）
  - 全量 `--all --safe` 本轮未运行。master 6ce35959（R2183）的后台全量 13:42 结束，退出码 0，用时 709 秒，凭据已写入；到 R2185 为止 R2183 之后改过源码的轮次为 0（`auto_full_safe.py --status`），本轮最多是第 1 个，不到 8 个。本次合并没有改启动入口、Tk 控件的销毁／重建、`storage_maintenance.py`、`tests/architecture/_layers.py`，§5 的当次全量触发条件都不命中。
  - 真机未手动核对。
- 轮次号：领号放在提交前一刻，在干净的分支 worktree 里领到 R2190，主检出没有被切走分支。
- `project_status.md` 欠账：没有减少，也没有新增；本轮把当前轮次更新为 2191。

## 合并内容
- `git merge --no-ff claude/model-deletion-issue-6e8e80`，自动合并，无文本冲突。分支含两轮：
  - R2166（f848e888，清理提交 a571865d）：模型管理删掉的模型不再被补回。删后表单清空；删除记录对所有模型生效，阶段配置同步跳过已删的模型；当前项目里选了它的阶段改回「自动」，删除确认框先列出这些阶段。
  - R2174（5d5b9e57）：模型管理列表加「调用方式」列，去掉 API 根地址／协议／密钥名三列，状态一格可用时只写「可用」。
- 合并提交里另有两处改动。
  - 语义冲突：master 上 R2167 已把底栏「保存并关闭」改为只关窗的「关闭」，并删掉 `save_and_close`。
    - `tests/test_pet_ui.py::ModelPoolTests::test_save_and_close_right_after_delete_does_not_save_it_back`：原来点「保存并关闭」，改为依次点「保存这条」和「关闭」，两次点击后各查一次模型池里没有被删的那条。按钮改名是契约有意变更（§2.4），原有断言未动，只多一条点「保存这条」之后的检查。
    - 反向核对：临时去掉 `delete_one` 里删后清空表单的两行，这条测试变红：`AssertionError: 'delete-then-close' != ''`（删掉之后表单不能还停在那一条）；还原后通过。
    - `pet_models_ui.py` `delete_one` 里的注释把「保存并关闭」改为「保存这条」，代码未动。
  - 模块行数上限：R2166 给 `model_pool.py` 加了 `deleted_ids()`，文件从 1117 行增到 1125 行，超过 `tests/architecture/test_module_size_ratchet.py` 给它定的上限 1117。R2166、R2174 都没跑 `--architecture`，合并后的架构测试才发现。
    - 上限只许降，所以没有抬高上限，而是去掉这个函数：`pool()` 和 `remove()` 改回合并基点 14f853f7 原有的 `data.get('deleted_desktop_models') or []` 写法，`skill_panel_support.sync_models` 那一处直接读同一个键（`model_pool.raw()` 总是返回 dict）。原 docstring 的说明并进 `remove()` 的 docstring 和调用处注释。
    - 行为不变，`model_pool.py` 回到 1117 行，与 master 相同。没有测试引用 `deleted_ids`，测试未改。
- 其余断言未动。
- 过程：先在分支 worktree 上对 master 957ad83a 试合并，架构测试在那里发现行数超限。之后 master 先后前进到 6ce35959（R2183）和 04abbdfd（R2185），最终在主检出对 04abbdfd 重新合并，上面的测试都在这棵树上重跑。

## 合并证据（§2.6 第 41 条）
在暂存区上运行（提交前；提交内容与暂存区相同）。本分支没有改 `project_status.md`，只有表头那一行由本轮改写。

```
$ git diff --cached 04abbdfd -- 程序/project_status.md | grep ^- | grep -v ^--- | grep -v 当前轮次：
（无输出）
$ git show :程序/project_status.md | grep -oE ^R[0-9]+ | sort -u | wc -l
100
$ 与 04abbdfd 一侧、5d5b9e57 一侧的 R 号逐个比较（comm）
仅在暂存区: 0 个；仅在两侧并集: 0 个；并集 100 个
```


## 用户需做
重启应用后生效。然后在模型管理里把现有的 `claude-desktop-app` 再删一次：R2166 修好之前，它已经被补回成一条没有 API 根地址的 API 记录。

## 提交
提交说明首行为 `R2190: 合入 claude/model-deletion-issue-6e8e80（R2166：模型管理删掉的模型不再被补回；R2174：模型列表加「调用方式」列）到 master（合并轮）`。提交哈希写不进随提交入库的本文件，以 `git log` 为准；未 push。主检出未提交的 `.claude/settings.local.json` 不属于本轮，未暂存。
