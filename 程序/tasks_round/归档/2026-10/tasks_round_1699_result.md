# R1699 修复轮（源码轮）：剧本准备选「Google Gemini 4 Argon」发送后，任务没有进入 Gemini 窗口

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.2 修复轮（源码轮 + docs + tests）。按 §2.7 先补 `REQ-S01-50`／`DES-S01-50`，再改代码与测试。
2. **测试跑了吗？三个基线过了吗？** 默认冒烟 **8/8**；定向 `run_selftests -k codex_paste desktop_idea_chat_desktop_paste` **14/14、0 红**；直接 unittest（codex_paste + 新用例 + test_workflow + test_claude_program_detection）**125/125 OK**；`test_pet_ui` **599/599 OK**；`smoke_test.py --architecture` **368/368、OK、145.371 秒**。任务书指定的含 `test_workflow`／`test_pet_ui` 的 `run_selftests -k` 组合在 **跨树 GUI 令牌**处无法取得令牌（common-dir 在沙箱可写根之外），见 C；未跑全量。
3. **project_status.md 的欠账少了吗？** 没有。按任务书未改 `project_status.md`、未领取轮次、未记账；本轮只改文件与测试，提交由 Claude 做。

## A 根因

### 事实

- 模型池记录：`Google Gemini 4 Argon`，`provider: desktop`，`call_mode: Desktop`，`program: C:/Users/LAIBIAO/AppData/Local/Google/Gemini/Gemini.exe`。
- 探针用同一字段注入 `workflow_settings.current(..., model_snapshot=(...))`：`engine` 为 **`desktop-app`**，`display_model` 为 `Google Gemini 4 Argon`，`program` 为上面的 `Gemini.exe`。
- 修复前同一探针（已 patch `launch_windows_app` 与 `paste_existing`，不启动、不粘贴）的结果：
  - `launch_windows_app` 被调用；
  - `paste_existing` **调用次数为 0**；
  - `finish(receipt, 'prepared', ...)` 的文案是 **`已打开 Google Gemini 4 Argon，任务已复制到剪贴板；请切到该窗口粘贴并手动发送。`**（修复前位于 `desktop_idea_chat.py` 的原桌面分支，当前已迁到同文件 `_deliver_desktop_app` 的 `:81`）。
- 因此当前树的真实缺陷是：**`desktop-app` 分支只复制、不粘贴**；文案本身说的是“已复制”，但用户期望的是任务进入 Gemini 输入框。

### 用户看到的「已粘贴」到底出自哪一行

当前工作树里**没有**“已粘贴信息到窗口”这句原文，也没有任何 `desktop-app` 成功粘贴的代码路径。唯一会说“已粘贴到 …”的是 `codex_paste.ps1` 的成功文案（修复前 `:85`，当前 `:111`）：

```text
已粘贴到 $appName，请检查内容并手动点击发送。
```

它只在 `paste_existing` 被调用且真的完成 `SendKeys('^v')` 后出现。修复前只有两个分支会调用它：`claude-desktop-app` 和 GPT 桌面；`desktop-app` 不会。结合 R1592 报告里的“修复在此工作树，正在运行的安装目录尚未更新或重启”，以及 R1592 之前自定义 Desktop 模型会落入 GPT 粘贴路径，**最可能的解释是：用户当时运行的是旧版/未重启的进程，界面来自旧 GPT 路径或旧文案；当前树无法复现该字面文案。**

这一点不能凭现有证据钉死到某一行：如果用户看到的是字面“已粘贴信息到窗口”，请 Claude 让用户确认是否原话，以及应用是否在 R1592 之后重启过。当前树的准确结论仍是：**`desktop-app` 不粘贴，只复制**。

## B 改动

- **docs 先行**
  - `docs/REQUIREMENTS.md`：新增 `REQ-S01-50`（任意 `Desktop` 调用方式：任务必须真的进入窗口，或明确说“仅复制，请手动粘贴”；不得谎称已粘贴）。
  - `docs/DESIGN.md`：新增 `DES-S01-50`（实现位置与降级策略）。
- **`codex_paste.py`**
  - 新增 `app_name=''` 参数并写入 payload；默认值仍是 `Claude Desktop`／`GPT`，既有 Claude/GPT 文案不变。
  - 超时、`OSError`、`ValueError` 文案改用 `app_name`；`OSError` 明确“未粘贴或发送，请手动粘贴”。
- **`codex_paste.ps1`**
  - 目标进程识别泛化：按 `program` 的进程名 + 完整路径匹配；允许同安装根目录下的 `app-*` 版本化子目录（本机 Gemini 实际运行在 `app-1.15.0/Gemini.exe`，配置指向根启动器）。
  - 新增 `app_name`；默认仍输出 `Claude Desktop`／`GPT 桌面`。
  - 桌面程序输入框已有草稿时不覆盖；找不到窗口/输入框时如实返回“已复制到剪贴板；未能自动粘贴…”。
  - 新增 `-SelfTestTarget/-SelfTestProcess/-SelfTestProgram` 只读自检入口，用于验证进程匹配，不启动窗口。
- **`desktop_idea_chat.py`**
  - 抽出模块级 `_deliver_desktop_app()`；`open_flow_agent(..., desktop_paste=False)` 在发送入口开启时调用 `paste_existing(..., program=program, app_name=display_model, deadline_seconds=45)`。
  - 失败时 `finish(..., 'failed', 真实原因)`；成功时 `finish(..., 'prepared', 真实原因)`；不再出现“说已粘贴但没粘贴”。
  - 直接调用 `open_flow_agent` 的旧路径默认保留“仅复制”提示，避免破坏既有断言与旧调用方。
- **`desktop_script_pages.py`**
  - `start_script_workflow()` 调用 `open_flow_agent` 时传 `desktop_paste=True`（真实“发送”入口）。
  - 简报提取的本地发送入口同样传 `desktop_paste=True`。
- **测试**
  - 新增 `tests/test_desktop_idea_chat_desktop_paste.py`（7 条，docstring 含 `REQ-S01-50`）：Gemini/Desktop 分支传参、失败如实回执、`app_name` 传输、超时/OSError/ValueError 文案、默认 Claude/GPT 文案、PowerShell 版本化路径匹配、发送入口 opt-in。
  - **没有修改任何既有断言**；既有 `test_workflow.py` 的 `paste.assert_not_called()` 仍成立，因为它直接调用 `open_flow_agent` 且未开启 `desktop_paste`。

## C 验证

| 命令/探针 | 实际结果 |
| --- | --- |
| 修复前探针 | `engine=desktop-app`；`paste_calls=[]`；提示为“已打开…任务已复制到剪贴板…” |
| 修复后探针 | `paste_calls` 含 `program=Gemini.exe`、`app_name=Google Gemini 4 Argon`、`deadline_seconds=45`；`finish=prepared` |
| `python -B smoke_test.py` | **通过 8 项，失败 0 项** |
| `run_selftests.py -k codex_paste desktop_idea_chat_desktop_paste` | **14 条用例，0 个文件有红，15.5 秒**；汇总后执行器不退出，包装器 45 秒终止（R1696 已登记的同类执行器问题） |
| `python -B -m unittest tests.test_codex_paste_diagnostics tests.test_desktop_idea_chat_desktop_paste tests.test_workflow tests.test_claude_program_detection` | **125/125 OK，18.7 秒** |
| `python -B -m unittest tests.test_pet_ui` | **599/599 OK，86.777 秒，exit=0** |
| `python -B smoke_test.py --architecture` | **368/368 OK，145.371 秒，returncode=0** |
| `smoke_test.py --affected codex_paste desktop_idea_chat` | 门禁 **14/14、0 红、16.2 秒**；汇总后执行器不退出，包装器 90 秒终止 |
| `smoke_test.py --affected codex_paste` | 门禁 **7/7、0 红、0.5 秒**；汇总后执行器不退出，包装器 120 秒终止 |
| 任务书原命令 `run_selftests.py -k codex_paste desktop_idea_chat test_workflow test_claude_program_detection test_pet_ui` | **未进入用例**：停在「申请跨树 GUI 令牌（最多等待 900.0 秒）」，包装器 420 秒终止。原因：Git common-dir 为 `D:/repo-meta/漫剧制作助手.git`，在沙箱可写根之外，GUI 锁无法创建；非用例失败。 |
| 任务书原命令 `smoke_test.py --affected desktop_idea_chat codex_paste workflow_settings` | **未进入门禁用例**：同样停在 GUI 令牌；包装器 100 秒终止。`workflow_settings` 的受影响映射含 `test_workflow`（模块级 `import desktop`）。 |
| `git diff --check` | 无空白错误；仅有 Git 的 LF/CRLF 提示 |
| PowerShell 自检（真实进程路径形态） | `{"match":true}`；错误进程名/越界路径为 false |

### 真机 Gemini 探测（未启动、未粘贴、未发送）

- `Get-Process -Name Gemini`：6 个进程，全部 `MainWindowHandle=0`；其中 3 个可读路径均为 `C:\Users\LAIBIAO\AppData\Local\Google\Gemini\app-1.15.0\Gemini.exe`。
- 当前会话用 `EnumWindows` 枚举，未发现 Gemini 顶层窗口；因此无法在本会话实际执行 UI Automation 的输入框探测。可能是窗口在托盘/最小化、进程在另一桌面会话，或当前会话无窗口访问权限。
- 结论：**“窗口匹配”已验证为纯函数 + 真实路径形态；UIA 实际能否找到 Gemini 输入框、以及粘贴是否成功，必须由用户在真实 Gemini 窗口做一次验收。** 本轮没有向 Gemini 发送任何内容。

## D 留给用户/Claude 的事项

1. **真机验收（必须）**：打开 Gemini 窗口，在剧本准备页选 `Google Gemini 4 Argon` 发送；确认任务文本进入输入框、不自动发送；输入框已有草稿时应拒绝覆盖并提示；未找到窗口时应显示“已复制到剪贴板，请手动粘贴…”。本轮未替用户发送。
2. **“已粘贴信息到窗口”字面来源需裁决**：当前树没有这句原文；若用户确认是原话，最可能是旧版/未重启进程（R1592 已注明运行安装目录未更新）。请 Claude 决定是否只需提示用户重启，还是继续追查旧版路径。
3. **`desktop_paste` 默认关闭**：只由 `start_script_workflow` 与简报提取入口开启；直接调用 `open_flow_agent` 的旧路径仍只复制。这样做是为了不改既有断言与旧调用方。请 Claude 确认这个兼容边界是否接受。
4. **执行器问题不在本轮范围**：`run_selftests` 汇总后不退出（R1696 已有同类记录）；含 `test_workflow`／`test_pet_ui` 的组合还受跨树 GUI 令牌限制。本轮未改执行器，也未把这两类阻塞写成产品失败。
5. **断言未动**：没有修改、弱化或删除任何既有断言；只新增测试文件。`test_workflow` 任务书提到的 2 条已知红在本机本轮直接运行中未出现（125/125 OK），未处理。
6. **未改范围外文件**：没有改 `skills/`、`AGENTS.md`、`architecture.md`、`project_status.md`；没有 `git add/commit/stash/checkout`；没有新增 `.bak_*`；探针只放在 `工作流任务/probe_gemini/`，未放进 `程序/` 根目录。

## E 提交

**未提交，由 Claude 验收后提交。**

## F 改动文件

- `程序/docs/REQUIREMENTS.md`
- `程序/docs/DESIGN.md`
- `程序/codex_paste.py`
- `程序/codex_paste.ps1`
- `程序/desktop_idea_chat.py`
- `程序/desktop_script_pages.py`
- `程序/tests/test_desktop_idea_chat_desktop_paste.py`（新增）
- 探针与临时验证脚本：`工作流任务/probe_gemini/`（不属于产品源码）
