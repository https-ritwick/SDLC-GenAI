# DevMind Studio 🧠

An AI-powered coding IDE — generate, edit, and preview full web projects in real time using Google Gemini.

---

## Prerequisites

- Python 3.10+
- A [Google Gemini API key](https://aistudio.google.com/app/apikey) (free tier works)

---

## Setup & Run

### 1. Install dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Set your Gemini API key

**Option A — `.env` file (recommended):**

```bash
# inside the backend/ folder
echo "GEMINI_API_KEY=AIza..." > .env
```

**Option B — In the UI:**  
Open Settings (⚙️ top-right) → paste key → Save.

### 3. Start the server

```bash
cd backend
python main.py
```

Server starts on **http://localhost:8000**

### 4. Open the app

Visit [http://localhost:8000](http://localhost:8000) in any modern browser.

---

## How to use

1. **Create a project** — Click "+ New Project" in the header.
2. **Chat with DevMind** — Type what you want to build in the left panel.  
   e.g. *"Build a to-do app with local storage and a clean dark theme"*
3. **Watch it build** — Files are created in real time; the Preview tab refreshes automatically.
4. **Edit manually** — Switch to the Code tab, pick a file from the tree, edit, and press **Ctrl+S** to save.
5. **Inspect logs** — The Logs tab shows every AI action and file operation.

---

## Project structure

```
devmind-studio/
├── backend/
│   ├── main.py            # FastAPI app, REST + WebSocket endpoints
│   ├── gemini_service.py  # Gemini 2.0 Flash integration + chat sessions
│   ├── file_manager.py    # Project filesystem management
│   └── requirements.txt
└── frontend/
    ├── index.html          # IDE shell
    ├── css/style.css       # Dark "Midnight Blueprint" theme
    └── js/
        ├── app.js          # App controller, WebSocket lifecycle
        ├── chat.js         # Chat panel + markdown rendering
        ├── editor.js       # CodeMirror editor + file tree
        ├── preview.js      # iframe preview + device switching
        └── logs.js         # Terminal-style logs panel
```

---

## Architecture

```
Browser  ──WebSocket──▶  FastAPI (main.py)
                              │
                    ┌─────────┴──────────┐
                    ▼                    ▼
            GeminiService          FileManager
         (Gemini 2.0 Flash)    (projects/ on disk)
```

**WebSocket message flow:**
- Client sends `{type: "chat", message: "..."}`
- Backend fetches full project file context → sends to Gemini
- Gemini returns `{message, actions[], logs[], status}`
- Backend executes file actions (create/update/delete)
- Backend emits `file_update` events → client refreshes editor & preview

---

## Tips

- Projects are stored in `backend/projects/<project-id>/`
- You can open the preview in a new tab for full-size testing
- Use the **device toggle** (🖥 📱) in the preview toolbar to test responsiveness
- Ask DevMind to *"add a feature"*, *"fix the layout"*, or *"refactor the JS"* — it maintains full context
