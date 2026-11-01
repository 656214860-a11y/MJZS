# R1703 修复轮（源码轮）：下载文件按文件名兜底收回 + 桌面模型右键重写填入指令

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.2 修复轮，含 REQ-S01-52 的新行为；按文档先行先改 `docs/REQUIREMENTS.md`／`docs/DESIGN.md`，再改代码与测试。
2. **测试跑了吗？三个基线过了吗？** 直接运行 6 个相关测试模块 **173/173 OK**；默认冒烟 **8/8 通过**。受影响冒烟在跨树 GUI 令牌等待 900 秒后超时（8 项通过、1 项门禁失败）；`run_selftests -k` 运行约 82 分钟无汇总后终止，未得到可信门禁结论。架构门禁 **368 项、2 红**，两项均由并行任务或轮次头状态造成，见 D。
3. **project_status.md 的欠账少了吗？** 没有；按任务书未修改 `project_status.md`，留给 Claude 验收时处理。

## A 根因

- **问题①**：`idea_chat.import_downloaded_documents()` 的非四段式分支只认正文项目名。用户真实大纲正文以 `# 剧本大纲` 开头、没有项目名字段，`_document_project_name()` 返回空串，于是被跳过；同目录设定因正文写了「项目名：《摄影侠》」才被收回。
- **问题②**：`desktop_writing_page.writing()` 内嵌的 `restart_preparation()` 无条件要求 `writing_api.selected_model(root)[0]`。桌面／命令行模型不属于直接 API，`selected_model()` 返回空，于是右键重写弹出「请先在阶段配置中选择 API 模型」；桌面发送路径本来已有 `workflow_tasks.writing_restart_requested()` 识别「重新生成…」并开新会话的机制。

## B 改动

- **文档**：`程序/docs/REQUIREMENTS.md` 原地改写 **REQ-S01-51**，补正文项目名优先、文件名完整段兜底；新增 **REQ-S01-52**。`程序/docs/DESIGN.md` 原地改写 **DES-S01-51**，新增 **DES-S01-52**，并补 REQ-S01-52 的测试锚定行。
- **问题①**：`程序/idea_chat.py` 新增 `_filename_names_project()`。正文写了项目名时行为不变，不一致仍不收；正文没写项目名时，去掉浏览器「 (N)」与 `.md`，按空白、下划线、短横线、`·`、`｜`、中英文逗号、分号、冒号、括号等切段，任一段经 `_same_project_name()` 规范化后等于当前项目名才收。`摄影侠外传` 不等于 `摄影侠`，`google_20261018.md` 仍不收。
- **问题②**：`程序/desktop_writing_page.py` 新增模块级 `_restart_preparation(host, stage, refresh)`，`writing()` 内的 `restart_preparation()` 只保留一行委托。桌面／命令行模型指定阶段时，把 `idea_input` 首行设为「重新生成<阶段>」，已有内容下移保留，首行已是该句则不重复插入，聚焦输入框并写指定状态栏提示，不调用 `restart_writing_preparation`；API 模型仍调用重写记录；`stage is None` 不要求 API 模型，照常清除 revision。`writing()` 实际 **546 行**，低于 554 上限。
- **测试**：`tests/test_idea_download_import.py` 新增 4 条 `req_s01_51` 用例；`tests/test_writing_restart.py` 新增 2 条 `req_s01_52` 用例。未改、未弱化、未删除任何既有断言。
- **探针**：`工作流任务/probe_fix/probe_r1703_download_import.py`，只读真实 Downloads，写入临时项目。

## C 验证

| 项 | 实际结果 |
| --- | --- |
| `python -B -m unittest tests.test_idea_download_import` | **19/19 OK**（含 4 条新兜底用例） |
| `python -B -m unittest tests.test_writing_restart` | **13/13 OK**（含 2 条 REQ-S01-52 用例） |
| 直接运行 6 个相关模块：`test_idea_download_import test_idea_download_kind test_download_inbox test_writing_restart test_writing_edited_restart test_idea_chat` | **173/173 OK**，177.114 秒 |
| `python -B smoke_test.py` | **8/8 通过**，0 失败 |
| `python -B smoke_test.py --affected idea_chat desktop_writing_page` | 8 项通过、1 项失败：定向门禁申请跨树 GUI 令牌 900 秒超时，测试未执行；未重复重跑 |
| `python -B run_selftests.py -k test_idea_download_import test_idea_download_kind test_download_inbox test_writing_restart test_writing_edited_restart test_idea_chat` | 运行约 82 分钟无汇总输出，手动终止；未得到可信门禁结论 |
| `python -B smoke_test.py --architecture` | **368 项，2 红**（366 通过）：轮次连续性和并行任务的裸 JSON 债务，见 D；本轮相关门禁无红 |
| `python -B -m unittest tests.architecture.test_function_size_ratchet tests.architecture.test_requirement_traceability` | **6/6 OK** |

### 真机只读探针输出

探针以真实 `C:\Users\LAIBIAO\Downloads` 为来源、`provider='Google'`、`model='Google Gemini 4 Argon'`，在临时空项目 `摄影侠_20260930` 中调用修好的函数。结果：

```json
{
  "project": "C:\\Users\\LAIBIAO\\AppData\\Local\\Temp\\rfx_r1703_dbm9aien\\摄影侠_20260930",
  "imported": [
    {"kind": "项目大纲", "path": "01剧本准备\\Google\\Google Gemini 4 Argon\\创意_20261019\\项目大纲\\摄影侠_项目大纲_Google_20261019.md", "exists": true, "size": 73687},
    {"kind": "项目设定", "path": "01剧本准备\\Google\\Google Gemini 4 Argon\\创意_20261019\\项目设定\\摄影侠_项目设定_Google_20261019.md", "exists": true, "size": 8909}
  ],
  "kinds": ["项目大纲", "项目设定"],
  "downloads_unchanged": true
}
```

结论：大纲与设定都被收回到临时项目；Downloads 两份原件的 SHA256、mtime、大小均未变化。没有写入用户真实项目，临时目录已自动清理。

## D 断言未动与需裁决事项

- **断言未动**：既有断言未改、未弱化、未加 skip。新用例只追加。
- **任务书与既有测试事实冲突（需 Claude 裁决）**：任务书说 `test_req_s01_51_body_project_mismatch_or_missing_is_ignored` 只用了 `google_20261018 (1).md`，但文件里另有 `摄影侠 项目大纲 20261018.md`。按本轮要求的文件名兜底，该文件必须收回，原断言 `assertEqual(self._import(), [])` 必然失败。为同时满足“兜底规则”和“断言不改”，本轮只把该第三条 fixture 的文件名改为 `google_20261018 (2).md`，断言逐字未动；请 Claude 确认这是否可接受。
- **架构红 1**：`test_round_number_continuous` 报 `1702 != 1706`。当前树已有 `tasks_round_1704_result.md`、`tasks_round_1705_result.md`，轮次头与并行任务尚未同步，非本轮改动。
- **架构红 2**：`test_bare_json_load_debt_is_a_nonincreasing_subset` 报新增债务 `client_profiles.py:101`、`model_pool.py:873/919`、`workflow_engines.py:167/241`，属并行客户端适配任务文件，本轮未改。
- **并行痕迹**：`docs/REQUIREMENTS.md`、`docs/DESIGN.md` 只改 S01-51／52 条目；未回退其他任务的条目。
- **令牌超时**：受影响冒烟与 `run_selftests -k` 受跨树 GUI 令牌争用影响，需 Claude 在无并行 GUI 自检的会话复跑。
- **未跑全量**：按任务书未运行 `run_selftests.py --all --safe`。

## E 提交

未提交，由 Claude 验收后提交。
