package com.siteproof.app

import com.siteproof.app.verification.model.SessionCreateResponse
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import org.junit.Assert.assertEquals
import org.junit.Test

class SessionCreateResponseJsonTest {
    private val adapter = Moshi.Builder()
        .add(KotlinJsonAdapterFactory())
        .build()
        .adapter(SessionCreateResponse::class.java)

    @Test
    fun `semantic challenge count decodes from server camel case field`() {
        val response = adapter.fromJson(
            """
            {
              "sessionId": "session-1",
              "inspectionId": "inspection-1",
              "status": "CREATED",
              "expiresAt": "2026-09-05T12:00:00Z",
              "serverTime": "2026-09-05T11:45:00Z",
              "requiredCaptureDurationSeconds": 30,
              "captureMaximumSeconds": 45,
              "allowedRadiusMeters": 500,
              "deadline": "2026-09-06T12:00:00Z",
              "semanticChallengeCount": 2
            }
            """.trimIndent(),
        )

        requireNotNull(response)
        assertEquals(2, response.semanticChallengeCount)
    }

    @Test
    fun `missing semantic challenge count remains backward compatible`() {
        val response = adapter.fromJson(
            """
            {
              "sessionId": "session-1",
              "inspectionId": "inspection-1",
              "status": "CREATED",
              "expiresAt": "2026-09-05T12:00:00Z",
              "serverTime": "2026-09-05T11:45:00Z",
              "requiredCaptureDurationSeconds": 30,
              "captureMaximumSeconds": 45,
              "allowedRadiusMeters": 500,
              "deadline": "2026-09-06T12:00:00Z"
            }
            """.trimIndent(),
        )

        requireNotNull(response)
        assertEquals(0, response.semanticChallengeCount)
    }
}
