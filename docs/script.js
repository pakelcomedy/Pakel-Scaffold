// script.js
// Versi JavaScript untuk mem-parse ASCII-tree, generate ZIP, dan menghapus komentar serta emoji otomatis

// Utility: hapus emoji dari string
function removeEmojis(str) {
  // Menggunakan Unicode property escapes untuk emoji
  return str.replace(/\p{Emoji_Presentation}/gu, '').replace(/\p{Emoji}/gu, '');
}

class TreeNode {
  constructor(name, isDir = false) {
    this.name = name;
    this.isDir = isDir;
    this.children = [];
  }

  addChild(child) {
    if (!this.children.find(c => c.name === child.name && c.isDir === child.isDir)) {
      this.children.push(child);
    }
  }
}

class ProjectTreeParser {
  /**
   * indentWidth: jumlah spasi dianggap satu level
   */
  constructor(indentWidth = 4) {
    this.indentWidth = indentWidth;
    this.pureArt = /^[\s│├└─]+$/;
  }

  parse(raw) {
    // Hapus komentar (// dan #) dan emoji
    raw = raw
      .split('\n')
      .map(line => {
        // hapus JS comments
        let txt = line.replace(/\/\/.*$/, '');
        // hapus inline # comments
        txt = txt.split('#')[0];
        // hapus emoji
        txt = removeEmojis(txt);
        return txt.replace(/\r?$/, '');
      })
      .join('\n');

    const lines = raw.split('\n')
      .map((l, i) => ({ lineno: i+1, txt: l.trimEnd() }))
      .filter(l => l.txt.trim());

    if (!lines.length) throw new Error('Input kosong atau komentar saja');

    const filtered = lines.filter(l => !this.pureArt.test(l.txt));
    if (!filtered.length) throw new Error('Tidak ada entri valid');

    // Root
    const rootName = filtered[0].txt.replace(/\/$/, '').trim();
    const root = new TreeNode(rootName, true);
    const stack = [root];

    filtered.slice(1).forEach(({ lineno, txt }) => {
      // hitung indent
      let cutIdx = Infinity;
      ['├','└'].forEach(ch => {
        const idx = txt.indexOf(ch);
        if (idx >= 0 && idx < cutIdx) cutIdx = idx;
      });
      if (cutIdx === Infinity) {
        const spaces = txt.match(/^ */)[0].length;
        cutIdx = spaces;
      }
      const level = Math.floor(cutIdx / this.indentWidth);

      // nama dan tipe
      let nameRaw = txt.replace(/^[\s│├└─]+/, '').trim();
      const isDir = /\/$/.test(nameRaw);
      nameRaw = nameRaw.replace(/\/$/, '');
      if (!nameRaw) return;

      // hapus emoji dari nama node
      nameRaw = removeEmojis(nameRaw);

      const parts = nameRaw.split('/').map(p => p.trim()).filter(Boolean);
      // adjust stack
      while (stack.length > level + 1) stack.pop();
      let parent = stack[stack.length - 1];

      parts.forEach((part, idx) => {
        const last = idx === parts.length - 1;
        const node = new TreeNode(part, last ? isDir : true);
        parent.addChild(node);
        if (node.isDir) {
          parent = node;
          stack.push(node);
        }
      });
    });

    return root;
  }
}

class FileSystemCreator {
  constructor(rootNode) {
    this.root = rootNode;
    this.zip = new JSZip();
  }

  _recurse(node, folder) {
    if (node.isDir) {
      const sub = folder.folder(node.name);
      node.children.forEach(child => this._recurse(child, sub));
    } else {
      folder.file(node.name, '');
    }
  }

  generateZip() {
    // mulai dari root
    const rootFolder = this.zip.folder(this.root.name);
    this.root.children.forEach(child => this._recurse(child, rootFolder));
    return this.zip.generateAsync({ type: 'blob' });
  }
}

// --- DOM & Event Handling ---
const textarea = document.getElementById('ascii-input');
const parseBtn = document.getElementById('parse-btn');
const downloadBtn = document.getElementById('download-zip-btn');
const treeRoot = document.getElementById('tree-root');

let currentRoot = null;

function renderTree(node, ul) {
  ul.innerHTML = '';
  function walk(n, parentUl) {
    const li = document.createElement('li');
    li.textContent = n.name + (n.isDir ? '/' : '');
    parentUl.appendChild(li);
    if (n.isDir && n.children.length) {
      const subUl = document.createElement('ul');
      subUl.classList.add('tree');
      li.appendChild(subUl);
      n.children.forEach(c => walk(c, subUl));
    }
  }
  walk(node, ul);
}

parseBtn.addEventListener('click', () => {
  try {
    const parser = new ProjectTreeParser(4);
    currentRoot = parser.parse(textarea.value);
    renderTree(currentRoot, treeRoot);
    downloadBtn.disabled = false;
  } catch (e) {
    alert('Error parsing: ' + e.message);
    treeRoot.innerHTML = '';
    downloadBtn.disabled = true;
  }
});

downloadBtn.addEventListener('click', () => {
  if (!currentRoot) return;
  const creator = new FileSystemCreator(currentRoot);
  creator.generateZip().then(blob => {
    saveAs(blob, `${currentRoot.name}.zip`);
  });
});
