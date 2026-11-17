# R3212 全量失败修复与任务书最后三项验收缺口
<!-- round-evidence: {"commit_base": "593cf4bc", "credential_hits": 0, "evidence_sha256": "0bf9fe5f64fce8d3", "exit": 0, "failed": 0, "passed": 125, "round": 3212, "tests": "run_selftests.py -k test_file_origin_provenance test_stage_file_index_publication test_file_index test_global_library_service test_file_naming_producers test_aigc_package_diff test_exit_maintenance test_stage_gateway_base test_storyboard_catalog_scan_count test_ui_edges_guards test_claude_writing_session"} -->

## 三问

1. 类型：功能收尾/验收修复轮。根据 R3208 全量8350条、12文件红的真实结果修复，不以原任务书的过早完成声明为准。
2. 当前冒烟9/9；架构485条中484通过，唯一红为分支状态页轮次（3159≠3209，仅master更新状态页）。定向属性/界面集成135条仅compact布局类别集合1红，按真实文件叶子同步后compact 5条全绿；来源/发布/命名等最终82条OK；全量暴露的兼容专项43条OK。修改后完整全量尚未重跑，不能宣称已获得本提交的全量绿凭据。
3. 欠账：补齐独立来源事实、跨阶段分组切换及文件属性列3个任务书明确缺口；修复全量暴露的入口/旧门面/UTF8/计时替身等兼容问题。运行时分发口径仍要按既有R3210说明如实区分3.14.7与原3.15受控环境。

## 功能补齐

- Treeview增加kind/size/mtime，阶段/类型/日期独立跨阶段分组；保留name列、原剧本动作、组节点非文件保护、图标顺序、图片缩略图、筛选、后台加载和动态宽度。Tooltip保留完整文件名与时间，不用解析媒体头。
- 来源事实不存唯一缓存：`stage_layout.workflow_dir(root,'文件索引','来源记录.json')` 独立schema，严格项目路径校验，共用线程/文件锁；rebuild读取事实恢复origin。上传音频/首帧/库复制明确标用户上传；本地正式发布默认系统生成，模型分镜发布显式模型产出；不把已有用户上传改成系统/模型来源。
- 保持发布API兼容；text的context/origin归入严格校验的publication_options，不新增第8个形参越过复杂度门槛。调用方未知选项报错，不静默吞掉。
- 修复索引Windows运行时闭包：只用随附msvcrt文件锁，不导入不可用Unix fcntl。

## 全量失败逐项处置

- 分发清单：本任务108个根临时日志及遗留_w1.log已移至被排除的程序/logs/file_management_R3181，未修改正式分发白名单放过垃圾。
- module size：script_contract实体已缩至1103，冻结上限从1208下调1103，固化真实下降，未抬高门槛。
- exit：测试patch更新到infra日志/工作树维护实体。
- gateway：复用并行修复be7b0d36，补stage_execution_service历史网关重导出，原键集和publisher身份断言不变。
- aigc：隔离子进程保留-I并显式-Xutf8，修复Windows CP936与父进程UTF8解码不一致；真实9条测试通过，不注入PYTHONPATH。
- storyboard scan：回放旧版代码只在作用域内提供真实contract.script_manifest_schema别名；保留扫描次数和结果比较断言。
- UI源码守卫：补entity_file局部导入，修复NameError，不弱化断言。
- Claude：time替身从有限side_effect改每次业务调用前固定return100/101，避免date.today隐式额外取时耗尽；签名不等断言保留。
- UI消费者：分组后根节点不是文件；all_script_items返回真实叶子。原文件卡mtime、四类动作和长名缩宽断言保留，位置/属性列按授权新契约等强同步。
- stdlib裁剪：当前随附运行时在17:50被并行作业从3.15换成完整3.14.7，恢复的58个模块导致裁剪快照测试红。未擅自删除/替换运行时。原受控3.15备份明确执行test_stdlib_closure 10/10通过；主线R3210结果也已批准沿用该门禁/全量口径，3.14.7另跑冒烟9/9。

## 真实验证

- `logs/file_management_R3181/R3212_integrated2.log`：135条，158.6秒，仅compact类别断言1红；后续按叶子集合修正，`R3212_compact_final.log`：5条0红，20.2秒执行（含队列等待总763.9秒）。其他134条没有重改。
- `R3212_final_services.log`：82 tests /4.024秒/OK，含来源事实重建、正式发布、索引、复制和8类生产命名。
- `fullsuite-fixes-green.txt`：43 tests /8.239秒/OK（AIGC/exit/gateway/旧回放/UI守卫/Claude）。
- `R3212_arch.log`：485条，131.954秒，1红仅轮次头。`R3212_smoke.log`：9/9。
- 两套覆盖工具已真实重测，行覆盖625模块/77有覆盖（9组定向），分支84实体1212/2318，未写失败测量；全部历史下限保留并满足。门面100假象已在R3181更正。
- 所有文件操作测试TemporaryDirectory，Tk经隐藏桌面，没有操作真实用户项目。

## 未完成与下一步

本提交之后必须在干净树再次跑完整全量；同步最新master媒体预览/文件操作并行更改并保留双方功能；用实际绿凭据合并，然后输出同名任务完成文件。当前不标任务完成。
