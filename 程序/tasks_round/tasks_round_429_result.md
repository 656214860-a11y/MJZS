# R429 结构治理轮：结构剧本发布边界

- **范围**：执行 R418 J-1 / K 的下一项，只为结构剧本产物补发布失败与唯一发布者保护；不改生产模块、阶段完成事件、用户数据、配置、缓存或白模上传。
- **改动**：`tests/test_script_structure.py` 新增发布失败回归：底层 `save_text` 失败时，`artifact_lineage.record()` 不得被调用。新增 `tests/architecture/test_structured_script_write_boundary.py`，锁定 `stage_exec` 只能委托 `script_contract.write_structured_script()`、不得直接写入，且服务内保存先于血缘记录。
- **文档**：`AGENTS.md` 架构门禁清单登记该测试，架构基线同步为 21 个文件、39 项检查。
- **验证**：`python -m unittest tests.test_script_structure tests.architecture.test_structured_script_write_boundary` **16/16** 通过；`python smoke_test.py --architecture` **39/39** 通过（15.811 秒）；`python smoke_test.py` **8/8** 通过。
- **欠账**：全阶段统一写入仍须按成果族分批收敛；白模真实上传继续等待用户授权，未尝试外部上传。
