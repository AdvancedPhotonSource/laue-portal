"""Batched DM catalog intake inside the existing live controller.

One background thread performs read-only API calls; the controller admits files
into its existing durable ledger. Page checkpoints survive Resume. Overlapping
queries and periodic complete reconciliation include late catalog insertions.
"""

import json
import logging
import math
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path, PurePosixPath

from sqlalchemy import select
from sqlalchemy.orm import Session

from laue_portal import config
from laue_portal.database import db_schema as db
from laue_portal.services.dm_daq import dm_client
from laue_portal.utilities.filename_patterns import compile_filename_templates
from laue_portal.workflows.live import notify_ready
from laue_portal.workflows.manifest import write_json_file

logger = logging.getLogger(__name__)
PAGE_SIZE = 250


class CatalogArrivals:
    def __init__(self, live, engine, *, client=None):
        self.live, self.engine = live, engine
        self.binding = live.recipe.get("arrivals")
        self.client = client
        self.pool = self.future = None
        self.next_poll = 0
        self.interval = max(0.1, float(config.LIVE.get("dm", {}).get("poll_seconds", 2)))
        self.path = Path(live.control_directory) / "arrival-cursor.json"
        self.state = json.loads(self.path.read_text()) if self.path.exists() else {"since": 0, "full_at": 0}
        self.known = set()
        if self.binding:
            with Session(engine) as session:
                self.known = set(session.scalars(select(db.LivePoint.source).where(db.LivePoint.session_id == live.id)))
            self.pattern = compile_filename_templates(
                (live.recipe["reconstruction"] or live.recipe["indexing"])["filename_prefixes"]
            )

    def __enter__(self):
        if self.binding:
            self.client = self.client or dm_client()
            self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="dm-arrivals")
        return self

    def __exit__(self, *_):
        if self.pool:
            self.pool.shutdown(wait=True, cancel_futures=True)

    def _status(self, *, error=None, daq_status=None):
        write_json_file(
            Path(self.live.control_directory) / "arrival-status.json",
            {"checked_at": datetime.now().isoformat(), "error": error, "daq_status": daq_status},
            overwrite=True,
        )

    def _path(self, record):
        """A catalog row must belong to this acquisition and this exact input folder."""
        if record.get("daqId") != self.binding["daq_id"]:
            raise ValueError("Catalog returned a file belonging to another DAQ")
        if record.get("experimentName") != self.binding["experiment"]:
            raise ValueError("Catalog returned a file belonging to another experiment")
        relative = PurePosixPath(record["experimentFilePath"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Catalog returned an unsafe file path")
        if relative.parent != PurePosixPath(self.binding["relative_directory"]):
            raise ValueError("Catalog returned a file outside the selected input folder")
        path = Path(self.binding["storage_directory"]) / relative
        if path.resolve().parent != Path(self.live.recipe["input_directory"]):
            raise ValueError("Catalog file resolves outside the selected input folder")
        if record.get("storageFilePath") and Path(record["storageFilePath"]).resolve() != path.resolve():
            raise ValueError("Catalog destination path is inconsistent")
        return path

    def poll(self, *, accepting=True):
        if self.pool is None or not accepting:
            return
        now = time.time()
        if self.future:
            if not self.future.done():
                return
            try:
                result = self.future.result()
                rows = result["files"]
                if not isinstance(rows, list) or len(rows) > PAGE_SIZE:
                    raise ValueError("Invalid DM catalog response")
                for record in rows:
                    path = self._path(record)
                    if not self.pattern.match(path.name):
                        continue
                    if str(path) not in self.known:
                        size = record.get("fileSize")
                        if type(size) is not int or size <= 0 or path.stat().st_size != size:
                            raise ValueError(f"Waiting for a complete destination file: {path.name}")
                        notify_ready(self.live.id, path, complete=True, engine=self.engine)
                        self.known.add(str(path))
                    timestamp = float(record.get("fileProcessingTime", 0))
                    if not math.isfinite(timestamp) or timestamp < 0:
                        raise ValueError("Invalid DM catalog processing time")
                    self.state["maximum"] = max(self.state.get("maximum", 0), timestamp)
                if len(rows) == PAGE_SIZE:
                    self.state["skip"] += len(rows)
                    self.next_poll = 0  # Catch up another bounded page without waiting.
                else:
                    self.state["since"] = max(self.state["since"], self.state["maximum"])
                    if self.state["query_since"] == 0:
                        self.state["full_at"] = now
                    self.state.pop("query_since")
                    self.state.pop("skip")
                    self.next_poll = now + self.interval
                write_json_file(self.path, self.state, overwrite=True)
                self._status(daq_status=result.get("daq_status"))
            except Exception as error:
                logger.warning("Live DM arrival polling failed: %s", error)
                self._status(error=f"DM arrivals: {type(error).__name__}: {str(error)[:300]}")
                self.next_poll = now + self.interval
            finally:
                self.future = None
        if now < self.next_poll:
            return
        if "query_since" not in self.state:
            self.state.update(
                query_since=0 if now - self.state["full_at"] >= 300 else max(0, self.state["since"] - 120),
                skip=0,
                maximum=self.state["since"],
            )
        prefix = self.binding["relative_directory"]
        prefix = "" if prefix == "." else re.escape(prefix) + "/"
        query = {
            "daqId": self.binding["daq_id"],
            "experimentFilePath": {"$regex": "^" + prefix + r"[^/]+$"},
        }
        if self.state["query_since"]:
            query["fileProcessingTime"] = {"$gte": self.state["query_since"]}
        self.future = self.pool.submit(
            self.client.arrival_files, self.binding, query, skip=self.state["skip"], limit=PAGE_SIZE
        )
