# R4506 技术审计剩余 16 项修复
<!-- round-evidence: {"commit_base": "06d0fd067", "credential_hits": 0, "evidence_sha256": "79b4a94cb3f50e9c", "exit": 0, "failed": 0, "passed": 538, "round": 4506, "tests": "run_selftests.py -k test_tts test_account_client test_keyframe_lifecycle_service test_cloud_video test_script_autosave test_job_store test_asset_resume test_artifact_index test_desktop_async_tasks test_background_probe test_skills test_skill_templates test_skill_orchestrator_completion test_stage_flow test_stage_exec test_root_layout test_http_client test_storage_maintenance test_project_archive test_renew_concurrency"} -->

- 修复轮。基线 06d0fd067 已合入 H1–H3，本轮完成 M4、H4、H6、M11、H5、M1–M3、M6、M7、M5、M8–M10、L1、L2。分类与验收场景见[项目健康记录](../../PROJECT_HEALTH.md)。
- 费用与作品：配音错误正文不进入时间轴与回调；真实回收批次恢复同名历史中的正确帧；关闭窗口时保存防抖期末次编辑；云视频配置第二写失败时回滚。覆盖已有、新建及旧数据兼容。
- 自动化：组合预算预检、环拒绝、前驱失败/待输入/待确认时后继零调用、独立支路继续。阶段模板不漏过前置步骤，人工放行及重试沿用已成功步骤。后台完成回调抛错后照常推进。
- 数据：使用临时 SQLite 验证跨类型同名隔离、清账、并发连接、过期租约、旧库迁移、版本外键、旧孤立引用保留和并发重建。128 MiB 临时文件的 Python 分配峰值为 2.13 MiB，单次登记约 0.11 秒。
- 维护：停用旧安装整理器，保留发布指引；账号客户端 8 MiB 有界读取并识别 HTTP 短读；云端探测拒绝、去重、取消后重试和 404 提示均有回归。系统 Python 在“程序”目录执行默认 mypy 成功，严格检查 2 个契约文件。
- 复核：本地子代理独立验证数据库、UI 和事务故障分支；修复前观察到相关失败。定向测试、凭据扫描以本轮盖章为准。冒烟、静态、架构以主干合并出口为准。未调用生产供应商、接触真实项目数据或代用户付费。第三方授权、实付结果、生产旧库规模及全流程性能仍需相应环境验证。
