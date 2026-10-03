# R858 结果：全量回归按内容树去重并将全量门禁移至合并点

## 变更

- `--all --safe` 的三轮计数仅适用于 `master` 提交序列；分支/worktree 不再产生全量欠账，仍须完成默认冒烟、架构门禁、定向和默认增量。
- `维护记录/测试分层基线.json` 新增 `full_safe_verified_trees`。同一 `HEAD:程序` 内容树在七日内已有绿记录时，命令明确引用 R 轮次、时长与 0 红而免跑；任一红项会撤销该树的绿凭据。
- 增量缓存改存共同 Git 目录的 `selftest-incremental.json`，以临时文件加原子替换写入；无法定位 Git 时才回退到原维护目录。
- 架构测试覆盖主干专属计数与凭据元数据；自检测试覆盖内容树七日去重、共享缓存回退和原子写入。

## 验证

- `python -m unittest tests.test_selftests tests.architecture.test_round_baselines`：27/27 通过。
- `smoke_test.py`：默认冒烟 8/8 通过。
- `run_selftests.py --serial -k selftests round_baselines`：27/27 通过，0 红；增量台账写入共同 Git 目录。

## 边界

- 本轮为测试治理轮，不把分支上的手动全量运行伪记为主干内容树凭据；真实主干合并点全量绿后才写入该记录。
