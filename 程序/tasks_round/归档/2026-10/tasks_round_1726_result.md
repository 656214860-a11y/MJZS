# R1726：结构治理轮——UI 批次 9：宠物层命中区、键盘可达与颜色令牌

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.3 结构治理轮（执行子场景）。来源：`D:\opencode任务\输出\UI设计评审报告.md` §5 批次 9；执行依据：`工作流任务/RUI9_taskbook.md`。只做宠物层可用性与令牌化，不改宠物形状、动画、表情。
2. **测试跑了吗？三个基线过了吗？**
   - 默认冒烟：`python -B smoke_test.py` → 8/8 通过。
   - 架构门禁：只跑任务书点名的 `function_size_ratchet`、`module_size_ratchet`、`skip_hygiene` → 7/7 通过（未跑全套 `--architecture`）。
   - 全量回归：未运行（任务书明确不跑 `--all`／`--all --safe`；全量欠账按源码轮 +1，见第 3 问）。
   - 定向：直接真 Tk 用例 102/102 通过（4 条新增 + 44 条宠物既有 + 54 条云朵）；`run_selftests.py -k ...` 的精确命令多次受跨树 GUI 令牌／长跑限制，未在可用时间内出结论，详见 C。
3. **project_status.md 的欠账少了吗？** 没有减少。本轮改产品源码，按源码轮口径全量欠账 +1（0/8 → 1/8）；按任务书未改 `project_status.md`，由 Claude 验收时统一记账。

## A 现状核对（改前）

- `程序/pet_ui_support.py`：齿轮是 22×22 Canvas，只绑 `<Button-1>`／`<Enter>`／`<Leave>`；没有 `takefocus`，没有 Enter／空格等价操作。
- 同一文件的猫爪排是一整块 52×18 Canvas，视觉爪 16px，只绑 `<Button-1>`／`<Motion>`／`<Leave>`；没有键盘入口，也没有逐爪 32×32 承接区。
- `程序/pet_cloud.py:field_bg()` 读基础 `TEntry` 的 `fieldbackground`，而回复框实际使用 `Tokens.LineInput.TEntry`。
- 颜色散布：`CANVAS_BG='#f3f6fa'`、`CAPTION_INK='#000000'`、`GEAR_COLOR=('#f0a03a','#7a4a0c')`、`GEAR_HOVER=('#ffc061','#a8620f')`；其余为三虎、猫爪、心情、等级等宠物专属插画色。
- 既有 `tests/test_pet_ui.py::CaptionTests.test_the_caption_is_black_ink` 明确断言 `pet_ui.CAPTION_INK == '#000000'`；用户第 21 期也要求三档小字用黑色。

## B 改动

- `程序/pet_ui_support.py`
  - 新增 `PAW_HIT_SIZE = CONTROL_HIT_MIN`、`GEAR_HIT_SIZE = CONTROL_HIT_MIN`（均 32）。
  - `GearButton`：外层 Canvas 改为 32×32，22px 齿轮图形居中绘制；`takefocus=1`；`<Return>`／`<Key-space>` 与点击走同一个 `click()`；焦点环用 `COLORS['focus']` 画在 Canvas 内。
  - `CANVAS_BG` 改 `COLORS['background_primary']`；齿轮齿身／悬停／描边改 `COLORS['primary']`／`primary_hover`／`primary_pressed`；`PATCH_ROOM` 计入 32px 命中区高度。
  - `CAPTION_INK` **保留 `#000000`**：既有断言与用户第 21 期要求都钉死黑色，改成 `text_primary` 会让 `CaptionTests` 变红；按任务书不改既有断言。
- `程序/pet_ui.py`
  - 初始化 `_paw_focus` 与 `paw_hits`，供三只猫爪各自的外层承接区使用。
- `程序/pet_ui_view.py`
  - `_build_paws()` 为每只猫爪创建独立的 32×32 外层 Canvas，中心对准该爪；`takefocus=1`，绑 `<Button-1>`、`<Return>`、`<Key-space>`、`<FocusIn>`／`<FocusOut>`、`<Enter>`／`<Leave>`。
  - 新增 `paw_choose()`、`paw_hover_at()`、`paw_focus_at()`、`paw_blur()`；焦点环画在猫爪画布上，颜色 `COLORS['focus']`。
  - 重建猫爪时先销毁旧承接区，避免重复控件。
  - **修正了一个对齐缺陷**：初版承接区的 `place(x=...)` 少减了整排宽度 `PAW_WIDTH`，导致三只承接区整体右移 52px；用真 Tk 探针量到中心分别为 941/959/977，而视觉爪中心是 890/908/926。修正后中心为 890/908/926，与视觉爪逐只对齐；新测试增加了中心对齐断言。
- `程序/pet_cloud.py`
  - `field_bg()` 优先读 `self.reply` 的实际 style（`Tokens.LineInput.TEntry`）的 `fieldbackground`／`background`。
  - 兼容口径：若回复框 style 仍是 `background_card`，而基础 `TEntry` 被显式改成别的颜色，则仍返回基础色，保证既有 `CloudFitTests` 的行为不变；生产环境两者同色，实际结果不变。
- 新增 `程序/tests/test_ui_batch9_pet_accessibility.py`（4 条真 Tk 用例）：齿轮 32×32／焦点／Enter+空格；三只猫爪精确 32×32、中心对齐、Tab 顺序、焦点；猫爪 Enter+空格；`field_bg()` 读回复框实际样式。
- 截图探针：`工作流任务/probe_ui9/probe_shot.py`（切到交互式 Default 桌面后创建临时项目窗口，GDI 抓屏）与 `annotate_shot.ps1`（只在 PNG 上画标注，不改 UI）。

## C 验证与截图路径

### C-1 直接真 Tk

- `python -B -m unittest -v tests.test_ui_batch9_pet_accessibility`（`PYTHONPATH=程序/tests`）→ **4/4 OK**。
- `tests.test_pet_ui.PawTests + PawHoverTests + CloudFitTests + GeometryTests + CaptionTests` → **44/44 OK**。
- `tests.test_pet_ui.CloudTests + CloudHygieneTests + CloudCloseTests` → **54/54 OK**。
- 合计 **102/102**；没有改任何既有断言、没有加 skip。

### C-2 冒烟与架构

- `python -B smoke_test.py` → **8 项通过、0 失败**。
- `python -B smoke_test.py --affected pet_ui pet_ui_support pet_ui_view pet_cloud` → 8 项检查通过；内嵌定向门禁 `run_selftests.py --serial -k ...` 在“申请跨树 GUI 令牌”处等到 900 秒超时，整体冒烟因此判 1 项失败。超时是并发批次占锁，不是断言失败。
- `tests.architecture.test_function_size_ratchet + test_module_size_ratchet + test_skip_hygiene` → **7/7 OK**。

### C-3 定向长命令

任务书原命令：

```text
python -B run_selftests.py -k test_pet_ui pet_ui_support pet_cloud pet_ui_view test_layers function_size_ratchet module_size_ratchet test_ui_batch9
```

实际尝试：

- 第 1 次：在 `申请跨树 GUI 令牌` 后超过 30 分钟会话上限，被环境终止；日志只有等待行，无测试结论。
- 第 2 次：`smoke_test.py --affected ...` 内嵌同一门禁，等待 900 秒后超时；冒烟整体失败。
- 第 3 次：加 `--serial --gui-wait 0`，拿到锁并运行超过 11 分钟，仍未产出汇总；为避免继续占用并发批次的 GUI 锁，手动停止。**未把这次运行写成通过**。
- 结论：精确长命令在本机多批次并发下未完成；受影响的 102 条用例已用直接 `unittest` 全部跑过。Claude 验收时应在空闲环境复跑原命令或接受直接用例证据。

### C-4 截图（真 Tk，不是几何示意）

- `工作流任务/probe_ui9/pet_hit_zones.png`：真实 Tk 窗口截图。红框 G＝齿轮 32×32 命中区，红框 1/2/3＝三只猫爪各 32×32 命中区（相邻目标按 18px 间距重叠，标注里已注明），绿框＝16px 视觉爪，蓝框＝宠物头像，黄框＝档位小字。
- `工作流任务/probe_ui9/cloud_reply_hit_zone.png`：真实 Tk 窗口截图。红框＝回复框（reply entry），橙框＝回复行，蓝框＝云朵。
- 原始证据：`raw_pet.bmp`、`raw_cloud.bmp`、`window_pet.json`、`window_cloud.json`。
- 探针只用 `tempfile` 临时项目，截图后销毁窗口；没有打开或读取真实用户项目；没有在 UI 上涂临时高亮，标注只画在导出的 PNG 上。

## D 断言未动与需裁决事项

- **断言未动**：未修改 `程序/tests/test_pet_ui.py`；未修改任何既有断言；未加 `skipTest`；未改共享令牌文件 `ui_tokens.py`、`ui_widgets.py`、`ui_theme.py`。
- **`CAPTION_INK` 保留黑色**：既有 `CaptionTests.test_the_caption_is_black_ink` 断言 `'#000000'`，且用户第 21 期明确要黑色。若 Claude 要把它也令牌化，建议新增 `TEXT_BLACK = '#000000'`（用途：宠物档位小字／暂停小字；用在 `pet_ui_support.py` 的 `CAPTION_INK`，由 `pet_ui.py` 导入），并有意更新该断言；本轮未做。
- **保留的宠物专属 hex（39 处）**：
  - `pet_ui_support.py:17-22`：`SANHU_FUR '#ff8a3d'`、`SANHU_EAR '#ff9292'`、`SANHU_MUZZLE '#fff2d9'`、`SANHU_INK '#1a1c2a'`、`SANHU_STAR '#22d3ee'`、`SANHU_BLUSH '#ff8d9b'`（三虎皮毛／耳窝／口鼻／描边／星光／腮红）。
  - `pet_ui_support.py:57-58`：`PAW_IDLE ('#e7edf5','#a9b6c7')`、`PAW_HOVER ('#f4f9ff','#6f8bab')`（猫爪未选中／悬停）。
  - `pet_ui_support.py:98-100`：`ICE '#eef5fc'`、`INK_SOFT '#3c526d'`、`TONGUE '#c98ba4'`（冰白／浅墨／舌头）。
  - `pet_ui_support.py:101-104`：`MOODS` 四档心情（idle `#7fb0dd/#101c2b/#0a1521`、busy `#d9a63c/#2a1e05/#1b1200`、worry `#d4645c/#2d0d0a/#1c0603`、paused `#c2c8d2/#3a4048/#20242a`）。
  - `pet_ui_support.py:109-111`：`LEVEL_COLORS` 三档等级（hint `#6fb3e0/#123a5e/#08182a`、semi `#e0b13c/#6b4a10/#241703`、auto `#dd5f57/#7c231e/#2a0806`）。
  - `pet_ui_support.py:416-418`：暂停时的 `muzzle '#e3e6eb'`、`ear '#c7cbd2'`、`blush '#c0a8ac'`。
  - `pet_ui_support.py:458`：眼睛高光 `#cfe7ff`。
  - `pet_ui.py:74`：`BLUSH '#8fb6d8'`（撒娇腮红）。
  - 另有注释引用 `#101c2b`、`#243247`，不是实际颜色声明。
- **齿轮颜色**：由琥珀 `#f0a03a/#ffc061` 改为主题蓝 `primary/primary_hover/primary_pressed`。齿轮是控制入口、不是宠物形状，按任务书“通用 hex 换令牌”处理；真实截图里已是蓝色。若产品要保留琥珀个性，需要新增齿轮专用令牌或保留原 hex，请 Claude 目视裁决。
- **32×32 命中区重叠**：视觉爪 16px、间距 2px，32×32 目标中心相距 18px，因此相邻目标重叠 14px。这是“视觉不变 + 每只 32×32”下的必然结果；点击视觉爪仍由上层 52×18 猫爪画布按 x 分派，键盘焦点按目标独立。若要求命中区不重叠，需要把整排从 52px 加宽到至少 94px（或缩小目标），会改变布局，未擅自做。
- **`field_bg()` 兼容分支**：回复框 style 为 `background_card` 且基础 `TEntry` 被显式改成别的颜色时，仍返回基础色；这是为了既有 `CloudFitTests` 不变。若要求“永远只读回复框 style”，删掉该分支即可，但需要 Claude 确认是否接受既有用例的契约变化。
- **长命令未出结论**：见 C-3；不是断言红，不能在验收时写成“定向全绿”。Claude 需复跑原命令或明确接受 102 条直接用例作为本批证据。

## E 提交

**未提交，由 Claude 验收后提交。** 本轮没有执行任何 git 写命令（add／commit／stash／checkout／reset／clean／restore 均未执行），没有改 `project_status.md`、`AGENTS.md`、`architecture.md`、`skills/`，也没有碰其他批次的文件。

改动文件：

- `程序/pet_ui.py`
- `程序/pet_ui_support.py`
- `程序/pet_ui_view.py`
- `程序/pet_cloud.py`
- `程序/tests/test_ui_batch9_pet_accessibility.py`（新增）
- `程序/tasks_round/tasks_round_pending_UI9_result.md`（本文件）
- `工作流任务/probe_ui9/`（截图探针、原始截图与标注图）

## G RUI9b（猫爪点击区重叠）

### 改前红（先写测试，未改实现）

命令：`python -B -m unittest -v tests.test_ui_batch9_pet_accessibility.PetAccessibilityBatch9Tests.test_clicks_across_the_paw_hit_union_pick_the_nearest_visual_centre`

输出关键行：

```text
FAIL: test_clicks_across_the_paw_hit_union_pick_the_nearest_visual_centre
AssertionError: 1 not found in {0} : 点 (524.0, 318) 落在 1 爪上，最近的却是 [0]
Ran 1 test in 0.592s
FAILED (failures=1)
```

原因：三只 32×32 承接区互相重叠，点击由最上层承接区按固定索引接走；在 0/1 重叠区里靠近 0 爪的位置会触发 1 爪。

### 改动

- `程序/pet_ui_view.py`
  - 新增 `paw_choose_event()`：点击时按 `event.x_root` 与三只视觉爪中心比较，选最近的一只；坐标不可用时才退回被点控件自己的档位。
  - 新增 `paw_nearest_at_root()`，统一从猫爪画布根坐标计算三只爪中心。
  - `paw_at()` 由「按 18px 网格取整」改为「取最近视觉中心」，仍拒绝整排范围外的点；猫爪画布上的点击同样走最近中心。
  - `_build_paws()` 的 `<Button-1>` 改绑 `paw_choose_event()`；键盘 `<Return>`／`<Key-space>`、Tab 顺序、焦点环绑定未改。
- 视觉布局未动：爪 16px、间距 2px、承接区 32×32、位置与重叠宽度保持原样。
- `程序/tests/test_ui_batch9_pet_accessibility.py`
  - 新增 1 条真 Tk 用例：在三只承接区并集取 21 个点（含两个重叠区中点及其两侧、两端外扩 15px、三条纵向高度），通过 `winfo_containing()` ＋真实 `<Button-1>` 事件验证每次触发最近爪；中点是等距，允许左右任一。

### 实际计数

- 新用例先红后绿：改前 1 失败；改后 `PetAccessibilityBatch9Tests` 5/5 OK。
- 既有宠物层定向：`PawTests + PawHoverTests + GeometryTests + CaptionTests + CloudFitTests` 44/44 OK。
- 任务书定向集合（串行）：`test_ui_batch9`、`test_pet_ui`、`pet_cloud`、`function_size_ratchet`、`module_size_ratchet` 共 **635 条，0 个文件有红**；`test_ui_batch9_pet_accessibility` 5 条 / 10.5 秒。
- 冒烟：`smoke_test.py --affected pet_ui pet_ui_view pet_ui_support pet_cloud` → **9 项通过、0 项失败**；定向门禁 277 秒、0 红。
- 精确并行 `run_selftests.py -k ...` **未运行完**：本沙箱在 `D:\repo-meta\漫剧制作助手.git` 新建锁／台账文件会阻塞，并行 GUI worker 在 43 秒被外部终止且无汇总。上述 635 条为同一命令加 `--serial` 的完整汇总；父／子进程仅把 `GIT_DIR` 指向临时裸库以避开该写阻塞。按任务书要求，不把精确并行命令写成「通过」。

### 截图

- 已重跑真 Tk 探针并重新标注：`工作流任务/probe_ui9/pet_hit_zones.png`（红框 G/1/2/3 为 32×32 承接区，相邻承接区重叠；绿框为 16px 视觉爪）。视觉布局与改前相同，仅实现改为重叠区按最近视觉中心分派。

## 独立验收（Claude，主工作区四批同树）

- 四批同树合测：`run_selftests.py -k`（smoke --affected 选出的 97 个文件）共 2364 条，3 个文件红：`test_idea_inline_brief`（SP 改契约，mock 缺 `lock_fields`）、`test_ui_batch9`（`winfo_containing` 被桌面上 Chrome 窗口挡住）——均已修复复跑 0 红；`test_writing_api` 1 条在干净 HEAD 绿、主树红，因读取本机真实模型配置，与本批无关。
- `smoke_test.py` 默认 8/8；`--architecture` 368 条 4 红：模块体积（skill_panel 1503>1500，已压回 1500）、skip 台账漏登 UI6、TODO 快照行号 1019→1087（UI3 平移）——已修复，单跑 9/9；全量欠账为后台自动补跑项，不阻断。
- Claude 修测试：`winfo_containing` 在 run_selftests 下取到桌面 Chrome 窗口返回 None；改为本窗口内按叠放次序命中，最近爪断言未动。
