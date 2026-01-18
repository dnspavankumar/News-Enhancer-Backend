const API_URL = 'http://localhost:8000';

document.getElementById('newsForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const age = parseInt(document.getElementById('age').value);
    const goals = document.getElementById('goals').value;
    const k = parseInt(document.getElementById('k').value);
    
    // Get selected interests
    const checkboxes = document.querySelectorAll('input[name="interest"]:checked');
    const interests = Array.from(checkboxes).map(cb => cb.value);
    
    if (interests.length < 3) {
        showError('Please select at least 3 interests');
        return;
    }
    
    // Show loading
    document.getElementById('loading').classList.remove('hidden');
    document.getElementById('results').classList.add('hidden');
    document.getElementById('error').classList.add('hidden');
    
    try {
        const response = await fetch(`${API_URL}/personalized-news`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ age, goals, interests, k })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Failed to fetch news');
        }
        
        const data = await response.json();
        displayResults(data);
        
    } catch (error) {
        showError(error.message);
    } finally {
        document.getElementById('loading').classList.add('hidden');
    }
});

function displayResults(data) {
    const resultsDiv = document.getElementById('results');
    const topInterestsDiv = document.getElementById('topInterests');
    const newsContainer = document.getElementById('newsContainer');
    
    // Display top interests
    topInterestsDiv.innerHTML = '';
    data.recommended_interests.forEach(interest => {
        const badge = document.createElement('div');
        badge.className = 'interest-badge';
        badge.textContent = interest;
        topInterestsDiv.appendChild(badge);
    });
    
    // Display news by interest
    newsContainer.innerHTML = '';
    
    for (const [interest, articles] of Object.entries(data.news_by_interest)) {
        const section = document.createElement('div');
        section.className = 'news-section';
        
        const heading = document.createElement('h3');
        heading.textContent = `📌 ${interest.toUpperCase()}`;
        section.appendChild(heading);
        
        if (articles.length === 0) {
            const noNews = document.createElement('p');
            noNews.textContent = 'No articles found for this interest.';
            noNews.style.color = '#999';
            section.appendChild(noNews);
        } else {
            articles.forEach(article => {
                const articleDiv = document.createElement('div');
                articleDiv.className = 'article';
                
                const title = document.createElement('h4');
                const link = document.createElement('a');
                link.href = article.link;
                link.target = '_blank';
                link.textContent = article.title;
                title.appendChild(link);
                articleDiv.appendChild(title);
                
                const meta = document.createElement('div');
                meta.className = 'article-meta';
                meta.textContent = `📰 ${article.source}`;
                if (article.date) {
                    meta.textContent += ` • ${article.date}`;
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
                    articleDiv.appendChild(img);
                }
                
                section.appendChild(articleDiv);
            });
        }
        
        newsContainer.appendChild(section);
    }
    
    resultsDiv.classList.remove('hidden');
    resultsDiv.scrollIntoView({ behavior: 'smooth' });
}

function showError(message) {
    const errorDiv = document.getElementById('error');
    errorDiv.textContent = `❌ Error: ${message}`;
    errorDiv.classList.remove('hidden');
}
