"""Keep the adopted collection separate from the episode currently on screen."""
import app_logging
import os, time
from pathlib import Path
from agent.core import read,save
from file_cache import read_json
from project_settings import read_prefs
from project_context_factory import project_context
from storyboard_adoption_contract import adopted as _adopted, problem_text, resolve_source
import pet_bus
from ui_tokens import SPACING


def _asset_plan_gateway(gateway):
    """分镜采用是 L3，缺省时在此装配资产计划的正式发布能力。"""
    if isinstance(gateway, dict):
        return gateway
    from agent.core import save_bytes, save_text
    from file_cache import remove_temporary_file
    return {'publish_json': save, 'publish_bytes': save_bytes,
            'publish_text': save_text, 'remove_file': remove_temporary_file}


def prefs(project):
    # 一次页面重排里会被读 9 次以上：按文件签名缓存解析；损坏时给出可操作提示而不是解析异常。
    return read_prefs(Path(project)/'ui_settings.json',read_json)


def writable_prefs(project):
    """读—改—写路径专用：prefs() 给的是共享缓存，就地修改会污染同一轮里的其他读者。"""
    return dict(prefs(project))


def remember_many(project, kind, values):
    """Persist the selected script or storyboard paths without involving Tk."""
    project = Path(project).resolve()
    if kind not in ('script', 'storyboard'):
        raise ValueError('选择类型无效')
    data = writable_prefs(project)
    stored = []
    for value in values:
        path = Path(value).resolve()
        entry = path.relative_to(project).as_posix() if path.is_relative_to(project) else str(path)
        if entry not in stored:
            stored.append(entry)
    plural = 'storyboard_scripts' if kind == 'script' else 'storyboard_files'
    singular = 'storyboard_script' if kind == 'script' else 'storyboard_file'
    data[plural] = stored
    data[singular] = stored[0] if stored else ''
    save(project / 'ui_settings.json', data)


def selected_many(project, kind):
    """Read the current script or storyboard selection as existing paths."""
    project = Path(project).resolve()
    if kind not in ('script', 'storyboard'):
        raise ValueError('选择类型无效')
    data = prefs(project)
    plural = 'storyboard_scripts' if kind == 'script' else 'storyboard_files'
    singular = 'storyboard_script' if kind == 'script' else 'storyboard_file'
    values = data.get(plural)
    if values is None:
        values = [data.get(singular)] if data.get(singular) else []
    if not isinstance(values, list):
        raise ValueError('已选文件列表格式错误')
    result = []
    for value in values:
        path = resolve_source(project, value)
        if path.is_file() and path not in result:
            result.append(path)
    return result


def remember_final_view(project, source):
    """Persist the final-storyboard viewer pointer without involving the Tk page."""
    project = Path(project).resolve()
    source = Path(source).resolve()
    if not source.is_relative_to(project):
        raise ValueError('分镜定稿不在当前项目内')
    data = writable_prefs(project)
    data['final_storyboard_json'] = source.relative_to(project).as_posix()
    save(project / 'ui_settings.json', data)
    return source


def sync_structured_script(project):
    """Put the newest structured script first while preserving user selections."""
    from script_contract import structured_script_path
    project = Path(project).resolve()
    script = structured_script_path(project).resolve()
    if not script.is_file():
        return []
    values = [script, *(path for path in selected_many(project, 'script') if path != script)]
    remember_many(project, 'script', values)
    return values


def paths(project,values):
    project=Path(project).resolve();result=[]
    for value in values:
        path=resolve_source(project,value)
        if not path.is_relative_to(project) or not path.is_file():
            raise ValueError('已采用的分镜不存在或不在当前项目内：'+str(path))
        if path not in result:result.append(path)
    return result


def adopted(project):
    return _adopted(project)


def current_source(project, legacy_sources=(), fallbacks=(), remember=None):
    """解析下游页面当前使用的分镜，并兼容旧版桌面设置。

    解析规则不依赖 Tk；``remember`` 只由调用方提供，用于把仍可用的旧指针迁移到
    当前采用记录。这样首帧、资产和视频页面可以共享同一来源约束。
    """
    from storyboard_catalog_service import default_source, resolve_source

    project = Path(project).resolve()
    settings_path = project / 'ui_settings.json'
    if settings_path.is_file():
        data = prefs(project)
        saved = data.get('frame_json') if isinstance(data, dict) else None
        if saved:
            path = resolve_source(project_context(project), saved)
            if path.is_relative_to(project) and path.is_file():
                return path
            raise ValueError('上次的镜头 JSON 找不到了：' + str(path) + '。请到'+pet_bus.stage_step('storyboard')+'重新采用一份。')
        if isinstance(data, dict) and 'adopted_storyboards' in data:
            sources = adopted(project)
            if sources:
                focus(project, sources[-1])
                return sources[-1]
            raise ValueError('尚未采用分镜JSON，请在'+pet_bus.stage_step('storyboard')+'采用一份或多份JSON。')

    for root, value in legacy_sources:
        if Path(root).resolve() != project:
            continue
        candidate = Path(value).resolve()
        if candidate.is_relative_to(project) and candidate.is_file():
            if remember is not None:
                remember(candidate)
            return candidate

    for candidate in (default_source(project_context(project)), *fallbacks):
        candidate = Path(candidate)
        if candidate.is_file():
            candidate = candidate.resolve()
            if remember is not None:
                remember(candidate)
            return candidate
    raise ValueError('这个项目还没有分镜 JSON，请先到'+pet_bus.stage_step('storyboard')+'采用一份。')


def source_script_error(project, board, available=None):
    """JSON 必须来自当前“初步分镜”栏中实际可用的一份剧本。

    迁移目录后，旧 JSON 常保留 ``writing/script.md`` 之类已经失效的来源。
    它们可以留在磁盘供用户查看，但不能继续被采用并推进后续阶段。

    ``available`` 是可选预取参数：可以是“当前可用剧本集合”，也可以是取数器；
    取数器只在 ``source is not None`` 之后调用，保证没有任何板到达来源比对时零扫描。
    批量校验（prune_invalid_adoptions）传惰性取数器，只有真正需要来源比对时才扫一次，
    之后各板复用；提前返回的板与空采用列表都不触发扫描。
    """
    from storyboard_catalog_service import board_source_script, catalog
    project=Path(project).resolve();board=Path(board).resolve()
    try:data=read_json(board)
    except (OSError,ValueError,TypeError):return '无法读取 JSON 的分镜初稿来源'
    if not isinstance(data,dict):return 'JSON 的分镜初稿来源格式错误'
    # 早期 JSON 没有记录来源；它们已经是用户既有成果，保持可采用。新 JSON 和带来源的
    # 历史 JSON 则必须走下面的严格校验，防止误把无关文件推进到后续阶段。
    if not str(data.get('source_script') or '').strip():return ''
    try:source=board_source_script(project_context(project),board)
    except (OSError,ValueError,TypeError):return '无法读取 JSON 的分镜初稿来源'
    if source is None:return 'JSON 未记录分镜初稿来源'
    # 先通过来源读取检查，确认真的要做来源比对了再取“当前可用剧本集合”。
    # 批量校验的取数器在此才触发，且只扫一次；提前返回的板不会让它扫描。
    if callable(available) and not isinstance(available,(set,frozenset)):
        available=available()
    if available is None:
        # 只取剧本路径集合，不需要“已制作分镜”标记：传空 completed 避免 produced_scripts
        # 顺带再扫一遍分镜目录。
        available=catalog(project_context(project),'script',completed=set())
    if not isinstance(available,(set,frozenset)):
        available={entry['path'] for entry in available}
    if source not in available:
        return '对应分镜初稿不存在或已迁移：'+str(source)
    return ''


def prune_invalid_adoptions(project):
    """仅取消来源已失效 JSON 的采用；保留 JSON 文件和任何历史资产。"""
    project=Path(project).resolve();data=writable_prefs(project)
    values=data.get('adopted_storyboards')
    if not isinstance(values,list):return ()
    # 惰性扫描、多板复用：第一个真正要做来源比对的板才取一次“当前可用剧本集合”，
    # 调用次数不随已采用分镜数增长（N 个板到达比对时都只扫一遍剧本目录）；
    # 空采用列表或所有板提前返回时一次都不扫，不给 UI 线程新增整库扫描。
    from storyboard_catalog_service import catalog
    cache=[]
    def available():
        if not cache:
            cache.append(catalog(project_context(project),'script',completed=set()))
        return cache[0]
    valid=[];removed=[]
    for value in values:
        try:board=paths(project,[value])[0]
        except (OSError,ValueError,IndexError):
            removed.append(str(value));continue
        if source_script_error(project,board,available=available):
            removed.append(str(board));continue
        if board not in valid:valid.append(board)
    if not removed:return ()
    data['adopted_storyboards']=[path.relative_to(project).as_posix() for path in valid]
    current=data.get('frame_json')
    try:current_path=paths(project,[current])[0] if current else None
    except (OSError,ValueError,IndexError):current_path=None
    if current_path not in valid:
        data['frame_json']=valid[-1].relative_to(project).as_posix() if valid else ''
    save(project/'ui_settings.json',data)
    sync_draft_outputs(project)
    return tuple(removed)


DRAFT_NAME='storyboard_draft.json';BREAKDOWN_NAME='scene_breakdown.json'


def draft_dir(project):
    import stage_layout
    return stage_layout.paths(Path(project),'03初步分镜')['output']


def _episode_shots(source):
    data=read(source)
    shots=[s for s in data.get('shots') or [] if isinstance(s,dict)] if isinstance(data,dict) else []
    return str(data.get('episode_id') or '') if isinstance(data,dict) else '',shots


def _breakdown_items(sources):
    """按「连续同一 location 的镜头为一场」从已采用分镜派生场次拆分（程序派生，不是模型自述）。"""
    items=[]
    for source in sources:
        episode,shots=_episode_shots(source);runs=[]
        for shot in shots:
            place=str(shot.get('location') or '')
            if runs and runs[-1][0]==place:runs[-1][1].append(shot)
            else:runs.append((place,[shot]))
        for place,group in runs:
            ids=[str(s.get('id') or '') for s in group];people=[]
            for shot in group:
                people+=[c for c in shot.get('characters') or [] if isinstance(c,str) and c not in people]
            items.append({'name':place or str(group[0].get('title') or ''),'episode_id':episode,'scene_id':place,'time_place':place,'characters':people,
                          'task':str(group[0].get('title') or ''),'boundary':'%s~%s'%(ids[0],ids[-1]),'shot_ids':ids})
    return items


def _draft_sources(project,sources):
    out=[]
    for source in sources:
        episode,shots=_episode_shots(source)
        out.append({'path':source.relative_to(project).as_posix(),'episode_id':episode,
                    'shot_ids':[str(s.get('id') or '') for s in shots]})
    return out


def sync_draft_outputs(project):
    """把已采用分镜同步成 03初步分镜/output/ 下的 storyboard_draft.json 与 scene_breakdown.json。"""
    from script_manifest_schema import manifest
    project=Path(project).resolve();sources=adopted(project);folder=draft_dir(project)
    save(folder/DRAFT_NAME,{'manifest':DRAFT_NAME,'kind':'storyboard_draft','sources':_draft_sources(project,sources)})
    save(folder/BREAKDOWN_NAME,manifest('scene_breakdown',_breakdown_items(sources)))
    return folder


def _read_output(path):
    try:return read(path),''
    except (OSError,ValueError):return None,'%s 还没产出或读不出来'%path.name


def draft_problems(project):
    """核验 03 的两份落盘产物与当前已采用分镜一致；旧项目缺文件时先按已采用分镜补写。空列表＝通过。"""
    from script_manifest_schema import duplicate_ids,items_of,validate
    project=Path(project).resolve();sources=adopted(project)
    if not sources:return []
    folder=draft_dir(project)
    if not (folder/DRAFT_NAME).is_file() and not (folder/BREAKDOWN_NAME).is_file():
        try:sync_draft_outputs(project)
        except (OSError,ValueError,KeyError,TypeError) as exc:return ['同步分镜初稿产物失败：%s'%exc]
    draft,problem=_read_output(folder/DRAFT_NAME);problems=[problem] if problem else []
    if draft is not None:
        try:fresh=_draft_sources(project,sources)
        except (OSError,ValueError,KeyError,TypeError):fresh=None
        if not isinstance(draft,dict) or draft.get('sources')!=fresh:
            problems.append('%s 与已采用分镜不一致，请在初步分镜页重新采用以同步'%DRAFT_NAME)
    data,problem=_read_output(folder/BREAKDOWN_NAME)
    if problem:return problems+[problem]
    items=items_of(data);have=sorted(sid for item in items for sid in item.get('shot_ids') or [])
    want=sorted(sid for _s,shots in ((_episode_shots(p)) for p in sources) for s in shots for sid in [str(s.get('id') or '')])
    if have!=want:problems.append('%s 没有覆盖全部已采用镜头，请重新采用以同步'%BREAKDOWN_NAME)
    problems+=duplicate_ids({BREAKDOWN_NAME:data})
    # 场景／角色编号是否写成 LOC_／CHAR_ 由资产阶段（SG-01）判定，这里只拦结构性错误。
    problems+=['%s 第 %d 条：%s'%(BREAKDOWN_NAME,index,text) for index,item in enumerate(items,1)
               for text in validate('scene_breakdown',item) if not text.startswith(('scene_id 要写','characters 里要写'))]
    return problems


def adopt(project,values,*,gateway=None):
    """Validate the whole request before changing any adoption or asset state."""
    from writing import validate_episode
    from storyboard_paths import media_root
    from asset_context import library_dir
    from asset_plan import _sync_plan
    project=Path(project).resolve();incoming=paths(project,values)
    if not incoming:raise ValueError('请先选择一份或多份分镜 JSON')
    existing=adopted(project);incoming=[p for p in incoming if p not in existing]
    if not incoming:return existing
    combined=[*existing,*incoming]
    for source in combined:
        reason=source_script_error(project,source)
        if reason:raise ValueError(f'{source.name}：{reason}')
        # 第 62 期任务 12：报错带上文件名和具体差多少，别只说一句「不一致」。
        try:validate_episode(read(source),media_root(source))
        except ValueError as exc:raise ValueError(f'{source.name}：'+problem_text(exc)) from None
    _sync_plan(project,library_dir(project),combined,_adopting=True,
               gateway=_asset_plan_gateway(gateway), context=project_context(project))
    data=writable_prefs(project)
    data['adopted_storyboards']=[p.relative_to(project).as_posix() for p in combined]
    data['frame_json']=incoming[-1].relative_to(project).as_posix()
    save(project/'ui_settings.json',data)
    sync_draft_outputs(project)
    return combined


def sync_working_episode(project,source=None):
    """项目还没有视频任务时，把工作集指针切到该分镜（config 的 episode_dir／episode_file）。"""
    from asset_context import library_dir
    project=Path(project).resolve()
    sources=paths(project,[source]) if source else adopted(project)
    if not sources:return None
    target=sources[-1]
    db=project/'data/state.json'
    try:state=read(db) if db.is_file() else {}
    except (OSError,ValueError):state={}
    if isinstance(state,dict) and any((state.get('shots') or {}).values()):return None
    config=project/'config.json'
    try:cfg=read(config) if config.is_file() else {}
    except (OSError,ValueError):cfg={}
    if not isinstance(cfg,dict):cfg={}
    updated=dict(cfg,episode_dir=str(target.parent),episode_file=str(target))
    if not updated.get('asset_library_dir'):updated['asset_library_dir']=str(library_dir(project))
    if updated!=cfg:save(config,updated)
    return target


def repair_working_episode(project,source=None):
    """工作集指针指的分镜已经不在采用清单里时，把它拉回最近采用的那一份（第 62 期任务 7）。

    强制关闭可能正好落在 adopt() 与 sync_working_episode() 之间：分镜已经记进采用清单，
    config.json 的 episode_file 还停在旧分镜（甚至已经不存在）上。重启后 adopt_pending
    看到「没有新东西」就早退了，这一步没人补，04 之后各步就还按旧分镜走——用户看到的
    就是「强制关闭后三虎没有自动同步已经完成的分镜」。
    指针没歪（还在采用清单里）时什么都不做，免得覆盖用户手动切过的工作集。
    """
    project=Path(project).resolve()
    sources=[Path(p) for p in (paths(project,[source]) if source else adopted(project))]
    if not sources:return None
    config=project/'config.json'
    try:cfg=read(config) if config.is_file() else {}
    except (OSError,ValueError):cfg={}
    current=Path(cfg['episode_file']) if isinstance(cfg,dict) and cfg.get('episode_file') else None
    if current is not None and any(current==path for path in sources):return None
    return sync_working_episode(project)


def _validate(path):
    from writing import validate_episode
    from storyboard_paths import media_root
    try:validate_episode(read(path),media_root(path))
    except ValueError as exc:raise ValueError(f'{Path(path).name}：'+problem_text(exc)) from None


def tree_signature(project):
    """分镜目录的轻量指纹：只数 JSON 与最新写入时间，用来跳过没有变化的重扫。"""
    from storyboard_catalog_service import IGNORED, discover_files
    # 新产物统一位于“03初步分镜”；不再因旧 ``storyboard/`` 目录为空而漏掉自动采用。
    from project_stages import storyboard
    root=storyboard(project);count=0;latest=0.0
    if not root.is_dir():return (count,latest)
    for _path,_resolved,stat in discover_files((root,), {'.json'}, IGNORED):
        latest=max(latest, stat.st_mtime)
        count+=1
    return (count,latest)


def adopt_pending(project,minimum_age=10,*,gateway=None):
    """无人值守自动采用：把新出现且校验通过的分镜 JSON 推进后续流程。

    返回 {'adopted':[路径…],'failed':{路径:原因},'waiting':[路径…]}。刚写入的文件先等
    minimum_age 秒，避免读到 agent 正在写的一半内容（记在 waiting，下一轮再看）；某一份
    不合法只跳过它，其余照常采用；整批只同步一次资产计划，重复调用不会重复采用。
    """
    from storyboard_catalog_service import catalog
    project=Path(project).resolve();now=time.time()
    used=set(adopted(project))
    entries=sorted((entry for entry in catalog(project_context(project),'storyboard') if entry['path'] not in used),key=lambda entry:entry['order'])
    ready=[];failed={};waiting=[]
    for entry in entries:
        path=entry['path']
        try:age=now-path.stat().st_mtime
        except OSError:continue
        if age<minimum_age:
            failed[str(path)]='文件刚写入，等待写入完成后自动采用';waiting.append(path);continue
        try:_validate(path)
        except (OSError,ValueError,KeyError,TypeError) as exc:
            failed[str(path)]=str(exc);continue
        ready.append(path)
    if not ready:return {'adopted':[],'failed':failed,'waiting':waiting}
    try:adopt(project,ready,gateway=gateway)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        for path in ready:failed[str(path)]=str(exc)
        return {'adopted':[],'failed':failed,'waiting':waiting}
    sync_working_episode(project)
    return {'adopted':ready,'failed':failed,'waiting':waiting}


def remove(project,values,*,gateway=None):
    from asset_context import library_dir
    from asset_plan import _sync_plan
    project=Path(project).resolve();removed=set(paths(project,values))
    remaining=[p for p in adopted(project) if p not in removed]
    data=writable_prefs(project)
    data['adopted_storyboards']=[p.relative_to(project).as_posix() for p in remaining]
    current=resolve_source(project,data['frame_json']) if data.get('frame_json') else None
    if current not in remaining:data['frame_json']=remaining[-1].relative_to(project).as_posix() if remaining else ''
    _sync_plan(project,library_dir(project),remaining,gateway=_asset_plan_gateway(gateway), context=project_context(project))
    save(project/'ui_settings.json',data)
    sync_draft_outputs(project)
    return remaining


def focus(project,source):
    project=Path(project).resolve();source=paths(project,[source])[0]
    if source not in adopted(project):raise ValueError('请先采用该分镜')
    data=writable_prefs(project);data['frame_json']=source.relative_to(project).as_posix()
    save(project/'ui_settings.json',data)


def summary(project):
    entries=[(source,read_json(source)) for source in adopted(project)]
    names=[str(ep.get('episode_id',source.stem)) for source,ep in entries]
    shots=sum(len(ep.get('shots',[])) for _,ep in entries)
    return f'已采用 {len(entries)} 份分镜，共 {shots} 镜：'+('、'.join(names) if names else '尚未采用')


def source_selector(app,index,*,select_box):
    """Downstream pages share one focus control while keeping every adopted file."""
    import tkinter as tk
    from tkinter import ttk
    sources=adopted(app.root)
    if not sources:return
    from storyboard_source_service import source_options
    labels,sources,current_index=source_options(sources,app.asset_scope(),app.current_frame_json())
    row=ttk.Frame(app.content);row.pack(fill='x',pady=(SPACING['none'],SPACING['xs']))
    # 第 64 期任务 5：「全部分镜」这一项原来只有资产管理页有，用户要它同步到其他页面的
    # 「选择分镜」下拉框——各页本来就是同一份范围偏好（asset_scope：全部分镜 ／ 只这一份），
    # 列出来的项也该一模一样。只有一份采用清单时这一项没有意义，就照旧不列。
    broad=len(sources)>1
    def display_index():
        """下拉框该显示的那一条：「全部分镜」不是一个文件，只能按范围偏好判断。"""
        return source_options(adopted(app.root),app.asset_scope(),app.current_frame_json())[2]
    line=ttk.Frame(row);line.pack(fill='x',pady=SPACING['xs'])
    ttk.Label(line,text='选择分镜').pack(side='left',padx=(SPACING['none'],SPACING['sm']))
    combo=select_box(line,values=labels,width=1)
    combo.pack(side='left',fill='x',expand=True)
    combo.current(current_index)
    def guard_wheel(event):
        # 「选择分镜」只读下拉框绝不被滚轮改选：控件自身的绑定先于 TCombobox 类绑定执行，
        # 这里直接把滚轮转给页面滚动并中断后续绑定，即使页面滚轮标签万一没补上也不会换文件。
        scroll=getattr(app,'scroll_page',None)
        if scroll is not None:scroll(event)
        return 'break'
    combo.bind('<MouseWheel>',guard_wheel)
    def collapse():
        """重建页面前先收起 Tk 自建的下拉弹窗：弹窗与页面同时变化，看起来就是「换文件内容抖动」。"""
        try:app.win.tk.call('ttk::combobox::Unpost',str(combo))
        except tk.TclError:pass
    def choose(event=None):
        selected=combo.current()
        if selected<0:return
        def apply():
            video=getattr(app,'video',None)
            if video and (getattr(video,'busy',False) or getattr(video,'optimizer_busy',False)):
                raise ValueError('请等待当前镜头操作完成后再切换集数')
            target=sources[selected]
            # 重复选中同一项（例如下拉列表里点回原来那条）不再重建整页，避免内容抖动。
            if broad and target is None:
                if app.asset_scope()!='current':return
            # 范围偏好还是「全部分镜」时，点回当前这一份也要把它切回「只这一份」，
            # 否则下拉框会立刻弹回「全部分镜」，看着像点了没反应。
            elif (target is not None and app.asset_scope()=='current'
                  and app.current_frame_json()==Path(target).resolve()):return
            if broad:
                data=writable_prefs(app.root);data['asset_scope']='current' if target else 'adopted'
                save(Path(app.root)/'ui_settings.json',data)
            if target is not None:focus(app.root,target)
            # 先明确收起下拉弹窗，等本控件的事件处理结束后再重建页面：切换途中的重建会让页面抖动。
            collapse()
            app.win.after_idle(lambda:app.safe(lambda:app.show(index)))
        def resync():
            """切换没生效时把下拉框显示拉回真实文件。

            后台任务占用时 safe 只提示不切换，下拉框却已经停在新文件名上：显示与页面内容
            不一致，下一次重建又跳回原文件，表现出来就是「换文件时内容抖动」。
            """
            try:
                if not combo.winfo_exists():return
                target=display_index()
                if combo.current()!=target:combo.current(target)
            except Exception:app_logging.swallowed()
        app.safe(apply)
        app.win.after_idle(resync)
    combo.bind('<<ComboboxSelected>>',choose)
