# R1810：结构治理轮——压平 storage_maintenance.source_protection，并补 42 种夹具的差分测试（批次 D-1）

1. 本轮类型：§3 结构治理轮（只重构，不改行为）。这是批次 A 里因“缺回收站测试”被搁置的一项，先补测试再改。

2. 测试与基线：
   - 新增 `tests/test_source_protection_equivalence.py`：旧实现原样内嵌，与新实现在 42 个夹具上逐例对照 `(受保护文件集合, 报错列表)`。夹具以一份完整项目（资产清单、来源旁证链、商业声明、成片来源清单、两种位置的生成台账、回收站里的干扰清单）为底，叠加 41 种变异：清单损坏／标量／列表、旁证链与断尾、台账缺镜头表／版本列表非列表／版本非对象／版本号为浮点或布尔或缺失／全部未结算／锁定／创建时间无效／输出目录非字符串或越界或指向根、成片来源清单各种坏行与坏 JSON 与老文件名、保留期策略 0／文本／坏 JSON／1 天／3650 天、空项目。测试自身断言对照不是“空对空”：至少 20 个夹具有受保护文件、至少 10 个夹具有报错。另一条用默认 `now` 对照。
   - 先按“已有测试 + 新差分测试”确认旧实现通过，再改写；改写后差分、`test_storage` 与架构门禁共 403 条：除 `test_round_number_continuous`（分支上状态页轮次头只能在 master 更新）外全绿。
   - 完整安全全量：本轮未跑。

3. project_status.md 欠账：本轮改源码 +1。

## 改了什么
| 位置 | 内容 |
|---|---|
| `storage_maintenance.source_protection` | 内部闭包 `collect` 提成模块级 `_collect_sources`（早返回压平）；台账分支提成 `_protect_ledger`（版本规则打包成一个元组，参数 8→5）；成片来源清单检查提成 `_check_export_manifest`；旁证追踪循环提成 `_chase_receipts`。主函数嵌套 7→4 |
| `test_complexity_ratchet.py` | 删 `source_protection` 与（随闭包一起消失的）`collect` 两条嵌套登记 |

## 没做
`storage_summary`（嵌套 6）与同文件其余函数留着：改它需要的是容量统计口径的行为测试，而不是结构对照。
