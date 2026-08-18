package com.siteproof.app.data

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import com.siteproof.app.BuildConfig
import com.siteproof.app.verification.model.AbortRequest
import com.siteproof.app.verification.model.CaptureCompleteRequest
import com.siteproof.app.verification.model.EvidenceCompleteRequest
import com.siteproof.app.verification.model.EvidenceFileResponse
import com.siteproof.app.verification.model.EvidenceInitiateRequest
import com.siteproof.app.verification.model.EvidenceInitiateResponse
import com.siteproof.app.verification.model.EvidenceListResponse
import com.siteproof.app.verification.model.SessionCreateRequest
import com.siteproof.app.verification.model.SessionCreateResponse
import com.siteproof.app.verification.model.StartCaptureRequest
import com.siteproof.app.verification.model.VerificationSession
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import java.nio.ByteBuffer
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query
import retrofit2.http.Url

interface SiteProofApi {
    @POST("auth/login")
    suspend fun login(@Body request: LoginRequest): LoginResponse

    @GET("inspections")
    suspend fun inspections(
        @Query("page") page: Int = 1,
        @Query("pageSize") pageSize: Int = 100,
    ): InspectionPage

    @GET("inspections/{id}")
    suspend fun inspection(@Path("id") id: String): InspectionDetail

    @POST("inspections/{id}/acknowledge")
    suspend fun acknowledge(@Path("id") id: String): InspectionSummary

    @POST("inspections/{id}/ready")
    suspend fun markReady(@Path("id") id: String): InspectionSummary

    @POST("inspections/{id}/sessions")
    suspend fun createVerificationSession(
        @Path("id") inspectionId: String,
        @Body request: SessionCreateRequest,
    ): SessionCreateResponse

    @GET("inspections/{id}/sessions/latest")
    suspend fun latestVerificationSession(@Path("id") inspectionId: String): VerificationSession?

    @GET("sessions/{id}")
    suspend fun verificationSession(@Path("id") sessionId: String): VerificationSession

    @POST("sessions/{id}/start-capture")
    suspend fun startCapture(
        @Path("id") sessionId: String,
        @Body request: StartCaptureRequest,
    ): VerificationSession

    @POST("sessions/{id}/capture-complete")
    suspend fun captureComplete(
        @Path("id") sessionId: String,
        @Body request: CaptureCompleteRequest,
    ): VerificationSession

    @POST("sessions/{id}/abort")
    suspend fun abortSession(
        @Path("id") sessionId: String,
        @Body request: AbortRequest,
    ): VerificationSession

    @POST("sessions/{id}/evidence/initiate")
    suspend fun initiateEvidence(
        @Path("id") sessionId: String,
        @Body request: EvidenceInitiateRequest,
    ): EvidenceInitiateResponse

    @PUT
    suspend fun uploadEvidence(@Url relativeUrl: String, @Body body: RequestBody): EvidenceFileResponse

    @POST("sessions/{id}/evidence/complete")
    suspend fun completeEvidence(
        @Path("id") sessionId: String,
        @Body request: EvidenceCompleteRequest,
    ): VerificationSession

    @GET("sessions/{id}/evidence")
    suspend fun evidence(@Path("id") sessionId: String): EvidenceListResponse
}

class TokenStore(context: Context) : SessionStore {
    private val preferences = context.getSharedPreferences("siteproof_auth", Context.MODE_PRIVATE)
    private val alias = "siteproof_session_key"

    private fun secretKey(): SecretKey {
        val keyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (keyStore.getKey(alias, null) as? SecretKey)?.let { return it }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        generator.init(
            KeyGenParameterSpec.Builder(
                alias,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
            )
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .build(),
        )
        return generator.generateKey()
    }

    private fun encrypt(value: String): String {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, secretKey())
        val encrypted = cipher.doFinal(value.toByteArray(Charsets.UTF_8))
        val payload = ByteBuffer.allocate(4 + cipher.iv.size + encrypted.size)
            .putInt(cipher.iv.size)
            .put(cipher.iv)
            .put(encrypted)
            .array()
        return Base64.encodeToString(payload, Base64.NO_WRAP)
    }

    private fun decrypt(value: String): String? = runCatching {
        val payload = ByteBuffer.wrap(Base64.decode(value, Base64.NO_WRAP))
        val ivSize = payload.int
        require(ivSize in 12..32)
        val iv = ByteArray(ivSize).also { payload.get(it) }
        val encrypted = ByteArray(payload.remaining()).also { payload.get(it) }
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, secretKey(), GCMParameterSpec(128, iv))
        String(cipher.doFinal(encrypted), Charsets.UTF_8)
    }.getOrNull()

    override var accessToken: String?
        get() = preferences.getString("access_token", null)?.let(::decrypt)
        set(value) {
            preferences.edit().apply {
                if (value == null) remove("access_token") else putString("access_token", encrypt(value))
            }.apply()
        }

    override var inspectorName: String?
        get() = preferences.getString("inspector_name", null)
        set(value) {
            preferences.edit().apply {
                if (value == null) remove("inspector_name") else putString("inspector_name", value)
            }.apply()
        }

    override fun clear() {
        preferences.edit().clear().apply()
    }
}

fun createApi(context: Context, tokenStore: SessionStore): SiteProofApi {
    val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()
    val client = OkHttpClient.Builder()
        .addInterceptor { chain ->
            val original = chain.request()
            val token = tokenStore.accessToken
            val request: Request = if (token.isNullOrBlank()) original else original.newBuilder()
                .header("Authorization", "Bearer $token")
                .build()
            chain.proceed(request)
        }
        .build()
    return Retrofit.Builder()
        .baseUrl(BuildConfig.SITEPROOF_API_BASE_URL)
        .client(client)
        .addConverterFactory(MoshiConverterFactory.create(moshi))
        .build()
        .create(SiteProofApi::class.java)
}
