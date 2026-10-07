# R1097：四项修复与分批简化完成性核验

- 类型：§3 文档／验收收尾轮；中央领取 1097。无生产代码改动。
- 实跑：当前 0caca30 隔离树四项专项回归 29/29、2.124 秒、退出 0；默认冒烟与正式安全全量待运行。
- 欠账：四项修复与两批简化已合入；整体完成判定等待本轮收尾验收，不提前标记 TASK_COMPLETE。

## 原要求与当前证据

| 要求 | 当前实现与回归证据 | 边界 |
| --- | --- | --- |
| F1 模型请求重定向泄露 | model_pool 的两种传输均使用禁止重定向的 opener；test_model_pool_redirects 用真实 urllib 重定向处理、仅替换网络层，覆盖两种传输、五种状态、跨域／降级／同域及正常响应 | 不跟随任何重定向；非网络实站探针 |
| F2 Office 解压与展开预算 | idea_attachments 的 OfficeBudget 在读取前检查声明大小，实际 read(limit+1)，累计 XML 和输出字符；test_idea_attachment_budgets 覆盖伪小声明、累计读取、各 XML 成员、共享字符串重复、中文、API／本地分流 | 不是精确的进程内存上限；本地解析失败仍可保留原件 |
| F3 整目录恢复及登记 | storage_maintenance 接受普通目录，预检冲突／越界／链接／重叠；控制器仅登记项目库恢复的一级目录；test_recycle_directories 覆盖空目录、内容、回滚、登记失败及已有登记 | 旧清单缺失的历史登记元数据不能精确恢复；链接探测打桩，不操作真实项目 |
| F4 取消后迟到发布 | writing_api 在请求前后、工具之间、自动保存及注入发布入口检查同一取消回调；test_writing_cancellation 覆盖旧新请求隔离、取消和正常成功 | 协作式取消，不撤销已经进入的原子写入 |
| 分批行为保持简化 | R1094 c0d7001：pet_cloud 三处取消合一、storyboard_final 删除无操作异常包装；R1096 616308b：local_previs 三处复用已有即时选择函数 | 两批分别有 AST 展开等价与受影响测试证据；不把行数减少当作唯一收益 |
| 用户追加表单修复 | R1095 f4e4dd7：调用时现算引用、显式引用直传、复用窗口补齐空白未编辑字段 | 无头 8 项及定向 137 项既有实跑；未进行真实界面上传验收，需重启加载 |

专项命令：在隔离树程序目录使用项目 Python 的 `-B -m unittest tests.test_model_pool_redirects tests.test_idea_attachment_budgets tests.test_recycle_directories tests.test_writing_cancellation`。29 项全部通过；输出存在合成 HTTPError 的 ResourceWarning，未掩盖、未修改断言，不将其计为测试失败或声称零警告。

## 全仓简化范围与保留依据

全仓跟踪源码静态清点、Python AST 筛选与候选模块人工阅读不是全仓逐行人工安全认证。现有范围为 587 个 Python、4 个 pyw、JS／PS1／CMD／HTML 各 1 个；不含运行环境、用户项目、私有配置、历史副本及未跟踪输出。安全发现来源及原验收要求见 R1089，四项修复详见 R1090—R1093，两批简化详见 R1094／R1096。

全仓 Python 筛选已用于定位重复函数、重复语句与复杂入口；非 Python 跟踪入口／工具／模板已补查。重点候选保留理由：cloud_video 的恢复顺序、keyframe_comfy 的显隐状态、storyboard_files 的异步选择回调不等价；核心原子写入的 replace 与独占创建不能合并；native_assets 的不确定计费与确定失败不同；各 lifecycle 的校验与回滚次序不能当作相同代码；pet_ui、pet_settings、stage_execution_service 的微小去重增加跳转但无明显收益。asset_plan 的预留 ID 与分配顺序、prompt_optimizer 的字段／密钥语义、desktop 的提交／确认／粘贴安全分支均保留。

非 Python：Codex 粘贴脚本的枚举诊断、选择窗口与最终复核职责不同；两个首帧启动器的配置来源不同；HTML 模板的状态优先级与回退值不同，缺少足够 DOM 转移用例，不强行合并。保留不是宣称代码永远不可优化，也不是安全问题豁免；本轮不引入新功能、不扩大架构重写、不删除动态入口。

## 待完成的当前验证

正式全量必须基于干净 master 检查点并取得执行器回执，历史 R1094 全量不能替代当前版本。后续将记录默认冒烟、正式安全全量、提交与用户预设哈希核对。真实应用、真实 API、真实项目、实际 UIA／浏览器渲染不在本轮实跑范围。
