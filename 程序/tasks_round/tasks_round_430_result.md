# R430 结构治理轮：资产计划发布包

- **范围**：执行 R418 J-2 的一个成果族迁移：仅处理资产计划的四份派生产物；不改资产图片导入、配置、密钥、缓存、删除入口、阶段完成事件或白模上传。
- **改动**：`asset_plan.publish_plan_bundle()` 成为名称编号对照、`assets.json`、来源和导入进度的唯一同步发布入口。它校验入参、记录旧字节、逐份调用原子保存、落盘复核；任一环节失败即恢复旧内容，并受控清理本轮新建文件。`sync_plan()` 不再直接写这四份文件。
- **测试**：新增 `tests/test_asset_plan.py`，覆盖失败回滚四份旧文件及成功发布复核；新增 `test_asset_plan_publication_boundary.py`，禁止 `sync_plan()` 直接写入并要求调用发布包。测试未扩大白名单或削弱断言。
- **文档**：`AGENTS.md` 架构门禁清单登记新门禁，基线同步为 22 个文件、40 项检查。
- **验证**：`python -m unittest tests.test_asset_plan tests.test_workflow tests.architecture.test_asset_plan_publication_boundary` **82/82** 通过；`python smoke_test.py --architecture` **40/40** 通过（15.827 秒）；`python smoke_test.py` **8/8** 通过。
- **欠账**：阶段产物统一写入尚未覆盖所有成果族；下一批应先形成可审计的阶段写入清单，再选择一个未收敛成果族。白模真实上传继续等待用户授权。
