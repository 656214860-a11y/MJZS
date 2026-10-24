# R1960：修复轮——侧栏导航点击时文字被裁（「遮挡」）

## 现象与根因

- 现象：点击左侧目录列表任意一项时，被点那一行的文字上下被裁掉约 4px，看起来像文字被一个色块挡住。
- 根因：ttk 的 `padding` 映射是绝对值。`ui_widgets._configure_button` 在样式创建时按默认内边距 (12,8) 登记按下映射 (12,9,12,7)；随后 `desktop_layout.fit_sidebar` 按窗口高度把导航行内边距 `configure` 成 (10,4)（非 compact 档，行高 29px，正好一个字体行高 19px），却没有同步按下映射。点击瞬间 ttk 按旧映射 (12,9,12,7) 排版：行高仍按常态 29px，文字区只剩 29-2-16=11px，19px 的行高被上下各裁 4px。
- 修复：`ui_widgets` 新增 `set_button_padding(style, name, padding)`——改常态内边距时连按下映射一起改到同一基准（保持「按下文字下移 1px、上下合计不变」的既有反馈）。`_configure_button` 复用同一 `pressed_padding()`。`desktop_layout.fit_sidebar` 的所有按钮内边距调整（Compact.TButton／Nav.TButton／Selected.Nav.TButton／Sub.Nav.TButton／Selected.Sub.Nav.TButton／ProjectAction.TButton）改走该入口。

## 复现步骤

1. 打开应用，窗口高度高于 compact 阈值（非紧凑档）。
2. 鼠标点击左侧导航「03 初步分镜」。
3. 按下瞬间观察该行文字：上下被裁约 4px（红前实测 label 元素高度 11px < 字体行高 19px）。

## 改动文件

- `程序/ui_widgets.py`：新增 `pressed_padding()`、`set_button_padding()`；`_configure_button` 复用。
- `程序/desktop_layout.py`：`fit_sidebar` 的内边距调整改走 `set_button_padding`。
- `程序/tests/test_nav_press_padding.py`（新增）：3 条用例真 Tk 量 label 元素几何，钉住按下态文字区 ≥ 字体行高、子/选中样式同样成立、以及改内边距不清掉 fill/foreground 映射。

## 验证

- 红：改动前旧代码路径实测（Nav.TButton 内边距收到 (10,4) 后按下）label 元素仅占 y=10..20 共 11px，小于字体行高 19px；新测试在修复前运行报 `AttributeError: module 'ui_widgets' has no attribute 'set_button_padding'`。
- 绿：`tests.test_nav_press_padding` 3/3 通过（经 `工作流任务/gui_hidden.py` 隐藏桌面运行）。
- 默认冒烟：8/8 通过（第 10 轮检查项）。
- 受影响模块门禁：`smoke_test.py --affected ui_widgets desktop_layout`（经 `工作流任务/gui_hidden.py` 隐藏桌面运行）→ 定向 36 文件 / 1258 用例，5 个红单元：`test_idea_chat` 13 条、`test_pet_ui` 6 条。红单元均不引用 `set_button_padding`／`fit_sidebar`／`Nav.TButton`（`test_pet_ui` 零引用；`test_idea_chat` 仅一处 `Desktop` 构造且不在红单元），与本轮改动无代码路径关联。其中 `test_pet_ui` 5 条「需要登录账号」红与 project_status R1926 记录的干净 master 既有红一致（R1913 登录闸门遗留）；其余红未能在干净基线复验——沙箱阻止写 Git 公共目录 `D:\repo-meta`（worktree 分支与 index.lock 均 Permission denied）。
- 架构门禁：本轮未触发（改动为 L4 层内，未跨层；未运行）。
- 全量安全回归：本轮未触发，未运行。

## 提交

- 已提交：分支 `codex/wip-R1960`；提交包含上述 4 个文件，最终 commit 以 `git log -1` 为准。

## 备注

- 工作树开轮前已有未提交改动：`程序/project_status.md`、`.claude/settings.local.json`（用户既有改动），本轮未触碰。
- 认领：`round_claim.py next` → R1960，分支 `codex/wip-R1960`（脏树按新契约自动带分支）。
