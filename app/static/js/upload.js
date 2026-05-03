document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const fileList = document.getElementById('file-list');
    const uploadBtn = document.getElementById('upload-btn');
    const uploadForm = document.getElementById('upload-form');
    const progressDiv = document.getElementById('upload-progress');
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');
    const newCatBtn = document.getElementById('new-cat-btn');
    const newCatForm = document.getElementById('new-cat-form');
    const createCatBtn = document.getElementById('create-cat-btn');
    const categorySelect = document.getElementById('category-select');

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
        const files = Array.from(e.dataTransfer.files);
        addFiles(files);
    });

    dropZone.addEventListener('click', (e) => {
        // Don't double-trigger when the label or the file input itself is clicked
        if (e.target.tagName === 'LABEL' || e.target === fileInput) return;
        fileInput.click();
    });

    fileInput.addEventListener('change', () => {
        addFiles(Array.from(fileInput.files));
        fileInput.value = '';
    });

    function addFiles(files) {
        selectedFiles = selectedFiles.concat(files);
        renderFileList();
        uploadBtn.disabled = selectedFiles.length === 0;
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
                uploadBtn.disabled = selectedFiles.length === 0;
            });
        });
    }

    // Upload
    uploadForm.addEventListener('submit', e => {
        e.preventDefault();
        if (selectedFiles.length === 0) return;

        const formData = new FormData();
        const category = categorySelect.value || 'general';
        formData.append('category', category);
        selectedFiles.forEach(f => formData.append('files', f));

        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/api/upload');

        progressDiv.classList.remove('hidden');
        uploadBtn.disabled = true;

        xhr.upload.addEventListener('progress', e => {
            if (e.lengthComputable) {
                const pct = Math.round((e.loaded / e.total) * 100);
                progressBar.style.width = pct + '%';
                progressText.textContent = `Uploading... ${pct}%`;
            }
        });

        xhr.addEventListener('load', () => {
            if (xhr.status === 200) {
                let res;
                try {
                    res = JSON.parse(xhr.responseText);
                } catch (e) {
                    progressText.textContent = 'Session expired. Please reload the page and log in again.';
                    uploadBtn.disabled = false;
                    return;
                }
                const count = (res.uploaded || []).length;
                const errors = (res.errors || []);
                if (errors.length > 0) {
                    const msgs = errors.map(e => e.error).join('; ');
                    progressText.textContent = `${count} file(s) uploaded. Errors: ${msgs}`;
                } else {
                    progressText.textContent = `Done! ${count} file(s) uploaded.`;
                }
                progressBar.style.width = '100%';
                selectedFiles = [];
                renderFileList();
                setTimeout(() => window.location.reload(), 1500);
            } else {
                progressText.textContent = 'Upload failed. Please try again.';
                uploadBtn.disabled = false;
            }
        });

        xhr.addEventListener('error', () => {
            progressText.textContent = 'Upload failed. Please try again.';
            uploadBtn.disabled = false;
        });

        xhr.send(formData);
    });

    // New category
    newCatBtn.addEventListener('click', () => {
        newCatForm.classList.toggle('hidden');
    });

    createCatBtn.addEventListener('click', async () => {
        const name = document.getElementById('new-cat-name').value.trim();
        if (!name) return;

        const formData = new FormData();
        formData.append('name', name);

        const res = await fetch('/api/category', { method: 'POST', body: formData });
        if (res.ok) {
            const cat = await res.json();
            const option = document.createElement('option');
            option.value = cat.name;
            option.textContent = cat.name + ' (0 files)';
            option.selected = true;
            categorySelect.appendChild(option);
            document.getElementById('new-cat-name').value = '';
            newCatForm.classList.add('hidden');
        }
    });

    function formatSize(bytes) {
        if (bytes === 0) return '0 B';
        const units = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(1024));
        return (bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1) + ' ' + units[i];
    }
});
