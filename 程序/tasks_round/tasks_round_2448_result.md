# R2448 可靠性轮：无人值守认证开关接入模型配置页

## 结论

把“无人值守前要求五合一认证”从代码常量改为可配置项，并在“三虎模型配置”页增加复选框，保存/重置即时读写。

## 关键改动

- [model_pool.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/model_pool.py)
  - 新增 `require_certified(program)`／`set_require_certified(value, program)`，存储在 `配置/宠物/配置.json` 的 `model_settings.require_certified`。
- [storyboard_direct_api.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/storyboard_direct_api.py)
  - 直连准入改读配置项，不再写死常量。
- [pet_models_ui.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/pet_models_ui.py)
  - 模型配置页新增复选框，保存/重置同步该配置。

## 验证

- 定向 unittest 83/83 通过（模型池与三个直连执行器）。

## 提交

- 已提交：`de78aedc92049ea55bacf9003419e4f5aca1c4b1`
- 分支：`codex/wip-R2448`
