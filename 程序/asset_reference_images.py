"""Per-asset source images, kept separate from generated/registered artwork."""

from pathlib import Path

import hashlib, re

from agent.core import read,save,save_bytes
from contract.platform_tools import open_path
from infra.pet_state import PAGE_OF

# 第 46 期第 1 条：内容框的右键菜单（查看／删除）与其它页共用同一份实现。
from cell_hover import bind_row_menu
# 第 57 期第 4 条：「参考图」那一窗的「分类」右边加一列缩略图（悬停放大也在这层图里）。
import ui.asset_thumbs as asset_thumbs
from cell_hover import CellHover,CellImages,ZOOM_SIZE
from responsive_ui import row_height_for
from ui_widgets import (SelectBox, BaseDialog, DataTable, DescriptionBlock, PrimaryButton,
                        ProgressLabel, SecondaryButton, TextArea)
from ui_tokens import TEXT_ROWS, WRAPLENGTH, SPACING

REF_THUMB=asset_thumbs.DEFAULT_SIZE          # 缩略图长边：与资产页那一列同尺寸
# 第 58 期第 2 条：行高按格子里最高的那点内容算（这一张就是缩略图）——
# 原来写死 REF_THUMB+8，现在与其他内容框同一套（responsive_ui.fit_row_height）。
REF_ROW_HEIGHT=row_height_for(REF_THUMB)



ROLE_GROUPS={'CHAR':('长相','服饰','画风','色调','氛围','姿态动作','表情','其他'),
             'LOC':('空间锚定','氛围光线','视觉特写','多角度实景','俯视布局'),
             'PROP':('多视角形态','比例与交互校验','材质与磨损','使用场景')}
ROLE_HINTS={'综合参考':'按资产提示词选择相关特征，保持已确认设定','长相':'仅参考面部、五官、发型和体态','服饰':'仅参考服装、配饰、剪裁和材质','画风':'仅参考绘画或渲染风格，不照搬人物身份和服装','色调':'仅参考配色、明暗和色彩关系','氛围':'仅参考光线、天气、情绪和环境氛围','场景布局':'仅参考空间布局和构图关系','道具造型':'仅参考道具的形状、结构和材质'}
ROLE_HINTS.update({
    '姿态动作':'仅参考人物姿态、动作幅度与肢体关系，不改身份、服装与画风',
    '表情':'仅参考面部表情与情绪状态，不改身份、服装与画风',
    '多角度实景':'参考同一场景的其他角度与远近，保持空间结构、陈设和光位一致',
    '俯视布局':'参考俯视／平面图里的空间划分、出入口与陈设位置，锁定机位与走位关系',
    '使用场景':'参考道具在使用状态下的持握、接触与搭配，保持结构和比例一致',
    '其他':'仅参考提示词明确指定的特征，不改变已确认角色设定',
    '空间锚定':'锁定场景空间布局、出入口、固定地标及人物和机位的相对位置',
    '氛围光线':'参考天气、时段、光源方向、明暗、色温和情绪氛围，保持场景空间一致',
    '视觉特写':'参考局部细节、纹理和特写构图，不据此改变整个场景结构',
    '多视角形态':'综合正面、侧面、背面等视角，保持道具轮廓、结构和部件一致',
    '比例与交互校验':'核对道具相对人物、手掌和场景的尺寸，以及抓握、接触、使用关系',
    '材质与磨损':'参考道具表面材质、粗糙度、反光、使用痕迹和磨损位置'})
CATEGORIES={'CHAR':'角色','LOC':'场景','PROP':'道具'}
# 类目在界面上按登记顺序排（第 55 期第 6 条）：「待分类」永远垫底。
ROLE_ORDER=tuple(dict.fromkeys(role for roles in ROLE_GROUPS.values() for role in roles))+('综合参考','待分类')


def role_order(counts):
    """计数里出现过的类目排一排：登记过的按登记顺序，没登记过的跟在后头，「待分类」垫底。"""
    known=[role for role in ROLE_ORDER if role in counts and role!='待分类']
    extra=sorted(role for role in counts if role not in ROLE_ORDER and role!='待分类')
    return known+extra+(['待分类'] if '待分类' in counts else [])


def role_counts(asset):
    """这一项资产的参考图按类目各几张：{类目: 张数}（读不出来就是空的）。"""
    if not isinstance(asset,dict):return {}
    values=asset.get('reference_images',[])
    values=[value for value in values if isinstance(value,str) and value] if isinstance(values,list) else []
    roles=asset.get('reference_roles',{})
    roles=roles if isinstance(roles,dict) else {}
    counts={}
    for value in dict.fromkeys(values):
        role=str(roles.get(value) or '待分类')
        counts[role]=counts.get(role,0)+1
    return counts


def role_summary(asset):
    """「参考图（类目）」那一格的字：几张 ＋ 按类目各几张（第 55 期第 6 条）。

    用户问过「要不要在参考图下面再加一栏『类目』」——单开一栏会把已经排得很紧的资产表
    再挤窄一列，所以改成写在同一格里：张数摆在前面（一眼看多少），后面跟类目明细
    （一眼看是什么），单击这一格进「查看参考图」按类目筛。
    """
    counts=role_counts(asset)
    if not counts:return '—'
    return '%d 张 · %s' % (sum(counts.values()),
                           ' '.join('%s%d' % (role,counts[role]) for role in role_order(counts)))

EXTENSIONS={'.png','.jpg','.jpeg','.webp'}



def safe_name(value):

    name=re.sub(r'[<>:"/\\|?*\x00-\x1f]+','_',str(value)).strip(' ._')[:48].strip(' ._')
    return name or '未命名'



def category_folder(base,aid):

    category=CATEGORIES.get(aid.split('_')[0])

    if not category:raise ValueError('未知的资产类别')

    return Path(base)/'assets/参考图'/category



def inbox(base,category):

    if category not in CATEGORIES.values():raise ValueError('未知的资产类别')

    folder=Path(base)/'assets/参考图'/category/'待导入'

    folder.mkdir(parents=True,exist_ok=True)

    return folder



def prepare_folders(base):
    for prefix,roles in ROLE_GROUPS.items():
        for role in (*roles,'待分类'):
            (Path(base)/'assets/参考图'/CATEGORIES[prefix]/role).mkdir(parents=True,exist_ok=True)
    return {name:inbox(base,name) for name in CATEGORIES.values()}


def classified_target(base,aid,role,digest,suffix,name,pending=False):
    role=role or '待分类'
    if role not in (*ROLE_GROUPS[aid.split('_')[0]],'待分类'):raise ValueError('参考图分类与资产类别不匹配')
    folder=category_folder(base,aid)
    if pending:folder=folder/'待导入'
    folder=folder/role/aid
    target=folder/(role+'_'+aid+'_'+safe_name(name)+'_'+digest[:12]+suffix)
    if not target.resolve().is_relative_to(Path(base).resolve()):raise ValueError('参考图保存路径超出资产库')
    return target


def save_copy(target,raw):
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():
        if target.read_bytes()!=raw:raise ValueError('参考图文件名冲突，请刷新后重试')
    else:save_bytes(target,raw)




def image_bytes(path):

    path=Path(path)

    if path.stat().st_size>20*1024*1024:raise ValueError('参考图不能超过20MB：'+path.name)

    raw=path.read_bytes()

    suffix=path.suffix.lower()

    valid=(suffix=='.png' and raw.startswith(b'\x89PNG\r\n\x1a\n') and raw[-8:-4]==b'IEND'

           or suffix in ('.jpg','.jpeg') and raw.startswith(b'\xff\xd8') and raw.endswith(b'\xff\xd9')

           or suffix=='.webp' and raw[:4]==b'RIFF' and raw[8:12]==b'WEBP')

    if not valid:raise ValueError('参考图格式无效，请选择完整PNG、JPG或WebP图片：'+path.name)

    return raw



def resolve(base,asset):

    base=Path(base).resolve();values=asset.get('reference_images',[])

    if not isinstance(values,list):raise ValueError('参考图清单格式不正确')
    result=[]

    for value in values:

        if not isinstance(value,str) or not value.strip() or Path(value).is_absolute():raise ValueError('参考图必须使用资产库内的相对路径')

        path=(base/value).resolve()

        if not path.is_relative_to(base):raise ValueError('参考图路径超出资产库')

        if not path.is_file():raise ValueError('参考图不存在，请重新添加：'+value)

        image_bytes(path)

        if path not in result:result.append(path)

    return result



def signature(base,asset):

    base=Path(base).resolve()

    roles=asset.get('reference_roles',{})
    roles=roles if isinstance(roles,dict) else {}
    return [{'path':p.relative_to(base).as_posix(),'sha256':hashlib.sha256(image_bytes(p)).hexdigest(),**({'role':roles[p.relative_to(base).as_posix()]} if roles.get(p.relative_to(base).as_posix()) else {})} for p in resolve(base,asset)]


def snapshot(base,asset):

    return {**asset,'_reference_signature':signature(base,asset)}



def reference_instruction(asset):
    if not isinstance(asset,dict):return ''
    values=asset.get('reference_images',[]);roles=asset.get('reference_roles',{})
    values=values if isinstance(values,list) else []
    roles=roles if isinstance(roles,dict) else {}
    if not values:return ''
    lines=['参考图按以下用途使用；以文字提示词和已确认的资产设定为准：']
    for i,path in enumerate(dict.fromkeys(values),1):
        role=roles.get(path,'综合参考')
        lines.append(f'参考图{i}：{role}。'+ROLE_HINTS.get(role,ROLE_HINTS['综合参考'])+'。')
    return '\n'.join(lines)


def set_roles(base,aid,values,role):
    if role not in ROLE_GROUPS.get(aid.split('_')[0],()):raise ValueError('参考用途与资产类别不匹配')
    file=Path(base)/'assets/资产清单/assets.json';plan=read(file);asset=plan[aid]
    if any(path not in asset.get('reference_images',[]) for path in values):raise ValueError('参考图已变化，请刷新')
    base=Path(base).resolve();roles=asset.setdefault('reference_roles',{});old_files=[]
    for path in values:
        source=resolve(base,{'reference_images':[path]})[0];raw=image_bytes(source)
        target=classified_target(base,aid,role,hashlib.sha256(raw).hexdigest(),source.suffix.lower(),asset.get('name',aid))
        save_copy(target,raw);relative=target.relative_to(base).as_posix()
        asset['reference_images']=[relative if item==path else item for item in asset['reference_images']]
        roles.pop(path,None);roles[relative]=role
        if source!=target:old_files.append((path,source))
    asset['reference_images']=list(dict.fromkeys(asset['reference_images']))
    save(file,plan)
    used={path for item in plan.values() for path in item.get('reference_images',[])}
    stale=[path for relative,path in old_files
           if relative not in used and path.is_relative_to((base/'assets/参考图').resolve())]
    if stale:
        from infra.storage_maintenance import recycle_paths
        recycle_paths(base,stale,'更新参考图绑定')


def attach(base,aid,paths,role=None):
    if role is not None and role not in ROLE_GROUPS.get(aid.split('_')[0],()):raise ValueError('参考用途与资产类别不匹配')
    if not re.fullmatch(r'(CHAR|LOC|PROP)_\d{3,}',aid):raise ValueError('资产编号无效')

    base=Path(base).resolve();planfile=base/'assets/资产清单/assets.json';plan=read(planfile)

    if aid not in plan:raise ValueError('资产已不存在，请刷新列表')

    # Validate the whole selection before changing the manifest.

    existing=list(plan[aid].get('reference_images',[]));known={(v['sha256'],v.get('role','待分类')) for v in signature(base,plan[aid])}
    additions=[]

    for value in paths:

        path=Path(value);raw=image_bytes(path);digest=hashlib.sha256(raw).hexdigest()

        identity=(digest,role or '待分类')
        if identity in known:continue
        known.add(identity);additions.append((digest,path.suffix.lower(),raw))
    title=safe_name(plan[aid].get('name',aid))

    added=[]
    for digest,suffix,raw in additions:
        dest=classified_target(base,aid,role,digest,suffix,title)
        save_copy(dest,raw)
        existing.append(dest.relative_to(base).as_posix())
        added.append(existing[-1])
    # Re-read so image imports or prompt edits performed meanwhile are retained.

    latest=read(planfile)

    if latest.get(aid,{}).get('reference_images',[])!=plan[aid].get('reference_images',[]):raise ValueError('参考图绑定已变化，请刷新重试')

    latest[aid]['reference_images']=existing
    if role is not None:latest[aid].setdefault('reference_roles',{}).update({path:role for path in added})
    save(planfile,latest)
    return len(additions)



def unbind(base,aid,values):

    """Remove selected bindings and their managed files, including batch originals."""

    base=Path(base).resolve();file=base/'assets/资产清单/assets.json';plan=read(file)

    if aid not in plan:raise ValueError('资产已不存在，请刷新列表')

    current=plan[aid].get('reference_images',[])

    selected=list(dict.fromkeys(values))

    if not selected or any(value not in current for value in selected):

        raise ValueError('参考图绑定已变化，请刷新重试')

    managed=(base/'assets/参考图').resolve()

    shared={value for other,asset in plan.items() if other!=aid for value in asset.get('reference_images',[])}

    owned=[]

    for value in selected:

        path=(base/value).resolve()

        # Never delete an external source or another asset's reference.

        legacy=managed/aid

        current_folder=category_folder(base,aid)/aid

        role_folders=[category_folder(base,aid)/role/aid for role in (*ROLE_GROUPS[aid.split('_')[0]],'待分类')]
        if value not in shared and path.is_file() and any(path.is_relative_to(folder) for folder in (legacy,current_folder,*role_folders)):
            if path.is_symlink() or not path.is_relative_to(managed):raise ValueError('参考图路径不安全')

            owned.append(path)

    # A bulk import preserves the original under the category archive. Remove

    # that copy only when its asset ID and file hash match this binding.

    archives=[]

    archive=category_folder(base,aid)/'已导入'

    if archive.is_dir():

        for path in owned:

            digest=hashlib.sha256(path.read_bytes()).digest()

            for candidate in archive.iterdir():

                if (candidate.is_file() and not candidate.is_symlink() and re.search(r'(?<![A-Z0-9])'+re.escape(aid)+r'(?!\d)',candidate.stem)
                    and candidate.resolve().is_relative_to(archive.resolve())

                    and hashlib.sha256(candidate.read_bytes()).digest()==digest):

                    archives.append(candidate)

    plan[aid]['reference_images']=[value for value in current if value not in selected]
    plan[aid]['reference_roles']={value:role for value,role in plan[aid].get('reference_roles',{}).items() if value not in selected}
    save(file,plan)

    targets=list(dict.fromkeys([*owned,*archives]))
    if targets:
        from infra.storage_maintenance import recycle_paths
        recycled=recycle_paths(base,targets,'解除参考图绑定')
        moved={record['source'] for record in recycled}
        failed=[path for path in targets if path.exists() and path.resolve().relative_to(base).as_posix() not in moved]
        if failed:
            raise OSError('已移除参考图绑定，但无法移入回收站：'+'、'.join(str(path) for path in failed))

    return len(owned)+len(set(archives))





def selected_column(table,column,message):
    """内容框当前选中的行 → 指定列的值；一行都没选就报同一句中文提示（编辑与查看两个对话框共用）。"""
    if not table.selection():raise ValueError(message)
    return [table.item(item,'values')[column] for item in table.selection()]


def show(app,aid):

    import tkinter as tk

    from tkinter import ttk

    from domain.asset_reference_prompts import display_prompt

    from responsive_ui import FlowBar, auto_columns

    if not aid:raise ValueError('请先选择要绑定参考图的资产')

    project=Path(app.root);base=app.asset_base();file=base/'assets/资产清单/assets.json'

    asset=read(file)[aid]

    win=BaseDialog(app.win,'',modal=False,chrome=False);win.withdraw();win.title('参考图 + 提示词 · '+aid+' '+asset.get('name',aid));win.geometry('800x500');win.transient(app.win)
    DescriptionBlock(win,text='参考图可选，可添加多张并指定用途；不添加时仅按提示词生成。支持 PNG／JPG／WebP。',wraplength=WRAPLENGTH['xl']).pack(anchor='w',padx=SPACING['md'],pady=SPACING['sm'])
    rolebar=FlowBar(win);rolebar.pack(fill='x',padx=SPACING['md'],pady=SPACING['xs'])
    ttk.Label(rolebar,text='参考用途').pack(side='left')
    choices=ROLE_GROUPS[aid.split('_')[0]]
    rolevar=tk.StringVar(value=choices[0])
    SelectBox(rolebar,textvariable=rolevar,values=choices).pack(side='left',padx=SPACING['sm'])
    def change_roles():
        nonlocal base,file
        guard();base=app.asset_write_base();file=base/'assets/资产清单/assets.json'
        set_roles(base,aid,selected_values(),rolevar.get());changed()
    SecondaryButton(rolebar,text='应用到选中参考图',command=lambda:app.safe(change_roles)).pack(side='left')
    ttk.Label(rolebar,text='显示分类').pack(side='left',padx=(SPACING['md'],SPACING['none']))
    filtervar=tk.StringVar(value='全部')
    filterbox=SelectBox(rolebar,textvariable=filtervar,values=('全部',*choices,'待分类'))
    filterbox.pack(side='left',padx=SPACING['xs'])
    table_shell=DataTable(win,columns=[('file','已绑定参考图',600),('role','参考用途',110)],
                          show='headings',selectmode='extended',height=TEXT_ROWS['md'],
                          empty_text='暂无已绑定参考图')
    table=table_shell.tree
    table.heading('role',text='参考用途');table.column('role',width=SPACING['sm'] * 14,stretch=False)
    table.heading('file',text='已绑定参考图');table.column('file',width=SPACING['sm'] * 75);table_shell.pack(fill='x',padx=SPACING['md'])
    auto_columns(table)
    status=tk.StringVar();ProgressLabel(win,textvariable=status).pack(anchor='w',padx=SPACING['md'],pady=SPACING['xs'])

    prompt=TextArea(win,height=TEXT_ROWS['xl'],wrap='word');prompt.insert('1.0',display_prompt(asset));prompt.configure(state='disabled');prompt.pack(fill='both',expand=True,padx=SPACING['md'])

    def guard():

        if Path(app.root)!=project:raise ValueError('项目已切换，请重新打开参考图窗口')

    def refresh():

        guard();table.delete(*table.get_children())

        current=read(file)[aid];values=current.get('reference_images',[])
        for i,value in enumerate(values):
            role=current.get('reference_roles',{}).get(value,'待分类')
            if filtervar.get() not in ('全部',role):continue
            table.insert('','end',iid=str(i),values=(value,role))
        table_shell.refresh_empty_state()
        status.set(f'已绑定 {len(values)} 张；按每张用途结合提示词生成。' if values else '未选择参考图：仅使用提示词生成。')
    def changed():

        refresh();app.show(PAGE_OF['assets'])

    def add():
        guard()
        # 导入窗口是延迟加载的 UI 插件；参考图服务不能反向静态导入它。
        from infra.ui_plugin_registry import module
        import_images=module('asset_reference_import').show
        import_images(app,aid,role=rolevar.get(),parent=win,on_saved=changed)
    def selected_values():return selected_column(table,0,'请先选择参考图')
    def preview_values(values):
        """查看：把这一批参考图各自打开（右键那一行传的就是它自己那一张）。"""
        guard()
        for path in resolve(base,{'reference_images':list(values)}):open_path(path)
    def remove_values(values):
        """删除：只解除这一批绑定——高亮与勾选都不参与（第 46 期第 1／9 条）。"""
        nonlocal base,file
        guard();base=app.asset_write_base();file=base/'assets/资产清单/assets.json'
        unbind(base,aid,list(values));changed()
    # 第 46 期第 1 条：目标永远是右键点中的那一行。
    bind_row_menu(table,
                  view=lambda row,_column:app.safe(lambda:preview_values([table.set(row,'file')])),
                  delete=lambda row:app.safe(lambda:remove_values([table.set(row,'file')])))

    def preview():

        guard();paths=resolve(base,{'reference_images':selected_values()})

        for path in paths:open_path(path)

    def remove():

        guard();unbind(base,aid,selected_values());changed()

    buttons=FlowBar(win);buttons.pack(fill='x',padx=SPACING['md'],pady=SPACING['sm'])

    for label,fn,button_type in [('添加参考图',add,PrimaryButton),('查看参考图',preview,SecondaryButton),('移除绑定',remove,SecondaryButton),('打开待导入目录',lambda:open_path(inbox(base,CATEGORIES[aid.split('_')[0]])),SecondaryButton)]:
        button_type(buttons,text=label,command=lambda f=fn:app.safe(f)).pack(side='left')

    table.bind('<Double-1>',lambda event:app.safe(preview))
    filterbox.bind('<<ComboboxSelected>>',lambda event:refresh());refresh()
    win.update_idletasks()
    win.geometry(f'+{max(0,app.win.winfo_rootx()+(app.win.winfo_width()-800)//2)}+{max(0,app.win.winfo_rooty()+(app.win.winfo_height()-500)//2)}')
    win.deiconify()

def view_references(app, aid):
    """查看某一项资产的参考图：按类目筛，按类目数（第 55 期第 6 条）。

    原来这扇窗只有「分类」一列，看的人得自己一行行找；类目是参考图唯一的组织方式，
    所以在这儿摆成看得见的一等公民：一栏筛选（全部／这一类的每个类目／待分类），
    一行按类目计数，导入的入口也摆在同一行按钮里——看的时候顺手补一张，不必再回资产表。
    """
    import tkinter as tk
    from tkinter import ttk
    from responsive_ui import FlowBar, auto_columns
    if not aid:raise ValueError('请先选择要查看参考图的资产')
    base=app.asset_base();file=base/'assets/资产清单/assets.json'
    asset=read(file)[aid];category=CATEGORIES.get(aid.split('_')[0],'未知')
    roles=ROLE_GROUPS.get(aid.split('_')[0],())
    win=BaseDialog(app.win,'',modal=False,chrome=False);win.withdraw();win.title(f'参考图 · {aid} {asset.get("name",aid)}');win.geometry('760x480');win.minsize(560,380);win.transient(app.win)
    ttk.Label(win,text=f'编号：{aid}　类别：{category}　名称：{asset.get("name",aid)}',font=('Microsoft YaHei UI',11,'bold')).pack(anchor='w',padx=SPACING['md'],pady=(SPACING['md'],SPACING['sm']))
    bar=FlowBar(win);bar.pack(fill='x',padx=SPACING['md'],pady=(SPACING['none'],SPACING['xs']))
    ttk.Label(bar,text='显示分类').pack(side='left')
    filtervar=tk.StringVar(value='全部')
    filterbox=SelectBox(bar,textvariable=filtervar,values=('全部',*roles,'待分类'))
    filterbox.pack(side='left',padx=(SPACING['sm'],SPACING['none']))
    ttk.Label(bar,text='参考图按类目归档；改类目请用「导入参考图」里的「参考分类」。',style='Muted.TLabel').pack(side='left',padx=(SPACING['sm'],SPACING['none']))
    # 第 57 期第 4 条：「分类」右边就是这一张参考图的缩略图——原来只有路径，看不出来是哪张。
    # 缩略图那一列由盖图那一层管（解不开的格式退回空白），行高也就得放到装得下一整张图。
    table_shell=DataTable(win,columns=[('role','分类',130),('thumb','缩略图',REF_THUMB+18),
                                       ('file','参考图文件（项目内相对路径）',360)],
                          show='headings',height=TEXT_ROWS['md'],selectmode='browse',style='Reference.Treeview',
                          empty_text='暂无参考图')
    table=table_shell.tree
    from responsive_ui import fit_row_height
    fit_row_height(table,REF_THUMB,style='Reference.Treeview')      # 第 58 期第 2 条
    table.heading('role',text='分类');table.column('role',width=SPACING['sm'] * 16,minwidth=90,stretch=False)
    table.heading('thumb',text='缩略图');table.column('thumb',width=REF_THUMB+18,
                                                     minwidth=REF_THUMB+18,stretch=False)
    table.heading('file',text='参考图文件（项目内相对路径）');table.column('file',width=SPACING['sm'] * 45)
    auto_columns(table)
    # 第 55 期第 6 条：底下那行按钮与状态行改成 side='bottom' 落位（pack 顺序见文件末尾）——
    # 这一期补了「显示分类」那一行之后，这一窗的请求高度（518）超过了窗口高度（480），按
    # 原来的顺序排下去，正好把三个按钮整个挤出窗外（winfo_ismapped()=0）：看着有、点不着。
    status=tk.StringVar()
    status_label=ProgressLabel(win,textvariable=status)
    def refresh():
        """重读资产清单重画这张表：只摆筛选要的那几类，底下那行说清「几张、哪几类」。"""
        now=read(file)
        row=now.get(aid,{}) if isinstance(now,dict) else {}
        vals=[value for value in row.get('reference_images',[]) if isinstance(value,str)]
        role_map=row.get('reference_roles',{}) if isinstance(row.get('reference_roles',{}),dict) else {}
        picked=filtervar.get()
        counts={}
        for value in dict.fromkeys(vals):
            role=str(role_map.get(value) or '待分类')
            counts[role]=counts.get(role,0)+1
        table.delete(*table.get_children())
        for i,value in enumerate(vals):
            role=str(role_map.get(value) or '待分类')
            if picked not in ('全部',role):continue
            table.insert('','end',iid=str(i),values=(role,'',value))
        table_shell.refresh_empty_state()
        table.cell_images.refresh()
        detail=' '.join('%s%d' % (role,counts[role]) for role in role_order(counts))
        status.set(('共 %d 张参考图（%s）' % (len(vals),detail) if detail else '还没有参考图：可用下面的「导入参考图」添加')
                   +('' if picked=='全部' else '；当前只显示「%s」。' % picked))
    def selected_files():return selected_column(table,2,'请先选择一行参考图')
    def preview_files(values):
        for path in resolve(base,{'reference_images':list(values)}):open_path(path)
    def preview():
        preview_files(selected_files())
    def remove_files(values):
        """删除：解除这一批参考图的绑定，再把这张表重画一遍（第 46 期第 1／9 条）。"""
        nonlocal base,file
        base=app.asset_write_base();file=base/'assets/资产清单/assets.json'
        unbind(base,aid,list(values));refresh()
    # 第 46 期第 1 条：右键＝查看这一行的图片／删除这一行的绑定。
    # 第 57 期第 4 条：这三列整栏交给 CellHover——右键先落在盖着缩略图的那层 Label 上，
    # 只绑树就点不出菜单；左键单击那一格（含缩略图）＝打开这一行的图，与资产页同一套。
    table.cell_hover=CellHover(table,('#1','#2','#3'),
                               lambda row,_column:app.safe(lambda:preview_files([table.set(row,'file')])),
                               delete=lambda row,_column:app.safe(lambda:remove_files([table.set(row,'file')])))
    def ref_thumb(row,size):
        """这一行参考图的小图：文件不在、路径越界、Tk 解不开（jpg／webp）一律返回 None。"""
        try:value=table.set(row,'file')
        except Exception:return None
        try:path=resolve(base,{'reference_images':[value]})[0]
        except (ValueError,OSError,IndexError):return None
        return asset_thumbs.thumbnail(win,path,size)
    def thumb_value(row,column):
        image=ref_thumb(row,REF_THUMB)
        return None if image is None else (image,'')
    # 第 57 期第 5 条：所有缩略图停上去都放大（放大图另解一张，不是把小图拉大）。
    table.cell_images=CellImages(table,('#2',),thumb_value,hover=table.cell_hover,
                                 zoom=lambda row,column:ref_thumb(row,ZOOM_SIZE))
    refresh()                                   # 盖图那一层建好了，这才铺第一遍
    def open_folder():
        prepare_folders(base);open_path(base/'assets/参考图'/category)
    def add():
        """顺手补一张：导入用的还是「导入参考图」那一扇窗（分类／目录都摆在里头）。"""
        from infra.ui_plugin_registry import module
        import_images=module('asset_reference_import').show
        import_images(app,aid,role=filtervar.get() if filtervar.get() in roles else roles[0],
                      parent=win,on_saved=lambda:(refresh(),app.safe(lambda:app.show(PAGE_OF['assets']))))
    buttons=FlowBar(win)
    for label,fn,button_type in [('查看图片',preview,SecondaryButton),('导入参考图',add,PrimaryButton),('打开参考图目录',open_folder,SecondaryButton)]:
        button_type(buttons,text=label,command=lambda f=fn:app.safe(f)).pack(side='left',padx=(SPACING['none'],SPACING['xs']))
    # 按钮与状态行先落位（bottom），内容框最后 pack 去吃掉剩下的空间：窗口再矮也是内容框
    # 先让步，不会是这三个按钮消失。
    buttons.pack(side='bottom',fill='x',padx=SPACING['md'],pady=(SPACING['none'],SPACING['sm']))
    status_label.pack(side='bottom',anchor='w',padx=SPACING['md'],pady=SPACING['sm'])
    table_shell.pack(fill='both',expand=True,padx=SPACING['md'])
    filterbox.bind('<<ComboboxSelected>>',lambda event:refresh())
    table.bind('<Double-1>',lambda e:app.safe(preview))
    win.update_idletasks()
    win.geometry(f'+{max(0,app.win.winfo_rootx()+(app.win.winfo_width()-760)//2)}+{max(0,app.win.winfo_rooty()+(app.win.winfo_height()-480)//2)}')
    win.deiconify()
