# R1432 结果：阶段配置「新增 SKILL」稳定导入

- 本轮属于 §3.2 **修复轮**。工作位置：独立工作树分支 `codex/r1432-skill-master`（主目录另一任务有未提交改动）；开发与测试在 Linux 副本（Python 3.12，非随附解释器）。
- 测试跑了吗：跑了定向测试与架构目录，见下；随附解释器冒烟与全量未跑。
- 欠账：全量回归欠账未减少（仍待 Windows 补跑，且须避开桌面弹窗时段）。

## 复现与根因

用户问"新增 SKILL 后程序怎么做、有没有漏洞"。原 `skill_panel.add_skill_from_file` 只做一次 `shutil.copy2`：

1. 选中外部包的 `SKILL.md` 时**只复制这一个文件**，包内 `references/`、`assets/`、`scripts/` 全部丢失。
2. 新清单与已有 SKILL 同名时，扫描把新文件丢进问题列表静默丢弃，界面却显示"已新增"。
3. 目标已存在只弹一次确认就**直接覆盖**，旧版不进回收站。
4. 导入时不做发送前检查：正文为空、引用缺失／越界、超过 96000 字上限都要等到发送时才阻断。
5. 不记录来源与版本，无法判断来源是否更新。

## 修复

新增 `skill_import_service.py`（L4，无 Tk），面板只负责弹窗与刷新：

- `plan_import`：只读预检。读不出、**重名**（不同位置的同名 SKILL）直接硬拦；字段缺失、声明阶段不一致、目标已存在仍交给界面二次确认。
- `perform_import`：
  - 先复制到阶段目录下以 `.` 开头的暂存目录（注册表不扫描点目录）。外部包整包复制，跳过 `.git`／`__pycache__`。
  - 目标已存在时，旧版经 `storage_maintenance.recycle_paths` 移入程序回收站。
  - `os.replace` 换入后，按真实发送流程试冻结一次（`workflow_settings._inline_skill_report(strict=True)`）。失败就把新版撤回暂存区，并经 `restore_recycle_batch` 恢复旧版。
  - 暂存区同样只移入回收站，不永久删除。
- 成功后写导入台账 `skills/导入台账.json`：目标相对路径 → 来源、类型、名称、内容摘要、时间。

## 契约变化（§2.4）

- `test_confirm_allows_invalid_manifest_copy`：夹具补一行正文。正文为空的清单发送时必被拦，导入同样硬拦。原断言"字段不全但确认后可导入"未动，新增 `test_empty_body_is_blocked_even_after_confirm` 覆盖空正文。
- `test_skill_notes.test_new_package_import_is_registered_and_selected`：外部包导入也做重名预检，夹具补 `registry.getAll.return_value = []`；断言未动。

## 测试

- 新增 6 项 `StableImportTests`：
  - 整包带上 references 且跳过 `.git`、台账字段齐全；
  - 断链撤回不留暂存；
  - 更新失败恢复旧版；
  - 覆盖时旧版进回收站；
  - 异处同名硬拦、不复制；
  - 空正文硬拦。
- `test_skill_import_validation`／`test_skill_panel_imported`／`test_skills`／`test_skill_notes` 共 175 项通过。
- 架构目录 341 项：4 项失败，与未改动副本对比均为既有或环境项：
  - 副本未带根 `.gitignore`；
  - 轮次连续性；
  - R1431 欠全量；
  - TODO 快照 `desktop.py` 行号漂移，来自另一任务 R1431，差异与未改动副本逐字相同。
- `skill_import_service` 登记为 L4（依赖同层 `workflow_settings` 的冻结口径）。
- 未运行：随附解释器冒烟、全量。

## 自审

只改导入路径与对应测试；删除、覆盖均走回收服务；无越层依赖。同类问题：`delete_checked_skills` 只回收 `.skill.md`，外部包目录不在删除范围，属既有限制，本轮未改。
