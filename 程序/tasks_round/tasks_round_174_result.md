# 第 174 轮：自动入口保留当前结构剧本失败状态

## 问题

- 自动模式启用时，会用已落盘的结构剧本兼容历史项目缺失的状态记录。
- 原实现对任何状态都直接写成成功；若本轮 Writer/Editor 已失败但目录残留旧 `script.md`，自动链会跳过修复并错误进入分镜。

## 改动

- `pet_ui.Pet.arm_auto()` 仅在 `script` 与 `script_structure` 状态缺失或为 `pending` 时，才用现存正稿补记成功。
- 明确的 `failed`、`running`、`retrying` 状态保持原样，自动链会回到失败步骤。
- 在 `tests/test_sanhu_mode.py` 增加临时项目回归：旧结构正稿与当前结构化失败并存时，续跑目标仍为 `script_structure`。

## 验证

- `python test_sanhu_mode.py`：10 条通过。
- `python test_stage_flow.py`：45 条通过。
- `python run_selftests.py sanhu_mode stage_flow`：55 条通过。
- `python smoke_test.py --affected sanhu_mode`：9 项冒烟检查通过。

## 风险与下一步

- 仍兼容历史项目中“文件已存在但状态尚未建立”的情况；本轮不改模型配置、项目素材或用户数据。
- 下一轮继续审计自动入口中批处理失败事件与状态机落盘之间的对应关系。
