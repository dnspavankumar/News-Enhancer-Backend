from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import google.genai as genai
import os
from dotenv import load_dotenv
import json
import requests

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
serp_api_key = os.getenv("SERP_API_KEY")

# Request and Response Models
class InterestRequest(BaseModel):
    age: int = Field(..., description="User's age", examples=[25])
    goals: str = Field(..., description="User's professional or personal goals", examples=["Become a senior software engineer and stay healthy"])
    interests: List[str] = Field(..., description="List of user interests", examples=[["coding", "gaming", "hiking", "cooking", "yoga"]])
    k: int = Field(default=3, ge=1, description="Number of top interests to return")

class InterestResponse(BaseModel):
    recommended_interests: List[str] = Field(..., description="List of top K recommended interests")

class NewsArticle(BaseModel):
    title: str
    link: str
    source: str
    snippet: Optional[str] = None
    date: Optional[str] = None

class PersonalizedNewsResponse(BaseModel):
    recommended_interests: List[str] = Field(..., description="Top K interests selected")
    news_by_interest: Dict[str, List[NewsArticle]] = Field(..., description="News articles grouped by interest")

@app.get("/health")
async def health_check():
    return JSONResponse(content={"status": "healthy"}, status_code=200)

def fetch_news_for_interest(interest: str, num_results: int = 5) -> List[NewsArticle]:
    """
    Fetch news articles for a specific interest using SERP API.
    """
    if not serp_api_key:
        return []
    
    try:
        params = {
            "engine": "google_news",
            "q": interest,
            "api_key": serp_api_key,
            "num": num_results
        }
        
        response = requests.get("https://serpapi.com/search", params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        articles = []
        news_results = data.get("news_results", [])
        
        for item in news_results[:num_results]:
            article = NewsArticle(
                title=item.get("title", ""),
                link=item.get("link", ""),
                source=item.get("source", {}).get("name", "Unknown") if isinstance(item.get("source"), dict) else item.get("source", "Unknown"),
                snippet=item.get("snippet", ""),
                date=item.get("date", "")
            )
            articles.append(article)
        
        return articles
    except Exception as e:
        print(f"Error fetching news for {interest}: {str(e)}")
        return []

@app.post("/recommend-interests", response_model=InterestResponse)
async def recommend_interests(request: InterestRequest):
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
        - Age: {request.age}
        - Goals: {request.goals}
        
        Interests to evaluate: {request.interests}
        
        Task: Pick the top {request.k} interests that best align with the user's age and goals based on the intensity of alignment.
        
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
            # Fallback in case Gemini returns something else
            raise HTTPException(status_code=500, detail="Failed to parse Gemini response as JSON")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini API Error: {str(e)}")

@app.post("/personalized-news", response_model=PersonalizedNewsResponse)
async def get_personalized_news(request: InterestRequest):
    """
    Gets top K interests based on user profile, then fetches personalized news for each interest.
    """
    if not api_key:
        raise HTTPException(
            status_code=500, 
            detail="GEMINI_API_KEY not configured. Please set it in the .env file."
        )
    
    if not serp_api_key:
        raise HTTPException(
            status_code=500, 
            detail="SERP_API_KEY not configured. Please set it in the .env file."
        )
    
    try:
        # Step 1: Get top K interests using Gemini
        client = genai.Client(api_key=api_key)
        
        prompt = f"""
        User Profile:
        - Age: {request.age}
        - Goals: {request.goals}
        
        Interests to evaluate: {request.interests}
        
        Task: Pick the top {request.k} interests that best align with the user's age and goals based on the intensity of alignment.
        
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
        
        # Step 2: Fetch news for each recommended interest
        news_by_interest = {}
        for interest in recommended_interests:
            articles = fetch_news_for_interest(interest, num_results=5)
            news_by_interest[interest] = articles
        
        return PersonalizedNewsResponse(
            recommended_interests=recommended_interests,
            news_by_interest=news_by_interest
        )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    # Use load_dotenv before running uvicorn if calling via python main.py
    uvicorn.run(app, host="0.0.0.0", port=8000)
