from PIL import Image
src = "UDC.png"
img = Image.open(src).convert("RGBA")
# Сохранить набор стандартных размеров для Windows
img.save("icon.ico", sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])
print("Готово: icon.ico")