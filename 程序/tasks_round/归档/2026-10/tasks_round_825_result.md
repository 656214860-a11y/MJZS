# R825 结果：架构统一第 4 项缓存读取首批

## 完成项

- `asset_reference_search.candidates_from_file()` 的标准 JSON 清单改由 `file_cache.read_json()` 读取；JSONL 保留逐行解析兼容，但文本读取统一由 `file_cache.read_text()` 承担。
- `asset_thumbs.worker()` 的后台任务描述改由 `file_cache.read_json()` 读取。
- 未改变候选对象形状校验、JSONL 输入、缩略图缓存键、后台进程或失败回退语义。
- 架构统一第 4 项 pending 由 21 降至 18；`baseline_pending=35` 与已迁移记录保留为审计证据。
- 因移除无用导入使既有覆盖率审计 21 的 `asset_thumbs.py` 坐标从 516 校准到 515，未改变该待办归属或行为。

## 实测

```text
python run_selftests.py -k "reference_search asset_thumbs unification_ratchet" --safe
80 条，0 红

python smoke_test.py
8/8 通过

python smoke_test.py --architecture
219/219 通过
```

## 全量判定

R825−R824=1，未达到“三轮一次完整安全全量”的算式阈值；本轮未关闭架构项、未涉及发布/交付风险边界，故不重复运行 `--all --safe`，`last_full_safe_all_round` 保持 R824。
