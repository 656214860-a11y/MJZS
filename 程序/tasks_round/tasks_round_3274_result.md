# R3274：SKILL 上下文预算第二轮——正文优先、快照预算与兼容闭环
<!-- round-evidence: {"commit_base": "abd48c38", "credential_hits": 0, "evidence_sha256": "7cb55be39f0bacbe", "exit": 0, "failed": 0, "passed": 79, "round": 3274, "tests": "run_selftests.py -k skill_context_budget_prestage skill_deep_inline skill_reference_closure workflow_settings_cache request_freeze_entries writing_quality stage_prompt_governance"} -->

## 三问

- 类型：§3.2 修复轮，任务书第二轮。第一轮 R3273（abd48c38）完成后已自动启动独立子会话 `round2-freeze` 执行。
- 验证：最终关联集94/94、0跳过；默认冒烟9/9；静态/体积门禁包含于关联集。架构改前502条2失败1错误，补齐固定输入后其中24条相关门禁24/24，状态头连续性留最终共享状态合并；本轮未跑全量。
- 欠账：原始故障仍需第三轮完整发送预检与第四轮受控端到端确认；最终合入 master 前必须复验。

## 范围与设计

- `orchestrator/skill_inline.py`：注入已捕获模型记录；优先显式窗口，再使用用户指定前缀默认；仅明确 API 在缺窗口时拒绝，CLI/桌面保留原无窗口路径。默认程序根由 model_pool 自己负责，不误用 contract 目录。
- `orchestrator/workflow_settings.py`：预算元数据只含 model/context_length/source，绑定同次模型身份，不冻结完整模型记录或凭据；正文优先、引用后分配；两次遍历复用一次读取的局部快照，最终检查完整冻结文本，包装/制作锁/质量/资源提示/未发送引用提示均计入。
- 保留字符硬闸、缺失/越界/循环校验以及正文不可截断；新增显式 skipped/degraded 等安全元数据。API 不能读取本地路径，提示不能宣称已读取这些引用。
- 独立复核发现跨技能 shared seen 不可把文件的一个 fragment 当全文去重，需按 (路径, fragment) 保留不同章节；大章节被跳过不能吞掉后续可装小章节。先红后绿纳入本轮。

## 基线环境修复记录

R3273 报告的架构失败误名已按原始 traceback 更正：真实第三项是 `test_script_stages_name_only_their_approved_00_references`，并非不存在的方法。当前功能树缺少固定 Gitlink 工作目录：用本机干净嵌套仓库本地 clone，detach 到外层索引固定提交，未复制源工作目录配置、用户项目、密钥或运行数据，未修改 Gitlink pin。

按 `scripts/auto_full_safe.py` 现有 IGNORED_INPUTS 唯一白名单补齐 `维护记录/基准历史.json`，未整目录复制。`run_selftests.py -k agents_md skill_reference_injection` 已恢复 24/24。剩余轮次头连续性在最终共享状态合并处理，分支不提交 project_status.md。

主树 R3268 后台全量曾占跨树 GUI 令牌，本轮按运行器排队，未绕过隐藏桌面/锁。该主树全量最终失败，已证实至少两类环境问题：GBK 子进程解码失败，以及干净副本 PATH 中缺 FFmpeg/FFprobe 导致 tool_path 返回 None。不得统称为单一 GBK 根因。本任务后续测试进程使用 PYTHONUTF8=1，并将已存在的公共 `D:/Tools/ffmpeg/bin` 加入进程 PATH；只读 --version 已确认 ffmpeg/ffprobe 9.0.1 可用。不写生产配置、不改测试断言或主树脚本。

## 验证与提交

原始红绿输出位于 common-dir `task-logs/R3274-round2/`。最初 `red.log` 10条中9红；新增 snapshot/fragment/frontier/unused-quality 等边界均分别保留 red-*.log。最终 `green-final.log` 10文件94/94、0跳过（16条新prestage、17条quality、11条deep、11条closure、6条cache、3条request_freeze、15条governance、静态名字8、hygiene5、体积2）。`smoke.log` 默认9/9。所有包含Tk的测试经正式隐藏桌面运行器；未弱化原业务断言，仅为已有 api 无模型的质量测试 fixture 注入合成窗口记录（新拒发契约所需）。

2026-11-18 03:55 接续检查点：第一轮已提交 abd48c38；本轮已领 R3274 尚未提交。`round2-freeze` 子会话独占两个生产模块及新 prestage 测试/必要 quality fixture，正在将过度保守全闭包提示预留改为直接 frontier 逐层预留，并修复不同 fragment 去重和实际质量规则判定；`budget-review` 只读审查；`entry-trace` 只读检查原始 slash 入口。父代理不得与之并发写相同文件。已有 narrow15/15、static15/15 绿色，但新增边界修复后必须重跑，不能据中间结果提交。父代理仅改本轮报告与上一轮报告误名。第二轮完成后：父代理复核/冒烟/统一入口提交，领下一编号，启动第三轮新子会话写 writing_api 完整请求前缀窗口终检及 freeze sections（不与第二轮并发写），随后第四轮合成6技能近334580字符输入成功到桩传输、超大负例零网络；最后同步master（当前00e3938b）、完整受控安全全量、合并队列合入、任务完成文件与goal complete。所有命令环境 PYTHONUTF8=1 / PYTHONIOENCODING=utf-8，并加进程PATH的 D:/Tools/ffmpeg/bin（已验证9.0.1）；主树上一全量因GBK及缺媒体工具失败，不可复用旧绿凭据。

后续检查点：宽回归 `green-wide.log` 曾为91/91、13.7秒，新增fragment/frontier/quality后必须再跑。`round2-freeze` 决定取消深collecting，改全部所选正文先预读一次、仅直接frontier预留，引用入选后才占后代frontier；避免不可达后代Unicode/missing与大量hint误拒。等待其最终原始红绿输出后再提交。独立 `entry-trace` 已证实原slash入口实际是Qwen CLI配置DeepSeek API环境，不是writing_api直连；第四轮须分别验证CLI启动受控终点和writing_api桩传输两条链路，不能互相替代。原 `desktop_shared_send._resolve_skill` 用domain.__file__算路径可能还有真实包化缺陷，entry-trace正在确认，不提前扩大修复。`validation-env`完成只读环境核查：主树现在无活动合并，无排队merge；四gitlink外层指针未改、基准输入两门禁已24/24。主树00e3938b，最终同步/合并前仍重查。

未产生远端收费调用，未修改用户项目或生产模型配置，未新增依赖。提交回执见 Git 的 `R3274:` 记录。
