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
    userId: Optional[str] = Field(None, description="User ID for caching interests")
    cachedInterests: Optional[List[str]] = Field(None, description="Pre-cached recommended interests from database")

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
    Gets top K interests based on user profile, then fetches news for each interest.
    Uses LLM only for interest selection (and caches result), then directly fetches from RSS feeds.
    """
    if not api_key:
        raise HTTPException(
            status_code=500, 
            detail="GEMINI_API_KEY not configured. Please set it in the .env file."
        )
    
    try:
        # Step 1: Check if we have cached interests from frontend
        if profile.cachedInterests and len(profile.cachedInterests) > 0:
            print(f"Using cached interests from database: {profile.cachedInterests}")
            recommended_interests = profile.cachedInterests
        else:
            # Use LLM to select interests (only if not cached)
            print("No cached interests found, using LLM to select interests...")
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
                print(f"LLM selected interests: {recommended_interests}")
            except json.JSONDecodeError:
                raise HTTPException(status_code=500, detail="Failed to parse Gemini response as JSON")
        
        # Step 2: Fetch news for all interests in parallel (NO PERSONALIZATION)
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
                    # Convert dicts to NewsArticle objects directly (no personalization)
                    articles = [NewsArticle(**article) for article in articles_data]
                    news_by_interest[interest] = articles
                except Exception as e:
                    print(f"Error fetching news for {interest}: {str(e)}")
                    news_by_interest[interest] = []
        
        return PersonalizedNewsResponse(
            recommended_interests=recommended_interests,
            news_by_interest=news_by_interest
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

class ImpactReportRequest(BaseModel):
    article: NewsArticle = Field(..., description="News article to analyze")
    user_profile: Dict = Field(..., description="User profile for personalized impact analysis")

class ImpactReportResponse(BaseModel):
    relevance_score: float = Field(..., description="Relevance score out of 10")
    impact_level: str = Field(..., description="High, Medium, or Low")
    financial_impact: Dict = Field(..., description="Financial impact details")
    recommendations: List[Dict] = Field(..., description="Actionable recommendations")
    confidence: float = Field(..., description="AI confidence percentage")

@app.post("/generate-impact-report", response_model=ImpactReportResponse)
async def generate_impact_report(request: ImpactReportRequest):
    """
    Generate a detailed personalized impact report for a news article.
    Uses LLM to analyze how the news affects the user specifically.
    """
    if not api_key:
        raise HTTPException(
            status_code=500, 
            detail="GEMINI_API_KEY not configured. Please set it in the .env file."
        )
    
    try:
        client = genai.Client(api_key=api_key)
        
        # Extract user profile details
        age = request.user_profile.get('age', 'Unknown')
        goals = request.user_profile.get('goals', 'Not specified')
        interests = request.user_profile.get('interests', [])
        profession = request.user_profile.get('profession', 'Not specified')
        
        # Convert arrays to strings if needed
        if isinstance(goals, list):
            goals = ', '.join(goals)
        if isinstance(interests, list):
            interests = ', '.join(interests)
        
        prompt = f"""You are a financial and news impact analyst. Generate a detailed personal impact report for this news article.

USER PROFILE:
- Age: {age}
- Profession: {profession}
- Goals: {goals}
- Interests: {interests}

NEWS ARTICLE:
Title: {request.article.title}
Source: {request.article.source}
Content: {request.article.content or request.article.snippet}

TASK: Analyze how this news specifically impacts this user. Consider their age, profession, goals, and interests.

Return a JSON object with this EXACT structure:
{{
    "relevance_score": <float between 0-10>,
    "impact_level": "<High/Medium/Low>",
    "confidence": <float between 0-100>,
    "financial_impact": {{
        "monthly_cash_flow": "<amount with + or - prefix, e.g., +₹2,400 or -₹1,200>",
        "monthly_impact_type": "<EXPENSE INCREASE/EXPENSE DECREASE/INCOME INCREASE/INCOME DECREASE/NO CHANGE>",
        "risk_sensitivity": "<High/Medium/Low>",
        "risk_status": "<STABLE PORTFOLIO/MODERATE RISK/HIGH RISK>",
        "ten_year_outlook": "<amount, e.g., ₹8.5 Lakhs>",
        "ten_year_change": "<percentage with + or - prefix, e.g., +12% or -5%>"
    }},
    "recommendations": [
        {{
            "title": "<action title>",
            "description": "<brief description>",
            "benefit": "<optional benefit amount, e.g., +₹1.2L BENEFIT>",
            "priority": <1-5, where 1 is highest>
        }}
    ]
}}

IMPORTANT:
- Be specific to the user's profile
- Use Indian currency (₹) for financial amounts
- Provide 3-5 actionable recommendations
- Make the analysis realistic and practical
- If the news doesn't significantly impact them, reflect that in the scores"""

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
            
            # Validate and fix the structure
            if not isinstance(result, dict):
                raise ValueError(f"Expected dict, got {type(result)}")
            
            # Ensure recommendations is a list
            if 'recommendations' in result and not isinstance(result['recommendations'], list):
                print(f"Warning: recommendations is not a list: {type(result['recommendations'])}")
                result['recommendations'] = []
            
            # Ensure financial_impact is a dict
            if 'financial_impact' in result and not isinstance(result['financial_impact'], dict):
                print(f"Warning: financial_impact is not a dict: {type(result['financial_impact'])}")
                result['financial_impact'] = {
                    "monthly_cash_flow": "₹0",
                    "monthly_impact_type": "NO CHANGE",
                    "risk_sensitivity": "Low",
                    "risk_status": "STABLE PORTFOLIO",
                    "ten_year_outlook": "₹0",
                    "ten_year_change": "+0%"
                }
            
            print(f"Parsed impact report successfully: {result}")
            return ImpactReportResponse(**result)
        except json.JSONDecodeError as e:
            print(f"Failed to parse impact report JSON: {content}")
            raise HTTPException(status_code=500, detail=f"Failed to parse AI response: {str(e)}")
        except Exception as e:
            print(f"Error creating ImpactReportResponse: {str(e)}")
            print(f"Result data: {result}")
            raise HTTPException(status_code=500, detail=f"Error processing AI response: {str(e)}")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating impact report: {str(e)}")

@app.post("/generate-notifications")
async def generate_notifications(profile: UserProfile):
    """
    Generate daily notifications with high-impact news.
    Uses cached interests if available, otherwise calls LLM.
    """
    if not api_key:
        raise HTTPException(
            status_code=500, 
            detail="GEMINI_API_KEY not configured. Please set it in the .env file."
        )
    
    try:
        # Step 1: Check if we have cached interests
        if profile.cachedInterests and len(profile.cachedInterests) > 0:
            print(f"Using cached interests for notifications: {profile.cachedInterests}")
            recommended_interests = profile.cachedInterests
        else:
            # Use LLM to select interests (only if not cached)
            print("No cached interests found, using LLM for notifications...")
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
        
        # Step 3: Create notifications from articles (NO AI PERSONALIZATION)
        all_articles = []
        for interest, articles in news_by_interest.items():
            for article in articles:
                all_articles.append({
                    "interest": interest,
                    "article": article
                })
        
        # Limit to top 5 articles
        all_articles = all_articles[:5]
        
        # Create notifications with original headlines
        notifications = []
        for item in all_articles:
            article = item["article"]
            interest = item["interest"]
            
            # Calculate impact score (simple heuristic)
            impact_score = 7 + (len(article.get('content', '')) / 500)
            impact_score = min(9, impact_score)
            
            notifications.append({
                "id": f"notif-{len(notifications) + 1}",
                "headline": article['title'],
                "original_title": article['title'],
                "summary": article.get('content', '')[:200] if article.get('content') else article.get('snippet', ''),
                "source": article['source'],
                "link": article['link'],
                "image": article.get('image'),
                "interest": interest,
                "impact_score": round(impact_score, 1),
                "impact_level": "High" if impact_score >= 8 else "Medium" if impact_score >= 6 else "Low",
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
