# UI 设计 Token

本文件是「漫剧制作助手」全部 UI 视觉取值的唯一权威。所有 Tk 页面、主题、组件与评审均以此为准。

## 颜色

| Token | 值 | 用途 |
| --- | --- | --- |
| `color.background.primary` | `#F7F8FA` | 主背景 |
| `color.background.card` | `#FFFFFF` | 卡片、输入框与次按钮背景 |
| `color.border.default` | `#E5E7EB` | 默认 1px 边框 |
| `color.text.primary` | `#1F2937` | 主文字 |
| `color.text.secondary` | `#6B7280` | 次文字 |
| `color.text.muted` | `#9CA3AF` | 弱文字、禁用文字 |
| `color.primary` | `#2563EB` | 主按钮、强调 |
| `color.primary.subtle` | `#EFF6FF` | 悬停浅色背景 |
| `color.danger` | `#DC2626` | 危险操作与错误 |
| `color.success` | `#16A34A` | 成功状态 |
| `color.warning` | `#D97706` | 警告状态 |

## 间距

所有间距只能使用下列 4px 倍数 token；不允许魔法数字。

| Token | 值 |
| --- | --- |
| `space.xs` | 4px |
| `space.sm` | 8px |
| `space.md` | 12px |
| `space.lg` | 16px |
| `space.xl` | 24px |
| `space.2xl` | 32px |

## 圆角

| Token | 值 |
| --- | --- |
| `radius.sm` | 4px |
| `radius.md` | 8px |
| `radius.lg` | 12px |

## 字体

| Token | 字体 |
| --- | --- |
| `font.title` | 微软雅黑，14px，bold |
| `font.body` | 微软雅黑，12px |
| `font.assistive` | 微软雅黑，10px |
| `font.numeric` | Consolas，12px |

## 下拉框（Combobox）

下拉框的视觉由 `ui_widgets.setup_styles(root)` 一次性应用；业务页面不得自行指定颜色、字体、边框或内边距。业务页统一使用 `SelectBox`：只读选项按 ASCII=1、CJK=2 估算最长宽度，封顶 28；空选项及可编辑框默认宽度 15。布局需要时可显式覆盖宽度。弹出列表默认最多 12 行，超出由原生滚动条承载。

| Token | 值 | 用途 |
| --- | --- | --- |
| `combobox.width` | 15 字符 | 空选项及可编辑框的默认宽度 |
| `COMBOBOX_MAX_WIDTH` | 28 字符 | 只读框自适应宽度上限 |
| `COMBOBOX_POPDOWN_HEIGHT` | 12 行 | 弹出列表默认最大行数 |
| `combobox.font` | `font.body` | 输入区和下拉列表文字 |
| `combobox.padding` | `space.sm` × `space.xs` | 字段水平／垂直内边距 |
| `combobox.field.background` | `color.background.card` | 可编辑与只读字段背景 |
| `combobox.foreground` | `color.text.primary` | 正常文字 |
| `combobox.arrow.color` | `color.text.secondary` | 下拉箭头；主题不支持时安全回退系统箭头 |
| `combobox.list.selection` | `color.primary` + `color.background.card` | 弹出列表选中项前景／背景 |

## 输入框（LineInput／TextArea）

单行输入必须使用 `ui_widgets.LineInput`，多行输入必须使用 `ui_widgets.TextArea`。组件统一占位文字、只读态和错误边框；页面仅提供字段内容、尺寸和领域校验，不得重写视觉参数。

| Token | 值 | 用途 |
| --- | --- | --- |
| `input.font` | `font.body` | 单行与多行正文 |
| `input.foreground` | `color.text.primary` | 正常输入文字 |
| `input.placeholder.foreground` | `color.text.secondary` | 占位文字 |
| `input.background` | `color.background.card` | 输入区底色 |
| `input.border` | `color.border.default` | 默认 1px 边框 |
| `input.error.border` | `color.danger` | 校验失败边框 |
| `input.padding` | `space.md` × `space.sm` | 水平／垂直内边距 |

## 文字层级

三类辅助文字只能由 `ui_widgets.HintLabel`、`DescriptionBlock`、`ProgressLabel` 构建。Tk 的 Label 没有独立行距属性，`*.linespace` 以组件统一的垂直内边距表达；页面不得自行覆写字体、颜色、折行或内边距。

| Token 组 | 用途 | 字体／颜色 | 最大内容与折行 |
| --- | --- | --- | --- |
| `text.hint` | 输入空态、图标旁短提示 | `font.assistive` / `color.text.secondary` | ≤20 字；240px 内左对齐折行；`space.xs` 行距/纵向留白 |
| `text.desc` | 功能说明、按钮下方或区块底部 | `font.body` / `color.text.secondary` | ≤60 字；560px 内左对齐自动折行；`space.sm` 行距/纵向留白 |
| `text.progress` | 状态栏、页面底部进度 | `font.body` / `color.primary` | 单行优先、≤40 字；480px 左对齐兜底折行；`space.xs` 行距/纵向留白 |

## 弹窗

弹窗仅由 `ui_widgets.BaseDialog`、`FormDialog`、`ConfirmDialog` 构建。标题栏、内容区与底部按钮区不得由业务页自行设定视觉参数；危险确认主按钮复用既有 `color.danger`。

| Token | 值 | 用途 |
| --- | --- | --- |
| `dialog.title.font` | `font.title` | 弹窗标题 |
| `dialog.content.padding` | `space.lg` | 标题、内容区的水平留白与内容区内边距 |
| `dialog.action.height` | `space.xl` | 底部按钮区最小高度 |
| `dialog.action.gap` | `space.sm` | 按钮之间的间距 |

## 通知

通知的严重级别复用既有 `color.danger`、`color.warning`、`color.success` 语义；`NotificationDispatcher` 负责将业务消息投递到既有状态栏，并只在调用方明确要求时复用系统模态提示。通知组件不新增另一套颜色或窗口 token。

## Tooltip

Tooltip 仅由 `ui_widgets.Tooltip` 建立；页面不得自行创建无边框 `Toplevel` 或复制鼠标进入／离开的延迟销毁逻辑。它用 `font.assistive`、`color.text.primary`、`color.background.card` 与 `color.border.default`，内容留白为 `space.sm` × `space.xs`，相对控件偏移为 `space.sm`。显示延迟统一为 400ms；鼠标悬停和键盘焦点进入均可触发，离开、失焦或控件销毁必须取消等待并销毁浮层。

## 表格（DataTable）

业务页通过 `ui_widgets.DataTable` 建立新表格；它统一列标题、滚动条、选择回调、按列排序和空态，页面只提供列定义、数据与领域单元格行为。

### 滚动条

标准 `ttk.Scrollbar` 的轨道、滑块、箭头和悬停色仅由 `ui_theme.apply()` 读取 `ui_tokens.py` 的 `SCROLLBAR_*` token 设置；业务页面不得为单个滚动条内联颜色、边框或另建 Style。横向和纵向使用同一视觉与 active 反馈。

| Token | 值 | 用途 |
| --- | --- | --- |
| `table.header.font` | `font.body` | 列标题 |
| `table.row.font` | `font.body` | 数据行 |
| `table.row.height` | `space.xl` | 默认行高 |
| `table.empty.padding` | `space.lg` | 空态留白 |

## 强制规则

1. 所有 `padx` / `pady` 必须取自 `space.*`；禁止魔法数字。
2. 所有颜色必须取自 `color.*`；禁止在页面或组件中内联 hex。
3. 所有圆角必须取自 `radius.*`。
4. 同一视觉层级的控件必须使用相同字体 token 与字号。
5. 新增、修改 UI 时必须先选定 token；评审必须检查本文件与 `ui_components.md` 的遵循情况。
