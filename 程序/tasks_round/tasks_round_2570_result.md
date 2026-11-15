# R2570 结果：SWE-2 优化清单 T1——私有服务器远端门禁与备份

1. 类型：可靠性轮。未改产品代码；冒烟未跑（纯脚本与服务器配置）；未触发全量。
2. 已执行（用户已确认 Linux 服务器与 SSH 密钥方式）：
   - 新增 `维护记录/基准脚本/remote_pre_receive.py`：bare 仓库 pre-receive 门禁，python3 标准库零依赖。对推送中 `程序/` 下改动的 `.py` 做 `compile()`（SyntaxWarning 按错误）+ 新增行凭据形态扫描（与 round_evidence 同族 7 类）。
   - 已在 `/srv/git/manju-assistant.git/hooks/pre-receive` 部署（LF 转换、chmod +x）。
   - 验证：服务器 `/srv/git/ci/test.git` 沙箱实测——干净推送通过、`程序/bad.py` 语法错误被拒（`语法错误 程序/bad.py:1`）、`ghp_`+36 位密钥被拒（`程序/leak.py:1:github-token`）、删分支不受影响；沙箱已清理。
   - 备份：`/srv/git/ci/weekly_bundle.sh` 每周一 04:00（cron.d `manju-bundle`）对 bare 仓库 `git bundle --all` 到 `/srv/git/backups/`，`bundle verify` 校验，保留最近 4 份；首份 `manju-2026-11-15.bundle`（14 MB）已生成并 verify 通过。
3. 边界：Linux 只做可判定静态门禁；Tk 测试与全量仍在 Windows 本机。master 领先 backup 远端 115 个提交，是否 `git push` 待用户明确授权（规则 38）。
4. 未完成：T7 测试拆分并行、T8 门禁补强、T9 归档执行（dev.py archive 预览为 0 份待归档）、T10 包化方案。
