# R1586：媒体阶段源变更失效核对

类型：§3.5只读诊断，含必要的临时目录验证实验，无队列ID。未改产品和正式测试，未跑重复冒烟/全量。

核对stage_completion_service：audio/edit/delivery统一使用media_scope的当前采用分镜SHA及_validate_media_completion，并核对成果SHA。复用MediaCompletionTests临时目录/探测夹具，三个阶段分别执行真实prepare/confirm/completion_evidence，原确认有效后将S01改成S02；旧完成状态拒绝，重新提交旧prepared亦抛ValueError。3阶段均通过，证据.git/media-stage-invalidation-audit.json。模拟媒体探测不代表真实内容质量；未扩称全部13阶段或上游所有变更均被覆盖。

R1585整体审计仍有效。P0-3用户明确延后；真实模型/供应商故障和账单、商用授权内容核验、剪辑软件实际导入、目标用户无协助完成率不能靠本地模拟证明。目前这些外部验收缺少资料/参与者；P1-4软件版本及导入结果已询问待答，未重复询问。当前未找到本次核对范围内的新产品缺陷，不为继续轮次而新增功能。目标不标完成；外部输入到达后按原11项标准推进。

自审通过：不修改用户原件，临时目录由测试夹具自动回收，保留结构化实验摘要；未调用付费模型。git diff --check通过。本轮无产品代码，不冒称新的完整安全回归。
