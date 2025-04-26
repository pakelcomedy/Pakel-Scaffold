#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Structure Creator - Ignore Duplicates (with inline comment & trailing-slash support)

Reads an ASCII-tree from stdin (you can include “# comments” at end of lines),
parses levels based on box-drawing characters, honors trailing “/” for directories,
then creates directories/files.  Ignores duplicates under the same parent.
"""

import sys
import re
import argparse
import logging
from pathlib import Path
from typing import List, Optional, Union
from dataclasses import dataclass, field

# ANSI color codes for CLI output
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
    children: List['Node'] = field(default_factory=list)

    def full_path(self) -> Path:
        return (self.parent.full_path() / self.name) if self.parent else Path(self.name)

    def add_child(self, child: 'Node'):
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
    """Exception for parsing errors."""
    pass

class ProjectTreeParser:
    """Parser for ASCII-tree project structures, honoring trailing “/” for dirs."""

    _pure_tree_art = re.compile(r'^[\s│├└─]+$')

    def parse(self, raw: str) -> DirectoryNode:
        # 1) Remove comments (anything after '#') but remember trailing slash in original
        lines = []
        for line in raw.splitlines():
            # keep original to detect trailing slash
            text = line.split('#', 1)[0].rstrip('\n')
            if text.strip():  # skip empty after comment removal
                lines.append((line, text))

        # 2) Filter out lines that are just tree-art (│ ├ ─ etc)
        filtered = []
        for orig, txt in lines:
            if not self._pure_tree_art.match(txt):
                filtered.append((orig, txt))
        if not filtered:
            raise ParseError("Empty or invalid input.")

        # 3) First non-art line is root
        root_orig, root_txt = filtered[0]
        root_name = root_txt.rstrip('/ ').strip()
        root = DirectoryNode(name=root_name, parent=None)
        stack: List[DirectoryNode] = [root]

        # process children
        for lineno, (orig, txt) in enumerate(filtered[1:], start=2):
            # find tree-art cutoff
            cut_positions = [i for i in (txt.find('├'), txt.find('└')) if i != -1]
            cut_idx = min(cut_positions) if cut_positions else 0

            prefix = txt[:cut_idx]
            level = prefix.count('│')

            # detect if line ended with slash → directory
            is_dir_line = orig.rstrip().endswith('/')

            # the names part after tree-art glyphs
            names_raw = txt[cut_idx:].lstrip('├└─ ').rstrip()
            # drop only one trailing slash if present (we already recorded it)
            if names_raw.endswith('/'):
                names_raw = names_raw[:-1]

            if not names_raw.strip():
                # nothing to create
                continue

            # support nested by slash in one line: e.g. services/auth/controllers
            name_list = [n.strip() for n in names_raw.split('/') if n.strip()]

            if level + 1 > len(stack):
                raise ParseError(f"Line {lineno}: Indentation too deep (level {level}).")

            # climb back up to correct parent
            while len(stack) > level + 1:
                stack.pop()
            parent = stack[-1]

            # create each segment in name_list
            for idx, name in enumerate(name_list):
                is_last = (idx == len(name_list) - 1)

                # decide class:
                if not is_last:
                    node_cls = DirectoryNode
                else:
                    # last segment: if trailing slash → dir
                    if is_dir_line:
                        node_cls = DirectoryNode
                    # if has an extension → file
                    elif Path(name).suffix:
                        node_cls = FileNode
                    # no slash & no extension: assume file (Dockerfile, Makefile, etc.)
                    else:
                        node_cls = FileNode

                node = node_cls(name=name, parent=parent)
                parent.add_child(node)

                # if it’s a directory, push onto stack for further nesting
                if isinstance(node, DirectoryNode):
                    parent = node
                    stack.append(node)

        return root

class FileSystemCreator:
    """Create folders & files from DirectoryNode recursively."""
    def __init__(self, dry_run: bool = False, confirm: bool = True):
        self.dry_run = dry_run
        self.confirm = confirm
        self.logger = logging.getLogger('ProjectCreator')

    def _create_dir(self, path: Path):
        if self.dry_run:
            self.logger.info(colorize(f"[DRY-RUN] mkdir {path}", Colors.OKBLUE))
        else:
            path.mkdir(parents=True, exist_ok=True)
            self.logger.info(colorize(f"[DIR] {path}", Colors.OKGREEN))

    def _create_file(self, path: Path):
        if self.dry_run:
            self.logger.info(colorize(f"[DRY-RUN] touch {path}", Colors.OKBLUE))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(exist_ok=True)
            self.logger.info(colorize(f"[FILE] {path}", Colors.OKGREEN))

    def execute(self, root: DirectoryNode):
        if self.confirm and not self.dry_run:
            try:
                ans = input(colorize("Proceed with creation? [y/N]: ", Colors.WARNING)).strip().lower()
            except (KeyboardInterrupt, EOFError):
                self.logger.warning(colorize("Operation cancelled by user.", Colors.FAIL))
                sys.exit(1)

            if ans != 'y':
                self.logger.warning(colorize("Operation aborted.", Colors.WARNING))
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

def read_multiline_input(prompt: str = "Enter project structure (end with blank line):") -> str:
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

def setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(message)s")

def main():
    parser = argparse.ArgumentParser(description="Create project structure from ASCII-tree input.")
    parser.add_argument("-d", "--dry-run", action="store_true", help="Simulate without creating files.")
    parser.add_argument("--no-confirm", action="store_true", help="Create without confirmation prompt.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show debug logs.")
    args = parser.parse_args()

    setup_logging(args.verbose)
    logger = logging.getLogger('ProjectCreator')

    try:
        tree_str = read_multiline_input()
        if not tree_str.strip():
            logger.error(colorize("No input detected. Exiting.", Colors.FAIL))
            sys.exit(1)

        parser_obj = ProjectTreeParser()
        root_node = parser_obj.parse(tree_str)

        creator = FileSystemCreator(dry_run=args.dry_run, confirm=not args.no_confirm)
        creator.execute(root_node)

        logger.info(colorize("✔ Project structure creation complete.", Colors.OKBLUE))
    except ParseError as e:
        logger.error(colorize(f"Parse Error: {e}", Colors.FAIL))
        sys.exit(1)
    except Exception as e:
        logger.exception(colorize(f"Unhandled Error: {e}", Colors.FAIL))
        sys.exit(1)

if __name__ == "__main__":
    main()
