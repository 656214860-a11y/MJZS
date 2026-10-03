# R836 结果：覆盖率审计 21 宠物自检进程收口

- 宠物服务的同步增量自检经 `platform_tools.run_process()` 执行，后台增量自检经 `platform_tools.launch_background()` 启动；保留输出合流、临时输出文件、失败处理与可替换启动钩子。
- 审计 21 pending 从 2 降至 1；扫描器、判据文档与台账数字一致。

```text
python run_selftests.py -k "pet_test_service coverage_audit_ratchet unification_ratchet" --safe
26 条，0 红

python smoke_test.py
8/8 通过

python smoke_test.py --architecture
219/219 通过（46.714 秒）
```

距 R833 的完整安全全量正好三轮；R836 的下一轮提交前必须补跑完整安全全量。
