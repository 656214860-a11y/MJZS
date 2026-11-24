# R4399：AST-MOTION-REF 角色动态参考视频资产与提交接线
<!-- round-evidence: {"commit_base": "d16585a84", "credential_hits": 0, "evidence_sha256": "37650b2f7b2bf517", "exit": 0, "failed": 0, "passed": 125, "round": 4399, "tests": "run_selftests.py -k asset_versions asset_detail cloud_video"} -->

- 轮次类型：§3.1 功能轮（先改文档再写码，先红后绿）。
- 测试跑了吗、三个基线过了吗：跑了。定向 125 条 0 红；架构门禁 708 条 0 红；默认冒烟基线本轮未跑（卡面验收只点名定向与 `--architecture`，未跑项如实标注）。
- 欠账少了吗：没有新增欠账；卡外发现一条记录见末节。

## 允许修改文件清单（全部命中，无越界改动）

- `domain/asset_versions.py`（+232）
- `ui/asset_detail.py`（+5，994→999，模块行数棘轮上限 1000 内）
- `agent/volcengine.py`（+66）
- `tests/test_asset_versions.py`（+165，新增 `MotionRefTests` 9 条）
- `tests/test_cloud_video.py`（+111，新增 `MotionReferencePayloadTests` 4 条）
- `docs/specs/09_资产数据生命周期.md`（+9/-7）
- `docs/stages/S05_资产管理.md`（+1/-1）
- `docs/stages/S10_视频生成.md`（+1）
- 本结果文件

## 缺陷复现方式

改前 `domain.asset_versions` 没有任何动态参考入口，详情页没有「动态参考」块，`VolcengineAdapter.payload` 也不读 `motion_references`。新测试 `MotionRefTests` 直接调用 `attach_motion_ref`／`unbind_motion_ref`／`motion_refs`／`motion_ref_dir`／`motion_lines`，`MotionReferencePayloadTests` 在 `motion_references` 已登记的前提下断言 Seedance `content` 里出现 `role=reference_video` 条目。

## 改前红（原样摘录，共 11 条）

`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k asset_versions asset_detail cloud_video` 退出码 1，失败原文：

```
test_asset_versions#2         15 条     0.6 秒  ✗ 9
test_cloud_video#1            15 条     0.8 秒  ✗ 2

AttributeError: module 'domain.asset_versions' has no attribute 'attach_motion_ref'
  （test_attach_registers_file_plan_and_version / test_attach_dedupes_same_sha256 /
    test_attach_limit_three / test_attach_rejects_suffix_oversize_and_missing /
    test_unbind_recycles_file_and_versions / test_motion_refs_skip_escape_missing_and_bad_rows 同因）
AttributeError: module 'domain.asset_versions' has no attribute 'unbind_motion_ref'（test_unbind_missing_row_refused）
AttributeError: module 'domain.asset_versions' has no attribute 'motion_ref_dir'（test_motion_ref_dir_validation）
AttributeError: module 'domain.asset_versions' has no attribute 'motion_lines'（test_motion_lines_rows_and_actions）

test_seedance_payload_carries_motion_reference: AssertionError: 0 != 1
test_motion_reference_skips_escape_missing_and_bad_rows: AssertionError: 0 != 1
```

同轮另有 1 条与本卡无关的红：`test_asset_detail_service.test_both_l2_bindings_return_published_paths` 在 `agent/publication.py:_file_access` 抛 `PermissionError [Errno 13]`（并行写锁争用）；改后复跑已绿，判定为瞬时噪声，记录为卡外问题。

## 改了哪几处

- `domain/asset_versions.py:396-627`：新增动态参考段。`motion_ref_dir`（`assets/参考视频/<类目>/<aid>/`，编号正则锁死防越界）、`_motion_gateway`（`read_json/publish_json/publish_bytes/file_hash/copy_file` 五件套，`None` 时用 `agent.core`＋`infra.file_cache` L1 底座自装）、`_motion_plan`/`_motion_rows`/`_motion_publish`、`_motion_probe`（ffprobe 时长，失败记 `None`）、`attach_motion_ref`（mp4/mov/webm、≤20MB、最多 3 条、sha256 去重、落库名 `<原名>_<sha256:12>.<后缀>`、记 imported 版本）、`unbind_motion_ref`（清单移除＋`storage_maintenance.recycle_paths` 回收＋manual 版本）、`motion_refs`（越界/缺文件/坏行/非视频后缀跳过）、`_open_media`、`motion_lines`（详情块行规格 `(文案, 动作, 视频路径)`，`pick/after/safe/probe` 可注入）。
- `ui/asset_detail.py:860-864`：`show()` 在 `_board_block` 之后内联「动态参考」块（行数棘轮只剩 6 行预算，无法独立成函数）；`safe=desktop.safe` 注入，`media_thumbnail` 现取首帧封面（L4→L4 同层调用，图元留 `button.image` 引用），`run=None` 的说明行以 disabled 按钮展示。
- `agent/volcengine.py:92`：seedance 参考模式 `content += _motion_reference_entries(shot, self.cfg)`。`:110-172`：`_motion_suffixes`/`_motion_base_of`（由资产图路径向上找含 `assets/资产清单/assets.json` 的库根）/`_motion_rows_of`/`_motion_reference_entries`（`white_model_ref.SUPPORT` 同一张能力表判定，`content` 槽位逐条 `role=reference_video`，单条超 `max_mb` 抛错不发请求；只认本镜引用的 CHAR_）。函数放文件尾部：`__init__` 的方舟地址在 `docs/process/外部依赖清单.md` 按 `agent/volcengine.py:18` 登记，行号不能漂。
- 文档：`09_资产数据生命周期.md`（DOC-D9-1 后半件 ✅；§3/§4 加 `motion_references`、§5 参考视频命名、§6 写入口、§9 「动态参考」块、§12/§13）；`S05_资产管理.md` IF-S05-34 → ✅；`S10_视频生成.md` 新增读入行 IF-S10-35 → ✅。
- 测试：`tests/test_asset_versions.py` 新增 `MotionRefTests`（登记/版本/去重/上限/后缀与大小与缺失拒绝/回收与版本/未登记删除拒绝/读侧跳坏行/目录校验/行规格与动作）；`tests/test_cloud_video.py` 新增 `MotionReferencePayloadTests`（带入、不支持模型跳过、非角色跳过、坏行跳过）。

## 改后验收输出尾部（原文）

```
共 125 条用例，40.1 秒；0 个文件有红
实际跳过 0 条用例：本机没有任何登记位被跳过
ALL TESTS PASSED        （run_selftests.py -k asset_versions asset_detail cloud_video，退出码 0）
```

```
Ran 708 tests in 249.795s
OK
✅ 架构治理测试：tests/architecture    （smoke_test.py --architecture，退出码 0）
```

## 三个基线数

- 默认冒烟基线 8/8：本轮未跑（卡面验收未点名；如总控需要可补）。
- 架构门禁：当轮 708 条全绿（改前同口径首次跑时 1 红——正是本卡把登记 URL 行号推漂所致，已修正）。
- 全量回归：未跑（非 master 提交点，卡面未要求）；欠账以 `full-safe-receipts.json` 为准。

## git diff --numstat（提交前原文）

```
66	0	程序/agent/volcengine.py
9	7	程序/docs/specs/09_资产数据生命周期.md
1	1	程序/docs/stages/S05_资产管理.md
1	0	程序/docs/stages/S10_视频生成.md
232	0	程序/domain/asset_versions.py
165	0	程序/tests/test_asset_versions.py
111	0	程序/tests/test_cloud_video.py
5	0	程序/ui/asset_detail.py
```

## 按「建议，待确认」授权执行的项（单列）

- 存储目录定为 `assets/参考视频/<类目>/<aid>/`，文件名 `<原名>_<sha256:12>.<后缀>`——沿用参考图既有 digest 命名与去重口径。
- 大小上限取 20MB——与白模参考视频 `DEFAULT_MAX_MB` 同口径；时长探测用随包 `ffprobe`，失败记 `None` 不阻断导入。
- 「动态参考」块放正典板之后、锚点之前，按 09 §13 推荐位置；说明行写明「仅 Seedance 2.0／2.5 带入，其它模型仅存档」。
- 提交接线只落火山 `content` 槽位；万相 `media` 槽位与不支持的模型本次不接（IF-S10-35 已注明），不支持时详情页写明原因。

## 未验证的地方

- 真实 Seedance 付费提交未发（卡面禁止真实调用）：请求体仅以 mock/构造断言 `role=reference_video`。
- 详情页块的视觉截图未人工过目；行规格、动作闭环、块内按钮与缩略图挂接由 `motion_lines` 测试与既有详情页 Tk 用例（`show()` 全路径仍绿）覆盖。
- `unbind_motion_ref` 对回收站目录的确切批次路径未逐字节核对（断言「源文件消失＋回收根下出现 mp4＋manual 版本记录」）。

## 卡外发现的问题（只记录，不顺手修）

- `test_asset_detail_service` 在并行跑时偶发 `PermissionError`（`writer.lock` flush），单测重跑即绿，疑似增量台账/隐藏桌面包装下的文件锁争用；与本卡无关。

## 被拒绝的命令

无。
