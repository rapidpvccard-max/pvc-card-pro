document.addEventListener('DOMContentLoaded', () => {
    // Inject Toast Container
    if (!document.getElementById('toast-container')) {
        const toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        document.body.appendChild(toastContainer);
    }
    
    // Global Toast Function
    window.showToast = function(message, type = 'info') {
        const container = document.getElementById('toast-container');
        if (!container) return;
        
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        let icon = 'ℹ️';
        if (type === 'success') icon = '✅';
        if (type === 'error') icon = '⚠️';
        if (type === 'warning') icon = '🚧';
        
        toast.innerHTML = `
            <div class="toast-icon">${icon}</div>
            <div class="toast-message">${message}</div>
        `;
        
        container.appendChild(toast);
        
        // Trigger animation
        requestAnimationFrame(() => {
            toast.classList.add('show');
        });
        
        // Remove after 4 seconds
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => {
                if (toast.parentNode === container) {
                    container.removeChild(toast);
                }
            }, 300);
        }, 4000);
    };

    // Password Error Handling Helpers
    const pdfPasswordInput = document.getElementById('pdf-password');
    const passwordErrorBox = document.getElementById('password-error-box');
    const passwordErrorTitle = document.getElementById('password-error-title');
    const passwordErrorDesc = document.getElementById('password-error-desc');
    const passwordHintGuide = document.getElementById('password-hint-guide');
    const passwordHintPill = document.getElementById('password-hint-pill');
    const passwordGroupContainer = document.getElementById('password-group-container');

    window.showPasswordError = function(type = 'incorrect', customMessage = null) {
        if (!passwordErrorBox || !pdfPasswordInput) return;
        
        const docType = (document.getElementById('selected-document-type')?.value || 'aadhaar').toLowerCase();
        
        if (type === 'required') {
            if (passwordErrorTitle) passwordErrorTitle.textContent = '🔒 Password Required! Kripya PDF Password Dalein';
            if (passwordErrorDesc) passwordErrorDesc.textContent = customMessage || 'Yeh PDF password se protected hai. Kripya unlock karne ke liye password enter karein.';
        } else {
            if (passwordErrorTitle) passwordErrorTitle.textContent = '⚠️ Galat Password! Kripya Sahi Password Dalein';
            if (passwordErrorDesc) passwordErrorDesc.textContent = customMessage || 'PDF unlock nahi hui. Kripya sahi password enter karke dobara koshish karein.';
        }

        if (passwordHintGuide) {
            if (docType === 'ayushman') {
                passwordHintGuide.innerHTML = '💡 <strong>Ayushman PDF:</strong> Agar aapka PDF password protected hai to sahi password enter karein.';
            } else {
                passwordHintGuide.innerHTML = '💡 <strong>Aadhaar Password Format:</strong> Naam ke pehle 4 Akshar CAPITAL me + Janm ka Saal (YYYY).<br><span style="display: inline-block; margin-top: 3px;">Udaharan: <em>SURESH (1995) &rarr;</em> <strong style="font-family: monospace; letter-spacing: 1px; background: #fee2e2; padding: 2px 6px; border-radius: 4px; color: #b91c1c; border: 1px solid #fca5a5;">SURE1995</strong></span>';
            }
        }

        passwordErrorBox.style.display = 'block';
        pdfPasswordInput.classList.add('is-invalid');
        
        // Ensure error box is visible to user immediately
        passwordErrorBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

        if (passwordGroupContainer) {
            passwordGroupContainer.classList.remove('shake-animation');
            void passwordGroupContainer.offsetWidth; // trigger reflow
            passwordGroupContainer.classList.add('shake-animation');
        }

        // Smooth focus
        setTimeout(() => {
            pdfPasswordInput.focus();
            pdfPasswordInput.select();
        }, 120);
    };

    window.clearPasswordError = function() {
        if (passwordErrorBox) passwordErrorBox.style.display = 'none';
        if (pdfPasswordInput) pdfPasswordInput.classList.remove('is-invalid');
        if (passwordGroupContainer) passwordGroupContainer.classList.remove('shake-animation');
    };

    if (pdfPasswordInput) {
        pdfPasswordInput.addEventListener('input', () => {
            window.clearPasswordError();
        });
    }

    // Global password toggle
    window.togglePassword = function() {
        const input = document.getElementById('pdf-password');
        if (!input) return;
        input.type = input.type === 'password' ? 'text' : 'password';
    };

    // Document Type Selector Handler
    window.setDocumentType = function(type) {
        const input = document.getElementById('selected-document-type');
        if (input) input.value = type;
        const btnAadhaar = document.getElementById('doc-btn-aadhaar');
        const btnAyushman = document.getElementById('doc-btn-ayushman');
        const uploadText = document.getElementById('upload-zone-text');
        const heroTitle = document.getElementById('hero-title');
        const heroDesc = document.getElementById('hero-desc');
        const pwDesc = document.getElementById('password-desc');
        
        window.clearPasswordError();

        if (type === 'ayushman') {
            if (btnAyushman) btnAyushman.classList.add('active');
            if (btnAadhaar) btnAadhaar.classList.remove('active');
            if (uploadText) uploadText.textContent = 'Upload Ayushman PDF';
            if (heroTitle) heroTitle.textContent = 'Create Professional Ayushman PVC Cards';
            if (heroDesc) heroDesc.textContent = 'Upload your Ayushman / PM-JAY PDF and PVC Card Pro will extract the required details and generate print-ready files.';
            if (pwDesc) pwDesc.textContent = 'Enter the PDF password if your Ayushman PDF is protected.';
            if (passwordHintPill) {
                passwordHintPill.textContent = 'Ayushman Password (if locked)';
                passwordHintPill.style.color = '#065f46';
                passwordHintPill.style.background = '#d1fae5';
                passwordHintPill.style.borderColor = '#a7f3d0';
            }
        } else {
            if (btnAadhaar) btnAadhaar.classList.add('active');
            if (btnAyushman) btnAyushman.classList.remove('active');
            if (uploadText) uploadText.textContent = 'Upload Aadhaar PDF';
            if (heroTitle) heroTitle.textContent = 'Create Professional PVC Cards in Seconds';
            if (heroDesc) heroDesc.textContent = 'Upload your Aadhaar PDF and PVC Card Pro will securely extract the required details, prepare the card design and generate print-ready files.';
            if (pwDesc) pwDesc.textContent = 'Some Aadhaar PDFs are protected. Enter the PDF password if required.';
            if (passwordHintPill) {
                passwordHintPill.textContent = 'Aadhaar Hint: NAME4 + YOB (e.g. SURE1995)';
                passwordHintPill.style.color = '#1e40af';
                passwordHintPill.style.background = '#eff6ff';
                passwordHintPill.style.borderColor = '#bfdbfe';
            }
        }
    };

    const docBtnAadhaar = document.getElementById('doc-btn-aadhaar');
    const docBtnAyushman = document.getElementById('doc-btn-ayushman');
    if (docBtnAadhaar) {
        docBtnAadhaar.addEventListener('click', (e) => {
            e.preventDefault();
            window.setDocumentType('aadhaar');
        });
    }
    if (docBtnAyushman) {
        docBtnAyushman.addEventListener('click', (e) => {
            e.preventDefault();
            window.setDocumentType('ayushman');
        });
    }

    // API Status Check
    const systemStatus = document.getElementById('system-status');
    const statusContainer = document.querySelector('.status-container');
    
    if (systemStatus && statusContainer) {
        fetch('/health')
            .then(response => response.json())
            .then(data => {
                if (data.success && data.status === 'online') {
                    systemStatus.textContent = 'System Online';
                    statusContainer.classList.add('online');
                    statusContainer.classList.remove('offline');
                } else {
                    throw new Error('API Offline');
                }
            })
            .catch(() => {
                systemStatus.textContent = 'System Offline';
                statusContainer.classList.add('offline');
                statusContainer.classList.remove('online');
            });
    }

    // Elements
    const fileDropArea = document.getElementById('file-drop-area');
    const fileInput = document.getElementById('pdf-file');
    const fileInfo = document.getElementById('file-info');
    const filenameDisplay = document.getElementById('filename-display');
    const filesizeDisplay = document.getElementById('filesize-display');
    const btnRemoveFile = document.getElementById('btn-remove-file');
    const uploadForm = document.getElementById('upload-form');
    const uploadBtn = document.getElementById('upload-btn');
    
    const uploadSection = document.getElementById('upload-section');
    const processingSection = document.getElementById('processing-section');
    const resultSection = document.getElementById('result-section');
    
    // Preview Elements
    const frontPreview = document.getElementById('front-preview');
    const backPreview = document.getElementById('back-preview');
    
    // Download Buttons
    const btnDlFront = document.getElementById('btn-dl-front');
    const btnDlBack = document.getElementById('btn-dl-back');
    const btnDlA4 = document.getElementById('btn-dl-a4');
    const btnStartOver = document.getElementById('btn-start-over');
    
    let currentRunId = null;
    let currentFrontUrl = null;
    let currentBackUrl = null;
    let currentA4Url = null;

    // Drag and Drop
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        fileDropArea.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        fileDropArea.addEventListener(eventName, () => {
            fileDropArea.classList.add('dragover');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        fileDropArea.addEventListener(eventName, () => {
            fileDropArea.classList.remove('dragover');
        }, false);
    });

    fileDropArea.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            fileInput.files = files;
            updateFileInfo();
        }
    });

    fileInput.addEventListener('change', updateFileInfo);

    if(btnRemoveFile) {
        btnRemoveFile.addEventListener('click', () => {
            fileInput.value = '';
            updateFileInfo();
        });
    }

    function updateFileInfo() {
        if (typeof window.clearPasswordError === 'function') {
            window.clearPasswordError();
        }
        if (fileInput.files.length > 0) {
            const file = fileInput.files[0];
            
            if (file.type !== 'application/pdf') {
                window.showToast('That file doesn\'t appear to be a valid PDF. Please select a genuine Aadhaar PDF.', 'error');
                fileInput.value = '';
                fileDropArea.classList.remove('has-file');
                fileInfo.style.display = 'none';
                uploadBtn.disabled = true;
                return;
            }
            
            const fileSizeMB = (file.size / (1024 * 1024)).toFixed(2);
            if (file.size > 10 * 1024 * 1024) {
                window.showToast(`File is larger than the 10 MB limit.`, 'error');
                fileInput.value = '';
                fileDropArea.classList.remove('has-file');
                fileInfo.style.display = 'none';
                uploadBtn.disabled = true;
                return;
            }
            
            filenameDisplay.textContent = file.name;
            filesizeDisplay.textContent = `${fileSizeMB} MB`;
            fileDropArea.classList.add('has-file');
            // fileDropArea.querySelector('.saas-upload-text').style.display = 'none';
            Array.from(fileDropArea.children).forEach(c => { if(c.tagName !== 'INPUT') c.style.display = 'none'; });
            
            fileInfo.style.display = 'flex';
            uploadBtn.disabled = false;
        } else {
            fileDropArea.classList.remove('has-file');
            //
            Array.from(fileDropArea.children).forEach(c => { if(c.tagName !== 'INPUT') c.style.display = 'block'; });
            
            fileInfo.style.display = 'none';
            uploadBtn.disabled = true;
        }
    }

    // Progress Tracker Logic
    const wfSteps = [
        { id: 'wf-step-1' }, // Upload
        { id: 'wf-step-2' }, // Extract
        { id: 'wf-step-3' }, // Create PVC
        { id: 'wf-step-4' }, // A4 Print
        { id: 'wf-step-5' }  // Download
    ];
    
    function setStepState(stepIndex, state) {
        if (!wfSteps[stepIndex]) return;
        const step = document.getElementById(wfSteps[stepIndex].id);
        if (!step) return;
        
        const icon = step.querySelector('.step-icon') || step.querySelector('.step-icon-circle');
        
        if (state === 'active') {
            step.classList.add('active');
            step.classList.remove('completed');
            step.style.opacity = '1';
            if (icon) {
                icon.style.background = '#2563eb';
                icon.style.color = '#ffffff';
            }
        } else if (state === 'completed') {
            step.classList.remove('active');
            step.classList.add('completed');
            step.style.opacity = '1';
            if (icon) {
                icon.style.background = '#10b981';
                icon.style.color = '#ffffff';
            }
        } else {
            step.classList.remove('active');
            step.classList.remove('completed');
            step.style.opacity = '0.5';
            if (icon) {
                icon.style.background = '#f1f5f9';
                icon.style.color = '#64748b';
            }
        }
    }

    function resetProgress() {
        setStepState(0, 'active');
        for (let i = 1; i < wfSteps.length; i++) {
            setStepState(i, null);
        }
    }

    function sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    uploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        if (fileInput.files.length === 0) {
            window.showToast('Please select an Aadhaar PDF.', 'warning');
            return;
        }

        const formData = new FormData(uploadForm);
        
        // ENTER PROCESSING STATE
        uploadSection.style.display = 'none';
        if(processingSection) processingSection.style.display = 'block';
        document.getElementById('workflow-indicator').style.display = 'flex';
        resetProgress();

        try {
            // STEP 1: Upload PDF
            setStepState(0, 'active');
            await sleep(500); 
            
            // Fire the actual pipeline request in the background
            const generatePromise = fetch('/generate', {
                method: 'POST',
                body: formData
            });

            // Visually advance steps based on time/heuristics since we don't have websocket events
            setStepState(0, 'completed');
            setStepState(1, 'active');
            await sleep(800);
            
            setStepState(1, 'completed');
            setStepState(2, 'active');
            await sleep(800);
            
            setStepState(2, 'completed');
            setStepState(3, 'active');

            // Wait for PVC generation to finish
            const response = await generatePromise;
            
            if (response.status === 401) {
                window.location.href = '/login';
                return;
            }
            if (response.status === 402) {
                throw new Error("Insufficient credits to generate a card. Please top up your account.");
            }
            
            const data = await response.json();

            if (!response.ok || !data.success) {
                const errCode = data.code || '';
                const rawErr = (data.error || '').toLowerCase();
                const isPwError = errCode === 'INCORRECT_PASSWORD' || 
                                  errCode === 'PASSWORD_REQUIRED' || 
                                  rawErr.includes('password') || 
                                  rawErr.includes('authenticate') ||
                                  rawErr.includes('unlock');

                if (isPwError) {
                    const pwType = (errCode === 'PASSWORD_REQUIRED' || rawErr.includes('protected') || rawErr.includes('supply')) ? 'required' : 'incorrect';
                    const friendly = pwType === 'required' ? 
                        'Yeh PDF password protected hai. Kripya document ka password enter karein.' : 
                        'Galat password! Kripya sahi password dalein (Please enter correct password).';
                    const err = new Error(friendly);
                    err.isPasswordError = true;
                    err.passwordType = pwType;
                    throw err;
                }

                throw new Error(getFriendlyErrorMsg(data.error));
            }
            
            currentRunId = data.run_id;
            currentFrontUrl = data.front_url;
            currentBackUrl = data.back_url;

            setStepState(3, 'completed');
            setStepState(4, 'active');

            // Wait for A4 layout generation
            const a4Response = await fetch('/generate-a4', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ run_id: currentRunId, cards_count: 1, mirror_duplex: false })
            });
            const a4Data = await a4Response.json();

            if (!a4Response.ok || !a4Data.success) {
                throw new Error("Unable to create A4 Print layout. " + getFriendlyErrorMsg(a4Data.error));
            }
            
            currentA4Url = a4Data.pdf_url;
            setStepState(4, 'completed');
            
            await sleep(400); // final pause before showing results

            // SUCCESS STATE
            
            // Populate previews (add timestamp to bust cache with auto-retry)
            const bustTime = Date.now();
            frontPreview.style.opacity = '0';
            backPreview.style.opacity = '0';
            
            frontPreview.onload = () => { frontPreview.style.transition = 'opacity 0.3s ease'; frontPreview.style.opacity = '1'; };
            backPreview.onload = () => { backPreview.style.transition = 'opacity 0.3s ease'; backPreview.style.opacity = '1'; };
            
            frontPreview.onerror = () => {
                setTimeout(() => { frontPreview.src = data.front_url + "?retry=1&t=" + Date.now(); }, 400);
            };
            backPreview.onerror = () => {
                setTimeout(() => { backPreview.src = data.back_url + "?retry=1&t=" + Date.now(); }, 400);
            };

            frontPreview.src = data.front_url + "?t=" + bustTime;
            backPreview.src = data.back_url + "?t=" + bustTime;
            
            if(processingSection) processingSection.style.display = 'none';
            resultSection.style.display = 'block';
            
        } catch (error) {
            console.error('Generation Error:', error);
            // Revert back to upload section with error
            if(processingSection) processingSection.style.display = 'none';
            uploadSection.style.display = 'block';

            if (error.isPasswordError) {
                window.showPasswordError(error.passwordType, error.message);
                window.showToast(error.message, 'error');
            } else {
                window.showToast(error.message, 'error');
            }
        }
    });

    function getFriendlyErrorMsg(rawError) {
        if (!rawError) return 'Unable to generate PVC card. Please try again.';
        const lower = rawError.toLowerCase();
        if (lower.includes('credit')) {
            return rawError;
        }
        if (lower.includes('password') || lower.includes('authenticate')) {
            return 'Incorrect PDF password or unable to unlock the PDF.';
        }
        if (lower.includes('magic bytes') || lower.includes('valid pdf')) {
            return 'This PDF could not be processed. Please ensure it is a valid Aadhaar PDF.';
        }
        if (lower.includes('size')) {
            return 'File size must be 10 MB or less.';
        }
        return 'Unable to generate PVC card. Please try again.';
    }

    // Download Helpers
    function triggerDownload(url, filename) {
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    btnDlFront.addEventListener('click', () => {
        if (currentFrontUrl) triggerDownload(currentFrontUrl, `Aadhaar_Front_${currentRunId.substring(0,6)}.png`);
    });

    btnDlBack.addEventListener('click', () => {
        if (currentBackUrl) triggerDownload(currentBackUrl, `Aadhaar_Back_${currentRunId.substring(0,6)}.png`);
    });

    btnDlA4.addEventListener('click', () => {
        if (currentA4Url) triggerDownload(currentA4Url, `PVC_Print_${currentRunId.substring(0,8)}.pdf`);
    });

    // Start Over
    btnStartOver.addEventListener('click', () => {
        uploadForm.reset();
        fileInput.value = '';
        currentRunId = null;
        currentFrontUrl = null;
        currentBackUrl = null;
        currentA4Url = null;
        window.clearPasswordError();
        updateFileInfo();
        resultSection.style.display = 'none';
        if(processingSection) processingSection.style.display = 'none';
        uploadSection.style.display = 'block';
    });
});



