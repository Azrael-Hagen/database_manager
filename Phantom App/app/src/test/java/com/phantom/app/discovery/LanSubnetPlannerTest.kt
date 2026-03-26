package com.phantom.app.discovery

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class LanSubnetPlannerTest {

    @Test
    fun excludesOwnDeviceIpFromCandidates() {
        val urls = LanSubnetPlanner.buildBaseUrls("192.168.1.20")

        assertFalse(urls.any { it.contains("192.168.1.20") })
    }

    @Test
    fun includesNeighborhoodOnSameSubnet() {
        val urls = LanSubnetPlanner.buildBaseUrls("10.0.0.50", listOf(8000, 8080))

        assertTrue(urls.any { it == "http://10.0.0.49:8000" })
        assertTrue(urls.any { it == "http://10.0.0.49:8080" })
    }

    @Test
    fun includesInfrastructureRangeWhenServerIsFarFromDeviceHost() {
        val hosts = LanSubnetPlanner.buildHosts("192.168.1.162")

        assertTrue(hosts.contains("192.168.1.10"))
        assertTrue(hosts.contains("192.168.1.40"))
    }

    @Test
    fun omitsExplicitPortForHttpPort80() {
        val urls = LanSubnetPlanner.buildBaseUrls("192.168.1.20", listOf(80))

        assertTrue(urls.any { it == "http://192.168.1.19" })
    }

    @Test
    fun fullSubnetFallbackCoversFarHosts() {
        val urls = LanSubnetPlanner.buildFullSubnetBaseUrls("192.168.1.20", listOf(8000))

        assertTrue(urls.any { it == "http://192.168.1.162:8000" })
    }

    @Test
    fun returnsEmptyForInvalidIp() {
        val urls = LanSubnetPlanner.buildBaseUrls("not-an-ip")

        assertTrue(urls.isEmpty())
    }
}
