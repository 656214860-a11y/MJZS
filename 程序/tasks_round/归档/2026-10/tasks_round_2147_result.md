# R2147 结果：模型管理底栏加「语音识别…」设置弹窗，语音识别配置不再需要手改 JSON（功能轮）REQ-S01-71／DES-S01-71

## 三问
- 轮次类型：功能轮（§3）。REQ-S01-71 补充界面入口：识别服务设置从「手改 `data/语音识别.json`」改为在弹窗里改。
- 测试和三个基线：都在本 worktree、本轮改动后的树上运行。
  - `run_selftests.py -k speech_api model_manager_actions script_composer button_consistency pet_models platform_tools writing_page pet_settings`（经 gui_hidden）：115 条全过。
  - 默认冒烟：失败 0 项。
  - 架构门禁 `--architecture`：411 项全过。worktree 缺 `维护记录/基准历史.json`，运行前从主检出临时拷入，跑完已删除，未提交。
  - 全量 `--all --safe` 本轮未运行。
  - 弹窗未在真实应用里人工点验，只有隐藏桌面上的界面测试。
- `project_status.md` 欠账：没有减少，也没有新增。本分支不提交 project_status.md，由合并轮在 master 上同步。

## 为什么改
用户问语音识别的配置接口在哪，得知要手改 `data/语音识别.json` 后要求「需要可视化入口」。

## 改动
- `speech_api.py`（L2）：新增 `save_settings(values, *, publish, path=None)` 与 `NUMBER_RANGES`。
  - 逐项校验：`silence_ms` 100–2000、`max_seconds` 10–3600、`timeout` 3–120 的整数；文字项不能为空；地址仍由 `endpoint()` 要求 `wss://`。不合法抛中文 `ValueError`，文件不动。
  - 只写与默认不同的字段（全默认写 `{}`），写后 `file_cache.invalidate`，下次开麦即读到新值。
  - 发布器由界面层注入（L2 不直接写正式路径，符合统一台账第三项）。
  - 没配密钥时状态栏提示改为指向「模型管理 › 语音识别…」。
- 新模块 `speech_settings_ui.py`（L4，已登记 `tests/architecture/_layers.py`）：`open_speech_settings(pet, parent)`。
  - 字段：服务地址、模型（可下拉可手填）、密钥名、识别语言（zh/en/ja/ko/yue，可手填）、断句停顿、单次开麦上限、超时。
  - 密钥名下方实时显示「密钥已配置」或「没找到这个密钥」；密钥本身不在这里填写或显示。
  - 按钮：恢复默认（只填回表单，点保存才生效）、取消、保存。保存失败在弹窗内提示原因并保持打开，成功后关闭。
  - 注入 `agent.core.save` 作发布器。外壳不从 `pet_models_ui` 导入，避免循环依赖。
- `pet_models_ui.py`：模型管理底栏「保存这条」右侧加「语音识别…」按钮，经函数内延迟 import 打开弹窗。弹窗放进新模块是因为 `pet_models_ui.py` 写进去会到 1050 行，超过 1000 行上限。
- 新增生产模块后按门禁要求重跑 `scripts/coverage_report.py`（原 8 组定向用例，全通过）刷新 `维护记录/覆盖率基线.json`：模块 330→331，覆盖到 50 个不变；其他模块的行数随历史改动一并刷新。`runbook.md` §11 的数字同步为 331／281。
- 文档：S01 的 REQ／DES-S01-71 与验收表（加 `test_model_manager_actions`）、`配置说明.md` 语音识别一节、`architecture.md` L2 说明。

## 测试（新增，原有断言未动）
- `test_speech_api.test_save_settings_validates_and_writes_only_changes`：只写改动字段、保存后立即可读、四类非法输入都拒绝且不动文件、全默认写空对象。
- `test_model_manager_actions.SpeechSettingsTests` 3 条：入口按钮在「保存这条」右侧；表单显示当前设置与缺密钥提示；保存失败保持打开并显示原因；恢复默认、保存传入表单值后关闭。
