"""
🏛️ HỆ THỐNG TIẾP NHẬN PHẢN ÁNH & TƯ VẤN CỘNG ĐỒNG
Tích hợp đầy đủ: SendGrid Email, Database, Diễn đàn
ĐÃ SỬA HOÀN TOÀN: Fix RecursionError và các lỗi khác
"""

import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import hashlib
import secrets
import time
import os

# THAY ĐỔI QUAN TRỌNG: Import werkzeug thay bcrypt
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
</style>
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
        
        # Tạo hash từ thời gian để tracking
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
    
    # 1. Lưu vào database
    report_id = save_to_database(title, description, location, incident_time)
    
    if not report_id:
        return None, False, "Lỗi lưu database"
    
    # 2. Chuẩn bị dữ liệu email
    report_data = {
        'title': title,
        'description': description,
        'location': location,
        'incident_time': incident_time,
        'report_id': report_id
    }
    
    # 3. Gửi email qua SendGrid (nếu có)
    if SENDGRID_AVAILABLE:
        email_success, email_message = send_email_report(report_data)
    else:
        # Fallback nếu không có email service
        email_success = False
        email_message = "Tính năng email chưa được cấu hình"
    
    # 4. Cập nhật trạng thái email trong database
    if email_success:
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('UPDATE security_reports SET email_sent = 1 WHERE id = ?', (report_id,))
            conn.commit()
            conn.close()
        except:
            pass
    
    # 5. Hiển thị kết quả cho người dùng
    return report_id, email_success, email_message

# ================ HÀM DIỄN ĐÀN ================
def save_forum_post(title, content, category):
    """Lưu bài đăng diễn đàn"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        anonymous_id = f"NgườiDân_{secrets.token_hex(4)}"
        
        # Thêm bài đăng mới
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
    """Lưu bình luận diễn đàn - CHỈ CÔNG AN ĐƯỢC PHÉP"""
    try:
        if not is_police or not police_info:
            return None, "Chỉ công an mới được bình luận và trả lời câu hỏi."
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        author_type = "police"
        author_id = police_info['badge_number']
        display_name = police_info['display_name']
        is_official = 1
        
        # Thêm bình luận mới
        c.execute('''
            INSERT INTO forum_replies (post_id, content, author_type, author_id, display_name, is_official)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (post_id, content, author_type, author_id, display_name, is_official))
        
        # Cập nhật trạng thái
        c.execute('UPDATE forum_posts SET is_answered = 1 WHERE id = ?', (post_id,))
        
        # Đếm lại tổng số reply
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
    """Lấy danh sách bài đăng"""
    try:
        conn = sqlite3.connect(DB_PATH)
        
        query = '''
            SELECT id, title, content, category, anonymous_id, 
                   created_at, reply_count, is_answered,
                   strftime('%d/%m/%Y %H:%M', created_at) as formatted_date
            FROM forum_posts
        '''
        
        params = []
        if category_filter != "Tất cả":
            query += " WHERE category = ?"
            params.append(category_filter)
        
        query += " ORDER BY created_at DESC LIMIT 50"
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    except:
        return pd.DataFrame()

def get_forum_replies(post_id):
    """Lấy bình luận của bài đăng"""
    try:
        conn = sqlite3.connect(DB_PATH)
        query = '''
            SELECT id, content, author_type, display_name, is_official,
                   strftime('%d/%m/%Y %H:%M', created_at) as formatted_date
            FROM forum_replies
            WHERE post_id = ?
            ORDER BY created_at ASC
        '''
        df = pd.read_sql_query(query, conn, params=(post_id,))
        conn.close()
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
    
    # Khởi tạo database
    init_database()
    
    # Khởi tạo session state
    if 'police_user' not in st.session_state:
        st.session_state.police_user = None
    if 'show_new_question' not in st.session_state:
        st.session_state.show_new_question = False
    if 'just_submitted' not in st.session_state:
        st.session_state.just_submitted = False
    if 'last_action' not in st.session_state:
        st.session_state.last_action = None
    
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>🏛️ CỔNG TIẾP NHẬN PHẢN ÁNH CỘNG ĐỒNG</h1>
        <p>Phản ánh an ninh • Hỏi đáp pháp luật • Ẩn danh hoàn toàn</p>
        <p><small>⚠️ <strong>Chỉ công an mới được bình luận và trả lời câu hỏi</strong></small></p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar - Đăng nhập công an
    with st.sidebar:
        st.markdown("### 🔐 Đăng nhập Công an")
        
        if not st.session_state.police_user:
            # Form đăng nhập
            badge = st.text_input("Số hiệu", key="login_badge")
            password = st.text_input("Mật khẩu", type="password", key="login_password")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Đăng nhập", type="primary", use_container_width=True):
                    user = police_login(badge, password)
                    if user:
                        st.session_state.police_user = user
                        st.session_state.last_action = "login"
                        st.success(f"Xin chào {user['display_name']}!")
                    else:
                        st.error("Sai số hiệu hoặc mật khẩu!")
            with col2:
                st.button("Đăng xuất", disabled=True, use_container_width=True)
        else:
            # Thông tin đã đăng nhập
            user = st.session_state.police_user
            st.success(f"👮 **{user['display_name']}**")
            st.info(f"Số hiệu: `{user['badge_number']}`")
            st.info(f"Quyền: `{user['role']}`")
            
            if st.button("🚪 Đăng xuất", use_container_width=True):
                st.session_state.police_user = None
                st.session_state.last_action = "logout"
                st.success("Đã đăng xuất!")
        
        # Thông tin hệ thống
        st.markdown("---")
        st.markdown("### 📊 Thống kê nhanh")
        
        try:
            conn = sqlite3.connect(DB_PATH)
            today = datetime.now().strftime('%Y-%m-%d')
            
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
        
        # Thông tin SendGrid
        st.markdown("---")
        if SENDGRID_AVAILABLE:
            st.success("✅ SendGrid: Đã kết nối")
        else:
            st.warning("⚠️ SendGrid: Chưa cấu hình")
    
    # Main tabs
    tab1, tab2, tab3 = st.tabs(["📢 PHẢN ÁNH AN NINH", "💬 DIỄN ĐÀN", "ℹ️ HƯỚNG DẪN"])
    
    # ========= TAB 1: PHẢN ÁNH AN NINH =========
    with tab1:
        st.subheader("Biểu mẫu Phản ánh An ninh Trật tự")
        
        if not SENDGRID_AVAILABLE:
            st.warning("""
            ⚠️ **TÍNH NĂNG EMAIL CHƯA SẴN SÀNG**
            
            Phản ánh sẽ chỉ được lưu vào database.
            Để gửi email tự động, cần cấu hình SendGrid trong file `email_service.py`.
            """)
        
        with st.form("security_report_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                title = st.text_input("Tiêu đề phản ánh *", 
                                    placeholder="Ví dụ: Mất trộm xe máy tại...")
                location = st.text_input("Địa điểm", 
                                       placeholder="Số nhà, đường, phường/xã...")
            
            with col2:
                incident_time = st.text_input("Thời gian xảy ra", 
                                            placeholder="VD: Khoảng 20h tối qua")
            
            description = st.text_area("Mô tả chi tiết *", 
                                     height=150,
                                     placeholder="Mô tả đầy đủ sự việc, đối tượng, phương tiện, thiệt hại...")
            
            # SỬA: ĐÚNG CÚ PHÁP cho form_submit_button
            submitted = st.form_submit_button("🚨 GỬI PHẢN ÁNH", use_container_width=True)
            
            # Xử lý khi form được submit
            if submitted:
                if not title or not description:
                    st.error("⚠️ Vui lòng điền tiêu đề và mô tả sự việc!")
                else:
                    # Xử lý phản ánh
                    report_id, email_success, email_message = handle_security_report(
                        title, description, location, incident_time
                    )
                    
                    if report_id:
                        if email_success:
                            st.markdown(f"""
                            <div class="success-box">
                                <h4>✅ ĐÃ TIẾP NHẬN PHẢN ÁNH #{report_id:06d}</h4>
                                <p>{email_message}</p>
                                <p>Phản ánh đã được gửi đến Công an. Cảm ơn bạn đã đóng góp!</p>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.markdown(f"""
                            <div class="warning-box">
                                <h4>⚠️ ĐÃ LƯU PHẢN ÁNH #{report_id:06d}</h4>
                                <p>{email_message}</p>
                                <p>Vui lòng liên hệ trực tiếp Công an địa phương nếu cần thiết.</p>
                            </div>
                            """, unsafe_allow_html=True)
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
        
        # Form đặt câu hỏi mới
        if st.session_state.show_new_question:
            with st.expander("✍️ ĐẶT CÂU HỎI MỚI", expanded=True):
                # SỬA: Dùng form đúng cách
                form_key = "new_question_form"
                with st.form(form_key, clear_on_submit=True):
                    q_title = st.text_input("Tiêu đề câu hỏi *")
                    q_category = st.selectbox("Chủ đề *", 
                                            ["Hỏi đáp pháp luật", "Giải quyết mâu thuẫn", 
                                             "Tư vấn thủ tục", "An ninh trật tự", "Khác"])
                    q_content = st.text_area("Nội dung chi tiết *", height=150,
                                           placeholder="Mô tả rõ vấn đề bạn đang gặp phải...")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        submit_q = st.form_submit_button("📤 Đăng câu hỏi")
                    with col2:
                        cancel_q = st.form_submit_button("❌ Hủy")
                    
                    # Xử lý khi form được submit
                    if st.session_state.get('form_submitted') != form_key:
                        if submit_q:
                            if not q_title or not q_content:
                                st.error("Vui lòng điền tiêu đề và nội dung câu hỏi!")
                            else:
                                post_id, anon_id, error = save_forum_post(q_title, q_content, q_category)
                                if post_id:
                                    st.success(f"✅ Câu hỏi đã đăng! (ID: {anon_id})")
                                    st.session_state.show_new_question = False
                                    st.session_state.form_submitted = form_key
                                    # KHÔNG dùng st.rerun() ở đây
                                else:
                                    st.error(f"❌ {error}")
                        
                        elif cancel_q:
                            st.session_state.show_new_question = False
                            st.session_state.form_submitted = form_key
        
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
            # Áp dụng tìm kiếm
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
                    
                    # Hiển thị bình luận
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
                    
                    # Form bình luận - CHỈ HIỂN THỊ CHO CÔNG AN
                    if st.session_state.police_user:
                        reply_form_key = f"reply_form_{post['id']}"
                        with st.form(reply_form_key, clear_on_submit=True):
                            reply_content = st.text_area("Bình luận của bạn:", 
                                                       height=80,
                                                       placeholder="Viết câu trả lời hoặc ý kiến...")
                            
                            submitted_reply = st.form_submit_button(
                                f"👮 Trả lời ({st.session_state.police_user['display_name']})",
                                use_container_width=True
                            )
                            
                            if submitted_reply and st.session_state.get('form_submitted') != reply_form_key:
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
                                        st.success("✅ Đã gửi trả lời chính thức!")
                                        st.session_state.form_submitted = reply_form_key
                                        # KHÔNG dùng st.rerun()
                                    else:
                                        st.error(f"❌ {result[1]}")
                    else:
                        st.warning("🔒 **Chỉ công an mới được bình luận và trả lời câu hỏi.**")
        else:
            st.info("📝 Chưa có câu hỏi nào. Hãy là người đầu tiên đặt câu hỏi!")
    
    # ========= TAB 3: HƯỚNG DẪN =========
    with tab3:
        st.subheader("📖 Hướng dẫn sử dụng")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            ### 📢 **Phản ánh An ninh:**
            1. **Điền thông tin** sự việc
            2. **Nhấn GỬI PHẢN ÁNH**
            3. Hệ thống tự động **gửi đến Công an**
            
            ### 💬 **Diễn đàn:**
            1. **Đặt câu hỏi** ẩn danh
            2. **Chỉ công an trả lời** chính thức
            3. **Người dân chỉ xem**, không bình luận
            """)
        
        with col2:
            st.markdown("""
            ### 🔒 **Bảo mật & Quyền hạn:**
            - **Người dân:** Chỉ đặt câu hỏi, không bình luận
            - **Công an:** Trả lời câu hỏi chính thức
            - **Không lưu** thông tin cá nhân
            - **ID ngẫu nhiên** mỗi lần
            """)
        
        # Thông tin liên hệ
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("""
            ### 📞 Liên hệ khẩn cấp
            - **Hotline Công an:** 113
            - **Trực ban địa phương**
            - **Tình huống nguy hiểm:** Gọi ngay 113
            """)
        with col2:
            st.markdown("""
            ### ⏰ Thời gian tiếp nhận
            - **Phản ánh:** 24/7
            - **Trả lời diễn đàn:** Trong giờ hành chính
            - **Xử lý sự việc:** Theo quy trình
            """)
        with col3:
            st.markdown("""
            ### 📱 Quyền hạn
            - **Người dân:** Chỉ đọc & đặt câu hỏi
            - **Công an:** Đăng nhập để trả lời
            - **Admin:** Quản lý toàn hệ thống
            """)

# Chạy ứng dụng
if __name__ == "__main__":
    main()
