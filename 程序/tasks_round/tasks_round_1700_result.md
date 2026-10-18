# R1700 修复轮（源码轮）：桌面端导出文件名不是约定名时，改按正文项目名收回

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.2 修复轮（源码 + 文档 + 测试）。按任务书先补 `docs/` 的 REQ-S01-51／DES-S01-51，再改 `idea_chat` 与测试。
2. **测试跑了吗？三个基线过了吗？** 新增/相关 `test_idea_download_import` 直接运行 **15/15 OK**；`test_idea_download_kind` **2/2 OK**；`test_download_inbox` **5/5 OK**；默认冒烟 **8/8 通过**。受影响冒烟在跨树 GUI 令牌等待 900 秒后超时（8 项通过、1 项门禁失败），`run_selftests -k` 运行约 40 分钟未返回汇总后中止；均未伪装成通过。架构门禁 **368 项，1 红**，红项与本轮无关（见 D）。
3. **project_status.md 的欠账少了吗？** 没有；按任务书不修改 `project_status.md`。本轮改动未改变该页的欠账记录，留给 Claude 验收时处理。

## A 根因

下载收回有两条路径，之前都先解析文件名：

- `download_inbox.match()` 只按任务书登记的目标文件名匹配，容忍「 (N)」；
- `idea_chat.import_downloaded_documents()` 只按四段式 `项目名_文件类型_内容_年月日.md`（`stage_file_info` 的 `stage-v1`）匹配，文件名不合格式直接 `continue`。

桌面端导出 `google_YYYYMMDD.md`（如用户的 `google_20261018.md`）时，两条路都无法从文件名得到项目名／类型，因此刷新后文件没有被搬回项目。正文其实已经能由 `is_project_document_text()` 和 `_project_file_type()` 判类，缺的是「文件名解析失败后改读正文并核对正文项目名」。

## B 改动

- **文档**：`程序/docs/REQUIREMENTS.md` 新增 **REQ-S01-51**（仅按正文、项目名必须与当前项目一致、取不到或不一致不收）；`程序/docs/DESIGN.md` 新增 **DES-S01-51** 并补测试锚定行。
- **实现**：`程序/idea_chat.py` 在 `stage_file_info()` 非 `stage-v1` 时读取正文（`utf-8-sig`），经 `is_project_document_text()`／`_project_file_type()` 判类，再从正文的 `项目名／项目名称／剧名` 字段或首行标题中的类型标签取项目名，与 `script_contract.project_name(root)` 比较；取不到或不一致一律跳过。
- **保持原逻辑**：四段式老路径的项目／类型／Provider 内容段匹配不变；正文分支不比较 Provider 内容段，落盘仍使用调用方传入的 Provider／模型；每类只取最新一份、必须比该模型该类已保存文件新、沿用 `DOWNLOAD_IMPORT_MAX_AGE` 三天窗口和 `save_reply`；下载原件不动，只扫描下载目录顶层 `*.md`。
- **状态文案**：`refresh_script_workspace()` 现有「已从下载文件夹更新<类型>「<文件名>」」已包含文件名，无需改 UI。
- **探针**：`工作流任务/probe_dl/probe_download_import.py`，只复制用户文件到临时下载目录，对临时项目调用修好的函数，不写用户真实项目。

## C 验证

| 项 | 实际结果 |
| --- | --- |
| `python -B tests/test_idea_download_import.py` | 15 项，OK（含 7 项 REQ-S01-51 新用例） |
| `python -B tests/test_idea_download_kind.py` | 2 项，OK |
| `python -B tests/test_download_inbox.py` | 5 项，OK |
| `python -B smoke_test.py` | 8 项通过，0 失败 |
| `python -B smoke_test.py --affected idea_chat desktop_script_pages stage_execution_service` | 8 项通过，1 项门禁失败：跨树 GUI 令牌等待 900 秒超时；未重复重跑 |
| `python -B run_selftests.py -k test_idea_download_import test_idea_download_kind test_download_inbox test_idea_chat` | 运行约 40 分钟无汇总输出，中止；未得到可信门禁结论（直接跑前三个测试文件的结果见上） |
| `python -B smoke_test.py --architecture` | 368 项，1 红：`desktop_writing_page.py::writing 564 行 > 上限 554`；本轮未改该文件 |
| `python -B -m unittest tests.architecture.test_requirement_traceability tests.architecture.test_static_hygiene` | 8 项，OK |

### 真机只读探针

首次运行（原件存在时）：

- 原件：`C:\Users\LAIBIAO\Downloads\google_20261018.md`，8910 字节；
- 临时项目：`摄影侠_20261018`；
- 结果：`kind=项目设定`，写入 `01剧本准备\Google\Gemini Desktop\创意_20261018\项目设定\摄影侠_项目设定_Google_20261018.md`；
- 临时下载目录中的副本 `source_untouched=true`。

后续再次运行探针时，原路径文件已不存在；Downloads 中出现了外部的 `摄影侠 项目设定 Google 20261018.md` 与 `摄影侠 项目大纲 Google 20261018.md`。这不是本轮移动或改名，探针没有写用户目录。因此真机证据以首次运行结果为准，后续原件状态如实记录。

## D 断言未动与留给 Claude／用户的事项

- **断言未动**：未修改、弱化或删除任何既有断言；新用例新增在 `tests/test_idea_download_import.py`，测试名含 `REQ-S01-51`。
- **架构红灯**：`git status` 显示 `程序/desktop_writing_page.py` 与 `程序/tests/test_writing_restart.py` 有并行改动；`desktop_writing_page.py::writing` 超 554 行上限不是本轮产生，本轮未碰该文件。
- **并行改动**：`程序/docs/DESIGN.md` 同时出现 `DES-S01-52`，`idea_chat.py` 曾出现「正文无项目名时按文件名兜底」的并行改动；后者与任务书「正文取不到项目名就不收」冲突，已只移除该兜底与对应测试，没有回退 `DES-S01-52` 或其他并行文件。
- **令牌超时**：受影响冒烟与 `run_selftests -k` 都受跨树 GUI 令牌争用影响；需要 Claude 在无并行 GUI 自检的会话复跑受影响冒烟与 `run_selftests -k`。
- **真机原件变化**：`google_20261018.md` 在验证期间被外部改名／移走；用户真实项目没有被本轮写入。若需要再次真机复验，请恢复或指定该导出文件。
- **真实项目名未核验**：按任务书没有读取用户真实项目目录，因此无法确认其项目名是否就是「摄影侠」；探针只证明正文中的项目名能被提取并与临时项目名匹配。
- **未跑全量**：按任务书未运行 `--all --safe`。

## E 提交

未提交，由 Claude 验收后提交。
