# R2129 结果：一份下载只收回到最近一次派发登记的位置（REQ-S01-74／DES-S01-74）（修复轮）

## 问题
用户项目「摄影侠」剧本准备页的项目大纲列出两份相同文件：`Google/Google Gemini 4 Argon/创意_20261030/项目大纲/` 与 `Google/Google Gemini/创意_20261030/项目大纲/` 下的 `摄影侠_项目大纲_Google_20261030.md`，逐字节相同，同一秒写入。
原因：`工作流任务/下载收件箱.json` 里有两次派发的登记（约 1 小时 40 分前记在「Google Gemini 4 Argon」名下、目标是 `创意_20261018/…_20261018.md`；稍后记在「Google Gemini」名下、目标是 `创意_20261030/…_20261030.md`）。`download_inbox.match_registered` 按目标文件名去重，两条登记文件名只差日期，各自成立：后一条同名命中，前一条经 REQ-S01-68 的「只差日期且更新」规则命中，同一份下载被写了两处。

## 改动
- `download_inbox.match_registered`：先为每条登记找候选下载件，再按下载件分组，每组只取派发时间最新的一条（同一时间同名优先）写入；「已有更新文件就跳过」只判这一条。第三个返回值改为登记目标元组。`match()` 返回形状不变。
- `stage_download_inbox_service.collect_download_inbox`：写入后把元组里的登记全部销账，旧登记之后不会补写副本。
- `docs/stages/S01_剧本准备.md`：新增 REQ-S01-74、DES-S01-74 与锚定行。
- `tests/test_download_inbox.py`：新增两条（复现用户场景；最近派发只差日期时按它另存）。新测试在改动前的代码上 2 条都失败，改动后通过。已有断言未动。

## 用户数据
- 经 `storage_maintenance.recycle_paths()` 把 `Google Gemini 4 Argon/创意_20261030/项目大纲/摄影侠_项目大纲_Google_20261030.md` 移到项目 `工作流任务/回收站/自动维护_20261030_153723_d13a00e8/`，移前核对与 `Google Gemini` 目录那份逐字节相同。没有永久删除。

## 验证（本轮运行，worktree）
- `run_selftests -k download_inbox idea_download flow_agent_launch desktop_send_ledger media_publish stage_execution`：全部通过。
- `run_selftests -k req_s01_anchors requirement_traceability download_inbox`：全部通过。
- `smoke_test.py --architecture`：通过。首次运行因 worktree 缺被忽略的本机文件 `维护记录/基准历史.json` 报 1 个错，从主检出临时复制后通过，跑完已删除。

## 未处理
- 同一个 Gemini 网页被识别成两个模型名（「Google Gemini 4 Argon」「Google Gemini」）的问题没有改，本轮只保证不再重复写入。
