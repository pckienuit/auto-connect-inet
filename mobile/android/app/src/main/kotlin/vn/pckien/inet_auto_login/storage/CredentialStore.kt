package vn.pckien.inet_auto_login.storage

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import org.json.JSONObject
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

data class Credential(val username: String, val password: String, val createdAt: Long = System.currentTimeMillis(), val version: Int = 1)
interface CredentialStore { fun load(): Credential?; fun save(value: Credential); fun clear() }
class AndroidCredentialStore(context: Context, private val alias: String = "inet.portal.credentials") : CredentialStore {
    private val preferences = context.getSharedPreferences("encrypted_credentials", Context.MODE_PRIVATE)
    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(alias, null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").run {
            init(KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
            generateKey()
        }
    }
    override fun save(value: Credential) {
        val plain = JSONObject().put("version",value.version).put("username",value.username).put("password",value.password).put("createdAt",value.createdAt).toString().toByteArray()
        val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE, key()) }
        preferences.edit().putString("iv", Base64.encodeToString(cipher.iv, Base64.NO_WRAP))
            .putString("data", Base64.encodeToString(cipher.doFinal(plain), Base64.NO_WRAP)).apply()
    }
    override fun load(): Credential? = try {
        val iv = preferences.getString("iv", null) ?: return null
        val data = preferences.getString("data", null) ?: return null
        val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, Base64.decode(iv, Base64.NO_WRAP))) }
        JSONObject(String(cipher.doFinal(Base64.decode(data, Base64.NO_WRAP)))).let {
            Credential(it.getString("username"), it.getString("password"), it.getLong("createdAt"), it.getInt("version"))
        }
    } catch (_: Exception) { clear(); null }
    override fun clear() { preferences.edit().clear().apply() }
}
