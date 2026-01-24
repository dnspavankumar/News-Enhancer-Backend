"""
Chat Service - Handles chatbot interactions with news context
"""
import google.genai as genai
from typing import List, Optional, Dict
from datetime import datetime
import json


class ChatService:
    """Service for handling chat interactions with news context"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = genai.Client(api_key=api_key)
        self.conversation_history = []
        self.current_news_context = []
    
    def _build_context_prompt(self, news_articles: Optional[List] = None) -> str:
        """Build context prompt from news articles"""
        if not news_articles or len(news_articles) == 0:
            return "No news articles are currently loaded."
        
        context = "Here are the current news articles the user is viewing:\n\n"
        
        for i, article in enumerate(news_articles, 1):
            # Handle both dict and object formats
            if isinstance(article, dict):
                title = article.get('title', 'No title')
                source = article.get('source', 'Unknown')
                content = article.get('content', article.get('snippet', 'No content'))
                link = article.get('link', '')
            else:
                title = getattr(article, 'title', 'No title')
                source = getattr(article, 'source', 'Unknown')
                content = getattr(article, 'content', getattr(article, 'snippet', 'No content'))
                link = getattr(article, 'link', '')
            
            context += f"Article {i}:\n"
            context += f"Title: {title}\n"
            context += f"Source: {source}\n"
            context += f"Content: {content[:500]}...\n"
            context += f"Link: {link}\n\n"
        
        return context
    
    def chat(self, message: str, news_context: Optional[List] = None, user_profile: Optional[Dict] = None) -> Dict:
        """
        Process a chat message with news context and user profile.
        Returns a response from the AI assistant.
        """
        # Update news context if provided
        if news_context:
            self.current_news_context = news_context
        
        # Build the full prompt with context
        context_prompt = self._build_context_prompt(self.current_news_context)
        
        # Build user profile context
        profile_context = ""
        if user_profile:
            print(f"DEBUG: Received user profile: {user_profile}")  # Debug log
            age = user_profile.get('age', 'Unknown')
            goals = user_profile.get('goals', 'Not specified')
            interests = user_profile.get('interests', [])
            profession = user_profile.get('profession', 'Not specified')
            
            # Convert goals array to string if needed
            if isinstance(goals, list):
                goals = ', '.join(goals)
            
            # Convert interests array to string
            if isinstance(interests, list):
                interests = ', '.join(interests)
            
            profile_context = f"""
USER PROFILE (THIS IS THE PERSON YOU'RE TALKING TO):
- Age: {age} years old
- Profession: {profession}
- Goals: {goals}
- Interests: {interests}

YOU MUST USE THIS PROFILE INFORMATION IN YOUR RESPONSE!
When they ask "How does this affect me?", analyze the news impact for a {age}-year-old {profession} with goals of {goals}.
"""
        else:
            print("WARNING: No user profile provided!")  # Debug log
        
        system_instruction = f"""You are a PERSONALIZED news impact assistant. You MUST analyze news specifically for the user based on their profile.

{profile_context}

{context_prompt}

CRITICAL INSTRUCTIONS:
1. When user asks "How does this affect me?" - You MUST give a PERSONALIZED answer based on their age ({user_profile.get('age', 'X')}), profession ({user_profile.get('profession', 'X')}), and goals ({goals})
2. DO NOT say "As an AI" or give generic responses
3. Speak directly to the user as if you're their personal financial/news advisor
4. Use their specific details in your response
5. Give actionable, specific advice based on their situation
6. If the news doesn't affect them, explain WHY based on their profile

Example response format:
"Based on your profile - you're {user_profile.get('age', 'X')} years old, working as a {user_profile.get('profession', 'professional')}, with goals of {goals} - here's how this news impacts YOU specifically: [detailed personal impact]. I recommend you [specific actions for their situation]."

Remember: You are speaking TO the user, not ABOUT them. Use "you" and "your" extensively. Make it personal!"""

        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": message
        })
        
        # Build conversation for Gemini
        conversation_text = system_instruction + "\n\n"
        
        # Add recent conversation history (last 10 messages)
        recent_history = self.conversation_history[-10:]
        for msg in recent_history:
            role = "User" if msg["role"] == "user" else "Assistant"
            conversation_text += f"{role}: {msg['content']}\n\n"
        
        try:
            # Generate response
            response = self.client.models.generate_content(
                model='gemini-2.0-flash-exp',
                contents=conversation_text
            )
            
            assistant_message = response.text.strip()
            
            # Add assistant response to history
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_message
            })
            
            return {
                "response": assistant_message,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            raise Exception(f"Failed to generate chat response: {str(e)}")
    
    def reset_conversation(self):
        """Reset the conversation history"""
        self.conversation_history = []
        self.current_news_context = []
