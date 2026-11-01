# R771 结构治理轮结果：`projects.py` 单模块入口统一

## 范围与编号

用户明确授权首轮仅迁移 `projects.py`，作为“每轮 2–3 个模块”规则的例外。R770 已有回收站恢复入口结果文件，故本轮顺延为 R771，未覆盖既有记录。

## 交付

- L2 `Projects` 只接受 L3 注入的项目登记网关；无网关构造会以可定位的 `TypeError` 拒绝。
- L3 `stage_execution_service.project_registry_gateway()` 注入缓存读取、原子 JSON／字节发布、回滚及复制操作。
- `desktop` 与 `app` 仅装配网关；`writing.import_project()` 仅接收传入网关，避免 L2 反向导入 L3。
- 新棘轮拒绝 `projects.py` 恢复直接调用项目读写／复制 API。
- 台账中十条 `projects.py` 项均保留并标为 `migrated`；第 3 项 pending：66 → 56（减少 10），第 4 项：24 → 24。按每轮最多 3 个模块估算，分别约余 19、8 轮，关键路径约 19 轮。

## 验证

- `python smoke_test.py`：8/8。
- `python smoke_test.py --affected projects`：9/9。
- `python run_selftests.py -k projects unification_ratchet --safe`：4 条／0 红。
- `python smoke_test.py --architecture`：140/140（状态轮次同步后复验）。
- 上轮完整安全全量基线为 R769；R771 − R769 = 2 < 3，且本轮未触及 Tk 生命周期、删除语义或层级登记表，故不跑完整安全全量。

## Git

本轮未提交、未推送。建议提交信息：`refactor: 注入 projects 项目登记网关`。
