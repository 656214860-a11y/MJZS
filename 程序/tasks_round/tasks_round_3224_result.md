# R3224：锁定绿色版生产依赖并隔离开发工具
<!-- round-evidence: {"commit_base": "76b291ac", "credential_hits": 0, "evidence_sha256": "6c0b217d91e20401", "exit": 0, "failed": 0, "passed": 40, "round": 3224, "tests": "run_selftests.py -k dependency_whitelist http_client"} -->

## 三问

1. 类型：兼容/可靠性轮；生产依赖锁及其门禁，复用现有分发构建器。
2. 验证：隔离环境依赖门禁15/15；HTTP+依赖共40/40；默认冒烟9/9；完整架构500条、3 failures+1 error，与R3218/R3220已复现基线四项相同（新增12条依赖测试绿）。发布全量/主干同步后回归尚待下一轮，不能宣布正式发布。
3. 欠账：原“要求所有开发工具预装”“旧requests固定版本”已修正；基线架构四项未扩大处理，发布欠账保留。

## 改动

- requirements.txt：六个生产依赖精确锁定，作为版本唯一源；requests2.34.2、urllib3 2.8.0、certifi2026.10.23、charset-normalizer3.5.2、idna3.20、Pillow13.0.0。
- tests/architecture/test_dependency_whitelist.py：从requirements读取生产版本；生产六包必装，R3215已允许的开发工具可选、存在才验版本；metadata distributions(path=[purelib]) 排除个人site干扰。新增缺包、错版、未知包、名称归一化、锁表解析及发现范围等行为测试，避免版本双真源。
- 维护记录/依赖白名单.md：更新实际政策，移除未测节省时间、星数和体积等硬阈值，按需要、维护、许可证、Windows支持和体积评估。开发工具不进入生产副本。官方Requests HISTORY记录2.32.4修复CVE-2024-47081，本次不再将2.32.3列为新发布期望版本。

## 红绿证据

改前隔离依赖测试3项2失败（旧requests版本与强制开发包）；改后15/15通过。原共享解释器加载本树测试14通过1失败，仅requests2.32.3不匹配2.34.2；不为通过兼容旧发布版本，也未修改共享解释器。

父正式runner（本树隔离Python3.14.7，UTF8）：

- run_selftests.py -k dependency_whitelist http_client：40条、2.3秒、0红。
- smoke_test.py：9/9，隐藏桌面探针成功。
- smoke_test.py --architecture：500条150.759秒，3 failures+1 error。集合：维护记录/基准历史.json缺失、轮次连续性、剧本技能引用、裸JSON债务；改前复现见R3218。
- pip --isolated download --index-url https://pypi.org/simple --only-binary=:all: -r requirements.txt：六包wheel均成功保存于Git common-dir/requests-migration-evidence/wheels-r3224，不作为源码入库。
- git diff --check通过（requirements换行提示非错误）。

## 隔离运行环境与候选

本工作树运行环境/Python基于原主树Python3.14.7复制标准库/Tcl，排除site-packages、Scripts和pyc，然后官方PyPI仅安装上述六包。主树运行环境保持原样。许可证/CA随wheel安装元数据保留。

现有distribution_build.py从本树源码和本树运行环境构建。初始候选requests-r3224 digest2448文件无差异、排除项零命中，但清单缺ffmpeg（工作树无随包目录），未宣称通过。随后只读复用主树ffmpeg到本树运行环境，独立候选requests-r3224-final构建与verify均exit0，keep/digest/排除检查均通过；子任务完成移动路径与隔离实际HTTP复验后，最终summary单独记录，留待下一轮任务总验收引用。

权限过程如实：新隔离解释器向两个工作树外新目录写入WinError5，未改ACL/绕过沙箱。改用既有开发解释器调用同一构建器成功；候选自身-I导入requests/Pillow、在自身目录写入/删除探针成功。不能由构建脚本运行问题推断用户发行不可用，也不能省略候选自身验证。

## 后续与提交

本轮不含HTTP逻辑变更（R3220已提交76b291ac）。主干期间进到01792e15并含包化/政策接续；需下一同步轮合入并重测消费者、完整安全全量及候选。旧主干后台全量有多个既存失败，不混称本轮新增，不删除断言。

提交使用本树隔离解释器通过dev.py commit（依赖测试应对正确生产环境）；hash/evidence由实际git log/evidence/R3224.json核验。任务书整体执行中，尚无任务完成声明。
