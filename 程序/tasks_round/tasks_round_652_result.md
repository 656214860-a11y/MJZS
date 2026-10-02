# R652｜修复轮：SKILL 清单落盘行尾保护

## 开工三问与验证档位

1. 本轮只处理 `skill_tools.py` 的 `delivery.exportManifest` JSON 落盘未接入 `line_endings` 的问题。
2. 修改后的清单仍写入调用方指定或项目内的 `交付清单.json`，内容与路径契约不变；仅统一原子写入时的行尾校验。
3. 目标是让唯一文本写入点使用项目既有 `line_endings.write_text`，避免 CR CR LF 回归。

本轮改动涉及 1 个模块，按分级规则执行默认冒烟 + `--affected skill_tools`，跳过架构门禁和全量，理由：单模块内部文本落盘适配，未触及导入关系、异常边界、启动路径、用户数据格式、L0 契约或删除路径。

## 改动文件清单

- `skill_tools.py`：`delivery.exportManifest` 改由 `line_endings.write_text` 以 UTF-8 JSON 格式原子落盘。

用户数据、项目资产与既有清单内容均未改动。

## 验证原始输出片段

### 定点回归

命令：`D:\\漫剧制作助手\\运行环境\\Python\\python.exe -B -m unittest tests.test_line_endings`

```text
Ran 15 tests in 0.289s
OK
```

### 默认冒烟

命令：`D:\\漫剧制作助手\\运行环境\\Python\\python.exe -B smoke_test.py`

```text
通过：8 项
失败：0 项
```

### 声明的定向门禁

命令：`D:\\漫剧制作助手\\运行环境\\Python\\python.exe -B smoke_test.py --affected skill_tools`

```text
定向：忽略增量台账，执行 0 个匹配测试文件
共 0 条用例，0.0 秒；0 个文件有红
❌ 门禁 run_selftests.py（定向：skill_tools）：定向筛选未命中任何测试
```

## [TASK_FAILED]

声明档位中的 `--affected skill_tools` 未命中测试文件，依失败判定本轮不得验收。代码级定点回归与默认冒烟虽通过，不能替代该门禁。

## J 后续

- 下一独立轮次应仅补充 `skill_tools` 的可发现测试映射，并重新按其自身声明的档位验证；不得在本轮补跑或改写档位。

## 自审

是：代码改动只涉及该项；失败原因是测试发现性，不夹带修复其他失败项。
