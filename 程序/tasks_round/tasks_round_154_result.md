# 第 154 轮：结构剧本同步配置异常安全收敛

## 改动

- 扩展 `Desktop.pet_script_structure_batch()` 的同步异常边界，除文件/校验问题外，也捕获损坏选择配置可能造成的 `TypeError`、`AttributeError`、`KeyError`。
- 此类错误统一发出 `stage.failed(script_structure)`，不泄漏为后台回调异常，也不推进初步分镜。

## 验证

- 新增 `DesktopPetSeamTests.test_auto_structure_bad_selection_settings_stays_in_that_stage`，模拟选择配置读取抛出 `AttributeError`。
- 与上轮同步返回空列表、缺失原稿用例一起执行：3 项通过。

## 风险与下一步

- 仅收敛同步边界的已知数据格式异常；不会掩盖结构化生成本身失败（其原有失败路径仍保留）。
- Tk `invalid command name ... <lambda>` 仍需独立的稳定复现后再改动；避免把不确定的测试清理提示误改为生产逻辑。
