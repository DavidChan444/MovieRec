# README.md

## Project Overview

AI movie recommendation system — FastAPI backend + Vue 3 frontend with SQLite, ChromaDB vector search, LangChain LLM integration, and multi-algorithm recommendation (content-based, collaborative filtering, vector semantic search).

## Commands

### Backend

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server (port 8000, with hot-reload)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# Or directly:
python app/main.py

# Verify Python files compile (no tests exist)
python -c "import py_compile; py_compile.compile('app/main.py', doraise=True)"
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Dev server (port 3000, proxies /api to localhost:8000)
npm run dev

# Production build
npm run build
```

### Verification

```bash
# Backend: compile all Python files
find app -name "*.py" -exec python -c "import py_compile; py_compile.compile('{}', doraise=True)" \;

# Frontend: build check
cd frontend && npx vite build
```

## Architecture

```
app/
  main.py                    # FastAPI app entry, CORS, DB init, router registration
  data/database.py            # SQLAlchemy engine (SQLite), SessionLocal, Base
  core/
    config.py                 # Settings via pydantic-settings (DB path, OpenAI keys, behavior weights)
    security.py               # JWT tokens, password hashing (bcrypt via passlib)
  models/
    base.py                   # Abstract BaseModel with id, created_at, updated_at
    movie.py                  # Movie ORM (id, title, rating, genres, directors, actors, tags, etc.)
    user.py                   # User, UserInteraction, UserReview, UserPreferenceVector, ChatSession, ChatMessage
  routers/
    movies.py                 # GET /api/movies/search, /trending, /{id}, /{id}/similar; POST /recommend
    users.py                  # Auth (register, login), profile (get/update, preferences, interactions), user recommendations
    chat.py                   # POST /api/chat/ — LLM chat + recommendations, GET sessions/messages
  schemas/
    movie.py                  # MovieResponse, RecommendationRequest, RecommendationResponse
  services/
    recommendation.py         # RecommendationService — base recommendation, trending, advanced search
    adaptive_recommendation_service.py  # AdaptiveRecommendationService — multi-algorithm fusion with user preferences
    vector_service.py         # ChromaDB vector store — semantic search via SentenceTransformer embeddings
    langchain_service.py      # LangChain + ChatOpenAI — query analysis, recommendation reasons, chat responses
    llm_service.py            # Raw OpenAI fallback when LangChain unavailable
    user_behavior_service.py  # User interaction tracking, preference learning, behavior statistics
    data_preprocessor.py      # Builds text prompts from Movie/UserProfile for LLM consumption

frontend/src/
  main.js                     # Vue app entry (Pinia, Router, Element Plus, global styles)
  App.vue                     # Root layout: NavBar + router-view
  router/index.js             # Vue Router — 7 routes, JWT-based auth guard
  stores/user.js              # Pinia store — user state, login/register/logout actions
  api/index.js                # Axios client — userAPI, movieAPI, chatAPI (proxy /api → :8000)
  styles/main.css             # Global styles
  components/
    MovieCard.vue             # Reusable card: poster, rating, hover actions (like/dislike/watched)
    NavBar.vue                # Top navigation bar
  views/
    Home.vue                  # Hero search + "For You" recommendations + trending
    Movies.vue                # Search bar + movie grid (vector-enhanced search via /movies/search)
    MovieDetail.vue           # Full detail + similar movies + rating dialog + like/dislike/watched
    Chat.vue                  # LLM chat with session management + MovieCards in responses
    Profile.vue               # Profile edit, preference analytics, liked/watched movie grids, interaction history
    Login.vue / Register.vue  # Auth forms
```

## Key Design Points

### Recommendation Pipeline

1. **Query analysis** — `langchain_service.analyze_user_query()` extracts genres, mood, rating_preference, excluded_genres, keywords from user text via LLM. Falls back to keyword matching in `_fallback_analysis()`.

2. **Multi-algorithm fusion** — `adaptive_recommendation_service._generate_multi_algorithm_recommendations()` runs 3 algorithms in parallel:
   - **Content-based**: Filter by genre preferences/query genres, score by personalized match
   - **Vector search**: Semantic similarity via ChromaDB + SentenceTransformer (`paraphrase-multilingual-MiniLM-L12-v2`)
   - **Collaborative**: Find similar users by genre preference overlap, recommend movies those users liked (`UserInteraction` table)

3. **Post-processing** — Deduplication → personalized filtering → diversity injection → LangChain enrichment (relevance scoring) → controlled shuffle (keep top-2, shuffle rest)

4. **Query enhancement** — `_enhance_query_with_preferences()` only adds user preference genres when query lacks explicit genre keywords (prevents polluting "科幻电影" with unrelated user preferences)

### User Interaction System

Interaction types: `like`, `cancel_like`, `dislike`, `cancel_dislike`, `view`, `cancel_view`, `share`, `search`, `click`

Behavior weights in `config.py` → `BEHAVIOR_WEIGHT_CONFIG`. Cancel operations undo the original interaction (delete the record, decrement counters). Recorded in `UserInteraction` table for collaborative filtering signal.

### ChromaDB Vector Store

- Collection name: `movie_collection`
- Text built from: title + genres + tags + directors + actors + summary + rating
- `_get_or_create_collection()` handles 3 cases: new collection (init), existing populated (return as-is), existing empty (init)
- If tags field missing in metadata → auto-rebuild

### Frontend Data Flow

- All API calls go through `api/index.js` Axios instance with JWT interceptor
- 401 responses auto-redirect to `/login`
- Auth state: Pinia `userStore` + localStorage token/user backup
- `MovieCard` accepts `initialLiked`/`initialWatched` props for correct icon display (used in Profile liked/watched tabs)
- MovieCard emits `unliked`/`unwatched` events for reactive removal from Profile grids
- Broken poster images → CSS "暂无封面" fallback

### Database

SQLite via SQLAlchemy with `check_same_thread=False`. Tables auto-created on startup via `Base.metadata.create_all()`. Session pattern: `db = SessionLocal(); try: ... finally: db.close()`.

Removed features: favorites (收藏) — `total_favorites` column kept for DB compatibility but unused. `UserPlaylist` model deleted.

## Environment

Config loaded from `.env` at project root, falling back to defaults in `app/core/config.py`. Key env vars: `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, `JWT_SECRET_KEY`, `CHROMA_PERSIST_DIRECTORY`.
