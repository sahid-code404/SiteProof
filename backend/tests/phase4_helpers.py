import math
import uuid

CAPTURE_ANCHOR_NS = 600_000_000


def _motion_spec(challenge_type: str) -> tuple[int, float]:
    if challenge_type == "ROTATE_RIGHT":
        return 1, -1.0
    if challenge_type == "ROTATE_LEFT":
        return 1, 1.0
    if challenge_type == "TILT_DOWN":
        return 0, 1.0
    if challenge_type == "TILT_UP":
        return 0, -1.0
    raise AssertionError(f"Unsupported challenge type {challenge_type}")


def synthetic_sensor_body(
    challenge: dict,
    *,
    start_relative_ns: int = 500_000_000,
    wrong_direction: bool = False,
    magnitude_factor: float = 1.0,
    rotation_vector_conflict: bool = False,
    reverse_timestamps: bool = False,
) -> dict:
    axis, raw_sign = _motion_spec(challenge["type"])
    if wrong_direction:
        raw_sign *= -1.0
    target = float(challenge["parameters"]["targetDegrees"]) * magnitude_factor
    movement_start_ns = 600_000_000
    movement_end_ns = 1_600_000_000
    total_ns = 2_000_000_000
    step_ns = 20_000_000
    angular_rate = raw_sign * math.radians(target)
    samples = []

    for offset in range(0, total_ns + 1, step_ns):
        timestamp = start_relative_ns + offset
        moving = movement_start_ns <= offset <= movement_end_ns
        gyro_values = [0.0, 0.0, 0.0]
        if moving:
            gyro_values[axis] = angular_rate
        samples.append(
            {
                "type": "GYROSCOPE",
                "relativeTimestampNs": timestamp,
                "values": gyro_values,
                "accuracy": 3,
            }
        )

        if offset <= movement_start_ns:
            progress = 0.0
        elif offset >= movement_end_ns:
            progress = 1.0
        else:
            progress = (offset - movement_start_ns) / (movement_end_ns - movement_start_ns)
        rv_sign = -raw_sign if rotation_vector_conflict else raw_sign
        angle = math.radians(target * progress) * rv_sign
        vector = [0.0, 0.0, 0.0, math.cos(angle / 2.0)]
        vector[axis] = math.sin(angle / 2.0)
        samples.append(
            {
                "type": "ROTATION_VECTOR",
                "relativeTimestampNs": timestamp,
                "values": vector,
                "accuracy": 3,
            }
        )
        samples.append(
            {
                "type": "ACCELEROMETER",
                "relativeTimestampNs": timestamp,
                "values": [0.0, 9.81, 0.0],
                "accuracy": 3,
            }
        )

    samples.sort(key=lambda sample: sample["relativeTimestampNs"])
    if reverse_timestamps:
        samples = list(reversed(samples))
    return {
        "nonce": challenge["nonce"],
        "idempotencyKey": f"challenge-{challenge['challengeId']}-{uuid.uuid4()}",
        "sensorWindow": {
            "startRelativeNs": start_relative_ns,
            "endRelativeNs": start_relative_ns + total_ns,
        },
        "samples": samples,
        "sensorSummary": {
            "gyroSamples": 101,
            "rotationVectorSamples": 101,
            "accelerometerSamples": 101,
        },
    }


def perform_current_challenge(
    client,
    headers,
    session_id: str,
    *,
    start_relative_ns: int,
    wrong_direction: bool = False,
    magnitude_factor: float = 1.0,
    rotation_vector_conflict: bool = False,
):
    issued = client.post(f"/api/v1/sessions/{session_id}/challenges/next", headers=headers)
    assert issued.status_code == 200, issued.text
    challenge = issued.json()
    started = client.post(
        f"/api/v1/challenges/{challenge['challengeId']}/start",
        headers=headers,
        json={
            "nonce": challenge["nonce"],
            "clientMonotonicNs": CAPTURE_ANCHOR_NS + start_relative_ns,
        },
    )
    assert started.status_code == 200, started.text
    body = synthetic_sensor_body(
        challenge,
        start_relative_ns=start_relative_ns,
        wrong_direction=wrong_direction,
        magnitude_factor=magnitude_factor,
        rotation_vector_conflict=rotation_vector_conflict,
    )
    submitted = client.post(
        f"/api/v1/challenges/{challenge['challengeId']}/submit",
        headers=headers,
        json=body,
    )
    return challenge, body, submitted


def complete_required_challenges(client, headers, session_id: str) -> None:
    current = client.get(f"/api/v1/sessions/{session_id}", headers=headers)
    if current.status_code != 200:
        return
    if current.json()["status"] not in {"CAPTURING", "CHALLENGES_IN_PROGRESS"}:
        return

    for index in range(6):
        start_relative_ns = 500_000_000 + (index * 2_500_000_000)
        _, _, submitted = perform_current_challenge(
            client,
            headers,
            session_id,
            start_relative_ns=start_relative_ns,
        )
        assert submitted.status_code == 200, submitted.text
        result = submitted.json()
        if result["sequenceComplete"]:
            return
    raise AssertionError("Challenge sequence did not complete within expected attempts")
