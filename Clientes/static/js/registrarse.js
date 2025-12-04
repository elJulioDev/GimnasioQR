// --- Utils ---
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
const csrftoken = getCookie('csrftoken');

// --- Modal Logic ---
function showCustomModal(title, message, type = 'error') {
    const modal = document.getElementById('customModal');
    const iconBox = document.getElementById('modalIcon');
    const icon = iconBox.querySelector('i');
    
    document.getElementById('modalTitle').textContent = title;
    document.getElementById('modalMessage').textContent = message;
    
    iconBox.className = 'modal-icon-box ' + type;
    if (type === 'success') {
        icon.className = 'fas fa-check';
    } else {
        icon.className = 'fas fa-exclamation-triangle';
    }
    
    modal.style.display = 'flex';
}

function closeCustomModal() {
    document.getElementById('customModal').style.display = 'none';
}

// --- Step Logic ---
let currentStep = 1;
let selectedPlanData = null;

function nextStep() {
    if (validateStep(currentStep)) {
        document.getElementById(`step${currentStep}`).classList.remove('active');
        document.querySelector(`.step-item[data-step="${currentStep}"]`).classList.remove('active');
        document.querySelector(`.step-item[data-step="${currentStep}"]`).classList.add('completed');
        
        currentStep++;
        
        document.getElementById(`step${currentStep}`).classList.add('active');
        document.querySelector(`.step-item[data-step="${currentStep}"]`).classList.add('active');
    }
}

function prevStep() {
    document.getElementById(`step${currentStep}`).classList.remove('active');
    document.querySelector(`.step-item[data-step="${currentStep}"]`).classList.remove('active');
    
    currentStep--;
    
    document.getElementById(`step${currentStep}`).classList.add('active');
    document.querySelector(`.step-item[data-step="${currentStep}"]`).classList.add('active');
    document.querySelector(`.step-item[data-step="${currentStep}"]`).classList.remove('completed');
}

function selectPlan(radio) {
    selectedPlanData = {
        type: radio.value,
        price: radio.dataset.price,
        name: radio.dataset.name
    };
    document.getElementById('summaryPlanName').textContent = selectedPlanData.name;
    document.getElementById('summaryPlanPrice').textContent = '$' + parseInt(selectedPlanData.price).toLocaleString('es-CL');
    document.getElementById('btnStep1').disabled = false;
}

function enablePayment() {
    document.getElementById('btnPayment').disabled = false;
}

function validateStep(step) {
    if (step === 1 && !selectedPlanData) {
        showCustomModal('Atención', 'Por favor selecciona un plan para continuar.', 'error');
        return false;
    }
    if (step === 2) {
        const required = ['rut', 'firstName', 'lastName', 'email', 'phone', 'password', 'confirmPassword', 'birthdate'];
        for (let id of required) {
            if (!document.getElementById(id).value) {
                showCustomModal('Campos Incompletos', 'Por favor completa todos los campos del formulario.', 'error');
                return false;
            }
        }
        if (document.getElementById('password').value !== document.getElementById('confirmPassword').value) {
            showCustomModal('Contraseña', 'Las contraseñas no coinciden.', 'error');
            return false;
        }
        if (document.getElementById('password').value.length < 8) {
            showCustomModal('Seguridad', 'La contraseña debe tener al menos 8 caracteres.', 'error');
            return false;
        }
    }
    return true;
}

// --- Registration Logic ---
async function processPayment() {
    const btn = document.getElementById('btnPayment');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Procesando...';

    const formData = {
        rut: document.getElementById('rut').value,
        firstName: document.getElementById('firstName').value,
        lastName: document.getElementById('lastName').value,
        email: document.getElementById('email').value,
        phone: document.getElementById('phone').value,
        birthdate: document.getElementById('birthdate').value,
        password: document.getElementById('password').value,
        plan: selectedPlanData.type,
        paymentMethod: document.querySelector('input[name="paymentMethod"]:checked').value,
        sendQREmail: document.getElementById('sendQREmail').checked,
        sendContract: document.getElementById('sendContract').checked
    };

    try {
        const registerForm = document.getElementById('registerForm');
        const urlRegistro = registerForm.getAttribute('data-url-registro');

        const response = await fetch(urlRegistro, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrftoken
            },
            body: JSON.stringify(formData)
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: 'Error del servidor desconocido' }));
            throw new Error(errorData.error || 'Error en la solicitud');
        }

        const data = await response.json();

        if (data.success) {
            // CAMBIO AQUÍ: Usamos qr_code_b64 en lugar de qr_code_url
            if (data.qr_code_b64) {
                // Como ya viene con el prefijo "data:image/png;base64,...", lo ponemos directo en el src
                document.getElementById('qrContainer').innerHTML = `<img src="${data.qr_code_b64}" alt="QR Code">`;
            }
            nextStep(); // Ir al paso 4
        } else {
            showCustomModal('Error de Registro', data.error, 'error');
            resetButton();
        }

    } catch (error) {
        console.error("Registration Error:", error);
        if(currentStep !== 4) {
            showCustomModal('Error', error.message || 'Ocurrió un problema de conexión.', 'error');
            resetButton();
        }
    }
}

function resetButton() {
    const btn = document.getElementById('btnPayment');
    btn.disabled = false;
    btn.textContent = 'Confirmar y Registrarse';
}

function goToLogin() {
    const registerForm = document.getElementById('registerForm');
    const urlLogin = registerForm.getAttribute('data-url-login');
    window.location.href = urlLogin;
}