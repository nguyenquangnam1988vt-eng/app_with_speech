"""
DỊCH VỤ GỬI EMAIL BẰNG SENDGRID API
Không cần SMTP, không cần App Password
"""

import streamlit as st
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Content, To, From, Subject, Personalization
import json
from datetime import datetime
import logging

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SendGridEmailService:
    """Lớp xử lý gửi email qua SendGrid"""
    
    def __init__(self):
        """Khởi tạo với API key từ secrets.toml"""
        try:
            self.api_key = st.secrets["sendgrid"]["api_key"]
            self.from_email = st.secrets["sendgrid"]["from_email"]
            self.to_email = st.secrets["sendgrid"]["to_email"]
            self.sender_name = st.secrets["sendgrid"].get("sender_name", "Hệ thống Phản ánh")
            
            self.sg = SendGridAPIClient(self.api_key)
            logger.info("✅ SendGrid service initialized successfully")
            
        except KeyError as e:
            logger.error(f"❌ Missing configuration in secrets.toml: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Error initializing SendGrid: {e}")
            raise
    
    def send_security_report(self, report_data):
        """
        Gửi email phản ánh an ninh
        
        Args:
            report_data: dict với keys:
                - title: Tiêu đề phản ánh
                - description: Mô tả chi tiết
                - location: Địa điểm (optional)
                - incident_time: Thời gian (optional)
                - report_id: Mã báo cáo (optional)
        
        Returns:
            tuple: (success, message)
        """
        try:
            # Chuẩn bị nội dung email
            subject = f"🚨 PHẢN ÁNH AN NINH: {report_data.get('title', 'Không có tiêu đề')[:50]}"
            
            # HTML template đẹp hơn
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background: #dc3545; color: white; padding: 15px; text-align: center; border-radius: 5px; }}
                    .content {{ background: #f8f9fa; padding: 20px; border-radius: 5px; margin-top: 15px; }}
                    .field {{ margin-bottom: 10px; }}
                    .label {{ font-weight: bold; color: #495057; }}
                    .value {{ color: #212529; }}
                    .footer {{ margin-top: 20px; font-size: 12px; color: #6c757d; text-align: center; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h2>🚨 PHẢN ÁNH AN NINH TRẬT TỰ</h2>
                    </div>
                    
                    <div class="content">
                        <div class="field">
                            <span class="label">Tiêu đề:</span><br>
                            <span class="value">{report_data.get('title', 'Không có tiêu đề')}</span>
                        </div>
                        
                        <div class="field">
                            <span class="label">Mô tả chi tiết:</span><br>
                            <span class="value">{report_data.get('description', 'Không có mô tả')}</span>
                        </div>
                        
                        <div class="field">
                            <span class="label">Địa điểm:</span><br>
                            <span class="value">{report_data.get('location', 'Không cung cấp')}</span>
                        </div>
                        
                        <div class="field">
                            <span class="label">Thời gian sự việc:</span><br>
                            <span class="value">{report_data.get('incident_time', 'Không cung cấp')}</span>
                        </div>
                        
                        <div class="field">
                            <span class="label">Mã báo cáo:</span><br>
                            <span class="value">PA-{report_data.get('report_id', 'N/A'):06d}</span>
                        </div>
                        
                        <div class="field">
                            <span class="label">Thời gian tiếp nhận:</span><br>
                            <span class="value">{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</span>
                        </div>
                    </div>
                    
                    <div class="footer">
                        <p>📧 Email tự động từ Hệ thống Tiếp nhận Phản ánh Cộng đồng</p>
                        <p>📞 Liên hệ khẩn cấp: 113</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Plain text version (dự phòng)
            plain_text = f"""
            PHẢN ÁNH AN NINH TRẬT TỰ MỚI
            
            Tiêu đề: {report_data.get('title', 'Không có tiêu đề')}
            Mô tả: {report_data.get('description', 'Không có mô tả')}
            Địa điểm: {report_data.get('location', 'Không cung cấp')}
            Thời gian: {report_data.get('incident_time', 'Không cung cấp')}
            Mã báo cáo: PA-{report_data.get('report_id', 'N/A'):06d}
            
            Thời gian tiếp nhận: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
            ---
            Hệ thống tiếp nhận phản ánh cộng đồng
            """
            
            # Tạo email object
            message = Mail(
                from_email=From(self.from_email, self.sender_name),
                to_emails=To(self.to_email),
                subject=Subject(subject),
                html_content=html_content,
                plain_text_content=plain_text
            )
            
            # Thêm custom headers (optional)
            message.custom_arg = {
                "report_id": str(report_data.get('report_id', 'unknown')),
                "category": "security_report",
                "timestamp": datetime.now().isoformat()
            }
            
            # Gửi email
            response = self.sg.send(message)
            
            if response.status_code in [200, 201, 202]:
                logger.info(f"✅ Email sent successfully! Status: {response.status_code}")
                return True, f"✅ Email đã gửi thành công (Mã: PA-{report_data.get('report_id', 'N/A'):06d})"
            else:
                error_msg = f"SendGrid error: {response.status_code} - {response.body}"
                logger.error(error_msg)
                return False, f"❌ Lỗi gửi email (Mã: {response.status_code})"
                
        except Exception as e:
            error_msg = f"❌ Exception sending email: {str(e)}"
            logger.error(error_msg)
            return False, f"❌ Lỗi hệ thống: {str(e)[:100]}"
    
    def send_forum_notification(self, post_data, reply_data=None):
        """Gửi thông báo có câu hỏi/câu trả lời mới"""
        try:
            if reply_data:
                # Thông báo có trả lời mới
                subject = f"💬 CÓ TRẢ LỜI MỚI: {post_data.get('title', '')[:50]}"
                content = f"Có trả lời mới cho câu hỏi '{post_data.get('title')}'"
            else:
                # Thông báo câu hỏi mới
                subject = f"❓ CÂU HỎI MỚI: {post_data.get('title', '')[:50]}"
                content = f"Có câu hỏi mới trên diễn đàn"
            
            message = Mail(
                from_email=From(self.from_email, self.sender_name),
                to_emails=To(self.to_email),
                subject=Subject(subject),
                plain_text_content=content
            )
            
            response = self.sg.send(message)
            return response.status_code in [200, 201, 202]
            
        except Exception as e:
            logger.error(f"Notification error: {e}")
            return False

# Hàm tiện ích để sử dụng trong app.py
def send_email_report(report_data):
    """Hàm wrapper đơn giản để gọi từ app.py"""
    try:
        service = SendGridEmailService()
        return service.send_security_report(report_data)
    except Exception as e:
        return False, f"❌ Không thể khởi tạo dịch vụ email: {str(e)}"

# Test function
def test_sendgrid_connection():
    """Kiểm tra kết nối SendGrid"""
    try:
        service = SendGridEmailService()
        
        # Test với dữ liệu mẫu
        test_data = {
            'title': 'TEST - Phản ánh thử nghiệm',
            'description': 'Đây là email test từ hệ thống',
            'location': 'Địa điểm test',
            'incident_time': datetime.now().strftime('%H:%M %d/%m/%Y'),
            'report_id': 999999
        }
        
        success, message = service.send_security_report(test_data)
        return success, message
        
    except Exception as e:
        return False, f"❌ Test failed: {str(e)}"

if __name__ == "__main__":
    # Chạy thử khi chạy file trực tiếp
    print("🧪 Testing SendGrid email service...")
    success, msg = test_sendgrid_connection()
    print(f"Result: {success} - {msg}")
