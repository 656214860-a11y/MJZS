"""Replace only this adapter when selecting an actual domestic provider."""
from abc import ABC, abstractmethod


class VideoAdapter(ABC):
    @abstractmethod
    def submit(self, shot, frame, request_id):
        """Return durable provider task ID. Never blindly retry a paid POST."""

    @abstractmethod
    def poll(self, task_id):
        """Return {status: queued|running|succeeded|failed, url?: HTTPS URL}."""
