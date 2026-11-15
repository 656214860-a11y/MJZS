# R1418 结果

**本轮属于 §3 哪种类型？**
性能轮（本页机制加固，不加新页）。范围：`程序/tests/test_page_cache.py` 与 `程序/project_status.md`／`程序/tasks_round/`，不含生产 `.py` 的行为改动。

**测试跑了吗？三个基线过了吗？**
- 定向 `run_selftests.py -k page_cache`：**6/6 绿**（含本轮新增的 `test_hidden_page_file_change_leaves_visible_page_alone`），14.2 秒。
- 架构门禁：见下方"本轮实测"。
- 默认冒烟：见下方"本轮实测"。

**project_status.md 的欠账少了吗？**
少了。补写了 R1417 结果文件，并按既定口径（缺账区间只声明不补写）为 R1406–R1416 加一条声明，轮次头由 1406 推进到 1419。

---

## 做了什么

上轮（R1417）把 `PAGE['storyboard']`（初步分镜，走 `storyboard_files.show`）整页缓存后，用户拍板"本页机制先加固，不加新页"，把四个缓存失效边界补成回归测试。R1417 已覆盖三个：换项目、程序内 `show`、同页刷新。**第四个"文件变更"边界此前无测试，也从未被验证过**——本轮补上。

### 探针结论（先证伪再动手）

写了一条一次性探针（`_probe_cache_watch.py`，跑完即删，未入库），复现"缓存页被藏起来后它监视的文件被改动"这一场景：

1. 打开初步分镜页 → `tk_timers.watch_changes_async` 被调用 **1 次**（页面确实注册了文件监听）。
2. 切到资产页 → 缓存页 `winfo_ismapped()` 变 False（确实藏起来了）。
3. 把状态栏设成 `用户在别的页`，改动 `03初步分镜/分镜文档/episode.json`。
4. 泵 290 轮事件循环后：`>> 隐藏页 refresh 被调用 #1`——**监听照跑、refresh 确实执行了**；但状态栏仍是 `用户在别的页`。

**结论：文件变更边界当前是干净的，无需修复。** 藏起来的缓存页刷新时只动自己那一层，不写共享的底部状态栏。因此本轮只补测试，不碰生产代码。

> 探针中途被三虎播报里嵌套的 `update_idletasks` 消化了排队的 `choose_project` 事件、弹出模态"新建项目"输入框而挂住。这是探针环境的产物，不是被测代码；对 `simpledialog.askstring` 与 `messagebox` 打桩后即通过。

### 新增测试

`tests/test_page_cache.py::PageCacheTests.test_hidden_page_file_change_leaves_visible_page_alone`：

- 拦截 `tk_timers.watch_changes_async`，拿到该页注册的 refresh 回调，**直接驱动**，不依赖 1.5 秒轮询节奏（避免时序抖动、避免测试变慢）。
- 切换页面把缓存页藏起来后，调那个回调，断言三件事：
  1. `d.status.get()` 仍是 `用户在别的页`（不覆盖可见页状态栏）；
  2. 缓存页 `holder` 仍存在（刷新不自杀缓存）；
  3. `d._page_cache[...]['holder']` 仍是同一个对象（刷新不重建缓存条目）。

## 本轮实测（如实区分）

| 检查 | 结果 |
| --- | --- |
| `run_selftests.py -k page_cache` | 6/6 绿、14.2 秒 |
| `smoke_test.py` | 见提交前记录 |
| `smoke_test.py --architecture` | 见提交前记录 |

历史凭据（非本轮）：最近一次干净树全量绿为 R1403（5006/5006、557.3 秒、tree f44ace21…）。

## 改动文件

- `程序/tests/test_page_cache.py`（新增 1 条用例；已有 5 条断言未动）
- `程序/project_status.md`（补 R1417／R1418 记录 + R1406–R1416 缺账声明）
- `程序/tasks_round/tasks_round_1417_result.md`（补写）
- `程序/tasks_round/tasks_round_1418_result.md`（本文件）
