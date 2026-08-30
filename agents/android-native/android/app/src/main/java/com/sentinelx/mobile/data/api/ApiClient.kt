package com.sentinelx.mobile.data.api

import com.sentinelx.mobile.BuildConfig
import com.sentinelx.mobile.data.api.dto.ApiErrorBody
import kotlinx.serialization.json.Json
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Response
import retrofit2.HttpException
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * Rewrites every request against the base URL the user configured at login,
 * so a single Retrofit instance survives server-address changes.
 */
class HostSelectionInterceptor(private val baseUrlProvider: () -> String) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val configured = baseUrlProvider().trim()
        val target: HttpUrl = normalize(configured)?.toHttpUrlOrNull()
            ?: throw IOException("Invalid SentinelX server URL: \"$configured\"")

        val original = chain.request()
        val rewritten = original.url.newBuilder()
            .scheme(target.scheme)
            .host(target.host)
            .port(target.port)
            .build()

        return chain.proceed(original.newBuilder().url(rewritten).build())
    }

    companion object {
        fun normalize(raw: String): String? = normalize(raw, BuildConfig.ALLOW_LOCAL_CLEARTEXT)

        /**
         * Release builds are HTTPS-only: a missing scheme becomes https://,
         * and explicit http:// is rejected instead of silently accepted
         * (network security config would block it anyway — fail loudly here).
         * Debug and "local" builds accept http://, and even there only for
         * private-network / loopback hosts — a cleartext URL pointing at the
         * public internet is refused in every build.
         */
        fun normalize(raw: String, allowCleartext: Boolean): String? {
            if (raw.isBlank()) return null
            val trimmed = raw.trim()
            val withScheme = when {
                trimmed.startsWith("https://") -> trimmed
                trimmed.startsWith("http://") ->
                    if (allowCleartext && isPrivateHost(trimmed)) trimmed else return null
                else -> {
                    val asHttp = "http://$trimmed"
                    if (allowCleartext && isPrivateHost(asHttp)) asHttp else "https://$trimmed"
                }
            }
            return withScheme.trimEnd('/')
        }

        /** True for RFC1918 ranges, loopback, link-local and .local names. */
        fun isPrivateHost(url: String): Boolean {
            val host = url.toHttpUrlOrNull()?.host ?: return false
            if (host == "localhost" || host.endsWith(".local")) return true
            val parts = host.split(".")
            if (parts.size == 4 && parts.all { (it.toIntOrNull() ?: -1) in 0..255 }) {
                val a = parts[0].toInt()
                val b = parts[1].toInt()
                return a == 10 || a == 127 ||
                    (a == 192 && b == 168) ||
                    (a == 172 && b in 16..31) ||
                    (a == 169 && b == 254)
            }
            return false
        }
    }
}

object ApiClient {

    val json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
        explicitNulls = false
        coerceInputValues = true
    }

    fun create(baseUrlProvider: () -> String): SentinelXApi {
        val client = OkHttpClient.Builder()
            .addInterceptor(HostSelectionInterceptor(baseUrlProvider))
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(20, TimeUnit.SECONDS)
            .writeTimeout(20, TimeUnit.SECONDS)
            .build()

        return Retrofit.Builder()
            // Placeholder; HostSelectionInterceptor swaps in the real host per request.
            .baseUrl("http://sentinelx.invalid/")
            .client(client)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
            .create(SentinelXApi::class.java)
    }

    /** Extracts FastAPI's {"detail": "..."} message when available. */
    fun readableError(t: Throwable): String = when (t) {
        is HttpException -> {
            val detail = try {
                t.response()?.errorBody()?.string()?.let { body ->
                    json.decodeFromString(ApiErrorBody.serializer(), body).detail
                }
            } catch (_: Exception) {
                null
            }
            detail ?: "Server error (HTTP ${t.code()})"
        }
        is IOException -> t.message?.takeIf { it.isNotBlank() }?.let { "Network error: $it" } ?: "Network error"
        else -> t.message ?: "Unexpected error"
    }
}
