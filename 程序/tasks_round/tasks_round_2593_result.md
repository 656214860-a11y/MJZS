# R2593 结果：修复 R2589 合入门禁——裸 json.loads 棘轮债务清偿
<!-- round-evidence: {"commit_base": "bc5a805b", "credential_hits": 0, "evidence_sha256": "4ecacc582deb2557", "exit": 0, "failed": 0, "passed": 54, "round": 2593, "tests": "run_selftests.py -k unification_ratchet http_client http_boundary execution_deadline shared_adapter cloud_video"} -->

## 类型与三问

- 类型：修复轮（合入门禁暴露）。
- 测试：`run_selftests.py -k "unification_ratchet http_client http_boundary execution_deadline shared_adapter cloud_video"` 全绿。
- project_status 欠账：无新增。

## 根因与修复

- 迁移后的 volcengine/wan 在调用方新增 `json.loads` 调用点，触发 `test_unification_ratchet` 第四项「裸 json.loads 债务只减不增」。
- 正确修法不是登记新债，而是收口：`http_client` 在 HTTPError 分支已解析 `error_json`、成功分支已有 `json` 字段；调用方改用 `data['json']`／`data['error_json']`，删除全部新增 `json.loads`。
- 同步从 `维护记录/架构统一基数.json` 移除两条已不可定位的旧台账项（volcengine/wan 原 error body 解析点）。
- 非 JSON 响应语义保持：原 `json.load` 抛 JSONDecodeError，新代码抛 ValueError（同族）。

## 提交

- 待回填 hash。
