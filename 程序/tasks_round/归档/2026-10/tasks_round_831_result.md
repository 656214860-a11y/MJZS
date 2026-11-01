# R831 结果：架构统一第 4 项稳定快照读取收口

## 完成项

- `storyboard_storage.snapshot()` 不再自行读取并解析工作 JSON，改由 `file_cache.read_stable_json_snapshot()` 统一承担。
- 新入口在读取前后比较 `mtime_ns` 与文件大小；不一致即拒绝“文件正在写入”，因此分镜半写入保护、原始字节回传和摘要计算语义不变。
- 中央 `file_cache.py:112` 已登记为缓存权威自身的受控解析入口；`storyboard_storage.py:49` 已迁移。
- 第 4 项 pending 由 1 降至 0，定稿基数 35 不变；第一批第 3、4 项均满足清单清空判据。

## 实测

```text
python run_selftests.py -k "storyboard_storage file_cache coverage_audit_ratchet unification_ratchet round_baselines" --safe
34 条，0 红

python smoke_test.py
8/8 通过

python smoke_test.py --architecture
219/219 通过（47.164 秒）
```

## 全量判定

R831−R830=1，未触发“间隔三轮必须完整安全全量”算式门禁；完整安全全量基线保持 R830。本轮仍须在提交前完成默认冒烟与架构门禁。
