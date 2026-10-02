# 第 172 轮：分镜、首帧、白模行目标测试阶段对齐

## 问题

- 行目标测试以旧页号打开白模、首帧和初步分镜页面。
- 因连贯性清单进入流程，这些数字分别指向分镜定稿、首帧管理和剧本结构，导致白模状态、首帧表和分镜 JSON 表缺失。

## 改动

- 引入 `pet_state.PAGE_OF`，将三处页面入口改为 `previs`、`keyframe`、`storyboard` 的语义阶段名。
- 继续验证高亮行在无勾选时可作为白模制作、首帧删除、分镜取消采用的目标。

## 验证

- `python test_row_targets.py`：15 条通过。
- `python run_selftests.py --serial -k row_targets`：15 条通过。
- `python smoke_test.py --affected row_targets`：9 项冒烟检查通过。

## 风险与下一步

- 本轮只更新测试入口，不改桌面功能、自动链或用户项目数据。
- 接着审计其他固定阶段页号；业务代码仍以 `pet_bus.STAGES` / `PAGE_OF` 作为阶段顺序唯一来源。
