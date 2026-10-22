# R1848 结果：修合并后自动全量的两处新红（修复轮）

- 背景：R1846 合并后，提交后钩子在隐藏桌面跑了自动全量（HEAD c0647784，退出码 1，用时 1075 秒）。红的测试文件：test_round_baselines（常驻）、test_root_layout／test_ui_edges／test_asset_detail／test_desktop_tray／test_video_ui（与合并前 master 对照一致，属隐藏桌面环境问题），以及两个新出现的。
- 修复：
  - `tests/test_content_box_equivalence.py`（R1832 的差分测试）：内嵌旧实现里的三按钮块换成 R1842 的 `_install_script_edit_controls` 调用（与 master aa3e2efe 一致）；点击序列的按钮文字同步为“编辑／后退／恢复”。断言未动。
  - `distribution_manifest.md`：把 master R1815 加在根目录的 `handoff-full-safe.md` 声明为开发资料排除项。
- 验证：`-k content_box_equivalence` 通过。`distribution_selfcheck` 在 D:\漫剧制作助手 本机跑时，被约 2544 个本机未跟踪文件（`.tools/` 等）拖红；干净树（.wt/ci）的自动全量只报了 handoff-full-safe.md 这一个，已补。干净树复验留给下一次自动全量。
- 已提交：本提交。未 push。
