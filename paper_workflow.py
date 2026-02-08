#!/usr/bin/env python3
"""
PhD-Agent Paper Workflow
Search → Download → Analyze papers automatically
"""

import os
import sys
import argparse
import re
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

try:
    import requests
except ImportError:
    print("❌ requests package required. Install with: pip install requests")
    sys.exit(1)

# 환경 설정
load_dotenv()
OBSIDIAN_PATH = os.getenv("OBSIDIAN_PATH")

if not OBSIDIAN_PATH:
    OBSIDIAN_PATH = None

# ========================================
# arXiv API
# ========================================

def search_arxiv(query, max_results=10):
    """arXiv에서 논문 검색"""
    print(f"🔍 Searching arXiv for: {query}")

    base_url = "http://export.arxiv.org/api/query?"
    params = {
        'search_query': f'all:{query}',
        'start': 0,
        'max_results': max_results,
        'sortBy': 'relevance',
        'sortOrder': 'descending'
    }

    url = base_url + urllib.parse.urlencode(params)

    try:
        response = urllib.request.urlopen(url)
        data = response.read().decode('utf-8')

        # 간단한 XML 파싱 (정규식 사용)
        papers = []
        entries = re.findall(r'<entry>(.*?)</entry>', data, re.DOTALL)

        for entry in entries:
            # 제목
            title_match = re.search(r'<title>(.*?)</title>', entry, re.DOTALL)
            title = title_match.group(1).strip().replace('\n', ' ') if title_match else "Unknown"

            # 저자
            authors = re.findall(r'<name>(.*?)</name>', entry)
            authors_str = ", ".join(authors[:3])
            if len(authors) > 3:
                authors_str += " et al."

            # arXiv ID
            id_match = re.search(r'<id>http://arxiv.org/abs/(.*?)</id>', entry)
            arxiv_id = id_match.group(1) if id_match else None

            # 발표일
            published_match = re.search(r'<published>(.*?)</published>', entry)
            published = published_match.group(1)[:10] if published_match else "Unknown"
            year = published[:4] if published != "Unknown" else "Unknown"

            # Abstract
            abstract_match = re.search(r'<summary>(.*?)</summary>', entry, re.DOTALL)
            abstract = abstract_match.group(1).strip().replace('\n', ' ') if abstract_match else ""

            if arxiv_id:
                papers.append({
                    'source': 'arXiv',
                    'title': title,
                    'authors': authors_str,
                    'year': year,
                    'arxiv_id': arxiv_id,
                    'pdf_url': f'https://arxiv.org/pdf/{arxiv_id}.pdf',
                    'abstract': abstract,
                    'doi': None
                })

        return papers
    except Exception as e:
        print(f"❌ arXiv search failed: {e}")
        return []

# ========================================
# Semantic Scholar API
# ========================================

def search_semantic_scholar(query, max_results=10):
    """Semantic Scholar에서 논문 검색"""
    print(f"🔍 Searching Semantic Scholar for: {query}")

    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        'query': query,
        'limit': max_results,
        'fields': 'title,authors,year,abstract,externalIds,openAccessPdf'
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        papers = []
        for paper in data.get('data', []):
            # 저자
            authors = paper.get('authors', [])
            authors_str = ", ".join([a['name'] for a in authors[:3]])
            if len(authors) > 3:
                authors_str += " et al."

            # DOI
            external_ids = paper.get('externalIds', {})
            doi = external_ids.get('DOI')
            arxiv_id = external_ids.get('ArXiv')

            # PDF URL
            pdf_url = None
            open_access = paper.get('openAccessPdf')
            if open_access:
                pdf_url = open_access.get('url')
            elif arxiv_id:
                pdf_url = f'https://arxiv.org/pdf/{arxiv_id}.pdf'

            papers.append({
                'source': 'Semantic Scholar',
                'title': paper.get('title', 'Unknown'),
                'authors': authors_str,
                'year': str(paper.get('year', 'Unknown')),
                'arxiv_id': arxiv_id,
                'doi': doi,
                'pdf_url': pdf_url,
                'abstract': paper.get('abstract', '')
            })

        return papers
    except Exception as e:
        print(f"❌ Semantic Scholar search failed: {e}")
        return []

# ========================================
# 메타데이터 & 파일 생성
# ========================================

def generate_citekey(authors, year):
    """저자와 연도로 citekey 생성 (e.g., KimEtAl2024)"""
    # 리스트와 문자열 둘 다 처리
    if isinstance(authors, list):
        # 리스트인 경우
        if len(authors) == 0:
            first_author = "Unknown"
        elif len(authors) == 1:
            first_author = authors[0].replace(' ', '')
            return f"{first_author}{year}"
        else:
            first_author = authors[0].replace(' ', '')
            return f"{first_author}EtAl{year}"
    else:
        # 문자열인 경우 (기존 로직)
        authors_str = authors
        # 첫 번째 저자 성 추출
        first_author = authors_str.split(',')[0].strip()
        # "et al." 제거
        first_author = first_author.replace(' et al.', '')
        # 공백 제거
        first_author = first_author.replace(' ', '')

        # 여러 저자면 EtAl 추가
        if 'et al' in authors_str or ',' in authors_str:
            citekey = f"{first_author}EtAl{year}"
        else:
            citekey = f"{first_author}{year}"

    return citekey

def download_pdf(pdf_url, save_path):
    """PDF 다운로드"""
    try:
        print(f"  📥 Downloading PDF...")
        response = requests.get(pdf_url, timeout=30, stream=True)
        response.raise_for_status()

        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return True
    except Exception as e:
        print(f"  ❌ PDF download failed: {e}")
        return False

def create_paper_note(paper, paper_dir):
    """Papers_Zotero_v3 템플릿으로 논문 노트 생성"""

    citekey = generate_citekey(paper['authors'], paper['year'])
    today = datetime.now().strftime("%Y-%m-%d")

    # DOI URL
    doi_url = f"https://doi.org/{paper['doi']}" if paper['doi'] else ""

    # arXiv URL
    arxiv_url = f"https://arxiv.org/abs/{paper['arxiv_id']}" if paper['arxiv_id'] else ""

    # 템플릿 생성
    content = f"""---
type: paper
source: {paper['source']}
citekey: {citekey}
title: "{paper['title']}"
authors: {paper['authors']}
year: {paper['year']}
journal: {paper['source']}
doi: {paper['doi'] or ''}
arxiv_id: {paper['arxiv_id'] or ''}
url: {arxiv_url or doi_url}
created: {today}
template: Papers_Zotero_v3
tags:
  - paper
---

# {paper['title']}

---

## 🧠 My Synthesis (DO NOT AUTO-OVERWRITE)
> ⚠️ **Manually written section**
> This section must NOT be modified by re-sync.

- Key contributions:
- What I care about:
- Open questions / limitations:
- Ideas for my own research:

---

## 📄 Abstract
{paper['abstract']}

---

## 📚 Resources
- **PDF:** [[{citekey}.pdf]]
- **arXiv:** {arxiv_url}
- **DOI:** {doi_url}

---

## 🤖 AI Analysis
- Divergence notes: (여기에 비교 결과 수동 기입)

---

[[Literature Review]], [[2D Materials]], [[Valleytronics]]
"""

    # 파일 저장
    note_path = os.path.join(paper_dir, f"{citekey}.md")
    with open(note_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return citekey, note_path

# ========================================
# 메인 워크플로우
# ========================================

def main():
    parser = argparse.ArgumentParser(
        description="Search, download, and analyze papers automatically"
    )
    parser.add_argument('--search', type=str, required=True, help='Search query')
    parser.add_argument('--max-results', type=int, default=10, help='Maximum results to show')
    parser.add_argument('--source', choices=['arxiv', 'semantic', 'both'], default='both',
                        help='Search source (default: both)')
    parser.add_argument('--auto-analyze', action='store_true',
                        help='Automatically run analysis after download')

    args = parser.parse_args()

    # 1. 논문 검색
    papers = []

    if args.source in ['arxiv', 'both']:
        papers.extend(search_arxiv(args.search, args.max_results))

    if args.source in ['semantic', 'both']:
        papers.extend(search_semantic_scholar(args.search, args.max_results))

    if not papers:
        print("❌ No papers found")
        return

    # 중복 제거 (제목 기준)
    seen_titles = set()
    unique_papers = []
    for paper in papers:
        if paper['title'] not in seen_titles:
            seen_titles.add(paper['title'])
            unique_papers.append(paper)

    papers = unique_papers[:args.max_results]

    # 2. 결과 표시
    print(f"\n{'='*60}")
    print(f"Found {len(papers)} papers:")
    print('='*60)

    for i, paper in enumerate(papers, 1):
        pdf_status = "✅ PDF" if paper['pdf_url'] else "❌ No PDF"
        print(f"\n{i}. [{paper['year']}] {paper['title'][:80]}")
        print(f"   Authors: {paper['authors']}")
        print(f"   Source: {paper['source']} | {pdf_status}")
        if paper['arxiv_id']:
            print(f"   arXiv: {paper['arxiv_id']}")
        if paper['doi']:
            print(f"   DOI: {paper['doi']}")

    # 3. 사용자 선택
    print(f"\n{'='*60}")
    selection = input("Select papers [1-10, comma-separated, or 'all']: ").strip()

    if selection.lower() == 'all':
        selected_papers = papers
    else:
        try:
            indices = [int(x.strip()) - 1 for x in selection.split(',')]
            selected_papers = [papers[i] for i in indices if 0 <= i < len(papers)]
        except:
            print("❌ Invalid selection")
            return

    if not selected_papers:
        print("❌ No papers selected")
        return

    # 4. 다운로드 & 저장
    print(f"\n📥 Processing {len(selected_papers)} paper(s)...")

    papers_base = os.path.join(OBSIDIAN_PATH, "30_Resources", "Papers", "zotero")
    os.makedirs(papers_base, exist_ok=True)

    created_notes = []

    for paper in selected_papers:
        print(f"\n📄 {paper['title'][:60]}...")

        citekey = generate_citekey(paper['authors'], paper['year'])
        paper_dir = os.path.join(papers_base, citekey)
        os.makedirs(paper_dir, exist_ok=True)

        # PDF 다운로드
        if paper['pdf_url']:
            pdf_path = os.path.join(paper_dir, f"{citekey}.pdf")
            if download_pdf(paper['pdf_url'], pdf_path):
                print(f"  ✅ PDF saved")
            else:
                print(f"  ⚠️  PDF download failed, continuing...")
        else:
            print(f"  ⚠️  No PDF available")

        # 노트 생성
        citekey, note_path = create_paper_note(paper, paper_dir)
        created_notes.append((citekey, note_path))
        print(f"  ✅ Note created: {citekey}.md")

    # 5. 분석 옵션
    print(f"\n🎉 Complete! Created {len(created_notes)} paper note(s)")

    if args.auto_analyze or input("\n🤖 Run AI analysis now? [Y/n]: ").strip().lower() in ['y', 'yes', '']:
        print("\n🤖 Running analysis...")
        for citekey, note_path in created_notes:
            print(f"\n  Analyzing {citekey}...")
            # analyze_paper_v2.py 호출
            os.system(f'python analyze_paper_v2.py "{citekey}.md" --auto-approve')

    print("\n✅ All done!")

if __name__ == "__main__":
    main()
