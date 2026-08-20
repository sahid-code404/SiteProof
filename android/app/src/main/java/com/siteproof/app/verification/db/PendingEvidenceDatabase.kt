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
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase
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

@Entity(tableName = "active_challenges")
data class ActiveChallengeEntity(
    @PrimaryKey val challengeId: String,
    val sessionId: String,
    val type: String,
    val issuedAt: String,
    val expiresAt: String,
    val nonce: String,
    val localStartMonotonicNs: Long? = null,
    val state: String,
    val submissionStatus: String,
    val idempotencyKey: String,
    val evidencePath: String? = null,
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

@Dao
interface ActiveChallengeDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(item: ActiveChallengeEntity)

    @Query("SELECT * FROM active_challenges WHERE sessionId = :sessionId LIMIT 1")
    suspend fun forSession(sessionId: String): ActiveChallengeEntity?

    @Query(
        "UPDATE active_challenges SET localStartMonotonicNs = :startNs, state = :state, submissionStatus = :submissionStatus WHERE challengeId = :challengeId",
    )
    suspend fun markStarted(
        challengeId: String,
        startNs: Long,
        state: String = "STARTED",
        submissionStatus: String = "PENDING",
    )

    @Query(
        "UPDATE active_challenges SET state = :state, submissionStatus = :submissionStatus, evidencePath = :evidencePath WHERE challengeId = :challengeId",
    )
    suspend fun updateSubmission(
        challengeId: String,
        state: String,
        submissionStatus: String,
        evidencePath: String?,
    )

    @Query("DELETE FROM active_challenges WHERE sessionId = :sessionId")
    suspend fun clearSession(sessionId: String)
}

@Database(
    entities = [PendingEvidenceEntity::class, ActiveChallengeEntity::class],
    version = 2,
    exportSchema = false,
)
abstract class PendingEvidenceDatabase : RoomDatabase() {
    abstract fun pendingEvidenceDao(): PendingEvidenceDao
    abstract fun activeChallengeDao(): ActiveChallengeDao

    companion object {
        @Volatile private var instance: PendingEvidenceDatabase? = null

        private val migration1To2 = object : Migration(1, 2) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    """
                    CREATE TABLE IF NOT EXISTS active_challenges (
                        challengeId TEXT NOT NULL PRIMARY KEY,
                        sessionId TEXT NOT NULL,
                        type TEXT NOT NULL,
                        issuedAt TEXT NOT NULL,
                        expiresAt TEXT NOT NULL,
                        nonce TEXT NOT NULL,
                        localStartMonotonicNs INTEGER,
                        state TEXT NOT NULL,
                        submissionStatus TEXT NOT NULL,
                        idempotencyKey TEXT NOT NULL,
                        evidencePath TEXT
                    )
                    """.trimIndent(),
                )
            }
        }

        fun get(context: Context): PendingEvidenceDatabase = instance ?: synchronized(this) {
            instance ?: Room.databaseBuilder(
                context.applicationContext,
                PendingEvidenceDatabase::class.java,
                "siteproof-verification.db",
            )
                .addMigrations(migration1To2)
                .build()
                .also { instance = it }
        }
    }
}
