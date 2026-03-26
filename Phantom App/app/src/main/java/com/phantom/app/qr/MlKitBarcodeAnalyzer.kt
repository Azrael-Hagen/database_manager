package com.phantom.app.qr

import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import com.google.mlkit.vision.barcode.BarcodeScanner
import com.google.mlkit.vision.common.InputImage
import java.util.concurrent.atomic.AtomicBoolean

class MlKitBarcodeAnalyzer(
    private val barcodeScanner: BarcodeScanner,
    private val hasDeliveredResult: AtomicBoolean,
    private val onCodeDetected: (String) -> Unit,
) : ImageAnalysis.Analyzer {

    private val isProcessingFrame = AtomicBoolean(false)

    override fun analyze(imageProxy: ImageProxy) {
        if (hasDeliveredResult.get()) {
            imageProxy.close()
            return
        }
        if (!isProcessingFrame.compareAndSet(false, true)) {
            imageProxy.close()
            return
        }

        val mediaImage = imageProxy.image
        if (mediaImage == null) {
            isProcessingFrame.set(false)
            imageProxy.close()
            return
        }

        val inputImage = InputImage.fromMediaImage(mediaImage, imageProxy.imageInfo.rotationDegrees)
        barcodeScanner.process(inputImage)
            .addOnSuccessListener { barcodes ->
                val rawValue = barcodes.firstNotNullOfOrNull { it.rawValue?.trim()?.takeIf(String::isNotEmpty) }
                if (rawValue != null && !hasDeliveredResult.get()) {
                    onCodeDetected(rawValue)
                }
            }
            .addOnCompleteListener {
                isProcessingFrame.set(false)
                imageProxy.close()
            }
    }
}