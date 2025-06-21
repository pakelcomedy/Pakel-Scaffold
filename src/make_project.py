#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Structure Creator – Versi Ditingkatkan dan Lebih Kompleks

Fitur:
    - Parse ASCII-tree (box-drawing characters atau spasi biasa) dari stdin atau file.
    - Dukungan indentasi campuran.
    - Opsi dry-run, no-confirm, verbose.
    - Opsi output JSON.
    - Opsi templates untuk mengisi konten otomatis.
    - Opsi exclude dengan pola (regex).
    - Validasi error/parsing yang lebih ketat.
    - Ringkasan akhir (jumlah direktori/file dibuat/skip).
"""

import sys
import re
import argparse
import logging
import json
from pathlib import Path
from typing import List, Optional, Dict, Union, Pattern
from dataclasses import dataclass, field

# ----- KODE UNTUK MENGHADIRKAN WARNA DI TERMINAL (ANSI) -----
class Colors:
    HEADER    = "\033[95m"
    OKBLUE    = "\033[94m"
    OKGREEN   = "\033[92m"
    WARNING   = "\033[93m"
    FAIL      = "\033[91m"
    ENDC      = "\033[0m"

def colorize(msg: str, color: str) -> str:
    return f"{color}{msg}{Colors.ENDC}"

# ----- DEFINISI NODE UNTUK POHON STRUKTUR -----
@dataclass
class Node:
    name: str
    parent: Optional['DirectoryNode']

    def full_path(self) -> Path:
        raise NotImplementedError

    def to_dict(self) -> Dict[str, Union[str, bool, List]]:
        raise NotImplementedError

@dataclass
class DirectoryNode(Node):
    children: List['Node'] = field(default_factory=list)

    def full_path(self) -> Path:
        if self.parent:
            return self.parent.full_path() / self.name
        else:
            return Path(self.name)

    def add_child(self, child: 'Node'):
        # Abaikan duplicate di level yang sama
        if any(c.name == child.name for c in self.children):
            logging.getLogger('ProjectCreator').debug(
                colorize(f"[SKIP] Duplicate '{child.name}' under '{self.name}'", Colors.WARNING)
            )
            return
        self.children.append(child)

    def to_dict(self) -> Dict[str, Union[str, bool, List]]:
        return {
            "name": self.name,
            "is_dir": True,
            "children": [c.to_dict() for c in self.children],
        }

@dataclass
class FileNode(Node):
    def full_path(self) -> Path:
        if self.parent:
            return self.parent.full_path() / self.name
        else:
            return Path(self.name)

    def to_dict(self) -> Dict[str, Union[str, bool]]:
        return {
            "name": self.name,
            "is_dir": False
        }

# ----- EKSEPSI KETIKA PARSING GAGAL -----
class ParseError(Exception):
    """Exception for parsing errors."""
    pass

# ----- PARSER ASCII-TREE YANG DITINGKATKAN -----
class ProjectTreeParser:
    """
    Parser untuk ASCII-tree / ASCII-art yang mendukung:
      - Box-drawing characters (│ ├ └ ─) atau spasi biasa.
      - Inline nested paths (folder1/folder2/file.txt).
      - Trailing slash "/" menandakan directory.
      - Pengecualian baris yang hanya box-drawing.
    """

    # Regex untuk mendeteksi baris yang hanya berisi grafis box-drawing/spasi
    _pure_tree_art = re.compile(r'^[\s│├└─]+$')

    def __init__(self, indent_width: int = 4):
        """
        indent_width: Berapa banyak karakter (spasi atau 1 box-drawing unit setara indent_width)
                      dianggap satu level indentasi.
        """
        self.indent_width = indent_width

    def parse(self, raw: str) -> DirectoryNode:
        # 1) Hapus komentar (setelah '#') dan skip baris kosong
        lines: List[tuple[str, str]] = []
        for i, line in enumerate(raw.splitlines(), start=1):
            orig = line.rstrip('\n')
            txt = orig.split('#', 1)[0].rstrip()
            if txt.strip():
                lines.append((i, orig, txt))
        if not lines:
            raise ParseError("Input kosong atau semuanya komentar.")

        # 2) Filter out baris yang hanya grafis box-drawing/spasi
        filtered: List[tuple[int, str, str]] = [
            (lineno, o, t) for lineno, o, t in lines
            if not self._pure_tree_art.match(t)
        ]
        if not filtered:
            raise ParseError("Tidak ada entri valid (semua baris adalah grafis).")

        # 3) Baris pertama (setelah filter) dianggap root
        root_lineno, root_orig, root_txt = filtered[0]
        root_name = root_txt.rstrip('/ ').strip()
        if not root_name:
            raise ParseError(f"Baris {root_lineno}: Nama root kosong.")
        root = DirectoryNode(name=root_name, parent=None)
        stack: List[DirectoryNode] = [root]

        # 4) Proses baris selanjutnya
        for lineno, orig, txt in filtered[1:]:
            # Menentukan posisi indentasi
            # Hitung “level” berdasarkan:
            #   - Berapa banyak box-drawing char sebelum teks
            #   - Atau jika spasi, setiap indent_width spasi = 1 level
            # Cari index dari box-drawing cut ('├' atau '└')
            cuts = [txt.find('├') if '├' in txt else None,
                    txt.find('└') if '└' in txt else None]
            cuts = [c for c in cuts if c is not None and c >= 0]
            if cuts:
                cut_idx = min(cuts)
            else:
                # Kalau tidak ada box-drawing, hitung spasi di awal
                leading_spaces = len(txt) - len(txt.lstrip(' '))
                cut_idx = leading_spaces

            level = cut_idx // self.indent_width

            # Deteksi apakah entri ini direktori (txt diakhiri '/')
            is_dir = txt.strip().endswith('/')

            # Ekstrak nama (setelah box-drawing); hapus karakter grafis
            # Hapus semua karakter '│', '├', '└', '─' serta spasi di depan
            names_raw = re.sub(r'^[\s│├└─]+', '', txt).strip()
            # Jika ada trailing '/', hapus agar tidak jadi bagian nama
            if names_raw.endswith('/'):
                names_raw = names_raw[:-1]

            if not names_raw:
                # Baris ini sepertinya hanya grafis, skip saja
                continue

            # Bisa berupa nested inline (folder1/folder2/file)
            parts = [p.strip() for p in names_raw.split('/') if p.strip()]
            if not parts:
                continue

            # Validasi indentasi: level maksimal = len(stack)-1
            if level + 1 > len(stack):
                raise ParseError(
                    f"Baris {lineno}: Indentasi terlalu dalam (level {level}, max {len(stack)-1})."
                )
            # Turun / naik ke parent yang sesuai
            while len(stack) > level + 1:
                stack.pop()
            parent = stack[-1]

            # Buat node untuk setiap bagian
            for idx, name in enumerate(parts):
                last = (idx == len(parts) - 1)
                # Tentukan kelas: directory atau file
                if not last:
                    cls = DirectoryNode
                else:
                    if is_dir:
                        cls = DirectoryNode
                    elif Path(name).suffix:
                        cls = FileNode
                    else:
                        # Jika nama tidak memiliki ekstensi tapi tidak diakhiri slash,
                        # anggap file “tanpa ekstensi”.
                        cls = FileNode

                node = cls(name=name, parent=parent)
                parent.add_child(node)

                if isinstance(node, DirectoryNode):
                    # Jika ini directory, turunkan parent
                    parent = node
                    stack.append(node)

        return root

# ----- KELAS UNTUK MEMBUAT FILE/FOLDER DARI NODE -----
class FileSystemCreator:
    """
    Menciptakan direktori dan file berdasarkan DirectoryNode.
      - dry_run: Jika True, hanya logging, tidak benar-benar membuat.
      - confirm: Jika True, akan prompt [y/N] sebelum mulai.
      - templates_dir: Jika diset, gunakan file dari sini sebagai template isi file.
      - exclude_patterns: Daftar regex untuk mengecualikan nama path tertentu.
    """

    def __init__(self,
                 dry_run: bool = False,
                 confirm: bool = True,
                 templates_dir: Optional[Path] = None,
                 exclude_patterns: Optional[List[Pattern[str]]] = None):
        self.dry_run = dry_run
        self.confirm = confirm
        self.templates_dir = templates_dir
        self.exclude_patterns = exclude_patterns or []
        self.logger = logging.getLogger('ProjectCreator')
        # Statistik
        self.count_dirs_created = 0
        self.count_files_created = 0
        self.count_skipped = 0

    def _matches_exclude(self, rel_path: Path) -> bool:
        """
        Cek apakah rel_path (relatif terhadap root) cocok salah satu pattern exclude.
        """
        s = str(rel_path)
        for pat in self.exclude_patterns:
            if pat.search(s):
                self.logger.debug(colorize(f"[EXCLUDE] '{s}' dicekal oleh pattern '{pat.pattern}'", Colors.WARNING))
                return True
        return False

    def _get_template_content(self, filename: str) -> Optional[str]:
        """
        Jika ada templates_dir, dan di dalamnya ada file dengan nama filename,
        baca dan kembalikan kontennya.
        """
        if not self.templates_dir:
            return None
        tpl_path = self.templates_dir / filename
        if tpl_path.is_file():
            try:
                return tpl_path.read_text(encoding='utf-8')
            except Exception as e:
                self.logger.warning(colorize(f"[TEMPLATE READ ERROR] {e}", Colors.FAIL))
        return None

    def _create_dir(self, path: Path, rel_path: Path):
        if self._matches_exclude(rel_path):
            self.count_skipped += 1
            return

        if self.dry_run:
            self.logger.info(colorize(f"[DRY-RUN] mkdir {path}", Colors.OKBLUE))
        else:
            path.mkdir(parents=True, exist_ok=True)
            self.logger.info(colorize(f"[DIR] {path}", Colors.OKGREEN))
        self.count_dirs_created += 1

    def _create_file(self, path: Path, rel_path: Path):
        if self._matches_exclude(rel_path):
            self.count_skipped += 1
            return

        content = self._get_template_content(path.name)
        if self.dry_run:
            self.logger.info(colorize(f"[DRY-RUN] touch {path}", Colors.OKBLUE))
            if content:
                self.logger.info(colorize(f"         -> would fill from template '{self.templates_dir/path.name}'", Colors.OKBLUE))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            if content is not None:
                # Buat file dengan isi template
                try:
                    path.write_text(content, encoding='utf-8')
                    self.logger.info(colorize(f"[FILE+TEMPLATE] {path}", Colors.OKGREEN))
                except Exception as e:
                    self.logger.warning(colorize(f"[FILE ERROR] Gagal menulis '{path}': {e}", Colors.FAIL))
            else:
                # Buat file kosong
                try:
                    path.touch(exist_ok=True)
                    self.logger.info(colorize(f"[FILE] {path}", Colors.OKGREEN))
                except Exception as e:
                    self.logger.warning(colorize(f"[FILE ERROR] Gagal membuat '{path}': {e}", Colors.FAIL))
        self.count_files_created += 1

    def execute(self, root: DirectoryNode, export_json: Optional[Path] = None):
        """
        Rekursif membuat direktori dan file.
        Jika export_json tidak None, simpan representasi tree ke JSON.
        """
        if self.confirm and not self.dry_run:
            try:
                ans = input(colorize("Proceed with creation? [y/N]: ", Colors.WARNING)).strip().lower()
            except (KeyboardInterrupt, EOFError):
                self.logger.warning(colorize("Operation cancelled by user.", Colors.FAIL))
                sys.exit(1)
            if ans != 'y':
                self.logger.warning(colorize("Operation aborted.", Colors.WARNING))
                sys.exit(1)

        root_path = root.full_path()

        def recurse(node: Union[DirectoryNode, FileNode], base_path: Path, rel_base: Path):
            """
            - node: Node yang sedang diproses.
            - base_path: Path full di FS.
            - rel_base: Path relatif terhadap root, untuk pengecekan exclude.
            """
            current_path = base_path / node.name
            current_rel = rel_base / node.name

            if isinstance(node, DirectoryNode):
                self._create_dir(current_path, current_rel)
                for child in node.children:
                    recurse(child, current_path, current_rel)
            else:
                self._create_file(current_path, current_rel)

        # Mulai rekursi
        recurse(root, Path('.'), Path(''))

        # Ekspor JSON jika diminta
        if export_json:
            try:
                data = root.to_dict()
                export_json.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
                self.logger.info(colorize(f"[JSON] Struktur diekspor ke '{export_json}'", Colors.OKBLUE))
            except Exception as e:
                self.logger.warning(colorize(f"[JSON ERROR] Gagal menulis '{export_json}': {e}", Colors.FAIL))

        # Tampilkan ringkasan
        self.logger.info(colorize("✔ Project structure creation complete.", Colors.OKGREEN))
        self.logger.info(colorize(f"   Direktori dibuat: {self.count_dirs_created}", Colors.OKBLUE))
        self.logger.info(colorize(f"   File dibuat    : {self.count_files_created}", Colors.OKBLUE))
        self.logger.info(colorize(f"   Dilewati (exclude/duplicate): {self.count_skipped}", Colors.WARNING))


# ----- FUNGSI UNTUK MEMBACA MULTILINE INPUT -----
def read_multiline_input(prompt: str = "Enter project structure (akhiri dengan baris kosong):") -> str:
    print(colorize(prompt, Colors.HEADER))
    lines: List[str] = []
    try:
        while True:
            line = input()
            if not line.strip():
                break
            lines.append(line)
    except (EOFError, KeyboardInterrupt):
        pass
    return '\n'.join(lines)


# ----- SETUP LOGGER ----- 
def setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(message)s"
    logging.basicConfig(level=level, format=fmt)


# ----- FUNGSI UTAMA ----- 
def main():
    parser = argparse.ArgumentParser(
        description="Create project structure from ASCII-tree input (dengan opsi lanjutan)."
    )
    parser.add_argument("-d", "--dry-run", action="store_true",
                        help="Simulasi tanpa benar-benar membuat file/folder.")
    parser.add_argument("--no-confirm", action="store_true",
                        help="Lewati prompt konfirmasi dan langsung eksekusi.")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Tampilkan log DEBUG.")
    parser.add_argument("--output-json", metavar="FILE.JSON",
                        help="Ekspor struktur pohon ke file JSON.")
    parser.add_argument("--templates-dir", metavar="TEMPLATE_DIR",
                        help="Gunakan direktori untuk template file (jika nama sama, konten akan di-copy).")
    parser.add_argument("--exclude", metavar="REGEX", action="append",
                        help="Pola (regex) untuk mengecualikan pembuatan file/folder. Bisa dipanggil berulang.")

    args = parser.parse_args()
    setup_logging(args.verbose)
    logger = logging.getLogger('ProjectCreator')

    # Siapkan daftar pola exclude
    exclude_patterns: List[Pattern[str]] = []
    if args.exclude:
        for pat in args.exclude:
            try:
                exclude_patterns.append(re.compile(pat))
            except re.error as e:
                logger.error(colorize(f"[REGEX ERROR] Pola '{pat}' tidak valid: {e}", Colors.FAIL))
                sys.exit(1)

    # Siapkan templates_dir
    templates_dir: Optional[Path] = None
    if args.templates_dir:
        templates_dir = Path(args.templates_dir)
        if not templates_dir.is_dir():
            logger.error(colorize(f"[TEMPLATE ERROR] '{templates_dir}' bukan direktori valid.", Colors.FAIL))
            sys.exit(1)

    try:
        tree_str = read_multiline_input()
        if not tree_str.strip():
            logger.error(colorize("Tidak ada input terdeteksi. Keluar.", Colors.FAIL))
            sys.exit(1)

        parser_obj = ProjectTreeParser(indent_width=4)
        root_node = parser_obj.parse(tree_str)

        creator = FileSystemCreator(
            dry_run=args.dry_run,
            confirm=not args.no_confirm,
            templates_dir=templates_dir,
            exclude_patterns=exclude_patterns
        )

        export_json_path = Path(args.output_json) if args.output_json else None
        creator.execute(root_node, export_json=export_json_path)
    except ParseError as e:
        logger.error(colorize(f"Parse Error: {e}", Colors.FAIL))
        sys.exit(1)
    except KeyboardInterrupt:
        logger.warning(colorize("Dibatalkan oleh pengguna.", Colors.FAIL))
        sys.exit(1)
    except Exception as e:
        logger.exception(colorize(f"Unhandled Error: {e}", Colors.FAIL))
        sys.exit(1)


if __name__ == "__main__":
    main()
