package com.phantom.app.session

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

class SessionStore(context: Context) {

    private val prefs: SharedPreferences = buildPreferences(context)

    fun saveServerUrl(url: String) {
        prefs.edit().putString(KEY_SERVER_URL, url).apply()
    }

    fun getServerUrl(): String? = prefs.getString(KEY_SERVER_URL, null)

    fun saveLastUsername(username: String) {
        prefs.edit().putString(KEY_LAST_USERNAME, username).apply()
    }

    fun getLastUsername(): String? = prefs.getString(KEY_LAST_USERNAME, null)

    private fun buildPreferences(context: Context): SharedPreferences {
        return try {
            val masterKey = MasterKey.Builder(context)
                .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                .build()
            EncryptedSharedPreferences.create(
                context,
                PREF_NAME,
                masterKey,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
            )
        } catch (_: Exception) {
            context.getSharedPreferences(PREF_NAME_FALLBACK, Context.MODE_PRIVATE)
        }
    }

    companion object {
        private const val PREF_NAME = "phantom_session"
        private const val PREF_NAME_FALLBACK = "phantom_session_fallback"
        private const val KEY_SERVER_URL = "server_url"
        private const val KEY_LAST_USERNAME = "last_username"
    }
}
