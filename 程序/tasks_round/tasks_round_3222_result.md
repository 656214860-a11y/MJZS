# R3222 全量验收：修正属性列后的可见点击坐标
<!-- round-evidence: {"commit_base": "6c59f1e4", "credential_hits": 0, "evidence_sha256": "e0742a53b832fd97", "exit": 0, "failed": 0, "passed": 44, "round": 3222, "tests": "run_selftests.py -k test_file_index test_stage_file_index_publication"} -->

## 三问

1. 类型：测试契约同步/验收修复轮，不改产品。新列表增加属性与媒体信息列，旧测试取整行bbox中点已超出窄窗可见区域。
2. 全量：在净树6c59f1e4、原受控3.15解释器、随包FFmpeg进程PATH下真实运行，8447条/865.1秒/2文件红：分支轮次头，及本轮修复的双击用例；没有其他功能红。修复后同一单用例1条/6.141秒/OK。尚无本提交完整绿凭据，不虚报。
3. 欠账：双击用例继续断言表头不打开、可见文件行恰好打开一次、键盘Enter恰好打开一次；只把点击坐标改为name单元格可见位置，不弱化行为断言。

## 改动与证据

- `tests/test_idea_chat.py`：`tree.bbox(item,'name')` 定位文件名单元格，点击x钳位到实际可见宽；原表头保护与两次单独open_path精确断言保留。
- `logs/file_management_R3181/R3214_full_safe315.log`、`visible_double_click.log`为实际运行日志，均不入产品源。

## 下一步

标准合并轮更新master状态页，复验轮次一致性并完整安全回归；全部通过后输出R3092同名任务完成文件，不能把仅剩轮次头的分支全量写成ALL TESTS PASSED。
