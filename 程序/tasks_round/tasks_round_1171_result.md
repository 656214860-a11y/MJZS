# R1171 HOLLMWOOD 四角色规则去重

- 类型：按用户任务书进行规则文案契约变更，保留角色职责、交接与审核。
- 测试：指定定向 68/68；指定 smoke_test.py --gate 251/251，冒烟 9/9（默认 8 项）。全量验证待干净提交后执行，不将历史 R1160 冒充本轮通过。
- 欠账：本次重复写作规则和硬编码冲突已移除；历史待办不变，无匹配队列 ID。

## 改动及边界

hollmwood_rules.py 删除详细节奏、20 字和 60–90 秒限制，字数引用所选 SKILL、单集时长引用 brief 单集时间。保留演员不改结局卡点的边界，导演 APPROVED/REVISE、动作可视化与行为连贯要求。结构化输出禁令只在编剧职责中保留一次。单窗口 Gate 1~2/3~5 分工改为通用 SKILL 职责引用。

rhythm_template.yaml 保留 name/template_id/version，rules/constraints 为空映射，注释指向 SKILL 与 brief。load_rhythm_template 仅返回文本，空规则不报错，无需修改。当前 HOLLMWOOD 源码没有 100 秒硬编码，因此未臆造第二处修改。

未改 ROLE_ORDER、MAX_REVISIONS、hollmwood_roles.run 串行与审核往返、SKILL 正文或 brief 契约。现有用户修改和并行任务保留。

## 断言变更登记

- test_stage_prompt_governance：两条 Gate 1~2/3~5 正向断言分别替换为导演/编剧引用所选 SKILL 的完整职责文案；五角色规则各出现一次等既有断言保留。
- test_hollmwood_agent_delivery：首发/续发新增 SKILL 字数、brief 时长、APPROVED/REVISE 正向断言；新增旧指标/模板键/Gate/反形容词缺席与结构化禁令仅一次断言。
- test_hollmwood_roles：模板路径断言保留，补充模板元数据及空规则的完整非注释内容校验。
- 首次新增测试误用环境未安装的 yaml 库，失败 1 项；改为读取本身的非注释行契约，不新增依赖；指定定向复测 68/68。未删除验收断言。

## 提交与验证回执

当前为全量前干净检查点；最终结果与实现哈希在验证后补记。未运行真实模型，未重启应用，未 push。

中央编号因并行任务推进，R1167 提交遭 hook 拒绝后在干净工作树重新领取 R1171；此前全量被脏树前检拒绝，未执行测试。
