# R1391：UI 路线图 §三 第 4 项 — 项目进入路径覆盖门禁（DesktopStartupController／desktop_settings_service）

类型：修复轮（§3.2，2026-10-12）。中央轮次：1391。范围＝路线图 v1 §三 第 4 项「项目选择／切换」——承接 R1390 登记缺口「缺『所有项目进入路径必经控制器』的架构覆盖门禁」。**不改生产代码**。

## 三个必答
- 本轮类型：修复轮（§3.2）——只新增架构门禁测试与 `AGENTS.md` §5 清单登记，不改生产代码／阶段／路径／分层。
- 测试：定向 `test_project_entry_boundary` **5/5**；默认冒烟 `smoke_test.py` **8/8**；架构 `smoke_test.py --architecture` **341/341**（336→341）；**命中 §5 五轮规则（1391−1386=5）** → 干净 master 工作树 `o07-fullsafe-master` `--all --safe` **4983 条、546.4 秒、0 文件有红**。
- 欠账：本轮清掉 §三 第 4 项缺口（7/7 收口）；`last_full_safe_all_round` 刷新为 1390。

## 实现（不改生产代码）
新增 `tests/architecture/test_project_entry_boundary.py`（5 条）：

1. `test_project_load_calls_sit_in_frozen_entrypoints`：静态冻结 `desktop.py` 中直接调用 `self.load(...)` 的入口集合——**进入**（首参非 None）＝ `{open_project_or_cleanup, _choose_project_impl, new, import_json, enter}`；**关闭当前项目**（首参 None）＝ `{gone, completed}`。任何新增／改名的项目进入路径都会失败，必须先登记，避免绕过控制器与设置服务。
2. `test_every_entering_path_remembers_daily_choice`：每条进入路径都必须经「当天选择」记忆入口（`remember_daily_project_choice(` 或 `daily_project_choice(`）。
3. `test_first_choice_is_scheduled_by_startup_controller`：`DesktopStartupController` 只装配一次、绑定 `choose_project=self.choose_project`／`before_project_choice=self._after_first_paint`、`.start()` 一次、teardown 经 `controller.cancel()` 收回。
4. `test_daily_choice_memory_delegates_to_settings_service`：`remember_daily_project_choice` 委托 `publish_desktop_preferences`、不得直接 `save(self.settings_file`；`daily_project_choice` 只读 `project_choice_day`／`project_choice_path`；`desktop_settings_service.publish_desktop_settings` 为唯一写入权威。
5. `test_startup_controller_module_stays_tk_free`：`desktop_startup_service.py` 不 import `tkinter`，保持无 Tk 可独立审计。

- 反向验证（mutation）：向 `switch()` 注入一处未登记的 `self.load(path)` → `entering` 多出 `switch`，门禁会失败（已实测）。
- `AGENTS.md` §5 架构门禁清单补 `test_project_entry_boundary.py`。

## §三 第 4 项裁定（收口）
- 权威入口＝`DesktopStartupController`（首帧首次选择时序）＋`desktop_settings_service`（当天选择／桌面设置写入）。
- 覆盖证据：新增 5 条门禁 ＋ 既有 `test_desktop_settings_boundary`（4 个 mutation 方法全委托 service）＋ `test_project_context_boundary`（项目上下文 L0 只由 L3 构造）。
- 裁定：**已收口**（§三 7/7）。

## 测试契约同步（§2.4）
- 无既有断言被改；`维护记录/架构统一基数.json` 无行号平移。

## 验证
- 定向 `tests.architecture.test_project_entry_boundary`：**5/5、OK**。
- 默认冒烟 `smoke_test.py`：**8/8、0 失败**。
- 架构 `smoke_test.py --architecture`：**341/341、0 红**（336→341，138.9 秒）。
- 全量（§5 五轮 1391−1386=5）：干净 master 工作树 `o07-fullsafe-master` `run_selftests.py --all --safe` **4983 条、546.4 秒、0 文件有红**；`test_desktop_startup_perf` 14/14、`test_perf_baseline` 9/9 无抖动。凭据 `{round:1390, tree:a8cfd2f0…, at:2026-10-12T23:44:43}`＝内容提交 `37ed5bc:程序`；`last_full_safe_all_round` 刷新为 1390。

## 提交
- 内容：`37ed5bc`（新门禁测试＋`AGENTS.md` §5 清单）。
- 报告／状态／接力：见后续补记。

## 复盘：路线图 v1 §三
- 7 项全部收口（第 4 项本轮收口）。无新增缺口。
- 未做（说明理由）：§三 之外仍走根目录口径的门禁（coverage ratchet 20/21/22/24/25/26、json_io/table 等）是否同批递归化，需逐段评估子目录候选，另轮处理，不与本轮混改。
