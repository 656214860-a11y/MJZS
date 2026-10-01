# UI 组件契约

本文件定义项目可复用 UI 组件的唯一写法。组件的颜色、间距、圆角和字体均引用 `design_tokens.md`；页面不得自行变体。

## 主按钮

| 属性 | Token / 规则 |
| --- | --- |
| 背景 | `color.primary` |
| 文字 | 白色 |
| 圆角 | `radius.md` |
| 内边距 | `padx=space.lg`，`pady=space.sm` |
| 悬停 | `color.primary.subtle` |
| 禁用 | 背景 `color.border.default`，文字 `color.text.muted` |

用于页面的首要、提交、确认动作；同一操作组最多一个主按钮。

## 次按钮

| 属性 | Token / 规则 |
| --- | --- |
| 背景 | `color.background.card` |
| 边框 | 1px `color.border.default` |
| 文字 | `color.text.primary` |
| 圆角 | `radius.md` |
| 内边距 | `padx=space.lg`，`pady=space.sm` |

用于次要、返回、刷新等不应抢占主动作视觉层级的操作。

## 卡片

| 属性 | Token / 规则 |
| --- | --- |
| 背景 | `color.background.card` |
| 边框 | 1px `color.border.default` |
| 圆角 | `radius.lg` |
| 内边距 | `space.lg` |

卡片承载一个完整的信息或操作单元；同一卡片内的标题、正文与辅助文字分别使用对应字体 token。

## 输入框

| 属性 | Token / 规则 |
| --- | --- |
| 背景 | `color.background.card` |
| 边框 | 1px `color.border.default` |
| 圆角 | `radius.md` |
| 内边距 | `padx=space.md`，`pady=space.sm` |
| 正文 | `font.body` + `color.text.primary` |
| 提示/辅助 | `font.assistive` + `color.text.secondary` |

## 下拉框

所有 `ttk.Combobox` 由 `ui_widgets.setup_styles(root)` 作为唯一样式入口。字段、只读态、弹出列表、字体、边框与内边距使用 `design_tokens.md` 的 `combobox.*` token；页面只负责选项、数据绑定和必要的内容宽度，不得复制颜色或字体配置。

## 文字组件

| 组件 | 使用时机 | 规则 |
| --- | --- | --- |
| `HintLabel` | 输入空态、图标旁短提示 | ≤20 字，次级灰、常规辅助字号。 |
| `DescriptionBlock` | 功能说明、按钮下方、区块底部 | ≤60 字，自动折行并保留较宽行距。 |
| `ProgressLabel` | 状态栏、页面底部进度 | 单行优先、≤40 字，使用主色强调。 |

三者的唯一构建入口为 `ui_widgets.py`，并只消费 `ui_tokens.py` 的 `TEXT_HINT`、`TEXT_DESC`、`TEXT_PROGRESS`。页面不得直接为 `ttk.Label` 设置 `foreground` 或 `font` 来替代这些语义组件。

## 弹窗

| 组件 | 使用时机 | 规则 |
| --- | --- | --- |
| `BaseDialog` | 任何新建的应用内弹窗 | 统一标题栏、内容区、底部动作区、`transient`、`grab_set`、Esc 关闭、首个可交互控件聚焦与销毁时释放 grab。 |
| `FormDialog` | 用户填写或编辑字段 | 继承 `BaseDialog`；表单字段放入 `content`，提交／取消必须用 `add_form_actions()`。 |
| `ConfirmDialog` | 询问、删除或不可逆确认 | 继承 `BaseDialog`；调用方经 `result`／`on_result` 接收确认态，危险主操作使用 `color.danger`。 |

业务页禁止新建裸 `tk.Toplevel(...)` 作对话框；已有历史弹窗按独立轮次迁移，不在一次组件改造中批量替换。

## 复用规则

每个组件只能有以上一种写法。新增页面必须复用既有组件实现或先扩展本契约；不得在页面内复制、修改样式参数形成第二种写法。

`Toplevel` 弹窗与普通页面遵循完全相同的 token 和组件规则：标题、内容区、输入框和操作按钮均不得退回通用 ttk 样式。主按钮悬停为浅主色底加主色文字；次按钮悬停同样保持可读的主色文字。
