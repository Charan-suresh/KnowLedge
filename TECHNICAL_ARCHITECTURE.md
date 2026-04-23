# KnowLedge: Technical Architecture & Implementation
## Comprehensive Technical Presentation

---

## 📋 Table of Contents

1. [System Architecture Overview](#system-architecture-overview)
2. [Technology Stack](#technology-stack)
3. [Core Components](#core-components)
4. [Data Flow](#data-flow)
5. [Frontend Architecture](#frontend-architecture)
6. [Backend Architecture](#backend-architecture)
7. [AI/ML Pipeline](#aiml-pipeline)
8. [Database Schema](#database-schema)
9. [Integration Points](#integration-points)
10. [Deployment & Configuration](#deployment--configuration)

---

## System Architecture Overview

### Mission Statement
KnowLedge is a **Comprehension Debt Tracker (CDT)** that addresses AI-induced over-reliance in education by tracking, measuring, and systematically clearing "comprehension debt"—concepts students passively copy without truly understanding.

### Core Philosophy
Instead of instantly answering questions (traditional AI tutoring), KnowLedge:
- **Detects** borrowed concepts automatically (Scout)
- **Tracks** learning debt across a personal ledger
- **Guides** students through Socratic clearing (Sage)
- **Verifies** true mastery via multimodal assessment (Lens)

### System Layers

```
┌─────────────────────────────────────────────────────────┐
│                    User Interface Layer                  │
│         (HTML/CSS/JavaScript Frontend + Jinja2)          │
├─────────────────────────────────────────────────────────┤
│                  Application Server Layer                │
│         (FastAPI + Uvicorn + Orchestrator)               │
├─────────────────────────────────────────────────────────┤
│                  Integration Layer                       │
│    (Scout | Sage | Lens | RAG | Classroom Sync)         │
├─────────────────────────────────────────────────────────┤
│                  AI Model Layer                          │
│         (Gemma-4 via Ollama - Offline)                   │
├─────────────────────────────────────────────────────────┤
│                  Persistence Layer                       │
│    (SQLite + ChromaDB Vector Store + File Storage)       │
└─────────────────────────────────────────────────────────┘
```

---

## Technology Stack

### Backend Framework
| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Web Framework** | FastAPI 0.100+ | RESTful API, async request handling, auto-documentation |
| **ASGI Server** | Uvicorn | Production-grade async HTTP server |
| **Templating** | Jinja2 | Server-side templating for HTML responses |
| **HTTP Client** | httpx | Async HTTP requests to external services |

### Frontend Technologies
| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Markup** | HTML5 | Semantic structure |
| **Styling** | CSS3 | Custom design system (no frameworks) |
| **Interactivity** | Vanilla JavaScript | Tab switching, modals, real-time updates |
| **Visualization** | Mermaid.js | Interactive flowcharts and diagrams |
| **Fonts** | Google Fonts (DM Sans, DM Mono, Playfair Display) | Professional typography |

### AI/ML Stack
| Component | Technology | Purpose |
|-----------|-----------|---------|
| **LLM Runtime** | Ollama | Local, offline Gemma-4 execution |
| **Models** | Gemma-4-E2B, Gemma-4-E4B | Lightweight and creative reasoning respectively |
| **Function Calling** | Native Ollama Tools | Structured concept extraction and decision-making |
| **Vision Processing** | Gemma-4 Vision | Handwritten solution analysis and feedback |

### Data & Storage
| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Relational DB** | SQLite3 | Debt ledger, clearing history, classroom sessions |
| **Vector Store** | ChromaDB | Syllabus embeddings for RAG context retrieval |
| **Vector Search** | Chroma API | Semantic similarity matching for concept retrieval |
| **File Storage** | Local File System | Images, submissions, documents |

### Data Processing
| Component | Technology | Purpose |
|-----------|-----------|---------|
| **PDF Processing** | pdfplumber | Convert syllabus PDFs to vectorizable text |
| **Image Processing** | Pillow (PIL) | Read, resize, encode images for vision models |
| **Data Analysis** | pandas | Aggregate statistics for reports and progress charts |
| **Multipart Handling** | python-multipart | Parse file uploads and form data |

---

## Core Components

### 1. **Scout** (`scout.py`)
**Role:** Background behavioral intelligence agent

**Functionality:**
- Monitors student text input (notes, code, explanations)
- Uses Gemma-4-E2B with native function calling
- Extracts key concepts and assigns confidence scores (0.0-1.0)
- Logs "On Loan" concepts to SQLite ledger

**Key Methods:**
```python
tag_content(text: str) -> List[ConceptTag]
```

**Workflow:**
```
Student Input
    ↓
Gemma-4-E2B (Function Calling)
    ↓
Extract: [concept_tag, confidence_score]
    ↓
Insert to debt_log table (status='on_loan')
    ↓
Event Bus: DEBT_ADDED event
```

**Model Specification:** `gemma:4-e2b`
- Lightweight, hyper-fast
- Function calling for structured output
- Runs continuously in background thread

---

### 2. **Sage** (`sage.py` + `sage_stream.py`)
**Role:** Socratic clearing agent (interactive dialogue)

**Functionality:**
- Engages students in guided conversation
- Uses Gemma-4-E4B with function calling
- Evaluates mastery through dialogue quality
- Clears concepts only on demonstrated understanding

**Key Methods:**
```python
run_session(concept: str, debt_log: List[Dict], chat_history: List[Dict]) -> ClearingResult
run_sage_streaming(concept: str, chat_history: List[Dict]) -> Iterator[str]
```

**Function Tools Available:**
1. `verify_comprehension(reasoning: str)` - Call when student demonstrates mastery
2. Implicit: Question generation, gap identification

**Clearing Logic:**
- Student explains concept in own words
- Sage asks probing questions (Socratic method)
- If reasoning incomplete → guide further
- If reasoning complete → call `verify_comprehension` tool
- Status changes to "clear" in database

**Model Specification:** `gemma:4-e4b`
- Larger, creative reasoning capability
- Better dialogue coherence
- Can synthesize multimodal feedback

---

### 3. **Lens** (`lens.py`)
**Role:** Multimodal verification agent (vision + audio analysis)

**Functionality:**
- Analyzes handwritten solutions via vision
- Identifies logical gaps and misconceptions
- Returns pixel coordinates of errors with explanations
- Flags concepts as "persists" if gaps found

**Key Methods:**
```python
verify_image(image_bytes: bytes, concept: str) -> ExaminerResult
```

**ExaminerResult Structure:**
```python
@dataclass
class ExaminerResult:
    x: int                      # Pixel column of error
    y: int                      # Pixel row of error
    width: int                  # Bounding box width
    height: int                 # Bounding box height
    explanation: str            # Why the logic fails
    audio_bytes: Optional[bytes] = None  # Future: spoken feedback
```

**Vision Prompt Strategy:**
- Detects reasoning errors visually
- Maps to pixel coordinates for visual feedback
- Evaluates concept-specific correctness criteria

**Model Specification:** `gemma:4-e4b` (vision-enabled)
- Multimodal input (image + text)
- Spatial reasoning for bounding boxes
- Detailed error explanation generation

---

### 4. **Orchestrator** (`orchestrator.py`)
**Role:** Asynchronous workflow coordinator

**Functionality:**
- Manages three independent model agents (Scout, Sage, Lens)
- Enforces resource constraints (LOW_RAM mode)
- Coordinates concurrent operations safely
- Emits event bus messages for UI updates

**Threading Model:**
```python
class Orchestrator:
    input_queue: Queue()      # Scout input buffer
    event_bus: Queue()        # Broadcast to WebSocket listeners
    resource_lock: Lock()     # Prevent Sage + Lens simultaneous execution
    _scout_thread: Thread()   # Background daemon
    _stop_event: Event()      # Graceful shutdown signal
```

**Key Methods:**
```python
start_scout_loop()              # Launch background Scout thread
trigger_clearing(concept, history) -> ClearingResult  # Synchronous Sage call
trigger_verification(image, concept) -> ExaminerResult # Synchronous Lens call
```

**Resource Management:**
- **LOW_RAM mode** (`config.LOW_RAM = true`):
  - Mutual exclusion lock between Sage and Lens
  - Prevents simultaneous heavy model execution
  - Recommended for 8GB RAM systems
- **High-RAM mode** (`config.LOW_RAM = false`):
  - Concurrent Sage + Lens execution allowed
  - Recommended for 16GB+ systems

---

### 5. **RAG (Retrieval-Augmented Generation)** (`rag.py` + `retrieval.py`)
**Role:** Context injection for accurate Socratic guidance

**Functionality:**
- Retrieves relevant syllabus content for concepts
- Grounds Sage dialogue in course materials
- Prevents hallucinations via vector similarity search

**Architecture:**
```
Syllabus PDF
    ↓
pdfplumber (extract text)
    ↓
Text chunking (sliding window)
    ↓
ChromaDB (vectorize + store embeddings)
    ↓
Query time: retrieve top-K semantically similar chunks
    ↓
Inject into Sage system prompt
```

**Key Methods:**
```python
retrieve_context(concept: str, top_k: int = 3) -> List[str]
```

**ChromaDB Configuration:**
- Collection: "syllabus-embeddings"
- Path: `./cdt_vectorstore`
- Auto-instantiated on first query

---

### 6. **Database Layer** (`db.py`)
**Role:** Persistent storage for learning history

**Schema:**

#### `debt_log` Table
```sql
CREATE TABLE debt_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    concept TEXT NOT NULL,
    source_text TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confidence REAL,              -- 0.0 to 1.0 (Scout confidence)
    status TEXT DEFAULT 'on_loan' -- 'on_loan' | 'clear' | 'persists'
)
```

#### `clearing_history` Table
```sql
CREATE TABLE clearing_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    concept TEXT NOT NULL,
    session_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    result TEXT,                  -- 'cleared' | 'not_cleared'
    notes TEXT                    -- Sage explanation or error details
)
```

#### `classroom_sessions` Table
```sql
CREATE TABLE classroom_sessions (
    session_id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    assignment_id TEXT NOT NULL,
    course_id TEXT NOT NULL,
    attachment_id TEXT,
    submission_id TEXT,
    status TEXT DEFAULT 'pending'
)
```

**Key Operations:**
```python
insert_debt(concept: str, source_text: str, confidence: float)
get_debt_by_concept(concept: str) -> List[Dict]
update_debt_status(concept: str, status: str)
get_clearing_history(concept: str) -> List[Dict]
```

---

## Data Flow

### 1. **Concept Tracking Flow (Scout)**

```
┌────────────────────────────────────────────────────┐
│  Student pastes notes/code into ledger input area  │
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│   POST /api/tag → Scout.tag_content(text)          │
│   Ollama: gemma:4-e2b (native function calling)    │
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│  Function Result: [{concept_tag, confidence}]      │
│  Example: [                                        │
│    {concept_tag: "Binary Search", confidence: 0.9},│
│    {concept_tag: "Time Complexity", confidence: 0.7}│
│  ]                                                 │
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│  db.insert_debt() for each concept                 │
│  Status: 'on_loan' (student hasn't cleared it yet)│
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│  Event Bus: emit DEBT_ADDED events                 │
│  Dashboard refreshes via JS polling                │
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│  User sees new concepts in My Ledger table         │
│  Status badge: "On Loan"                          │
└────────────────────────────────────────────────────┘
```

### 2. **Clearing Flow (Sage)**

```
┌────────────────────────────────────────────────────┐
│    User clicks concept → opens Sage modal          │
│    Example: "Binary Search"                       │
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│  POST /api/sage (concept, chat_history=[])        │
│  Backend calls:                                   │
│  1. RAG.retrieve_context("Binary Search") → text  │
│  2. Sage.run_session(concept, history, context)   │
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│  Ollama: gemma:4-e4b                              │
│  System Prompt gels RAG context + Socratic method │
│  User message: [student's explanation]            │
│                                                    │
│  Tools available:                                 │
│  - verify_comprehension(reasoning: str)          │
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│  Response Strategy (LLM chooses):                 │
│                                                    │
│  IF student answer correct & complete:           │
│    → Call verify_comprehension tool               │
│    → ClearingResult = {cleared: true, response}  │
│                                                    │
│  IF student answer incomplete:                   │
│    → Ask probing question                        │
│    → Return response (student can re-answer)     │
│                                                    │
│  IF student answer wrong:                        │
│    → Point out logical inconsistency             │
│    → Guide toward correct reasoning              │
│    → Return response                             │
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│  IF cleared:                                      │
│    db.update_debt_status("Binary Search", "clear")|
│    db.insert_clearing_history(concept, "cleared") │
│  ELSE:                                            │
│    Maintain status 'on_loan' (can try again)     │
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│  Response streamed back to modal                  │
│  Dashboard updates status badge                  │
└────────────────────────────────────────────────────┘
```

### 3. **Verification Flow (Lens)**

```
┌────────────────────────────────────────────────────┐
│  User uploads handwritten solution image          │
│  POST /api/lens (image, concept)                  │
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│  Backend: Image validation                        │
│  - Check file type (PNG, JPG, WEBP)              │
│  - Load with PIL to verify integrity             │
│  - Encode to base64 for vision model             │
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│  Ollama: gemma:4-e4b (vision-enabled)            │
│  Vision Prompt:                                  │
│  "Analyze handwritten work for concept: [Binary  │
│   Search]. Identify exact step where logic fails.│
│   Return JSON with (x, y, width, height,         │
│   explanation) for error location."              │
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│  Model Output (JSON):                            │
│  {                                                │
│    "x": 150,                                     │
│    "y": 200,                                     │
│    "width": 300,                                 │
│    "height": 80,                                 │
│    "explanation": "Off-by-one error in binary    │
│     search termination condition."               │
│  }                                               │
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│  ExaminerResult parsed & processed                │
│  If gaps found:                                  │
│    → db.update_debt_status(concept, "persists")  │
│    → Store ExaminerResult in clearing_history    │
│  Else:                                           │
│    → Concept stays "clear" (confirmed)           │
└────────────────────────────────────────────────────┘
                        ↓
┌────────────────────────────────────────────────────┐
│  Frontend: Render feedback overlay                │
│  - Display original image                        │
│  - Draw red bounding box at (x, y, width, height)│
│  - Show explanation tooltip                      │
│  - Option to revisit with Sage                   │
└────────────────────────────────────────────────────┘
```

---

## Frontend Architecture

### Technology Choices (No Frameworks)
- **Vanilla HTML/CSS/JavaScript** for simplicity and offline capability
- **No build step** required
- **Responsive design** with CSS Grid and Flexbox
- **Progressive enhancement** (works without JavaScript)

### Design System

**Color Palette:**
```css
:root {
    --cream: #F5F0E8;          /* Background */
    --ink: #1C1A14;             /* Text */
    --amber: #D4820A;           /* Primary action */
    --teal: #0E7A6E;            /* Success states */
    --coral: #C94A3A;           /* Warning/error */
}
```

**Typography:**
- **Headlines:** Playfair Display (serif, bold)
- **Body:** DM Sans (sans-serif, readable)
- **Monospace:** DM Mono (code examples, metadata)

### Page Structure

**Base Template** (`base.html`):
```
┌─────────────────────────────────────────┐
│  Sidebar (240px, fixed)                 │
│  - Logo                                 │
│  - Navigation items                     │
│  - Scout status indicator               │
└─────────────────────────────────────────┐
┌─────────────────────────────────────────┐
│  Main Content Area                      │
│  ├─ Topbar (sticky)                     │
│  │  ├─ Page title                       │
│  │  └─ Context subtitle                 │
│  │                                       │
│  └─ Content Block                       │
│     └─ {% block content %}              │
└─────────────────────────────────────────┐
┌─────────────────────────────────────────┐
│  Floating Help Button (? in circle)    │
│  → Link to /help                        │
└─────────────────────────────────────────┐
┌─────────────────────────────────────────┐
│  Sage Modal (hidden by default)         │
│  - Avatar (🦉)                          │
│  - Message bubble area                  │
│  - Input field + send button            │
└─────────────────────────────────────────┐
```

### Key Pages

#### 1. **My Ledger** (`ledger.html`)
**Purpose:** Dashboard showing all tracked concepts

**Components:**
- Input area: paste notes + "Tag concepts" button
- Ledger table:
  - Concept name
  - Confidence score (Scout's rating)
  - Status badge (On Loan | Clear | Persists)
  - Action buttons: Open Sage, Upload to Lens, Details
- Statistics cards (total, cleared, pending)
- Refresh button (force Scout re-evaluation)

**Interactivity:**
```javascript
// Click concept row
→ openSageModal(concept)
→ POST /api/sage with empty chat_history
→ Stream response into modal
→ Allow user reply

// Click Lens button
→ openLensModal(concept)
→ File input for image
→ POST /api/lens
→ Render feedback overlay
```

#### 2. **Help Page** (`help.html`)
**Purpose:** Comprehensive onboarding and feature documentation

**Sections:**
1. **Hero Overview** - App mission + 3 key features
2. **Tabbed Interface:**
   - Step-by-Step Guide (5 expandable steps)
   - Workflow Flowchart (Mermaid.js interactive diagram)
   - FAQ with keyword search
3. **Tips for Success** - 4 actionable tips

**Flowchart Visualization:**
```
Student Input
    ↓
Scout Detection
    ↓
[Decision: Clear with Sage?]
    ├─ Yes → Sage Session → Mastery? → Clear or Persists
    └─ No → View Progress
```

**Implementation:** Mermaid.js (responsive, interactive)

#### 3. **Progress Page** (`progress.html`)
**Purpose:** Learning analytics and trend visualization

**Metrics:**
- Weekly concept movement (stacked bar chart)
- Clear rate over time (line chart)
- Outstanding debt (donut chart)
- Clearing velocity (concepts/week)

**Data Source:**
```python
# queries/progress_stats.sql
SELECT DATE(timestamp) as date,
       COUNT(*) as total_concepts,
       SUM(CASE WHEN status = 'clear' THEN 1 ELSE 0 END) as cleared
FROM debt_log
GROUP BY DATE(timestamp)
```

#### 4. **Reports Page** (`teacher_view.html` / `reports.html`)
**Purpose:** Instructor-facing analytics

**Audience:** Teachers monitoring class learning patterns

**Visualizations:**
- Class-wide clearing rates
- Concept difficulty heatmap
- Student cohort comparisons
- Intervention recommendations

---

## Backend Architecture

### FastAPI Application Structure

**Main Application** (`main.py`):
```python
app = FastAPI(title="KnowLedge Backend")

# Mount static files
app.mount("/static", StaticFiles(...), name="static")

# Mount Jinja2 templates
templates = Jinja2Templates(directory="knowledge/templates")

# Include routers
app.include_router(progress.router)
app.include_router(reports.router)
app.include_router(ingest_router)
app.include_router(classroom_router)

# Initialize services
db.init_db()
orchestrator.start_scout_loop()
```

### API Routes Design

#### Page Routes (Server-Side Rendered)
```python
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(request, "ledger.html", {})

@app.get("/ledger", response_class=HTMLResponse)
async def read_ledger(request: Request):
    # Fetch debts from DB and render with context
    debts = db.get_all_debts()
    return templates.TemplateResponse(request, "ledger.html", {"debts": debts})

@app.get("/help", response_class=HTMLResponse)
async def read_help(request: Request):
    return templates.TemplateResponse(request, "help.html", {})

@app.get("/progress", response_class=HTMLResponse)
async def read_progress(request: Request):
    stats = db.get_progress_stats()
    return templates.TemplateResponse(request, "progress.html", {"stats": stats})
```

#### API Routes (JSON Response)
```python
@app.post("/api/scout/tag")
async def tag_concepts(request: ScoutRequest):
    """Trigger Scout concept extraction"""
    concepts = tag_content(request.text)
    for concept in concepts:
        db.insert_debt(concept.concept_tag, request.text, concept.confidence_score)
    return {"concepts": concepts}

@app.post("/api/sage/chat")
async def sage_session(request: SageRequest):
    """Run Sage clearing session"""
    result = orchestrator.trigger_clearing(request.concept, request.chat_history)
    return {"cleared": result.cleared, "response": result.response}

@app.post("/api/lens/verify")
async def lens_verify(image: UploadFile, concept: str):
    """Run Lens vision verification"""
    image_bytes = await image.read()
    result = verify_image(image_bytes, concept)
    if result:
        db.update_debt_status(concept, "persists")
    return {"x": result.x, "y": result.y, "width": result.width, "height": result.height, "explanation": result.explanation}
```

### Error Handling

**Strategy:**
- Try/except blocks with typed exceptions
- HTTP error codes (400 Bad Request, 500 Server Error)
- User-friendly error messages

**Example:**
```python
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Check logs."}
    )
```

### Streaming Responses

**For Sage (Long-Running Dialogue):**
```python
@app.post("/api/sage/stream")
async def sage_stream(request: SageRequest):
    """Stream Sage response for real-time UI update"""
    
    async def response_generator():
        for chunk in run_sage_streaming(request.concept, request.chat_history):
            yield f"data: {chunk}\n\n"
    
    return StreamingResponse(response_generator(), media_type="text/event-stream")
```

**Frontend Handler:**
```javascript
const eventSource = new EventSource("/api/sage/stream");
eventSource.onmessage = (e) => {
    const text = e.data;
    document.getElementById("sageResponse").textContent += text;
};
```

---

## AI/ML Pipeline

### Model Selection Rationale

**Gemma-4-E2B (Scout):**
- Lightweight (2B parameters)
- Fast execution (ideal for background thread)
- Native function calling for structured extraction
- Low latency for real-time tagging

**Gemma-4-E4B (Sage + Lens):**
- Medium-sized (4B parameters)
- Better reasoning for Socratic dialogue
- Multimodal (text + vision)
- Can handle context-rich intricate reasoning

### Function Calling Implementation

**Scout's Function Calling:**
```json
{
  "type": "function",
  "function": {
    "name": "log_comprehension_concepts",
    "description": "Identifies academic concepts in text",
    "parameters": {
      "type": "object",
      "properties": {
        "concepts": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "concept_tag": {"type": "string"},
              "confidence_score": {"type": "number"}
            }
          }
        }
      }
    }
  }
}
```

**Sage's Function Calling:**
```json
{
  "type": "function",
  "function": {
    "name": "verify_comprehension",
    "description": "Call when student demonstrates mastery",
    "parameters": {
      "type": "object",
      "properties": {
        "reasoning": {
          "type": "string",
          "description": "Why student has cleared the concept"
        }
      },
      "required": ["reasoning"]
    }
  }
}
```

### Prompt Engineering Strategies

**Scout System Prompt:**
```
Analyze the student input and extract key academic concepts.
Focus on:
1. Language constructs (e.g., "for loop", "recursion")
2. Algorithmic concepts (e.g., "binary search", "dynamic programming")
3. Mathematical concepts (e.g., "big-O notation", "derivatives")
4. Domain-specific knowledge (varies by subject)

Assign confidence scores reflecting how explicitly the concept appears.
Return only valid JSON.
```

**Sage System Prompt:**
```
You are the Debt Collector. Your goal is to clear comprehension debt.
Use socratic method:
1. Ask questions that lead students to discover answers
2. Point out logical inconsistencies
3. Guide toward independent understanding
4. NEVER give the answer directly

Context from textbook:
{RAG_CONTEXT}

If student demonstrates mastery, call verify_comprehension tool.
```

### RAG Context Injection

**Pipeline:**
```
Syllabus PDF
    ↓
pdfplumber.extract_text()
    ↓
Split into 500-char chunks with 100-char overlap
    ↓
ChromaDB: embed and upsert to "syllabus-embeddings" collection
    ↓
Query: embedding("Binary Search") → retrieve top-3 similar chunks
    ↓
Inject into Sage system prompt
```

**Retrieval Query:**
```python
results = chroma_client.collection("syllabus-embeddings").query(
    query_embeddings=[embedding_model.embed("Binary Search")],
    n_results=3
)
context_str = "\n".join([doc for doc in results["documents"][0]])
```

---

## Database Schema

### Primary Tables

**debt_log (Concept Tracking)**
```sql
CREATE TABLE debt_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    concept TEXT NOT NULL,              -- e.g., "Binary Search"
    source_text TEXT,                   -- Original student text
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confidence REAL,                    -- 0.0-1.0 (Scout confidence)
    status TEXT DEFAULT 'on_loan'       -- 'on_loan'|'clear'|'persists'
);

CREATE INDEX idx_concept ON debt_log(concept);
CREATE INDEX idx_status ON debt_log(status);
CREATE INDEX idx_timestamp ON debt_log(timestamp);
```

**clearing_history (Session Logs)**
```sql
CREATE TABLE clearing_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    concept TEXT NOT NULL,
    session_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    result TEXT,                        -- 'cleared'|'not_cleared'
    notes TEXT                          -- Sage feedback or Lens explanation
);

CREATE INDEX idx_concept_history ON clearing_history(concept);
```

**classroom_sessions (LMS Integration)**
```sql
CREATE TABLE classroom_sessions (
    session_id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    assignment_id TEXT NOT NULL,
    course_id TEXT NOT NULL,
    attachment_id TEXT,
    submission_id TEXT,
    status TEXT DEFAULT 'pending'
);
```

### Query Patterns

**Get all On Loan concepts:**
```sql
SELECT concept, confidence, timestamp
FROM debt_log
WHERE status = 'on_loan'
ORDER BY timestamp DESC;
```

**Get clearing history for a concept:**
```sql
SELECT session_ts, result, notes
FROM clearing_history
WHERE concept = ?
ORDER BY session_ts DESC;
```

**Weekly progress statistics:**
```sql
SELECT DATE(timestamp) as date,
       SUM(CASE WHEN status = 'clear' THEN 1 ELSE 0 END) as cleared,
       COUNT(*) as total
FROM debt_log
GROUP BY DATE(timestamp)
ORDER BY date;
```

---

## Integration Points

### 1. **Google Classroom Integration** (`classroom_client.py`)

**OAuth Flow:**
```
1. Student clicks "Sync with Classroom"
2. Redirect to Google OAuth consent
3. Exchange auth code for access token
4. API: List student's assignments
5. Store session_id + student_id mapping
6. Monitor for new submissions
7. Auto-pull handwritten work into Lens
```

**Configuration Variables:**
```python
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
APP_BASE_URL = os.getenv("APP_BASE_URL")  # e.g., https://abc123.ngrok.io
```

### 2. **Ollama Service Integration**

**Service Discovery:**
```python
SCOUT_MODEL = os.getenv("SCOUT_MODEL", "gemma4:e2b")
SAGE_MODEL = os.getenv("SAGE_MODEL", "gemma4:e4b")
LENS_MODEL = os.getenv("LENS_MODEL", "gemma4:e4b")

client = ollama.Client(host="http://localhost:11434")
response = client.chat(model=SCOUT_MODEL, messages=[...])
```

**Fallback Strategy:**
- If Ollama unavailable → HTTPException 503
- Retry logic with exponential backoff
- Graceful degradation (queue requests, serve cached responses)

### 3. **ChromaDB Vector Store**

**Initialization:**
```python
import chromadb

chroma_client = chromadb.Client(
    chromadb.config.Settings(
        chroma_db_impl="duckdb+parquet",
        persist_directory="./cdt_vectorstore"
    )
)
collection = chroma_client.get_or_create_collection("syllabus-embeddings")
```

**Upsert Syllabus:**
```python
# vectorize.py
documents = extract_from_pdf("syllabus.pdf")
embeddings = [model.embed(doc) for doc in documents]
collection.upsert(
    embeddings=embeddings,
    documents=documents,
    ids=[f"chunk_{i}" for i in range(len(documents))]
)
```

---

## Deployment & Configuration

### Local Development Setup

**Prerequisites:**
```bash
# 1. Install Python 3.10+
python3 --version

# 2. Clone repository
git clone https://github.com/Charan-suresh/Gemma4-CDT.git
cd Gemma4-CDT

# 3. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Start Ollama daemon (in separate terminal)
ollama serve

# 6. Pull Gemma models
ollama pull gemma:4-e2b
ollama pull gemma:4-e4b

# 7. (Optional) Vectorize syllabus
python3 knowledge/vectorize.py path/to/syllabus.pdf
```

**Run Application:**
```bash
# Terminal 1: Ollama daemon
ollama serve

# Terminal 2: Development server
python3 -m uvicorn knowledge.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 3: (Optional) Streamlit companion dashboard
streamlit run app.py
```

### Environment Variables

**Core Configuration:**
```bash
# Models
SCOUT_MODEL=gemma4:e2b
SAGE_MODEL=gemma4:e4b
LENS_MODEL=gemma4:e4b

# Database
DB_PATH=./debt_log.db

# Vector Store
CHROMA_PATH=./cdt_vectorstore

# Hardware
LOW_RAM=true  # Set false for 16GB+ systems

# Google Classroom (optional)
GOOGLE_CLIENT_ID=YOUR_CLIENT_ID
GOOGLE_CLIENT_SECRET=YOUR_CLIENT_SECRET
APP_BASE_URL=https://your-domain.com

# Features
AUTO_SUBMIT_HOURS=24
```

### Production Deployment

**Recommended Stack:**
- **ASGI Server:** Gunicorn with Uvicorn workers
- **Reverse Proxy:** Nginx
- **TLS:** Let's Encrypt (acme.sh)
- **Database:** SQLite (for <100 users) or PostgreSQL (for scale)
- **Vector Store:** ChromaDB persistent directory

**Docker Deployment:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY knowledge/ ./knowledge/
COPY knowledge/static/ ./knowledge/static/
COPY knowledge/templates/ ./knowledge/templates/

# Pull models on container start
RUN ollama pull gemma4:e2b && ollama pull gemma4:e4b

EXPOSE 8000

CMD ["uvicorn", "knowledge.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Systemd Service (Linux):**
```ini
[Unit]
Description=KnowLedge Learning Platform
After=network.target ollama.service

[Service]
Type=notify
User=www-data
WorkingDirectory=/opt/knowldege
ExecStart=/opt/knowldege/venv/bin/uvicorn knowledge.main:app --port 8000
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

### Performance Optimization

**Strategy 1: Off-load Scout to Background**
```python
# Non-blocking Scout execution
orchestrator.input_queue.put(student_text)  # Immediate return
# Scout processes asynchronously in daemon thread
```

**Strategy 2: Cache Clearing Contexts**
```python
@lru_cache(maxsize=128)
def get_rag_context(concept: str) -> str:
    return retrieve_context(concept)
```

**Strategy 3: Database Connection Pooling** (if migrating to PostgreSQL)
```python
from sqlalchemy.pool import QueuePool
engine = create_engine(
    "postgresql://...",
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=40
)
```

**Strategy 4: Compress Images Before Vision Processing**
```python
from PIL import Image
img = Image.open(BytesIO(image_bytes))
img.thumbnail((1024, 1024))  # Resize if large
# Reduces token consumption for vision model
```

---

## Monitoring & Observability

### Logging Configuration

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('knowldege.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
logger.info(f"Scout tagged concepts: {concepts}")
logger.error(f"Sage session failed: {exc}")
```

### Key Metrics

1. **Scout Metrics:**
   - Concepts detected per minute
   - Average confidence score
   - False positive rate (concepts tagged but student doesn't use)

2. **Sage Metrics:**
   - Clearing rate (% of attempts that result in cleared status)
   - Average dialogue turns to clear
   - Student satisfaction (if survey added)

3. **Lens Metrics:**
   - Gap detection accuracy (if ground truth available)
   - Processing time per image
   - User validation rate

4. **System Metrics:**
   - Request latency (p50, p99)
   - Ollama API response time
   - Database query time
   - Memory usage (Scout thread, model weights, embeddings)

### Health Checks

```python
@app.get("/health")
async def health_check():
    """Liveness probe for container orchestration"""
    try:
        # Check database
        db.get_connection()
        
        # Check Ollama
        client = ollama.Client()
        client.chat(model=config.SCOUT_MODEL, messages=[{"role": "user", "content": "ping"}])
        
        # Check ChromaDB
        chroma_client.heartbeat()
        
        return {"status": "healthy"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}, 503
```

---

## Testing Strategy

### Unit Tests (Scout, Sage, Lens)
```python
# test_scout.py
def test_tag_content():
    text = "I implemented a binary search in Python"
    concepts = tag_content(text)
    assert len(concepts) > 0
    assert any(c.concept_tag == "binary search" for c in concepts)

# test_sage.py
def test_clearing_with_correct_answer():
    concept = "Binary Search"
    chat_history = [
        {"role": "user", "content": "It's an algorithm that divides the search space in half..."}
    ]
    result = run_session(concept, [], chat_history)
    assert result.cleared == True

# test_lens.py
def test_vision_feedback():
    image_path = "tests/fixtures/handwritten_solution.jpg"
    with open(image_path, 'rb') as f:
        image_bytes = f.read()
    
    result = verify_image(image_bytes, "Binary Search")
    assert result.x > 0 and result.y > 0
    assert len(result.explanation) > 0
```

### Integration Tests
```python
# test_integration.py
def test_full_workflow():
    # 1. Scout detects concept
    text = "I used quicksort to solve this..."
    concepts = tag_content(text)
    assert len(concepts) > 0
    
    # 2. Insert to database
    db.insert_debt(concepts[0].concept_tag, text, concepts[0].confidence_score)
    
    # 3. Sage clears
    chat_history = [{"role": "user", "content": "Quicksort is a divide-and-conquer..."}]
    result = orchestrator.trigger_clearing(concepts[0].concept_tag, chat_history)
    assert result.cleared in [True, False]
```

---

## Future Roadmap

### Phase 1 (Current)
✅ Scout (concept detection)
✅ Sage (Socratic dialogue)
✅ Lens (vision verification)
✅ SQLite persistence
✅ Help Center with Mermaid flowcharts

### Phase 2 (Planned)
- [ ] Google Classroom sync
- [ ] Audio feedback from Lens (speech synthesis)
- [ ] Multi-language support
- [ ] Spaced repetition scheduling
- [ ] Peer learning groups (collaborative clearing)

### Phase 3 (Envisioned)
- [ ] Advanced NLP intent detection
- [ ] Psychometric scoring (true learning debt FICO score)
- [ ] LMS integrations (Canvas, Blackboard)
- [ ] Adaptive difficulty adjustment

---

## Conclusion

**KnowLedge** is a tightly integrated system combining:
- **AI-powered detection** (Scout)
- **Interactive guidance** (Sage)
- **Multimodal verification** (Lens)
- **Persistent learning records** (SQLite + ChromaDB)
- **Intuitive interface** (Vanilla HTML/CSS/JS)

All components work **locally and offline**, respecting student privacy while providing rigorous, data-driven learning accountability.

---

**Document Version:** 1.0  
**Last Updated:** April 2026  
**Author:** Technical Team, KnowLedge Project
