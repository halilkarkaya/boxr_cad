## \file main.py
## \brief Ana uygulama dosyası. PyQt5 tabanlı CAD arayüzünü başlatır ve ana pencereyi yönetir.

import sys
import os
import logging
from PyQt5.QtWidgets import QApplication
from arayuz_design import MainWindow

# --- AR Sunucu için Gerekli Kütüphaneler ---
import http.server
import socketserver
import threading
import qrcode
import socket
from PyQt5.QtWidgets import QDialog, QLabel, QVBoxLayout
from PyQt5.QtGui import QPixmap, QFont
from PyQt5.QtCore import Qt

# --- Loglama ve Kaynak Yolu ---
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

logging.basicConfig(
    filename=resource_path('uygulama.log'),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

# --- AR Sunucu Fonksiyonları ---

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

class QRCodeDialog(QDialog):
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
        if self.httpd:
            print("Web sunucusu kapatılıyor...")
            threading.Thread(target=self.httpd.shutdown).start()
        event.accept()

def start_ar_server(model_path):
    """ AR sunucusunu ve QR kod penceresini başlatır. """
    import shutil

    if not os.path.exists(model_path):
        logging.error(f"AR sunucusu için model dosyası bulunamadı: {model_path}")
        print(f"Hata: Belirtilen dosya bulunamadı: {model_path}")
        sys.exit(1)

    file_dir = os.path.dirname(os.path.abspath(model_path))
    model_filename = os.path.basename(model_path)
    
    viewer_html_src = resource_path('viewer.html')
    viewer_html_dest = os.path.join(file_dir, 'viewer.html')
    
    try:
        # Kaynak ve hedef aynı dosya değilse veya hedef hiç yoksa kopyala
        if not os.path.exists(viewer_html_dest) or not os.path.samefile(viewer_html_src, viewer_html_dest):
            shutil.copy(viewer_html_src, viewer_html_dest)
            logging.info(f"'{viewer_html_src}' -> '{viewer_html_dest}' kopyalandı.")
    except shutil.SameFileError:
        logging.info("viewer.html zaten doğru konumda, kopyalama atlandı.")
        pass # Dosya zaten yerinde, sorun yok.
    except Exception as e:
        logging.error(f"Kritik Hata: viewer.html kopyalanamadı: {e}")
        print(f"Kritik Hata: viewer.html kopyalanamadı: {e}")
        sys.exit(1)

    # Sunucuyu modelin olduğu dizinde çalıştır
    os.chdir(file_dir)

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
    
    print("AR sunucu uygulaması kapatıldı.")


## \fn main
## \brief Uygulamanın ana giriş noktasıdır.
if __name__ == "__main__":
    # Komut satırı argümanlarını kontrol et
    # Argüman 1: --ar-server
    # Argüman 2: model_dosya_yolu
    if len(sys.argv) > 2 and sys.argv[1] == '--ar-server':
        model_file_path = sys.argv[2]
        logging.info(f"AR sunucusu başlatılıyor: {model_file_path}")
        start_ar_server(model_file_path)
    else:
        logging.info("Ana uygulama başlatıldı.")
        app = QApplication(sys.argv)
        app.setStyleSheet("""
            QMessageBox {
                background-color: #2b2b2b;
            }
            QMessageBox QLabel {
                color: #ffffff;
            }
            QMessageBox QPushButton {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #555555;
                padding: 5px;
                min-width: 70px;
            }
            QMessageBox QPushButton:hover {
                background-color: #4d4d4d;
            }
        """)
        win = MainWindow()
        win.show()
        win.occ_widget.updateGeometry()
        win.occ_widget.adjustSize()
        sys.exit(app.exec_())