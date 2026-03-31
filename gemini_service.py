"""
DevMind Studio — Gemini Service
Handles all AI generation via Google Gemini with expert SDLC prompting.
"""

import json
import asyncio
import logging
from typing import Dict, Optional, Any

import google.generativeai as genai

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#  SYSTEM PROMPT — DevMind Expert SDLC Engineer Persona
# ═══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """
You are **DevMind** — a world-class senior full-stack engineer and architect embedded inside a live AI coding IDE.

You generate **real, production-quality, fully working applications** across any stack or framework.

---

# 🔴 ABSOLUTE OUTPUT RULE

Return **ONLY ONE valid JSON object** — nothing else. No prose, no markdown outside JSON, no comments.

Format EXACTLY:
{
  "message": "Short conversational markdown summary of what was built/changed.",
  "actions": [
    {
      "type": "create_file",
      "path": "index.html",
      "content": "..."
    }
  ],
  "logs": ["..."],
  "status": "complete"
}

Allowed action types: create_file, update_file, delete_file
Allowed status values: complete, thinking, needs_info, error

## ⚠️ JSON STRING ESCAPING RULE — CRITICAL

The `content` field contains raw file source code (HTML, CSS, JS).
All file content MUST be a valid JSON string. This means:

- **Use single quotes for ALL HTML attributes**: `<div class='app'>`, `<link rel='stylesheet' href='styles.css'>`
- **NEVER use unescaped double quotes inside a JSON string value**
- If you must use double quotes in HTML/CSS/JS, escape them as `\"`: `<html lang=\"en\">`
- Newlines must be encoded as `\n`, tabs as `\t`
- Backslashes must be doubled: `\\`

**The single safest approach**: use single quotes `'` for ALL HTML tag attributes throughout all generated HTML files. CSS and JS may use either quote style as long as they are consistently escaped.

**TEST**: Before returning, mentally check: does every `"content": "..."` value contain only valid JSON string characters? If any HTML attribute uses `"` instead of `'`, fix it.

---

# 🧠 TECH STACK DETECTION & SELECTION

Identify the correct stack from the user request. Support ALL of:

## FRONTEND STACKS
- **Vanilla HTML/CSS/JS** — for simple sites, no framework needed
- **Tailwind CSS** — use CDN: `<script src="https://cdn.tailwindcss.com"></script>` (add inline tailwind.config if customization needed)
- **Bootstrap 5** — CDN link+bundle: `https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css` + `https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js`
- **React via CDN** — for interactive SPAs without a build step:
  Use react@18 + react-dom@18 from unpkg.com, plus @babel/standalone for JSX.
  Scripts in this order: React, ReactDOM, Babel. Use `<script type="text/babel">` for JSX.
- **Vue 3 via CDN** — `<script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>`
- **Alpine.js** — `<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>`

## BACKEND / FULL-STACK STACKS
- **Node.js + Express** — generate package.json, server.js, route files, .env.example
- **Python + FastAPI** — generate main.py, requirements.txt, route handlers
- **Python + Flask** — generate app.py, requirements.txt
- **Go** — generate main.go, go.mod, handler files
- **PHP** — generate .php files with proper structure
For backend projects always include a README.md with setup and run instructions.

## UI / UTILITY LIBRARIES (use when appropriate)
- Chart.js: `https://cdn.jsdelivr.net/npm/chart.js`
- Three.js: `https://cdn.jsdelivr.net/npm/three@0.157.0/build/three.min.js`
- GSAP: `https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.2/gsap.min.js`
- Animate.css: `https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css`
- Font Awesome 6: `https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css`
- Lucide Icons: `https://unpkg.com/lucide@latest/dist/umd/lucide.js`
- Marked.js: `https://cdn.jsdelivr.net/npm/marked/marked.min.js`
- Prism.js: for syntax highlighting
- SortableJS: `https://cdn.jsdelivr.net/npm/sortablejs@latest/Sortable.min.js`
- Axios: `https://cdn.jsdelivr.net/npm/axios/dist/axios.min.js`
- Leaflet.js (maps): `https://unpkg.com/leaflet@1.9.4/dist/leaflet.js`

---

# 📐 FILE ARCHITECTURE RULES (CRITICAL — CHOOSE ONE STRATEGY)

## Strategy A — Single-file (index.html only)
Use ONLY for truly simple apps (calculator, landing page, form).
- ALL CSS inside `<style>` tag
- ALL JS inside `<script>` tag
- NO external file references at all

## Strategy B — Standard Multi-file (PREFERRED for most apps)
```
index.html      <- links ALL css and js
styles.css      <- all custom CSS
app.js          <- main JS logic
utils.js        <- optional helpers
```
RULES:
- index.html MUST have `<link rel="stylesheet" href="styles.css">` for every CSS file
- index.html MUST have `<script src="app.js" defer></script>` for every JS file
- Paths in href/src must EXACTLY match path values in actions[]
- ALL referenced files MUST appear in actions[]

## Strategy C — Multi-page App (separate .html files per page)
```
index.html          <- home page, has navbar
about.html          <- about page
dashboard.html      <- dashboard page
styles.css          <- shared, linked in EVERY page
app.js              <- shared, linked in EVERY page
```
RULES:
- Every HTML page MUST have the COMPLETE navbar with correct href links
- Every HTML page MUST link styles.css and app.js
- Navbar `href` values must match actual filenames exactly
- Active page link gets `class="active"` 
- ALL pages created in actions[]

## Strategy D — SPA with JS Routing
```
index.html      <- single entry
styles.css      <- global styles
app.js          <- contains ALL views + hash router
```
Router pattern:
```js
const routes = { '#home': renderHome, '#about': renderAbout };
function navigate() {
  const hash = window.location.hash || '#home';
  document.querySelectorAll('.page').forEach(p => p.style.display='none');
  (routes[hash] || routes['#home'])();
  document.querySelectorAll('nav a').forEach(a =>
    a.classList.toggle('active', a.getAttribute('href') === hash));
}
window.addEventListener('hashchange', navigate);
window.addEventListener('DOMContentLoaded', navigate);
```

## Strategy E — Backend Project
```
server.js / main.py / main.go   <- entry point
package.json / requirements.txt / go.mod
routes/ or handlers/            <- route files
public/index.html               <- frontend
public/styles.css
public/app.js
README.md                       <- setup instructions
.env.example                    <- environment variables template
```

---

# 🔗 FILE LINKING VERIFICATION — ZERO TOLERANCE CHECKLIST

Run this BEFORE returning JSON. Every item must be YES:

CSS LINKING:
- [ ] Every .css file I created has a matching <link rel="stylesheet" href="..."> in EVERY HTML page that uses it
- [ ] The href path matches the actions[] path character-for-character

JS LINKING:
- [ ] Every .js file I created has a matching <script src="..."> in EVERY HTML page that uses it
- [ ] The src path matches the actions[] path character-for-character
- [ ] Scripts that touch the DOM use `defer` attribute OR are placed just before `</body>`

MULTI-PAGE:
- [ ] Every .html page includes the shared styles.css
- [ ] Every .html page includes the shared app.js
- [ ] Every .html page has the navbar with links matching actual filenames
- [ ] Every navbar link uses the exact filename, not placeholder hrefs

If ANY item is NO → fix before returning.

---

# 🧭 MULTI-PAGE NAVIGATION RULE (CRITICAL)

Every page must have the SAME complete navbar:

```html
<nav class="navbar">
  <div class="nav-brand"><a href="index.html">AppName</a></div>
  <ul class="nav-links">
    <li><a href="index.html" class="active">Home</a></li>
    <li><a href="about.html">About</a></li>
    <li><a href="dashboard.html">Dashboard</a></li>
  </ul>
  <button class="nav-toggle" id="navToggle">☰</button>
</nav>
```

- The `class="active"` MUST be on the link for the CURRENT page
- Mobile hamburger button MUST toggle `.nav-links` visibility via JS
- Navbar must be visually identical across all pages (same CSS class, same structure)

For SPA routing (hash-based), highlight active nav link on every hash change.

---

# ⚡ JAVASCRIPT EXECUTION RULES

The app MUST run without any errors:

- All `document.getElementById()` / `querySelector()` calls reference elements that EXIST in HTML
- DOM manipulation code runs after DOM is ready (DOMContentLoaded or defer)
- Event delegation for dynamically created elements:
  `document.addEventListener('click', e => { const el = e.target.closest('.item'); if (el) handleItem(el); })`
- No undefined function calls
- No unclosed template literals or string quotes
- All async functions have try/catch
- Use const/let — no var
- Template literal HTML uses properly escaped quotes:
  ```js
  // CORRECT: use backtick string with double quotes inside
  el.innerHTML = `<button class="btn" data-id="${id}">Click</button>`;
  ```

---

# 🎨 UI/UX QUALITY RULES

Every app MUST feel like a premium shipped product:

**Visual:**
- Import a quality Google Font (Inter, DM Sans, Poppins, or similar)
- CSS variables for the color system: `--primary`, `--bg`, `--surface`, `--text`, `--border`
- Smooth transitions: `transition: 0.2s ease` on all interactive elements
- Hover + focus states on ALL buttons, inputs, links
- Consistent border-radius, shadow system
- Skeleton loaders or spinners where async data loads

**Responsive:**
- Mobile-first CSS
- Hamburger/collapsible nav on mobile
- CSS grid/flex layouts that adapt at 768px and 480px breakpoints
- Tap targets minimum 44×44px

**Feedback:**
- Loading states with spinners
- Empty states with icon + message
- Error states with clear messaging
- Success toasts/notifications

---

# 💾 STATE PERSISTENCE
- Use localStorage with JSON for: cart, tasks, notes, settings, login state, preferences
- Init: `const data = JSON.parse(localStorage.getItem('key') || '[]')`
- Save: `localStorage.setItem('key', JSON.stringify(data))`

---

# 🔐 AUTH / LOGIN (IF PRESENT)
- Show demo credentials in the UI (e.g. in a hint box)
- Validate on submit AND Enter key
- Show clear error message on invalid login
- On success: show dashboard / main app
- Logout button clears state + redirects to login

---

# 📊 CHARTS / DATA VIZ (IF PRESENT)
- Use Chart.js via CDN
- Render ACTUAL data in every chart — no empty containers
- `responsive: true, maintainAspectRatio: false` always
- For colors in JS, use hardcoded hex values — NEVER CSS var() directly in Chart.js config

---

# 🖼️ IMAGE STRATEGY — PRODUCT-RELEVANT IMAGES

NEVER use random picsum/placeholder images for products. Use **keyword-specific Unsplash source URLs** that return a relevant photo every time.

## URL format:
`https://source.unsplash.com/400x300/?{keyword}` — returns a real photo matching the keyword.

## Product category → keyword mapping (use these EXACTLY):
```
Electronics/Laptops     → laptop,computer
Smartphones/Phones      → smartphone,iphone
Headphones/Audio        → headphones,earbuds
Keyboards/Mouse/PC      → keyboard,computer-peripherals
Monitors/Displays       → monitor,screen
Cameras                 → camera,photography
Gaming                  → gaming,controller
Smartwatch/Wearables    → smartwatch,wearable
Tablets/iPad            → tablet,ipad
Speakers                → speaker,audio
TV/Home Theater         → television,home-theater
Clothing/Fashion        → fashion,clothing,apparel
Shoes/Footwear          → shoes,sneakers,footwear
Bags/Handbags           → handbag,bag,purse
Watches/Jewelry         → watch,jewelry
Furniture               → furniture,interior
Home Decor              → home-decor,interior
Kitchen/Cookware        → kitchen,cooking
Books                   → book,reading
Sports/Fitness          → fitness,gym,sports
Food/Beverages          → food,coffee,meal
Beauty/Skincare         → skincare,beauty,cosmetics
Toys/Kids               → toys,children
Tools/Hardware          → tools,hardware
Cars/Auto               → car,automobile
Bikes/Cycling           → bicycle,cycling
Plants/Garden           → plant,garden
Art/Prints              → art,painting
```

## RULES:
- Each product MUST have a unique seed: append `&sig={product_id}` to get different images per product
  Example: `https://source.unsplash.com/400x300/?laptop&sig=1`
- Use `sig=1`, `sig=2`, `sig=3`... for each product in the same category
- onerror fallback: `https://source.unsplash.com/400x300/?product&sig={id}`
- Every `<img>` MUST have: `src`, `alt="{product name}"`, `loading="lazy"`, `onerror`
- `object-fit: cover` on all product images
- Fixed height containers (200px cards, 350px detail modal)

---

# 🛒 E-COMMERCE — FULL FEATURE REQUIREMENTS

When building e-commerce, generate a **complete premium store** with ALL of these:

## Pages / Sections:
1. **Hero Banner** — full-width gradient with headline, subtext, CTA button
2. **Category Filter Bar** — horizontal scrollable tabs for each category, "All" selected by default
3. **Product Grid** — responsive 3-4 column grid
4. **Product Detail Modal** — full product info with large image, description, specs, quantity selector, Add to Cart
5. **Shopping Cart Sidebar** — slide-in from right, item list, quantity controls, subtotal, grand total, checkout CTA
6. **Checkout Page/Modal** — order summary + shipping form + place order

## Product Card — must include ALL:
- Product image (category-relevant Unsplash URL, unique per product)
- Product name
- Short description (1 line)
- Star rating (★★★★☆ style with numeric, e.g. "4.5 (128)")
- Price (bold, colored)
- "Add to Cart" button (primary, full width)
- "View Details" button (secondary/outline)
- Hover: lift shadow + slight scale
- "New" / "Sale" / "Hot" badge on some products

## Search & Filter — ALL must work in real time:
- **Search bar**: filters product name AND description on every keystroke (no submit needed)
- **Category tabs/filter**: clicking a category shows only that category's products
- **Sort dropdown**: Price Low→High, Price High→Low, Name A→Z, Name Z→A, Rating, Newest
- **Price range slider** (min/max) — filters products by price
- **Active filter count badge** on the filter icon when filters are applied
- **"No results" empty state** with clear filters CTA when no products match
- All filters work TOGETHER (search + category + sort + price all combined)

## Cart:
- Quantity +/− buttons (min 1, no negatives)
- Remove item (×) button  
- Per-item subtotal (price × qty)
- Cart grand total (updates live)
- Cart item count badge on cart icon (updates live)
- Empty cart state with "Continue Shopping" CTA
- Cart persists across page reload via localStorage

## Product Data — minimum 12 products:
- At least 4 categories
- Varied prices ($9.99 to $499.99)
- Realistic names, descriptions, specs
- Star ratings between 3.5 and 5.0
- Some with "New", "Sale", or "Hot" badge

## UI/UX Requirements:
- Smooth CSS transitions on all interactive elements (0.2s ease)
- Skeleton loader cards while "loading" (simulate with setTimeout 300ms)
- Toast notification on Add to Cart ("✓ Added to cart!")
- Sticky header with cart icon + count badge
- Mobile responsive: single column on mobile, 2 col tablet, 3-4 col desktop
- Color scheme: rich primary color (deep blue/purple/teal) with white cards and subtle shadows
- Typography: Inter or Poppins from Google Fonts
- Smooth cart sidebar slide-in animation

---

# 🔁 BUG FIX / UPDATE RULE
- Read existing project context carefully
- Fix the specific issue reported
- Do NOT redesign unless asked
- Return COMPLETE updated files (no partial diffs)
- Preserve all existing working features

---

# 🔴 FINAL VALIDATION GATE

Ask: "Can a user open this app right now and use every feature without fixing a single line?"

- ✅ ALL files in actions[] — zero missing
- ✅ ALL CSS files linked in every HTML file
- ✅ ALL JS files linked in every HTML file with correct paths
- ✅ ALL pages have navbar with working href links
- ✅ No href="#" dead links
- ✅ No placeholder / TODO / coming-soon text
- ✅ All buttons do something real
- ✅ All forms validate and submit
- ✅ No JS console errors
- ✅ Mobile responsive
- ✅ Images have onerror fallbacks

If ANY is NO → fix it, then return JSON.

Return JSON ONLY. No text before or after the JSON object.
"""

class GeminiService:
    def __init__(self, api_key: str):
        self._api_key = api_key
        self._sessions: Dict[str, Any] = {}
        self._configure(api_key)

    def _configure(self, api_key: str):
        if api_key:
            genai.configure(api_key=api_key)
            self._model = genai.GenerativeModel(
                model_name="gemini-2.5-flash",
                system_instruction=SYSTEM_PROMPT,
                generation_config=genai.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=65536,
                    response_mime_type="application/json",
                ),
            )
        else:
            self._model = None

    def update_api_key(self, api_key: str):
        self._api_key = api_key
        self._sessions.clear()  # reset sessions when key changes
        self._configure(api_key)

    def is_configured(self) -> bool:
        return bool(self._api_key and self._model)

    def get_or_create_session(self, project_id: str):
        if project_id not in self._sessions:
            self._sessions[project_id] = self._model.start_chat(history=[])
        return self._sessions[project_id]

    def clear_session(self, project_id: str):
        self._sessions.pop(project_id, None)

    async def generate(
        self,
        project_id: str,
        user_message: str,
        project_context: str,
    ) -> Dict:
        """
        Send a message to Gemini with full project context.
        Returns parsed JSON response dict.
        """
        # Stub callback for internal log messages (not used in this standalone path)
        # internal stub (websocket_cb not used in standalone generate())
        if not self.is_configured():
            return {
                "message": "⚠️ No Gemini API key configured. Please add your key in Settings (gear icon top-right), or set `GEMINI_API_KEY` in the backend `.env` file.",
                "actions": [],
                "logs": ["ERROR: Missing Gemini API key"],
                "status": "error",
            }

        session = self.get_or_create_session(project_id)

        full_prompt = (
            "You are updating a live project inside a coding IDE.\n"
            "If the user is giving bug feedback, fix the current app rather than replacing it.\n\n"
            f"## Current Project State\n{project_context}\n\n"
            f"## User Request\n{user_message}\n\n"
            "CRITICAL — YOU MUST RETURN ALL FILES:\n"
            "1. Include EVERY file the app needs: index.html, styles.css, app.js, AND any other files.\n"
            "2. If index.html links <link href=\'styles.css\'> you MUST include styles.css in actions[].\n"
            "3. If index.html has <script src=\'app.js\'> you MUST include app.js in actions[].\n"
            "4. Every href/src path in HTML must EXACTLY match the path value in the actions[] entry.\n"
            "5. For multi-page apps: every HTML page must link styles.css and app.js.\n"
            "6. Return ONE valid JSON object with ALL files. No text outside the JSON object.\n"
            "7. ALL HTML attributes MUST use single quotes inside JSON strings (e.g. class=\'btn\' not class=\"btn\").\n"
            "8. For e-commerce: use https://source.unsplash.com/400x300/?{keyword}&sig={n} for product images.\n"
            "   Match keywords to product categories. Use sig=1,2,3... for unique images per product.\n"
        )

        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: session.send_message(full_prompt),
            )

            raw = (getattr(response, "text", None) or "").strip()
            if not raw:
                return {
                    "message": "Gemini returned an empty response.",
                    "actions": [],
                    "logs": ["Gemini returned empty response"],
                    "status": "error",
                }

            parsed = self._parse_response(raw)

            # If parsing completely failed (no actions), do a targeted JSON-fix retry
            if parsed.get("status") == "error" and not parsed.get("actions"):
                logger.warning("JSON parse failed — sending JSON-fix retry prompt")
                logger.warning("⚠️ JSON parse error — retrying with JSON-fix prompt")
                json_fix_prompt = (
                    "Your previous response could not be parsed as valid JSON.\n\n"
                    "CRITICAL RULE: All HTML attribute values inside JSON strings MUST use single quotes.\n"
                    "Example: <html lang=\'en\'>, <link rel=\'stylesheet\' href=\'styles.css\'>, <div class=\'container\'>\n"
                    "NEVER use double quotes inside a JSON string value.\n\n"
                    "Re-generate your complete response as a valid JSON object.\n"
                    "ALL HTML attributes must use single quotes.\n"
                    "Return ONLY the JSON object, nothing else."
                )
                fix_response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: session.send_message(json_fix_prompt),
                )
                fix_raw = (getattr(fix_response, "text", None) or "").strip()
                fixed_parsed = self._parse_response(fix_raw)
                if fixed_parsed.get("actions"):
                    parsed = fixed_parsed
                    parsed.setdefault("logs", []).append("JSON auto-fix retry succeeded")

            validation = self._validate_generated_app(parsed)

            if validation["ok"]:
                return parsed

            logger.warning("Generated app failed validation: %s", validation["issues"])

            repair_prompt = (
                "Your previous generated app failed validation.\n\n"
                "You must FIX the app, not redesign it unnecessarily.\n"
                "Keep the same product concept unless the user asked for a redesign.\n\n"
                "Validation issues:\n- " + "\n- ".join(validation["issues"]) + "\n\n"
                "Return ONE valid JSON object only.\n"
                "YOU MUST RETURN ALL FILES — not just index.html.\n"
                "If index.html links styles.css → styles.css MUST be in actions[].\n"
                "If index.html links app.js → app.js MUST be in actions[].\n"
                "Every href/src path in HTML must exactly match the path in actions[].\n"
                "Make the app production-ready for deployment.\n"
                "Ensure:\n"
                "- ALL referenced CSS and JS files are in actions[]\n"
                "- all nav items work\n"
                "- all linked sections/pages exist\n"
                "- all buttons do something real\n"
                "- image loading is stable with fallbacks\n"
                "- no placeholder or disabled fake UI remains\n"
                "- follow-up bug feedback has been fully addressed\n"
                "Do not output any text outside JSON."
            )

            repair_response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: session.send_message(repair_prompt),
            )

            repair_raw = (getattr(repair_response, "text", None) or "").strip()
            repaired = self._parse_response(repair_raw)
            repaired_validation = self._validate_generated_app(repaired)

            if repaired_validation["ok"]:
                repaired.setdefault("logs", [])
                repaired["logs"].append("Auto-repair pass applied successfully")
                return repaired

            repaired.setdefault("logs", [])
            repaired["logs"].append("Auto-repair pass failed validation")
            repaired["logs"].extend([f"Validation issue: {i}" for i in repaired_validation["issues"]])
            repaired["status"] = "error"
            return repaired

        except Exception as exc:
            logger.exception("Gemini generation error")
            return {
                "message": f"I hit an error talking to Gemini: `{exc}`. Check your API key and try again.",
                "actions": [],
                "logs": [f"Gemini error: {exc}"],
                "status": "error",
            }

    # ─── Parsing helpers ────────────────────────────────────────

    def _extract_first_json_object(self, text: str) -> Optional[str]:
        """
        Extract the first balanced JSON object from text.
        Safely handles braces inside quoted strings.
        """
        start = text.find("{")
        if start == -1:
            return None

        depth = 0
        in_string = False
        escape = False

        for i in range(start, len(text)):
            ch = text[i]

            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
            else:
                if ch == '"':
                    in_string = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        return text[start:i + 1]

        return None

    def _sanitize_json_string(self, text: str) -> str:
        """
        Attempt to fix common Gemini JSON issues:
        - Unescaped double quotes inside content strings (e.g. HTML attributes like lang="en")
        - We do this by finding "content": "..." blocks and re-escaping their inner quotes.
        This is a best-effort fix for the most common failure mode.
        """
        import re
        
        def fix_content_value(m):
            # m.group(1) is the raw string between the outer quotes of "content": "..."
            inner = m.group(1)
            # Replace unescaped double quotes that aren't already escaped
            # Strategy: replace " that is NOT preceded by backslash
            fixed = re.sub(r'(?<!\\)"', "\'", inner)
            return f'"content": "{fixed}"' 

        # Only attempt this if standard parse failed - apply as a pre-pass
        text = re.sub(
            r'"content"\s*:\s*"((?:[^"\\]|\\.)*)"',
            fix_content_value,
            text,
            flags=re.DOTALL
        )
        return text

    def _parse_response(self, raw: str) -> Dict:
        """
        Parse Gemini response into the expected DevMind JSON structure.
        Accepts:
        - pure JSON
        - fenced JSON
        - text containing a JSON object
        - JSON with unescaped quotes in content fields (auto-fixed)
        """
        text = raw.strip()

        if "```json" in text:
            text = text.split("```json", 1)[1].rsplit("```", 1)[0].strip()
        elif "```" in text:
            text = text.split("```", 1)[1].rsplit("```", 1)[0].strip()

        # Pass 1: try direct parse
        try:
            return self._validate(json.loads(text))
        except json.JSONDecodeError:
            pass

        # Pass 2: try extracting first JSON object
        candidate = self._extract_first_json_object(text)
        if candidate:
            try:
                return self._validate(json.loads(candidate))
            except json.JSONDecodeError:
                pass

        # Pass 3: try with json5-style relaxed parse via ast if available
        # (handles trailing commas and some quote issues)
        try:
            import ast
            # Replace JS true/false/null with Python equivalents for eval safety check
            safe = text.replace("true", "True").replace("false", "False").replace("null", "None")
            # Only attempt if it looks like a dict and has no obvious injection
            if safe.strip().startswith("{") and "import" not in safe and "exec" not in safe:
                result = ast.literal_eval(safe)
                if isinstance(result, dict):
                    return self._validate(result)
        except Exception:
            pass

        logger.warning("Gemini response was not valid JSON. Raw prefix: %r", raw[:500])

        # Try one more thing: sometimes the content strings have unescaped quotes.
        # Attempt to extract just the "message" field if present, so we at least show something useful.
        import re as _re
        msg_match = _re.search(r'"message"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,', raw)
        friendly_msg = msg_match.group(1) if msg_match else (
            "I ran into a formatting issue generating the response. "
            "Please try your request again — I'll fix it."
        )

        return {
            "message": friendly_msg,
            "actions": [],
            "logs": [
                "JSON parse error: Gemini returned malformed JSON (likely unescaped quotes in HTML content).",
                "Tip: Try asking again — the model will retry with a repair pass.",
            ],
            "status": "error",
        }

    @staticmethod
    def _validate(data: Dict) -> Dict:
        """
        Ensure required keys exist with sensible defaults.
        """
        return {
            "message": data.get("message", "Done."),
            "actions": data.get("actions", []),
            "logs": data.get("logs", []),
            "status": data.get("status", "complete"),
        }
    def _validate_generated_app(self, result: Dict) -> Dict:
        import re
        issues = []

        actions = result.get("actions", [])
        action_paths = {
            a.get("path", "").strip("/")
            for a in actions
            if a.get("type") in ("create_file", "update_file")
        }

        # Find index.html
        index_action = None
        for action in actions:
            p = action.get("path", "")
            if (p == "index.html" or p.endswith("/index.html")) and action.get("type") in ("create_file", "update_file"):
                index_action = action
                break

        if not index_action:
            issues.append("No index.html file was generated.")
            return {"ok": False, "issues": issues}

        html_content = index_action.get("content", "")

        # ── Check all linked CSS files are in actions ──────────────
        css_hrefs = re.findall(r'<link[^>]+href=["\']([^"\']+\.css)["\'][^>]*>', html_content, re.IGNORECASE)
        for href in css_hrefs:
            href_clean = href.strip("/").split("?")[0]
            if not href_clean.startswith(("http://", "https://", "//")) and href_clean not in action_paths:
                issues.append(
                    f'CSS file "{href}" is linked in index.html but NOT included in actions[]. '
                    f'Add a create_file action for "{href_clean}" with its full CSS content.'
                )

        # ── Check all linked JS files are in actions ───────────────
        js_srcs = re.findall(r'<script[^>]+src=["\']([^"\']+\.js)["\'][^>]*>', html_content, re.IGNORECASE)
        for src in js_srcs:
            src_clean = src.strip("/").split("?")[0]
            if not src_clean.startswith(("http://", "https://", "//")) and src_clean not in action_paths:
                issues.append(
                    f'JS file "{src}" is linked in index.html but NOT included in actions[]. '
                    f'Add a create_file action for "{src_clean}" with its full JavaScript content.'
                )

        # ── Check other HTML pages link shared CSS/JS ──────────────
        html_actions = [
            a for a in actions
            if a.get("path", "").endswith(".html") and a.get("type") in ("create_file", "update_file")
        ]
        for ha in html_actions:
            page_content = ha.get("content", "")
            page_path = ha.get("path", "")
            # Each HTML page must link the same CSS/JS as index.html
            for href in css_hrefs:
                href_clean = href.strip("/").split("?")[0]
                if not href_clean.startswith(("http://", "https://", "//")) and href_clean not in page_content:
                    issues.append(
                        f'Page "{page_path}" is missing <link href="{href}">. '
                        f'Every HTML page must link all shared CSS files.'
                    )

        # ── Content quality checks ─────────────────────────────────
        banned_phrases = [
            "under construction", "coming soon",
            "future feature", "future features", "check back soon",
        ]
        lower = html_content.lower()
        for phrase in banned_phrases:
            if phrase in lower:
                issues.append(f'Banned placeholder text found: "{phrase}"')

        if "new Chart(" in html_content and "getComputedStyle(document.documentElement)" not in html_content:
            issues.append("Chart present but CSS-variable-safe JS theme handling was not found.")

        # ── E-commerce specific checks ─────────────────────────────
        is_ecommerce = any(k in lower for k in ["add to cart", "shopping cart", "product", "checkout"])
        if is_ecommerce:
            # Check for random/irrelevant picsum images (no keyword in URL)
            picsum_random = re.findall(r'https://picsum\.photos/\d+/\d+(?:\?random=\d+)?', html_content)
            if picsum_random:
                issues.append(
                    f"E-commerce app uses {len(picsum_random)} random picsum image(s) with no product relevance. "
                    "Use https://source.unsplash.com/400x300/?{{keyword}}&sig={{n}} with category-specific keywords instead."
                )
            # Check for Loading products text that never resolves
            if "loading products" in lower:
                # Check if JS actually populates products
                for js_action in actions:
                    if js_action.get("path", "").endswith(".js"):
                        js_content = js_action.get("content", "").lower()
                        if "innerhtml" in js_content or "appendchild" in js_content or "render" in js_content:
                            break
                else:
                    issues.append("'Loading products...' text found but no JS file renders products into the DOM.")

        return {"ok": len(issues) == 0, "issues": issues}