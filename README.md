# 🤖 C.G.P.A. (ChitraGupt Personal Assistant)

**An Intelligent, Agentic Campus Assistant for the Faculty of Technology, University of Delhi.**

**C.G.P.A.** is a Hybrid RAG (Retrieval-Augmented Generation) AI application designed to bridge the gap between static campus data (syllabi, timetables, maps) and dynamic administrative actions (attendance marking, student analytics). It empowers students with instant information and gives teachers "Agentic" tools to manage classes via natural language.

-----

## 🚀 Key Features

### 🎓 For Students

  * **Dynamic Syllabus Engine:** Automatically filters and fetches syllabus summaries based on Year (1st, 2nd, 3rd) and Branch (CSE, ECE, EE).
  * **Campus Navigator:** Integrated Leaflet.js map with visual guides to key locations (Kanad Bhawan, Library, Canteen).
  * **Voice Interaction:** Full Speech-to-Text and Text-to-Speech support for hands-free queries.
  * **Contextual Chat:** Remembers conversation history for fluid interaction.

### 👨‍🏫 For Teachers (Agentic AI)

  * **Natural Language Attendance:** Mark attendance by speaking naturally.
      * *"Mark Roll No. 101 and 102 as Present."*
      * *"Mark everyone present whose name starts with 'A'."* (Pattern Matching)
  * **Data Analytics:** Query student performance instantly.
      * *"Show me students with attendance below 75%."*
  * **Smart Roster Upload:** Bulk import student data via CSV/Excel.
  * **Privacy:** Role-based access ensures students cannot access teacher tools.

-----

## 🏗️ Technical Architecture

This project uses a **Hybrid RAG** approach with a "Brain, Muscle, Memory" architecture:

1.  **The Brain (AI & Logic):**

      * **Google Gemini 2.0 Flash:** Runs with `Temperature 0.0` for strict adherence to facts.
      * **TF-IDF Vector Search (Scikit-Learn):** Handles general queries (Syllabus, Faculty) efficiently without heavy vector databases.
      * **Hard Logic Injection:** For Room/Vacancy queries, the system bypasses vector search and injects raw timetable data for precise calculation.

2.  **The Muscle (Backend - Flask):**

      * **Action Interceptors:** The Python backend intercepts JSON commands from the AI to execute database writes (The AI never touches the DB directly).
      * **Data Processing:** `process_data.py` converts PDFs and Images into a semantic knowledge base.

3.  **The Memory (Database - Supabase):**

      * **PostgreSQL** schema for `students`, `classes`, and `attendance_records`.

4.  **The Face (Frontend):**

      * **Vanilla JavaScript & CSS:** No heavy frameworks. Features Glassmorphism UI and optimized for mobile/desktop.

-----

## 📂 Project Structure

```text
├── backend
│   ├── app.py                 # Main Flask API & Action Handlers
│   ├── process_data.py        # ETL Script: PDF/Image -> Knowledge Base
│   ├── knowledge_base.json    # Processed text chunks (The "Book")
│   ├── vectorizer.pkl         # TF-IDF Model (The "Index")
│   └── tfidf_matrix.pkl       # Matrix Model (The "Map")
├── data
│   ├── knowledge_source       # Raw PDFs, Timetables, Images
│   └── structured_data        # Campus images for the Map
├── frontend
│   ├── index.html             # Main Entry Point
│   ├── script.js              # Frontend Logic (Auth, Voice, API)
│   └── style.css              # Cyberpunk/Glassmorphism Styles
└── requirements.txt           # Python Dependencies
```

-----

## 🛠️ Installation & Setup

### 1\. Clone the Repository

```bash
git clone https://github.com/Mr-BlackAngek/CGPA-Chatbot.git
cd CGPA-Chatbot
```

### 2\. Backend Setup

Create a virtual environment and install dependencies:

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_google_ai_key
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_service_role_key
```

### 3\. Train the Brain

Before running the app, you must process the data files in `/data/knowledge_source`:

```bash
python process_data.py
```

*This generates `knowledge_base.json`, `vectorizer.pkl`, and `tfidf_matrix.pkl`.*

### 4\. Run the Application

```bash
python app.py
```

The server will start at `http://127.0.0.1:5001`.

-----

## 🚀 Deployment

  * **Frontend:** Hosted on **Vercel** (Static site serving `index.html`).
  * **Backend:** Hosted on **Railway** (Python Flask Service).
  * **Database:** Hosted on **Supabase**.

**Note for Production:** Ensure `process_data.py` is run locally and the generated `.pkl` and `.json` files are pushed to the repository so the production server has the latest "Brain".

-----

## 🛡️ Action Protocols (How it works)

When a teacher speaks, the AI outputs a **JSON Command** instead of text. The Backend intercepts this:

**User:** "Mark attendance for roll numbers ending in 77."

**AI Output (Hidden):**

```json
{
  "action": "update_attendance",
  "pattern": { "type": "endswith", "value": "77" },
  "status": "Present"
}
```

**Backend Action:**

1.  Scans class roster.
2.  Finds matching IDs.
3.  Writes to Supabase.
4.  Returns: "✅ Marked Present for 3 students..."

-----

## 📜 License

This project is developed for the Faculty of Technology, University of Delhi.

-----
