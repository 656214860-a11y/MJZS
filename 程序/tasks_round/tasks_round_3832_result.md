# R3832 账户设计全文归并子任务结果
<!-- round-evidence: {"commit_base": "b860721f", "credential_hits": 0, "evidence_sha256": "26f2f0ebd8162951", "exit": 0, "failed": 0, "passed": 0, "round": 3832, "tests": "docs-only"} -->

- 本轮类型：§3.3 结构治理中的纯文档归并；不改源码、测试、运行配置或登记表。
- 测试跑了吗、三个基线过了吗：运行本轮文本覆盖与Markdown路径／锚点核验，59/59；链接32条就绪、2条待root既定迁移，无坏锚点；`git diff --check`通过。纯文档轮按CLAUDE约定不跑smoke／selftest；默认冒烟8/8、架构当轮数量、全量回归均**未运行／未宣称通过**，不借历史绿色结果替代。未验全部GUI、云服务、备份恢复、法务或支付。
- 欠账少了吗：账户设计由旧权威外指变为07完整单一正文，消除本册重复，补齐D/Q状态和接口差异；跨分册引用、旧说明删除与全仓目录门禁留给root，不把这些记为本子任务已完成。

## 交付与范围

基点 `b860721f`，独立分支 `codex/account-design-consolidation`，工作树 `D:\漫剧制作助手\.agents\worktrees\account-design-consolidation`。真实领取R3832；领号命令成功返回3832，但附带子线程GBK解码告警，本轮后续工具统一`PYTHONUTF8=1`；不伪称该告警已修复。

只修改 `docs/specs/07_业务域规格.md`，新增 `docs/records/账户设计条款迁移映射.md` 与本结果文件；规范提交工具还将生成本轮 `tasks_round/evidence/R3832.json`。不改master索引、不合master、不推远端，不动原说明文件，R3812整体任务完成文件由root统一交付。

## 完成证据

1. 完整读当前07（218行）、旧设计（250行）、立项清单（101行）、ADR-0007–0012，以及最新主树R3812任务书§4与本树AGENTS／相关runbook。
2. 07保留7.1–7.8一级锚点；7.4设置、7.5素材、7.6模型、7.7依赖正文逐字保留，仅把生成服务失败契约链接改将来规范位置；7.2/7.3/7.8集中引用7.9。
3. 7.9正文承接旧设计1–10全节：十张原核心表及字段、19个原API组合及全部反引号标识、RSA14字段、设备/重放/双时钟/MAC/留存/退款/推荐预设非Key池/部署边界/分期/未决；D1–D16加D11b共17项，Q1–Q8共8项逐ID状态保留。
4. 公开源码核对：当前客户端`domain/account_client.py`，独立服务端`app/main.py`；必要输出/处理取`service.py`、`providers.py`、`lease.py`；客户端加固只定位`entitlement_service.py`、`account_store.py`、`lease_verifier.py`和控制器。只读取公开契约必要内容，未读私密配置或发起网络请求。
5. 修正`/me`顶层has_password、并非所有响应有server_time；补请求解析上限、元数据可选升级字段、export.deletion_at、退款入出参、providers实际字段。服务端退款路由已存在，但该客户端文件无退款包装，不能宣称UI验收。
6. 旧价格39/99/399明确被用户19/49/189取代；`/v1/metering`两端均不存在，保留为未实现候选隐私上限；原07免费含初步分镜／已成功导出与前两阶段设计冲突显式处置；导出消费者未复验，不擅宣称全部免费或已拦截。
7. 明确历史部署（SSH无登录后台与后续8433认证后台）、邮件log验证码与禁日志冲突、5年财税估计／数周备案／容量假设不作法律或验证事实；清理器新增表留存仍需实际验收。

原文件SHA256（旧文件本轮未改）：

- 旧设计：`c02c6b209464def0bab7c087fe4bf48d228753cd8f2cc7aa53c859af18697622`
- 立项清单：`dc9bf6484d32b57e883187083ecf8e97f375ada33c79dd4c553c51d8ff8f1f5a`

## 实际检查与可复核方法

执行随附解释器`-B`运行工作树外临时校验脚本，退出码0：`checks 59 passed 59 links 34 ok 32`；另运行`git diff --check`退出码0（仅CRLF将规范为LF的提示）。早期PowerShell重定向报告得到非UTF8文件、一次内联引号错误均已改用UTF8脚本输出并重新验证，未把失败命令当成功。

59项构成：8个稳定一级锚点＋10个来源大节＋10张表各自字段＋1组14字段租约＋1组旧API所有标识词元＋25个D/Q映射＋旧权威外指已移除＋metering未实现声明＋非账户三域/依赖正文保留＋无坏锚点。

在仓库根可复核核心覆盖（PowerShell，把代码存于工作树外临时脚本，用主树随附Python运行；不改仓库）：

```python
from pathlib import Path
import re, subprocess
r = Path.cwd()
o = (r/'程序/说明/账户会员云端设计.md').read_text(encoding='utf-8')
n = (r/'程序/docs/specs/07_业务域规格.md').read_text(encoding='utf-8')
m = (r/'程序/docs/records/账户设计条款迁移映射.md').read_text(encoding='utf-8')
for i in range(1,9):
    assert len(re.findall(r'^## 7\.'+str(i)+r' ', n, re.M)) == 1
for i in range(1,11):
    assert re.search(r'^### 7\.9\.'+str(i)+r' ', n, re.M)
for table in ('user identity device session subscription trial_ledger '
              'user_password email_code audit_log redeem_code').split():
    row = next(x for x in o.splitlines() if x.startswith('| `'+table+'` |'))
    assert all('`'+x+'`' in n for x in re.findall(r'`([^`]+)`', row))
lease = o[o.index('`payload` 字段：'):o.index('### 4.2')]
fields = re.findall(r'^\| `([^`]+)`', lease, re.M)
assert len(fields) == 14 and all('| `'+x+'`' in n for x in fields)
api = o[o.index('### 3.2'):o.index('### 3.3')]
assert all('`'+x+'`' in n for x in re.findall(r'`([^`]+)`', api))
for id in [*('D'+str(i) for i in range(1,17)), 'D11b',
           *('Q'+str(i) for i in range(1,9))]:
    assert re.search(r'^\| '+id+r'(?:[ （])', n, re.M)
    assert re.search(r'^\| '+id+r'(?:[ （])', m, re.M)
base = subprocess.check_output(['git','show',
    'b860721f:程序/docs/specs/07_业务域规格.md']).decode('utf-8')
mid = base[base.index('## 7.4 设置'):base.index('## 7.8 未决事项')]
mid = mid.replace('`说明/生成服务失败处理契约.md`',
    '[生成服务失败处理契约](../contracts/生成服务失败处理契约.md)')
assert mid in n
print('覆盖核验通过')
```

34个链接逐个解析相对路径，并对存在目标按Markdown标题slug校验片段。仅2个待root迁移目标：

- `docs/requirements/产品需求规格.md`
- `docs/contracts/生成服务失败处理契约.md`

源代码API核对是静态阅读，不是调用服务或自动接口集成测试。未伪造实现/运行凭据。覆盖脚本的词元检查保证字段未丢，不能替代条款语义审阅；本轮另逐节人工读回07与映射核对。

## root接续、提交与回滚

- root迁移后删除旧重复设计正文并处理立项历史身份；更新02/04/06和PRD/导航/队列/登记/状态引用，尤其02的metering不能再标已实现；迁移后重新查全仓链接。
- root另核验导出闸门消费者、后增表注销清理、部署端口/认证、真实邮件模式、OSS/恢复与未决法务资质；本轮只记录差异，不扩大范围改实现。
- 本分支提交状态：待本轮规范提交；提交hash以最终交接和Git日志为准，不在自包含提交正文中编造自身hash。规范证据文件由工具生成并随提交保留。
- 回滚：对最终本分支提交执行`git revert <hash>`；不涉及用户数据或数据库。

账户合并子任务完成；R3812整体未在本分支宣称完成。
