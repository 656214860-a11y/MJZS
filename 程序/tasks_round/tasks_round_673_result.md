# R673 修复轮——三虎聊天框多显示器定位错误

## 开头三问与验证档位

1. 本轮属于修复轮：仅修复三虎聊天框在副屏时被主屏边界钳制的问题。
2. 已新增定位回归并完成声明档位内验证：默认冒烟与 `--affected pet_cloud` 均通过。
3. 未改变用户数据、配置、密钥、主窗口或其他弹窗；生产代码仅改 `pet_cloud.py`，测试仅在既有 `tests/test_pet_cloud_contract.py` 增加回归断言。

本轮改动涉及 1 个生产模块（`pet_cloud.py`），按分级规则执行默认冒烟 + `--affected pet_cloud`，跳过架构门禁与全量，理由：仅调整三虎聊天框自身定位，未触及契约、路径、启动或删除。

## 第一部分：只读诊断

### 1. 创建与定位代码

三虎聊天框是 `pet_cloud.Cloud` 的无边框 `Toplevel`，创建于 `pet_cloud.py:345-387`：

```python
def build(self):
    ...
    win = tk.Toplevel(self.parent)
    win._drama_cloud = True
    win.overrideredirect(True)
    ...
    self.win, self.canvas = win, canvas
```

修改前，实际摆放入口为 `pet_cloud.py:1219-1229`：

```python
def _place_window(self):
    if self.win is None:
        return None
    left, top = self._origin()
    self.win.geometry('+%d+%d' % (int(left), int(top)))
    return left, top
```

`_origin()`（修改前 `pet_cloud.py:1161-1184`）按三虎贴片脸颊计算原点，并调用屏幕边界钳制。`_work_right()` 和 `_screen_height()` 分别在 `pet_cloud.py:955-960, 996-1000` 使用：

```python
return int(self.win.winfo_screenwidth())
...
return int(self.win.winfo_screenheight()) if self.win is not None else 0
```

### 2. 原算法结论

原算法并非父窗口居中：常规位置由贴片锚点计算，钳制上界来自 `winfo_screenwidth()/winfo_screenheight()`。在 Windows 多显示器下，该值可对应主屏；父窗口在副屏（例如 `rootx=2000`）时，右边界仍按主屏宽度处理，聊天框遂被推回主屏。

虽然 `_window_rect()`（`pet_cloud.py:962-971`）读取过 `parent.winfo_rootx/rooty/width/height`，它仅在“已越界后挪进主界面”这一兜底路径使用，未参与常规定位，故不足以修复现象。

### 3. 同类算法登记（本轮不改）

项目内还发现：

- `ui_theme.py:301` 的回退工作区为 `0,0,root.winfo_screenwidth(),root.winfo_screenheight()`；其通用 `place()` 在 `ui_theme.py:303-335` 已优先使用 `MonitorFromWindow(parent or window)`，且再以父窗口中心居中。
- `desktop.py:251` 使用 `winfo_screenwidth()/height()` 决定主窗口初始尺寸，不是弹窗定位。

按范围约束，本轮未修改上述位置；`ui_theme.py` 的回退策略可另立轮次评估。

## 第二部分：修复

### 改动清单

- `pet_cloud.py`
  - 新增纯函数 `centered_popup_origin()`：使用父窗口 `(rootx, rooty, width, height)` 计算聊天框中心；若超过工作区，钳制到工作区。
  - `_place_window()` 改为取父窗口矩形与聊天框实际尺寸后调用该函数。
  - 新增 `_parent_work_area()`：在 Windows 使用 `MonitorFromWindow(parent.winfo_id(), ...)` / `GetMonitorInfoW` 取得父窗口所在显示器的工作区；系统接口不可用时，以父窗口坐标扩展回退范围，避免副屏正坐标被主屏宽度截断。
  - 父窗口宽或高 `<= 1` 时，使用 `parent.after_idle(self._place_window)` 延迟一次，不使用 `sleep`。
- `tests/test_pet_cloud_contract.py`
  - 只增加本项四条无界面回归断言；不改变生产模块数。

### 定位算法前后对比

| 项目 | 修复前 | 修复后 |
| --- | --- | --- |
| 锚点 | 三虎贴片脸颊 | 父窗口中心 |
| 显示器边界 | 聊天框自身 `winfo_screenwidth/height`，可能是主屏 | 父窗口所在显示器工作区 |
| 副屏 `rootx=2000` | 可能被主屏右边界压回 | 中心保持在副屏坐标范围 |
| 父窗口未布局 | 无专门延迟 | `after_idle` 重试，无固定等待 |

未调整聊天框尺寸、样式、动画、事件绑定或主窗口定位。

## 回归断言清单

`tests/test_pet_cloud_contract.py`：

1. 父窗口 `(2000,500,800,600)`、聊天框 `(400,300)`、副屏工作区 `(1920,0,3840,1080)`，结果 `(2200,650)`，其中心等于父窗口中心。
2. 主屏父窗口 `(100,80,800,600)` 时结果 `(300,230)`，保持原有居中预期。
3. 父窗口宽度为 `1` 时，纯计算返回 `None`；`Cloud._place_window()` 的模拟父窗口断言实际登记一次 `after_idle`，不报错也不使用固定等待。
4. 聊天框 `(2400,1200)` 大于工作区 `(1920,1080)` 时结果钳制为 `(0,0)`。

## 验证原始输出

```text
D:\漫剧制作助手\运行环境\Python\python.exe -B -m unittest tests.test_pet_cloud_contract
.......
----------------------------------------------------------------------
Ran 8 tests in 0.001s
OK
```

```text
D:\漫剧制作助手\运行环境\Python\python.exe -B smoke_test.py
通过：8 项
失败：0 项
✅ 冒烟测试通过，可以进入下一轮
```

```text
D:\漫剧制作助手\运行环境\Python\python.exe -B smoke_test.py --affected pet_cloud
共 18 条用例，1.4 秒；0 个文件有红
ALL TESTS PASSED
通过：9 项
失败：0 项
✅ 冒烟测试通过，可以进入下一轮
```

定向自检尝试写增量台账时受环境权限阻止：`维护记录/自检增量.json...tmp`，工具明确标注“不影响结果”；全部测试已取得 `ALL TESTS PASSED` 汇总。

## J. 后续

- `ui_theme.py:301` 的非 Windows/系统接口失败回退仍采用主屏尺寸；它是其他通用弹窗的潜在多显示器风险，本轮未动，建议另立统一弹窗定位轮评估。

## 自审

生产改动只在三虎聊天框定位模块 `pet_cloud.py`；未修改其他弹窗、主窗口、布局、用户数据、配置或密钥。测试文件只增添本项要求的回归断言；未夹带其他修复。
