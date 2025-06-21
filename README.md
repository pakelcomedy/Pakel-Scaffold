# Pakel-Scaffold

**Pakel-Scaffold** is a lightweight CLI tool that helps you quickly generate project structures from a simple input prompt.  
It's like planting a Pakel tree: you define the shape, and the tool helps it grow.

## 🌱 Features
- Easy interactive CLI to input your custom project structure
- Supports nested folders and files
- Automatically creates placeholder files
- Add inline comments for each file (document your project structure from the start)
- Lightweight and zero dependencies

## 🚀 Installation
Clone the repository and run it directly with Python 3.8+:
```
git clone https://github.com/pakelcomedy/pakel-scaffold.git
cd pakel-scaffold
python make_project.py
```
---
```
Pakel-Scaffold/
├── 📁 docs/                # Semua aset publik (akan di-deploy ke GitHub Pages)
│   ├── 📄 index.html         # Halaman utama UI web
│   ├── 📄 styles.css         # Styling halaman
│   ├── 📄 script.js          # Logika frontend (parser, renderer, ZIP)
├── 📁 src/                   # Python tools (opsional tetap digunakan CLI)
│   └── 📄 make_project.py    # Script asli kamu (CLI tool)
├── 📄 .gitignore             # Git ignore file
├── 📄 readme.md              # Dokumentasi proyek
└── 📄 LICENSE                # (opsional) lisensi terbuka seperti MIT
```
