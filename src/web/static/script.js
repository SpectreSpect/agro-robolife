let currentJobId = null;
let uploadedFiles = [];

document.addEventListener('DOMContentLoaded', function() {
    loadHistory();
    setupUploadArea();
    setupFileInput();
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
        hideProcessingStatus();
        
        // Убеждаемся, что кнопка обработки активна
        const processBtn = document.getElementById('processBtn');
        processBtn.disabled = false;
        
    } catch (error) {
        console.error('Ошибка:', error);
        alert('Ошибка при загрузке файлов: ' + error.message);
        hideProcessingStatus();
    }
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
    
    // Сброс состояния кнопки обработки
    const processBtn = document.getElementById('processBtn');
    processBtn.disabled = false;
}

async function processFiles() {
    if (!currentJobId) {
        alert('Сначала загрузите файлы');
        return;
    }
    
    const processBtn = document.getElementById('processBtn');
    processBtn.disabled = true;
    
    try {
        showProcessingStatus('Обработка файлов...');
        
        const response = await fetch(`/api/process/${currentJobId}`, {
            method: 'POST'
        });
        
        if (!response.ok) {
            throw new Error('Ошибка при обработке файлов');
        }
        
        const data = await response.json();
        
        await waitForCompletion(currentJobId);
        
        hideProcessingStatus();
        clearFiles();
        loadHistory();
        
        alert('Обработка завершена! Файл доступен для скачивания в истории.');
        
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
    
    const date = new Date(job.created_at).toLocaleString('ru-RU');
    const statusClass = `status-${job.status}`;
    const statusText = {
        'pending': 'Ожидание',
        'processing': 'Обработка',
        'completed': 'Завершено',
        'failed': 'Ошибка'
    }[job.status];
    
    let html = `
        <div class="history-header">
            <div class="history-date">📅 ${date}</div>
            <span class="status-badge ${statusClass}">${statusText}</span>
        </div>
        <div class="history-details">
            <p><strong>Файлов загружено:</strong> ${job.input_files ? job.input_files.length : 0}</p>
    `;
    
    if (job.status === 'completed') {
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
    
    if (job.status === 'completed') {
        html += `
            <button class="btn btn-info btn-sm" onclick="downloadFile(${job.id})">
                ⬇️ Скачать результат
            </button>
        `;
    }
    
    html += `
        <button class="btn btn-danger btn-sm" onclick="deleteJob(${job.id})">
            🗑️ Удалить
        </button>
    </div>`;
    
    div.innerHTML = html;
    return div;
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
    if (!confirm('Удалить эту обработку?')) {
        return;
    }
    
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

