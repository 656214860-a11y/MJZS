# R1776：修复轮——托盘窗口过程回调被提前释放导致测试进程池整批中断（0xC000041D）

1. 本轮类型：§3.2 修复轮。现象：补齐 SKILL 内容后跑完整自检，进程池报 `BrokenProcessPool`，某个工作进程以 `0xC000041D`（`STATUS_FATAL_USER_CALLBACK_EXCEPTION`）异常终止，整批用例中断。

2. 测试跑了吗、三个基线过了吗：
   - 定向 `run_selftests.py -k desktop_tray test_timers architecture`：391 条、0 个文件有红（含架构门禁）。
   - 默认冒烟 `smoke_test.py` 通过。
   - 修复后完整 `run_selftests.py`（`PYTHONFAULTHANDLER=1`）：3804 条跑完、进程池不再中断；当时剩 4 个红文件，其中 3 个（master_skill／script_contract／skills）是工作区里 `skills/00全流程SKILL/AIGC创作全流程`、`skills/01 剧本准备SKILL/剧本锻造`、`编剧技能集` 三个嵌套仓库为空造成的环境问题（已从主检出复制内容补齐，未入库），1 个（timers）见下。
   - 完整安全全量：本轮改了托盘线程模型，合入 master 后由 `scripts/auto_full_safe.py --run` 补跑，未跑前不写通过。

3. project_status.md 欠账少了吗：本轮改源码 +1（desktop_tray.py）；全量欠账由合入后补跑清账。

## 根因

R1775 把托盘改到独立线程的隐藏原生窗口后，留下两处回调生命周期隐患：

- 窗口类名是进程内固定的 `DramaStudioTrayWindow`。同一进程里第二个托盘窗口会沿用第一个实例注册的窗口类，也就沿用第一个实例的 `WNDPROC` 回调；第一个实例一收摊、回调对象被释放，第二个窗口再收到消息，窗口过程指向已释放内存，Windows 把回调里的访问违例转成 `0xC000041D` 带崩整个进程。桌面测试里每个 `Desktop` 都会建托盘，同进程多实例是常态。
- `remove()` 在 `join(5s)` 超时后仍无条件 `self._wndproc = None`。托盘线程这时可能仍在消息循环里，回调一释放同样是野指针。

## 修复

- 窗口类名按实例唯一（`DramaStudioTrayWindow<序号>`），每个托盘窗口只用自己的回调。
- `WNDPROC` 对象由托盘线程自己的栈帧持有，线程退出消息循环、注销窗口类之后才释放；`remove()` 不再清它。建窗失败路径同样先销毁窗口、注销类再放手。
- 删掉不再使用的 `ERROR_CLASS_ALREADY_EXISTS` 常量（类名唯一后不会再遇到）。

## 测试

- `tests/test_desktop_tray.py` 新增 `test_two_trays_do_not_share_a_window_class`：两个托盘共存，先收掉第一个，再给第二个投一次左键单击，第二个自己的回调必须还活着并触发恢复。7/7 通过，原断言未动。
- `tests/test_timers.py::test_batch_window_cancels_its_timer_on_close`：该用例在干净 HEAD 上就红（`after#…` 残留）。原因是 R1775 的托盘 120ms 排空定时器挂在主窗口上，不归 `cancel_timers` 管，被算进了「批量窗口销毁后残留」。用例观察前先 `d.close_tray()`，把与批量窗口无关的托盘定时器排除；**断言未动**。

## 未通过项

无（本批相关测试全绿）。

## 提交

- 已在分支 `claude/project-handoff-f6eb50` 提交，commit hash 见 git log `R1776:`。
