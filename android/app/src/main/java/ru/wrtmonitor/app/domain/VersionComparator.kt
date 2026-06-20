package ru.wrtmonitor.app.domain

object VersionComparator {
    fun compare(left: String, right: String): Int {
        val pattern = Regex("""\d+|[A-Za-z]+""")
        val leftParts = pattern.findAll(left).map { it.value }.toList()
        val rightParts = pattern.findAll(right).map { it.value }.toList()
        val maxSize = maxOf(leftParts.size, rightParts.size)
        for (index in 0 until maxSize) {
            val leftPart = leftParts.getOrNull(index) ?: "0"
            val rightPart = rightParts.getOrNull(index) ?: "0"
            val comparison = if (leftPart.all(Char::isDigit) && rightPart.all(Char::isDigit)) leftPart.toLong().compareTo(rightPart.toLong()) else leftPart.compareTo(rightPart, ignoreCase = true)
            if (comparison != 0) return comparison
        }
        return 0
    }
}
