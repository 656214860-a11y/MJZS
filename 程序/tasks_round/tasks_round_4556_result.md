# R4556 结果报告：UX-SETTINGS-MODELS 设置专属图标、模型配置右侧内嵌、语音识别入左上分类与 5 主流下拉
<!-- round-evidence: {"commit_base": "162d37b93", "credential_hits": 0, "evidence_sha256": "a369c3359f0e8acb", "exit": 0, "failed": 0, "passed": 10, "round": 4556, "tests": "run_selftests.py -k settings_models_redesign"} -->

- **本轮属于 §3 哪种类型**：3.1 功能轮（设置与模型管理 UI/UX 改版）。
- **测试跑了吗、三个基线过了吗**：已跑。独立只读验收复核者（`1ae746f7`）复跑定向套件 **229/229** 全绿（含新增 `test_settings_models_redesign` 10/10）；默认冒烟 **9/9** 通过（含隐藏桌面探针，对应 8/8 登记基线）；架构门禁 **711/711** 全通过（改前后 0 红）；未跑 `--all --safe` 全量回归（功能分支不触发全量，合并前按规则评估）。
- **欠账少了吗**：少了。`ui/pet_models_ui.py` 行数由 993 压降至 **915 行**（`_ModelManager` 由 563 压降至 **480 行**）；消除「模型配置」弹窗跳转并收拢为标准设置右栏页；消除独立「语音识别…」弹窗入口并统一为左上角模型分类。

## 改动摘要
1. **设置左栏 8 枚专属目录图标（与主界面 0 复用）**：
   - 在 `程序/scripts/build_nav_icons.py` 新增 8 枚未复用 Fluent `-20-filled` 码位（`settings_basic` `0xF591`、`settings_pet_model` `0xF126`、`settings_model_config` `0xE9AB`、`settings_level` `0xE629`、`settings_token` `0xF1D3`、`settings_budget` `0xEE2C`、`settings_skills` `0xE9F1`、`settings_dev` `0xF2EF`）并生成 8 张 `24×24` RGBA PNG（`程序/assets/nav/settings_*.png`）；
   - `程序/ui/pet_settings_ui.py`（934 行）全部切换至 8 枚新键，支持日/夜主题自动重染。
2. **「模型配置」入左栏并右侧内嵌显示**：
   - `程序/contract/pet_settings_contract.py` 在 `TABS` 中「三虎模型配置」之后新增 `('model_config', '模型配置')`；
   - `程序/ui/pet_settings_ui.py` 移除原无图标独立按钮与弹窗跳转，点击后经 `pet_models_ui.manager_page(...)` 在右侧栈直接显示并接通底栏保存、切页/关窗脏检查与清理；`open_manager(pet)` 独立外壳保持向后兼容。
3. **「语音识别」取消按钮并作为模型分类加入左上角分段栏**：
   - `程序/ui/pet_models_tabs.py` 更新 `MODES = ('API', 'Desktop', 'CLI', '语音识别')`；`程序/ui/pet_models_ui.py` 移除底部「语音识别…」按钮；
   - `程序/ui/speech_settings_ui.py`（432 行）抽离可嵌入 `speech_settings_panel(...)`（保留 `open_speech_settings` 壳兼容），切换分段即原地展示完整语音识别/离线包/词典/AI 优化配置并接入脏守卫与底栏保存。
4. **下方全部非密钥输入框升级为可编辑下拉框（默认 5 项主流选择）**：
   - `程序/ui/pet_models_tabs.py`（603 行）集中维护 Provider、按调用方式/模态联动的 `model`/`label`/`program` 与 `base_url`/`key_env`/`context_length`/`note`/`rpm`/`group`/`weight`/`max_output`/`temperature`/`timeout`/`retries` 及语音识别单行字段的 5 项主流预设；
   - 全部改用可编辑 `SelectBox(state='normal', style=COMPACT_COMBOBOX_STYLE)`，支持自由手输并接入 `<<ComboboxSelected>>` 置脏与自动联动；`key_entry` 严格保留 `PasswordInput(mask='*', show='*')`（守住安全红线 C12）。
5. 同步测试（新增 `test_settings_models_redesign.py` 10/10，更新 `test_pet_settings.py`、`test_model_manager_actions.py`、`test_ui_batch7_settings_models.py`、`test_ui_icons.py`）与获批治理登记（`外部依赖清单.md` 新增 5 条 `https://` 预设、`structure.json` 与 `structure-baseline.json` 登记新测试归属与哈希）。

## 独立验收结论
- 执行者：独立同模型子代理 `fc6bc58e`（`codex/ux-settings-models-embed`，基线 `d3a911aef`）
- 独立验收者：独立只读同模型子代理 `1ae746f7` — **VERDICT: PASS**（零阻断，未触碰 `desktop_layout.py` 与主工作树）
- 提交状态：本分支已按 `dev.py commit` 生成 `R4556` 证据提交（待性能优化会话释放主目录后合并入 `master`）。
