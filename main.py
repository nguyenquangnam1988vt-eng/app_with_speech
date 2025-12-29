"""
🏛️ HỆ THỐNG TIẾP NHẬN PHẢN ÁNH & TƯ VẤN CỘNG ĐỒNG
ĐƠN GIẢN - DỄ DÙNG CHO NGƯỜI LỚN TUỔI
"""

import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import hashlib
import secrets
import time
import os

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

# ================ IMPORT THƯ VIỆN ================
try:
    from streamlit_mic_recorder import mic_recorder
    MIC_RECORDER_AVAILABLE = True
except ImportError:
    MIC_RECORDER_AVAILABLE = False
    st.warning("⚠️ Thư viện streamlit-mic-recorder chưa cài đặt. Vui lòng chạy: pip install streamlit-mic-recorder")

SPEECH_AVAILABLE = False
try:
    import speech_recognition as sr
    SPEECH_AVAILABLE = True
except ImportError:
    SPEECH_AVAILABLE = False

from werkzeug.security import generate_password_hash, check_password_hash

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
    .mic-recorder-container {
        background: linear-gradient(135deg, #f0f8ff 0%, #e6f3ff 100%);
        padding: 15px;
        border-radius: 10px;
        border: 2px solid #3B82F6;
        margin: 10px 0;
    }
    .form-clear-button {
        margin-top: 10px;
    }
    .large-text {
        font-size: 1.2rem !important;
    }
    .simple-form {
        background: white;
        padding: 2rem;
        border-radius: 10px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .section-title {
        color: #1E3A8A;
        font-size: 1.5rem;
        margin-bottom: 1.5rem;
        border-bottom: 3px solid #3B82F6;
        padding-bottom: 0.5rem;
    }
    .mic-button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 15px 25px;
        border-radius: 10px;
        font-size: 1.2rem;
        font-weight: bold;
        cursor: pointer;
        width: 100%;
        margin: 10px 0;
        transition: all 0.3s;
    }
    .mic-button:hover {
        transform: scale(1.02);
        box-shadow: 0 5px 15px rgba(0,0,0,0.2);
    }
    .record-status {
        text-align: center;
        padding: 10px;
        margin: 10px 0;
        border-radius: 5px;
        font-weight: bold;
    }
    .recording {
        background: #ffebee;
        color: #c62828;
        border: 2px solid #c62828;
    }
    .stopped {
        background: #e8f5e8;
        color: #2e7d32;
        border: 2px solid #2e7d32;
    }
    .audio-container {
        background: #f8f9fa;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# ================ HÀM XỬ LÝ AUDIO ĐƠN GIẢN ================
def process_audio_to_text(audio_bytes, language='vi-VN'):
    """Xử lý audio bytes thành văn bản (tự động chuyển)"""
    if not SPEECH_AVAILABLE:
        return None, "Thư viện speech_recognition chưa cài đặt"
    
    try:
        recognizer = sr.Recognizer()
        
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
            tmp_file.write(audio_bytes)
            tmp_path = tmp_file.name
        
        try:
            with sr.AudioFile(tmp_path) as source:
                audio = recognizer.record(source)
            
            text = recognizer.recognize_google(audio, language=language)
            
            os.unlink(tmp_path)
            return text, None
            
        except sr.UnknownValueError:
            os.unlink(tmp_path)
            return None, "Không thể nhận diện giọng nói"
        except sr.RequestError as e:
            os.unlink(tmp_path)
            return None, f"Lỗi kết nối: {str(e)}"
            
    except Exception as e:
        return None, f"Lỗi xử lý audio: {str(e)}"

def create_simple_mic_recorder(label="Ghi âm", key_suffix="default"):
    """Tạo component ghi âm đơn giản - tự động chuyển thành văn bản"""
    if not MIC_RECORDER_AVAILABLE:
        st.warning("⚠️ Thư viện streamlit-mic-recorder chưa khả dụng")
        return None, None
    
    with st.container():
        st.markdown(f"<div class='mic-recorder-container'>", unsafe_allow_html=True)
        st.markdown(f"<h3>🎤 {label}</h3>", unsafe_allow_html=True)
        
        # Trạng thái ghi âm
        status_placeholder = st.empty()
        
        # Nút ghi âm
        audio = mic_recorder(
            start_prompt=f"🎤 BẮT ĐẦU GHI ÂM",
            stop_prompt="⏹️ DỪNG GHI ÂM",
            key=f"simple_recorder_{key_suffix}",
            format="wav",
            just_once=True
        )
        
        result_text = None
        
        if audio:
            # Hiển thị trạng thái đã ghi âm xong
            status_placeholder.markdown(
                "<div class='record-status stopped'>✅ Đã ghi âm xong. Đang chuyển thành văn bản...</div>", 
                unsafe_allow_html=True
            )
            
            # Tự động chuyển thành văn bản
            with st.spinner("Đang chuyển giọng nói thành văn bản..."):
                text, error = process_audio_to_text(audio['bytes'])
                if text:
                    result_text = text
                    st.success(f"✅ **Đã chuyển thành văn bản thành công!**")
                    # Hiển thị kết quả
                    st.markdown(f"**Kết quả:**")
                    st.info(text)
                elif error:
                    st.error(f"❌ {error}")
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    return result_text, audio

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
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS forum_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT DEFAULT 'Câu hỏi từ người dân',
                content TEXT NOT NULL,
                category TEXT DEFAULT 'Hỏi đáp pháp luật',
                anonymous_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reply_count INTEGER DEFAULT 0,
                is_answered BOOLEAN DEFAULT 0
            )
        ''')
        
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
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS police_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                badge_number TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'officer'
            )
        ''')
        
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
def save_forum_post(content, category):
    """Lưu bài đăng diễn đàn (không cần tiêu đề)"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        anonymous_id = f"NgườiDân_{secrets.token_hex(4)}"
        
        c.execute('''
            INSERT INTO forum_posts (title, content, category, anonymous_id)
            VALUES (?, ?, ?, ?)
        ''', ('Câu hỏi từ người dân', content, category, anonymous_id))
        
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
    
    # Khởi tạo session state
    if 'police_user' not in st.session_state:
        st.session_state.police_user = None
    if 'show_new_question' not in st.session_state:
        st.session_state.show_new_question = False
    if 'form_submitted' not in st.session_state:
        st.session_state.form_submitted = False
    if 'form_data' not in st.session_state:
        st.session_state.form_data = {
            'description': '',
            'location': '',
            'incident_time': ''
        }
    if 'forum_form_data' not in st.session_state:
        st.session_state.forum_form_data = {
            'content': ''
        }
    if 'speech_texts' not in st.session_state:
        st.session_state.speech_texts = {}
    
    # Header với thời gian VN
    vietnam_now = get_vietnam_time()
    st.markdown(f"""
    <div class="main-header">
        <h1>🏛️ CỔNG TIẾP NHẬN PHẢN ÁNH CỘNG ĐỒNG</h1>
        <p>Phản ánh an ninh • Hỏi đáp pháp luật • Ẩn danh hoàn toàn • Giờ Việt Nam: {format_vietnam_time(vietnam_now)}</p>
        <p><small>⚠️ <strong>Chỉ công an mới được bình luận và trả lời câu hỏi</strong></small></p>
        <p><small>🎤 <strong>Ghi âm đơn giản - Tự động chuyển thành chữ</strong></small></p>
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
    
    # ========= TAB 1: PHẢN ÁNH AN NINH (ĐƠN GIẢN) =========
    with tab1:
        st.markdown('<div class="section-title">📝 PHẢN ÁNH AN NINH TRẬT TỰ</div>', unsafe_allow_html=True)
        
        # Hiển thị thời gian hiện tại
        now_vn = get_vietnam_time()
        st.info(f"**Thời gian hiện tại:** {format_vietnam_time(now_vn, '%H:%M %d/%m/%Y')}")
        
        if not SENDGRID_AVAILABLE:
            st.warning("⚠️ Tính năng email chưa sẵn sàng")
        
        # Xử lý form submitted
        if st.session_state.form_submitted:
            st.markdown(f"""
            <div class="success-box">
                <h4>✅ ĐÃ TIẾP NHẬN PHẢN ÁNH</h4>
                <p>Phản ánh của bạn đã được gửi đến Công an thành công!</p>
                <p><strong>Thời gian tiếp nhận:</strong> {format_vietnam_time(now_vn)}</p>
                <p>Cảm ơn bạn đã đóng góp cho an ninh cộng đồng!</p>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("📝 Gửi phản ánh mới", type="primary", use_container_width=True):
                st.session_state.form_submitted = False
                st.session_state.form_data = {
                    'description': '',
                    'location': '',
                    'incident_time': ''
                }
                st.session_state.speech_texts = {}
                st.rerun()
            return
        
        # FORM PHẢN ÁNH ĐƠN GIẢN
        with st.form("security_report_form", clear_on_submit=False):
            st.markdown('<div class="simple-form">', unsafe_allow_html=True)
            
            # Hướng dẫn đơn giản
            st.markdown("""
            ### 🎯 **CÁCH GỬI PHẢN ÁNH:**
            1. **Nhập hoặc ghi âm** mô tả sự việc
            2. **Chọn địa điểm** (nếu biết)
            3. **Chọn thời gian** (nếu nhớ)
            4. **Nhấn nút GỬI PHẢN ÁNH**
            """)
            
            # Phần 1: MÔ TẢ SỰ VIỆC (BẮT BUỘC)
            st.markdown("---")
            st.markdown("### 1. MÔ TẢ SỰ VIỆC *")
            
            col1, col2 = st.columns([2, 1])
            with col1:
                st.markdown("**Nhập mô tả bằng văn bản:**")
                description = st.text_area(
                    "Mô tả chi tiết sự việc:",
                    height=120,
                    placeholder="Ví dụ: Tôi thấy có 2 thanh niên lạ mặt đang cố mở khóa xe máy trước cửa nhà số 5...",
                    value=st.session_state.form_data['description'],
                    key="report_description_input"
                )
                st.session_state.form_data['description'] = description
            
            with col2:
                st.markdown("**Hoặc ghi âm (nói xong tự chuyển thành chữ):**")
                if MIC_RECORDER_AVAILABLE:
                    desc_audio_text, _ = create_simple_mic_recorder("Ghi âm mô tả", "description")
                    if desc_audio_text:
                        st.session_state.form_data['description'] = desc_audio_text
                        st.session_state.speech_texts['description'] = desc_audio_text
                        st.rerun()
                else:
                    st.warning("Chưa hỗ trợ ghi âm")
            
            # Phần 2: THÔNG TIN BỔ SUNG (KHÔNG BẮT BUỘC)
            st.markdown("---")
            st.markdown("### 2. THÔNG TIN BỔ SUNG (Nếu có)")
            
            col_loc, col_time = st.columns(2)
            
            with col_loc:
                st.markdown("**Địa điểm xảy ra:**")
                location = st.text_input(
                    "Địa điểm (không bắt buộc)",
                    placeholder="Ví dụ: Trước nhà số 5, đường ABC",
                    value=st.session_state.form_data['location'],
                    key="report_location_input"
                )
                st.session_state.form_data['location'] = location
            
            with col_time:
                st.markdown("**Thời gian xảy ra:**")
                incident_time = st.text_input(
                    "Thời gian (không bắt buộc)",
                    placeholder=f"Ví dụ: {format_vietnam_time(now_vn, '%H:%M')} ngày {format_vietnam_time(now_vn, '%d/%m')}",
                    value=st.session_state.form_data['incident_time'],
                    key="report_time_input"
                )
                st.session_state.form_data['incident_time'] = incident_time
            
            st.markdown("</div>", unsafe_allow_html=True)
            
            # NÚT HÀNH ĐỘNG - LỚN VÀ RÕ RÀNG
            st.markdown("---")
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                submit_button = st.form_submit_button(
                    "🚨 **GỬI PHẢN ÁNH**",
                    use_container_width=True,
                    type="primary"
                )
            
            with col2:
                clear_button = st.form_submit_button(
                    "🗑️ **XÓA NỘI DUNG**",
                    use_container_width=True
                )
            
            with col3:
                cancel_button = st.form_submit_button(
                    "↩️ **HỦY**",
                    use_container_width=True
                )
            
            if clear_button:
                st.session_state.form_data = {
                    'description': '',
                    'location': '',
                    'incident_time': ''
                }
                st.session_state.speech_texts = {}
                st.rerun()
            
            if cancel_button:
                st.session_state.form_submitted = False
                st.rerun()
            
            if submit_button:
                if not description:
                    st.error("⚠️ Vui lòng mô tả sự việc!")
                else:
                    with st.spinner("Đang xử lý phản ánh..."):
                        submit_time = get_vietnam_time()
                        
                        # Tạo tiêu đề tự động từ mô tả
                        title = f"Phản ánh: {description[:50]}..." if len(description) > 50 else f"Phản ánh: {description}"
                        
                        report_id, email_success, email_message = handle_security_report(
                            title, description, location, incident_time
                        )
                        
                        if report_id:
                            # Đánh dấu đã submit
                            st.session_state.form_submitted = True
                            st.rerun()
                        else:
                            st.error("❌ Lỗi lưu phản ánh. Vui lòng thử lại!")
    
    # ========= TAB 2: DIỄN ĐÀN (ĐƠN GIẢN) =========
    with tab2:
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.markdown('<div class="section-title">💬 HỎI ĐÁP PHÁP LUẬT</div>', unsafe_allow_html=True)
            st.info("⚠️ **Chỉ công an mới được bình luận và trả lời câu hỏi**")
        with col2:
            if st.button("📝 Đặt câu hỏi mới", type="primary", key="new_question_btn", use_container_width=True):
                st.session_state.show_new_question = not st.session_state.show_new_question
        
        # Form đặt câu hỏi mới ĐƠN GIẢN
        if st.session_state.show_new_question:
            with st.expander("✍️ ĐẶT CÂU HỎI MỚI", expanded=True):
                with st.form("new_question_form"):
                    st.markdown("### 🎯 **CÁCH ĐẶT CÂU HỎI:**")
                    st.markdown("1. **Chọn chủ đề** câu hỏi")
                    st.markdown("2. **Nhập hoặc ghi âm** nội dung câu hỏi")
                    st.markdown("3. **Nhấn ĐĂNG CÂU HỎI**")
                    
                    # Chủ đề câu hỏi
                    q_category = st.selectbox(
                        "**Chọn chủ đề câu hỏi:**",
                        ["Hỏi đáp pháp luật", "Giải quyết mâu thuẫn", 
                         "Tư vấn thủ tục", "An ninh trật tự", "Khác"],
                        key="q_category_select"
                    )
                    
                    st.markdown("---")
                    st.markdown("### **NỘI DUNG CÂU HỎI:**")
                    
                    col_text, col_mic = st.columns([2, 1])
                    
                    with col_text:
                        q_content = st.text_area(
                            "**Nhập câu hỏi bằng văn bản:**",
                            height=120,
                            placeholder="Ví dụ: Tôi muốn hỏi về thủ tục đăng ký tạm trú cho người thân từ tỉnh khác đến...",
                            value=st.session_state.forum_form_data.get('content', ''),
                            key="q_content_input"
                        )
                        st.session_state.forum_form_data['content'] = q_content
                    
                    with col_mic:
                        st.markdown("**Hoặc ghi âm câu hỏi:**")
                        if MIC_RECORDER_AVAILABLE:
                            forum_audio_text, _ = create_simple_mic_recorder("Ghi âm câu hỏi", "forum_content")
                            if forum_audio_text:
                                st.session_state.forum_form_data['content'] = forum_audio_text
                                st.session_state.speech_texts['forum_content'] = forum_audio_text
                                st.rerun()
                        else:
                            st.warning("Chưa hỗ trợ ghi âm")
                    
                    # Nút hành động
                    col_submit, col_clear, col_cancel = st.columns(3)
                    
                    with col_submit:
                        submit_q = st.form_submit_button("📤 **ĐĂNG CÂU HỎI**", use_container_width=True, type="primary")
                    
                    with col_clear:
                        clear_q = st.form_submit_button("🗑️ **XÓA**", use_container_width=True)
                    
                    with col_cancel:
                        cancel_q = st.form_submit_button("❌ **HỦY**", use_container_width=True)
                    
                    if clear_q:
                        st.session_state.forum_form_data = {'content': ''}
                        if 'speech_texts' in st.session_state and 'forum_content' in st.session_state.speech_texts:
                            del st.session_state.speech_texts['forum_content']
                        st.rerun()
                    
                    if submit_q:
                        if not q_content:
                            st.error("Vui lòng nhập nội dung câu hỏi!")
                        else:
                            post_id, anon_id, error = save_forum_post(q_content, q_category)
                            if post_id:
                                current_time = get_vietnam_time()
                                st.success(f"✅ Câu hỏi đã đăng lúc {format_vietnam_time(current_time)}! (ID: {anon_id})")
                                st.session_state.show_new_question = False
                                st.session_state.forum_form_data = {'content': ''}
                                if 'speech_texts' in st.session_state and 'forum_content' in st.session_state.speech_texts:
                                    del st.session_state.speech_texts['forum_content']
                                st.rerun()
                            else:
                                st.error(f"❌ {error}")
                    
                    if cancel_q:
                        st.session_state.show_new_question = False
                        st.rerun()
        
        # Bộ lọc và tìm kiếm
        st.markdown("---")
        col1, col2 = st.columns([2, 1])
        with col1:
            filter_category = st.selectbox(
                "Lọc theo chủ đề", 
                ["Tất cả", "Hỏi đáp pháp luật", "Giải quyết mâu thuẫn", 
                 "Tư vấn thủ tục", "An ninh trật tự"],
                key="filter_category"
            )
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
                
                with st.expander(f"**{post['category']}** - {post['formatted_date']} • {status_badge}", expanded=False):
                    st.markdown(f"""
                    <div style="margin-bottom: 1rem;">
                        <strong>👤 {post['anonymous_id']}</strong> • 
                        <span style="background-color: {badge_color}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.8em;">
                            {status_badge}
                        </span>
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
                        with st.form(f"reply_form_{post['id']}"):
                            st.markdown("### **BÌNH LUẬN/TRẢ LỜI:**")
                            
                            col_reply_text, col_reply_mic = st.columns([2, 1])
                            
                            with col_reply_text:
                                reply_content = st.text_area(
                                    "Nhập bình luận:",
                                    height=80,
                                    placeholder="Viết câu trả lời hoặc ý kiến...",
                                    key=f"reply_input_{post['id']}"
                                )
                            
                            with col_reply_mic:
                                st.markdown("**Hoặc ghi âm:**")
                                if MIC_RECORDER_AVAILABLE:
                                    reply_audio_text, _ = create_simple_mic_recorder("Ghi âm trả lời", f"reply_{post['id']}")
                                    if reply_audio_text:
                                        # Cập nhật text area với nội dung ghi âm
                                        reply_content = reply_audio_text
                                        st.rerun()
                            
                            col_submit, col_clear = st.columns([3, 1])
                            with col_submit:
                                submitted_reply = st.form_submit_button(
                                    f"👮 **TRẢ LỜI** ({st.session_state.police_user['display_name']})",
                                    use_container_width=True,
                                    type="primary"
                                )
                            with col_clear:
                                clear_reply = st.form_submit_button("🗑️ **XÓA**", use_container_width=True)
                            
                            if clear_reply:
                                st.rerun()
                            
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
                                        st.rerun()
                                    else:
                                        st.error(f"❌ {result[1]}")
                    else:
                        st.warning("🔒 **Chỉ công an mới được bình luận và trả lời câu hỏi.**")
        else:
            st.info("📝 Chưa có câu hỏi nào. Hãy là người đầu tiên đặt câu hỏi!")
    
    # ========= TAB 3: THÔNG TIN =========
    with tab3:
        st.markdown('<div class="section-title">📖 HƯỚNG DẪN SỬ DỤNG</div>', unsafe_allow_html=True)
        
        server_time = datetime.now()
        vietnam_time = get_vietnam_time()
        
        st.info(f"""
        ### 🕐 **THỜI GIAN HIỆN TẠI:**
        - **Giờ Việt Nam:** {format_vietnam_time(vietnam_time, '%H:%M:%S %d/%m/%Y')}
        - **Múi giờ:** UTC+7 (Asia/Ho_Chi_Minh)
        """)
        
        # Hướng dẫn bằng hình ảnh đơn giản
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            ### 📢 **GỬI PHẢN ÁNH AN NINH:**
            
            **Bước 1:** Mô tả sự việc
            - Nhập chữ **HOẶC** nhấn 🎤 ghi âm
            - Nói rõ ràng, chậm rãi
            - Tự động chuyển thành chữ
            
            **Bước 2:** Thông tin bổ sung (nếu có)
            - Địa điểm xảy ra
            - Thời gian xảy ra
            
            **Bước 3:** Nhấn **GỬI PHẢN ÁNH**
            - Hệ thống tự động tiếp nhận
            - Báo cáo đến Công an
            """)
        
        with col2:
            st.markdown("""
            ### 💬 **ĐẶT CÂU HỎI PHÁP LUẬT:**
            
            **Bước 1:** Chọn chủ đề
            - Hỏi đáp pháp luật
            - Giải quyết mâu thuẫn
            - Tư vấn thủ tục
            - An ninh trật tự
            
            **Bước 2:** Nội dung câu hỏi
            - Nhập chữ **HOẶC** nhấn 🎤 ghi âm
            - Nói rõ câu hỏi của bạn
            - Tự động chuyển thành chữ
            
            **Bước 3:** Nhấn **ĐĂNG CÂU HỎI**
            - Ẩn danh hoàn toàn
            - Chỉ Công an được trả lời
            """)
        
        st.markdown("---")
        st.markdown("""
        ### 🎤 **HƯỚNG DẪN GHI ÂM:**
        1. **Nhấn nút 🎤 BẮT ĐẦU GHI ÂM**
        2. **Nói** nội dung của bạn
        3. **Nhấn ⏹️ DỪNG GHI ÂM** khi xong
        4. **Hệ thống tự động** chuyển thành chữ
        
        ### ⚠️ **LƯU Ý QUAN TRỌNG:**
        - **Không cần đăng ký** tài khoản
        - **Ẩn danh** hoàn toàn
        - **Chỉ Công an** được trả lời câu hỏi
        - Phản ánh được **báo cáo ngay** đến Công an
        """)

# ================ CHẠY ỨNG DỤNG ================
if __name__ == "__main__":
    main()
