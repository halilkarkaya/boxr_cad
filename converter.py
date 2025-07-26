## \file converter.py
## \brief 3D model dosya formatları arasında dönüşüm fonksiyonları (OBJ, STL, GLB)
import trimesh
import os
import subprocess
import tempfile
from PyQt5.QtWidgets import QFileDialog, QMessageBox

## \fn dosya_secici_ac(parent=None)
#  \brief OBJ, STL, STEP, ve IGES dosyalarını seçmek için dosya seçici açar.
#  \param parent QWidget veya None, dosya seçici için ebeveyn pencere.
#  \return Seçilen dosya yolu (str) veya None.
def dosya_secici_ac(parent=None):
    file_path, _ = QFileDialog.getOpenFileName(
        parent, "3D Model Dosyası Aç", "", 
        "Tüm Desteklenen Formatlar (*.obj *.stl *.step *.stp *.iges *.igs);;"
        "Mesh Dosyaları (*.obj *.stl);;"
        "CAD Dosyaları (*.step *.stp *.iges *.igs);;"
        "Tüm Dosyalar (*.*)"
    )
    return file_path or None

## \fn obj_to_stl(obj_path)
#  \brief OBJ dosyasını geçici bir STL dosyasına dönüştürür.
#  \param obj_path Kaynak OBJ dosya yolu (str).
#  \return Oluşan geçici STL dosya yolu (str).
def obj_to_stl(obj_path):
    temp_dir = tempfile.gettempdir()
    temp_stl = os.path.join(temp_dir, "temp_obj_conversion.stl")
    mesh = trimesh.load(obj_path, force='mesh')
    mesh.export(temp_stl, file_type='stl')
    return temp_stl

## \fn obj_to_glb(obj_path)
#  \brief OBJ dosyasını GLB formatına dönüştürür.
#  \param obj_path Kaynak OBJ dosya yolu (str)
#  \return Oluşan GLB dosya yolu (str)
def obj_to_glb(obj_path):
    mesh = trimesh.load(obj_path, force='mesh')
    glb_path = os.path.splitext(obj_path)[0] + ".glb"
    mesh.export(glb_path, file_type='glb')
    return glb_path

## \fn stl_to_obj(stl_path)
#  \brief STL dosyasını OBJ formatına dönüştürür.
#  \param stl_path Kaynak STL dosya yolu (str)
#  \return Oluşan OBJ dosya yolu (str)
def stl_to_obj(stl_path):
    mesh = trimesh.load(stl_path, force='mesh')
    obj_path = os.path.splitext(stl_path)[0] + ".obj"
    mesh.export(obj_path, file_type='obj')
    return obj_path

def obj_to_fbx(obj_path, fbx_path, blender_path=r"D:\\blender\\blender-launcher.exe"):
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
        result_path = obj_to_glb(source_path)
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
        blender_path = r'D:\\blender\\blender-launcher.exe'
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
    temp_stl = tempfile.mktemp(suffix='.stl')
    try:
        mesh = BRepMesh_IncrementalMesh(shape, 0.1)
        mesh.Perform()
        writer = StlAPI_Writer()
        writer.Write(shape, temp_stl)
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