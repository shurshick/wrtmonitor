package ru.wrtmonitor.app.ui.screens

import org.junit.Assert.assertEquals
import org.junit.Test

class TelemetryChartTest {
    @Test
    fun niceAxisMaximumUsesReadableSteps() {
        assertEquals(1.0, niceTelemetryAxisMaximum(0.0), 0.0)
        assertEquals(2.0, niceTelemetryAxisMaximum(1.2), 0.0)
        assertEquals(5.0, niceTelemetryAxisMaximum(4.1), 0.0)
        assertEquals(10.0, niceTelemetryAxisMaximum(9.9), 0.0)
        assertEquals(2_000_000.0, niceTelemetryAxisMaximum(1_340_000.0), 0.0)
    }

    @Test
    fun niceAxisMaximumHandlesInvalidValues() {
        assertEquals(1.0, niceTelemetryAxisMaximum(Double.NaN), 0.0)
        assertEquals(1.0, niceTelemetryAxisMaximum(Double.POSITIVE_INFINITY), 0.0)
        assertEquals(1.0, niceTelemetryAxisMaximum(-10.0), 0.0)
    }
}
