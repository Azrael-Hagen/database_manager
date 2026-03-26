package com.phantom.app.discovery

import android.content.Context
import android.net.wifi.WifiManager
import okhttp3.OkHttpClient
import okhttp3.Request
import java.net.NetworkInterface
import java.util.concurrent.Callable
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

class PhantomDiscoveryManager(
    private val context: Context,
    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(450, TimeUnit.MILLISECONDS)
        .readTimeout(450, TimeUnit.MILLISECONDS)
        .writeTimeout(450, TimeUnit.MILLISECONDS)
        .build()
) {

    private val discoveryPorts = listOf(8000, 80)

    data class DiscoveryResult(
        val selected: ServerCandidate?,
        val allCandidates: List<ServerCandidate>
    )

    fun discover(previousUrl: String?, onComplete: (DiscoveryResult) -> Unit, onFailure: (String) -> Unit) {
        val coordinator = Executors.newSingleThreadExecutor()
        coordinator.execute {
            try {
                val candidates = discoverCandidates(previousUrl)
                val selected = ServerSelector.selectBest(candidates, previousUrl)
                onComplete(DiscoveryResult(selected = selected, allCandidates = candidates))
            } catch (ex: Exception) {
                onFailure(ex.message ?: "No se pudo detectar un servidor en LAN")
            } finally {
                coordinator.shutdown()
            }
        }
    }

    private fun discoverCandidates(previousUrl: String?): List<ServerCandidate> {
        val staticUrls = listOf(
            "http://phantom.database.local",
            "http://phantom.database.local:8000",
            "http://database-manager.local:8000",
            "http://phantom.local:8000"
        )

        val localIp = getDeviceIpAddress()
        val plannedUrls = LanSubnetPlanner.buildBaseUrls(localIp, discoveryPorts)
        val fullSubnetUrls = LanSubnetPlanner.buildFullSubnetBaseUrls(localIp, discoveryPorts)

        val prioritizedUrls = linkedSetOf<String>()
        if (!previousUrl.isNullOrBlank()) {
            prioritizedUrls += previousUrl.trimEnd('/')
        }
        prioritizedUrls += staticUrls
        prioritizedUrls += plannedUrls

        val prioritizedResults = probeMany(prioritizedUrls.toList(), previousUrl, timeoutSeconds = 4)
        if (prioritizedResults.isNotEmpty()) {
            return prioritizedResults
        }

        val fallbackUrls = linkedSetOf<String>()
        fallbackUrls += prioritizedUrls
        fallbackUrls += fullSubnetUrls
        return probeMany(fallbackUrls.toList(), previousUrl, timeoutSeconds = 8)
    }

    private fun probeMany(urls: List<String>, previousUrl: String?, timeoutSeconds: Long): List<ServerCandidate> {
        val pool = Executors.newFixedThreadPool(24)
        return try {
            val tasks = urls.map { baseUrl ->
                Callable {
                    probe(baseUrl)?.copy(source = sourceOf(baseUrl, previousUrl))
                }
            }
            pool.invokeAll(tasks, timeoutSeconds, TimeUnit.SECONDS)
                .mapNotNull { future -> runCatching { future.get() }.getOrNull() }
                .sortedBy { it.latencyMs }
        } finally {
            pool.shutdownNow()
        }
    }

    private fun sourceOf(baseUrl: String, previousUrl: String?): String {
        return when {
            !previousUrl.isNullOrBlank() && baseUrl == previousUrl -> "cached"
            baseUrl.contains(".local") -> "hostname"
            else -> "probe"
        }
    }

    private fun probe(baseUrl: String): ServerCandidate? {
        val url = "$baseUrl/api/health"
        val request = Request.Builder().url(url).get().build()
        val started = System.nanoTime()

        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                return null
            }
            val body = response.body?.string().orEmpty()
            if (!body.contains("ok", ignoreCase = true) && !body.contains("status", ignoreCase = true)) {
                return null
            }
            val latency = TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - started)
            return ServerCandidate(baseUrl = baseUrl, latencyMs = latency, source = "probe")
        }
    }

    private fun getDeviceIpAddress(): String? {
        val wifiIp = runCatching {
            val wifi = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager
                ?: return null
            val ip = wifi.connectionInfo.ipAddress
            if (ip == 0) {
                return null
            }
            val a = ip and 0xff
            val b = ip shr 8 and 0xff
            val c = ip shr 16 and 0xff
            val d = ip shr 24 and 0xff
            "$a.$b.$c.$d"
        }.getOrNull()

        if (!wifiIp.isNullOrBlank()) {
            return wifiIp
        }

        return runCatching {
            NetworkInterface.getNetworkInterfaces().toList()
                .asSequence()
                .filter { network -> network.isUp && !network.isLoopback }
                .flatMap { network -> network.inetAddresses.toList().asSequence() }
                .mapNotNull { address -> address.hostAddress }
                .firstOrNull { host ->
                    host.count { it == '.' } == 3 &&
                        !host.startsWith("127.") &&
                        !host.startsWith("169.254.")
                }
        }.getOrNull()
    }
}
