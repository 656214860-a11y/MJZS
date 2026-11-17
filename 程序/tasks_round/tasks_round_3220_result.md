# R3220：默认 JSON HTTP 传输复用 requests，保留产品保护行为
<!-- round-evidence: {"commit_base": "89987d28", "credential_hits": 0, "evidence_sha256": "bf9b874aa0a1377f", "exit": 0, "failed": 0, "passed": 63, "round": 3220, "tests": "run_selftests.py -k http_client platform_tools open_https_redirect http_boundary outbound_http_authority module_size_ratchet"} -->

## 三问

1. 类型：功能轮（基础传输实现替换），依《引入成熟框架与工作树规范任务书》T3执行；未改业务数据契约。
2. 验证：默认冒烟9/9（--affected连同门禁10项）；相关6文件63条用例在 requests2.34.2隔离环境及原2.32.3环境均绿；HTTP25条以ResourceWarning视作错误双环境均绿。架构488条、3 failures/1 error，与R3218及未修改a2281abc相同四项。发布全量尚未运行，不能宣称绿色版本已交付。
3. 欠账：修复HTTP错误响应的资源关闭，新增requests出站边界；四项基线架构问题未抹平，发布验收仍需处理。

## 实际改动与复用

公开签名保持 `request_json(method,url,*,headers=None,payload=None,timeout,**opts)`。infra/http_client.py 只改默认opener为平台RequestsJsonOpener，并在HTTPError读取后finally关闭。

平台contract/platform_tools.py新增73行协议适配（全文件882行，不提高模块大小阈值）：requests惰性导入，Session.prepare_request + HTTPAdapter.send（max_retries=0），避免requests处理下一跳时无界消费响应；保留环境代理和TLS验证。恒等认证钩子阻止netrc覆盖显式Authorization。所有3xx拒绝，不自动跟随。

保留现有opener注入、urllib Request协议、序列化、payload非None强制POST、POST默认不重试、显式允许才重试、重试计数与sleep注入、熔断、状态分类、响应/错误体上限、头脱敏。读取走raw.read(size,decode_content=True)，成功/超限/错误/读失败均关闭response与session；requests/urllib3异常归一为既有超时/URLError语义。遵守DRAMA_SUPPRESS_NETWORK。

出站守卫新增requests模块别名、函数别名、Session实例调用识别和13坏/9好样本，保留原始urllib断言，不因业务request/send/get同名误报。生产直接请求仍只能在平台层。

测试保留原11项，新增14项（合计25）；本地HTTP服务器验证真实默认requests路径，无外网收费请求。

## 红绿和命令

- 新增HTTP测试初次22条：11 failures + 1 error；实现后25/25绿。
- requests扫描器空实现下13坏样本断言失败；实现后本文件5/5绿。
- 父正式runner：`run_selftests.py -k http_client platform_tools open_https_redirect http_boundary outbound_http_authority module_size_ratchet`：6文件63条、0红、4.2秒，隔离环境requests2.34.2。
- 子相同unittest集合：新环境63条7.031秒、原环境63条5.751秒均OK。
- `-W error::ResourceWarning -m unittest tests.test_http_client`：双环境25/25通过。
- `smoke_test.py --affected http_client platform_tools outbound_http_authority`：隐藏桌面探针成功，默认9项及定向门禁均绿。
- `smoke_test.py --architecture`（原环境）：488条161.631秒，3 failures+1 error；相较R3218仅新增2个requests扫描自审测试，全绿。
- git diff --check 通过。

架构红灯集合保持：缺维护记录/基准历史.json、轮次连续性、剧本技能00引用、裸json.loads债务；改前独立检出复现证据见R3218。未用放宽白名单或删除断言处置。

## 并发与分发

标准scope扫描：42个其他活跃分支与本轮指定4路径无已提交重叠；此结果不证明他人工作区无未提交修改，也不授权暂停他人。

隔离运行环境已在当前工作树建立，基于主树Python3.14.7复制标准库/Tcl，排除原site-packages与Scripts，再从官方PyPI仅装requests2.34.2/urllib3 2.8.0/certifi 2026.10.23/charset-normalizer3.5.2/idna3.20/Pillow13.0.0。共享运行环境没改。此副本未入Git，锁文件/依赖门禁更新、分发自检/全量/合入留后续轮；本轮不把运行环境准备称交付完成。

## 提交与后续

本轮机器证据与提交由标准dev.py commit生成，以git log/evidence/R3220.json为准，不预填hash。任务书整体执行中，T4未完成。下一轮锁定生产依赖、验证隔离分发和发布基线；只在主干合入轮维护project_status，不硬写过期轮次。
