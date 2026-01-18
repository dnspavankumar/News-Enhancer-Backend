const API_URL = 'http://localhost:8000';

// Check if already logged in
if (localStorage.getItem('authToken')) {
    window.location.href = 'feed.html';
}

// Login Form
document.getElementById('loginFormElement').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const email = document.getElementById('loginEmail').value;
    const password = document.getElementById('loginPassword').value;
    
    showLoading();
    hideError();
    
    try {
        const response = await fetch(`${API_URL}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Login failed');
        }
        
        const data = await response.json();
        localStorage.setItem('authToken', data.access_token);
        window.location.href = 'feed.html';
        
    } catch (error) {
        showError(error.message);
    } finally {
        hideLoading();
    }
});

// Register Form
document.getElementById('registerFormElement').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const email = document.getElementById('regEmail').value;
    const password = document.getElementById('regPassword').value;
    const age = parseInt(document.getElementById('regAge').value);
    const goals = document.getElementById('regGoals').value;
    const k = parseInt(document.getElementById('regK').value);
    
    const checkboxes = document.querySelectorAll('#registerForm input[name="interest"]:checked');
    const interests = Array.from(checkboxes).map(cb => cb.value);
    
    if (interests.length < 3) {
        showError('Please select at least 3 interests');
        return;
    }
    
    showLoading();
    hideError();
    
    try {
        const response = await fetch(`${API_URL}/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password, age, goals, interests, k })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Registration failed');
        }
        
        const data = await response.json();
        localStorage.setItem('authToken', data.access_token);
        window.location.href = 'feed.html';
        
    } catch (error) {
        showError(error.message);
    } finally {
        hideLoading();
    }
});

function showLogin() {
    document.getElementById('loginForm').classList.remove('hidden');
    document.getElementById('registerForm').classList.add('hidden');
    hideError();
}

function showRegister() {
    document.getElementById('loginForm').classList.add('hidden');
    document.getElementById('registerForm').classList.remove('hidden');
    hideError();
}

function showLoading() {
    document.getElementById('loading').classList.remove('hidden');
}

function hideLoading() {
    document.getElementById('loading').classList.add('hidden');
}

function showError(message) {
    const errorDiv = document.getElementById('error');
    errorDiv.textContent = `❌ ${message}`;
    errorDiv.classList.remove('hidden');
}

function hideError() {
    document.getElementById('error').classList.add('hidden');
}
