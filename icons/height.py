import os
from PIL import Image

# 검사할 폴더 경로
folder = r"C:\Users\pipupang\Desktop\isaac\icons\items"

max_h = 0
max_file = None

for fn in os.listdir(folder):
    if fn.lower().endswith((".png", ".jpg", ".jpeg")):
        path = os.path.join(folder, fn)
        try:
            with Image.open(path) as img:
                w, h = img.size
                if h > max_h:
                    max_h = h
                    max_file = fn
        except Exception as e:
            print(f"[WARN] {fn} 열기 실패: {e}")

if max_file:
    print(f"✅ 가장 세로가 큰 파일: {max_file} ({max_h}px)")
else:
    print("이미지를 찾지 못했음")
