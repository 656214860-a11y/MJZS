# R834 结果：覆盖率审计 21 缩略图 worker 收口

- 缩略图 worker 的后台启动收口到 `platform_tools.launch_background()`；仍显式传入白名单 `env`，不会继承模型/API 凭据。
- 适配器提供可注入 `popen` 启动器，`asset_thumbs` 保留其原有可替换测试钩子；静默标准流和无控制台策略不变。
- 审计 21 pending 从 4 降至 3；扫描器、判据文档与台账数字一致。

```text
python run_selftests.py -k "asset_thumbs coverage_audit_ratchet unification_ratchet" --safe
28 条，0 红

python smoke_test.py
8/8 通过

python smoke_test.py --architecture
219/219 通过（46.725 秒）
```

距 R833 的完整安全全量仅一轮；未触发三轮算式门禁。
