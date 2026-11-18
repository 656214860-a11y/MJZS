# R3281：SKILL预算第四轮——原始命令与API双路线受控验收
<!-- round-evidence: {"commit_base": "dec4239c", "credential_hits": 0, "evidence_sha256": "a279c2e72d21ba46", "exit": 0, "failed": 0, "passed": 65, "round": 3281, "tests": "run_selftests.py -k skill_budget_send_entries shared_input_stages skill_command writing_context_budget_guard"} -->

## 三问

- 类型：§3.2 修复轮；第三轮dd6a7cd4结束后按用户要求自动启动新子会话 round4-e2e。实际中央领号R3281。
- 验证：最终路径还原红8中3红→窄集8/8；关联65/65、0跳过、45.0秒；默认冒烟9/9。尚未完成最终安全全量与master合并。
- 欠账：最终稳定候选完整架构/安全全量、任务完成文件及主线合入尚待闭环。

## 主线同步证据

R3278之后同步最新master056f882f（含L1与UI），冲突仅writing_api限流位置。保留我方网络前预算拒发顺序，并将主线 `wait_for_rpm(...credential=key_env)` 放到校验后位置，未丢凭据分桶语义。相关guard14+L1可靠性27共41/41，原始common-dir `task-logs/R3278-round3/merge-l1.log`。同步提交dec4239c。遵守功能分支不能提交project_status约束，分支保留旧状态页，最终合并时主树保留其最新状态头与双方正文，不能整体覆盖主树。

本机 `.git/info/exclude` 仅加入 `/.agents/worktrees/`，避免把功能检出容器视为主树未跟踪源码。不修改共享.gitignore，不隐藏其他路径或实际源码变更。

## 入口事实

- 解析为kind=engine/skill的slash命令走共享发送→open_flow_agent→真实resolve/freeze→Qwen CLI适配器，API供应商/模型以OPENAI环境传给CLI，并非writing_api直连。
- slash目标本身只是路径指令，不自动加入所选技能正文；不得声称API能补读路径。含空格未匹配文本可能走自由消息，测试须明确原始文本与parsed kind。
- desktop_shared_send在domain迁包后用`skill_command.__file__.parent/skills`会找错domain/skills，engine分支在冻结前失败；本轮以单行根路径修复与行为回归锁定，不扩大UI/路由重构。

## 执行边界

子会话独占 desktop_shared_send.py 最小路径修和新增tests/test_skill_budget_send_entries.py。所有fixture临时项目/技能/模型，保留真实预算和payload/launch适配器，仅最外部进程或HTTP传输用桩，不读取用户项目/生产模型池/密钥，不收费实发。

验收必须分别证明：有效128K六技能正文完整到达受控终点；展开体积可超过300000但按预算引用可观测skipped；未知窗口和超大正文拒发且终点零次。不得将“换错误文案”或“日志没旧错误”作成功。

原始红绿日志位于 common-dir `task-logs/R3281-round4/`。窄集8/8、0跳过（green-narrow.log），真实CLI两段契约与API正例/负例均完成。为排除早期夹具错误影响，最终合成夹具在仅还原原业务路径行时单独重新跑 red-final.log（路径miss导致3红），恢复单行修后再跑指定宽集，最终 `green-regression.log` 为65/65、0跳过、45.0秒，`smoke.log` 9/9。CLI明确为获准两段契约，不宣称完整Tk/UI dispatch；真实Qwen任务文件包含全部六正文、args模型及环境URL均正确。API保留真实capture_request→reply→WritingRequestAdapter→PoolAdapter→HTTP payload，两个128K正例各传输一次；未知/巨大正文均HTTP0/RPM0。无实费远端调用。
