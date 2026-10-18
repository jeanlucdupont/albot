#!/usr/bin/env python3
"""ArtifactDump: extracted browser/EVTX/MFT/Prefetch/Registry files to CSV/JSON.

Python 3.11+. Browser needs no additional packages.
Optional dependencies:
  EVTX:     pip install python-evtx defusedxml
  MFT:      pip install dissect.ntfs
  Prefetch: pip install libscca-python
  Registry: pip install libregf-python

Examples:
  python artifactdump.py evtx Security.evtx --output events-export
  python artifactdump.py browser History --browser chrome --profile Default --output browser-export

Adapted from Jean-Luc Dupont's Locard (Apache-2.0):
https://github.com/jeanlucdupont/locard
Modified 2026-10-18: standalone exports and single-file packaging.
Optional dependencies retain their respective licenses, including AGPL-3.0-or-later
(dissect.ntfs) and LGPL-3.0-or-later (libscca-python/libregf-python).
"""
# ---- common ----
"""Small standalone record/provenance helpers; adapted from Locard."""
import hashlib as common_hashlib
import json as common_json

def common_dump(value):
    return common_json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))

def common_digest(path):
    result = common_hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()

def common_context_id(sha, product, profile):
    return 'BROWSERCTX:' + common_hashlib.sha256(common_dump([sha, product, profile]).encode()).hexdigest()

def common_base_record(eid, kind, subtype, locator, warnings=None, original=None):
    return dict(evidence_id=eid, source_type=kind, artifact_type=subtype, locator_json=common_dump(locator), warnings_json=common_dump(warnings or []), original_json=common_dump(original or {}))

# ---- times ----
"""Integer FILETIME normalization without loss of the 100ns source precision."""
from datetime import datetime as times_datetime, timedelta as times_timedelta, timezone as times_timezone

def times_filetime(value, slot, source, meaning):
    result = dict(slot=slot, original_value=str(value) if value is not None else None, encoding='FILETIME', source=source, meaning=meaning, precision_ns=100, timestamp_utc=None, normalization_status='missing' if value in (None, 0) else 'invalid')
    if value is not None and isinstance(value, int) and (0 < value < 2 ** 64):
        try:
            seconds, ticks = divmod(value, 10000000)
            dt = times_datetime(1601, 1, 1, tzinfo=times_timezone.utc) + times_timedelta(seconds=seconds)
            result.update(timestamp_utc=dt.strftime('%Y-%m-%dT%H:%M:%S') + f'.{ticks * 100:09d}Z', normalization_status='normalized')
        except (ValueError, OverflowError):
            pass
    return result

# ---- registry_logs ----
"""Filename-designated Registry companions; no replay or content validation."""
from pathlib import Path as registry_logs_Path
registry_logs_LIMITATION = 'Registry transaction-log replay is not supported; companion was not parsed as a hive'
registry_logs_CLASSIFIER = 'locard-registry-companion-classifier'

def registry_logs_is_log(path):
    return registry_logs_Path(path).suffix.casefold() in ('.log1', '.log2')

def registry_logs_describe(path):
    path = registry_logs_Path(path)
    candidates = []
    for sibling in path.parent.iterdir():
        if sibling.name.casefold() != path.stem.casefold() or sibling.is_symlink() or (not sibling.is_file()):
            continue
        with sibling.open('rb') as stream:
            if stream.read(4) == b'regf':
                candidates.append(str(sibling))
    return dict(classification='registry_transaction_log', classification_basis='Filename suffix .LOG1/.LOG2; log contents not validated', companion_hive=candidates[0] if len(candidates) == 1 else None, companion_basis='Possible companion by same-directory case-insensitive filename; not verified' if len(candidates) == 1 else 'Unmatched or ambiguous companion filename', limitation=registry_logs_LIMITATION, replay_performed=False)

# ---- mft ----
"""Dissect performs binary decoding/fixups; Locard preserves slots and semantics."""
import base64 as mft_base64
import io as mft_io
from functools import lru_cache as mft_lru_cache
mft_PARSER = 'dissect.ntfs'

def mft_parse(path, sha, record_size=None):
    from dissect.ntfs.mft import MftRecord
    from dissect.ntfs.attr import Attribute, AttributeHeader
    from dissect.ntfs.c_ntfs import c_ntfs
    with open(path, 'rb') as fh:
        first = fh.read(64)
        if record_size is None:
            if first[:4] != b'FILE':
                raise ValueError('MFT header invalid; record framing cannot be established')
            record_size = int(c_ntfs._FILE_RECORD_SEGMENT_HEADER(first).BytesAllocated)
        if record_size not in (512, 1024, 2048, 4096, 8192, 16384, 32768, 65536):
            raise ValueError('Unsupported MFT record size')
        fh.seek(0)
