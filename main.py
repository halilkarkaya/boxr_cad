## \file main.py
## \brief Ana uygulama dosyası. PyQt5 tabanlı CAD arayüzünü başlatır ve ana pencereyi yönetir.

from PyQt5.QtWidgets import QApplication  # \brief PyQt5 uygulama nesnesi için
import sys  # \brief Sistem argümanları ve çıkış işlemleri için
from arayuz_design import MainWindow  # \brief Arayüz tasarımını içe aktarır
import logging  # \brief Loglama işlemleri için
from PyQt5.QtGui import QFont

## \details
# Loglama yapılandırması: uygulama.log dosyasına INFO seviyesinde log kaydı tutar.
logging.basicConfig(
    filename='uygulama.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

## \fn main
## \brief Uygulamanın ana giriş noktasıdır.
## \details QApplication nesnesi oluşturulur, ana pencere başlatılır ve gösterilir.
if __name__ == "__main__":
    logging.info("Uygulama başlatıldı.")
    app = QApplication(sys.argv)  # \brief Uygulama nesnesini oluşturur
    win = MainWindow()            # \brief Ana pencereyi oluşturur
    win.show()                    # \brief Ana pencereyi gösterir
    win.occ_widget.updateGeometry()  # \brief OCC widget'ının geometrisini günceller
    win.occ_widget.adjustSize()      # \brief OCC widget'ının boyutunu ayarlar
    sys.exit(app.exec_())            # \brief Uygulama döngüsünü başlatır ve çıkış kodunu döndürür
