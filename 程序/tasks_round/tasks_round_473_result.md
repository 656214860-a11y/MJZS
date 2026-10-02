# R473 契约轮结果

## 来源与目标

本轮按用户指定的契约轮执行，只处理 L0 的 `stage_layout`。修正 JSON 与 MD 职责对照表泄漏旧内部目录名的问题，使人读路径与当前编号阶段目录契约一致。

## 改动

- `stage_layout.json_md_rows()` 中六条 MD 路径统一改为 `04资产管理`、`05连贯性清单`、`06分镜定稿` 或 `09视频生成` 下的 `docs/` 路径。
- `tests/test_stage_layout.py` 现在逐条确认目录属于 `stage_layout.names()`，且路径严格落在该目录的 `docs/` 下。
- `AGENTS.md` 与 `architecture.md` 明确禁止该对照表重新使用旧内部目录名。

## 验证

- 定向：`tests.test_stage_layout`，21/21 通过。
- `python smoke_test.py --architecture`：72/72 通过。
- `python smoke_test.py`：8/8 通过。
- `python run_selftests.py --all --safe`：3,183/3,183 通过，796.6 秒，0 个文件失败。

## 约束审查

通过：生产代码只修改 L0 的 `stage_layout.py`；没有改动 L1 以上模块、用户项目数据或旧目录迁移逻辑。`json_md_rows()` 仅为人读职责对照，机器输入输出和兼容读取行为不变。
