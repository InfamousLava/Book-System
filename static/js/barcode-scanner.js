/**
 * Barcode Scanner using html5-qrcode
 * With manual entry fallback
 */

let onScanCallback = null;
let html5QrCode = null;

function openBarcodeScanner(callback) {
    onScanCallback = callback;

    // Load html5-qrcode if needed
    if (typeof Html5Qrcode === 'undefined') {
        const script = document.createElement('script');
        script.src = '/html5-qrcode/html5-qrcode.min.js';
        script.onload = createModal;
        script.onerror = () => {
            const code = prompt('Scanner failed to load.\n\nEnter barcode manually:');
            if (code && callback) callback(code.trim());
        };
        document.head.appendChild(script);
    } else {
        createModal();
    }
}

function createModal() {
    const existing = document.getElementById('scannerModal');
    if (existing) existing.remove();

    const modal = document.createElement('div');
    modal.id = 'scannerModal';
    modal.innerHTML = `
        <div style="position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.9);z-index:9999;display:flex;align-items:center;justify-content:center;">
            <div style="background:#1a1a2e;padding:1.5rem;border-radius:16px;width:95%;max-width:500px;color:white;">
                <div style="display:flex;justify-content:space-between;margin-bottom:1rem;">
                    <h3 style="margin:0;">📷 Scan Barcode</h3>
                    <button onclick="closeBarcodeScanner()" style="background:none;border:none;color:#888;font-size:1.5rem;cursor:pointer;">×</button>
                </div>
                
                <select id="cameraSelect" style="width:100%;padding:0.75rem;margin-bottom:1rem;border:1px solid #333;border-radius:8px;background:#0f0f1a;color:white;">
                    <option>Loading cameras...</option>
                </select>
                
                <div id="reader" style="width:100%;border-radius:8px;overflow:hidden;"></div>
                
                <div id="scanStatus" style="margin:1rem 0;color:#f59e0b;">Starting camera...</div>
                
                <div style="border-top:1px solid #333;padding-top:1rem;margin-top:1rem;">
                    <div style="display:flex;gap:0.5rem;">
                        <input type="text" id="manualCode" placeholder="Or enter barcode manually..." style="flex:1;padding:0.75rem;border:1px solid #333;border-radius:8px;background:#0f0f1a;color:white;">
                        <button onclick="submitManual()" style="padding:0.75rem 1rem;background:#10b981;color:white;border:none;border-radius:8px;cursor:pointer;">OK</button>
                    </div>
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(modal);

    loadCameras();
}

async function loadCameras() {
    const select = document.getElementById('cameraSelect');
    const status = document.getElementById('scanStatus');

    try {
        const devices = await Html5Qrcode.getCameras();

        if (devices && devices.length > 0) {
            select.innerHTML = devices.map(d =>
                `<option value="${d.id}">${d.label || 'Camera'}</option>`
            ).join('');

            // Prefer back camera
            const back = devices.find(d => d.label.toLowerCase().includes('back'));
            if (back) select.value = back.id;

            select.onchange = () => startScanner(select.value);
            startScanner(select.value);
        } else {
            select.innerHTML = '<option>No cameras found</option>';
            status.textContent = '❌ No cameras found';
            status.style.color = '#ef4444';
        }
    } catch (err) {
        status.textContent = '❌ ' + err.message;
        status.style.color = '#ef4444';
    }
}

async function startScanner(cameraId) {
    const status = document.getElementById('scanStatus');

    // Stop existing
    if (html5QrCode) {
        try { await html5QrCode.stop(); } catch (e) { }
    }

    // Configure for 1D barcodes (Books/Products)
    const formats = [
        Html5QrcodeSupportedFormats.EAN_13,
        Html5QrcodeSupportedFormats.EAN_8,
        Html5QrcodeSupportedFormats.UPC_A,
        Html5QrcodeSupportedFormats.UPC_E,
        Html5QrcodeSupportedFormats.CODE_128,
        Html5QrcodeSupportedFormats.CODE_39
    ];

    html5QrCode = new Html5Qrcode("reader", {
        formatsToSupport: formats,
        experimentalFeatures: { useBarCodeDetectorIfSupported: true }
    });

    try {
        await html5QrCode.start(
            cameraId,
            {
                fps: 25,
                qrbox: (viewfinderWidth, viewfinderHeight) => {
                    // Maximum width, but leave small margin
                    const minEdgePercentage = 0.85; // 85% width
                    const minDim = Math.min(viewfinderWidth, viewfinderHeight);
                    const width = Math.floor(viewfinderWidth * minEdgePercentage);
                    // Taller height based on user request
                    return { width: width, height: Math.floor(width * 0.75) };
                },
                // Re-removing aspectRatio to be safe.
                // NOTE: Using a function for qrbox is supported in newer versions.
            },
            (code) => foundCode(code),
            (err) => { } // Ignore errors
        );
        status.textContent = '✅ Scanning...';
        status.style.color = '#10b981';
    } catch (err) {
        status.textContent = '❌ ' + err.message;
        status.style.color = '#ef4444';
    }
}

function foundCode(code) {
    // Vibrate
    if (navigator.vibrate) navigator.vibrate(100);

    // Update status
    const status = document.getElementById('scanStatus');
    if (status) {
        status.textContent = '✅ Found: ' + code;
        status.style.color = '#10b981';
    }

    // Save callback and close
    const cb = onScanCallback;
    closeBarcodeScanner();
    if (cb) cb(code);
}

function submitManual() {
    const input = document.getElementById('manualCode');
    const code = input?.value?.trim();
    if (code) foundCode(code);
}

async function closeBarcodeScanner() {
    if (html5QrCode) {
        try { await html5QrCode.stop(); } catch (e) { }
        html5QrCode = null;
    }
    document.getElementById('scannerModal')?.remove();
    onScanCallback = null;
}

window.openBarcodeScanner = openBarcodeScanner;
window.closeBarcodeScanner = closeBarcodeScanner;
window.submitManual = submitManual;
