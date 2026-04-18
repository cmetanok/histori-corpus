import base64
with open("menaion.ttf", "rb") as f: # укажите имя вашего файла шрифта
    print(base64.b64encode(f.read()).decode())