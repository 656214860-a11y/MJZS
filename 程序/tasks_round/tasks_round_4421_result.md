# R4421：S04-TIMELINE-LOCK 时间线、单镜版本与锁定回写
<!-- round-evidence: {"commit_base": "2e77de5db", "credential_hits": 0, "evidence_sha256": "b176e6075d30a522", "exit": 0, "failed": 0, "passed": 133, "round": 4421, "tests": "run_selftests.py -k animatic_timeline animatic_service req_s04_anchors animatic_scope artifact_schema copy_rules"} -->

- 轮次类型：§3.1 功能轮（REQ-S04-62/80…85/90/91，DES-S04-23/24）。
- 测试跑了吗：跑了定向与架构门禁，全绿。三个基线：定向 115 条全绿；架构门禁 708 条全绿（当轮实际数，改前曾 1 红见下）；覆盖率基线已按 15 个核心目标真实重测刷新（686 模块/133 触达/553 未触达/目标全绿）。
- 欠账少了吗：未新增欠账；`json.loads` 裸债务未新增（两处改为对象校验＋标记串文本校验）。

## 先红摘要（改动前）

`run_selftests.py -k animatic_timeline animatic_service req_s04_anchors animatic_scope artifact_schema`：4 个文件 18 条红，原因即卡面缺陷——

- `test_artifact_schema` ×2：`KeyError: '未登记的产物类型：animatic_timeline'`。
- `test_animatic_timeline` ×10：`ImportError: cannot import name 'animatic_timeline' from 'domain'`；`cannot import name 'load_or_sync_animatic_timeline'/'update_animatic_shot'/'regenerate_animatic_shot'/'replace_animatic_shot_image'/'run_animatic_timeline' from 'stage_execution_service'`。
- `test_animatic_service` ×4、`test_req_s04_anchors` ×2：`ImportError: cannot import name 'lock_animatic'`。
- `test_animatic_scope`、`test_artifact_schema_wiring` 既有用例保持绿，无回归。

## 改了哪几处

- `domain/animatic_timeline.py`（新建，纯 L2 零同层 import 不写盘）：`TIMELINE_FILE/MIN_DURATION/MAX_DURATION`；`build`（初建＋S03 变化重建：同 ID 保留 seconds/image_version/source/references/dialogue_audio/note，经 `artifact_schema.stamp` 落 schema_version）；`set_duration`（仅 2–15 整数秒）、`set_version`、`set_note`；`next_version`（v<N>.* 递增）、`next_video_name`（版本/animatic_v<NNN>.mp4）；`writeback_plan`（深拷贝只改各镜 duration＋顶层 duration＋trim_out 夹紧/trim_in 归零/edit_duration 重算）。
- `contract/artifact_schema.py:34-36`：REGISTRY 登记 `animatic_timeline` v1（required kind/source/shots，owner animatic_timeline，legacy None）。
- `domain/animatic_service.py`（128-146、176-179、197-200、208-217、229-232）：`build_bundle` 形参不变（仍 12 个），经 settings 可选键支持 `shot_references` 逐镜参考图（含 allow_empty_references）、`existing_images` 缺图才生成、`timeline_durations`、`video_relpath`、`shot_versions`（镜头/<ID>/v<N>.<ext> 图名＋image_version 入清单）、`version_tag`/`timeline_sha256` 清单字段；旧签名与旧 v1 清单行为不变。
- `orchestrator/stage_animatic_gateways.py:243-657`（末尾追加，:75/:157 行未移、无新 http:// 字面量）：`_animatic_source`、`_publish_animatic_timeline`（发布前 validate 对象）、`load_or_sync_animatic_timeline`（sha 一致直返、变化重建＋warn_once「分镜已更新，时间线已重建」）、`update_animatic_shot`（切版本先验文件存在）、`regenerate_animatic_shot`（单镜重做写 v<N+1>）、`replace_animatic_shot_image`（validate_imported_sketch 后写 v<N+1> 记 imported）、`_timeline_audio`（三轨：整轨/音乐取 声音/ 目录或注入，逐镜对白幂等 TTS，混音命令 L2 拼装）、`run_animatic_timeline`（参考库配图＋缺图才生成＋按时间线时长＋版本化视频＋清单发布＋时间线回写版本/参考/对白音频）、`lock_animatic`（REQ-S04-90：三项确认→最新清单逐镜时长==时间线否则「时间线改过，请先重新合成」→时长一致只确认→不一致时 writeback_plan→validate_episode→历史版本/<stem>_<时间戳>_<6位sha>.json 存档→原文件原子替换→storyboard_selection.adopt→清单新 sha＋全 True 原子发布；全部在 `publication.transaction()` 内，任一步失败全回滚）。
- `stage_execution_service.py:33`：re-export 追加 6 个新入口。
- `tests/test_animatic_timeline.py`、`tests/test_animatic_service.py`、`tests/test_req_s04_anchors.py`、`tests/test_artifact_schema.py`：18 条新契约/边界用例（见先红摘要）。
- `tests/architecture/_layers.py:46`：`_register(2, "animatic_timeline")`。
- `维护记录/架构统一基数.json` 第一项：`entity_paths`＋`exempt_items` 加 animatic_timeline，`exempt_count` 59→60。
- `维护记录/覆盖率基线.json`：按原 15 个核心目标重测刷新（686 模块）。
- `runbook.md` §11：685→686、552→553。

## 验收命令输出尾部原文

命令 1：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k animatic_timeline animatic_service req_s04_anchors animatic_scope artifact_schema`（目录 程序，exit 0）

```
共 115 条用例，12.8 秒；0 个文件有红
实际跳过 0 条用例：本机没有任何登记位被跳过
ALL TESTS PASSED
```

命令 2：`..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`（目录 程序，exit 0）

```
Ran 708 tests in 278.012s
OK
✅ 架构治理测试：tests/architecture
```

附加：`run_selftests.py -k copy_rules`（18 条全绿，新增文案均 ≤45 字）；`run_selftests.py -k ... copy_rules unification_ratchet`（138 条，unification_ratchet 5 条全绿）；`scripts\coverage_report.py <15 核心目标> --json 维护记录\覆盖率基线.json`（195 tests OK，133/686 触达，已写入）。

## 过程中出现过并已修复的失败

- `test_unification_ratchet.test_bare_json_load_debt_is_a_nonincreasing_subset` 曾红：两处新 `json.loads` 未登记债务 → 改为对象校验＋标记串文本校验（`_publish_animatic_timeline`、`lock_animatic`），未新增债务登记。
- `test_animatic_service.test_req_s04_90_lock_...` 曾红 1 次：清单发布文本校验 needle 写错（`"confirmed":true` 对对象值不成立）→ 改 `'"rhythm":true'`。

## 未验证项

- 默认 `comfy_local` 后端真实出图未在本轮离线验证（测试经 `animatic_sketch_backends.register` 桩件与注入 render 覆盖路径；`_timeline_render` 走 `create(settings)` 同一分流）。
- UI 页面对新入口的接线由 S04-PAGE-REDESIGN 承担，本卡未做页面联调。
- 全量 `--all --safe` 未跑（卡面不要求；定向与架构门禁均绿）。

## 卡外发现（只记录）

- `orchestrator/stage_animatic_gateways.py` 既有 `confirm_animatic` 的 `json.loads` 属第四项已登记债务；本轮新代码未沿用该写法。
