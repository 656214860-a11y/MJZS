# R4194：FIX-IMGCHECK-FIXTURES 图片校验收紧后同步三处假 PNG 夹具
<!-- round-evidence: {"commit_base": "7f4b58d5", "credential_hits": 0, "evidence_sha256": "9ae18d7e761d105a", "exit": 0, "failed": 0, "passed": 23, "round": 4194, "tests": "run_selftests.py -k test_uow_write_paths test_latent_defects_r1853"} -->

## 开头三问

- （一）本轮属于哪种类型：修复轮（§3.2）。R4177 合入后图片导入校验改为魔数＋结尾结构，旧夹具里 `b'new image'`、`b'png-data'` 这类假 PNG 字节被如实拒绝。按 §2.4 契约有意变更，只同步夹具，断言语义不变。
- （二）测试跑了吗、三个基线：跑了。合入 R4177 后后台全量（HEAD 537900b）报 4 个文件红：`test_uow_write_paths`（2 条）、`test_latent_defects_r1853`（1 条）为真回归，错误均为「图片内容无效，请选择完整的 PNG、JPG 或 WebP 图片」；`test_publication_fsync_budget`、`test_perf_baseline` 为负载下的耗时抖动，单独重跑不复现，不属本轮。改前定向 `run_selftests.py -k latent_defects_r1853 uow_write_paths` 共 23 条，2 个文件 3 条红；改后 0 个文件有红、ALL TESTS PASSED。架构门禁未单独重跑（只改测试夹具，未触代码与登记表），默认冒烟未跑；全量以 `full-safe-receipts.json` 为准，后台自动全量已在 R4193 后重启。
- （三）欠账少了吗：少了。R4177 合入引入的三条红已清零；无新增欠账。

## 改了哪些文件

- `程序/tests/test_uow_write_paths.py`：两处假 PNG 夹具（`incoming.png`、`source.png`）改用 `image_fixtures.png()`；顶部补 `from image_fixtures import png`。
- `程序/tests/test_latent_defects_r1853.py`：`source.png` 夹具改用 `png()`；末尾断言「目标文件内容等于来源」的预期值由字面量改为同一夹具值（语义不变）；顶部补 `from image_fixtures import png`。
- 产品代码未改。

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| `run_selftests.py -k latent_defects_r1853 uow_write_paths`（改前） | 共 23 条；2 个文件 3 条红，均为「图片内容无效」 |
| 同上（改后） | 共 23 条；0 个文件有红；ALL TESTS PASSED |

## 未验证

- 未跑默认冒烟与架构门禁（仅测试夹具）。
- `test_publication_fsync_budget`、`test_perf_baseline` 的抖动未深查，只确认单独重跑不复现。

## 偏离卡面

无卡：由总控在合入后全量回归中发现并就地开车道修复，原因是执行者额度全部受限。
