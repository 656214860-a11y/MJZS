# R4581 同步 GUI 测试登记名
<!-- round-evidence: {"commit_base": "fc1b1a8a4", "credential_hits": 0, "evidence_sha256": "2781eb8edea997f0", "exit": 0, "failed": 0, "passed": 3, "round": 4581, "tests": "run_selftests.py -k test_skip_hygiene"} -->

- 修复轮。R4576 提交门禁 347 条全过，出口冒烟通过，静态门禁 47 条中有 1 条失败。
- 资产菜单测试更名后，平台无 Tk 时的已有跳过登记仍引用旧方法名。同步该条名称，跳过条件及条目数维持原值。
- 定向复验覆盖 skip 台账与源码之间的双向校验。完整主分支回归对照与启动耗时见 R4576。
