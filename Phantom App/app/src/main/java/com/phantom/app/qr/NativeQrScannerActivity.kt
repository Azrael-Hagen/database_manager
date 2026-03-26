package com.phantom.app.qr

import android.os.Bundle
import android.util.Size
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import com.phantom.app.R
import com.google.mlkit.vision.barcode.BarcodeScannerOptions
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

class NativeQrScannerActivity : AppCompatActivity() {

    private lateinit var previewView: PreviewView
    private lateinit var scannerStatus: TextView
    private lateinit var cancelButton: Button

    private val cameraExecutor: ExecutorService = Executors.newSingleThreadExecutor()
    private val hasDeliveredResult = AtomicBoolean(false)

    private val barcodeScanner by lazy {
        val options = BarcodeScannerOptions.Builder()
            .setBarcodeFormats(
                Barcode.FORMAT_QR_CODE,
                Barcode.FORMAT_CODE_128,
                Barcode.FORMAT_CODE_39,
                Barcode.FORMAT_EAN_13,
                Barcode.FORMAT_EAN_8,
                Barcode.FORMAT_UPC_A,
                Barcode.FORMAT_UPC_E,
            )
            .build()
        BarcodeScanning.getClient(options)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_native_qr_scanner)

        previewView = findViewById(R.id.previewView)
        scannerStatus = findViewById(R.id.scannerStatus)
        cancelButton = findViewById(R.id.cancelScanButton)

        cancelButton.setOnClickListener {
            setResult(RESULT_CANCELED)
            finish()
        }
    }

    override fun onStart() {
        super.onStart()
        startCamera()
    }

    private fun startCamera() {
        val cameraProviderFuture = ProcessCameraProvider.getInstance(this)
        cameraProviderFuture.addListener({
            val cameraProvider = cameraProviderFuture.get()

            val preview = Preview.Builder().build().also {
                it.surfaceProvider = previewView.surfaceProvider
            }

            val analysis = ImageAnalysis.Builder()
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .setTargetResolution(Size(1280, 720))
                .build()
                .also {
                    it.setAnalyzer(
                        cameraExecutor,
                        MlKitBarcodeAnalyzer(
                            barcodeScanner = barcodeScanner,
                            hasDeliveredResult = hasDeliveredResult,
                            onCodeDetected = { rawValue ->
                                runOnUiThread { deliverResult(rawValue) }
                            },
                        )
                    )
                }

            val selector = CameraSelector.DEFAULT_BACK_CAMERA

            cameraProvider.unbindAll()
            cameraProvider.bindToLifecycle(this, selector, preview, analysis)
            scannerStatus.text = "Apunta la cámara hacia el código"
        }, ContextCompat.getMainExecutor(this))
    }

    private fun deliverResult(rawValue: String) {
        if (!hasDeliveredResult.compareAndSet(false, true)) {
            return
        }
        val intent = intent.apply {
            putExtra(EXTRA_SCAN_RESULT, rawValue)
        }
        setResult(RESULT_OK, intent)
        finish()
    }

    override fun onDestroy() {
        barcodeScanner.close()
        cameraExecutor.shutdown()
        super.onDestroy()
    }

    companion object {
        const val EXTRA_SCAN_RESULT = "scan_result"
    }
}