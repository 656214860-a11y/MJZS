# R2330 结果：补回被 R2292 同步冲突误丢的 R2237 成果，U11 收口（修复轮）

## 发现
R2237（U1/U4/U8/U11/U12）已合入 master，但 R2292「同步 master 到 codex/wip-R2278」的冲突解决把其中 scripts/release_snapshot.py、tests/test_release_snapshot.py、artifact_schema.py 的 artifact_lineage 登记、发布检查单第 6 步与观察指标段、优化待办队列 U1/U4/U8/U11 状态、持久化产物版本清单都还原了。master 上 U4/U8 因此既无代码也无勾选。

## 改动
- 从 a856e718 原样补回 release_snapshot.py 与其测试、artifact_schema 登记；恢复检查单与待办队列对应段落（观察指标段同步 20% 裁定）。
- U11 收口：核实 natural_script_selection.json／skill_config.json／assets.json 现行无版本键，记入版本清单，不改磁盘格式。U1/U4/U8/U11 勾选。

## 验证
smoke_test.py --architecture 416 条 OK；run_selftests -k release artifact schema persist 过。断言未动。全量见合入后的干净检出运行。
