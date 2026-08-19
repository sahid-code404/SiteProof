package com.siteproof.app.verification

import android.os.Build
import android.os.SystemClock
import com.siteproof.app.BuildConfig
import com.siteproof.app.data.InspectionDetail
import com.siteproof.app.data.SiteProofApi
import com.siteproof.app.verification.db.ActiveChallengeDao
import com.siteproof.app.verification.db.ActiveChallengeEntity
import com.siteproof.app.verification.db.PendingEvidenceDao
import com.siteproof.app.verification.db.PendingEvidenceEntity
import com.siteproof.app.verification.model.AbortRequest
import com.siteproof.app.verification.model.CaptureCompleteRequest
import com.siteproof.app.verification.model.CaptureLocation
import com.siteproof.app.verification.model.ChallengeIssue
import com.siteproof.app.verification.model.ChallengeListResponse
import com.siteproof.app.verification.model.ChallengeStartRequest
import com.siteproof.app.verification.model.ChallengeSubmitRequest
import com.siteproof.app.verification.model.ChallengeValidationResult
import com.siteproof.app.verification.model.DeviceCapabilities
import com.siteproof.app.verification.model.EvidencePackage
import com.siteproof.app.verification.model.SessionCreateRequest
import com.siteproof.app.verification.model.SessionCreateResponse
import com.siteproof.app.verification.model.StartCaptureRequest
import com.siteproof.app.verification.model.VerificationSession
import java.time.Instant
import java.util.UUID

class VerificationRepository(
    private val api: SiteProofApi,
    private val pendingDao: PendingEvidenceDao,
    private val challengeDao: ActiveChallengeDao,
) {
    suspend fun inspection(id: String): InspectionDetail = api.inspection(id)

    suspend fun createSession(inspectionId: String, deviceSessionId: String): SessionCreateResponse =
        api.createVerificationSession(
            inspectionId,
            SessionCreateRequest(
                deviceSessionId = deviceSessionId,
                clientTime = Instant.now().toString(),
                clientMonotonicNs = SystemClock.elapsedRealtimeNanos(),
                clientVersion = BuildConfig.VERSION_NAME,
                androidVersion = Build.VERSION.RELEASE,
                deviceModel = "${Build.MANUFACTURER} ${Build.MODEL}".trim(),
            ),
        )

    suspend fun startCapture(
        sessionId: String,
        captureStartNs: Long,
        location: CaptureLocation,
        capabilities: DeviceCapabilities,
    ): VerificationSession = api.startCapture(
        sessionId,
        StartCaptureRequest(
            clientWallClock = Instant.now().toString(),
            clientMonotonicNs = captureStartNs,
            location = location,
            capabilities = capabilities,
        ),
    )

    suspend fun issueChallenge(sessionId: String): ChallengeIssue {
        val issue = api.nextChallenge(sessionId)
        challengeDao.upsert(
            ActiveChallengeEntity(
                challengeId = issue.challengeId,
                sessionId = sessionId,
                type = issue.type,
                issuedAt = issue.issuedAt,
                expiresAt = issue.expiresAt,
                nonce = issue.nonce,
                state = "ISSUED",
                submissionStatus = "PENDING",
                idempotencyKey = "${issue.challengeId}-${UUID.randomUUID()}",
            ),
        )
        return issue
    }

    suspend fun startChallenge(issue: ChallengeIssue, clientStartNs: Long): ChallengeIssue {
        val started = api.startChallenge(
            issue.challengeId,
            ChallengeStartRequest(issue.nonce, clientStartNs),
        )
        challengeDao.markStarted(issue.challengeId, clientStartNs)
        return started
    }

    suspend fun preserveChallengeEvidence(challengeId: String, evidencePath: String) {
        challengeDao.updateSubmission(
            challengeId = challengeId,
            state = "STARTED",
            submissionStatus = "SAVED_FOR_RETRY",
            evidencePath = evidencePath,
        )
    }

    suspend fun submitChallenge(issue: ChallengeIssue, request: ChallengeSubmitRequest): ChallengeValidationResult {
        challengeDao.updateSubmission(issue.challengeId, "STARTED", "SUBMITTING", null)
        return try {
            api.submitChallenge(issue.challengeId, request).also {
                challengeDao.updateSubmission(issue.challengeId, it.result, "SUBMITTED", null)
            }
        } catch (error: Exception) {
            throw error
        }
    }

    suspend fun challengeIdempotencyKey(sessionId: String): String =
        challengeDao.forSession(sessionId)?.idempotencyKey ?: UUID.randomUUID().toString()

    suspend fun challengeTimeline(sessionId: String): ChallengeListResponse = api.challenges(sessionId)

    suspend fun clearChallengeState(sessionId: String) = challengeDao.clearSession(sessionId)

    suspend fun captureComplete(sessionId: String, request: CaptureCompleteRequest): VerificationSession =
        api.captureComplete(sessionId, request)

    suspend fun abort(sessionId: String, reason: String) {
        runCatching { api.abortSession(sessionId, AbortRequest(reason)) }
        challengeDao.clearSession(sessionId)
    }

    suspend fun savePending(inspectionId: String, sessionId: String, evidence: EvidencePackage) {
        pendingDao.upsert(
            PendingEvidenceEntity(
                sessionId = sessionId,
                inspectionId = inspectionId,
                captureStatus = "CAPTURED_PENDING_UPLOAD",
                uploadStatus = "PENDING",
                localEvidencePath = evidence.directoryPath,
                manifestSha256 = evidence.manifestSha256,
                uploadIdempotencyKey = "${sessionId}-${UUID.randomUUID()}",
                createdAtEpochMs = System.currentTimeMillis(),
            ),
        )
    }

    fun observePending(sessionId: String) = pendingDao.observe(sessionId)
}
