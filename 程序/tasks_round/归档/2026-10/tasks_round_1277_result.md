# R1277 修复轮：新增 Claude Code 即时进入厂商下拉

- 类型：AGENTS §3.2 修复轮，中央入口领取 1277；无对应队列 ID。
- 测试：定向 171/171，模型管理窗口 18/18，默认冒烟 8/8；无失败或跳过。完整架构、全量未运行；本轮无全量升级改动，隔离分支不累计周期欠账。R1264 历史全量不覆盖本轮，master 周期验收仍由 R1275 接续，不冒称清零。
- 欠账：本轮复现已修复；主目录代码同步，正式 master 集成及周期验收仍待接续。

## 根因与最小修改

实际新增 ID 为 `claude code`。保存链路已经调用 refresh_all，但 desktop_engine 仅认三个内置 ID，因此新记录被分到 desktop 厂商；选择后也不能识别为 Claude CLI。
仅改 model_pool.desktop_engine：精确接受 Claude Code / Claude Code Cli 的空格、连字符、下划线和大小写写法，统一返回既有 claude 引擎。厂商分组和既有刷新链路自然归入 Anthropic；不增加另一套刷新、不改模型 ID 或用户配置。Claude Desktop 与 Claude API 名称保持原路由。

## 验证

新增测试先运行：2 项，6 个失败（5 个名称子例归到 desktop；已打开的 Anthropic 模型框缺新增条目）。补丁后 2/2。
- `python -B run_selftests.py -k model_pool workflow`：171 条，2.0 秒，ALL TESTS PASSED。
- `test_pet_ui.ModelPoolTests`：18/18；最终复验 2.587 秒。新增测试走真实 save_pool → refresh_all → 已打开 Panel，检查当前选择保留、新条目立即出现及引擎。安装探测替身仅隔离本机 CLI 是否安装，不放宽断言。
- `python -B smoke_test.py`：8 项通过、0 失败。
- `git diff --check`：通过。未实发 API、未启动 CLI、未重启应用。

自审：生产修改仅根因模块，未引入依赖或结构变化；API 与 Desktop 反例覆盖。原有断言未修改。
提交：本报告随 R1277 提交，提交号以 Git 的 R1277 记录为准。上一轮 R1276 检查点现已提交 01171ad；其 master 集成尚待周期验收。
