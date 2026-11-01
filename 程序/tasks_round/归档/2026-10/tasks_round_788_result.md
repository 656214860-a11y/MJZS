# R788 结果｜UI 统一入口第三批第 15 项：阶段显示

## 交付

- `desktop.PAGES` 的 12 个制作页改由 `pet_bus.STAGES` 和 `pet_bus.stage_name()` 生成，阶段名称唯一服从 `STAGE_NAMES`；“13 参考网站”仍是独立工具页。
- `pet_bus.stage_name()` 提供未知阶段的稳定回退值，`Bus.stage_name()` 复用该入口。
- 新增 `tests/architecture/test_stage_display_boundary.py`，拒绝桌面页表重新硬编码阶段名称；架构清单已登记。
- 全量首次运行定位到 R787 遗留的 Windows 闭包问题：Unix 专用 `fcntl` 静态导入在裁剪运行环境缺失。现改为仅非 Windows 实际分支加载；覆盖率 24 的扫描器将该唯一标准库平台锁豁免明确列入白名单，未改变业务动态导入的扫描集合。

## 验证

| 检查 | 结果 |
| --- | --- |
| `python smoke_test.py` | 8/8 |
| `python smoke_test.py --affected desktop pet_bus pet_ui` | 通过 |
| 阶段显示／总线定向回归 | 20 条／0 红 |
| 锁／复制／闭包及覆盖率定向回归 | 14 条／0 红 |
| `python smoke_test.py --architecture` | 154/154，不低于 153/153 |
| `python run_selftests.py --all --safe` | 3,568 条／0 红／859.6 秒 |

R788 − R785 = 3，依 AGENTS.md §5 执行完整安全全量；成功后 `last_full_safe_all_round` 已推进至 788。

## Git

- 本轮未暂存、未提交、未推送。
- 建议提交信息：`refactor(ui): 统一桌面阶段显示名称来源`
