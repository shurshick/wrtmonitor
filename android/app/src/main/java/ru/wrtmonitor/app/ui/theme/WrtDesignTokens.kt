package ru.wrtmonitor.app.ui.theme

import androidx.compose.ui.unit.dp

object WrtSpacing {
    val xxs = 4.dp
    val xs = 8.dp
    val sm = 12.dp
    val md = 16.dp
    val lg = 24.dp
    val xl = 32.dp
}

object WrtSizes {
    val iconSmall = 18.dp
    val icon = 22.dp
    val iconLarge = 28.dp
    val touchTarget = 48.dp
    val contentMaxWidth = 1120.dp
    val readingMaxWidth = 760.dp
    val navigationRailWidth = 88.dp
}

object WrtMotion {
    const val quick = 120
    const val standard = 220
    const val deliberate = 320
}

enum class WrtStatus {
    Online,
    Offline,
    Warning,
    Critical,
    Updating,
    Rebooting,
    Connecting,
    Unknown,
    Disabled,
}
