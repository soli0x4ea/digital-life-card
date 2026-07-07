#!/usr/bin/env python3
"""epub → markdown 批量转换。纯标准库，零外部依赖。"""
import zipfile, re, os, sys, json
from html.parser import HTMLParser
from pathlib import Path

class CleanParser(HTMLParser):
    """洗掉 HTML 标签，保留文本和段落边界"""
    def __init__(self):
        super().__init__()
        self.lines = []
        self._current_line = []
        self._skip = False
        self._block_tags = {'p','div','h1','h2','h3','h4','h5','h6','li','br','tr'}
        self._heading_tags = {'h1','h2','h3','h4','h5','h6'}

    def handle_starttag(self, tag, attrs):
        if tag in ('script','style'): self._skip = True
        if tag in self._block_tags and self._current_line:
            self.lines.append(''.join(self._current_line).strip())
            self._current_line = []

    def handle_endtag(self, tag):
        if tag in ('script','style'): self._skip = False
        if tag in self._block_tags and self._current_line:
            self.lines.append(''.join(self._current_line).strip())
            self._current_line = []
        if tag in self._heading_tags:
            self._current_line = ['## '] if 'h1' not in tag else ['# ']

    def handle_data(self, data):
        if not self._skip:
            text = data.strip()
            if text:
                self._current_line.append(text)

    def get_text(self):
        if self._current_line:
            self.lines.append(''.join(self._current_line).strip())
        # 合并连续空行
        result = []
        prev_empty = False
        for line in self.lines:
            if not line:
                if not prev_empty:
                    result.append('')
                prev_empty = True
            else:
                result.append(line)
                prev_empty = False
        return '\n\n'.join(result)


def extract_title_from_html(html_content):
    """从 HTML 中提取标题，优先级：<title> > <h1> > <h2>"""
    # 1. 尝试 <title> 标签（epub 通常用这个存章节标题）
    m = re.search(r'<title[^>]*>([^<]+)</title>', html_content, re.IGNORECASE)
    if m:
        title = m.group(1).strip()
        # 清理前缀 "Tempo: " / "Genesi: " 等
        title = re.sub(r'^[^:]+:\s*', '', title)
        if title and title != Path(html_content).stem:  # 避免纯文件名标题
            return title
    # 2. 尝试 <h1>
    m = re.search(r'<h1[^>]*>([^<]+)</h1>', html_content, re.IGNORECASE)
    if m: return m.group(1).strip()
    # 3. 尝试 <h2>
    m = re.search(r'<h2[^>]*>([^<]+)</h2>', html_content, re.IGNORECASE)
    if m: return m.group(1).strip()
    return None


# Genesi 的章节号 → 标题映射（epub 无标准 HTML 标题标签，手动补）
GENESI_TITLES = {
    4: "Introduzione — Il grande racconto delle origini",
    5: "In principio era il vuoto (Day 0)",
    6: "Giorno 1 — Un soffio inarrestabile produce la prima meraviglia",
    7: "Giorno 2 — Tutto si riempie di rugiada (Il bosone di Higgs)",
    8: "Giorno 3 — Noi siamo gli immortali (Quark e nucleosintesi)",
    9: "Giorno 4 — Fatevi sotto, sciocchi (CMB e materia oscura)",
    10: "Giorno 5 — Tu, piccola, inutile massa (La prima stella)",
    11: "Giorno 6 — Trattenete il respiro (Dalla vita ai primati)",
    12: "Giorno 7 — La meraviglia di essere unici (Agricoltura, scrittura, città)",
    13: "Capitolo umano — L'animale che volle farsi immortale",
    14: "Epilogo — Il tempo del sogno",
}


def extract_ch_num(filename):
    """从文件名提取章节号"""
    m = re.search(r'chapter(\d+)', filename, re.IGNORECASE)
    if m: return int(m.group(1))
    m = re.search(r'part0*(\d+)', filename, re.IGNORECASE)
    if m: return int(m.group(1))
    m = re.search(r'Genesi-(\d+)', filename, re.IGNORECASE)
    if m: return int(m.group(1))
    return None


def extract_first_sentence(text, max_len=60):
    """从清洗后的文本中提取第一句作为标题"""
    for line in text.split('\n'):
        line = line.strip()
        if not line: continue
        # 截取第一句（到第一个句号/问号/感叹号）
        m = re.match(r'^(.+?[.!?])', line)
        if m:
            title = m.group(1).strip()
            if len(title) > 10:
                return title[:max_len]
        # 否则取前 max_len 字符
        if len(line) > 10:
            return line[:max_len]
    return None


def convert_epub(epub_path, out_dir):
    """将 epub 按章节拆分为独立 md 文件"""
    book_name = Path(epub_path).stem.replace(' ', '_')
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []

    with zipfile.ZipFile(epub_path) as z:
        all_html = sorted([
            f for f in z.namelist()
            if f.endswith(('.html','.xhtml','.htm'))
        ])

        # 匹配章节文件：优先 chapterNN，其次 Genesi-N，回退到 partNN
        chapter_files = [f for f in all_html if re.search(r'chapter\d+', f, re.IGNORECASE)]
        if not chapter_files:
            chapter_files = [f for f in all_html if re.search(r'Genesi-(\d+)\.', f)]
        if not chapter_files:
            chapter_files = [f for f in all_html if re.search(r'part\d+', f, re.IGNORECASE)]
        if not chapter_files:
            chapter_files = [f for f in all_html if not any(skip in f.lower() 
                for skip in ('cover','toc','nav','copyright','colophon','dedication','halftitle','backmatter','Section0001'))]

        for f in chapter_files:
            content = z.read(f).decode('utf-8', errors='ignore')
            
            if len(content) < 500:
                continue

            title = extract_title_from_html(content)
            ch_num = extract_ch_num(f)
            if not ch_num:
                ch_num = len(results) + 1

            # Genesi 用硬编码标题（epub 无标准 HTML 标题）
            if 'Genesi' in book_name and ch_num in GENESI_TITLES:
                title = GENESI_TITLES[ch_num]
            
            # 跳过极短的前言/后记类文件
            if len(content) < 1500 and not title:
                continue

            parser = CleanParser()
            parser.feed(content)
            text = parser.get_text()

            # 如果 HTML 标题提取失败，用第一句
            if not title:
                title = extract_first_sentence(text) or f'第{ch_num}章'

            # 生成文件名
            slug = re.sub(r'[\\/:*?"<>|\.]', '', title)[:60].strip()
            fname = f"{ch_num:02d}_{slug}.md"

            out_path = out_dir / fname

            md_content = f"""# {title}

> 书籍：{book_name}
> 源文件：{f}
> 章节：第{ch_num}章

---

{text}
"""
            out_path.write_text(md_content, encoding='utf-8')
            results.append({
                'ch': ch_num,
                'file': fname,
                'title': title,
                'chars': len(text),
            })
            print(f"  [{ch_num:02d}] {fname:50s} {len(text):>6,} 字符")

    # 写索引
    idx_path = out_dir / '_index.json'
    idx_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f"\n  ✅ {book_name}: {len(results)} 个章节 → {out_dir}")
    return results


def convert_pdf(pdf_path, out_dir):
    """PDF 转 markdown。尝试提取文本内容。"""
    path = Path(pdf_path)
    book_name = path.stem.replace(' ', '_')
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 尝试用 PyPDF2 / pdfplumber 如果可用
    try:
        from pdfminer.high_level import extract_text
        text = extract_text(str(pdf_path))
    except ImportError:
        try:
            import PyPDF2
            with open(pdf_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                pages = [reader.pages[i].extract_text() or '' for i in range(len(reader.pages))]
            text = '\n\n---\n\n'.join(pages)
        except ImportError:
            # 纯标准库：PDF 无法可靠解析，返回错误
            print(f"  ⚠️ {book_name}: PDF 需要 pdfminer.six 或 PyPDF2，跳过")
            return []

    # PDF 文本通常不分章节，按页分割
    out_path = out_dir / f"{book_name}.md"
    md = f"""# {book_name}

> 源文件：{pdf_path}
> 转换日期：自动

---

{text}
"""
    out_path.write_text(md, encoding='utf-8')
    chars = len(text)
    print(f"  📄 {book_name}.md  {chars:>6,} 字符")
    return [{'file': f'{book_name}.md', 'title': book_name, 'chars': chars}]


def main():
    script_dir = Path(__file__).resolve().parent
    skill_refs = script_dir.parent / 'references' / 'books'
    raw_dir = skill_refs / 'raw'
    out_base = skill_refs / 'txt'

    books = [
        ('epub', raw_dir / 'tonelli' / 'Tonelli_Tempo_IT.epub',  out_base / 'tempo'),
        ('epub', raw_dir / 'tonelli' / 'Genesi_Tonelli_IT.epub', out_base / 'genesi'),
        ('pdf',  raw_dir / 'lederman' / '莱德曼量子物理通识讲义.pdf', out_base / 'lederman'),
    ]

    all_results = {}
    for fmt, src, out in books:
        if not Path(src).exists():
            print(f"⚠️ 源文件不存在：{src}")
            continue
        print(f"\n📖 {Path(src).name}")
        try:
            if fmt == 'epub':
                results = convert_epub(str(src), str(out))
            else:
                results = convert_pdf(str(src), str(out))
            if results:
                all_results[Path(src).stem] = results
        except Exception as e:
            print(f"  ❌ 转换失败：{e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*50}")
    print(f"✅ 完成：{len(all_results)} 本书，{sum(len(v) for v in all_results.values())} 个文件")
    print(f"   输出目录：{out_base}")


if __name__ == '__main__':
    main()
