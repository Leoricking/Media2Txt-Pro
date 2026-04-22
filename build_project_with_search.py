import os, zipfile, textwrap

BASE = "youtube2txt_pro_search"

FILES = {
"main.py": r'''
import sys
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
''',

"requirements.txt": r'''
PySide6
yt-dlp
faster-whisper
requests
''',

"run.bat": r'''
@echo off
pip install -r requirements.txt
python main.py
pause
''',

"pipeline/downloader.py": r'''
import yt_dlp, os, shutil

def get_js_runtime():
    if shutil.which("node"): return "node"
    if shutil.which("deno"): return "deno"
    return None

def download_audio(url, progress_cb):
    os.makedirs("data", exist_ok=True)
    runtime = get_js_runtime()

    def hook(d):
        if d['status']=='downloading' and d.get('total_bytes'):
            p = d['downloaded_bytes']/d['total_bytes']*100
            progress_cb(int(p))
        elif d['status']=='finished':
            progress_cb(100)

    opts = {
        'format':'bestaudio/best',
        'outtmpl':'data/%(id)s.%(ext)s',
        'quiet':True,
        'progress_hooks':[hook],
        'cookiesfrombrowser':('chrome',),
    }

    if runtime:
        opts['js_runtimes']=[runtime]

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)
''',

"pipeline/transcriber.py": r'''
from faster_whisper import WhisperModel
model = WhisperModel("base", compute_type="int8")

def transcribe(audio, progress_cb):
    segments,_ = model.transcribe(audio)
    segs=list(segments)
    total=len(segs) or 1
    text=[]
    for i,s in enumerate(segs):
        text.append(s.text)
        progress_cb(int((i+1)/total*100))
    return " ".join(text)
''',

"pipeline/summarizer.py": r'''
import subprocess, shutil

def summarize(text):
    if not shutil.which("ollama"):
        return "⚠️ 未安裝 Ollama（略過摘要）"

    prompt=f"整理重點:\n{text}"
    try:
        r = subprocess.run(
            ["ollama","run","mistral"],
            input=prompt.encode("utf-8"),
            stdout=subprocess.PIPE
        )
        return r.stdout.decode("utf-8")
    except Exception as e:
        return f"摘要失敗:{e}"
''',

"pipeline/knowledge.py": r'''
import os
def save_note(title, content):
    os.makedirs("knowledge", exist_ok=True)
    name = title.replace("https://","").replace("/","_")[:50]
    with open(f"knowledge/{name}.txt","w",encoding="utf-8") as f:
        f.write(content)
''',

# 🔥 新增：搜尋（RAG）
"pipeline/search.py": r'''
import os, subprocess, shutil

def load_knowledge():
    texts=[]
    if not os.path.exists("knowledge"): return texts
    for f in os.listdir("knowledge"):
        with open(os.path.join("knowledge",f),encoding="utf-8") as file:
            texts.append(file.read())
    return texts

def search_answer(query):
    if not shutil.which("ollama"):
        return "⚠️ 未安裝 Ollama"

    docs = load_knowledge()
    context = "\n\n".join(docs[:5])  # 限制長度

    prompt=f"""
你是知識助手，根據以下內容回答問題：

內容：
{context}

問題：
{query}
"""

    try:
        r = subprocess.run(
            ["ollama","run","mistral"],
            input=prompt.encode("utf-8"),
            stdout=subprocess.PIPE
        )
        return r.stdout.decode("utf-8")
    except Exception as e:
        return f"搜尋失敗:{e}"
''',

"pipeline/task.py": r'''
from PySide6.QtCore import QObject, Signal, QRunnable
from pipeline.downloader import download_audio
from pipeline.transcriber import transcribe
from pipeline.summarizer import summarize
from pipeline.knowledge import save_note

class S(QObject):
    progress=Signal(int)
    status=Signal(str)
    result=Signal(str)
    done=Signal()

class Task(QRunnable):
    def __init__(self,url):
        super().__init__()
        self.url=url
        self.s=S()
        self.run_flag=True

    def stop(self):
        self.run_flag=False

    def run(self):
        try:
            if not self.run_flag:return
            self.s.status.emit("下載中")
            a=download_audio(self.url, lambda p:self.s.progress.emit(int(p*0.5)))

            if not self.run_flag:return
            self.s.status.emit("轉錄")
            t=transcribe(a, lambda p:self.s.progress.emit(50+int(p*0.3)))

            if not self.run_flag:return
            self.s.status.emit("摘要")
            s=summarize(t)

            full=f"===原文===\n{t}\n\n===摘要===\n{s}"
            save_note(self.url, full)

            self.s.result.emit(full)
            self.s.progress.emit(100)
            self.s.status.emit("完成")

        except Exception as e:
            self.s.status.emit(str(e))

        self.s.done.emit()
''',

# 🔥 UI（加搜尋框）
"ui/main_window.py": r'''
from PySide6.QtWidgets import *
from PySide6.QtCore import QThreadPool
import shutil
from pipeline.task import Task
from pipeline.search import search_answer

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube → AI 知識系統（搜尋版）")
        self.resize(900,700)

        self.pool=QThreadPool()
        self.tasks=[]
        self.done=0

        l=QVBoxLayout()

        self.env=QLabel("未檢查")
        self.btn_check=QPushButton("檢查環境")

        self.input=QTextEdit()
        self.start=QPushButton("開始")
        self.stop=QPushButton("停止")

        self.total=QProgressBar()
        self.list=QListWidget()
        self.out=QTextEdit()

        # 🔥 搜尋區
        self.query=QLineEdit()
        self.query.setPlaceholderText("輸入問題（查詢所有影片）")
        self.btn_search=QPushButton("AI 搜尋")

        for w in [self.env,self.btn_check,self.input,self.start,self.stop,
                  self.total,self.list,self.out,self.query,self.btn_search]:
            l.addWidget(w)

        self.setLayout(l)

        self.btn_check.clicked.connect(self.check)
        self.start.clicked.connect(self.run)
        self.stop.clicked.connect(self.stop_all)
        self.btn_search.clicked.connect(self.search)

        self.setStyleSheet("QWidget{background:#1e1e1e;color:white;} QPushButton{background:#3a86ff;}")

    def check(self):
        n="✔" if shutil.which("node") else "❌"
        o="✔" if shutil.which("ollama") else "❌"
        y="✔" if shutil.which("yt-dlp") else "❌"
        self.env.setText(f"Node:{n} Ollama:{o} yt-dlp:{y}")

    def run(self):
        urls=[u.strip() for u in self.input.toPlainText().split("\\n") if u.strip()]
        self.list.clear(); self.out.clear()
        self.tasks=[]; self.done=0

        for u in urls:
            item=QListWidgetItem(u)
            self.list.addItem(item)
            t=Task(u)

            t.s.progress.connect(lambda p,i=item:i.setText(f"{i.text().split('|')[0]} | {p}%"))
            t.s.status.connect(lambda s,i=item:i.setText(f"{i.text().split('|')[0]} | {s}"))
            t.s.result.connect(self.out.append)
            t.s.done.connect(self.update)

            self.tasks.append(t)
            self.pool.start(t)

    def stop_all(self):
        for t in self.tasks: t.stop()

    def update(self):
        self.done+=1
        total=len(self.tasks)
        if total:
            self.total.setValue(int(self.done/total*100))

    def search(self):
        q=self.query.text().strip()
        if not q:
            self.out.append("⚠️ 請輸入問題")
            return
        ans=search_answer(q)
        self.out.append("\\n=== AI 回答 ===\\n"+ans+"\\n")
'''
}

# 建檔
for path, content in FILES.items():
    full = os.path.join(BASE, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(textwrap.dedent(content).strip()+"\n")

# 打包
zip_name = BASE + ".zip"
with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as z:
    for root,_,files in os.walk(BASE):
        for f in files:
            p=os.path.join(root,f)
            z.write(p, arcname=os.path.relpath(p, BASE))

print("✅ 已產生:", zip_name)