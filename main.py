from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import google.genai as genai
import os
from dotenv import load_dotenv
import json

# Import services
from services.news_service import fetch_news_for_interest
from services.chat_service import ChatService

# Load environment variables
load_dotenv()

app = FastAPI(title="News Enhancer Backend")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get API key from environment
api_key = os.getenv("GEMINI_API_KEY")

# Initialize chat service
chat_service = ChatService(api_key)

# Request and Response Models
class UserProfile(BaseModel):
    age: int = Field(..., description="User's age", examples=[25])
    goals: str = Field(..., description="User's professional or personal goals", examples=["Become a senior software engineer and stay healthy"])
    interests: List[str] = Field(..., description="List of user interests", examples=[["coding", "gaming", "hiking", "cooking", "yoga"]])
    k: int = Field(default=3, ge=1, le=10, description="Number of top interests to return")

class InterestResponse(BaseModel):
    recommended_interests: List[str] = Field(..., description="List of top K recommended interests")

class NewsArticle(BaseModel):
    title: str
    link: str
    source: str
    snippet: Optional[str] = None
    date: Optional[str] = None
    content: Optional[str] = None
    image: Optional[str] = None

class PersonalizedNewsResponse(BaseModel):
    recommended_interests: List[str] = Field(..., description="Top K interests selected")
    news_by_interest: Dict[str, List[NewsArticle]] = Field(..., description="News articles grouped by interest")

class ChatMessage(BaseModel):
    message: str = Field(..., description="User's chat message")
    news_context: Optional[List[NewsArticle]] = Field(None, description="Current news articles for context")
    user_profile: Optional[Dict] = Field(None, description="User profile for personalization")

class ChatResponse(BaseModel):
    response: str = Field(..., description="AI assistant's response")
    timestamp: str = Field(..., description="Response timestamp")

@app.get("/health")
async def health_check():
    return JSONResponse(content={"status": "healthy"}, status_code=200)

@app.post("/recommend-interests", response_model=InterestResponse)
async def recommend_interests(profile: UserProfile):
    """
    Evaluates user interests based on age and goals using Gemini API.
    Returns the top K interests.
    """
    if not api_key:
        raise HTTPException(
            status_code=500, 
            detail="GEMINI_API_KEY not configured. Please set it in the .env file."
        )
    
    try:
        client = genai.Client(api_key=api_key)
        
        prompt = f"""
        User Profile:
        - Age: {profile.age}
        - Goals: {profile.goals}
        
        Interests to evaluate: {profile.interests}
        
        Task: Pick the top {profile.k} interests that best align with the user's age and goals based on the intensity of alignment.
        
        Return ONLY a JSON object in the following format:
        {{
            "recommended_interests": ["interest1", "interest2", ...]
        }}
        """
        
        response = client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        content = response.text.replace("```json", "").replace("```", "").strip()
        
        try:
            result = json.loads(content)
            return result
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="Failed to parse Gemini response as JSON")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini API Error: {str(e)}")

@app.post("/personalized-news", response_model=PersonalizedNewsResponse)
async def get_personalized_news(profile: UserProfile):
    """
    Gets top K interests based on user profile, then fetches personalized news for each interest.
    Generates AI-powered personalized headlines that show direct personal impact.
    Uses RSS feeds and parallel processing for optimal performance.
    """
    if not api_key:
        raise HTTPException(
            status_code=500, 
            detail="GEMINI_API_KEY not configured. Please set it in the .env file."
        )
    
    try:
        # Step 1: Get top K interests using Gemini
        client = genai.Client(api_key=api_key)
        
        prompt = f"""
        User Profile:
        - Age: {profile.age}
        - Goals: {profile.goals}
        
        Interests to evaluate: {profile.interests}
        
        Task: Pick the top {profile.k} interests that best align with the user's age and goals based on the intensity of alignment.
        
        Return ONLY a JSON object in the following format:
        {{
            "recommended_interests": ["interest1", "interest2", ...]
        }}
        """
        
        response = client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        content = response.text.replace("```json", "").replace("```", "").strip()
        
        try:
            result = json.loads(content)
            recommended_interests = result.get("recommended_interests", [])
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="Failed to parse Gemini response as JSON")
        
        # Step 2: Fetch news for all interests in parallel
        news_by_interest = {}
        
        with ThreadPoolExecutor(max_workers=profile.k) as executor:
            future_to_interest = {
                executor.submit(fetch_news_for_interest, interest, 5): interest 
                for interest in recommended_interests
            }
            
            for future in as_completed(future_to_interest):
                interest = future_to_interest[future]
                try:
                    articles_data = future.result()
                    news_by_interest[interest] = articles_data
                except Exception as e:
                    print(f"Error fetching news for {interest}: {str(e)}")
                    news_by_interest[interest] = []
        
        # Step 3: Generate personalized headlines for ALL articles
        personalized_news_by_interest = {}
        
        for interest, articles in news_by_interest.items():
            personalized_articles = []
            
            for article in articles:
                try:
                    # Generate personalized headline
                    headline_prompt = f"""
                    User Profile:
                    - Age: {profile.age}
                    - Goals: {profile.goals}
                    - Interest: {interest}
                    
                    News Article:
                    Title: {article['title']}
                    Content: {article.get('content', '')[:500]}
                    
                    Task: Generate a personalized headline that shows the DIRECT PERSONAL IMPACT on the user.
                    
                    Examples:
                    - Instead of "Gold prices expected to rise next month"
                    - Say: "Invest in gold now - potential ₹50K profit if you sell next month"
                    
                    - Instead of "RBI increases repo rate by 0.5%"
                    - Say: "Your home loan EMI may increase by ₹2,500/month due to rate hike"
                    
                    - Instead of "Tech hiring slowdown expected"
                    - Say: "Upskill now - tech job market tightening for mid-level roles"
                    
                    - Instead of "New tax deduction rules announced"
                    - Say: "Save ₹15,000 in taxes this year with new deduction rules"
                    
                    Generate ONE concise, actionable headline (max 120 characters) that:
                    1. Shows direct personal impact with numbers if possible
                    2. Uses "you/your" language
                    3. Is actionable and specific
                    4. Relates to their goals: {profile.goals}
                    
                    Return ONLY the headline text, nothing else.
                    """
                    
                    headline_response = client.models.generate_content(
                        model='gemini-2.0-flash-exp',
                        contents=headline_prompt
                    )
                    personalized_headline = headline_response.text.strip()
                    
                    # Create personalized article
                    personalized_article = NewsArticle(
                        title=personalized_headline,
                        link=article['link'],
                        source=article['source'],
                        snippet=article.get('snippet'),
                        date=article.get('date'),
                        content=article.get('content'),
                        image=article.get('image')
                    )
                    personalized_articles.append(personalized_article)
                    
                except Exception as e:
                    print(f"Error personalizing headline: {str(e)}")
                    # Fallback to original article
                    personalized_articles.append(NewsArticle(**article))
            
            personalized_news_by_interest[interest] = personalized_articles
        
        return PersonalizedNewsResponse(
            recommended_interests=recommended_interests,
            news_by_interest=personalized_news_by_interest
        )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/chat", response_model=ChatResponse)
async def chat_with_news(chat_request: ChatMessage):
    """
    Chat with AI about the current news articles.
    The AI has context of the news articles being displayed and user profile.
    """
    if not api_key:
        raise HTTPException(
            status_code=500, 
            detail="GEMINI_API_KEY not configured. Please set it in the .env file."
        )
    
    try:
        response = chat_service.chat(
            message=chat_request.message,
            news_context=chat_request.news_context,
            user_profile=chat_request.user_profile
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat Error: {str(e)}")

@app.post("/chat/reset")
async def reset_chat():
    """Reset the chat conversation history"""
    chat_service.reset_conversation()
    return {"status": "success", "message": "Chat conversation reset"}

@app.post("/generate-notifications")
async def generate_notifications(profile: UserProfile):
    """
    Generate personalized daily notifications with AI-generated headlines
    that reflect personal impact of high-impact news
    """
    if not api_key:
        raise HTTPException(
            status_code=500, 
            detail="GEMINI_API_KEY not configured. Please set it in the .env file."
        )
    
    try:
        # Step 1: Get top interests
        client = genai.Client(api_key=api_key)
        
        prompt = f"""
        User Profile:
        - Age: {profile.age}
        - Goals: {profile.goals}
        
        Interests to evaluate: {profile.interests}
        
        Task: Pick the top {profile.k} interests that best align with the user's age and goals.
        
        Return ONLY a JSON object in the following format:
        {{
            "recommended_interests": ["interest1", "interest2", ...]
        }}
        """
        
        response = client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        content = response.text.replace("```json", "").replace("```", "").strip()
        result = json.loads(content)
        recommended_interests = result.get("recommended_interests", [])
        
        # Step 2: Fetch news for all interests in parallel
        news_by_interest = {}
        
        with ThreadPoolExecutor(max_workers=profile.k) as executor:
            future_to_interest = {
                executor.submit(fetch_news_for_interest, interest, 3): interest 
                for interest in recommended_interests
            }
            
            for future in as_completed(future_to_interest):
                interest = future_to_interest[future]
                try:
                    articles_data = future.result()
                    news_by_interest[interest] = articles_data
                except Exception as e:
                    print(f"Error fetching news for {interest}: {str(e)}")
                    news_by_interest[interest] = []
        
        # Step 3: Generate personalized headlines for high-impact news
        all_articles = []
        for interest, articles in news_by_interest.items():
            for article in articles:
                all_articles.append({
                    "interest": interest,
                    "article": article
                })
        
        # Limit to top 5 articles
        all_articles = all_articles[:5]
        
        # Generate personalized headlines using AI
        notifications = []
        for item in all_articles:
            article = item["article"]
            interest = item["interest"]
            
            # Generate personalized headline
            headline_prompt = f"""
            User Profile:
            - Age: {profile.age}
            - Goals: {profile.goals}
            - Interest: {interest}
            
            News Article:
            Title: {article['title']}
            Content: {article['content'][:500]}
            
            Task: Generate a personalized notification headline that shows the DIRECT PERSONAL IMPACT on the user.
            
            Examples:
            - Instead of "Gold prices expected to rise next month"
            - Say: "Invest in gold now - potential ₹50K profit if you sell next month"
            
            - Instead of "RBI increases repo rate by 0.5%"
            - Say: "Your home loan EMI may increase by ₹2,500/month due to rate hike"
            
            - Instead of "New tax deduction rules announced"
            - Say: "Save ₹15,000 in taxes this year with new deduction rules"
            
            Generate ONE concise, actionable headline (max 100 characters) that:
            1. Shows direct personal impact with numbers if possible
            2. Uses "you/your" language
            3. Is actionable and specific
            4. Relates to their goals: {profile.goals}
            
            Return ONLY the headline text, nothing else.
            """
            
            try:
                headline_response = client.models.generate_content(
                    model='gemini-2.0-flash-exp',
                    contents=headline_prompt
                )
                personalized_headline = headline_response.text.strip()
                
                # Calculate impact score (simple heuristic for now)
                impact_score = 7 + (len(article['content']) / 500)  # 7-9 range
                impact_score = min(9, impact_score)
                
                notifications.append({
                    "id": f"notif-{len(notifications) + 1}",
                    "headline": personalized_headline,
                    "original_title": article['title'],
                    "summary": article['content'][:200] if article['content'] else article.get('snippet', ''),
                    "source": article['source'],
                    "link": article['link'],
                    "image": article.get('image'),
                    "interest": interest,
                    "impact_score": round(impact_score, 1),
                    "impact_level": "High" if impact_score >= 8 else "Medium" if impact_score >= 6 else "Low",
                    "timestamp": article.get('date', 'Recently')
                })
            except Exception as e:
                print(f"Error generating headline: {str(e)}")
                # Fallback to original title
                notifications.append({
                    "id": f"notif-{len(notifications) + 1}",
                    "headline": article['title'],
                    "original_title": article['title'],
                    "summary": article['content'][:200] if article['content'] else article.get('snippet', ''),
                    "source": article['source'],
                    "link": article['link'],
                    "image": article.get('image'),
                    "interest": interest,
                    "impact_score": 7.0,
                    "impact_level": "Medium",
                    "timestamp": article.get('date', 'Recently')
                })
        
        return {
            "notifications": notifications,
            "generated_at": json.dumps({"timestamp": "now"})
        }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/personalize-headline")
async def personalize_headline(data: dict):
    """
    Generate a personalized headline for a single news article
    """
    if not api_key:
        raise HTTPException(
            status_code=500, 
            detail="GEMINI_API_KEY not configured. Please set it in the .env file."
        )
    
    try:
        client = genai.Client(api_key=api_key)
        
        article = data.get('article', {})
        user_profile = data.get('user_profile', {})
        
        headline_prompt = f"""
        User Profile:
        - Age: {user_profile.get('age', 25)}
        - Goals: {user_profile.get('goals', 'Career growth')}
        
        News Article:
        Title: {article.get('title', '')}
        Content: {article.get('content', '')[:500]}
        Category: {article.get('category', 'General')}
        
        Task: Generate a personalized headline that shows the DIRECT PERSONAL IMPACT on the user.
        
        Examples:
        - Instead of "Gold prices expected to rise next month"
        - Say: "Invest in gold now - potential ₹50K profit if you sell next month"
        
        - Instead of "RBI increases repo rate by 0.5%"
        - Say: "Your home loan EMI may increase by ₹2,500/month due to rate hike"
        
        - Instead of "Tech hiring slowdown expected"
        - Say: "Upskill now - tech job market tightening for mid-level roles"
        
        Generate ONE concise, actionable headline (max 100 characters) that:
        1. Shows direct personal impact with numbers if possible
        2. Uses "you/your" language
        3. Is actionable and specific
        4. Relates to their goals: {user_profile.get('goals', 'Career growth')}
        
        Return ONLY the headline text, nothing else.
        """
        
        headline_response = client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=headline_prompt
        )
        personalized_headline = headline_response.text.strip()
        
        return {
            "personalized_headline": personalized_headline,
            "original_headline": article.get('title', '')
        }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
