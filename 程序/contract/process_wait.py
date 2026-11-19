"""Pure bounded-polling decisions for an already launched subprocess."""


def _started_stop(process, stopped, terminate, stopped_type):
    terminated = terminate(process)
    error = stopped_type(stopped.reason, started=True)
    error.process_tree_terminated = bool(terminated)
    raise error from None


def controlled_communicate(process, data, timeout, control, runtime):
    """Communicate while checking cancel/deadline at most every 100 ms."""
    terminate, stopped_type, monotonic, timeout_expired = runtime
    deadline = monotonic() + float(timeout)
    payload = data
    while True:
        try:
            wait = min(.1, max(.001, deadline - monotonic()), control.remaining(timeout))
        except stopped_type as stopped:
            _started_stop(process, stopped, terminate, stopped_type)
        try:
            return process.communicate(payload, timeout=wait)
        except timeout_expired:
            payload = None
            try:
                control.checkpoint()
            except stopped_type as stopped:
                _started_stop(process, stopped, terminate, stopped_type)
            if monotonic() >= deadline:
                terminate(process)
                try:
                    process.wait(timeout=3)
                except timeout_expired:
                    process.kill()
                    process.wait(timeout=3)
                raise


def controlled_wait(process, timeout, control, runtime):
    """Wait for a streaming process while checking cancel/deadline every 100 ms."""
    terminate, stopped_type, monotonic, timeout_expired = runtime
    deadline = monotonic() + float(timeout)
    while True:
        try:
            wait = min(.1, max(.001, deadline - monotonic()), control.remaining(timeout))
        except stopped_type as stopped:
            _started_stop(process, stopped, terminate, stopped_type)
        try:
            process.wait(timeout=wait)
            return
        except timeout_expired:
            try:
                control.checkpoint()
            except stopped_type as stopped:
                _started_stop(process, stopped, terminate, stopped_type)
            if monotonic() >= deadline:
                raise
