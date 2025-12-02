// Obtener CSRF token
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
    // Toggle password visibility
    const togglePassword = document.getElementById('togglePassword');
    const passwordInput = document.getElementById('password');

    togglePassword.addEventListener('click', function() {
        const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
        passwordInput.setAttribute('type', type);
        this.classList.toggle('fa-eye');
        this.classList.toggle('fa-eye-slash');
    });

    // Form submission
    const loginForm = document.getElementById('loginForm');
    const loginButton = document.getElementById('loginButton');
    const alert = document.getElementById('alert');

    loginForm.addEventListener('submit', async function(e) {
        e.preventDefault();

        // Add loading state
        loginButton.classList.add('loading');
        loginButton.querySelector('span').textContent = 'Iniciando sesión...';
        alert.classList.remove('show');

        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;
        const url = loginForm.getAttribute('data-url');
        
        try {
            // USAR LA VARIABLE url AQUÍ
            const response = await fetch(url, { 
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken
                },
                body: JSON.stringify({
                    username: username,
                    password: password
                })
            });

            const data = await response.json();

            if (data.success) {
                // Success
                alert.className = 'alert alert-success show';
                alert.innerHTML = '<i class="fas fa-check-circle"></i><span>¡Inicio de sesión exitoso!</span>';
                
                // Redirigir según el rol
                setTimeout(() => {
                    window.location.href = data.redirect_url;
                }, 1000);
            } else {
                // Error
                alert.className = 'alert alert-error show';
                alert.innerHTML = `<i class="fas fa-exclamation-circle"></i><span>${data.error}</span>`;
                
                loginButton.classList.remove('loading');
                loginButton.querySelector('span').textContent = 'Iniciar Sesión';

                setTimeout(() => {
                    alert.classList.remove('show');
                }, 4000);
            }
        } catch (error) {
            console.error('Error:', error);
            alert.className = 'alert alert-error show';
            alert.innerHTML = '<i class="fas fa-exclamation-circle"></i><span>Error de conexión. Por favor intenta nuevamente.</span>';
            
            loginButton.classList.remove('loading');
            loginButton.querySelector('span').textContent = 'Iniciar Sesión';
        }
    });

    // Remove alert on input focus
    const inputs = document.querySelectorAll('.input-group input');
    inputs.forEach(input => {
        input.addEventListener('focus', () => {
            alert.classList.remove('show');
        });
    });
});