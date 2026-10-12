# R1398 结果 — 剧本准备阶段「作为确认输出文件」右键入口

- 本轮属于 §3 哪种类型？ **功能轮（§3.1）**。
- 测试跑了吗？三个基线过了吗？ 定向 --affected writing_api stage_execution_service desktop idea_chat preparation_confirmation = 9/9、0 文件有红（283 秒）；默认冒烟 8/8；架构门禁 smoke_test.py --architecture = 325/325 绿。全量未跑（未触发 §5 升级条件：未改启动路径、Tk 控件生命周期、删除语义、_layers.py 登记表）。
- project_status.md 的欠账少了吗？ **未变**：本分支非 master，状态页只能由 master 提交，轮次头需在 master 侧同步为 R1398+1。

## 做什么

用户改过阶段文件正文后，原确认记录（路径/SHA256）即失效，对话路径会以
「文件已删除或修改，原确认失效」拒发。新增显式入口把**磁盘上的当前文件**登记为该阶段的确认输出：

- L2 writing_api.confirm_preparation_document(project, stage, path, *, publish)：按当前正文重算 SHA256，写 working 集合（有 evision 时写 evision.documents），不改文件本体；返回本次失效的下游阶段元组。
- L3 stage_execution_service.confirm_writing_preparation(project, stage, path)：注入 publish_stage_text，桌面不直接写确认台账。
- L4 desktop.script_menu：项目设定／剧本大纲／角色卡三列右键新增「作为确认输出文件」（项目剧本列不适用），执行前二次确认并说明会清除其后确认记录。

## 边界与不变量

- 不执行 estart_preparation 语义之外的替换：只登记选中文件，不删除、不移动任何文件。
- 不跳阶段：前置阶段未确认时拒绝登记（与既有「不能跳阶段」一致）。
- 只接受剧本准备目录内的非空文件（路径权威：stage_path_service.write_dir）。
- 架构统一基数第四项 3 处 point 随行号位移重钉为 1050／1081／1097。

## 验证与提交

- 新增 	ests/test_preparation_confirmation.py（5 条）：复现用户现场（记录指向已搬走旧稿 → 登记现有文件后校验恢复通过）、下游失效回报、前置未确认拒绝、越界路径拒绝、空文件拒绝。
- 本轮已提交：是（本文件与代码同批提交，commit hash 见本轮提交）。

---