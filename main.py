from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import google.genai as genai
import os
from dotenv import load_dotenv
import json

# Import services
from services.auth import (
    get_password_hash, 
    verify_password, 
    create_access_token, 
    get_current_user
)
from services.firestore_db import FirestoreUser, FirestoreReadArticle
from services.news_service import fetch_news_for_interest

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
    content: Optional[str] = None
    image: Optional[str] = None

class PersonalizedNewsResponse(BaseModel):
    recommended_interests: List[str] = Field(..., description="Top K interests selected")
    news_by_interest: Dict[str, List[NewsArticle]] = Field(..., description="News articles grouped by interest")

# Authentication Models
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    age: int = Field(..., ge=13, le=120)
    goals: str
    interests: List[str] = Field(..., min_items=3)
    k: int = Field(default=3, ge=1, le=10)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserProfile(BaseModel):
    id: str
    email: str
    age: int
    goals: str
    interests: List[str]
    k: int

class UpdateProfile(BaseModel):
    age: Optional[int] = None
    goals: Optional[str] = None
    interests: Optional[List[str]] = None
    k: Optional[int] = None

@app.get("/health")
async def health_check():
    return JSONResponse(content={"status": "healthy"}, status_code=200)

# ============= AUTHENTICATION ENDPOINTS =============

@app.post("/auth/register", response_model=Token)
async def register(user_data: UserRegister):
    """Register a new user"""
    # Check if user exists
    existing_user = FirestoreUser.get_by_email(user_data.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    new_user = FirestoreUser.create(
        email=user_data.email,
        hashed_password=hashed_password,
        age=user_data.age,
        goals=user_data.goals,
        interests=user_data.interests,
        k=user_data.k
    )
    
    # Create access token
    access_token = create_access_token(data={"sub": new_user["id"]})
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/auth/login", response_model=Token)
async def login(credentials: UserLogin):
    """Login user"""
    user = FirestoreUser.get_by_email(credentials.email)
    
    if not user or not verify_password(credentials.password, user["hashed_password"]):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password"
        )
    
    # Update last login
    FirestoreUser.update_last_login(user["id"])
    
    # Create access token
    access_token = create_access_token(data={"sub": user["id"]})
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/auth/me", response_model=UserProfile)
async def get_profile(current_user: Dict = Depends(get_current_user)):
    """Get current user profile"""
    return UserProfile(
        id=current_user["id"],
        email=current_user["email"],
        age=current_user["age"],
        goals=current_user["goals"],
        interests=current_user["interests"],
        k=current_user["k"]
    )

@app.put("/auth/profile", response_model=UserProfile)
async def update_profile(
    profile_data: UpdateProfile,
    current_user: Dict = Depends(get_current_user)
):
    """Update user profile"""
    updates = {}
    if profile_data.age is not None:
        updates["age"] = profile_data.age
    if profile_data.goals is not None:
        updates["goals"] = profile_data.goals
    if profile_data.interests is not None:
        updates["interests"] = profile_data.interests
    if profile_data.k is not None:
        updates["k"] = profile_data.k
    
    updated_user = FirestoreUser.update(current_user["id"], updates)
    
    return UserProfile(
        id=updated_user["id"],
        email=updated_user["email"],
        age=updated_user["age"],
        goals=updated_user["goals"],
        interests=updated_user["interests"],
        k=updated_user["k"]
    )

# ============= NEWS ENDPOINTS =============

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
        
        # Step 2: Fetch news for all interests in parallel
        news_by_interest = {}
        
        with ThreadPoolExecutor(max_workers=request.k) as executor:
            future_to_interest = {
                executor.submit(fetch_news_for_interest, interest, 5): interest 
                for interest in recommended_interests
            }
            
            for future in as_completed(future_to_interest):
                interest = future_to_interest[future]
                try:
                    articles_data = future.result()
                    # Convert dicts to NewsArticle objects
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

@app.get("/news/feed", response_model=PersonalizedNewsResponse)
async def get_user_feed(
    current_user: Dict = Depends(get_current_user),
    since: Optional[str] = None
):
    """
    Get personalized news feed for authenticated user.
    Filters out already-read articles.
    """
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")
    
    try:
        # Get user's read articles
        read_urls = set(FirestoreReadArticle.get_user_read_articles(current_user["id"]))
        
        # Step 1: Get top K interests using Gemini
        client = genai.Client(api_key=api_key)
        
        prompt = f"""
        User Profile:
        - Age: {current_user["age"]}
        - Goals: {current_user["goals"]}
        
        Interests to evaluate: {current_user["interests"]}
        
        Task: Pick the top {current_user["k"]} interests that best align with the user's age and goals.
        
        Return ONLY a JSON object in the following format:
        {{
            "recommended_interests": ["interest1", "interest2", ...]
        }}
        """
        
        response = client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=prompt,
            config=genai.types.GenerateContentConfig(response_mime_type="application/json")
        )
        content = response.text.replace("```json", "").replace("```", "").strip()
        result = json.loads(content)
        recommended_interests = result.get("recommended_interests", [])
        
        # Step 2: Fetch news for all interests in parallel
        news_by_interest = {}
        
        with ThreadPoolExecutor(max_workers=current_user["k"]) as executor:
            future_to_interest = {
                executor.submit(fetch_news_for_interest, interest, 10): interest 
                for interest in recommended_interests
            }
            
            for future in as_completed(future_to_interest):
                interest = future_to_interest[future]
                try:
                    articles_data = future.result()
                    # Convert dicts to NewsArticle objects and filter read articles
                    articles = [NewsArticle(**article) for article in articles_data]
                    unread_articles = [
                        article for article in articles 
                        if article.link not in read_urls
                    ]
                    news_by_interest[interest] = unread_articles[:5]
                except Exception as e:
                    print(f"Error fetching news for {interest}: {str(e)}")
                    news_by_interest[interest] = []
        
        return PersonalizedNewsResponse(
            recommended_interests=recommended_interests,
            news_by_interest=news_by_interest
        )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/news/mark-read")
async def mark_article_read(
    article_url: str,
    current_user: Dict = Depends(get_current_user)
):
    """Mark an article as read"""
    FirestoreReadArticle.mark_read(current_user["id"], article_url)
    return {"status": "success", "message": "Article marked as read"}

if __name__ == "__main__":
    import uvicorn
    # Use load_dotenv before running uvicorn if calling via python main.py
    uvicorn.run(app, host="0.0.0.0", port=8000)
