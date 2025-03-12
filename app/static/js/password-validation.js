document.addEventListener('DOMContentLoaded', function() {
    console.log('Password validation script loaded');
    
    // Password change validation
    const passwordForm = document.getElementById('passwordForm');
    const newPassword = document.getElementById('new_password');
    const confirmNewPassword = document.getElementById('confirm_new_password');
    const changePasswordBtn = document.getElementById('changePasswordBtn');
    const passwordMatch = document.getElementById('password_match');
    
    if (!passwordForm || !newPassword || !confirmNewPassword || !changePasswordBtn || !passwordMatch) {
        console.log('Required elements not found, password validation not initialized');
        return;
    }
    
    console.log('Password validation elements found, initializing validation');
    
    // Password requirement checks
    const requirements = {
        length: str => str.length >= 8,
        uppercase: str => /[A-Z]/.test(str),
        lowercase: str => /[a-z]/.test(str),
        number: str => /\d/.test(str),
        special: str => /[!@#$%^&*(),.?":{}|<>]/.test(str)
    };
    
    function updatePasswordStrength(password) {
        console.log('updatePasswordStrength called with:', password);
        let allValid = true;
        for (let [requirement, testFn] of Object.entries(requirements)) {
            const element = document.getElementById(requirement);
            if (!element) continue;
            
            const isValid = testFn(password);
            console.log(`Requirement ${requirement}:`, isValid);
            
            if (isValid) {
                element.classList.remove('text-red-600');
                element.classList.add('text-green-600');
                element.textContent = '✓ ' + element.textContent.substring(2);
            } else {
                element.classList.remove('text-green-600');
                element.classList.add('text-red-600');
                element.textContent = '✗ ' + element.textContent.substring(2);
                allValid = false;
            }
        }
        console.log('All requirements valid:', allValid);
        return allValid;
    }
    
    function validatePasswordForm() {
        console.log('validatePasswordForm called');
        const passwordValue = newPassword.value;
        const isPasswordValid = updatePasswordStrength(passwordValue);
        const doPasswordsMatch = newPassword.value === confirmNewPassword.value;
        const currentPasswordFilled = document.getElementById('current_password').value.length > 0;
        
        console.log('Password validation state:', {
            isPasswordValid,
            doPasswordsMatch,
            currentPasswordFilled
        });
        
        if (doPasswordsMatch && confirmNewPassword.value) {
            passwordMatch.textContent = 'Passwords match';
            passwordMatch.classList.remove('text-red-600');
            passwordMatch.classList.add('text-green-600');
        } else if (confirmNewPassword.value) {
            passwordMatch.textContent = 'Passwords do not match';
            passwordMatch.classList.remove('text-green-600');
            passwordMatch.classList.add('text-red-600');
        } else {
            passwordMatch.textContent = '';
        }
        
        const shouldEnable = isPasswordValid && doPasswordsMatch && currentPasswordFilled;
        console.log('Should enable button:', shouldEnable);
        
        if (shouldEnable) {
            changePasswordBtn.removeAttribute('disabled');
        } else {
            changePasswordBtn.setAttribute('disabled', 'true');
        }
    }
    
    // Add event listeners
    document.getElementById('current_password').addEventListener('input', validatePasswordForm);
    newPassword.addEventListener('input', validatePasswordForm);
    confirmNewPassword.addEventListener('input', validatePasswordForm);
    
    // Initial validation
    validatePasswordForm();
}); 