# R546 功能轮结果

日期：2026-09-29  
前置：已读取 `tasks_round/tasks_round_538_result.md`；其首个确认阻塞点为 `skill_registry.py:363` 的 `rglob`，位于自动打开项目的 Tk 主线程调用链。

## 轮次自答

1. 本轮是功能轮还是整理轮？功能轮。
2. 测试跑了吗？三个基线过了吗？默认冒烟 8/8、架构门禁 95/95 通过；全量安全基线本轮未运行。
3. `project_status.md` 的欠账少了吗？减少：自动打开项目的入口、桌面页面构建与宠物启动挂接链现有静态回归守卫，禁止重新直接调用递归目录扫描。

## 改动

- 新增 `tests/architecture/test_startup_budget.py`：以 AST 扫描 `app.py` 入口、`Desktop.__init__/choose_project/load/show/writing` 和 `pet_ui.attach/watch_status/start`；上述启动链禁止直接调用 `rglob`、`glob` 或 `os.walk`。
- `smoke_test.py --architecture` 已按既有 `tests/architecture/test_*.py` 自动发现机制纳入新测试，不需要、也未修改启动代码或门禁调度。
- `AGENTS.md` 更新架构门禁清单为 54 文件 / 95 检查、基线为 95/95，并登记 `test_startup_budget.py`；`architecture.md` 同步当前架构基线。

## 验证

1. `D:\漫剧制作助手\运行环境\Python\python.exe smoke_test.py --architecture`：**95/95 通过**（20.885 秒）。
2. `D:\漫剧制作助手\运行环境\Python\python.exe smoke_test.py`：**8/8 通过**。

## 自审

通过：未修改 `app.py`、`desktop.py`、`pet_ui.py` 或任何启动实现；未修改其他架构测试。当前项目没有稳定、无界面的“可交互”计时钩子，因此未虚构 `<3 秒` 断言；本轮交付的是确定性的静态递归扫描回归守卫。
