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
    total_assets: int = 0
    processed_assets: int = 0
    current_asset: Optional[str] = None
    last_message: Optional[str] = None
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

    def mark_running(self, job_id: str, total_assets: int) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "running"
                job.total_assets = total_assets
                job.processed_assets = 0
                job.current_asset = None
                job.last_message = "Processamento iniciado."
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
                job.current_asset = None
                job.last_message = "Processamento concluído."
                job.updated_at = time.time()

    def fail_job(self, job_id: str, error_message: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "failed"
                job.error_message = error_message
                job.current_asset = None
                job.last_message = "Processamento interrompido."
                job.updated_at = time.time()

    def update_progress(
        self,
        job_id: str,
        processed_assets: int,
        current_asset: str,
        results: List[Dict[str, str]],
        failures: List[Dict[str, str]],
        message: str,
    ) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.processed_assets = processed_assets
                job.current_asset = current_asset
                job.results = list(results)
                job.failures = list(failures)
                job.last_message = message
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
                total_assets=job.total_assets,
                processed_assets=job.processed_assets,
                current_asset=job.current_asset,
                last_message=job.last_message,
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


class DataComJobProgressUpdater:
    def __init__(self, job_store: DataComJobStore, job_id: str, total_assets: int) -> None:
        self._job_store = job_store
        self._job_id = job_id
        self._total_assets = total_assets

    def mark_running(self) -> None:
        self._job_store.mark_running(self._job_id, self._total_assets)
        print(
            f"[data-com][job {self._job_id}] Iniciando processamento de {self._total_assets} ativos."
        )

    def report_progress(
        self,
        processed_assets: int,
        current_asset: str,
        results: List[Dict[str, str]],
        failures: List[Dict[str, str]],
        message: str,
    ) -> None:
        self._job_store.update_progress(
            self._job_id,
            processed_assets,
            current_asset,
            results,
            failures,
            message,
        )
        print(
            f"[data-com][job {self._job_id}] {message} ({processed_assets}/{self._total_assets})."
        )

    def mark_completed(self, results: List[Dict[str, str]], failures: List[Dict[str, str]]) -> None:
        self._job_store.complete_job(self._job_id, results, failures)
        print(f"[data-com][job {self._job_id}] Processamento concluído.")

    def mark_failed(self, error_message: str) -> None:
        self._job_store.fail_job(self._job_id, error_message)
        print(f"[data-com][job {self._job_id}] Falha: {error_message}")
