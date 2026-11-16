"""阶段配置面板的制作锁预选弹窗（R2862 起替代总控预设工作流）。

总控机制（master_skill／master_import_service／预设套用／面板内模型选择）已整体
删除：制作锁是项目级事实（skill_config.json 的 production_locks），本模块只提供
面板入口行与弹窗编辑，读写仍走 stage_config／stage_execution_service 权威。
"""
import app_logging
import tkinter as tk
from tkinter import ttk

from contract.script_contract import PRODUCTION_LOCK_DEFINITIONS
from production_lock_fields import CompactLabel, ProductionLockFields
from ui_tokens import (CHAR_WIDTH, DIALOG_MIN_HEIGHT, DIALOG_MIN_WIDTH, SPACING,
                       STAGE_PANEL_LAYOUT)
from ui_widgets import (BaseDialog, DescriptionBlock, HintLabel, PrimaryButton,
                        SecondaryButton, notify)

DIALOG_SCREEN_MARGIN_X = SPACING['2xl']
DIALOG_SCREEN_MARGIN_TOP = SPACING['2xl']
DIALOG_SCREEN_MARGIN_BOTTOM = SPACING['2xl'] + SPACING['lg']


def dialog_working_area(widget):
    """返回对话框可用的屏幕工作区 ``(left, top, right, bottom)``。

    只按屏幕尺寸扣掉标题栏与任务栏余量，不去探测窗口管理器；测试用
    ``winfo_screenheight`` 的包装固定尺寸，不依赖本机真实分辨率。
    """
    try:
        width = int(widget.winfo_screenwidth())
        height = int(widget.winfo_screenheight())
    except tk.TclError:
        width, height = 1280, 800
    return (DIALOG_SCREEN_MARGIN_X,
            DIALOG_SCREEN_MARGIN_TOP,
            max(DIALOG_SCREEN_MARGIN_X + DIALOG_MIN_WIDTH, width - DIALOG_SCREEN_MARGIN_X),
            max(DIALOG_SCREEN_MARGIN_TOP + DIALOG_MIN_HEIGHT, height - DIALOG_SCREEN_MARGIN_BOTTOM))


class PanelWorkflowMixin:
    """Panel 的制作锁弹窗方法集（面板本体在 skill_panel.Panel）。"""

    def refresh_locks(self):
        """打开面板时把附件里的制作锁同步进项目锁；本面板已无锁行控件要刷新。"""
        try:
            project = self.project()
        except Exception:
            return {}
        try:
            import stage_execution_service
            stage_execution_service.sync_writing_attachment_locks(project)
        except Exception:
            app_logging.swallowed()
        try:
            import orchestrator.stage_config as stage_config
            return stage_config.workflow_lock(project)
        except Exception:
            return {}

    def refresh_lock_hint(self):
        """入口行右侧的小字：已填几项制作锁。"""
        hint = getattr(self, 'lock_hint', None)
        if hint is None:
            return ''
        try:
            import orchestrator.stage_config as stage_config
            values = stage_config.workflow_lock(self.project())
        except Exception:
            values = {}
        filled = sum(1 for item in PRODUCTION_LOCK_DEFINITIONS
                     if str(values.get(item['key']) or '').strip())
        text = ('已填 %d 项' % filled) if filled else '未填写'
        hint.configure(text=text)
        return text

    def build_lock_entry(self, pad, parent=None):
        """制作锁入口行：标签＋「预选制作锁…」按钮＋已填计数。"""
        row = ttk.Frame(parent or self)
        row.pack(fill='x')
        CompactLabel(row, text='制作锁', style='Muted.TLabel',
                     min_px=getattr(self, 'label_px', 0)).pack(side='left')
        self.lock_button = SecondaryButton(row, text='预选制作锁…',
                                           width=CHAR_WIDTH['2xl'],
                                           command=self.open_lock_dialog)
        self.lock_button.pack(side='left',
                              padx=(STAGE_PANEL_LAYOUT['field_gap'], SPACING['sm']))
        self.lock_hint = HintLabel(row, text='')
        self.lock_hint.pack(side='left')
        self.refresh_lock_hint()
        return row

    def open_lock_dialog(self):
        """制作锁弹窗预选：全部契约定义，保存走 stage_execution_service 权威。"""
        try:
            project = self.project()
        except Exception as exc:
            notify(self.winfo_toplevel(), str(exc), title='制作锁预选',
                   status=getattr(self.desktop, 'status', None), modal=False)
            return None
        import orchestrator.stage_config as stage_config
        current = stage_config.workflow_lock(project)
        window = BaseDialog(self.winfo_toplevel(), '制作锁预选', modal=False, chrome=False)
        window.resizable(True, True)
        body = ttk.Frame(window, padding=SPACING['md'])
        body.pack(fill='both', expand=True)
        DescriptionBlock(body, text='制作锁是项目级事实（故事画幅／视频模型／交付形态等），'
                                    '简报门禁与各阶段发送门禁共用这份取值；留空的项不参与必填判定。'
                                    ).pack(anchor='w', pady=(SPACING['none'], SPACING['sm']))
        holder = ttk.Frame(body)
        holder.pack(fill='both', expand=True)
        fields = ProductionLockFields(holder, definitions=PRODUCTION_LOCK_DEFINITIONS)
        fields.set_values(current)
        fields.pack(fill='x')
        actions = ttk.Frame(body)
        actions.pack(fill='x', pady=(SPACING['sm'], SPACING['none']))

        def save():
            from stage_execution_service import save_writing_production_locks
            try:
                save_writing_production_locks(project, fields.values())
            except Exception as exc:
                notify(window, '制作锁保存失败：%s' % exc, title='制作锁预选',
                       status=getattr(self.desktop, 'status', None), modal=False)
                return
            if getattr(self, 'state', None) is not None:
                self.state.configure(text='制作锁已保存。')
            self.refresh_lock_hint()
            window.destroy()

        PrimaryButton(actions, text='保存', width=CHAR_WIDTH['xl'],
                      command=save).pack(side='left')
        SecondaryButton(actions, text='取消', width=CHAR_WIDTH['xl'],
                        command=window.destroy).pack(side='right')
        return window
