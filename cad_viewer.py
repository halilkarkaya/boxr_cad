## \file cad_viewer.py
## \brief PyQt5 tabanlı 3D CAD model görüntüleyici ve yardımcı fonksiyonlar.

from PyQt5.QtWidgets import QFileDialog, QWidget, QVBoxLayout, QSizePolicy, QFrame, QLabel, QProgressBar, QMessageBox, QHBoxLayout, QPushButton
from PyQt5.QtGui import QPainter, QPen, QColor, QLinearGradient, QBrush
from PyQt5.QtCore import pyqtSignal
import trimesh
import tempfile
import os
from OCC.Display.backend import load_backend
load_backend("pyqt5")  # OpenCASCADE'nin PyQt5 ile entegrasyonunu sağlar, 3D görüntüleme için gerekli
from OCC.Display.qtDisplay import qtViewer3d
from OCC.Extend.DataExchange import read_stl_file
from PyQt5.QtCore import Qt
import numpy as np
# Model taşıma için OCC importları
from OCC.Core.gp import gp_Trsf, gp_Vec
from OCC.Core.AIS import AIS_Shape
from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB



## \fn create_progress_bar()
#  \brief Koyu temalı özel bir QProgressBar oluşturur.
#  \return QProgressBar nesnesi.
def create_progress_bar():
    bar = QProgressBar()
    bar.setTextVisible(False)
    bar.setValue(0)
    bar.setAlignment(Qt.AlignCenter)
    bar.setStyleSheet("""
        QProgressBar {
            border: 1.5px solid #2196f3;
            border-radius: 10px;
            background: #232836;
            height: 20px;
            margin-top: 8px;
        }
        QProgressBar::chunk {
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:1,
                stop:0 #21cbf3, stop:1 #2196f3
            );
            border-radius: 10px;
            margin: 1px;
        }
    """)
    return bar

## \class OCCModelWidget
#  \brief OpenCASCADE tabanlı 3D model görüntüleyici widget'ı.
class OCCModelWidget(QWidget):
    mesafe_olcum_tamamlandi = pyqtSignal(float)
    ## \brief OCCModelWidget kurucusu. 3D görüntüleyici ve temel ayarları başlatır.
    #  \param parent QWidget ebeveyni (varsayılan: None)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLayout(QVBoxLayout())
        # --- Axis Gizmo ---
        self._gizmo_rotating = False
        self._gizmo_last_pos = None
        self._gizmo_azimuth = 0.0
        self._gizmo_elevation = 0.0
        # ---
        self.canvas = qtViewer3d(self)
        self.layout().addWidget(self.canvas)
        self.canvas.InitDriver()
        self.display = self.canvas._display
        # 3D Grid (Graduated Trihedron)
        try:
            view = self.display.View
            view.GraduatedTrihedronDisplay(True)
        except Exception as e:
            print('Grid display error:', e)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.model_path = None
        self.stl_path = None
        self.measure_mode = False
        self.selected_points = []
        self.canvas.installEventFilter(self)
        self._dragging = False
        self._last_mouse_pos = None
        self.model_ais = None
        self._current_trsf = gp_Trsf()  # Modelin mevcut transformasyonu
        self.models = []  # Tüm model referansları (AIS_Shape)
        self.model_trsfs = {}  # Her model için dönüşüm matrisi
        # For measurement
        self.measurement_model_path = None
        self.measurement_model_ref = None

    def set_active_model_for_measurement(self, model_path, model_ref):
        """Sets the model to be used for the next measurement operation."""
        self.measurement_model_path = model_path
        self.measurement_model_ref = model_ref

    def resizeEvent(self, event):
        margin_x = 30
        margin_y = 30
        # btn_width = self._gizmo.width() # Axis Gizmo ile ilgili kodlar kaldırıldı
        # self._gizmo.move(self.width() - btn_width - margin_x, margin_y) # Axis Gizmo ile ilgili kodlar kaldırıldı
        super().resizeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        # self._gizmo.raise_() # Axis Gizmo ile ilgili kodlar kaldırıldı

    def eventFilter(self, obj, event):
        from PyQt5.QtCore import QEvent
        # Sadece ölçüm modunda mouse eventlerini override et
        if obj == self.canvas and self.measure_mode:
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                pos = event.pos()
                x, y = pos.x(), pos.y()
                if self.measurement_model_path and os.path.exists(self.measurement_model_path):
                    try:
                        mesh = trimesh.load(self.measurement_model_path, force='mesh')
                        
                        # Get transformation and apply it to vertices
                        trsf = gp_Trsf()
                        if self.measurement_model_ref and hasattr(self.measurement_model_ref, 'LocalTransformation'):
                            trsf = self.measurement_model_ref.LocalTransformation()
                        
                        from OCC.Core.gp import gp_Pnt
                        transformed_vertices = []
                        for v_np in mesh.vertices:
                            p = gp_Pnt(float(v_np[0]), float(v_np[1]), float(v_np[2]))
                            p.Transform(trsf)
                            transformed_vertices.append(np.array([p.X(), p.Y(), p.Z()]))
                        
                        # Use a new mesh with transformed vertices for all calculations
                        mesh.vertices = np.array(transformed_vertices)

                        # Kenar Ölçüm
                        if hasattr(self, 'active_measure') and self.active_measure == 'edge':
                            min_dist = float('inf')
                            closest_v = None
                            for v in mesh.vertices:
                                if hasattr(self.display, 'View') and hasattr(self.display.View, 'Project'):
                                    projected = self.display.View.Project(v[0], v[1], v[2])
                                    px, py = projected[:2]
                                    dist = (px - x) ** 2 + (py - y) ** 2
                                    if dist < min_dist:
                                        min_dist = dist
                                        closest_v = v
                                else:
                                    closest_v = mesh.vertices[0]
                                    break
                            if closest_v is None:
                                QMessageBox.warning(self, "Hata", "Yakın vertex bulunamadı.")
                                return True
                            min_edge_dist = float('inf')
                            best_edge = None
                            best_edge_idx = None
                            for idx, edge in enumerate(mesh.edges):
                                v1 = mesh.vertices[edge[0]]
                                v2 = mesh.vertices[edge[1]]
                                mid = (v1 + v2) / 2
                                if hasattr(self.display, 'View') and hasattr(self.display.View, 'Project'):
                                    projected = self.display.View.Project(mid[0], mid[1], mid[2])
                                    px, py = projected[:2]
                                    dist = (px - x) ** 2 + (py - y) ** 2
                                    if dist < min_edge_dist:
                                        min_edge_dist = dist
                                        best_edge = (v1, v2)
                                        best_edge_idx = idx
                                else:
                                    best_edge = (v1, v2)
                                    best_edge_idx = idx
                                    break
                            if best_edge is not None:
                                v1, v2 = best_edge
                                uzunluk = np.linalg.norm(v1 - v2)
                                midpoint = (v1 + v2) / 2
                                direction = v2 - v1
                                alanlar = []
                                if hasattr(mesh, 'faces'):
                                    for face in mesh.faces:
                                        if mesh.edges[best_edge_idx][0] in face and mesh.edges[best_edge_idx][1] in face:
                                            tri = mesh.vertices[face]
                                            a = np.linalg.norm(tri[0] - tri[1])
                                            b = np.linalg.norm(tri[1] - tri[2])
                                            c = np.linalg.norm(tri[2] - tri[0])
                                            s = (a + b + c) / 2
                                            area = max(s * (s - a) * (s - b) * (s - c), 0)
                                            alanlar.append(np.sqrt(area))
                                info = {
                                    'Uzunluk': uzunluk,
                                    'Başlangıç Noktası': f"({v1[0]:.2f}, {v1[1]:.2f}, {v1[2]:.2f})",
                                    'Bitiş Noktası': f"({v2[0]:.2f}, {v2[1]:.2f}, {v2[2]:.2f})",
                                    'Orta Nokta': f"({midpoint[0]:.2f}, {midpoint[1]:.2f}, {midpoint[2]:.2f})",
                                    'Yön Vektörü': f"({direction[0]:.2f}, {direction[1]:.2f}, {direction[2]:.2f})",
                                    'Kenar İndeksi': best_edge_idx,
                                    'Vertex İndeksleri': f"{mesh.edges[best_edge_idx][0]}, {mesh.edges[best_edge_idx][1]}"
                                }
                                if alanlar:
                                    info['Ait Olduğu Üçgen(ler) Alanı'] = ', '.join([f"{a:.2f}" for a in alanlar])
                                mainwin = self.window()
                                if hasattr(mainwin, 'show_shape_info_in_panel'):
                                    mainwin.show_shape_info_in_panel(info, "Kenar Ölçüm Sonucu")
                                self.measure_mode = False
                                return True
                        # Vertex Ölçüm
                        if hasattr(self, 'active_measure') and self.active_measure == 'vertex':
                            min_dist = float('inf')
                            closest_idx = None
                            for idx, v in enumerate(mesh.vertices):
                                if hasattr(self.display, 'View') and hasattr(self.display.View, 'Project'):
                                    projected = self.display.View.Project(v[0], v[1], v[2])
                                    px, py = projected[:2]
                                    dist = (px - x) ** 2 + (py - y) ** 2
                                    if dist < min_dist:
                                        min_dist = dist
                                        closest_idx = idx
                                else:
                                    closest_idx = 0
                                    break
                            if closest_idx is None:
                                QMessageBox.warning(self, "Hata", "Yakın vertex bulunamadı.")
                                return True
                            v = mesh.vertices[closest_idx]
                            edge_lengths = []
                            valency = 0
                            for edge in mesh.edges:
                                if closest_idx in edge:
                                    v1 = mesh.vertices[edge[0]]
                                    v2 = mesh.vertices[edge[1]]
                                    edge_lengths.append(np.linalg.norm(v1 - v2))
                                    valency += 1
                            face_areas = []
                            if hasattr(mesh, 'faces'):
                                for fidx, face in enumerate(mesh.faces):
                                    if closest_idx in face:
                                        tri = mesh.vertices[face]
                                        a = np.linalg.norm(tri[0] - tri[1])
                                        b = np.linalg.norm(tri[1] - tri[2])
                                        c = np.linalg.norm(tri[2] - tri[0])
                                        s = (a + b + c) / 2
                                        area = max(s * (s - a) * (s - b) * (s - c), 0)
                                        face_areas.append((fidx, np.sqrt(area)))
                            info = {
                                'Koordinatlar': f"({v[0]:.2f}, {v[1]:.2f}, {v[2]:.2f})",
                                'Vertex İndeksi': closest_idx,
                                'Bağlı Kenar Sayısı': valency,
                                'Bağlı Kenar Uzunlukları': ', '.join([f"{l:.2f}" for l in edge_lengths]),
                            }
                            if face_areas:
                                info['Bağlı Yüzey(ler) Alanı'] = ', '.join([f"#{fidx}: {a:.2f}" for fidx, a in face_areas])
                            mainwin = self.window()
                            if hasattr(mainwin, 'show_shape_info_in_panel'):
                                mainwin.show_shape_info_in_panel(info, "Vertex Ölçüm Sonucu")
                            self.measure_mode = False
                            return True
                        # Alan (Face) Ölçüm
                        if hasattr(self, 'active_measure') and self.active_measure == 'face':
                            min_dist = float('inf')
                            closest_face_idx = None
                            for fidx, face in enumerate(mesh.faces):
                                tri = mesh.vertices[face]
                                centroid = np.mean(tri, axis=0)
                                if hasattr(self.display, 'View') and hasattr(self.display.View, 'Project'):
                                    projected = self.display.View.Project(centroid[0], centroid[1], centroid[2])
                                    px, py = projected[:2]
                                    dist = (px - x) ** 2 + (py - y) ** 2
                                    if dist < min_dist:
                                        min_dist = dist
                                        closest_face_idx = fidx
                                else:
                                    closest_face_idx = 0
                                    break
                            if closest_face_idx is None:
                                QMessageBox.warning(self, "Hata", "Yakın yüzey bulunamadı.")
                                return True
                            face = mesh.faces[closest_face_idx]
                            vertices = mesh.vertices[face]
                            vertex_indices = ', '.join(str(idx) for idx in face)
                            centroid = np.mean(vertices, axis=0)
                            # Normal vektör (ilk üç vertex ile, üçgenden büyükse de yaklaşık normal)
                            if len(vertices) >= 3:
                                normal = np.cross(vertices[1] - vertices[0], vertices[2] - vertices[0])
                                normal = normal / (np.linalg.norm(normal) + 1e-8)
                            else:
                                normal = np.array([0, 0, 0])
                            edge_lengths = []
                            for i in range(len(vertices)):
                                v1 = vertices[i]
                                v2 = vertices[(i+1)%len(vertices)]
                                edge_lengths.append(np.linalg.norm(v1 - v2))
                            cevre = sum(edge_lengths)
                            # Alan hesabı (üçgen için Heron, çokgen için trimesh)
                            if len(vertices) == 3:
                                a, b, c = edge_lengths
                                s = (a + b + c) / 2
                                area = max(s * (s - a) * (s - b) * (s - c), 0)
                                area = np.sqrt(area)
                            else:
                                # Çokgen için trimesh'in area özelliği
                                try:
                                    area = trimesh.Trimesh(vertices=vertices, faces=[[i for i in range(len(vertices))]]).area
                                except Exception:
                                    area = 0
                            min_edge = min(edge_lengths)
                            max_edge = max(edge_lengths)
                            avg_edge = sum(edge_lengths) / len(edge_lengths)
                            aspect_ratio = max_edge / min_edge if min_edge > 0 else 0
                            komsu_faces = []
                            for fidx2, face2 in enumerate(mesh.faces):
                                if fidx2 == closest_face_idx:
                                    continue
                                ortak = set(face) & set(face2)
                                if len(ortak) >= 2:
                                    komsu_faces.append(fidx2)
                            info = {
                                'Alan': area,
                                'Çevre': cevre,
                                'Yüzey İndeksi': closest_face_idx,
                                'Vertex İndeksleri': vertex_indices,
                                'Vertex Koordinatları': '; '.join([f'({v[0]:.2f}, {v[1]:.2f}, {v[2]:.2f})' for v in vertices]),
                                'Kenar Uzunlukları': ', '.join([f'{l:.2f}' for l in edge_lengths]),
                                'Min Kenar Uzunluğu': f'{min_edge:.2f}',
                                'Max Kenar Uzunluğu': f'{max_edge:.2f}',
                                'Ortalama Kenar Uzunluğu': f'{avg_edge:.2f}',
                                'Aspect Ratio': f'{aspect_ratio:.2f}',
                                'Normal': f'({normal[0]:.2f}, {normal[1]:.2f}, {normal[2]:.2f})',
                                'Yüzeyin Merkezi': f'({centroid[0]:.2f}, {centroid[1]:.2f}, {centroid[2]:.2f})',
                                'Komşu Yüzeyler': ', '.join(str(idx) for idx in komsu_faces) if komsu_faces else 'Yok'
                            }
                            mainwin = self.window()
                            if hasattr(mainwin, 'show_shape_info_in_panel'):
                                mainwin.show_shape_info_in_panel(info, "Alan/Çoklu Yüzey Ölçüm Sonucu")
                            self.measure_mode = False
                            return True
                        # --- 2 Nokta Mesafe Ölçüm ---
                        if hasattr(self, 'active_measure') and self.active_measure == 'two_point':
                            min_dist = float('inf')
                            closest_idx = None
                            transformed_vertices = []
                            # Modelin dönüşümünü uygula
                            trsf = None
                            if hasattr(self, 'model_ais') and hasattr(self.model_ais, 'LocalTransformation'):
                                trsf = self.model_ais.LocalTransformation()
                            for idx, v in enumerate(mesh.vertices):
                                v_occ = v
                                if trsf is not None:
                                    from OCC.Core.gp import gp_Pnt
                                    p = gp_Pnt(float(v[0]), float(v[1]), float(v[2]))
                                    p.Transform(trsf)
                                    v_occ = np.array([p.X(), p.Y(), p.Z()])
                                transformed_vertices.append(v_occ)
                                if hasattr(self.display, 'View') and hasattr(self.display.View, 'Project'):
                                    projected = self.display.View.Project(v_occ[0], v_occ[1], v_occ[2])
                                    px, py = projected[:2]
                                    dist = (px - x) ** 2 + (py - y) ** 2
                                    if dist < min_dist:
                                        min_dist = dist
                                        closest_idx = idx
                                else:
                                    closest_idx = 0
                                    break
                            if closest_idx is None:
                                QMessageBox.warning(self, "Hata", "Yakın vertex bulunamadı.")
                                return True
                            v = transformed_vertices[closest_idx]
                            # İlk seçimde önceki seçimi ve küreleri temizle
                            if not hasattr(self, 'selected_points') or len(self.selected_points) == 0:
                                if hasattr(self, '_temp_spheres'):
                                    for sph in self._temp_spheres:
                                        self.display.Context.Remove(sph, True)
                                    self.display.Context.UpdateCurrentViewer()
                                    self._temp_spheres = []
                                self.selected_points = []
                            # Seçilen vertexlerin indexini de sakla
                            if not hasattr(self, 'selected_points'):
                                self.selected_points = []  # [(koordinat, index)]
                            # Aynı vertex iki kez seçildiyse uyarı ver
                            if len(self.selected_points) == 1:
                                prev_v, prev_idx = self.selected_points[0]
                                if (closest_idx == prev_idx) or np.allclose(prev_v, v, atol=1e-3):
                                    QMessageBox.warning(self, "Uyarı", "Aynı noktayı iki kez seçtiniz. Lütfen farklı bir nokta seçin.")
                                    return True
                            self.selected_points.append((v, closest_idx))
                            # Noktayı vurgula (küçük bir sphere veya highlight)
                            from OCC.Core.gp import gp_Pnt
                            from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeSphere
                            from OCC.Core.AIS import AIS_Shape
                            from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB
                            sphere = BRepPrimAPI_MakeSphere(gp_Pnt(v[0], v[1], v[2]), 0.7).Shape()
                            ais_sphere = AIS_Shape(sphere)
                            ais_sphere.SetColor(Quantity_Color(1.0, 0.0, 0.0, Quantity_TOC_RGB))
                            self.display.Context.Display(ais_sphere, False)
                            self.display.Context.UpdateCurrentViewer()
                            if not hasattr(self, '_temp_spheres'):
                                self._temp_spheres = []
                            self._temp_spheres.append(ais_sphere)
                            # İki nokta seçildiyse mesafeyi hesapla
                            if len(self.selected_points) == 2:
                                (v1, idx1), (v2, idx2) = self.selected_points
                                mesafe = np.linalg.norm(v1 - v2)
                                mainwin = self.window()
                                if hasattr(mainwin, 'mesafe_sonuc_goster'):
                                    mainwin.mesafe_sonuc_goster(mesafe)
                                # Geçici noktaları temizle
                                for sph in getattr(self, '_temp_spheres', []):
                                    self.display.Context.Remove(sph, True)
                                self.display.Context.UpdateCurrentViewer()
                                self.selected_points = []
                                self._temp_spheres = []
                                self.measure_mode = False
                                return True
                            return True
                    except Exception as e:
                        QMessageBox.warning(self, "Hata", f"Nokta seçimi veya ölçüm başarısız: {e}")
                return True
            return super().eventFilter(obj, event)
        # Ölçüm modu dışında kalan tüm eventler OCC'ye bırakılır
        return super().eventFilter(obj, event)

    def show_box_grid(self, size=100, major_step=10, minor_step=1):
        """Blender tarzı XY düzleminde grid çizer. Major/minor çizgiler ve renkli eksenler."""
        from OCC.Core.gp import gp_Pnt, gp_Dir, gp_Lin
        from OCC.Core.AIS import AIS_Line
        from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB
        from OCC.Core.Geom import Geom_Line
        if hasattr(self, '_box_grid_lines') and self._box_grid_lines:
            return  # Zaten çiziliyse tekrar çizme
        self._box_grid_lines = []
        # Minor grid (ince gri)
        minor_color = Quantity_Color(0.4, 0.4, 0.4, Quantity_TOC_RGB)
        for i in range(0, size+1, minor_step):
            # Y ekseni boyunca (X sabit)
            p1 = gp_Pnt(i, 0, 0)
            p2 = gp_Pnt(i, size, 0)
            direction = gp_Dir(p2.X() - p1.X(), p2.Y() - p1.Y(), p2.Z() - p1.Z())
            geom_line = Geom_Line(gp_Lin(p1, direction))
            line = AIS_Line(geom_line)
            line.SetColor(minor_color)
            line.SetWidth(1)
            self.display.Context.Display(line, False)
            self._box_grid_lines.append(line)
            # X ekseni boyunca (Y sabit)
            p3 = gp_Pnt(0, i, 0)
            p4 = gp_Pnt(size, i, 0)
            direction2 = gp_Dir(p4.X() - p3.X(), p4.Y() - p3.Y(), p4.Z() - p3.Z())
            geom_line2 = Geom_Line(gp_Lin(p3, direction2))
            line2 = AIS_Line(geom_line2)
            line2.SetColor(minor_color)
            line2.SetWidth(1)
            self.display.Context.Display(line2, False)
            self._box_grid_lines.append(line2)
        # Major grid (kalın açık gri)
        major_color = Quantity_Color(0.7, 0.7, 0.7, Quantity_TOC_RGB)
        for i in range(0, size+1, major_step):
            # Y ekseni boyunca (X sabit)
            p1 = gp_Pnt(i, 0, 0)
            p2 = gp_Pnt(i, size, 0)
            direction = gp_Dir(p2.X() - p1.X(), p2.Y() - p1.Y(), p2.Z() - p1.Z())
            geom_line = Geom_Line(gp_Lin(p1, direction))
            line = AIS_Line(geom_line)
            line.SetColor(major_color)
            line.SetWidth(2)
            self.display.Context.Display(line, False)
            self._box_grid_lines.append(line)
            # X ekseni boyunca (Y sabit)
            p3 = gp_Pnt(0, i, 0)
            p4 = gp_Pnt(size, i, 0)
            direction2 = gp_Dir(p4.X() - p3.X(), p4.Y() - p3.Y(), p4.Z() - p3.Z())
            geom_line2 = Geom_Line(gp_Lin(p3, direction2))
            line2 = AIS_Line(geom_line2)
            line2.SetColor(major_color)
            line2.SetWidth(2)
            self.display.Context.Display(line2, False)
            self._box_grid_lines.append(line2)
        # X ekseni (yeşil)
        x_color = Quantity_Color(0.0, 1.0, 0.0, Quantity_TOC_RGB)
        p1 = gp_Pnt(0, size//2, 0)
        p2 = gp_Pnt(size, size//2, 0)
        direction = gp_Dir(p2.X() - p1.X(), p2.Y() - p1.Y(), p2.Z() - p1.Z())
        geom_line = Geom_Line(gp_Lin(p1, direction))
        x_axis = AIS_Line(geom_line)
        x_axis.SetColor(x_color)
        x_axis.SetWidth(3)
        self.display.Context.Display(x_axis, False)
        self._box_grid_lines.append(x_axis)
        # Y ekseni (kırmızı)
        y_color = Quantity_Color(1.0, 0.0, 0.0, Quantity_TOC_RGB)
        p3 = gp_Pnt(size//2, 0, 0)
        p4 = gp_Pnt(size//2, size, 0)
        direction2 = gp_Dir(p4.X() - p3.X(), p4.Y() - p3.Y(), p4.Z() - p3.Z())
        geom_line2 = Geom_Line(gp_Lin(p3, direction2))
        y_axis = AIS_Line(geom_line2)
        y_axis.SetColor(y_color)
        y_axis.SetWidth(3)
        self.display.Context.Display(y_axis, False)
        self._box_grid_lines.append(y_axis)
        # Model gridin üstünde kalsın
        self.center_model_on_grid(size)

    def center_model_on_grid(self, grid_size):
        """Modelin alt yüzeyini gridin üstüne (y=0) hizalar ve ortalar."""
        if not hasattr(self, 'model_refs') or not self.model_refs:
            return
        from OCC.Core.Bnd import Bnd_Box
        from OCC.Core.BRepBndLib import brepbndlib_Add
        from OCC.Core.gp import gp_Vec, gp_Trsf
        from OCC.Core.TopLoc import TopLoc_Location
        # Tüm model_refs için bounding box hesapla
        bbox = Bnd_Box()
        for ref in self.model_refs:
            brepbndlib_Add(ref, bbox)
        xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
        # Modelin alt yüzeyini y=0'a, merkezini gridin ortasına taşı
        model_center_x = (xmin + xmax) / 2
        model_center_z = (zmin + zmax) / 2
        dx = grid_size/2 - model_center_x
        dz = grid_size/2 - model_center_z
        dy = -ymin  # Alt yüzey y=0'a gelsin
        trsf = gp_Trsf()
        trsf.SetTranslation(gp_Vec(dx, dy, dz))
        for ref in self.model_refs:
            ref.Location(TopLoc_Location(trsf))
        self.display.Context.UpdateCurrentViewer()

    def hide_box_grid(self):
        """Çizilmiş kutu grid çizgilerini sahneden kaldırır."""
        if hasattr(self, '_box_grid_lines'):
            for line in self._box_grid_lines:
                self.display.Context.Remove(line, True)
            self._box_grid_lines = []
            self.display.Context.UpdateCurrentViewer()
            self.display.Repaint()

    ## \fn yukle_ve_goster(self, stl_path, model_path=None)
    #  \brief STL dosyasını yükler ve 3D ekranda gösterir.
    #  \param stl_path STL dosya yolu (str)
    #  \param model_path Orijinal model dosya yolu (str, opsiyonel)
    def yukle_ve_goster(self, stl_path, model_path=None):
        shape = read_stl_file(stl_path)
        self.display.EraseAll()
        # Modeli AIS_Shape olarak sakla (liste dönebilir!)
        result = self.display.DisplayShape(shape, update=True)
        if isinstance(result, list):
            self.model_ais = result[0]
        else:
            self.model_ais = result
        self.display.Repaint()
        self.stl_path = stl_path
        if model_path:
            self.model_path = model_path
        self._current_trsf = gp_Trsf()

    ## \fn get_model_info(self)
    #  \brief Yüklü modelin temel bilgilerini (vertex, yüzey, boyut, format) döndürür.
    #  \return Model bilgilerini içeren sözlük (dict)
    def get_model_info(self):
        info = {}
        if self.model_path and os.path.exists(self.model_path):
            info['Dosya'] = os.path.basename(self.model_path)
            info['Yol'] = self.model_path
            try:
                mesh = trimesh.load(self.model_path, force='mesh')
                info['Vertex Sayısı'] = len(mesh.vertices)
                info['Yüzey (Face) Sayısı'] = len(mesh.faces)
                info['Boyutlar'] = mesh.extents.tolist() if hasattr(mesh, 'extents') else '-'
                info['Format'] = os.path.splitext(self.model_path)[-1].upper()
            except Exception as e:
                info['Hata'] = str(e)
        else:
            info['Bilgi'] = 'Model yüklenmedi.'
        return info

    def add_model(self, stl_path, model_path=None):
        shape = read_stl_file(stl_path)
        # Modeli AIS_Shape olarak ekle (liste dönebilir!)
        result = self.display.DisplayShape(shape, update=True)
        if isinstance(result, list):
            model_ref = result[0]
        else:
            model_ref = result
        self.models.append(model_ref)
        self.model_trsfs[model_ref] = gp_Trsf()  # Yeni model için sıfır dönüşüm
        self.display.Repaint()
        if model_path:
            self.model_path = model_path
        return model_ref

    def add_step_iges_model(self, file_path):
        """STEP veya IGES dosyasını okur ve sahneye ekler."""
        from OCC.Extend.DataExchange import read_step_file, read_iges_file
        shape = None
        try:
            if file_path.lower().endswith(('.step', '.stp')):
                shape = read_step_file(file_path)
            elif file_path.lower().endswith(('.iges', '.igs')):
                shape = read_iges_file(file_path)
        except Exception as e:
            print(f"Hata: {file_path} dosyası okunamadı. {e}")
            return None

        if shape is None:
            return None

        model_ref = self.display.DisplayShape(shape, update=True)
        if isinstance(model_ref, list):
            model_ref = model_ref[0]

        self.models.append(model_ref)
        self.model_trsfs[model_ref] = gp_Trsf()
        self.model_path = file_path # Ana model yolunu güncelle
        self.display.Repaint()
        return model_ref

    def set_model_visible(self, model_ref, visible):
        if visible:
            self.display.Context.Display(model_ref, True)
        else:
            self.display.Context.Erase(model_ref, True)
        self.display.Repaint()

    def set_model_color(self, model_ref, color):
        # color: QColor nesnesi
        r = color.red() / 255.0
        g = color.green() / 255.0
        b = color.blue() / 255.0
        qcolor = Quantity_Color(r, g, b, Quantity_TOC_RGB)
        if hasattr(model_ref, 'SetColor'):
            model_ref.SetColor(qcolor)
        elif hasattr(model_ref, 'Attributes'):
            model_ref.Attributes().SetColor(qcolor)
        self.display.Context.UpdateCurrentViewer()
        self.display.Repaint()

    def set_measure_mode(self, enabled=True):
        self.measure_mode = enabled
        # Temizlik: Ölçüm modu kapatılırken veya başlatılırken geçici küreleri ve seçili noktaları temizle
        if hasattr(self, '_temp_spheres'):
            for sph in self._temp_spheres:
                self.display.Context.Remove(sph, True)
            self.display.Context.UpdateCurrentViewer()
            self._temp_spheres = []
        self.selected_points = []

    def rotate_model(self, model_ref, axis='z', angle_deg=15):
        """Verilen model_ref'i kendi merkezi etrafında belirtilen eksende angle_deg kadar döndür."""
        from OCC.Core.gp import gp_Trsf, gp_Ax1, gp_Dir, gp_Pnt
        import math
        bbox = model_ref.BoundingBox()
        xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
        center = gp_Pnt((xmin + xmax) / 2, (ymin + ymax) / 2, (zmin + zmax) / 2)
        trsf = gp_Trsf()
        if axis == 'x':
            trsf.SetRotation(gp_Ax1(center, gp_Dir(1, 0, 0)), math.radians(angle_deg))
        elif axis == 'y':
            trsf.SetRotation(gp_Ax1(center, gp_Dir(0, 1, 0)), math.radians(angle_deg))
        else:
            trsf.SetRotation(gp_Ax1(center, gp_Dir(0, 0, 1)), math.radians(angle_deg))
        if hasattr(model_ref, 'LocalTransformation'):
            current_trsf = model_ref.LocalTransformation()
            trsf.Multiply(current_trsf)
        model_ref.SetLocalTransformation(trsf)
        self.display.Context.UpdateCurrentViewer()
        self.display.Repaint()

    def rotate_model_x(self, model_ref, angle_deg=15):
        """Modeli kendi merkezi etrafında X ekseninde angle_deg kadar döndür."""
        from OCC.Core.gp import gp_Trsf, gp_Ax1, gp_Dir, gp_Pnt
        import math
        bbox = model_ref.BoundingBox()
        xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
        center = gp_Pnt((xmin + xmax) / 2, (ymin + ymax) / 2, (zmin + zmax) / 2)
        trsf = gp_Trsf()
        trsf.SetRotation(gp_Ax1(center, gp_Dir(1, 0, 0)), math.radians(angle_deg))
        if hasattr(model_ref, 'LocalTransformation'):
            current_trsf = model_ref.LocalTransformation()
            trsf.Multiply(current_trsf)
        model_ref.SetLocalTransformation(trsf)
        self.display.Context.UpdateCurrentViewer()
        self.display.Repaint()

    def rotate_model_y(self, model_ref, angle_deg=15):
        """Modeli kendi merkezi etrafında Y ekseninde angle_deg kadar döndür."""
        from OCC.Core.gp import gp_Trsf, gp_Ax1, gp_Dir, gp_Pnt
        import math
        bbox = model_ref.BoundingBox()
        xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
        center = gp_Pnt((xmin + xmax) / 2, (ymin + ymax) / 2, (zmin + zmax) / 2)
        trsf = gp_Trsf()
        trsf.SetRotation(gp_Ax1(center, gp_Dir(0, 1, 0)), math.radians(angle_deg))
        if hasattr(model_ref, 'LocalTransformation'):
            current_trsf = model_ref.LocalTransformation()
            trsf.Multiply(current_trsf)
        model_ref.SetLocalTransformation(trsf)
        self.display.Context.UpdateCurrentViewer()
        self.display.Repaint()

    def rotate_model_z(self, model_ref, angle_deg=15):
        """Modeli kendi merkezi etrafında Z ekseninde angle_deg kadar döndür."""
        from OCC.Core.gp import gp_Trsf, gp_Ax1, gp_Dir, gp_Pnt
        import math
        bbox = model_ref.BoundingBox()
        xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
        center = gp_Pnt((xmin + xmax) / 2, (ymin + ymax) / 2, (zmin + zmax) / 2)
        trsf = gp_Trsf()
        trsf.SetRotation(gp_Ax1(center, gp_Dir(0, 0, 1)), math.radians(angle_deg))
        if hasattr(model_ref, 'LocalTransformation'):
            current_trsf = model_ref.LocalTransformation()
            trsf.Multiply(current_trsf)
        model_ref.SetLocalTransformation(trsf)
        self.display.Context.UpdateCurrentViewer()
        self.display.Repaint()

    def move_model(self, model_ref, dx=0, dy=0, dz=0):
        from OCC.Core.gp import gp_Trsf, gp_Vec
        # Mevcut dönüşüm matrisini al
        current_trsf = model_ref.LocalTransformation() if hasattr(model_ref, 'LocalTransformation') else gp_Trsf()
        # Hareket vektörünü sadece rotasyona göre döndür
        move_vec = gp_Vec(dx, dy, dz)
        rot_only = gp_Trsf()
        rot_only.SetRotation(current_trsf.GetRotation())
        move_vec_local = move_vec.Transformed(rot_only)
        # Yeni hareket matrisini oluştur
        move_trsf = gp_Trsf()
        move_trsf.SetTranslation(move_vec_local)
        # Mevcut matrisin üstüne hareketi uygula
        current_trsf.Multiply(move_trsf)
        model_ref.SetLocalTransformation(current_trsf)
        self.model_trsfs[model_ref] = current_trsf
        self.display.Context.UpdateCurrentViewer()
        self.display.Repaint()

    def apply_scale_to_model(self, model_ref, factor):
        from OCC.Core.gp import gp_Trsf, gp_Pnt
        # Modelin merkezi etrafında ölçekle
        bbox = model_ref.BoundingBox()
        xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
        center = gp_Pnt((xmin + xmax) / 2, (ymin + ymax) / 2, (zmin + zmax) / 2)
        trsf = gp_Trsf()
        trsf.SetScale(center, factor)
        if hasattr(model_ref, 'LocalTransformation'):
            current_trsf = model_ref.LocalTransformation()
            trsf.Multiply(current_trsf)
        model_ref.SetLocalTransformation(trsf)
        self.display.Context.UpdateCurrentViewer()
        self.display.Repaint()

    def update_grid(self, spacing, unit):
        # Eğer manuel grid çizimi varsa burada güncelle
        # (Örneğin: grid çizgilerini silip yeni spacing ve birime göre tekrar çiz)
        # Eğer OCC'nin GraduatedTrihedron'u kullanılıyorsa, bu fonksiyon placeholder olarak kalabilir
        print(f"Grid güncellendi: aralık={spacing}, birim={unit}")

    def set_selection_mode(self, mode):
        # mode: 1=vertex, 2=edge, 4=face
        for model_ref in self.models:
            self.display.Context.Deactivate(model_ref)
            self.display.Context.Activate(model_ref, mode)
        self.display.Context.UpdateCurrentViewer()

    def set_view_mode(self, mode):
        """Changes the display mode for all models in the scene.
        :param mode: 'shaded' or 'wireframe'
        """
        # In OCC, 0 is wireframe, 1 is shaded
        display_mode = 1 if mode == 'shaded' else 0
        if not self.models:
            return
        for model_ref in self.models:
            self.display.Context.SetDisplayMode(model_ref, display_mode, False)
        self.display.Context.UpdateCurrentViewer()

    def set_sky_background(self):
        try:
            from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB
            self.display.View.SetBackgroundColor(Quantity_Color(0.53, 0.81, 0.98, Quantity_TOC_RGB))
            self.display.Repaint()
        except Exception as e:
            print('Arka plan düz maviye ayarlanamadı:', e)

    def get_shape_from_ref(self, model_ref):
        """
        Retrieves the underlying TopoDS_Shape from an AIS_Shape reference.
        """
        if model_ref is not None and hasattr(model_ref, 'Shape'):
            return model_ref.Shape()
        return None

    def get_active_shape(self):
        """Yüklü modelin TopoDS_Shape nesnesini döndürür."""
        if hasattr(self, 'model_ais') and self.model_ais is not None and hasattr(self.model_ais, 'Shape'):
            return self.model_ais.Shape()
        return None