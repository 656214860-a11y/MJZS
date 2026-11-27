# R4601 解开媒体控件与缩略图缓存的导入环
<!-- round-evidence: {"commit_base": "7e1f1455a", "credential_hits": 0, "evidence_sha256": "6f39172b9ea84382", "exit": 0, "failed": 0, "passed": 49, "round": 4601, "tests": "run_selftests.py -k test_asset_thumbs test_no_circular_import"} -->

在已有图标绘制模块画播放与波形标记，缩略图缓存继续持有图片。媒体面板和缩略图缓存无需互相导入。
