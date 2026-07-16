package vn.pckien.inet_auto_login.network

import android.content.Context
import android.net.*
import android.net.wifi.WifiInfo
import android.os.Build
import androidx.annotation.RequiresApi
import java.net.Inet4Address
import java.util.concurrent.atomic.AtomicLong

class AndroidNetworkRepository(context: Context) : NetworkRepository {
    private val connectivity = context.getSystemService(ConnectivityManager::class.java)
    private val generation = AtomicLong()
    private var callback: ConnectivityManager.NetworkCallback? = null
    private var listener: ((NetworkContext?) -> Unit)? = null
    private val capabilities = mutableMapOf<Network, NetworkCapabilities>()
    private val linkProperties = mutableMapOf<Network, LinkProperties>()
    @Volatile private var value: NetworkContext? = null

    override fun current(): NetworkContext? = value

    override fun start(listener: (NetworkContext?) -> Unit) {
        if (callback != null) return
        this.listener = listener
        callback = createCallback().also {
            connectivity.registerNetworkCallback(
                NetworkRequest.Builder()
                    .addTransportType(NetworkCapabilities.TRANSPORT_WIFI)
                    .build(),
                it,
            )
        }
    }

    private fun createCallback(): ConnectivityManager.NetworkCallback =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            RepositoryNetworkCallback(ConnectivityManager.NetworkCallback.FLAG_INCLUDE_LOCATION_INFO)
        } else {
            RepositoryNetworkCallback()
        }

    private inner class RepositoryNetworkCallback : ConnectivityManager.NetworkCallback {
        constructor() : super()

        @RequiresApi(Build.VERSION_CODES.S)
        constructor(flags: Int) : super(flags)

        override fun onCapabilitiesChanged(network: Network, networkCapabilities: NetworkCapabilities) {
            synchronized(this@AndroidNetworkRepository) {
                capabilities[network] = networkCapabilities
                refresh(network)
            }
        }

        override fun onLinkPropertiesChanged(network: Network, properties: LinkProperties) {
            synchronized(this@AndroidNetworkRepository) {
                linkProperties[network] = properties
                refresh(network)
            }
        }

        override fun onLost(network: Network) {
            synchronized(this@AndroidNetworkRepository) {
                capabilities.remove(network)
                linkProperties.remove(network)
                if (value?.network == network) {
                    value = null
                    generation.incrementAndGet()
                    listener?.invoke(null)
                }
            }
        }
    }

    private fun refresh(network: Network) {
        val caps = capabilities[network] ?: return
        val ssid = NetworkSelectors.normalizeSsid((caps.transportInfo as? WifiInfo)?.ssid)
        if (!NetworkSelectors.isTargetSsid(ssid)) {
            if (value?.network == network) {
                value = null
                generation.incrementAndGet()
                listener?.invoke(null)
            }
            return
        }
        val links = linkProperties[network] ?: return
        val local = links.linkAddresses
            .map { it.address }
            .filterIsInstance<Inet4Address>()
            .firstOrNull()
            ?.hostAddress
            ?: return
        val gateway = NetworkSelectors.selectIpv4Gateway(
            links.routes.map {
                NetworkSelectors.RouteCandidate(
                    it.gateway?.hostAddress,
                    it.isDefaultRoute,
                    it.gateway is Inet4Address,
                )
            },
        ) ?: return
        val old = value
        val gen = if (old?.network == network) old.generation else generation.incrementAndGet()
        NetworkContext(network, gen, ssid!!, local, gateway).also {
            value = it
            listener?.invoke(it)
        }
    }

    @Synchronized
    override fun stop() {
        callback?.let { connectivity.unregisterNetworkCallback(it) }
        callback = null
        capabilities.clear()
        linkProperties.clear()
        value = null
        listener = null
    }
}
