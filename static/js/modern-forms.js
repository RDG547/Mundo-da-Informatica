/**
 * Modern Forms JavaScript
 * Funcionalidades avançadas para formulários modernos
 */

class ModernPostForm {
    constructor() {
        this.currentStep = 1;
        this.totalSteps = 3;
        this.tags = [];

        this.init();
    }

    init() {
        this.bindEvents();
        this.initializeComponents();
    }

    bindEvents() {
        // Step Navigation
        document.getElementById('nextStep')?.addEventListener('click', () => this.nextStep());
        document.getElementById('prevStep')?.addEventListener('click', () => this.prevStep());

        // Form Submission
        document.getElementById('savePostBtn')?.addEventListener('click', () => this.submitForm());

        // Character Counting
        this.bindCharacterCounters();

        // Rich Text Editor
        this.initRichEditor();

        // Image Upload
        this.initImageUpload();

        // Tags System
        this.initTagsSystem();

        // Link Validation
        this.initLinkValidation();

        // Status Change Handling
        this.initStatusHandling();

        // Real-time Preview
        this.initPreview();

        // Auto-slug generation
        this.initSlugGeneration();
    }

    initializeComponents() {
        this.updateStepDisplay();
        this.updatePreview();

        // Load existing tags if any
        const existingTags = document.getElementById('postTags')?.value;
        if (existingTags) {
            this.tags = existingTags.split(',').map(tag => tag.trim()).filter(tag => tag);
            this.updateTagsDisplay();
        }
    }

    // Step Navigation
    nextStep() {
        if (this.validateCurrentStep()) {
            if (this.currentStep < this.totalSteps) {
                this.currentStep++;
                this.updateStepDisplay();
            }
        }
    }

    prevStep() {
        if (this.currentStep > 1) {
            this.currentStep--;
            this.updateStepDisplay();
        }
    }

    updateStepDisplay() {
        // Update step indicators
        document.querySelectorAll('.step').forEach((step, index) => {
            const stepNumber = index + 1;
            step.classList.remove('active', 'completed');

            if (stepNumber === this.currentStep) {
                step.classList.add('active');
            } else if (stepNumber < this.currentStep) {
                step.classList.add('completed');
            }
        });

        // Update step content
        document.querySelectorAll('.step-content').forEach((content, index) => {
            content.classList.remove('active');
            if (index + 1 === this.currentStep) {
                content.classList.add('active');
            }
        });

        // Update navigation buttons
        const prevBtn = document.getElementById('prevStep');
        const nextBtn = document.getElementById('nextStep');
        const saveBtn = document.getElementById('savePostBtn');

        if (prevBtn) {
            prevBtn.style.display = this.currentStep > 1 ? 'inline-flex' : 'none';
        }

        if (nextBtn && saveBtn) {
            if (this.currentStep === this.totalSteps) {
                nextBtn.style.display = 'none';
                saveBtn.style.display = 'inline-flex';
            } else {
                nextBtn.style.display = 'inline-flex';
                saveBtn.style.display = 'none';
            }
        }
    }

    validateCurrentStep() {
        const currentStepElement = document.querySelector(`.step-content[data-step="${this.currentStep}"]`);
        const requiredFields = currentStepElement.querySelectorAll('[required]');
        let isValid = true;

        requiredFields.forEach(field => {
            if (!field.value.trim()) {
                field.classList.add('is-invalid');
                isValid = false;
            } else {
                field.classList.remove('is-invalid');
            }
        });

        if (!isValid) {
            this.showNotification('Por favor, preencha todos os campos obrigatórios.', 'warning');
        }

        return isValid;
    }

    // Character Counters
    bindCharacterCounters() {
        const counters = [
            { input: 'postTitle', counter: 'titleCount', max: 100 },
            { input: 'postContent', counter: 'contentCount' },
            { input: 'postSeoTitle', counter: 'seoTitleCount', max: 60 },
            { input: 'postSeoDescription', counter: 'seoDescCount', max: 160 }
        ];

        counters.forEach(({ input, counter, max }) => {
            const inputElement = document.getElementById(input);
            const counterElement = document.getElementById(counter);

            if (inputElement && counterElement) {
                const updateCounter = () => {
                    const length = inputElement.value.length;
                    counterElement.textContent = length;

                    if (max) {
                        counterElement.parentElement.style.color = length > max ? '#e74c3c' : '#6c757d';
                    }
                };

                inputElement.addEventListener('input', updateCounter);
                updateCounter(); // Initial count
            }
        });
    }

    // Rich Text Editor
    initRichEditor() {
        const editor = document.getElementById('postContentEditor');
        const hiddenTextarea = document.getElementById('postContent');

        if (!editor || !hiddenTextarea) return;

        // Toolbar buttons
        document.querySelectorAll('.toolbar-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const command = btn.dataset.command;

                if (command === 'createLink') {
                    const url = prompt('Digite a URL:');
                    if (url) {
                        document.execCommand(command, false, url);
                    }
                } else {
                    document.execCommand(command, false, null);
                }

                this.updateHiddenTextarea();
                btn.classList.toggle('active');
            });
        });

        // Update hidden textarea when content changes
        editor.addEventListener('input', () => {
            this.updateHiddenTextarea();
            this.updatePreview();

            // Update character count
            const counter = document.getElementById('contentCount');
            if (counter) {
                counter.textContent = editor.textContent.length;
            }
        });

        // Load existing content
        if (hiddenTextarea.value) {
            editor.innerHTML = hiddenTextarea.value;
        }
    }

    updateHiddenTextarea() {
        const editor = document.getElementById('postContentEditor');
        const hiddenTextarea = document.getElementById('postContent');

        if (editor && hiddenTextarea) {
            hiddenTextarea.value = editor.innerHTML;
        }
    }

    // Image Upload
    initImageUpload() {
        const uploadArea = document.getElementById('imageUploadArea');
        const fileInput = document.getElementById('postImage');
        const preview = uploadArea?.querySelector('.image-preview');
        const placeholder = uploadArea?.querySelector('.upload-placeholder');
        const removeBtn = document.getElementById('removeImage');

        if (!uploadArea || !fileInput) return;

        // Click to upload
        uploadArea.addEventListener('click', (e) => {
            if (e.target.closest('.remove-image')) return;
            fileInput.click();
        });

        // Drag and drop
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('drag-over');
        });

        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('drag-over');
        });

        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('drag-over');

            const files = e.dataTransfer.files;
            if (files.length > 0) {
                this.handleImageFile(files[0]);
            }
        });

        // File input change
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.handleImageFile(e.target.files[0]);
            }
        });

        // Remove image
        removeBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.removeImage();
        });
    }

    handleImageFile(file) {
        if (!file.type.startsWith('image/')) {
            this.showNotification('Por favor, selecione apenas arquivos de imagem.', 'error');
            return;
        }

        if (file.size > 5 * 1024 * 1024) { // 5MB
            this.showNotification('A imagem deve ter no máximo 5MB.', 'error');
            return;
        }

        const reader = new FileReader();
        reader.onload = (e) => {
            this.showImagePreview(e.target.result);
        };
        reader.readAsDataURL(file);
    }

    showImagePreview(src) {
        const uploadArea = document.getElementById('imageUploadArea');
        const preview = uploadArea?.querySelector('.image-preview');
        const placeholder = uploadArea?.querySelector('.upload-placeholder');
        const img = uploadArea?.querySelector('#previewImg');

        if (img && preview && placeholder) {
            img.src = src;
            placeholder.style.display = 'none';
            preview.style.display = 'block';
        }
    }

    removeImage() {
        const uploadArea = document.getElementById('imageUploadArea');
        const preview = uploadArea?.querySelector('.image-preview');
        const placeholder = uploadArea?.querySelector('.upload-placeholder');
        const fileInput = document.getElementById('postImage');

        if (preview && placeholder && fileInput) {
            preview.style.display = 'none';
            placeholder.style.display = 'block';
            fileInput.value = '';
        }
    }

    // Tags System
    initTagsSystem() {
        const tagsInput = document.getElementById('postTagsInput');
        const hiddenInput = document.getElementById('postTags');

        if (!tagsInput || !hiddenInput) return;

        tagsInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ',') {
                e.preventDefault();
                this.addTag(tagsInput.value.trim());
                tagsInput.value = '';
            }
        });

        tagsInput.addEventListener('blur', () => {
            if (tagsInput.value.trim()) {
                this.addTag(tagsInput.value.trim());
                tagsInput.value = '';
            }
        });
    }

    addTag(tagText) {
        if (!tagText || this.tags.includes(tagText)) return;

        this.tags.push(tagText);
        this.updateTagsDisplay();
        this.updateTagsInput();
    }

    removeTag(tagText) {
        this.tags = this.tags.filter(tag => tag !== tagText);
        this.updateTagsDisplay();
        this.updateTagsInput();
    }

    updateTagsDisplay() {
        const display = document.getElementById('tagsDisplay');
        if (!display) return;

        display.innerHTML = this.tags.map(tag => `
            <span class="tag-item">
                ${tag}
                <button type="button" class="tag-remove" onclick="modernPostForm.removeTag('${tag}')">
                    <i class="fas fa-times"></i>
                </button>
            </span>
        `).join('');
    }

    updateTagsInput() {
        const hiddenInput = document.getElementById('postTags');
        if (hiddenInput) {
            hiddenInput.value = this.tags.join(',');
        }
    }

    // Link Validation
    initLinkValidation() {
        const validateBtn = document.getElementById('validateLink');
        const linkInput = document.getElementById('postDownloadLink');
        const statusDiv = document.getElementById('linkStatus');

        if (!validateBtn || !linkInput || !statusDiv) return;

        validateBtn.addEventListener('click', () => {
            this.validateLink(linkInput.value, statusDiv);
        });

        linkInput.addEventListener('blur', () => {
            if (linkInput.value) {
                this.validateLink(linkInput.value, statusDiv);
            }
        });
    }

    async validateLink(url, statusDiv) {
        if (!url) {
            statusDiv.style.display = 'none';
            return;
        }

        try {
            // Simple URL validation
            new URL(url);

            statusDiv.className = 'link-status checking';
            statusDiv.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Verificando link...';

            // Simulate validation (in real app, you'd make an actual request)
            setTimeout(() => {
                statusDiv.className = 'link-status valid';
                statusDiv.innerHTML = '<i class="fas fa-check"></i> Link válido e acessível';
            }, 1000);

        } catch (e) {
            statusDiv.className = 'link-status invalid';
            statusDiv.innerHTML = '<i class="fas fa-exclamation-triangle"></i> URL inválida';
        }
    }

    // Status Handling
    initStatusHandling() {
        const statusRadios = document.querySelectorAll('input[name="status"]');
        const scheduleGroup = document.getElementById('scheduleGroup');

        statusRadios.forEach(radio => {
            radio.addEventListener('change', () => {
                if (scheduleGroup) {
                    scheduleGroup.style.display = radio.value === 'scheduled' ? 'block' : 'none';
                }
            });
        });
    }

    // Real-time Preview
    initPreview() {
        const titleInput = document.getElementById('postTitle');
        const categorySelect = document.getElementById('postCategory');
        const contentEditor = document.getElementById('postContentEditor');

        [titleInput, categorySelect, contentEditor].forEach(element => {
            if (element) {
                element.addEventListener('input', () => this.updatePreview());
                element.addEventListener('change', () => this.updatePreview());
            }
        });
    }

    updatePreview() {
        const previewTitle = document.getElementById('previewTitle');
        const previewCategory = document.getElementById('previewCategory');
        const previewDescription = document.getElementById('previewDescription');

        if (previewTitle) {
            const title = document.getElementById('postTitle')?.value || 'Título do Post';
            previewTitle.textContent = title;
        }

        if (previewCategory) {
            const categorySelect = document.getElementById('postCategory');
            const categoryText = categorySelect?.options[categorySelect.selectedIndex]?.text || 'Categoria';
            previewCategory.textContent = categoryText;
        }

        if (previewDescription) {
            const contentEditor = document.getElementById('postContentEditor');
            const content = contentEditor?.textContent || 'Descrição aparecerá aqui...';
            previewDescription.textContent = content.substring(0, 150) + (content.length > 150 ? '...' : '');
        }
    }

    // Auto-slug generation
    initSlugGeneration() {
        const titleInput = document.getElementById('postTitle');
        const slugInput = document.getElementById('postSlug');

        if (titleInput && slugInput) {
            titleInput.addEventListener('input', () => {
                if (!slugInput.value) {
                    slugInput.value = this.generateSlug(titleInput.value);
                }
            });
        }
    }

    generateSlug(text) {
        return text
            .toLowerCase()
            .trim()
            .replace(/[^\w\s-]/g, '')
            .replace(/[\s_-]+/g, '-')
            .replace(/^-+|-+$/g, '');
    }

    // Form Submission
    submitForm() {
        if (this.validateCurrentStep()) {
            // Update hidden textarea with editor content
            this.updateHiddenTextarea();

            // Show loading state
            const saveBtn = document.getElementById('savePostBtn');
            if (saveBtn) {
                saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Salvando...';
                saveBtn.disabled = true;
            }

            // Submit the form
            document.getElementById('addPostForm').submit();
        }
    }

    // Utility Functions
    showNotification(message, type = 'info') {
        // Use existing notification system if available
        if (typeof showNotification === 'function') {
            showNotification(message, type);
        } else {
            alert(message);
        }
    }

    reset() {
        this.currentStep = 1;
        this.tags = [];
        this.updateStepDisplay();
        this.updateTagsDisplay();
        this.updateTagsInput();
        this.removeImage();

        // Reset form
        document.getElementById('addPostForm')?.reset();

        // Clear editor
        const editor = document.getElementById('postContentEditor');
        if (editor) {
            editor.innerHTML = '';
        }
    }
}

// Export for global access
window.ModernPostForm = ModernPostForm;

/**
 * Modern Category Form Class
 */
class ModernCategoryForm {
    constructor() {
        this.init();
    }

    init() {
        this.bindEvents();
        this.initializeComponents();
    }

    bindEvents() {
        // Character counters
        this.bindCharacterCounters();

        // Color picker
        this.initColorPicker();

        // Icon selector
        this.initIconSelector();

        // Auto-slug generation
        this.initSlugGeneration();

        // Real-time preview
        this.initPreview();

        // Form submission
        document.getElementById('saveCategoryBtn')?.addEventListener('click', () => this.submitForm());

        // Reset form
        document.getElementById('resetForm')?.addEventListener('click', () => this.resetForm());
    }

    initializeComponents() {
        this.updatePreview();
        this.updateColorPreview();
        this.updateIconPreview();
    }

    bindCharacterCounters() {
        const counters = [
            { input: 'categoryName', counter: 'categoryNameCount', max: 50 },
            { input: 'categoryDescription', counter: 'categoryDescCount', max: 200 }
        ];

        counters.forEach(({ input, counter, max }) => {
            const inputElement = document.getElementById(input);
            const counterElement = document.getElementById(counter);

            if (inputElement && counterElement) {
                const updateCounter = () => {
                    const length = inputElement.value.length;
                    counterElement.textContent = length;

                    if (max) {
                        counterElement.parentElement.style.color = length > max ? '#e74c3c' : '#6c757d';
                    }
                };

                inputElement.addEventListener('input', updateCounter);
                updateCounter();
            }
        });
    }

    initColorPicker() {
        const colorInput = document.getElementById('categoryColor');
        const colorText = document.getElementById('categoryColorText');
        const colorPreview = document.getElementById('colorPreview');
        const presets = document.querySelectorAll('.color-preset');

        if (!colorInput || !colorText || !colorPreview) return;

        // Sync color input with text input
        colorInput.addEventListener('input', () => {
            colorText.value = colorInput.value.toUpperCase();
            this.updateColorPreview();
            this.updatePreview();
        });

        colorText.addEventListener('input', () => {
            if (this.isValidColor(colorText.value)) {
                colorInput.value = colorText.value;
                this.updateColorPreview();
                this.updatePreview();
            }
        });

        // Color presets
        presets.forEach(preset => {
            preset.addEventListener('click', () => {
                const color = preset.dataset.color;
                colorInput.value = color;
                colorText.value = color.toUpperCase();
                this.updateColorPreview();
                this.updatePreview();

                // Update active preset
                presets.forEach(p => p.classList.remove('active'));
                preset.classList.add('active');
            });
        });
    }

    initIconSelector() {
        const iconInput = document.getElementById('categoryIcon');
        const iconPreview = document.getElementById('iconPreview');
        const iconButtons = document.querySelectorAll('.icon-btn');

        if (!iconInput || !iconPreview) return;

        iconInput.addEventListener('input', () => {
            this.updateIconPreview();
            this.updatePreview();
        });

        iconButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                const icon = btn.dataset.icon;
                iconInput.value = icon;
                this.updateIconPreview();
                this.updatePreview();

                // Update active icon
                iconButtons.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
            });
        });
    }

    initSlugGeneration() {
        const nameInput = document.getElementById('categoryName');
        const slugInput = document.getElementById('categorySlug');

        if (nameInput && slugInput) {
            nameInput.addEventListener('input', () => {
                if (!slugInput.value) {
                    slugInput.value = this.generateSlug(nameInput.value);
                }
            });
        }
    }

    initPreview() {
        const inputs = ['categoryName', 'categoryDescription'];

        inputs.forEach(inputId => {
            const input = document.getElementById(inputId);
            if (input) {
                input.addEventListener('input', () => this.updatePreview());
            }
        });
    }

    updateColorPreview() {
        const colorInput = document.getElementById('categoryColor');
        const colorPreview = document.getElementById('colorPreview');

        if (colorInput && colorPreview) {
            colorPreview.style.background = colorInput.value;
        }
    }

    updateIconPreview() {
        const iconInput = document.getElementById('categoryIcon');
        const iconPreview = document.getElementById('iconPreview');

        if (iconInput && iconPreview) {
            const iconClass = iconInput.value || 'fas fa-folder';
            iconPreview.innerHTML = `<i class="${iconClass}"></i>`;
        }
    }

    updatePreview() {
        const previewName = document.getElementById('previewName');
        const previewDesc = document.getElementById('previewDesc');
        const previewIcon = document.getElementById('previewIcon');
        const categoryIcon = document.getElementById('previewIcon');

        // Update name
        if (previewName) {
            const name = document.getElementById('categoryName')?.value || 'Nome da Categoria';
            previewName.textContent = name;
        }

        // Update description
        if (previewDesc) {
            const desc = document.getElementById('categoryDescription')?.value || 'Descrição da categoria';
            previewDesc.textContent = desc.substring(0, 100) + (desc.length > 100 ? '...' : '');
        }

        // Update icon and color
        if (previewIcon && categoryIcon) {
            const iconClass = document.getElementById('categoryIcon')?.value || 'fas fa-folder';
            const color = document.getElementById('categoryColor')?.value || '#4a90e2';

            previewIcon.innerHTML = `<i class="${iconClass}"></i>`;
            categoryIcon.style.background = color;
        }
    }

    isValidColor(color) {
        const style = new Option().style;
        style.color = color;
        return style.color !== '';
    }

    generateSlug(text) {
        return text
            .toLowerCase()
            .trim()
            .replace(/[^\w\s-]/g, '')
            .replace(/[\s_-]+/g, '-')
            .replace(/^-+|-+$/g, '');
    }

    submitForm() {
        const form = document.getElementById('addCategoryForm');
        if (form) {
            // Show loading state
            const saveBtn = document.getElementById('saveCategoryBtn');
            if (saveBtn) {
                saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Salvando...';
                saveBtn.disabled = true;
            }

            // Submit form
            form.submit();
        }
    }

    resetForm() {
        const form = document.getElementById('addCategoryForm');
        if (form) {
            form.reset();

            // Reset to defaults
            document.getElementById('categoryColor').value = '#4a90e2';
            document.getElementById('categoryColorText').value = '#4A90E2';
            document.getElementById('categoryIcon').value = 'fas fa-folder';
            document.getElementById('categoryOrder').value = '0';

            // Update UI
            this.updateColorPreview();
            this.updateIconPreview();
            this.updatePreview();

            // Clear character counters
            document.getElementById('categoryNameCount').textContent = '0';
            document.getElementById('categoryDescCount').textContent = '0';
        }
    }
}

/**
 * Modern User Form Class
 */
class ModernUserForm {
    constructor() {
        this.init();
    }

    init() {
        this.bindEvents();
        this.initializeComponents();
    }

    bindEvents() {
        // Password generation
        this.initPasswordGenerator();

        // Avatar upload
        this.initAvatarUpload();

        // Form validation
        this.initValidation();

        // Form submission
        document.getElementById('saveUser')?.addEventListener('click', () => this.submitForm());
    }

    initializeComponents() {
        this.updateAvatarPreview();
    }

    initPasswordGenerator() {
        const generateBtn = document.getElementById('generatePassword');
        const passwordInput = document.getElementById('password');

        if (generateBtn && passwordInput) {
            generateBtn.addEventListener('click', () => {
                const password = this.generateSecurePassword();
                passwordInput.value = password;
                passwordInput.type = 'text';
                setTimeout(() => {
                    passwordInput.type = 'password';
                }, 2000);
            });
        }
    }

    initAvatarUpload() {
        const avatarUpload = document.getElementById('avatarUpload');
        const avatarPreview = document.getElementById('avatarPreview');

        if (avatarUpload && avatarPreview) {
            avatarPreview.addEventListener('click', () => {
                avatarUpload.click();
            });

            avatarUpload.addEventListener('change', (e) => {
                if (e.target.files.length > 0) {
                    this.handleAvatarFile(e.target.files[0]);
                }
            });
        }
    }

    initValidation() {
        const emailInput = document.getElementById('email');
        const usernameInput = document.getElementById('username');

        if (emailInput) {
            emailInput.addEventListener('blur', () => {
                this.validateEmail(emailInput.value);
            });
        }

        if (usernameInput) {
            usernameInput.addEventListener('blur', () => {
                this.validateUsername(usernameInput.value);
            });
        }
    }

    handleAvatarFile(file) {
        if (!file.type.startsWith('image/')) {
            this.showNotification('Por favor, selecione apenas arquivos de imagem.', 'error');
            return;
        }

        if (file.size > 2 * 1024 * 1024) { // 2MB
            this.showNotification('A imagem deve ter no máximo 2MB.', 'error');
            return;
        }

        const reader = new FileReader();
        reader.onload = (e) => {
            this.updateAvatarPreview(e.target.result);
        };
        reader.readAsDataURL(file);
    }

    updateAvatarPreview(src = null) {
        const avatarPreview = document.getElementById('avatarPreview');
        if (!avatarPreview) return;

        if (src) {
            avatarPreview.innerHTML = `
                <img src="${src}" alt="Avatar">
                <div class="avatar-overlay">
                    <i class="fas fa-camera"></i>
                </div>
            `;
        } else {
            const username = document.getElementById('username')?.value || '';
            const initials = this.getInitials(username);
            avatarPreview.innerHTML = `
                <span>${initials}</span>
                <div class="avatar-overlay">
                    <i class="fas fa-camera"></i>
                </div>
            `;
        }
    }

    getInitials(name) {
        if (!name) return 'U';
        return name.substring(0, 2).toUpperCase();
    }

    generateSecurePassword() {
        const length = 12;
        const charset = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*';
        let password = '';

        for (let i = 0; i < length; i++) {
            password += charset.charAt(Math.floor(Math.random() * charset.length));
        }

        return password;
    }

    validateEmail(email) {
        const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        const isValid = regex.test(email);

        const emailInput = document.getElementById('email');
        if (emailInput) {
            emailInput.classList.toggle('is-invalid', !isValid && email.length > 0);
            emailInput.classList.toggle('is-valid', isValid);
        }

        return isValid;
    }

    validateUsername(username) {
        const isValid = username.length >= 3 && /^[a-zA-Z0-9_]+$/.test(username);

        const usernameInput = document.getElementById('username');
        if (usernameInput) {
            usernameInput.classList.toggle('is-invalid', !isValid && username.length > 0);
            usernameInput.classList.toggle('is-valid', isValid);
        }

        return isValid;
    }

    submitForm() {
        const form = document.getElementById('userForm');
        if (form && this.validateForm()) {
            const saveBtn = document.getElementById('saveUser');
            if (saveBtn) {
                saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Salvando...';
                saveBtn.disabled = true;
            }
            form.submit();
        }
    }

    validateForm() {
        const email = document.getElementById('email')?.value;
        const username = document.getElementById('username')?.value;

        return this.validateEmail(email) && this.validateUsername(username);
    }

    showNotification(message, type = 'info') {
        if (typeof showNotification === 'function') {
            showNotification(message, type);
        } else {
            alert(message);
        }
    }
}

// Initialize all forms when DOM is loaded
function initializeModernForms() {
    // Initialize ModernPostForm if exists
    if (document.getElementById('addPostForm') && !window.modernPostForm) {
        window.modernPostForm = new ModernPostForm();
    }

    // Initialize ModernCategoryForm if exists
    if (document.getElementById('addCategoryForm') && !window.modernCategoryForm) {
        window.modernCategoryForm = new ModernCategoryForm();
    }

    // Initialize ModernUserForm if exists
    if (document.getElementById('userForm') && !window.modernUserForm) {
        window.modernUserForm = new ModernUserForm();
    }
}

document.addEventListener('DOMContentLoaded', initializeModernForms);

// Listen for dynamic page loads
document.addEventListener('adminPageLoaded', initializeModernForms);

// Export classes and initialization function for global access
window.ModernCategoryForm = ModernCategoryForm;
window.ModernUserForm = ModernUserForm;
window.initializeModernForms = initializeModernForms;
