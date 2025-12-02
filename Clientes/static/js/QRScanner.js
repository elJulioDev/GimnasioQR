let html5QrCode = null;
let isScanning = false;
let debugMode = false;
let scanAttempts = 0;

// Función para agregar logs de debug
function addDebugLog(message, type = 'info') {
    if (!debugMode) return;
    
    const logContainer = document.getElementById('debugLog');
    const entry = document.createElement('div');
    entry.className = `debug-log-entry ${type}`;
    entry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
    logContainer.appendChild(entry);
    logContainer.scrollTop = logContainer.scrollHeight;
    console.log(message);
}

// Toggle debug
function toggleDebug() {
    debugMode = !debugMode;
    document.getElementById('debugLog').classList.toggle('show', debugMode);
    addDebugLog(`Modo debug ${debugMode ? 'ACTIVADO' : 'DESACTIVADO'}`, 'success');
}

// Cerrar con ESC
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && confirm('¿Cerrar escáner?')) {
        if (html5QrCode && isScanning) {
            html5QrCode.stop();
        }
        window.close();
    }
});

// Iniciar escáner automáticamente
window.addEventListener('DOMContentLoaded', () => {
    addDebugLog('Página cargada, iniciando escáner...');
    initScanner();
});

async function initScanner() {
    try {
        addDebugLog('Solicitando permisos de cámara...');
        
        html5QrCode = new Html5Qrcode("qr-reader");
        addDebugLog('Html5Qrcode inicializado');
        
        const config = { 
            fps: 30,
            qrbox: { width: 250, height: 250 },
            aspectRatio: 1.0
        };

        await html5QrCode.start(
            { facingMode: "environment" },
            config,
            onScanSuccess,
            onScanError
        );

        isScanning = true;
        addDebugLog('✓ Escáner iniciado (30 FPS)', 'success');

    } catch (err) {
        addDebugLog(`ERROR: ${err.message || err}`, 'error');
        console.error("Error completo:", err);
        alert(`Error al iniciar el escáner: ${err.message || 'Error desconocido'}\n\nAsegúrate de:\n1. Permitir acceso a la cámara\n2. Usar HTTPS o localhost`);
    }
}

function onScanSuccess(decodedText, decodedResult) {
    if (!isScanning) return;
    
    addDebugLog(`✓ QR DETECTADO: ${decodedText}`, 'success');
    isScanning = false;
    
    html5QrCode.pause(true);
    addDebugLog('Escáner pausado');
    
    processQR(decodedText);
}

function onScanError(errorMessage) {
    scanAttempts++;
    if (debugMode && scanAttempts % 100 === 0) {
        addDebugLog(`${scanAttempts} intentos...`);
    }
}

function processQR(qrData) {
    addDebugLog(`Procesando QR: ${qrData}`);

    // ✅ CONEXIÓN REAL CON DJANGO
    fetch('/api/process-qr-scan/', {
        method: 'POST',
        headers: { 
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({ qr_data: qrData })
    })
    .then(response => {
        addDebugLog(`✓ Respuesta HTTP ${response.status}`, response.ok ? 'success' : 'error');
        
        // ✅ IMPORTANTE: Manejar 403 (Ya ingresó hoy) como respuesta válida
        if (response.status === 403 || response.ok) {
            return response.json();
        }
        
        // Para otros errores (404, 500, etc.)
        throw new Error(`HTTP ${response.status}`);
    })
    .then(data => {
        addDebugLog('✓ JSON parseado correctamente', 'success');
        
        if (data.success && data.status === 'allowed') {
            // ✅ ACCESO PERMITIDO - Primera entrada del día
            addDebugLog('✓ ACCESO PERMITIDO', 'success');
            showResult({
                allowed: true,
                name: data.user.name,
                rut: data.user.rut,
                plan: data.user.membership_plan,
                expiry: formatDate(data.user.membership_end),
                time: data.user.access_time,
                days_remaining: data.user.days_remaining,
                weekly_access: data.user.weekly_access,
                monthly_access: data.user.monthly_access,
                already_accessed: false
            });
        } else if (data.already_accessed_today === true) {
            // ⚠️ YA INGRESÓ HOY - Mostrar como advertencia, NO como error
            addDebugLog('⚠️  YA INGRESÓ HOY', 'error');
            showResult({
                allowed: false,
                alreadyAccessedToday: true,  // Flag especial
                name: data.user.name,
                rut: data.user.rut,
                plan: data.user.membership_plan,
                expiry: formatDate(data.user.membership_end),
                time: data.user.first_access_today || data.user.access_time,
                error: data.error,
                weekly_access: data.user.weekly_access,
                monthly_access: data.user.monthly_access
            });
        } else {
            // ❌ ACCESO DENEGADO - Membresía vencida u otro error
            addDebugLog('✗ ACCESO DENEGADO', 'error');
            showResult({
                allowed: false,
                name: data.user?.name || 'Usuario desconocido',
                rut: data.user?.rut || 'N/A',
                plan: data.user?.membership_plan || 'Sin plan activo',
                expiry: 'VENCIDO',
                time: new Date().toLocaleTimeString('es-CL'),
                error: data.error
            });
        }
    })
    .catch(error => {
        addDebugLog(`✗ Error: ${error.message}`, 'error');
        console.error('Error completo:', error);
        
        // Mostrar error en pantalla
        showResult({
            allowed: false,
            name: 'Error de conexión',
            rut: 'N/A',
            plan: 'Error',
            expiry: 'Error al procesar',
            time: new Date().toLocaleTimeString('es-CL'),
            error: 'No se pudo conectar con el servidor'
        });
        
        // Reintentar automáticamente en 3 segundos
        setTimeout(() => {
            resumeScanner();
        }, 3000);
    });
}

function formatDate(dateString) {
    try {
        const date = new Date(dateString);
        return date.toLocaleDateString('es-CL');
    } catch {
        return dateString;
    }
}
function showResult(data) {
    document.getElementById('mainContainer').classList.add('result-active');

    const card = document.getElementById('resultCard');
    const icon = document.getElementById('resultIcon');
    const status = document.getElementById('resultStatus');

    card.classList.remove('success', 'denied', 'warning');
    icon.classList.remove('success', 'denied', 'warning');
    status.classList.remove('allowed', 'denied', 'warning');

    if (data.allowed) {
        // ✅ ACCESO PERMITIDO
        card.classList.add('success');
        icon.classList.add('success');
        icon.innerHTML = '<i class="fas fa-check-circle"></i>';
        status.classList.add('allowed');
        status.innerHTML = '<i class="fas fa-check-circle"></i><span>ACCESO PERMITIDO</span>';
        status.innerHTML += '<br><small style="font-size: 0.8em;">¡Bienvenido al gimnasio!</small>';
    
    } else if (data.alreadyAccessedToday) {
        // ⚠️ YA INGRESÓ HOY - Estilo de advertencia (naranja/amarillo)
        card.classList.add('warning');
        icon.classList.add('warning');
        icon.innerHTML = '<i class="fas fa-info-circle"></i>';
        status.classList.add('warning');
        status.innerHTML = '<i class="fas fa-info-circle"></i><span>YA INGRESASTE HOY</span>';
        status.innerHTML += `<br><small style="font-size: 0.8em;">Primera entrada: ${data.time}</small>`;
    
    } else {
        // ❌ ACCESO DENEGADO
        card.classList.add('denied');
        icon.classList.add('denied');
        icon.innerHTML = '<i class="fas fa-times-circle"></i>';
        status.classList.add('denied');
        status.innerHTML = '<i class="fas fa-times-circle"></i><span>ACCESO DENEGADO</span>';
    
        if (data.error) {
            status.innerHTML += `<br><small style="font-size: 0.8em;">${data.error}</small>`;
        }
    }

    document.getElementById('resultName').textContent = data.name;
    document.getElementById('resultRut').textContent = data.rut;
    document.getElementById('resultPlan').textContent = data.plan;
    document.getElementById('resultExpiry').textContent = data.expiry;
    document.getElementById('resultTime').textContent = data.time;

    card.classList.add('show');

    addDebugLog('Mostrando resultado en pantalla');
    startCountdown();
}


function startCountdown() {
    let seconds = 5;
    const el = document.getElementById('countdownValue');

    const timer = setInterval(() => {
        seconds--;
        el.textContent = seconds;

        if (seconds <= 0) {
            clearInterval(timer);
            addDebugLog('Reiniciando escáner...');
            resumeScanner();
        }
    }, 1000);
}

function resumeScanner() {
    addDebugLog('Resumiendo escáner...');
    
    document.getElementById('resultCard').classList.remove('show');
    document.getElementById('mainContainer').classList.remove('result-active');
    scanAttempts = 0;

    if (html5QrCode) {
        html5QrCode.resume();
        isScanning = true;
        addDebugLog('✓ Escáner reanudado', 'success');
    }
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}