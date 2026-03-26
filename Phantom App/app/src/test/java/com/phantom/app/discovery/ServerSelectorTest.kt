package com.phantom.app.discovery

import org.junit.Assert.assertEquals
import org.junit.Test

class ServerSelectorTest {

    @Test
    fun returnsPreviousUrlWhenStillAvailable() {
        val previous = "http://192.168.1.20:8000"
        val candidates = listOf(
            ServerCandidate("http://192.168.1.50:8000", 45L, "probe"),
            ServerCandidate(previous, 120L, "mdns")
        )

        val selected = ServerSelector.selectBest(candidates, previous)

        assertEquals(previous, selected?.baseUrl)
    }

    @Test
    fun returnsLowestLatencyWhenPreviousUnavailable() {
        val candidates = listOf(
            ServerCandidate("http://192.168.1.30:8000", 90L, "probe"),
            ServerCandidate("http://192.168.1.12:8000", 25L, "mdns"),
            ServerCandidate("http://192.168.1.8:8000", 30L, "probe")
        )

        val selected = ServerSelector.selectBest(candidates, "http://192.168.1.99:8000")

        assertEquals("http://192.168.1.12:8000", selected?.baseUrl)
    }

    @Test
    fun returnsNullForEmptyCandidates() {
        val selected = ServerSelector.selectBest(emptyList(), null)
        assertEquals(null, selected)
    }
}
