#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Structure Creator - Ignore Duplicates

Membaca ASCII-tree input dari stdin, parsing dengan menghitung
level berdasar box-drawing chars, lalu membuat direktori/file.
Jika menemukan duplikat di satu parent, akan diabaikan.
"""

import sys
import re
import argparse
import logging
from pathlib import Path
from typing import List, Optional, Union
from dataclasses import dataclass, field

# ANSI color codes untuk output CLI yang lebih enak dibaca
class Colors:
    HEADER    = "\033[95m"
    OKBLUE    = "\033[94m"
    OKGREEN   = "\033[92m"
    WARNING   = "\033[93m"
    FAIL      = "\033[91m"
    ENDC      = "\033[0m"

def colorize(msg: str, color: str) -> str:
    return f"{color}{msg}{Colors.ENDC}"

@dataclass
class Node:
    name: str
    parent: Optional['DirectoryNode']

    def full_path(self) -> Path:
        raise NotImplementedError

@dataclass
class DirectoryNode(Node):
    children: List[Node] = field(default_factory=list)

    def full_path(self) -> Path:
        return (self.parent.full_path() / self.name) if self.parent else Path(self.name)

    def add_child(self, child: Node):
        # Jika sudah ada, skip tanpa error
        if any(c.name == child.name for c in self.children):
            logging.getLogger('ProjectCreator').debug(
                colorize(f"[SKIP] Duplicate '{child.name}' under '{self.name}'", Colors.WARNING)
            )
            return
        self.children.append(child)

@dataclass
class FileNode(Node):
    def full_path(self) -> Path:
        return (self.parent.full_path() / self.name) if self.parent else Path(self.name)

class ParseError(Exception):
    pass

class ProjectTreeParser:
    """
    Parser untuk ASCII-tree project structure.
    Level ditentukan dari jumlah '│' sebelum '├' / '└'.
    Mendukung multi-file per-barus: "file1 / file2".
    """
    _empty_line_re = re.compile(r'^[\s│├└─]+$')

    def parse(self, raw: str) -> DirectoryNode:
        all_lines = raw.strip().splitlines()
        lines = [
            l for l in all_lines
            if l.strip() and not self._empty_line_re.match(l)
        ]
        if not lines:
            raise ParseError("Input kosong.")

        root_name = lines[0].rstrip('/ ')
        root = DirectoryNode(name=root_name, parent=None)
        stack: List[DirectoryNode] = [root]

        for lineno, raw_line in enumerate(lines[1:], start=2):
            # hitung level berdasarkan '│'
            cut_idx = min(
                [i for i in (raw_line.find('├'), raw_line.find('└')) if i != -1] or
                [len(raw_line)]
            )
            prefix = raw_line[:cut_idx]
            level = prefix.count('│')

            # ekstrak sisa nama
            names_part = raw_line[cut_idx:].lstrip('├└─ ').rstrip().rstrip('/')
            if not names_part:
                continue

            # split jika ada " / "
            name_list = [n.strip() for n in names_part.split('/')]

            if level + 1 > len(stack):
                raise ParseError(f"Line {lineno}: indentasi terlalu dalam (level {level})")
            while len(stack) > level+1:
                stack.pop()
            parent = stack[-1]

            for name in name_list:
                if not name:
                    continue
                node_cls = FileNode if Path(name).suffix else DirectoryNode
                node = node_cls(name=name, parent=parent)
                parent.add_child(node)
                if isinstance(node, DirectoryNode):
                    stack.append(node)

        return root

class FileSystemCreator:
    """Buat folder & file dari DirectoryNode rekursif."""
    def __init__(self, dry_run: bool=False, confirm: bool=True):
        self.dry_run = dry_run
        self.confirm = confirm
        self.logger = logging.getLogger('ProjectCreator')

    def _create_dir(self, path: Path):
        if self.dry_run:
            self.logger.info(colorize(f"[DRY-RUN] mkdir {path}", Colors.OKBLUE))
        else:
            path.mkdir(parents=True, exist_ok=True)
            self.logger.info(colorize(f"Created dir : {path}", Colors.OKGREEN))

    def _create_file(self, path: Path):
        if self.dry_run:
            self.logger.info(colorize(f"[DRY-RUN] touch {path}", Colors.OKBLUE))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(exist_ok=True)
            self.logger.info(colorize(f"Created file: {path}", Colors.OKGREEN))

    def execute(self, root: DirectoryNode):
        if self.confirm and not self.dry_run:
            ans = input(colorize("Proceed with creation? [y/N]: ", Colors.WARNING))
            if ans.lower() != 'y':
                self.logger.warning("Operation cancelled.")
                sys.exit(1)

        def recurse(node: Union[DirectoryNode, FileNode]):
            p = node.full_path()
            if isinstance(node, DirectoryNode):
                self._create_dir(p)
                for child in node.children:
                    recurse(child)
            else:
                self._create_file(p)

        recurse(root)

def read_multiline_input(prompt: str="Masukkan struktur project (akhiri dengan baris kosong):") -> str:
    print(colorize(prompt, Colors.HEADER))
    lines: List[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if not line.strip():
            break
        lines.append(line)
    return '\n'.join(lines)

def setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(message)s")

def main():
    parser = argparse.ArgumentParser(description="Create project structure from ASCII-tree input.")
    parser.add_argument("-d", "--dry-run", action="store_true", help="Simulate only, tanpa eksekusi.")
    parser.add_argument("--no-confirm", action="store_true", help="Lewati konfirmasi.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Logging debug.")
    args = parser.parse_args()

    setup_logging(args.verbose)
    logger = logging.getLogger('ProjectCreator')

    try:
        tree_str = read_multiline_input()
        if not tree_str.strip():
            logger.error(colorize("Tidak ada input. Keluar.", Colors.FAIL))
            sys.exit(1)

        parser_obj = ProjectTreeParser()
        root_node = parser_obj.parse(tree_str)

        creator = FileSystemCreator(dry_run=args.dry_run, confirm=not args.no_confirm)
        creator.execute(root_node)

        logger.info(colorize("✔ Selesai.", Colors.OKBLUE))
    except Exception as e:
        logger.error(colorize(f"Error: {e}", Colors.FAIL))
        sys.exit(1)

if __name__ == "__main__":
    main()
