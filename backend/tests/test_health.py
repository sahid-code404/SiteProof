def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "siteproof-api"
    assert body["autonomousVerificationEnabled"] is False
    assert body["autonomousProviderConfigured"] is False
    assert body["autonomousVerificationReady"] is True
