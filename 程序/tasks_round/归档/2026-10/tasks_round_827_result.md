# R827 结果：架构统一第 4 项引擎验证台账读取

## 完成项

- `engine_probe.record()` 的引擎真机验证台账读取收口至 `file_cache.read_json()`。
- `engine_probe.py:163` 解析的是外部 CLI 的标准输出，非文件读取；保留为具理由的审计豁免。
- 资产页余行首次补齐延迟从 1 秒调整为 2 秒，避免慢机器的首次 `update()` 越过计时器而提前插入第二批，首帧维持 24 行性能契约。
- 架构统一第 4 项 pending 由 16 降至 14，定稿基数 35 保持不变。

## 实测

```text
python run_selftests.py -k "engine_probe unification_ratchet layers" --safe
30 条，0 红

python run_selftests.py -k asset_gating --safe
17 条，0 红

python smoke_test.py
8/8 通过

python run_selftests.py --all --safe
3,663 条，0 红，912.6 秒
```

## 全量判定

R827−R824=3，触发完整安全全量算式门禁。首次全量发现资产首帧第二批提前插入；修复后重跑全量通过，`last_full_safe_all_round` 已推进至 R827。
