document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const fileList = document.getElementById('file-list');
    const submitBtn = document.getElementById('submit-btn');
    const browseBtn = document.getElementById('browse-btn');
    const submitForm = document.getElementById('submit-form');
    const errorMsg = document.getElementById('error-msg');

    const ALLOWED_EXT = ['.py', '.ipynb'];
    let selectedFiles = [];

    // Drag and drop
    ['dragenter', 'dragover'].forEach(evt => {
        dropZone.addEventListener(evt, e => {
            e.preventDefault();
            dropZone.classList.add('drag-over');
        });
    });

    ['dragleave', 'drop'].forEach(evt => {
        dropZone.addEventListener(evt, e => {
            e.preventDefault();
            dropZone.classList.remove('drag-over');
        });
    });

    dropZone.addEventListener('drop', e => {
        addFiles(Array.from(e.dataTransfer.files));
    });

    dropZone.addEventListener('click', () => fileInput.click());
    browseBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        fileInput.click();
    });

    fileInput.addEventListener('change', () => {
        addFiles(Array.from(fileInput.files));
        fileInput.value = '';
    });

    function addFiles(files) {
        for (const f of files) {
            const ext = '.' + f.name.split('.').pop().toLowerCase();
            if (!ALLOWED_EXT.includes(ext)) {
                showError(`"${f.name}" is not allowed. Only .py and .ipynb files.`);
                continue;
            }
            // Replace if same name already selected
            selectedFiles = selectedFiles.filter(sf => sf.name !== f.name);
            selectedFiles.push(f);
        }
        renderFileList();
        updateSubmitBtn();
    }

    function renderFileList() {
        fileList.innerHTML = selectedFiles.map((f, i) => `
            <div class="flex items-center justify-between bg-gray-50 rounded px-3 py-2 text-sm">
                <span class="text-gray-700 truncate">${f.name} <span class="text-gray-400">(${formatSize(f.size)})</span></span>
                <button type="button" data-index="${i}" class="remove-file text-red-400 hover:text-red-600 ml-2">&times;</button>
            </div>
        `).join('');

        fileList.querySelectorAll('.remove-file').forEach(btn => {
            btn.addEventListener('click', () => {
                selectedFiles.splice(parseInt(btn.dataset.index), 1);
                renderFileList();
                updateSubmitBtn();
            });
        });
    }

    function updateSubmitBtn() {
        submitBtn.disabled = selectedFiles.length === 0;
        hideError();
    }

    function showError(msg) {
        errorMsg.textContent = msg;
        errorMsg.classList.remove('hidden');
    }

    function hideError() {
        errorMsg.classList.add('hidden');
    }

    // Override form submission to attach files from drag-drop
    submitForm.addEventListener('submit', e => {
        e.preventDefault();
        if (selectedFiles.length === 0) {
            showError('Please select at least one file.');
            return;
        }

        const formData = new FormData(submitForm);
        // Remove default file input and add our selected files
        formData.delete('files');
        selectedFiles.forEach(f => formData.append('files', f));

        submitBtn.disabled = true;
        submitBtn.textContent = 'Submitting...';

        fetch('/api/tp/submit', { method: 'POST', body: formData })
            .then(res => {
                if (res.redirected) {
                    window.location.href = res.url;
                } else if (!res.ok) {
                    return res.json().then(data => {
                        throw new Error(data.detail || 'Submission failed');
                    });
                } else {
                    window.location.href = '/tp';
                }
            })
            .catch(err => {
                showError(err.message);
                submitBtn.disabled = false;
                submitBtn.textContent = 'Submit Work';
            });
    });

    function formatSize(bytes) {
        if (bytes === 0) return '0 B';
        const units = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(1024));
        return (bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1) + ' ' + units[i];
    }
});
