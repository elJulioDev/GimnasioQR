
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

document.addEventListener('DOMContentLoaded', function() {
    const navLinks = document.querySelectorAll('.nav-link');
    const sections = document.querySelectorAll('.content-section');
    navLinks.forEach(link => {
        if(link.getAttribute('data-target')) {
            link.addEventListener('click', function(e) {
                e.preventDefault();
                const targetId = this.getAttribute('data-target');
                navLinks.forEach(nav => nav.classList.remove('active'));
                sections.forEach(sec => sec.classList.remove('active'));
                this.classList.add('active');
                document.getElementById(targetId).classList.add('active');
                document.querySelector('.main-content').scrollTo({ top: 0, behavior: 'smooth' });
            });
        }
    });
});

function navigateTo(sectionId) {
    event.preventDefault();
    const targetSection = document.getElementById(sectionId);
    const targetLink = document.querySelector(`[data-target="${sectionId}"]`);
    if (targetSection && targetLink) {
        document.querySelectorAll('.nav-link').forEach(nav => nav.classList.remove('active'));
        document.querySelectorAll('.content-section').forEach(sec => sec.classList.remove('active'));
        targetLink.classList.add('active');
        targetSection.classList.add('active');
        document.querySelector('.main-content').scrollTo({ top: 0, behavior: 'smooth' });
    }
}

// --- Lógica del Modal de Cancelación ---
function openCancelModal() {
    const modal = document.getElementById('cancelModal');
    modal.style.display = 'flex';
    modal.querySelector('.modal-warning-content').style.animation = 'popIn 0.3s ease';
}

function closeCancelModal() {
    document.getElementById('cancelModal').style.display = 'none';
}

async function confirmCancelPlan() {
    const btn = document.querySelector('#cancelModal button[style*="background: #ff4757"]');
    const originalText = btn.innerText;
    btn.disabled = true;
    btn.innerText = "Procesando...";

    try {
        const response = await fetch('/api/cancelar-plan/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            }
        });

        const data = await response.json();

        if (data.success) {
            closeCancelModal();
            location.reload(); 
        } else {
            alert("Error: " + data.error);
            btn.disabled = false;
            btn.innerText = originalText;
        }
    } catch (error) {
        console.error(error);
        alert("Error de conexión al intentar cancelar el plan.");
        btn.disabled = false;
        btn.innerText = originalText;
    }
}

// --- Lógica de Renovación ---
function selectPlanForRenewal(planName, price, planId) {
    document.getElementById('modalPlanName').textContent = planName;
    document.getElementById('modalPlanPrice').textContent = '$' + price.toLocaleString('es-CL');
    document.getElementById('modalPlanId').value = planId;
    document.getElementById('paymentMethod').value = "";
    document.getElementById('checkQR').checked = false;
    document.getElementById('checkContract').checked = true;
    const modal = document.getElementById('renewalModal');
    modal.style.display = 'flex';
}

function closeRenewalModal() {
    document.getElementById('renewalModal').style.display = 'none';
}

async function handleRenewalSubmit(e) {
    e.preventDefault();
    const planId = document.getElementById('modalPlanId').value;
    const paymentMethod = document.getElementById('paymentMethod').value;
    const sendQr = document.getElementById('checkQR').checked;
    const sendContract = document.getElementById('checkContract').checked;
    
    const btn = document.getElementById('btnConfirmRenewal');
    const btnText = btn.querySelector('.btn-text');
    const loader = btn.querySelector('.loader-spinner');

    btn.disabled = true;
    if(btnText) btnText.style.display = 'none';
    if(loader) loader.style.display = 'block';

    try {
        const response = await fetch('/api/renovar-plan/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
            body: JSON.stringify({
                plan_id: planId,
                payment_method: paymentMethod,
                send_qr: sendQr,
                send_contract: sendContract,
                notes: "Renovación automática desde panel socio"
            })
        });

        const data = await response.json();

        if (data.success) {
            alert("¡Plan renovado con éxito!");
            location.reload();
        } else {
            alert("Error: " + data.error);
            btn.disabled = false;
            if(btnText) btnText.style.display = 'block';
            if(loader) loader.style.display = 'none';
        }
    } catch (error) {
        console.error(error);
        alert("Error de conexión.");
        btn.disabled = false;
        if(btnText) btnText.style.display = 'block';
        if(loader) loader.style.display = 'none';
    }
}

// --- Lógica Cambio Contraseña ---
function openPasswordModal() {
    const modal = document.getElementById('passwordModal');
    document.getElementById('formStep1').reset();
    document.getElementById('formStep2').reset();
    document.getElementById('step1-error').style.display = 'none';
    document.getElementById('step2-error').style.display = 'none';
    document.getElementById('match-feedback').textContent = '';
    document.querySelectorAll('.modern-input').forEach(i => i.classList.remove('valid', 'invalid'));
    showStep(1);
    modal.style.display = 'flex';
}

function closePasswordModal() { document.getElementById('passwordModal').style.display = 'none'; }
function showStep(step) {
    document.querySelectorAll('.step-container').forEach(el => el.classList.remove('active'));
    document.getElementById(`step-${step}`).classList.add('active');
}

async function handleVerifyStep(e) {
    e.preventDefault();
    const passInput = document.getElementById('current_password_input');
    const currentPass = passInput.value;
    const errorDiv = document.getElementById('step1-error');
    const btn = document.getElementById('btn-verify');
    const btnText = btn.querySelector('.btn-text-content');
    const loader = btn.querySelector('.loader-spinner');

    if (!currentPass) return;
    btn.disabled = true; btnText.style.display = 'none'; loader.style.display = 'block'; errorDiv.style.display = 'none';

    try {
        const response = await fetch('/api/verify-password/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
            body: JSON.stringify({ password: currentPass })
        });
        const data = await response.json();
        if (data.valid) { showStep(2); } 
        else { errorDiv.textContent = data.error || "Contraseña incorrecta"; errorDiv.style.display = 'block'; passInput.classList.add('invalid'); }
    } catch (error) { errorDiv.textContent = "Error de conexión."; errorDiv.style.display = 'block'; } 
    finally { btn.disabled = false; btnText.style.display = 'block'; loader.style.display = 'none'; }
}

function validatePasswordsUI() {
    const p1 = document.getElementById('new_password_input');
    const p2 = document.getElementById('confirm_password_input');
    const feedback = document.getElementById('match-feedback');
    if (p1.value.length > 0 && p1.value.length < 8) p1.classList.add('invalid'); else p1.classList.remove('invalid');
    if (p2.value.length > 0) {
        if (p1.value === p2.value) { p2.classList.remove('invalid'); p2.classList.add('valid'); feedback.innerHTML = '<span class="text-match"><i class="fas fa-check"></i> Coinciden</span>'; } 
        else { p2.classList.remove('valid'); p2.classList.add('invalid'); feedback.innerHTML = '<span class="text-mismatch"><i class="fas fa-times"></i> No coinciden</span>'; }
    } else { feedback.innerHTML = ''; p2.classList.remove('valid', 'invalid'); }
}

async function handleSubmitNewPass(e) {
    e.preventDefault();
    const newPass = document.getElementById('new_password_input').value;
    const confirmPass = document.getElementById('confirm_password_input').value;
    const errorDiv = document.getElementById('step2-error');
    const btn = document.getElementById('btn-save-pass');
    const btnText = btn.querySelector('.btn-text-content');
    const loader = btn.querySelector('.loader-spinner');

    if (newPass.length < 8) { errorDiv.textContent = "La contraseña debe tener mínimo 8 caracteres."; errorDiv.style.display = 'block'; return; }
    if (newPass !== confirmPass) { errorDiv.textContent = "Las contraseñas no coinciden."; errorDiv.style.display = 'block'; return; }

    btn.disabled = true; btnText.style.display = 'none'; loader.style.display = 'block'; errorDiv.style.display = 'none';

    try {
        const response = await fetch('/api/change-password/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
            body: JSON.stringify({ new_password: newPass, confirm_password: confirmPass })
        });
        const data = await response.json();
        if (data.success) { showStep(3); } else { errorDiv.textContent = data.error || "Error al actualizar."; errorDiv.style.display = 'block'; }
    } catch (error) { errorDiv.textContent = "Error de conexión."; errorDiv.style.display = 'block'; } 
    finally { btn.disabled = false; btnText.style.display = 'block'; loader.style.display = 'none'; }
}

function shareQR() {
    if (navigator.share) { navigator.share({ title: 'Mi QR ClubHouse', text: 'Mi código QR de acceso al gimnasio', url: window.location.href }).catch(console.error); } 
    else { alert('Función de compartir no disponible en este navegador'); }
}

// Cierre de modales
window.onclick = function(event) {
    const renewalModal = document.getElementById('renewalModal');
    const cancelModal = document.getElementById('cancelModal');
    if (event.target == renewalModal) renewalModal.style.display = "none";
    if (event.target == cancelModal) cancelModal.style.display = "none";
}
