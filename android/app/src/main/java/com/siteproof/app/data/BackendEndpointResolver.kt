package com.siteproof.app.data

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import com.siteproof.app.BuildConfig
import java.io.IOException
import java.net.Inet4Address
import java.util.concurrent.Callable
import java.util.concurrent.ExecutorCompletionService
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response

internal const val SITEPROOF_DISCOVERY_HOST = "siteproof.invalid"
private const val SITEPROOF_BACKEND_PORT = 8010
private const val DISCOVERY_PREFS = "siteproof_backend_discovery_redesign_8010"
private const val DISCOVERY_PREF_URL = "base_url"
private const val MAX_DISCOVERY_CANDIDATES = 1022
private const val DISCOVERY_THREADS = 48
private const val DISCOVERY_DEADLINE_SECONDS = 7L
private const val ADB_REVERSE_NETWORK_KEY = "adb-reverse"
private const val PRECONFIGURED_NETWORK_KEY = "preconfigured"

private data class LocalNetworkIpv4(
    val address: Inet4Address,
    val prefixLength: Int,
    val gateway: Inet4Address?,
)

/**
 * Finds the redesign SiteProof development backend.
 *
 * Resolution order:
 * 1. 127.0.0.1:8010 for `adb reverse tcp:8010 tcp:8010`.
 * 2. Debug-build preconfigured backend URL, currently the active Fedora redesign backend.
 * 3. Last known healthy endpoint.
 * 4. Automatic LAN discovery on port 8010.
 *
 * The preconfigured address is only a debug convenience. If it changes or is blocked by the
 * network, the resolver continues automatically instead of failing on that address.
 */
internal class BackendEndpointResolver(context: Context) {
    private val appContext = context.applicationContext
    private val connectivity = appContext.getSystemService(ConnectivityManager::class.java)
    private val preferences = appContext.getSharedPreferences(DISCOVERY_PREFS, Context.MODE_PRIVATE)
    private val probeClient = OkHttpClient.Builder()
        .connectTimeout(300, TimeUnit.MILLISECONDS)
        .readTimeout(600, TimeUnit.MILLISECONDS)
        .callTimeout(800, TimeUnit.MILLISECONDS)
        .retryOnConnectionFailure(false)
        .build()
    private val adbReverseEndpoint = "http://127.0.0.1:$SITEPROOF_BACKEND_PORT/api/v1/".toHttpUrl()
    private val preconfiguredEndpoint = BuildConfig.SITEPROOF_DEV_BACKEND_URL
        .trim()
        .takeIf(String::isNotEmpty)
        ?.toHttpUrlOrNull()

    @Volatile
    private var resolved: HttpUrl? = null

    @Volatile
    private var resolvedNetwork: String? = null

    fun resolve(): HttpUrl {
        synchronized(this) {
            // Works even when the Wi-Fi isolates clients, as long as USB debugging is connected
            // and `adb reverse tcp:8010 tcp:8010` is active.
            if (isHealthy(adbReverseEndpoint)) {
                remember(adbReverseEndpoint, ADB_REVERSE_NETWORK_KEY)
                return adbReverseEndpoint
            }

            // Fast path for the current development machine. Never trust it blindly: the health
            // check must succeed, otherwise continue to cached/LAN discovery.
            preconfiguredEndpoint
                ?.takeIf { it.port == SITEPROOF_BACKEND_PORT && isHealthy(it) }
                ?.let {
                    remember(it, PRECONFIGURED_NETWORK_KEY)
                    return it
                }

            val localNetwork = localNetworkIpv4()
                ?: throw IOException(
                    "Could not reach the SiteProof redesign server on port $SITEPROOF_BACKEND_PORT. " +
                        "Use USB debugging with `adb reverse tcp:$SITEPROOF_BACKEND_PORT tcp:$SITEPROOF_BACKEND_PORT`, " +
                        "or connect to a local network that allows device-to-device traffic.",
                )
            val networkKey = "${localNetwork.address.hostAddress}/${localNetwork.prefixLength}"

            resolved?.takeIf {
                resolvedNetwork == networkKey &&
                    it.port == SITEPROOF_BACKEND_PORT &&
                    isHealthy(it)
            }?.let { return it }

            val persisted = preferences.getString(DISCOVERY_PREF_URL, null)?.toHttpUrlOrNull()
            if (persisted != null && persisted.port == SITEPROOF_BACKEND_PORT && isHealthy(persisted)) {
                remember(persisted, networkKey)
                return persisted
            }

            val discovered = discoverOnLocalSubnet(localNetwork)
                ?: throw IOException(
                    "Could not find the SiteProof redesign server on port $SITEPROOF_BACKEND_PORT. " +
                        "This Wi-Fi may block device-to-device traffic. Keep USB connected and run " +
                        "`adb reverse tcp:$SITEPROOF_BACKEND_PORT tcp:$SITEPROOF_BACKEND_PORT`.",
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
        if (endpoint.port != SITEPROOF_BACKEND_PORT) return false
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
