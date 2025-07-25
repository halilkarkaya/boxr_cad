## \file converter.py
## \brief 3D model dosya formatları arasında dönüşüm fonksiyonları (OBJ, STL, GLB)
import trimesh
import os
import subprocess
import tempfile

## \fn obj_to_glb(obj_path)
#  \brief OBJ dosyasını GLB formatına dönüştürür.
#  \param obj_path Kaynak OBJ dosya yolu (str)
#  \return Oluşan GLB dosya yolu (str)
def obj_to_glb(obj_path):
    """
    OBJ dosyasını GLB formatına dönüştürür.
    :param obj_path: Kaynak OBJ dosya yolu
    :return: Oluşan GLB dosya yolu
    """
    mesh = trimesh.load(obj_path, force='mesh')  # OBJ dosyasını yükle
    glb_path = os.path.splitext(obj_path)[0] + ".glb"  # GLB dosya yolu oluştur
    mesh.export(glb_path, file_type='glb')  # GLB olarak dışa aktar
    return glb_path  # GLB dosya yolunu döndür

## \fn stl_to_obj(stl_path)
#  \brief STL dosyasını OBJ formatına dönüştürür.
#  \param stl_path Kaynak STL dosya yolu (str)
#  \return Oluşan OBJ dosya yolu (str)
def stl_to_obj(stl_path):
    """
    STL dosyasını OBJ formatına dönüştürür.
    :param stl_path: Kaynak STL dosya yolu
    :return: Oluşan OBJ dosya yolu
    """
    mesh = trimesh.load(stl_path, force='mesh')  # STL dosyasını yükle
    obj_path = os.path.splitext(stl_path)[0] + ".obj"  # OBJ dosya yolu oluştur
    mesh.export(obj_path, file_type='obj')  # OBJ olarak dışa aktar
    return obj_path  # OBJ dosya yolunu döndür

def obj_to_stl(obj_path):
    """
    OBJ dosyasını STL formatına dönüştürür.
    :param obj_path: Kaynak OBJ dosya yolu
    :return: Oluşan STL dosya yolu
    """
    mesh = trimesh.load(obj_path, force='mesh')
    stl_path = os.path.splitext(obj_path)[0] + ".stl"
    mesh.export(stl_path, file_type='stl')
    return stl_path

def obj_to_fbx(obj_path, fbx_path, blender_path=r"D:\\blender\\blender-launcher.exe"):
    """
    OBJ dosyasını önce STL'ye, sonra GLB'ye, ardından Blender ile FBX'e dönüştürür.
    :param obj_path: Kaynak OBJ dosya yolu
    :param fbx_path: Hedef FBX dosya yolu
    :param blender_path: Blender uygulamasının tam yolu
    :return: Oluşan FBX dosya yolu veya None
    """
    temp_dir = tempfile.gettempdir()
    temp_stl = os.path.join(temp_dir, "temp_obj2fbx.stl")
    temp_glb = os.path.join(temp_dir, "temp_obj2fbx.glb")
    try:
        # OBJ'den STL'ye
        mesh = trimesh.load(obj_path, force='mesh')
        mesh.export(temp_stl, file_type='stl')
        # STL'den GLB'ye
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


