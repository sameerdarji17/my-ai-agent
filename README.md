# Django AI Agent — Starter Project

Ek complete, working AI agent jo Django par bana hai. **Default LLM provider
Groq hai** — free tier, koi billing/card nahi chahiye.

## Is version mein kya hai (v3)

- **Hinglish tone** — agent hamesha Roman script Hindi-English mix mein reply karta hai
- **Language matching** — Hindi poochoge to Hindi (Devanagari) mein jawab, English mein poochoge to English mein, Gujarati mein poochoge to Gujarati mein
- **Full chat UI** — Claude/ChatGPT jaisa center-search hero, jo pehle message ke baad neeche shift ho jata hai
- **Light/Dark mode** aur **collapsible sidebar**
- **Chat history** — sidebar mein purani conversations dikhti hain
- **File upload** — PDF, Word (.docx), text files padh sakta hai
- **Real email verification** — signup par asli verification email jaati hai, link click kiye bina account activate nahi hota
- **Free vs Premium**:
  - Free: 25 messages/day (logged in), 3 messages (anonymous, production mein)
  - Premium (₹109 / 3 months via Razorpay): unlimited messages + AI image generation
- **AI image generation** — Premium users ke liye (free API se, koi extra key nahi chahiye)
- **Admin panel** — `/admin/` par users, conversations, subscriptions sab manage kar sakte hain
- **Original logo** — apna khud ka abstract mark (koi copied logo nahi)

Tools already kaam kar rahe hain:

- `web_search` — live web search (Tavily API se, free tier)
- `read_file` — agent_files/ folder ki files padhna, ya upload ki hui files
- `list_files` — available files dikhana
- `execute_code` — Python code sandbox mein run karna
- `generate_image` — Premium users ke liye AI image generation (Pollinations.ai, free)
- `generate_kundli` — Real Vedic astrology birth chart calculation (Swiss Ephemeris se, koi API key nahi chahiye, sabke liye available)

**Note:** Video generation add nahi kiya hai — koi bhi free ya sasta reliable provider abhi available nahi hai (Runway/Luma jaise services bahut costly hote hain). Agar future mein chahiye, alag se paid API integrate karni hogi.

Yeh sirf ek chatbot nahi hai — is project mein ek **agent loop** hai jo khud
decide karta hai kaun sa tool use karna hai, use karke result wapas leta hai,
aur tab tak repeat karta hai jab tak final answer na mil jaaye.

---

## 1. Setup

```bash
cd myagent_project
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

`.env.example` ko copy karke `.env` banayein aur apni keys daalein:

```bash
cp .env.example .env
```

### Free keys kahan se lein

1. **Groq (LLM)** — https://console.groq.com par jaake sign up karein
   (Google/GitHub se), "API Keys" → "Create API Key". Koi card nahi chahiye.
   Key `gsk_...` se shuru hogi.
2. **Tavily (web search)** — https://tavily.com par sign up karein, dashboard
   mein hi key mil jaayegi (`tvly-...`). Free tier: 1000 searches/month.
3. **Razorpay (subscription, optional)** — https://dashboard.razorpay.com par
   sign up karein, "Test Mode" mein API Keys se test keys generate karein
   (`rzp_test_...`). Test mode mein real paisa nahi katega — test card
   numbers se checkout try kar sakte hain (Razorpay docs mein diye hain).

`.env` file mein daal dein:
```
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_xxxxxxxxxxxxx
TAVILY_API_KEY=tvly_xxxxxxxxxxxxx
RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxxx
RAZORPAY_KEY_SECRET=xxxxxxxxxxxxx
```

Agar `TAVILY_API_KEY` ya `RAZORPAY` keys nahi dete, to agent/site baaki sab
kaam karega — sirf wo specific feature (search / upgrade button) disabled
rahega, graceful message ke saath.

### Baad mein Claude (paid) par switch karna ho to

`.env` mein sirf ye 2 lines badal dein:
```
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx
```
Baaki poora code (tools, orchestrator, API) automatically kaam karega — koi
aur change nahi karna padega.

## 2. Database setup

```bash
python manage.py migrate
```

## 3. Terminal mein turant test karein (server chalaye bina)

```bash
python manage.py chat_with_agent
```

Isse aap seedha terminal mein agent se baat kar sakte hain aur dekh sakte hain
ki wo kaunse tools use kar raha hai.

## 4. Server chalayein

```bash
python manage.py runserver
```

### API endpoint

```
POST /api/agent/chat/
Content-Type: application/json

{
  "conversation_id": null,          // pehli baar null bhejein, response mein UUID milega
  "message": "Aaj Bitcoin ka price kya hai search karo"
}
```

Response:
```json
{
  "conversation_id": "xxxxxxxx-xxxx-...",
  "reply": "Bitcoin abhi $XX,XXX par trade ho raha hai...",
  "tool_trace": [
    {"tool": "web_search", "input": {"query": "bitcoin price today"}, "output": "..."}
  ]
}
```

Agli baar isi `conversation_id` ko bhejein taaki agent ko pichli baatcheet yaad rahe.

Conversation history dekhne ke liye:
```
GET /api/agent/conversations/<conversation_id>/
```

Django admin (`/admin/`) se bhi conversations, messages, aur tool-call logs
dekh sakte hain — pehle superuser banayein:
```bash
python manage.py createsuperuser
```

## 5. Files ke saath kaam karna

`agent_files/` folder (auto-create ho jata hai) mein koi bhi text file daal
dein — agent `list_files` aur `read_file` tools se use padh sakta hai.

## 6. Architecture — kaise kaam karta hai

```
User message
    │
    ▼
AgentOrchestrator.run()
    │
    ├──► Claude API call (system prompt + tool definitions + history)
    │
    ├──► Agar Claude tool maangta hai:
    │        agent/tools.py se wo tool run hota hai
    │        result wapas Claude ko diya jata hai
    │        (loop repeat hota hai — max MAX_AGENT_TURNS baar)
    │
    └──► Jab Claude final text de, wahi user ko return hota hai
```

Har cheez `agent/models.py` mein DB mein save hoti hai (Conversation, Message,
ToolCallLog) — isliye history persist rehti hai aur restart ke baad bhi
conversation continue ho sakti hai.

## 7. Naya tool add karna

1. `agent/tools.py` mein `TOOL_DEFINITIONS` list mein naya schema add karein
2. Ek `execute_<naam>(tool_input)` function likhein
3. `TOOL_DISPATCH` dict mein register karein

Bas — orchestrator automatically naya tool use karna seekh jayega, kyunki
wahi definitions Claude ko bheji jaati hain.

## 8. Production ke liye zaroori improvements (IMPORTANT)

Yeh project ek **solid starting point** hai, lekin production mein daalne se
pehle ye zaroor karein:

1. **Code sandboxing** — abhi `execute_code` ek plain subprocess use karta hai
   (timeout ke saath), jo host machine ke saath filesystem/network share
   karta hai. Untrusted users ke liye ye **kaafi nahi** hai. Docker
   (network-disabled container) ya E2B (e2b.dev) jaisi managed sandbox
   service use karein.
2. **Rate limiting** — `REST_FRAMEWORK` mein throttling already on hai, lekin
   production values apne traffic ke hisaab se tune karein.
3. **Async / background jobs** — lambe agent loops ke liye Celery ya Django
   Channels use karein taaki request thread block na ho.
4. **Streaming responses** — agar token-by-token output chahiye to
   `client.messages.stream()` (Anthropic SDK) ko Server-Sent Events se
   frontend tak bhejein.
5. **Postgres** — SQLite sirf dev ke liye hai; production mein Postgres use
   karein (`DATABASES` settings.py mein badal dein).
6. **Secrets** — `.env` ko kabhi git mein commit na karein (`.gitignore`
   already isko cover karta hai).
7. **Auth** — abhi API endpoints open hain; production mein DRF
   authentication/permission classes add karein.

## 10. Live deploy karna (Railway par, free)

1. https://railway.app par GitHub se sign up karein
2. Ye project GitHub repo mein push karein
3. Railway mein "New Project" → "Deploy from GitHub repo" → apna repo chunein
4. **Postgres addon add karein** — Railway project ke andar "+ New" → "Database" → "Add PostgreSQL". Ye automatically `DATABASE_URL` environment variable set kar dega, jisse aapka data har deploy ke baad safe rahega (SQLite ka data Railway ke temporary filesystem par delete ho jata hai).
5. Railway ke "Variables" tab mein ye set karein:
   ```
   LLM_PROVIDER=groq
   GROQ_API_KEY=...
   GROQ_MODEL=llama-3.3-70b-versatile
   TAVILY_API_KEY=...
   RAZORPAY_KEY_ID=...
   RAZORPAY_KEY_SECRET=...
   DJANGO_SECRET_KEY=<koi bhi random string>
   DJANGO_DEBUG=False
   DJANGO_ALLOWED_HOSTS=*.railway.app
   EMAIL_HOST=smtp.gmail.com
   EMAIL_PORT=587
   EMAIL_HOST_USER=your-email@gmail.com
   EMAIL_HOST_PASSWORD=your-gmail-app-password
   DEFAULT_FROM_EMAIL=your-email@gmail.com
   SITE_BASE_URL=https://<aapka-railway-domain>.up.railway.app
   ```
6. `Procfile` aur `requirements.txt` (gunicorn, whitenoise, psycopg2) already isi project mein hain — Railway inhe automatically detect karke deploy kar dega
7. Deploy hone ke baad Railway ek live URL dega — wahi `SITE_BASE_URL` mein daalein (varna verification email ka link galat domain par jayega), aur redeploy kar dein
8. `python manage.py createsuperuser` Railway ke shell se chalakar apna admin account bana lein (`/admin/` access ke liye)

**Important:** production mein `DJANGO_DEBUG=False` zaroor rakhein, aur `DJANGO_ALLOWED_HOSTS` mein apna asli Railway domain daalein.

## 11. Folder structure

```
myagent_project/
├── manage.py
├── requirements.txt
├── .env.example
├── agent_files/              # read_file tool ke liye files yahan daalein
├── sandbox_runs/             # execute_code ke temp scratch files
├── myagent_project/
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
└── agent/
    ├── models.py              # Conversation, Message, ToolCallLog
    ├── tools.py                # tool definitions + execution
    ├── orchestrator.py         # main agent loop
    ├── views.py                 # DRF API views
    ├── serializers.py
    ├── urls.py
    ├── admin.py
    └── management/commands/chat_with_agent.py   # terminal test tool
```

Bas — ab aap isme apne tools add karke, model swap karke, ya poora frontend
laga kar apna khud ka "Claude jaisa" agent chala sakte hain.
