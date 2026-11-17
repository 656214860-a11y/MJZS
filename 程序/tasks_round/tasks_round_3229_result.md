# R3229 自动全量文案守卫迁包路径同步
<!-- round-evidence: {"commit_base": "dd7ce8e0", "credential_hits": 0, "evidence_sha256": "920606219ab54acb", "exit": 0, "failed": 0, "passed": 14, "round": 3229, "tests": "run_selftests.py -k test_copy_rules"} -->

## 三问

1. 类型：验收兼容修复轮，仅测试路径同步，不改文案规则与产品。
2. 实测：R3226自动全量在master dd7ce8e0运行；出现test_copy_rules一项失败，另stdlib_closure两项为运行时裁剪契约差异。定位并修正文案路径后同模块14条/23.241秒/OK。最终全量仍待完成，不伪造绿凭据。
3. 欠账：消除并行infra包化残留的PROMPT_FILES旧路径2项；原用户“您”规则、对模型提示词的豁免范围均未扩大。

## 改动

`tests/test_copy_rules.py`：PROMPT_FILES中的pet_llm.py/continuity_ledger.py改为实际infra/实体路径。原规则已豁免这两份模型提示词，只是迁包后位置不匹配，故出现5条误报。

## 后续

本修复合入master后，跟踪自动全量或按R3210既有受控3.15口径完整回归；全部验收闭环后输出R3092任务完成文件。当前不标完成。
