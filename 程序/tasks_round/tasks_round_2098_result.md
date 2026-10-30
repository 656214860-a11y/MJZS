# R2098 结果：下载件日期比登记目标新时另存新批次（修复轮）
（R2089 领号后被其他会话顶号，提交钩子要求用最新领号，故改以 R2098 提交；R2089、R2095 空号。）

- 轮次类型：§3.2 修复轮（代码偏离用户预期；同轮新增 REQ-S01-62／DES-S01-62，S01 文档已同步）。
- 测试：新增 5 条，先红后绿；定向 30 条全绿；默认冒烟 8/8；`--affected` 有 69 条红，与 HEAD 基线逐文件条数一致（都是工作树缺 `skills/00全流程SKILL/AIGC创作全流程/sd-decision-engine/SKILL.md`），不是本轮引入。未跑 `--architecture`、`--all --safe`，也没在真实界面目测。
- 欠账：没有新增，也没有减少。断言未动。

## 问题

Gemini 桌面下载了 `摄影侠 项目大纲 Google 20261030.md`，剧本准备页的项目大纲列表看不到新文件。

## 根因

1. 任务书按 `delivery_document_path` 沿用已有最新一份，登记的目标是 `创意_20261018/项目大纲/摄影侠_项目大纲_Google_20261018.md`；Gemini 按当天日期命名。每 5 秒的自动收回（`download_inbox.match`）只认归一后完全同名的文件，日期段不同就收不回。
2. 手动「刷新」走 `idea_chat.import_downloaded_documents`，把新内容覆盖进了旧的 `…_20261018.md`，文件名不变，列表上看不出有新大纲。

用户裁决：新下载件另存为新日期文件，旧版本保留。

## 改动

- `download_inbox.py`：新增 `match_registered`／`dated_target`／`_dated`。没有同名件时，只差末尾日期段且下载件日期更新的，写到新日期的文件名和「创意_新日期」批次。`match()` 返回值不变。
- `stage_download_inbox_service.collect_download_inbox`：写新路径，按原登记目标销账。
- `idea_document_paths.reply_document_path`、`idea_chat.save_reply`：新增 `reuse_latest=True` 关键字，默认行为不变。
- `idea_chat.import_downloaded_documents`：下载件文件名日期比已有最新一份新时，按该日期另存（`reuse_latest=False`）。日期相同或更早仍覆盖。
- `docs/stages/S01_剧本准备.md`：REQ-S01-62、DES-S01-62、测试锚定行。

## 改动前失败输出

```
FAIL: test_newer_dated_download_is_saved_as_new_batch_and_old_kept (tests.test_download_inbox.DownloadInboxTests...)
FAIL: test_download_dated_after_existing_outline_is_saved_as_new_file (tests.test_idea_download_import.DownloadImportTests...)
Ran 30 tests ... FAILED (failures=2)
```

改动后：`Ran 30 tests ... OK`。

## 演练

把真实下载件 `C:\Users\LAIBIAO\Downloads\摄影侠 项目大纲 Google 20261030.md` 复制进临时项目，登记旧目标后调用 `collect_download_inbox`：写入 `01剧本准备\Google\Google Gemini 4 Argon\创意_20261030\项目大纲\摄影侠_项目大纲_Google_20261030.md`（85676 字节，与下载件一致），旧文件保留，登记表清空。真实项目没有改动。

## 未做／待用户决定

- 真实项目里的 `创意_20261018/项目大纲/摄影侠_项目大纲_Google_20261018.md` 已在修复前被 10-30 的内容覆盖两次（11:45、11:55）。下载文件夹里 10-24 的 `摄影侠 项目大纲 Google 20261018.md`（81877 字节）可能是旧版本，是否用它恢复由用户决定。
- 本分支合入 master、重启助手后才生效。
