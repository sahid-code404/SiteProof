package com.siteproof.app.verification.upload

object UploadRetryPolicy {
    fun shouldRetry(httpCode: Int?): Boolean = when {
        httpCode == null -> true
        httpCode == 408 || httpCode == 429 -> true
        httpCode in 500..599 -> true
        else -> false
    }
}
