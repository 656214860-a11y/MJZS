# Round 151 结果：剧本命名、兼容导入与结构页目录栏

类型：功能轮  
日期：2026-09-26

## 交付

1. `script_contract.py` 新增统一命名器：新自然剧本、结构剧本分别采用
   `项目名_自然剧本_文件内容_年月日.md`、`项目名_结构剧本_文件内容_年月日.md`。
2. 既有 `01剧本准备` 与历史 `writing` 文件继续可读；同一相对路径时当前阶段原稿优先，或字节内容相同则只保留一条，避免结构剧本页重复导入。
3. `desktop.py` 将结构剧本上下内容框的目录栏改为水平 `Panedwindow`，用户可拖动中间分隔条调整目录栏宽度；左侧阶段栏宽度缩短约三分之一。
4. 结构页在仅存在旧 `script_raw.md` 的历史项目中仍将已解析的输入加入目录栏，不因去重遗漏当前预览。

## 数据安全与指定路径核对

- 已核对指定项目：`01剧本准备/Anthropic/cladue--opus-5.5/创意_20260925/剧本准备_自然剧本_第01-05集_20260925.md` 存在；对应 `writing/...` 路径不存在。
- 因不存在可回收的重复副本，本轮未删除、移动或重命名用户项目文件；原稿保持不变。

## 验证

- `tests.test_script_structure`：12/12 通过。
- `tests.test_idea_chat`：56/56 通过。
- `tests.test_ui_edges.UiEdgeTests.test_script_structure_page_shows_source_and_output_in_separate_boxes`：1/1 通过。
- `py_compile script_contract.py idea_chat.py desktop.py`：通过。
- 默认 `smoke_test.py`：8/8 通过。

## Reviewer 结论

通过。新命名仅影响后续保存；历史文件为兼容读取，不会反向复制到旧 `writing`，也不会自动改写或删除原稿。界面测试同时锁定文件名简显与可拖动目录栏，未引入重复路径回归。
