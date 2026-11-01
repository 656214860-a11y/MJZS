# R1771：修复轮——下载收件箱空格/下划线文件名归一化匹配

1. 本轮类型：§3.2 修复轮。下载收件箱按精确文件名匹配，Google Gemini 等桌面应用把任务书里的下划线文件名下成空格（如「一百块流浪记 项目设定 Google 20261021.md」），故登记目标「一百块流浪记_项目设定_Google_20261021.md」收不回下载文件。

2. 测试跑了吗、三个基线过了吗：
   - 先红后绿：新增 `tests.test_download_inbox.DownloadInboxTests.test_space_separated_download_matches_underscore_target`，改前红（done=[]），改后绿。
   - 定向回归：test_download_inbox 6/6、test_idea_download_import＋test_media_publish_streaming 22/22 全绿；test_layers＋function_size_ratchet 7/7。
   - 默认冒烟 8/8。
   - 架构门禁全量、完整安全全量：未跑（改动为纯 L2 纯函数归一化，未命中 §5 强制条件；全量由 post-commit 后台补跑）。

3. project_status.md 欠账少了吗：本轮改源码 +1（download_inbox.py），全量欠账由后台补跑清账。

## 根因
`download_inbox.match` 用 `_plain_name(path.name) == target.name.casefold()` 做精确文件名匹配。任务书登记的目标是四段式下划线名（`一百块流浪记_项目设定_Google_20261021.md`），而 Google Gemini 桌面窗口下载时把下划线换成空格（`一百块流浪记 项目设定 Google 20261021.md`），两者不等 → 永不命中，文件留在下载目录。

## 修复
`download_inbox._plain_name` 增加归一化：`re.sub(r'[\s_]+', ' ', ...)` 把连续空格/下划线合并为单个空格后再 casefold；`match` 的 key 也改用同一 `_plain_name(target.name)`。空格与下划线分隔的同一四段式文件名现可互相命中，且保留原有「 (N)」副本后缀处理。

## 校验
- 边界：副本后缀「 (1)」、纯下划线名、纯空格名均归一化一致；精确同名（既有用例）不受影响。
- 断言未动：仅新增 1 条测试，未改既有断言。

## 独立验收（advisor，主树真实环境直接运行）

- 范围：download_inbox.py（_plain_name 归一化空格/下划线 + match 的 key 同归一化）、tests/test_download_inbox.py（新增 1 条）。
- 先红证据：新增用例改前 `AssertionError: Lists differ: [] != [WindowsPath('...一百块流浪记_项目设定_Google_20261021.md')]`。
- 真实复现：台账目标 `一百块流浪记_项目设定_Google_20261021.md`，下载文件 `一百块流浪记 项目设定 Google 20261021.md`；归一化后 `_plain_name` 二者一致（含「 (1)」副本后缀也一致）。
- 定向回归：test_download_inbox 6/6、test_idea_download_import＋test_media_publish_streaming 22/22、test_layers＋function_size_ratchet 7/7；冒烟 8/8。
- 断言未动：仅新增 1 条测试，未改既有断言。
