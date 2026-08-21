package com.siteproof.app.data

data class AuthUser(
    val id: String,
    val organizationId: String,
    val email: String,
    val fullName: String,
    val role: String,
)

data class LoginRequest(val email: String, val password: String)
data class LoginResponse(val accessToken: String, val tokenType: String, val user: AuthUser)

data class Inspector(
    val id: String,
    val userId: String,
    val name: String,
    val email: String,
    val employeeCode: String? = null,
    val phone: String? = null,
    val active: Boolean = true,
)

data class Assignment(
    val id: String,
    val inspector: Inspector,
    val status: String,
    val assignedAt: String,
    val acknowledgedAt: String? = null,
    val unassignedAt: String? = null,
    val reason: String? = null,
)

data class InspectionSummary(
    val id: String,
    val title: String,
    val description: String? = null,
    val inspectionType: String,
    val status: String,
    val expectedLatitude: Double,
    val expectedLongitude: Double,
    val allowedRadiusMeters: Int,
    val captureDurationSeconds: Int = 30,
    val locationName: String? = null,
    val locationAddress: String? = null,
    val deadline: String,
    val priority: String,
    val instructions: String? = null,
    val createdAt: String,
    val updatedAt: String,
    val cancelledAt: String? = null,
    val isOverdue: Boolean = false,
    val activeAssignment: Assignment? = null,
)

data class InspectionDetail(
    val id: String,
    val title: String,
    val description: String? = null,
    val inspectionType: String,
    val status: String,
    val expectedLatitude: Double,
    val expectedLongitude: Double,
    val allowedRadiusMeters: Int,
    val captureDurationSeconds: Int = 30,
    val locationName: String? = null,
    val locationAddress: String? = null,
    val deadline: String,
    val priority: String,
    val instructions: String? = null,
    val createdAt: String,
    val updatedAt: String,
    val cancelledAt: String? = null,
    val isOverdue: Boolean = false,
    val activeAssignment: Assignment? = null,
    val assignmentHistory: List<Assignment> = emptyList(),
    val createdByName: String = "",
)

data class InspectionPage(
    val items: List<InspectionSummary>,
    val page: Int,
    val pageSize: Int,
    val totalItems: Int,
    val totalPages: Int,
)

data class LoadedInspections(val items: List<InspectionSummary>, val offline: Boolean)
