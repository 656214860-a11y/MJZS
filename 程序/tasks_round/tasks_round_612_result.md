# R612｜修复轮｜剧本准备 SKILL 斜杠补全卡顿

## A. 根因与复现

在剧本准备输入框键入 `/` 后，`desktop.py` 的 `<KeyRelease>` 回调直接调用 `idea_skill_commands()`；该调用同步读取阶段配置并查询 SKILL 注册表。注册表首次查询可能递归扫描 SKILL 目录，运行在 Tk 主线程时会阻塞页面，表现为补全菜单弹出时卡死。

## B. 修复

- 将候选 SKILL 的加载移入独立后台线程；Tk 主线程只读取当前输入前缀、轮询结果并绘制菜单。
- 使用项目阶段配置的 mtime/大小签名缓存候选；配置未变时，继续输入只做内存过滤，不重复加载。
- 后台读取期间若配置发生变化，丢弃过期结果；关闭或重新输入不匹配的 `/` 前缀时不展示旧菜单。
- 未修改候选过滤规则、指令插入文本、发送链路、SKILL 配置或用户项目数据。

## C. 测试

- 新增回归：人为延迟 SKILL 查询时，调用补全菜单仍在 100ms 内返回，随后异步显示候选。
- `python -m unittest tests.test_idea_chat.SkillCommandCompletionTests tests.test_idea_chat.ComposerLayoutTests`：4/4 通过。
- `python smoke_test.py --affected desktop`：9/9 通过（定向 7 条用例、0 个文件有红）；仅既有受限环境的增量台账临时文件权限提示，不影响结果。
- `python smoke_test.py`：8/8 通过。

## D. 自审

通过。仅修改补全的 UI 事件调度与对应回归；未引入反向依赖，未改变用户可见产物或阶段配置写入。
