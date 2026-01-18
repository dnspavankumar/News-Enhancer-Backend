# Frontend - Personalized News Feed

## Pages

### 1. `auth.html` - Login/Register Page
- User authentication
- New user registration with interests selection
- Stores JWT token in localStorage

### 2. `feed.html` - News Feed Page
- Displays personalized news based on user's top k interests
- Auto-refreshes every 5 minutes
- Manual refresh button
- Marks articles as read when clicked
- Shows countdown to next auto-refresh

## Features

✅ **Authentication**
- JWT-based authentication
- Secure token storage
- Auto-redirect if not logged in

✅ **Personalized Feed**
- News based on user's interests and goals
- Filters out already-read articles
- Grouped by interest category

✅ **Auto-Refresh**
- Refreshes every 5 minutes automatically
- Countdown timer
- Manual refresh option

✅ **User Experience**
- Clean, modern UI
- Responsive design
- Loading states
- Error handling
- Article tracking

## How to Use

1. **Start the backend:**
   ```bash
   python main.py
   ```

2. **Open the frontend:**
   - Open `auth.html` in your browser
   - Or use a local server:
     ```bash
     cd frontend
     python -m http.server 3000
     ```
     Then visit http://localhost:3000/auth.html

3. **Register a new account:**
   - Enter email and password
   - Fill in age and goals
   - Select at least 3 interests
   - Choose top k interests to show
   - Click "Create Account"

4. **View your feed:**
   - Automatically redirected to feed page
   - See your personalized news
   - Click articles to read (marks as read)
   - Feed auto-refreshes every 5 minutes

5. **Logout:**
   - Click "Logout" button in header
   - Returns to login page

## File Structure

```
frontend/
├── auth.html          # Login/Register page
├── auth.css           # Auth page styles
├── auth.js            # Auth logic
├── feed.html          # News feed page
├── feed.css           # Feed page styles
├── feed.js            # Feed logic & auto-refresh
└── README.md          # This file
```

## API Endpoints Used

- `POST /auth/register` - Create new user
- `POST /auth/login` - Login user
- `GET /auth/me` - Get user profile
- `GET /news/feed` - Get personalized news (authenticated)
- `POST /news/mark-read` - Mark article as read

## Configuration

Update `API_URL` in both `auth.js` and `feed.js` if backend is on different host:

```javascript
const API_URL = 'http://localhost:8000';
```

## Features to Add (Future)

- Settings page to update profile
- Search functionality
- Filter by date
- Save articles for later
- Share articles
- Dark mode
- Push notifications
