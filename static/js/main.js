// Основной JavaScript файл для приложения Санатория КМВ

// Функция для отображения текущего времени
function updateTime() {
    const now = new Date();
    const timeString = now.toLocaleString('ru-RU', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
    const timeElement = document.getElementById('current-time');
    if (timeElement) {
        timeElement.textContent = timeString;
    }
}

// Функция для подтверждения удаления
function confirmDelete(id, name, type) {
    const modal = new bootstrap.Modal(document.getElementById('deleteModal'));
    const nameElement = document.getElementById('deleteItemName');
    const form = document.getElementById('deleteForm');
    
    if (nameElement) {
        nameElement.textContent = name;
    }
    if (form) {
        form.action = `/${type}/${id}/delete`;
    }
    
    modal.show();
}

// Функция для показа уведомлений
function showNotification(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    const container = document.querySelector('.container');
    if (container) {
        container.insertBefore(alertDiv, container.firstChild);
        
        // Автоматически скрыть через 5 секунд
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 5000);
    }
}

// Функция для форматирования дат
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU');
}

// Функция для форматирования времени
function formatTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleTimeString('ru-RU', {
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Функция для форматирования цен
function formatPrice(price) {
    return new Intl.NumberFormat('ru-RU', {
        style: 'currency',
        currency: 'RUB'
    }).format(price);
}

// Функция для подтверждения действий
function confirmAction(message, callback) {
    if (confirm(message)) {
        callback();
    }
}

// Функция для валидации форм
function validateForm(form) {
    const requiredFields = form.querySelectorAll('[required]');
    let isValid = true;
    
    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            field.classList.add('is-invalid');
            isValid = false;
        } else {
            field.classList.remove('is-invalid');
        }
    });
    
    return isValid;
}

// Функция для загрузки данных через AJAX
async function fetchData(url, options = {}) {
    try {
        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('Ошибка при загрузке данных:', error);
        showNotification('Ошибка при загрузке данных', 'danger');
        throw error;
    }
}

// Функция для отправки данных через AJAX
async function postData(url, data, options = {}) {
    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            body: JSON.stringify(data),
            ...options
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('Ошибка при отправке данных:', error);
        showNotification('Ошибка при отправке данных', 'danger');
        throw error;
    }
}

// Функция для создания модального окна
function createModal(title, content, options = {}) {
    const modalId = 'dynamicModal';
    let existingModal = document.getElementById(modalId);
    
    if (existingModal) {
        existingModal.remove();
    }
    
    const modalHtml = `
        <div class="modal fade" id="${modalId}" tabindex="-1">
            <div class="modal-dialog ${options.size || 'modal-lg'}">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">${title}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        ${content}
                    </div>
                    ${options.footer ? `
                        <div class="modal-footer">
                            ${options.footer}
                        </div>
                    ` : ''}
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    const modal = new bootstrap.Modal(document.getElementById(modalId));
    modal.show();
    
    return modal;
}

// Функция для создания таблицы
function createTable(data, columns, options = {}) {
    if (!data || data.length === 0) {
        return '<div class="text-center py-4"><p class="text-muted">Данные не найдены</p></div>';
    }
    
    let tableHtml = `
        <div class="table-responsive">
            <table class="table table-hover ${options.className || ''}">
                <thead class="table-light">
                    <tr>
    `;
    
    columns.forEach(column => {
        tableHtml += `<th>${column.title}</th>`;
    });
    
    tableHtml += '</tr></thead><tbody>';
    
    data.forEach(row => {
        tableHtml += '<tr>';
        columns.forEach(column => {
            const value = column.render ? column.render(row[column.key], row) : row[column.key];
            tableHtml += `<td>${value}</td>`;
        });
        tableHtml += '</tr>';
    });
    
    tableHtml += '</tbody></table></div>';
    
    return tableHtml;
}

// Функция для поиска в таблицах
function setupTableSearch(tableId, searchInputId) {
    const table = document.getElementById(tableId);
    const searchInput = document.getElementById(searchInputId);
    
    if (!table || !searchInput) return;
    
    searchInput.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase();
        const rows = table.querySelectorAll('tbody tr');
        
        rows.forEach(row => {
            const text = row.textContent.toLowerCase();
            if (text.includes(searchTerm)) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
    });
}

// Функция для сортировки таблиц
function setupTableSort(tableId) {
    const table = document.getElementById(tableId);
    if (!table) return;
    
    const headers = table.querySelectorAll('thead th');
    
    headers.forEach((header, index) => {
        header.style.cursor = 'pointer';
        header.addEventListener('click', () => {
            sortTable(table, index);
        });
    });
}

function sortTable(table, columnIndex) {
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    
    rows.sort((a, b) => {
        const aValue = a.cells[columnIndex].textContent.trim();
        const bValue = b.cells[columnIndex].textContent.trim();
        
        // Попытка числовой сортировки
        const aNum = parseFloat(aValue);
        const bNum = parseFloat(bValue);
        
        if (!isNaN(aNum) && !isNaN(bNum)) {
            return aNum - bNum;
        }
        
        // Строковая сортировка
        return aValue.localeCompare(bValue, 'ru-RU');
    });
    
    // Пересортировка строк
    rows.forEach(row => tbody.appendChild(row));
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Обновление времени каждую секунду
    updateTime();
    setInterval(updateTime, 1000);
    
    // Добавление анимации появления для карточек
    const cards = document.querySelectorAll('.card');
    cards.forEach((card, index) => {
        card.style.animationDelay = `${index * 0.1}s`;
        card.classList.add('fade-in');
    });
    
    // Настройка автоматического скрытия алертов
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            if (alert.parentNode) {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }
        }, 5000);
    });
    
    // Настройка форм
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!validateForm(this)) {
                e.preventDefault();
                showNotification('Пожалуйста, заполните все обязательные поля', 'warning');
            }
        });
    });
    
    // Настройка поиска в таблицах
    const searchInputs = document.querySelectorAll('[data-table-search]');
    searchInputs.forEach(input => {
        const tableId = input.getAttribute('data-table-search');
        setupTableSearch(tableId, input.id);
    });
    
    // Настройка сортировки таблиц
    const sortableTables = document.querySelectorAll('[data-sortable="true"]');
    sortableTables.forEach(table => {
        setupTableSort(table.id);
    });
    
    // Подсветка активного пункта навигации
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
    navLinks.forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        }
    });
    
    // Улучшение таблиц
    const tables = document.querySelectorAll('.table');
    tables.forEach(table => {
        if (!table.classList.contains('dataTable')) {
            table.classList.add('table-hover', 'table-striped');
        }
    });
});

// Экспорт функций для использования в других файлах
window.SanatoriumApp = {
    formatDate,
    formatTime,
    formatPrice,
    showNotification,
    confirmAction,
    validateForm,
    fetchData,
    postData,
    createModal,
    createTable,
    setupTableSearch,
    setupTableSort
}; 