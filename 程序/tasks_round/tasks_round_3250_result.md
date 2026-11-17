# R3250：发布前修复请求异常凭据泄露与系统TLS信任兼容
<!-- round-evidence: {"commit_base": "565e8389", "credential_hits": 0, "evidence_sha256": "8d037d2708fe9329", "exit": 0, "failed": 0, "passed": 75, "round": 3250, "tests": "run_selftests.py -k http_client platform_tools open_https_redirect outbound_http_authority branch_coverage_floor module_size_ratchet"} -->

## 三问

1. 类型：修复轮；独立复核命中两个P2，均在本任务新传输路径内，不扩展业务功能。
2. 测试：父正式runner覆盖http_client/platform_tools/redirect/outbound/module-size共70条全绿、4.3秒；完整架构502条172.256秒仅决策点基线待真实重测，其余501项绿。分支覆盖真实重测和最终门禁结果见后续补记/机器凭据，不冒填全量。
3. 欠账：修复对外错误可能带合成URL密钥/非法头内容；恢复系统CA默认信任。完整整应用发布验收仍在主树合入后完成，不把旧复制路径hidden失败称绿。

## 根因与最小改动

### 异常凭据

_requests_failure原str(error)会把requests请求URL query、代理/非法header内容带入ServiceResult.error_body。真实本机关闭端口+合成api_key、InvalidHeader验证命中。改为受控固定network request timed out / network request failed，保留timeout/URLError类别及内部cause，公开结果不外传原文。4个新增测试先红5失败；实现后HTTP29条通过，原禁网测试保留。

### 系统信任兼容

旧urllib默认ssl.create_default_context在Windows使用系统信任，新requests/certifi仅默认bundle可能拒绝已受信任企业代理/私有CA。新增私有VerifiedAdapter：默认创建系统上下文再load certifi；显式REQUESTS_CA_BUNDLE/CURL_CA_BUNDLE保持用户指定CA路径，使用空TLS-client上下文只加载该路径。普通/HTTPS代理均保持验证，requests2.32+连接池键不覆盖自定义context。不关闭TLS验证、不修改全局ssl、不引入额外依赖。

新增5个测试含7路径断言，先红后绿；覆盖默认系统/补certifi、自定义文件/目录、环境代理、verified_context等。TLS子任务最后回报中断，父接手完整读回并正式runner70条验证通过。生产platform_tools共915行，未抬module-size阈值。

## 范围

contract/platform_tools.py、tests/test_http_client.py、tests/test_platform_tools.py；另真实重测后的分支覆盖率基线和本结果。原断言未弱化，重试/重定向/上限/资源关闭语义保持。不会将原始凭据或系统证书内容写入报告。

## 当前主树与运行环境

mq-12已由标准merge队列完成，主树565e8389/R3249，merge CI通过；本分支已同步该提交。主树requests2.32.3包与dist-info先备份common-dir/requests-migration-evidence/main-requests-before-3250，检查无全量锁后，按已合入requirements从已下载官方wheel离线升级仅requests2.34.2（no-deps/no-compile）。主树依赖门禁15/15、默认冒烟9/9，其他依赖/用户配置未动。候选生产runtime六包不变。

本轮完成后仍走标准队列合入，不跳hook；随后用主树自身Python/FFmpeg路径完成最终安全全量，避免已证实的复制native文件hidden初始化限制。提交hash/evidence由实际git log/evidence/R3250.json核验。
