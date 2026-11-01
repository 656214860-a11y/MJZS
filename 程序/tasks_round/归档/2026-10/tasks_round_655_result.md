# R655｜修复轮：模型密钥测试隔离

## 开工三问与验证档位

1. 本轮只处理 `NamedKeyTests` 未安装替身 DPAPI 保护器、在受限主机上直接调用真实保护器的问题。
2. 测试仍只对临时目录执行加密写入；不读取、输出或修改用户的真实密钥与环境配置。
3. 目标是使具名密钥的保存、覆盖和读取测试沿用同文件既有的测试保护器模式。

本轮改动涉及 1 个模块，按分级规则执行默认冒烟 + `--affected model_pool`，跳过架构门禁和全量，理由：只调整单模块测试隔离，不触及生产代码、导入关系、启动路径、用户数据格式、L0 契约或删除路径。

## 改动文件清单

- `tests/test_model_pool.py`：`NamedKeyTests` 在每个用例前安装既有的测试 DPAPI 保护器。

确认：所有密钥写入只发生在临时目录；未读取、输出或修改用户数据。

## 验证原始输出片段

### 定点回归

命令：`D:\\漫剧制作助手\\运行环境\\Python\\python.exe -B -m unittest tests.test_model_pool.NamedKeyTests`

```text
Ran 5 tests in 0.024s
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
定向：忽略增量台账，执行 1 个匹配测试文件
共 59 条用例，4.7 秒；0 个文件有红
ALL TESTS PASSED
✅ 门禁 run_selftests.py（定向：model_pool）：6 秒 → 0 个文件有红
```

备注：定向自检的增量台账临时文件被受限环境拒绝写入；工具明确标注“不影响结果”，且完整测试汇总已取得。

## J 后续

- R654 的生产读取优先级修复由本轮的完整 `model_pool` 定向回归覆盖；R654 本身仍按其已发生的门禁失败保留未验收记录。

## 自审

是：只隔离具名密钥测试对真实 DPAPI 的依赖，未处理其他失败项。
