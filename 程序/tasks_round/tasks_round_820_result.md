# R820 结果：资产页首帧性能与统一对话框契约修复

## 完成项

- 资产页把首帧同步建行从 48 收窄到 24；以当前约 80 像素行高计，仍有约三屏可滚动余量。剩余行维持既有的按帧补齐机制，避免首次绘制同时为过多资产登记缩略图任务。
- 资产性能门禁不再假定打开即建完 31 行：它锁定首批 `ASSET_FIRST_ROWS` 行、等待 Treeview 映射后验证可视区确有缩略图覆盖，并继续限制实际解码量不超过可视区范围。
- 宠物“查看详情”仍复用全程序唯一的 `prompt_window` 与复制出口；测试改为遍历 `BaseDialog` 的正文／动作栏后代控件，验证文本、按钮名称、复制与关闭语义，不绑定旧的直接子控件层级。
- R819 遗留的完整安全全量欠账已由本轮实跑补齐，`last_full_safe_all_round` 推进至 R820。

## 实测

```text
python smoke_test.py
通过：8 项；失败：0 项

python smoke_test.py --architecture
214 条，0 红

python run_selftests.py -k perf_baseline --safe
9 条用例，0 个文件有红

python run_selftests.py -k asset_gating --safe
17 条用例，0 个文件有红

python run_selftests.py -k pet_ui --safe
560 条用例，0 个文件有红

python run_selftests.py --all --safe
3,657 条用例，918.0 秒；0 个文件有红
ALL TESTS PASSED
```

## 结论

本轮未回退渐进加载或统一对话框；性能、资产缩略图和宠物详情交互的契约均已由完整安全全量复验。历史 `.bak_*` 与升级备份保持不动，回滚点由 Git 提交承担。
