package vn.pckien.inet_auto_login.network

import android.content.Context
import android.net.*
import android.net.wifi.WifiInfo
import java.net.Inet4Address
import java.util.concurrent.atomic.AtomicLong

class AndroidNetworkRepository(context: Context) : NetworkRepository {
    private val connectivity = context.getSystemService(ConnectivityManager::class.java)
    private val generation = AtomicLong()
    private var callback: ConnectivityManager.NetworkCallback? = null
    private var listener: ((NetworkContext?) -> Unit)? = null
    @Volatile private var value: NetworkContext? = null
    override fun current(): NetworkContext? = value
    override fun start(listener: (NetworkContext?) -> Unit) {
        if (callback != null) return
        this.listener = listener
        callback = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) = refresh(network)
            override fun onCapabilitiesChanged(network: Network, capabilities: NetworkCapabilities) = refresh(network)
            override fun onLinkPropertiesChanged(network: Network, linkProperties: LinkProperties) = refresh(network)
            override fun onLost(network: Network) { if (value?.network == network) { value = null; generation.incrementAndGet(); listener(null) } }
        }.also { connectivity.registerNetworkCallback(NetworkRequest.Builder().addTransportType(NetworkCapabilities.TRANSPORT_WIFI).build(), it) }
    }
    private fun refresh(network: Network) {
        val caps = connectivity.getNetworkCapabilities(network) ?: return
        val ssid = NetworkSelectors.normalizeSsid((caps.transportInfo as? WifiInfo)?.ssid)
        if (!NetworkSelectors.isTargetSsid(ssid)) { if (value?.network == network) { value = null; listener?.invoke(null) }; return }
        val links = connectivity.getLinkProperties(network) ?: return
        val local = links.linkAddresses.map { it.address }.filterIsInstance<Inet4Address>().firstOrNull()?.hostAddress ?: return
        val gateway = NetworkSelectors.selectIpv4Gateway(links.routes.map {
            NetworkSelectors.RouteCandidate(it.gateway?.hostAddress, it.isDefaultRoute, it.gateway is Inet4Address)
        }) ?: return
        val old = value
        val gen = if (old?.network == network) old.generation else generation.incrementAndGet()
        NetworkContext(network, gen, ssid!!, local, gateway).also { value = it; listener?.invoke(it) }
    }
    override fun stop() { callback?.let { connectivity.unregisterNetworkCallback(it) }; callback = null; value = null; listener = null }
}
