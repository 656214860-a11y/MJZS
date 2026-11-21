# R4041 lanes.json 非对象条目按空表降级
<!-- round-evidence: {"commit_base": "be2bbe13", "credential_hits": 0, "evidence_sha256": "98c0e2d3d1927346", "exit": 0, "failed": 0, "passed": 55, "round": 4041, "tests": "run_selftests.py -k lane_merge_queue branch_scope"} -->

修复轮。`lane_registry._read` 只校验 `lanes` 是对象、不归一各条目：JSON 合法但车道条目不是
对象（手改或损坏写入）时，`list_lanes` 的 `entry.get` 与 `register` 的 `entry.update` 抛
AttributeError，沿本期新增的 `branch_scope.lane_activity` 一路崩到提交门禁（该处只捕
GATE_ERRORS/ValueError/TypeError，AttributeError 不在其中）。与本文件「文件损坏时按空表
降级（宁可少登记，不可拒绝领号）」的契约矛盾。修后 `_read` 丢弃非 dict 条目、保留文件里
其他顶层键；修前新增用例红（AttributeError: 'str' object has no attribute 'get'）。

- 轮次类型：修复轮（§3.2），只改根因所在模块 `维护记录/基准脚本/lane_registry.py` 加一条回归用例。
- 测试：修前 `test_non_dict_lane_entries_degrade_to_empty` 红（AttributeError）；修后
  `run_selftests.py -k lane_merge_queue branch_scope` 55/55 绿、默认冒烟 9/9、
  `--affected lane_registry` 10/10。三个基线：冒烟过（登记 8 项＋探针）；架构门禁未触发
  （无层级/跨层/删文件改动）；全量未跑，最近绿凭据 R3849。
- 欠账：无新增；本期代码审查其余发现只记录，见《simplify审查_2026-11-21.md》。
