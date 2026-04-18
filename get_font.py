import base64
import os

# Указываем имя вашего файла
font_filename = "menaionunicode.otf"

if os.path.exists(font_filename):
    with open(font_filename, "rb") as f:
        encoded_string = base64.b64encode(f.read()).decode()
        # Сохраняем в файл, так как строка будет очень длинной
        with open("font_base64.txt", "w") as out:
            out.write(encoded_string)
    print("✅ Готово! Код сохранен в файл font_base64.txt. Скопируйте его содержимое.")
else:
    print(f"❌ Файл {font_filename} не найден в папке!")