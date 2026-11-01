# R1144：单文件 SKILL 导入前校验与覆盖确认

## §7 三问

1. 类型：修复轮，中央领取 R1144。
2. 验证：指定 skill/ui_edges 回归首次完成 297 条，1 个 UI 断言失败及 skill_notes 超时；修正旧测试的确认弹窗模拟后，失败项定向复验 15/15。受影响冒烟 9/9（含默认 8 项），子门禁零红。未重跑全部已通过用例；未跑整套架构或全量。历史架构 310/310、R1140 全量 4226/4226 不代表本轮实测。
3. 欠账：闭环显式导入静默复制和覆盖问题；其他待办不变。主目录收尾推进至 1145，距最近 R1140 全量四轮，本轮不触发周期升级。

## 修改

- add_skill_from_file 在创建目录或复制前读取 UTF-8 文本并 parse；读失败在状态栏说明并返回。
- 文件名 casefold 后精确等于 skill.md 才是外部包，仅检查 displayName 或 Markdown 标题；其他文件走既有 validate_skill，known 来自当前注册表。
- 声明阶段与当前阶段不同、目标已存在以及字段问题合并成一次 dangerous=True 确认；取消时不复制、不重扫、不重建面板。
- 继续导入仍走原 copy2、扫描及面板刷新流程，无新的注册或删除机制。没有更改既有 Tk 控件销毁重建流程，仅在其前面加校验分支。

## 证据

- 新增 tests/test_skill_import_validation.py 五条用例，修复前共五个失败断言；修复后五条通过。覆盖问题汇总、保留被覆盖文件、确认继续、已知冲突不误报、外部包轻校验、取消不建目录、读取失败不扫描。
- run_selftests.py -k skill ui_edges：首次 297 条／331.5 秒。旧 test_skill_notes 导入无标题文本，新增确认窗未模拟导致等待超时；已补确认模拟并断言提示内容。另有 test_frame_page_batch_row_moved_below_table 可见性断言失败，未修改其测试或产品布局。
- unittest test_skill_notes test_ui_edges.UiEdgeTests.test_frame_page_batch_row_moved_below_table：15/15，2.153 秒，失败和超时项定向复验通过。UI 首次失败仅记录为未复现，不归因于已证明的产品缺陷。
- smoke_test.py --affected idea_chat workflow：9/9，子门禁零红，53 秒。未重复默认冒烟。

## 自审

通过：只改导入前校验，复用注册表校验及确认入口，无越界依赖；不修改实际用户 SKILL 文件或项目数据。原有主目录修改需保留。未做人工导入或完整安全全量，重启应用后加载修复。

收尾：实现 071ca74 已 fast-forward 同步到本地应用主目录，原有 7 个跟踪路径的内容哈希或缺失状态保持一致；暂存凭据形态扫描零命中（有限规则），diff --check 通过。未推送远端。
