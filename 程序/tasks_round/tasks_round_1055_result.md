# R1055 结构治理轮（执行）：cloud_video 私有死代码清理

1. 整理轮，来源 `tasks_round/tasks_round_1036_result.md` J14／OPT-12、K4；只处理 cloud_video 三个候选，不推进 J15。
2. 删除前后同组定向均 22/22，默认冒烟 8/8；架构 309/309、99.220 秒，较改前 309 无下降。最近全量为 R1053 的 3968/3968，不充作本轮全量。
3. 优化队列 J14 已关闭；状态页历史待办正文未顺带整理，当前轮次头为 1056 = 最新报告 1055 + 1。

## A. 认领与范围

中央 round_claim.next 领取 1055；使用既有共享锁与权威队列读写入口登记 R1036-J14，再 claim，owner=codex-j14。修改前创建 codex/wip-R1055；状态页仅在 master 更新。生产模块仅 cloud_video.py 一个，外加其已有测试、architecture 和本轮元数据，不超过三模块。

## B. 原候选位置

基准提交 08e59b2：cloud_video.py:25 `_legacy_provider_label`、:35 `_legacy_session_folder`、:54 `_legacy_saved_provider_key`。三个均无装饰器或定义时副作用，只是现行公开入口旁的旧私有实现。

## C. 调用方扫描

对程序范围受 Git 管理的 566 个 Python／pyw 文件作 AST 扫描（排除 private、episode、writing、配置、日志、备份、素材与技能数据目录），解析错误 0。三个候选各一个定义；Name、Attribute、Import alias 和含完整候选名的字符串引用均 0。另用 rg 对允许的源码与文档扫描：源码仅上述定义命中；历史诊断中的候选说明不是调用方。未扫描用户数据来推测消费者。

## D. 动态与兼容契约复核

ui_plugin_registry.py:12 只登记 cloud_video 模块，module() 返回模块而不枚举私有成员；desktop.py:6483/6487/6520 与 skill_panel.py:151 调用 settings_window，desktop.py:6490 调用 align_source。候选模块中三个 getattr 原行 75/179/227 均读取 desktop 的窗口或 page_index，不按名称调用候选。legacy_compat.FACADE_MANIFEST 未登记这三个符号。未发现拼接这些候选名或模块枚举调用的仓内消费者；不能据此证明仓库外任意脚本从未导入过私有实现。

## E. 唯一现行路径

保留 cloud_video.py:20 provider_label → cloud_video_service.provider_label；:24 session_folder → stage_execution_service.cloud_video_session_folder；:28 saved_provider_key → stage_execution_service.cloud_video_saved_provider_key。L3 仍注入 ProjectContext；现行服务保留会话复用、模型池优先和旧会话凭据只读回退，不删除兼容能力、不改变配置格式。

## F. 最小删除与等价检查

只删除上述三个私有函数，以及只被它们使用的 re 和 dated_path 导入。其他原有导入不顺带清理。将改前模块 AST 精确去掉这五个节点后，与改后模块 AST 比较完全相同（忽略位置），因此所有剩余顶层定义和函数体原样保留。未删除文件或用户可见产物，不涉及回收服务；Git 保留源码恢复依据。

## G. 兼容回归

在已有 tests/test_cloud_video.py 新增两个方法：四个供应商标签／尾斜杠分支；两供应商 × 记忆配置或磁盘配置四组旧凭据假数据回退。后者同时断言地址不匹配返回空、模型池入口调用和原配置／假 .env 字节不变；模型池与模块路径均隔离，绝不读取真实 private/。旧方法、断言与 Tk 密钥遮盖回归完整保留，无 skip 或弱化。

## H. 验证与三基线

- 随附 Python，程序目录执行 `-B run_selftests.py -k cloud_video`：删除前 22/22、删除后 22/22，均约 1.0 秒、0 红；包括 test_cloud_video 17 与架构发布边界 5。
- `-B smoke_test.py`：8/8，失败 0。
- `-B smoke_test.py --architecture`：309/309、99.220 秒；失败集合为空，与上一轮实际 309 一致，不以旧 JSON 数量代替。
- 最终文档／轮次复验：test_agents_md 与 test_round_baselines 15/15、0.311 秒。
- 本轮 1055−最近真实全量 1053=2；非架构统一路线图整项收口，不改启动／Tk 生命周期／删除语义／层级表，未触发全量升级。历史 R1053 固定检查点 c303259 全量 3968/3968、382.203 秒仅代表当时树，不替代本轮实测。

## I. 数据与提交边界

不改配置、用户项目、密钥、private/、episode/、writing/、logs/；不提交真实视频请求，不清缓存，不使用 computer-use。新增兼容数据仅在测试临时目录内生成及清理。文件范围：cloud_video.py、tests/test_cloud_video.py、architecture.md、project_status.md、优化待办队列.md、本报告。

## J. 整改结论

三个候选经消费者和兼容契约复核后删除；现行公开入口及服务不变。门禁通过，仅勾选 J14，并由中央 complete 收口。J15／J16 另轮处理，不能沿本轮范围扩大删除。没有退役有消费者且未到期的兼容 facade。

## K. 测试迁移计划

无需迁移：已有测试留在原文件，新增两个兼容保护方法，不删除旧测试。按来源 K4 在删除前后运行同一套；若出现遗漏消费者须恢复相关私有实现并重新验证，不能改断言迁就清理。架构测试文件和方法均未增删，无入口清单变更。

## L. 提交与扫描

适用门禁通过；凭据形态扫描未命中，扫描限于本轮差异中的常见 token／私钥形态，不构成完整安全证明；git diff --check 通过。最小暂存六个本轮文件，收尾提交以 Git 消息 `R1055: 清理cloud_video无消费者私有副本` 唯一定位；提交回执及哈希在最终回复提供，不预造自引用哈希、不 push。

## M. 自审

自审通过：范围为一个生产模块；只删经确认零消费者的候选，兼容功能由未变的现行服务保留。新增测试验证用户可观察行为而不是只断言符号消失；前后 AST 等价补充人工差异审查；原测试 17 个方法（含辅助方法）AST 不变。适用基线全部通过，不新增越界依赖或用户功能。
