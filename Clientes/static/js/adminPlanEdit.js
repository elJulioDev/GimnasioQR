
const reqFields = document.querySelectorAll('.req-field');
const submitBtn = document.getElementById('submitBtn');

function updatePreview() {
    const price = document.querySelector('input[name="price"]').value;
    const name = document.querySelector('input[name="name"]').value;
    const desc = document.querySelector('textarea[name="description"]').value;
    
    const formattedPrice = price ? new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 }).format(price) : '$0';
    
    document.getElementById('previewPrice').innerHTML = `${formattedPrice} <span>/mes</span>`;
    document.getElementById('previewName').textContent = name || 'Nombre del Plan';
    document.getElementById('previewDesc').textContent = desc || 'Descripción...';
    
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

document.getElementById('editPlanForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const originalText = submitBtn.innerHTML;
    submitBtn.disabled = true;
    submitBtn.innerHTML = "<i class='bx bx-loader-alt bx-spin'></i> Guardando...";

    const formData = new FormData(this);
    
    const data = {
        name: formData.get('name'),
        description: formData.get('description'),
        plan_type: formData.get('plan_type'),
        price: parseFloat(formData.get('price')),
        duration_days: parseInt(formData.get('duration_days')),
        
        // CORRECCIÓN CRÍTICA: No usar parseInt aquí para que guarde el texto
        access_days: formData.get('access_days'),
        
        includes_classes: formData.get('includes_classes') === 'true',
        includes_nutritionist: formData.get('includes_nutritionist') === 'true',
        benefits: formData.get('benefits') || '',
        is_active: formData.get('is_active') === 'true'
    };

    try {
        // Usamos window.location.href porque la URL ya tiene el ID correcto
        const response = await fetch(window.location.href, {
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
            submitBtn.innerHTML = "<i class='bx bx-check'></i> ¡Actualizado!";

            const form = document.getElementById('editPlanForm');
            const redirectUrl = form.getAttribute('data-url-redirect');

            setTimeout(() => {
                window.location.href = redirectUrl; 
            }, 800);
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

// Validar al inicio para activar el botón si los datos ya están bien
validateForm();