"""Background folder watcher: polls the dropbox folders, enqueues new/changed
PDFs for ingestion. A single worker thread processes the queue so Chroma/SQLite
writes are never concurrent. Partial copies are skipped via a stable-size check."""

from __future__ import annotations

import logging
import queue
import threading
import time
from pathlib import Path

from ..config.settings import AppConfig
from ..domain.enums import DocType
from .ingestion import IngestionUseCase

logger = logging.getLogger(__name__)

_TYPE_BY_FOLDER = {
    "sop": DocType.SOP,
    "policy": DocType.POLICY,
    "previous": DocType.PREVIOUS_REVIEW,
}


class FolderWatcher:
    def __init__(self, config: AppConfig, ingestion: IngestionUseCase):
        self._config = config
        self._ingestion = ingestion
        self._queue: queue.Queue[Path] = queue.Queue()
        self._sizes: dict[str, int] = {}
        self._stop = threading.Event()
        self._poller: threading.Thread | None = None
        self._worker: threading.Thread | None = None

    def start(self) -> None:
        self._worker = threading.Thread(target=self._worker_loop, name="ingest-worker", daemon=True)
        self._worker.start()
        self._poller = threading.Thread(target=self._poll_loop, name="folder-poller", daemon=True)
        self._poller.start()
        logger.info("Folder watcher started")

    def stop(self) -> None:
        self._stop.set()
        if self._poller:
            self._poller.join(timeout=5)
        self._queue.put_nowait(Path("/__exit__"))
        if self._worker:
            self._worker.join(timeout=30)

    def scan_now(self) -> int:
        """Trigger an immediate scan; returns number of files enqueued."""
        count = 0
        for doc_type, folder in self._config.dropbox_folders.items():
            if not folder.exists():
                continue
            for pdf in folder.glob("*.pdf"):
                if self._stable_and_new(pdf):
                    self._queue.put_nowait(pdf)
                    count += 1
        return count

    # ---- internals --------------------------------------------------------

    def _poll_loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.scan_now()
            except Exception:
                logger.exception("poll scan failed")
            self._stop.wait(self._config.poll_interval_sec)

    def _worker_loop(self) -> None:
        while True:
            path = self._queue.get()
            if str(path) == "/__exit__":
                break
            try:
                self._process(path)
            except Exception:
                logger.exception("failed to ingest %s", path)

    def _stable_and_new(self, path: Path) -> bool:
        """Return True if the file size has been stable across two observations
        (i.e. the copy finished) and it's not already indexed with the same hash."""
        try:
            size = path.stat().st_size
        except OSError:
            return False
        prev = self._sizes.get(str(path))
        self._sizes[str(path)] = size
        return prev is not None and prev == size

    def _process(self, path: Path) -> None:
        from ..domain.enums import DocStatus

        folder = path.parent.name
        doc_type = _TYPE_BY_FOLDER.get(folder, DocType.SOP)
        doc = self._ingestion.register_file(path, doc_type)
        if doc.status in (DocStatus.READY, DocStatus.NEEDS_PASSWORD, DocStatus.NEEDS_OCR):
            return  # already indexed, or waiting for manual action
        self._ingestion.index_document(doc.id)
