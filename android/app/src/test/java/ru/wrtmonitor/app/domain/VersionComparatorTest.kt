package ru.wrtmonitor.app.domain

import org.junit.Assert.assertTrue
import org.junit.Test

class VersionComparatorTest {
    @Test
    fun rc1IsNewerThanTest16() {
        assertTrue(VersionComparator.compare("0.1.1-rc1", "0.1.0-test.16") > 0)
    }
}
