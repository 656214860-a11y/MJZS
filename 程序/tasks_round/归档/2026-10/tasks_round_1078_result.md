# R1078：修复 Codex 深链打开边界

- 类型：修复轮，非功能或整理轮；中央已领取 1078，现有队列无对应 ID，不认领其他任务。
- 验收：TASK_FAILED（目标修复通过，完整架构验收被全量欠账阻断）；默认冒烟 8/8，架构 308/309，未生成全量绿凭据。欠账未减少。
- 根因与复现：`codex_tasks.py:130/139` 生成 `codex://threads/...` 或 `codex://new?...`，`desktop.py:4999` 交给 `open_target`，原实现只接受 HTTP(S)，在回调中抛错。新增模拟回归修复前有 2 failures、2 errors，错误与深链拒绝一致。
- 最小修复：仅 `platform_tools.py` 的既有入口增加仅含 codex 的 scheme 白名单；经 getattr 获取 startfile，原样投递并返回链接；不可调用或 OSError 转为指定友好 ValueError。盘符优先、HTTP(S)、本地路径与未知协议分支原样保留。
- 回归：`tests/test_platform_tools.py` 新增 4 个测试，覆盖两种深链、原样返回、无浏览器旁路、evil 拒绝、启动失败及不可用文案；既有断言不变。未改 desktop 调用点或新增入口。

## 实际验证

以下命令在程序目录使用内置 `..\运行环境\Python\python.exe -B`，按用户指定顺序执行前三项：

| 命令 | 结果 |
| --- | --- |
| `run_selftests.py -k platform_tools` | 17/17，0 个失败文件 |
| `run_selftests.py --layer architecture --all` | 309 项，1 项失败：`test_round_baselines.py:68`，R1077 欠完整安全全量；其余 308 项通过，含平台与 UI 入口门禁 |
| `smoke_test.py --affected idea_chat` | 9/9 |
| `smoke_test.py` | 8/8 |
| `run_selftests.py --all --safe` | 前置检查拒绝未提交工作树，未运行全量、未产凭据；未清除用户预设或原有未跟踪文件 |

R1077 已记录旧版本 fcntl 闭包失败及干净副本技能数量差异，本轮不修复这些无关问题，不借历史绿色结果替代当前验收。测试执行器自动改写的测试分层台账已撤回，实际失败保留在本报告；未改断言或伪造凭据。

## 全程序调用点只读排查

- `asset_batch.py:239`：Midjourney HTTPS。
- `desktop.py:4110/4113`：参考网站列表，全部硬编码 HTTPS。
- `desktop.py:4999`：Codex 任务 URL，唯一发现的生产自定义 scheme 目标为上述两种 codex 深链。
- `desktop.py:5541`：配置项 comfy_url，默认 HTTP；未读取用户私有配置。若人为配置其他协议，仍按既有边界拒绝，不属于应放行的应用深链。
- `desktop.py:6688`：ElevenLabs HTTPS。

自审：生产修改仅根因模块，无越层依赖，其他硬编码自定义协议目标未发现；未实机打开外部 Agent、未测试桌面协议注册状况。需重启应用加载修复。
提交：本轮按失败诊断提交收尾，主题 `R1078-FAIL: 修复 Codex 深链并记录验收阻塞`；hash 以该主题的 Git 回执为准。状态头下一轮 1079；不推送，不触碰用户数据。
