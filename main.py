from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List
import google.genai as genai
import os
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

app = FastAPI(title="News Enhancer Backend")

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

@app.get("/health")
async def health_check():
    return JSONResponse(content={"status": "healthy"}, status_code=200)

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

if __name__ == "__main__":
    import uvicorn
    # Use load_dotenv before running uvicorn if calling via python main.py
    uvicorn.run(app, host="0.0.0.0", port=8000)
