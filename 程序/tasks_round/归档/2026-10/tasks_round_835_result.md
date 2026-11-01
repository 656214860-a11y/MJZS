# R835 结果：覆盖率审计 21 ffmpeg 转码收口

- `native_asset_codec` 的 ffmpeg PNG 转码统一经 `platform_tools.run_process()` 执行；命令、输入输出捕获、120 秒超时与失败语义不变。
- 适配器保留可注入 `run` 的测试接缝，调用方继续显式使用其既有 `subprocess.run` 对象。
- 审计 21 pending 从 3 降至 2；扫描器、判据文档与台账数字一致。

```text
python run_selftests.py -k "seedream_direct aspect_ratio_priority coverage_audit_ratchet unification_ratchet" --safe
23 条，0 红

python smoke_test.py
8/8 通过

python smoke_test.py --architecture
219/219 通过（46.785 秒）
```

距 R833 的完整安全全量仅两轮；未触发三轮算式门禁。
