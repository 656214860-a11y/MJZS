# R444 结构治理轮结果

## 范围

- 来源：R418 整改路线 J3/K；修正分镜文件页的动态导入契约遗漏。
- 仅处理 `storyboard_files.py` 的分镜选择服务依赖与相应静态门禁扫描范围；未改变分镜功能、阶段启动、上传、用户项目数据或主界面“齿轮 → 设置”入口。

## 改动

- 将 `show()` 内未登记的 `importlib.import_module('storyboard_selection')` 改为既有 L2 `storyboard_selection` 的模块级静态导入，保持回调绑定与原有选择行为不变。
- 将 `storyboard_files` 加入 `test_dynamic_import_registry.py` 的真实 L4 页面扫描列表；未将 L2 服务误登记为 UI 插件。

## 验证

- `python -m unittest tests.architecture.test_dynamic_import_registry tests.test_final_viewer tests.test_file_cache`：38/38 通过。
- `python smoke_test.py --architecture`：55/55 通过。
- `python smoke_test.py`：8/8 通过。
- 全量安全自检未在本轮执行；最新可用全量基线仍为 R439 的 3,116/3,116。

## 自审与结束检查

- 通过：动态导入规则由实际页面扫描锁定，且仅改为适当层级的正常依赖，没有扩大 UI 插件登记表。
- 通过：未触及齿轮→设置入口、任何设置路由、外部服务或用户可见删除。
- 本轮为结构治理轮；项目已接续至 R445。已知阻塞数未减少，统一阶段写入总项与白模真实上传授权仍待后续轮次。
