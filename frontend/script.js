// --- CONFIGURATION ---
// REPLACE THIS URL AFTER DEPLOYING YOUR BACKEND TO RAILWAY
// Example: "https://campus-gpt-production.up.railway.app"
const API_BASE = "cgpa-chatbot-production.up.railway.app"; // Default for local testing

// --- AUTO-LOGIN LOGIC ---
document.addEventListener('DOMContentLoaded', () => {
    const savedUser = localStorage.getItem('campus_user');
    const savedRole = localStorage.getItem('campus_role');

    if (savedUser && savedRole) {
        currentUser = savedUser;
        currentRole = savedRole;
        
        // Skip the intro animation for returning users
        document.getElementById('intro-wrapper').style.display = 'none';
        document.getElementById('guest-wrapper').style.display = 'none';
        document.getElementById('app-wrapper').style.display = 'flex';
        document.getElementById('app-wrapper').style.opacity = 1;
        
        document.getElementById('user-role-display').innerText = currentRole.toUpperCase();
        
        // Load Data
        loadChatHistory();
        loadDashboard();
        addMsg("Session Restored. Welcome back.", false);
    }
});


// --- SCROLL LOGIC ---
window.addEventListener('scroll', () => {
    const fraction = document.documentElement.scrollTop / (document.documentElement.scrollHeight - window.innerHeight);
    if (fraction > 0.95) {
        document.getElementById('intro-wrapper').style.opacity = 0;
        document.getElementById('intro-wrapper').style.pointerEvents = 'none';
        if(!currentUser) document.getElementById('guest-wrapper').style.display = 'flex';
    }
});

let currentUser = null;
let currentRole = 'student';
let currentClassId = null; // WE TRACK THIS NOW
let chatHistory = [];
// ... (Keep existing auth and scroll logic) ...

// --- VOICE LOGIC ---
let recognition;
let isListening = false;

if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
        isListening = true;
        document.getElementById('mic-btn').style.background = 'red';
        document.getElementById('mic-btn').style.color = 'white';
        document.getElementById('user-input').placeholder = "Listening...";
    };

    recognition.onend = () => {
        isListening = false;
        document.getElementById('mic-btn').style.background = 'transparent';
        document.getElementById('mic-btn').style.color = 'var(--accent)';
        document.getElementById('user-input').placeholder = "Type or Speak...";
    };

    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        document.getElementById('user-input').value = transcript;
        window.sendMessage(); // Auto send
    };
}

window.toggleVoice = () => {
    if (!recognition) return alert("Browser does not support voice.");
    if (isListening) recognition.stop();
    else recognition.start();
};

function speakText(text) {
    // Simple clean up for TTS (remove markdown)
    const cleanText = text.replace(/[*#`]/g, '');
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.rate = 1;
    utterance.pitch = 1;
    window.speechSynthesis.speak(utterance);
}

// --- HISTORY LOADER ---
async function loadChatHistory() {
    if (!currentUser) return;
    const res = await fetch(`${API_BASE}/get_history`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ email: currentUser })
    });
    const data = await res.json();
    
    const chatBox = document.getElementById('chat-box');
    // Don't clear, just append previous messages at top if needed, 
    // but for now let's just ensure we don't duplicate if dashboard reloads.
    chatBox.innerHTML = '<div class="msg bot">System Online. Welcome back.</div>';
    
    chatHistory = []; // Reset local context
    
    data.history.forEach(h => {
        const isUser = h.role === 'user';
        addMsg(h.message, isUser, false, false); // false flag to skip TTS on load
        chatHistory.push({ text: h.message, isUser: isUser });
    });
    
    // Scroll to bottom
    chatBox.scrollTop = chatBox.scrollHeight;
}

// --- UPDATED SEND MESSAGE ---
window.sendMessage = async (textInput = null) => {
    const input = document.getElementById('user-input');
    const text = textInput || input.value.trim();
    if (!text) return;
    
    addMsg(text, true); // User msg
    if (!textInput) input.value = '';
    
    const loadId = addMsg('Thinking...', false, true);

    try {
        const res = await fetch(`${API_BASE}/chat`, {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ 
                message: text, 
                history: chatHistory, 
                role: currentRole, 
                email: currentUser,
                class_id: currentClassId 
            })
        });
        const data = await res.json();
        document.getElementById(loadId).remove();
        
        addMsg(data.response, false, false, true); // True for TTS
        
        chatHistory.push({text, isUser:true});
        chatHistory.push({text: data.response, isUser:false});
    } catch (e) { document.getElementById(loadId).innerText = "Error."; }
};

function addMsg(text, isUser, isLoading, playAudio = false) {
    const div = document.createElement('div');
    div.className = `msg ${isUser ? 'user' : 'bot'}`;
    div.innerHTML = isLoading ? text : marked.parse(text);
    div.id = isLoading ? 'loading' : '';
    document.getElementById('chat-box').appendChild(div);
    document.getElementById('chat-box').scrollTop = 999999;
    
    if (playAudio && !isUser && !isLoading) {
        speakText(text);
    }
    
    return div.id;
}

// --- UPDATED AUTH ---
// Call loadChatHistory() inside window.finalizeAuth
window.finalizeAuth = async () => {
    // ... (existing auth logic) ...
    // After currentUser is set:
    loadChatHistory();
    loadDashboard();
};

// --- AUTH & GUEST ---
window.showAuthModal = (mode) => {
    document.getElementById('auth-modal').style.display = 'flex';
    document.getElementById('auth-title').innerText = mode === 'signup' ? "REGISTER" : "LOGIN";
};

window.toggleAuthMode = () => {
    const title = document.getElementById('auth-title');
    title.innerText = title.innerText === 'LOGIN' ? 'REGISTER' : 'LOGIN';
};

window.setRole = (role) => {
    currentRole = role;
    document.getElementById('btn-student').style.background = role === 'student' ? 'var(--accent)' : 'transparent';
    document.getElementById('btn-teacher').style.background = role === 'teacher' ? 'var(--accent)' : 'transparent';
};

window.finalizeAuth = async () => {
    const email = document.getElementById('email-in').value;
    if (!email) return alert("Email Required");
    
    // Save to LocalStorage
    localStorage.setItem('campus_user', email);
    localStorage.setItem('campus_role', currentRole);
    
    const res = await fetch(`${API_BASE}/login`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ email, role: currentRole })
    });
    
    currentUser = email;
    document.getElementById('auth-modal').style.display = 'none';
    document.getElementById('guest-wrapper').style.display = 'none';
    document.getElementById('app-wrapper').style.display = 'flex';
    setTimeout(() => document.getElementById('app-wrapper').style.opacity = 1, 50);
    
    loadChatHistory();
    loadDashboard();
};

// Add this to script.js
window.logout = () => {
    localStorage.removeItem('campus_user');
    localStorage.removeItem('campus_role');
    location.reload(); // Reloads page to show Login screen again
};

window.startGuestMode = () => {
    currentUser = null;
    currentRole = 'guest';
    document.getElementById('guest-wrapper').style.display = 'none';
    document.getElementById('app-wrapper').style.display = 'flex';
    setTimeout(() => document.getElementById('app-wrapper').style.opacity = 1, 50);
    loadDashboard();
};

// --- DASHBOARD ---
function loadDashboard() {
    const sidebar = document.getElementById('sidebar-content');
    const tools = document.getElementById('tools-bar');
    
    if (currentRole === 'student') {
        sidebar.innerHTML = `
            <div style="color:#888; font-size:0.8rem; margin-bottom:10px;">ACADEMIC YEAR</div>
            <select id="year-selector" style="width:100%; margin-bottom:10px; padding:8px; background:black; color:white; border:1px solid #333;">
                <option value="First Year">First Year</option>
                <option value="Second Year">Second Year</option>
                <option value="Third Year">Third Year</option>
            </select>
            <select id="branch-selector" onchange="window.fetchDynamicSubjects()" style="width:100%; margin-bottom:10px; padding:8px; background:black; color:white; border:1px solid #333;">
                <option value="">Branch...</option>
                <option value="CSE">CSE</option>
                <option value="ECE">ECE</option>
                <option value="EE">EE</option>
            </select>
            <div id="subject-list" style="margin-top:5px; font-size:0.8rem; color:var(--accent);"></div>
        `;
        tools.style.display = 'flex';
        tools.innerHTML = `<div class="chip" onclick="window.openMap()">Campus Map</div>`;
    } else if (currentRole === 'teacher') {
        sidebar.innerHTML = `
             <select id="class-selector" onchange="window.loadClassRoster()" style="width:100%; padding:10px; background:black; color:white; border:1px solid #333;"><option value="">Select Class...</option></select>
             <div id="roster-list" style="flex:1; overflow-y:auto; margin-top:10px;"></div>
        `;
        tools.style.display = 'flex';
        tools.innerHTML = `
            <input type="file" id="roster-upload" hidden onchange="window.uploadSmartRoster()">
            <div class="chip" onclick="document.getElementById('roster-upload').click()">Upload Roster</div>
            <div class="chip" style="color:red; border-color:red;" onclick="window.deleteRecord()">Delete Record</div>
        `;
        window.loadClasses();
    } else {
        sidebar.innerHTML = `<div style="padding:10px;">Guest Access.<br>Ask about Faculty, Syllabus, or Admissions.</div>`;
    }
}

// --- DATA FUNCTIONS ---
window.fetchDynamicSubjects = async () => {
    const year = document.getElementById('year-selector').value;
    const branch = document.getElementById('branch-selector').value;
    const list = document.getElementById('subject-list');

    if (!year || !branch) return;

    list.innerHTML = '<div style="color:white; padding:10px;"><i class="fas fa-spin fa-circle-notch"></i> Scanning PDFs...</div>';

    try {
        const res = await fetch(`${API_BASE}/get_subjects_dynamic`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ year, branch })
        });
        const data = await res.json();
        
        list.innerHTML = '';
        
        if (data.subjects && data.subjects.length > 0) {
            data.subjects.forEach(sub => {
                list.innerHTML += `
                <div class="chip" style="width:100%; justify-content:flex-start; margin-bottom:5px;" 
                     onclick="window.sendMessage('Syllabus for ${sub}')">
                    ${sub}
                </div>`;
            });
        } else {
            list.innerHTML = '<div style="color:red;">No syllabus found for this Year/Branch.</div>';
        }
    } catch (e) {
        list.innerHTML = "Connection Error.";
    }
};

window.loadClasses = async () => {
    const res = await fetch(`${API_BASE}/get_classes`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({email:currentUser})});
    const data = await res.json();
    const sel = document.getElementById('class-selector');
    sel.innerHTML = '<option value="">Select Class...</option>';
    data.classes.forEach(c => sel.innerHTML += `<option value="${c.id}">${c.class_name}</option>`);
    sel.innerHTML += '<option value="NEW">+ Create New</option>';
}

window.loadClassRoster = async () => {
    const val = document.getElementById('class-selector').value;
    if(val === 'NEW') {
        const name = prompt("Class Name:");
        await fetch(`${API_BASE}/create_class`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({email:currentUser, name})});
        window.loadClasses(); return;
    }
    currentClassId = val; // SAVE THIS
    const res = await fetch(`${API_BASE}/get_students`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({email:currentUser})});
    const data = await res.json();
    const list = document.getElementById('roster-list');
    list.innerHTML = '';
    data.students.filter(s => s.class_id == val).forEach(s => {
        list.innerHTML += `<div style="padding:10px; border-bottom:1px solid #333;">${s.name} (${s.student_id}) <span style="float:right; color:cyan;">${s.details.Attendance || 'N/A'}</span></div>`;
    });
}

window.uploadSmartRoster = async () => {
    const file = document.getElementById('roster-upload').files[0];
    const formData = new FormData();
    formData.append('file', file); formData.append('class_id', currentClassId); formData.append('email', currentUser);
    addMsg("Uploading...", false, true);
    await fetch(`${API_BASE}/upload_smart_roster`, { method:'POST', body:formData });
    window.loadClassRoster();
    addMsg("Done.", false);
}

window.deleteRecord = async () => {
    const id = prompt("ID to delete:");
    if(id) { await fetch(`${API_BASE}/delete_student`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id})}); window.loadClassRoster(); }
}

// --- CHAT ---
window.sendMessage = async (textInput = null) => {
    const input = document.getElementById('user-input');
    const text = textInput || input.value.trim();
    if (!text) return;
    
    addMsg(text, true);
    if (!textInput) input.value = '';
    const loadId = addMsg('Thinking...', false, true);

    try {
        // SEND CLASS_ID HERE
        const res = await fetch(`${API_BASE}/chat`, {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ 
                message: text, 
                history: chatHistory, 
                role: currentRole, 
                email: currentUser,
                class_id: currentClassId // KEY FIX
            })
        });
        const data = await res.json();
        document.getElementById(loadId).remove();
        addMsg(data.response, false);
        chatHistory.push({text, isUser:true});
        chatHistory.push({text: data.response, isUser:false});
    } catch (e) { document.getElementById(loadId).innerText = "Error."; }
};

function addMsg(text, isUser, isLoading) {
    const div = document.createElement('div');
    div.className = `msg ${isUser ? 'user' : 'bot'}`;
    div.innerHTML = isLoading ? text : marked.parse(text);
    div.id = isLoading ? 'loading' : '';
    document.getElementById('chat-box').appendChild(div);
    document.getElementById('chat-box').scrollTop = 999999;
    return div.id;
}

window.openMap = () => {
    document.getElementById('map-modal').style.display = 'flex';
    
    // Initialize Map
    if (window.campusMap) { window.campusMap.remove(); } // Reset if exists
    window.campusMap = L.map('tactical-map').setView([28.690, 77.207], 16);
    
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', { maxZoom: 20 }).addTo(window.campusMap);

    // --- DATA POINTS ---
    const locations = [
        { 
            lat: 28.687828658697054, lng: 77.21418554373469, title: "Kanad Bhawan (Academic Block)", 
            img: `${API_BASE}/data/structured_data/FoT_KanadBhawan.webp`,
            desc: "Classes and Labs on 2nd and 3rd Floor." 
        },
        { 
            lat: 28.689144509591976, lng: 77.2113344042128, title: "Central Science Library",  
            img: `${API_BASE}/data/structured_data/ScienceLibrary.jpg`,
            desc: "Access to research papers and study material." 
        },
        { 
            lat: 28.689325229058053, lng:  77.21139761300562, title: "DU Computer Centre", 
            img: "https://du.ac.in/du/uploads/slider/DUCC.jpg",
            desc: "Lecture halls R1-R4." 
        },
        {
            lat: 28.68868486826251, lng: 77.20978017821722, title: "Gate no. 4, University of Delhi",
            img: `${API_BASE}/data/structured_data/Gateno4.jpg`,
            desc:"One of the entries to Faculty of Technology."
        },
        { 
            lat: 28.689815449124655, lng: 77.21022550328749, title: "Entry to Geology Department", 
            img: `${API_BASE}/data/structured_data/GeoDept.jpg`,
            desc: "Nearest entry to Classes R1 to R4 i.e. DUCC." 
        },
        { 
            lat: 28.68922650677703, lng: 77.21510440060177, title: "Gate no. 1, University of Delhi",   
            img: `${API_BASE}/data/structured_data/GateNo1.jpg`,
            desc: "Nearest to Examination office and VC office." 
        },
        { 
            lat: 28.688426021158353, lng:  77.21438146812639, title: "College Canteen, Administrative Block",  
            img: `${API_BASE}/data/structured_data/Canteen.jpg`,
            desc: "Nearest Canteen to Faculty of Technology." 
        },
        {
            lat: 28.687144819175142, lng: 77.21385126240584, title: "Stationery Shop", 
            img: `${API_BASE}/data/structured_data/Stationaryshop.jpg`,
            desc:"Nearest stationry/photostate shop to FoT."
        }
    ];

    locations.forEach(loc => {
        const popupContent = `
            <div style="width:200px; color:black; text-align:center;">
                <img src="${loc.img}" style="width:100%; height:120px; object-fit:cover; border-radius:8px; margin-bottom:8px;">
                <h3 style="margin:0; font-size:1rem;">${loc.title}</h3>
                <p style="margin:5px 0 0 0; font-size:0.8rem; color:#555;">${loc.desc}</p>
            </div>
        `;
        L.marker([loc.lat, loc.lng]).addTo(window.campusMap).bindPopup(popupContent);
    });

    setTimeout(() => window.campusMap.invalidateSize(), 200);
};

document.getElementById('user-input').addEventListener('keypress', (e) => { if (e.key === 'Enter') window.sendMessage(); });