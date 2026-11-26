# R4568 三虎切档重复播报
<!-- round-evidence: {"commit_base": "b886d288c", "credential_hits": 0, "evidence_sha256": "b09405a40cd49bea", "exit": 0, "failed": 0, "passed": 25, "round": 4568, "tests": "run_selftests.py -k sanhu_mode"} -->

REQ-UI-SIDEBAR-1 界面联查发现点猫爪会先设置控制模式，再次设置等级，同时单独播报模式及自动开关状态。现将目标等级一次应用到位，合并为一条可见反馈。直接切换、自动化开关同步及未同步的项目继续走原逻辑。
文件面板关闭时丢弃上一列表的显示上下文，下次打开重新载入。补齐项目文件入口和会员按钮位置的回归断言。
定向验证使用 test_sanhu_mode 和默认冒烟。
