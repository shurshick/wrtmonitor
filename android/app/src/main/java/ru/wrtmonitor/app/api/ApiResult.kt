package ru.wrtmonitor.app.api

sealed class ApiResult<out T> {
    data class Success<T>(val data: T) : ApiResult<T>()
    data class Error(
        val message: String,
        val statusCode: Int? = null,
        val code: String? = null,
        val cause: Throwable? = null,
    ) : ApiResult<Nothing>()
}

fun ApiResult.Error.isUnauthorized(): Boolean = statusCode == 401
