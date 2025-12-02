
// Validación y Preview en tiempo real
const reqFields = document.querySelectorAll('.req-field');
const submitBtn = document.getElementById('submitBtn');

function updatePreview() {
    // Datos
    const price = document.querySelector('input[name="price"]').value;
    const name = document.querySelector('input[name="name"]').value;
    const desc = document.querySelector('textarea[name="description"]').value;
    
    // Formateo Precio
    const formattedPrice = price ? new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 }).format(price) : '$0';
    
    // Actualizar DOM
    document.getElementById('previewPrice').innerHTML = `${formattedPrice} <span>/mes</span>`;
    document.getElementById('previewName').textContent = name || 'Nombre del Plan';
    document.getElementById('previewDesc').textContent = desc || 'Descripción del plan...';
    
    validateForm();
}

function validateForm() {
    let isValid = true;
    reqFields.forEach(field => {
        if (!field.value.trim()) isValid = false;
    });

    if (isValid) {
        submitBtn.classList.add('ready');
        submitBtn.disabled = false;
    } else {
        submitBtn.classList.remove('ready');
        submitBtn.disabled = true;
    }
}

// Envío del formulario
document.getElementById('createPlanForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    // Visual Loading
    const originalText = submitBtn.innerHTML;
    submitBtn.disabled = true;
    submitBtn.innerHTML = "<i class='bx bx-loader-alt bx-spin'></i> Guardando...";

    const formData = new FormData(this);
    
    // Construir objeto JSON manual para asegurar tipos
    const data = {
        name: formData.get('name'),
        description: formData.get('description'),
        plan_type: formData.get('plan_type'),
        price: parseFloat(formData.get('price')),
        duration_days: parseInt(formData.get('duration_days')),
        access_days: formData.get('access_days'), // Texto directo
        includes_classes: formData.get('includes_classes') === 'true',
        includes_nutritionist: formData.get('includes_nutritionist') === 'true',
        benefits: formData.get('benefits') || '',
        is_active: formData.get('is_active') === 'true'
    };

    // 1. Obtener las URLs desde los atributos del formulario
    const form = document.getElementById('createPlanForm');
    const urlCreate = form.getAttribute('data-url-create');
    const urlRedirect = form.getAttribute('data-url-redirect');

    try {
        const response = await fetch(urlCreate, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
            },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (result.success) {
            submitBtn.style.background = "#fff";
            submitBtn.style.color = "#000";
            submitBtn.innerHTML = "<i class='bx bx-check'></i> ¡Guardado!";
            setTimeout(() => {
                window.location.href = urlRedirect;
            }, 600);
        } else {
            alert('❌ Error: ' + result.error);
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalText;
        }

    } catch (error) {
        console.error(error);
        alert('❌ Error de conexión.');
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalText;
    }
});

// Init
validateForm();