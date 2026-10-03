"""Choose a reference category and asset before saving managed image copies."""
from pathlib import Path
import hashlib
import tkinter as tk
from tkinter import ttk,messagebox
from agent.core import read
from asset_reference_images import CATEGORIES,EXTENSIONS,ROLE_GROUPS,classified_target,image_bytes,save_copy,attach,unbind
from ui_dialogs import FileDialog
from ui_widgets import BaseDialog, LineInput, ProgressLabel, ask_confirmation, notify


def save_images(base,aid,role,paths,active_ids,pending=False):
    base=Path(base).resolve();plan=read(base/'assets/资产清单/assets.json')
    if aid not in active_ids or aid not in plan:raise ValueError('请选择已采用分镜引用的资产编号')
    if role not in ROLE_GROUPS.get(aid.split('_')[0],()):raise ValueError('请选择该资产对应的参考分类')
    prepared=[]
    for path in paths:
        path=Path(path);raw=image_bytes(path)
        target=classified_target(base,aid,role,hashlib.sha256(raw).hexdigest(),path.suffix.lower(),plan[aid].get('name',aid),pending)
        prepared.append((target,raw))
    if not prepared:raise ValueError('请选择需要保存的参考图片')
    if not pending:return attach(base,aid,paths,role)
    count=0
    for target,raw in prepared:
        existed=target.exists();save_copy(target,raw);count+=not existed
    return count


def show(app,aid=None,role=None,pending=False,parent=None,on_saved=None):
    from stage_execution_service import sync_asset_plan
    from asset_context import scope_sources
    project=Path(app.root);base=app.asset_base()
    rows=sync_asset_plan(project,base,scope_sources(project,'adopted'),scope='adopted')
    if not rows:raise ValueError('请先采用分镜，再添加资产参考图')
    parent=parent or app.win
    win=BaseDialog(parent,'导入参考图',geometry='760x470',minsize=(620,430),modal=False,chrome=False)
    win.withdraw()
    body=ttk.Frame(win,padding=16);body.pack(fill='both',expand=True);body.columnconfigure(1,weight=1);body.rowconfigure(4,weight=1)
    prefix=aid.split('_')[0] if aid in rows else {'characters':'CHAR','scenes':'LOC','props':'PROP'}.get(app.asset_kind,'CHAR')
    category=tk.StringVar(value=CATEGORIES[prefix]);purpose=tk.StringVar();asset=tk.StringVar();destination=tk.StringVar();status=tk.StringVar()
    ttk.Label(body,text='资产类别').grid(row=0,column=0,sticky='w',padx=(0,12),pady=5)
    category_box=ttk.Combobox(body,textvariable=category,values=list(CATEGORIES.values()),state='readonly');category_box.grid(row=0,column=1,sticky='ew')
    ttk.Label(body,text='参考分类').grid(row=1,column=0,sticky='w',pady=5)
    role_box=ttk.Combobox(body,textvariable=purpose,state='readonly');role_box.grid(row=1,column=1,sticky='ew')
    ttk.Label(body,text='资产编号').grid(row=2,column=0,sticky='w',pady=5)
    asset_box=ttk.Combobox(body,textvariable=asset,state='readonly');asset_box.grid(row=2,column=1,sticky='ew')
    paths=[];choices={}
    ttk.Label(body,text='参考图片').grid(row=3,column=0,sticky='w',pady=(12,5))
    files=tk.Listbox(body,height=6);files.grid(row=4,column=0,columnspan=2,sticky='nsew',pady=5)
    def update_destination(event=None):
        selected=choices.get(asset.get())
        if not selected:destination.set('当前类别没有可绑定的资产');return
        folder=classified_target(base,selected,purpose.get(),'000000000000','.png',rows[selected].get('name',selected),pending).parent
        destination.set(str(folder));status.set('命名：'+purpose.get()+'_'+selected+'_资产名称_图片标识.png')
    def update_categories(event=None):
        selected_prefix=next(key for key,value in CATEGORIES.items() if value==category.get())
        roles=ROLE_GROUPS[selected_prefix];role_box.configure(values=roles)
        purpose.set(role if role in roles else roles[0]);choices.clear()
        choices.update({key+' · '+value.get('name',key):key for key,value in rows.items() if key.startswith(selected_prefix+'_')})
        asset_box.configure(values=list(choices));asset.set(next((label for label,key in choices.items() if key==aid),next(iter(choices),'')))
        update_destination()
    category_box.bind('<<ComboboxSelected>>',update_categories)
    role_box.bind('<<ComboboxSelected>>',update_destination);asset_box.bind('<<ComboboxSelected>>',update_destination)
    def choose_files():
        selected=FileDialog(win).open_files(title='选择参考图片（可多选）',filetypes=[('参考图片',' '.join('*'+suffix for suffix in sorted(EXTENSIONS)))])
        for value in selected:
            if value not in paths:paths.append(value);files.insert('end',Path(value).name)
    ttk.Button(body,text='选择图片…',command=choose_files).grid(row=3,column=1,sticky='e',pady=(12,5))
    ttk.Label(body,text='保存目录').grid(row=5,column=0,sticky='w',pady=5)
    LineInput(body,textvariable=destination,state='readonly').grid(row=5,column=1,sticky='ew',pady=5)
    ProgressLabel(body,textvariable=status,wraplength=690).grid(row=6,column=0,columnspan=2,sticky='w',pady=5)
    buttons=ttk.Frame(body);buttons.grid(row=7,column=0,columnspan=2,sticky='ew',pady=(12,0))
    def commit():
        try:
            if Path(app.root)!=project:raise ValueError('项目已切换，请重新打开添加窗口')
            active=sync_asset_plan(project,base,scope_sources(project,'adopted'),scope='adopted')
            count=save_images(base,choices.get(asset.get()),purpose.get(),paths,active,pending)
            if on_saved:on_saved()
            else:app.show(2)
            app.status.set(f'已保存 {count} 张分类参考图。'+('点击“批量导入参考图”完成绑定。' if pending else '已自动绑定资产。'))
            win.destroy()
        except (ValueError,OSError) as exc:notify(win, str(exc), level='error', title='保存未完成')
    def remove_refs():
        """解除参考图绑定并将受控文件移入回收站。

        按钮就摆在「保存」右边——保存是往里加、删除是从里拿掉，同一件事的两头挨着放。
        """
        try:
            if Path(app.root)!=project:raise ValueError('项目已切换，请重新打开添加窗口')
            active=sync_asset_plan(project,base,scope_sources(project,'adopted'),scope='adopted')
            target=choices.get(asset.get())
            if target not in active:raise ValueError('请选择已采用分镜引用的资产编号')
            role=purpose.get()
            now=read(base/'assets/资产清单/assets.json').get(target,{})
            roles=now.get('reference_roles',{}) if isinstance(now.get('reference_roles',{}),dict) else {}
            values=[value for value in now.get('reference_images',[])
                    if isinstance(value,str) and str(roles.get(value) or '待分类')==role]
            if not values:raise ValueError('这一项资产在「'+role+'」分类下还没有参考图')
            if not ask_confirmation(win, '解除参考图绑定',
                    '解除 '+target+' 的「'+role+'」参考图 '+str(len(values))+' 张？\n受控文件将一并移入项目回收站。',
                    dangerous=True):
                return
            unbind(base,target,values)
            if on_saved:on_saved()
            else:app.show(2)
            app.status.set('已解除 '+str(len(values))+' 张「'+role+'」参考图绑定，文件已移入回收站。')
            win.destroy()
        except (ValueError,OSError) as exc:notify(win, str(exc), level='error', title='删除未完成')
    ttk.Button(buttons,text='保存',command=commit).pack(side='left')
    ttk.Button(buttons,text='删除参考图',command=remove_refs).pack(side='left',padx=(8,0))
    ttk.Button(buttons,text='取消',command=win.destroy).pack(side='right')
    update_categories();win.update_idletasks()
    x=max(0,parent.winfo_rootx()+(parent.winfo_width()-win.winfo_width())//2);y=max(0,parent.winfo_rooty()+(parent.winfo_height()-win.winfo_height())//2)
    win.geometry(f'+{x}+{y}');win.deiconify()
