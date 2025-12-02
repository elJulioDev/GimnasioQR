
document.addEventListener('DOMContentLoaded', function() {
    // Navegación entre secciones
    const navLinks = document.querySelectorAll('.nav-link[data-section]');
    const sections = document.querySelectorAll('.content-section');

    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Remover active de todos los links
            navLinks.forEach(l => l.classList.remove('active'));
            
            // Agregar active al link clickeado
            this.classList.add('active');
            
            // Ocultar todas las secciones
            sections.forEach(s => s.classList.remove('active'));
            
            // Mostrar la sección correspondiente
            const targetSection = this.getAttribute('data-section');
            document.getElementById(targetSection).classList.add('active');
            
            // Scroll to top
            document.querySelector('.main-content').scrollTo(0, 0);
        });
    });

    // Tabs para Socios y Moderadores
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            // Remover active de todos los tabs
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));
            
            // Agregar active al tab clickeado
            this.classList.add('active');
            
            // Mostrar el contenido correspondiente
            const targetTab = this.getAttribute('data-tab');
            document.getElementById(targetTab + '-content').classList.add('active');
        });
    });
});

// Funciones del Modal de Eliminación
let deleteUserId = null;

function showDeleteModal(userId, userName, userRut) {
    deleteUserId = userId;
    document.getElementById('modalUserName').textContent = userName;
    document.getElementById('modalUserRut').textContent = 'RUT: ' + userRut;
    document.getElementById('deleteModal').classList.add('active');
    
    // Actualizar la acción del formulario
    const deleteForm = document.getElementById('deleteForm');
    deleteForm.action = `/management/users/${userId}/delete/`;
}

function closeDeleteModal() {
    document.getElementById('deleteModal').classList.remove('active');
    deleteUserId = null;
}

// Cerrar modal al hacer clic fuera de él
document.getElementById('deleteModal').addEventListener('click', function(e) {
    if (e.target === this) {
        closeDeleteModal();
    }
});

// Cerrar modal con tecla ESC
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeDeleteModal();
    }
});

// ========== FUNCIONES DEL MODAL DE PLANES ==========
let deletePlanId = null;

function showDeletePlanModal(planId, planName, planType, activeUsers) {
    deletePlanId = planId;
    document.getElementById('modalPlanName').textContent = planName;
    document.getElementById('modalPlanType').textContent = 'Tipo: ' + planType;
    
    // Mostrar advertencia si hay usuarios activos
    const warningElement = document.getElementById('planWarning');
    const activeUsersElement = document.getElementById('planActiveUsers');
    
    if (activeUsers > 0) {
        activeUsersElement.textContent = activeUsers;
        warningElement.style.display = 'inline';
    } else {
        warningElement.style.display = 'none';
    }
    
    document.getElementById('deletePlanModal').classList.add('active');
    
    // Actualizar la acción del formulario
    const deletePlanForm = document.getElementById('deletePlanForm');
    deletePlanForm.action = `/management/plans/${planId}/delete/`;
}

function closeDeletePlanModal() {
    document.getElementById('deletePlanModal').classList.remove('active');
    deletePlanId = null;
}

// Cerrar modal de plan al hacer clic fuera de él
document.getElementById('deletePlanModal').addEventListener('click', function(e) {
    if (e.target === this) {
        closeDeletePlanModal();
    }
});

// Cerrar modal de plan con tecla ESC (actualizar el listener existente)
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeDeleteModal();
        closeDeletePlanModal();
    }
});

// Función genérica de búsqueda
function setupSearch(inputId, rowClass, noResultsId, originalEmptyId) {
    const input = document.getElementById(inputId);
    if (!input) return;

    input.addEventListener('keyup', function(e) {
        const searchTerm = e.target.value.toLowerCase().trim();
        const rows = document.querySelectorAll('.' + rowClass);
        const noResultsMsg = document.getElementById(noResultsId);
        const originalEmptyMsg = document.getElementById(originalEmptyId);
        
        let hasVisibleRows = false;

        rows.forEach(row => {
            const searchData = row.getAttribute('data-search').toLowerCase();
            if (searchData.includes(searchTerm)) {
                row.style.display = '';
                hasVisibleRows = true;
            } else {
                row.style.display = 'none';
            }
        });

        // Mostrar mensaje si no hay resultados
        if (noResultsMsg) {
            if (!hasVisibleRows && rows.length > 0) {
                noResultsMsg.style.display = '';
                if(originalEmptyMsg) originalEmptyMsg.style.display = 'none';
            } else {
                noResultsMsg.style.display = 'none';
            }
        }
    });
}

setupSearch('searchSocioInput', 'searchable-socio-row', 'search-socio-no-results', 'no-socios-row');
// 1. Configurar búsqueda de Socios
setupSearch('searchInput', 'searchable-row', 'search-no-results', 'no-results-row');

// 2. Configurar búsqueda de Moderadores
setupSearch('searchModeradorInput', 'searchable-moderador-row', 'search-moderador-no-results', 'no-moderadores-row');

// 1. Formateador de Moneda (CLP)
const currencyElements = document.querySelectorAll('.currency-format');
const clpFormatter = new Intl.NumberFormat('es-CL', {
    style: 'currency',
    currency: 'CLP',
    minimumFractionDigits: 0
});

currencyElements.forEach(el => {
    const rawValue = el.getAttribute('data-value');
    if(rawValue) {
        el.textContent = clpFormatter.format(parseFloat(rawValue));
    }
});

// 2. Configuración Global de Chart.js
Chart.defaults.color = '#b4b4b4';
Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.05)';
Chart.defaults.font.family = "'Inter', sans-serif";

// --- DATOS DESDE DJANGO ---
// Asegúrate de que estas variables existen en tu views.py
// En lugar de parsear las etiquetas aquí, leemos el objeto global definido en el HTML
const ingresosLabels = window.djangoChartData.ingresosLabels;
const ingresosData = window.djangoChartData.ingresosData;

// Nuevos datos para métodos de pago
const pagosLabels = window.djangoChartData.pagosLabels;
const pagosData = window.djangoChartData.pagosData;

// GRÁFICO 1: INGRESOS (Línea con gradiente)
const ctxRevenue = document.getElementById('revenueChart').getContext('2d');
// Crear gradiente verde
const gradientGreen = ctxRevenue.createLinearGradient(0, 0, 0, 400);
gradientGreen.addColorStop(0, 'rgba(0, 255, 157, 0.2)');
gradientGreen.addColorStop(1, 'rgba(0, 255, 157, 0)');

new Chart(ctxRevenue, {
    type: 'line',
    data: {
        labels: ingresosLabels,
        datasets: [{
            label: 'Ingresos ($)',
            data: ingresosData,
            borderColor: '#00ff9d',
            backgroundColor: gradientGreen,
            borderWidth: 2,
            tension: 0.4, // Curva suave
            fill: true,
            pointBackgroundColor: '#0a0a0a',
            pointBorderColor: '#00ff9d',
            pointBorderWidth: 2,
            pointRadius: 4,
            pointHoverRadius: 6
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false },
            tooltip: {
                backgroundColor: '#151515',
                titleColor: '#fff',
                bodyColor: '#00ff9d',
                padding: 10,
                callbacks: {
                    label: function(context) {
                        return clpFormatter.format(context.raw);
                    }
                }
            }
        },
        scales: {
            y: {
                beginAtZero: true,
                grid: { borderDash: [5, 5], color: 'rgba(255,255,255,0.03)' },
                ticks: {
                    callback: function(value) {
                        return '$' + value / 1000 + 'k'; // Formato corto
                    }
                }
            },
            x: {
                grid: { display: false }
            }
        }
    }
});

// GRÁFICO 2: MÉTODOS DE PAGO (Dona) - NUEVO
const ctxPayment = document.getElementById('paymentMethodsChart');
if (ctxPayment) {
    new Chart(ctxPayment, {
        type: 'doughnut',
        data: {
            labels: pagosLabels,
            datasets: [{
                data: pagosData,
                backgroundColor: [
                    '#00ff9d', // Efectivo (Verde)
                    '#3742fa', // Transferencia (Azul)
                    '#ffa502', // Tarjeta (Naranja)
                    '#ff4757'  // Webpay (Rojo)
                ],
                borderWidth: 0,
                hoverOffset: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '75%', // Dona más delgada
            plugins: {
                legend: {
                    position: 'right',
                    labels: {
                        boxWidth: 12,
                        usePointStyle: true,
                        font: { size: 11 }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            let value = context.raw;
                            let total = context.chart._metasets[context.datasetIndex].total;
                            let percentage = Math.round((value / total) * 100) + '%';
                            return context.label + ': ' + clpFormatter.format(value) + ' (' + percentage + ')';
                        }
                    }
                }
            }
        }
    });
}

function switchAssistTab(tabName) {
    // Ocultar todos
    document.getElementById('tab-logs').style.display = 'none';
    document.getElementById('tab-absent').style.display = 'none';
    
    // Quitar clase active botones
    const btns = document.querySelectorAll('#asistencias .tab-btn');
    btns.forEach(b => b.classList.remove('active'));
    
    // Mostrar seleccionado
    document.getElementById('tab-' + tabName).style.display = 'block';
    
    // Activar botón (buscando por onclick es una forma rápida)
    const activeBtn = Array.from(btns).find(b => b.getAttribute('onclick').includes(tabName));
    if(activeBtn) activeBtn.classList.add('active');
}

function filterTable(inputId, rowClass) {
    const input = document.getElementById(inputId);
    const filter = input.value.toLowerCase();
    const rows = document.getElementsByClassName(rowClass);

    for (let i = 0; i < rows.length; i++) {
        const textContent = rows[i].textContent || rows[i].innerText;
        if (textContent.toLowerCase().indexOf(filter) > -1) {
            rows[i].style.display = "";
        } else {
            rows[i].style.display = "none";
        }
    }
}

function filterByMethod() {
    const select = document.getElementById('paymentMethodFilter');
    const filterValue = select.value;
    const rows = document.getElementsByClassName('payment-row');

    for (let i = 0; i < rows.length; i++) {
        const rowMethod = rows[i].getAttribute('data-method');
        if (filterValue === 'all' || rowMethod === filterValue) {
            rows[i].style.display = "";
        } else {
            rows[i].style.display = "none";
        }
    }
}