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
        const inputDoc = document.getElementById('selected-document-type');
        const inputStyle = document.getElementById('selected-template-style');
        const btnAadhaar = document.getElementById('doc-btn-aadhaar');
        const btnAadhaarColor = document.getElementById('doc-btn-aadhaar-color');
        const btnAyushman = document.getElementById('doc-btn-ayushman');
        const uploadText = document.getElementById('upload-zone-text');
        const heroTitle = document.getElementById('hero-title');
        const heroDesc = document.getElementById('hero-desc');
        const pwDesc = document.getElementById('password-desc');
        
        window.clearPasswordError();

        // Reset all active classes
        if (btnAadhaar) btnAadhaar.classList.remove('active');
        if (btnAadhaarColor) btnAadhaarColor.classList.remove('active');
        if (btnAyushman) btnAyushman.classList.remove('active');
        const btnCrop = document.getElementById('doc-btn-crop');
        if (btnCrop) btnCrop.classList.remove('active');

        const instantCropContainer = document.getElementById('instant-autocrop-container');
        if (instantCropContainer) {
            instantCropContainer.style.display = (type === 'crop') ? 'block' : 'none';
        }

        if (type === 'crop') {
            if (inputDoc) inputDoc.value = 'crop';
            if (inputStyle) inputStyle.value = 'default';
            if (btnCrop) btnCrop.classList.add('active');
            if (uploadText) uploadText.textContent = 'Upload Voter, e-Shram, PAN, or DL PDF/Image';
            if (heroTitle) heroTitle.textContent = 'Auto Card Cropper (CR80 Edge-to-Edge)';
            if (heroDesc) heroDesc.textContent = 'Upload any document with existing PVC cards (Voter ID, e-Shram, PAN, DL). Auto-crops to exact CR80 size with 100% precision.';
            if (pwDesc) pwDesc.textContent = 'Enter PDF password if document is locked.';
            if (passwordHintPill) {
                passwordHintPill.textContent = 'Document Password (if locked)';
                passwordHintPill.style.color = '#5b21b6';
                passwordHintPill.style.background = '#f5f3ff';
                passwordHintPill.style.borderColor = '#ddd6fe';
            }
            if (fileInput) fileInput.accept = "application/pdf,image/png,image/jpeg,image/jpg";
        } else if (type === 'ayushman') {
            if (inputDoc) inputDoc.value = 'ayushman';
            if (inputStyle) inputStyle.value = 'default';
            if (btnAyushman) btnAyushman.classList.add('active');
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
            if (fileInput) fileInput.accept = "application/pdf";
        } else if (type === 'aadhaar_color' || type === 'color') {
            if (inputDoc) inputDoc.value = 'aadhaar';
            if (inputStyle) inputStyle.value = 'color';
            if (btnAadhaarColor) btnAadhaarColor.classList.add('active');
            if (uploadText) uploadText.textContent = 'Upload Aadhaar PDF (Colourful HD Card)';
            if (heroTitle) heroTitle.textContent = 'Create Vibrant Colourful Aadhaar Cards';
            if (heroDesc) heroDesc.textContent = 'Upload your Aadhaar PDF and PVC Card Pro will generate a stunning multicolor HD background layout ready for duplex print.';
            if (pwDesc) pwDesc.textContent = 'Some Aadhaar PDFs are protected. Enter the PDF password if required.';
            if (passwordHintPill) {
                passwordHintPill.textContent = 'Aadhaar Hint: NAME4 + YOB (e.g. SURE1995)';
                passwordHintPill.style.color = '#92400e';
                passwordHintPill.style.background = '#fef3c7';
                passwordHintPill.style.borderColor = '#fde68a';
            }
            if (fileInput) fileInput.accept = "application/pdf";
        } else {
            if (inputDoc) inputDoc.value = 'aadhaar';
            if (inputStyle) inputStyle.value = 'default';
            if (btnAadhaar) btnAadhaar.classList.add('active');
            if (uploadText) uploadText.textContent = 'Upload Aadhaar PDF (Standard White)';
            if (heroTitle) heroTitle.textContent = 'Create Professional PVC Cards in Seconds';
            if (heroDesc) heroDesc.textContent = 'Upload your Aadhaar PDF and PVC Card Pro will securely extract the required details, prepare the card design and generate print-ready files.';
            if (pwDesc) pwDesc.textContent = 'Some Aadhaar PDFs are protected. Enter the PDF password if required.';
            if (passwordHintPill) {
                passwordHintPill.textContent = 'Aadhaar Hint: NAME4 + YOB (e.g. SURE1995)';
                passwordHintPill.style.color = '#1e40af';
                passwordHintPill.style.background = '#eff6ff';
                passwordHintPill.style.borderColor = '#bfdbfe';
            }
            if (fileInput) fileInput.accept = "application/pdf";
        }
    };

    const docBtnAadhaar = document.getElementById('doc-btn-aadhaar');
    const docBtnAadhaarColor = document.getElementById('doc-btn-aadhaar-color');
    const docBtnAyushman = document.getElementById('doc-btn-ayushman');
    const docBtnCrop = document.getElementById('doc-btn-crop');
    if (docBtnAadhaar) {
        docBtnAadhaar.addEventListener('click', (e) => {
            e.preventDefault();
            window.setDocumentType('aadhaar');
        });
    }
    if (docBtnAadhaarColor) {
        docBtnAadhaarColor.addEventListener('click', (e) => {
            e.preventDefault();
            window.setDocumentType('aadhaar_color');
        });
    }
    if (docBtnAyushman) {
        docBtnAyushman.addEventListener('click', (e) => {
            e.preventDefault();
            window.setDocumentType('ayushman');
        });
    }
    if (docBtnCrop) {
        docBtnCrop.addEventListener('click', (e) => {
            e.preventDefault();
            window.setDocumentType('crop');
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
            const currentDocType = (document.getElementById('selected-document-type')?.value || 'aadhaar').toLowerCase();
            
            if (currentDocType === 'crop') {
                const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
                const isImg = file.type.startsWith('image/') || /\.(png|jpe?g|webp)$/i.test(file.name);
                if (!isPdf && !isImg) {
                    window.showToast('Please select a valid PDF or Image file (PNG/JPG).', 'error');
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
                filesizeDisplay.textContent = `${fileSizeMB} MB • Ready to crop`;
                fileDropArea.classList.add('has-file');
                Array.from(fileDropArea.children).forEach(c => { if(c.tagName !== 'INPUT') c.style.display = 'none'; });
                fileInfo.style.display = 'flex';
                uploadBtn.disabled = false;
                
                // Directly launch the interactive crop preview
                launchCropPreview(file);
                return;
            }

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
            
            // Fire the pipeline request immediately
            const generatePromise = fetch('/generate', {
                method: 'POST',
                body: formData
            });

            // Fast smooth visual progress indicators
            setStepState(0, 'completed');
            setStepState(1, 'active');
            
            // Wait for PVC generation to finish
            const response = await generatePromise;
            setStepState(1, 'completed');
            setStepState(2, 'completed');
            setStepState(3, 'completed');
            
            if (response.status === 401) {
                window.location.href = '/login';
                return;
            }
            if (response.status === 402) {
                throw new Error("Insufficient credits to generate a card. Please top up your account.");
            }
            
            let data;
            try {
                data = await response.json();
            } catch (jsonErr) {
                throw new Error("Server communication issue or timeout. Please check your file and try again.");
            }

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
            currentA4Url = data.pdf_url || `/download-pdf/${currentRunId}`;

            setStepState(4, 'completed');
            await sleep(300); // smooth transition to results

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
            startExpiryCountdown(300); // 5 Minutes Zero-Retention Privacy Timer
            
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

    // Zero-Retention Expiry Countdown Manager
    let expiryInterval = null;
    let isSessionExpired = false;

    function resetDownloadButtons() {
        isSessionExpired = false;
        if (frontPreview) {
            frontPreview.style.filter = 'none';
        }
        if (backPreview) {
            backPreview.style.filter = 'none';
        }
        [btnDlFront, btnDlBack, btnDlA4].forEach(btn => {
            if (btn) {
                btn.disabled = false;
                btn.style.opacity = '1';
                btn.style.cursor = 'pointer';
                btn.style.pointerEvents = 'auto';
            }
        });
        if (btnDlFront) {
            btnDlFront.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg> Download Front (PNG)`;
        }
        if (btnDlBack) {
            btnDlBack.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg> Download Back (PNG)`;
        }
        if (btnDlA4) {
            btnDlA4.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg> Download A4 Print File (PDF)`;
        }
    }

    function lockSessionAsExpired() {
        isSessionExpired = true;
        const timerEl = document.getElementById('expiry-timer-text');
        const badgeEl = document.getElementById('expiry-badge');

        if (timerEl) timerEl.textContent = '00:00 (Expired)';
        if (badgeEl) {
            badgeEl.style.background = '#fef2f2';
            badgeEl.style.borderColor = '#fecaca';
            badgeEl.style.color = '#dc2626';
        }

        // 1. Permanently disable and lock download buttons
        [btnDlFront, btnDlBack, btnDlA4].forEach(btn => {
            if (btn) {
                btn.disabled = true;
                btn.style.opacity = '0.45';
                btn.style.cursor = 'not-allowed';
                btn.style.pointerEvents = 'none';
            }
        });
        if (btnDlFront) btnDlFront.innerHTML = '🔒 Expired';
        if (btnDlBack) btnDlBack.innerHTML = '🔒 Expired';
        if (btnDlA4) btnDlA4.innerHTML = '🔒 Session Expired - Files Purged';

        // 2. Blur / shield previews to guarantee citizen data privacy
        if (frontPreview) frontPreview.style.filter = 'blur(14px) grayscale(80%)';
        if (backPreview) backPreview.style.filter = 'blur(14px) grayscale(80%)';

        // 3. Immediately trigger backend purge
        if (currentRunId) {
            fetch(`/api/purge-run/${currentRunId}`, { method: 'POST' }).catch(() => {});
        }

        // 4. Pop up zero-retention privacy modal
        showExpiredModal();
    }

    function startExpiryCountdown(durationSeconds = 300) {
        if (expiryInterval) clearInterval(expiryInterval);
        resetDownloadButtons();
        let remaining = durationSeconds;
        const timerEl = document.getElementById('expiry-timer-text');
        const badgeEl = document.getElementById('expiry-badge');
        
        function updateDisplay() {
            const mins = Math.floor(remaining / 60);
            const secs = remaining % 60;
            const formatted = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
            if (timerEl) timerEl.textContent = formatted;

            if (badgeEl) {
                if (remaining <= 60) {
                    badgeEl.style.background = '#fef2f2';
                    badgeEl.style.borderColor = '#fecaca';
                    badgeEl.style.color = '#dc2626';
                } else if (remaining <= 120) {
                    badgeEl.style.background = '#fffbeb';
                    badgeEl.style.borderColor = '#fde68a';
                    badgeEl.style.color = '#d97706';
                } else {
                    badgeEl.style.background = '#eff6ff';
                    badgeEl.style.borderColor = '#bfdbfe';
                    badgeEl.style.color = '#1e40af';
                }
            }
        }

        updateDisplay();
        expiryInterval = setInterval(() => {
            remaining--;
            if (remaining <= 0) {
                clearInterval(expiryInterval);
                lockSessionAsExpired();
            } else {
                updateDisplay();
            }
        }, 1000);
    }

    // Expired Modal Helpers
    const expiredModal = document.getElementById('expired-modal');
    const btnModalReupload = document.getElementById('btn-modal-reupload');
    const btnModalClose = document.getElementById('btn-modal-close');

    function showExpiredModal() {
        if (expiredModal) expiredModal.style.display = 'flex';
    }

    function hideExpiredModal() {
        if (expiredModal) expiredModal.style.display = 'none';
    }

    if (btnModalReupload) {
        btnModalReupload.addEventListener('click', () => {
            hideExpiredModal();
            btnStartOver.click();
        });
    }

    if (btnModalClose) {
        btnModalClose.addEventListener('click', () => {
            hideExpiredModal();
        });
    }

    if (expiredModal) {
        expiredModal.addEventListener('click', (e) => {
            if (e.target === expiredModal) hideExpiredModal();
        });
    }

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

    // Robust Binary Blob Download Helper with Expired Session Interception
    async function triggerDownload(url, filename, btnElement = null) {
        if (isSessionExpired) {
            lockSessionAsExpired();
            return;
        }

        let originalText = '';
        if (btnElement) {
            originalText = btnElement.innerHTML;
            btnElement.disabled = true;
            btnElement.innerHTML = `
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="animation: spin 1s linear infinite;"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>
                Downloading...
            `;
        }
        try {
            const res = await fetch(url);
            
            // Check if file was purged / 404 / 410 / expired
            if (res.status === 404 || res.status === 410) {
                lockSessionAsExpired();
                return;
            }

            if (!res.ok) {
                throw new Error('File download failed from server.');
            }

            const blob = await res.blob();
            const blobUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = blobUrl;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            setTimeout(() => {
                document.body.removeChild(a);
                window.URL.revokeObjectURL(blobUrl);
            }, 300);
            window.showToast(`${filename} downloaded successfully!`, 'success');
        } catch (err) {
            console.error('Download error:', err);
            window.showToast('Unable to download file. Please generate a new card.', 'error');
        } finally {
            if (btnElement && !isSessionExpired) {
                btnElement.disabled = false;
                btnElement.innerHTML = originalText;
            }
        }
    }

    btnDlFront.addEventListener('click', () => {
        if (isSessionExpired) { lockSessionAsExpired(); return; }
        if (currentFrontUrl && currentRunId) {
            triggerDownload(currentFrontUrl, `PVC_Front_${currentRunId.substring(0, 8)}.png`, btnDlFront);
        }
    });

    btnDlBack.addEventListener('click', () => {
        if (isSessionExpired) { lockSessionAsExpired(); return; }
        if (currentBackUrl && currentRunId) {
            triggerDownload(currentBackUrl, `PVC_Back_${currentRunId.substring(0, 8)}.png`, btnDlBack);
        }
    });

    btnDlA4.addEventListener('click', () => {
        if (isSessionExpired) { lockSessionAsExpired(); return; }
        if (currentA4Url && currentRunId) {
            triggerDownload(currentA4Url, `PVC_Card_Print_${currentRunId.substring(0, 8)}.pdf`, btnDlA4);
        }
    });

    // Start Over
    btnStartOver.addEventListener('click', () => {
        if (expiryInterval) clearInterval(expiryInterval);
        resetDownloadButtons();
        uploadForm.reset();
        fileInput.value = '';
        currentRunId = null;
        currentFrontUrl = null;
        currentBackUrl = null;
        currentA4Url = null;
        if (frontPreview) frontPreview.src = '';
        if (backPreview) {
            backPreview.src = '';
            if (backPreview.parentElement && backPreview.parentElement.parentElement) {
                backPreview.parentElement.parentElement.style.display = 'block';
            }
        }
        window.clearPasswordError();
        updateFileInfo();
        resultSection.style.display = 'none';
        if (processingSection) processingSection.style.display = 'none';
        if (cropEditorSection) cropEditorSection.style.display = 'none';
        uploadSection.style.display = 'block';
    });

    // =========================================================
    // SMART CROPPER INTERACTIVE CONTROLLER
    // =========================================================
    const cropEditorSection = document.getElementById('crop-editor-section');
    const cropperPageWrapper = document.getElementById('cropper-page-wrapper');
    const cropperPreviewImage = document.getElementById('cropper-preview-image');
    const frontCropBox = document.getElementById('front-crop-box');
    const backCropBox = document.getElementById('back-crop-box');
    const btnSubmitCrop = document.getElementById('btn-submit-crop');
    const btnCropReupload = document.getElementById('btn-crop-reupload');
    const cropModeSelect = document.getElementById('crop-mode-select');
    const btnTargetFront = document.getElementById('btn-target-front');
    const btnTargetBack = document.getElementById('btn-target-back');

    let cropBoxes = {
        front: { x: 0.1824, y: 0.0696, w: 0.3880, h: 0.1878 },
        back:  { x: 0.1824, y: 0.2615, w: 0.3880, h: 0.1872 }
    };
    let cropPresetsMap = {
        voter: { front: { x: 0.076, y: 0.582, w: 0.412, h: 0.185 }, back: { x: 0.512, y: 0.582, w: 0.412, h: 0.185 } },
        eshram: { front: { x: 0.1824, y: 0.0696, w: 0.3880, h: 0.1878 }, back: { x: 0.1824, y: 0.2615, w: 0.3880, h: 0.1872 } },
        pan_dual: { front: { x: 0.1137, y: 0.7721, w: 0.4032, h: 0.1761 }, back: { x: 0.5169, y: 0.7721, w: 0.3952, h: 0.1761 } },
        pan_single: { front: { x: 0.1137, y: 0.7721, w: 0.4032, h: 0.1761 }, back: null },
        dl: { front: { x: 0.078, y: 0.330, w: 0.412, h: 0.185 }, back: { x: 0.510, y: 0.330, w: 0.412, h: 0.185 } },
        custom: { front: { x: 0.1824, y: 0.0696, w: 0.3880, h: 0.1878 }, back: { x: 0.1824, y: 0.2615, w: 0.3880, h: 0.1872 } }
    };
    let activeBoxTarget = 'front';
    let isDualCropMode = true;
    let cropTempId = null;
    let cropFileExt = '.pdf';
    let currentPresetKey = 'custom';

    // Renders the box positions in pixels over the rendered preview image
    function renderCropBoxes() {
        if (!cropperPreviewImage || !cropperPreviewImage.clientWidth) return;
        const imgW = cropperPreviewImage.clientWidth;
        const imgH = cropperPreviewImage.clientHeight;
        
        // Front Box
        if (frontCropBox) {
            const fb = cropBoxes.front;
            frontCropBox.style.left = `${fb.x * imgW}px`;
            frontCropBox.style.top = `${fb.y * imgH}px`;
            frontCropBox.style.width = `${fb.w * imgW}px`;
            frontCropBox.style.height = `${fb.h * imgH}px`;
        }

        // Back Box
        if (backCropBox) {
            if (isDualCropMode && cropBoxes.back) {
                backCropBox.style.display = 'block';
                const bb = cropBoxes.back;
                backCropBox.style.left = `${bb.x * imgW}px`;
                backCropBox.style.top = `${bb.y * imgH}px`;
                backCropBox.style.width = `${bb.w * imgW}px`;
                backCropBox.style.height = `${bb.h * imgH}px`;
            } else {
                backCropBox.style.display = 'none';
            }
        }
    }

    // Set Active Focus Box
    window.setActiveBoxTarget = function(target) {
        activeBoxTarget = target;
        if (btnTargetFront && btnTargetBack) {
            if (target === 'front') {
                btnTargetFront.style.background = '#2563eb';
                btnTargetFront.style.color = '#ffffff';
                btnTargetBack.style.background = '#f8fafc';
                btnTargetBack.style.color = '#64748b';
                frontCropBox?.classList.add('active-focus');
                backCropBox?.classList.remove('active-focus');
            } else {
                btnTargetBack.style.background = '#10b981';
                btnTargetBack.style.color = '#ffffff';
                btnTargetFront.style.background = '#f8fafc';
                btnTargetFront.style.color = '#64748b';
                backCropBox?.classList.add('active-focus');
                frontCropBox?.classList.remove('active-focus');
            }
        }
    };

    // Toggle Dual vs Single Mode
    window.toggleCropMode = function(mode) {
        isDualCropMode = (mode === 'dual');
        if (cropModeSelect) cropModeSelect.value = mode;
        if (btnTargetBack) btnTargetBack.style.display = isDualCropMode ? 'inline-block' : 'none';
        if (!isDualCropMode && activeBoxTarget === 'back') {
            window.setActiveBoxTarget('front');
        }
        renderCropBoxes();
    };

    // Preset Selection
    window.applyCropPreset = function(presetKey) {
        currentPresetKey = presetKey;
        document.querySelectorAll('.preset-chip-btn').forEach(btn => {
            if (btn.getAttribute('data-preset') === presetKey) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        if (cropPresetsMap[presetKey]) {
            const p = cropPresetsMap[presetKey];
            cropBoxes.front = { ...p.front };
            if (p.back) {
                cropBoxes.back = { ...p.back };
                window.toggleCropMode('dual');
            } else {
                window.toggleCropMode('single');
            }
        } else {
            // Standard fallback presets
            if (presetKey === 'pan_single') {
                cropBoxes.front = { x: 0.1137, y: 0.7721, w: 0.4032, h: 0.1761 };
                window.toggleCropMode('single');
            } else if (presetKey === 'pan_dual') {
                cropBoxes.front = { x: 0.1137, y: 0.7721, w: 0.4032, h: 0.1761 };
                cropBoxes.back  = { x: 0.5169, y: 0.7721, w: 0.3952, h: 0.1761 };
                window.toggleCropMode('dual');
            } else if (presetKey === 'eshram') {
                cropBoxes.front = { x: 0.1824, y: 0.0696, w: 0.3880, h: 0.1878 };
                cropBoxes.back  = { x: 0.1824, y: 0.2615, w: 0.3880, h: 0.1872 };
                window.toggleCropMode('dual');
            } else if (presetKey === 'abha') {
                cropBoxes.front = { x: 0.0186, y: 0.0158, w: 0.9628, h: 0.4775 };
                cropBoxes.back  = { x: 0.0186, y: 0.5067, w: 0.9628, h: 0.4783 };
                window.toggleCropMode('dual');
            } else if (presetKey === 'dl') {
                cropBoxes.front = { x: 0.078, y: 0.330, w: 0.412, h: 0.185 };
                cropBoxes.back  = { x: 0.510, y: 0.330, w: 0.412, h: 0.185 };
                window.toggleCropMode('dual');
            } else {
                cropBoxes.front = { x: 0.076, y: 0.582, w: 0.412, h: 0.185 };
                cropBoxes.back  = { x: 0.512, y: 0.582, w: 0.412, h: 0.185 };
                window.toggleCropMode('dual');
            }
        }
        renderCropBoxes();
    };

    // Nudge Box
    window.nudgeActiveBox = function(dx_px, dy_px) {
        if (!cropperPreviewImage || !cropperPreviewImage.clientWidth) return;
        const imgW = cropperPreviewImage.clientWidth;
        const imgH = cropperPreviewImage.clientHeight;
        const b = cropBoxes[activeBoxTarget];
        if (!b) return;

        b.x = Math.max(0, Math.min(1.0 - b.w, b.x + (dx_px / imgW)));
        b.y = Math.max(0, Math.min(1.0 - b.h, b.y + (dy_px / imgH)));
        renderCropBoxes();
    };

    // Resize Box
    window.resizeActiveBox = function(factor) {
        const b = cropBoxes[activeBoxTarget];
        if (!b) return;
        const nw = Math.max(0.1, Math.min(0.95, b.w * factor));
        const nh = Math.max(0.05, Math.min(0.95, b.h * factor));
        const cx = b.x + b.w / 2;
        const cy = b.y + b.h / 2;
        b.w = nw;
        b.h = nh;
        b.x = Math.max(0, Math.min(1.0 - nw, cx - nw / 2));
        b.y = Math.max(0, Math.min(1.0 - nh, cy - nh / 2));
        renderCropBoxes();
    };

    // Reset Box
    window.resetActiveBox = function() {
        window.applyCropPreset(currentPresetKey);
    };

    // Drag and Resize Events
    function initBoxInteractions(boxEl, targetKey) {
        let isDragging = false;
        let isResizing = false;
        let resizeHandle = null;
        let startX = 0, startY = 0;
        let origBox = {};

        function onPointerDown(e) {
            window.setActiveBoxTarget(targetKey);
            const handle = e.target.closest('.crop-handle');
            if (handle) {
                isResizing = true;
                resizeHandle = handle.getAttribute('data-handle');
            } else {
                isDragging = true;
            }
            startX = e.clientX || (e.touches && e.touches[0] ? e.touches[0].clientX : 0);
            startY = e.clientY || (e.touches && e.touches[0] ? e.touches[0].clientY : 0);
            origBox = { ...cropBoxes[targetKey] };
            document.addEventListener('pointermove', onPointerMove);
            document.addEventListener('pointerup', onPointerUp);
            e.preventDefault();
        }

        function onPointerMove(e) {
            if (!isDragging && !isResizing) return;
            const curX = e.clientX || (e.touches && e.touches[0] ? e.touches[0].clientX : 0);
            const curY = e.clientY || (e.touches && e.touches[0] ? e.touches[0].clientY : 0);
            const dx = curX - startX;
            const dy = curY - startY;
            const imgW = cropperPreviewImage.clientWidth;
            const imgH = cropperPreviewImage.clientHeight;
            if (!imgW || !imgH) return;

            const b = cropBoxes[targetKey];

            if (isDragging) {
                b.x = Math.max(0, Math.min(1.0 - origBox.w, origBox.x + (dx / imgW)));
                b.y = Math.max(0, Math.min(1.0 - origBox.h, origBox.y + (dy / imgH)));
            } else if (isResizing) {
                let nw = origBox.w;
                let nh = origBox.h;
                if (resizeHandle.includes('r')) {
                    nw = Math.max(0.1, origBox.w + (dx / imgW));
                } else if (resizeHandle.includes('l')) {
                    const candidateW = origBox.w - (dx / imgW);
                    if (candidateW > 0.1) {
                        nw = candidateW;
                        b.x = origBox.x + (dx / imgW);
                    }
                }
                
                // Maintain CR80 ratio
                const cardRatio = 1.5858;
                nh = (nw * imgW) / (cardRatio * imgH);
                
                if (resizeHandle.includes('t')) {
                    b.y = origBox.y + (origBox.h - nh);
                }
                b.w = Math.min(1.0 - b.x, nw);
                b.h = Math.min(1.0 - b.y, nh);
            }
            renderCropBoxes();
        }

        function onPointerUp() {
            isDragging = false;
            isResizing = false;
            document.removeEventListener('pointermove', onPointerMove);
            document.removeEventListener('pointerup', onPointerUp);
        }

        boxEl.addEventListener('pointerdown', onPointerDown);
    }

    if (frontCropBox) initBoxInteractions(frontCropBox, 'front');
    if (backCropBox) initBoxInteractions(backCropBox, 'back');

    // Launch Crop Preview API Call
    async function launchCropPreview(file) {
        uploadSection.style.display = 'none';
        if (cropEditorSection) cropEditorSection.style.display = 'none';
        if (processingSection) {
            processingSection.style.display = 'block';
            const h = processingSection.querySelector('h3');
            const p = processingSection.querySelector('p');
            if (h) h.textContent = 'Detecting PVC Cards...';
            if (p) p.textContent = 'Rendering high-resolution document and scanning card cut boundaries.';
        }

        const formData = new FormData();
        formData.append('file', file);
        if (pdfPasswordInput && pdfPasswordInput.value) {
            formData.append('password', pdfPasswordInput.value);
        }
        formData.append('preset', currentPresetKey);

        try {
            const resp = await fetch('/api/crop/upload-preview', {
                method: 'POST',
                body: formData
            });
            const data = await resp.json();

            if (!resp.ok || !data.success) {
                if (processingSection) processingSection.style.display = 'none';
                uploadSection.style.display = 'block';
                if (data.code === 'PASSWORD_REQUIRED' || data.code === 'INCORRECT_PASSWORD') {
                    window.showPasswordError(data.code === 'PASSWORD_REQUIRED' ? 'required' : 'incorrect', data.error);
                } else {
                    window.showToast(data.error || 'Failed to load document preview.', 'error');
                }
                return;
            }

            cropTempId = data.temp_id;
            cropFileExt = data.file_ext || '.pdf';
            if (data.presets) cropPresetsMap = data.presets;

            if (data.detected_type) {
                currentPresetKey = data.detected_type;
                document.querySelectorAll('.preset-chip-btn').forEach(btn => {
                    if (btn.getAttribute('data-preset') === data.detected_type) {
                        btn.classList.add('active');
                    } else {
                        btn.classList.remove('active');
                    }
                });
            }

            if (data.detected) {
                const label = data.detected_label || 'Card';
                window.showToast(`⚡ Auto-detected ${label} with 100% precision!`, 'success');
                const detectBadge = document.getElementById('crop-auto-detect-badge');
                if (detectBadge) {
                    detectBadge.style.display = 'inline-flex';
                    detectBadge.innerHTML = `✨ <strong>Auto-Detected:</strong>&nbsp;${label} (100% Snapped)`;
                }
            }

            // Set Initial Boxes
            if (data.front_box) cropBoxes.front = { ...data.front_box };
            if (data.back_box) {
                cropBoxes.back = { ...data.back_box };
                window.toggleCropMode('dual');
            } else {
                window.toggleCropMode('single');
            }

            // 1-Click Direct Auto-Crop Check:
            const isInstantCrop = document.getElementById('chk-instant-autocrop')?.checked;
            if (isInstantCrop && data.detected) {
                if (processingSection) {
                    const h = processingSection.querySelector('h3');
                    const p = processingSection.querySelector('p');
                    if (h) h.textContent = `Auto-Detected: ${data.detected_label || 'Card'}!`;
                    if (p) p.textContent = 'Card borders detected with 100% precision. Generating high-resolution PVC Card and A4 print file...';
                }
                setTimeout(() => {
                    btnSubmitCrop?.click();
                }, 300);
                return;
            }

            // Load Preview Image
            cropperPreviewImage.onload = () => {
                if (processingSection) processingSection.style.display = 'none';
                if (cropEditorSection) cropEditorSection.style.display = 'block';
                renderCropBoxes();
                window.setActiveBoxTarget('front');
            };
            cropperPreviewImage.src = data.preview_url;

        } catch (err) {
            if (processingSection) processingSection.style.display = 'none';
            uploadSection.style.display = 'block';
            window.showToast(`Preview error: ${err.message}`, 'error');
        }
    }

    // Re-upload Button in Crop Editor
    if (btnCropReupload) {
        btnCropReupload.addEventListener('click', () => {
            if (cropEditorSection) cropEditorSection.style.display = 'none';
            uploadSection.style.display = 'block';
            fileInput.value = '';
            updateFileInfo();
        });
    }

    // Submit Crop Generation
    if (btnSubmitCrop) {
        btnSubmitCrop.addEventListener('click', async () => {
            if (!cropTempId) {
                window.showToast('Session error. Please upload file again.', 'error');
                return;
            }

            if (cropEditorSection) cropEditorSection.style.display = 'none';
            if (processingSection) {
                processingSection.style.display = 'block';
                const h = processingSection.querySelector('h3');
                const p = processingSection.querySelector('p');
                if (h) h.textContent = 'Cropping & Rendering PVC Card...';
                if (p) p.textContent = 'Generating 300 DPI razor-sharp CR80 card and aligning A4 print sheet.';
            }

            const formData = new FormData();
            formData.append('temp_id', cropTempId);
            formData.append('file_ext', cropFileExt);
            formData.append('front_box', JSON.stringify(cropBoxes.front));
            formData.append('back_box', isDualCropMode && cropBoxes.back ? JSON.stringify(cropBoxes.back) : '');
            formData.append('card_type', currentPresetKey);
            if (pdfPasswordInput && pdfPasswordInput.value) {
                formData.append('password', pdfPasswordInput.value);
            }

            try {
                const resp = await fetch('/api/crop/generate', {
                    method: 'POST',
                    body: formData
                });
                const res = await resp.json();

                if (!resp.ok || !res.success) {
                    if (processingSection) processingSection.style.display = 'none';
                    if (cropEditorSection) cropEditorSection.style.display = 'block';
                    window.showToast(res.error || 'Crop generation failed.', 'error');
                    return;
                }

                // SUCCESS STATE
                currentRunId = res.run_id;
                currentFrontUrl = res.front_url;
                currentBackUrl = res.back_url;
                currentA4Url = res.pdf_url;

                if (frontPreview) frontPreview.src = res.front_url;
                if (backPreview) {
                    if (res.has_back && res.back_url) {
                        backPreview.src = res.back_url;
                        if (backPreview.parentElement && backPreview.parentElement.parentElement) {
                            backPreview.parentElement.parentElement.style.display = 'block';
                        }
                    } else {
                        if (backPreview.parentElement && backPreview.parentElement.parentElement) {
                            backPreview.parentElement.parentElement.style.display = 'none';
                        }
                    }
                }

                // Update wallet balance if available
                if (res.wallet_balance !== undefined) {
                    const balEls = document.querySelectorAll('.wallet-balance-amount, #user-wallet-display, #header-wallet-amount');
                    balEls.forEach(el => el.textContent = `₹${parseFloat(res.wallet_balance).toFixed(2)}`);
                }

                if (processingSection) processingSection.style.display = 'none';
                if (resultSection) resultSection.style.display = 'block';

                startExpiryCountdown(300);
                window.showToast('✅ PVC Card cropped & generated successfully!', 'success');

            } catch (err) {
                if (processingSection) processingSection.style.display = 'none';
                if (cropEditorSection) cropEditorSection.style.display = 'block';
                window.showToast(`Generation failed: ${err.message}`, 'error');
            }
        });
    }

    // Window resize observer for responsive crop box resizing
    window.addEventListener('resize', () => {
        if (cropEditorSection && cropEditorSection.style.display !== 'none') {
            renderCropBoxes();
        }
    });
});



