# R3886 修复轮：归档编码修正（总控退役验收）

- 类型：§3.2 修复轮；只修正上一轮归档材料的编码落点，不改产品与既有断言。
- 测试：R3877 定向38/38已绿；本轮定向 line_endings/distribution_selfcheck/root_layout 串行复验通过（见 logs/R3886_targeted_utf8.txt）。完整安全全量待本轮提交后重跑，未预写通过。
- 欠账：总控退役主体已提交（9bff4d5b/R3818-FAIL、0d2ede1f/R3860、6080d20d/R3877），合入 master 与任务完成文件仍未完成。

## 根因与最小修复

验收诊断中 `test_line_endings` 红：R3877 把上游检查点误入根 `.agents` 的验证结果 `account_r3832_checks.json` 原字节归档进 `程序/` 后，该文件实为 PowerShell 重定向产生的 UTF-16LE（430 处落单 CR），违反程序树文本行尾/UTF-8 门禁。

修复：不扩行尾扫描白名单，不动产品；把该文件以**原字节**改名为 `account_r3832_checks.json.utf16le`（非文本后缀，扫描不把它当文本），SHA-256 保持 `a78bc7f4…57567e`；`manifest.json` 增记 `archived_path`／`encoding`／原字节说明。Git 公共 rescue 中的原字节副本仍在。

## 验证

- `python -m ... line_endings.audit(evidence/R3877_checkpoint_artifacts)`：6 个文本文件 0 脏；UTF-16 文件字节哈希与 manifest 一致。
- `run_selftests.py -k line_endings distribution_selfcheck root_layout --serial`：全绿，退出 0。
- 下一步：提交本轮后重跑权威 `--all --safe`，通过且主树干净才走标准合并；合并后输出逐条任务完成文件。
- 回滚：本轮独立提交可 `git revert`；被归档文件原始路径与哈希见 manifest。
