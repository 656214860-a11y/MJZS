# R4611 分镜预演页全量回归断言同步
<!-- round-evidence: {"commit_base": "9181472eb", "credential_hits": 0, "evidence_sha256": "e42c75f26490289c", "exit": 0, "failed": 0, "passed": 99, "round": 4611, "tests": "run_selftests.py -k test_media_page_buttons test_desktop_page_nav test_animatic_page"} -->

R4604 引入五个常驻工具条入口，旧集成用例仍要求整页最多一颗按钮。按 REQ-S04-114 验证五个入口及真实生成前后的确认条，并保留 880×600 下可见性校验。

原按钮断言更新后，实测 880×600 下锁定按钮底沿 809 像素，画布底沿 403 像素。桌面确认栏改为独立占用工作区底部，随页面显隐和销毁。覆盖滚动及离页清理。
