package com.phantom.app

import android.Manifest
import android.annotation.SuppressLint
import android.content.ActivityNotFoundException
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.webkit.PermissionRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.phantom.app.bridge.PhantomJavascriptBridge
import com.phantom.app.discovery.PhantomDiscoveryManager
import com.phantom.app.qr.NativeQrScannerActivity
import com.phantom.app.session.SessionStore
import com.phantom.app.web.PhantomWebChromeClient
import com.phantom.app.web.PhantomWebViewClient
import com.phantom.app.web.QrInjectionScriptBuilder
import com.phantom.app.web.TrustedOriginPolicy

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var statusText: TextView
    private lateinit var discoverButton: Button
    private lateinit var reloadButton: Button
    private lateinit var scanButton: Button
    private lateinit var openExternalButton: Button

    private lateinit var sessionStore: SessionStore
    private lateinit var discoveryManager: PhantomDiscoveryManager

    private var trustedBaseUrl: String? = null
    private var currentPageUrl: String? = null
    private var pendingInjectedScan: String? = null
    private var pendingWebPermissionRequest: PermissionRequest? = null
    private var launchScannerAfterPermission = false
    private var lastProgress: Int = 0
    private var lastLoadAttemptUrl: String? = null
    private var currentLoadAttempt = 0

    private val mainHandler = Handler(Looper.getMainLooper())
    private val maxAutoRetries = 2
    private val loadStuckTimeoutMs = 6500L

    private val loadWatchdog = Runnable {
        if (lastProgress in 1..20) {
            statusText.text = "Carga lenta (${lastProgress}%). Reintentando..."
            retryCurrentLoad("timeout de carga")
        }
    }

    private val cameraPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        val pendingRequest = pendingWebPermissionRequest
        pendingWebPermissionRequest = null

        if (granted) {
            pendingRequest?.grant(arrayOf(PermissionRequest.RESOURCE_VIDEO_CAPTURE))
            if (launchScannerAfterPermission) {
                startNativeQrScanner()
            }
        } else {
            pendingRequest?.deny()
            statusText.text = "Permiso de cámara denegado"
            if (launchScannerAfterPermission) {
                toast("Se requiere permiso de cámara para escanear códigos")
            }
        }

        launchScannerAfterPermission = false
    }

    private val nativeScannerLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        val decodedValue = result.data
            ?.getStringExtra(NativeQrScannerActivity.EXTRA_SCAN_RESULT)
            ?.trim()

        if (result.resultCode != RESULT_OK || decodedValue.isNullOrBlank()) {
            statusText.text = "Escaneo cancelado"
            return@registerForActivityResult
        }

        statusText.text = "Código leído. Enviando al panel..."
        injectScanIntoWeb(decodedValue)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        webView = findViewById(R.id.webView)
        statusText = findViewById(R.id.statusText)
        discoverButton = findViewById(R.id.discoverButton)
        reloadButton = findViewById(R.id.reloadButton)
        scanButton = findViewById(R.id.scanButton)
        openExternalButton = findViewById(R.id.openExternalButton)

        sessionStore = SessionStore(this)
        discoveryManager = PhantomDiscoveryManager(this)

        configureWebView()
        bindActions()
        configureBackNavigation()

        val cached = sessionStore.getServerUrl()
        if (!cached.isNullOrBlank()) {
            loadServer(cached, "Servidor guardado")
        } else {
            discoverAndLoad()
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun configureWebView() {
        with(webView.settings) {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            allowFileAccess = false
            allowContentAccess = false
            cacheMode = WebSettings.LOAD_DEFAULT
            javaScriptCanOpenWindowsAutomatically = false
            setSupportMultipleWindows(false)
            loadsImagesAutomatically = true
            useWideViewPort = true
            loadWithOverviewMode = true
            mediaPlaybackRequiresUserGesture = false
            mixedContentMode = WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE
        }

        webView.setInitialScale(1)

        webView.addJavascriptInterface(
            PhantomJavascriptBridge {
                runOnUiThread { requestNativeQrScan() }
            },
            "PhantomAndroid"
        )

        webView.webChromeClient = PhantomWebChromeClient(
            activity = this,
            trustedBaseUrlProvider = { trustedBaseUrl },
            currentPageUrlProvider = { currentPageUrl },
            onCameraPermissionRequired = { request ->
                pendingWebPermissionRequest?.deny()
                pendingWebPermissionRequest = request
                ensureCameraPermissionForWebView()
            },
            onProgressChanged = { progress ->
                lastProgress = progress
                if (progress in 1..99) {
                    val host = runCatching { Uri.parse(lastLoadAttemptUrl).host ?: "-" }.getOrDefault("-")
                    statusText.text = "Cargando servidor (${host})... ${progress}%"
                } else if (progress >= 100) {
                    cancelLoadWatchdog()
                }
            }
        )

        webView.webViewClient = PhantomWebViewClient(
            trustedBaseUrlProvider = { trustedBaseUrl },
            onPageReady = { url ->
                currentPageUrl = url
                cancelLoadWatchdog()
                currentLoadAttempt = 0
                statusText.text = "Servidor conectado: $url"
                flushPendingScanIfPossible()
            },
            onNavigationBlocked = { url -> openExternalUrl(url) },
            onPageError = { message ->
                statusText.text = message
                retryCurrentLoad("error principal")
            }
        )
    }

    private fun bindActions() {
        discoverButton.setOnClickListener { discoverAndLoad() }
        reloadButton.setOnClickListener {
            currentLoadAttempt = 0
            val url = trustedBaseUrl ?: lastLoadAttemptUrl
            if (!url.isNullOrBlank()) {
                startLoad(url, "Recargando")
            } else {
                discoverAndLoad()
            }
        }
        scanButton.setOnClickListener { requestNativeQrScan() }
        openExternalButton.setOnClickListener {
            val url = trustedBaseUrl ?: currentPageUrl ?: lastLoadAttemptUrl
            if (url.isNullOrBlank()) {
                toast("No hay URL de servidor para abrir")
                return@setOnClickListener
            }
            openExternalUrl(url)
        }
    }

    private fun configureBackNavigation() {
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (webView.canGoBack()) {
                    webView.goBack()
                    return
                }
                isEnabled = false
                onBackPressedDispatcher.onBackPressed()
            }
        })
    }

    private fun discoverAndLoad() {
        discoverButton.isEnabled = false
        statusText.text = "Buscando servidor LAN..."

        val previous = sessionStore.getServerUrl()
        discoveryManager.discover(
            previousUrl = previous,
            onComplete = { result ->
                runOnUiThread {
                    discoverButton.isEnabled = true
                    val selected = result.selected
                    if (selected == null) {
                        statusText.text = "No se encontró servidor disponible"
                        return@runOnUiThread
                    }
                    sessionStore.saveServerUrl(selected.baseUrl)
                    loadServer(selected.baseUrl, "Servidor ${selected.source} (${selected.latencyMs}ms)")
                }
            },
            onFailure = { message ->
                runOnUiThread {
                    discoverButton.isEnabled = true
                    statusText.text = message
                }
            }
        )
    }

    private fun loadServer(baseUrl: String, message: String) {
        val normalizedBaseUrl = TrustedOriginPolicy.normalizeBaseUrl(baseUrl)
        if (normalizedBaseUrl == null) {
            statusText.text = "URL de servidor inválida"
            return
        }

        trustedBaseUrl = normalizedBaseUrl
        currentPageUrl = null
        pendingWebPermissionRequest?.deny()
        pendingWebPermissionRequest = null

        startLoad(normalizedBaseUrl, message)
    }

    private fun startLoad(url: String, message: String) {
        cancelLoadWatchdog()
        lastLoadAttemptUrl = url
        lastProgress = 0
        statusText.text = "$message: $url"
        webView.stopLoading()
        webView.loadUrl(url)
        scheduleLoadWatchdog()
    }

    private fun retryCurrentLoad(reason: String) {
        val url = lastLoadAttemptUrl ?: trustedBaseUrl ?: return
        if (currentLoadAttempt >= maxAutoRetries) {
            statusText.text = "No se pudo cargar en la app. Usa 'Abrir externo'."
            return
        }
        currentLoadAttempt += 1
        startLoad(url, "Reintento ${currentLoadAttempt}/${maxAutoRetries} ($reason)")
    }

    private fun scheduleLoadWatchdog() {
        mainHandler.removeCallbacks(loadWatchdog)
        mainHandler.postDelayed(loadWatchdog, loadStuckTimeoutMs)
    }

    private fun cancelLoadWatchdog() {
        mainHandler.removeCallbacks(loadWatchdog)
    }

    private fun requestNativeQrScan() {
        if (!packageManager.hasSystemFeature(PackageManager.FEATURE_CAMERA_ANY)) {
            toast("Este dispositivo no reporta una cámara disponible")
            return
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
            startNativeQrScanner()
            return
        }

        launchScannerAfterPermission = true
        cameraPermissionLauncher.launch(Manifest.permission.CAMERA)
    }

    private fun ensureCameraPermissionForWebView() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
            pendingWebPermissionRequest?.grant(arrayOf(PermissionRequest.RESOURCE_VIDEO_CAPTURE))
            pendingWebPermissionRequest = null
            return
        }
        cameraPermissionLauncher.launch(Manifest.permission.CAMERA)
    }

    private fun startNativeQrScanner() {
        val intent = Intent(this, NativeQrScannerActivity::class.java)
        nativeScannerLauncher.launch(intent)
    }

    private fun injectScanIntoWeb(decodedValue: String) {
        pendingInjectedScan = decodedValue
        flushPendingScanIfPossible()
    }

    private fun flushPendingScanIfPossible() {
        val decodedValue = pendingInjectedScan ?: return
        if (!TrustedOriginPolicy.isTrustedNavigation(currentPageUrl, trustedBaseUrl)) {
            return
        }

        pendingInjectedScan = null
        val script = QrInjectionScriptBuilder.build(decodedValue)
        webView.evaluateJavascript(script, null)
    }

    private fun openExternalUrl(url: String) {
        try {
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
            toast("Enlace externo abierto en el navegador")
        } catch (_: ActivityNotFoundException) {
            toast("No se pudo abrir el enlace externo")
        }
    }

    private fun toast(message: String) {
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show()
    }

    override fun onDestroy() {
        cancelLoadWatchdog()
        pendingWebPermissionRequest?.deny()
        pendingWebPermissionRequest = null
        webView.removeJavascriptInterface("PhantomAndroid")
        webView.destroy()
        super.onDestroy()
    }
}
