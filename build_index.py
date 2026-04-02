#!/usr/bin/env python3
"""법령 데이터를 Vercel 배포용 JSON으로 사전 빌드"""
import os, re, json, yaml
from pathlib import Path

LAW_DIR = Path(__file__).parent / "legalize-kr" / "kr"
OUT_DIR = Path(__file__).parent / "data"

def parse_frontmatter(content):
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                meta = yaml.safe_load(parts[1]) or {}
            except yaml.YAMLError:
                meta = {}
            return meta, parts[2].strip()
    return {}, content

def extract_articles(body):
    articles = []
    lines = body.split("\n")
    cur = None
    buf = []
    for line in lines:
        m = re.match(r"^#{1,6}\s*(제\d+조(?:의\d+)?)\s*(?:\((.+?)\))?\s*$", line)
        if m:
            if cur:
                articles.append({"number": cur["number"], "title": cur["title"], "content": "\n".join(buf).strip()})
            cur = {"number": m.group(1), "title": m.group(2) or ""}
            buf = []
        elif cur:
            buf.append(line)
    if cur:
        articles.append({"number": cur["number"], "title": cur["title"], "content": "\n".join(buf).strip()})
    return articles

def build():
    OUT_DIR.mkdir(exist_ok=True)
    index = {}
    if not LAW_DIR.exists():
        print("legalize-kr not found")
        return
    count = 0
    for law_dir in sorted(LAW_DIR.iterdir()):
        if not law_dir.is_dir():
            continue
        law_name = law_dir.name
        files = {}
        for md_file in sorted(law_dir.glob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            meta, body = parse_frontmatter(content)
            file_type = md_file.stem
            articles = extract_articles(body)
            files[file_type] = {
                "meta": {
                    "제목": meta.get("제목", ""),
                    "소관부처": meta.get("소관부처", []),
                    "공포일자": str(meta.get("공포일자", "")),
                    "시행일자": str(meta.get("시행일자", "")),
                    "상태": meta.get("상태", ""),
                    "출처": meta.get("출처", ""),
                },
                "articles": articles,
            }
        index[law_name] = {"name": law_name, "files": files}
        count += 1

    # 전체 인덱스 저장
    out_path = OUT_DIR / "laws_index.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False)

    size_mb = out_path.stat().st_size / 1024 / 1024
    print(f"빌드 완료: {count}개 법령, {size_mb:.1f}MB -> {out_path}")

if __name__ == "__main__":
    build()
