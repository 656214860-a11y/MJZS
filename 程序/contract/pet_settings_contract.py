"""Shared labels for the pet settings UI, kept independent of UI modules."""
TABS = (('basic', '基础功能'), ('model', '三虎模型配置'), ('level', '自动化等级'),
        ('token', 'Token 节省'), ('budget', '预算'), ('skills', 'SKILL 管理'), ('dev', '开发信息'))

LEVEL_NOTES = {
    'hint': '只提示：三虎只报告进度，不会自行启动制作。',
    'semi': '半自动：非付费步骤自动推进；付费步骤先征求确认。',
    'auto': '全自动：按阶段规则自动推进，异常或超预算时暂停。',
}
