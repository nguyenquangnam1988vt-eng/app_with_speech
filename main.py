"""
🏛️ HỆ THỐNG TIẾP NHẬN PHẢN ÁNH & TƯ VẤN CỘNG ĐỒNG
TÍCH HỢP GIỌNG NÓI - HỎI POPUP CHO PHÉP MICRO
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
SPEECH_AVAILABLE = False  # Mặc định là False
try:
    import speech_recognition as sr
    SPEECH_AVAILABLE = True
except ImportError:
    SPEECH_AVAILABLE = False
    st.warning("⚠️ Thư viện speech_recognition chưa được cài đặt. Vui lòng chạy: pip install SpeechRecognition")

# Import werkzeug thay bcrypt
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
    .speech-btn {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 10px 15px;
        border-radius: 8px;
        cursor: pointer;
        font-weight: bold;
        width: 100%;
        margin: 5px 0;
    }
    .speech-btn:hover {
        background: linear-gradient(135deg, #764ba2 0%, #667eea 100%);
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

# ================ HÀM NHẬN DIỆN GIỌNG NÓI ================
def speech_to_text(language='vi-VN', timeout=10):
    """Chuyển giọng nói thành văn bản"""
    if not SPEECH_AVAILABLE:
        return None, "Tính năng giọng nói chưa khả dụng"
    
    try:
        recognizer = sr.Recognizer()
        
        # Kiểm tra micro có sẵn không
        try:
            mic_list = sr.Microphone.list_microphone_names()
            if not mic_list:
                return None, "Không tìm thấy micro"
        except:
            pass
        
        with sr.Microphone() as source:
            # Điều chỉnh cho tiếng ồn môi trường
            st.info("🔊 Đang điều chỉnh micro... Hãy giữ im lặng trong 1 giây")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            
            st.info("🎤 Đang nghe... Hãy nói ngay bây giờ!")
            
            # Ghi âm với timeout
            try:
                audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=15)
            except sr.WaitTimeoutError:
                return None, "Hết thời gian chờ, vui lòng nói trong vòng 10 giây"
            
        # Nhận diện với Google Speech Recognition
        try:
            text = recognizer.recognize_google(audio, language=language)
            return text, None
        except sr.UnknownValueError:
            return None, "Không thể nhận diện giọng nói. Vui lòng thử lại"
        except sr.RequestError as e:
            return None, f"Lỗi kết nối: {str(e)}"
            
    except Exception as e:
        return None, f"Lỗi: {str(e)}"

# ================ GIAO DIỆN CHÍNH ================
def main():
    """Hàm chính của ứng dụng"""
    
    init_database()
    
    # Khởi tạo session state
    session_defaults = {
        'police_user': None,
        'show_new_question': False,
        'speech_target': None,
        'speech_result': None,
        'listening': False
    }
    
    for key, value in session_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    
    # Header với thời gian VN
    vietnam_now = get_vietnam_time()
    st.markdown(f"""
    <div class="main-header">
        <h1>🏛️ CỔNG TIẾP NHẬN PHẢN ÁNH CỘNG ĐỒNG</h1>
        <p>Phản ánh an ninh • Hỏi đáp pháp luật • Ẩn danh hoàn toàn • Giờ Việt Nam: {format_vietnam_time(vietnam_now)}</p>
        <p><small>⚠️ <strong>Chỉ công an mới được bình luận và trả lời câu hỏi</strong></small></p>
    </div>
    """, unsafe_allow_html=True)
    
    # ================ XỬ LÝ GIỌNG NÓI ================
    if st.session_state.get('speech_target'):
        target = st.session_state.speech_target
        
        # Hiển thị trạng thái đang nghe
        placeholder = st.empty()
        with placeholder.container():
            st.warning(f"🎤 Đang chờ phản hồi từ trình duyệt...")
            st.info("**Trình duyệt sẽ hiện popup hỏi cho phép micro.**")
            st.markdown("""
            **Nếu không thấy popup, hãy:**
            1. Kiểm tra biểu tượng 🔒 trên thanh URL
            2. Cho phép micro trong cài đặt trình duyệt
            3. Refresh trang và thử lại
            """)
        
        # Thực hiện nhận diện giọng nói
        try:
            text, error = speech_to_text()
            
            if text:
                st.session_state.speech_result = text
                st.success(f"✅ Đã nhận diện: **{text}**")
            elif error:
                st.error(f"❌ {error}")
                
        except Exception as e:
            st.error(f"Lỗi hệ thống: {str(e)}")
        
        # Reset target
        st.session_state.speech_target = None
        st.rerun()
    
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
        
        # Thông tin tính năng
        st.markdown("---")
        if SENDGRID_AVAILABLE:
            st.success("✅ SendGrid: Đã kết nối")
        else:
            st.warning("⚠️ SendGrid: Chưa cấu hình")
        
        if SPEECH_AVAILABLE:
            st.success("🎤 Nhận diện giọng nói: Sẵn sàng")
        else:
            st.warning("🎤 Nhận diện giọng nói: Chưa cài đặt")
        
        # Nút kiểm tra micro - SẼ HỎI POPUP
        st.markdown("### 🎤 Kiểm tra micro")
        if st.button("🎤 Kiểm tra Micro", key="test_micro_sidebar", use_container_width=True):
            if SPEECH_AVAILABLE:
                st.session_state.speech_target = "test"
                st.rerun()
            else:
                st.error("""
                **Tính năng giọng nói chưa khả dụng!**
                
                Cài đặt thư viện:
                ```bash
                pip install SpeechRecognition
                ```
                
                **Trên macOS:**
                ```bash
                brew install portaudio
                pip install pyaudio
                ```
                """)
    
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
        
        # ========== NÚT GIỌNG NÓI CHO FORM PHẢN ÁNH ==========
        st.markdown("### 🎤 Tính năng giọng nói")
        st.info("Nhấn nút bên dưới để sử dụng giọng nói. **Trình duyệt sẽ hiện popup hỏi cho phép micro.**")
        
        col_speech1, col_speech2, col_speech3 = st.columns(3)
        
        # Nút 1: Tiêu đề
        with col_speech1:
            if st.button("🎤 Tiêu đề bằng giọng nói", key="speech_title_btn", use_container_width=True):
                if SPEECH_AVAILABLE:
                    st.session_state.speech_target = "title"
                    st.rerun()
                else:
                    st.error("Tính năng giọng nói chưa khả dụng")
        
        # Nút 2: Địa điểm
        with col_speech2:
            if st.button("🎤 Địa điểm bằng giọng nói", key="speech_location_btn", use_container_width=True):
                if SPEECH_AVAILABLE:
                    st.session_state.speech_target = "location"
                    st.rerun()
                else:
                    st.error("Tính năng giọng nói chưa khả dụng")
        
        # Nút 3: Mô tả
        with col_speech3:
            if st.button("🎤 Mô tả bằng giọng nói", key="speech_desc_btn", use_container_width=True):
                if SPEECH_AVAILABLE:
                    st.session_state.speech_target = "description"
                    st.rerun()
                else:
                    st.error("Tính năng giọng nói chưa khả dụng")
        
        # FORM PHẢN ÁNH
        with st.form("security_report_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                # Tiêu đề - tự động điền từ giọng nói nếu có
                title_key = "report_title_input"
                if title_key not in st.session_state:
                    st.session_state[title_key] = ""
                
                if st.session_state.get('speech_target') == 'title' and st.session_state.get('speech_result'):
                    st.session_state[title_key] = st.session_state.speech_result
                
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
                
                if st.session_state.get('speech_target') == 'location' and st.session_state.get('speech_result'):
                    st.session_state[location_key] = st.session_state.speech_result
                
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
            
            if st.session_state.get('speech_target') == 'description' and st.session_state.get('speech_result'):
                st.session_state[desc_key] = st.session_state.speech_result
            
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
                        st.session_state.speech_result = None
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
            st.info("Nhấn nút để sử dụng giọng nói. **Trình duyệt sẽ hiện popup hỏi cho phép micro.**")
            
            col_q_speech1, col_q_speech2 = st.columns(2)
            with col_q_speech1:
                if st.button("🎤 Tiêu đề câu hỏi", key="speech_q_title_btn", use_container_width=True):
                    if SPEECH_AVAILABLE:
                        st.session_state.speech_target = "forum_title"
                        st.rerun()
                    else:
                        st.error("Tính năng giọng nói chưa khả dụng")
            with col_q_speech2:
                if st.button("🎤 Nội dung câu hỏi", key="speech_q_content_btn", use_container_width=True):
                    if SPEECH_AVAILABLE:
                        st.session_state.speech_target = "forum_content"
                        st.rerun()
                    else:
                        st.error("Tính năng giọng nói chưa khả dụng")
        
        # Form đặt câu hỏi mới
        if st.session_state.show_new_question:
            with st.expander("✍️ ĐẶT CÂU HỎI MỚI", expanded=True):
                with st.form("new_question_form", clear_on_submit=True):
                    # Tiêu đề câu hỏi
                    q_title_key = "q_title_input"
                    if q_title_key not in st.session_state:
                        st.session_state[q_title_key] = ""
                    
                    if st.session_state.get('speech_target') == 'forum_title' and st.session_state.get('speech_result'):
                        st.session_state[q_title_key] = st.session_state.speech_result
                    
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
                    
                    if st.session_state.get('speech_target') == 'forum_content' and st.session_state.get('speech_result'):
                        st.session_state[q_content_key] = st.session_state.speech_result
                    
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
                                st.session_state.speech_result = None
                                st.session_state[q_title_key] = ""
                                st.session_state[q_content_key] = ""
                            else:
                                st.error(f"❌ {error}")
                    
                    if cancel_q:
                        st.session_state.show_new_question = False
                        # Xóa kết quả giọng nói
                        st.session_state.speech_result = None
        
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
                        # Nút giọng nói cho bình luận
                        col_reply_speech, _ = st.columns([1, 3])
                        with col_reply_speech:
                            if st.button(f"🎤 Bình luận bằng giọng nói", 
                                       key=f"speech_reply_btn_{post['id']}",
                                       use_container_width=True):
                                if SPEECH_AVAILABLE:
                                    st.session_state.speech_target = f"reply_{post['id']}"
                                    st.rerun()
                                else:
                                    st.error("Tính năng giọng nói chưa khả dụng")
                        
                        reply_form_key = f"reply_form_{post['id']}"
                        with st.form(reply_form_key, clear_on_submit=True):
                            # Nội dung bình luận
                            reply_key = f"reply_input_{post['id']}"
                            if reply_key not in st.session_state:
                                st.session_state[reply_key] = ""
                            
                            # Tự động điền nếu có kết quả giọng nói cho bài này
                            if (st.session_state.get('speech_target') == f"reply_{post['id']}" and 
                                st.session_state.get('speech_result')):
                                st.session_state[reply_key] = st.session_state.speech_result
                            
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
                                        st.session_state.speech_result = None
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
            - **Chrome/Firefox:** Click vào biểu tượng 🔒 → cho phép Microphone
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
        **Khi nhấn nút giọng nói lần đầu:**
        1. **Trình duyệt sẽ hiện popup** hỏi: "example.com muốn sử dụng micro của bạn"
        2. **Chọn "Cho phép"** để kích hoạt tính năng
        3. **Nói rõ ràng** vào micro khi thấy thông báo "Đang nghe..."
        
        **Nếu không thấy popup:**
        - **Chrome:** Click vào 🔒 trên thanh URL → Site settings → Microphone → Allow
        - **Safari:** Safari → Preferences → Websites → Microphone → Cho phép
        - **Firefox:** Click vào biểu tượng camera/micro trên thanh URL → Allow
        
        **Lỗi thường gặp:**
        - **"Micro không khả dụng":** Kiểm tra micro có được kết nối không
        - **"Không thể nhận diện":** Nói to hơn, rõ ràng hơn
        - **"Hết thời gian chờ":** Nói trong vòng 10 giây
        """)

# ================ CHẠY ỨNG DỤNG ================
if __name__ == "__main__":
    main()
