# R2254 换页决策一次接收状态快照（J20 结构治理轮·执行）

## 来源
`tasks_round/tasks_round_2178_result.md` 候选 11 的 J20：「`page_navigation_controller` 一次接收状态快照、返回完整换页决策，`desktop_page_nav` 改为一次调用」。

## 基线
分支 `codex/wip-R2254`，自 `codex/wip-R2245`。

## 轮次类型／三套基线／债务
结构治理轮；行为等价（判定顺序、闸门回调的惰性读取、副作用先后均不变）；无新增债务。

## 改动
- `page_navigation_controller.py`：新增 `PagePlan`（route／reason／selector／align／cached／choosing）与 `decide(index, page, snap, *, free_pages, cached_pages)`；顺序＝锁定→免项目页→无项目首页→分镜闸门→来源选择／对齐标记→启动壳／清单／详情／常规建页。
- `desktop_page_nav.py`：`show` 构造一次快照调用 `decide`，只按 `route` 摆控件；原有分散的 `choosing_video`／`needs_adopted_storyboard`／`needs_source_selector` 调用收进 `decide`（函数本身保留）。

## 新增测试
`tests/test_page_navigation_decide.py`：锁定优先、免项目页与首页、闸门惰性读盘、来源选择与对齐标记、四种子路由、缓存仅限常规建页。

## 测试
- 已跑（隐藏桌面）：`run_selftests.py -k page_navigation page_nav desktop_page` 与 `-k navigation slowpage video_nav page_cache desktop_show locked_page startup` 全过；`smoke_test.py --architecture` 412 条，仅两项已知环境红。
- 未运行：`--all --safe`；真机界面。既有测试断言未动。

## 回滚
`git revert` 本轮提交。

## 下一步
J21（候选 10）：`stage_execution_service` 网关字典收成一个基础构造。
