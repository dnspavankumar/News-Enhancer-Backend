import requests
import json

# Test the personalized news endpoint
url = "http://localhost:8000/personalized-news"

with open("test_news_req.json", "r") as f:
    payload = json.load(f)

print("Testing /personalized-news endpoint...")
print(f"Request: {json.dumps(payload, indent=2)}\n")

response = requests.post(url, json=payload)

if response.status_code == 200:
    data = response.json()
    print("✓ Success!\n")
    print(f"Recommended Interests: {data['recommended_interests']}\n")
    
    for interest, articles in data['news_by_interest'].items():
        print(f"\n{'='*60}")
        print(f"NEWS FOR: {interest.upper()}")
        print(f"{'='*60}")
        for i, article in enumerate(articles, 1):
            print(f"\n{i}. {article['title']}")
            print(f"   Source: {article['source']}")
            print(f"   Link: {article['link']}")
            if article.get('date'):
                print(f"   Date: {article['date']}")
            if article.get('snippet'):
                print(f"   Snippet: {article['snippet'][:100]}...")
else:
    print(f"✗ Error: {response.status_code}")
    print(response.text)
