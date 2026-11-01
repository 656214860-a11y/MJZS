# R1977 按钮一致性第三步：阶段弹窗脱离 Compact.TButton，侧栏紧凑模式补完（功能轮）

## 改动
- `ui_widgets.py`：批量执行弹窗（重试失败项／返回阶段页面／关闭）与手动制作精简窗（修改配置／直接执行／取消）由裸 `ttk.Button` + `Compact.TButton` + `padx=(6, 0)` 改为 `SecondaryButton`／`PrimaryButton`，间距取 `BUTTON_GAP`；手动制作窗按弹窗底栏规则排成「修改配置」靠左、「直接执行」最右、「取消」紧挨其左。`Compact.TButton` 从此只剩侧栏使用，窗口变矮时不再把弹窗按钮缩到 21px。
- `desktop_layout.fit_sidebar`：紧凑内边距补上 `Selected.Compact.TButton`（此前只覆盖 Compact／Nav 系，选中态漏改）；行高字面量 `20 if compact else 24` 改引用新令牌 `NAV_ROW_HEIGHT`(24)／`NAV_ROW_HEIGHT_COMPACT`(20)（`ui_tokens.py`），`design_tokens.md` 补行。
- 新测试 `tests/test_button_consistency.py::StageDialogButtonTests`：阶段弹窗源码不含 `Compact.TButton`／`padx=(6, 0)`；fit_sidebar 含 Selected.Compact 且无行高字面量；Selected.Compact 按下态内边距与常态同步。
- 删除误入库的重复结果文件 `tasks_round_1971_result.md`（内容已在 1970／1973）。

## 验证
- 本轮相关 119 条（button_consistency、ui_style_engine、ui_modern_system、button_boundary、token_boundary、desktop_compact_layout、responsive_layout、manual_plan、module_size 等）全绿；ui_widgets.py 1493 行（上限 1500）。断言未动。
- 另跑 pet_ui＋architecture 全组 1008 条：红项为 architecture 三项（agents_md、round_baselines、skill_reference_injection，历史红）和 test_pet_ui 6 条（无人值守开关／auto_storyboard 5 条与云朵几何 1 条），失败内容在 project_settings／宠物几何，与按钮样式无关，本轮未在基线上逐条复现。
- 未跑 --all --safe，未真实窗口目测（弹窗宽度因 Secondary 最小宽度略宽，未量）。
