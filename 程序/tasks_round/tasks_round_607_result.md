# R607｜功能轮｜剧本准备输入框 SKILL 斜杠指令

## A. 目标与范围

- 在剧本准备的输入框中输入 `/` 时，显示当前项目“剧本准备”阶段已勾选的 SKILL 指令。
- 本轮仅修改 `desktop.py` 与剧本准备界面回归测试；不改 SKILL 文件、发送链路或项目数据。

## B. 实现

- `Desktop.idea_skill_commands()` 从项目级 `stage_config.load(...)["script"]["skills"]` 读取已勾选项，并通过注册表取得规范 ID、显示名与说明；仅保留未弃用的剧本阶段 SKILL。
- 输入框光标所在行以 `/` 开头时，`show_idea_skill_menu()` 在输入框下方显示可筛选列表。继续输入会按 ID/显示名过滤；没有匹配项即关闭列表。
- 点击、Tab 或 Enter 选择后，`insert_idea_skill_command()` 仅将当前 `/片段` 替换为 `/skill-id `。它仍是普通输入文字，原有发送、附件引用和模型调用逻辑未变。
- 新增回归：只显示当前勾选的 `script-dialogue-polish`，并验证选择后的插入文本与菜单关闭行为。

## C. 改动文件

| 文件 | 改动 |
| --- | --- |
| `desktop.py` | 新增斜杠指令读取、候选列表、插入/关闭逻辑，并绑定输入框 `KeyRelease`。 |
| `tests/test_idea_chat.py` | 新增 `SkillCommandCompletionTests` 1 条 Tk 回归。 |

## D. 验证

- `python -m unittest tests.test_idea_chat.SkillCommandCompletionTests`：1/1 通过。
- `python -m unittest tests.test_idea_chat.ComposerLayoutTests`：2/2 通过。
- `python smoke_test.py --affected desktop`：9 项通过；定向 7 条用例无红。增量台账临时文件写入被系统拒绝，测试本身通过。
- `python smoke_test.py`：8/8 通过。

## E. 交互说明

在“剧本准备”输入框键入 `/`，即可看到目前在“阶段配置”中勾选的 SKILL。输入 ID 或显示名的一部分可缩小列表；选择后会插入如 `/script-dialogue-polish `，再继续补充创意并按原方式发送。
