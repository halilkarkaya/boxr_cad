

## \file ar_server.py
## \brief Komut satırından alınan 3D model için bir web sunucusu ve QR kod üreten betik.

import sys
import os
import http.server
import socketserver
import threading
import qrcode
import socket
from PyQt5.QtWidgets import QApplication, QDialog, QLabel, QVBoxLayout
from PyQt5.QtGui import QPixmap, QFont
from PyQt5.QtCore import Qt

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

## \fn get_local_ip
## \brief Yerel ağdaki IP adresini alır.
## \return Yerel IP adresi (str).
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

## \class QRCodeDialog
## \brief QR kodunu ve sunucu bilgilerini gösteren bir PyQt5 penceresi.
class QRCodeDialog(QDialog):
    ## \brief QRCodeDialog kurucusu.
    ## \param image_path Gösterilecek QR kod resminin yolu (str).
    ## \param server_url Sunucunun web adresi (str).
    ## \param parent Ebeveyn QWidget (opsiyonel).
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

    ## \brief Pencere kapatıldığında web sunucusunu durdurur.
    ## \param event Kapatma olayı.
    def closeEvent(self, event):
        if self.httpd:
            print("Web sunucusu kapatılıyor...")
            threading.Thread(target=self.httpd.shutdown).start()
        event.accept()

## \brief Betiğin ana giriş noktası.
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Hata: Lütfen bir model dosyası yolu belirtin.")
        print("Kullanım: python ar_server.py <dosya_yolu>")
        sys.exit(1)

    model_path = sys.argv[1]
    if not os.path.exists(model_path):
        print(f"Hata: Belirtilen dosya bulunamadı: {model_path}")
        sys.exit(1)

    file_dir = os.path.dirname(os.path.abspath(model_path))
    model_filename = os.path.basename(model_path)
    os.chdir(file_dir)

    viewer_html_src = resource_path('viewer.html')
    viewer_html_dest = os.path.join(file_dir, 'viewer.html')
    if os.path.exists(viewer_html_src) and not os.path.exists(viewer_html_dest):
        import shutil
        shutil.copy(viewer_html_src, viewer_html_dest)

    PORT = 8000
    IP_ADDRESS = get_local_ip()
    SERVER_URL = f"http://{IP_ADDRESS}:{PORT}"
    VIEWER_URL = f"{SERVER_URL}/viewer.html?model={model_filename}"

    Handler = http.server.SimpleHTTPRequestHandler
    httpd = socketserver.TCPServer(('', PORT), Handler)
    
    print(f"Sunucu {SERVER_URL} adresinde başlatılıyor...")
    server_thread = threading.Thread(target=httpd.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    qr_img_path = os.path.join(file_dir, "temp_qr_code.png")
    qrcode.make(VIEWER_URL).save(qr_img_path)
    print(f"QR kodu oluşturuldu: {qr_img_path}")

    app = QApplication(sys.argv)
    dialog = QRCodeDialog(qr_img_path, SERVER_URL)
    dialog.httpd = httpd
    dialog.show()
    
    app.exec_()

    if os.path.exists(qr_img_path):
        os.remove(qr_img_path)
    
    print("Uygulama kapatıldı.")

