"""Queue-to-session state adapter; worker completion is not always success."""

from queue import Empty


def consume_download_progress(state):
    """Drain updates, preserving terminal status and the caller's cancel event."""
    terminal = None
    while True:
        try:
            update = state["progress_queue"].get_nowait()
        except Empty:
            break
        if isinstance(update, dict) and update.get("type") == "finished":
            terminal = update
        elif isinstance(update, int) and terminal is None and not state.get("download_outcome"):
            state["progress"] = max(0, min(99, update))
    if terminal is None:
        return False
    state["download_outcome"] = terminal
    state["task_running"] = False
    total = terminal["total_intervals"]
    completed = terminal["completed_intervals"]
    state["progress"] = 100 if terminal["status"] == "completed" else min(99, int(100 * completed / total)) if total else 0
    return True


def download_worker_alive(state):
    worker = state.get("download_thread")
    return worker is not None and worker.is_alive()


def collect_download_files(state):
    """Keep published file lists pending until an explicit merge succeeds."""
    if "download_files" not in state:
        state["download_files"] = []
    while True:
        try:
            files = state["result_queue"].get_nowait()
        except Empty:
            break
        if files:
            state["download_files"].extend(files)
    return state["download_files"]
