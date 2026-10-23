# R1949 结果：剧本页有聊天记录时首绘不再先放示例、再跳成历史（修复轮）

## 背景
用户真机反馈：剧本准备页的聊天气泡先弹出默认示例，再跳成历史记录，前后不一致。（同一次反馈的“换页瞬间空白”，用户当时运行的是 master 851818a0，不含 R1945；用户先用工作树版本复测，本轮不动换页。）

原因：REQ-S01-22 规定 `writing()` 首绘只放示例气泡，布局稳定后 `show_conversation()` 再整份重绘真实历史。首次进入项目时还要等后台线程解析模型键，期间 `rows=[]` 也被当作“没有历史”画示例。有历史的项目因此必然经历“示例 → 历史”的跳变。

## 改动
- `idea_chat.py`：新增 `has_history(context, gateway)`，只读，不做迁移。它复用 `_read_rows` 的 mtime 缓存，后续 `load()` 不会多解析一次。
- `desktop_idea_deferred.py`：
  - `show_example_bubble(loading=None)`：有记录时首绘只放一行灰色的“正在读取聊天记录…”，标签为 `bubble_loading`，不是示例，不参与复制和编辑；没有记录时照旧放示例。
  - 新增 `idea_history_expected()`：同一项目在本次运行内只问一次盘，之后以 `show_conversation` 实际读到的结果为准。
- `desktop_idea_chat.py::show_conversation`：
  - 模型键还没回来、项目又有记录时，继续放读取提示，不画示例；
  - 读到结果后记下这个项目是否有记录；
  - `IdeaChatMixin` 类体量保持在登记上限 770 行内。

## 契约
- 用户已批准改 REQ-S01-22 的两条用例。实际改动收得更窄：没有聊天记录的项目，首绘仍是示例，所以 `test_writing_defers_idea_updates_and_shows_example_first` 和 `test_real_project_chat_shows_independent_content_before_model_key` 两条原用例都没有改，并且照旧通过。断言未动。
- 新规则只覆盖有记录的项目：首绘放读取提示，由新用例守护。

## 测试（经 `工作流任务/gui_hidden.py` 在隐藏桌面运行）
- 新增 `tests/test_idea_history_first_paint.py`，3 条全部通过：
  - `has_history` 能区分有无记录；
  - 有记录的项目在模型键慢解析的全过程中从不出现示例，最终显示历史，读取提示被清掉；
  - 没有记录的项目仍先出示例，且在 `CHAT_FIRST_TEXT_SECONDS` 内出现。
- 跑过的测试组：`-k idea slowpage desktop_startup_perf writing script_page architecture complexity function_size skip coverage copy`。复杂度修正后用 `-k complexity idea_history_first_paint` 复跑，全部通过。
- 其余红项都是旧红，不是本轮引入：
  - `architecture.test_copy_entry_boundary` 和 `test_copy_rules`：两条都指向 `desktop_account_page.py`，R1925 引入；
  - `architecture.test_round_baselines`：1939 ≠ 1949，状态页只在 master 改，分支上必红。
- 未运行：smoke、全量。
- 真机观感需要用户确认：有聊天记录的项目进入剧本页时，应该先看到读取提示，再直接出历史，中间不出现示例。
