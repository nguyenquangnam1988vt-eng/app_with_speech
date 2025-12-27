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
import wave
import io
import base64
from typing import Optional
import numpy as np

# Import speech recognition
try:
    import speech_recognition as sr
    import pyaudio
    import sounddevice as sd
    from pydub import AudioSegment
    SPEECH_ENABLED = True
except ImportError:
    SPEECH_ENABLED = False
    st.warning("Cần cài thư viện speech_recognition, pyaudio, pydub để sử dụng tính năng nói")

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Hệ Thống Tiếp Nhận - Hỗ trợ giọng nói",
    page_icon="🎤",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS với tính năng voice
st.markdown("""
<style>
    .voice-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        color: white;
        margin-bottom: 2rem;
    }
    .voice-button {
        background-color: #4CAF50;
        color: white;
        border: none;
        padding: 15px 32px;
        text-align: center;
        text-decoration: none;
        display: inline-block;
        font-size: 16px;
        margin: 4px 2px;
        cursor: pointer;
        border-radius: 50px;
        transition: all 0.3s ease;
    }
    .voice-button:hover {
        background-color: #45a049;
        transform: scale(1.05);
    }
    .voice-button-recording {
        background-color: #f44336 !important;
        animation: pulse 1.5s infinite;
    }
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.1); }
        100% { transform: scale(1); }
    }
    .mic-icon {
        font-size: 24px;
        margin-right: 10px;
    }
    .voice-result {
        background-color: #f8f9fa;
        border-left: 5px solid #4CAF50;
        padding: 1rem;
        margin-top: 1rem;
        border-radius: 5px;
        min-height: 100px;
    }
    .language-selector {
        background-color: white;
        padding: 0.5rem;
        border-radius: 5px;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize database (giữ nguyên)
def init_database():
    conn = sqlite3.connect('community_app.db')
    c = conn.cursor()
    
    # Giữ nguyên các bảng cũ...
    # (code database như trước)
    
    # Thêm bảng lưu audio files nếu cần
    c.execute('''
        CREATE TABLE IF NOT EXISTS audio_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_session TEXT,
            audio_data BLOB,
            text_content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            duration_seconds FLOAT
        )
    ''')
    
    conn.commit()
    conn.close()

# Class xử lý giọng nói
class VoiceToTextConverter:
    def __init__(self):
        self.recognizer = sr.Recognizer() if SPEECH_ENABLED else None
        self.is_recording = False
        self.audio_data = None
        self.text_result = ""
        
    def start_recording(self, duration=10):
        """Bắt đầu ghi âm"""
        if not SPEECH_ENABLED:
            return False, "Thư viện speech recognition chưa được cài đặt"
        
        try:
            with sr.Microphone() as source:
                st.info("🎤 Đang điều chỉnh tiếng ồn môi trường...")
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                
                st.success("✅ Sẵn sàng! Nói điều bạn muốn...")
                
                # Ghi âm
                self.audio_data = self.recognizer.listen(source, timeout=duration)
                self.is_recording = True
                
                return True, "Đang ghi âm... Hãy nói vào micro"
                
        except sr.WaitTimeoutError:
            return False, "Hết thời gian chờ, không có âm thanh"
        except Exception as e:
            return False, f"Lỗi: {str(e)}"
    
    def stop_and_convert(self, language="vi-VN"):
        """Dừng và chuyển thành văn bản"""
        if not self.audio_data:
            return False, "Không có dữ liệu âm thanh"
        
        try:
            # Sử dụng Google Speech Recognition
            text = self.recognizer.recognize_google(
                self.audio_data, 
                language=language
            )
            self.text_result = text
            self.is_recording = False
            
            # Lưu vào session state
            if 'voice_results' not in st.session_state:
                st.session_state.voice_results = []
            
            st.session_state.voice_results.append({
                'text': text,
                'timestamp': datetime.now().strftime("%H:%M:%S"),
                'language': language
            })
            
            return True, text
            
        except sr.UnknownValueError:
            return False, "Không thể nhận diện giọng nói. Vui lòng thử lại"
        except sr.RequestError as e:
            return False, f"Lỗi kết nối: {str(e)}"
        except Exception as e:
            return False, f"Lỗi: {str(e)}"
    
    def save_audio_to_db(self, session_id):
        """Lưu audio vào database (nếu cần)"""
        if not self.audio_data:
            return False
        
        try:
            conn = sqlite3.connect('community_app.db')
            c = conn.cursor()
            
            # Chuyển audio data thành bytes
            audio_bytes = self.audio_data.get_wav_data()
            
            c.execute('''
                INSERT INTO audio_files (user_session, audio_data, text_content, duration_seconds)
                VALUES (?, ?, ?, ?)
            ''', (session_id, audio_bytes, self.text_result, len(audio_bytes)/16000))
            
            conn.commit()
            conn.close()
            return True
        except:
            return False

# Hàm hiển thị giao diện voice
def show_voice_input(text_area_key, default_text="", language="vi-VN"):
    """Hiển thị giao diện nhập bằng giọng nói"""
    
    # Khởi tạo converter trong session state
    if 'voice_converter' not in st.session_state:
        st.session_state.voice_converter = VoiceToTextConverter()
    
    converter = st.session_state.voice_converter
    
    # Container voice
    st.markdown('<div class="voice-container">', unsafe_allow_html=True)
    st.markdown("### 🎤 NHẬP BẰNG GIỌNG NÓI")
    st.markdown("Dành cho người không tiện gõ phím hoặc muốn mô tả nhanh")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Chọn ngôn ngữ
    col1, col2 = st.columns([3, 1])
    
    with col1:
        language_options = {
            "Tiếng Việt": "vi-VN",
            "Tiếng Anh": "en-US",
            "Tiếng Trung": "zh-CN",
            "Tiếng Nhật": "ja-JP",
            "Tiếng Hàn": "ko-KR"
        }
        
        selected_lang_name = st.selectbox(
            "Chọn ngôn ngữ nói:",
            list(language_options.keys()),
            index=0
        )
        selected_lang = language_options[selected_lang_name]
    
    with col2:
        recording_duration = st.slider("Thời gian ghi (giây)", 5, 60, 15)
    
    # Các nút điều khiển
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Nút bắt đầu ghi âm
        button_label = "⏺️ ĐANG GHI..." if converter.is_recording else "🎤 BẮT ĐẦU NÓI"
        button_class = "voice-button voice-button-recording" if converter.is_recording else "voice-button"
        
        if st.button(button_label, key=f"start_{text_area_key}", use_container_width=True):
            success, message = converter.start_recording(recording_duration)
            if success:
                st.success(message)
                st.balloons()
            else:
                st.error(message)
            st.rerun()
    
    with col2:
        # Nút dừng và chuyển đổi
        if st.button("⏹️ DỪNG & CHUYỂN THÀNH CHỮ", 
                    key=f"stop_{text_area_key}", 
                    disabled=not converter.is_recording,
                    use_container_width=True):
            
            success, result = converter.stop_and_convert(selected_lang)
            
            if success:
                # Cập nhật text area
                current_text = st.session_state.get(text_area_key, default_text)
                new_text = current_text + " " + result if current_text else result
                st.session_state[text_area_key] = new_text
                
                st.success("✅ Đã chuyển thành văn bản!")
                
                # Hiển thị kết quả
                with st.expander("📝 Xem kết quả chuyển đổi", expanded=True):
                    st.write("**Giọng nói đã nhận diện:**")
                    st.markdown(f'<div class="voice-result">{result}</div>', unsafe_allow_html=True)
                    
                    # Nút copy
                    if st.button("📋 Sao chép vào khung nhập"):
                        st.session_state[text_area_key] = result
                        st.rerun()
            else:
                st.error(f"Không thể chuyển đổi: {result}")
            
            st.rerun()
    
    with col3:
        # Nút xóa
        if st.button("🗑️ XÓA KẾT QUẢ", 
                    key=f"clear_{text_area_key}",
                    use_container_width=True):
            converter.text_result = ""
            converter.audio_data = None
            if 'voice_results' in st.session_state:
                st.session_state.voice_results = []
            st.rerun()
    
    # Hiển thị trạng thái
    if converter.is_recording:
        st.warning("🔴 **ĐANG GHI ÂM... Hãy nói rõ ràng vào micro**")
        # Progress bar cho thời gian ghi âm
        progress_bar = st.progress(0)
        for i in range(100):
            time.sleep(recording_duration/100)
            progress_bar.progress(i + 1)
    
    # Lịch sử chuyển đổi
    if 'voice_results' in st.session_state and st.session_state.voice_results:
        with st.expander("📜 Lịch sử chuyển đổi gần đây"):
            for i, result in enumerate(st.session_state.voice_results[-5:]):
                st.write(f"**{result['timestamp']}** ({result['language']}):")
                st.info(result['text'][:200] + "..." if len(result['text']) > 200 else result['text'])
                
                # Nút sử dụng lại
                if st.button(f"Sử dụng lại #{i+1}", key=f"reuse_{i}"):
                    st.session_state[text_area_key] = result['text']
                    st.rerun()
    
    # Hướng dẫn
    with st.expander("💡 Hướng dẫn sử dụng"):
        st.markdown("""
        1. **Chọn ngôn ngữ** bạn sẽ nói
        2. Nhấn **🎤 BẮT ĐẦU NÓI** và bắt đầu nói vào micro
        3. Nhấn **⏹️ DỪNG & CHUYỂN THÀNH CHỮ** khi nói xong
        4. Kiểm tra kết quả và **sao chép vào form**
        
        **Mẹo:**
        - Nói rõ ràng, không quá nhanh
        - Giữ micro gần miệng
        - Tránh nơi có nhiều tiếng ồn
        - Có thể nói từng đoạn ngắn rồi ghép lại
        """)
    
    return converter

# Hàm tạo form phản ánh với voice input
def show_security_report_with_voice():
    """Form phản ánh ANTT với voice input"""
    
    st.subheader("📢 PHẢN ÁNH AN NINH TRẬT TỰ")
    
    # Tab chọn phương thức nhập
    input_method = st.radio(
        "Chọn cách nhập nội dung:",
        ["⌨️ Gõ phím", "🎤 Nói"],
        horizontal=True
    )
    
    with st.form("security_report_form"):
        # Các trường cơ bản
        title = st.text_input("Tiêu đề phản ánh *", 
                            placeholder="Ví dụ: Mất trộm xe máy tại...")
        
        col1, col2 = st.columns(2)
        with col1:
            location = st.text_input("Địa điểm xảy ra", 
                                   placeholder="Địa chỉ cụ thể...")
        with col2:
            incident_time = st.text_input("Thời gian", 
                                        placeholder="VD: 20h30 ngày 15/12/2023")
        
        # Nội dung chi tiết - với voice input
        st.markdown("### Mô tả chi tiết sự việc *")
        
        if input_method == "🎤 Nói" and SPEECH_ENABLED:
            # Hiển thị voice input
            voice_converter = show_voice_input("security_description")
            
            # Text area để chỉnh sửa
            description = st.text_area(
                "Chỉnh sửa nội dung (nếu cần):",
                key="security_description",
                height=150,
                placeholder="Nội dung sẽ tự động điền từ giọng nói... Hoặc bạn có thể gõ trực tiếp"
            )
        else:
            # Chỉ text area thông thường
            if not SPEECH_ENABLED:
                st.warning("⚠️ Tính năng nói chưa khả dụng. Vui lòng cài thư viện speech_recognition")
            
            description = st.text_area(
                "Mô tả chi tiết sự việc:",
                height=200,
                placeholder="Mô tả đầy đủ sự việc, nhân vật, phương tiện, thiệt hại..."
            )
        
        # Tải file đính kèm
        uploaded_file = st.file_uploader(
            "Tải lên hình ảnh/tài liệu (nếu có)",
            type=['jpg', 'jpeg', 'png', 'pdf', 'mp3', 'wav'],
            help="Có thể tải lên file âm thanh ghi âm sự việc"
        )
        
        submitted = st.form_submit_button("🚨 GỬI PHẢN ÁNH", type="primary", use_container_width=True)
        
        if submitted:
            if not title or not description:
                st.error("Vui lòng điền tiêu đề và mô tả sự việc!")
            else:
                # Xử lý gửi phản ánh...
                # (code xử lý như trước)
                pass

# Hàm tạo form diễn đàn với voice input
def show_forum_post_with_voice():
    """Form đăng bài diễn đàn với voice input"""
    
    with st.expander("📝 ĐẶT CÂU HỎI MỚI (có thể nói)", expanded=False):
        # Chọn phương thức nhập
        input_method = st.radio(
            "Cách nhập câu hỏi:",
            ["⌨️ Gõ phím", "🎤 Nói câu hỏi"],
            key="forum_input_method",
            horizontal=True
        )
        
        with st.form("new_forum_post_form"):
            post_title = st.text_input("Tiêu đề câu hỏi *")
            post_category = st.selectbox("Chuyên mục *", 
                                       ["Hỏi đáp pháp luật", 
                                        "Giải quyết mâu thuẫn",
                                        "Tư vấn thủ tục",
                                        "Khác"])
            
            st.markdown("### Nội dung câu hỏi *")
            
            if input_method == "🎤 Nói câu hỏi" and SPEECH_ENABLED:
                # Voice input cho nội dung
                voice_converter = show_voice_input("forum_content")
                
                post_content = st.text_area(
                    "Chỉnh sửa nội dung (nếu cần):",
                    key="forum_content",
                    height=200,
                    placeholder="Câu hỏi của bạn sẽ được chuyển từ giọng nói thành văn bản..."
                )
            else:
                post_content = st.text_area(
                    "Nội dung chi tiết câu hỏi:",
                    height=200,
                    placeholder="Mô tả rõ vấn đề bạn đang gặp phải..."
                )
            
            submitted = st.form_submit_button("📤 ĐĂNG CÂU HỎI", type="primary")
            
            if submitted and post_title and post_content:
                # Xử lý đăng bài...
                pass

# Trang chính với voice features
def main():
    # Session state
    if 'police_logged_in' not in st.session_state:
        st.session_state.police_logged_in = False
    
    # Header với tính năng mới
    st.markdown("""
    <h1 style='text-align: center; color: #1E3A8A;'>
        🎤 HỆ THỐNG TIẾP NHẬN PHẢN ÁNH<br>
        <small style='font-size: 0.6em; color: #666;'>Hỗ trợ nhập liệu bằng giọng nói</small>
    </h1>
    """, unsafe_allow_html=True)
    
    # Thông báo nếu không có speech recognition
    if not SPEECH_ENABLED:
        st.warning("""
        ⚠️ **Tính năng nhận diện giọng nói chưa khả dụng**
        
        Để sử dụng tính năng nói, vui lòng cài đặt:
        ```bash
        pip install SpeechRecognition pyaudio pydub
        ```
        
        *Trên Windows có thể cần cài Visual C++ Redistributable*
        """)
    
    # Tabs chính
    tab1, tab2, tab3 = st.tabs(["📢 PHẢN ÁNH AN NINH", "💬 DIỄN ĐÀN", "🎤 HƯỚNG DẪN NÓI"])
    
    with tab1:
        show_security_report_with_voice()
    
    with tab2:
        show_forum_post_with_voice()
        # Hiển thị diễn đàn như cũ...
    
    with tab3:
        show_voice_guide()

# Trang hướng dẫn sử dụng voice
def show_voice_guide():
    st.title("🎤 HƯỚNG DẪN SỬ DỤNG TÍNH NĂNG GIỌNG NÓI")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### ✅ **Lợi ích:**
        
        1. **Tiết kiệm thời gian:** Nói nhanh hơn gõ
        2. **Tiện lợi:** Không cần gõ phím, dùng trên điện thoại
        3. **Dễ dàng:** Cho người lớn tuổi, không rành công nghệ
        4. **Tự nhiên:** Diễn đạt bằng lời nói dễ hơn viết
        5. **Đa ngôn ngữ:** Hỗ trợ nhiều ngôn ngữ khác nhau
        """)
    
    with col2:
        st.markdown("""
        ### 🎯 **Các trường hợp nên dùng:**
        
        - **Khi đang di chuyển:** Không tiện gõ phím
        - **Sự việc phức tạp:** Dễ mô tả bằng lời nói
        - **Người khuyết tật:** Khó khăn trong việc gõ phím
        - **Trình độ CNTT thấp:** Ngại gõ phím, dùng tiếng địa phương
        - **Mô tả chi tiết:** Giọng nói truyền tải cảm xúc tốt hơn
        """)
    
    st.markdown("---")
    
    # Demo video/ảnh
    st.subheader("🎬 Hướng dẫn trực quan")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.image("https://cdn-icons-png.flaticon.com/512/3576/3576680.png", width=100)
        st.markdown("**1. Chọn 'Nói'**")
        st.write("Chọn phương thức nhập bằng giọng nói")
    
    with col2:
        st.image("https://cdn-icons-png.flaticon.com/512/3094/3094833.png", width=100)
        st.markdown("**2. Nhấn nút micro**")
        st.write("Nhấn và bắt đầu nói rõ ràng")
    
    with col3:
        st.image("https://cdn-icons-png.flaticon.com/512/5706/5706745.png", width=100)
        st.markdown("**3. Kiểm tra & gửi**")
        st.write("Xem lại văn bản và gửi đi")
    
    st.markdown("---")
    
    # Tips cải thiện độ chính xác
    st.subheader("💡 Mẹo để nhận diện chính xác hơn")
    
    tips = [
        "🎯 **Nói rõ ràng:** Phát âm rõ từng từ",
        "📏 **Tốc độ vừa phải:** Không quá nhanh hoặc quá chậm",
        "🔇 **Yên tĩnh:** Tìm nơi ít tiếng ồn",
        "🎤 **Micro gần:** Giữ điện thoại/gần micro",
        "📱 **Dùng headset:** Để chất lượng âm thanh tốt hơn",
        "🇻🇳 **Đúng ngôn ngữ:** Chọn đúng ngôn ngữ đang nói",
        "✂️ **Đoạn ngắn:** Nói từng đoạn ngắn 10-20 giây"
    ]
    
    for tip in tips:
        st.markdown(f"- {tip}")
    
    # Test microphone
    st.markdown("---")
    st.subheader("🎧 Kiểm tra microphone")
    
    if st.button("🎤 Kiểm tra mic của tôi"):
        if SPEECH_ENABLED:
            try:
                with sr.Microphone() as source:
                    st.info("Đang kiểm tra mic... Hãy nói 'xin chào'")
                    audio = sr.Recognizer().listen(source, timeout=3)
                    
                    try:
                        text = sr.Recognizer().recognize_google(audio, language="vi-VN")
                        if "xin chào" in text.lower():
                            st.success("✅ Micro hoạt động tốt!")
                        else:
                            st.info(f"Mic hoạt động, nhận diện được: '{text}'")
                    except:
                        st.warning("Mic hoạt động nhưng không nhận diện được giọng nói")
            except Exception as e:
                st.error(f"Không thể truy cập mic: {str(e)}")
        else:
            st.error("Chưa cài đặt thư viện speech recognition")

# Chạy ứng dụng
if __name__ == "__main__":
    init_database()
    main()
