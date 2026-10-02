# R538 只读诊断轮：启动卡死实测定位

## 轮次自检

1. 本轮是什么类型？只读诊断轮；按用户要求禁止修改任何 `.py`，只复现并抓取线程栈。
2. 测试跑了吗？没有；用户明确禁止 `smoke_test`，本轮使用真实启动命令与 `faulthandler`，不是自动化冒烟。
3. `project_status.md` 的欠账少了吗？没有；本轮只新增本结果报告，P1 启动卡死仍是未解决阻塞项，等待确认后进入修复轮。

## 复现条件与过程

- 启动入口已核对：`app.py:1404` 调用 `desktop_launcher.launch()`，后者在 `desktop_launcher.py:17` 进入 Tk `mainloop()`。
- 实际执行的是项目内置解释器，并以 `-X faulthandler` 启动；诊断包装器仅在内存中安排 10 秒转储和 35 秒强制退出，未修改任何项目文件或源码。
- 第一次复现：窗口已经出现；t+10 秒触发超时并转储。除 faulthandler 的堆栈外，没有 Python 异常、错误输出或死锁报错。
- 第二次复现：t+10 秒仍在 SKILL 递归目录扫描；t+20 秒推进到同一次 `Desktop.writing()` 的 Tk 字体度量。t+35 秒由诊断看门狗结束，因此事实只能表述为“至少卡住 20 秒”；本轮不能断言它会在 30 秒后恢复，也不能断言永久卡死。
- 启动时刻：本诊断运行器没有输出可审计的壁钟启动时间，只保留了上述相对时刻 t+10/t+20/t+35。用户截图提供的事实是窗口标题已显示“未响应”，与本轮主线程被同步调用占用一致。

## 1. 卡死发生在哪一步

首个阻塞点为 `skill_registry.Registry.files()` 的递归扫描：

- `skill_registry.py:363`：`return sorted(self.root.rglob('*' + SKILL_SUFFIX))`
- Python 标准库 `glob.py:527`：`scandir`

它不是窗口出现前的导入，也不是点击某按钮后触发；调用来自窗口显示后的 Tk 定时回调：

`Desktop.__init__` 在 `desktop.py:363` 注册 150ms 后的 `choose_project` → `desktop.py:2958` 自动 `load(remembered)` → `desktop.py:2834` `show(0)` → `desktop.py:3181` `writing()` → `desktop.py:3352` 创建阶段配置按钮。

创建该按钮会同步求取模型文案：`skill_panel.py:342` → `stage_button_label()` (`skill_panel.py:314`) → `workflow_settings.effective_model()` (`workflow_settings.py:308`) / `current()` (`workflow_settings.py:345`) → `stage_config.get()` (`stage_config.py:202`) → `synchronize()` (`stage_config.py:134`) → `Registry.canonical_id()` (`skill_registry.py:429`) → `_fresh()` (`skill_registry.py:405`) → `fingerprint()` (`skill_registry.py:367`) → `files()` (`skill_registry.py:363`)。

## 2. 卡死时主线程堆栈（原文）

第一次 t+10 秒转储：

```text
Timeout (0:00:10)!
Thread 0x0000533c (most recent call first):
  File "D:\\u6f2b\\u5267\\u5236\\u4f5c\\u52a9\\u624b\\u8fd0行环境\\Python\\Lib\\glob.py", line 527 in scandir
  File "D:\\u6f2b\\u5267\\u5236\\u4f5c\\u52a9\\u624b\\u8fd0行环境\\Python\\Lib\\glob.py", line 477 in select_recursive_step
  File "D:\\u6f2b\\u5267\\u5236\\u4f5c\\u52a9\\u624b\\u8fd0行环境\\Python\\Lib\\glob.py", line 472 in select_recursive
  File "D:\\u6f2b\\u5267\\u5236\\u4f5c\\u52a9\\u624b\\u7a0b序\\skill_registry.py", line 363 in files
  File "D:\\u6f2b\\u5267\\u5236\\u4f5c\\u52a9\\u624b\\u7a0b序\\skill_registry.py", line 367 in fingerprint
  File "D:\\u6f2b\\u5267\\u5236\\u4f5c\\u52a9\\u624b\\u7a0b序\\skill_registry.py", line 405 in _fresh
  File "D:\\u6f2b\\u5267\\u5236\\u4f5c\\u52a9\\u624b\\u7a0b序\\skill_registry.py", line 429 in canonical_id
  File "D:\\u6f2b\\u5267\\u5236\\u4f5c\\u52a9\\u624b\\u7a0b序\\stage_config.py", line 134 in synchronize
  File "D:\\u6f2b\\u5267\\u5236\\u4f5c\\u52a9\\u624b\\u7a0b序\\stage_config.py", line 202 in get
  File "D:\\u6f2b\\u5267\\u5236\\u4f5c\\u52a9\\u624b\\u7a0b序\\workflow_settings.py", line 345 in current
  File "D:\\u6f2b\\u5267\\u5236\\u4f5c\\u52a9\\u624b\\u7a0b序\\workflow_settings.py", line 308 in effective_model
  File "D:\\u6f2b\\u5267\\u5236\\u4f5c\\u52a9\\u624b\\u7a0b序\\skill_panel.py", line 314 in stage_button_label
  File "D:\\u6f2b\\u5267\\u5236\\u4f5c\\u52a9\\u624b\\u7a0b序\\skill_panel.py", line 342 in stage_button
  File "D:\\u6f2b\\u5267\\u5236\\u4f5c\\u52a9\\u624b\\u7a0b序\\desktop.py", line 3352 in writing
  File "D:\\u6f2b\\u5267\\u5236\\u4f5c\\u52a9\\u624b\\u7a0b序\\desktop.py", line 3181 in show
  File "D:\\u6f2b\\u5267\\u5236\\u4f5c\\u52a9\\u624b\\u7a0b序\\desktop.py", line 2834 in load
  File "D:\\u6f2b\\u5267\\u5236\\u4f5c\\u52a9\\u624b\\u7a0b序\\desktop.py", line 2958 in choose_project
  File "D:\\u6f2b\\u5267\\u5236\\u4f5c\\u52a9\\u624b\\u8fd0行环境\\Python\\Lib\\tkinter\\__init__.py", line 876 in callit
  File "D:\\u6f2b\\u5267\\u5236\\u4f5c\\u52a9\\u624b\\u8fd0行环境\\Python\\Lib\\tkinter\\__init__.py", line 2089 in __call__
  File "D:\\u6f2b\\u5267\\u5236\\u4f5c\\u52a9\\u624b\\u8fd0行环境\\Python\\Lib\\tkinter\\__init__.py", line 1613 in mainloop
  File "D:\\u6f2b\\u5267\\u5236\\u4f5c\\u52a9\\u624b\\u7a0b序\\desktop_launcher.py", line 17 in launch
  File "app.py", line 1404 in <module>
```

第二次 t+20 秒主线程已经离开 `glob.scandir`，但仍在同一条同步启动链：

```text
File "...\\Python\\Lib\\tkinter\\font.py", line 176 in metrics
File "...\\responsive_ui.py", line 497 in font_linespace
File "...\\responsive_ui.py", line 516 in row_text_height
File "...\\responsive_ui.py", line 546 in fit_row_height
File "...\\desktop.py", line 3462 in writing
File "...\\desktop.py", line 3181 in show
File "...\\desktop.py", line 2834 in load
File "...\\desktop.py", line 2958 in choose_project
File "...\\tkinter\\__init__.py", line 876 in callit
File "...\\tkinter\\__init__.py", line 1613 in mainloop
```

## 3. 是否多线程死锁

没有观察到多线程互相等待。第一份转储只有主线程，且它在同步文件系统 `scandir`；35 秒观测中唯一附加线程是诊断看门狗 `Thread-1`，其栈停在 `threading.Event.wait`，这是等待到期的正常行为。主线程随后能从扫描推进到字体度量，进一步反证不是互锁死锁。

## 4. 最近四轮与卡死位置的关系

| 轮次 | 变更 | 与本次栈的关系 |
| --- | --- | --- |
| R534 | 轮次类型文字及静态门禁 | 无调用关系。 |
| R535 | 剧本准备固定高度测量取消 `update_idletasks()`，改为空闲批次 | t+20 位于 `writing()` 的字体度量附近，但 t+10 的首个、最长证据是 SKILL 文件扫描；本轮证据不能把 R535 定为根因。 |
| R536 | `show()` 提前返回路径补排空闲布局 | 当前栈进入的是正常 `writing()` 分支，未命中提前返回路径；不是本次首因。 |
| R537 | 剧本准备输入区和阶段配置按钮布局收紧 | 当前链确实在创建该阶段配置按钮时触发同步模型/SKILL 解析；但证据表明耗时来源是既有 `skill_registry` 递归扫描，而不是按钮位置或输入区布局本身。 |

## 5. 根因假设与证据

**高置信根因：** 启动后自动打开当日项目（`desktop.py:2958`）在 Tk 主线程同步构建“剧本准备”页；构建阶段配置按钮时，为展示当前模型调用了会反复递归遍历整个 `skills/` 目录的 `Registry.fingerprint()`。该文件系统扫描发生在事件循环回调内，至少占用主线程 10 秒，Windows 因而标记窗口“未响应”。扫描完成后，同一次同步页面构建仍继续执行 Tk 字体/行高计算，至少持续到 t+20 秒。

**直接证据：** 两次真实启动的 faulthandler 栈均经过 `choose_project → load → show → writing`；首个栈精确停在 `glob.scandir` 和 `skill_registry.py:363`，第二个栈显示相同调用链尚未交还 Tk 事件循环。

**待修复范围（未执行）：** 将启动时的自动项目打开与阶段配置按钮的模型/SKILL 求值从首屏主线程关键路径中移出，并避免一次按钮文案查询触发完整 `skills/` 递归指纹扫描；修复轮还需保留首次打开项目的功能与阶段配置文案正确性。

## 自审

- 未修改 `.py`、未运行 `smoke_test`、未更改测试或状态台账。真实启动会执行既有的 `load()`／`stage_config.synchronize()` 路径；后者在发现旧配置需整理时本身可能写入项目级设置。本轮未对用户项目目录做写入或磁盘差异审计，不能将该既有启动副作用误报为“已验证零写入”。
- 未把“35 秒内被看门狗结束”误报成永久卡死；已明确当前证据只覆盖至少 20 秒的无响应。
