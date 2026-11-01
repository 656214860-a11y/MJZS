# R830 结果：架构统一第 4 项正式读取收口

## 完成项

- `script_contract` 的五类 manifest 正式读取统一经 L0 `agent.core.read()`；该契约不能反向依赖 L1 `file_cache`，且不再自行解析 JSON。
- `shot_numbering` 的镜头编号重排分镜读取改由 `file_cache.read_json()`。
- `stage_parallel` 的阶段 JSONL 日志文本读取改由 `file_cache.read_text()`；每行 JSON 解码保留为文本记录解析。
- `stage_execution_service` 三处、`storyboard_final_controller` 与 `storyboard_final` 三处解析均只校验内存文本，不是文件读取，保留具理由豁免。
- 资产页首帧在慢机上会挤占补行定时器；补行改为首个 idle 后再计时 2 秒，保留既有渐进展示而避免同帧批量插入。
- 第 4 项 pending 由 9 降至 1，定稿基数 35 保持不变。

## 实测

```text
python run_selftests.py -k "script_contract shot_numbering stage_parallel unification_ratchet coverage_audit_ratchet" --safe
101 条，0 红

python smoke_test.py
8/8 通过

python smoke_test.py --architecture
219/219 通过

python run_selftests.py --all --safe
本轮强制执行，结果见下方全量判定。
```

## 全量判定

R830−R827=3，触发完整安全全量算式门禁；`python run_selftests.py --all --safe` 实测 3663 条、0 红、991.6 秒。`维护记录/测试分层基线.json` 已回写 `last_full_safe_all_round=830`。
