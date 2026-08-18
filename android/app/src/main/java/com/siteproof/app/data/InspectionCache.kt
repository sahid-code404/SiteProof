package com.siteproof.app.data

import android.content.Context
import com.squareup.moshi.Moshi
import com.squareup.moshi.Types
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory

class InspectionCache(context: Context) : InspectionStore {
    private val preferences = context.getSharedPreferences("siteproof_inspection_cache", Context.MODE_PRIVATE)
    private val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()
    private val type = Types.newParameterizedType(List::class.java, InspectionSummary::class.java)
    private val adapter = moshi.adapter<List<InspectionSummary>>(type)

    override fun save(items: List<InspectionSummary>) {
        preferences.edit()
            .putString("items", adapter.toJson(items))
            .putLong("last_synced", System.currentTimeMillis())
            .apply()
    }

    override fun load(): List<InspectionSummary> {
        val json = preferences.getString("items", null) ?: return emptyList()
        return runCatching { adapter.fromJson(json).orEmpty() }.getOrDefault(emptyList())
    }

    override fun update(updated: InspectionSummary) {
        val current = load()
        val items = if (current.any { it.id == updated.id }) {
            current.map { if (it.id == updated.id) updated else it }
        } else {
            current + updated
        }
        save(items)
    }

    override fun lastSyncedMillis(): Long = preferences.getLong("last_synced", 0L)

    override fun clear() {
        preferences.edit().clear().apply()
    }
}
