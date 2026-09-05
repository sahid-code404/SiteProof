package com.siteproof.app.verification.model

import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = false)
data class SemanticChallengeIssue(
    val challengeId: String,
    val sequenceNumber: Int,
    val attemptNumber: Int,
    val totalChallenges: Int,
    val type: String,
    val instruction: String,
    val target: Map<String, Any?> = emptyMap(),
    val issuedAt: String,
    val expiresAt: String,
    val serverTime: String,
    val nonce: String,
)

@JsonClass(generateAdapter = false)
data class SemanticChallengeStartRequest(
    val nonce: String,
    val clientMonotonicNs: Long,
)

@JsonClass(generateAdapter = false)
data class SemanticChallengeCompleteRequest(
    val nonce: String,
    val clientMonotonicNs: Long,
)

@JsonClass(generateAdapter = false)
data class SemanticChallengeCompleteResult(
    val challengeId: String,
    val sequenceNumber: Int,
    val attemptNumber: Int,
    val type: String,
    val status: String,
    val windowStartMs: Long,
    val windowEndMs: Long,
    val sequenceComplete: Boolean,
    val serverTime: String,
)

@JsonClass(generateAdapter = false)
data class SemanticChallengeTimelineItem(
    val id: String,
    val sequenceNumber: Int,
    val attemptNumber: Int,
    val type: String,
    val instruction: String,
    val target: Map<String, Any?> = emptyMap(),
    val status: String,
    val issuedAt: String,
    val startedAt: String? = null,
    val completedAt: String? = null,
    val expiresAt: String,
    val windowStartMs: Long? = null,
    val windowEndMs: Long? = null,
)

@JsonClass(generateAdapter = false)
data class SemanticChallengeListResponse(
    val sessionId: String,
    val totalRequired: Int,
    val sequenceComplete: Boolean,
    val items: List<SemanticChallengeTimelineItem>,
)
