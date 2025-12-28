"""
🏛️ HỆ THỐNG TIẾP NHẬN PHẢN ÁNH & TƯ VẤN CỘNG ĐỒNG
TÍCH HỢP GIỌNG NÓI - DÙNG WEB SPEECH API
GIỮ NGUYÊN TẤT CẢ TÍNH NĂNG
"""

import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import hashlib
import secrets
import time
import os
import json

# ================ CẤU HÌNH GIỜ VIỆT NAM ================
import pytz

# Múi giờ Việt Nam (UTC+7)
VIETNAM_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

def get_vietnam_time():
    """Lấy thời gian hiện tại theo giờ Việt Nam"""
    utc_now = datetime.utcnow()
    vietnam_time = utc_now + timedelta(hours=7)
    return vietnam_time.replace(tzinfo=VIETNAM_TZ)

def format_vietnam_time(dt, format_str='%H:%M %d/%m/%Y'):
    """Định dạng thời gian theo giờ Việt Nam"""
    if dt is None:
        return "N/A"
    
    if isinstance(dt, str):
        try:
            dt = datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
        except:
            return dt
    
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=VIETNAM_TZ)
    
    return dt.strftime(format_str)

# ================ PHÁT HIỆN THIẾT BỊ ================
import platform

def detect_device_info():
    """Phát hiện loại thiết bị và trình duyệt"""
    device_info = {
        'is_mobile': False,
        'is_ios': False,
        'is_android': False,
        'is_safari': False,
        'is_chrome': False,
        'is_firefox': False,
        'browser': 'unknown',
        'os': 'unknown'
    }
    
    try:
        # Try to get from query params
        try:
            query_params = st.experimental_get_query_params()
            user_agent = query_params.get('_ua', [''])[0].lower()
        except:
            user_agent = ''
        
        if not user_agent:
            # Fallback based on platform
            system = platform.system()
            device_info['os'] = system
            
            if system == 'Darwin':
                device_info['is_safari'] = True
            elif system == 'Windows':
                device_info['is_chrome'] = True
            
            return device_info
        
        # Detect OS
        if 'iphone' in user_agent or 'ipad' in user_agent or 'ipod' in user_agent:
            device_info['is_mobile'] = True
            device_info['is_ios'] = True
            device_info['os'] = 'iOS'
        elif 'android' in user_agent:
            device_info['is_mobile'] = True
            device_info['is_android'] = True
            device_info['os'] = 'Android'
        elif 'mac os' in user_agent or 'macintosh' in user_agent:
            device_info['os'] = 'macOS'
        elif 'windows' in user_agent:
            device_info['os'] = 'Windows'
        elif 'linux' in user_agent:
            device_info['os'] = 'Linux'
        
        # Detect browser
        if 'safari' in user_agent and 'chrome' not in user_agent:
            device_info['is_safari'] = True
            device_info['browser'] = 'Safari'
        elif 'chrome' in user_agent:
            device_info['is_chrome'] = True
            device_info['browser'] = 'Chrome'
        elif 'firefox' in user_agent:
            device_info['is_firefox'] = True
            device_info['browser'] = 'Firefox'
        elif 'edge' in user_agent:
            device_info['browser'] = 'Edge'
        
        # Detect mobile device
        mobile_keywords = ['mobile', 'iphone', 'ipad', 'android', 'blackberry', 
                          'webos', 'iemobile', 'opera mini', 'windows phone']
        if any(keyword in user_agent for keyword in mobile_keywords):
            device_info['is_mobile'] = True
            
    except Exception as e:
        st.error(f"Lỗi phát hiện thiết bị: {str(e)}")
    
    return device_info

# ================ IMPORT THƯ VIỆN ================
from werkzeug.security import generate_password_hash, check_password_hash

# Import SendGrid email service
try:
    from email_service import send_email_report
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False

# ================ CẤU HÌNH DATABASE ================
DB_PATH = 'community_app.db'

# ================ CẤU HÌNH TRANG ================
st.set_page_config(
    page_title="Cổng Tiếp Nhận Phản Ánh Cộng Đồng",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ================ WEB SPEECH API COMPONENT ================
def create_speech_component(field_id, label="Nhập văn bản bằng giọng nói"):
    """Tạo component nhận diện giọng nói"""
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Speech Recognition</title>
        <style>
            .speech-container {{
                padding: 15px;
                border: 2px solid #3B82F6;
                border-radius: 10px;
                background: linear-gradient(135deg, #f0f8ff 0%, #e6f3ff 100%);
                margin: 10px 0;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .speech-header {{
                color: #1E3A8A;
                font-size: 1.1em;
                margin-bottom: 10px;
                font-weight: bold;
            }}
            .speech-btn {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                cursor: pointer;
                font-weight: bold;
                margin: 5px;
                transition: all 0.3s;
                display: inline-flex;
                align-items: center;
                gap: 8px;
            }}
            .speech-btn:hover {{
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            }}
            .speech-btn.recording {{
                background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
                animation: pulse 1.5s infinite;
            }}
            @keyframes pulse {{
                0% {{ opacity: 1; }}
                50% {{ opacity: 0.8; }}
                100% {{ opacity: 1; }}
            }}
            .status-box {{
                background: white;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 10px;
                margin: 10px 0;
                font-size: 14px;
                min-height: 40px;
            }}
            .result-box {{
                background: #f8f9fa;
                border: 1px solid #28a745;
                border-radius: 5px;
                padding: 12px;
                margin: 10px 0;
                font-size: 16px;
                min-height: 60px;
            }}
            .language-select {{
                margin: 10px 0;
                padding: 5px;
                border-radius: 5px;
                border: 1px solid #ccc;
            }}
            .instructions {{
                background: #fff3cd;
                border: 1px solid #ffc107;
                border-radius: 5px;
                padding: 10px;
                margin: 10px 0;
                font-size: 14px;
            }}
        </style>
    </head>
    <body>
        <div class="speech-container">
            <div class="speech-header">🎤 {label}</div>
            
            <div class="instructions">
                <strong>Hướng dẫn:</strong>
                <ol>
                    <li>Nhấn <strong>Bắt đầu nói</strong> và cho phép micro</li>
                    <li>Nói rõ ràng vào micro</li>
                    <li>Nhấn <strong>Dừng lại</strong> khi hoàn thành</li>
                    <li>Nhấn <strong>Gửi kết quả</strong> để điền vào form</li>
                </ol>
            </div>
            
            <select class="language-select" id="languageSelect">
                <option value="vi-VN">Tiếng Việt</option>
                <option value="en-US">Tiếng Anh</option>
            </select>
            
            <button class="speech-btn" onclick="startRecognition()" id="startBtn">
                🎤 Bắt đầu nói
            </button>
            
            <button class="speech-btn" onclick="stopRecognition()" id="stopBtn" style="display:none;">
                ⏹️ Dừng lại
            </button>
            
            <button class="speech-btn" onclick="sendResultToStreamlit()" id="sendBtn" style="display:none;">
                📤 Gửi kết quả
            </button>
            
            <div class="status-box" id="statusBox">
                <span id="statusText">Sẵn sàng nhận diện giọng nói...</span>
            </div>
            
            <div class="result-box" id="resultBox">
                <strong>Kết quả nhận diện:</strong><br>
                <span id="resultText">Kết quả sẽ hiển thị ở đây</span>
            </div>
        </div>

        <script>
        let recognition = null;
        let isListening = false;
        let finalTranscript = '';
        let currentLanguage = 'vi-VN';
        
        // Kiểm tra hỗ trợ Web Speech API
        function checkSpeechSupport() {{
            if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {{
                document.getElementById('statusText').innerHTML = 
                    '❌ Trình duyệt không hỗ trợ nhận diện giọng nói. Vui lòng dùng Chrome, Edge hoặc Safari.';
                document.getElementById('statusText').style.color = '#dc3545';
                return false;
            }}
            return true;
        }}
        
        // Khởi tạo Speech Recognition
        function initSpeechRecognition() {{
            if (!checkSpeechSupport()) return null;
            
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            recognition = new SpeechRecognition();
            
            // Cấu hình
            recognition.continuous = true;
            recognition.interimResults = true;
            recognition.lang = currentLanguage;
            recognition.maxAlternatives = 1;
            
            // Xử lý sự kiện
            recognition.onstart = () => {{
                isListening = true;
                updateStatus('🎤 <strong>ĐANG NGHE...</strong> Hãy nói vào micro', '#28a745');
                document.getElementById('startBtn').classList.add('recording');
                document.getElementById('startBtn').style.display = 'none';
                document.getElementById('stopBtn').style.display = 'inline-block';
                document.getElementById('sendBtn').style.display = 'none';
            }};
            
            recognition.onresult = (event) => {{
                let interimTranscript = '';
                
                for (let i = event.resultIndex; i < event.results.length; i++) {{
                    const transcript = event.results[i][0].transcript;
                    
                    if (event.results[i].isFinal) {{
                        finalTranscript += transcript + ' ';
                    }} else {{
                        interimTranscript += transcript;
                    }}
                }}
                
                // Cập nhật kết quả
                document.getElementById('resultText').innerHTML = 
                    '<span style="color: #28a745">' + finalTranscript + '</span>' + 
                    '<br><span style="color: #6c757d"><em>' + interimTranscript + '</em></span>';
            }};
            
            recognition.onerror = (event) => {{
                console.error('Speech recognition error:', event.error);
                
                let errorMsg = 'Lỗi nhận diện: ';
                switch(event.error) {{
                    case 'no-speech':
                        errorMsg = 'Không phát hiện giọng nói. Vui lòng nói lại.';
                        break;
                    case 'audio-capture':
                        errorMsg = 'Không thể truy cập micro. Vui lòng kiểm tra quyền truy cập.';
                        break;
                    case 'not-allowed':
                        errorMsg = 'Micro bị từ chối. Vui lòng cho phép micro trong cài đặt trình duyệt.';
                        break;
                    default:
                        errorMsg = 'Lỗi: ' + event.error;
                }}
                
                updateStatus('❌ ' + errorMsg, '#dc3545');
                stopRecognition();
            }};
            
            recognition.onend = () => {{
                if (isListening) {{
                    // Tự động bắt đầu lại nếu vẫn đang nghe
                    try {{
                        recognition.start();
                    }} catch (e) {{
                        console.log('Auto-restart failed:', e);
                    }}
                }} else {{
                    updateStatus('✅ Đã dừng ghi âm', '#6c757d');
                    document.getElementById('startBtn').classList.remove('recording');
                    document.getElementById('startBtn').style.display = 'inline-block';
                    document.getElementById('stopBtn').style.display = 'none';
                    document.getElementById('sendBtn').style.display = 'inline-block';
                }}
            }};
            
            return recognition;
        }}
        
        // Bắt đầu nhận diện
        function startRecognition() {{
            if (!recognition) {{
                recognition = initSpeechRecognition();
                if (!recognition) return;
            }}
            
            // Cập nhật ngôn ngữ
            currentLanguage = document.getElementById('languageSelect').value;
            recognition.lang = currentLanguage;
            
            // Reset transcript
            finalTranscript = '';
            document.getElementById('resultText').innerHTML = 'Đang nghe...';
            
            try {{
                recognition.start();
            }} catch (e) {{
                updateStatus('❌ Không thể bắt đầu: ' + e.message, '#dc3545');
            }}
        }}
        
        // Dừng nhận diện
        function stopRecognition() {{
            if (recognition && isListening) {{
                isListening = false;
                recognition.stop();
            }}
        }}
        
        // Gửi kết quả về Streamlit
        function sendResultToStreamlit() {{
            const text = finalTranscript.trim();
            if (!text) {{
                updateStatus('⚠️ Không có nội dung để gửi', '#ffc107');
                return;
            }}
            
            // Gửi message về parent window
            window.parent.postMessage({{
                type: 'SPEECH_RESULT',
                fieldId: '{field_id}',
                text: text,
                language: currentLanguage
            }}, '*');
            
            updateStatus('✅ Đã gửi kết quả thành công!', '#28a745');
        }}
        
        // Cập nhật trạng thái
        function updateStatus(message, color) {{
            const statusEl = document.getElementById('statusText');
            statusEl.innerHTML = message;
            statusEl.style.color = color;
        }}
        
        // Xử lý khi trang load
        window.addEventListener('load', () => {{
            if (!checkSpeechSupport()) {{
                document.getElementById('startBtn').disabled = true;
                document.getElementById('startBtn').style.opacity = '0.5';
            }}
        }});
        
        // Lắng nghe message từ Streamlit
        window.addEventListener('message', (event) => {{
            if (event.data.type === 'GET_SPEECH_RESULT') {{
                sendResultToStreamlit();
            }}
        }});
        </script>
    </body>
    </html>
    """
    
    return html

# ================ CSS STYLING ================
st.markdown("""
<style>
    .main-header {
        text-align: center;
        color: white;
        padding: 1.5rem;
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .report-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
        border-left: 5px solid #dc3545;
    }
    .forum-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
        border-left: 5px solid #28a745;
    }
    .police-badge {
        background: #dc3545;
        color: white;
        padding: 0.3rem 1rem;
        border-radius: 20px;
        font-size: 0.9rem;
        font-weight: bold;
        display: inline-block;
    }
    .success-box {
        background: #d4edda;
        color: #155724;
        padding: 1rem;
        border-radius: 5px;
        border-left: 5px solid #28a745;
        margin: 1rem 0;
    }
    .warning-box {
        background: #fff3cd;
        color: #856404;
        padding: 1rem;
        border-radius: 5px;
        border-left: 5px solid #ffc107;
        margin: 1rem 0;
    }
    .official-reply {
        background: #e8f4fd !important;
        border-left: 4px solid #007bff !important;
        border: 1px solid #007bff;
    }
    .user-reply {
        background: #f8f9fa !important;
    }
    .tab-content {
        padding: 1.5rem;
        background: #f8f9fa;
        border-radius: 10px;
        margin-top: 1rem;
    }
    .vietnam-time {
        background: #e6f3ff;
        padding: 5px 10px;
        border-radius: 5px;
        border-left: 4px solid #0066cc;
        font-size: 0.9em;
        margin: 5px 0;
    }
    .speech-section {
        background: linear-gradient(135deg, #f0f8ff 0%, #e6f3ff 100%);
        padding: 20px;
        border-radius: 10px;
        border: 2px solid #3B82F6;
        margin: 20px 0;
    }
    .device-warning {
        background: #fff3cd;
        border: 1px solid #ffc107;
        border-radius: 5px;
        padding: 10px;
        margin: 10px 0;
        font-size: 0.9em;
    }
</style>
""", unsafe_allow_html=True)

# ================ HIỂN THỊ GIỜ VIỆT NAM ================
def show_vietnam_time():
    """Hiển thị giờ Việt Nam hiện tại"""
    vietnam_now = get_vietnam_time()
    st.sidebar.markdown(f"""
    <div class="vietnam-time">
        <strong>🇻🇳 Giờ Việt Nam:</strong><br>
        {format_vietnam_time(vietnam_now, '%H:%M:%S')}<br>
        {format_vietnam_time(vietnam_now, '%A, %d/%m/%Y')}
    </div>
    """, unsafe_allow_html=True)

# ================ KHỞI TẠO DATABASE ================
def init_database():
    """Khởi tạo tất cả bảng database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Bảng phản ánh an ninh
        c.execute('''
            CREATE TABLE IF NOT EXISTS security_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                location TEXT,
                incident_time TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_hash TEXT,
                email_sent BOOLEAN DEFAULT 0
            )
        ''')
        
        # Bảng diễn đàn
        c.execute('''
            CREATE TABLE IF NOT EXISTS forum_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT DEFAULT 'Hỏi đáp pháp luật',
                anonymous_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reply_count INTEGER DEFAULT 0,
                is_answered BOOLEAN DEFAULT 0
            )
        ''')
        
        # Bảng bình luận
        c.execute('''
            CREATE TABLE IF NOT EXISTS forum_replies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER,
                content TEXT NOT NULL,
                author_type TEXT DEFAULT 'anonymous',
                author_id TEXT,
                display_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_official BOOLEAN DEFAULT 0,
                FOREIGN KEY (post_id) REFERENCES forum_posts(id)
            )
        ''')
        
        # Bảng công an
        c.execute('''
            CREATE TABLE IF NOT EXISTS police_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                badge_number TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'officer'
            )
        ''')
        
        # Tạo admin mặc định nếu chưa có
        c.execute("SELECT COUNT(*) FROM police_users WHERE badge_number = 'CA001'")
        if c.fetchone()[0] == 0:
            password_hash = generate_password_hash("congan123", method='pbkdf2:sha256')
            c.execute('''
                INSERT INTO police_users (badge_number, display_name, password_hash, role)
                VALUES (?, ?, ?, ?)
            ''', ('CA001', 'Admin Công An', password_hash, 'admin'))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        st.error(f"Lỗi khởi tạo database: {str(e)}")

# ================ HÀM XỬ LÝ PHẢN ÁNH ================
def save_to_database(title, description, location="", incident_time=""):
    """Lưu phản ánh vào database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        ip_hash = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
        
        c.execute('''
            INSERT INTO security_reports (title, description, location, incident_time, ip_hash)
            VALUES (?, ?, ?, ?, ?)
        ''', (title, description, location, incident_time, ip_hash))
        
        conn.commit()
        report_id = c.lastrowid
        conn.close()
        
        return report_id
    except Exception as e:
        return None

def handle_security_report(title, description, location, incident_time):
    """Xử lý phản ánh và gửi email"""
    report_id = save_to_database(title, description, location, incident_time)
    
    if not report_id:
        return None, False, "Lỗi lưu database"
    
    report_data = {
        'title': title,
        'description': description,
        'location': location,
        'incident_time': incident_time,
        'report_id': report_id,
        'created_at': format_vietnam_time(get_vietnam_time())
    }
    
    if SENDGRID_AVAILABLE:
        email_success, email_message = send_email_report(report_data)
    else:
        email_success = False
        email_message = "Tính năng email chưa được cấu hình"
    
    if email_success:
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('UPDATE security_reports SET email_sent = 1 WHERE id = ?', (report_id,))
            conn.commit()
            conn.close()
        except:
            pass
    
    return report_id, email_success, email_message

# ================ HÀM DIỄN ĐÀN ================
def save_forum_post(title, content, category):
    """Lưu bài đăng diễn đàn"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        anonymous_id = f"NgườiDân_{secrets.token_hex(4)}"
        
        c.execute('''
            INSERT INTO forum_posts (title, content, category, anonymous_id)
            VALUES (?, ?, ?, ?)
        ''', (title, content, category, anonymous_id))
        
        conn.commit()
        post_id = c.lastrowid
        conn.close()
        
        return post_id, anonymous_id, None
        
    except Exception as e:
        return None, None, f"Lỗi: {str(e)}"

def save_forum_reply(post_id, content, is_police=False, police_info=None):
    """Lưu bình luận diễn đàn"""
    try:
        if not is_police or not police_info:
            return None, "Chỉ công an mới được bình luận và trả lời câu hỏi."
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        author_type = "police"
        author_id = police_info['badge_number']
        display_name = police_info['display_name']
        is_official = 1
        
        c.execute('''
            INSERT INTO forum_replies (post_id, content, author_type, author_id, display_name, is_official)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (post_id, content, author_type, author_id, display_name, is_official))
        
        c.execute('UPDATE forum_posts SET is_answered = 1 WHERE id = ?', (post_id,))
        
        c.execute('SELECT COUNT(*) FROM forum_replies WHERE post_id = ?', (post_id,))
        reply_count = c.fetchone()[0]
        c.execute('UPDATE forum_posts SET reply_count = ? WHERE id = ?', (reply_count, post_id))
        
        conn.commit()
        reply_id = c.lastrowid
        conn.close()
        
        return reply_id, "Bình luận đã được gửi thành công!"
        
    except Exception as e:
        return None, f"Lỗi hệ thống: {str(e)}"

def get_forum_posts(category_filter="Tất cả"):
    """Lấy danh sách bài đăng với thời gian VN"""
    try:
        conn = sqlite3.connect(DB_PATH)
        
        query = '''
            SELECT id, title, content, category, anonymous_id, 
                   created_at, reply_count, is_answered
            FROM forum_posts
        '''
        
        params = []
        if category_filter != "Tất cả":
            query += " WHERE category = ?"
            params.append(category_filter)
        
        query += " ORDER BY created_at DESC LIMIT 50"
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        if not df.empty and 'created_at' in df.columns:
            df['formatted_date'] = df['created_at'].apply(
                lambda x: format_vietnam_time(x, '%H:%M %d/%m/%Y') if pd.notnull(x) else "N/A"
            )
        
        return df
    except:
        return pd.DataFrame()

def get_forum_replies(post_id):
    """Lấy bình luận của bài đăng với thời gian VN"""
    try:
        conn = sqlite3.connect(DB_PATH)
        query = '''
            SELECT id, content, author_type, display_name, is_official, created_at
            FROM forum_replies
            WHERE post_id = ?
            ORDER BY created_at ASC
        '''
        df = pd.read_sql_query(query, conn, params=(post_id,))
        conn.close()
        
        if not df.empty and 'created_at' in df.columns:
            df['formatted_date'] = df['created_at'].apply(
                lambda x: format_vietnam_time(x, '%H:%M %d/%m/%Y') if pd.notnull(x) else "N/A"
            )
        
        return df
    except:
        return pd.DataFrame()

# ================ ĐĂNG NHẬP CÔNG AN ================
def police_login(badge_number, password):
    """Đăng nhập công an"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute('''
            SELECT badge_number, display_name, password_hash, role 
            FROM police_users 
            WHERE badge_number = ?
        ''', (badge_number,))
        
        user = c.fetchone()
        conn.close()
        
        if user and check_password_hash(user[2], password):
            return {
                'badge_number': user[0],
                'display_name': user[1],
                'role': user[3]
            }
        return None
    except Exception as e:
        return None

# ================ GIAO DIỆN CHÍNH ================
def main():
    """Hàm chính của ứng dụng"""
    
    init_database()
    
    # Phát hiện thiết bị
    device_info = detect_device_info()
    
    # Khởi tạo session state
    session_defaults = {
        'police_user': None,
        'show_new_question': False,
        'speech_results': {},
        'device_info': device_info
    }
    
    for key, value in session_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    
    # Hiển thị cảnh báo nếu là thiết bị di động
    if device_info['is_mobile']:
        st.markdown(f"""
        <div class="device-warning">
            📱 <strong>ĐANG TRUY CẬP TỪ {device_info['os'].upper()}</strong><br>
            <small>• Dùng {device_info['browser']} để có trải nghiệm tốt nhất</small><br>
            <small>• Micro điện thoại sẽ tự động được sử dụng</small>
        </div>
        """, unsafe_allow_html=True)
    
    # Header với thông tin thiết bị
    vietnam_now = get_vietnam_time()
    device_icon = "📱" if device_info['is_mobile'] else "💻"
    
    st.markdown(f"""
    <div class="main-header">
        <h1>{device_icon} CỔNG TIẾP NHẬN PHẢN ÁNH CỘNG ĐỒNG</h1>
        <p>Phản ánh an ninh • Hỏi đáp pháp luật • Ẩn danh hoàn toàn • Giờ Việt Nam: {format_vietnam_time(vietnam_now)}</p>
        <p><small>⚠️ <strong>Chỉ công an mới được bình luận và trả lời câu hỏi</strong></small></p>
        <p><small>🎤 <strong>Giọng nói hỗ trợ: {device_info['browser']} trên {device_info['os']}</strong></small></p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("### 🔐 Đăng nhập Công an")
        
        if not st.session_state.police_user:
            badge = st.text_input("Số hiệu", key="login_badge")
            password = st.text_input("Mật khẩu", type="password", key="login_password")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Đăng nhập", type="primary", use_container_width=True):
                    user = police_login(badge, password)
                    if user:
                        st.session_state.police_user = user
                        st.success(f"Xin chào {user['display_name']}!")
                        st.rerun()
                    else:
                        st.error("Sai số hiệu hoặc mật khẩu!")
            with col2:
                st.button("Đăng xuất", disabled=True, use_container_width=True)
        else:
            user = st.session_state.police_user
            st.success(f"👮 **{user['display_name']}**")
            st.info(f"Số hiệu: `{user['badge_number']}`")
            
            if st.button("🚪 Đăng xuất", use_container_width=True):
                st.session_state.police_user = None
                st.success("Đã đăng xuất!")
                st.rerun()
        
        # Hiển thị giờ Việt Nam
        show_vietnam_time()
        
        # Thông tin thiết bị
        st.markdown("---")
        st.markdown("### 📱 Thông tin thiết bị")
        
        if device_info['is_mobile']:
            st.success(f"📱 **{device_info['os']}** - {device_info['browser']}")
            st.caption("Đang sử dụng phiên bản di động")
        else:
            st.info(f"💻 **{device_info['os']}** - {device_info['browser']}")
        
        # Thông tin hệ thống
        st.markdown("---")
        st.markdown("### 📊 Thống kê nhanh")
        
        try:
            conn = sqlite3.connect(DB_PATH)
            today = get_vietnam_time().strftime('%Y-%m-%d')
            
            col1, col2, col3 = st.columns(3)
            with col1:
                total_reports = pd.read_sql_query("SELECT COUNT(*) FROM security_reports", conn)
                st.metric("Phản ánh", int(total_reports.iloc[0,0]))
            with col2:
                total_posts = pd.read_sql_query("SELECT COUNT(*) FROM forum_posts", conn)
                st.metric("Câu hỏi", int(total_posts.iloc[0,0]))
            with col3:
                today_reports = pd.read_sql_query(
                    "SELECT COUNT(*) FROM security_reports WHERE DATE(created_at) = ?", 
                    conn, params=(today,)
                )
                st.metric("Hôm nay", int(today_reports.iloc[0,0]))
            
            conn.close()
        except:
            st.warning("Không thể kết nối database")
    
    # Main tabs
    tab1, tab2, tab3 = st.tabs(["📢 PHẢN ÁNH AN NINH", "💬 DIỄN ĐÀN", "ℹ️ THÔNG TIN"])
    
    # ========= TAB 1: PHẢN ÁNH AN NINH =========
    with tab1:
        st.subheader("Biểu mẫu Phản ánh An ninh Trật tự")
        
        # Hiển thị thời gian hiện tại
        now_vn = get_vietnam_time()
        st.info(f"**Thời gian hiện tại:** {format_vietnam_time(now_vn, '%H:%M %d/%m/%Y')}")
        
        if not SENDGRID_AVAILABLE:
            st.warning("⚠️ Tính năng email chưa sẵn sàng")
        
        # ========== COMPONENT GIỌNG NÓI CHO FORM PHẢN ÁNH ==========
        st.markdown("### 🎤 Tính năng giọng nói")
        
        # Tạo các component giọng nói cho từng field
        speech_fields = {
            'title': 'Tiêu đề phản ánh',
            'location': 'Địa điểm',
            'description': 'Mô tả chi tiết'
        }
        
        # Container cho các component giọng nói
        with st.container():
            st.markdown('<div class="speech-section">', unsafe_allow_html=True)
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("**Tiêu đề bằng giọng nói:**")
                st.components.v1.html(
                    create_speech_component("speech_title", "Nói tiêu đề phản ánh"),
                    height=400
                )
                
            with col2:
                st.markdown("**Địa điểm bằng giọng nói:**")
                st.components.v1.html(
                    create_speech_component("speech_location", "Nói địa điểm sự việc"),
                    height=400
                )
                
            with col3:
                st.markdown("**Mô tả bằng giọng nói:**")
                st.components.v1.html(
                    create_speech_component("speech_description", "Nói mô tả chi tiết"),
                    height=400
                )
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # FORM PHẢN ÁNH
        with st.form("security_report_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                # Tiêu đề
                title_key = "report_title_input"
                if title_key not in st.session_state:
                    st.session_state[title_key] = ""
                
                # Nếu có kết quả từ speech component
                if 'speech_results' in st.session_state and 'speech_title' in st.session_state.speech_results:
                    st.session_state[title_key] = st.session_state.speech_results['speech_title']
                
                title = st.text_input(
                    "Tiêu đề phản ánh *", 
                    placeholder="Ví dụ: Mất trộm xe máy tại...",
                    value=st.session_state[title_key],
                    key=title_key
                )
                
                # Địa điểm
                location_key = "report_location_input"
                if location_key not in st.session_state:
                    st.session_state[location_key] = ""
                
                if 'speech_results' in st.session_state and 'speech_location' in st.session_state.speech_results:
                    st.session_state[location_key] = st.session_state.speech_results['speech_location']
                
                location = st.text_input(
                    "Địa điểm", 
                    placeholder="Số nhà, đường, phường/xã...",
                    value=st.session_state[location_key],
                    key=location_key
                )
            
            with col2:
                incident_time = st.text_input(
                    "Thời gian xảy ra", 
                    placeholder=f"VD: {format_vietnam_time(now_vn, '%H:%M')} ngày {format_vietnam_time(now_vn, '%d/%m')}",
                    key="report_time"
                )
            
            # Mô tả
            desc_key = "report_description_input"
            if desc_key not in st.session_state:
                st.session_state[desc_key] = ""
            
            if 'speech_results' in st.session_state and 'speech_description' in st.session_state.speech_results:
                st.session_state[desc_key] = st.session_state.speech_results['speech_description']
            
            description = st.text_area(
                "Mô tả chi tiết *",
                height=150,
                placeholder="Mô tả đầy đủ sự việc, đối tượng, phương tiện, thiệt hại...",
                value=st.session_state[desc_key],
                key=desc_key
            )
            
            # Nút submit
            submitted = st.form_submit_button("🚨 GỬI PHẢN ÁNH", use_container_width=True)
            
            if submitted:
                if not title or not description:
                    st.error("⚠️ Vui lòng điền tiêu đề và mô tả sự việc!")
                else:
                    submit_time = get_vietnam_time()
                    
                    report_id, email_success, email_message = handle_security_report(
                        title, description, location, incident_time
                    )
                    
                    if report_id:
                        if email_success:
                            st.markdown(f"""
                            <div class="success-box">
                                <h4>✅ ĐÃ TIẾP NHẬN PHẢN ÁNH #{report_id:06d}</h4>
                                <p>{email_message}</p>
                                <p><strong>Thời gian tiếp nhận:</strong> {format_vietnam_time(submit_time)}</p>
                                <p>Phản ánh đã được gửi đến Công an. Cảm ơn bạn đã đóng góp!</p>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.markdown(f"""
                            <div class="warning-box">
                                <h4>⚠️ ĐÃ LƯU PHẢN ÁNH #{report_id:06d}</h4>
                                <p>{email_message}</p>
                                <p><strong>Thời gian lưu:</strong> {format_vietnam_time(submit_time)}</p>
                                <p>Vui lòng liên hệ trực tiếp Công an địa phương nếu cần thiết.</p>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        # Xóa kết quả giọng nói sau khi submit
                        if 'speech_results' in st.session_state:
                            st.session_state.speech_results = {}
                        
                        # Xóa các field
                        st.session_state[title_key] = ""
                        st.session_state[location_key] = ""
                        st.session_state[desc_key] = ""
                    else:
                        st.error("❌ Lỗi lưu phản ánh. Vui lòng thử lại!")
    
    # ========= TAB 2: DIỄN ĐÀN =========
    with tab2:
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.subheader("💬 Diễn đàn Hỏi đáp Pháp luật")
            st.info("⚠️ **Chỉ công an mới được bình luận và trả lời câu hỏi**")
        with col2:
            if st.button("📝 Đặt câu hỏi mới", type="primary", key="new_question_btn"):
                st.session_state.show_new_question = True
        
        # Nếu đang đặt câu hỏi mới
        if st.session_state.show_new_question:
            st.markdown("### 🎤 Tính năng giọng nói cho câu hỏi")
            
            with st.container():
                st.markdown('<div class="speech-section">', unsafe_allow_html=True)
                
                col_q1, col_q2 = st.columns(2)
                
                with col_q1:
                    st.markdown("**Tiêu đề câu hỏi bằng giọng nói:**")
                    st.components.v1.html(
                        create_speech_component("forum_title", "Nói tiêu đề câu hỏi"),
                        height=400
                    )
                
                with col_q2:
                    st.markdown("**Nội dung câu hỏi bằng giọng nói:**")
                    st.components.v1.html(
                        create_speech_component("forum_content", "Nói nội dung câu hỏi"),
                        height=400
                    )
                
                st.markdown('</div>', unsafe_allow_html=True)
        
        # Form đặt câu hỏi mới
        if st.session_state.show_new_question:
            with st.expander("✍️ ĐẶT CÂU HỎI MỚI", expanded=True):
                with st.form("new_question_form", clear_on_submit=True):
                    # Tiêu đề câu hỏi
                    q_title_key = "q_title_input"
                    if q_title_key not in st.session_state:
                        st.session_state[q_title_key] = ""
                    
                    if 'speech_results' in st.session_state and 'forum_title' in st.session_state.speech_results:
                        st.session_state[q_title_key] = st.session_state.speech_results['forum_title']
                    
                    q_title = st.text_input(
                        "Tiêu đề câu hỏi *",
                        placeholder="Nhập tiêu đề câu hỏi",
                        value=st.session_state[q_title_key],
                        key=q_title_key
                    )
                    
                    q_category = st.selectbox("Chủ đề *", 
                                            ["Hỏi đáp pháp luật", "Giải quyết mâu thuẫn", 
                                             "Tư vấn thủ tục", "An ninh trật tự", "Khác"])
                    
                    # Nội dung câu hỏi
                    q_content_key = "q_content_input"
                    if q_content_key not in st.session_state:
                        st.session_state[q_content_key] = ""
                    
                    if 'speech_results' in st.session_state and 'forum_content' in st.session_state.speech_results:
                        st.session_state[q_content_key] = st.session_state.speech_results['forum_content']
                    
                    q_content = st.text_area(
                        "Nội dung chi tiết *",
                        height=150,
                        placeholder="Mô tả rõ vấn đề bạn đang gặp phải...",
                        value=st.session_state[q_content_key],
                        key=q_content_key
                    )
                    
                    # Nút submit
                    col1, col2 = st.columns(2)
                    with col1:
                        submit_q = st.form_submit_button("📤 Đăng câu hỏi")
                    with col2:
                        cancel_q = st.form_submit_button("❌ Hủy")
                    
                    if submit_q:
                        if not q_title or not q_content:
                            st.error("Vui lòng điền tiêu đề và nội dung câu hỏi!")
                        else:
                            post_id, anon_id, error = save_forum_post(q_title, q_content, q_category)
                            if post_id:
                                current_time = get_vietnam_time()
                                st.success(f"✅ Câu hỏi đã đăng lúc {format_vietnam_time(current_time)}! (ID: {anon_id})")
                                st.session_state.show_new_question = False
                                # Xóa kết quả giọng nói
                                if 'speech_results' in st.session_state:
                                    st.session_state.speech_results = {}
                                st.session_state[q_title_key] = ""
                                st.session_state[q_content_key] = ""
                            else:
                                st.error(f"❌ {error}")
                    
                    if cancel_q:
                        st.session_state.show_new_question = False
                        # Xóa kết quả giọng nói
                        if 'speech_results' in st.session_state:
                            st.session_state.speech_results = {}
        
        # Bộ lọc
        st.markdown("---")
        col1, col2 = st.columns([2, 1])
        with col1:
            filter_category = st.selectbox("Lọc theo chủ đề", 
                                         ["Tất cả", "Hỏi đáp pháp luật", "Giải quyết mâu thuẫn", 
                                          "Tư vấn thủ tục", "An ninh trật tự"],
                                         key="filter_category")
        with col2:
            search_term = st.text_input("Tìm kiếm...", key="search_term")
        
        # Hiển thị danh sách câu hỏi
        df_posts = get_forum_posts(filter_category if filter_category != "Tất cả" else "Tất cả")
        
        if not df_posts.empty:
            if search_term:
                df_posts = df_posts[
                    df_posts['title'].str.contains(search_term, case=False) | 
                    df_posts['content'].str.contains(search_term, case=False)
                ]
            
            for idx, post in df_posts.iterrows():
                status_badge = "✅ Đã trả lời" if post['is_answered'] else "⏳ Chờ trả lời"
                badge_color = "#28a745" if post['is_answered'] else "#ffc107"
                
                with st.expander(f"**{post['title']}** - {post['formatted_date']} • {status_badge}", expanded=False):
                    st.markdown(f"""
                    <div style="margin-bottom: 1rem;">
                        <strong>👤 {post['anonymous_id']}</strong> • 
                        <span style="background-color: {badge_color}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.8em;">
                            {status_badge}
                        </span> • 
                        <strong>{post['category']}</strong>
                    </div>
                    <div style="background: #f8f9fa; padding: 1rem; border-radius: 5px; margin-bottom: 1rem;">
                        {post['content']}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    df_replies = get_forum_replies(post['id'])
                    st.markdown(f"**💬 Bình luận ({len(df_replies)})**")
                    
                    if not df_replies.empty:
                        for _, reply in df_replies.iterrows():
                            reply_class = "official-reply" if reply['is_official'] else "user-reply"
                            author_icon = "👮" if reply['is_official'] else "👤"
                            
                            st.markdown(f"""
                            <div class="{reply_class}" style="padding: 1rem; margin: 0.5rem 0; border-radius: 5px;">
                                <strong>{author_icon} {reply['display_name']}</strong> 
                                <small style="color: #666;">({reply['formatted_date']})</small>
                                <p style="margin-top: 0.5rem;">{reply['content']}</p>
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.info("Chưa có bình luận nào.")
                    
                    # Form bình luận cho công an
                    if st.session_state.police_user:
                        # Component giọng nói cho bình luận
                        with st.container():
                            st.markdown("### 🎤 Bình luận bằng giọng nói")
                            st.components.v1.html(
                                create_speech_component(f"reply_{post['id']}", "Nói bình luận của bạn"),
                                height=400
                            )
                        
                        reply_form_key = f"reply_form_{post['id']}"
                        with st.form(reply_form_key, clear_on_submit=True):
                            # Nội dung bình luận
                            reply_key = f"reply_input_{post['id']}"
                            if reply_key not in st.session_state:
                                st.session_state[reply_key] = ""
                            
                            # Tự động điền nếu có kết quả giọng nói
                            speech_key = f"reply_{post['id']}"
                            if ('speech_results' in st.session_state and 
                                speech_key in st.session_state.speech_results):
                                st.session_state[reply_key] = st.session_state.speech_results[speech_key]
                            
                            reply_content = st.text_area(
                                "Bình luận của bạn:",
                                height=80,
                                placeholder="Viết câu trả lời hoặc ý kiến...",
                                value=st.session_state[reply_key],
                                key=reply_key
                            )
                            
                            # Nút submit
                            submitted_reply = st.form_submit_button(
                                f"👮 Trả lời ({st.session_state.police_user['display_name']})",
                                use_container_width=True
                            )
                            
                            if submitted_reply:
                                if not reply_content.strip():
                                    st.error("Vui lòng nhập nội dung bình luận!")
                                else:
                                    result = save_forum_reply(
                                        post['id'], 
                                        reply_content, 
                                        is_police=True,
                                        police_info=st.session_state.police_user
                                    )
                                    
                                    if result[0]:
                                        st.success(f"✅ Đã gửi trả lời lúc {format_vietnam_time(get_vietnam_time())}!")
                                        # Xóa kết quả giọng nói
                                        if 'speech_results' in st.session_state:
                                            st.session_state.speech_results.pop(speech_key, None)
                                        st.session_state[reply_key] = ""
                                    else:
                                        st.error(f"❌ {result[1]}")
                    else:
                        st.warning("🔒 **Chỉ công an mới được bình luận và trả lời câu hỏi.**")
        else:
            st.info("📝 Chưa có câu hỏi nào. Hãy là người đầu tiên đặt câu hỏi!")
    
    # ========= TAB 3: THÔNG TIN =========
    with tab3:
        st.subheader("📖 Thông tin hệ thống")
        
        server_time = datetime.now()
        vietnam_time = get_vietnam_time()
        
        col_time1, col_time2 = st.columns(2)
        with col_time1:
            st.markdown(f"""
            ### 🕐 Thời gian hệ thống
            **Server (UTC):** {server_time.strftime('%H:%M:%S %d/%m/%Y')}
            """)
        with col_time2:
            st.markdown(f"""
            ### 🇻🇳 Giờ Việt Nam
            **Hiện tại:** {format_vietnam_time(vietnam_time, '%H:%M:%S %d/%m/%Y')}
            **Múi giờ:** UTC+7 (Asia/Ho_Chi_Minh)
            """)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            ### 📢 **Phản ánh An ninh:**
            1. **Điền thông tin** sự việc
            2. **Dùng nút giọng nói** nếu cần (trình duyệt sẽ hỏi popup cho phép micro)
            3. **Nhấn GỬI PHẢN ÁNH** để gửi
            
            ### 🎤 **Hướng dẫn sử dụng micro:**
            - **Chrome/Firefox:** Click vào 🔒 → cho phép Microphone
            - **Safari:** Safari → Cài đặt → Trang web → Microphone → Cho phép
            - **Đã từ chối?** Xóa cache và thử lại
            """)
        
        with col2:
            st.markdown("""
            ### 💬 **Diễn đàn:**
            1. **Đặt câu hỏi** ẩn danh
            2. **Chỉ công an** được trả lời
            3. **Dùng giọng nói** để đặt câu hỏi nhanh
            
            ### 🔒 **Bảo mật:**
            - **Không lưu IP** thực (chỉ hash)
            - **Không đăng ký** tài khoản
            - **Email** được mã hóa
            """)
        
        st.markdown("---")
        st.markdown("### 🎤 Hướng dẫn sử dụng tính năng giọng nói")
        
        st.info("""
        **Web Speech API hoạt động trên:**
        - ✅ **Chrome 25+** (tốt nhất)
        - ✅ **Edge 79+** (tốt)
        - ✅ **Safari 14.1+** (hỗ trợ cơ bản)
        - ✅ **Firefox** (cần bật flag)
        
        **Hỗ trợ tiếng Việt:**
        - Nhận diện tiếng Việt chính xác
        - Hỗ trợ đa ngôn ngữ
        - Không cần cài đặt thêm
        
        **Trên điện thoại:**
        - **iOS Safari:** Hỗ trợ đầy đủ
        - **Android Chrome:** Hoạt động tốt
        - **Micro tự động:** Sử dụng micro điện thoại
        """)
        
        # Thông tin về Web Speech API
        with st.expander("🔧 Thông tin kỹ thuật về Web Speech API"):
            st.markdown("""
            **Ưu điểm so với PyAudio:**
            1. **Không cần cài đặt** thư viện âm thanh
            2. **Hoạt động trên mọi hệ điều hành**
            3. **Tương thích mobile** hoàn hảo
            4. **Không lỗi biên dịch** portaudio
            
            **Cách hoạt động:**
            - Trình duyệt xử lý toàn bộ việc ghi âm
            - Google Cloud Speech-to-Text xử lý nhận diện
            - Kết quả trả về trực tiếp cho ứng dụng
            
            **Bảo mật:**
            - Âm thanh không gửi lên server của chúng tôi
            - Google xử lý và xóa sau khi nhận diện
            - Tuân thủ chính sách bảo mật trình duyệt
            """)

# ================ CHẠY ỨNG DỤNG ================
if __name__ == "__main__":
    main()
