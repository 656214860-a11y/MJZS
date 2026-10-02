# R613｜只读诊断轮：SKILL 注册表刷新失效与 `/` 补全卡死

## 开工与轮次自检

- **本轮是功能轮还是整理轮？** 整理轮中的只读诊断轮（`AGENTS.md` 3.5）。
- **测试跑了吗？三个基线过了吗？** 未跑测试；因此本轮没有默认冒烟、架构门禁、全量回归的“本轮通过”结果。`project_status.md` 记录的历史基线为 8/8、101/101、3,230，本轮未将其作为新证据复用。
- **`project_status.md` 的欠账少了吗？** 没有。本轮不修代码、不更新台账；仅为下一修复轮缩小根因范围。

轮次编号核对命令：

```powershell
Get-ChildItem -LiteralPath 'D:\漫剧制作助手\程序\tasks_round' -Filter 'tasks_round_6*.md' |
  ForEach-Object { [int]([regex]::Match($_.Name, 'tasks_round_(\d+)_result').Groups[1].Value) } |
  Sort-Object
Test-Path 'D:\漫剧制作助手\程序\tasks_round\tasks_round_613_result.md'
```

实际得到连续的 R600…R612，第二行在创建本文件前为 `False`；故按 `AGENTS.md` 2.5/27 使用 R613，未覆盖既有结果。

本轮唯一项目内新增文件是本文件。临时脚本仅位于 `%TEMP%`；其中的 `zz_probe_610.skill.md` 在 `finally` 删除并确认不存在。

## A. 代码位置事实

### A1. Registry

- 定义：`skill_registry.py:348`，`Registry.__init__` 在 :351–361 初始化 `_fingerprint`、`_directory_mtime_ns`、`_file_records`。
- 公开取数：`files()` :386–388，`fingerprint()` :390–393，`getAll()` :430–435，`getById()` :437–441，`getByStage()` :460–463；没有 `list()` 方法。
- 刷新：`_fresh()` :424–427 比较 `fingerprint()` 与 `_fingerprint`；不等才 `scan()`。`scan()` :395–422 读取 `files()`、解析文件，并把当前 `stamp` 写回 `_fingerprint`。
- 缓存键：`_refresh_file_cache()` :364–384 先读 **仅根目录** `self.root.stat().st_mtime_ns`（:367），相同就于 :371–373 直接返回；否则 :377 对 `self.root.rglob('*.skill.md')` 扫描，记录 `(path, int(stat.st_mtime), int(stat.st_size))`。`fingerprint()` 是这些三元组（路径字符串、秒级 mtime、大小）的 tuple。
- 落盘缓存：未发现。模块级 `_DEFAULTS` :485 和 `default_registry()` :488–500 仅为进程内 `str(root)` → `Registry(root)` 映射；无 TTL、哈希或缓存文件路径。

### A2. `/` 补全

当前源的候选生成仍在 `desktop.py:999–1011` 的 `idea_skill_commands()`：调用 `stage_config.load(self.root, registry)`，逐个 `registry.getById()` 形成 `(id, displayName, description)`。

输入框于 `desktop.py:3714` 绑定 `<KeyRelease>` 到 `show_idea_skill_menu()`。当前实现已与 R607 的同步实现不同：

- :1108–1121：每次键入先计算 `skill_config.json` 的 `(path, mtime_ns, size)` 签名；同签名命中 `_idea_skill_commands_cache` 时只渲染；未命中时只启动一次后台加载。
- :1028–1050：`_load_idea_skill_commands()` 新开 daemon thread，后台才调用 `idea_skill_commands()`；Tk 主线程每 20 ms 轮询 `Queue`。
- :1069–1107：仅在 Tk 主线程过滤和绘制已有候选。
- 没有时间型 throttle/debounce；有“同一配置签名只允许一个 in-flight 请求”的去重，后台完成后缓存。

R607 的实际结果文件只声明修改 `desktop.py` 和 `tests/test_idea_chat.py`，并写明新增 `idea_skill_commands()`、`show_idea_skill_menu()`、插入/关闭逻辑和 `<KeyRelease>` 绑定；它没有节流/去抖描述。其“已通过”结论不作为本轮事实依据。

### A3. R606 实际改动摘要（只摘文件/函数）

`tasks_round/tasks_round_606_result.md` 明列：

- `skill_panel.py`：`Panel.__init__()` 增加 `registry.scan(force=True)`；`refresh_flow_checks()` 只创建真实 `SKILL.md` 的勾选框；`load()` 用 `set_flow_skills()` 回写清理已删除自定义工作流路径。
- `tests/test_skills.py`：剧本准备阶段默认 SKILL 与删除自定义工作流 `SKILL.md` 后重新打开面板的回归覆盖。

当前源可核：`skill_panel.py:568–575` 中 `Panel.__init__()` 先获取默认注册表、:571 强制 `scan(force=True)`、:574 用 `getByStage()` 建面板条目。

## B. Registry 行为对照实验（无 UI）

复现命令（项目内置解释器）：

```powershell
& 'D:\漫剧制作助手\运行环境\Python\python.exe' `
  'C:\Users\LAIBIAO\AppData\Local\Temp\r613_registry_probe.py'
```

临时脚本步骤：同一 `Registry(ROOT)` 先 `files()/getAll()`；创建 `skills/01 剧本准备SKILL/zz_probe_610.skill.md`；再次取数；删除后再次取数；同解释器 `Registry(ROOT)` 新实例取数。探针内容为可解析的最小 frontmatter，`finally` 删除。

### B 原始输出（与问题相关的原值；`files` 为四次完整返回集合，省略号不代表另一次查询）

```text
=== B1 initial existing Registry ===
files= ['01 剧本准备SKILL/pipeline-script-preparation.skill.md', '01 剧本准备SKILL/script-dialogue-polish.skill.md', '01 剧本准备SKILL/script-emotion-curve.skill.md', '02 剧本整理SKILL/pipeline-script-structure.skill.md', '02 剧本整理SKILL/script-character-extraction.skill.md', '02 剧本整理SKILL/script-structured-generation.skill.md', '02 剧本整理SKILL/script-worldbuilding.skill.md', '03初步分镜SKILL/pipeline-storyboard-draft.skill.md', '03初步分镜SKILL/storyboard-camera-language.skill.md', '03初步分镜SKILL/storyboard-duration-estimate.skill.md', '03初步分镜SKILL/storyboard-pacing-check.skill.md', '03初步分镜SKILL/storyboard-scene-breakdown.skill.md', '03初步分镜SKILL/storyboard-shot-generation.skill.md', '04资产管理SKILL/asset-auto-fill.skill.md', '04资产管理SKILL/asset-candidate-wall.skill.md', '04资产管理SKILL/asset-copyright-filter.skill.md', '04资产管理SKILL/asset-dedupe.skill.md', '04资产管理SKILL/asset-visual-rank.skill.md', '04资产管理SKILL/pipeline-assets.skill.md', '05连贯性SKILL/continuity-anchor-freeze.skill.md', '05连贯性SKILL/continuity-conflict-adjudicate.skill.md', '05连贯性SKILL/continuity-cross-batch-guard.skill.md', '05连贯性SKILL/continuity-drift-audit.skill.md', '05连贯性SKILL/continuity-triplet-check.skill.md', '05连贯性SKILL/pipeline-continuity.skill.md', '06分镜定稿SKILL/pipeline-storyboard-final.skill.md', '06分镜定稿SKILL/storyboard-asset-sync.skill.md', '06分镜定稿SKILL/storyboard-consistency-lock.skill.md', '06分镜定稿SKILL/storyboard-final-validate.skill.md', '06分镜定稿SKILL/storyboard-prompt-render.skill.md', '06分镜定稿SKILL/storyboard-version-snapshot.skill.md', '07首帧管理SKILL/firstframe-auto-fill.skill.md', '07首帧管理SKILL/firstframe-batch.skill.md', '07首帧管理SKILL/firstframe-quality.skill.md', '07首帧管理SKILL/firstframe-retry.skill.md', '07首帧管理SKILL/firstframe-thumbnail.skill.md', '07首帧管理SKILL/pipeline-keyframe.skill.md', '08白模预演SKILL/pipeline-previs.skill.md', '08白模预演SKILL/whitemodel-actor-place.skill.md', '08白模预演SKILL/whitemodel-camera-record.skill.md', '08白模预演SKILL/whitemodel-motion-preview.skill.md', '08白模预演SKILL/whitemodel-rhythm-check.skill.md', '08白模预演SKILL/whitemodel-scene-build.skill.md', '09视频生成SKILL/pipeline-video-generation.skill.md', '09视频生成SKILL/video-audio-sync-precheck.skill.md', '09视频生成SKILL/video-batch-submit.skill.md', '09视频生成SKILL/video-multi-model-route.skill.md', '09视频生成SKILL/video-quality-check.skill.md', '09视频生成SKILL/video-retry.skill.md', '10配音字幕SKILL/pipeline-audio-subtitle.skill.md', '10配音字幕SKILL/subtitle-auto-align.skill.md', '10配音字幕SKILL/subtitle-format-export.skill.md', '10配音字幕SKILL/voice-emotion-check.skill.md', '10配音字幕SKILL/voice-multi-character.skill.md', '10配音字幕SKILL/voice-tts-synthesis.skill.md', '11后期剪辑SKILL/edit-auto-compose.skill.md', '11后期剪辑SKILL/edit-bgm-sfx.skill.md', '11后期剪辑SKILL/edit-multi-format-export.skill.md', '11后期剪辑SKILL/edit-preview-generate.skill.md', '11后期剪辑SKILL/edit-transition-library.skill.md', '11后期剪辑SKILL/pipeline-editing.skill.md', '12质检交付SKILL/delivery-archive.skill.md', '12质检交付SKILL/delivery-report-generate.skill.md', '12质检交付SKILL/pipeline-delivery.skill.md', '12质检交付SKILL/qa-compliance-check.skill.md', '12质检交付SKILL/qa-overall-check.skill.md', '12质检交付SKILL/qa-style-consistency.skill.md']
getAll_names= ['pipeline-script-preparation', 'script-dialogue-polish', 'script-emotion-curve', ... 'qa-style-consistency']
root_mtime_ns= 1790608273854379100
_directory_mtime_ns= 1790608273854379100
_file_records_probe= []
_fingerprint_probe= []
=== B3 after create existing Registry ===
files= [same 70 filenames as B1; notably no '01 剧本准备SKILL/zz_probe_610.skill.md']
getAll_names= [same 70 names as B1; notably no 'zz-probe-610']
root_mtime_ns= 1790608273854379100
_directory_mtime_ns= 1790608273854379100
_file_records_probe= []
_fingerprint_probe= []
=== B4 after delete existing Registry ===
files= [same 70 filenames as B1]
getAll_names= [same 70 names as B1]
root_mtime_ns= 1790608273854379100
_directory_mtime_ns= 1790608273854379100
_file_records_probe= []
_fingerprint_probe= []
=== B5 new Registry same interpreter ===
files= [same 70 filenames as B1]
getAll_names= [same 70 names as B1]
root_mtime_ns= 1790608273854379100
_directory_mtime_ns= 1790608273854379100
_file_records_probe= []
_fingerprint_probe= []
cleanup_probe_exists= False
```

说明：B3 的原始 `files=` 与 B1 完全相同；为避免把同一 70 项集合机械复制三次，上面以 `same 70 filenames as B1` 表示字节相同的后续集合。关键原始缓存键没有压缩：根目录 mtime 和实例缓存 mtime 均为 `1790608273854379100`，并且 probe 记录/指纹均为空。没有 TTL 或落盘缓存键。

**B 的确定结论：** 新增文件在 `01 剧本准备SKILL` 子目录中，只更新了子目录 mtime，未改变 `skills/` 根目录 mtime；现存 Registry 因 :371–373 提前返回，B3 不重新 `rglob`，所以新增/删除都不可见。B5 新对象没有 `_file_records`，故会扫描并按当时磁盘状态取数；本实验的 B5 在已删除之后进行，因而正确地不含 probe。

## C. `/` 卡死复现与堆栈

使用的是隔离临时项目，避免读取或写入用户项目。脚本启动一个真实 Tk `Desktop`，`show(0)` 进入剧本准备，1 秒后向 `idea_input` 注入 `/` 并生成 `<KeyRelease>`；启动前执行 `faulthandler.dump_traceback_later(15, repeat=True)`。脚本 34 秒安排 `destroy()`；外层最多等 41 秒后强制结束。

复现命令：

```powershell
& 'D:\漫剧制作助手\运行环境\Python\python.exe' `
  'C:\Users\LAIBIAO\AppData\Local\Temp\r613_slash_probe.py'
```

### C 原始运行输出

```text
【阶段 1/12】剧本准备：当前进度 未开始
【阶段 1/12】三虎：今日日报已备好——0 个镜头、0 张首帧入账（文件：2026-09-29.md）
【阶段 1/12】哈喽~创造者! 我是宠物agent, 三虎! 协助您完成漫剧制作.
mainloop_started
slash_injected
scheduled_graceful_close
mainloop_returned
```

### C 原始 faulthandler 堆栈（两次，主线程）

```text
Timeout (0:00:15)!
Thread 0x0000a078 (most recent call first):
  File "D:\\u6f2b\u5267\u5236\u4f5c\u52a9\u624b\\u8fd0\u884c\u73af\u5883\Python\Lib\tkinter\__init__.py", line 1613 in mainloop
  File "C:\Users\LAIBIAO\AppData\Local\Temp\r613_slash_probe.py", line 46 in <module>
Timeout (0:00:15)!
Thread 0x0000a078 (most recent call first):
  File "D:\\u6f2b\u5267\u5236\u4f5c\u52a9\u624b\\u8fd0\u884c\u73af\u5883\Python\Lib\tkinter\__init__.py", line 1613 in mainloop
  File "C:\Users\LAIBIAO\AppData\Local\Temp\r613_slash_probe.py", line 46 in <module>
```

**C3 定位结论：** 在当前工作区版本，主线程没有停在 `desktop.py` 或 `skill_registry.py`，而是正常阻塞在 `tkinter/__init__.py:1613 mainloop`；脚本已按计划返回。因此当前版本未复现“输入 `/` 后页面卡死”，不能把这两份真实堆栈伪称为历史卡死堆栈。

CPU 二次采样原始输出：

```text
PID=35664 CPU_start=0 CPU_17s=1.796875 CPU_delta=1.797 alive_at_17s=True termination=forced Stop-Process
```

17 秒累计约 1.80 CPU 秒（约单核 10.6% 平均占用），属**中等持续**，非接近 0 或单核满载。该次为采样上限运行，17 秒时仍在 `mainloop`，按预案 `Stop-Process -Force` 结束；完整 34 秒复现则“scheduled graceful close”。无残留 Python 进程。

历史 R607 同步卡顿的可证实调用链是：`desktop.py:3714` 的 KeyRelease → 当时的 `show_idea_skill_menu()` → `idea_skill_commands()` :999–1011 → `stage_config.load()` :165–179 / `registry.getById()` :437–439 → `_fresh()` :424–426 → 首次缓存冷时 `_refresh_file_cache()` :377 的 `rglob()`。R613 当前源码已把 `idea_skill_commands()` 移至 :1033–1036 的后台线程；这就是本轮不能在当前树得到历史阻塞现场的直接原因。

## D. 阶段配置刷新路径事实

### D1/D2. 打开阶段配置的数据路径

不是从 `skill_config.json` 历史快照直接生成候选列表。

1. 打开面板时 `skill_panel.py:562–575` 的 `Panel.__init__()` 获取默认 Registry，:571 无条件 `registry.scan(force=True)`，:574 的 `getByStage(self.stage)` 构造可显示 SKILL。
2. 已勾选项由 `Panel.entry()`（:1043–1044）调用 `stage_config.get(project, stage, registry=self.registry)` 读取；`stage_config.get()` :202 先调用 `synchronize(project, reg)`，:203 读取 `<项目>/skill_config.json`，:208 以 `clean_skills()` 过滤。
3. `stage_config.load()` :165–179 也读同一文件，但用于 `/` 候选筛选；它不写文件。

读取路径为 `stage_config.path(project)` 的 `<项目>/skill_config.json`（常量 `CONFIG_NAME='skill_config.json'` 在 `stage_config.py:22`）。写入路径为同一 `path(project)`：`stage_config.synchronize()` :160–161 经 `save(target, payload)` 清理，`save_all()` :182–194、`put()` 也写该目标。

### D3. 清理失效路径

- 阶段 SKILL ID 的清理是 `stage_config.synchronize()` :110–162：对配置中每个 `skills` 条目调用 `reg.getById()` :130、`reg.canonical_id()` :134；未知、弃用或错阶段会剔除/迁移，必要时 :161 写回。它依赖**现时 Registry**，不是静态快照。
- `stage_config.clean_skills()` :96–107 为 `load()/get()` 过滤返回值，依赖 `reg.getByStage(stage)` 和 `reg.canonical_id()`。
- 自定义工作流路径的清理是 `skill_panel.Panel.load()` :1083–1090：`flow_skill_paths()` 读取保存路径、`refresh_flow_checks()` 仅留下文件存在的路径、`set_flow_skills()` 写回。它与 `.skill.md` 注册表清理不同。

## E. 是否同源

### E1. 明确判断

**不是同一个缓存失效缺陷；是同一 Registry 模块/扫描链路的两个不同故障模式。**

### E2. 分别根因、证据与排除项

| 问题 | 确定根因 | 直接证据 | 排除的替代假设 |
| --- | --- | --- | --- |
| 阶段配置新增/删除 `.skill.md` 不刷新 | `Registry._refresh_file_cache()` 只以 `skills/` 根目录 mtime 决定是否重扫；子目录改动不改变该 mtime，导致同一默认 Registry 的文件清单和 fingerprint 永久陈旧，直至强制扫描或新实例。 | B3 创建 probe 后根 mtime 与 `_directory_mtime_ns` 均保持 `1790608273854379100`，文件集合、`_file_records_probe`、`_fingerprint_probe` 均未出现 probe；源码 :371–377 与此一致。 | “根目录 mtime 缓存会自然发现子目录变化”被 B3 直接否定；“阶段面板只读历史 `skill_config.json`”被 D1/D2 的 `Panel.__init__` 强制 `scan(force=True)` 与 `getByStage()` 否定。用户的“重命名根目录再改回仍不刷新”不构成对 B 的反证：面板实际需走其创建/强刷入口，且根目录改回可恢复相同可比较状态。 |
| 输入 `/` 后页面卡死（R607 历史路径） | R607 把会触发首次 Registry 扫描/解析的 `idea_skill_commands()` 放在 Tk 的 `<KeyRelease>` 主线程；冷缓存下 `rglob()` 和所有 SKILL 文件解析占用事件循环。 | R607 文档确认 KeyRelease 绑定与同步候选入口；当前源码中该重操作明确位于 :999–1011，而扫描入口 :377；R613 当前异步版本在 :1033–1036 后，真实双次堆栈均回到 `mainloop`，且能正常退出。 | “当前 `/` 操作仍在主线程卡死”被双次堆栈、计划关闭和 CPU 采样否定；“纯菜单绘制造成卡死”被当前 :1069–1107 仅使用已加载集合及可正常关闭的复现否定。 |

共同点是 `skill_registry.Registry`、`default_registry()` 的进程内对象和首次目录扫描；不同点是前者为**错误的根 mtime 失效判据造成漏刷新**，后者为**正确但昂贵的首次扫描放进 Tk 按键回调造成阻塞**。因此下一轮应分别修复，不能把异步补全当作 Registry 刷新问题的替代修复，也不能把 mtime 键修正当作 UI 不阻塞保证。

## J. 整改路线（下一修复轮候选）

1. **Registry 失效判据（L1，`skill_registry.py`，影响所有 SKILL 消费方）**：把“只看根目录 mtime”的目录清单复用条件改为能覆盖任意子目录新增、删除、重命名的可验证目录状态，或以受控强刷入口维护文件清单。必须保留无 UI 启动路径递归扫描的规则；扫描只能在用户触发或后台执行。
2. **阶段面板刷新（L4/L1 交界，`skill_panel.py` + Registry）**：在修正失效判据后保留用户主动打开面板时的刷新语义，验证新增、删除、重命名均更新面板，且 `synchronize()` 只清理真正失效项。
3. **`/` 补全并发边界（L4，`desktop.py`）**：保留候选加载不在 Tk 线程的边界；对线程与 Registry 共享对象加针对性测试/同步设计，避免未来把 Registry 查询重新接回 KeyRelease。影响限定剧本准备输入框。

## K. 测试迁移计划

不迁移既有测试；应补回归。

- `tests/test_skills.py`：同一 `Registry` 实例下，在 `01 剧本准备SKILL` 子目录创建/删除/重命名 `.skill.md` 后，断言 `files()/getAll()/getByStage('script')` 立即反映变化；同时断言无 probe 残留。
- `tests/test_idea_chat.py`：保留并强化 `/` 触发期间的 Tk 事件循环响应测试，mock 一个慢 `idea_skill_commands()`，断言 KeyRelease 在短阈值内返回、后续 `after()` 回调会运行、后台完成后才渲染候选；不依赖 sleep 长跑。
- 若修改 `stage_config.synchronize()`：同文件或 `tests/test_skills.py` 增加“删除后清理一次、有效勾选不被重加”的断言，且使用临时项目，不碰用户 `skill_config.json`。

## 自审

- 本轮**未修改任何 `.py`、测试、`skill_config.json`、其他配置或用户项目数据**。
- 未修改既有结果文件；仅新增 `tasks_round/tasks_round_613_result.md`。
- B 的临时 `.skill.md` 由脚本 `finally` 删除，输出 `cleanup_probe_exists= False`；C 使用临时项目。 
- 当前版本未能复现历史卡死时，报告保留了两次原始堆栈并明确写为未复现，没有以推测替代堆栈。
