# R839 结果：覆盖率审计 27 密钥 source→sink

- 新增 `test_secret_sink_audit.py`：在同一函数中从 `model_secrets.load`、`model_pool.credential`、`pet_llm.credential`、`api_endpoints.configured_key` 或敏感环境变量读取开始，追踪变量传播到日志、任务 JSON、prompt 三类 sink。
- 三个金丝雀分别覆盖日志、`json.dumps` 与 prompt 拼接；生产扫描没有命中，未发现密钥外泄，也未触发 `[SECURITY]` 修复轮。
- 判据文档、`覆盖率审计27` 台账 pending 与冻结扫描均为 0；新增架构测试已登记至 `AGENTS.md` 的门禁清单。

## 验证

- `run_selftests.py -k 'secret_sink_audit coverage_audit_ratchet' --safe`：7 条／0 红。
- `python smoke_test.py`：8/8 通过。
- `python smoke_test.py --architecture`：222/222 通过（54.856 秒）。
- R839−R837=2，未触发每三轮一次的完整安全全量；`last_full_safe_all_round` 保持 R837。
