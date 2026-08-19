package com.siteproof.app.data

class InspectionRepository(
    private val api: SiteProofApi,
    private val tokenStore: SessionStore,
    private val cache: InspectionStore,
) {
    fun hasSession(): Boolean = !tokenStore.accessToken.isNullOrBlank()

    fun inspectorName(): String = tokenStore.inspectorName ?: "Inspector"

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

    suspend fun loadInspections(): LoadedInspections {
        return try {
            val items = api.inspections().items
            cache.save(items)
            LoadedInspections(items, offline = false)
        } catch (error: Exception) {
            val cached = cache.load()
            if (cached.isEmpty()) throw error
            LoadedInspections(cached, offline = true)
        }
    }

    suspend fun loadInspection(id: String): Pair<InspectionDetail, Boolean> {
        return try {
            api.inspection(id) to false
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

    suspend fun loadInspectorVerification(inspectionId: String): InspectorVerificationResponse? {
        val session = api.latestVerificationSession(inspectionId) ?: return null
        return runCatching { api.inspectorVerification(session.id) }.getOrNull()
    }

    suspend fun acknowledge(id: String): InspectionSummary {
        val updated = api.acknowledge(id)
        cache.update(updated)
        return updated
    }

    suspend fun markReady(id: String): InspectionSummary {
        val updated = api.markReady(id)
        cache.update(updated)
        return updated
    }
}
