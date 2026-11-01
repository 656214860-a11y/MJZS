# R1816 结果（整理轮）

- 新增整页差分测试 tests/test_asset_page_equivalence.py、tests/test_script_structure_page_equivalence.py（旧实现原样内嵌，含一次预热会话消除首窗布局差）。
- AssetPagesMixin.assets → _AssetPage；ScriptPagesMixin.script_structure → _ScriptStructurePage（c2c 原样改写）。
- 删除 assets（嵌套 6、长度 223）、script_structure（长度 244）、AssetPagesMixin 类上限登记；test_stage_workspace_boundary 改为同时扫描薄方法与 _AssetPage（len==2），断言未动；skip 台账补两条。
- 验证：-k asset_page_equivalence script_structure_page_equivalence asset script_structure static_names architecture，仅剩常驻红 test_round_number_continuous。
