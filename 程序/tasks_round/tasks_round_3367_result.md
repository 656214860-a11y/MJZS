# R3367：C4 第 1 批——项目配置损坏写入封堵（部分交付）
<!-- round-evidence: {"commit_base": "92b8182e", "credential_hits": 0, "evidence_sha256": "31b2c0648631b5c4", "exit": 0, "failed": 0, "passed": 32, "round": 3367, "tests": "run_selftests.py -k project_settings_validation l1_lost_update req_s10_anchors"} -->

## 三问

1. 本轮属于 §3.2 修复轮。只封堵项目配置写入口，不交付完整 C4 schema。
2. 已运行非 Tk red→green：固定 92b 基线 11 tests / 11 failures，修复后 11/11 通过。官方首轮 884 条用例有 2 个环境资源红文件，实际 trace 后恢复公共资源 / 进程 FFmpeg 夹具，仅这两文件复验 618 条全绿；正常默认 smoke 9/9、隐藏 probe 通过。架构-all / full 未运行，不能声称三个基线全部全绿；提交门禁由真实自动证据记录。
3. 项目配置损坏后被自动覆写的安全欠账已按本批范围封堵并验证。完整 C4 仍待后续批次，不减少或伪造全量欠账。

## V2 每轮字段

| 字段 | 本轮记录 |
|---|---|
| 目标 | put 遇损坏或不可读配置时拒写，原文件字节保持、正式 save 发布器零调用，仅 FileNotFoundError 可创建新对象。 |
| 范围 | infra/project_settings.py::_read_for_write；tests/test_project_settings_validation.py；tests/test_l1_lost_update.py::ProjectSettingsWriteTests 的一项旧安全契约；本结果和机器证据。 |
| 前置 | 用户授权的独立树 codex/foundation-config-write-safety，固定基线 92b8182ec51a2b49294a7e9affaeea56edcfc471，开工 clean；normal round_claim next 领 R3367，无匹配队列 ID，不冒领其他任务。 |
| 验收 | 坏 JSON、非法 UTF-8、非 object 根值、PermissionError / OSError、损坏 no-op 均 ValueError 且原 bytes 不变 / save 0；missing 成功；unknown fields、隔离读取视图、锁内重读、同文件并发不丢键。 |
| 风险 | 以前依赖“损坏备份后继续写”的调用将收到明确拒写；读取侧 safe-off 维持原样。恢复损坏文件必须显式用户动作，不在本轮。 |
| 回滚 | 由整合 owner 对本轮单一源码提交执行 git revert；无需配置迁移或环境回退。 |
| 车道 | 独立 config-write-safety，仅占用上述文件；不碰 HTTP3359 merge/evidence、DPI/A3/API 或主树源码，不合 master / push。 |

## 四态与 C4 边界

| 项目 | 已实现 | 已验证 | 已合入 | 已发布 |
|---|---|---|---|---|
| C4 part / writecorruptionclosed | 是 | 是，非 Tk + 官方消费者 / 失败项复验 + smoke | 否，交 lead 整合 | 否 |
| 完整 C4 统一配置 schema | 否 | 否 | 否 | 否 |

未引入 schema_version / future-version 规则，未新建 module/layer/helper，未装 pydantic，未改 requirements、依赖白名单或主运行环境。本分支不含主线 runtime 工具定位修复；进程 PATH 只是外部工具测试夹具，不宣称 production tool_path 已修。后续统一校验、project/profile 接入、正式依赖与发行安装验证仍属后续批次。

## 已核实事实与根因

- 固定基线 `_read_for_write` 先 is_file 检查，读取异常后复制 `.corrupt` 并返回空字典，非 object 根值也返回空字典；put 随后继续 save，能抹去未知键。UI `load()` 安全关闭视图不构成写入许可。
- 最小修复保留 put 原有 access 锁内 read-modify-write，不借用 load()；去掉预检降级，直接严格 read，只有 FileNotFoundError 返回空字典。其余读取异常固定 ValueError from None，非 object 固定 ValueError，不把原始异常、路径或输入内容带入错误文案；不再自动创建 `.corrupt` 并据此覆盖。
- 旧测试 `test_corrupt_file_is_quarantined_then_put_succeeds` 明确期待损坏后继续覆盖，与新授权安全契约冲突；仅此项同步为 `test_corrupt_file_rejects_put_without_overwriting`，断言拒写 / save 0 / 原 bytes。不删或 skip，其他丢失更新与并发断言保持原样。
- 所有新行为夹具仅 TemporaryDirectory 合成 JSON 字节；没有读取或写入真实项目配置、主安装 config，也无真实用户配置 dump。

## 验证与证据

- 非 Tk 快速命令：随附 Python，cwd 程序，UTF8=1，`-B -m unittest tests.test_project_settings_validation -v`：11/11 OK。
- 固定基线重放：把 git show 92b8182e:程序/infra/project_settings.py 的源码仅加载进测试进程内存，再跑相同新行为测试：11 tests / 11 failures / 0 errors，确认旧实现会改写原字节，损坏 no-op 也未拒写。
- 关键 red 断言：`AssertionError: b'{\r\n  "auto_review": true\r\n}' != b'{"unknown":"fixture_private_value"}'`；`FAILED (failures=11)`。fixture_private_value 是合成测试标记，不是实际配置。
- 官方持久 wrapper PID 67760；绝对收据 `C:/Users/LAIBIAO/AppData/Local/Temp/R3367-validation/receipt.json`，定向 log 同目录 `00.log`。收据记录 start/end/exit/command，try/finally 落盘；同树串行无重复在途。
- 首次官方定向最终 884 条用例 / 18 文件 / 2 红文件共 4 红 / skip 0 / exit 1；validation 11、l1_lost_update 14、REQ-S10 7、L1-L0 integration 22、integration 27 及其他消费者保持绿。真实 trace：writing_stages 2 红缺 sd-decision-engine/SKILL.md；pet_ui 2 红在 FrameBatchSeamTests → keyframe_evidence.image_facts → tool_path('ffmpeg') 为 None → subprocess.list2cmdline TypeError，不是配置拒写断言。
- 原 wrapper 首个失败即 break，多余 smoke --probe 预设命令未实际执行；不把不存在的运行记成失败或成功。后续只运行正常 `smoke_test.py`，不修改其源码。
- 公共资源按授权从 `D:/漫剧制作助手/.git/foundation-aigc-pinned.zip` 恢复到原空 gitlink 目录；固定 commit 1a43ae5a019d157eb3d45ad73e800081cb127763 / tree d9a208042147179768f0a24dc54bdfbd5374a9e9，与缓存 `D:/漫剧制作助手/.git/foundation-aigc-source` 和登记一致，资源 git diff 空；无配置复制。
- 缺 FFmpeg 仅对子验证进程 PATH 前置 `D:/漫剧制作助手/运行环境/ffmpeg/bin`，未持久修改系统或安装环境。失败两文件官方复验 + 正常 smoke 串行 wrapper PID 68776；收据 `C:/Users/LAIBIAO/AppData/Local/Temp/R3367-validation/recheck-receipt.json`。两文件复验 618 条 / 0 红 / skip 0 / exit 0；默认 smoke 9 通过 / 0 失败，内部隐藏桌面 probe 通过 / exit 0。原 884 条中其余 16 文件保持通过，不无故全套重跑。
- 本轮未跑 full / architecture-all / cycle-all；无新增 import 或层依赖，full 由 root 最终统一 all-safe。

## 提交与整合交接

适用验证已收齐，使用正常 dev.py commit，--tests project_settings_validation l1_lost_update req_s10_anchors 与 exact file allowlist；真实提交证据为 tasks_round/evidence/R3367.json（自动盖章，credential / targeted 计数以该文件为准）。本轮仅一个源码提交；提交自身 full hash、提交后 index clean / no jobs 在交接消息提供，不为补自身 hash 另建文档提交链。

本批安全目标已实现 / 已验证，未合 master / 未发布，完整 C4 未完成。两次临时验证 wrapper 均已有 end/exit receipt 并退出；无本车道仍在途测试。project_status.md 的 N=M+1 由 master 整合 owner 统一更新，分支不修改该文件；完整任务书和总完成文件由 root 汇总，不代填其他车道四态。
