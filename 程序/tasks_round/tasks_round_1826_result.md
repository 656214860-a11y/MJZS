# R1826 结果（功能轮）：三虎主动提问精简，回答接得上

## 改动
- pet_ui_voice.offer_text：只说头一件缺口和总件数，去掉“阶段 → 手动xxx”导航与括号说明；上限 OFFER_MAX_CHARS=60。
- offer_oneclick：问了没人理时重问间隔翻倍（最多 OFFER_BACKOFF_MAX=8 倍，约 2 小时）；缺口变了就复位；答“先不用”后同一批缺口不再追问（原来清空 _offer_at 会更快再问）。
- offer_verdict：除整句词表外，认“不用了谢谢”“好啊做吧”这类以答词起头的说法；“是什么意思”等问句不算点头。
- Agent.context：挂着的提问写进 pending_offer，模型抽意图时知道用户在回哪个问题。
- pet_cloud_text.reply_lines：单条回答超过 REPLY_MAX_CHARS=80 收成一句加“…（详情见进度面板）”。
- 新增 tests/test_pet_offer_brevity.py（6 条）。断言未动；提问仍用绿色对话框（回复框在里面）。

## 验证
- run_selftests.py -k pet_ui pet_agent pet_cloud sanhu：714 条，0 红。
- run_selftests.py -k pet_offer_brevity：6 条，0 红。
- smoke_test.py --affected pet_ui_voice pet_cloud_text pet_agent pet_ui_support：8 项过，1 项红——test_skills 2 条（SKILL 计数 71≠73），为本 worktree SKILL gitlink 为空的已知环境缺口，与本轮改动无关；未在完整副本复跑。
- 未跑全量。
