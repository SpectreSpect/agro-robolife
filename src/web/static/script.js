let currentJobId = null;
let uploadedFiles = [];
let timers = {}; // Хранение таймеров для каждой задачи

document.addEventListener('DOMContentLoaded', function() {
    loadHistory();
    setupUploadArea();
    setupFileInput();
    startTimersUpdate();
});

function setupUploadArea() {
    const uploadArea = document.getElementById('uploadArea');
    
    uploadArea.addEventListener('click', function() {
        document.getElementById('fileInput').click();
    });
    
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
            handleFiles(files);
        }
    });
}

function setupFileInput() {
    const fileInput = document.getElementById('fileInput');
    
    fileInput.addEventListener('change', function(e) {
        const files = Array.from(e.target.files);
        if (files.length > 0) {
            handleFiles(files);
        }
    });
}

async function handleFiles(files) {
    const formData = new FormData();
    
    files.forEach(file => {
        formData.append('files', file);
    });
    
    try {
        showProcessingStatus('Загрузка файлов...');
        
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error('Ошибка при загрузке файлов');
        }
        
        const data = await response.json();
        currentJobId = data.job_id;
        uploadedFiles = data.files;
        
        displayUploadedFiles(data.files);
        setDefaultScheduleTime();
        hideProcessingStatus();
        
        const processBtn = document.getElementById('processBtn');
        processBtn.disabled = false;
        
    } catch (error) {
        console.error('Ошибка:', error);
        alert('Ошибка при загрузке файлов: ' + error.message);
        hideProcessingStatus();
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
    document.getElementById('scheduledTime').value = timeString;
}

function displayUploadedFiles(files) {
    const filesList = document.getElementById('filesList');
    const filesListItems = document.getElementById('filesListItems');
    
    filesListItems.innerHTML = '';
    files.forEach(file => {
        const li = document.createElement('li');
        li.textContent = file;
        filesListItems.appendChild(li);
    });
    
    filesList.style.display = 'block';
    document.getElementById('uploadArea').style.display = 'none';
}

function clearFiles() {
    currentJobId = null;
    uploadedFiles = [];
    
    document.getElementById('filesList').style.display = 'none';
    document.getElementById('uploadArea').style.display = 'block';
    document.getElementById('fileInput').value = '';
    document.getElementById('scheduledTime').value = '';
    document.getElementById('recipientEmail').value = '';
    
    const processBtn = document.getElementById('processBtn');
    processBtn.disabled = false;
}

async function processFiles() {
    if (!currentJobId) {
        alert('Сначала загрузите файлы');
        return;
    }
    
    const scheduledTime = document.getElementById('scheduledTime').value;
    const recipientEmail = document.getElementById('recipientEmail').value;
    
    if (scheduledTime && recipientEmail && !validateEmail(recipientEmail)) {
        alert('Пожалуйста, введите корректный email адрес');
        return;
    }
    
    if (scheduledTime && new Date(scheduledTime) <= new Date()) {
        alert('Время отправки должно быть в будущем');
        return;
    }
    
    const processBtn = document.getElementById('processBtn');
    processBtn.disabled = true;
    
    try {
        showProcessingStatus('Обработка файлов...');
        
        // Обрабатываем файлы
        const response = await fetch(`/api/process/${currentJobId}`, {
            method: 'POST'
        });
        
        if (!response.ok) {
            throw new Error('Ошибка при обработке файлов');
        }
        
        const data = await response.json();
        
        await waitForCompletion(currentJobId);
        
        if (scheduledTime && recipientEmail) {
            try {
                const localDate = new Date(scheduledTime);
                
                console.log('Планирование отправки:', {
                    scheduled_time: localDate.toISOString(),
                    recipient_email: recipientEmail
                });
                
                const scheduleResponse = await fetch(`/api/jobs/${currentJobId}/schedule`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        scheduled_time: localDate.toISOString(),
                        recipient_email: recipientEmail
                    })
                });
                
                if (scheduleResponse.ok) {
                    alert('Обработка завершена! Файл будет отправлен в указанное время.');
                } else {
                    const errorData = await scheduleResponse.json();
                    console.error('Ошибка сервера:', errorData);
                    throw new Error(errorData.detail || 'Ошибка при планировании отправки');
                }
            } catch (scheduleError) {
                console.error('Ошибка планирования:', scheduleError);
                alert('Обработка завершена, но не удалось запланировать отправку.\nОшибка: ' + scheduleError.message);
            }
        } else {
            alert('Обработка завершена! Файл доступен для скачивания в истории.');
        }
        
        hideProcessingStatus();
        clearFiles();
        loadHistory();
        
    } catch (error) {
        console.error('Ошибка:', error);
        alert('Ошибка при обработке файлов: ' + error.message);
        hideProcessingStatus();
        processBtn.disabled = false;
    }
}

async function waitForCompletion(jobId, maxAttempts = 30) {
    for (let i = 0; i < maxAttempts; i++) {
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        const response = await fetch(`/api/job/${jobId}`);
        const job = await response.json();
        
        if (job.status === 'completed' || job.status === 'failed') {
            return job;
        }
    }
    throw new Error('Превышено время ожидания');
}

function validateEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

function showProcessingStatus(message) {
    const status = document.getElementById('processingStatus');
    status.querySelector('p').textContent = message;
    status.style.display = 'block';
}

function hideProcessingStatus() {
    document.getElementById('processingStatus').style.display = 'none';
}

async function loadHistory() {
    const historyList = document.getElementById('historyList');
    
    try {
        const response = await fetch('/api/history');
        if (!response.ok) {
            throw new Error('Ошибка при загрузке истории');
        }
        
        const jobs = await response.json();
        
        if (jobs.length === 0) {
            historyList.innerHTML = '<p class="loading">История пуста</p>';
            return;
        }
        
        historyList.innerHTML = '';
        jobs.forEach(job => {
            const item = createHistoryItem(job);
            historyList.appendChild(item);
        });
        
    } catch (error) {
        console.error('Ошибка:', error);
        historyList.innerHTML = '<p class="loading">Ошибка при загрузке истории</p>';
    }
}

function createHistoryItem(job) {
    const div = document.createElement('div');
    div.className = 'history-item';
    div.id = `job-${job.id}`;
    
    const date = new Date(job.created_at).toLocaleString('ru-RU');
    const statusClass = `status-${job.status}`;
    const statusText = {
        'pending': 'Ожидание',
        'processing': 'Обработка',
        'completed': 'Завершено',
        'failed': 'Ошибка',
        'sent': 'Отправлено'
    }[job.status];
    
    let html = `
        <div class="history-header">
            <div class="history-date">📅 ${date}</div>
            <span class="status-badge ${statusClass}">${statusText}</span>
        </div>
        <div class="history-details">
            <p><strong>Файлов загружено:</strong> ${job.input_files ? job.input_files.length : 0}</p>
    `;
    
    // Информация о расписании
    if (job.scheduled_time && job.status !== 'sent' && !job.is_cancelled) {
        const scheduledDate = new Date(job.scheduled_time);
        const now = new Date();
        const timeLeft = scheduledDate - now;
        
        html += `
            <div class="schedule-info">
                <p><strong>📧 Email:</strong> ${job.recipient_email || 'Не указан'}</p>
                <p><strong>⏰ Время отправки:</strong> ${scheduledDate.toLocaleString('ru-RU')}</p>
                <p class="timer" data-job-id="${job.id}" data-scheduled="${job.scheduled_time}">
                    <strong>⏳ До отправки:</strong> <span class="countdown"></span>
                </p>
            </div>
        `;
    } else if (job.sent_at) {
        const sentDate = new Date(job.sent_at);
        html += `
            <div class="schedule-info">
                <p><strong>✅ Отправлено:</strong> ${sentDate.toLocaleString('ru-RU')}</p>
                <p><strong>📧 Email:</strong> ${job.recipient_email}</p>
            </div>
        `;
    }
    
    if (job.status === 'completed' || job.status === 'sent') {
        html += `
            <div class="history-stats">
                <div class="stat-item">
                    <div class="stat-label">Записей</div>
                    <div class="stat-value">${job.records_count || 0}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Подразделений</div>
                    <div class="stat-value">${job.departments_count || 0}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Операций</div>
                    <div class="stat-value">${job.operations_count || 0}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Культур</div>
                    <div class="stat-value">${job.crops_count || 0}</div>
                </div>
            </div>
        `;
    }
    
    if (job.error_message) {
        html += `<div class="error-message">❌ ${job.error_message}</div>`;
    }
    
    html += `</div><div class="history-actions">`;
    
    // Кнопки в зависимости от статуса
    if (job.status === 'completed' || job.status === 'sent') {
        html += `
            <button class="btn btn-info btn-sm" onclick="downloadFile(${job.id})">
                ⬇️ Скачать файл
            </button>
        `;
    }
    
    if (job.status === 'completed') {
        if (!job.scheduled_time) {
            // Если отправка не запланирована, показываем кнопку планирования
            html += `
                <button class="btn btn-success btn-sm" onclick="openScheduleModal(${job.id})">
                    📅 Запланировать отправку
                </button>
            `;
        } else if (!job.is_cancelled) {
            // Если отправка запланирована, показываем кнопки управления
            html += `
                <button class="btn btn-warning btn-sm" onclick="openEditModal(${job.id}, '${job.scheduled_time}', '${job.recipient_email}')">
                    ✏️ Изменить
                </button>
                <button class="btn btn-success btn-sm" onclick="confirmSendNow(${job.id})">
                    🚀 Отправить сейчас
                </button>
                <button class="btn btn-secondary btn-sm" onclick="confirmCancelSchedule(${job.id})">
                    ⏸️ Отменить отправку
                </button>
            `;
        }
    }
    
    html += `
        <button class="btn btn-danger btn-sm" onclick="confirmDeleteJob(${job.id}, ${job.scheduled_time ? 'true' : 'false'})">
            🗑️ Удалить
        </button>
    </div>`;
    
    div.innerHTML = html;
    return div;
}

// Обновление таймеров
function startTimersUpdate() {
    setInterval(updateTimers, 1000);
}

function updateTimers() {
    const timers = document.querySelectorAll('.timer');
    timers.forEach(timer => {
        const scheduledTime = new Date(timer.dataset.scheduled);
        const now = new Date();
        const timeLeft = scheduledTime - now;
        
        const countdownSpan = timer.querySelector('.countdown');
        
        if (timeLeft <= 0) {
            countdownSpan.textContent = 'Отправка...';
            countdownSpan.style.color = '#e74c3c';
        } else {
            const hours = Math.floor(timeLeft / (1000 * 60 * 60));
            const minutes = Math.floor((timeLeft % (1000 * 60 * 60)) / (1000 * 60));
            const seconds = Math.floor((timeLeft % (1000 * 60)) / 1000);
            
            countdownSpan.textContent = `${hours}ч ${minutes}м ${seconds}с`;
            countdownSpan.style.color = '#2ecc71';
        }
    });
}

// Модальные окна
function openScheduleModal(jobId) {
    const modal = document.getElementById('editModal');
    const saveBtn = document.getElementById('editModalSaveBtn');
    
    setDefaultScheduleTime();
    const defaultTime = document.getElementById('scheduledTime').value;
    document.getElementById('editScheduledTime').value = defaultTime;
    document.getElementById('editRecipientEmail').value = '';
    
    saveBtn.onclick = async () => {
        const scheduledTime = document.getElementById('editScheduledTime').value;
        const email = document.getElementById('editRecipientEmail').value;
        
        if (!scheduledTime || !email) {
            alert('Заполните все поля');
            return;
        }
        
        if (!validateEmail(email)) {
            alert('Введите корректный email адрес');
            return;
        }
        
        if (new Date(scheduledTime) <= new Date()) {
            alert('Время отправки должно быть в будущем');
            return;
        }
        
        try {
            const localDate = new Date(scheduledTime);
            const response = await fetch(`/api/jobs/${jobId}/schedule`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    scheduled_time: localDate.toISOString(),
                    recipient_email: email
                })
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Ошибка при планировании');
            }
            
            alert('Отправка успешно запланирована!');
            closeEditModal();
            loadHistory();
            
        } catch (error) {
            console.error('Ошибка:', error);
            alert('Ошибка: ' + error.message);
        }
    };
    
    modal.style.display = 'flex';
}

function openEditModal(jobId, currentScheduledTime, currentEmail) {
    const modal = document.getElementById('editModal');
    const saveBtn = document.getElementById('editModalSaveBtn');
    
    const scheduledDate = new Date(currentScheduledTime);
    const year = scheduledDate.getFullYear();
    const month = String(scheduledDate.getMonth() + 1).padStart(2, '0');
    const day = String(scheduledDate.getDate()).padStart(2, '0');
    const hours = String(scheduledDate.getHours()).padStart(2, '0');
    const minutes = String(scheduledDate.getMinutes()).padStart(2, '0');
    
    const localDateTime = `${year}-${month}-${day}T${hours}:${minutes}`;
    
    document.getElementById('editScheduledTime').value = localDateTime;
    document.getElementById('editRecipientEmail').value = currentEmail;
    
    saveBtn.onclick = async () => {
        const newTime = document.getElementById('editScheduledTime').value;
        const newEmail = document.getElementById('editRecipientEmail').value;
        
        if (!newTime || !newEmail) {
            alert('Заполните все поля');
            return;
        }
        
        if (!validateEmail(newEmail)) {
            alert('Введите корректный email адрес');
            return;
        }
        
        if (new Date(newTime) <= new Date()) {
            alert('Время отправки должно быть в будущем');
            return;
        }
        
        try {
            const localDate = new Date(newTime);
            const response = await fetch(`/api/jobs/${jobId}/schedule`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    scheduled_time: localDate.toISOString(),
                    recipient_email: newEmail
                })
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Ошибка при обновлении');
            }
            
            alert('Настройки отправки обновлены!');
            closeEditModal();
            loadHistory();
            
        } catch (error) {
            console.error('Ошибка:', error);
            alert('Ошибка: ' + error.message);
        }
    };
    
    modal.style.display = 'flex';
}

function closeEditModal() {
    document.getElementById('editModal').style.display = 'none';
}

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

// Подтверждения действий
function confirmSendNow(jobId) {
    openModal(
        '⚠️ Отправить сейчас?',
        'Файл будет немедленно отправлен на указанный email адрес. Запланированная отправка будет отменена. Продолжить?',
        async () => {
            try {
                const response = await fetch(`/api/jobs/${jobId}/send-now`, {
                    method: 'POST'
                });
                
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || 'Ошибка при отправке');
                }
                
                alert('✅ Файл успешно отправлен!');
                loadHistory();
                
            } catch (error) {
                console.error('Ошибка:', error);
                alert('Ошибка при отправке: ' + error.message);
            }
        }
    );
}

function confirmCancelSchedule(jobId) {
    openModal(
        '⚠️ Отменить отправку?',
        'Запланированная автоматическая отправка будет отменена. Вы сможете скачать файл вручную или запланировать отправку заново. Продолжить?',
        async () => {
            try {
                const response = await fetch(`/api/jobs/${jobId}/cancel`, {
                    method: 'POST'
                });
                
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || 'Ошибка при отмене');
                }
                
                alert('Отправка отменена');
                loadHistory();
                
            } catch (error) {
                console.error('Ошибка:', error);
                alert('Ошибка при отмене: ' + error.message);
            }
        }
    );
}

function confirmDeleteJob(jobId, hasSchedule) {
    const message = hasSchedule
        ? 'Эта задача удалится вместе со всеми файлами. Запланированная отправка будет отменена. Это действие необратимо. Продолжить?'
        : 'Эта задача удалится вместе со всеми файлами. Это действие необратимо. Продолжить?';
    
    openModal(
        '⚠️ Удалить задачу?',
        message,
        () => deleteJob(jobId)
    );
}

async function downloadFile(jobId) {
    try {
        window.location.href = `/api/download/${jobId}`;
    } catch (error) {
        console.error('Ошибка:', error);
        alert('Ошибка при скачивании файла');
    }
}

async function deleteJob(jobId) {
    try {
        const response = await fetch(`/api/jobs/${jobId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            throw new Error('Ошибка при удалении');
        }
        
        loadHistory();
        
    } catch (error) {
        console.error('Ошибка:', error);
        alert('Ошибка при удалении задачи');
    }
}

// Закрытие модальных окон при клике вне их
window.onclick = function(event) {
    const confirmModal = document.getElementById('confirmModal');
    const editModal = document.getElementById('editModal');
    
    if (event.target === confirmModal) {
        closeModal();
    }
    if (event.target === editModal) {
        closeEditModal();
    }
}
