import os
import json
import re
import time
import pickle
import google.generativeai as genai
from dotenv import load_dotenv
from pypdf import PdfReader
import PIL.Image
from sklearn.feature_extraction.text import TfidfVectorizer

# --- CONFIG ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
data_dir = os.path.join(project_root, 'data', 'knowledge_source') 
env_path = os.path.join(project_root, '.env')

# Paths for Saving the Brain
kb_path = os.path.join(current_dir, 'knowledge_base.json')
vectorizer_path = os.path.join(current_dir, 'vectorizer.pkl')
matrix_path = os.path.join(current_dir, 'tfidf_matrix.pkl')

load_dotenv(env_path)
api_key = os.getenv('GEMINI_API_KEY')

if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash')
else:
    model = None

def clean_text(text):
    return re.sub(r'\s+', ' ', text).strip()

# --- 1. UNIVERSAL SAFETY CHUNKER (Keep Syllabus Intact) ---
def universal_chunker(text, source_tag, max_chunk_size=4000):
    """
    Splits text by Headers/Units first, then by size if needed.
    Tags every chunk with its source (e.g., [Syllabus]).
    """
    # Step A: Semantic Split (Headers, Units, Horizontal Rules)
    semantic_chunks = re.split(r'(?=\n## |\n---|Unit \d|Module \d)', text)
    
    final_chunks = []
    
    for chunk in semantic_chunks:
        chunk = chunk.strip()
        if not chunk: continue
        
        # Add Source Tag
        tagged_chunk = f"[{source_tag}] {chunk}"
        
        # Step B: Size Safety Check
        if len(tagged_chunk) <= max_chunk_size:
            final_chunks.append(tagged_chunk)
        else:
            # If chunk is massive, slice it with overlap
            for i in range(0, len(chunk), max_chunk_size - 200):
                slice_text = chunk[i : i + max_chunk_size]
                final_chunks.append(f"[{source_tag}] {slice_text}")
                
    return final_chunks

# --- 2. FILE READERS ---
def analyze_image(image_path):
    if not model: return ""
    try:
        print(f"   👁️  AI Analyzing: {os.path.basename(image_path)}...")
        img = PIL.Image.open(image_path)
        prompt = "Analyze this image. Extract all text, map locations, dates, or names found. Output plain text."
        response = model.generate_content([prompt, img])
        return response.text
    except Exception as e:
        return ""

def extract_pdf_text(pdf_path):
    text = ""
    try:
        reader = PdfReader(pdf_path)
        for page in reader.pages: 
            extracted = page.extract_text()
            if extracted: text += extracted + "\n"
    except Exception: return ""
    return clean_text(text)

# --- 3. TRAINING THE BRAIN ---
def create_knowledge_base():
    print("------------------------------------------------")
    print("🧠 TRAINING AI BRAIN (TF-IDF + CHUNKING)")
    print("------------------------------------------------")
    
    if not os.path.exists(data_dir): return

    # We now use a FLAT LIST for TF-IDF, not a Dictionary
    all_knowledge_chunks = []
    files = os.listdir(data_dir)

    for f in files:
        if f.startswith('.'): continue
        fp = os.path.join(data_dir, f)
        content = ""
        
        # 1. READ CONTENT
        if f.lower().endswith(('.png', '.jpg', '.jpeg')):
            content = analyze_image(fp)
            time.sleep(1) 
        elif f.lower().endswith('.pdf'):
            print(f"   📄 Processing PDF: {f}")
            content = extract_pdf_text(fp)
        elif f.lower().endswith('.txt'):
            try:
                print(f"   📝 Processing Text: {f}")
                with open(fp, 'r', encoding='utf-8') as txt: content = txt.read()
            except: pass

        if not content: continue

        # 2. PROCESS CHUNKS
        # We use the filename as the "Source Tag" so the AI knows where data came from
        tag = f.replace('.txt', '').replace('.pdf', '').replace('_', ' ').title()
        
        chunks = universal_chunker(content, source_tag=tag)
        all_knowledge_chunks.extend(chunks)
        print(f"      -> Extracted {len(chunks)} segments.")

    # 3. SAVE TEXT DATABASE
    # This is the human-readable text
    with open(kb_path, 'w', encoding='utf-8') as f: 
        json.dump(all_knowledge_chunks, f, indent=4)
    
    print(f"   ✅ Text Database Saved: {len(all_knowledge_chunks)} total chunks.")

    # 4. TRAIN VECTORIZER (The "Regression" Part)
    print("   ⚙️  Training Math Model (TF-IDF)...")
    vectorizer = TfidfVectorizer(stop_words='english')
    tfidf_matrix = vectorizer.fit_transform(all_knowledge_chunks)
    
    # 5. SAVE THE BRAIN
    with open(vectorizer_path, 'wb') as f: pickle.dump(vectorizer, f)
    with open(matrix_path, 'wb') as f: pickle.dump(tfidf_matrix, f)
    
    print(f"   ✅ Model Trained! Vocab Size: {len(vectorizer.vocabulary_)}")
    print(f"   ✅ Saved to {vectorizer_path}")

if __name__ == "__main__":
    create_knowledge_base()