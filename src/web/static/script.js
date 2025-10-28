// Глобальные переменные
let countdownInterval = null;
let countdownTargetTime = null;  // Целевое время для countdown (вычисляется локально)
let currentRenamingFile = null;
let ws = null;
let wsReconnectTimeout = null;

// Глобальный обработчик необработанных Promise rejection
// Предотвращает показ alert "Failed to fetch" при сетевых ошибках
window.addEventListener('unhandledrejection', function(event) {
    const reason = event.reason;
    
    // Игнорируем сетевые ошибки (часто возникают при перезагрузке страницы)
    if (reason && (
        (reason.message && reason.message.includes('Failed to fetch')) ||
        (reason.message && reason.message.includes('NetworkError')) ||
        (reason.name === 'AbortError')
    )) {
        console.debug('Игнорируем сетевую ошибку:', reason.message || reason);
        event.preventDefault();
        return;
    }
    
    // Для других ошибок логируем подробно
    console.warn('Необработанная ошибка Promise:', reason);
    event.preventDefault(); // Предотвращаем дефолтное поведение браузера
});

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    setupUploadArea();
    setupFileInput();
    loadFiles();
    loadSchedule();
    loadReports();
    setDefaultScheduleTime();
    startCountdownUpdate();
    connectWebSocket();  // WebSocket для real-time обновлений (генерация + расписание)
    
    // Проверяем статус генерации с небольшой задержкой
    // чтобы страница и WebSocket успели инициализироваться
    setTimeout(() => {
        checkGenerationStatus();
    }, 500);
});

// ============================================================================
// WebSocket для real-time обновлений
// ============================================================================

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    ws = new WebSocket(wsUrl);
    
    ws.onopen = function() {
        console.log('WebSocket подключен');
        if (wsReconnectTimeout) {
            clearTimeout(wsReconnectTimeout);
            wsReconnectTimeout = null;
        }
    };
    
    ws.onmessage = function(event) {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };
    
    ws.onclose = function() {
        console.log('WebSocket отключен, попытка переподключения через 3 сек...');
        wsReconnectTimeout = setTimeout(connectWebSocket, 3000);
    };
    
    ws.onerror = function(error) {
        console.error('WebSocket ошибка:', error);
    };
}

function handleWebSocketMessage(data) {
    // Обработка уведомления об изменении расписания
    if (data.type === 'schedule_updated') {
        console.log('Расписание обновлено другим пользователем');
        loadSchedule();  // Перезагружаем расписание
        return;
    }
    
    // Обработка статуса генерации отчёта
    const status = data.status;
    
    if (status === 'started') {
        // Генерация началась
        showGenerationStatus();
        disableScheduleButtons();
        disableFileActions();  // Блокируем действия с файлами
    } else if (status === 'completed') {
        // Генерация завершена успешно
        hideGenerationStatus();
        enableScheduleButtons();
        enableFileActions();  // Разблокируем действия с файлами
        // Автоматически обновляем историю отчётов и список файлов
        setTimeout(() => {
            loadReports();
            loadFiles();  // Обновляем список файлов (они были удалены)
        }, 500);
        // Молча завершаем (без alert)
        console.log('✅ Отчёт успешно создан');
    } else if (status === 'failed') {
        // Генерация не удалась
        hideGenerationStatus();
        enableScheduleButtons();
        enableFileActions();  // Разблокируем действия с файлами
        showNotification('Ошибка при генерации отчёта: ' + (data.error || 'неизвестная ошибка'), 'error');
    }
}

function showGenerationStatus() {
    const statusDiv = document.getElementById('generationStatus');
    statusDiv.style.display = 'block';
}

function hideGenerationStatus() {
    const statusDiv = document.getElementById('generationStatus');
    statusDiv.style.display = 'none';
}

function disableScheduleButtons() {
    document.getElementById('setScheduleBtn').disabled = true;
    document.getElementById('generateNowBtn').disabled = true;
    document.getElementById('cancelScheduleBtn').disabled = true;
}

function enableScheduleButtons() {
    document.getElementById('setScheduleBtn').disabled = false;
    document.getElementById('generateNowBtn').disabled = false;
    document.getElementById('cancelScheduleBtn').disabled = false;
}

function disableFileActions() {
    // Блокируем drag-and-drop зону
    const uploadArea = document.getElementById('uploadArea');
    if (uploadArea) {
        uploadArea.classList.add('disabled');
        uploadArea.style.pointerEvents = 'none';
        uploadArea.style.opacity = '0.5';
    }
    
    // Блокируем кнопку "Загрузить файлы"
    const uploadFilesBtn = document.getElementById('uploadFilesBtn');
    if (uploadFilesBtn) {
        uploadFilesBtn.disabled = true;
    }
    
    // Блокируем input для выбора файлов
    const fileInput = document.getElementById('fileInput');
    if (fileInput) {
        fileInput.disabled = true;
    }
    
    // Блокируем все кнопки действий с файлами
    document.querySelectorAll('.file-actions .btn').forEach(btn => {
        btn.disabled = true;
    });
}

function enableFileActions() {
    // Разблокируем drag-and-drop зону
    const uploadArea = document.getElementById('uploadArea');
    if (uploadArea) {
        uploadArea.classList.remove('disabled');
        uploadArea.style.pointerEvents = 'auto';
        uploadArea.style.opacity = '1';
    }
    
    // Разблокируем кнопку "Загрузить файлы"
    const uploadFilesBtn = document.getElementById('uploadFilesBtn');
    if (uploadFilesBtn) {
        uploadFilesBtn.disabled = false;
    }
    
    // Разблокируем input для выбора файлов
    const fileInput = document.getElementById('fileInput');
    if (fileInput) {
        fileInput.disabled = false;
    }
    
    // Разблокируем все кнопки действий с файлами
    document.querySelectorAll('.file-actions .btn').forEach(btn => {
        btn.disabled = false;
    });
}

function showNotification(message, type = 'info') {
    // Простое уведомление через alert (можно улучшить позже)
    alert(message);
}

async function checkGenerationStatus() {
    // Проверяем статус генерации при загрузке страницы
    try {
        const response = await fetch('/api/generation-status');
        
        // Проверяем что запрос успешен
        if (!response.ok) {
            console.warn('Не удалось получить статус генерации:', response.status);
            return;
        }
        
        const data = await response.json();
        
        if (data.is_generating) {
            // Если идёт генерация, показываем индикатор и блокируем всё
            showGenerationStatus();
            disableScheduleButtons();
            disableFileActions();  // Блокируем действия с файлами
            console.log('Обнаружена активная генерация при загрузке страницы');
        }
    } catch (error) {
        // Молча игнорируем ошибки при проверке статуса
        // (может быть сервер ещё не готов или временная проблема сети)
        console.debug('Не удалось проверить статус генерации:', error.message);
    }
}

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
        
        // Молча обновляем список файлов (без alert)
        console.log(`Загружено ${data.files.length} файлов`);
        loadFiles();
        
    } catch (error) {
        console.error('Ошибка:', error);
        // Проверяем на сетевую ошибку
        if (error.message && error.message.includes('Failed to fetch')) {
            alert('⚠️ Проблема с подключением. Попробуйте ещё раз.');
        } else {
            alert('Ошибка при загрузке файлов: ' + error.message);
        }
    }
}

async function loadFiles() {
    const filesList = document.getElementById('filesList');
    
    try {
        const response = await fetch('/api/files');
        
        if (!response.ok) {
            console.warn('Не удалось загрузить список файлов:', response.status);
            filesList.innerHTML = '<p class="info-message">Загрузка файлов...</p>';
            return;
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
        // Молча обрабатываем ошибки (могут быть при перезагрузке страницы)
        console.debug('Не удалось загрузить список файлов:', error.message);
        filesList.innerHTML = '<p class="info-message">Загрузка файлов...</p>';
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
            console.warn('Не удалось загрузить расписание:', response.status);
            statusDiv.innerHTML = '<p class="info-message">Загрузка расписания...</p>';
            return;
        }
        
        const schedule = await response.json();
        
        if (schedule.is_enabled) {
            let html = '<div class="schedule-active">';
            html += '<h3>✅ Расписание активно</h3>';
            
            if (schedule.schedule_type === 'one_time') {
                const scheduledDate = new Date(schedule.scheduled_time);
                html += `<p><strong>Тип:</strong> Разовая задача</p>`;
                html += `<p><strong>Дата и время:</strong> ${scheduledDate.toLocaleString('ru-RU')}</p>`;
                
                // Сохраняем целевое время для countdown
                countdownTargetTime = scheduledDate;
            } else if (schedule.schedule_type === 'periodic') {
                // Конвертируем UTC время обратно в локальное для отображения
                // schedule.periodic_time = "11:00" (UTC)
                const [utcHours, utcMinutes] = schedule.periodic_time.split(':');
                const utcDate = new Date();
                utcDate.setUTCHours(parseInt(utcHours), parseInt(utcMinutes), 0, 0);
                
                // Получаем локальные часы:минуты
                const localHours = utcDate.getHours();
                const localMinutes = utcDate.getMinutes();
                const localTimeStr = `${String(localHours).padStart(2, '0')}:${String(localMinutes).padStart(2, '0')}`;
                
                html += `<p><strong>Тип:</strong> Периодическая задача (ежедневно)</p>`;
                html += `<p><strong>Время:</strong> ${localTimeStr}</p>`;
                
                // Вычисляем следующее срабатывание для countdown
                let nextRun = new Date();
                nextRun.setHours(localHours, localMinutes, 0, 0);
                
                if (nextRun <= new Date()) {
                    // Если время уже прошло сегодня, берем завтра
                    nextRun.setDate(nextRun.getDate() + 1);
                }
                
                countdownTargetTime = nextRun;
            }
            
            html += `<p><strong>Email:</strong> ${schedule.recipient_email || 'Не указан'}</p>`;
            html += '<p id="countdownText" class="countdown-text"></p>';
            html += '</div>';
            
            statusDiv.innerHTML = html;
    } else {
            statusDiv.innerHTML = '<div class="schedule-inactive"><p>❌ Расписание не установлено</p></div>';
            countdownTargetTime = null;  // Сбрасываем countdown
        }
        
    } catch (error) {
        // Молча обрабатываем ошибки (могут быть при перезагрузке страницы)
        console.debug('Не удалось загрузить расписание:', error.message);
        statusDiv.innerHTML = '<p class="info-message">Загрузка расписания...</p>';
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
        
        // Конвертируем локальное время в UTC
        // periodicTime = "15:00" (локальное время пользователя)
        const [hours, minutes] = periodicTime.split(':');
        const localDate = new Date();
        localDate.setHours(parseInt(hours), parseInt(minutes), 0, 0);
        
        // Получаем часы:минуты в UTC
        const utcHours = localDate.getUTCHours();
        const utcMinutes = localDate.getUTCMinutes();
        const utcTime = `${String(utcHours).padStart(2, '0')}:${String(utcMinutes).padStart(2, '0')}`;
        
        requestData.periodic_time = utcTime;
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
    // Проверяем, не идет ли уже генерация
    try {
        const statusResponse = await fetch('/api/generation-status');
        
        if (!statusResponse.ok) {
            console.warn('Не удалось проверить статус генерации');
            // Продолжаем выполнение, т.к. это не критично
        } else {
            const statusData = await statusResponse.json();
            
            if (statusData.is_generating) {
                alert('⏳ Подождите, идёт генерация отчёта...');
                return;
            }
        }
    } catch (error) {
        // Молча игнорируем ошибки проверки статуса
        console.debug('Не удалось проверить статус генерации:', error.message);
        // Продолжаем выполнение
    }
    
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
                
                // WebSocket сам покажет индикатор и обновит историю
                // Просто закрываем модальное окно
                closeModal();
                
            } catch (error) {
                // Проверяем тип ошибки
                if (error.message && error.message.includes('Failed to fetch')) {
                    // Сетевая ошибка - молча игнорируем (может быть при перезагрузке)
                    console.debug('Сетевая ошибка при запуске генерации:', error.message);
                    closeModal();
                } else {
                    // Реальная ошибка - показываем пользователю
                    console.error('Ошибка при запуске генерации:', error);
                    alert('Ошибка при запуске генерации: ' + error.message);
                }
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

function updateCountdown() {
    const countdownText = document.getElementById('countdownText');
    
    if (!countdownText || !countdownTargetTime) {
        return;
    }
    
    // Вычисляем разницу локально (без запросов к серверу)
    const now = new Date();
    const diffMs = countdownTargetTime - now;
    const secondsLeft = Math.floor(diffMs / 1000);
    
    if (secondsLeft > 0) {
        const hours = Math.floor(secondsLeft / 3600);
        const minutes = Math.floor((secondsLeft % 3600) / 60);
        const seconds = secondsLeft % 60;
        
        countdownText.innerHTML = `<strong>⏳ До генерации отчета:</strong> ${hours}ч ${minutes}м ${seconds}с`;
    } else if (secondsLeft > -60) {
        // В течение минуты после срабатывания показываем "Генерация..."
        countdownText.innerHTML = '<strong>⏳ Генерация отчета...</strong>';
    } else {
        // Если прошло больше минуты, перезагружаем расписание
        // (возможно уже завершилась и расписание обновилось)
        loadSchedule();
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
            console.warn('Не удалось загрузить отчеты:', response.status);
            reportsList.innerHTML = '<p class="info-message">Загрузка отчетов...</p>';
            return;
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
        // Молча обрабатываем ошибки (могут быть при перезагрузке страницы)
        console.debug('Не удалось загрузить отчеты:', error.message);
        reportsList.innerHTML = '<p class="info-message">Загрузка отчетов...</p>';
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
            html += '<details><summary>Исходные файлы (скачать)</summary><ul class="source-files-list">';
            report.archived_files.forEach(file => {
                html += `
                    <li>
                        📄 ${file}
                        <button class="btn btn-sm btn-download" onclick="downloadSourceFile(${report.id}, '${file}')">
                            ⬇ Скачать
                        </button>
                    </li>
                `;
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

function downloadSourceFile(reportId, filename) {
    // Скачивание исходного файла из архива
    const url = `/api/reports/${reportId}/files/${encodeURIComponent(filename)}`;
    window.location.href = url;
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
