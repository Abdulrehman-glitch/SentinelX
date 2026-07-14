package com.sentinelx.mobile.data.prefs

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

/** Keystore-backed storage for the two secrets: user JWT and device token. */
class SecureStore(context: Context) {

    private val prefs: SharedPreferences = run {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        EncryptedSharedPreferences.create(
            context,
            "sentinelx_secure",
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    }

    var userJwt: String?
        get() = prefs.getString(KEY_USER_JWT, null)
        set(value) = prefs.edit().putString(KEY_USER_JWT, value).apply()

    var deviceToken: String?
        get() = prefs.getString(KEY_DEVICE_TOKEN, null)
        set(value) = prefs.edit().putString(KEY_DEVICE_TOKEN, value).apply()

    fun clearUserJwt() = prefs.edit().remove(KEY_USER_JWT).apply()

    fun clearAll() = prefs.edit().clear().apply()

    private companion object {
        const val KEY_USER_JWT = "user_jwt"
        const val KEY_DEVICE_TOKEN = "device_token"
    }
}
