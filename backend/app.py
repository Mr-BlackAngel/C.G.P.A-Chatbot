import os
import json
import traceback
import pickle
import pandas as pd
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import google.generativeai as genai
from dotenv import load_dotenv
from supabase import create_client, Client
from sklearn.metrics.pairwise import cosine_similarity

# --- 1. SETUP ---
current_file_path = os.path.abspath(__file__)
backend_dir = os.path.dirname(current_file_path)
project_root = os.path.dirname(backend_dir)
frontend_dir = os.path.join(project_root, 'frontend')
kb_path = os.path.join(backend_dir, 'knowledge_base.json')
dotenv_path = os.path.join(project_root, '.env')

# Paths for the "Trained Brain"
vectorizer_path = os.path.join(backend_dir, 'vectorizer.pkl')
matrix_path = os.path.join(backend_dir, 'tfidf_matrix.pkl')

load_dotenv(dotenv_path)

app = Flask(__name__, template_folder=frontend_dir, static_folder=frontend_dir, static_url_path='')
CORS(app)

# Initialize Gemini (STRICT MODE - Temperature 0.0)
api_key = os.getenv('GEMINI_API_KEY')
if api_key:
    genai.configure(api_key=api_key)
    generation_config = genai.types.GenerationConfig(
        temperature=0.0,  # CRITICAL: No creativity, just facts.
        top_p=0.95,
        top_k=40,
        max_output_tokens=4096,
    )
    model = genai.GenerativeModel(
        model_name='gemini-2.0-flash',
        generation_config=generation_config
    )
else:
    print("⚠️ WARNING: GEMINI_API_KEY not found in .env")

# Initialize Supabase
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try: supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except: pass

# --- 2. LOAD THE "TRAINED BRAIN" ---
chunks = []
vectorizer = None
tfidf_matrix = None

def load_brain():
    global chunks, vectorizer, tfidf_matrix
    print("⚡ Loading AI Brain (TF-IDF Models)...")
    
    # Load Raw Text Chunks
    if os.path.exists(kb_path):
        with open(kb_path, 'r', encoding='utf-8') as f:
            chunks = json.load(f)
    
    # Load Mathematical Models
    if os.path.exists(vectorizer_path) and os.path.exists(matrix_path):
        with open(vectorizer_path, 'rb') as f: vectorizer = pickle.load(f)
        with open(matrix_path, 'rb') as f: tfidf_matrix = pickle.load(f)
        print(f"   ✅ Brain Loaded: {len(chunks)} knowledge nodes.")
    else:
        print("   ⚠️ Brain missing! Run 'python backend/process_data.py' first.")

load_brain()

# --- 3. HYBRID CONTEXT RETRIEVAL ---
def get_context(query):
    if not vectorizer or not chunks: return ""
    
    q_lower = query.lower()
    relevant_text = []

    # --- STRATEGY A: HARD RULES (For "Exact" Tasks) ---
    # If user asks about Rooms/Vacancy, we dump the WHOLE timetable/room list.
    # TF-IDF is bad at "logic puzzles", so we give it all the data to solve it.
    if any(w in q_lower for w in ['room', 'vacant', 'free', 'empty', 'where', 'class']):
        # Filter chunks manually for room/timetable content
        room_data = [c for c in chunks if '[Campus Room Inventory]' in c]
        timetable_data = [c for c in chunks if 'Timetable' in c]
        
        # Return ALL room data so it can do the subtraction logic
        return "\n".join(room_data + timetable_data)

    # --- STRATEGY B: AI SEARCH (TF-IDF) ---
    # For Syllabus, Faculty, General info - use Math.
    try:
        query_vec = vectorizer.transform([query])
        similarities = cosine_similarity(query_vec, tfidf_matrix).flatten()
        
        # Get Top 8 Matches (Increased context for better accuracy)
        top_indices = similarities.argsort()[-8:][::-1]
        
        for idx in top_indices:
            if similarities[idx] > 0.1: # Only keep relevant stuff
                relevant_text.append(chunks[idx])
    except Exception as e:
        print(f"Search Error: {e}")

    if not relevant_text:
        return "No specific data found. Answer generally."
    
    return "\n---\n".join(relevant_text)

# --- 4. ROUTES ---
# --- IMAGE SERVING ROUTE ---
@app.route('/data/<path:filename>')
def serve_data(filename):
    # Defines the path to the 'data' folder in your project root
    data_dir = os.path.join(project_root, 'data')
    return send_from_directory(data_dir, filename)

@app.route('/')
def home(): return render_template('index.html')

# --- HISTORY ROUTE ---
@app.route('/get_history', methods=['POST'])
def get_history():
    if not supabase: return jsonify({'history': []})
    email = request.json.get('email')
    res = supabase.table('conversations').select('*').eq('user_email', email).order('created_at', desc=False).limit(50).execute()
    return jsonify({'history': res.data})

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        msg = data.get('message', '')
        hist = data.get('history', []) 
        role = data.get('role', 'guest')
        email = data.get('email', '')
        cid = data.get('class_id')
        
        # 1. Save User Message
        if supabase and email:
            supabase.table('conversations').insert({'user_email': email, 'role': 'user', 'message': msg}).execute()
        
        roster_ctx = ""
        
        # --- TEACHER INTELLIGENCE ---
        if role == 'teacher' and email and supabase:
            if not cid:
                c = supabase.table('classes').select('id').eq('teacher_email', email).limit(1).execute()
                if c.data: cid = c.data[0]['id']
            
            if cid:
                st = supabase.table('students').select('*').eq('class_id', cid).execute()
                s_list = "\n".join([f"Roll_ID: {s['student_id']} -> Name: {s['name']}" for s in st.data])
                roster_ctx = f"[CLASS ROSTER]\n{s_list}\n"

        kb_ctx = get_context(msg)
        
        # --- STRICT SYSTEM PROMPT ---
        sys_prompt = f"""
        You are the Faculty of Technology (FoT) Campus AI.
        
        [KNOWLEDGE BASE]
        {kb_ctx}
        
        [TEACHER DATA]
        {roster_ctx}
        
        [STRICT PROTOCOLS - DO NOT DEVIATE]
        1. **Syllabus:** Quote the syllabus EXACTLY. Do NOT invent units. If the text says Unit 3 contains X and Y, do not split them into Unit 3 and 4.
        2. **Vacant Rooms:** - Identify the Day and Time from the query.
           - Look at the [TIMETABLE] chunks provided.
           - List the rooms that are *occupied*.
           - Subtract them from the [Campus Room Inventory] list.
           - The result is the Vacant Rooms.
        3. **Attendance:** If asked to mark attendance, output strictly JSON: {{ "action": "update_attendance", "ids": ["123"], "status": "Present", "date": "YYYY-MM-DD" }}
        4. **General:** If the info is not in the Knowledge Base, say "I don't have that information."
        """

        ghist = [{"role": "user", "parts": ["System Instruction: " + sys_prompt]}]
        for m in hist:
            ghist.append({"role": "user" if m['isUser'] else "model", "parts": [m['text']]})
        
        chat_session = model.start_chat(history=ghist)
        resp = chat_session.send_message(msg)
        txt = resp.text.strip()

        # 2. Save Bot Response
        if supabase and email:
            save_text = txt
            if '"action":' in txt: save_text = "✅ Attendance Updated."
            supabase.table('conversations').insert({'user_email': email, 'role': 'model', 'message': save_text}).execute()

        # --- ACTION HANDLER ---
        if '"action":' in txt:
            try:
                clean = txt.replace('```json','').replace('```','').strip()
                cmd = json.loads(clean)
                
                if cid and cmd.get('action') == 'update_attendance':
                    t_ids = [str(i) for i in cmd.get('ids', [])]
                    status = cmd.get('status', 'Present')
                    date = cmd.get('date')
                    
                    st_data = supabase.table('students').select('student_id, name').eq('class_id', cid).execute().data
                    valid_map = {str(s['student_id']): s['name'] for s in st_data}
                    
                    updated_names = []
                    for tid in t_ids:
                        matched_id = next((k for k in valid_map.keys() if k.endswith(tid)), None)
                        if matched_id:
                            supabase.table('attendance_records').upsert({
                                "student_id": matched_id, "class_id": cid, 
                                "date": date, "status": status
                            }, on_conflict="student_id, class_id, date").execute()
                            updated_names.append(valid_map[matched_id])
                    
                    if updated_names:
                        return jsonify({'response': f"✅ Marked **{status}** for: {', '.join(updated_names)}", 'success': True})
                    else:
                        return jsonify({'response': f"❌ No matching students found.", 'success': True})
            except Exception as e:
                print(f"JSON Action Error: {e}")

        return jsonify({'response': txt, 'success': True})

    except Exception as e:
        print(traceback.format_exc())
        return jsonify({'response': f"Server Error: {str(e)}", 'success': False})

# --- 5. ROSTER UPLOAD ---
@app.route('/upload_smart_roster', methods=['POST'])
def upload_smart_roster():
    if not supabase: return jsonify({'success': False, 'msg': 'DB Error'})
    
    try:
        file = request.files['file']
        class_id = request.form.get('class_id')
        teacher_email = request.form.get('email')

        if not file or not class_id: return jsonify({'success': False, 'msg': 'Missing data'})

        if file.filename.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)

        df.columns = [c.lower().strip() for c in df.columns]
        roll_col = next((c for c in df.columns if 'roll' in c or 'id' in c), None)
        name_col = next((c for c in df.columns if 'name' in c or 'student' in c), None)

        if not roll_col or not name_col:
            return jsonify({'success': False, 'msg': 'Columns "Roll Number" and "Name" not found.'})

        count = 0
        for _, row in df.iterrows():
            sid = str(row[roll_col])
            sname = str(row[name_col])
            supabase.table('students').upsert({
                "student_id": sid, "name": sname, "class_id": class_id,
                "teacher_email": teacher_email, "details": {"Attendance": "0%"}
            }, on_conflict="class_id, student_id").execute()
            count += 1

        return jsonify({'success': True, 'count': count, 'msg': f'Uploaded {count} students.'})

    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)})

# --- UTILS: FULL SUBJECT MAP ---
SUBJECT_MAP = {
    "First Year": {
        "CSE": ["FCP (Programming)", "Mathematics-I", "IEEE / Physics", "Mathematics-II", "Data Structures", "Physics / IEEE"],
        "ECE": ["FCP (Programming)", "Mathematics-I", "IEEE / Physics", "Mathematics-II", "Data Structures", "Physics / IEEE"],
        "EE":  ["FCP (Programming)", "Mathematics-I", "IEEE / Physics", "Mathematics-II", "Data Structures", "Physics / IEEE"]
    },
    "Second Year": {
        "CSE": ["ADA (Algorithms)", "Digital System Design", "DBMS", "Operating Systems (OS)", "Software Engineering", "Computer System Arch."],
        "ECE": ["Electronic Devices", "Network Analysis", "Digital Electronics", "Signals & Systems", "Electromagnetic Theory", "Linear Integrated Circuits"],
        "EE":  ["Network Analysis", "Electrical Machines-I", "Analog & Digital Circuits", "Electrical Machines-II", "Power Trans. & Dist.", "Electrical Measurements"]
    },
    "Third Year": {
        "CSE": ["Theory of Computation", "AI & Machine Learning", "Computer Networks", "Cybersecurity", "Cloud Computing", "Software Project Mgmt"],
        "ECE": ["Control Systems", "Digital Signal Processing", "Analog Communication", "CMOS VLSI Design", "Embedded Systems", "Digital Communication"],
        "EE":  ["Power System Analysis", "Control Systems", "Electromagnetic Fields", "Switchgear & Protection", "Embedded Systems", "Power Electronics"]
    }
}

@app.route('/get_subjects_dynamic', methods=['POST'])
def get_subjects_dynamic():
    try:
        data = request.json
        year = data.get('year')
        branch = data.get('branch')
        subjects = SUBJECT_MAP.get(year, {}).get(branch, [])
        if not subjects: return jsonify({'subjects': [f"No data for {year} {branch}"]})
        return jsonify({'subjects': subjects})
    except Exception as e:
        return jsonify({'subjects': []})

@app.route('/login', methods=['POST'])
def login(): return jsonify({'success': True, 'email': request.json.get('email')})

@app.route('/get_classes', methods=['POST'])
def get_classes():
    if not supabase: return jsonify({'classes': []})
    res = supabase.table('classes').select('*').eq('teacher_email', request.json.get('email')).execute()
    return jsonify({'classes': res.data})

@app.route('/get_students', methods=['POST'])
def get_students():
    if not supabase: return jsonify({'students': []})
    res = supabase.table('students').select('*').eq('teacher_email', request.json.get('email')).execute()
    return jsonify({'students': res.data})

@app.route('/create_class', methods=['POST'])
def create_class():
    if supabase: supabase.table('classes').insert(request.json).execute()
    return jsonify({'success': True})

@app.route('/delete_student', methods=['POST'])
def delete_student():
    if supabase: supabase.table('students').delete().eq('student_id', request.json.get('id')).execute()
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(port=5001, debug=True)