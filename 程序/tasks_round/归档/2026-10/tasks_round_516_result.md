# R516 结构治理轮：结构剧本空成果拦截

- `script_contract.write_structured_script()` 现拒绝空白显式正文，发布前不会创建空结构剧本。
- 验证：`tests.test_script_contract tests.test_script_structure` 60/60；默认冒烟 8/8。
