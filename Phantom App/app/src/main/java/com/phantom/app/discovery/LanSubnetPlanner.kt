package com.phantom.app.discovery

object LanSubnetPlanner {
    private const val INFRASTRUCTURE_LOWER_BOUND = 2
    private const val INFRASTRUCTURE_UPPER_BOUND = 40
    private const val NEIGHBOR_RADIUS = 12

    fun buildBaseUrls(deviceIp: String?, ports: List<Int> = listOf(8000)): List<String> {
        val hosts = buildHosts(deviceIp)
        if (hosts.isEmpty()) {
            return emptyList()
        }

        return hosts.flatMap { host -> ports.map { port -> formatBaseUrl(host, port) } }
    }

    fun buildFullSubnetBaseUrls(deviceIp: String?, ports: List<Int> = listOf(8000)): List<String> {
        val hosts = buildAllHosts(deviceIp)
        if (hosts.isEmpty()) {
            return emptyList()
        }

        return hosts.flatMap { host -> ports.map { port -> formatBaseUrl(host, port) } }
    }

    fun buildHosts(deviceIp: String?): List<String> {
        val parsed = parseDeviceIp(deviceIp) ?: return emptyList()
        val (prefix, hostOctet) = parsed

        val lower = maxOf(INFRASTRUCTURE_LOWER_BOUND, hostOctet - NEIGHBOR_RADIUS)
        val upper = minOf(254, hostOctet + NEIGHBOR_RADIUS)

        val prioritizedHostOctets = linkedSetOf<Int>()

        for (octet in lower..upper) {
            if (octet != hostOctet) {
                prioritizedHostOctets += octet
            }
        }

        for (octet in INFRASTRUCTURE_LOWER_BOUND..INFRASTRUCTURE_UPPER_BOUND) {
            if (octet != hostOctet) {
                prioritizedHostOctets += octet
            }
        }

        return prioritizedHostOctets.map { "$prefix.$it" }
    }

    private fun buildAllHosts(deviceIp: String?): List<String> {
        val parsed = parseDeviceIp(deviceIp) ?: return emptyList()
        val (prefix, hostOctet) = parsed

        return (INFRASTRUCTURE_LOWER_BOUND..254)
            .asSequence()
            .filter { it != hostOctet }
            .map { "$prefix.$it" }
            .toList()
    }

    private fun parseDeviceIp(deviceIp: String?): Pair<String, Int>? {
        if (deviceIp.isNullOrBlank()) {
            return null
        }

        val octets = deviceIp.split(".")
        if (octets.size != 4) {
            return null
        }

        val hostOctet = octets[3].toIntOrNull() ?: return null
        val prefix = "${octets[0]}.${octets[1]}.${octets[2]}"
        return prefix to hostOctet
    }

    private fun formatBaseUrl(host: String, port: Int): String {
        return when (port) {
            80 -> "http://$host"
            443 -> "https://$host"
            8443 -> "https://$host:8443"
            else -> "http://$host:$port"
        }
    }
}
