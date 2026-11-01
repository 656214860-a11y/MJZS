# R1701 修复轮：采风「独立信源」按来源主体去重，百科分级封顶 T2

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.2 修复轮（源码轮）。按 §2.7 先改 `docs/REQUIREMENTS.md`（REQ-S01-48／49）与 `docs/DESIGN.md`（DES-S01-41），再改 `recon_service.py` 与测试。
2. **测试跑了吗？三个基线过了吗？** 定向用例全绿：`test_recon_service` 46/46、`test_skill_tools` 5/5、需求锚定 4/4；默认冒烟 8/8；架构门禁 368/368。`run_selftests.py -k recon_service skill_tools` 的测试阶段 51/51、0 红，但进程在写共享增量台账时阻塞（详见 D）；用仅重定向台账路径的等价执行器复跑，51/51、`ALL TESTS PASSED`。
3. **project_status.md 的欠账少了吗？** 未改 `project_status.md`（任务书禁止）；本轮改生产源码，按源码轮应由 Claude 在状态页记 +1，未命中 §5 强制全量条件，未跑全量。

## A 问题与根因

`recon_service.domain_of()` 只用注册域近似发布方。真实样本中新华社同一篇稿同时出现在 `xinhuanet.com.cn`、`news.cn`、`xinhuanet.com`，被算成 3 个独立来源；同一发布方的多个域名、同稿转载都没有合并。`evidence()` 又按同一套域名口径重算，所以卡片声明与机检一起虚高。

## B 改动

- **docs**：新增 `REQ-S01-48`（按来源主体去重：同发布方多域名算 1；正文规范化后相同算 1；无正文时同标题同日期视为同稿，两侧都有正文且不同则不合并）与 `REQ-S01-49`（百科最高 T2，仍计入独立信源）；`DES-S01-41` 补实现位置与字段兼容说明。
- **`recon_service.py`**：
  - `PUBLISHER_ALIASES`：仅登记可确认的新华社三域名（`news.cn`／`xinhuanet.com`／`xinhuanet.com.cn`），注释写明依据；没有把握的域名未加。
  - `publisher_of()`：先查别名表，无别名用注册域。
  - `normalize_content()`／`article_digest()`：正文去空白与零宽字符后取 SHA-256；仅用于同稿合并。
  - `independent_source_count()`：同发布方只算 1；正文哈希相同的转载合并；无正文时用标题＋日期兜底。
  - `evidence()` 与 `collect()` 统一调用新计数口径；落盘字段仍名 `independent_domains`，不新增字段、不改 `artifact_schema` 版本，旧卡读取不受影响。
  - `tier_of()` 新增单一入口 `is_encyclopedia_host()`：`baike.baidu.com`、`baike.sogou.com`、`wikipedia.org`、`baike.com`（含子域名）无论 authority 与正文情况一律最高 T2。
  - `summary()` 文案由「独立域名」改为「独立信源」；`render()` 沿用字段，数值随新口径变化。
- **测试**：`tests/test_recon_service.py` 追加 8 条用例，覆盖 REQ-S01-48 的 (a) 新华社同稿跨域名=1、(b) 同发布方异稿跨域名=1、(c) 无别名异域异稿=2、(d) 旧卡缺新字段可读、(e) 不实声明仍报问题；REQ-S01-49 的 (a) 百科有正文仍 T2、(b) 同权威新闻站有正文仍 T1、(c) 百科仍算 1 个独立信源。既有 38 条断言未改。

## C 验证

| 命令 | 实际结果 |
| --- | --- |
| `python -B -m unittest tests.test_recon_service -v` | 46/46 OK |
| `python -B -m unittest tests.test_skill_tools` | 5/5 OK |
| `python -B -m unittest tests.architecture.test_requirement_traceability` | 4/4 OK |
| `python -B smoke_test.py` | 8/8 通过，0 失败 |
| `python -B smoke_test.py --architecture` | 368/368 OK，281.193 秒 |
| `python -B run_selftests.py -k recon_service skill_tools` | 测试阶段 51 条、0 红；随后卡在共享增量台账写入，未返回（见 D） |
| 等价执行器（仅把 `run_selftests.cache_path` 指到工作区内）`-k recon_service skill_tools` | 51/51、0 红，`ALL TESTS PASSED` |
| `python -B smoke_test.py --affected recon_service skill_tools` | 子门禁 51 条、0 红；父进程因同一台账写入阻塞未返回，已中断 |

未运行：`run_selftests.py --all --safe`（任务书明确不跑）。

## D 环境阻塞与待裁决

1. **共享台账写入阻塞（环境）**：`run_selftests.save_cache()` 的目标在 Git common-dir `D:\repo-meta\漫剧制作助手.git\selftest-incremental.json`，该路径不在本会话可写根内。单独探针调用 `save_cache()` 20 秒超时；测试本身 0.5 秒完成。精确命令的测试阶段均全绿，但进程不能正常收尾。建议 Claude 在可写 common-dir 的环境复跑 `run_selftests.py -k recon_service skill_tools` 与 `smoke_test.py --affected recon_service skill_tools`。
2. **标题＋日期兜底口径**：任务书实现条目只点名「正文哈希」，REQ 文字要求「正文相同或同标题同日期」。当前实现为：两侧都有正文时只认哈希，正文不同不合并；只有缺正文时才用标题＋日期兜底。这样避免两条正文不同的同标题文章被误并。若要求严格只看哈希，删掉 `_title_date_key()` 分支即可。
3. **未纳入别名表的主体**：只登记了任务书给出且能确认的新华社三域名；其他疑似同主体域名没有把握，未加。
4. **工作区并行改动**：`程序/idea_chat.py`、`程序/tests/test_idea_download_import.py`、`docs` 中的 REQ-S01-51／DES-S01-51 与 `程序/维护记录/AIGC包阶段归属.json` 属 R1700／并行任务改动，不在本轮提交范围内，请勿随本轮暂存。

## E 提交

按任务书不执行 `git add/commit`；本轮未提交，等待 Claude 验收与提交。
