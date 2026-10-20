# R1766：文案轮——分镜定稿流程模板第 4 步由旧产出文件名改为 episode.json 与 assets.json（C5）

**轮次类型**：文档/文案轮（AGENTS.md §3）

**三问**：
- 测了吗？是。V1–V4 均实测。
- 三基线过了吗？未运行（AGENTS.md §3 文档/文案轮不强制全量基线；smoke_test 8/8 绿，消费者测试全部绿）。
- project_status.md 欠账少了吗？本轮不涉及欠账（纯文案对齐，不改变欠账条目）。

---

## 改动

### skills/templates/final_process_template.yaml:19
- 
ame: 写入 storyboard_final.json → 
ame: 写入 episode.json 与 assets.json
- 其余字段（index、action、needs_confirmation）不变，其它 3 个步骤不动

### tests/test_stage_templates.py:35-42
- 新增 1 个测试方法 	est_final_template_name_no_longer_mentions_legacy_storyboard_final_json
- 既有的 	est_each_canonical_stage_has_a_valid_sequential_step_template 未动

---

## V1–V4 实测

### V1（模板加载不变）
skill_templates.load_template('final') → stage_id=final, steps=4, actions 依次：review_storyboard / verify_assets / generate_final_storyboard / write_final_storyboard。步骤数与 action 均不变。✓

### V2（消费方测试）
| 测试文件 | 结果 |
|---|---|
| tests.test_skill_templates | 3/3 OK |
| tests.test_req_anchor_s02 | 11/11 OK |
| tests.test_req_s08_anchors | 19/19 OK |
| tests.test_stage_templates | 2/2 OK |

全部绿。✓

### V3（smoke）
python -B smoke_test.py → 8 个测试，0 个失败。✓

### V4（先红后绿）
- **改前红**：AssertionError: 'storyboard_final.json' unexpectedly found in … name: 写入 storyboard_final.json …
- **改后绿**：Ran 1 test in 0.000s OK
- **断言未动声明**：	est_each_canonical_stage_has_a_valid_sequential_step_template 未做任何修改，原断言全部保留。✓

---

## 剩余在役旧名清单

全仓扫描（排除 	asks_round、维护记录、升级备份、.git、__pycache__、.bak）：

| 文件:行 | 内容 | 判定 |
|---|---|---|
| tests\test_req_s07_anchors.py:648 | self.assertNotIn('storyboard_final.json', declared) | 负向断言（验证 stage_layout 不再含旧名），正确保留 |
| tests\test_stage_templates.py:39 | 'storyboard_final.json', text, | 本轮新增的负向断言，正确保留 |
| docs\stages\S07_分镜定稿.md:44 | stage_layout.STAGES 不再出现 storyboard_final.json | REQ 限制条款（声明旧名不应出现），正确保留 |

**结论**：无在役文件仍把 storyboard_final.json 当作正向产出文件名。三个命中均为负向声明/断言，无需修改。

---

## 需裁决事项

无。

## 独立验收（Claude，车道 lane_c5 内隐藏桌面真实环境直接运行）

- 范围：模板 1 行（仅 name）＋测试追加 1 条，`git diff` 逐行读过；行尾与 HEAD 一致（无 CR）。
- 测试：`test_stage_templates` 2/2、`test_skill_templates` 3/3、`test_req_anchor_s02` 11/11、`test_req_s08_anchors` 19/19；`smoke_test.py` 8/8；`smoke_test.py --architecture` 375/375。
- 变异：把模板还原为 HEAD 版本，新增断言变红（failures=1），还原后 sha256 一致并转绿。
- 执行通道：首次用 dispatch_v8 派发，Codex 经 magpie 一次完成（约 7 分钟），未降级到 harness 官方档。
- 已知瑕疵：执行方在 PowerShell 里写结果文件，`\n`、`\t` 被吞（如“ame:”“est_”），内容可读，不影响结论，未返修。
