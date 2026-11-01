# R1147：修复 Anthropic 本地 Claude Code 安装识别

## §7 三问
1. 类型：修复轮；中央领取 R1147，队列无匹配任务，不冒领其他任务。
2. 验证：新增 3 项回归先跑 2 红 1 绿，修复后 3/3；工作流定向 101/101；受影响冒烟 9/9（包含默认 8/8 与额外 2 项定向门禁）。均为本轮实跑。
3. 欠账：本轮无新增；历史安全全量 R1145，不冒称当前树全量。仅 L3 现有程序定位函数增补路径，无启动生命周期、删除语义或层级变更；未触发五轮排程，不重复整套架构或全量。

## 根因与修复
- 现有 `claude-desktop` 映射的是 Claude Code CLI，不是 Claude 桌面聊天窗口；不能把两者的命令行参数混用。
- `find_program()` 只识别 PATH 原生 exe 和用户 `.local/bin/claude.exe`，本机 npm 安装提供的是 cmd/ps1 包装入口，因此误报未安装。
- 保留显式配置、PATH exe、独立安装原有优先级；再从 PATH 中 claude.cmd 的父目录及 APPDATA/npm 查找包内原生 exe。仅检查明确文件，不递归扫描、不执行包装脚本、不新增 shell。
- 本机只读版本探针确认为 Claude Code 2.1.280；修复后的定位及下拉框标签探针成功，不再带“未安装”。不修改用户项目或配置。

## 实跑命令
- `python -B -m unittest discover -s tests -p test_claude_program_detection.py`：3/3。
- `python -B run_selftests.py -k workflow claude_program`：101/101，1.2 秒。
- `python -B smoke_test.py --affected workflow_settings`：9/9；附加定向 2/2。
- 本机已定位程序 `--version`：2.1.280 (Claude Code)。未调用模型、未启动真实创作会话；登录权限与端到端创作未验证。

## 自审与交付边界
通过：无越界依赖、无新公开接口或业务入口、未扩大无关模块；标签与执行共用同一定位函数，同类 npm 识别覆盖默认与自定义前缀。既有断言未删除/弱化，保留缺少二进制时明确报错。最小修复与定向测试技能用于限制改动及测试范围。
需重启助手清除旧进程的安装状态缓存；该接口继续启动 Claude Code 交互命令行，并不新增 Claude 桌面聊天投递协议。主目录原有修改保留，不推送。

[TASK_COMPLETE]
