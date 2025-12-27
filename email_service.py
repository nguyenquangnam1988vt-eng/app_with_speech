# email_service.py - Gửi email thật bằng SendGrid
import streamlit as st
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Content, To, From, Subject
from datetime import datetime
import os

def send_email_report(report_data):
    """
    Hàm gửi email thông qua SendGrid API
    """
    try:
        # Lấy API Key từ secrets.toml hoặc biến môi trường
        # CÁCH 1: Dùng Streamlit secrets (tốt nhất)
        try:
            api_key = st.secrets["sendgrid"]["api_key"]
            from_email = st.secrets["sendgrid"]["from_email"]
            to_email = st.secrets["sendgrid"]["to_email"]
            sender_name = st.secrets["sendgrid"].get("sender_name", "Hệ thống Phản ánh")
        except:
            # CÁCH 2: Dùng biến môi trường
            api_key = os.environ.get('SENDGRID_API_KEY')
            from_email = os.environ.get('FROM_EMAIL', 'phảnánh@tiepnhancapthanhmieu.streamlit.app')
            to_email = os.environ.get('TO_EMAIL', 'congan.diaphuong@gmail.com')
            sender_name = "Hệ thống Tiếp nhận Phản ánh"
        
        if not api_key:
            return False, "❌ Chưa cấu hình SendGrid API Key"
        
        # Tạo tiêu đề email
        subject = f"🚨 PHẢN ÁNH AN NINH #{report_data['report_id']:06d}: {report_data['title'][:50]}"
        
        # Nội dung HTML đẹp
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ 
                    background: linear-gradient(135deg, #dc3545 0%, #ff6b6b 100%);
                    color: white; 
                    padding: 20px; 
                    text-align: center; 
                    border-radius: 10px 10px 0 0;
                }}
                .content {{ 
                    background: #f8f9fa; 
                    padding: 25px; 
                    border-radius: 0 0 10px 10px;
                    border: 1px solid #dee2e6;
                }}
                .field {{ margin-bottom: 15px; }}
                .label {{ font-weight: bold; color: #495057; font-size: 14px; }}
                .value {{ 
                    color: #212529; 
                    background: white; 
                    padding: 10px; 
                    border-radius: 5px; 
                    border-left: 4px solid #007bff;
                    margin-top: 5px;
                }}
                .report-id {{ 
                    background: #dc3545; 
                    color: white; 
                    padding: 5px 15px; 
                    border-radius: 20px; 
                    display: inline-block;
                    font-weight: bold;
                }}
                .footer {{ 
                    margin-top: 30px; 
                    font-size: 12px; 
                    color: #6c757d; 
                    text-align: center;
                    border-top: 1px solid #dee2e6;
                    padding-top: 15px;
                }}
                .urgent {{ color: #dc3545; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🚨 PHẢN ÁNH AN NINH TRẬT TỰ</h1>
                    <div class="report-id">Mã: PA-{report_data['report_id']:06d}</div>
                </div>
                
                <div class="content">
                    <div class="field">
                        <div class="label">TIÊU ĐỀ:</div>
                        <div class="value">{report_data.get('title', 'Không có tiêu đề')}</div>
                    </div>
                    
                    <div class="field">
                        <div class="label">MÔ TẢ CHI TIẾT:</div>
                        <div class="value">{report_data.get('description', 'Không có mô tả').replace(chr(10), '<br>')}</div>
                    </div>
                    
                    <div class="field">
                        <div class="label">ĐỊA ĐIỂM:</div>
                        <div class="value">{report_data.get('location', 'Không cung cấp')}</div>
                    </div>
                    
                    <div class="field">
                        <div class="label">THỜI GIAN SỰ VIỆC:</div>
                        <div class="value">{report_data.get('incident_time', 'Không cung cấp')}</div>
                    </div>
                    
                    <div class="field">
                        <div class="label">THỜI GIAN TIẾP NHẬN:</div>
                        <div class="value">{datetime.now().strftime('%H:%M %d/%m/%Y')}</div>
                    </div>
                </div>
                
                <div class="footer">
                    <p class="urgent">📞 LIÊN HỆ KHẨN CẤP: 113</p>
                    <p>📧 Email tự động từ <strong>Cổng Tiếp nhận Phản ánh Cộng đồng</strong></p>
                    <p>🏛️ Hệ thống tiếp nhận và xử lý phản ánh trực tuyến</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Plain text version cho client không hỗ trợ HTML
        plain_text = f"""
        PHẢN ÁNH AN NINH TRẬT TỰ
        
        MÃ PHẢN ÁNH: PA-{report_data['report_id']:06d}
        TIÊU ĐỀ: {report_data.get('title', 'Không có tiêu đề')}
        
        MÔ TẢ:
        {report_data.get('description', 'Không có mô tả')}
        
        ĐỊA ĐIỂM: {report_data.get('location', 'Không cung cấp')}
        THỜI GIAN: {report_data.get('incident_time', 'Không cung cấp')}
        
        THỜI GIAN TIẾP NHẬN: {datetime.now().strftime('%H:%M %d/%m/%Y')}
        
        ---
        📞 LIÊN HỆ KHẨN CẤP: 113
        🏛️ Cổng Tiếp nhận Phản ánh Cộng đồng
        """
        
        # Tạo email object
        message = Mail(
            from_email=From(from_email, sender_name),
            to_emails=To(to_email),
            subject=Subject(subject),
            html_content=html_content,
            plain_text_content=plain_text
        )
        
        # Gửi email
        sg = SendGridAPIClient(api_key)
        response = sg.send(message)
        
        # Kiểm tra kết quả
        if response.status_code == 202:
            return True, f"✅ Email đã gửi thành công đến Công an! (Mã: PA-{report_data['report_id']:06d})"
        else:
            return False, f"⚠️ Lỗi gửi email (Mã lỗi: {response.status_code})"
            
    except Exception as e:
        return False, f"❌ Lỗi hệ thống: {str(e)[:100]}"
