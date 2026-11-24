# tasks_round_4350_result
<!-- round-evidence: {"commit_base": "82e396a27", "credential_hits": 0, "evidence_sha256": "e749c0e46b68ee94", "exit": 0, "failed": 0, "passed": 128, "round": 4350, "tests": "run_selftests.py -k asset_detail asset_versions desktop_asset_pages ui_edges_pages"} -->

## 三问

- 本轮类型：§3.1 功能轮（AST-VERSION-2，先改文档状态再写码，先红后绿）。
- 测试跑了吗、三个基线过了吗：跑了。定向 `-k asset_detail asset_versions desktop_asset_pages ui_edges_pages` 128 条全绿；`smoke_test.py --affected asset_detail desktop_asset_pages asset_versions` 9 个测试文件全绿；`smoke_test.py --architecture` 702 条全绿。
- 欠账少了吗：专项册 09 的「演变记录／并排对比／退回上一版」三个 ⬜ 项落地为 ✅；新增 18 条回归用例。无新增欠账。

## 缺陷复现方式

卡面缺陷：资产详情页没有「演变记录」块（版本历史、并排对比、退回上一版入口缺失，`domain.asset_versions` 无 `restore_version` 写入口）。先在 `tests/test_asset_detail.py` 加 `EvolutionBlockTests`（9 条：列表与来源徽标、块位置、展开全部、文字/图片对比、退回确认/锁定/取消、三档宽度）、在 `tests/test_asset_versions.py` 加 `RestoreVersionTests`（7 条：快照重建、一句话摘要、文字退回、锁定拒绝、缺版拒绝、图片换回历史、旧图缺失拒写），未改产品前跑定向命令确认红。

## 改前红的条数和原因（原文）

共 18 条红（test_asset_versions 7 条、test_asset_detail 11 条），原文节选：

```
AttributeError: module 'domain.asset_versions' has no attribute 'describe'
AttributeError: module 'domain.asset_versions' has no attribute 'restore_version'
AttributeError: module 'domain.asset_versions' has no attribute 'snapshot_at'
AttributeError: module 'ui.asset_detail' has no attribute 'compare_versions'
AttributeError: module 'ui.asset_detail' has no attribute '_evolution_block'
AttributeError: module 'ui.asset_detail' has no attribute 'restore_to_version'
AssertionError: '演变记录' not found in [...]
AssertionError: 'v25' not found in [...]
```

（另有 1 条 `TypeError: png() got an unexpected keyword argument 'size'` 是测试自身签名笔误，已改为位置参数 `png(16, 16, color=…)`，与缺陷无关。）

## 改了哪几处

- `程序/domain/asset_versions.py:22` 加 `import uuid`；`:92-93` `append_version` 透传 `restore_of`；`:156-401` 新增 `_delta`/`describe`/`snapshot_at`/`_sha256`/`_history_dir`/`_find_version_file`/`restore_version`（退回写入口：锁定拒绝、缺版拒绝、旧图缺失拒写；`unit_of_work` 原子写清单与登记表；当前图复制进 `assets/<kind>/历史版本/` 后经 `recycle_paths` 回收；追加 `source='manual'`、`field='restore'`、`restore_of=n` 新记录，不删历史）。
- `程序/ui/asset_detail.py:20` 加 `import difflib`；`:560-562` 常量；`:574-824` 新增 `_evolution_block`（after_idle 读版本文件，空写「暂无历史」、失败降级提示）、`_version_rows`（勾选框＋版本号＋时间＋来源徽标＋`describe` 一句话；默认最近 20 条＋「展开全部」；时间与徽标用 HintLabel 组件过 L4-F9 门禁）、`compare_versions`（左右两栏 `difflib.ndiff` 逐行高亮＋图片缩略图并排、只读）、`restore_to_version`（锁定先拒、确认窗列出将被覆盖的当前内容、`asset_batch_gateway` 注入）、`_restore_preview`/`_version_image`/`_short`/`_checked`/`_compare_pick`/`_restore_pick`/`_version_line`；`:868` `show()` 在使用情况后、原始 JSON 前插一行。文件总行数 995 < 1000 上限。
- `程序/docs/specs/09_资产数据生命周期.md`：DOC-D9-2、§6 并排对比/退回、§9、§12 共 8 处状态格改 ✅/更新（DOC-D9-4 保留 🟡：「被采用版本保留到项目交付」不在本卡范围）。
- `程序/docs/stages/S05_资产管理.md`：IF-S05-33 状态改 ✅；UX-S05-52 按实测填齐交互契约。
- `程序/tests/test_asset_versions.py:451-588` 新增 `RestoreVersionTests`（7 条）。
- `程序/tests/test_asset_detail.py:850-1031` 新增 `_record_change` 辅助与 `EvolutionBlockTests`（9 条；skip 复用 `_Harness.desktop()` 已登记站点，不新增台账项）。

## 改后命令输出尾部（原文）

`run_selftests.py -k asset_detail asset_versions desktop_asset_pages ui_edges_pages`：退出码 0

```
共 128 条用例，91.7 秒；0 个文件有红
实际跳过 0 条用例：本机没有任何登记位被跳过
ALL TESTS PASSED
```

`smoke_test.py --affected asset_detail desktop_asset_pages asset_versions`：退出码 0

```
✅ 门禁 run_selftests.py（定向：asset_detail、desktop_asset_pages、asset_versions）：89 秒 → 0 个文件有红
通过：10 项
失败：0 项
✅ 冒烟测试通过，可以进入下一轮
```

`smoke_test.py --architecture`：退出码 0

```
Ran 702 tests in 294.904s
OK
✅ 架构治理测试：tests/architecture
```

注：首轮架构门禁曾报 2 红——`asset_detail.py` 手写样式 Label 13>11（已把时间与来源徽标两处 `foreground=` Label 换成 HintLabel 组件）与 skip 台账 335!=337（已去掉两个新增 skipTest 站点，改走 `_Harness.desktop()` 已登记站点）；复跑后 702 条全绿。

## 三个基线数

- 默认冒烟基线：8/8（本轮 `--affected` 冒烟 10/10 项通过）。
- 架构门禁：当轮 702 条、失败集合 ∅（改前 2 红为本轮新增样式/skip 违规，已修复；与既有基线相比无新增欠账）。
- 全量回归：分支不累计，未跑 `--all --safe`（卡面验收未要求）。

## 没有验证的地方

- 真机界面交互（勾选两条→对比窗、勾选一条→确认窗→退回）只用隐藏桌面真 Tk 覆盖到对话框创建与内容断言；人工点按路径未实机复验。
- 「大历史后台读取」按 after_idle 一拍后读文件实现，未在超大版本文件下测卡顿阈值。
- 退回后引用镜头的首帧/视频「过期」标记联动属 §8 欠账，不在本卡范围。
- DOC-D9-4「被采用过的版本保留到项目交付」未做（规格里保持 🟡）。

## 卡外发现的问题（只记录）

- `desktop_asset_pages.py` 与 `asset_detail.py` 的版本记录读取口径依赖 `library_dir` 解析，旧布局项目退回时 `asset_write_base()` 先经 `prepare_legacy_asset_base` 迁移；本实现沿用了同一约定，未发现缺陷，但迁移路径下的版本文件搬迁未在本卡测试覆盖。

## 被拒绝的命令原文

```
cd 程序                                     （探测用 cd，两轮均被拒，改用工具读文件与 workdir 参数）
(Get-Content -Encoding UTF8 '…\ui\asset_detail.py').Count   （行数探测，被拒；改用 read 工具看行号）
Select-String -Path '…\content.txt' -Pattern '…'           （读溢出日志探测，两轮均被拒；改用 read 工具）
```

## 提交

- 提交方式：`scripts\dev.py commit -m "R4350: AST-VERSION-2 修复" <文件…> --tests asset_detail asset_versions desktop_asset_pages ui_edges_pages`
- 提交哈希：见完成报告（提交后回填）。
