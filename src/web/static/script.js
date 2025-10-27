// Глобальные переменные
let countdownInterval = null;
let currentRenamingFile = null;

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    setupUploadArea();
    setupFileInput();
    loadFiles();
    loadSchedule();
    loadReports();
    setDefaultScheduleTime();
    startCountdownUpdate();
});

// ============================================================================
// Управление файлами
// ============================================================================

function setupUploadArea() {
    const uploadArea = document.getElementById('uploadArea');
    
    uploadArea.addEventListener('dragover', function(e) {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });
    
    uploadArea.addEventListener('dragleave', function(e) {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
    });
    
    uploadArea.addEventListener('drop', function(e) {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        
        const files = Array.from(e.dataTransfer.files).filter(file => 
            file.name.endsWith('.xlsx') || file.name.endsWith('.xls')
        );
        
        if (files.length > 0) {
            uploadFiles(files);
        }
    });
}

function setupFileInput() {
    const fileInput = document.getElementById('fileInput');
    
    fileInput.addEventListener('change', function(e) {
        const files = Array.from(e.target.files);
        if (files.length > 0) {
            uploadFiles(files);
        }
        // Сбрасываем input чтобы можно было загрузить те же файлы снова
        fileInput.value = '';
    });
}

async function uploadFiles(files) {
    const formData = new FormData();
    
    files.forEach(file => {
        formData.append('files', file);
    });
    
    try {
        const response = await fetch('/api/files/upload', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error('Ошибка при загрузке файлов');
        }
        
        const data = await response.json();
        
        alert(`Загружено ${data.files.length} файлов`);
        loadFiles();
        
    } catch (error) {
        console.error('Ошибка:', error);
        alert('Ошибка при загрузке файлов: ' + error.message);
    }
}

async function loadFiles() {
    const filesList = document.getElementById('filesList');
    
    try {
        const response = await fetch('/api/files');
        if (!response.ok) {
            throw new Error('Ошибка при загрузке списка файлов');
        }
        
        const data = await response.json();
        const files = data.files;
        
        if (files.length === 0) {
            filesList.innerHTML = '<p class="empty-message">Нет загруженных файлов</p>';
            return;
        }
        
        // Создаем таблицу файлов
        let html = `
            <table class="files-table-content">
                <thead>
                    <tr>
                        <th>Название</th>
                        <th>Размер</th>
                        <th>Дата загрузки</th>
                        <th>Действия</th>
                    </tr>
                </thead>
                <tbody>
        `;
        
        files.forEach(file => {
            const size = formatFileSize(file.size);
            const date = new Date(file.modified).toLocaleString('ru-RU');
            
            html += `
                <tr>
                    <td class="file-name">
                        <span class="file-icon">📄</span>
                        ${file.name}
                    </td>
                    <td>${size}</td>
                    <td>${date}</td>
                    <td class="file-actions">
                        <button class="btn btn-info btn-sm" onclick="downloadFile('${file.name}')" title="Скачать">
                            ⬇️
                        </button>
                        <button class="btn btn-warning btn-sm" onclick="openRenameModal('${file.name}')" title="Переименовать">
                            ✏️
                        </button>
                        <button class="btn btn-danger btn-sm" onclick="confirmDeleteFile('${file.name}')" title="Удалить">
                            🗑️
                        </button>
                    </td>
                </tr>
            `;
        });
        
        html += '</tbody></table>';
        filesList.innerHTML = html;
        
    } catch (error) {
        console.error('Ошибка:', error);
        filesList.innerHTML = '<p class="error-message">Ошибка при загрузке списка файлов</p>';
    }
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' Б';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' КБ';
    return (bytes / (1024 * 1024)).toFixed(1) + ' МБ';
}

function downloadFile(filename) {
    window.location.href = `/api/files/download/${encodeURIComponent(filename)}`;
}

function confirmDeleteFile(filename) {
    openModal(
        '⚠️ Удалить файл?',
        `Файл "${filename}" будет удален. Это действие необратимо. Продолжить?`,
        () => deleteFile(filename)
    );
}

async function deleteFile(filename) {
    try {
        const response = await fetch(`/api/files/${encodeURIComponent(filename)}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            throw new Error('Ошибка при удалении файла');
        }
        
        loadFiles();
        
    } catch (error) {
        console.error('Ошибка:', error);
        alert('Ошибка при удалении файла: ' + error.message);
    }
}

function openRenameModal(filename) {
    currentRenamingFile = filename;
    const modal = document.getElementById('renameModal');
    const input = document.getElementById('newFileName');
    const saveBtn = document.getElementById('renameModalSaveBtn');
    
    input.value = filename;
    
    saveBtn.onclick = async () => {
        const newName = input.value.trim();
        
        if (!newName) {
            alert('Введите имя файла');
            return;
        }
        
        if (!newName.endsWith('.xlsx') && !newName.endsWith('.xls')) {
            alert('Файл должен иметь расширение .xlsx или .xls');
            return;
        }
        
        await renameFile(currentRenamingFile, newName);
        closeRenameModal();
    };
    
    modal.style.display = 'flex';
}

function closeRenameModal() {
    document.getElementById('renameModal').style.display = 'none';
    currentRenamingFile = null;
}

async function renameFile(oldName, newName) {
    try {
        const response = await fetch(`/api/files/${encodeURIComponent(oldName)}/rename`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ new_name: newName })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Ошибка при переименовании');
        }
        
        loadFiles();
        
    } catch (error) {
        console.error('Ошибка:', error);
        alert('Ошибка при переименовании файла: ' + error.message);
    }
}

// ============================================================================
// Управление расписанием
// ============================================================================

function toggleScheduleType() {
    const type = document.querySelector('input[name="scheduleType"]:checked').value;
    const oneTimeFields = document.getElementById('oneTimeFields');
    const periodicFields = document.getElementById('periodicFields');
    
    if (type === 'one_time') {
        oneTimeFields.style.display = 'block';
        periodicFields.style.display = 'none';
    } else {
        oneTimeFields.style.display = 'none';
        periodicFields.style.display = 'block';
    }
}

function setDefaultScheduleTime() {
    const now = new Date();
    now.setHours(now.getHours() + 1);
    now.setMinutes(0);
    now.setSeconds(0);
    
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    
    const timeString = `${year}-${month}-${day}T${hours}:${minutes}`;
    document.getElementById('scheduledDateTime').value = timeString;
}

async function loadSchedule() {
    const statusDiv = document.getElementById('scheduleStatus');
    
    try {
        const response = await fetch('/api/schedule');
        if (!response.ok) {
            throw new Error('Ошибка при загрузке расписания');
        }
        
        const schedule = await response.json();
        
        if (schedule.is_enabled) {
            let html = '<div class="schedule-active">';
            html += '<h3>✅ Расписание активно</h3>';
            
            if (schedule.schedule_type === 'one_time') {
                const scheduledDate = new Date(schedule.scheduled_time);
                html += `<p><strong>Тип:</strong> Разовая задача</p>`;
                html += `<p><strong>Дата и время:</strong> ${scheduledDate.toLocaleString('ru-RU')}</p>`;
            } else if (schedule.schedule_type === 'periodic') {
                html += `<p><strong>Тип:</strong> Периодическая задача (ежедневно)</p>`;
                html += `<p><strong>Время:</strong> ${schedule.periodic_time}</p>`;
            }
            
            html += `<p><strong>Email:</strong> ${schedule.recipient_email || 'Не указан'}</p>`;
            html += '<p id="countdownText" class="countdown-text"></p>';
            html += '</div>';
            
            statusDiv.innerHTML = html;
        } else {
            statusDiv.innerHTML = '<div class="schedule-inactive"><p>❌ Расписание не установлено</p></div>';
        }
        
    } catch (error) {
        console.error('Ошибка:', error);
        statusDiv.innerHTML = '<p class="error-message">Ошибка при загрузке расписания</p>';
    }
}

async function setSchedule() {
    const type = document.querySelector('input[name="scheduleType"]:checked').value;
    const email = document.getElementById('recipientEmail').value.trim();
    
    if (!email) {
        alert('Введите email получателя');
        return;
    }
    
    const requestData = {
        schedule_type: type,
        recipient_email: email
    };
    
    if (type === 'one_time') {
        const scheduledTime = document.getElementById('scheduledDateTime').value;
        
        if (!scheduledTime) {
            alert('Выберите дату и время');
            return;
        }
        
        if (new Date(scheduledTime) <= new Date()) {
            alert('Время должно быть в будущем');
            return;
        }
        
        requestData.scheduled_time = new Date(scheduledTime).toISOString();
    } else {
        const periodicTime = document.getElementById('periodicTime').value;
        
        if (!periodicTime) {
            alert('Выберите время');
            return;
        }
        
        requestData.periodic_time = periodicTime;
    }
    
    try {
        const response = await fetch('/api/schedule', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Ошибка при установке расписания');
        }
        
        alert('✅ Расписание успешно установлено!');
        loadSchedule();
        
    } catch (error) {
        console.error('Ошибка:', error);
        alert('Ошибка: ' + error.message);
    }
}

async function cancelSchedule() {
    openModal(
        '⚠️ Отменить расписание?',
        'Автоматическая генерация отчетов будет остановлена. Продолжить?',
        async () => {
            try {
                const response = await fetch('/api/schedule', {
                    method: 'DELETE'
                });
                
                if (!response.ok) {
                    throw new Error('Ошибка при отмене расписания');
                }
                
                alert('Расписание отменено');
                loadSchedule();
                
            } catch (error) {
                console.error('Ошибка:', error);
                alert('Ошибка: ' + error.message);
            }
        }
    );
}

async function generateNow() {
    openModal(
        '🚀 Сгенерировать отчет сейчас?',
        'Отчет будет немедленно сгенерирован из всех файлов в папке. Если в расписании указан email, отчет будет отправлен туда. Продолжить?',
        async () => {
            try {
                const response = await fetch('/api/schedule/generate-now', {
                    method: 'POST'
                });
                
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || 'Ошибка при генерации');
                }
                
                const data = await response.json();
                
                alert('✅ Генерация отчета запущена! Отчет появится в истории через несколько секунд.');
                
                // Обновляем историю через 3 секунды
                setTimeout(() => {
                    loadReports();
                }, 3000);
                
            } catch (error) {
                console.error('Ошибка:', error);
                alert('Ошибка при запуске генерации: ' + error.message);
            }
        }
    );
}

function startCountdownUpdate() {
    if (countdownInterval) {
        clearInterval(countdownInterval);
    }
    
    countdownInterval = setInterval(updateCountdown, 1000);
}

async function updateCountdown() {
    const countdownText = document.getElementById('countdownText');
    
    if (!countdownText) {
        return;
    }
    
    try {
        const response = await fetch('/api/schedule/countdown');
        if (!response.ok) {
            return;
        }
        
        const data = await response.json();
        
        if (data.active && data.seconds_left > 0) {
            const hours = Math.floor(data.seconds_left / 3600);
            const minutes = Math.floor((data.seconds_left % 3600) / 60);
            const seconds = data.seconds_left % 60;
            
            countdownText.innerHTML = `<strong>⏳ До генерации отчета:</strong> ${hours}ч ${minutes}м ${seconds}с`;
        } else if (data.active && data.seconds_left <= 0) {
            countdownText.innerHTML = '<strong>⏳ Генерация отчета...</strong>';
        }
        
    } catch (error) {
        // Игнорируем ошибки обновления таймера
    }
}

// ============================================================================
// История отчетов
// ============================================================================

async function loadReports() {
    const reportsList = document.getElementById('reportsList');
    
    try {
        const response = await fetch('/api/reports');
        if (!response.ok) {
            throw new Error('Ошибка при загрузке отчетов');
        }
        
        const reports = await response.json();
        
        if (reports.length === 0) {
            reportsList.innerHTML = '<p class="empty-message">История отчетов пуста</p>';
            return;
        }
        
        reportsList.innerHTML = '';
        reports.forEach(report => {
            const item = createReportItem(report);
            reportsList.appendChild(item);
        });
        
    } catch (error) {
        console.error('Ошибка:', error);
        reportsList.innerHTML = '<p class="error-message">Ошибка при загрузке отчетов</p>';
    }
}

function createReportItem(report) {
    const div = document.createElement('div');
    div.className = 'report-item';
    
    const date = new Date(report.created_at).toLocaleString('ru-RU');
    const statusClass = `status-${report.status}`;
    const statusText = {
        'completed': 'Сгенерирован',
        'sent': 'Отправлен',
        'failed': 'Ошибка'
    }[report.status] || report.status;
    
    let html = `
        <div class="report-header">
            <div class="report-date">📅 ${date}</div>
            <span class="status-badge ${statusClass}">${statusText}</span>
        </div>
        <div class="report-details">
    `;
    
    if (report.sent_at) {
        const sentDate = new Date(report.sent_at);
        html += `<p><strong>✅ Отправлено:</strong> ${sentDate.toLocaleString('ru-RU')}</p>`;
        html += `<p><strong>📧 Email:</strong> ${report.recipient_email}</p>`;
    }
    
    if (report.status === 'completed' || report.status === 'sent') {
        html += `
            <div class="report-stats">
                <div class="stat-item">
                    <div class="stat-label">Записей</div>
                    <div class="stat-value">${report.records_count || 0}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Подразделений</div>
                    <div class="stat-value">${report.departments_count || 0}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Операций</div>
                    <div class="stat-value">${report.operations_count || 0}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Культур</div>
                    <div class="stat-value">${report.crops_count || 0}</div>
                </div>
            </div>
        `;
        
        if (report.archived_files && report.archived_files.length > 0) {
            html += `<p><strong>Обработано файлов:</strong> ${report.archived_files.length}</p>`;
            html += '<details><summary>Список файлов</summary><ul>';
            report.archived_files.forEach(file => {
                html += `<li>${file}</li>`;
            });
            html += '</ul></details>';
        }
    }
    
    if (report.error_message) {
        html += `<div class="error-message">❌ ${report.error_message}</div>`;
    }
    
    html += `</div><div class="report-actions">`;
    
    if (report.status === 'completed' || report.status === 'sent') {
        html += `
            <button class="btn btn-info btn-sm" onclick="downloadReport(${report.id})">
                ⬇️ Скачать отчет
            </button>
        `;
    }
    
    html += `
        <button class="btn btn-danger btn-sm" onclick="confirmDeleteReport(${report.id})">
            🗑️ Удалить
        </button>
    </div>`;
    
    div.innerHTML = html;
    return div;
}

function downloadReport(reportId) {
    window.location.href = `/api/reports/${reportId}/download`;
}

function confirmDeleteReport(reportId) {
    openModal(
        '⚠️ Удалить отчет?',
        'Отчет будет удален вместе с файлом. Это действие необратимо. Продолжить?',
        () => deleteReport(reportId)
    );
}

async function deleteReport(reportId) {
    try {
        const response = await fetch(`/api/reports/${reportId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            throw new Error('Ошибка при удалении отчета');
        }
        
        loadReports();
        
    } catch (error) {
        console.error('Ошибка:', error);
        alert('Ошибка при удалении отчета: ' + error.message);
    }
}

// ============================================================================
// Модальные окна
// ============================================================================

function openModal(title, message, onConfirm) {
    const modal = document.getElementById('confirmModal');
    const modalTitle = document.getElementById('modalTitle');
    const modalMessage = document.getElementById('modalMessage');
    const confirmBtn = document.getElementById('modalConfirmBtn');
    
    modalTitle.textContent = title;
    modalMessage.textContent = message;
    confirmBtn.onclick = () => {
        onConfirm();
        closeModal();
    };
    
    modal.style.display = 'flex';
}

function closeModal() {
    document.getElementById('confirmModal').style.display = 'none';
}

// Закрытие модальных окон при клике вне их
window.onclick = function(event) {
    const confirmModal = document.getElementById('confirmModal');
    const renameModal = document.getElementById('renameModal');
    
    if (event.target === confirmModal) {
        closeModal();
    }
    if (event.target === renameModal) {
        closeRenameModal();
    }
}
