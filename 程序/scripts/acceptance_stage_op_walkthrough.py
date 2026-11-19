# -*- coding: utf-8 -*-
"""F 维接入索引走查（R3812）：S07 分镜定稿「手动同步资产」真实界面走查。

在隐藏桌面里用临时项目走通已实现操作，覆盖任务书要求的三态：
  A. 正常输入：定稿页选中已采用分镜 → 「手动同步资产」→ 07分镜定稿 产物核验。
  B. 缺失输入：无已采用分镜 → 同一按钮 → 用户可见报错、零产出。
  C. 旧项目：定稿产物位于旧目录 06分镜定稿（只读兼容位）→ 同一操作 →
     签名复用旧目录、不新建 07分镜定稿。

每态记录：界面入口、服务入口、产物、完成核验（stage_parallel.batches_ready）、
回收站退役结果。证据写 --evidence/stage_op_walkthrough.json。

用法（程序/ 下，隐藏桌面）：
  python scripts/gui_hidden.py <out> <程序目录> -- python scripts/acceptance_stage_op_walkthrough.py \
      --evidence <证据目录>
"""
import argparse
import hashlib
import json
import shutil
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import file_cache  # noqa: E402  正式 JSON 读唯一入口
import app_logging  # noqa: E402  验收探针尽力而为路径留痕
sys.path.insert(0, str(HERE / 'tests'))  # catalog_page_test_support 等测试侧支撑

PROGRAM = HERE
WORK = None  # 由 main 注入临时根


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make_project(root, adopt=True):
    """最小可定稿项目（与 tests/test_req_s07_anchors._project 同构）。"""
    from agent.core import save
    from tests.image_fixtures import png
    project = Path(root).resolve()
    episode = project / 'episode'
    (episode / 'assets' / '资产清单').mkdir(parents=True)
    (episode / 'assets' / 'characters').mkdir(parents=True)
    (episode / 'frames').mkdir(parents=True)
    source_dir = project / '03初步分镜' / '分镜文档'
    source_dir.mkdir(parents=True)
    (project / '03初步分镜' / 'frames').mkdir(parents=True)
    (project / '02剧本').mkdir(parents=True, exist_ok=True)
    save(project / 'config.json', {'episode_dir': str(episode),
                                   'asset_library_dir': str(episode),
                                   'episode_file': str(episode / 'episode.json')})
    script = project / '02剧本' / 'EP001_结构剧本.json'
    script.write_text(json.dumps({'episode_id': 'EP001'}, ensure_ascii=False),
                      encoding='utf-8')
    save(episode / 'assets' / '资产清单' / 'assets.json',
         {'CHAR_001': {'name': '主角'}, 'CHAR_002': {'name': '配角'},
          'LOC_001': {'name': '街道'}})
    save(episode / 'assets.json',
         {'CHAR_001': {'name': '主角', 'image': 'assets/characters/CHAR_001.png'},
          'LOC_001': {'name': '街道', 'image': 'assets/characters/LOC_001.png'}})
    (episode / 'assets' / 'characters' / 'CHAR_001.png').write_bytes(png())
    (episode / 'assets' / 'characters' / 'LOC_001.png').write_bytes(png(color='blue'))
    (project / '03初步分镜' / 'frames' / 'SH001.png').write_bytes(png())
    (project / '03初步分镜' / 'frames' / 'SH002.png').write_bytes(png(color='blue'))
    source = source_dir / 'EP001_分镜.json'
    shots = [
        {'id': 'SH001', 'title': '开场', 'duration': 5, 'characters': ['主角', 'CHAR_002'],
         'location': 'LOC_001', 'frame': 'frames/SH001.png', 'video_prompt': '开场镜头',
         'dialogue': [{'speaker': '主角', 'text': '您好'}]},
        {'id': 'SH002', 'title': '反应', 'duration': 4, 'characters': ['CHAR_001'],
         'location': 'LOC_001', 'frame': 'frames/SH002.png', 'video_prompt': '反应镜头',
         'dialogue': []},
    ]
    source.write_text(json.dumps({'episode_id': 'EP001', 'title': '第一集', 'shots': shots,
                                  'source_script': '02剧本/EP001_结构剧本.json'},
                                 ensure_ascii=False, indent=2), encoding='utf-8')
    (episode / 'episode.json').write_text(json.dumps(
        {'episode_id': 'EP001', 'title': '第一集', 'shots': shots},
        ensure_ascii=False, indent=2), encoding='utf-8')
    prefs = {'adopted_storyboards': [source.resolve().relative_to(
        project).as_posix()] if adopt else [],
        'frame_json': source.resolve().relative_to(project).as_posix() if adopt else ''}
    (project / 'ui_settings.json').write_text(
        json.dumps(prefs, ensure_ascii=False), encoding='utf-8')
    return project, episode, source


def pump(win, seconds=0.05):
    try:
        win.update()
    except Exception:
        app_logging.swallowed()
    time.sleep(seconds)


def wait_until(win, predicate, timeout=60.0, interval=0.1):
    deadline = time.time() + timeout
    while time.time() < deadline:
        pump(win, interval)
        try:
            if predicate():
                return True
        except Exception:
            app_logging.swallowed()
    return False


def all_widgets(root):
    stack = [root]
    while stack:
        w = stack.pop()
        yield w
        try:
            stack.extend(w.winfo_children())
        except Exception:
            app_logging.swallowed()


def find_button(win, label):
    for w in all_widgets(win):
        try:
            if str(w.cget('text')) == label:
                return w
        except Exception:
            continue
    return None


def find_tree_with(win, iid):
    for w in all_widgets(win):
        try:
            if w.winfo_class() == 'Treeview' and iid in w.get_children():
                return w
        except Exception:
            continue
    return None


def open_desktop(project):
    """真实隐藏桌面 Desktop（与 tests/test_final_viewer 同一开法）。"""
    import tkinter as tk
    import desktop
    win = tk.Tk()
    win.withdraw()
    original = desktop.Desktop.choose_project
    desktop.Desktop.choose_project = lambda self: None
    try:
        from local_video import open_studio
        app = desktop.Desktop(win, root=str(PROGRAM))
        app.root = Path(project)
        app.studio = open_studio(app.root)
        app.poll_auto_adopt()
        from catalog_page_test_support import show_catalog_page_ready
        from infra.pet_state import PAGE_OF
        show_catalog_page_ready(app, PAGE_OF['final'])
        return win, app
    finally:
        desktop.Desktop.choose_project = original


def case_missing_input(evidence):
    """B：无已采用分镜时点「手动同步资产」→ 可见报错、零产出。"""
    rec = {'case': 'missing_input', 'checks': {}}
    project, episode, _source = make_project(WORK / 'case_missing', adopt=False)
    win, app = open_desktop(project)
    errors = []
    # 按钮命令经 desktop.safe 兜底：异常落到 notifier.error → 状态栏（非模态）。
    real_error = app.notifier.error

    def capture_error(message, **kwargs):
        errors.append(str(message))
        return real_error(message, **kwargs)

    app.notifier.error = capture_error
    try:
        pump(win, 0.3)
        button = find_button(win, '手动同步资产')
        rec['checks']['button_found'] = button is not None
        rec['button_state'] = str(button.cget('state')) if button is not None else ''
        if button is not None:
            try:
                button.invoke()
            except Exception as exc:  # invoke 同步抛出也算用户可见失败
                errors.append(str(exc))
            pump(win, 0.5)
        finals = list((project / '07分镜定稿').glob('**/episode.json')) \
            if (project / '07分镜定稿').is_dir() else []
        rec['checks']['no_final_produced'] = not finals
        rec['checks']['error_surfaced'] = bool(errors)
        rec['error_text'] = (errors[0] if errors else '')[:200]
        rec['status_text'] = str(getattr(getattr(app, 'status', None), 'text', ''))[:200]
    finally:
        try:
            win.destroy()
        except Exception:
            app_logging.swallowed()
    evidence['cases'].append(rec)
    return rec


def case_normal(evidence):
    """A：正常输入——界面选中已采用分镜 → 手动同步资产 → 产物核验。"""
    rec = {'case': 'normal_input', 'checks': {}}
    project, episode, source = make_project(WORK / 'case_normal', adopt=True)
    win, app = open_desktop(project)
    try:
        iid = str(source.resolve())
        ok_tree = wait_until(win, lambda: find_tree_with(win, iid) is not None,
                             timeout=30)
        rec['checks']['catalog_row_visible'] = ok_tree
        tree = find_tree_with(win, iid)
        if tree is not None:
            tree.selection_set(iid)
            tree.focus(iid)
            tree.event_generate('<<TreeviewSelect>>')
            pump(win, 0.5)
        button = find_button(win, '手动同步资产')
        rec['checks']['button_found'] = button is not None
        clicked = False
        if button is not None:
            try:
                button.invoke()
                clicked = True
            except Exception as exc:
                rec['invoke_error'] = str(exc)
        rec['checks']['button_invoke'] = clicked

        def finalized():
            return list((project / '07分镜定稿' / '分镜').glob('*/episode.json'))

        def settled():
            hits = finalized()
            return bool(hits) and all(
                (h.parent / name).is_file()
                for h in hits for name in ('assets.json', '产物来源关系.json')) \
                and not source.is_file()  # 退役在血缘/文档派生之后，等它落定

        rec['checks']['final_landed'] = wait_until(win, settled, timeout=90)
        finals = finalized()
        rec['final_dirs'] = [p.parent.name for p in finals]
        if finals:
            ep = finals[0].parent
            data = file_cache.read_json((ep / 'episode.json'))
            shots = data.get('shots') or []
            rec['artifact'] = {
                'episode_json': str(ep / 'episode.json'),
                'episode_sha256': _sha256(ep / 'episode.json'),
                'assets_json': (ep / 'assets.json').is_file(),
                'batch_ids': [s.get('batch_id') for s in shots],
                'missing_assets': data.get('missing_assets'),
                'assets_ready': data.get('assets_ready'),
                'asset_status': [s.get('asset_status') for s in shots],
            }
            rec['checks']['bundle_pair'] = (ep / 'assets.json').is_file()
            rec['checks']['batch_assigned'] = all(s.get('batch_id') for s in shots)
            rec['checks']['missing_recorded'] = 'CHAR_002' in \
                (data.get('missing_assets') or [])
            rec['checks']['lineage'] = (ep / '产物来源关系.json').is_file()
            # 完成核验：与阶段完成同一判据 stage_parallel.batches_ready（SG-03 口径）
            import orchestrator.stage_parallel as stage_parallel
            gate = stage_parallel.batches_ready(project)
            rec['gate'] = {'ok': gate.get('ok'), 'started': gate.get('started'),
                           'detail': str(gate.get('detail') or '')[:200]}
            rec['checks']['batches_ready_ok'] = bool(gate.get('ok'))
            # 工作稿退役：发布完成后原路径应已不在（进回收站）
            rec['checks']['working_source_retired'] = not source.is_file()
        # 桌面状态：status 文本/三虎播报不强求，产物即证据
        rec['status_tail'] = str(getattr(getattr(app, 'status', None), 'text', ''))[:200]
    except Exception:
        rec['traceback'] = traceback.format_exc()
    finally:
        try:
            win.destroy()
        except Exception:
            app_logging.swallowed()
    evidence['cases'].append(rec)
    return rec


def case_legacy(evidence):
    """C：旧项目——定稿产物在旧目录 06分镜定稿，工作稿仍被采用。

    先用 L3 入口（与按钮同一函数）在 retire_working 关闭的口径生成定稿、
    把产物挪进 06分镜定稿/分镜/（模拟旧版本布局），再从真实界面点
    「手动同步资产」：签名复用应命中旧目录、不新建 07分镜定稿。
    """
    rec = {'case': 'legacy_project', 'checks': {}}
    project, episode, source = make_project(WORK / 'case_legacy', adopt=True)
    # 1) 无退役生成定稿（等价旧版本产物），再整体挪进旧目录位。
    from orchestrator.storyboard_final import finalize
    from stage_execution_service import asset_plan_gateway
    first = finalize(project, episode, source, retire_working=lambda *a: None,
                     gateway=asset_plan_gateway())
    legacy_parent = project / '06分镜定稿' / '分镜'
    legacy_parent.mkdir(parents=True, exist_ok=True)
    legacy_dir = legacy_parent / first.name
    shutil.move(str(first), str(legacy_dir))
    shutil.rmtree(project / '07分镜定稿', ignore_errors=True)
    rec['checks']['legacy_dir_seeded'] = (legacy_dir / 'episode.json').is_file()
    rec['checks']['new_dir_absent'] = not (project / '07分镜定稿').exists()

    # 2) 真实界面再走一遍同一操作。
    win, app = open_desktop(project)
    try:
        iid = str(source.resolve())
        rec['checks']['catalog_row_visible'] = wait_until(
            win, lambda: find_tree_with(win, iid) is not None, timeout=30)
        tree = find_tree_with(win, iid)
        if tree is not None:
            tree.selection_set(iid)
            tree.focus(iid)
            tree.event_generate('<<TreeviewSelect>>')
            pump(win, 0.5)
        button = find_button(win, '手动同步资产')
        rec['checks']['button_found'] = button is not None
        if button is not None:
            try:
                button.invoke()
            except Exception as exc:
                rec['invoke_error'] = str(exc)
        # 签名复用是同步完成的；给事件循环一点余量。
        pump(win, 1.0)
        for _ in range(40):
            pump(win, 0.1)
        rec['checks']['no_new_07_dir'] = not (project / '07分镜定稿').exists()
        rec['checks']['legacy_dir_intact'] = (legacy_dir / 'episode.json').is_file()
        data = file_cache.read_json((legacy_dir / 'episode.json'))
        rec['legacy_episode_sha256'] = _sha256(legacy_dir / 'episode.json')
        rec['legacy_shots'] = len(data.get('shots') or [])
        import orchestrator.stage_parallel as stage_parallel
        gate = stage_parallel.batches_ready(project)
        rec['gate'] = {'ok': gate.get('ok'), 'started': gate.get('started'),
                       'detail': str(gate.get('detail') or '')[:200]}
        rec['checks']['batches_ready_ok'] = bool(gate.get('ok'))
    except Exception:
        rec['traceback'] = traceback.format_exc()
    finally:
        try:
            win.destroy()
        except Exception:
            app_logging.swallowed()
    evidence['cases'].append(rec)
    return rec


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence', required=True)
    args = parser.parse_args()
    global WORK
    import tempfile
    WORK = Path(tempfile.mkdtemp(prefix='acceptance-stage-op-'))
    evidence_dir = Path(args.evidence)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence = {'round': 'R3812', 'operation': 'S07 分镜定稿·手动同步资产',
                'entry_ui': 'ui/storyboard_files.py 手动同步资产按钮 → '
                            'desktop.make_final_storyboard → async_',
                'entry_service': 'orchestrator/storyboard_final_controller.'
                                 'finalize_stage_storyboard → '
                                 'orchestrator.storyboard_final.finalize',
                'work_dir': str(WORK), 'cases': []}
    started = time.time()
    try:
        case_missing_input(evidence)
        case_normal(evidence)
        case_legacy(evidence)
    except Exception:
        evidence['fatal'] = traceback.format_exc()
    evidence['elapsed'] = round(time.time() - started, 3)
    evidence['all_passed'] = all(
        all(c.get('checks', {}).values()) for c in evidence['cases']) \
        and 'fatal' not in evidence
    out = evidence_dir / 'stage_op_walkthrough.json'
    out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2),
                   encoding='utf-8')
    print(json.dumps({'all_passed': evidence['all_passed'],
                      'elapsed': evidence['elapsed'],
                      'cases': [{k: v for k, v in c.items() if k != 'checks'} |
                                {'checks': c.get('checks')} for c in evidence['cases']]},
                     ensure_ascii=False, indent=2))
    return 0 if evidence['all_passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
