"""Replace only this adapter when selecting an actual domestic provider."""
from abc import ABC, abstractmethod
import base64
import os
import urllib.parse
from .core import request


class VideoAdapter(ABC):
    @abstractmethod
    def submit(self, shot, frame, request_id):
        """Return durable provider task ID. Never blindly retry a paid POST."""

    @abstractmethod
    def poll(self, task_id):
        """Return {status: queued|running|succeeded|failed, url?: HTTPS URL}."""


class ContractExampleAdapter(VideoAdapter):
    """Fictional protocol for tests/local gateway; NOT a real vendor API."""
    def __init__(self, cfg):
        self.cfg = cfg
        self.base = cfg["base_url"].rstrip("/")
        self.headers = {"Authorization": "Bearer " + os.environ.get(cfg["key_env"], "")}

    def submit(self, shot, frame, request_id):
        # ADAPT 1: authentication/signing, endpoint, image upload/object storage.
        # ADAPT 2: model/duration/audio/dialogue field names, idempotency support.
        result = request(self.base + "/tasks", {
            "model": self.cfg["model"], "prompt": shot["video_prompt"],
            "duration": shot["duration"], "generate_audio": True,
            "image_base64": base64.b64encode(frame.read_bytes()).decode()
        }, {**self.headers, "Idempotency-Key": request_id})
        return str(result["task_id"])

    def poll(self, task_id):
        # ADAPT 3: task query path, vendor statuses, failure and signed output URL.
        result = request(self.base + "/tasks/" + urllib.parse.quote(task_id, safe=""), headers=self.headers)
        return {"status": result["status"], "url": result.get("video_url")}


def adapter(cfg):
    if cfg["adapter"] == "volcengine":
        from .volcengine import VolcengineAdapter
        return VolcengineAdapter(cfg)
    if cfg["adapter"] == "contract_example":
        return ContractExampleAdapter(cfg)
    raise ValueError("视频服务商尚未接入：请按 docs/视频API接入.md 实现并注册 adapter")
