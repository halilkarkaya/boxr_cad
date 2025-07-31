## \file arayuz_design.py
## \brief PyQt5 ile koyu temalı, 3 panelden oluşan modern 3D model görüntüleyici arayüzü

import os
import logging
import subprocess
import sys

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
from cad_viewer import OCCModelWidget, create_progress_bar
from OCC.Display.backend import load_backend
load_backend("pyqt5")
from OCC.Display.qtDisplay import qtViewer3d
from OCC.Extend.DataExchange import read_stl_file
from converter import obj_to_glb, stl_to_obj, obj_to_fbx, convert_to_glb, convert_to_fbx, convert_to_obj, convert_to_step, convert_to_ply, convert_to_gltf, convert_to_3mf, convert_to_dae, convert_step_to_stl, convert_step_to_obj, dosya_secici_ac, obj_to_stl

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

        self.scroll_area = QScrollArea(left_frame)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setStyleSheet("background: transparent; border: none;")
        self.scroll_content = QWidget()
        vbox = QVBoxLayout(self.scroll_content)
        vbox.setContentsMargins(16, 16, 16, 16)
        vbox.setSpacing(12)

        # --- BAŞLIKLAR ---
        boxr_label = QLabel("BOXR CAD")
        boxr_label.setFont(QFont("Arial Black", 16, QFont.Bold))
        boxr_label.setAlignment(Qt.AlignCenter)
        boxr_label.setStyleSheet("color: #FFD600; letter-spacing: 3px; margin-bottom: 8px; margin-top: 8px;")
        vbox.addWidget(boxr_label)
        self.left_panel_labels = [boxr_label]

        title = QLabel("Dosya İşlemleri")
        title.setFont(QFont("Arial", 12, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #bfc7e6;")
        vbox.addWidget(title)
        self.left_panel_labels.append(title)

        self.left_panel_buttons = []

        # --- BUTON STİLLERİ ---
        main_btn_style = """
            QPushButton {
                background-color: #353b4a; color: #fff; border: none; border-radius: 8px;
                padding: 12px 0 12px 18px; font-size: 17px; text-align: left;
            }
            QPushButton:hover { background-color: #FFD600; color: #232836; }
        """
        sub_btn_style = """
            QPushButton {
                background-color: #444a5a; color: #fff; border: none; border-radius: 8px;
                padding: 6px 0 6px 32px; font-size: 13px; margin-left: 0px; text-align: left;
            }
            QPushButton:hover { background-color: #5a6275; color: #fff; }
        """
        
        # 1. Katman Ekle
        self.open_btn = QPushButton("➕ Katman Ekle")
        self.open_btn.setStyleSheet(main_btn_style)
        self.open_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        vbox.addWidget(self.open_btn)
        self.left_panel_buttons.append(self.open_btn)

        # 2. Dosya Dönüştür
        self.convert_btn = QPushButton("🔄 Dosya Dönüştür")
        self.convert_btn.setStyleSheet(main_btn_style)
        self.convert_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        vbox.addWidget(self.convert_btn)
        self.left_panel_buttons.append(self.convert_btn)
        
        self.convert_sub_buttons = []
        convert_options = [
            ("🟠 GLB'ye Dönüştür", self.convert_to_glb), ("🟣 FBX'e Dönüştür", self.convert_to_fbx),
            ("🔵 OBJ'ye Dönüştür", self.convert_to_obj), ("🟢 STEP'e Dönüştür", self.convert_to_step),
            ("🟤 PLY'ye Dönüştür", self.convert_to_ply), ("🟪 GLTF'ye Dönüştür", self.convert_to_gltf),
            ("🟫 3MF'ye Dönüştür", self.convert_to_3mf), ("🟦 DAE'ye Dönüştür", self.convert_to_dae),
            ("🟧 STL'ye Dönüştür (STEP/IGES)", self.convert_step_to_stl), ("🟥 OBJ'ye Dönüştür (STEP/IGES)", self.convert_step_to_obj)
        ]
        for text, func in convert_options:
            sub_btn = QPushButton(text)
            sub_btn.setStyleSheet(sub_btn_style)
            sub_btn.setVisible(False)
            sub_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            sub_btn.setFixedHeight(32)
            sub_btn.clicked.connect(func)
            vbox.addWidget(sub_btn)
            self.convert_sub_buttons.append(sub_btn)

        # 3. Görünüm Seçenekleri
        self.view_options_btn = QPushButton("🎨 Görünüm Seçenekleri")
        self.view_options_btn.setStyleSheet(main_btn_style)
        self.view_options_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        vbox.addWidget(self.view_options_btn)
        self.left_panel_buttons.append(self.view_options_btn)

        self.view_sub_buttons = []
        view_options = [
            ("🖼️ Katı Model", lambda: self.occ_widget.set_view_mode('shaded')),
            ("📉 Tel Kafes", lambda: self.occ_widget.set_view_mode('wireframe'))
        ]
        for text, func in view_options:
            sub_btn = QPushButton(text)
            sub_btn.setStyleSheet(sub_btn_style)
            sub_btn.setVisible(False)
            sub_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            sub_btn.setFixedHeight(32)
            sub_btn.clicked.connect(func)
            vbox.addWidget(sub_btn)
            self.view_sub_buttons.append(sub_btn)

        # 4. Model Bilgileri
        model_info_btn = QPushButton("👁️‍🗨️ Model Bilgileri")
        model_info_btn.setStyleSheet(main_btn_style)
        model_info_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        vbox.addWidget(model_info_btn)
        self.left_panel_buttons.append(model_info_btn)

        # 5. Ölçüm Yap
        self.olcum_btn = QPushButton("📏 Ölçüm Yap")
        self.olcum_btn.setStyleSheet(main_btn_style)
        self.olcum_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        vbox.addWidget(self.olcum_btn)
        self.left_panel_buttons.append(self.olcum_btn)

        self.olcum_sub_buttons = []
        olcum_options = [
            ("📏 Kenar Ölç", 'edge', 2), ("🟡 Vertex Ölç", 'vertex', 1), ("🟦 Alan Ölç", 'face', 4)
        ]
        for text, measure_type, selection_mode in olcum_options:
            sub_btn = QPushButton(text)
            sub_btn.setStyleSheet(sub_btn_style)
            sub_btn.setVisible(False)
            sub_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            sub_btn.setFixedHeight(32)
            sub_btn.clicked.connect(lambda checked, mt=measure_type, sm=selection_mode: self.setup_measurement(mt, sm))
            vbox.addWidget(sub_btn)
            self.olcum_sub_buttons.append(sub_btn)

        # 6. Kesit Düzlemi
        self.section_btn = QPushButton("✂️ Kesit Düzlemi")
        self.section_btn.setStyleSheet(main_btn_style)
        self.section_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        vbox.addWidget(self.section_btn)
        self.left_panel_buttons.append(self.section_btn)

        # --- Kesit Alma GroupBox ---
        self.section_group_box = QGroupBox("Kesit Kontrol")
        self.section_group_box.setStyleSheet("""
            QGroupBox {
                color: #FFD600;
                font-size: 14px;
                font-weight: bold;
                border: 1px solid #353b4a;
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 5px;
            }
        """)
        section_layout = QVBoxLayout()
        section_layout.setSpacing(8)
        section_layout.setContentsMargins(10, 20, 10, 10)

        # Eksen seçimi için Radio Butonlar
        axis_layout = QHBoxLayout()
        self.section_axis_group = QButtonGroup(self)
        self.z_radio = QRadioButton("Z")
        self.y_radio = QRadioButton("Y")
        self.x_radio = QRadioButton("X")
        self.z_radio.setChecked(True)
        self.z_radio.setStyleSheet("color: #fff;")
        self.y_radio.setStyleSheet("color: #fff;")
        self.x_radio.setStyleSheet("color: #fff;")
        self.section_axis_group.addButton(self.z_radio)
        self.section_axis_group.addButton(self.y_radio)
        self.section_axis_group.addButton(self.x_radio)
        axis_label = QLabel("Eksen:")
        axis_label.setStyleSheet("color: #fff;")
        axis_layout.addWidget(axis_label)
        axis_layout.addStretch()
        axis_layout.addWidget(self.z_radio)
        axis_layout.addWidget(self.y_radio)
        axis_layout.addWidget(self.x_radio)
        section_layout.addLayout(axis_layout)

        # Konum Slider'ı
        self.section_slider = QSlider(Qt.Horizontal)
        self.section_slider.setMinimum(-100)
        self.section_slider.setMaximum(100)
        self.section_slider.setValue(0)
        section_layout.addWidget(self.section_slider)

        # Konum Değeri ve Etiketi
        pos_layout = QHBoxLayout()
        self.section_label = QLabel("Konum: 0")
        self.section_label.setStyleSheet("color:#FFD600; font-size:13px;")
        self.section_pos_edit = QLineEdit("0")
        self.section_pos_edit.setFixedWidth(50)
        self.section_pos_edit.setStyleSheet("color: #fff; background-color: #353b4a; border-radius: 4px; padding: 2px;")
        pos_layout.addWidget(self.section_label)
        pos_layout.addStretch()
        pos_layout.addWidget(self.section_pos_edit)
        section_layout.addLayout(pos_layout)

        # Kaydet ve Kapat Butonları
        section_btn_layout = QHBoxLayout()
        self.save_section_btn = QPushButton("💾 Kaydet")
        self.close_section_btn = QPushButton("❌ Kapat")
        self.save_section_btn.setStyleSheet(sub_btn_style)
        self.close_section_btn.setStyleSheet(sub_btn_style)
        section_btn_layout.addWidget(self.save_section_btn)
        section_btn_layout.addWidget(self.close_section_btn)
        section_layout.addLayout(section_btn_layout)

        self.section_group_box.setLayout(section_layout)
        self.section_group_box.setVisible(False)
        vbox.addWidget(self.section_group_box)

        # 7. Ortala
        self.ortala_btn = QPushButton("🎯 Ortala")
        self.ortala_btn.setStyleSheet(main_btn_style)
        self.ortala_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        vbox.addWidget(self.ortala_btn)
        self.left_panel_buttons.append(self.ortala_btn)

        # 8. AR'da Görüntüle
        self.ar_btn = QPushButton("📱 AR'da Görüntüle")
        self.ar_btn.setStyleSheet(main_btn_style)
        self.ar_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        vbox.addWidget(self.ar_btn)
        self.left_panel_buttons.append(self.ar_btn)

        # 9. 3D Yazıcıya Gönder
        self.printer_btn = QPushButton("🖨️ 3D Yazıcıya Gönder")
        self.printer_btn.setStyleSheet(main_btn_style)
        self.printer_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        vbox.addWidget(self.printer_btn)
        self.left_panel_buttons.append(self.printer_btn)

        # 10. Loglar
        logs_btn = QPushButton("📝 Loglar")
        logs_btn.setStyleSheet(main_btn_style)
        logs_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        vbox.addWidget(logs_btn)
        self.left_panel_buttons.append(logs_btn)

        # 11. Yardım / SSS
        help_btn = QPushButton("💡 Yardım / SSS")
        help_btn.setStyleSheet(main_btn_style)
        help_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        vbox.addWidget(help_btn)
        self.left_panel_buttons.append(help_btn)

        # 12. Hakkında
        about_btn = QPushButton("❔ Hakkında")
        about_btn.setStyleSheet(main_btn_style)
        about_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        vbox.addWidget(about_btn)
        self.left_panel_buttons.append(about_btn)
        self.about_btn_style = about_btn.styleSheet() # Stili sakla

        vbox.addStretch()
        self.scroll_area.setWidget(self.scroll_content)
        layout = QVBoxLayout(left_frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.scroll_area)

        # --- BUTON FONKSİYONLARI ---
        self.open_btn.clicked.connect(lambda: self.katman_ekle_dosya_yolu(dosya_secici_ac(parent=self)))
        self.convert_btn.clicked.connect(lambda: self.toggle_sub_menu(self.convert_sub_buttons))
        self.view_options_btn.clicked.connect(lambda: self.toggle_sub_menu(self.view_sub_buttons))
        model_info_btn.clicked.connect(self.show_model_info_in_panel)
        self.olcum_btn.clicked.connect(lambda: self.toggle_sub_menu(self.olcum_sub_buttons))
        self.section_btn.clicked.connect(self.toggle_section_ui)
        self.ortala_btn.clicked.connect(lambda: self.occ_widget.display.FitAll())
        self.ar_btn.clicked.connect(self.show_ar_preview)
        self.printer_btn.clicked.connect(self.send_to_printer)
        logs_btn.clicked.connect(self.show_logs)
        about_btn.clicked.connect(self.show_about_dialog)

        # Yeni Kesit Arayüzü Bağlantıları
        self.close_section_btn.clicked.connect(self.toggle_section_ui)
        self.save_section_btn.clicked.connect(self.save_section)
        self.section_slider.valueChanged.connect(self.update_section_from_slider)
        self.section_pos_edit.textChanged.connect(self.update_section_from_lineedit)
        self.z_radio.toggled.connect(self.update_section)
        self.y_radio.toggled.connect(self.update_section)
        self.x_radio.toggled.connect(self.update_section)

        return left_frame

    def toggle_sub_menu(self, sub_buttons):
        visible = not sub_buttons[0].isVisible()
        for btn in sub_buttons:
            btn.setVisible(visible)

    def setup_measurement(self, measure_type, selection_mode):
        self.occ_widget.active_measure = measure_type
        self.occ_widget.set_selection_mode(selection_mode)
        self.occ_widget.set_measure_mode(True)
        self.right_content_label.setText(f'<div style="color:#FFD600; font-size:16px;">Lütfen bir {measure_type} seçin.</div>')

    def toggle_section_ui(self):
        visible = not self.section_group_box.isVisible()
        self.section_group_box.setVisible(visible)
        self.section_btn.setText("❌ Kesiti Kapat" if visible else "✂️ Kesit Düzlemi")

        if visible:
            if not hasattr(self, 'clip_plane') or self.clip_plane is None:
                from OCC.Core.gp import gp_Pln, gp_Pnt, gp_Dir
                from OCC.Core.Graphic3d import Graphic3d_ClipPlane
                plane = gp_Pln(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1))
                self.clip_plane = Graphic3d_ClipPlane(plane)
                self.occ_widget.display.View.AddClipPlane(self.clip_plane)
            self.update_section()
        else:
            if hasattr(self, 'clip_plane') and self.clip_plane is not None:
                self.occ_widget.display.View.RemoveClipPlane(self.clip_plane)
                self.clip_plane = None
                self.occ_widget.display.View.Redraw()

    def update_section_from_slider(self, value):
        self.section_pos_edit.blockSignals(True)
        self.section_pos_edit.setText(str(value))
        self.section_pos_edit.blockSignals(False)
        self.update_section()

    def update_section_from_lineedit(self, text):
        try:
            val = int(text)
            self.section_slider.blockSignals(True)
            self.section_slider.setValue(val)
            self.section_slider.blockSignals(False)
            self.update_section()
        except (ValueError, TypeError):
            pass # Ignore non-integer input

    def update_section(self):
        if not self.section_group_box.isVisible() or not hasattr(self, 'clip_plane') or self.clip_plane is None:
            return

        from OCC.Core.gp import gp_Pln, gp_Pnt, gp_Dir

        pos = self.section_slider.value()
        self.section_label.setText(f"Konum: {pos}")
        
        axis_btn = self.section_axis_group.checkedButton()
        if not axis_btn: # Return if no button is checked yet
            return
        axis = axis_btn.text()

        if axis == "Z":
            normal = gp_Dir(0, 0, 1)
            origin = gp_Pnt(0, 0, pos)
        elif axis == "Y":
            normal = gp_Dir(0, 1, 0)
            origin = gp_Pnt(0, pos, 0)
        else: # X
            normal = gp_Dir(1, 0, 0)
            origin = gp_Pnt(pos, 0, 0)
        
        plane = gp_Pln(origin, normal)
        self.clip_plane.SetEquation(plane)
        self.occ_widget.display.View.Redraw()

    def save_section(self):
        if not hasattr(self, 'clip_plane') or self.clip_plane is None:
            QMessageBox.warning(self, "Uyarı", "Önce bir kesit düzlemi oluşturmalısınız!")
            return

        # Seçili katmanın modelini al
        selected_items = self.layer_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir katman seçin.")
            return
        idx = self.layer_list.row(selected_items[0])
        model_refs = self.layers[idx]["model_refs"]
        
        if not model_refs:
            return

        model_ref = model_refs[0]  # Katmandaki ilk model
        model_shape = self.occ_widget.get_shape_from_ref(model_ref)

        if model_shape is None:
            QMessageBox.warning(self, "Uyarı", "Seçili katmanın geçerli bir modeli (shape) yok!")
            return

        try:
            from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Common
            from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeHalfSpace
            from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
            from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
            from OCC.Core.StlAPI import StlAPI_Writer
            from OCC.Core.gp import gp_Pln, gp_Pnt, gp_Dir, gp_Vec

            # Düzlemi UI'dan al
            axis_btn = self.section_axis_group.checkedButton()
            if not axis_btn:
                QMessageBox.warning(self, "Hata", "Kesit ekseni seçilmemiş.")
                return
            axis = axis_btn.text()
            pos = self.section_slider.value()

            if axis == "Z":
                origin = gp_Pnt(0, 0, pos)
                normal = gp_Dir(0, 0, 1)
            elif axis == "Y":
                origin = gp_Pnt(0, pos, 0)
                normal = gp_Dir(0, 1, 0)
            else: # X
                origin = gp_Pnt(pos, 0, 0)
                normal = gp_Dir(1, 0, 0)
            
            plane = gp_Pln(origin, normal)
            face = BRepBuilderAPI_MakeFace(plane, -10000, 10000, -10000, 10000).Face()

            # Düzlemin negatif tarafında bir yarım uzay (HalfSpace) oluştur
            # Bu, kesitin "korunacak" tarafını temsil eder
            reversed_vec = gp_Vec(normal.Reversed().XYZ())
            scaled_vec = reversed_vec.Multiplied(10000) # Scale the vector
            point_on_solid_side = origin.Translated(scaled_vec)
            half_space = BRepPrimAPI_MakeHalfSpace(face, point_on_solid_side).Solid()

            # Orijinal model ile yarım uzayın kesişimini (ortak bölümünü) al
            intersection = BRepAlgoAPI_Common(model_shape, half_space)
            cut_shape = intersection.Shape()

            if cut_shape.IsNull():
                QMessageBox.warning(self, "Hata", "Kesit oluşturulamadı. Model ve düzlem kesişmiyor olabilir.")
                return

            # STL olarak kaydetmek için dosya yolu al
            file_path, _ = QFileDialog.getSaveFileName(self, "Kesiti STL Olarak Kaydet", "kesit.stl", "STL Dosyası (*.stl)")
            if not file_path:
                return

            # Mesh oluştur ve STL dosyasına yaz
            mesh = BRepMesh_IncrementalMesh(cut_shape, 0.1, True)
            mesh.Perform()
            if not mesh.IsDone():
                 QMessageBox.warning(self, "Hata", "Kesitli model meshlenemedi.")
                 return

            writer = StlAPI_Writer()
            writer.SetASCIIMode(True) # ASCII formatında kaydet
            if not writer.Write(cut_shape, file_path):
                QMessageBox.critical(self, "Hata", f"Kesit dosyası yazılamadı: {file_path}")
                return

            # --- KESİTİ YENİ KATMAN OLARAK EKLE ---
            layer_name = f"Kesit - {os.path.basename(file_path)}"
            new_model_ref = self.occ_widget.add_model(file_path, model_path=file_path)
            if new_model_ref:
                layer = {"name": layer_name, "visible": True, "model_refs": [new_model_ref], "model_path": file_path}
                self.layers.append(layer)
                
                item = QListWidgetItem(layer_name)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked)
                self.layer_list.addItem(item)
                self.layer_list.setCurrentRow(self.layer_list.count() - 1)

                QMessageBox.information(self, "Başarılı", f"Kesit başarıyla kaydedildi ve yeni katman olarak eklendi!\n{file_path}")
            else:
                QMessageBox.warning(self, "Uyarı", "Kesit kaydedildi ancak yeni katman olarak eklenemedi.")

        except Exception as e:
            logging.error(f"Kesit kaydedilirken hata: {e}", exc_info=True)
            QMessageBox.critical(self, "Kritik Hata", f"Kesit kaydedilemedi:\n{e}")

    def send_to_printer(self):
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        import tempfile, os, json

        config_path = os.path.join(os.path.expanduser("~"), ".boxr_cad_printer.json")
        printer_path = None
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    printer_path = json.load(f).get("printer_path")
            except Exception: pass

        if not printer_path or not os.path.exists(printer_path):
            default_cura = r"D:\Yeni klasör (3)\UltiMaker Cura 5.10.1\UltiMaker-Cura.exe"
            printer_path, _ = QFileDialog.getOpenFileName(self, "3D Yazıcı Yazılımını Seç", default_cura, "Uygulama (*.exe)")
            if not printer_path:
                QMessageBox.warning(self, "Yazıcı Yazılımı Gerekli", "3D yazıcı yazılımı seçilmedi.")
                return
            try:
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump({"printer_path": printer_path}, f)
            except Exception: pass
        
        idx = self.layer_list.currentRow()
        if idx < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen yazıcıya göndermek için bir katman/model seçin.")
            return
        
        model_path = self.layers[idx].get("model_path")
        if not model_path or not os.path.exists(model_path):
            QMessageBox.warning(self, "Hata", "Model dosyası bulunamadı.")
            return

        try:
            import trimesh
            temp_stl = os.path.join(tempfile.gettempdir(), f"boxr_cad_export_{idx}.stl")
            mesh = trimesh.load(model_path, force='mesh')
            mesh.export(temp_stl, file_type='stl')
            os.startfile(temp_stl)
            QMessageBox.information(self, "Başarılı", f"Model STL olarak dışa aktarıldı ve varsayılan yazılımda açıldı: {temp_stl}")
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Model dışa aktarılamadı: {e}")

    def show_logs(self):
        self.right_frame.setVisible(True)
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                log_text = ''.join(f.readlines()[-100:]) # Son 100 satır
            html = self.logo_img_html + f"<div style='font-size:13px; color:#FFD600; background:#232836;'><pre>{log_text}</pre></div>"
        except Exception as e:
            html = self.logo_img_html + f"<span style='color:red;'>Log dosyası okunamadı: {e}</span>"
        
        self.right_content_label.setText(html)
        if not hasattr(self, 'log_download_btn'):
            self.log_download_btn = QPushButton('Tüm Logları İndir')
            self.log_download_btn.setStyleSheet('background-color:#FFD600; color:#232836; font-weight:bold; border-radius:8px; padding:8px; margin-top:12px;')
            self.log_download_btn.clicked.connect(self.download_logs)
            self.right_top_vbox.addWidget(self.log_download_btn)
        self.log_download_btn.setVisible(True)

    def hide_log_download_button(self):
        if hasattr(self, 'log_download_btn'):
            self.log_download_btn.setVisible(False)

    def download_logs(self):
        try:
            save_path, _ = QFileDialog.getSaveFileName(self, 'Logları Kaydet', 'uygulama.log', 'Log Dosyası (*.log);;Tüm Dosyalar (*)')
            if save_path:
                import shutil
                shutil.copy(log_path, save_path)
        except Exception as e:
            QMessageBox.warning(self, 'Hata', f'Log dosyası kaydedilemedi: {e}') 

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
        
        # --- TEMA TOGGLE BUTONU EKLE ---
        self.is_light_theme = False  # Başlangıçta koyu tema
        self.theme_toggle_btn = QPushButton("🌞 Açık Tema")
        self.theme_toggle_btn.setStyleSheet(self.about_btn_style if hasattr(self, 'about_btn_style') else "")
        self.theme_toggle_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.right_bottom_vbox.addWidget(self.theme_toggle_btn)

        def apply_light_theme():
            # Ana pencere arka planı
            self.setStyleSheet("background-color: #f5f5f5;")
            # Sol panel
            if hasattr(self, 'left_frame'):
                self.left_frame.setStyleSheet("background-color: #f9f9f9; border-radius: 12px;")
            # Sağ panel
            self.right_frame.setStyleSheet("background-color: #f9f9f9; border-radius: 12px;")
            # Sağ panel içerik alanı
            self.right_content_label.setStyleSheet("background: #fff; color: #232836; border-radius: 10px; padding: 12px;")
            self.right_scroll_area.setStyleSheet("background: #fff; border-radius: 10px;")
            # Katman listesi
            self.layer_list.setStyleSheet("""
                QListWidget {
                    background: #fff;
                    color: #232836;
                    border: 2px solid #e0e0e0;
                    border-radius: 10px;
                    font-size: 15px;
                    margin-bottom: 10px;
                    padding: 6px;
                }
                QListWidget::item:selected {
                    background: #e0e0e0;
                    color: #232836;
                    border-radius: 8px;
                }
            """)
            # Sağ paneldeki butonlar
            light_btn_style = """
                QPushButton {
                    background-color: #e0e0e0;
                    color: #232836;
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
            """
            for btn in [self.color_btn, self.bgcolor_btn, self.delete_layer_btn, self.theme_toggle_btn]:
                btn.setStyleSheet(light_btn_style)
            # Katman hareket/döndürme butonları
            light_katman_btn_style = """
                QPushButton {
                    background-color: #e0e0e0;
                    color: #232836;
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
            for btn in [self.up_btn, self.down_btn, self.left_btn, self.right_btn, self.rotate_x_btn, self.rotate_y_btn, self.rotate_z_btn]:
                btn.setStyleSheet(light_katman_btn_style)
            # Sol paneli de açık temaya geçir
            if hasattr(self, 'apply_left_panel_light_theme'):
                self.apply_left_panel_light_theme()
            elif 'apply_left_panel_light_theme' in locals():
                apply_left_panel_light_theme()
            # Model arka plan rengini #61ffa3 yap
            if hasattr(self, 'occ_widget') and hasattr(self.occ_widget, 'display') and hasattr(self.occ_widget.display, 'View'):
                from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB
                r, g, b = 97/255.0, 255/255.0, 163/255.0
                self.occ_widget.display.View.SetBackgroundColor(Quantity_Color(r, g, b, Quantity_TOC_RGB))
                self.occ_widget.display.Repaint()

        def apply_dark_theme():
            self.setStyleSheet("background-color: #181c24;")
            if hasattr(self, 'left_frame'):
                self.left_frame.setStyleSheet("background-color: #232836; border-radius: 12px;")
            self.right_frame.setStyleSheet("background-color: #232836; border-radius: 12px;")
            self.right_content_label.setStyleSheet("background: #232836; color: #bfc7e6; border-radius: 10px; padding: 12px;")
            self.right_scroll_area.setStyleSheet("background: #232836; border-radius: 10px;")
            self.layer_list.setStyleSheet("""
                QListWidget {
                    background: #232836;
                    color: #bfc7e6;
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
            dark_btn_style = """
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
            """
            for btn in [self.color_btn, self.bgcolor_btn, self.delete_layer_btn, self.theme_toggle_btn]:
                btn.setStyleSheet(dark_btn_style)
            dark_katman_btn_style = """
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
            for btn in [self.up_btn, self.down_btn, self.left_btn, self.right_btn, self.rotate_x_btn, self.rotate_y_btn, self.rotate_z_btn]:
                btn.setStyleSheet(dark_katman_btn_style)
            if hasattr(self, 'apply_left_panel_dark_theme'):
                self.apply_left_panel_dark_theme()
            elif 'apply_left_panel_dark_theme' in locals():
                apply_left_panel_dark_theme()
            # Model arka plan rengini koyu yap
            if hasattr(self, 'occ_widget') and hasattr(self.occ_widget, 'display') and hasattr(self.occ_widget.display, 'View'):
                from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB
                r, g, b = 24/255.0, 28/255.0, 36/255.0
                self.occ_widget.display.View.SetBackgroundColor(Quantity_Color(r, g, b, Quantity_TOC_RGB))
                self.occ_widget.display.Repaint()

        def apply_left_panel_dark_theme():
            if hasattr(self, 'left_frame'):
                self.left_frame.setStyleSheet("background-color: #232836; border-radius: 12px;")
            if hasattr(self, 'scroll_area'):
                self.scroll_area.setStyleSheet("background: transparent; border: none;")
            if hasattr(self, 'scroll_content'):
                self.scroll_content.setStyleSheet("background: transparent;")
            dark_btn_style = """
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
            """
            for btn in getattr(self, 'left_panel_buttons', []):
                btn.setStyleSheet(dark_btn_style)
            # Ölçüm Yap ve Kesit Düzlemi butonları da koyu tema olmalı
            if hasattr(self, 'olcum_btn'):
                self.olcum_btn.setStyleSheet(dark_btn_style)
            if hasattr(self, 'section_btn'):
                self.section_btn.setStyleSheet(dark_btn_style)
            for label in getattr(self, 'left_panel_labels', []):
                label.setStyleSheet("color: #FFD600; letter-spacing: 3px; margin-bottom: 8px; margin-top: 8px;" if "BOXR CAD" in label.text() else "color: #bfc7e6;")
            # Ölçüm alt butonları (küçük, tema uyumlu)
            dark_olcum_sub_btn_style = """
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
            for btn in [getattr(self, 'kenar_olc_btn', None), getattr(self, 'vertex_olc_btn', None), getattr(self, 'alan_olc_btn', None)]:
                if btn:
                    btn.setStyleSheet(dark_olcum_sub_btn_style)
                    btn.setFixedHeight(32) # Sabit yükseklik
                    btn.setFont(QFont(btn.font().family(), 13))
            # Dönüştürme alt butonları için özel stil
            dark_convert_sub_btn_style = """
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
            for btn in getattr(self, 'convert_sub_buttons', []):
                btn.setStyleSheet(dark_convert_sub_btn_style)
                btn.setFixedHeight(32) # Sabit yükseklik
                btn.setFont(QFont(btn.font().family(), 13))

        def toggle_theme():
            if self.is_light_theme:
                apply_dark_theme()
                self.theme_toggle_btn.setText("🌞 Açık Tema")
                self.is_light_theme = False
            else:
                apply_light_theme()
                self.theme_toggle_btn.setText("🌙 Koyu Tema")
                self.is_light_theme = True

        self.theme_toggle_btn.clicked.connect(toggle_theme)

        self.right_bottom_vbox.addStretch()

        # --- SOL PANEL AÇIK TEMA FONKSİYONU ---
        def apply_left_panel_light_theme():
            # Sol panel arka planı
            if hasattr(self, 'left_frame'):
                self.left_frame.setStyleSheet("background-color: #f9f9f9; border-radius: 12px;")
            if hasattr(self, 'scroll_area'):
                self.scroll_area.setStyleSheet("background: #f9f9f9; border: none;")
            if hasattr(self, 'scroll_content'):
                self.scroll_content.setStyleSheet("background: #f9f9f9;")
            # Sol paneldeki butonlar
            light_btn_style = """
                QPushButton {
                    background-color: #e0e0e0;
                    color: #232836;
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
            """
            for btn in getattr(self, 'left_panel_buttons', []):
                btn.setStyleSheet(light_btn_style)
            # Özellikle ölçüm ve kesit butonları da dahil tüm butonlara açık tema uygula
            if hasattr(self, 'olcum_btn'):
                self.olcum_btn.setStyleSheet(light_btn_style)
            if hasattr(self, 'kenar_olc_btn'):
                self.kenar_olc_btn.setStyleSheet(light_btn_style)
            if hasattr(self, 'vertex_olc_btn'):
                self.vertex_olc_btn.setStyleSheet(light_btn_style)
            if hasattr(self, 'alan_olc_btn'):
                self.alan_olc_btn.setStyleSheet(light_btn_style)
            if hasattr(self, 'section_btn'):
                self.section_btn.setStyleSheet(light_btn_style)
            if hasattr(self, 'save_section_btn'):
                self.save_section_btn.setStyleSheet(light_btn_style)
            # Ölçüm alt butonları için özel stil
            light_olcum_sub_btn_style = """
                QPushButton {
                    background-color: #e0e0e0; /* Light theme background */
                    color: #232836; /* Dark text for light theme */
                    border: none;
                    border-radius: 8px;
                    padding: 6px 0 6px 32px; /* Smaller padding */
                    font-size: 13px; /* Smaller font size */
                    margin-left: 0px;
                    text-align: left;
                }
                QPushButton:hover {
                    background-color: #FFD600; /* Hover color */
                    color: #232836; /* Hover text color */
                }
            """
            if hasattr(self, 'kenar_olc_btn'):
                self.kenar_olc_btn.setStyleSheet(light_olcum_sub_btn_style)
            if hasattr(self, 'vertex_olc_btn'):
                self.vertex_olc_btn.setStyleSheet(light_olcum_sub_btn_style)
            if hasattr(self, 'alan_olc_btn'):
                self.alan_olc_btn.setStyleSheet(light_olcum_sub_btn_style)
            # Dönüştürme alt butonları için özel stil
            light_convert_sub_btn_style = """
                QPushButton {
                    background-color: #e0e0e0; /* Light theme background */
                    color: #232836; /* Dark text for light theme */
                    border: none;
                    border-radius: 8px;
                    padding: 6px 0 6px 32px; /* Smaller padding */
                    font-size: 13px; /* Smaller font size */
                    margin-left: 0px;
                    text-align: left;
                }
                QPushButton:hover {
                    background-color: #FFD600; /* Hover color */
                    color: #232836; /* Hover text color */
                }
            """
            for btn in getattr(self, 'convert_sub_buttons', []):
                btn.setStyleSheet(light_convert_sub_btn_style)
            # Sol paneldeki başlık ve label'lar
            for lbl in getattr(self, 'left_panel_labels', []):
                if lbl.text() == "BOXR CAD":
                    lbl.setStyleSheet("color: #FFD600; letter-spacing: 3px; margin-bottom: 8px; margin-top: 8px; background: transparent;")
                elif lbl.text() == "Dosya İşlemleri":
                    lbl.setStyleSheet("color: #232836; background: transparent;")
                else:
                    lbl.setStyleSheet("color: #232836; background: transparent;")

        return self.right_frame

    # MainWindow'un metodu olarak ekle:
    def show_ar_preview(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "AR Önizlemesi için Model Seç", "", "3D Modeller (*.glb *.gltf)")
        if file_path:
            try:
                # ar_server.py'nin tam yolunu al
                script_dir = os.path.dirname(os.path.abspath(__file__))
                ar_server_path = os.path.join(script_dir, 'ar_server.py')
                
                # ar_server.py'yi yeni bir işlem olarak başlat
                # subprocess.Popen, GUI'yi bloklamadan arka planda çalışmasını sağlar
                subprocess.Popen([sys.executable, ar_server_path, file_path])
                QMessageBox.information(self, "AR Sunucusu Başlatıldı", f"'{os.path.basename(file_path)}' modeli için AR sunucusu başlatıldı. Açılan penceredeki QR kodu tarayın.")
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"AR sunucusu başlatılırken bir hata oluştu: {e}")

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

    def show_about_dialog(self):
        """Hakkında penceresini gösterir."""
        self.right_frame.setVisible(True)
        self.hide_log_download_button()
        html = self.logo_img_html +             "<div style='font-family: Segoe UI; font-size: 15px; color:#bfc7e6; text-align:center;'>"             "<p><b>Versiyon:</b> 1.0.0</p>"             "<p>Bu uygulama çeşitli CAD formatlarını görüntülemek ve dönüştürmek için tasarlanmıştır.</p>"             "<h3 style='color: #2196f3;'>Desteklenen formatlar:</h3>"             "<ul style='text-align:left; margin: 0 auto 0 30px; padding-left:0;'>"             "<li style='margin-bottom:2px;'>STEP (.step, .stp)</li>"             "<li style='margin-bottom:2px;'>STL (.stl)</li>"             "<li style='margin-bottom:2px;'>FBX (.fbx)</li>"             "<li style='margin-bottom:2px;'>GLB (.glb)</li>"             "<li style='margin-bottom:2px;'>OBJ (.obj)</li>"             "</ul>"             "<p style='font-size:13px; color:#fcb045;'>© 2025 digiMODE. Tüm hakları saklıdır.</p>"             "</div>"
        self.right_content_label.setText(html)

    def convert_to_glb(self):
        convert_to_glb(self)

    def convert_to_fbx(self):
        convert_to_fbx(self)

    def convert_to_obj(self):
        convert_to_obj(self)

    def convert_to_step(self):
        convert_to_step(self)

    def convert_to_ply(self):
        convert_to_ply(self)

    def convert_to_gltf(self):
        convert_to_gltf(self)

    def convert_to_3mf(self):
        convert_to_3mf(self)

    def convert_to_dae(self):
        convert_to_dae(self)

    def convert_step_to_stl(self):
        convert_step_to_stl(self)

    def convert_step_to_obj(self):
        convert_step_to_obj(self)

    def show_model_info_in_panel(self):
        """Sağ panelde mevcut modelin bilgilerini gösterir."""
        self.right_frame.setVisible(True)
        self.hide_log_download_button()
        if hasattr(self, 'right_content_label'):
            info = self.occ_widget.get_model_info()
            html = self.logo_img_html
            html += "<div style='font-size:15px; color:#bfc7e6;'><b>Model Bilgileri:</b><br>"
            for k, v in info.items():
                html += f"<b>{k}:</b> {v}<br>"
            html += "</div>"
            self.right_content_label.setText(html)

    def show_shape_info_in_panel(self, info, title=None, is_html=False):
        self.hide_log_download_button()
        if is_html:
            self.right_content_label.setText(info)
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