# R687 修复轮结果｜启动首帧全栈终裁

## 开头三问

1. **本轮是什么？** 修复轮：处理自动续开项目时首帧被 Tk 回调嵌套重入、同步模型配置和三虎布局量测共同放大的启动卡顿。
2. **验证与三个基线数？** 默认冒烟 **8/8** 通过；受影响门禁命中 **10 个测试文件**且命令退出码为 0；`gui-short --safe --all` 执行 **39 个测试文件 / 153 个工作单元**。新增首帧专项 `test_desktop_startup_perf.py` 为 **1/1** 通过。性能验收未关闭：最终同机全栈探针有一次 `init+paint=3.614s`，高于 3.0s 线，故本轮标记 `[TASK_FAILED]`，不得将其写作验收完成。
3. **欠账增减？** 新增 1 项：项目自动续开下的首帧耗时仍须稳定压到 3.0s 内；其余启动根因已消除或隔离，未清理用户数据。

## 验证档位声明

本轮改动涉及 2 个生产模块（`desktop.py`、`pet_cloud.py`）及 2 个测试模块，按用户明确指定执行默认冒烟、受影响门禁和 `gui-short` 全量安全自检；未改启动入口、用户数据格式、L0 契约、路径或删除逻辑。性能目标以同机一次性全栈树探针作为额外验收门槛。

## 第一部分：先测终裁

前两轮归因（三虎/注册表/desktop 今日改动）均被 A/B 否定，本轮为全栈树终裁后修复。

一次性探针包装 `tkinter.Misc.after` 的全部登记回调，以嵌套层级累计总耗时，并列出回调自耗时 Top 10；同一脚本随后以空临时项目目录再测。探针已按要求删除；原始运行记录保留在：

- `维护记录/r687_startup_probe_before.log`
- `维护记录/r687_startup_probe_method_detail.log`
- `维护记录/r687_startup_probe_after_acceptance.log`
- `维护记录/r687_startup_probe_final.log`

### 改前原始输出片段

```text
[probe] program-root Desktop.__init__ 0.435s
[probe] program-root update_idletasks 0.040s
[probe] program-root init+paint 10.713s
[probe]   9.773s self | 9.856s total | 1 calls | 9773.2ms max | desktop.Desktop.choose_project
[probe]   0.105s self | 9.961s total | 37 calls | 55.7ms max | DesktopAutomationScheduler...<lambda>
[probe] empty-project init+paint 0.453s
```

细化方法计时定位为 `Desktop.load()` 内同步 `skill_panel.sync_models()`：已选项目需约 7.630s；注册表全树冷解析仅约 46ms。故非注册表扫描根因。叶子样本还显示 `pet_cloud._render` 的 `canvas.update_idletasks()` 23 次累计约 10.01s（均值约 430ms），属嵌套 spin 放大器。

### 修后原始输出片段

```text
[probe] program-root Desktop.__init__ 0.455s
[probe] program-root update_idletasks 0.070s
[probe] program-root init+paint 3.614s
[probe] update_idletasks top10 (program-root)
[probe]   0.045s total | 1 calls | 44.9ms max | _startup_probe_tmp.py:132
[probe]   0.018s total | 1 calls | 18.0ms max | ui_theme.py:307
[probe] empty-project init+paint 0.393s
[probe]   0.026s total | 1 calls | 26.4ms max | _startup_probe_tmp.py:132
```

单次 `update_idletasks` 已低于 300ms（最大 44.9ms），但 `init+paint` 的 3.614s 仍未满足 ≤3.0s 的硬门槛。因此不以较快的空项目 0.393s 代替真实项目验收。

## 修复改动

- `pet_cloud.py`
  - 启动期或主窗口未映射时，不再在 `_render()` / `_fit_font()` 内同步 `update_idletasks()`。
  - 字体几何量测合并为一个 `after_idle` 延迟任务；按剩余启动窗口安排一次重试，不形成 50ms 嵌套 spin。
  - 窗口关闭时取消延迟渲染，避免已销毁 Tk 命令回调；映射完成后的字号自适应路径保持同步量测语义。
- `desktop.py`
  - 首帧控制器完成前暂停既有 automation scheduler 的 `tick`；项目页完成一次构建后，复用既有 `start('tick', ...)` 恢复，不增加新心跳。
  - 自动续开项目先显示已映射壳页，项目页建造随后执行；模型同步由带代次校验的后台线程执行，结果经既有 tick 回填，过期项目结果不应用。
  - 不在后台访问 Tk；`import_generated_assets`、资产清理及恢复链路不变。
- `tests/test_desktop_startup_perf.py`
  - 新增空临时项目构建 Desktop 到首帧 ≤4.5s 的 `gui-short` 回归。
- `tests/test_core.py`
  - 既有直接构造 `Desktop` 的加载测试显式 stub 新增的模型同步排程，保持其只测原有加载责任。

## 回归与验证原始输出片段

```text
python smoke_test.py
... 8/8 passed

python smoke_test.py --affected pet_cloud desktop desktop_automation_service responsive_ui
... 10 matching test files; exit code 0

python -m unittest discover -s tests -p test_desktop_startup_perf.py -v
test_empty_project_first_paint_is_bounded ... ok
Ran 1 test in 0.681s
OK

python run_selftests.py --layer gui-short --safe --all
... gui-short: 39 test files / 153 work units; safe serial run completed
```

此前一次 `gui-short` 尝试发生在延迟三虎渲染尚未取消销毁回调之前，产生的中断临时日志已删除，避免将修前失败输出误作本轮最终证据。

## 用户数据与边界确认

- 未修改用户项目、`skill_config.json`、工作流设置、密钥或任何用户配置。
- 一次性探针 `logs/_startup_probe_tmp.py` 已删除；只保留维护记录中的原始输出。
- 未改注册表扫描、三虎样式/尺寸/动画，未重构其他启动路径。

## J 后续

1. 需另立 R688，仅针对自动续开项目的首帧稳定性继续切片；本轮真实项目仍有一次 3.614s，不能验收关闭。
2. 全栈树中项目页 `Desktop.writing()` 构造约 1.8–3.9s，现已与最早壳页隔离；若继续影响用户可用时间，应在独立轮次拆分页面建造，不能夹带进本轮。

## 自审

仅改三虎启动量测、桌面首帧 tick/模型同步调度及对应测试；未借机处理注册表、其他弹窗、项目数据或配置。因真实性能硬门槛未稳定通过，本轮结论为 `[TASK_FAILED]`。
