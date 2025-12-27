"""
🏛️ HỆ THỐNG TIẾP NHẬN PHẢN ÁNH & TƯ VẤN CỘNG ĐỒNG
Tích hợp đầy đủ: SendGrid Email, Database, Diễn đàn, Voice-to-Text
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import hashlib
import secrets
import time
import json
import os

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
    }
    .warning-box {
        background: #fff3cd;
        color: #856404;
        padding: 1rem;
        border-radius: 5px;
        border-left: 5px solid #ffc107;
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
        import bcrypt
        hashed_pw = bcrypt.hashpw("congan123".encode(), bcrypt.gensalt()).decode()
        c.execute('''
            INSERT INTO police_users (badge_number, display_name, password_hash, role)
            VALUES (?, ?, ?, ?)
        ''', ('CA001', 'Admin Công An', hashed_pw, 'admin'))
    
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
    """Xử lý phản ánh và gửi email - PHẦN QUAN TRỌNG ĐÃ SỬA"""
    
    # 1. Lưu vào database
    report_id = save_to_database(title, description, location, incident_time)
    
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
        conn = sqlite3.connect('community_app.db')
        c = conn.cursor()
        c.execute('UPDATE security_reports SET email_sent = 1 WHERE id = ?', (report_id,))
        conn.commit()
        conn.close()
    
    # 5. Hiển thị kết quả cho người dùng
    return report_id, email_success, email_message

# ================ HÀM DIỄN ĐÀN ================
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
    """Lưu bình luận diễn đàn"""
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

# ================ ĐĂNG NHẬP CÔNG AN ================
def police_login(badge_number, password):
    """Đăng nhập công an"""
    try:
        import bcrypt
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
    except Exception:
        return None

# ================ GIAO DIỆN CHÍNH ================
def main():
    """Hàm chính của ứng dụng"""
    
    # Khởi tạo database
    init_database()
    
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
            st.markdown(f'<span class="police-badge">👮 {user["display_name"]}</span>', unsafe_allow_html=True)
            st.info(f"Số hiệu: {user['badge_number']}")
            
            if st.button("Đăng xuất", use_container_width=True):
                st.session_state.police_user = None
                st.rerun()
        
        # Thông tin hệ thống
        st.markdown("---")
        st.markdown("### 📊 Thống kê nhanh")
        
        conn = sqlite3.connect('community_app.db')
        today = datetime.now().strftime('%Y-%m-%d')
        
        col1, col2 = st.columns(2)
        with col1:
            total_reports = pd.read_sql_query("SELECT COUNT(*) FROM security_reports", conn)
            st.metric("Phản ánh", int(total_reports.iloc[0,0]))
        with col2:
            total_posts = pd.read_sql_query("SELECT COUNT(*) FROM forum_posts", conn)
            st.metric("Câu hỏi", int(total_posts.iloc[0,0]))
        
        conn.close()
    
    # Main tabs
    tab1, tab2, tab3 = st.tabs(["📢 PHẢN ÁNH AN NINH", "💬 DIỄN ĐÀN", "ℹ️ HƯỚNG DẪN"])
    
    # ========= TAB 1: PHẢN ÁNH AN NINH =========
    with tab1:
        st.subheader("Biểu mẫu Phản ánh An ninh Trật tự")
        
        if not SENDGRID_AVAILABLE:
            st.warning("""
            ⚠️ **TÍNH NĂNG EMAIL CHƯA SẴN SÀNG**
            
            Phản ánh sẽ chỉ được lưu vào database.
            Để gửi email tự động, cần cấu hình SendGrid.
            """)
        
        with st.form("security_report_form"):
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
                    # Xử lý phản ánh - GỌI HÀM ĐÃ SỬA
                    report_id, email_success, email_message = handle_security_report(
                        title, description, location, incident_time
                    )
                    
                    if email_success:
                        st.markdown(f"""
                        <div class="success-box">
                            <h4>✅ ĐÃ TIẾP NHẬN PHẢN ÁNH #{report_id}</h4>
                            <p>{email_message}</p>
                            <p>Phản ánh đã được gửi đến Công an. Cảm ơn bạn đã đóng góp!</p>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <div class="warning-box">
                            <h4>⚠️ ĐÃ LƯU PHẢN ÁNH #{report_id}</h4>
                            <p>{email_message}</p>
                            <p>Vui lòng liên hệ trực tiếp qua số điện thoại nếu cần thiết.</p>
                        </div>
                        """, unsafe_allow_html=True)
    
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
                with st.form("new_question_form"):
                    q_title = st.text_input("Tiêu đề câu hỏi *")
                    q_category = st.selectbox("Chủ đề", 
                                            ["Hỏi đáp pháp luật", "Giải quyết mâu thuẫn", 
                                             "Tư vấn thủ tục", "An ninh trật tự", "Khác"])
                    q_content = st.text_area("Nội dung chi tiết *", height=150,
                                           placeholder="Mô tả rõ vấn đề bạn đang gặp phải...")
                    
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
                        reply_content = st.text_area("Bình luận của bạn", height=80,
                                                   placeholder="Viết câu trả lời hoặc ý kiến...")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.session_state.police_user:
                                submit_label = "👮 Trả lời (Công an)"
                            else:
                                submit_label = "💬 Gửi bình luận"
                            
                            submit_reply = st.form_submit_button(submit_label)
                        
                        if submit_reply and reply_content:
                            if st.session_state.police_user:
                                author_id = save_forum_reply(
                                    post['id'], 
                                    reply_content, 
                                    is_police=True,
                                    police_info=st.session_state.police_user
                                )
                                st.success("✅ Đã gửi trả lời chính thức!")
                            else:
                                author_id = save_forum_reply(post['id'], reply_content)
                                st.success("✅ Đã gửi bình luận!")
                            st.rerun()
        else:
            st.info("📝 Chưa có câu hỏi nào. Hãy là người đầu tiên đặt câu hỏi!")
    
    # ========= TAB 3: HƯỚNG DẪN =========
    with tab3:
        st.subheader("📖 Hướng dẫn sử dụng")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            ### 📢 **Phản ánh An ninh:**
            1. Điền thông tin sự việc
            2. Nhấn **GỬI PHẢN ÁNH**
            3. Hệ thống tự động gửi đến Công an
            
            ### 💬 **Diễn đàn:**
            1. Đặt câu hỏi ẩn danh
            2. Công an trả lời chính thức
            3. Mọi người cùng thảo luận
            """)
        
        with col2:
            st.markdown("""
            ### 🔒 **Bảo mật:**
            - Không lưu thông tin cá nhân
            - ID ngẫu nhiên mỗi lần
            - Không cần đăng ký
            
            ### 👮 **Dành cho Công an:**
            - Đăng nhập bằng số hiệu
            - Trả lời câu hỏi chính thức
            - Theo dõi phản ánh
            """)
        
        # Thông tin liên hệ
        st.markdown("---")
        st.markdown("""
        ### 📞 Liên hệ khẩn cấp
        - **Hotline Công an:** 113
        - **Trực ban địa phương:** Liên hệ Công an phường/xã
        - **Tình huống nguy hiểm:** Gọi ngay 113
        """)

# Chạy ứng dụng
if __name__ == "__main__":
    main()
