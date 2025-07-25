

import sys
import os
import http.server
import socketserver
import threading
import qrcode
import socket
from PyQt5.QtWidgets import QApplication, QDialog, QLabel, QVBoxLayout
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt

def get_local_ip():
    """Yerel IP adresini bulan fonksiyon."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Bu IP adresinin ulaşılabilir olması gerekmez
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

class QRCodeDialog(QDialog):
    """QR kodunu ve sunucu bilgilerini gösteren pencere."""
    def __init__(self, image_path, server_url, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AR Kodu - Telefonunuzla Tarayın")
        self.setMinimumSize(350, 400)
        self.setStyleSheet("background-color: #232836; color: #bfc7e6;")

        layout = QVBoxLayout(self)
        
        info_label = QLabel(f"Modeli görüntülemek için aşağıdaki QR kodu tarayın.\nSunucu adresi: {server_url}")
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setWordWrap(True)
        info_label.setFont(QFont("Arial", 11))
        layout.addWidget(info_label)

        qr_label = QLabel()
        pixmap = QPixmap(image_path)
        qr_label.setPixmap(pixmap.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        qr_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(qr_label)

        self.httpd = None

    def closeEvent(self, event):
        """Pencere kapatıldığında web sunucusunu durdurur."""
        if self.httpd:
            print("Web sunucusu kapatılıyor...")
            threading.Thread(target=self.httpd.shutdown).start()
        event.accept()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Hata: Lütfen bir model dosyası yolu belirtin.")
        print("Kullanım: python ar_server.py <dosya_yolu>")
        sys.exit(1)

    model_path = sys.argv[1]
    if not os.path.exists(model_path):
        print(f"Hata: Belirtilen dosya bulunamadı: {model_path}")
        sys.exit(1)

    # Sunucunun çalışacağı dizini modelin bulunduğu dizin olarak ayarla
    file_dir = os.path.dirname(os.path.abspath(model_path))
    model_filename = os.path.basename(model_path)
    os.chdir(file_dir)

    # viewer.html dosyasını sunucu dizinine kopyala (eğer yoksa)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    viewer_html_src = os.path.join(script_dir, 'viewer.html')
    viewer_html_dest = os.path.join(file_dir, 'viewer.html')
    if os.path.exists(viewer_html_src) and not os.path.exists(viewer_html_dest):
        import shutil
        shutil.copy(viewer_html_src, viewer_html_dest)

    PORT = 8000
    IP_ADDRESS = get_local_ip()
    SERVER_URL = f"http://{IP_ADDRESS}:{PORT}"
    # Model adını URL'e parametre olarak ekle
    VIEWER_URL = f"{SERVER_URL}/viewer.html?model={model_filename}"

    # Web sunucusunu ayarla ve başlat
    Handler = http.server.SimpleHTTPRequestHandler
    httpd = socketserver.TCPServer(('', PORT), Handler)
    
    print(f"Sunucu {SERVER_URL} adresinde başlatılıyor...")
    server_thread = threading.Thread(target=httpd.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    # Geçici QR kod resmini oluştur
    qr_img_path = os.path.join(file_dir, "temp_qr_code.png")
    qrcode.make(VIEWER_URL).save(qr_img_path)
    print(f"QR kodu oluşturuldu: {qr_img_path}")

    # QR kodunu bir PyQt penceresinde göster
    app = QApplication(sys.argv)
    from PyQt5.QtGui import QFont
    dialog = QRCodeDialog(qr_img_path, SERVER_URL)
    dialog.httpd = httpd  # Kapatma işlemi için sunucu referansını ver
    dialog.show()
    
    app.exec_()

    # Geçici QR kod dosyasını temizle
    if os.path.exists(qr_img_path):
        os.remove(qr_img_path)
    
    print("Uygulama kapatıldı.")

