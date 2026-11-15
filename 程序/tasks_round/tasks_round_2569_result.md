# R2569 结果：SWE-2 优化清单批次 2（T6 安全加固＋T9 文档起步）

1. 类型：功能轮（安全护栏与治理文档，不改阶段行为）。冒烟 8/8；定向测试全绿；未触发全量。
2. 范围：
   - T6a SKILL 导入护栏：`skill_import_service` 新增单文件 20MB／包 2000 文件·200MB 上限与符号链接（含 junction）拒绝；单文件在读入前拦截，包在 copytree 前拦截。新增 `tests/test_skill_import_validation.py::SkillImportBoundsTests` 4 条。
   - T6b 提交凭据扫描扩展：`round_evidence.SECRET_PATTERNS` 增加 GitHub（ghp_/github_pat_/gho_/ghu_/ghs_/ghr_）、Slack（xox*）、Google API（AIza）三类高置信形态；已验证 `scan_lines` 命中。当前跟踪文件全仓扫描未发现真实密钥。
   - T6c `.gitleaks.toml`（CI/发布前可选）、`SECURITY.md`（信任边界与已有防线）、`external_tools.lock.json`＋`scripts/tools_lock.py`（随附解释器 sha256 核对，`dev.py lint` 第三步）。
   - T9 起步：`GLOSSARY.md`、`CHANGELOG.md`、`docs/adr/0001-layered-architecture.md`。`tasks_round` 归档已有 `dev.py archive`（按月 git mv，保留近 2 月），`.err` 文件本就未跟踪，无需归档；归档执行留待单独一轮。
3. 未完成：T1 远端 CI、T7 测试拆分并行、T8 门禁补强、T9 归档执行与状态页瘦身、T10 包化方案。
