# R3241 结果 · U4 发送键圆形外框 + ↑/■
<!-- round-evidence: {"commit_base": "cc998ada", "credential_hits": 0, "evidence_sha256": "c7920942a315b51b", "exit": 0, "failed": 0, "passed": 222, "round": 3241, "tests": "run_selftests.py -k shared_input_ui script_composer idea_chat ui_icons nav_icon icon_source"} -->

- 轮次类型：功能轮（UI 统一组件标准任务书 U4，D13 契约）。
- 三问：测试跑了；定向集复测 222/222 全绿、冒烟 9/9、图标两门禁 8/8；`project_status.md` 欠账无变化。首轮 17 红均非本轮代码缺陷：2 红为运行中读到中途修订前的旧断言，16 红为本工作树三个技能 gitlink 子模块未检出（环境欠账，已按主工作区同 SHA 补齐）。

## 改动

- `ui/ui_composer_style.py`：`Tokens.Composer.Send.TButton` 由「主色块＋PNG」改为 D13 圆形外框——`rounded_photo` 生成 32px（`SPACING['2xl']`）圆环底图，`element_create("image")` 按 normal/active/disabled/focus 四态挂不同描边色（`border_input_hover`/`primary`/`disabled_text`/`focus`），卡片底无填充；字形 `ICON_FONT` 居中，foreground 同态映射。原主色块样式平移给新增的 `Tokens.Composer.Listening.TButton`（听写中麦克风高亮不变）。
- `desktop_shared_input.py`：发送键撤掉 `IconLoader.nav_icon('send'/'stop')` 与 `_icon_*` 属性，纯 `PrimaryButton(text=ICON_SEND, style=Send.TButton)`；注释改为「圆形描边由命名样式绘制；MDL2 上箭头／方块随运行态切换，不加载 PNG」。
- `ui/desktop_script_pages.py`：`update_script_interrupt_button()` 保留为运行中↔空闲唯一入口，仅删 `_icon_send/_icon_stop` 图片切换，text 在 `ICON_STOP`/`ICON_SEND` 间切换、command 在 `interrupt_script_agent`/`shared.send` 间切换，行为不变。
- `ui/desktop_voice_input.py`：`LISTENING_STYLE` 由 `Send.TButton` 改 `Listening.TButton`（原来听写高亮借发送键样式，发送键改圆环后必须拆出，否则麦克风会被画成圆环）。
- `scripts/build_nav_icons.py`：`send`/`stop` 移出 `ICONS` 与 `LIGHT_INK_KEYS`，`render_icons` 签名去 `light_ink`；`assets/nav/send.png`、`stop.png` 删除（全仓 grep 零引用后删，U4 任务书授权）。
- `docs/stages/S01_剧本准备.md`：REQ-S01-62／DES-S01-62 描述同步为「无填充圆形描边＋MDL2 字形」，注明不再依赖两张 PNG。
- `tests/architecture/test_icon_source_boundary.py`：`GLYPH_BASELINE` 中 `ui/ui_composer_style.py` 的 `ICON_FONT` 3→4 并注明原因——Send 拆出 Listening 后同域多一处字体引用，属样式拆分非新增字形类别（输入图标行 MDL2 域，U3 已裁决保留）。

## 测试契约变化（§2.4）

- `tests/test_shared_input_ui.py` 新增 `test_send_outline_is_circular_and_matches_icon_row`：断言 `image` 为空、按钮宽≈高（圆）、与 `voice_button` 垂直中心对齐（Δ≤3px）、style map 的 active→`primary`／disabled→`disabled_text`、语音钮仍 `Icon.TButton`。
- `tests/test_script_composer.py:219`：听写中断言 `Send.TButton`→`Listening.TButton`（样式拆分的契约同步）；同文件 238/263/276/288 行空闲态 `Icon.TButton` 断言不动。
- 行为类断言（点击发送、Enter 发送、运行中终止、Esc 终止）全部保持原样。

## 验证

- `ICON_SEND=\uE74A`（MDL2 "Up"）与 `ICON_STOP=\uE71A`（"Stop"）经 Microsoft Learn 码位表核实，字形即上箭头与方块，无需新增常量。
- 截图取证（隐藏桌面真 Tk，PrintWindow）：`tasks_round/evidence/R3241_send_{idle,running,hover,disabled,focus}.png`（100%）与 `R3241_send_{idle,running}_150.png`（150% `tk scaling=2.0`）。像素核验：按钮实测 34×34（150% 档 50×50，scaling 感知正确）；五态主题色均实测命中（idle/running=`border_input_hover` 灰、hover/focus=`primary` 蓝、disabled=`disabled_text` 中性灰）；idle 中心裁剪行剖面呈「宽顶细茎」上箭头形，running 呈方块形；state 互差 idle↔hover 177px、idle↔focus 213px、idle↔running 61px。
- `run_selftests.py -k shared_input_ui script_composer idea_chat ui_icons nav_icon icon_source`：首轮 222 条／12 文件，1090.8 秒，7 文件红——`test_icon_source_boundary` 1 红与 `test_script_composer` 1 红均为运行中读取到本轮中途修订前的旧断言（基线 3→4、Listening 样式名），修订落盘后复测；`test_idea_chat` 16 红全部为 `skills/00全流程SKILL/AIGC创作全流程/sd-decision-engine/SKILL.md` 缺失——本工作树三个技能 gitlink（`reference/HoLLMwood`、`AIGC创作全流程`、`编剧技能集`）子模块未检出，已按主工作区同 SHA（`git rev-parse HEAD` 与 gitlink 逐一相符）补齐内容后复测。
- `run_selftests.py -k shared_input_ui script_composer idea_chat ui_icons nav_icon icon_source` 复测：**222 条用例全绿，0 红**（519.7 秒；`test_idea_chat` 全部分片、`test_script_composer` 听写态、`test_shared_input_ui` 圆形断言、图标三门禁均过）。首轮 17 红的两类根因（中途修订旧断言、gitlink 子模块未检出）已在上文说明。
- `python -B -m unittest tests.architecture.test_icon_source_boundary tests.architecture.test_nav_icon_size_boundary` → 8/8 绿（基线修订后）。
- `smoke_test.py` → 9/9 绿。

## 基线与欠账

- MDL2 字形欠账：`ui_composer_style.py` ICON_FONT 3→4 为 D13 有意契约（样式拆分），已在基线注明；无新增字形类别，emoji 债无变化。
- `assets/nav/` 由 26→24 张 PNG（send/stop 移除），`test_nav_icon_size_boundary` 集合断言仍绿。
- 技能 gitlink 子模块在功能工作树默认不检出属环境欠账，本轮仅按主工作区同 SHA 补齐以跑通既有测试，未改任何受跟踪文件。

## 提交

见 git log（`codex/wip-R3241`）。
