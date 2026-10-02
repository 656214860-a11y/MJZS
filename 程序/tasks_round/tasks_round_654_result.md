# R654｜修复轮：模型密钥迁移后的新值读取

## 开工三问与验证档位

1. 本轮只处理旧 `private/.env` 密钥迁移后保存新密钥时，按名称读取结果仍为旧值的回归。
2. 改动不得写入真实用户密钥；所有验证使用测试的临时目录与替身加密器。
3. 修复目标是让同一密钥名在“迁旧后新存”场景读取新值，保留旧文件全部成功加密后才删除的恢复语义。

本轮预计改动集中在 1 个模块，按分级规则执行默认冒烟 + `--affected model_pool`，跳过架构门禁和全量，理由：单模块密钥解析/保存顺序修复，未触及导入关系、启动路径、用户数据格式、L0 契约或删除路径。

## 改动文件清单

- `model_pool.py`：同名密钥读取优先使用程序本机 DPAPI 存储，确保迁旧后新保存的值不被进程环境中的旧同名值覆盖。

确认：未读取、输出或改动任何真实用户密钥；测试使用临时目录和替身加密器。

## 验证原始输出片段

### 目标回归

命令：`D:\\漫剧制作助手\\运行环境\\Python\\python.exe -B -m unittest tests.test_model_pool.EnvKeyTests`

```text
Ran 4 tests in 0.026s
OK
```

### 默认冒烟

命令：`D:\\漫剧制作助手\\运行环境\\Python\\python.exe -B smoke_test.py`

```text
通过：8 项
失败：0 项
```

### 声明的定向门禁

命令：`D:\\漫剧制作助手\\运行环境\\Python\\python.exe -B smoke_test.py --affected model_pool`

```text
test_model_pool#3              5 条     0.1 秒  ✗ 2
ValueError: Windows 无法读取或保存模型 API Key，请在当前用户下重新保存。
❌ 门禁 run_selftests.py（定向：model_pool）：6 秒 → 退出码 1
```

单独运行完整模块确认错误来源为 `NamedKeyTests` 的两项真实 DPAPI 调用，不是本轮迁旧用例：`Ran 59 tests ... FAILED (errors=2)`。

## [TASK_FAILED]

声明的 `--affected model_pool` 门禁未通过。目标迁移回归和默认冒烟通过，但依失败判定本轮不得验收。

## J 后续

- 独立处理 `NamedKeyTests` 在无可用 Windows DPAPI 环境中直接调用真实保护器的测试隔离问题；不得在本轮继续修改。

## 自审

是：只修复迁旧后新值读取优先级；定向门禁发现的 DPAPI 测试隔离问题已登记为后续。
