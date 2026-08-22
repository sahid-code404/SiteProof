package com.siteproof.app.data

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import java.io.IOException
import java.net.Inet4Address
import java.util.concurrent.Callable
import java.util.concurrent.ExecutorCompletionService
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response

internal const val SITEPROOF_DISCOVERY_HOST = "siteproof.invalid"
private const val SITEPROOF_BACKEND_PORT = 8000
private const val DISCOVERY_PREFS = "siteproof_backend_discovery"
private const val DISCOVERY_PREF_URL = "base_url"
private const val MANUAL_PREF_URL = "manual_base_url"
private const val MAX_DISCOVERY_CANDIDATES = 1022
private const val DISCOVERY_THREADS = 48
private const val DISCOVERY_DEADLINE_SECONDS = 7L

private data class LocalNetworkIpv4(
    val address: Inet4Address,
    val prefixLength: Int,
    val gateway: Inet4Address?,
)

/**
 * Runtime backend configuration for development/test APKs.
 *
 * A manually configured endpoint always wins over local-network discovery and is kept in app
 * preferences, so it survives OTA updates. No developer machine IP address is compiled into the APK.
 * Manual addresses are verified against both /health and the current SiteProof auth route before
 * they are persisted, which prevents accidentally pointing the app at the web server or a stale API.
 */
class BackendEndpointSettings(context: Context) {
    private val preferences = context.applicationContext
        .getSharedPreferences(DISCOVERY_PREFS, Context.MODE_PRIVATE)
    private val validationClient = OkHttpClient.Builder()
        .connectTimeout(2, TimeUnit.SECONDS)
        .readTimeout(3, TimeUnit.SECONDS)
        .callTimeout(5, TimeUnit.SECONDS)
        .retryOnConnectionFailure(false)
        .build()

    fun configuredEndpoint(): String? = preferences.getString(MANUAL_PREF_URL, null)

    suspend fun configureAndValidate(raw: String): String = withContext(Dispatchers.IO) {
        val endpoint = normalizeEndpoint(raw)
        validateEndpoint(endpoint)
        preferences.edit()
            .putString(MANUAL_PREF_URL, endpoint.toString())
            .remove(DISCOVERY_PREF_URL)
            .apply()
        endpoint.toString()
    }

    fun useAutomaticDiscovery() {
        preferences.edit()
            .remove(MANUAL_PREF_URL)
            .remove(DISCOVERY_PREF_URL)
            .apply()
    }

    private fun normalizeEndpoint(raw: String): HttpUrl {
        val trimmed = raw.trim()
        require(trimmed.isNotBlank()) { "Enter the backend IP address or URL." }

        val withScheme = if (trimmed.contains("://")) trimmed else "http://$trimmed"
        val parsed = withScheme.toHttpUrlOrNull()
            ?: throw IllegalArgumentException("Enter a valid backend IP address or URL.")
        require(parsed.scheme == "http" || parsed.scheme == "https") {
            "Backend URL must use http or https."
        }

        val authority = withScheme.substringAfter("://").substringBefore('/')
        val explicitPort = authority.substringAfterLast(':', "").toIntOrNull()
        val builder = parsed.newBuilder()
            .encodedPath("/api/v1/")
            .query(null)
            .fragment(null)
        if (parsed.scheme == "http" && explicitPort == null) {
            builder.port(SITEPROOF_BACKEND_PORT)
        }
        return builder.build()
    }

    private fun validateEndpoint(endpoint: HttpUrl) {
        val healthUrl = endpoint.newBuilder()
            .encodedPath("/health")
            .query(null)
            .build()
        val healthRequest = Request.Builder().url(healthUrl).get().build()
        val healthy = runCatching {
            validationClient.newCall(healthRequest).execute().use { response ->
                if (!response.isSuccessful) return@use false
                val body = response.body?.string().orEmpty()
                body.contains("\"status\":\"ok\"") &&
                    body.contains("\"service\":\"siteproof-api\"")
            }
        }.getOrElse { error ->
            throw IllegalArgumentException(
                "Could not reach SiteProof at ${endpoint.host}:${endpoint.port}. " +
                    "Check the IP, port, Wi-Fi and backend container.",
                error,
            )
        }
        require(healthy) {
            "The address responds, but it is not the SiteProof backend. Use the backend port (normally 8000), not the web dashboard port."
        }

        val authUrl = endpoint.newBuilder()
            .encodedPath("/api/v1/auth/me")
            .query(null)
            .build()
        val authRequest = Request.Builder().url(authUrl).get().build()
        val authStatus = runCatching {
            validationClient.newCall(authRequest).execute().use { it.code }
        }.getOrElse { error ->
            throw IllegalArgumentException("The SiteProof backend became unreachable while checking its API.", error)
        }
        require(authStatus != 404) {
            "This server is running an older or incorrect SiteProof API: /api/v1/auth/me was not found (HTTP 404). Rebuild/restart the current backend."
        }
        require(authStatus in setOf(200, 401, 403)) {
            "The SiteProof auth API returned HTTP $authStatus. Verify that the current backend is running on this address."
        }
    }
}

/**
 * Finds the SiteProof development backend on the phone's current local network.
 *
 * The APK deliberately contains no machine IP address. If the user configured a backend in the
 * sign-in screen, that endpoint is used first. Otherwise a previously discovered endpoint is
 * validated, then discovery uses Android's actual IPv4 prefix instead of assuming /24. The result
 * is cached and automatically rediscovered after a network change or connection failure.
 */
internal class BackendEndpointResolver(context: Context) {
    private val appContext = context.applicationContext
    private val connectivity = appContext.getSystemService(ConnectivityManager::class.java)
    private val preferences = appContext.getSharedPreferences(DISCOVERY_PREFS, Context.MODE_PRIVATE)
    private val probeClient = OkHttpClient.Builder()
        .connectTimeout(250, TimeUnit.MILLISECONDS)
        .readTimeout(450, TimeUnit.MILLISECONDS)
        .callTimeout(650, TimeUnit.MILLISECONDS)
        .retryOnConnectionFailure(false)
        .build()

    @Volatile
    private var resolved: HttpUrl? = null

    @Volatile
    private var resolvedNetwork: String? = null

    fun resolve(): HttpUrl {
        preferences.getString(MANUAL_PREF_URL, null)?.toHttpUrlOrNull()?.let { return it }

        val localNetwork = localNetworkIpv4()
            ?: throw IOException(
                "Connect this phone to the same local network as the SiteProof server, " +
                    "or configure the backend IP on the sign-in screen.",
            )
        val networkKey = "${localNetwork.address.hostAddress}/${localNetwork.prefixLength}"

        resolved?.takeIf { resolvedNetwork == networkKey }?.let { return it }

        synchronized(this) {
            preferences.getString(MANUAL_PREF_URL, null)?.toHttpUrlOrNull()?.let { return it }
            resolved?.takeIf { resolvedNetwork == networkKey }?.let { return it }

            val persisted = preferences.getString(DISCOVERY_PREF_URL, null)?.toHttpUrlOrNull()
            if (persisted != null && isHealthy(persisted)) {
                remember(persisted, networkKey)
                return persisted
            }

            val discovered = discoverOnLocalSubnet(localNetwork)
                ?: throw IOException(
                    "Could not find the SiteProof server on this local network. " +
                        "Configure the backend IP on the sign-in screen or verify that the backend is running.",
                )
            remember(discovered, networkKey)
            return discovered
        }
    }

    fun invalidate(endpoint: HttpUrl? = null) {
        synchronized(this) {
            if (endpoint == null || resolved == endpoint) {
                resolved = null
                resolvedNetwork = null
            }
            val persisted = preferences.getString(DISCOVERY_PREF_URL, null)?.toHttpUrlOrNull()
            if (endpoint == null || persisted == endpoint) {
                preferences.edit().remove(DISCOVERY_PREF_URL).apply()
            }
        }
    }

    private fun remember(endpoint: HttpUrl, networkKey: String) {
        resolved = endpoint
        resolvedNetwork = networkKey
        preferences.edit().putString(DISCOVERY_PREF_URL, endpoint.toString()).apply()
    }

    private fun localNetworkIpv4(): LocalNetworkIpv4? {
        for (network in connectivity.allNetworks) {
            val capabilities = connectivity.getNetworkCapabilities(network) ?: continue
            val localTransport = capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) ||
                capabilities.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)
            if (!localTransport) continue

            val linkProperties = connectivity.getLinkProperties(network) ?: continue
            val linkAddress = linkProperties.linkAddresses.firstOrNull { candidate ->
                val address = candidate.address
                address is Inet4Address && !address.isLoopbackAddress && !address.isLinkLocalAddress
            } ?: continue
            val address = linkAddress.address as Inet4Address
            val gateway = linkProperties.routes
                .asSequence()
                .mapNotNull { route -> route.gateway as? Inet4Address }
                .firstOrNull { !it.isLoopbackAddress && !it.isLinkLocalAddress }

            return LocalNetworkIpv4(
                address = address,
                prefixLength = linkAddress.prefixLength.coerceIn(0, 32),
                gateway = gateway,
            )
        }
        return null
    }

    private fun discoverOnLocalSubnet(localNetwork: LocalNetworkIpv4): HttpUrl? {
        val candidates = discoveryCandidates(localNetwork)
        if (candidates.isEmpty()) return null

        val executor = Executors.newFixedThreadPool(minOf(DISCOVERY_THREADS, candidates.size))
        val completion = ExecutorCompletionService<HttpUrl?>(executor)

        return try {
            candidates.forEach { host ->
                completion.submit(Callable {
                    val endpoint = "http://$host:$SITEPROOF_BACKEND_PORT/api/v1/".toHttpUrl()
                    if (isHealthy(endpoint)) endpoint else null
                })
            }

            val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(DISCOVERY_DEADLINE_SECONDS)
            repeat(candidates.size) {
                val remaining = deadline - System.nanoTime()
                if (remaining <= 0L) return@repeat
                val result = completion.poll(remaining, TimeUnit.NANOSECONDS) ?: return@repeat
                val endpoint = runCatching { result.get() }.getOrNull()
                if (endpoint != null) return endpoint
            }
            null
        } catch (_: InterruptedException) {
            Thread.currentThread().interrupt()
            null
        } finally {
            executor.shutdownNow()
        }
    }

    private fun discoveryCandidates(localNetwork: LocalNetworkIpv4): List<String> {
        val own = ipv4ToLong(localNetwork.address)
        val prefixLength = localNetwork.prefixLength
        val mask = when (prefixLength) {
            0 -> 0L
            else -> (0xffffffffL shl (32 - prefixLength)) and 0xffffffffL
        }
        val networkAddress = own and mask
        val broadcastAddress = networkAddress or (mask.inv() and 0xffffffffL)
        val usableHosts = (broadcastAddress - networkAddress - 1L).coerceAtLeast(0L)
        val candidates = linkedSetOf<Long>()

        localNetwork.gateway?.let(::ipv4ToLong)?.let { gateway ->
            if (gateway != own && gateway in (networkAddress + 1L) until broadcastAddress) {
                candidates += gateway
            }
        }

        if (usableHosts <= MAX_DISCOVERY_CANDIDATES) {
            var candidate = networkAddress + 1L
            while (candidate < broadcastAddress) {
                if (candidate != own) candidates += candidate
                candidate += 1L
            }
        } else {
            val local24Network = own and 0xffffff00L
            val local24Broadcast = local24Network or 0xffL
            var candidate = maxOf(networkAddress + 1L, local24Network + 1L)
            val local24End = minOf(broadcastAddress, local24Broadcast)
            while (candidate < local24End && candidates.size < MAX_DISCOVERY_CANDIDATES) {
                if (candidate != own) candidates += candidate
                candidate += 1L
            }

            val remaining = MAX_DISCOVERY_CANDIDATES - candidates.size
            if (remaining > 0 && usableHosts > 0) {
                val stride = maxOf(1L, usableHosts / remaining.toLong())
                candidate = networkAddress + 1L
                while (candidate < broadcastAddress && candidates.size < MAX_DISCOVERY_CANDIDATES) {
                    if (candidate != own) candidates += candidate
                    candidate += stride
                }
            }
        }

        return candidates
            .asSequence()
            .filter { it != own }
            .take(MAX_DISCOVERY_CANDIDATES)
            .map(::longToIpv4)
            .toList()
    }

    private fun ipv4ToLong(address: Inet4Address): Long = address.address.fold(0L) { value, octet ->
        (value shl 8) or (octet.toInt() and 0xff).toLong()
    }

    private fun longToIpv4(value: Long): String = listOf(
        (value shr 24) and 0xff,
        (value shr 16) and 0xff,
        (value shr 8) and 0xff,
        value and 0xff,
    ).joinToString(".")

    private fun isHealthy(endpoint: HttpUrl): Boolean {
        val healthUrl = endpoint.newBuilder()
            .encodedPath("/health")
            .query(null)
            .build()
        val request = Request.Builder().url(healthUrl).get().build()
        return runCatching {
            probeClient.newCall(request).execute().use { response ->
                if (!response.isSuccessful) return@use false
                val body = response.body?.string().orEmpty()
                body.contains("\"status\":\"ok\"") && body.contains("\"service\":\"siteproof-api\"")
            }
        }.getOrDefault(false)
    }
}

/** Rewrites only SiteProof's placeholder Retrofit host; absolute evidence URLs remain untouched. */
internal class BackendEndpointInterceptor(context: Context) : Interceptor {
    private val resolver = BackendEndpointResolver(context)

    override fun intercept(chain: Interceptor.Chain): Response {
        val original = chain.request()
        if (original.url.host != SITEPROOF_DISCOVERY_HOST) return chain.proceed(original)

        val firstEndpoint = resolver.resolve()
        return try {
            chain.proceed(rewrite(original, firstEndpoint))
        } catch (firstFailure: IOException) {
            resolver.invalidate(firstEndpoint)
            val secondEndpoint = resolver.resolve()
            if (secondEndpoint == firstEndpoint) throw firstFailure
            chain.proceed(rewrite(original, secondEndpoint))
        }
    }

    private fun rewrite(request: Request, endpoint: HttpUrl): Request {
        val url = request.url.newBuilder()
            .scheme(endpoint.scheme)
            .host(endpoint.host)
            .port(endpoint.port)
            .build()
        return request.newBuilder().url(url).build()
    }
}
