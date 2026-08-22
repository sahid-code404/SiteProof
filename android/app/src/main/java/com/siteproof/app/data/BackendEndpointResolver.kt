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
private const val MAX_DISCOVERY_CANDIDATES = 1022
private const val DISCOVERY_THREADS = 48
private const val DISCOVERY_DEADLINE_SECONDS = 7L

private data class LocalNetworkIpv4(
    val address: Inet4Address,
    val prefixLength: Int,
    val gateway: Inet4Address?,
)

/**
 * Finds the SiteProof development backend on the phone's current local network.
 *
 * The APK deliberately contains no machine IP address. A previously discovered endpoint is
 * validated first. Discovery then uses Android's actual IPv4 prefix instead of assuming /24.
 * The default gateway is tried first, normal /22-/23-/24 style LANs are scanned completely, and
 * unusually large subnets use a bounded set that prioritizes the phone's local /24 plus addresses
 * spread across the advertised subnet. The result is cached and automatically rediscovered after
 * a network change or connection failure.
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
        val localNetwork = localNetworkIpv4()
            ?: throw IOException("Connect this phone to the same local network as the SiteProof server.")
        val networkKey = "${localNetwork.address.hostAddress}/${localNetwork.prefixLength}"

        resolved?.takeIf { resolvedNetwork == networkKey }?.let { return it }

        synchronized(this) {
            resolved?.takeIf { resolvedNetwork == networkKey }?.let { return it }

            val persisted = preferences.getString(DISCOVERY_PREF_URL, null)?.toHttpUrlOrNull()
            if (persisted != null && isHealthy(persisted)) {
                remember(persisted, networkKey)
                return persisted
            }

            val discovered = discoverOnLocalSubnet(localNetwork)
                ?: throw IOException(
                    "Could not find the SiteProof server on this local network. " +
                        "Make sure the backend is running and the phone is on the same network.",
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
            // First cover the phone's immediate /24 because home, hotspot and lab servers are most
            // commonly placed there even when DHCP advertises a wider subnet.
            val local24Network = own and 0xffffff00L
            val local24Broadcast = local24Network or 0xffL
            var candidate = maxOf(networkAddress + 1L, local24Network + 1L)
            val local24End = minOf(broadcastAddress, local24Broadcast)
            while (candidate < local24End && candidates.size < MAX_DISCOVERY_CANDIDATES) {
                if (candidate != own) candidates += candidate
                candidate += 1L
            }

            // Spend the remaining bounded budget evenly across the real subnet rather than silently
            // assuming that every LAN is /24.
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
