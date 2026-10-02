# 第 171 轮：资产门禁与阶段映射、动态配置标签对齐

## 问题

- 资产门禁回归仍把页面 `2` 视为资产页；12 阶段流程中它已经是初步分镜，资产控件和计划文件自然找不到。
- 资产操作行还把阶段配置按钮固定断言为“阶段配置”，但自动模式按设计显示实际调用引擎名称。

## 改动

- 所有资产页进入点改为 `PAGE_OF['assets']`，使测试与状态机唯一阶段顺序一致。
- 操作行测试读取 `stage_button_label(d, 'assets')`，验证动态模型标签仍在“手动制作资产”与 ComfyUI 管理按钮之间。

## 验证

- `python test_asset_gating.py`：16 条通过。
- `python run_selftests.py --serial -k asset_gating`：16 条通过。
- `python smoke_test.py --affected asset_gating`：9 项冒烟检查通过。

## 风险与下一步

- 本轮只修复过期的测试入口与文案断言，不改资产生成、ComfyUI 调用、模型配置或项目数据。
- 继续清查其他 GUI 测试中的固定页号，尤其是分镜、首帧和白模相关套件。
