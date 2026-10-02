# R806 结果：三虎增量自检账本 L3 发布迁移

## 范围

- `pet_test_service.record()` 改为只接受 L3 注入的正式 JSON 发布器。
- `pet_ui` 经 `stage_handler_registry.start()` 启动自检，并经 L3 轮询；不再直接调用 L2。
- 第 3 项 pending 从 18 降至 17；第 4 项仅重定位既存行号，数量保持 21。

## 验证

- `run_selftests.py -k test_pet_test_service stage_command_contract unification_ratchet --safe`：28 条／0 红。
- `smoke_test.py`：8/8。
- `smoke_test.py --architecture`：171/171（43.009 秒）。
- 强制 `run_selftests.py --all --safe`：3,604 条／0 红／1,026.4 秒；全量基线推进至 R806。

## 提交

- `b618cf2` `R806: 三虎增量自检账本接入 L3（冒烟8/8；架构171/171；全量3604/0）`；本文件不纳入暂存。
