package com.siteproof.app.data

import java.security.MessageDigest
import retrofit2.HttpException

class SessionExpiredException : IllegalStateException("Session expired — sign in again.")

class InspectionRepository(
    private val api: SiteProofApi,
    private val tokenStore: SessionStore,
    private val cache: InspectionStore,
) {
    fun hasSession(): Boolean = !tokenStore.accessToken.isNullOrBlank()

    fun inspectorName(): String = tokenStore.inspectorName ?: "Inspector"

    fun sessionScopeKey(): String {
        val token = tokenStore.accessToken ?: return "signed-out"
        return MessageDigest.getInstance("SHA-256")
            .digest(token.toByteArray(Charsets.UTF_8))
            .take(12)
            .joinToString("") { byte -> "%02x".format(byte.toInt() and 0xff) }
    }

    suspend fun login(email: String, password: String): AuthUser {
        val response = api.login(LoginRequest(email.trim(), password))
        require(response.user.role == "INSPECTOR") { "This Android app is for inspector accounts." }
        cache.clear()
        tokenStore.accessToken = response.accessToken
        tokenStore.inspectorName = response.user.fullName
        return response.user
    }

    fun signOut() {
        tokenStore.clear()
        cache.clear()
    }

    private suspend fun <T> authenticatedCall(block: suspend () -> T): T {
        return try {
            block()
        } catch (error: HttpException) {
            if (error.code() == 401) throw SessionExpiredException()
            throw error
        }
    }

    suspend fun loadInspections(): LoadedInspections {
        return try {
            val items = authenticatedCall { api.inspections() }.items
            cache.save(items)
            LoadedInspections(items, offline = false)
        } catch (error: SessionExpiredException) {
            throw error
        } catch (error: HttpException) {
            // Authentication/server HTTP failures are not offline mode. Showing cached data
            // as "offline" for a 401 hid the real problem during field testing.
            throw error
        } catch (error: Exception) {
            val cached = cache.load()
            if (cached.isEmpty()) throw error
            LoadedInspections(cached, offline = true)
        }
    }

    suspend fun loadInspection(id: String): Pair<InspectionDetail, Boolean> {
        return try {
            authenticatedCall { api.inspection(id) } to false
        } catch (error: SessionExpiredException) {
            throw error
        } catch (error: HttpException) {
            throw error
        } catch (error: Exception) {
            val cached = cache.load().firstOrNull { it.id == id } ?: throw error
            InspectionDetail(
                id = cached.id,
                title = cached.title,
                description = cached.description,
                inspectionType = cached.inspectionType,
                status = cached.status,
                expectedLatitude = cached.expectedLatitude,
                expectedLongitude = cached.expectedLongitude,
                allowedRadiusMeters = cached.allowedRadiusMeters,
                captureDurationSeconds = cached.captureDurationSeconds,
                locationName = cached.locationName,
                locationAddress = cached.locationAddress,
                deadline = cached.deadline,
                priority = cached.priority,
                instructions = cached.instructions,
                createdAt = cached.createdAt,
                updatedAt = cached.updatedAt,
                cancelledAt = cached.cancelledAt,
                isOverdue = cached.isOverdue,
                activeAssignment = cached.activeAssignment,
            ) to true
        }
    }

    suspend fun acknowledge(id: String): InspectionSummary {
        val updated = authenticatedCall { api.acknowledge(id) }
        cache.update(updated)
        return updated
    }

    suspend fun markReady(id: String): InspectionSummary {
        val updated = authenticatedCall { api.markReady(id) }
        cache.update(updated)
        return updated
    }
}
