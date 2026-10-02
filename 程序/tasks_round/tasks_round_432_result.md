# R432 结构治理轮：连续性成果发布包

- **范围**：按 R431 清单处理连续性阶段的四份关联成果：台账、Markdown 人读版、共享锚点库、三元组字典；不改阶段完成发送、UI、用户资产、白模上传或其他成果族。
- **改动**：新增 `continuity_ledger.publish_bundle()`。它记录四份旧字节，逐份原子发布后复核 JSON / Markdown；任一环节失败时经 `agent.core.restore_bytes()` 恢复旧文件或受控清理未发布的新文件。`write()` 保持兼容，但只委托发布包；`write_anchors()` / `write_triplets()` 保持原有公共入口。
- **修复**：复核改为与 JSON 规范化后的台账比较，避免 Python 元组与 JSON 列表的表示差异；避免 L0 连贯性模块直接依赖 L1 缓存模块。
- **测试**：`tests/test_continuity_ledger.py` 新增四文件失败回滚回归；`test_continuity_publication_boundary.py` 锁定兼容入口不得直接保存。未放宽删除白名单或降低断言。
- **验证**：`python -m unittest tests.test_continuity_ledger tests.test_confirm_gates tests.architecture.test_continuity_publication_boundary` **40/40** 通过；`python smoke_test.py --architecture` **41/41** 通过（15.382 秒）；`python smoke_test.py` **8/8** 通过。
- **欠账**：下一成果族为首帧（媒体文件与导入/生成记录），须先厘清哪些文件是用户可见成果、哪些是内部请求状态。白模真实上传仍等待用户明确授权。
