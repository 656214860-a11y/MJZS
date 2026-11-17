# R3159 结果（零依赖边界与媒体预览任务书 M1：FFmpeg 随包与取路径统一）
<!-- round-evidence: {"commit_base": "61d433b2", "credential_hits": 0, "evidence_sha256": "6896bd7207081d11", "exit": 0, "failed": 0, "passed": 166, "round": 3159, "tests": "run_selftests.py -k context environment_check req_s04 req_s10 output_spec editing_scope video_revision animatic_service edit_export"} -->

- 轮次类型：功能轮（任务书 M1；领号时 3154–3158 已被其它工作树占用，本轮实领 **R3159**，分支 `codex/wip-R3159`）。

## 三问

1. **本轮属于 §3 哪种类型？** 功能轮（默认）：FFmpeg/FFprobe 运行时解析契约变更，先改 `tool_path` 契约与测试，再迁移全部消费方。
2. **测试跑了吗、三个基线过了吗？** 跑了。冒烟 9/9 通过；定向 `run_selftests.py -k` 两批共 172 条用例全绿（context/environment_check/req_s04/req_s10/output_spec/editing_scope/video_revision/asset_gating/row_targets/timers/video_ui 等）；首轮定向暴露 `req_s04` 2 红（裸命令名替身被新校验拦截），已按「裸命令名原样下传」修复后复绿。全量 `--all --safe` 按 §5 攒到合入 master 前的发布点统一跑。
3. **欠账少了吗？** 减少：M1 全部落地——随包 FFmpeg 就位、取路径唯一入口收口、硬编码 `D:/Tools` 兜底清零、config 默认清空、新项目不再复制绝对路径、环境自检可分辨随包/配置/PATH 三档。

## 本轮改动

| 文件 | 改动 |
| --- | --- |
| `contract/platform_tools.py` | `tool_path(name, fallback='', configured='')`：优先级＝**显式有效配置 > 随包 > PATH > fallback 原文**。新增 `_bundled_tool()` 定位 `运行环境/ffmpeg/bin/<name>.exe`（相对应用根，文件真实存在才返回）。显式**路径**用 `is_file()` 校验，失效回退；**裸命令名**（无 `/` `\`）无法按文件校验，原样下传由 exec 时 PATH 解析——保留 `'stub'`/`'ffmpeg'` 测试替身缝（首轮 req_s04 红的根因修复）。`_TOOL_CACHE` 只缓存 which 结果的原契约不变。 |
| `orchestrator/engine.py` | 新增模块级 `_media_tool(cfg,name)`（测试用 `Studio.__new__`/鸭子替身只有 `cfg`），`_encode`/`_join_shots`/`assemble`/版本检查/输出校验共 7 处 `self.cfg['ffmpeg'/'ffprobe']` 直读全部改走统一解析。 |
| `local_video.py` | 复用 `engine._media_tool`，版本检查与解码校验 2 处直读改走统一解析。 |
| `agent/media.py` | 新增同款 `_media_tool`；`probe()`/`validate_import()` 不再直读 `cfg["ffprobe"]`，缺工具给出可读错误。 |
| `domain/animatic_service.py` | `build_bundle` 的 ffmpeg/ffprobe 实参改经 `tool_path(configured=settings.get(...))`。 |
| `domain/keyframe_evidence.py`、`infra/native_asset_codec.py` | 移除 `tool_path('ffmpeg','D:/Tools/ffmpeg/bin/ffmpeg.exe')` 硬编码兜底，改 `tool_path('ffmpeg')`。 |
| `orchestrator/previs_automation.py` | 移除 `D:/Tools` 兜底；`integrations.tool_path` 即 `platform_tools.tool_path` 再导出，自动获得随包层。 |
| `orchestrator/stage_animatic_gateways.py`、`stage_gate_gateways.py`、`stage_completion_service.py` | `config.get(tool) or tool_path(tool)` 旧式合并改为 `tool_path(tool, configured=...)`，失效显式值不再压住随包/PATH。 |
| `domain/projects.py` | `create()` 不再把 `ffmpeg`/`ffprobe` 复制进新项目 `config.json`（`cfg` 为 `_read_json` 新对象，pop 不影响全局配置）。既有项目里的失效绝对路径原样保留、读取时被忽略。 |
| `environment_check.py` | `check_ffmpeg(config, which, bundled=None)` 三档判定：有效显式配置 → 随包（标「随包版本」，失效配置降级 WARN 并提示）→ PATH → MISSING；裸命令名标「按 PATH 解析」，与 `tool_path` 同序。 |
| `distribution_manifest.md` | 「必须保留」新增 `运行环境/ffmpeg/` 行：LGPL 构建、须含 LICENSE/NOTICE 与来源版本说明、可替换性义务。`distribution_build.py` 按清单解析，无需改码。 |
| `tests/test_context.py` | `ToolPathTests` 注入 which/随包双桩；新增 3 条 REQ-M1 用例：有效显式路径优先、无配置时随包优先于 PATH、失效显式路径回退随包→PATH→fallback。原「which 缓存」「missing+fallback」断言原样保留。 |
| `tests/test_environment_check.py` | 新增随包档用例（无配置→随包 OK；失效配置→WARN+随包）；原 PATH/missing 断言保留。 |

## 随包 FFmpeg 实况（实测，非估算）

- 来源：FFmpeg-Builds `ffmpeg-n9.0-latest-win64-lgpl-9.0.zip`（LGPL 构建，`libx264/libx265/libfdk-aac` 均 `--disable`，见 `ffmpeg -version` 配置行）。
- 版本：`ffmpeg/ffprobe n9.0.2-57-gd838f9f9ae-20261116`。
- 落位：`D:\漫剧制作助手\运行环境\ffmpeg\` → `bin/ffmpeg.exe`、`bin/ffprobe.exe`（弃用 ffplay.exe）、`LICENSE.txt`（LGPL v3 全文）、`NOTICE.txt`（来源/版本/许可证/可替换性）、`presets/`。
- **实测体积：bin/ 合计约 252 MB**（任务书估 60–130 MB，LGPL 静态构建实际更大；已在本文件记实测值）。`运行环境/` 不入 Git，由分发构建/部署侧携带，清单已声明。
- 真实解析验证：`tool_path` 对随包 ffmpeg/ffprobe 返回绝对路径；有效显式路径优先；失效显式路径回退随包。

## 决策与边界

- `程序/config.json`（本机运行配置，不入库）`ffmpeg`/`ffprobe` 已清空为 `''`，新装默认即走随包；全局配置不再向项目复制这两个键。
- `维护记录/基准脚本/recovery_to_delivery_baseline.py` 仍含 `D:/Tools` 常量——属维护基准脚本非运行时消费方，未动（记录备查）。
- `ui/skill_tools.py` 的 `ffprobe_config` 上下文键生产侧从未赋值（存量死路径），其下游 `media.check→probe` 已走 `_media_tool`，不在本轮扩修。
- 未新增 pip 依赖；未打包离线 ASR（M6 另轮）。

## 验证

- `smoke_test.py`：9/9 通过（本轮改动后复跑）。
- `run_selftests.py -k context environment_check` 等两批：172 条用例 0 红；`test_req_s04_anchors` 初跑 2 红 → 裸命令名修复 → 复跑全绿。
- 真实随包解析冒烟（patched `_BUNDLED_BIN_DIR` 指向 D:\ 实况）：configured-valid > bundled > invalid-configured→bundled，符合优先级。
- `run_selftests.py --all --safe` 全量：未运行（按 §5 攒到合入 master 前发布点执行）。

## 提交

- 待提交（`dev.py commit`，功能轮，含 `--tests` 证据）。
