/**
 * RecruitFlow - Drag & Drop Resume File Uploader
 * Features:
 *  - Interactive drag-and-drop zone with visual hover states
 *  - Client-side validation: format (.pdf, .docx) & size (<10MB)
 *  - Dynamic file chip list with individual remove buttons
 *  - Loading spinner indicator on submit to prevent duplicate screening runs
 */

document.addEventListener('DOMContentLoaded', () => {
  const dropzone = document.getElementById('resumeDropzone');
  const fileInput = document.getElementById('resumeFileInput') || (dropzone ? dropzone.querySelector('input[type="file"]') : null) || document.querySelector('input[name="resumes"]') || document.querySelector('input[type="file"]');
  const fileListContainer = document.getElementById('selectedFilesList');
  const uploadForm = document.getElementById('resumeUploadForm') || document.querySelector('form[enctype="multipart/form-data"]');
  const submitBtn = document.getElementById('btnSubmitUpload') || uploadForm?.querySelector('button[type="submit"]');

  if (!dropzone || !fileInput) return;

  // Track selected files using DataTransfer
  let dt = new DataTransfer();

  // Prevent default drag behaviors across document
  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, preventDefaults, false);
    document.body.addEventListener(eventName, preventDefaults, false);
  });

  function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
  }

  // Highlight dropzone on dragover
  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, () => dropzone.classList.add('dropzone-active'), false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, () => dropzone.classList.remove('dropzone-active'), false);
  });

  // Handle dropped files
  dropzone.addEventListener('drop', (e) => {
    const files = e.dataTransfer.files;
    handleFiles(files);
  });

  // Handle standard file picker
  fileInput.addEventListener('change', (e) => {
    handleFiles(e.target.files);
  });

  function handleFiles(files) {
    const maxSizeBytes = 10 * 1024 * 1024; // 10 MB
    const allowedExts = ['pdf', 'docx'];

    Array.from(files).forEach(file => {
      const ext = file.name.split('.').pop().toLowerCase();

      if (!allowedExts.includes(ext)) {
        showToast(`Invalid file type: "${file.name}". Only PDF and DOCX files are allowed.`, 'error');
        return;
      }

      if (file.size > maxSizeBytes) {
        showToast(`File "${file.name}" exceeds maximum allowed size of 10MB.`, 'error');
        return;
      }

      // Check for duplicates
      let isDuplicate = false;
      for (let i = 0; i < dt.items.length; i++) {
        if (dt.items[i].getAsFile()?.name === file.name) {
          isDuplicate = true;
          break;
        }
      }

      if (!isDuplicate) {
        dt.items.add(file);
      }
    });

    fileInput.files = dt.files;
    renderFileList();
  }

  function renderFileList() {
    if (!fileListContainer) return;
    fileListContainer.innerHTML = '';

    if (dt.files.length === 0) {
      fileListContainer.style.display = 'none';
      return;
    }

    fileListContainer.style.display = 'flex';

    Array.from(dt.files).forEach((file, index) => {
      const chip = document.createElement('div');
      chip.className = 'file-chip';

      const sizeStr = (file.size / (1024 * 1024)).toFixed(2) + ' MB';

      chip.innerHTML = `
        <span class="file-chip-icon">📄</span>
        <span class="file-chip-name" title="${file.name}">${file.name}</span>
        <span class="file-chip-size">(${sizeStr})</span>
        <button type="button" class="file-chip-remove" data-index="${index}" aria-label="Remove">✕</button>
      `;

      chip.querySelector('.file-chip-remove').addEventListener('click', (e) => {
        const removeIndex = parseInt(e.target.dataset.index, 10);
        removeFile(removeIndex);
      });

      fileListContainer.appendChild(chip);
    });
  }

  function removeFile(index) {
    const newDt = new DataTransfer();
    for (let i = 0; i < dt.files.length; i++) {
      if (i !== index) {
        newDt.items.add(dt.files[i]);
      }
    }
    dt = newDt;
    fileInput.files = dt.files;
    renderFileList();
  }

  // Prevent double submissions & show AI screening spinner
  if (uploadForm && submitBtn) {
    uploadForm.addEventListener('submit', () => {
      submitBtn.disabled = true;
      submitBtn.innerHTML = `
        <span class="spinner" style="display:inline-block;width:14px;height:14px;border:2px solid #fff;border-top-color:transparent;border-radius:50%;animation:spin 0.8s linear infinite;margin-right:8px;vertical-align:middle;"></span>
        Extracting & Screening with AI...
      `;
    });
  }
});
