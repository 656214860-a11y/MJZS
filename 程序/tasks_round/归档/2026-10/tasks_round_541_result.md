# R541 只读诊断轮结果

日期：2026-09-29  
范围：仅真实启动观测、内存计时钩子和 `faulthandler`；未修改任何 `.py`、测试或用户项目数据。

## 轮次自答

1. 本轮是功能轮还是整理轮？均不是；本轮为只读诊断轮。
2. 测试跑了吗？三个基线过了吗？未运行测试（用户明确要求只做启动诊断，且禁止改代码）；不适用，沿用 R540 已验证的默认 8/8、架构 94/94、全量安全 3,230 条历史基线。
3. `project_status.md` 的欠账少了吗？没有；确认 R539 的递归扫描卡死已消失，但发现另一个 P1 启动响应性阻塞，已如实登记。

## 实测方法与耗时

使用项目内置解释器 `D:\漫剧制作助手\运行环境\Python\python.exe -X faulthandler` 启动 `app.py`；自动打开当前记住项目。仅在内存中包裹 `Desktop` 方法、记录 Tk `<Map>` 和 `after_idle` 时间，3.5 秒后自动关闭本次诊断实例。

两次独立启动的结果如下：

| 指标 | 第一次（构建期采样） | 第二次（稳定期采样） |
| --- | ---: | ---: |
| 主窗口映射（可见） | 0.478 s | 0.525 s |
| 项目构建开始 | 0.622 s | 未单独采集 |
| 事件循环重新空闲（可交互） | 1.980 s | 1.948 s |

结论：从启动到可交互实测约 **1.95–1.98 秒**，不是此前的 20 秒永久白屏；窗口约 0.5 秒出现。该数字是本机受控启动实测，不等同于用户手工双击时的冷盘、杀毒扫描或系统负载。

## faulthandler 堆栈事实

### 构建期（启动后 1.0 秒）

主线程不在 `skill_registry.rglob`；位于首次导入 `skill_panel`，调用链为 `desktop.Desktop.writing()` → `show()` → `load()`：

```text
File "<frozen importlib._bootstrap_external>", line 954 in get_data
File "D:\漫剧制作助手\程序\skill_panel.py", line 25 in <module>
File "D:\漫剧制作助手\程序\ui_plugin_registry.py", line 24 in module
File "D:\漫剧制作助手\程序\desktop.py", line 3361 in writing
File "D:\漫剧制作助手\程序\desktop.py", line 3190 in show
File "D:\漫剧制作助手\程序\desktop.py", line 2837 in load
File "D:\漫剧制作助手\程序\desktop.py", line 2967 in choose_project
File "...\\tkinter\\__init__.py", line 1613 in mainloop
File "D:\漫剧制作助手\程序\desktop_launcher.py", line 17 in launch
File "app.py", line 1404 in <module>
```

### 稳定期（启动后 2.5 秒）

构建完成后，主线程如预期停在 Tk 事件循环：

```text
File "...\\tkinter\\__init__.py", line 1613 in mainloop
File "D:\漫剧制作助手\程序\desktop_launcher.py", line 17 in launch
File "app.py", line 1404 in <module>
```

未见其他线程；因此本次采样没有多线程互等或死锁证据。

## 超过 1 秒的单点阻塞

仍有，故不能判定“启动卡死已彻底解决”。第一次启动的内存计时为：

| 同步主线程调用 | 耗时 |
| --- | ---: |
| `Desktop.writing()` | 0.609 s |
| `Desktop.show()`（项目页这一次） | **1.206 s** |
| `Desktop.load()` | **1.310 s** |
| `sync_stage_models()` | 0.087 s |
| 资源导入/清理/恢复 | 均不超过 0.004 s |

`show()` 和 `load()` 是包含关系，不应相加；事实是自动打开项目时，主 Tk 线程连续约 **1.31 秒** 不能处理用户输入。其首个已捕获位置是 `desktop.py:3361` 的 `writing()` 内动态导入 `skill_panel.py:25`，不是 `skill_registry.py` 的递归扫描。

## 结论与阻塞登记

- **已解决的根因（R539）**：本轮 1 秒堆栈完全没有 `skill_registry.rglob` / `glob` / `os.scandir`；稳定后进入 `tkinter.mainloop`。此前约 20 秒的 SKILL 递归扫描卡顿没有复现。
- **仍存在的 P1**：启动后自动项目加载将 `Desktop.load()` / `show()` / 剧本准备页面构建同步放在 Tk 主线程，总跨度约 1.31 秒，导致窗口虽已显示但直到约 1.95 秒才可交互。当前证据将首个采样点定位在 `desktop.py:3361` → `skill_panel.py:25` 的模块导入。
- 本轮按要求仅报告，不修复；后续修复应针对项目页构建/`skill_panel` 按需加载或更细粒度的空闲分批，而不是回退或重改 R539 的注册表缓存。
