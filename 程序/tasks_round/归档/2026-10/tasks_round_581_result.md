# R581｜修复轮｜全局按钮悬停尺寸收敛

## 本轮回答

1. 本轮是修复轮，不是整理轮。
2. 测试已运行：`test_ui_theme` 10/10、受影响 desktop 7/7、默认冒烟 8/8 均通过；架构门禁与全量安全回归未因本次纯样式修复重复运行。
3. `project_status.md` 的结构债务未减少；R568/P3-2 与 P0-3 阻塞项不变。

## 根因与复现

- `ui_theme.apply()` 为默认 `TButton` 设定了较大的内边距；生产代码仍有约 100 处直接 `ttk.Button(...)`，不会走仅配置 `Tokens.*` 样式的 `PrimaryButton`／`SecondaryButton`。
- 因而即使已迁移的页面缩小了 token 组件，历史直接按钮仍会在悬停时呈现过大的高亮块；逐一替换既有按钮既会扩大改动面，也无法保证漏网样式同步修复。

## 改动

| 文件 | 改动 |
| --- | --- |
| `ui_widgets.py` | 新增公共 `setup_styles(root)`；统一配置 `TButton`、`Primary.TButton`、`Secondary.TButton`、`Tokens.Primary.TButton`、`Tokens.Secondary.TButton` 的紧凑 token 内边距及可读的悬停／禁用态。保留 `_styles()` 作为组件构造的兼容别名。 |
| `desktop.py` | 在 `apply_theme(win)` 后调用一次 `setup_styles(win)`，让同一 Tk 根及其弹窗里的直接 `ttk.Button` 同步继承全局样式。 |
| `tests/test_ui_theme.py` | 增加默认、旧主按钮、旧次按钮均为 12×4 且悬停文字可读的回归。 |
| `project_status.md` | 登记本轮结果并推进轮次。 |

## 验证

| 命令 | 结果 |
| --- | --- |
| `D:\漫剧制作助手\运行环境\Python\python.exe -m unittest tests.test_ui_theme` | 10/10 通过。 |
| `D:\漫剧制作助手\运行环境\Python\python.exe smoke_test.py --affected desktop` | 7/7 通过。 |
| `D:\漫剧制作助手\运行环境\Python\python.exe smoke_test.py` | 8/8 通过。 |

## 自审

通过。只改统一的 Tk 样式安装入口、主桌面接线与对应回归；没有逐处改写按钮、没有改事件或布局结构、没有触及用户数据。相同问题已覆盖默认、历史主／次按钮和 token 组件按钮。
