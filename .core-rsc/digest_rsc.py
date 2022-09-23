import sqlite3

db = sqlite3.connect('ressources.db')
cursor = db.cursor()

with open(r"C:\Users\DEV\Downloads\ffprobe.exe", 'rb') as f:
    pdf_data = f.read()

cursor.execute('INSERT INTO files ("name", "data", "local") VALUES ("ffprobe.exe", ?, 1)', (pdf_data,))

with open(r"C:\Users\DEV\Downloads\ffmpeg.exe", 'rb') as f:
    pdf_data = f.read()

cursor.execute('INSERT INTO files ("name", "data", "local") VALUES ("ffmpeg.exe", ?, 1)', (pdf_data,))


with open(r"ressources.py", 'rb') as f:
    pdf_data = f.read()

cursor.execute('INSERT INTO files ("name", "data", "local") VALUES ("ressources.py", ?, 0)', (pdf_data,))

db.commit()