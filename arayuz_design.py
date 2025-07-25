## \file arayuz_design.py
## \brief PyQt5 ile koyu temalı, 3 panelden oluşan modern 3D model görüntüleyici arayüzü

import os
import logging

log_path = os.path.join(os.path.dirname(__file__), 'uygulama.log')
logging.basicConfig(
    filename=log_path,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

# Gerekli PyQt5 modüllerini içe aktar
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QListWidget, QFrame, QGroupBox, QSizePolicy, QFileDialog, QProgressBar, QMessageBox, QSplitter, QListWidgetItem, QCheckBox, QComboBox, QLineEdit, QSlider, QRadioButton, QButtonGroup, QScrollArea
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor, QPalette, QPixmap
from cad_viewer import dosya_secici_ac, OCCModelWidget, obj_to_stl, create_progress_bar
from OCC.Display.backend import load_backend
load_backend("pyqt5")
from OCC.Display.qtDisplay import qtViewer3d
from OCC.Extend.DataExchange import read_stl_file
from converter import obj_to_glb, stl_to_obj, obj_to_fbx

## \class MainWindow
#  \brief Ana uygulama penceresi, 3 ana panel içerir.
class MainWindow(QWidget):
    ## \brief MainWindow sınıfının kurucusu. Arayüzü başlatır.
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BOXR_CAD")  # Pencere başlığı
        self.setMinimumSize(1600, 900)   # Minimum pencere boyutu
        self.setStyleSheet("background-color: #181c24;")  # Arka plan rengi
        self.layers = []  # Katmanlar: [{name, visible, model_refs}]
        self.setAcceptDrops(True)  # Sürükle-bırak aktif
        self.initUI()  # Arayüzü başlat

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    ext = os.path.splitext(url.toLocalFile())[1].lower()
                    if ext in ['.obj', '.stl', '.step', '.stp', '.iges', '.igs']:
                        event.acceptProposedAction()
                        return
        event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    file_path = url.toLocalFile()
                    ext = os.path.splitext(file_path)[1].lower()
                    if ext in ['.obj', '.stl', '.step', '.stp', '.iges', '.igs']:
                        # Katman ekle fonksiyonunu çağır
                        self.katman_ekle_dosya_yolu(file_path)
                    else:
                        from PyQt5.QtWidgets import QMessageBox
                        QMessageBox.warning(self, "Uyarı", f"Desteklenmeyen dosya formatı: {file_path}")
        event.acceptProposedAction()

    def katman_ekle_dosya_yolu(self, dosya_yolu):
        # Dosya yolu ile katman ekle
        import logging
        from PyQt5.QtCore import QTimer
        if not dosya_yolu:
            return 

        logging.info(f"Katman olarak dosya ekleniyor: {dosya_yolu}")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(15)
        
        # Progress bar animasyonu için bir zamanlayıcı
        self._progress_value = 15
        timer = QTimer(self)
        def animate_progress():
            if self._progress_value < 90: # %90'a kadar animasyon yap
                self._progress_value += 5
                self.progress_bar.setValue(self._progress_value)
            else:
                timer.stop()
        timer.timeout.connect(animate_progress)
        timer.start(20)

        # Dosya uzantısına göre model yükleme
        ext = os.path.splitext(dosya_yolu)[1].lower()
        model_ref = None

        try:
            if ext in ['.step', '.stp', '.iges', '.igs']:
                model_ref = self.occ_widget.add_step_iges_model(dosya_yolu)
            elif ext in ['.obj', '.stl']:
                # .obj dosyaları için geçici .stl oluşturma mantığı devam ediyor
                stl_path = obj_to_stl(dosya_yolu) if ext == '.obj' else dosya_yolu
                model_ref = self.occ_widget.add_model(stl_path, model_path=dosya_yolu)
            
            if model_ref is None:
                raise ValueError("Model yüklenemedi veya desteklenmiyor.")

            # Katman oluştur ve listeye ekle
            layer_name = f"Katman {len(self.layers) + 1}"
            layer = {"name": layer_name, "visible": True, "model_refs": [model_ref]}
            self.layers.append(layer)

            # Arayüzde katman listesini güncelle
            item = QListWidgetItem(layer_name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.layer_list.addItem(item)

            logging.info(f"Model başarıyla katman olarak yüklendi: {dosya_yolu}")

        except Exception as e:
            logging.error(f"Model yüklenirken hata oluştu: {dosya_yolu} - {e}")
            QMessageBox.critical(self, "Yükleme Hatası", f"'{os.path.basename(dosya_yolu)}' yüklenirken bir hata oluştu.\n\nDetay: {e}")
        
        finally:
            # İşlem tamamlansın veya hata versin, progress bar'ı tamamla ve gizle
            timer.stop()
            self.progress_bar.setValue(100)
            QTimer.singleShot(500, lambda: self.progress_bar.setVisible(False))
            self.show_model_info_in_panel()

    ## \brief Ana arayüz düzenini ve panelleri oluşturur.
    def initUI(self):
        splitter = QSplitter(Qt.Horizontal)
        # Sol Panel
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)
        # Orta Panel
        center_panel = self.create_center_panel()
        splitter.addWidget(center_panel)
        # Sağ Panel
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)
        # Başlangıç genişlikleri (sol, orta, sağ)
        splitter.setSizes([300, 900, 400])
        # Ana layout'a splitter'ı ekle
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(splitter)

        self.setLayout(main_layout)

    ## \brief Sol paneli (logo ve dosya işlemleri) oluşturur.
    #  \return QWidget sol panel
    def create_left_panel(self):
        left_frame = QFrame()
        left_frame.setMinimumWidth(220)
        left_frame.setStyleSheet("background-color: #232836; border-radius: 12px;")

        # --- SCROLLABLE PANEL ---
        scroll_area = QScrollArea(left_frame)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet("background: transparent; border: none;")
        scroll_content = QWidget()
        vbox = QVBoxLayout(scroll_content)
        vbox.setContentsMargins(16, 16, 16, 16)
        vbox.setSpacing(12)
        # --- digimode.png logo en üste ---
        # ---
        # BOXR CAD yazısı
        boxr_label = QLabel("BOXR CAD")
        boxr_label.setFont(QFont("Arial Black", 16, QFont.Bold))
        boxr_label.setAlignment(Qt.AlignCenter)
        boxr_label.setStyleSheet("color: #FFD600; letter-spacing: 3px; margin-bottom: 8px; margin-top: 8px;")
        vbox.addWidget(boxr_label)
        # Dosya işlemleri başlığı
        title = QLabel("Dosya İşlemleri")
        title.setFont(QFont("Arial", 12, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #bfc7e6;")
        vbox.addWidget(title)
        # Dosya işlemleri butonları
        btn_names = [
            ("➕ Katman Ekle", "➕ Katman Ekle"),
            ("🔄 Dosya Dönüştür", "🔄 Dosya Dönüştür")
        ]

        btn_widgets = {}
        for text, name in btn_names:
            btn = QPushButton(text)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #353b4a;
                    color: #fff;
                    border: none;
                    border-radius: 8px;
                    padding: 12px 0 12px 18px;
                    font-size: 17px;
                    text-align: left;
                }
                QPushButton:hover {
                    background-color: #FFD600;
                    color: #232836;
                }
            """)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            vbox.addWidget(btn)
            btn_widgets[name] = btn  # Butonları sözlükte tut

        # Dönüştürme alt butonları (başta gizli)
        self.convert_sub_buttons = []
        convert_options = [
            ("🟠 GLB'ye Dönüştür", "to_glb"),
            ("🟣 FBX'e Dönüştür", "to_fbx"),
            ("🔵 OBJ'ye Dönüştür", "to_obj"),
            ("🟢 STEP'e Dönüştür", "to_step"),
            ("🟤 PLY'ye Dönüştür", "to_ply"),
            ("🟪 GLTF'ye Dönüştür", "to_gltf"),
            ("🟫 3MF'ye Dönüştür", "to_3mf"),
            ("🟦 DAE'ye Dönüştür", "to_dae"),
            ("🟧 STL'ye Dönüştür (STEP/IGES)", "step_to_stl"),
            ("🟥 OBJ'ye Dönüştür (STEP/IGES)", "step_to_obj")
        ]
        convert_btn_style = """
            QPushButton {
                background-color: #353b4a;
                color: #fff;
                border: none;
                border-radius: 8px;
                padding: 6px 0 6px 32px;
                font-size: 13px;
                margin-left: 0px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #444a5a;
                color: #fff;
            }
        """
        for idx, (text, name) in enumerate(convert_options):
            sub_btn = QPushButton(text)
            sub_btn.setStyleSheet(convert_btn_style)
            sub_btn.setVisible(False)
            sub_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            vbox.addWidget(sub_btn)
            self.convert_sub_buttons.append(sub_btn)

            # Her butonu kendi özel fonksiyonuna bağla
            if name == "to_glb":
                sub_btn.clicked.connect(self.convert_to_glb)
            elif name == "to_fbx":
                sub_btn.clicked.connect(self.convert_to_fbx)
            elif name == "to_obj":
                sub_btn.clicked.connect(self.convert_to_obj)
            elif name == "to_step":
                sub_btn.clicked.connect(self.convert_to_step)
            elif name == "to_ply":
                sub_btn.clicked.connect(self.convert_to_ply)
            elif name == "to_gltf":
                sub_btn.clicked.connect(self.convert_to_gltf)
            elif name == "to_3mf":
                sub_btn.clicked.connect(self.convert_to_3mf)
            elif name == "to_dae":
                sub_btn.clicked.connect(self.convert_to_dae)
            elif name == "step_to_stl":
                sub_btn.clicked.connect(self.convert_step_to_stl)
            elif name == "step_to_obj":
                sub_btn.clicked.connect(self.convert_step_to_obj)

        # Model Bilgileri butonu
        model_info_btn = QPushButton("👁️‍🗨️ Model Bilgileri")
        model_info_btn.setStyleSheet("""
            QPushButton {
                background-color: #353b4a;
                color: #fff;
                border: none;
                border-radius: 8px;
                padding: 12px 0 12px 18px;
                font-size: 17px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #FFD600;
                color: #232836;
            }
        """)
        model_info_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        vbox.addWidget(model_info_btn)
        model_info_btn.clicked.connect(self.show_model_info_in_panel)

        # Hakkında butonu
        about_btn = QPushButton("❔ Hakkında")
        about_btn.setStyleSheet("""
            QPushButton {
                background-color: #353b4a;
                color: #fff;
                border: none;
                border-radius: 8px;
                padding: 12px 0 12px 18px;
                font-size: 17px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #FFD600;
                color: #232836;
            }
        """)
        about_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.about_btn_style = about_btn.styleSheet()
        vbox.addWidget(about_btn)
        def show_about():
            logging.info("Hakkında butonuna tıklandı")
            html = self.logo_img_html
            html += (
                "<div style='font-family: Segoe UI; font-size: 15px; color:#bfc7e6; text-align:center;'>"
                "<p><b>Versiyon:</b> 1.0.0</p>"
                "<p>Bu uygulama çeşitli CAD formatlarını görüntülemek ve dönüştürmek için tasarlanmıştır.</p>"
                "<h3 style='color: #2196f3;'>Desteklenen formatlar:</h3>"
                "<ul style='text-align:left; margin: 0 auto 0 30px; padding-left:0;'>"
                "<li style='margin-bottom:2px;'>STEP (.step, .stp)</li>"
                "<li style='margin-bottom:2px;'>STL (.stl)</li>"
                "<li style='margin-bottom:2px;'>FBX (.fbx)</li>"
                "<li style='margin-bottom:2px;'>GLB (.glb)</li>"
                "<li style='margin-bottom:2px;'>OBJ (.obj)</li>"
                "</ul>"
                "<p style='font-size:13px; color:#fcb045;'>© 2025 digiMODE. Tüm hakları saklıdır.</p>"
                "</div>"
            )
            self.right_content_label.setText(html)
            # Log indirme butonunu kaldır
            if hasattr(self, 'log_download_btn') and self.log_download_btn is not None:
                self.log_download_btn.setParent(None)
                self.log_download_btn = None
        about_btn.clicked.connect(show_about)

        # --- YARDIM / SSS BUTONU ---
        help_btn = QPushButton("💡 Yardım / SSS")
        help_btn.setStyleSheet(about_btn.styleSheet())
        help_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        vbox.addWidget(help_btn)
        def show_help():
            logging.info("Yardım/SSS butonuna tıklandı")
            html = self.logo_img_html
            html += (
                "<div style='font-family: Segoe UI; font-size: 15px; color:#FFD600; text-align:center;'><b>Yardım & Sıkça Sorulan Sorular (SSS)</b></div>"
                "<div style='font-size:14px; color:#bfc7e6; text-align:left; margin-top:10px;'>"
                "<b>1. Katman nasıl eklenir?</b><br>"
                "Sol paneldeki '➕ Katman Ekle' butonuna tıklayın ve eklemek istediğiniz dosyayı seçin.<br><br>"
                "<b>2. Dosya formatları arasında nasıl dönüştürme yapabilirim?</b><br>"
                "'🔄 Dosya Dönüştür' butonuna tıklayın, ardından istediğiniz dönüştürme seçeneğini seçin.<br><br>"
                "<b>3. Modeli nasıl döndürebilirim veya taşıyabilirim?</b><br>"
                "Sağ paneldeki ok ve döndürme butonlarını kullanarak seçili katmanı hareket ettirebilir veya döndürebilirsiniz.<br><br>"
                "<b>4. Ölçüm nasıl yapılır?</b><br>"
                "'📏 Ölçüm Yap' butonuna tıklayın ve altındaki ölçüm türlerinden birini seçin. Ardından model üzerinde seçim yapın.<br><br>"
                "<b>5. Renk veya arka plan nasıl değiştirilir?</b><br>"
                "Sağ paneldeki '🎨 Renk Seç' veya '🖼️ Arka Plan Rengi' butonlarını kullanabilirsiniz.<br><br>"
                "<b>6. Loglara nasıl ulaşabilirim?</b><br>"
                "Sol paneldeki '📝 Loglar' butonuna tıklayarak uygulama loglarını görüntüleyebilir ve kaydedebilirsiniz.<br><br>"
                "<b>7. Sık karşılaşılan sorunlar ve çözümleri</b><br>"
                "- <b>Model yüklenmiyor:</b> Dosya formatının desteklendiğinden emin olun.<br>"
                "- <b>Dönüştürme başarısız:</b> Dosyanın bozuk olmadığından ve yeterli disk alanı olduğundan emin olun.<br>"
                "- <b>Arayüzde yazılar görünmüyor:</b> Ekran çözünürlüğünüzü ve ölçek ayarlarınızı kontrol edin.<br><br>"
                "<b>Diğer sorularınız için:</b> Lütfen geliştirici ile iletişime geçin.<br>"
                "</div>"
            )
            self.right_content_label.setText(html)
        help_btn.clicked.connect(show_help)

        # Mesafe Ölç butonunu kaldır, yerine Ölçüm Yap ve altına yeni butonlar ekle
        # Eski mesafe_btn ve ilgili kodlar kaldırıldı
        self.olcum_btn = QPushButton("📏 Ölçüm Yap")
        self.olcum_btn.setStyleSheet(about_btn.styleSheet())
        self.olcum_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        vbox.insertWidget(vbox.indexOf(about_btn), self.olcum_btn)
        # Altına üç yeni buton (başta gizli)
        self.olcum_sub_buttons = []
        olcum_sub_btn_style = """
            QPushButton {
                background-color: #444a5a;
                color: #fff;
                border: none;
                border-radius: 8px;
                padding: 6px 0 6px 32px;
                font-size: 13px;
                margin-left: 0px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #FFD600;
                color: #232836;
            }
        """
        self.kenar_olc_btn = QPushButton("📏 Kenar Ölç")
        self.kenar_olc_btn.setStyleSheet(olcum_sub_btn_style)
        self.kenar_olc_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.kenar_olc_btn.setVisible(False)
        vbox.insertWidget(vbox.indexOf(self.olcum_btn)+1, self.kenar_olc_btn)
        self.olcum_sub_buttons.append(self.kenar_olc_btn)
        self.vertex_olc_btn = QPushButton("🟡 Vertex Ölç")
        self.vertex_olc_btn.setStyleSheet(olcum_sub_btn_style)
        self.vertex_olc_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.vertex_olc_btn.setVisible(False)
        vbox.insertWidget(vbox.indexOf(self.kenar_olc_btn)+1, self.vertex_olc_btn)
        self.olcum_sub_buttons.append(self.vertex_olc_btn)
        self.alan_olc_btn = QPushButton("🟦 Alan Ölç")
        self.alan_olc_btn.setStyleSheet(olcum_sub_btn_style)
        self.alan_olc_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.alan_olc_btn.setVisible(False)
        vbox.insertWidget(vbox.indexOf(self.vertex_olc_btn)+1, self.alan_olc_btn)
        self.olcum_sub_buttons.append(self.alan_olc_btn)
        # Ölçüm alt butonlarını aç/kapa fonksiyonu
        def toggle_olcum_sub_buttons():
            visible = not self.olcum_sub_buttons[0].isVisible()
            for b in self.olcum_sub_buttons:
                b.setVisible(visible)
        self.olcum_btn.clicked.connect(toggle_olcum_sub_buttons)

        # Hakkında butonunun üstüne Ortala butonu ekle
        self.ortala_btn = QPushButton("🎯 Ortala")
        self.ortala_btn.setStyleSheet(about_btn.styleSheet())
        self.ortala_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        vbox.insertWidget(vbox.indexOf(about_btn), self.ortala_btn)
        def ortala_model():
            if hasattr(self, 'occ_widget') and hasattr(self.occ_widget, 'display'):
                self.occ_widget.display.FitAll()
                self.occ_widget.display.Repaint()
        self.ortala_btn.clicked.connect(ortala_model)

        # Hakkında butonunun üstüne Loglar butonu ekle
        logs_btn = QPushButton("📝 Loglar")
        logs_btn.setStyleSheet(about_btn.styleSheet())
        logs_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        vbox.insertWidget(vbox.indexOf(about_btn), logs_btn)
        def show_logs():
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    log_lines = f.readlines()
                # Son 'Uygulama başlatıldı.' satırını bul
                start_idx = 0
                for i in range(len(log_lines)-1, -1, -1):
                    if 'Uygulama başlatıldı.' in log_lines[i]:
                        start_idx = i + 1
                        break
                last_logs = log_lines[start_idx:]
                log_text = ''.join(last_logs)
                if len(log_text) > 2000:
                    log_text = log_text[-2000:]
                html = self.logo_img_html
                html += f"<div style='font-size:13px; color:#FFD600; background:#232836;'><pre>{log_text}</pre></div>"
            except Exception as e:
                html = self.logo_img_html
                html += f"<span style='color:red;'>Log dosyası okunamadı: {e}</span>"
            self.right_content_label.setText(html)
            # Sadece burada log indirme butonunu ekle, başka yerde varsa kaldır
            if hasattr(self, 'log_download_btn') and self.log_download_btn is not None:
                self.log_download_btn.setParent(None)
            from PyQt5.QtWidgets import QPushButton, QFileDialog
            self.log_download_btn = QPushButton('Tüm Logları İndir')
            self.log_download_btn.setStyleSheet('background-color:#FFD600; color:#232836; font-weight:bold; border-radius:8px; padding:8px; margin-top:12px;')
            def download_logs():
                try:
                    save_path, _ = QFileDialog.getSaveFileName(self, 'Logları Kaydet', 'uygulama.log', 'Log Dosyası (*.log);;Tüm Dosyalar (*)')
                    if save_path:
                        with open(log_path, 'r', encoding='utf-8') as src, open(save_path, 'w', encoding='utf-8') as dst:
                            dst.write(src.read())
                except Exception as e:
                    from PyQt5.QtWidgets import QMessageBox
                    QMessageBox.warning(self, 'Hata', f'Log dosyası kaydedilemedi: {e}')
            self.log_download_btn.clicked.connect(download_logs)
            self.right_top_vbox.addWidget(self.log_download_btn)
        logs_btn.clicked.connect(show_logs)

        # Dönüştürme alt butonlarını aç/kapa fonksiyonu
        convert_btn = btn_widgets["🔄 Dosya Dönüştür"]
        def toggle_sub_buttons():
            visible = not self.convert_sub_buttons[0].isVisible()
            for b in self.convert_sub_buttons:
                b.setVisible(visible)
        convert_btn.clicked.connect(toggle_sub_buttons)

        # Dosya Aç butonunu instance değişkeni olarak sakla ve fonksiyona bağla
        self.open_btn = btn_widgets["➕ Katman Ekle"]
        def katman_ekle_buton_fonksiyonu():
            dosya_yolu = dosya_secici_ac(parent=self)
            self.katman_ekle_dosya_yolu(dosya_yolu) # Ana yükleme fonksiyonunu çağır
        self.open_btn.clicked.connect(katman_ekle_buton_fonksiyonu)

        # --- 3D Yazıcıya Gönder Butonu ---
        import subprocess
        import json
        self.printer_btn = QPushButton("🖨️ 3D Yazıcıya Gönder")
        self.printer_btn.setStyleSheet(about_btn.styleSheet())
        self.printer_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        vbox.insertWidget(vbox.indexOf(help_btn)+1, self.printer_btn)
        def send_to_printer():
            from PyQt5.QtWidgets import QFileDialog, QMessageBox
            import tempfile, os
            # Ayar dosyası
            config_path = os.path.join(os.path.expanduser("~"), ".boxr_cad_printer.json")
            # Yazıcı yolu ayarlı mı?
            printer_path = None
            if os.path.exists(config_path):
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        printer_path = data.get("printer_path")
                except Exception:
                    printer_path = None
            if not printer_path or not os.path.exists(printer_path):
                # Her zaman kullanıcıdan doğru exe'yi seçmesini iste
                while True:
                    default_cura = r"D:\Yeni klasör (3)\UltiMaker Cura 5.10.1\UltiMaker-Cura.exe"
                    printer_path, _ = QFileDialog.getOpenFileName(self, "3D Yazıcı Yazılımını Seç (Cura, PrusaSlicer, vs.)", default_cura, "Uygulama (*.exe)")
                    if not printer_path:
                        QMessageBox.warning(self, "Yazıcı Yazılımı Gerekli", "3D yazıcı yazılımı seçilmedi.")
                        return
                    exe_name = os.path.basename(printer_path).lower()
                    allowed = ["ultimaker-cura.exe", "cura.exe", "prusa-slicer.exe", "bambustudio.exe", "ideamaker.exe", "photonworkshop.exe", "creality slicer.exe"]
                    if any(name in exe_name for name in allowed):
                        break
                    else:
                        QMessageBox.warning(self, "Yanlış Dosya", "Lütfen UltiMaker-Cura.exe, Cura.exe, PrusaSlicer.exe veya başka bir dilimleyici programın ana .exe dosyasını seçin. CuraEngine.exe veya benzeri motor dosyalarını seçmeyin.")
                # Ayar olarak kaydet
                try:
                    with open(config_path, "w", encoding="utf-8") as f:
                        json.dump({"printer_path": printer_path}, f)
                except Exception:
                    pass
            # Aktif katmanın model dosyasını bul
            idx = self.layer_list.currentRow()
            if idx < 0 or idx >= len(self.layers):
                QMessageBox.warning(self, "Uyarı", "Lütfen yazıcıya göndermek için bir katman/model seçin.")
                return
            layer = self.layers[idx]
            # Katmandaki ilk modelin yolunu al
            model_path = None
            if "model_refs" in layer and hasattr(self.occ_widget, 'model_path'):
                model_path = self.occ_widget.model_path
            if not model_path or not os.path.exists(model_path):
                QMessageBox.warning(self, "Hata", "Model dosyası bulunamadı.")
                return
            # STL olarak geçici kaydet
            import trimesh
            temp_dir = tempfile.gettempdir()
            temp_stl = os.path.join(temp_dir, f"boxr_cad_export_{idx}.stl")
            try:
                mesh = trimesh.load(model_path, force='mesh')
                mesh.export(temp_stl, file_type='stl')
            except Exception as e:
                QMessageBox.warning(self, "Hata", f"STL dosyası oluşturulamadı: {e}")
                return
            # STL dosyasını varsayılan programda aç
            try:
                import os
                os.startfile(temp_stl)
            except Exception as e:
                QMessageBox.warning(self, "Hata", f"STL dosyası varsayılan programda açılamadı: {e}")
                return
            QMessageBox.information(self, "Başarılı", "Model STL dosyası olarak kaydedildi ve varsayılan 3D yazıcı yazılımında açıldı. Eğer açılmazsa STL dosyasını elle açabilirsiniz: " + temp_stl)
        self.printer_btn.clicked.connect(send_to_printer)

        # --- Kesit Düzlemi Arayüzü ---
        self.section_btn = QPushButton("✂️ Kesit Düzlemi")
        self.section_btn.setStyleSheet(about_btn.styleSheet())
        self.section_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        vbox.addWidget(self.section_btn)
        # Eksen seçici
        self.section_axis = QComboBox()
        self.section_axis.addItems(["Z", "Y", "X"])
        self.section_axis.setVisible(False)
        vbox.addWidget(self.section_axis)
        # Slider
        self.section_slider = QSlider(Qt.Horizontal)
        self.section_slider.setMinimum(-100)
        self.section_slider.setMaximum(100)
        self.section_slider.setValue(0)
        self.section_slider.setVisible(False)
        vbox.addWidget(self.section_slider)
        # Label
        self.section_label = QLabel("Düzlem Konumu: 0")
        self.section_label.setStyleSheet("color:#FFD600; font-size:13px;")
        self.section_label.setVisible(False)
        vbox.addWidget(self.section_label)
        # --- KESİTİ KAYDET BUTONU ---
        self.save_section_btn = QPushButton("💾 Kesiti Kaydet")
        self.save_section_btn.setStyleSheet(about_btn.styleSheet())
        self.save_section_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.save_section_btn.setVisible(False)
        vbox.addWidget(self.save_section_btn)
        # OCC tarafı: clip_plane referansı
        self.clip_plane = None
        def toggle_section():
            if self.section_slider.isVisible():
                # Kapat
                self.section_slider.setVisible(False)
                self.section_axis.setVisible(False)
                self.section_label.setVisible(False)
                self.save_section_btn.setVisible(False)
                self.section_btn.setText("✂️ Kesit Düzlemi")
                # OCC: clip_plane kaldır
                try:
                    if self.clip_plane is not None:
                        self.occ_widget.display.View.RemoveClipPlane(self.clip_plane)
                        self.occ_widget.display.View.Redraw()
                        self.clip_plane = None
                except Exception:
                    pass
            else:
                # Aç
                self.section_slider.setVisible(True)
                self.section_axis.setVisible(True)
                self.section_label.setVisible(True)
                self.save_section_btn.setVisible(True)
                self.section_btn.setText("❌ Kesiti Kapat")
                # OCC: clip_plane oluştur
                try:
                    from OCC.Core.gp import gp_Pln, gp_Pnt, gp_Dir
                    from OCC.Core.Graphic3d import Graphic3d_ClipPlane
                    axis = self.section_axis.currentText()
                    pos = self.section_slider.value()
                    if axis == "Z":
                        origin = gp_Pnt(0, 0, pos)
                        normal = gp_Dir(0, 0, 1)
                    elif axis == "Y":
                        origin = gp_Pnt(0, pos, 0)
                        normal = gp_Dir(0, 1, 0)
                    else:
                        origin = gp_Pnt(pos, 0, 0)
                        normal = gp_Dir(1, 0, 0)
                    plane = gp_Pln(origin, normal)
                    self.clip_plane = Graphic3d_ClipPlane(plane)
                    self.occ_widget.display.View.AddClipPlane(self.clip_plane)
                    self.occ_widget.display.View.Redraw()
                except Exception as e:
                    print("Kesit düzlemi hatası:", e)
        self.section_btn.clicked.connect(toggle_section)
        def update_section():
            # Slider veya eksen değiştiğinde düzlemi güncelle
            self.section_label.setText(f"Düzlem Konumu: {self.section_slider.value()}")
            if self.clip_plane is not None:
                try:
                    from OCC.Core.gp import gp_Pln, gp_Pnt, gp_Dir
                    axis = self.section_axis.currentText()
                    pos = self.section_slider.value()
                    if axis == "Z":
                        origin = gp_Pnt(0, 0, pos)
                        normal = gp_Dir(0, 0, 1)
                    elif axis == "Y":
                        origin = gp_Pnt(0, pos, 0)
                        normal = gp_Dir(0, 1, 0)
                    else:
                        origin = gp_Pnt(pos, 0, 0)
                        normal = gp_Dir(1, 0, 0)
                    plane = gp_Pln(origin, normal)
                    self.clip_plane.SetEquation(plane)
                    self.occ_widget.display.View.Redraw()
                except Exception as e:
                    print("Kesit düzlemi güncelleme hatası:", e)
        self.section_slider.valueChanged.connect(update_section)
        self.section_axis.currentIndexChanged.connect(update_section)
        # --- KESİTİ KAYDET BUTONU FONKSİYONU ---
        def save_section():
            if self.clip_plane is None:
                QMessageBox.warning(self, "Uyarı", "Önce bir kesit düzlemi oluşturmalısınız!")
                return
            # Seçili katmanın modelini al
            def get_selected_layer_model_refs():
                idx = self.layer_list.currentRow()
                if idx < 0 or idx >= len(self.layers):
                    QMessageBox.warning(self, "Uyarı", "Lütfen önce bir katman seçin.")
                    return None
                return self.layers[idx]["model_refs"]
            model_refs = get_selected_layer_model_refs()
            if not model_refs:
                return
            model_ref = model_refs[0]  # Katmandaki ilk model
            # Modelin shape'ini al
            model_shape = None
            if hasattr(self.occ_widget, 'get_active_shape') and hasattr(model_ref, 'Shape'):
                model_shape = model_ref.Shape()
            if model_shape is None:
                QMessageBox.warning(self, "Uyarı", "Seçili katmanın geçerli bir modeli yok!")
                return
            try:
                from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
                from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
                from OCC.Core.StlAPI import StlAPI_Writer
                from OCC.Core.gp import gp_Pln, gp_Pnt, gp_Dir
                # Düzlemi oluştur
                axis = self.section_axis.currentText()
                pos = self.section_slider.value()
                if axis == "Z":
                    origin = gp_Pnt(0, 0, pos)
                    normal = gp_Dir(0, 0, 1)
                elif axis == "Y":
                    origin = gp_Pnt(0, pos, 0)
                    normal = gp_Dir(0, 1, 0)
                else:
                    origin = gp_Pnt(pos, 0, 0)
                    normal = gp_Dir(1, 0, 0)
                plane = gp_Pln(origin, normal)
                from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
                face = BRepBuilderAPI_MakeFace(plane, -1000, 1000, -1000, 1000).Face()
                # Modeli düzlemle kes (cut)
                cut = BRepAlgoAPI_Cut(model_shape, face)
                cut_shape = cut.Shape()
                # STL olarak kaydet
                file_path, _ = QFileDialog.getSaveFileName(self, "Kesiti STL Olarak Kaydet", "kesit.stl", "STL Dosyası (*.stl)")
                if not file_path:
                    return
                # Meshle
                mesh = BRepMesh_IncrementalMesh(cut_shape, 0.1)
                mesh.Perform()
                # Yaz
                writer = StlAPI_Writer()
                writer.Write(cut_shape, file_path)
                # --- KESİTİ YENİ KATMAN OLARAK EKLE ---
                stl_path = file_path
                layer_name = f"Kesit Katmanı {len(self.layers)+1}"
                model_ref = self.occ_widget.add_model(stl_path, model_path=stl_path)
                layer = {"name": layer_name, "visible": True, "model_refs": [model_ref]}
                self.layers.append(layer)
                # Katman paneline ekle
                def add_layer_item():
                    item = QListWidgetItem(layer_name)
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                    item.setCheckState(Qt.Checked)
                    self.layer_list.addItem(item)
                QTimer.singleShot(0, add_layer_item)
                QMessageBox.information(self, "Başarılı", f"Kesit STL olarak kaydedildi ve yeni katman olarak eklendi!\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Kesit kaydedilemedi:\n{e}")
        self.save_section_btn.clicked.connect(save_section)

        # Sol panelde (create_left_panel) vbox.addStretch() en sona taşınacak
        vbox.addStretch()
        scroll_area.setWidget(scroll_content)
        layout = QVBoxLayout(left_frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(scroll_area)
        return left_frame 

    ## \brief Orta paneli (3D model görüntüleme alanı) oluşturur.
    #  \return QWidget orta panel
    def create_center_panel(self):
        center_frame = QFrame()
        vbox = QVBoxLayout(center_frame)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)
        try:
            self.occ_widget = OCCModelWidget(self)
            vbox.addWidget(self.occ_widget)
            # Progress Bar'ı center panelin altına ekle
            from PyQt5.QtWidgets import QProgressBar
            self.progress_bar = QProgressBar(self)
            self.progress_bar.setMinimum(0)
            self.progress_bar.setMaximum(100)
            self.progress_bar.setValue(0)
            self.progress_bar.setVisible(False)
            self.progress_bar.setStyleSheet('QProgressBar { background: #232836; color: #FFD600; border-radius: 8px; height: 22px; font-size: 15px; } QProgressBar::chunk { background: #FFD600; border-radius: 8px; }')
            vbox.addWidget(self.progress_bar)
            # Varsayılan olarak digiMODE.obj dosyasını yükle
            default_obj = os.path.join(os.path.dirname(__file__), 'digiMODE.obj')
            if os.path.exists(default_obj):
                stl_path = obj_to_stl(default_obj)
                model_ref = self.occ_widget.add_model(stl_path, model_path=default_obj)
                # 1. katman olarak ekle
                layer_name = "Katman 1 (Varsayılan)"
                layer = {"name": layer_name, "visible": True, "model_refs": [model_ref]}
                self.layers.append(layer)
                # Katman paneline ekle (layer_list kesinlikle sağ panelde oluşturulduktan sonra ekleniyor)
                def add_first_layer_item():
                    item = QListWidgetItem(layer_name)
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                    item.setCheckState(Qt.Checked)
                    self.layer_list.addItem(item)
                QTimer.singleShot(0, add_first_layer_item)
                # Sağ panelde model bilgilerini göster
                if hasattr(self, 'right_content_label'):
                    info = self.occ_widget.get_model_info()
                    html = "<div style='font-size:15px; color:#bfc7e6;'><b>Model Bilgileri:</b><br>"
                    for k, v in info.items():
                        html += f"<b>{k}:</b> {v}<br>"
                    html += "</div>"
                    self.right_content_label.setText(html)
            # Mesafe ölçümü tamamlandığında sonucu sağ panelde göster
            self.occ_widget.mesafe_olcum_tamamlandi.connect(self.mesafe_sonuc_goster)
        except Exception as e:
            hata_label = QLabel(f"Model yüklenemedi:\n{e}")
            hata_label.setStyleSheet("color: red; font-size: 16px;")
            hata_label.setAlignment(Qt.AlignCenter)
            vbox.addWidget(hata_label, 1)
        return center_frame

    ## \brief Sağ paneli (model bilgileri ve materyal görünümü) oluşturur.
    #  \return QWidget sağ panel
    def create_right_panel(self):
        self.right_frame = QFrame()
        self.right_frame.setMinimumWidth(180)
        self.right_vbox = QVBoxLayout(self.right_frame)
        self.right_vbox.setContentsMargins(28, 28, 28, 28)
        self.right_vbox.setSpacing(10)
        # Üst ve alt bölümler için iki ayrı layout
        self.right_top_vbox = QVBoxLayout()
        self.right_top_vbox.setSpacing(10)
        self.right_bottom_vbox = QVBoxLayout()
        self.right_bottom_vbox.setSpacing(10)

        # --- digimode.png logo en üste ---
        # Logo artık içeriklerin üstünde HTML olarak gösterilecek
        self.logo_img_html = f"<div style='text-align:center; margin-bottom:10px;'><img src='file:///{os.path.join(os.path.dirname(__file__), 'digimode.png').replace(os.sep, '/')}' width='120'/></div>"
        # ---
        # Tek bir içerik alanı QLabel
        self.right_content_label = QLabel()
        self.right_content_label.setWordWrap(True)
        self.right_content_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.right_content_label.setStyleSheet("background: #232836; color: #bfc7e6; border-radius: 10px; padding: 12px;")
        # Kaydırılabilir alan ekle
        self.right_scroll_area = QScrollArea()
        self.right_scroll_area.setWidgetResizable(True)
        self.right_scroll_area.setStyleSheet("background: #232836; border-radius: 10px;")
        self.right_scroll_area.setWidget(self.right_content_label)
        self.right_top_vbox.addWidget(self.right_scroll_area, 1)
        # Başlangıçta hakkında göster
        self.right_content_label.setText(
            self.logo_img_html +
            "<div style='font-family: Segoe UI; font-size: 15px; color:#bfc7e6; text-align:center;'>"
            "<p><b>Versiyon:</b> 1.0.0</p>"
            "<p>Bu uygulama çeşitli CAD formatlarını görüntülemek ve dönüştürmek için tasarlanmıştır.</p>"
            "<h3 style='color: #2196f3;'>Desteklenen formatlar:</h3>"
            "<ul style='text-align:left; margin: 0 auto 0 30px; padding-left:0;'>"
            "<li style='margin-bottom:2px;'>STEP (.step, .stp)</li>"
            "<li style='margin-bottom:2px;'>STL (.stl)</li>"
            "<li style='margin-bottom:2px;'>FBX (.fbx)</li>"
            "<li style='margin-bottom:2px;'>GLB (.glb)</li>"
            "<li style='margin-bottom:2px;'>OBJ (.obj)</li>"
            "</ul>"
            "<p style='font-size:13px; color:#fcb045;'>© 2025 digiMODE. Tüm hakları saklıdır.</p>"
            "</div>"
        )
        self.right_top_vbox.addStretch()
        # Alt bölüme butonlar eklenecek
        from PyQt5.QtWidgets import QColorDialog, QPushButton, QMessageBox
        # self.right_bottom_vbox.addStretch() kaldırıldı veya en sona taşındı
        self.color_btn = QPushButton("🎨 Renk Seç")
        self.color_btn.setStyleSheet(self.about_btn_style if hasattr(self, 'about_btn_style') else "")
        self.color_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.right_bottom_vbox.addWidget(self.color_btn)
        def renk_sec_ve_uygula():
            color = QColorDialog.getColor()
            if color.isValid():
                selected_idx = self.layer_list.currentRow()
                if selected_idx < 0 or selected_idx >= len(self.layers):
                    QMessageBox.warning(self, "Uyarı", "Lütfen renk vermek için bir katman seçin.")
                    return
                layer = self.layers[selected_idx]
                for model_ref in layer["model_refs"]:
                    if hasattr(self.occ_widget, 'set_model_color'):
                        self.occ_widget.set_model_color(model_ref, color)
        self.color_btn.clicked.connect(renk_sec_ve_uygula)
        
        # --- Arka Plan Rengi Butonu ---
        self.bgcolor_btn = QPushButton("🖼️ Arka Plan Rengi")
        self.bgcolor_btn.setStyleSheet(self.about_btn_style if hasattr(self, 'about_btn_style') else "")
        self.bgcolor_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.right_bottom_vbox.addWidget(self.bgcolor_btn)
        def arka_plan_rengi_sec():
            color = QColorDialog.getColor()
            if color.isValid() and hasattr(self, 'occ_widget'):
                r = color.red() / 255.0
                g = color.green() / 255.0
                b = color.blue() / 255.0
                if hasattr(self.occ_widget.display, 'View'):
                    from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB
                    self.occ_widget.display.View.SetBackgroundColor(Quantity_Color(r, g, b, Quantity_TOC_RGB))
                    self.occ_widget.display.Repaint()
        self.bgcolor_btn.clicked.connect(arka_plan_rengi_sec)

        # --- SEÇİLİ KATMANI SİL BUTONU ---
        self.delete_layer_btn = QPushButton("🗑️ Seçili Katmanı Sil")
        self.delete_layer_btn.setStyleSheet(self.about_btn_style if hasattr(self, 'about_btn_style') else "")
        self.delete_layer_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.right_bottom_vbox.addWidget(self.delete_layer_btn)
        def secili_katmani_sil():
            idx = self.layer_list.currentRow()
            if idx < 0 or idx >= len(self.layers):
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Uyarı", "Lütfen silmek için bir katman seçin.")
                return
            # Model varsa 3D görünümden kaldır
            for ref in self.layers[idx]["model_refs"]:
                if hasattr(self.occ_widget, 'display'):
                    self.occ_widget.display.Context.Remove(ref, True)
            if hasattr(self.occ_widget, 'display'):
                self.occ_widget.display.Context.UpdateCurrentViewer()
            self.layers.pop(idx)
            self.layer_list.takeItem(idx)
        self.delete_layer_btn.clicked.connect(secili_katmani_sil)

        # Üst ve alt layoutları ayıran çizgi
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setFrameShadow(QFrame.Sunken)
        divider.setStyleSheet("color: #353b4a; background: #353b4a; min-height:2px; max-height:2px;")
        self.right_vbox.addLayout(self.right_top_vbox, 1)
        self.right_vbox.addWidget(divider)
        self.right_vbox.addLayout(self.right_bottom_vbox, 1)
        # (Sağ panelin altına katman kontrol butonları ve layer_list ekle)
        # Katman kontrol butonları için yatay kutu
        katman_btn_layout = QHBoxLayout()
        katman_btn_layout.setSpacing(6)
        btn_style = """
            QPushButton {
                background-color: #353b4a;
                color: #FFD600;
                border: none;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 16px;
                min-width: 28px;
                min-height: 28px;
            }
            QPushButton:hover {
                background-color: #FFD600;
                color: #232836;
            }
        """
        self.up_btn = QPushButton("↑")
        self.up_btn.setToolTip("Katmanı Yukarı Taşı")
        self.up_btn.setStyleSheet(btn_style)
        katman_btn_layout.addWidget(self.up_btn)
        self.down_btn = QPushButton("↓")
        self.down_btn.setToolTip("Katmanı Aşağı Taşı")
        self.down_btn.setStyleSheet(btn_style)
        katman_btn_layout.addWidget(self.down_btn)
        self.left_btn = QPushButton("←")
        self.left_btn.setToolTip("Katmanı Sola Taşı")
        self.left_btn.setStyleSheet(btn_style)
        katman_btn_layout.addWidget(self.left_btn)
        self.right_btn = QPushButton("→")
        self.right_btn.setToolTip("Katmanı Sağa Taşı")
        self.right_btn.setStyleSheet(btn_style)
        katman_btn_layout.addWidget(self.right_btn)
        self.rotate_x_btn = QPushButton("X↻")
        self.rotate_x_btn.setToolTip("Katmanı X Ekseninde Döndür")
        self.rotate_x_btn.setStyleSheet(btn_style)
        katman_btn_layout.addWidget(self.rotate_x_btn)
        self.rotate_y_btn = QPushButton("Y↻")
        self.rotate_y_btn.setToolTip("Katmanı Y Ekseninde Döndür")
        self.rotate_y_btn.setStyleSheet(btn_style)
        katman_btn_layout.addWidget(self.rotate_y_btn)
        self.rotate_z_btn = QPushButton("Z↻")
        self.rotate_z_btn.setToolTip("Katmanı Z Ekseninde Döndür")
        self.rotate_z_btn.setStyleSheet(btn_style)
        katman_btn_layout.addWidget(self.rotate_z_btn)
        self.right_bottom_vbox.addLayout(katman_btn_layout)

        # --- Katman Hareket ve Döndürme Fonksiyonları ---
        import math
        from PyQt5.QtWidgets import QMessageBox
        def get_selected_layer_model_refs():
            idx = self.layer_list.currentRow()
            if idx < 0 or idx >= len(self.layers):
                QMessageBox.warning(self, "Uyarı", "Lütfen önce bir katman seçin.")
                return None
            return self.layers[idx]["model_refs"]
        def move_selected_layer(dx=0, dy=0, dz=0):
            model_refs = get_selected_layer_model_refs()
            if not model_refs:
                return
            for ref in model_refs:
                if hasattr(self.occ_widget, 'move_model'):
                    self.occ_widget.move_model(ref, dx, dy, dz)
        def rotate_selected_layer(axis='x', angle_deg=15):
            model_refs = get_selected_layer_model_refs()
            if not model_refs:
                return
            for ref in model_refs:
                if hasattr(self.occ_widget, 'rotate_model'):
                    self.occ_widget.rotate_model(ref, axis, angle_deg)
        self.up_btn.clicked.connect(lambda: move_selected_layer(dy=10))
        self.down_btn.clicked.connect(lambda: move_selected_layer(dy=-10))
        self.left_btn.clicked.connect(lambda: move_selected_layer(dx=-10))
        self.right_btn.clicked.connect(lambda: move_selected_layer(dx=10))
        self.rotate_x_btn.clicked.connect(lambda: rotate_selected_layer('x', 15))
        self.rotate_y_btn.clicked.connect(lambda: rotate_selected_layer('y', 15))
        self.rotate_z_btn.clicked.connect(lambda: rotate_selected_layer('z', 15))
        # Katmanlar başlığı ve listesi
        self.layer_list = QListWidget()
        self.layer_list.setStyleSheet("""
            QListWidget {
                background: #181c24;
                color: #FFD600;
                border: 2px solid #353b4a;
                border-radius: 10px;
                font-size: 15px;
                margin-bottom: 10px;
                padding: 6px;
            }
            QListWidget::item:selected {
                background: #353b4a;
                color: #FFD600;
                border-radius: 8px;
            }
        """)
        self.layer_list.setFixedHeight(100)
        self.right_bottom_vbox.addWidget(self.layer_list)
        # Katman görünürlüğü toggle
        def on_layer_check(item):
            idx = self.layer_list.row(item)
            visible = item.checkState() == Qt.Checked
            self.layers[idx]["visible"] = visible
            for ref in self.layers[idx]["model_refs"]:
                self.occ_widget.set_model_visible(ref, visible)
        self.layer_list.itemChanged.connect(on_layer_check)
        # Katmanlar kutusunda sağ tık menüsü ile katman silme
        self.layer_list.setContextMenuPolicy(Qt.CustomContextMenu)
        def katman_context_menu(point):
            idx = self.layer_list.indexAt(point).row()
            if idx < 0 or idx >= len(self.layers):
                return
            from PyQt5.QtWidgets import QMenu
            menu = QMenu()
            sil_action = menu.addAction("🗑️ Katmanı Sil")
            action = menu.exec_(self.layer_list.mapToGlobal(point))
            if action == sil_action:
                # Katmanı ve modellerini kaldır
                for ref in self.layers[idx]["model_refs"]:
                    self.occ_widget.display.Context.Remove(ref, True)
                self.occ_widget.display.Context.UpdateCurrentViewer()
                self.layers.pop(idx)
                self.layer_list.takeItem(idx)
        self.layer_list.customContextMenuRequested.connect(katman_context_menu)

        # Ölçüm alt butonlarına (Kenar Ölç, Vertex Ölç, Alan Ölç) tıklandığında seçim modunu değiştir (kenar:2, vertex:1, yüzey:4).
        self.kenar_olc_btn.clicked.connect(lambda: (
    setattr(self.occ_widget, 'active_measure', 'edge'),
    self.occ_widget.set_selection_mode(2),
    self.occ_widget.set_measure_mode(True),
    self.right_content_label.setText('<div style="color:#FFD600; font-size:16px;">Bir kenar seçin, seçtiğiniz kenarın özellikleri burada gözükecek.</div>')
))
        self.vertex_olc_btn.clicked.connect(lambda: (
    setattr(self.occ_widget, 'active_measure', 'vertex'),
    self.occ_widget.set_selection_mode(1),
    self.occ_widget.set_measure_mode(True),
    self.right_content_label.setText('<div style="color:#FFD600; font-size:16px;">Bir vertex seçin, tüm bilgileri burada gözükecek.</div>')
))
        self.alan_olc_btn.clicked.connect(lambda: (
    setattr(self.occ_widget, 'active_measure', 'face'),
    self.occ_widget.set_selection_mode(4),
    self.occ_widget.set_measure_mode(True),
    self.right_content_label.setText('<div style="color:#FFD600; font-size:16px;">Bir yüzey seçin, tüm bilgileri burada gözükecek.</div>')
))
        # 2 Nokta Mesafe butonunu ve bağlantılarını kaldır
        # self.mesafe_btn = QPushButton("🔴 2 Nokta Mesafe")
        # self.mesafe_btn.setStyleSheet(olcum_sub_btn_style)
        # self.mesafe_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        # self.mesafe_btn.setVisible(False)
        # vbox.insertWidget(vbox.indexOf(self.alan_olc_btn)+1, self.mesafe_btn)
        # self.olcum_sub_buttons.append(self.mesafe_btn)
        # self.mesafe_btn.clicked.connect(lambda: (
        #     setattr(self.occ_widget, 'active_measure', 'two_point'),
        #     self.occ_widget.set_selection_mode(1),
        #     self.occ_widget.set_measure_mode(True),
        #     self.right_content_label.setText('<div style="color:#FFD600; font-size:16px;">İki nokta seçin, aralarındaki mesafe burada gözükecek.</div>')
        # ))

        # Sağ panelde (create_right_panel) self.right_top_vbox.addStretch() ve self.right_bottom_vbox.addStretch() en sona taşınacak
        self.right_top_vbox.addStretch()
        self.right_bottom_vbox.addStretch()

        return self.right_frame

    # MainWindow'un metodu olarak ekle:
    def mesafe_olc(self):
        if hasattr(self, 'occ_widget'):
            self.occ_widget.set_measure_mode(True)
            self.right_content_label.setText('<div style="color:#FFD600; font-size:16px;">Lütfen ölçmek için iki nokta seçin.</div>')

    def mesafe_sonuc_goster(self, mesafe):
        if hasattr(self, 'right_content_label'):
            html = self.logo_img_html
            html += f'<div style="color:#FFD600; font-size:18px;"><b>İki nokta arası mesafe:</b> {mesafe:.2f} birim</div>'
            self.right_content_label.setText(html)
        # Mesafe ölçümü tamamlandığında butonun rengini eski haline döndür
        if hasattr(self, 'olcum_btn') and hasattr(self, 'about_btn_style'):
            self.olcum_btn.setStyleSheet(self.about_btn_style)
        # Log indirme butonunu kaldır
        if hasattr(self, 'log_download_btn') and self.log_download_btn is not None:
            self.log_download_btn.setParent(None)
            self.log_download_btn = None

    def show_shape_info_in_panel(self, info, title=None, is_html=False):
        if is_html:
            self.right_content_label.setText(info)
            # Log indirme butonunu kaldır
            if hasattr(self, 'log_download_btn') and self.log_download_btn is not None:
                self.log_download_btn.setParent(None)
                self.log_download_btn = None
            return
        # Ölçüm sonucu ise, paneli tamamen temizle ve sadece ölçüm detaylarını göster
        if title is not None:
            html = f'<div style="font-size:18px; color:#FFD600; font-weight:bold;">{title}</div><div style="font-size:15px; color:#bfc7e6; margin-top:10px;">'
            for k, v in info.items():
                if k == 'Uzunluk':
                    html += f"<b>Uzunluk:</b> <span style='color:#FFD600;'>{v:.2f} birim</span><br>"
                elif k == 'Alan':
                    html += f"<b>Alan:</b> <span style='color:#FFD600;'>{v:.2f} birim²</span><br>"
                else:
                    html += f"<b>{k}:</b> {v}<br>"
            html += '</div>'
            self.right_content_label.setText(html)
            # Log indirme butonunu kaldır
            if hasattr(self, 'log_download_btn') and self.log_download_btn is not None:
                self.log_download_btn.setParent(None)
                self.log_download_btn = None
            return
        html = "<div style='font-size:15px; color:#bfc7e6;'><b>Seçili Özellikler:</b><br>"
        # Öncelikli anahtarlar sırası
        order = ['Tip', 'Koordinat', 'Koordinatlar', 'Alan', 'Uzunluk', 'Hacim', 'Renk']
        for k in order:
            if k in info:
                if k == 'Uzunluk':
                    html += f"<b>Uzunluk:</b> <span style='color:#FFD600; font-size:18px;'>{info[k]:.2f} birim</span><br>"
                elif k == 'Alan':
                    html += f"<b>Alan:</b> <span style='color:#FFD600; font-size:18px;'>{info[k]:.2f} birim²</span><br>"
                elif k == 'Koordinatlar' or k == 'Koordinat':
                    html += f"<b>Koordinatlar:</b> {info[k]}<br>"
                else:
                    html += f"<b>{k}:</b> {info[k]}<br>"
        # Ek ölçüm bilgileri
        extra_keys = [
            'Kenar İndeksi', 'Vertex İndeksi', 'Yüzey İndeksi',
            'Başlangıç Noktası', 'Bitiş Noktası', 'Orta Nokta', 'Yön Vektörü',
            'Vertex İndeksleri', 'Bağlı Kenar Sayısı', 'Bağlı Kenar Uzunlukları',
            'Bağlı Yüzey(ler) Alanı', 'Normal', 'Kenar Uzunlukları', 'Çevre', 'Ait Olduğu Üçgen(ler) Alanı'
        ]
        for k in extra_keys:
            if k in info:
                html += f"<b>{k}:</b> {info[k]}<br>"
        # Diğer anahtarlar
        for k, v in info.items():
            if k not in order and k not in extra_keys:
                html += f"<b>{k}:</b> {v}<br>"
        html += "</div>"
        self.right_content_label.setText(html)
        # Log indirme butonunu kaldır
        if hasattr(self, 'log_download_btn') and self.log_download_btn is not None:
            self.log_download_btn.setParent(None)
            self.log_download_btn = None
   
    def show_measure_popup(self, info, title="Ölçüm Sonucu"):
        from PyQt5.QtWidgets import QMessageBox
        html = f"""
        <div style='background:#232836; border-radius:16px; padding:18px 18px 8px 18px; min-width:340px;'>
            <div style='font-size:22px; color:#FFD600; font-weight:bold; margin-bottom:10px; letter-spacing:1px;'>
                <span style='font-size:28px; vertical-align:middle;'>📏</span> {title}
            </div>
            <table style='width:100%; border-collapse:separate; border-spacing:0 10px; font-size:16px; color:#bfc7e6;'>
        """
        for k, v in info.items():
            if k == 'Uzunluk':
                html += ("<tr>"
                         "<td style='background:#282d3a; border-radius:7px; border:1.5px solid #FFD600; padding:8px 14px; color:#FFD600; font-weight:bold;'>Uzunluk:</td>"
                         f"<td style='background:#232836; border-radius:7px; border:1.5px solid #353b4a; padding:8px 14px; color:#FFD600; font-weight:bold;'><b>{v:.2f} birim</b></td>"
                         "</tr>")
            elif k == 'Alan':
                html += ("<tr>"
                         "<td style='background:#282d3a; border-radius:7px; border:1.5px solid #FFD600; padding:8px 14px; color:#FFD600; font-weight:bold;'>Alan:</td>"
                         f"<td style='background:#232836; border-radius:7px; border:1.5px solid #353b4a; padding:8px 14px; color:#FFD600; font-weight:bold;'><b>{v:.2f} birim²</b></td>"
                         "</tr>")
            else:
                html += ("<tr>"
                         f"<td style='background:#282d3a; border-radius:7px; border:1.5px solid #353b4a; padding:8px 14px; color:#FFD600; font-weight:bold;'>{k}:</td>"
                         f"<td style='background:#232836; border-radius:7px; border:1.5px solid #353b4a; padding:8px 14px; color:#bfc7e6;'>{v}</td>"
                         "</tr>")
        html += "</table></div>"

        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setTextFormat(1)  # Qt.RichText
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #232836;
                border-radius: 16px;
            }
            QLabel {
                color: #bfc7e6;
                font-size: 16px;
            }
            QPushButton {
                background-color: #FFD600;
                color: #232836;
                border-radius: 8px;
                padding: 8px 18px;
                font-weight: bold;
                font-size: 15px;
            }
            QPushButton:hover {
                background-color: #fff176;
                color: #232836;
            }
        """)
        msg.setText(html)
        msg.exec_()
   
    def show_model_info_in_panel(self):
        """Sağ panelde mevcut modelin bilgilerini gösterir."""
        if hasattr(self, 'right_content_label'):
            info = self.occ_widget.get_model_info()
            html = self.logo_img_html
            html += "<div style='font-size:15px; color:#bfc7e6;'><b>Model Bilgileri:</b><br>"
            for k, v in info.items():
                html += f"<b>{k}:</b> {v}<br>"
            html += "</div>"
            self.right_content_label.setText(html)
            # Log indirme butonunu da kaldır
            if hasattr(self, 'log_download_btn') and self.log_download_btn is not None:
                self.log_download_btn.setParent(None)
                self.log_download_btn = None

    def convert_to_glb(self):
        source_path = dosya_secici_ac(parent=self)
        if not source_path: return
        if not source_path.lower().endswith('.obj'):
            QMessageBox.warning(self, "Desteklenmeyen Format", "GLB formatına sadece OBJ dosyaları dönüştürülebilir.")
            return
        
        default_name = os.path.splitext(os.path.basename(source_path))[0] + ".glb"
        save_path, _ = QFileDialog.getSaveFileName(self, "GLB Olarak Kaydet", default_name, "GLB Dosyası (*.glb)")
        if not save_path: return
        
        try:
            # converter.py'deki fonksiyonun çıktısını yönet
            result_path = obj_to_glb(source_path)
            # Eğer fonksiyon belirli bir yere kaydediyorsa, onu istenen yere taşı/kopyala
            if result_path != save_path:
                import shutil
                shutil.move(result_path, save_path)
            QMessageBox.information(self, "Başarılı", f"Dosya GLB formatına dönüştürüldü:\n{save_path}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"GLB'ye dönüştürme başarısız: {e}")

    def convert_to_fbx(self):
        source_path = dosya_secici_ac(parent=self)
        if not source_path: return
        if not source_path.lower().endswith('.obj'):
            QMessageBox.warning(self, "Desteklenmeyen Format", "FBX formatına sadece OBJ dosyaları dönüştürülebilir.")
            return

        default_name = os.path.splitext(os.path.basename(source_path))[0] + ".fbx"
        save_path, _ = QFileDialog.getSaveFileName(self, "FBX Olarak Kaydet", default_name, "FBX Dosyası (*.fbx)")
        if not save_path: return

        try:
            # Blender yolunu burada belirtin veya bir ayar dosyasından okuyun
            blender_path = r'D:\blender\blender-launcher.exe'
            result = obj_to_fbx(source_path, save_path, blender_path)
            if result:
                QMessageBox.information(self, "Başarılı", f"Dosya FBX formatına dönüştürüldü:\n{save_path}")
            else:
                raise Exception("Dönüştürme işlemi başarısız oldu. Blender konsolunu kontrol edin.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"FBX'e dönüştürme başarısız: {e}")

    def convert_to_obj(self):
        source_path = dosya_secici_ac(parent=self)
        if not source_path: return
        if not source_path.lower().endswith('.stl'):
            QMessageBox.warning(self, "Desteklenmeyen Format", "OBJ formatına sadece STL dosyaları dönüştürülebilir.")
            return

        default_name = os.path.splitext(os.path.basename(source_path))[0] + ".obj"
        save_path, _ = QFileDialog.getSaveFileName(self, "OBJ Olarak Kaydet", default_name, "OBJ Dosyası (*.obj)")
        if not save_path: return
        
        try:
            result_path = stl_to_obj(source_path)
            if result_path != save_path:
                import shutil
                shutil.move(result_path, save_path)
            QMessageBox.information(self, "Başarılı", f"Dosya OBJ formatına dönüştürüldü:\n{save_path}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"OBJ'ye dönüştürme başarısız: {e}")

    def convert_to_step(self):
        from OCC.Extend.DataExchange import write_step_file, read_stl_file, read_iges_file
        source_path = dosya_secici_ac(parent=self)
        if not source_path: return
        
        ext = os.path.splitext(source_path)[1].lower()
        shape = None
        try:
            if ext in ['.obj', '.stl']:
                if ext == '.obj':
                    import trimesh
                    mesh = trimesh.load(source_path, force='mesh')
                    temp_stl = os.path.splitext(source_path)[0] + "_temp.stl"
                    mesh.export(temp_stl, file_type='stl')
                    shape = read_stl_file(temp_stl)
                    os.remove(temp_stl)
                else: # .stl
                    shape = read_stl_file(source_path)
            elif ext in ['.iges', '.igs']:
                shape = read_iges_file(source_path)
            elif ext in ['.step', '.stp']:
                 QMessageBox.information(self, "Bilgi", "Seçilen dosya zaten bir STEP dosyası.")
                 return
            else:
                QMessageBox.warning(self, "Desteklenmeyen Format", "Bu dosya formatı STEP'e dönüştürülemez.")
                return

            if shape is None:
                raise ValueError("Dosya okunamadı veya boş.")

            default_name = os.path.splitext(os.path.basename(source_path))[0] + ".step"
            save_path, _ = QFileDialog.getSaveFileName(self, "STEP Olarak Kaydet", default_name, "STEP Dosyası (*.step *.stp)")
            if not save_path: return

            write_step_file(shape, save_path)
            QMessageBox.information(self, "Başarılı", f"Dosya STEP formatına dönüştürüldü:\n{save_path}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"STEP'e dönüştürme başarısız: {e}")

    def convert_to_ply(self):
        import trimesh
        source_path = dosya_secici_ac(parent=self)
        if not source_path: return
        ext = os.path.splitext(source_path)[1].lower()
        if ext not in ['.obj', '.stl', '.glb']:
            QMessageBox.warning(self, "Desteklenmeyen Format", "PLY'ye sadece OBJ, STL veya GLB dosyaları dönüştürülebilir.")
            return
        mesh = trimesh.load(source_path, force='mesh')
        default_name = os.path.splitext(os.path.basename(source_path))[0] + ".ply"
        save_path, _ = QFileDialog.getSaveFileName(self, "PLY Olarak Kaydet", default_name, "PLY Dosyası (*.ply)")
        if not save_path: return
        try:
            mesh.export(save_path, file_type='ply')
            QMessageBox.information(self, "Başarılı", f"Dosya PLY formatına dönüştürüldü:\n{save_path}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"PLY'ye dönüştürme başarısız: {e}")

    def convert_to_gltf(self):
        import trimesh
        source_path = dosya_secici_ac(parent=self)
        if not source_path: return
        ext = os.path.splitext(source_path)[1].lower()
        if ext not in ['.obj', '.stl']:
            QMessageBox.warning(self, "Desteklenmeyen Format", "GLTF'ye sadece OBJ veya STL dosyaları dönüştürülebilir.")
            return
        mesh = trimesh.load(source_path, force='mesh')
        default_name = os.path.splitext(os.path.basename(source_path))[0] + ".gltf"
        save_path, _ = QFileDialog.getSaveFileName(self, "GLTF Olarak Kaydet", default_name, "GLTF Dosyası (*.gltf)")
        if not save_path: return
        try:
            mesh.export(save_path, file_type='gltf')
            QMessageBox.information(self, "Başarılı", f"Dosya GLTF formatına dönüştürüldü:\n{save_path}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"GLTF'ye dönüştürme başarısız: {e}")

    def convert_to_3mf(self):
        import trimesh
        source_path = dosya_secici_ac(parent=self)
        if not source_path: return
        ext = os.path.splitext(source_path)[1].lower()
        if ext not in ['.obj', '.stl']:
            QMessageBox.warning(self, "Desteklenmeyen Format", "3MF'ye sadece OBJ veya STL dosyaları dönüştürülebilir.")
            return
        mesh = trimesh.load(source_path, force='mesh')
        default_name = os.path.splitext(os.path.basename(source_path))[0] + ".3mf"
        save_path, _ = QFileDialog.getSaveFileName(self, "3MF Olarak Kaydet", default_name, "3MF Dosyası (*.3mf)")
        if not save_path: return
        try:
            mesh.export(save_path, file_type='3mf')
            QMessageBox.information(self, "Başarılı", f"Dosya 3MF formatına dönüştürüldü:\n{save_path}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"3MF'ye dönüştürme başarısız: {e}")

    def convert_to_dae(self):
        import trimesh
        source_path = dosya_secici_ac(parent=self)
        if not source_path: return
        ext = os.path.splitext(source_path)[1].lower()
        if ext not in ['.obj', '.stl']:
            QMessageBox.warning(self, "Desteklenmeyen Format", "DAE'ye sadece OBJ veya STL dosyaları dönüştürülebilir.")
            return
        mesh = trimesh.load(source_path, force='mesh')
        default_name = os.path.splitext(os.path.basename(source_path))[0] + ".dae"
        save_path, _ = QFileDialog.getSaveFileName(self, "DAE Olarak Kaydet", default_name, "DAE Dosyası (*.dae)")
        if not save_path: return
        try:
            mesh.export(save_path, file_type='dae')
            QMessageBox.information(self, "Başarılı", f"Dosya DAE formatına dönüştürüldü:\n{save_path}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"DAE'ye dönüştürme başarısız: {e}")

    def convert_step_to_stl(self):
        from OCC.Extend.DataExchange import read_step_file, read_iges_file
        from OCC.Core.StlAPI import StlAPI_Writer
        from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
        source_path = dosya_secici_ac(parent=self)
        if not source_path: return
        ext = os.path.splitext(source_path)[1].lower()
        if ext not in ['.step', '.stp', '.iges', '.igs']:
            QMessageBox.warning(self, "Desteklenmeyen Format", "STL'ye sadece STEP veya IGES dosyaları dönüştürülebilir.")
            return
        if ext in ['.step', '.stp']:
            shape = read_step_file(source_path)
        else:
            shape = read_iges_file(source_path)
        default_name = os.path.splitext(os.path.basename(source_path))[0] + ".stl"
        save_path, _ = QFileDialog.getSaveFileName(self, "STL Olarak Kaydet", default_name, "STL Dosyası (*.stl)")
        if not save_path: return
        try:
            mesh = BRepMesh_IncrementalMesh(shape, 0.1)
            mesh.Perform()
            writer = StlAPI_Writer()
            writer.Write(shape, save_path)
            QMessageBox.information(self, "Başarılı", f"Dosya STL formatına dönüştürüldü:\n{save_path}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"STL'ye dönüştürme başarısız: {e}")

    def convert_step_to_obj(self):
        from OCC.Extend.DataExchange import read_step_file, read_iges_file
        import trimesh
        from OCC.Core.StlAPI import StlAPI_Writer
        from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
        import tempfile, os
        source_path = dosya_secici_ac(parent=self)
        if not source_path: return
        ext = os.path.splitext(source_path)[1].lower()
        if ext not in ['.step', '.stp', '.iges', '.igs']:
            QMessageBox.warning(self, "Desteklenmeyen Format", "OBJ'ye sadece STEP veya IGES dosyaları dönüştürülebilir.")
            return
        if ext in ['.step', '.stp']:
            shape = read_step_file(source_path)
        else:
            shape = read_iges_file(source_path)
        # Önce geçici STL'ye export et
        temp_stl = tempfile.mktemp(suffix='.stl')
        try:
            mesh = BRepMesh_IncrementalMesh(shape, 0.1)
            mesh.Perform()
            writer = StlAPI_Writer()
            writer.Write(shape, temp_stl)
            # Sonra STL'den OBJ'ye çevir
            mesh_trimesh = trimesh.load(temp_stl, force='mesh')
            default_name = os.path.splitext(os.path.basename(source_path))[0] + ".obj"
            save_path, _ = QFileDialog.getSaveFileName(self, "OBJ Olarak Kaydet", default_name, "OBJ Dosyası (*.obj)")
            if not save_path: return
            mesh_trimesh.export(save_path, file_type='obj')
            QMessageBox.information(self, "Başarılı", f"Dosya OBJ formatına dönüştürüldü:\n{save_path}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"OBJ'ye dönüştürme başarısız: {e}")
        finally:
            if os.path.exists(temp_stl):
                os.remove(temp_stl)

