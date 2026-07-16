package ru.wrtmonitor.app.domain

import org.junit.Assert.assertTrue
import org.junit.Test

class VersionComparatorTest {
    @Test
    fun rc1IsNewerThanTest16() {
        assertTrue(VersionComparator.compare("0.1.1-rc1", "0.1.0-test.16") > 0)
    }

    @Test
    fun rc3IsNewerThanRc2() {
        assertTrue(VersionComparator.compare("0.1.1-rc3", "0.1.1-rc2") > 0)
    }

    @Test
    fun descriptiveReleaseTagMatchesApplicationVersion() {
        assertTrue(VersionComparator.compare("v0.2.0-rc1-full-router-foundation", "0.2.0-rc1") == 0)
    }
}
