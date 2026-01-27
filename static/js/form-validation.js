/**
 * Form Validation Utilities
 * Funções compartilhadas para validação de formulários
 */

/**
 * Valida um campo específico e exibe mensagem de erro
 * @param {HTMLElement} field - Campo a ser validado
 * @param {boolean} condition - Condição que determina se há erro (true = erro)
 * @param {string} errorMessage - Mensagem de erro a ser exibida
 * @returns {boolean} - true se válido, false se inválido
 */
function validateField(field, condition, errorMessage) {
    const feedbackElement = field.closest('.form-group').querySelector('.input-feedback');

    if (condition) {
        field.classList.add('input-error');
        if (feedbackElement) {
            feedbackElement.textContent = errorMessage;
            feedbackElement.classList.add('show');
        }
        return false;
    } else {
        clearFieldError(field);
        return true;
    }
}

/**
 * Limpa o erro de um campo
 * @param {HTMLElement} field - Campo do qual o erro será removido
 */
function clearFieldError(field) {
    field.classList.remove('input-error');
    const feedbackElement = field.closest('.form-group').querySelector('.input-feedback');
    if (feedbackElement) {
        feedbackElement.textContent = '';
        feedbackElement.classList.remove('show');
    }
}

/**
 * Valida formato de email
 * @param {string} email - Email a ser validado
 * @returns {boolean} - true se válido
 */
function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

/**
 * Valida força de senha
 * @param {string} password - Senha a ser validada
 * @returns {Object} - {isValid: boolean, message: string}
 */
function validatePasswordStrength(password) {
    if (password.length < 6) {
        return { isValid: false, message: 'A senha deve ter pelo menos 6 caracteres' };
    }
    if (!/[A-Z]/.test(password)) {
        return { isValid: false, message: 'A senha deve conter pelo menos uma letra maiúscula' };
    }
    if (!/[a-z]/.test(password)) {
        return { isValid: false, message: 'A senha deve conter pelo menos uma letra minúscula' };
    }
    if (!/[0-9]/.test(password)) {
        return { isValid: false, message: 'A senha deve conter pelo menos um número' };
    }
    return { isValid: true, message: 'Senha forte' };
}

/**
 * Valida se dois campos têm valores iguais (útil para confirmação de senha)
 * @param {string} value1 - Primeiro valor
 * @param {string} value2 - Segundo valor
 * @returns {boolean} - true se iguais
 */
function fieldsMatch(value1, value2) {
    return value1 === value2;
}

// Exportar funções para uso global
window.validateField = validateField;
window.clearFieldError = clearFieldError;
window.isValidEmail = isValidEmail;
window.validatePasswordStrength = validatePasswordStrength;
window.fieldsMatch = fieldsMatch;
