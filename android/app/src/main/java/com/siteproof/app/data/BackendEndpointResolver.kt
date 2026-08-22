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

/**
 * Finds the SiteProof development backend on the phone's current local network.
 *
 * The APK deliberately contains no machine IP address. A previously discovered endpoint is
 * validated first, then the phone's current IPv4 /24 is probed in parallel for the SiteProof
 * /health signature. The result is cached and automatically rediscovered after a network change
 * or connection failure.
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
        val localAddress = localWifiIpv4()
            ?: throw IOException("Connect this phone to the same local network as the SiteProof server.")
        val networkKey = localAddress.hostAddress.orEmpty()

        resolved?.takeIf { resolvedNetwork == networkKey }?.let { return it }

        synchronized(this) {
            resolved?.takeIf { resolvedNetwork == networkKey }?.let { return it }

            val persisted = preferences.getString(DISCOVERY_PREF_URL, null)?.toHttpUrlOrNull()
            if (persisted != null && isHealthy(persisted)) {
                remember(persisted, networkKey)
                return persisted
            }

            val discovered = discoverOnLocalSubnet(localAddress)
                ?: throw IOException(
                    "Could not find the SiteProof server on this Wi-Fi network. " +
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

    private fun localWifiIpv4(): Inet4Address? {
        val networks = connectivity.allNetworks
        for (network in networks) {
            val capabilities = connectivity.getNetworkCapabilities(network) ?: continue
            val localTransport = capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) ||
                capabilities.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)
            if (!localTransport) continue

            val address = connectivity.getLinkProperties(network)
                ?.linkAddresses
                ?.asSequence()
                ?.map { it.address }
                ?.filterIsInstance<Inet4Address>()
                ?.firstOrNull { !it.isLoopbackAddress && !it.isLinkLocalAddress }
            if (address != null) return address
        }
        return null
    }

    private fun discoverOnLocalSubnet(localAddress: Inet4Address): HttpUrl? {
        val octets = localAddress.address.map { it.toInt() and 0xff }
        if (octets.size != 4) return null
        val prefix = "${octets[0]}.${octets[1]}.${octets[2]}"
        val ownHost = octets[3]

        // Keep discovery bounded and fast. Home/lab Wi-Fi deployments almost always place the
        // phone and development host in the same /24 even when the upstream network is broader.
        val hosts = (1..254).filter { it != ownHost }
        val executor = Executors.newFixedThreadPool(32)
        val completion = ExecutorCompletionService<HttpUrl?>(executor)

        return try {
            hosts.forEach { host ->
                completion.submit(Callable {
                    val endpoint = "http://$prefix.$host:$SITEPROOF_BACKEND_PORT/api/v1/".toHttpUrl()
                    if (isHealthy(endpoint)) endpoint else null
                })
            }

            val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(5)
            repeat(hosts.size) {
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
