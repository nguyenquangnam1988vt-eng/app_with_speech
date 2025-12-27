"""
HỆ THỐNG TIẾP NHẬN PHẢN ÁNH & TƯ VẤN CỘNG ĐỒNG
TÍCH HỢP ĐẦY ĐỦ: Voice-to-Text, Database, Email, Authentication
"""
import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import hashlib
import secrets
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import time
import bcrypt
import json

# ================ VOICE-TO-TEXT INTEGRATION ================
VOICE_ENABLED = False
try:
    import speech_recognition as sr
    import pyaudio
    VOICE_ENABLED = True
except ImportError:
    st.sidebar.warning("⚠️ Cài `pip install SpeechRecognition pyaudio` để dùng tính năng nói")

# ================ CONFIGURATION ================
load_dotenv()

st.set_page_config(
    page_title="Cổng Tiếp Nhận Cộng Đồng",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ================ CSS ================
st.markdown("""
<style>
    .main-header {
        text-align: center;
        color: #1E3A8A;
        padding: 1rem;
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
        color: white;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .voice-panel {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 15px;
        margin-bottom: 1rem;
    }
    .mic-btn {
        background: #4CAF50;
        color: white;
        border: none;
        padding: 12px 25px;
        border-radius: 50px;
        font-size: 16px;
        cursor: pointer;
        transition: 0.3s;
        display: inline-block;
        margin: 5px;
    }
    .mic-btn:hover { background: #45a049; transform: scale(1.05); }
    .mic-btn-recording { 
        background: #f44336 !important; 
        animation: pulse 1.5s infinite;
    }
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.1); }
        100% { transform: scale(1); }
    }
    .forum-question { border-left: 5px solid #28a745; padding: 1rem; margin: 1rem 0; background: #f8f9fa; }
    .forum-answer { border-left: 5px solid #007bff; padding: 1rem; margin: 1rem 0; background: #e8f4fd; }
    .police-badge { background: #dc3545; color: white; padding: 0.2rem 0.8rem; border-radius: 15px; font-size: 0.8rem; }
</style>
""", unsafe_allow_html=True)

# ================ DATABASE FUNCTIONS ================
def init_db():
    """Khởi tạo database"""
    conn = sqlite3.connect('community_app.db')
    c = conn.cursor()
    
    # Security reports
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
    
    # Forum posts
    c.execute('''
        CREATE TABLE IF NOT EXISTS forum_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT,
            anonymous_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reply_count INTEGER DEFAULT 0,
            is_answered BOOLEAN DEFAULT 0
        )
    ''')
    
    # Forum replies
    c.execute('''
        CREATE TABLE IF NOT EXISTS forum_replies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            content TEXT NOT NULL,
            author_type TEXT,
            author_id TEXT,
            display_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_official BOOLEAN DEFAULT 0
        )
    ''')
    
    # Police users
    c.execute('''
        CREATE TABLE IF NOT EXISTS police_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            badge_number TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'officer'
        )
    ''')
    
    # Tạo admin mặc định
    c.execute("SELECT COUNT(*) FROM police_users WHERE badge_number = 'CA001'")
    if c.fetchone()[0] == 0:
        hashed_pw = bcrypt.hashpw("congan123".encode(), bcrypt.gensalt()).decode()
        c.execute('INSERT INTO police_users (badge_number, display_name, password_hash, role) VALUES (?, ?, ?, ?)',
                 ('CA001', 'Admin Công An', hashed_pw, 'admin'))
    
    conn.commit()
    conn.close()

# ================ VOICE-TO-TEXT FUNCTIONS ================
class VoiceRecorder:
    """Class xử lý ghi âm và chuyển giọng nói thành văn bản"""
    
    def __init__(self):
        self.recognizer = sr.Recognizer() if VOICE_ENABLED else None
        self.is_recording = False
        self.last_result = ""
        
    def start_recording(self, duration=10):
        """Bắt đầu ghi âm"""
        if not VOICE_ENABLED:
            return False, "Chưa cài thư viện giọng nói"
        
        try:
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                audio = self.recognizer.listen(source, timeout=duration)
                
                # Chuyển thành văn bản
                text = self.recognizer.recognize_google(audio, language='vi-VN')
                self.last_result = text
                return True, text
                
        except sr.WaitTimeoutError:
            return False, "Không có âm thanh"
        except sr.UnknownValueError:
            return False, "Không nhận diện được giọng nói"
        except Exception as e:
            return False, f"Lỗi: {str(e)}"
    
    def quick_record(self):
        """Ghi âm nhanh 5 giây"""
        return self.start_recording(5)

def show_voice_input(key_name, default_text=""):
    """Hiển thị giao diện nhập bằng giọng nói"""
    
    if not VOICE_ENABLED:
        st.warning("⚠️ Cài `pip install SpeechRecognition pyaudio` để dùng tính năng nói")
        return default_text
    
    # Khởi tạo recorder trong session state
    if 'voice_recorder' not in st.session_state:
        st.session_state.voice_recorder = VoiceRecorder()
    
    recorder = st.session_state.voice_recorder
    
    # Panel giọng nói
    st.markdown('<div class="voice-panel">', unsafe_allow_html=True)
    st.markdown("### 🎤 NHẬP BẰNG GIỌNG NÓI")
    st.markdown("Nhấn nút rồi nói vào micro")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Nút điều khiển
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🎤 Nói 5 giây", use_container_width=True, key=f"voice_5s_{key_name}"):
            with st.spinner("Đang nghe... Hãy nói"):
                success, result = recorder.quick_record()
                if success:
                    st.session_state[key_name] = result
                    st.success("✅ Đã nhận diện!")
                else:
                    st.error(f"Lỗi: {result}")
    
    with col2:
        if st.button("🎤 Nói 10 giây", use_container_width=True, key=f"voice_10s_{key_name}"):
            with st.spinner("Đang nghe 10 giây..."):
                success, result = recorder.start_recording(10)
                if success:
                    st.session_state[key_name] = result
                    st.success("✅ Đã nhận diện!")
                else:
                    st.error(f"Lỗi: {result}")
    
    with col3:
        if st.button("🗑️ Xóa", use_container_width=True, key=f"clear_{key_name}"):
            st.session_state[key_name] = ""
            st.rerun()
    
    # Hiển thị kết quả
    if recorder.last_result:
        st.info(f"**Kết quả nhận diện:** {recorder.last_result}")
    
    # Text area để chỉnh sửa
    text_content = st.text_area(
        "Chỉnh sửa nội dung:",
        value=st.session_state.get(key_name, default_text),
        key=key_name,
        height=150,
        placeholder="Nội dung sẽ tự động điền từ giọng nói..."
    )
    
    return text_content

# ================ EMAIL FUNCTIONS ================
def send_email_via_smtp(subject, body):
    """Gửi email qua SMTP"""
    try:
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", 587))
        email_address = os.getenv("EMAIL_ADDRESS")
        email_password = os.getenv("EMAIL_PASSWORD")
        to_email = os.getenv("TO_EMAIL", email_address)
        
        msg = MIMEMultipart()
        msg['From'] = email_address
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(email_address, email_password)
            server.send_message(msg)
        
        return True, "Email đã gửi!"
    except Exception as e:
        return False, f"Lỗi gửi email: {str(e)}"

# ================ AUTHENTICATION ================
def police_login(badge_number, password):
    """Đăng nhập công an"""
    conn = sqlite3.connect('community_app.db')
    c = conn.cursor()
    
    c.execute('SELECT badge_number, display_name, password_hash, role FROM police_users WHERE badge_number = ?', 
             (badge_number,))
    user = c.fetchone()
    conn.close()
    
    if user and bcrypt.checkpw(password.encode(), user[2].encode()):
        return {
            'badge_number': user[0],
            'display_name': user[1],
            'role': user[3]
        }
    return None

# ================ DATA OPERATIONS ================
def save_security_report(title, description, location="", incident_time=""):
    """Lưu phản ánh an ninh"""
    conn = sqlite3.connect('community_app.db')
    c = conn.cursor()
    
    ip_hash = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
    
    c.execute('''
        INSERT INTO security_reports (title, description, location, incident_time, ip_hash)
        VALUES (?, ?, ?, ?, ?)
    ''', (title, description, location, incident_time, ip_hash))
    
    conn.commit()
    report_id = c.lastrowid
    conn.close()
    
    # Gửi email
    email_body = f"""
    PHẢN ÁNH AN NINH MỚI #{report_id}
    
    Tiêu đề: {title}
    Nội dung: {description}
    Địa điểm: {location}
    Thời gian: {incident_time}
    
    Thời gian tiếp nhận: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
    """
    
    success, message = send_email_via_smtp(f"🚨 PHẢN ÁNH: {title[:50]}", email_body)
    
    return report_id, success, message

def save_forum_post(title, content, category):
    """Lưu bài đăng diễn đàn"""
    conn = sqlite3.connect('community_app.db')
    c = conn.cursor()
    
    anonymous_id = f"NgườiDân_{secrets.token_hex(4)}"
    
    c.execute('''
        INSERT INTO forum_posts (title, content, category, anonymous_id)
        VALUES (?, ?, ?, ?)
    ''', (title, content, category, anonymous_id))
    
    conn.commit()
    post_id = c.lastrowid
    conn.close()
    
    return post_id, anonymous_id

def save_forum_reply(post_id, content, is_police=False, police_info=None):
    """Lưu bình luận"""
    conn = sqlite3.connect('community_app.db')
    c = conn.cursor()
    
    if is_police and police_info:
        author_type = "police"
        author_id = police_info['badge_number']
        display_name = police_info['display_name']
        is_official = 1
    else:
        author_type = "anonymous"
        author_id = f"Khách_{secrets.token_hex(4)}"
        display_name = author_id
        is_official = 0
    
    c.execute('''
        INSERT INTO forum_replies (post_id, content, author_type, author_id, display_name, is_official)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (post_id, content, author_type, author_id, display_name, is_official))
    
    # Cập nhật số reply
    c.execute('UPDATE forum_posts SET reply_count = reply_count + 1 WHERE id = ?', (post_id,))
    
    conn.commit()
    conn.close()
    
    return author_id

def get_forum_posts():
    """Lấy danh sách bài đăng"""
    conn = sqlite3.connect('community_app.db')
    query = '''
        SELECT id, title, content, category, anonymous_id, 
               created_at, reply_count, is_answered,
               strftime('%d/%m/%Y %H:%M', created_at) as formatted_date
        FROM forum_posts
        ORDER BY created_at DESC
        LIMIT 50
    '''
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def get_forum_replies(post_id):
    """Lấy bình luận của bài đăng"""
    conn = sqlite3.connect('community_app.db')
    query = '''
        SELECT content, author_type, display_name, is_official,
               strftime('%d/%m/%Y %H:%M', created_at) as formatted_date
        FROM forum_replies
        WHERE post_id = ?
        ORDER BY created_at ASC
    '''
    df = pd.read_sql_query(query, conn, params=(post_id,))
    conn.close()
    return df

# ================ MAIN APP ================
def main():
    """Ứng dụng chính"""
    
    # Khởi tạo database
    init_db()
    
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>🏛️ CỔNG TIẾP NHẬN PHẢN ÁNH CỘNG ĐỒNG</h1>
        <p>Phản ánh an ninh • Hỏi đáp pháp luật • Ẩn danh hoàn toàn</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar - Đăng nhập công an
    with st.sidebar:
        st.markdown("### 🔐 Đăng nhập Công an")
        
        if 'police_user' not in st.session_state:
            st.session_state.police_user = None
        
        if not st.session_state.police_user:
            # Form đăng nhập
            badge = st.text_input("Số hiệu")
            password = st.text_input("Mật khẩu", type="password")
            
            if st.button("Đăng nhập", type="primary", use_container_width=True):
                user = police_login(badge, password)
                if user:
                    st.session_state.police_user = user
                    st.success(f"Xin chào {user['display_name']}!")
                    st.rerun()
                else:
                    st.error("Sai số hiệu hoặc mật khẩu!")
        else:
            # Thông tin đã đăng nhập
            user = st.session_state.police_user
            st.success(f"👮 {user['display_name']}")
            st.info(f"Số hiệu: {user['badge_number']}")
            
            if st.button("Đăng xuất", use_container_width=True):
                st.session_state.police_user = None
                st.rerun()
    
    # Main tabs
    tab1, tab2, tab3 = st.tabs(["📢 PHẢN ÁNH AN NINH", "💬 DIỄN ĐÀN", "ℹ️ HƯỚNG DẪN"])
    
    # ========= TAB 1: PHẢN ÁNH AN NINH =========
    with tab1:
        st.subheader("Biểu mẫu Phản ánh An ninh Trật tự")
        st.info("Thông tin sẽ được gửi NGAY đến email Công an. Bảo mật 100%.")
        
        with st.form("security_report"):
            col1, col2 = st.columns(2)
            
            with col1:
                title = st.text_input("Tiêu đề *", placeholder="Ví dụ: Mất trộm xe máy...")
                location = st.text_input("Địa điểm", placeholder="Số nhà, đường...")
            
            with col2:
                incident_time = st.text_input("Thời gian", placeholder="VD: 20h tối qua")
            
            # Chọn phương thức nhập nội dung
            input_method = st.radio(
                "Cách nhập mô tả:",
                ["⌨️ Gõ phím", "🎤 Nói (chuyển thành chữ)"],
                horizontal=True
            )
            
            if input_method == "🎤 Nói (chuyển thành chữ)":
                description = show_voice_input("security_desc", "")
            else:
                description = st.text_area(
                    "Mô tả chi tiết *",
                    height=150,
                    placeholder="Mô tả sự việc, đối tượng, thiệt hại..."
                )
            
            submitted = st.form_submit_button("🚨 GỬI PHẢN ÁNH", type="primary", use_container_width=True)
            
            if submitted:
                if not title or not description:
                    st.error("Vui lòng điền tiêu đề và mô tả!")
                else:
                    report_id, email_success, email_msg = save_security_report(
                        title, description, location, incident_time
                    )
                    
                    if email_success:
                        st.success(f"""
                        ✅ **ĐÃ TIẾP NHẬN PHẢN ÁNH #{report_id}**
                        
                        Phản ánh đã được gửi đến Công an qua email.
                        Cảm ơn bạn đã đóng góp cho an ninh cộng đồng!
                        """)
                    else:
                        st.warning(f"""
                        ⚠️ **ĐÃ LƯU NHƯNG LỖI EMAIL**
                        
                        Mã phản ánh: #{report_id}
                        Lỗi: {email_msg}
                        Vui lòng liên hệ trực tiếp 113 nếu cần thiết.
                        """)
    
    # ========= TAB 2: DIỄN ĐÀN =========
    with tab2:
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.subheader("💬 Diễn đàn Hỏi đáp Pháp luật")
        with col2:
            if st.button("📝 Đặt câu hỏi mới", type="primary"):
                st.session_state.show_new_question = True
        
        # Form đặt câu hỏi mới
        if st.session_state.get('show_new_question', False):
            with st.expander("✍️ ĐẶT CÂU HỎI MỚI", expanded=True):
                with st.form("new_question"):
                    q_title = st.text_input("Tiêu đề câu hỏi *")
                    q_category = st.selectbox("Chủ đề", ["Pháp luật", "Mâu thuẫn", "Thủ tục", "Khác"])
                    
                    # Voice input cho câu hỏi
                    use_voice = st.checkbox("Dùng giọng nói để đặt câu hỏi")
                    
                    if use_voice:
                        q_content = show_voice_input("forum_question", "")
                    else:
                        q_content = st.text_area("Nội dung câu hỏi *", height=150)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        submit_q = st.form_submit_button("📤 Đăng câu hỏi", type="primary")
                    with col2:
                        cancel_q = st.form_submit_button("❌ Hủy")
                    
                    if submit_q and q_title and q_content:
                        post_id, anon_id = save_forum_post(q_title, q_content, q_category)
                        st.success(f"✅ Câu hỏi đã đăng! (Bạn là: {anon_id})")
                        st.session_state.show_new_question = False
                        st.rerun()
                    
                    if cancel_q:
                        st.session_state.show_new_question = False
                        st.rerun()
        
        # Hiển thị danh sách câu hỏi
        st.markdown("---")
        st.subheader("📚 Câu hỏi gần đây")
        
        df_posts = get_forum_posts()
        
        if not df_posts.empty:
            for _, post in df_posts.iterrows():
                with st.expander(f"❓ {post['title']} - {post['formatted_date']}", expanded=False):
                    st.write(f"**Người hỏi:** {post['anonymous_id']}")
                    st.write(f"**Chủ đề:** {post['category']}")
                    st.write(f"**Nội dung:** {post['content']}")
                    
                    # Hiển thị bình luận
                    df_replies = get_forum_replies(post['id'])
                    
                    st.markdown(f"**💬 Bình luận ({len(df_replies)})**")
                    
                    if not df_replies.empty:
                        for _, reply in df_replies.iterrows():
                            if reply['is_official']:
                                st.markdown(f"""
                                <div style='background: #e8f4fd; padding: 1rem; margin: 0.5rem 0; border-radius: 5px; border-left: 3px solid #007bff;'>
                                    <strong>👮 {reply['display_name']}</strong> 
                                    <small style='color: #666;'>({reply['formatted_date']})</small>
                                    <p>{reply['content']}</p>
                                </div>
                                """, unsafe_allow_html=True)
                            else:
                                st.markdown(f"""
                                <div style='background: #f8f9fa; padding: 1rem; margin: 0.5rem 0; border-radius: 5px;'>
                                    <strong>👤 {reply['display_name']}</strong> 
                                    <small style='color: #666;'>({reply['formatted_date']})</small>
                                    <p>{reply['content']}</p>
                                </div>
                                """, unsafe_allow_html=True)
                    
                    # Form bình luận
                    with st.form(key=f"reply_form_{post['id']}"):
                        reply_content = st.text_area("Bình luận của bạn", height=80)
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.session_state.police_user:
                                submit_label = "👮 Trả lời (Công an)"
                            else:
                                submit_label = "💬 Gửi bình luận"
                            
                            submit_reply = st.form_submit_button(submit_label)
                        
                        with col2:
                            use_voice_reply = st.checkbox("Nói thay vì gõ", key=f"voice_reply_{post['id']}")
                        
                        if use_voice_reply:
                            reply_content = show_voice_input(f"reply_voice_{post['id']}", reply_content)
                        
                        if submit_reply and reply_content:
                            if st.session_state.police_user:
                                author_id = save_forum_reply(
                                    post['id'], 
                                    reply_content, 
                                    is_police=True,
                                    police_info=st.session_state.police_user
                                )
                            else:
                                author_id = save_forum_reply(post['id'], reply_content)
                            
                            st.success(f"✅ Đã gửi bình luận!")
                            st.rerun()
        else:
            st.info("Chưa có câu hỏi nào. Hãy là người đầu tiên!")
    
    # ========= TAB 3: HƯỚNG DẪN =========
    with tab3:
        st.subheader("📖 Hướng dẫn sử dụng")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            ### 📢 **Phản ánh An ninh:**
            1. Điền thông tin sự việc
            2. Có thể **NÓI** mô tả thay vì gõ
            3. Nhấn GỬI → Email đến Công an ngay
            
            ### 💬 **Diễn đàn:**
            1. Đặt câu hỏi ẩn danh
            2. Công an trả lời chính thức
            3. Mọi người cùng thảo luận
            """)
        
        with col2:
            st.markdown("""
            ### 🎤 **Nhập bằng giọng nói:**
            - Nhấn nút 🎤
            - Nói rõ vào micro
            - Tự động thành chữ
            - Chỉnh sửa nếu cần
            
            ### 🔒 **Bảo mật:**
            - Không lưu thông tin cá nhân
            - ID ngẫu nhiên mỗi lần
            - Không cần đăng ký
            """)
        
        # Thống kê
        st.markdown("---")
        st.subheader("📊 Thống kê hệ thống")
        
        conn = sqlite3.connect('community_app.db')
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_reports = pd.read_sql_query("SELECT COUNT(*) FROM security_reports", conn)
            st.metric("Phản ánh ANTT", int(total_reports.iloc[0,0]))
        
        with col2:
            total_posts = pd.read_sql_query("SELECT COUNT(*) FROM forum_posts", conn)
            st.metric("Câu hỏi", int(total_posts.iloc[0,0]))
        
        with col3:
            total_replies = pd.read_sql_query("SELECT COUNT(*) FROM forum_replies", conn)
            st.metric("Bình luận", int(total_replies.iloc[0,0]))
        
        with col4:
            today = datetime.now().strftime('%Y-%m-%d')
            today_reports = pd.read_sql_query(
                "SELECT COUNT(*) FROM security_reports WHERE DATE(created_at) = ?", 
                conn, params=(today,)
            )
            st.metric("Hôm nay", int(today_reports.iloc[0,0]))
        
        conn.close()

# Chạy ứng dụng
if __name__ == "__main__":
    main()
