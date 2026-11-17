# R3234：修复requests消费者测试注入并记录候选与全量结果
<!-- round-evidence: {"commit_base": "1d11d38f", "credential_hits": 0, "evidence_sha256": "b1945f117ba77b12", "exit": 0, "failed": 0, "passed": 49, "round": 3234, "tests": "run_selftests.py -k execution_deadline http_client dependency_whitelist"} -->

## 三问

1. 类型：修复轮；根因是HTTP底层替换后一个消费者测试仍mock旧build_opener，未改产品行为。
2. 验证：禁网、主树exe＋隔离生产PYTHONHOME下，execution_deadline/http_client/dependency_whitelist共49条0红，2.4秒；之前完整架构502/502和冒烟9/9见R3227。复制exe上完整安全全量8483条、1529.5秒、28个文件红，且运行期测试临时文件改变内容树，exit2，不产绿凭据。未以此声称发布通过。
3. 欠账：已修本任务明确引入的消费者mock失配；解释器执行上下文/临时目录/缺资料造成的其他失败已有对照，仍须在一致环境重验，不降断言或发布门槛。

## 根因和最小修复

`test_provider_adapters_reject_stopped_submits_but_allow_later_poll` 仍patch urllib.request.build_opener，实际 Volcengine/Wan poll 已经由 infra.http_client.request_json 调用新的 RequestsJsonOpener；旧mock未命中导致测试占位域 example.invalid 网络尝试。仅改mock到 infra.http_client._default_opener，沿用原Request/.open/context/read假对象，补status=200/headers={}。取消拦截、GET方法与saved-task断言全部保留。修后DRAMA_SUPPRESS_NETWORK=1下49条全部通过，未调用供应商收费API。

## 全量实测与归因边界

完整回归起点1d11d38f干净树，718文件/972工作单元；无Tk656并行、Tk316受控4路，实际8483例/1529.5秒，10条登记skip；28个文件有红。运行期自检创建源码内drama-test临时内容，content_tree改变，运行器判无效，不写绿凭据。所有原始摘要及堆栈保存在common-dir/requests-migration-evidence/full-r3234-hidden-final.log。没有把28个文件全当作历史欠账或requests缺陷。

确认的环境对照：复制Python与主树Python.exe SHA256相同；同一git_hooks合法消息单测，复制exe失败0xC0000142，stderr为MSYS NtCreateDirectoryObject BaseNamedObjects 0xC0000022；主树exe相同cwd通过。主树exe配PYTHONHOME=本树运行环境/Python时，sys.prefix/purelib为生产隔离依赖、requests2.34.2，git_hooks探针通过；line_endings16、remote_post_receive_ci16、script_rename_validation18均通过。不能将该对照推广到未核验的其他失败。

另确认：分发outside_repository测试因失败临时目录回退到源码内（或后来诊断TEMP位于.git内）误识别祖先仓库；技能71/73因本树缺主树现有剧本锻造/编剧技能集资料包，不改73断言。正式对照环境应使用可写系统临时目录，不能以.git内TEMP测试“仓库外”。这些后续复验单独留痕。

## 当前候选证据（1d11d38f产品源码）

候选目录common项目.selftmp/requests-1d11d38f；candidate ZIP148766619字节，2644成员，testzip=None，sha256=f9c30cc56e1540aebee7a240bf2e8975672df478b11b5cb5856049bcbdb837a7。现有构建器三次verify、隔离五入口导入、实际HTTP200中文JSON、PNG往返、118根CA均通过。生产Python实际67413698字节、FFmpeg263905916字节，纠正早期“requests导致+186MB”的错误归因。生产副本不带开发工具，不覆盖真实用户配置。

GUI全新可丢弃副本用原生downloads_root隔离，真实launcher/Desktop/Tk及登录页可见、after回调无异常；未登录故主页面first_paint按登录闸延后。真实WM_DELETE_WINDOW能销毁窗口并退出mainloop；注册表写入和退出维护子进程被审计阻止，完整退出维护未覆盖。既有开机自启尝试单列，不能误当新requests缺陷，也不能称GUI全绿。证据common-dir/requests-migration-evidence/requests-1d11d38f/final-summary.json、gui-summary.json、report.md；旧严格审计证据仍保留。

## 并发任务评估

同轮附《成熟依赖并发任务评估_20261117.md》：只读50工作树已提交和未提交文件名。建议继续统一传输车道、暂停另起HTTP底层；两UI测量车道共同6文件先协调；旧platform入口修改需核对门面关系；JSON业务契约/队列不整体替换。不擅停他人任务，不把Git分支等同活跃进程。

## 提交与接续

使用标准dev.py commit生成49条证据；hash以实际git log/evidence/R3234.json为准。下一步同步master当前已前进至49da616（已有主树8450条绿报告），处理stdlib并行兼容测试差异，补齐工作树技能资料，受控临时目录＋主树exe/生产PYTHONHOME重验，合入队列与正式完成文件仍未完成。目标保持active，无TASK_COMPLETE。
