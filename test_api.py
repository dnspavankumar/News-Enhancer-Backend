"""
Simple test script to verify the API is working
Run this after starting the server with: python main.py
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_health():
    """Test health endpoint"""
    print("Testing /health endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}\n")

def test_recommend_interests():
    """Test interest recommendation"""
    print("Testing /recommend-interests endpoint...")
    data = {
        "age": 25,
        "goals": "Become a senior software engineer and stay healthy",
        "interests": ["coding", "gaming", "hiking", "cooking", "yoga"],
        "k": 3
    }
    response = requests.post(f"{BASE_URL}/recommend-interests", json=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")
    return response.json()

def test_personalized_news():
    """Test personalized news"""
    print("Testing /personalized-news endpoint...")
    data = {
        "age": 25,
        "goals": "Become a senior software engineer and stay healthy",
        "interests": ["coding", "gaming", "hiking"],
        "k": 2
    }
    response = requests.post(f"{BASE_URL}/personalized-news", json=data)
    print(f"Status: {response.status_code}")
    result = response.json()
    print(f"Recommended Interests: {result['recommended_interests']}")
    for interest, articles in result['news_by_interest'].items():
        print(f"\n{interest}: {len(articles)} articles")
        if articles:
            print(f"  First article: {articles[0]['title'][:60]}...")
    return result

def test_chat():
    """Test chat endpoint"""
    print("\nTesting /chat endpoint...")
    
    # First get some news for context
    news_data = test_personalized_news()
    
    # Extract all articles for context
    all_articles = []
    for articles in news_data['news_by_interest'].values():
        all_articles.extend(articles)
    
    # Chat about the news
    chat_data = {
        "message": "What are the main topics in these articles?",
        "news_context": all_articles[:5]  # Send first 5 articles
    }
    
    response = requests.post(f"{BASE_URL}/chat", json=chat_data)
    print(f"\nChat Status: {response.status_code}")
    print(f"AI Response: {response.json()['response']}\n")
    
    # Follow-up question
    chat_data2 = {
        "message": "Can you summarize the most interesting article?",
        "news_context": all_articles[:5]
    }
    response2 = requests.post(f"{BASE_URL}/chat", json=chat_data2)
    print(f"AI Response 2: {response2.json()['response']}\n")

def test_chat_reset():
    """Test chat reset"""
    print("Testing /chat/reset endpoint...")
    response = requests.post(f"{BASE_URL}/chat/reset")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}\n")

if __name__ == "__main__":
    print("=" * 60)
    print("API Test Suite")
    print("=" * 60 + "\n")
    
    try:
        test_health()
        test_recommend_interests()
        test_chat()
        test_chat_reset()
        
        print("=" * 60)
        print("All tests completed!")
        print("=" * 60)
    except Exception as e:
        print(f"\nError: {str(e)}")
        print("Make sure the server is running: python main.py")
