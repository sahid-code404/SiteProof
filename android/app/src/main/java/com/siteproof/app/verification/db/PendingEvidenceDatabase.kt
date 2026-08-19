package com.siteproof.app.verification.db

import android.content.Context
import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.Room
import androidx.room.RoomDatabase
import kotlinx.coroutines.flow.Flow

@Entity(tableName = "pending_evidence")
data class PendingEvidenceEntity(
    @PrimaryKey val sessionId: String,
    val inspectionId: String,
    val captureStatus: String,
    val uploadStatus: String,
    val localEvidencePath: String,
    val manifestSha256: String,
    val uploadIdempotencyKey: String,
    val createdAtEpochMs: Long,
    val lastUploadAttemptEpochMs: Long? = null,
)

@Dao
interface PendingEvidenceDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(item: PendingEvidenceEntity)

    @Query("SELECT * FROM pending_evidence WHERE sessionId = :sessionId LIMIT 1")
    suspend fun get(sessionId: String): PendingEvidenceEntity?

    @Query("SELECT * FROM pending_evidence WHERE sessionId = :sessionId LIMIT 1")
    fun observe(sessionId: String): Flow<PendingEvidenceEntity?>

    @Query(
        "UPDATE pending_evidence SET uploadStatus = :status, lastUploadAttemptEpochMs = :attempt WHERE sessionId = :sessionId",
    )
    suspend fun updateUploadStatus(sessionId: String, status: String, attempt: Long?)

    @Query(
        "UPDATE pending_evidence SET uploadStatus = 'UPLOADED', localEvidencePath = '' WHERE sessionId = :sessionId",
    )
    suspend fun markUploaded(sessionId: String)
}

@Database(entities = [PendingEvidenceEntity::class], version = 1, exportSchema = false)
abstract class PendingEvidenceDatabase : RoomDatabase() {
    abstract fun pendingEvidenceDao(): PendingEvidenceDao

    companion object {
        @Volatile private var instance: PendingEvidenceDatabase? = null

        fun get(context: Context): PendingEvidenceDatabase = instance ?: synchronized(this) {
            instance ?: Room.databaseBuilder(
                context.applicationContext,
                PendingEvidenceDatabase::class.java,
                "siteproof-verification.db",
            ).build().also { instance = it }
        }
    }
}
