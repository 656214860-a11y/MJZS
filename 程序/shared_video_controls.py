"""One top action bar for local and cloud generation pages."""
from tkinter import ttk
from responsive_ui import FlowBar
from platform_tools import open_path

def build(desktop,parent,is_cloud):
    row=FlowBar(parent);row.pack(fill='x',pady=0)
    desktop.button(row,'刷新镜头',desktop.refresh_video_workspace)
    desktop.button(row,'刷新白模',lambda:desktop.video.refresh_white_model() if desktop.video else None)
    desktop.button(row,'查看首帧',lambda:desktop.video.safe(desktop.video.frame))
    if not is_cloud:
        ttk.Button(row,text='启动 H3 / ComfyUI',style='Compact.TButton',
                   command=lambda:desktop.safe(lambda:open_path(desktop.app/'h3_launcher.pyw'))).pack(side='left')
        import tkinter as tk
        import project_settings
        from local_video import LocalStudio,model_name
        if isinstance(desktop.studio,LocalStudio):
            desktop.pet.auto_variable('auto_video_var')
    return row
