"""
🏛️ HỆ THỐNG TIẾP NHẬN PHẢN ÁNH & TƯ VẤN CỘNG ĐỒNG
Tích hợp đầy đủ: SendGrid Email, Database, Diễn đàn
ĐÃ SỬA: Chỉ công an mới được bình luận & fix lỗi lặp bình luận
"""

import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import hashlib
import secrets
import time
import json
import os

# THAY ĐỔI QUAN TRỌNG: Import werkzeug thay bcrypt
from werkzeug.security import generate_password_hash, check_password_hash

# Import SendGrid email service
try:
    from email_service import send_email_report
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False
    st.sidebar.warning("⚠️ Chưa có file email_service.py")

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
    .comment-disabled {
        opacity: 0.6;
        background: #f0f0f0 !important;
    }
</style>
""", unsafe_allow_html=True)

# ================ KHỞI TẠO DATABASE ================
def init_database():
    """Khởi tạo tất cả bảng database"""
    conn = sqlite3.connect('community_app.db')
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
            is_answered BOOLEAN DEFAULT 0,
            UNIQUE(title, anonymous_id, created_at)  # THÊM CONSTRAINT để tránh trùng lặp
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
            FOREIGN KEY (post_id) REFERENCES forum_posts(id),
            UNIQUE(post_id, author_id, content, created_at)  # THÊM CONSTRAINT để tránh trùng lặp
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
    
    # Tạo admin mặc định nếu chưa có - SỬA: DÙNG werkzeug
    c.execute("SELECT COUNT(*) FROM police_users WHERE badge_number = 'CA001'")
    if c.fetchone()[0] == 0:
        # THAY ĐỔI QUAN TRỌNG: dùng generate_password_hash thay bcrypt
        password_hash = generate_password_hash("congan123", method='pbkdf2:sha256')
        c.execute('''
            INSERT INTO police_users (badge_number, display_name, password_hash, role)
            VALUES (?, ?, ?, ?)
        ''', ('CA001', 'Admin Công An', password_hash, 'admin'))
    
    conn.commit()
    conn.close()

# ================ HÀM XỬ LÝ PHẢN ÁNH ================
def save_to_database(title, description, location="", incident_time=""):
    """Lưu phản ánh vào database"""
    conn = sqlite3.connect('community_app.db')
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

def handle_security_report(title, description, location, incident_time):
    """Xử lý phản ánh và gửi email"""
    
    # 1. Lưu vào database
    report_id = save_to_database(title, description, location, incident_time)
    
    # 2. Chuẩn bị dữliệu email
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
        conn = sqlite3.connect('community_app.db')
        c = conn.cursor()
        c.execute('UPDATE security_reports SET email_sent = 1 WHERE id = ?', (report_id,))
        conn.commit()
        conn.close()
    
    # 5. Hiển thị kết quả cho người dùng
    return report_id, email_success, email_message

# ================ HÀM DIỄN ĐÀN ================
def save_forum_post(title, content, category):
    """Lưu bài đăng diễn đàn với kiểm tra trùng lặp"""
    conn = sqlite3.connect('community_app.db')
    c = conn.cursor()
    
    anonymous_id = f"NgườiDân_{secrets.token_hex(4)}"
    
    try:
        # Kiểm tra xem có bài đăng trùng trong 10 phút không
        time_threshold = (datetime.now().timestamp() - 600)  # 10 phút trước
        c.execute('''
            SELECT COUNT(*) FROM forum_posts 
            WHERE title = ? AND anonymous_id LIKE ? 
            AND created_at > datetime(?, 'unixepoch')
        ''', (title, 'NgườiDân_%', time_threshold))
        
        duplicate_count = c.fetchone()[0]
        
        if duplicate_count > 0:
            conn.close()
            return None, "Bài đăng trùng lặp. Vui lòng đợi 10 phút trước khi đăng câu hỏi mới."
        
        # Thêm bài đăng mới
        c.execute('''
            INSERT INTO forum_posts (title, content, category, anonymous_id)
            VALUES (?, ?, ?, ?)
        ''', (title, content, category, anonymous_id))
        
        conn.commit()
        post_id = c.lastrowid
        conn.close()
        
        return post_id, anonymous_id
        
    except sqlite3.IntegrityError:
        conn.rollback()
        conn.close()
        return None, "Bài đăng đã tồn tại trong hệ thống."
    except Exception as e:
        conn.rollback()
        conn.close()
        return None, f"Lỗi hệ thống: {str(e)}"

def save_forum_reply(post_id, content, is_police=False, police_info=None):
    """Lưu bình luận diễn đàn với kiểm tra trùng lặp"""
    conn = sqlite3.connect('community_app.db')
    c = conn.cursor()
    
    try:
        # Kiểm tra xem bình luận đã tồn tại chưa (trong 5 phút gần nhất)
        time_threshold = (datetime.now().timestamp() - 300)  # 5 phút trước
        
        if is_police and police_info:
            author_type = "police"
            author_id = police_info['badge_number']
            display_name = police_info['display_name']
            is_official = 1
            
            # Kiểm tra trùng lặp cho công an
            c.execute('''
                SELECT COUNT(*) FROM forum_replies 
                WHERE post_id = ? AND author_id = ? AND content = ?
                AND created_at > datetime(?, 'unixepoch')
            ''', (post_id, author_id, content, time_threshold))
        else:
            # Người dân bình thường KHÔNG được phép bình luận
            conn.close()
            return None, "Chỉ công an mới được bình luận và trả lời câu hỏi."
        
        duplicate_count = c.fetchone()[0]
        
        if duplicate_count > 0:
            conn.close()
            return None, "Bình luận trùng lặp. Vui lòng không gửi cùng nội dung nhiều lần."
        
        # Thêm bình luận mới
        c.execute('''
            INSERT INTO forum_replies (post_id, content, author_type, author_id, display_name, is_official)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (post_id, content, author_type, author_id, display_name, is_official))
        
        # Cập nhật số reply - CHỈ CẬP NHẬT 1 LẦN
        c.execute('''
            UPDATE forum_posts 
            SET reply_count = (
                SELECT COUNT(*) FROM forum_replies WHERE post_id = ?
            ),
            is_answered = 1
            WHERE id = ?
        ''', (post_id, post_id))
        
        conn.commit()
        reply_id = c.lastrowid
        conn.close()
        
        return reply_id, "Bình luận đã được gửi thành công!"
        
    except sqlite3.IntegrityError:
        conn.rollback()
        conn.close()
        return None, "Bình luận đã tồn tại trong hệ thống."
    except Exception as e:
        conn.rollback()
        conn.close()
        return None, f"Lỗi hệ thống: {str(e)}"

def get_forum_posts(category_filter="Tất cả"):
    """Lấy danh sách bài đăng"""
    conn = sqlite3.connect('community_app.db')
    
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

def get_forum_replies(post_id):
    """Lấy bình luận của bài đăng"""
    conn = sqlite3.connect('community_app.db')
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

# ================ ĐĂNG NHẬP CÔNG AN - SỬA ================
def police_login(badge_number, password):
    """Đăng nhập công an - SỬA: DÙNG werkzeug"""
    try:
        conn = sqlite3.connect('community_app.db')
        c = conn.cursor()
        
        c.execute('''
            SELECT badge_number, display_name, password_hash, role 
            FROM police_users 
            WHERE badge_number = ?
        ''', (badge_number,))
        
        user = c.fetchone()
        conn.close()
        
        if user and check_password_hash(user[2], password):  # SỬA: check_password_hash
            return {
                'badge_number': user[0],
                'display_name': user[1],
                'role': user[3]
            }
        return None
    except Exception as e:
        st.error(f"Lỗi đăng nhập: {str(e)}")
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
    if 'replied_posts' not in st.session_state:
        st.session_state.replied_posts = set()  # Lưu các post đã reply trong session
    
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
                        st.success(f"Xin chào {user['display_name']}!")
                        st.rerun()
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
                st.session_state.replied_posts = set()
                st.rerun()
        
        # Thông tin hệ thống
        st.markdown("---")
        st.markdown("### 📊 Thống kê nhanh")
        
        conn = sqlite3.connect('community_app.db')
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
            
            submitted = st.form_submit_button("🚨 GỬI PHẢN ÁNH", type="primary", use_container_width=True)
            
            if submitted:
                if not title or not description:
                    st.error("⚠️ Vui lòng điền tiêu đề và mô tả sự việc!")
                else:
                    # Xử lý phản ánh
                    report_id, email_success, email_message = handle_security_report(
                        title, description, location, incident_time
                    )
                    
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
    
    # ========= TAB 2: DIỄN ĐÀN =========
    with tab2:
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.subheader("💬 Diễn đàn Hỏi đáp Pháp luật")
            st.info("⚠️ **Chỉ công an mới được bình luận và trả lời câu hỏi**")
        with col2:
            if st.button("📝 Đặt câu hỏi mới", type="primary", key="new_question_btn"):
                st.session_state.show_new_question = True
                st.rerun()
        
        # Form đặt câu hỏi mới
        if st.session_state.show_new_question:
            with st.expander("✍️ ĐẶT CÂU HỎI MỚI", expanded=True):
                with st.form("new_question_form", clear_on_submit=True):
                    q_title = st.text_input("Tiêu đề câu hỏi *", key="q_title")
                    q_category = st.selectbox("Chủ đề *", 
                                            ["Hỏi đáp pháp luật", "Giải quyết mâu thuẫn", 
                                             "Tư vấn thủ tục", "An ninh trật tự", "Khác"],
                                            key="q_category")
                    q_content = st.text_area("Nội dung chi tiết *", height=150,
                                           placeholder="Mô tả rõ vấn đề bạn đang gặp phải...",
                                           key="q_content")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        submit_q = st.form_submit_button("📤 Đăng câu hỏi", type="primary")
                    with col2:
                        cancel_q = st.form_submit_button("❌ Hủy")
                    
                    if submit_q:
                        if not q_title or not q_content:
                            st.error("Vui lòng điền tiêu đề và nội dung câu hỏi!")
                        else:
                            result = save_forum_post(q_title, q_content, q_category)
                            if result[0]:  # Có post_id
                                post_id, anon_id = result
                                st.success(f"✅ Câu hỏi đã đăng! (ID: {anon_id})")
                                st.session_state.show_new_question = False
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(f"❌ {result[1]}")  # Hiển thị lỗi
                    
                    if cancel_q:
                        st.session_state.show_new_question = False
                        st.rerun()
        
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
            
            for _, post in df_posts.iterrows():
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
                        # Kiểm tra xem đã reply post này trong session chưa
                        already_replied = post['id'] in st.session_state.replied_posts
                        
                        if not already_replied:
                            with st.form(key=f"reply_form_{post['id']}", clear_on_submit=True):
                                reply_content = st.text_area("Bình luận của bạn:", 
                                                           height=80,
                                                           placeholder="Viết câu trả lời hoặc ý kiến...",
                                                           key=f"reply_content_{post['id']}")
                                
                                col1, col2 = st.columns([2, 1])
                                with col1:
                                    submit_label = f"👮 Trả lời ({st.session_state.police_user['display_name']})"
                                    submit_reply = st.form_submit_button(submit_label, 
                                                                        use_container_width=True,
                                                                        type="primary")
                                
                                if submit_reply:
                                    if not reply_content.strip():
                                        st.error("Vui lòng nhập nội dung bình luận!")
                                    else:
                                        with st.spinner("Đang gửi bình luận..."):
                                            result = save_forum_reply(
                                                post['id'], 
                                                reply_content, 
                                                is_police=True,
                                                police_info=st.session_state.police_user
                                            )
                                            
                                            if result[0]:  # Có reply_id
                                                # Thêm post_id vào danh sách đã reply
                                                st.session_state.replied_posts.add(post['id'])
                                                st.success("✅ Đã gửi trả lời chính thức!")
                                                time.sleep(1)
                                                st.rerun()
                                            else:
                                                st.error(f"❌ {result[1]}")  # Hiển thị lỗi
                        else:
                            st.info("✅ Bạn đã trả lời câu hỏi này. Câu trả lời đang được hiển thị ở trên.")
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
