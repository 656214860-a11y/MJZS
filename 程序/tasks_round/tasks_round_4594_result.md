# R4594 缩略图占位绘制拆分
<!-- round-evidence: {"commit_base": "397c109cf", "credential_hits": 0, "evidence_sha256": "5ca12a5778c570c1", "exit": 0, "failed": 0, "passed": 47, "round": 4594, "tests": "run_selftests.py -k test_asset_thumbs test_module_size_ratchet"} -->

将视频和音频占位图绘制移入独立模块，保留原有图片缓存和工作线程生命周期，满足每模块 1000 行的静态门禁。
