const API_URL = 'http://localhost:8000';
let refreshInterval;
let countdownInterval;
let countdown = 300; // 5 minutes

// Check authentication
const token = localStorage.getItem('authToken');
if (!token) {
    window.location.href = 'auth.html';
}

// Load user profile and feed on page load
window.addEventListener('load', async () => {
    await loadUserProfile();
    await loadFeed();
    startAutoRefresh();
});

async function loadUserProfile() {
    try {
        const response = await fetch(`${API_URL}/auth/me`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (!response.ok) {
            if (response.status === 401) {
                logout();
                return;
            }
            throw new Error('Failed to load profile');
        }
        
        const user = await response.json();
        document.getElementById('userEmail').textContent = user.email;
        
    } catch (error) {
        console.error('Error loading profile:', error);
    }
}

async function loadFeed() {
    showLoading();
    hideError();
    
    try {
        const response = await fetch(`${API_URL}/news/feed`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (!response.ok) {
            if (response.status === 401) {
                logout();
                return;
            }
            const error = await response.json();
            throw new Error(error.detail || 'Failed to load feed');
        }
        
        const data = await response.json();
        displayFeed(data);
        updateLastUpdateTime();
        
    } catch (error) {
        showError(error.message);
    } finally {
        hideLoading();
    }
}

function displayFeed(data) {
    // Display top interests
    const interestsDiv = document.getElementById('topInterests');
    const interestsListDiv = document.getElementById('interestsList');
    
    interestsListDiv.innerHTML = '';
    data.recommended_interests.forEach(interest => {
        const badge = document.createElement('div');
        badge.className = 'interest-badge';
        badge.textContent = interest;
        interestsListDiv.appendChild(badge);
    });
    interestsDiv.classList.remove('hidden');
    
    // Display news
    const newsContainer = document.getElementById('newsContainer');
    newsContainer.innerHTML = '';
    
    let hasArticles = false;
    
    for (const [interest, articles] of Object.entries(data.news_by_interest)) {
        if (articles.length === 0) continue;
        
        hasArticles = true;
        const section = document.createElement('div');
        section.className = 'news-section';
        
        const heading = document.createElement('h3');
        heading.textContent = `📌 ${interest.toUpperCase()}`;
        section.appendChild(heading);
        
        articles.forEach(article => {
            const articleDiv = document.createElement('div');
            articleDiv.className = 'article';
            
            const title = document.createElement('h4');
            const link = document.createElement('a');
            link.href = article.link;
            link.target = '_blank';
            link.textContent = article.title;
            link.onclick = () => markAsRead(article.link);
            title.appendChild(link);
            articleDiv.appendChild(title);
            
            const meta = document.createElement('div');
            meta.className = 'article-meta';
            
            const source = document.createElement('span');
            source.textContent = `📰 ${article.source}`;
            meta.appendChild(source);
            
            if (article.date) {
                const date = document.createElement('span');
                date.textContent = `📅 ${article.date}`;
                meta.appendChild(date);
            }
            
            articleDiv.appendChild(meta);
            
            if (article.content) {
                const content = document.createElement('div');
                content.className = 'article-content';
                content.textContent = article.content.substring(0, 300) + '...';
                articleDiv.appendChild(content);
            }
            
            if (article.image) {
                const img = document.createElement('img');
                img.src = article.image;
                img.className = 'article-image';
                img.alt = article.title;
                img.onerror = () => img.style.display = 'none';
                articleDiv.appendChild(img);
            }
            
            section.appendChild(articleDiv);
        });
        
        newsContainer.appendChild(section);
    }
    
    if (!hasArticles) {
        const emptyState = document.createElement('div');
        emptyState.className = 'empty-state';
        emptyState.innerHTML = `
            <h3>No new articles</h3>
            <p>All caught up! Check back later for more news.</p>
        `;
        newsContainer.appendChild(emptyState);
    }
    
    document.getElementById('refreshInfo').classList.remove('hidden');
}

async function markAsRead(articleUrl) {
    try {
        await fetch(`${API_URL}/news/mark-read?article_url=${encodeURIComponent(articleUrl)}`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
    } catch (error) {
        console.error('Error marking article as read:', error);
    }
}

function refreshFeed() {
    resetCountdown();
    loadFeed();
}

function startAutoRefresh() {
    // Refresh every 5 minutes
    refreshInterval = setInterval(() => {
        loadFeed();
        resetCountdown();
    }, 300000); // 5 minutes
    
    // Update countdown every second
    countdownInterval = setInterval(() => {
        countdown--;
        document.getElementById('countdown').textContent = countdown;
        
        if (countdown <= 0) {
            resetCountdown();
        }
    }, 1000);
}

function resetCountdown() {
    countdown = 300;
    document.getElementById('countdown').textContent = countdown;
}

function updateLastUpdateTime() {
    const now = new Date();
    const timeString = now.toLocaleTimeString();
    document.getElementById('lastUpdate').textContent = timeString;
}

function showSettings() {
    if (confirm('Go to settings page? (You can update your profile there)')) {
        // TODO: Create settings page
        alert('Settings page coming soon! For now, you can re-register with a new account.');
    }
}

function logout() {
    localStorage.removeItem('authToken');
    clearInterval(refreshInterval);
    clearInterval(countdownInterval);
    window.location.href = 'auth.html';
}

function showLoading() {
    document.getElementById('loading').classList.remove('hidden');
}

function hideLoading() {
    document.getElementById('loading').classList.add('hidden');
}

function showError(message) {
    const errorDiv = document.getElementById('error');
    errorDiv.textContent = `❌ Error: ${message}`;
    errorDiv.classList.remove('hidden');
}

function hideError() {
    document.getElementById('error').classList.add('hidden');
}
