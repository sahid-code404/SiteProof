package com.siteproof.app

import com.siteproof.app.data.Assignment
import com.siteproof.app.data.AuthUser
import com.siteproof.app.data.InspectionDetail
import com.siteproof.app.data.InspectionPage
import com.siteproof.app.data.InspectionRepository
import com.siteproof.app.data.InspectionStore
import com.siteproof.app.data.InspectionSummary
import com.siteproof.app.data.Inspector
import com.siteproof.app.data.LoginRequest
import com.siteproof.app.data.LoginResponse
import com.siteproof.app.data.SessionStore
import com.siteproof.app.data.SiteProofApi
import com.siteproof.app.verification.model.AbortRequest
import com.siteproof.app.verification.model.CaptureCompleteRequest
import com.siteproof.app.verification.model.EvidenceCompleteRequest
import com.siteproof.app.verification.model.EvidenceFileResponse
import com.siteproof.app.verification.model.EvidenceInitiateRequest
import com.siteproof.app.verification.model.EvidenceInitiateResponse
import com.siteproof.app.verification.model.EvidenceListResponse
import com.siteproof.app.verification.model.SessionCreateRequest
import com.siteproof.app.verification.model.SessionCreateResponse
import com.siteproof.app.verification.model.StartCaptureRequest
import com.siteproof.app.verification.model.VerificationSession
import kotlinx.coroutines.test.runTest
import okhttp3.RequestBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

private val inspector = Inspector(
    id = "inspector-1",
    userId = "user-1",
    name = "Inspector One",
    email = "inspector@siteproof.example.com",
)

private fun inspection(status: String = "ASSIGNED") = InspectionSummary(
    id = "inspection-1",
    title = "Verify repaired pothole",
    inspectionType = "ROAD_REPAIR",
    status = status,
    expectedLatitude = 22.5726,
    expectedLongitude = 88.3639,
    allowedRadiusMeters = 100,
    locationName = "Central Avenue",
    deadline = "2026-08-25T12:30:00Z",
    priority = "HIGH",
    createdAt = "2026-08-19T00:00:00Z",
    updatedAt = "2026-08-19T00:00:00Z",
    activeAssignment = Assignment(
        id = "assignment-1",
        inspector = inspector,
        status = "ACTIVE",
        assignedAt = "2026-08-19T00:00:00Z",
    ),
)

private fun detail(item: InspectionSummary) = InspectionDetail(
    id = item.id,
    title = item.title,
    description = item.description,
    inspectionType = item.inspectionType,
    status = item.status,
    expectedLatitude = item.expectedLatitude,
    expectedLongitude = item.expectedLongitude,
    allowedRadiusMeters = item.allowedRadiusMeters,
    locationName = item.locationName,
    locationAddress = item.locationAddress,
    deadline = item.deadline,
    priority = item.priority,
    instructions = item.instructions,
    createdAt = item.createdAt,
    updatedAt = item.updatedAt,
    cancelledAt = item.cancelledAt,
    isOverdue = item.isOverdue,
    activeAssignment = item.activeAssignment,
)

private class FakeSessionStore : SessionStore {
    override var accessToken: String? = null
    override var inspectorName: String? = null
    override fun clear() {
        accessToken = null
        inspectorName = null
    }
}

private class FakeInspectionStore(initial: List<InspectionSummary> = emptyList()) : InspectionStore {
    var items = initial
    override fun save(items: List<InspectionSummary>) { this.items = items }
    override fun load(): List<InspectionSummary> = items
    override fun update(updated: InspectionSummary) {
        items = items.map { if (it.id == updated.id) updated else it }
    }
    override fun lastSyncedMillis(): Long = 0
    override fun clear() { items = emptyList() }
}

private class FakeApi(
    var items: List<InspectionSummary> = listOf(inspection()),
    var failList: Boolean = false,
    var failDetail: Boolean = false,
) : SiteProofApi {
    override suspend fun login(request: LoginRequest): LoginResponse = LoginResponse(
        accessToken = "token-${request.email}",
        tokenType = "bearer",
        user = AuthUser("user-${request.email}", "org-1", request.email, "Inspector", "INSPECTOR"),
    )

    override suspend fun inspections(page: Int, pageSize: Int): InspectionPage {
        if (failList) error("network unavailable")
        return InspectionPage(items, 1, 100, items.size, if (items.isEmpty()) 0 else 1)
    }

    override suspend fun inspection(id: String): InspectionDetail {
        if (failDetail) error("network unavailable")
        return detail(items.first { it.id == id })
    }

    override suspend fun acknowledge(id: String): InspectionSummary {
        val updated = items.first { it.id == id }.copy(status = "ACKNOWLEDGED")
        items = listOf(updated)
        return updated
    }

    override suspend fun markReady(id: String): InspectionSummary {
        val updated = items.first { it.id == id }.copy(status = "READY")
        items = listOf(updated)
        return updated
    }

    // Phase 2 repository tests never call live-verification APIs. Explicit stubs keep this
    // test double honest as SiteProofApi grows without hiding unexpected calls.
    override suspend fun createVerificationSession(
        inspectionId: String,
        request: SessionCreateRequest,
    ): SessionCreateResponse = error("unused in Phase 2 repository tests")

    override suspend fun latestVerificationSession(inspectionId: String): VerificationSession? =
        error("unused in Phase 2 repository tests")

    override suspend fun verificationSession(sessionId: String): VerificationSession =
        error("unused in Phase 2 repository tests")

    override suspend fun startCapture(
        sessionId: String,
        request: StartCaptureRequest,
    ): VerificationSession = error("unused in Phase 2 repository tests")

    override suspend fun captureComplete(
        sessionId: String,
        request: CaptureCompleteRequest,
    ): VerificationSession = error("unused in Phase 2 repository tests")

    override suspend fun abortSession(
        sessionId: String,
        request: AbortRequest,
    ): VerificationSession = error("unused in Phase 2 repository tests")

    override suspend fun initiateEvidence(
        sessionId: String,
        request: EvidenceInitiateRequest,
    ): EvidenceInitiateResponse = error("unused in Phase 2 repository tests")

    override suspend fun uploadEvidence(
        relativeUrl: String,
        body: RequestBody,
    ): EvidenceFileResponse = error("unused in Phase 2 repository tests")

    override suspend fun completeEvidence(
        sessionId: String,
        request: EvidenceCompleteRequest,
    ): VerificationSession = error("unused in Phase 2 repository tests")

    override suspend fun evidence(sessionId: String): EvidenceListResponse =
        error("unused in Phase 2 repository tests")
}

class InspectionRepositoryTest {
    @Test
    fun `successful fetch stores server assignments`() = runTest {
        val api = FakeApi()
        val cache = FakeInspectionStore()
        val repository = InspectionRepository(api, FakeSessionStore(), cache)

        val result = repository.loadInspections()

        assertFalse(result.offline)
        assertEquals("Verify repaired pothole", result.items.single().title)
        assertEquals(result.items, cache.items)
    }

    @Test
    fun `network failure returns cached assignments`() = runTest {
        val cached = inspection()
        val repository = InspectionRepository(
            FakeApi(failList = true),
            FakeSessionStore(),
            FakeInspectionStore(listOf(cached)),
        )

        val result = repository.loadInspections()

        assertTrue(result.offline)
        assertEquals(cached.id, result.items.single().id)
    }

    @Test(expected = IllegalStateException::class)
    fun `network failure without cache remains an error`() = runTest {
        val repository = InspectionRepository(
            FakeApi(items = emptyList(), failList = true),
            FakeSessionStore(),
            FakeInspectionStore(),
        )
        repository.loadInspections()
    }

    @Test
    fun `login clears previous inspector cache and changes session scope`() = runTest {
        val cache = FakeInspectionStore(listOf(inspection()))
        val repository = InspectionRepository(FakeApi(), FakeSessionStore(), cache)

        repository.login("inspector1@siteproof.example.com", "password1234")
        val firstScope = repository.sessionScopeKey()
        assertTrue(cache.items.isEmpty())

        cache.save(listOf(inspection()))
        repository.login("inspector2@siteproof.example.com", "password1234")
        val secondScope = repository.sessionScopeKey()

        assertTrue(cache.items.isEmpty())
        assertNotEquals(firstScope, secondScope)
    }

    @Test
    fun `sign out clears session and cache`() = runTest {
        val cache = FakeInspectionStore(listOf(inspection()))
        val session = FakeSessionStore().apply {
            accessToken = "token-inspector1"
            inspectorName = "Inspector One"
        }
        val repository = InspectionRepository(FakeApi(), session, cache)

        repository.signOut()

        assertEquals("signed-out", repository.sessionScopeKey())
        assertTrue(cache.items.isEmpty())
        assertFalse(repository.hasSession())
    }

    @Test
    fun `acknowledge updates cached inspection`() = runTest {
        val cache = FakeInspectionStore(listOf(inspection()))
        val repository = InspectionRepository(FakeApi(), FakeSessionStore(), cache)

        repository.acknowledge("inspection-1")

        assertEquals("ACKNOWLEDGED", cache.items.single().status)
    }

    @Test
    fun `mark ready updates cached inspection`() = runTest {
        val acknowledged = inspection("ACKNOWLEDGED")
        val cache = FakeInspectionStore(listOf(acknowledged))
        val repository = InspectionRepository(FakeApi(items = listOf(acknowledged)), FakeSessionStore(), cache)

        repository.markReady("inspection-1")

        assertEquals("READY", cache.items.single().status)
    }
}
