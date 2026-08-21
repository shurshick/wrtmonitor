package ru.wrtmonitor.app.ui.screens

import android.content.Context
import android.content.Intent
import ru.wrtmonitor.app.R

internal fun shareDiagnosticReport(context: Context, deviceName: String, report: String) {
    val share = Intent(Intent.ACTION_SEND).apply {
        type = "application/json"
        putExtra(Intent.EXTRA_SUBJECT, "WrtMonitor $deviceName")
        putExtra(Intent.EXTRA_TEXT, report)
    }
    context.startActivity(
        Intent.createChooser(share, context.getString(R.string.share_diagnostic_report))
    )
}
