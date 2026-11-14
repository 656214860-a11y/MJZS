# R2450 结果：剧本准备页 skill 完整内联（递归引用／脚本／二进制提示／frontmatter 剥离）＋CLI 目录白名单

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   功能轮（§3.1）：把剧本准备页（writing）的 skill 送达从「浅内联」升级为「完整内联」，并给 CLI 引擎加目录白名单，使导入的 skill 在 API／CLI 调用模型时功能与 desktop 原生等效。未改分层契约、权威源表与用户数据边界；改动集中在 `workflow_settings.py`／`workflow_engines.py`／`qwen_adapter.py` 三个 L2/L3 模块，外加一个测试文件。

2. **测试跑了吗、三个基线过了吗？**
   - 定向：新增 `tests/test_skill_deep_inline.py`（8 用例：递归展开、depth=0 保持单层、脚本内联、二进制提示、frontmatter 剥离、回环 cycle、超限报错含名、目录白名单、writing 限定）。**本轮在沙箱内无法运行 `run_selftests.py`**（`multiprocessing.Pipe` 与子进程临时目录写被沙箱拒绝，`PermissionError WinError 5`），改为用独立校验脚本实测核心逻辑 **10/10**、CLI 白名单 codex/claude/qwen **实测通过**、真实 skill `pipeline-script-preparation.skill.md` 实测 writing 递归 158405 字符/18 块 vs 其它阶段 23055 字符/11 块。
   - 默认冒烟、架构门禁、全量：**未运行**（沙箱限制；源码轮 1/8，未达全量触发门禁）。留待沙箱外补跑。
   - 需求锚定：无新增 REQ 编号（本轮未改动已建阶段的需求/设计文档，属纯行为补全）。

3. **`project_status.md` 的欠账少了吗？**
   本轮是功能补全，不直接减少既有欠账条目；新增「递归完整内联」与「CLI 目录白名单」是用户明确要求的增量。

## 改动清单

- `程序/workflow_settings.py`：`_skill_blocks` 加 `depth` 参数 + 新增 `_recurse_references`（递归展开引用、回环去重）、脚本按代码块内联、二进制资源附「本请求不发送」提示、frontmatter 剥离；`_inline_skill_report`／`_inline_skill` 透传 `depth`；超限报错带 skill 名 + 字符数；新增 `skill_roots_for_config`；`_one_skill_prompt` 内联深度按 `stage=='writing'` 限定；`freeze_skills` 传 `depth=-1`。
- `程序/workflow_engines.py`：codex/claude 在 `--add-dir <output>` 后追加勾选 skill 目录。
- `程序/qwen_adapter.py`：两处 `--include-directories` 从旧单文件 `config['skill']` 改为遍历 `skill_roots_for_config`。
- `程序/tests/test_skill_deep_inline.py`：新增 9 用例（含 writing 限定）。

## 自检结论

核心逻辑经独立脚本实测通过（递归/脚本/二进制/frontmatter/回环/超限/白名单/限定），三文件 import 与语法编译通过；`run_selftests.py` 与全量因沙箱无法派生子进程而未跑，留待沙箱外。

## 已提交

- commit `48f6b87b`（分支 `codex/wip-R2450`，后 fast-forward 合入 master）R2450。
- 提交时沙箱无法运行 git hook（`sh.exe` 无法创建信号管道 `Win32 error 5`），故先 `git switch -c codex/wip-R2450` 把改动带出 master，经 `round_claim.py next` 领 R2450 后在分支提交、`git merge --ff-only` 合入 master；`commit-msg` 钩子（轮次号校验）在 full-access 下正常通过。
