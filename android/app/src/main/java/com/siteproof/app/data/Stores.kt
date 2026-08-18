package com.siteproof.app.data

interface SessionStore {
    var accessToken: String?
    var inspectorName: String?
    fun clear()
}

interface InspectionStore {
    fun save(items: List<InspectionSummary>)
    fun load(): List<InspectionSummary>
    fun update(updated: InspectionSummary)
    fun lastSyncedMillis(): Long
    fun clear()
}
