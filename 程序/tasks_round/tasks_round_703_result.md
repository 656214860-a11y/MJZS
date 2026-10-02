# R703 可靠性／数据迁移轮结果：统筹迁移干跑与画幅默认收口

## 承接说明

承接 R702 的完整安全全量基线（3,398 条／0 红）。本轮实现并验证既有项目进入统筹模式的只读迁移入口；先生成干跑报告，未对用户项目执行回写。

## 完成内容

- `scripts/migrate_workflow_presets.py`：默认只生成 `维护记录/统筹迁移干跑_YYYYMMDD.md`；扫描项目登记表及显式 `--root`，把旧 `flows.*.profiles.*.skills` 的路径／ID 归一到注册表 ID，计算统筹候选、阶段差异和缺锁。`--apply` 才会写入。
- `stage_config.apply_workflow_empty_stages()`：只补**显式**为空的阶段，保留已有勾选、旧 `flows` 文件和 `skill_config.json` 的未知顶层字段；同一迁移第二次不写文件，仍走既有原子发布边界。
- 新增迁移回归与三处画幅优先级回归。`asset_contract`（旧默认 `16:9`）、`keyframe_comfy`（`9:16`）和 `cloud_assets`（`1:1`）均固定为“`workflow.lock.aspect_ratio` → 已存偏好 → 原旧默认”。

## 干跑结论

报告：`维护记录/统筹迁移干跑_20261001.md`。

- 已登记的 3 个项目均已扫描；旧清单覆盖均为 `0/0`，无可映射统筹候选、无锁缺项。
- 因没有候选项目，本轮未运行 `--apply`，没有改动任何用户项目数据；后续出现可映射旧清单时，须先复核同一报告再显式执行 `--apply`。
- AIGC 全流程锁定义来源：模型版本为包 `SKILL.md:13,17-18`，画幅为 `:46-49`，交付形态为 `:51-56`；外部包 frontmatter 仍不作为执行字段来源。

## 验证

- `python -m unittest tests.test_aspect_ratio_priority tests.test_workflow_migration tests.test_asset_contract tests.test_stage_config_hollmwood`：35 条通过。
- `python smoke_test.py`：8/8 通过。
- `python smoke_test.py --affected keyframe_comfy asset_contract cloud_assets stage_config`：9/9 通过；定向自检 0 红。
- `python run_selftests.py --all --safe`：3,403 条、815.8 秒、0 个文件有红；日志：`维护记录/r703_safe_all.out.log`（进程退出后 Tk 延迟定位回调的既有 stderr 噪声另存 `r703_safe_all.err.log`，不影响退出成功与汇总）。

## 三个基线数

- 默认冒烟：8/8 通过。
- 受影响冒烟：9/9 通过。
- 完整安全全量：3,403 条／0 个文件有红。

[TASK_COMPLETE]
