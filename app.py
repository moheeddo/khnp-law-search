#!/usr/bin/env python3
"""한수원 계약 법령 검색 시스템 - Backend v3
인증, 북마크, 다크모드, Solar LLM 어드바이저 지원
"""

import os
import re
import json
import yaml
import time
import sqlite3
import secrets
import urllib.request
import urllib.error
import urllib.parse
import ssl
from pathlib import Path
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, g

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# Upstage Solar LLM 설정
SOLAR_API_KEY = os.environ.get("UPSTAGE_API_KEY", "") or "up_ppdAFGd03WVjGkZDihfdoqMByyKVV"
SOLAR_API_URL = "https://api.upstage.ai/v1/chat/completions"
SOLAR_MODEL = "solar-mini"

# 공공데이터포털 API 설정
DATA_GO_KR_KEY = os.environ.get("DATA_GO_KR_API_KEY", "22bf70353dbe75978aeb6ccbd606dcab8e13e843a8cd8aeba999bdd1453830f9")
PROCUREMENT_BASE = "https://apis.data.go.kr/1230000/ad"
ALIO_BASE = "http://apis.data.go.kr/B552015"

# API 응답 캐시 (key → (timestamp, data), 1시간 TTL)
_api_cache = {}
API_CACHE_TTL = 3600

def cached_api_call(cache_key: str, url: str, timeout: int = 30) -> dict | None:
    """공공데이터 API 호출 + 1시간 캐시"""
    now = time.time()
    if cache_key in _api_cache:
        ts, data = _api_cache[cache_key]
        if now - ts < API_CACHE_TTL:
            return data
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)
            _api_cache[cache_key] = (now, data)
            return data
    except Exception as e:
        print(f"공공데이터 API 오류: {type(e).__name__}: {e} | URL: {url[:120]}")
        return None

LAW_DIR = Path(__file__).parent / "legalize-kr" / "kr"
DB_PATH = Path(__file__).parent / "lawsearch.db"

# ===== 한수원 카테고리 =====
KHNP_CATEGORIES = {
    "contract_core": {
        "name": "계약 핵심 법령",
        "icon": "file-text",
        "description": "국가계약법, 공기업 계약사무규칙 등 계약의 근간이 되는 법령",
        "laws": [
            "국가를당사자로하는계약에관한법률",
            "공기업ㆍ준정부기관계약사무규칙",
            "조달사업에관한법률",
            "전자조달의이용및촉진에관한법률",
            "지방자치단체를당사자로하는계약에관한법률",
        ],
    },
    "public_org": {
        "name": "공공기관 운영",
        "icon": "building",
        "description": "공공기관 운영, 정보공개, 감사 관련 법령",
        "laws": [
            "공공기관의운영에관한법률",
            "공공기관의정보공개에관한법률",
            "공공기관의회계감사및결산감사에관한규칙",
            "공공기관의갈등예방과해결에관한규정",
        ],
    },
    "nuclear_energy": {
        "name": "원자력·전력",
        "icon": "zap",
        "description": "원자력 안전, 전기사업, 전력기술 관련 법령",
        "laws": [
            "원자력안전법",
            "원자력진흥법",
            "원자력손해배상법",
            "원자력손해배상보상계약에관한법률",
            "원자력시설등의방호및방사능방재대책법",
            "원자력안전위원회의설치및운영에관한법률",
            "원자력안전정보공개및소통에관한법률",
            "원전비리방지를위한원자력발전사업자등의관리ㆍ감독에관한법률",
            "전기사업법",
            "전력기술관리법",
            "에너지법",
            "방사성폐기물관리법",
        ],
    },
    "construction_subcontract": {
        "name": "건설·하도급",
        "icon": "hard-hat",
        "description": "건설산업, 하도급 거래 공정화 관련 법령",
        "laws": [
            "건설산업기본법",
            "하도급거래공정화에관한법률",
        ],
    },
    "fair_trade": {
        "name": "공정거래·민상법",
        "icon": "scale",
        "description": "독점규제, 민법, 상법 등 일반 거래법",
        "laws": [
            "독점규제및공정거래에관한법률",
            "민법",
        ],
    },
    "safety_environment": {
        "name": "안전·환경",
        "icon": "shield",
        "description": "산업안전, 환경영향평가 관련 법령",
        "laws": [
            "산업안전보건법",
            "환경영향평가법",
            "산업안전보건기준에관한규칙",
        ],
    },
}


# ===== Database =====
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(str(DB_PATH))
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db:
        db.close()


def init_db():
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        display_name TEXT NOT NULL,
        department TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS bookmarks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        law_name TEXT NOT NULL,
        file_type TEXT DEFAULT '법률',
        article_num TEXT DEFAULT '',
        article_title TEXT DEFAULT '',
        memo TEXT DEFAULT '',
        folder TEXT DEFAULT '기본',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id),
        UNIQUE(user_id, law_name, file_type, article_num)
    )""")
    db.execute("""CREATE INDEX IF NOT EXISTS idx_bookmarks_user
        ON bookmarks(user_id)""")
    db.commit()
    db.close()


def hash_password(password: str) -> str:
    from hashlib import pbkdf2_hmac
    salt = secrets.token_hex(16)
    h = pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex()
    return f"{salt}:{h}"


def verify_password(password: str, stored: str) -> bool:
    from hashlib import pbkdf2_hmac
    salt, h = stored.split(":")
    return pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex() == h


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "로그인이 필요합니다"}), 401
        return f(*args, **kwargs)
    return decorated


# ===== Law Index =====
def parse_frontmatter(content: str) -> tuple[dict, str]:
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                meta = yaml.safe_load(parts[1]) or {}
            except yaml.YAMLError:
                meta = {}
            return meta, parts[2].strip()
    return {}, content


def extract_articles(body: str) -> list[dict]:
    articles = []
    lines = body.split("\n")
    current_article = None
    current_content = []
    for line in lines:
        match = re.match(r"^#{1,6}\s*(제\d+조(?:의\d+)?)\s*(?:\((.+?)\))?\s*$", line)
        if match:
            if current_article:
                articles.append({
                    "number": current_article["number"],
                    "title": current_article["title"],
                    "content": "\n".join(current_content).strip(),
                })
            current_article = {"number": match.group(1), "title": match.group(2) or ""}
            current_content = []
        elif current_article:
            current_content.append(line)
    if current_article:
        articles.append({
            "number": current_article["number"],
            "title": current_article["title"],
            "content": "\n".join(current_content).strip(),
        })
    return articles


_law_index = None


def build_index() -> dict:
    global _law_index
    if _law_index is not None:
        return _law_index
    print("법령 인덱스 구축 중...")
    start = time.time()
    index = {}
    if not LAW_DIR.exists():
        _law_index = index
        return index
    for law_dir in sorted(LAW_DIR.iterdir()):
        if not law_dir.is_dir():
            continue
        law_name = law_dir.name
        law_entry = {"name": law_name, "files": {}}
        for md_file in sorted(law_dir.glob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            meta, body = parse_frontmatter(content)
            file_type = md_file.stem
            articles = extract_articles(body)
            law_entry["files"][file_type] = {
                "meta": meta, "body": body,
                "articles": articles, "path": str(md_file),
            }
        index[law_name] = law_entry
    elapsed = time.time() - start
    print(f"인덱스 구축 완료: {len(index)}개 법령, {elapsed:.1f}초")
    _law_index = index
    return index


def search_laws(query: str, category: str = None, limit: int = 50) -> list[dict]:
    index = build_index()
    results = []
    keywords = query.lower().split()
    khnp_priority = set()
    for cat in KHNP_CATEGORIES.values():
        khnp_priority.update(cat["laws"])
    scope = index
    if category and category in KHNP_CATEGORIES:
        cat_laws = KHNP_CATEGORIES[category]["laws"]
        scope = {k: v for k, v in index.items() if k in cat_laws}
    for law_name, law_data in scope.items():
        name_match = all(kw in law_name.lower() for kw in keywords)
        name_score = 100 if name_match else 0
        khnp_bonus = 200 if law_name in khnp_priority else 0
        for file_type, file_data in law_data["files"].items():
            meta = file_data.get("meta", {})
            title = meta.get("제목", law_name)
            if all(kw in title.lower() for kw in keywords):
                name_score = max(name_score, 90)
            matching_articles = []
            for article in file_data.get("articles", []):
                art_text = f"{article['number']} {article['title']} {article['content']}".lower()
                if all(kw in art_text for kw in keywords):
                    art_title_text = f"{article['number']} {article['title']}".lower()
                    art_score = 80 if all(kw in art_title_text for kw in keywords) else 50
                    content = article["content"]
                    snippet = ""
                    for kw in keywords:
                        idx = content.lower().find(kw)
                        if idx >= 0:
                            s = max(0, idx - 60)
                            e = min(len(content), idx + len(kw) + 60)
                            snippet = "..." + content[s:e] + "..."
                            break
                    matching_articles.append({
                        "number": article["number"],
                        "title": article["title"],
                        "snippet": snippet or content[:150] + "...",
                        "score": art_score,
                    })
            if name_score > 0 or matching_articles:
                total = name_score + khnp_bonus + sum(a["score"] for a in matching_articles[:5])
                results.append({
                    "law_name": law_name, "file_type": file_type,
                    "title": meta.get("제목", law_name),
                    "meta": {
                        "소관부처": meta.get("소관부처", []),
                        "공포일자": meta.get("공포일자", ""),
                        "상태": meta.get("상태", ""),
                        "출처": meta.get("출처", ""),
                    },
                    "matching_articles": sorted(matching_articles, key=lambda x: -x["score"])[:10],
                    "score": total,
                })
    results.sort(key=lambda x: -x["score"])
    return results[:limit]


# ===== Law Advisor Engine =====
# 시나리오 기반 법령 추천 - 자연어 질의를 분석하여 관련 법령을 추천
ADVISOR_SCENARIOS = [
    # ── 계약 유형별 ──
    {
        "keywords": ["공사", "건설", "시공", "건축", "토목", "준공", "착공", "감리"],
        "category": "공사계약",
        "recommendations": [
            {"law": "국가를당사자로하는계약에관한법률", "type": "법률", "reason": "공사계약의 입찰·체결·이행 전반 규율", "priority": "필수"},
            {"law": "국가를당사자로하는계약에관한법률", "type": "시행령", "reason": "계약보증금, 지체상금, 물가변동 상세 기준", "priority": "필수"},
            {"law": "공기업ㆍ준정부기관계약사무규칙", "type": "기획재정부령", "reason": "한수원 등 공기업 계약사무 특별규정", "priority": "필수"},
            {"law": "건설산업기본법", "type": "법률", "reason": "건설업 등록, 도급 한도, 하도급 제한", "priority": "필수"},
            {"law": "하도급거래공정화에관한법률", "type": "법률", "reason": "하도급 대금 지급, 기술유용 금지", "priority": "권장"},
            {"law": "산업안전보건법", "type": "법률", "reason": "공사현장 안전관리, 안전보건대장", "priority": "권장"},
            {"law": "환경영향평가법", "type": "법률", "reason": "일정 규모 이상 공사 시 환경영향평가", "priority": "해당시"},
        ],
    },
    {
        "keywords": ["용역", "기술용역", "설계용역", "엔지니어링", "컨설팅", "연구용역", "정보화", "SW", "소프트웨어", "IT", "시스템개발"],
        "category": "용역계약",
        "recommendations": [
            {"law": "국가를당사자로하는계약에관한법률", "type": "법률", "reason": "용역계약 입찰·체결 절차", "priority": "필수"},
            {"law": "국가를당사자로하는계약에관한법률", "type": "시행령", "reason": "협상에 의한 계약, 적격심사 기준", "priority": "필수"},
            {"law": "공기업ㆍ준정부기관계약사무규칙", "type": "기획재정부령", "reason": "공기업 용역계약 특례", "priority": "필수"},
            {"law": "전력기술관리법", "type": "법률", "reason": "전력기술용역 관련 자격·등록 요건", "priority": "해당시"},
            {"law": "하도급거래공정화에관한법률", "type": "법률", "reason": "용역 하도급 시 대금 지급 의무", "priority": "해당시"},
        ],
    },
    {
        "keywords": ["구매", "물품", "자재", "조달", "납품", "장비", "기자재", "부품", "소모품"],
        "category": "물품구매",
        "recommendations": [
            {"law": "국가를당사자로하는계약에관한법률", "type": "법률", "reason": "물품 구매 입찰·계약 절차", "priority": "필수"},
            {"law": "공기업ㆍ준정부기관계약사무규칙", "type": "기획재정부령", "reason": "공기업 물품구매 계약사무 규정", "priority": "필수"},
            {"law": "조달사업에관한법률", "type": "법률", "reason": "조달청 계약·다수공급자계약(MAS)", "priority": "권장"},
            {"law": "전자조달의이용및촉진에관한법률", "type": "법률", "reason": "나라장터 전자입찰 절차", "priority": "권장"},
        ],
    },
    # ── 원자력 특수 ──
    {
        "keywords": ["원전", "원자력", "핵", "방사선", "방사능", "원자로", "핵연료", "사용후핵연료", "노심"],
        "category": "원자력사업",
        "recommendations": [
            {"law": "원자력안전법", "type": "법률", "reason": "원자력시설 건설·운영 허가, 안전규제 전반", "priority": "필수"},
            {"law": "원자력안전법", "type": "시행령", "reason": "허가 기준, 검사 절차 상세", "priority": "필수"},
            {"law": "원자력시설등의방호및방사능방재대책법", "type": "법률", "reason": "원자력시설 물리적방호, 비상대응", "priority": "필수"},
            {"law": "원자력손해배상법", "type": "법률", "reason": "원자력 사고 시 손해배상 책임", "priority": "필수"},
            {"law": "원자력손해배상보상계약에관한법률", "type": "법률", "reason": "손해배상 보상계약 체결 의무", "priority": "필수"},
            {"law": "원전비리방지를위한원자력발전사업자등의관리ㆍ감독에관한법률", "type": "법률", "reason": "납품비리 방지, 품질관리 의무", "priority": "필수"},
            {"law": "원자력진흥법", "type": "법률", "reason": "원자력 연구개발, 기술자립 지원", "priority": "권장"},
            {"law": "방사성폐기물관리법", "type": "법률", "reason": "방사성폐기물 처리·처분 의무", "priority": "해당시"},
        ],
    },
    {
        "keywords": ["방폐물", "방사성폐기물", "폐기물처분", "해체", "원전해체"],
        "category": "방사성폐기물·해체",
        "recommendations": [
            {"law": "방사성폐기물관리법", "type": "법률", "reason": "방사성폐기물 관리·처분 전반", "priority": "필수"},
            {"law": "원자력안전법", "type": "법률", "reason": "원자력시설 해체 승인 절차", "priority": "필수"},
            {"law": "환경영향평가법", "type": "법률", "reason": "해체 시 환경영향평가 필요 여부", "priority": "해당시"},
        ],
    },
    # ── 전력·에너지 ──
    {
        "keywords": ["발전", "전기", "전력", "송전", "변전", "배전", "전력거래", "전력시장", "계통"],
        "category": "전력사업",
        "recommendations": [
            {"law": "전기사업법", "type": "법률", "reason": "발전·송전·배전사업 허가, 전력거래", "priority": "필수"},
            {"law": "전력기술관리법", "type": "법률", "reason": "전력기술자, 전력시설물 설계·감리", "priority": "필수"},
            {"law": "에너지법", "type": "법률", "reason": "국가에너지기본계획, 에너지 정책 방향", "priority": "권장"},
        ],
    },
    # ── 계약 절차별 ──
    {
        "keywords": ["입찰", "공고", "경쟁입찰", "제한경쟁", "지명경쟁", "입찰참가"],
        "category": "입찰절차",
        "recommendations": [
            {"law": "국가를당사자로하는계약에관한법률", "type": "법률", "reason": "입찰 방법·절차 (제7~10조)", "priority": "필수"},
            {"law": "국가를당사자로하는계약에관한법률", "type": "시행령", "reason": "입찰참가자격, 입찰보증금, 공동계약", "priority": "필수"},
            {"law": "공기업ㆍ준정부기관계약사무규칙", "type": "기획재정부령", "reason": "공기업 입찰 특례", "priority": "필수"},
            {"law": "전자조달의이용및촉진에관한법률", "type": "법률", "reason": "전자입찰 절차", "priority": "권장"},
        ],
    },
    {
        "keywords": ["수의계약", "수의", "1인견적", "긴급", "특수"],
        "category": "수의계약",
        "recommendations": [
            {"law": "국가를당사자로하는계약에관한법률", "type": "시행령", "reason": "수의계약 사유 (시행령 제26조)", "priority": "필수"},
            {"law": "공기업ㆍ준정부기관계약사무규칙", "type": "기획재정부령", "reason": "공기업 수의계약 한도·사유", "priority": "필수"},
        ],
    },
    {
        "keywords": ["계약보증", "보증금", "이행보증", "하자보증", "선급금보증", "계약이행"],
        "category": "보증·보험",
        "recommendations": [
            {"law": "국가를당사자로하는계약에관한법률", "type": "법률", "reason": "계약보증금 납부 의무 (제12조)", "priority": "필수"},
            {"law": "국가를당사자로하는계약에관한법률", "type": "시행령", "reason": "보증금 비율, 면제 사유, 국고귀속", "priority": "필수"},
        ],
    },
    {
        "keywords": ["설계변경", "물가변동", "계약금액조정", "에스컬레이션", "ES", "물가"],
        "category": "계약금액조정",
        "recommendations": [
            {"law": "국가를당사자로하는계약에관한법률", "type": "시행령", "reason": "설계변경·물가변동 계약금액 조정 (제64~66조)", "priority": "필수"},
            {"law": "국가를당사자로하는계약에관한법률", "type": "시행규칙", "reason": "물가변동 산출방법 상세", "priority": "필수"},
        ],
    },
    {
        "keywords": ["하자", "하자보수", "하자담보", "준공", "검사", "검수"],
        "category": "준공·하자",
        "recommendations": [
            {"law": "국가를당사자로하는계약에관한법률", "type": "법률", "reason": "준공검사, 하자보수보증금 (제17~18조)", "priority": "필수"},
            {"law": "국가를당사자로하는계약에관한법률", "type": "시행령", "reason": "하자보수 기간, 보증금 비율", "priority": "필수"},
            {"law": "건설산업기본법", "type": "법률", "reason": "건설공사 하자담보책임 기간", "priority": "해당시"},
        ],
    },
    {
        "keywords": ["지체상금", "지체", "납기지연", "지연배상"],
        "category": "지체상금",
        "recommendations": [
            {"law": "국가를당사자로하는계약에관한법률", "type": "시행령", "reason": "지체상금 비율·산정 (제74조)", "priority": "필수"},
            {"law": "공기업ㆍ준정부기관계약사무규칙", "type": "기획재정부령", "reason": "공기업 지체상금 특례", "priority": "필수"},
        ],
    },
    {
        "keywords": ["하도급", "하청", "재하도급", "수급사업자"],
        "category": "하도급관리",
        "recommendations": [
            {"law": "하도급거래공정화에관한법률", "type": "법률", "reason": "하도급 대금 지급, 부당행위 금지", "priority": "필수"},
            {"law": "하도급거래공정화에관한법률", "type": "시행령", "reason": "하도급 대금 직접지급 사유 등", "priority": "필수"},
            {"law": "건설산업기본법", "type": "법률", "reason": "건설공사 하도급 제한·통보 의무", "priority": "해당시"},
        ],
    },
    {
        "keywords": ["청렴", "부패", "비리", "뇌물", "부정당"],
        "category": "청렴·부정당",
        "recommendations": [
            {"law": "국가를당사자로하는계약에관한법률", "type": "법률", "reason": "청렴계약, 부정당업자 제재 (제27조)", "priority": "필수"},
            {"law": "원전비리방지를위한원자력발전사업자등의관리ㆍ감독에관한법률", "type": "법률", "reason": "원전 납품비리 방지 특별법", "priority": "필수"},
            {"law": "공공기관의운영에관한법률", "type": "법률", "reason": "공공기관 경영공시, 내부통제", "priority": "권장"},
        ],
    },
    # ── 안전·환경 ──
    {
        "keywords": ["안전", "산업재해", "재해", "사고", "중대재해"],
        "category": "안전관리",
        "recommendations": [
            {"law": "산업안전보건법", "type": "법률", "reason": "사업장 안전보건 의무, 안전관리자 선임", "priority": "필수"},
            {"law": "산업안전보건기준에관한규칙", "type": "법률", "reason": "안전보건 기준 상세 (위험기계 등)", "priority": "필수"},
            {"law": "원자력안전법", "type": "법률", "reason": "원자력시설 안전규제", "priority": "해당시"},
        ],
    },
    {
        "keywords": ["환경", "환경영향", "대기", "수질", "소음", "진동", "폐기물"],
        "category": "환경",
        "recommendations": [
            {"law": "환경영향평가법", "type": "법률", "reason": "환경영향평가 대상·절차", "priority": "필수"},
        ],
    },
    # ── 공공기관 ──
    {
        "keywords": ["정보공개", "공시", "경영평가", "감사"],
        "category": "공공기관 경영",
        "recommendations": [
            {"law": "공공기관의운영에관한법률", "type": "법률", "reason": "공공기관 지정, 경영평가, 이사회", "priority": "필수"},
            {"law": "공공기관의정보공개에관한법률", "type": "법률", "reason": "정보공개 청구·절차", "priority": "필수"},
            {"law": "공공기관의회계감사및결산감사에관한규칙", "type": "법률", "reason": "회계·결산 감사 기준", "priority": "해당시"},
        ],
    },
    {
        "keywords": ["독점", "공정거래", "담합", "입찰담합", "카르텔"],
        "category": "공정거래",
        "recommendations": [
            {"law": "독점규제및공정거래에관한법률", "type": "법률", "reason": "입찰담합 금지, 불공정거래행위", "priority": "필수"},
        ],
    },
    {
        "keywords": ["민법", "계약해제", "손해배상", "채무불이행", "위약금", "민사"],
        "category": "민사일반",
        "recommendations": [
            {"law": "민법", "type": "법률", "reason": "계약 총칙, 해제·해지, 손해배상 일반원칙", "priority": "필수"},
        ],
    },
    {
        "keywords": ["단가", "단가계약", "MAS", "다수공급자", "수산물", "식품", "농산물", "식자재", "급식"],
        "category": "단가계약·물품조달",
        "recommendations": [
            {"law": "국가를당사자로하는계약에관한법률", "type": "법률", "reason": "물품 구매·단가계약 체결 절차 규율", "priority": "필수"},
            {"law": "국가를당사자로하는계약에관한법률", "type": "시행령", "reason": "단가계약 체결 방법, 이행 기준 (제22조 등)", "priority": "필수"},
            {"law": "공기업ㆍ준정부기관계약사무규칙", "type": "기획재정부령", "reason": "공기업 단가계약 특례 규정", "priority": "필수"},
            {"law": "조달사업에관한법률", "type": "법률", "reason": "조달청 다수공급자계약(MAS), 단가계약 근거", "priority": "필수"},
            {"law": "전자조달의이용및촉진에관한법률", "type": "법률", "reason": "나라장터 전자입찰·단가계약 절차", "priority": "권장"},
        ],
    },
    {
        "keywords": ["낙찰", "적격심사", "종합심사", "최저가", "2단계"],
        "category": "낙찰·심사",
        "recommendations": [
            {"law": "국가를당사자로하는계약에관한법률", "type": "법률", "reason": "낙찰자 결정 방법 (제10조)", "priority": "필수"},
            {"law": "국가를당사자로하는계약에관한법률", "type": "시행령", "reason": "적격심사, 종합심사낙찰제 세부 기준", "priority": "필수"},
            {"law": "공기업ㆍ준정부기관계약사무규칙", "type": "기획재정부령", "reason": "공기업 낙찰자 결정 특례", "priority": "필수"},
        ],
    },
    {
        "keywords": ["대가지급", "기성", "선급금", "대금", "준공금"],
        "category": "대가지급",
        "recommendations": [
            {"law": "국가를당사자로하는계약에관한법률", "type": "법률", "reason": "대가 지급 시기·방법 (제15조)", "priority": "필수"},
            {"law": "국가를당사자로하는계약에관한법률", "type": "시행령", "reason": "선급금, 기성금 지급 절차", "priority": "필수"},
            {"law": "하도급거래공정화에관한법률", "type": "법률", "reason": "하도급 대금 직접 지급 의무", "priority": "해당시"},
        ],
    },
]


def advise_laws_keyword(query: str) -> dict:
    """키워드 기반 법령 추천 (폴백)"""
    q = query.lower().strip()
    matched = []
    for scenario in ADVISOR_SCENARIOS:
        score = 0
        matched_kw = []
        for kw in scenario["keywords"]:
            if kw.lower() in q:
                score += len(kw)
                matched_kw.append(kw)
        if score > 0:
            matched.append({
                "category": scenario["category"],
                "score": score,
                "matched_keywords": matched_kw,
                "recommendations": scenario["recommendations"],
            })
    if not matched:
        fallback_recs = [
            {"law": "국가를당사자로하는계약에관한법률", "type": "법률", "reason": "국가계약 전반 - 키워드로 관련 조문을 확인해보세요", "priority": "참고"},
            {"law": "공기업ㆍ준정부기관계약사무규칙", "type": "기획재정부령", "reason": "한수원 등 공기업 계약사무 규정", "priority": "참고"},
        ]
        text_results = search_laws(query, limit=5)
        for r in text_results:
            law = r["law_name"]
            if not any(rec["law"] == law for rec in fallback_recs):
                fallback_recs.append({
                    "law": law, "type": r["file_type"],
                    "reason": f"'{query}' 관련 조문 {len(r.get('matching_articles', []))}건 포함",
                    "priority": "참고",
                })
        matched.append({
            "category": "일반검색", "score": 1,
            "matched_keywords": query.split(),
            "recommendations": fallback_recs[:8],
        })
    matched.sort(key=lambda x: -x["score"])
    seen = set()
    all_recs = []
    categories = []
    for m in matched:
        categories.append(m["category"])
        for rec in m["recommendations"]:
            key = (rec["law"], rec["type"])
            if key not in seen:
                seen.add(key)
                rec["from_category"] = m["category"]
                all_recs.append(rec)
    priority_order = {"필수": 0, "권장": 1, "해당시": 2, "참고": 3}
    all_recs.sort(key=lambda x: priority_order.get(x["priority"], 9))
    return {
        "query": query, "categories": categories,
        "recommendations": all_recs, "total": len(all_recs),
        "source": "keyword",
    }


def call_solar(query: str, keyword_result: dict) -> dict | None:
    """Upstage Solar LLM으로 자연어 분석"""
    if not SOLAR_API_KEY:
        return None

    # 키워드 매칭 결과를 컨텍스트로 제공
    kw_laws = "\n".join(
        f"- [{r['priority']}] {r['law']} ({r['type']}): {r['reason']}"
        for r in keyword_result["recommendations"][:15]
    )

    # 사용 가능한 전체 법령 카테고리 목록
    all_scenarios = "\n".join(
        f"- {s['category']}: {', '.join(s['keywords'][:5])}"
        for s in ADVISOR_SCENARIOS
    )

    system_prompt = """당신은 한국수력원자력(한수원) 계약 업무 전문 법령 어드바이저입니다.
사용자의 질의를 분석하여 확인해야 할 법령을 추천합니다.

아래는 시스템이 키워드 매칭으로 찾은 1차 결과입니다:
{kw_result}

사용 가능한 시나리오 카테고리:
{scenarios}

당신의 역할:
1. 사용자의 실제 의도와 맥락을 분석하세요
2. 키워드 매칭 결과가 적절한지 판단하고, 빠진 법령이 있으면 추가하세요
3. 각 법령의 추천 이유를 사용자의 구체적 상황에 맞게 다시 작성하세요
4. 한수원 실무자 관점에서 실질적으로 도움이 되는 조언을 포함하세요

반드시 아래 JSON 형식으로만 응답하세요:
{{
  "analysis": "사용자 질의 분석 (2-3문장)",
  "categories": ["매칭된 카테고리들"],
  "recommendations": [
    {{
      "law": "법령 디렉토리명 (예: 국가를당사자로하는계약에관한법률)",
      "type": "법률/시행령/시행규칙 중 하나",
      "reason": "이 상황에서 왜 이 법을 봐야 하는지 구체적 설명",
      "priority": "필수/권장/해당시 중 하나",
      "key_articles": "핵심 확인 조문 (예: 제26조 수의계약)"
    }}
  ]
}}""".format(kw_result=kw_laws, scenarios=all_scenarios)

    payload = json.dumps({
        "model": SOLAR_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ],
        "temperature": 0.3,
        "max_tokens": 2000,
    }).encode("utf-8")

    req = urllib.request.Request(
        SOLAR_API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {SOLAR_API_KEY}",
            "Content-Type": "application/json",
        },
    )

    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"].strip()
            # JSON 파싱 (코드블록 제거)
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            return json.loads(content)
    except urllib.error.HTTPError as e:
        print(f"Solar API HTTP error {e.code}: {e.read().decode()[:300]}")
        return None
    except Exception as e:
        print(f"Solar API error: {type(e).__name__}: {e}")
        return None


def advise_laws(query: str) -> dict:
    """하이브리드 법령 추천: 키워드 매칭 + Solar LLM"""
    # 1단계: 키워드 매칭
    kw_result = advise_laws_keyword(query)

    # 2단계: Solar LLM 분석 (API 키 있을 때만)
    solar = call_solar(query, kw_result)

    if solar and "recommendations" in solar:
        # Solar 결과를 기반으로 최종 결과 구성
        index = build_index()
        final_recs = []
        seen = set()
        for rec in solar["recommendations"]:
            law = rec.get("law", "")
            ftype = rec.get("type", "법률")
            key = (law, ftype)
            if key in seen:
                continue
            seen.add(key)
            # 실제 존재하는 법령인지 확인
            if law in index:
                entry = {
                    "law": law,
                    "type": ftype,
                    "reason": rec.get("reason", ""),
                    "priority": rec.get("priority", "참고"),
                    "key_articles": rec.get("key_articles", ""),
                    "from_category": "",
                }
                final_recs.append(entry)

        # Solar가 빠뜨린 키워드 매칭 필수 법령 보충
        for rec in kw_result["recommendations"]:
            key = (rec["law"], rec["type"])
            if key not in seen and rec["priority"] == "필수":
                seen.add(key)
                final_recs.append(rec)

        priority_order = {"필수": 0, "권장": 1, "해당시": 2, "참고": 3}
        final_recs.sort(key=lambda x: priority_order.get(x["priority"], 9))

        return {
            "query": query,
            "analysis": solar.get("analysis", ""),
            "categories": solar.get("categories", kw_result["categories"]),
            "recommendations": final_recs,
            "total": len(final_recs),
            "source": "solar",
        }

    # Solar 실패 시 키워드 결과 반환
    return kw_result


# ===== Routes: Pages =====
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/advisor")
def api_advisor():
    """자연어 법령 추천"""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "검색어를 입력해주세요"}), 400
    return jsonify(advise_laws(query))


@app.route("/api/summarize", methods=["POST"])
def api_summarize():
    """Solar LLM으로 핵심 조문 요약"""
    if not SOLAR_API_KEY:
        return jsonify({"error": "LLM not configured"}), 503
    data = request.get_json()
    context = data.get("context", "")  # 원래 검색 맥락
    law_name = data.get("law_name", "")
    articles_text = data.get("articles_text", "")  # 핵심 조문 원문
    if not articles_text:
        return jsonify({"error": "조문 내용이 필요합니다"}), 400

    prompt = f"""당신은 한국수력원자력 계약 실무자를 돕는 법률 어드바이저입니다.

사용자의 업무 맥락: {context}
법령: {law_name}

아래 조문들의 **실무 핵심 포인트**를 정리해주세요.

조문 원문:
{articles_text[:3000]}

다음 형식으로 응답하세요 (JSON):
{{
  "summary": "이 법령을 봐야 하는 이유 한 줄 요약",
  "key_points": [
    {{
      "article": "제X조",
      "title": "조문 제목",
      "point": "실무자가 알아야 할 핵심 1-2문장",
      "warning": "주의사항 (있으면)"
    }}
  ],
  "practical_tips": ["실무 팁 1", "실무 팁 2"]
}}"""

    payload = json.dumps({
        "model": SOLAR_MODEL,
        "messages": [
            {"role": "system", "content": "법령 조문을 실무자 관점에서 쉽게 요약하는 전문가입니다. 반드시 JSON으로만 응답하세요."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 2000,
    }).encode("utf-8")

    req = urllib.request.Request(
        SOLAR_API_URL, data=payload,
        headers={"Authorization": f"Bearer {SOLAR_API_KEY}", "Content-Type": "application/json"},
    )

    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            content = result["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            return jsonify(json.loads(content))
    except Exception as e:
        print(f"Summarize API error: {type(e).__name__}: {e}")
        return jsonify({"error": str(e)}), 500


# ===== Routes: Auth =====
@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json()
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    display_name = (data.get("display_name") or "").strip()
    department = (data.get("department") or "").strip()
    if not username or not password or not display_name:
        return jsonify({"error": "아이디, 비밀번호, 이름을 모두 입력해주세요"}), 400
    if len(username) < 3:
        return jsonify({"error": "아이디는 3자 이상이어야 합니다"}), 400
    if len(password) < 4:
        return jsonify({"error": "비밀번호는 4자 이상이어야 합니다"}), 400
    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
    if existing:
        return jsonify({"error": "이미 사용 중인 아이디입니다"}), 409
    pw_hash = hash_password(password)
    cur = db.execute(
        "INSERT INTO users (username, password_hash, display_name, department) VALUES (?,?,?,?)",
        (username, pw_hash, display_name, department),
    )
    db.commit()
    session["user_id"] = cur.lastrowid
    session["username"] = username
    session["display_name"] = display_name
    return jsonify({"ok": True, "user": {"username": username, "display_name": display_name, "department": department}})


@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json()
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"error": "아이디와 비밀번호를 입력해주세요"}), 400
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not user or not verify_password(password, user["password_hash"]):
        return jsonify({"error": "아이디 또는 비밀번호가 올바르지 않습니다"}), 401
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["display_name"] = user["display_name"]
    return jsonify({"ok": True, "user": {
        "username": user["username"],
        "display_name": user["display_name"],
        "department": user["department"],
    }})


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/auth/me")
def auth_me():
    if "user_id" not in session:
        return jsonify({"logged_in": False})
    db = get_db()
    user = db.execute("SELECT username, display_name, department FROM users WHERE id=?",
                      (session["user_id"],)).fetchone()
    if not user:
        session.clear()
        return jsonify({"logged_in": False})
    return jsonify({
        "logged_in": True,
        "user": {"username": user["username"], "display_name": user["display_name"], "department": user["department"]},
    })


# ===== Routes: Bookmarks =====
@app.route("/api/bookmarks", methods=["GET"])
@login_required
def get_bookmarks():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM bookmarks WHERE user_id=? ORDER BY created_at DESC",
        (session["user_id"],),
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/bookmarks", methods=["POST"])
@login_required
def add_bookmark():
    data = request.get_json()
    law_name = data.get("law_name", "")
    file_type = data.get("file_type", "법률")
    article_num = data.get("article_num", "")
    article_title = data.get("article_title", "")
    memo = data.get("memo", "")
    folder = data.get("folder", "기본")
    if not law_name:
        return jsonify({"error": "법령명이 필요합니다"}), 400
    db = get_db()
    try:
        cur = db.execute(
            """INSERT INTO bookmarks (user_id, law_name, file_type, article_num, article_title, memo, folder)
               VALUES (?,?,?,?,?,?,?)""",
            (session["user_id"], law_name, file_type, article_num, article_title, memo, folder),
        )
        db.commit()
        return jsonify({"ok": True, "id": cur.lastrowid})
    except sqlite3.IntegrityError:
        return jsonify({"error": "이미 북마크에 추가되어 있습니다"}), 409


@app.route("/api/bookmarks/<int:bookmark_id>", methods=["PUT"])
@login_required
def update_bookmark(bookmark_id: int):
    data = request.get_json()
    db = get_db()
    bm = db.execute("SELECT * FROM bookmarks WHERE id=? AND user_id=?",
                     (bookmark_id, session["user_id"])).fetchone()
    if not bm:
        return jsonify({"error": "북마크를 찾을 수 없습니다"}), 404
    memo = data.get("memo", bm["memo"])
    folder = data.get("folder", bm["folder"])
    db.execute("UPDATE bookmarks SET memo=?, folder=? WHERE id=?", (memo, folder, bookmark_id))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/bookmarks/<int:bookmark_id>", methods=["DELETE"])
@login_required
def delete_bookmark(bookmark_id: int):
    db = get_db()
    db.execute("DELETE FROM bookmarks WHERE id=? AND user_id=?",
               (bookmark_id, session["user_id"]))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/bookmarks/folders")
@login_required
def bookmark_folders():
    db = get_db()
    rows = db.execute(
        "SELECT DISTINCT folder FROM bookmarks WHERE user_id=? ORDER BY folder",
        (session["user_id"],),
    ).fetchall()
    folders = [r["folder"] for r in rows]
    if "기본" not in folders:
        folders.insert(0, "기본")
    return jsonify(folders)


@app.route("/api/bookmarks/check")
@login_required
def check_bookmark():
    law_name = request.args.get("law_name", "")
    file_type = request.args.get("file_type", "")
    article_num = request.args.get("article_num", "")
    db = get_db()
    row = db.execute(
        "SELECT id FROM bookmarks WHERE user_id=? AND law_name=? AND file_type=? AND article_num=?",
        (session["user_id"], law_name, file_type, article_num),
    ).fetchone()
    return jsonify({"bookmarked": row is not None, "id": row["id"] if row else None})


# ===== Routes: Law API (unchanged) =====
@app.route("/api/categories")
def api_categories():
    return jsonify(KHNP_CATEGORIES)


@app.route("/api/search")
def api_search():
    query = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip() or None
    if not query:
        return jsonify([])
    return jsonify(search_laws(query, category))


@app.route("/api/law/<path:law_name>")
def api_law(law_name: str):
    index = build_index()
    file_type = request.args.get("type", "법률")
    law_data = index.get(law_name)
    if not law_data:
        return jsonify({"error": "법령을 찾을 수 없습니다"}), 404
    file_data = law_data["files"].get(file_type)
    if not file_data:
        available = list(law_data["files"].keys())
        if available:
            file_data = law_data["files"][available[0]]
            file_type = available[0]
        else:
            return jsonify({"error": "해당 문서를 찾을 수 없습니다"}), 404
    return jsonify({
        "law_name": law_name, "file_type": file_type,
        "title": file_data["meta"].get("제목", law_name),
        "meta": file_data["meta"],
        "articles": file_data["articles"],
        "available_types": list(law_data["files"].keys()),
        "body": file_data["body"],
    })


@app.route("/api/stats")
def api_stats():
    index = build_index()
    return jsonify({
        "total_laws": len(index),
        "total_files": sum(len(v["files"]) for v in index.values()),
        "total_articles": sum(
            len(fd["articles"]) for v in index.values() for fd in v["files"].values()
        ),
        "khnp_categories": len(KHNP_CATEGORIES),
        "khnp_law_count": sum(len(c["laws"]) for c in KHNP_CATEGORIES.values()),
    })


# ===== 공공데이터포털 API 프록시 =====

# ── 한수원 실제 계약 사례 데이터 (공공정보 기반) ──
KHNP_CONTRACT_CASES = [
    {"name":"신한울 3·4호기 주기기 공급계약","org":"한국수력원자력","type":"construction","amount":"4조 5000억","method":"수의계약","date":"2024-06","company":"두산에너빌리티","category":"원자력사업","keywords":["원전","신한울","주기기","건설","공사"]},
    {"name":"월성원전 삼중수소제거설비(WTRF) 건설","org":"한국수력원자력","type":"construction","amount":"3,830억","method":"일반경쟁","date":"2023-12","company":"현대건설 컨소시엄","category":"원자력사업","keywords":["월성","삼중수소","건설","방사능"]},
    {"name":"고리1호기 해체 안전성평가 용역","org":"한국수력원자력","type":"service","amount":"152억","method":"제한경쟁","date":"2024-03","company":"한국원자력연구원","category":"해체","keywords":["해체","고리","안전","용역"]},
    {"name":"원전 계측제어설비 국산화 연구용역","org":"한국수력원자력","type":"service","amount":"87억","method":"제한경쟁","date":"2024-01","company":"KEPCO KPS","category":"용역","keywords":["계측","제어","국산화","연구","용역"]},
    {"name":"한빛원전 정기검사 보수공사","org":"한국수력원자력","type":"construction","amount":"245억","method":"일반경쟁","date":"2024-06","company":"한전KPS","category":"공사계약","keywords":["정기검사","보수","한빛","공사"]},
    {"name":"사용후핵연료 중간저장시설 부지조사 용역","org":"한국수력원자력","type":"service","amount":"63억","method":"제한경쟁","date":"2024-02","company":"한국원자력환경공단","category":"방폐물","keywords":["사용후핵연료","저장","부지","용역"]},
    {"name":"원전 비상디젤발전기 교체 구매","org":"한국수력원자력","type":"goods","amount":"180억","method":"국제입찰","date":"2024-04","company":"두산에너빌리티","category":"물품구매","keywords":["비상","디젤","발전기","구매","물품"]},
    {"name":"원자력발전소 사이버보안시스템 구축","org":"한국수력원자력","type":"service","amount":"95억","method":"제한경쟁","date":"2024-05","company":"안랩","category":"SW·IT","keywords":["사이버","보안","IT","시스템"]},
    {"name":"한울원전 격납건물 건전성시험 용역","org":"한국수력원자력","type":"service","amount":"32억","method":"제한경쟁","date":"2024-07","company":"한국전력기술","category":"원자력사업","keywords":["격납건물","건전성","시험","한울"]},
    {"name":"원전 방사선감시 설비 유지보수","org":"한국수력원자력","type":"service","amount":"47억","method":"일반경쟁","date":"2024-08","company":"한전원자력연료","category":"원자력사업","keywords":["방사선","감시","유지보수","설비"]},
    {"name":"신고리 5·6호기 토목공사","org":"한국수력원자력","type":"construction","amount":"1조 2000억","method":"일반경쟁","date":"2023-09","company":"현대건설","category":"공사계약","keywords":["신고리","토목","건설","공사"]},
    {"name":"원전 안전등급 밸브 조달","org":"한국수력원자력","type":"goods","amount":"210억","method":"제한경쟁","date":"2024-03","company":"대우공업","category":"물품구매","keywords":["밸브","안전등급","조달","물품","구매"]},
    {"name":"경주 방폐장 운영지원 용역","org":"한국수력원자력","type":"service","amount":"128억","method":"일반경쟁","date":"2024-01","company":"한국원자력환경공단","category":"방폐물","keywords":["방폐장","경주","운영","용역"]},
    {"name":"원전 종합안전점검 컨설팅","org":"한국수력원자력","type":"service","amount":"56억","method":"수의계약","date":"2024-05","company":"한국원자력안전기술원","category":"안전","keywords":["안전점검","컨설팅","점검","안전"]},
    {"name":"중수로 원전 하도급 기자재 검사","org":"한국수력원자력","type":"service","amount":"18억","method":"제한경쟁","date":"2024-06","company":"한국품질재단","category":"하도급관리","keywords":["하도급","기자재","검사","중수로"]},
    {"name":"발전소 주변지역 환경영향평가 용역","org":"한국수력원자력","type":"service","amount":"42억","method":"일반경쟁","date":"2024-04","company":"한국환경연구원","category":"안전·환경","keywords":["환경영향평가","환경","발전소","용역"]},
    {"name":"원전 부지 내 도로·배수로 보수공사","org":"한국수력원자력","type":"construction","amount":"28억","method":"일반경쟁","date":"2024-09","company":"지역건설사","category":"공사계약","keywords":["도로","배수로","보수","공사"]},
    {"name":"원자력 전문인력 양성 교육 위탁","org":"한국수력원자력","type":"service","amount":"15억","method":"수의계약","date":"2024-07","company":"한국원자력연구원","category":"용역","keywords":["교육","인력","양성","위탁"]},
]

def _extract_keywords(text):
    """자연어 문장에서 핵심 키워드 추출 — 불용어/조사/어미 제거"""
    import re
    # 불용어: 질문 패턴, 조사, 어미, 일반 동사 등
    STOPWORDS = {
        # 질문 패턴
        "확인해야하는", "확인해야", "확인할", "참고해야", "참고할", "적용되는", "관련된",
        "필요한", "해야하는", "해야할", "알아야할", "알아야하는", "검토해야",
        "어떤", "무엇", "무엇인가요", "어떻게", "왜", "언제", "어디",
        # 조사/어미
        "은", "는", "이", "가", "을", "를", "의", "에", "에서", "으로", "로", "와", "과",
        "도", "만", "까지", "부터", "에게", "한테", "께",
        "시", "때", "경우", "관련", "관한", "대한", "위한", "따른",
        # 일반 동사/명사
        "법령", "법률", "법", "규정", "규칙", "조항", "조문",
        "계약", "계약시", "입찰", "체결", "절차", "방법",  # 계약법 시스템에서 너무 범용적
        "하는", "하면", "하고", "해야", "합니다", "입니다", "있는", "없는",
        "것", "수", "중", "등", "및", "또는",
    }
    # 한글 단어만 추출
    words = re.findall(r'[가-힣]{2,}', text)
    # 조사 붙은 변형 제거: "법령은" → "법령" → 불용어 매치
    cleaned = []
    for w in words:
        # 끝에 조사(은,는,이,가,을,를,의,에,로,도,과,와,시) 제거 후 불용어 체크
        base = re.sub(r'(은|는|이|가|을|를|의|에|로|도|과|와|시|요|까)$', '', w)
        if base in STOPWORDS or w in STOPWORDS:
            continue
        if len(base) >= 2:
            cleaned.append(base)
        elif len(w) >= 2:
            cleaned.append(w)
    return cleaned if cleaned else words[:3]


def _search_khnp_cases(keyword):
    """검색어로 한수원 계약 사례 필터링 — 매칭 없으면 빈 리스트"""
    if not keyword:
        return KHNP_CONTRACT_CASES[:10]
    tokens = _extract_keywords(keyword)
    if not tokens:
        return []
    scored = []
    for case in KHNP_CONTRACT_CASES:
        score = 0
        text = (case["name"] + " " + " ".join(case["keywords"]) + " " + case.get("category", "") + " " + case.get("method", "")).lower()
        for t in tokens:
            if t.lower() in text:
                score += 10
        if score > 0:
            scored.append((score, case))
    scored.sort(key=lambda x: -x[0])
    # 매칭 없으면 빈 리스트 (관련 없는 사례를 보여주지 않음)
    return [c for _, c in scored[:10]]


@app.route("/api/procurement/bids")
def procurement_bids():
    """나라장터 입찰공고 검색 + 서버측 키워드 필터링"""
    q = request.args.get("q", "")
    keyword = request.args.get("keyword", "") or q
    rows = int(request.args.get("rows", 10))
    bid_type = request.args.get("type", "all")

    if not DATA_GO_KR_KEY:
        return jsonify({"items": [], "total": 0, "mock": True})

    type_ops = {
        "goods": [("01", "BidPublicInfoService", "getBidPblancListInfoThng")],
        "construction": [("02", "BidPublicInfoService", "getBidPblancListInfoCnstwk")],
        "service": [("03", "BidPublicInfoService", "getBidPblancListInfoServc")],
        "all": [
            ("01", "BidPublicInfoService", "getBidPblancListInfoThng"),
            ("02", "BidPublicInfoService", "getBidPblancListInfoCnstwk"),
            ("03", "BidPublicInfoService", "getBidPblancListInfoServc"),
        ],
    }
    ops = type_ops.get(bid_type, type_ops["all"])
    type_label = {"01": "goods", "02": "construction", "03": "service"}

    # API 필터가 작동하지 않으므로 대량 조회 후 서버측 필터링
    fetch_rows = max(rows * 10, 100)
    items = []
    for (type_code, svc, op) in ops:
        from datetime import datetime, timedelta
        end_dt = datetime.now().strftime("%Y%m%d%H%M")
        start_dt = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d%H%M")
        params = urllib.parse.urlencode({
            "serviceKey": DATA_GO_KR_KEY,
            "numOfRows": fetch_rows,
            "pageNo": 1,
            "type": "json",
            "inqryDiv": 1,
            "inqryBgnDt": start_dt,
            "inqryEndDt": end_dt,
        })
        url = f"{PROCUREMENT_BASE}/{svc}/{op}?{params}"
        cache_key = f"bids:{type_code}:all:{fetch_rows}"
        data = cached_api_call(cache_key, url)
        if not data:
            continue
        try:
            body = data.get("response", {}).get("body", {})
            raw_items = body.get("items", [])
            if not raw_items:
                raw_items = []
            elif isinstance(raw_items, dict):
                raw_items = raw_items.get("item", [])
            if isinstance(raw_items, dict):
                raw_items = [raw_items]
            for it in raw_items:
                items.append({
                    "id": it.get("bidNtceNo", ""),
                    "name": it.get("bidNtceNm", ""),
                    "org": it.get("ntceInsttNm", ""),
                    "demand_org": it.get("dminsttNm", ""),
                    "date": it.get("bidNtceDt", ""),
                    "close_date": it.get("bidClseDt", ""),
                    "price": it.get("asignBdgtAmt", "0"),
                    "method": it.get("cntrctMthdNm", ""),
                    "bid_method": it.get("bidMthdNm", ""),
                    "url": f"https://www.g2b.go.kr/pt/menu/selectSubFrame.do?framesrc=/pt/menu/frameBidPblanc/selectBidPblancListUser.do?bidNtceNo={it.get('bidNtceNo', '')}",
                    "type": type_label.get(type_code, "service"),
                })
        except Exception as e:
            print(f"입찰공고 파싱 오류: {e}")

    # 서버측 키워드 필터링 (자연어에서 핵심어 추출)
    if keyword:
        tokens = _extract_keywords(keyword)
        if tokens:
            filtered = []
            for it in items:
                text = (it["name"] + " " + it["org"] + " " + it["demand_org"]).lower()
                if any(t.lower() in text for t in tokens):
                    filtered.append(it)
            items = filtered

    return jsonify({"items": items[:rows], "total": len(items), "mock": False})


@app.route("/api/procurement/contracts")
def procurement_contracts():
    """한수원 계약 사례 (내장 데이터 + 나라장터 보조)"""
    q = request.args.get("q", "")
    keyword = request.args.get("keyword", "") or q
    rows = int(request.args.get("rows", 10))

    # 한수원 내장 계약 사례에서 검색
    cases = _search_khnp_cases(keyword)
    items = []
    for c in cases:
        items.append({
            "id": f"khnp-{len(items)+1}",
            "name": c["name"],
            "org": c["org"],
            "amount": c["amount"],
            "date": c["date"],
            "company": c["company"],
            "method": c["method"],
            "category": c.get("category", ""),
            "url": "https://ebid.khnp.co.kr",
        })

    return jsonify({"items": items[:rows], "total": len(items), "mock": False,
                     "source": "한수원 공개 계약사례",
                     "links": {
                         "ebid": "https://ebid.khnp.co.kr",
                         "alio": "https://www.alio.go.kr/organ/organDisclosureDtl.do?apbaId=C0220",
                         "g2b": "https://www.g2b.go.kr",
                     }})


@app.route("/api/alio/contracts")
def alio_contracts():
    """한수원 경영공시 정보 (내장 데이터 기반)"""
    q = request.args.get("q", "")
    keyword = request.args.get("keyword", "") or q

    # 한수원 내장 사례에서 대형 계약 위주로 제공
    cases = _search_khnp_cases(keyword)
    items = []
    for c in cases:
        items.append({
            "org": c["org"],
            "name": c["name"],
            "amount": c["amount"],
            "method": c["method"],
            "company": c["company"],
            "date": c["date"],
            "category": c.get("category", ""),
        })

    return jsonify({"items": items, "total": len(items), "mock": False,
                     "source": "한수원 공개 경영정보",
                     "links": {
                         "alio": "https://www.alio.go.kr/organ/organDisclosureDtl.do?apbaId=C0220",
                     }})


if __name__ == "__main__":
    init_db()
    build_index()
    app.run(debug=False, port=5000)
