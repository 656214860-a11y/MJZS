# 变更日志

本项目按轮次（R<N>）演进，详细记录见 `程序/tasks_round/`。此处只保留对用户可见的里程碑。

## 未发布

- 发布门禁聚合 `dev.py release-gate`：一条命令逐项判定随包工具、CI 收据、全量凭据、分发自检与版本号一致性，回答「现在能不能发布」（REL-02）。
- 统一错误码注册表（`error_codes.py`）：网络、凭据、资产、契约类失败带可重试标记与修复建议。
- SKILL 导入护栏：单文件与包体积上限、符号链接拒绝。
- 提交凭据扫描扩展 GitHub／Slack／Google 密钥形态；新增开发期 ruff＋mypy＋工具哈希核对（`dev.py lint`）。
- 安全说明（`SECURITY.md`）、术语表（`GLOSSARY.md`）、ADR 起步（`docs/adr/`）。

## 发布记录的唯一入口

版本号由 app_metadata.VERSION 定义；发布前在本文登记版本/提交/轮次。迁移前更新记录的版本正文原样保留如下；未发布条目仍保留在文首。

版本号的唯一来源是 `app_metadata.VERSION`；本页必须有同名小节（`tests/test_version_record.py` 校验）。每次发布前补一节，逐轮细节仍以 `project_status.md` 与 `tasks_round/` 为准。


## V0.7

- 可靠性：统一日志 `logs/app.log`（滚动、脱敏），接管主线程、后台线程、Tk 回调与 C 层崩溃；启动失败日志改为追加并带时间／版本；静默吞异常（`except Exception: pass`）全部留痕并设棘轮（R1457–R1459）。
- 随附 Python 为裁剪版：新增标准库可用性门禁，缺库在开发机即红（R1458）。
- 性能与体验：切页性能、三虎弹窗 10 秒自动关闭、删除按钮、改名与布局（R1446–R1453）。
- 剧本：HOLLMWOOD 角色并入全流程 AIGC 剧本 SKILL，框架移除（R1441–R1442）。
- 工程：全量回归欠账按源码轮次计数、后台自动补跑、钩子自愈（R1439–R1443）。
