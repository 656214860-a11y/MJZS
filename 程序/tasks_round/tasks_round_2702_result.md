# R2702 结果：T8.2 黄金文件——prompt 渲染／字幕导出（SRT/ASS）／分镜提示词整份输出对照
<!-- round-evidence: {"commit_base": "a684ab97", "credential_hits": 0, "evidence_sha256": "5ca1f3eb2d57be66", "exit": 0, "failed": 0, "passed": 13, "round": 2702, "tests": "run_selftests.py -k golden_outputs"} -->

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   验证基线轮（任务书 T8 指定类型）。只新增测试与黄金文件，零生产代码改动。
   轮次号说明：本会话先在 marble-pulley 工作树领得 R2689，提交时中央计数器已被
   并行车道推进，按规则 27 重新领取 **R2702**；R2689 成空号（无提交、无结果文件）。
   执行工作树 `devin-swe2-tasks`（codex/wip-R2702，基于 master a684ab97）。

2. **测试跑了吗、三个基线过了吗？**
   - `run_selftests.py -k golden`：13/13 通过（新增 `tests/test_golden_outputs.py`）。
   - 默认冒烟：8/8 通过。
   - 架构门禁：466 项中 464 过；2 项与本轮无关——
     `test_performance_history…` 因干净检出缺 git-ignored `维护记录/基准历史.json`
     报 ERROR（按 R2682 同款环境修复从主工作区只读复制后单独复跑转绿）；
     `test_round_number_continuous` 在 master 基线本身即红（状态页 2697 vs
     最新结果文件 2682，系 R2696 合并轮未落自己的结果文件所致，属他车道在途
     簿记，本轮不代修）。

3. **project_status.md 的欠账少了吗？**
   无新增欠账；未跑全量（新增测试文件不触发源码轮欠账口径）。

## 交付物

- `tests/test_golden_outputs.py`（13 用例）：黄金文件对照助手 `_golden()`，
  `GOLDEN_UPDATE=1` 时重写基线；行尾统一按 `\n` 比较，机器相关绝对路径
  （`asset_prompt_rules.COMMON` 内嵌的 schema.json 位置）归一为 `<PROGRAM>`。
- `tests/fixtures/golden/`（14 个基线文件）：
  - prompt 渲染：`prompt_image_cst01.txt`、`prompt_video_roles.txt`、
    `prompt_contract_lines.txt`、`prompt_rows.txt`、
    `asset_rules_writing.txt`、`asset_rules_storyboard.txt`；
  - 字幕导出：`srt_estimated.srt`（估算轴）、`srt_calibrated.srt`（真实音频
    校准轴）、`ass_full.ass`（含页眉页脚全 ASS 文档）、`calibrate_report.json`；
  - 分镜提示词：`storyboard_contract_prompt_lines.txt`、
    `storyboard_batch_plan.md`、`storyboard_shot_table.md`、
    `shot_batches_grouping.txt`。
- 黄金文件为本轮首次建立（无旧基线可更），生成命令：
  `GOLDEN_UPDATE=1 PYTHONPATH=. python -B tests/test_golden_outputs.py`。
  后续任何渲染输出变更必须以同样方式重建并在对应结果文件写明原因（测试
  docstring 与本条同口径）。

## 边界与说明

- 未覆盖 `storyboard_contract.rules()` 全文：其中嵌入
  `writing.py` 的绝对路径与动态内容，不适合做整份黄金；已覆盖其
  `prompt_lines()` 提示词句部分。
- `agent/shot_assets.py` 的视频提示词组装依赖文件系统与供应商分支，不属于
  纯渲染器，本轮未纳入；如需可在后续轮次补夹具化黄金。
- 测试断言检验行为（整份文本相等）而非源码字符串；无 skip、无断言弱化。
