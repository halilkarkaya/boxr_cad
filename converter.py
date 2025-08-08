## \file converter.py
## \brief 3D model dosya formatlari arasinda dönüsüm fonksiyonlari (OBJ, STL, GLB)
import trimesh
import os
import subprocess
import tempfile
from PyQt5.QtWidgets import QFileDialog, QMessageBox
import json

CONFIG_FILE = os.path.expanduser("~/.boxr_cad_config.json")

def get_mesh_properties(file_path):
    """Trimesh kullanarak bir mesh dosyasının hacim ve yüzey alanı bilgilerini alır."""
    try:
        mesh = trimesh.load(file_path, force='mesh')
        return {
            "volume": mesh.volume,
            "area": mesh.area
        }
    except Exception as e:
        print(f"Özellikler alınırken hata: {e}")
        return None

def save_blender_path(path):
    """Blender yolunu JSON yapilandirma dosyasına kaydeder."""
    with open(CONFIG_FILE, "w") as f:
        json.dump({"blender_path": path}, f)

def load_blender_path():
    """Kaydedilmis Blender yolunu JSON yapilandirma dosyasindan yükler."""
    if not os.path.exists(CONFIG_FILE):
        return None
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
            return config.get("blender_path")
    except (json.JSONDecodeError, IOError):
        return None

def find_blender_executable():
    """Sistemde Blender'ı otomatik olarak bulmaya çalişir."""
    saved_path = load_blender_path()
    if saved_path and os.path.exists(saved_path):
        return saved_path
    possible_paths = []
    program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
    blender_foundation_path = os.path.join(program_files, "Blender Foundation")
    if os.path.exists(blender_foundation_path):
        for version_dir in os.listdir(blender_foundation_path):
            blender_exe = os.path.join(blender_foundation_path, version_dir, "blender.exe")
            if os.path.exists(blender_exe):
                possible_paths.append(blender_exe)
    for path in possible_paths:
        if os.path.exists(path):
            save_blender_path(path)
            return path
    try:
        blender_path = subprocess.check_output(["where", "blender"]).strip().decode()
        if os.path.exists(blender_path):
            save_blender_path(blender_path)
            return blender_path
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    QMessageBox.information(None, "Blender Bulunamadi", "FBX dönüsümü için Blender programına ihtiyaç var. Lütfen blender.exe dosyasını seçin.")
    user_path, _ = QFileDialog.getOpenFileName(None, "Blender Uygulamasını Seç", "", "Uygulama (*.exe)")
    if user_path and os.path.exists(user_path):
        save_blender_path(user_path)
        return user_path
    return None

def dosya_secici_ac(parent=None):
    file_path, _ = QFileDialog.getOpenFileName(
        parent, "3D Model Dosyası Aç", "", 
        "Tüm Desteklenen Formatlar (*.obj *.stl *.step *.stp *.iges *.igs);;"
        "Mesh Dosyaları (*.obj *.stl);;"
        "CAD Dosyaları (*.step *.stp *.iges *.igs);;"
        "Tüm Dosyalar (*.*)"
    )
    return file_path or None

def obj_to_stl(obj_path):
    temp_dir = tempfile.gettempdir()
    temp_stl = os.path.join(temp_dir, "temp_obj_conversion.stl")
    mesh = trimesh.load(obj_path, force='mesh')
    mesh.export(temp_stl, file_type='stl')
    return temp_stl

def obj_to_glb(obj_path):
    mesh = trimesh.load(obj_path, force='mesh')
    glb_path = os.path.splitext(obj_path)[0] + ".glb"
    mesh.export(glb_path, file_type='glb')
    return glb_path

def stl_to_obj(stl_path):
    mesh = trimesh.load(stl_path, force='mesh')
    obj_path = os.path.splitext(stl_path)[0] + ".obj"
    mesh.export(obj_path, file_type='obj')
    return obj_path

def obj_to_fbx(obj_path, fbx_path, blender_path):
    temp_dir = tempfile.gettempdir()
    temp_stl = os.path.join(temp_dir, "temp_obj2fbx.stl")
    temp_glb = os.path.join(temp_dir, "temp_obj2fbx.glb")
    try:
        mesh = trimesh.load(obj_path, force='mesh')
        mesh.export(temp_stl, file_type='stl')
        mesh2 = trimesh.load(temp_stl, force='mesh')
        mesh2.export(temp_glb, file_type='glb')
    except Exception as e:
        print(f"Ara dosya oluşturulurken hata: {e}")
        for f in [temp_stl, temp_glb]:
            if os.path.exists(f):
                os.remove(f)
        return None

    blender_script = f"""
import bpy

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=r'{temp_glb}')
bpy.ops.export_scene.fbx(filepath=r'{fbx_path}')
"""
    temp_script = os.path.join(temp_dir, "temp_blender_script.py")
    with open(temp_script, "w") as f:
        f.write(blender_script)
    try:
        subprocess.run([blender_path, "-b", "-P", temp_script], check=True)
        if os.path.exists(fbx_path):
            return fbx_path
        else:
            print("FBX dosyası oluşmadı.")
            return None
    except Exception as e:
        print(f"Blender ile FBX'e dönüştürme hatası: {e}")
        return None
    finally:
        for f in [temp_stl, temp_glb, temp_script]:
            if os.path.exists(f):
                os.remove(f)

def convert_to_glb(self, source_path=None):
    if source_path is None: source_path = dosya_secici_ac(parent=self)
    if not source_path: return None
    if not source_path.lower().endswith('.obj'):
        QMessageBox.warning(self, "Desteklenmeyen Format", "GLB formatına sadece OBJ dosyaları dönüştürülebilir.")
        return None
    
    default_name = os.path.splitext(os.path.basename(source_path))[0] + ".glb"
    save_path, _ = QFileDialog.getSaveFileName(self, "GLB Olarak Kaydet", default_name, "GLB Dosyası (*.glb)")
    if not save_path: return None
    
    try:
        original_props = get_mesh_properties(source_path)
        result_path = obj_to_glb(source_path)
        if result_path != save_path:
            import shutil
            shutil.move(result_path, save_path)
        
        new_props = get_mesh_properties(save_path)
        QMessageBox.information(self, "Başarılı", f"Dosya GLB formatına dönüştürüldü:\n{save_path}")
        return {"original": original_props, "new": new_props, "conversion_type": "OBJ -> GLB"}
    except Exception as e:
        QMessageBox.critical(self, "Hata", f"GLB'ye dönüştürme başarısız: {e}")
        return None

def convert_to_fbx(self, source_path=None):
    if source_path is None: source_path = dosya_secici_ac(parent=self)
    if not source_path: return None
    if not source_path.lower().endswith('.obj'):
        QMessageBox.warning(self, "Desteklenmeyen Format", "FBX formatına sadece OBJ dosyaları dönüştürülebilir.")
        return None

    default_name = os.path.splitext(os.path.basename(source_path))[0] + ".fbx"
    save_path, _ = QFileDialog.getSaveFileName(self, "FBX Olarak Kaydet", default_name, "FBX Dosyası (*.fbx)")
    if not save_path: return None

    try:
        blender_path = find_blender_executable()
        if not blender_path:
            QMessageBox.critical(self, "Hata", "Blender yürütülebilir dosyası bulunamadı. Dönüştürme iptal edildi.")
            return None

        result = obj_to_fbx(source_path, save_path, blender_path)
        if result:
            QMessageBox.information(self, "Başarılı", f"Dosya FBX formatına dönüştürüldü:\n{save_path}")
            return {"comparison_unavailable": True, "conversion_type": "OBJ -> FBX"}
        else:
            raise Exception("Dönüştürme işlemi başarısız oldu. Blender konsolunu kontrol edin.")
    except Exception as e:
        QMessageBox.critical(self, "Hata", f"FBX'e dönüştürme başarısız: {e}")
        return None

def convert_to_obj(self, source_path=None):
    if source_path is None: source_path = dosya_secici_ac(parent=self)
    if not source_path: return None
    if not source_path.lower().endswith('.stl'):
        QMessageBox.warning(self, "Desteklenmeyen Format", "OBJ formatına sadece STL dosyaları dönüştürülebilir.")
        return None

    default_name = os.path.splitext(os.path.basename(source_path))[0] + ".obj"
    save_path, _ = QFileDialog.getSaveFileName(self, "OBJ Olarak Kaydet", default_name, "OBJ Dosyası (*.obj)")
    if not save_path: return None
    
    try:
        original_props = get_mesh_properties(source_path)
        result_path = stl_to_obj(source_path)
        if result_path != save_path:
            import shutil
            shutil.move(result_path, save_path)
        new_props = get_mesh_properties(save_path)
        QMessageBox.information(self, "Başarılı", f"Dosya OBJ formatına dönüştürüldü:\n{save_path}")
        return {"original": original_props, "new": new_props, "conversion_type": "STL -> OBJ"}
    except Exception as e:
        QMessageBox.critical(self, "Hata", f"OBJ'ye dönüştürme başarısız: {e}")
        return None

def convert_to_step(self, source_path=None):
    from OCC.Extend.DataExchange import write_step_file, read_stl_file, read_iges_file
    if source_path is None: source_path = dosya_secici_ac(parent=self)
    if not source_path: return None
    
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
             return None
        else:
            QMessageBox.warning(self, "Desteklenmeyen Format", "Bu dosya formatı STEP'e dönüştürülemez.")
            return None

        if shape is None:
            raise ValueError("Dosya okunamadı veya boş.")

        default_name = os.path.splitext(os.path.basename(source_path))[0] + ".step"
        save_path, _ = QFileDialog.getSaveFileName(self, "STEP Olarak Kaydet", default_name, "STEP Dosyası (*.step *.stp)")
        if not save_path: return None

        write_step_file(shape, save_path)
        QMessageBox.information(self, "Başarılı", f"Dosya STEP formatına dönüştürüldü:\n{save_path}")
        # STEP dosyaları için Trimesh karşılaştırması yapılamaz
        return {"comparison_unavailable": True, "conversion_type": f"{ext.upper()} -> STEP"}
    except Exception as e:
        QMessageBox.critical(self, "Hata", f"STEP'e dönüştürme başarısız: {e}")
        return None

def convert_to_ply(self, source_path=None):
    import trimesh
    if source_path is None: source_path = dosya_secici_ac(parent=self)
    if not source_path: return None
    ext = os.path.splitext(source_path)[1].lower()
    if ext not in ['.obj', '.stl', '.glb']:
        QMessageBox.warning(self, "Desteklenmeyen Format", "PLY'ye sadece OBJ, STL veya GLB dosyaları dönüştürülebilir.")
        return None
    
    default_name = os.path.splitext(os.path.basename(source_path))[0] + ".ply"
    save_path, _ = QFileDialog.getSaveFileName(self, "PLY Olarak Kaydet", default_name, "PLY Dosyası (*.ply)")
    if not save_path: return None
    try:
        original_props = get_mesh_properties(source_path)
        mesh = trimesh.load(source_path, force='mesh')
        mesh.export(save_path, file_type='ply')
        new_props = get_mesh_properties(save_path)
        QMessageBox.information(self, "Başarılı", f"Dosya PLY formatına dönüştürüldü:\n{save_path}")
        return {"original": original_props, "new": new_props, "conversion_type": f"{ext.upper()} -> PLY"}
    except Exception as e:
        QMessageBox.critical(self, "Hata", f"PLY'ye dönüştürme başarısız: {e}")
        return None

def convert_to_gltf(self, source_path=None):
    import trimesh
    if source_path is None: source_path = dosya_secici_ac(parent=self)
    if not source_path: return None
    ext = os.path.splitext(source_path)[1].lower()
    if ext not in ['.obj', '.stl']:
        QMessageBox.warning(self, "Desteklenmeyen Format", "GLTF'ye sadece OBJ veya STL dosyaları dönüştürülebilir.")
        return None
    
    default_name = os.path.splitext(os.path.basename(source_path))[0] + ".gltf"
    save_path, _ = QFileDialog.getSaveFileName(self, "GLTF Olarak Kaydet", default_name, "GLTF Dosyası (*.gltf)")
    if not save_path: return None
    try:
        original_props = get_mesh_properties(source_path)
        mesh = trimesh.load(source_path, force='mesh')
        mesh.export(save_path, file_type='gltf')
        new_props = get_mesh_properties(save_path)
        QMessageBox.information(self, "Başarılı", f"Dosya GLTF formatına dönüştürüldü:\n{save_path}")
        return {"original": original_props, "new": new_props, "conversion_type": f"{ext.upper()} -> GLTF"}
    except Exception as e:
        QMessageBox.critical(self, "Hata", f"GLTF'ye dönüştürme başarısız: {e}")
        return None

def convert_to_3mf(self, source_path=None):
    import trimesh
    if source_path is None: source_path = dosya_secici_ac(parent=self)
    if not source_path: return None
    ext = os.path.splitext(source_path)[1].lower()
    if ext not in ['.obj', '.stl']:
        QMessageBox.warning(self, "Desteklenmeyen Format", "3MF'ye sadece OBJ veya STL dosyaları dönüştürülebilir.")
        return None
    
    default_name = os.path.splitext(os.path.basename(source_path))[0] + ".3mf"
    save_path, _ = QFileDialog.getSaveFileName(self, "3MF Olarak Kaydet", default_name, "3MF Dosyası (*.3mf)")
    if not save_path: return None
    try:
        original_props = get_mesh_properties(source_path)
        mesh = trimesh.load(source_path, force='mesh')
        mesh.export(save_path, file_type='3mf')
        new_props = get_mesh_properties(save_path)
        QMessageBox.information(self, "Başarılı", f"Dosya 3MF formatına dönüştürüldü:\n{save_path}")
        return {"original": original_props, "new": new_props, "conversion_type": f"{ext.upper()} -> 3MF"}
    except Exception as e:
        QMessageBox.critical(self, "Hata", f"3MF'ye dönüştürme başarısız: {e}")
        return None

def convert_to_dae(self, source_path=None):
    import trimesh
    if source_path is None: source_path = dosya_secici_ac(parent=self)
    if not source_path: return None
    ext = os.path.splitext(source_path)[1].lower()
    if ext not in ['.obj', '.stl']:
        QMessageBox.warning(self, "Desteklenmeyen Format", "DAE'ye sadece OBJ veya STL dosyaları dönüştürülebilir.")
        return None
    
    default_name = os.path.splitext(os.path.basename(source_path))[0] + ".dae"
    save_path, _ = QFileDialog.getSaveFileName(self, "DAE Olarak Kaydet", default_name, "DAE Dosyası (*.dae)")
    if not save_path: return None
    try:
        original_props = get_mesh_properties(source_path)
        mesh = trimesh.load(source_path, force='mesh')
        # DAE export için pycollada gerekebilir, kontrol edelim
        try:
            import collada
        except ImportError:
            QMessageBox.warning(self, "Eksik Kütüphane", "DAE formatına dönüştürmek için 'pycollada' kütüphanesi gereklidir.\nLütfen 'pip install pycollada' komutu ile kurun.")
            return None
        
        mesh.export(save_path, file_type='dae')
        new_props = get_mesh_properties(save_path)
        QMessageBox.information(self, "Başarılı", f"Dosya DAE formatına dönüştürüldü:\n{save_path}")
        return {"original": original_props, "new": new_props, "conversion_type": f"{ext.upper()} -> DAE"}
    except Exception as e:
        QMessageBox.critical(self, "Hata", f"DAE'ye dönüştürme başarısız: {e}")
        return None

def convert_step_to_stl(self, source_path=None):
    from OCC.Extend.DataExchange import read_step_file, read_iges_file
    from OCC.Core.StlAPI import StlAPI_Writer
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    if source_path is None: source_path = dosya_secici_ac(parent=self)
    if not source_path: return None
    ext = os.path.splitext(source_path)[1].lower()
    if ext not in ['.step', '.stp', '.iges', '.igs']:
        QMessageBox.warning(self, "Desteklenmeyen Format", "STL'ye sadece STEP veya IGES dosyaları dönüştürülebilir.")
        return None
    
    default_name = os.path.splitext(os.path.basename(source_path))[0] + ".stl"
    save_path, _ = QFileDialog.getSaveFileName(self, "STL Olarak Kaydet", default_name, "STL Dosyası (*.stl)")
    if not save_path: return None
    try:
        if ext in ['.step', '.stp']:
            shape = read_step_file(source_path)
        else:
            shape = read_iges_file(source_path)
        
        mesh = BRepMesh_IncrementalMesh(shape, 0.1)
        mesh.Perform()
        writer = StlAPI_Writer()
        writer.Write(shape, save_path)
        
        new_props = get_mesh_properties(save_path)
        # Orijinal STEP/IGES için Trimesh özellikleri alınamaz, bu yüzden None gönderiyoruz.
        QMessageBox.information(self, "Başarılı", f"Dosya STL formatına dönüştürüldü:\n{save_path}")
        return {"original": None, "new": new_props, "conversion_type": f"{ext.upper()} -> STL"}
    except Exception as e:
        QMessageBox.critical(self, "Hata", f"STL'ye dönüştürme başarısız: {e}")
        return None

def convert_step_to_obj(self, source_path=None):
    from OCC.Extend.DataExchange import read_step_file, read_iges_file
    import trimesh
    from OCC.Core.StlAPI import StlAPI_Writer
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    import tempfile, os
    if source_path is None: source_path = dosya_secici_ac(parent=self)
    if not source_path: return None
    ext = os.path.splitext(source_path)[1].lower()
    if ext not in ['.step', '.stp', '.iges', '.igs']:
        QMessageBox.warning(self, "Desteklenmeyen Format", "OBJ'ye sadece STEP veya IGES dosyaları dönüştürülebilir.")
        return None
    
    default_name = os.path.splitext(os.path.basename(source_path))[0] + ".obj"
    save_path, _ = QFileDialog.getSaveFileName(self, "OBJ Olarak Kaydet", default_name, "OBJ Dosyası (*.obj)")
    if not save_path: return None
    
    temp_stl = tempfile.mktemp(suffix='.stl')
    try:
        if ext in ['.step', '.stp']:
            shape = read_step_file(source_path)
        else:
            shape = read_iges_file(source_path)

        mesh = BRepMesh_IncrementalMesh(shape, 0.1)
        mesh.Perform()
        writer = StlAPI_Writer()
        writer.Write(shape, temp_stl)
        
        mesh_trimesh = trimesh.load(temp_stl, force='mesh')
        mesh_trimesh.export(save_path, file_type='obj')
        
        new_props = get_mesh_properties(save_path)
        QMessageBox.information(self, "Başarılı", f"Dosya OBJ formatına dönüştürüldü:\n{save_path}")
        return {"original": None, "new": new_props, "conversion_type": f"{ext.upper()} -> OBJ"}
    except Exception as e:
        QMessageBox.critical(self, "Hata", f"OBJ'ye dönüştürme başarısız: {e}")
        return None
    finally:
        if os.path.exists(temp_stl):
            os.remove(temp_stl)
