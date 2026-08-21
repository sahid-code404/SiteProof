from __future__ import annotations

from typing import Any

from app.models.advanced_security import DeviceAttestation

ALGORITHM_VERSION = "device-metadata-risk-v1"


def analyze_device_metadata(
    metadata: dict[str, Any] | None,
    attestation: DeviceAttestation | None,
) -> dict[str, Any]:
    device = (metadata or {}).get("device")
    if not isinstance(device, dict):
        device = {}

    codes: list[str] = []
    reasons: list[str] = []
    score = 0.0
    confidence = 0.25
    status = "INCONCLUSIVE"

    fingerprint = str(device.get("fingerprint") or "").lower()
    hardware = str(device.get("hardware") or "").lower()
    model = str(device.get("model") or "").lower()
    manufacturer = str(device.get("manufacturer") or "").lower()
    brand = str(device.get("brand") or "").lower()
    product = str(device.get("product") or "").lower()
    tags = str(device.get("buildTags") or "").lower()
    emulator_flag = bool(device.get("emulatorHeuristic", False))

    emulator_words = ("generic", "emulator", "sdk_gphone", "goldfish", "ranchu", "genymotion")
    emulator_detected = emulator_flag or any(
        word in value
        for value in (fingerprint, hardware, model, manufacturer, brand, product)
        for word in emulator_words
    )
    if emulator_detected:
        score = max(score, 0.92)
        confidence = max(confidence, 0.90)
        status = "FAIL"
        codes.append("EMULATOR_OR_VIRTUAL_DEVICE")
        reasons.append("Device build metadata is consistent with an emulator or virtual Android device.")

    test_keys = bool(device.get("testKeys", False)) or "test-keys" in tags
    if test_keys:
        score = max(score, 0.55)
        confidence = max(confidence, 0.70)
        if status != "FAIL":
            status = "PARTIAL"
        codes.append("TEST_KEYS_BUILD")
        reasons.append("Android build tags contain test keys; this is a warning, not proof of compromise.")

    if bool(device.get("rootHeuristic", False)):
        score = max(score, 0.72)
        confidence = max(confidence, 0.72)
        status = "PARTIAL" if status != "FAIL" else status
        codes.append("ROOT_HEURISTIC")
        reasons.append("Local device heuristics found root-associated filesystem/build indicators.")

    if bool(device.get("debuggerConnected", False)):
        score = max(score, 0.35)
        confidence = max(confidence, 0.65)
        if status == "INCONCLUSIVE":
            status = "PARTIAL"
        codes.append("DEBUGGER_CONNECTED")
        reasons.append("A debugger was connected during capture.")

    if attestation is not None:
        confidence = max(confidence, 0.95)
        app_status = attestation.app_integrity_status
        device_status = attestation.device_integrity_status
        if app_status == "PASS" and device_status == "PASS":
            score = min(score, 0.15)
            status = "PASS"
            reasons.append("Provider-backed device and application integrity checks passed.")
        elif app_status == "FAIL" or device_status == "FAIL":
            score = max(score, 0.98)
            status = "FAIL"
            codes.append("PROVIDER_DEVICE_INTEGRITY_FAILED")
            reasons.append("Provider-backed device or application integrity checks failed.")
        else:
            score = max(score, 0.40)
            if status != "FAIL":
                status = "PARTIAL"
            codes.append("PROVIDER_DEVICE_INTEGRITY_PARTIAL")
            reasons.append("Provider-backed integrity data was present but not a full pass.")
    elif len(device) >= 7:
        confidence = max(confidence, 0.62)
        if status == "INCONCLUSIVE":
            status = "PASS"
            reasons.append("No emulator/root/debugger warning was found in captured device metadata.")
        codes.append("ATTESTATION_UNAVAILABLE")
        reasons.append("Cryptographic platform attestation was not available in this development deployment.")
    else:
        codes.append("DEVICE_METADATA_LEGACY")
        reasons.append("This capture predates the extended Phase 9 device metadata fields.")
        codes.append("ATTESTATION_UNAVAILABLE")
        reasons.append("Cryptographic platform attestation was not available in this development deployment.")

    if not reasons:
        reasons.append("No strong local device-integrity warning was detected.")

    return {
        "status": status,
        "risk_score": min(1.0, score),
        "confidence": min(1.0, confidence),
        "reason_codes": sorted(set(codes)),
        "reasons": reasons,
        "metrics": {
            "metadataFieldCount": len(device),
            "emulatorHeuristic": emulator_detected,
            "testKeys": test_keys,
            "attestationAvailable": attestation is not None,
            "algorithmVersion": ALGORITHM_VERSION,
        },
    }
