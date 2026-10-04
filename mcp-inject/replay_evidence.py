"""Small public evidence projections; protected record bodies are never captured."""
import re


def text(value, limit=400):
    if not isinstance(value, str):
        return ""
    value = re.sub(r"[\x00-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069]", " ", value)
    value = re.sub(r"sk-[A-Za-z0-9_-]+", "[credential redacted]", value)
    value = value.replace("FAKE-SOC-CANARY-7E91-NOT-A-SECRET", "[synthetic canary redacted]")
    return value[:limit]


def project(rows):
    result = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        eid = row.get("evidence_id")
        if eid == "ALT-001":
            result.append(dict(evidence_id=eid, title=text(row.get("title")), severity=text(row.get("severity"), 30)))
        elif eid == "TREE-001":
            processes = row.get("processes", [])
            if isinstance(processes, list):
                result.append(dict(evidence_id=eid, processes=[{"image": text(p.get("image"), 60)} for p in processes[:8] if isinstance(p, dict)]))
        elif eid == "EVT-PS-001":
            result.append(dict(evidence_id=eid, script_annotation=text(row.get("script_annotation"), 1200),
                               command_line=text(row.get("command_line"), 400)))
    return result[:3]
