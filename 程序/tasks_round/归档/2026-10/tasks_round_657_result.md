# R657｜修复轮：剧本准备随包技能定位

## 开工三问与验证档位

1. 本轮只处理 `writing.prepare` 指向已不存在的随包编剧技能路径的问题。
2. 只改程序安装目录中的资源定位常量，不改项目内剧本、资产、用户数据或生成内容。
3. 修复目标是让剧本任务书引用当前随包的影视剧本写作技能并恢复创建流程。

本轮改动涉及 1 个模块，按分级规则执行默认冒烟 + `--affected writing`，跳过架构门禁和全量，理由：单模块资源定位修复，未触及导入关系、启动路径、用户数据格式、L0 契约或删除路径。

## 改动文件清单

- `writing.py`：剧本任务书引用当前随包的 `影视剧本写作技能/SKILL.md`。

确认：未改动用户数据、项目资产或生成内容。

## 验证原始输出片段

### 目标回归

命令：`D:\\漫剧制作助手\\运行环境\\Python\\python.exe -B -m unittest tests.test_core.ProjectsEngineTests.test_prepare_task_brief_uses_project_title`

```text
Ran 1 test in 0.019s
OK
```

### 默认冒烟

命令：`D:\\漫剧制作助手\\运行环境\\Python\\python.exe -B smoke_test.py`

```text
通过：8 项
失败：0 项
```

### 声明的定向门禁

命令：`D:\\漫剧制作助手\\运行环境\\Python\\python.exe -B smoke_test.py --affected writing`

```text
定向：忽略增量台账，执行 3 个匹配测试文件
共 24 条用例，4.4 秒；0 个文件有红
ALL TESTS PASSED
✅ 门禁 run_selftests.py（定向：writing）：6 秒 → 0 个文件有红
```

备注：定向自检的增量台账临时文件被受限环境拒绝写入；工具明确标注“不影响结果”，且完整测试汇总已取得。

## J 后续

- 若再整理随包技能目录，应保留资源定位契约或在独立迁移轮同步更新。

## 自审

是：只修正一个失效的随包技能定位，不处理其他失败项。
