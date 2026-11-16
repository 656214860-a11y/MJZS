"""Post-window-close dispatch policy; scheduled never means cleanup completed."""


def launch_cleanup(program, *, forced=False):
    """Preserve launch order and errors, without waiting, retrying or serializing workers.

    Storage is attempted even on forced exit and its errors propagate. Optional
    workers only suppress OSError. The fixed-size summary contains no paths,
    exception text or worker output; the existing workers own cleanup results.
    Repeated-close protection remains owned by Desktop.close, not this function.
    """
    result = dict.fromkeys(('storage', 'logs', 'workspace'), 'not-attempted')
    if forced:
        result.update(logs='skipped-force', workspace='skipped-force')
    try:
        from storage_maintenance import launch_cleanup as storage
        result['storage'] = 'launch-failed'
        storage(program)
        result['storage'] = 'scheduled'
        if not forced:
            try:
                from infra.log_maintenance import launch_cleanup as logs
                result['logs'] = 'launch-failed'
                logs(program)
                result['logs'] = 'scheduled'
            except OSError:
                pass
            try:
                from infra.workspace_maintenance import launch_cleanup as workspace
                result['workspace'] = 'launch-failed'
                workspace(program)
                result['workspace'] = 'scheduled'
            except OSError:
                pass
        return result
    finally:
        # A broken output stream must not mask the existing launch exception.
        try:
            print('exit-maintenance dispatch: ' + ', '.join(
                f'{name}={status}' for name, status in result.items())
                + '; completion=unobserved')
        except (OSError, ValueError):
            pass
