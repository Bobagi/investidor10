from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional
from uuid import uuid4


@dataclass
class DataComJobResult:
    status: str
    results: List[Dict[str, str]] = field(default_factory=list)
    failures: List[Dict[str, str]] = field(default_factory=list)
    error_message: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class DataComJobStore:
    def __init__(self) -> None:
        self._jobs: Dict[str, DataComJobResult] = {}
        self._lock = threading.Lock()

    def create_job(self) -> str:
        job_id = str(uuid4())
        with self._lock:
            self._jobs[job_id] = DataComJobResult(status="pending")
        return job_id

    def mark_running(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "running"
                job.updated_at = time.time()

    def complete_job(
        self,
        job_id: str,
        results: List[Dict[str, str]],
        failures: List[Dict[str, str]],
    ) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "completed"
                job.results = results
                job.failures = failures
                job.updated_at = time.time()

    def fail_job(self, job_id: str, error_message: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "failed"
                job.error_message = error_message
                job.updated_at = time.time()

    def get_job(self, job_id: str) -> Optional[DataComJobResult]:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            return DataComJobResult(
                status=job.status,
                results=list(job.results),
                failures=list(job.failures),
                error_message=job.error_message,
                created_at=job.created_at,
                updated_at=job.updated_at,
            )


@dataclass
class CachedDividendDate:
    date_com_date: date
    cached_at: float


class DividendDateCache:
    def __init__(self, ttl_seconds: float) -> None:
        self._ttl_seconds = ttl_seconds
        self._entries: Dict[str, CachedDividendDate] = {}
        self._lock = threading.Lock()

    def get(self, cache_key: str) -> Optional[date]:
        with self._lock:
            cached_entry = self._entries.get(cache_key)
            if not cached_entry:
                return None
            if time.time() - cached_entry.cached_at > self._ttl_seconds:
                del self._entries[cache_key]
                return None
            return cached_entry.date_com_date

    def set(self, cache_key: str, date_com_date: date) -> None:
        with self._lock:
            self._entries[cache_key] = CachedDividendDate(
                date_com_date=date_com_date,
                cached_at=time.time(),
            )
