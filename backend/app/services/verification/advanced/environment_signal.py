from __future__ import annotations

from statistics import fmean
from typing import Any

ALGORITHM_VERSION = "environment-signal-v1"


def _access_points(snapshot: dict[str, Any]) -> dict[str, tuple[float, int]]:
    result: dict[str, tuple[float, int]] = {}
    rows = snapshot.get("accessPoints")
    if not isinstance(rows, list):
        return result
    for row in rows:
        if not isinstance(row, dict):
            continue
        ap_hash = row.get("apHash")
        rssi = row.get("rssiDbm")
        frequency = row.get("frequencyMhz")
        if not isinstance(ap_hash, str) or len(ap_hash) != 64:
            continue
        if not isinstance(rssi, (int, float)) or not isinstance(frequency, int):
            continue
        result[ap_hash] = (float(rssi), frequency)
    return result


def analyze_environment_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Compare start/end Wi-Fi fingerprints without treating Wi-Fi as mandatory evidence."""
    environment = metadata.get("environment")
    if not isinstance(environment, dict):
        return {
            "status": "UNAVAILABLE",
            "consistency_score": None,
            "risk_score": 0.0,
            "confidence": 0.0,
            "reason_codes": ["ENVIRONMENT_EVIDENCE_UNAVAILABLE"],
            "reasons": ["No privacy-preserving Wi-Fi environment evidence was captured."],
            "metrics": {
                "algorithmVersion": ALGORITHM_VERSION,
                "snapshotCount": 0,
                "supportingEvidenceOnly": True,
            },
        }

    snapshots = environment.get("snapshots")
    if not isinstance(snapshots, list) or len(snapshots) < 2:
        return {
            "status": "LIMITED",
            "consistency_score": None,
            "risk_score": 0.0,
            "confidence": 0.1,
            "reason_codes": ["ENVIRONMENT_EVIDENCE_LIMITED"],
            "reasons": ["Environment evidence did not contain both start and end observations."],
            "metrics": {
                "algorithmVersion": ALGORITHM_VERSION,
                "snapshotCount": len(snapshots) if isinstance(snapshots, list) else 0,
                "supportingEvidenceOnly": True,
            },
        }

    start = _access_points(snapshots[0] if isinstance(snapshots[0], dict) else {})
    end = _access_points(snapshots[-1] if isinstance(snapshots[-1], dict) else {})
    start_hashes = set(start)
    end_hashes = set(end)
    union = start_hashes | end_hashes
    overlap = start_hashes & end_hashes

    if not union:
        wifi_enabled = any(
            isinstance(snapshot, dict) and bool(snapshot.get("wifiEnabled"))
            for snapshot in snapshots
        )
        permission_granted = all(
            isinstance(snapshot, dict) and bool(snapshot.get("permissionGranted"))
            for snapshot in (snapshots[0], snapshots[-1])
        )
        code = "ENVIRONMENT_SCAN_EMPTY" if wifi_enabled and permission_granted else "ENVIRONMENT_EVIDENCE_UNAVAILABLE"
        return {
            "status": "LIMITED",
            "consistency_score": None,
            "risk_score": 0.0,
            "confidence": 0.15 if wifi_enabled and permission_granted else 0.0,
            "reason_codes": [code],
            "reasons": ["Wi-Fi remained optional and no usable nearby access-point fingerprint was available."],
            "metrics": {
                "algorithmVersion": ALGORITHM_VERSION,
                "snapshotCount": len(snapshots),
                "startAccessPoints": 0,
                "endAccessPoints": 0,
                "supportingEvidenceOnly": True,
                "ssidStored": False,
                "rawBssidStored": False,
            },
        }

    jaccard = len(overlap) / len(union)
    rssi_similarity = 0.0
    if overlap:
        similarities = [
            max(0.0, 1.0 - abs(start[ap_hash][0] - end[ap_hash][0]) / 30.0)
            for ap_hash in overlap
        ]
        rssi_similarity = fmean(similarities)
    consistency = max(0.0, min(1.0, 0.80 * jaccard + 0.20 * rssi_similarity))
    risk = max(0.0, min(1.0, 1.0 - consistency))
    evidence_count = min(len(start), len(end))
    confidence = min(0.90, 0.40 + 0.04 * min(evidence_count, 8) + 0.15 * jaccard)

    if consistency >= 0.55:
        status = "CONSISTENT"
        codes: list[str] = []
        reasons = ["Nearby Wi-Fi fingerprints remained consistent across the live capture."]
    elif consistency >= 0.25:
        status = "PARTIAL"
        codes = ["ENVIRONMENT_CHANGED"]
        reasons = ["Nearby Wi-Fi fingerprints changed during capture; this remains supporting evidence only."]
    else:
        status = "MISMATCH"
        codes = ["ENVIRONMENT_MISMATCH"]
        reasons = ["Start and end Wi-Fi fingerprints had little overlap; Wi-Fi alone cannot fail verification."]

    return {
        "status": status,
        "consistency_score": consistency,
        "risk_score": risk,
        "confidence": confidence,
        "reason_codes": codes,
        "reasons": reasons,
        "metrics": {
            "algorithmVersion": ALGORITHM_VERSION,
            "snapshotCount": len(snapshots),
            "startAccessPoints": len(start),
            "endAccessPoints": len(end),
            "overlapAccessPoints": len(overlap),
            "jaccardSimilarity": round(jaccard, 6),
            "rssiSimilarity": round(rssi_similarity, 6),
            "supportingEvidenceOnly": True,
            "ssidStored": False,
            "rawBssidStored": False,
            "hashScope": "SESSION",
        },
    }
