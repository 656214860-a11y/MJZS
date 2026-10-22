# R1820 结果（整理轮）

- 新增差分测试 tests/test_flatten_flourish_open_cell.py：旧实现原样内嵌，用记账替身对照
  - pet_ui_support.flourish：8 种姿势（含未知与 None）× 4 个步数 × 2 组偏移，逐次对照画布调用
  - _AssetPage.open_cell：9 列 × 2 种资产状态，对照调用顺序与参数；对改名框，再调一次它的保存回调，对照 registry 的结果
- 压平：flourish 的 elif 长链改成「各分支画完就 return」；open_cell 的 #1／#2 分支改为画完 return，#3 的内层 if 并进条件。两者都从嵌套 6 层降到上限以下，删除 NESTING_CAPS 两项（flourish 的 9 个参数没动，PARAM_CAPS 保留）。
- 变异检查：两处各改一个值，2 例都变红。断言未动。
