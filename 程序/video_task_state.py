"""Read task activity without starting, cancelling, or resubmitting a job."""
from pathlib import Path
from agent.core import read
from file_cache import read_json_shared as read_cached
from storyboard_paths import project_root

ACTIVE={'submitting','unknown','queued','running','succeeded'}
VIDEO_MAX_SHOTS=100
MANIFEST_NAMES=('videos.json','video_manifest.json')


def shot_count_error(shots):
    """单项目视频镜头数上限的唯一判定：已删除镜头不计数；超限返回给用户看的原因，否则返回空串。"""
    count=sum(1 for shot in shots or () if isinstance(shot,dict) and not shot.get('video_deleted'))
    if count<=VIDEO_MAX_SHOTS:return ''
    return '本项目有 %d 个视频镜头，超过上限 %d 镜/项目；请把剧本拆成多集或多个项目后再制作视频。'%(count,VIDEO_MAX_SHOTS)


def provider_failure_reason(version):
    """供应商终态的恢复说明；不推断退款，也不触发重投。"""
    terminal = str(version.get('provider_status') or '').lower()
    reason = {'canceled': '服务商已取消任务', 'cancelled': '服务商已取消任务',
              'expired': '服务商任务已过期'}.get(terminal)
    if reason:return '原因：'+reason+'；不会自动重新提交'
    if not (version.get('error') or version.get('error_code')):
        return '原因未知：服务商未提供错误码，请到服务商控制台核实'
    return ''


def generation_active(studio,sid):
    versions=studio.state().get('shots',{}).get(sid,[])
    if versions and versions[-1].get('state') in ACTIVE:return True
    root=Path(studio.root)
    project=project_root(root)
    source=Path(studio.episode_path).resolve()
    own_root=root.resolve()
    # A different provider/session can still be generating the same shot.
    for config_path in (project/'cloud_video').glob('*/config.json'):
        if config_path.parent.resolve()==own_root:continue
        try:
            cfg=read_cached(config_path)
        except (OSError,ValueError):
            continue
        if not isinstance(cfg,dict) or not cfg.get('episode_file') or Path(cfg['episode_file']).resolve()!=source:continue
        state_path=config_path.parent/'data/state.json'
        if state_path.is_file():
            try:
                state=read_cached(state_path)
            except (OSError,ValueError):
                continue
            if not isinstance(state,dict):continue
            versions=state.get('shots',{}).get(sid,[])
            if isinstance(versions,list) and versions and versions[-1].get('state') in ACTIVE:return True
    return False


def prompt_locked(app,sid):
    return sid in (getattr(app,'submitting_sid',None),getattr(app,'local_submit_sid',None)) or generation_active(app.studio,sid)


def assert_prompt_editable(app,sid=None):
    sid=sid or app.sid()
    if prompt_locked(app,sid):raise ValueError(sid+' 正在生成或等待结果，完成后才能修改提示词、资产或调用 MCP。')


def poll_delay(count=1):return max(1.0,5.0/max(1,count))


def elapsed_text(version,now):
    started=version.get('created')
    if not isinstance(started,(int,float)):return ''
    total=max(0,int(now-started));minutes,seconds=divmod(total,60)
    return f' · 已等待 {minutes}分{seconds:02}秒'


def submission_block_reason(versions):
    """只判断显式生成请求；返工保留旧版，未决任务禁止再次提交。"""
    if any(version.get('state') not in ('downloaded', 'failed', 'rejected') for version in versions):
        return '此镜头已有未完成或结果不确定的任务，只能查询或恢复编号'
    downloaded = next((version for version in reversed(versions) if version.get('state') == 'downloaded'), None)
    if downloaded is not None and downloaded.get('review') != 'revise':
        return '此镜头视频已就绪；重做前请先标记需修改，旧版本会保留'
    return ''
