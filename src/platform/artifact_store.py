"""Durable mirror of discussion records in Vercel Blob.

Serverless instances have to assume any request may land on a process that did
not generate the record, so completed/partial records are mirrored to Blob and
pulled back on a local miss. Everything degrades to local files when the store
is not connected or the network call fails.
"""

import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)

PREFIX = "discussions/"

_TOKEN_ENV_VARS = ("BLOB_READ_WRITE_TOKEN", "VERCEL_BLOB_READ_WRITE_TOKEN")

# A concurrent reader may hold the destination open on Windows, so the rename
# is retried exactly like src/discussion/persistence.py does.
_REPLACE_ATTEMPTS = 5
_REPLACE_DELAY_SECONDS = 0.05


def enabled() -> bool:
    """Whether a Blob store is connected to this deployment."""
    if any(os.environ.get(name) for name in _TOKEN_ENV_VARS):
        return True
    # A store connected through OIDC exposes its id instead of a read-write
    # token; calls then fail and degrade, but the mirror stays configured.
    return bool(os.environ.get("BLOB_STORE_ID"))


def _pathname(discussion_id: str) -> str:
    return f"{PREFIX}{discussion_id}.json"


def _write_atomically(destination: Path, payload: bytes) -> None:
    """Materialise ``payload`` at ``destination`` without partial reads."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = destination.parent / f".{destination.name}.tmp.{os.getpid()}"

    try:
        temporary_path.write_bytes(payload)

        for attempt in range(_REPLACE_ATTEMPTS):
            try:
                os.replace(temporary_path, destination)
                break
            except OSError:
                if attempt == _REPLACE_ATTEMPTS - 1:
                    raise
                time.sleep(_REPLACE_DELAY_SECONDS * (attempt + 1))
    finally:
        if temporary_path.exists():
            try:
                temporary_path.unlink()
            except OSError:
                pass


def push_discussion(discussion_id: str, payload: bytes) -> None:
    """Mirror one discussion record; never raise into a running deliberation."""
    try:
        from vercel.blob import BlobClient

        BlobClient().put(
            _pathname(discussion_id),
            payload,
            access="private",
            overwrite=True,
            content_type="application/json",
        )
    except Exception as exc:
        logger.warning("Could not mirror discussion %s to Blob: %s", discussion_id, exc)


def pull_discussion(discussion_id: str, destination: Path) -> bool:
    """Copy a mirrored record into ``destination``.

    Returns False when the record is absent or the store is unreachable, so the
    caller keeps its existing "not found" behaviour.
    """
    try:
        from vercel.blob import BlobClient, BlobNotFoundError

        try:
            result = BlobClient().get(_pathname(discussion_id), access="private")
        except BlobNotFoundError:
            return False

        if result is None or result.status_code != 200 or not result.content:
            return False

        _write_atomically(Path(destination), result.content)
        return True
    except Exception as exc:
        logger.warning("Could not restore discussion %s from Blob: %s", discussion_id, exc)
        return False


def list_discussion_ids() -> list[str]:
    """Return every mirrored discussion id, oldest page first."""
    try:
        from vercel.blob import list_objects

        discussion_ids: list[str] = []
        cursor: str | None = None

        while True:
            page = list_objects(prefix=PREFIX, limit=1000, cursor=cursor)

            for blob in page.blobs:
                pathname = blob.pathname

                if pathname.startswith(PREFIX) and pathname.endswith(".json"):
                    discussion_ids.append(pathname[len(PREFIX):-len(".json")])

            if not page.has_more or not page.cursor:
                break

            cursor = page.cursor

        return discussion_ids
    except Exception as exc:
        logger.warning("Could not list mirrored discussions from Blob: %s", exc)
        return []
