"""Vercel Serverless Flask App - 한수원 계약 법령 검색"""
import os, re, json, ssl, secrets, urllib.request, urllib.error
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder=None)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(16))

SOLAR_API_KEY = os.environ.get("UPSTAGE_API_KEY", "")
SOLAR_API_URL = "https://api.upstage.ai/v1/chat/completions"
SOLAR_MODEL = "solar-mini"

BASE = Path(__file__).resolve().parent.parent

# ===== Categories =====
KHNP_CATEGORIES = {
    "contract_core": {"name":"계약 핵심 법령","icon":"file-text","description":"국가계약법, 공기업 계약사무규칙 등","laws":["국가를당사자로하는계약에관한법률","공기업ㆍ준정부기관계약사무규칙","조달사업에관한법률","전자조달의이용및촉진에관한법률","지방자치단체를당사자로하는계약에관한법률"]},
    "public_org": {"name":"공공기관 운영","icon":"building","description":"공공기관 운영, 정보공개, 감사","laws":["공공기관의운영에관한법률","공공기관의정보공개에관한법률","공공기관의회계감사및결산감사에관한규칙","공공기관의갈등예방과해결에관한규정"]},
    "nuclear_energy": {"name":"원자력·전력","icon":"zap","description":"원자력 안전, 전기사업, 전력기술","laws":["원자력안전법","원자력진흥법","원자력손해배상법","원자력손해배상보상계약에관한법률","원자력시설등의방호및방사능방재대책법","원자력안전위원회의설치및운영에관한법률","원자력안전정보공개및소통에관한법률","원전비리방지를위한원자력발전사업자등의관리ㆍ감독에관한법률","전기사업법","전력기술관리법","에너지법","방사성폐기물관리법"]},
    "construction_subcontract": {"name":"건설·하도급","icon":"hard-hat","description":"건설산업, 하도급 거래 공정화","laws":["건설산업기본법","하도급거래공정화에관한법률"]},
    "fair_trade": {"name":"공정거래·민상법","icon":"scale","description":"독점규제, 민법 등 일반 거래법","laws":["독점규제및공정거래에관한법률","민법"]},
    "safety_environment": {"name":"안전·환경","icon":"shield","description":"산업안전, 환경영향평가","laws":["산업안전보건법","환경영향평가법","산업안전보건기준에관한규칙"]},
}

# ===== Advisor Scenarios (imported from app.py) =====
ADVISOR_SCENARIOS = [
    {"keywords":["공사","건설","시공","건축","토목","준공","착공","감리"],"category":"공사계약","recommendations":[{"law":"국가를당사자로하는계약에관한법률","type":"법률","reason":"공사계약의 입찰·체결·이행 전반 규율","priority":"필수"},{"law":"국가를당사자로하는계약에관한법률","type":"시행령","reason":"계약보증금, 지체상금, 물가변동 상세 기준","priority":"필수"},{"law":"공기업ㆍ준정부기관계약사무규칙","type":"기획재정부령","reason":"한수원 등 공기업 계약사무 특별규정","priority":"필수"},{"law":"건설산업기본법","type":"법률","reason":"건설업 등록, 도급 한도, 하도급 제한","priority":"필수"},{"law":"하도급거래공정화에관한법률","type":"법률","reason":"하도급 대금 지급, 기술유용 금지","priority":"권장"},{"law":"산업안전보건법","type":"법률","reason":"공사현장 안전관리","priority":"권장"},{"law":"환경영향평가법","type":"법률","reason":"일정 규모 이상 공사 시 환경영향평가","priority":"해당시"}]},
    {"keywords":["용역","기술용역","설계용역","엔지니어링","컨설팅","연구용역","SW","소프트웨어","IT"],"category":"용역계약","recommendations":[{"law":"국가를당사자로하는계약에관한법률","type":"법률","reason":"용역계약 입찰·체결 절차","priority":"필수"},{"law":"국가를당사자로하는계약에관한법률","type":"시행령","reason":"협상에 의한 계약, 적격심사 기준","priority":"필수"},{"law":"공기업ㆍ준정부기관계약사무규칙","type":"기획재정부령","reason":"공기업 용역계약 특례","priority":"필수"},{"law":"전력기술관리법","type":"법률","reason":"전력기술용역 관련 자격·등록 요건","priority":"해당시"},{"law":"하도급거래공정화에관한법률","type":"법률","reason":"용역 하도급 시 대금 지급 의무","priority":"해당시"}]},
    {"keywords":["구매","물품","자재","조달","납품","장비","기자재","부품"],"category":"물품구매","recommendations":[{"law":"국가를당사자로하는계약에관한법률","type":"법률","reason":"물품 구매 입찰·계약 절차","priority":"필수"},{"law":"공기업ㆍ준정부기관계약사무규칙","type":"기획재정부령","reason":"공기업 물품구매 계약사무 규정","priority":"필수"},{"law":"조달사업에관한법률","type":"법률","reason":"조달청 계약·다수공급자계약(MAS)","priority":"권장"},{"law":"전자조달의이용및촉진에관한법률","type":"법률","reason":"나라장터 전자입찰 절차","priority":"권장"}]},
    {"keywords":["원전","원자력","핵","방사선","방사능","원자로","핵연료"],"category":"원자력사업","recommendations":[{"law":"원자력안전법","type":"법률","reason":"원자력시설 건설·운영 허가, 안전규제 전반","priority":"필수"},{"law":"원자력안전법","type":"시행령","reason":"허가 기준, 검사 절차 상세","priority":"필수"},{"law":"원자력시설등의방호및방사능방재대책법","type":"법률","reason":"원자력시설 물리적방호, 비상대응","priority":"필수"},{"law":"원자력손해배상법","type":"법률","reason":"원자력 사고 시 손해배상 책임","priority":"필수"},{"law":"원자력손해배상보상계약에관한법률","type":"법률","reason":"손해배상 보상계약 체결 의무","priority":"필수"},{"law":"원전비리방지를위한원자력발전사업자등의관리ㆍ감독에관한법률","type":"법률","reason":"납품비리 방지, 품질관리 의무","priority":"필수"},{"law":"원자력진흥법","type":"법률","reason":"원자력 연구개발, 기술자립 지원","priority":"권장"},{"law":"방사성폐기물관리법","type":"법률","reason":"방사성폐기물 처리·처분 의무","priority":"해당시"}]},
    {"keywords":["발전","전기","전력","송전","변전","배전","전력거래","계통"],"category":"전력사업","recommendations":[{"law":"전기사업법","type":"법률","reason":"발전·송전·배전사업 허가, 전력거래","priority":"필수"},{"law":"전력기술관리법","type":"법률","reason":"전력기술자, 전력시설물 설계·감리","priority":"필수"},{"law":"에너지법","type":"법률","reason":"국가에너지기본계획","priority":"권장"}]},
    {"keywords":["입찰","공고","경쟁입찰","제한경쟁"],"category":"입찰절차","recommendations":[{"law":"국가를당사자로하는계약에관한법률","type":"법률","reason":"입찰 방법·절차 (제7~10조)","priority":"필수"},{"law":"국가를당사자로하는계약에관한법률","type":"시행령","reason":"입찰참가자격, 입찰보증금","priority":"필수"},{"law":"공기업ㆍ준정부기관계약사무규칙","type":"기획재정부령","reason":"공기업 입찰 특례","priority":"필수"},{"law":"전자조달의이용및촉진에관한법률","type":"법률","reason":"전자입찰 절차","priority":"권장"}]},
    {"keywords":["수의계약","수의","1인견적","긴급"],"category":"수의계약","recommendations":[{"law":"국가를당사자로하는계약에관한법률","type":"시행령","reason":"수의계약 사유 (시행령 제26조)","priority":"필수"},{"law":"공기업ㆍ준정부기관계약사무규칙","type":"기획재정부령","reason":"공기업 수의계약 한도·사유","priority":"필수"}]},
    {"keywords":["계약보증","보증금","이행보증","하자보증","선급금보증"],"category":"보증·보험","recommendations":[{"law":"국가를당사자로하는계약에관한법률","type":"법률","reason":"계약보증금 납부 의무 (제12조)","priority":"필수"},{"law":"국가를당사자로하는계약에관한법률","type":"시행령","reason":"보증금 비율, 면제 사유","priority":"필수"}]},
    {"keywords":["설계변경","물가변동","계약금액조정","에스컬레이션"],"category":"계약금액조정","recommendations":[{"law":"국가를당사자로하는계약에관한법률","type":"시행령","reason":"설계변경·물가변동 계약금액 조정 (제64~66조)","priority":"필수"},{"law":"국가를당사자로하는계약에관한법률","type":"시행규칙","reason":"물가변동 산출방법 상세","priority":"필수"}]},
    {"keywords":["하자","하자보수","하자담보","준공","검사","검수"],"category":"준공·하자","recommendations":[{"law":"국가를당사자로하는계약에관한법률","type":"법률","reason":"준공검사, 하자보수보증금 (제17~18조)","priority":"필수"},{"law":"국가를당사자로하는계약에관한법률","type":"시행령","reason":"하자보수 기간, 보증금 비율","priority":"필수"},{"law":"건설산업기본법","type":"법률","reason":"건설공사 하자담보책임 기간","priority":"해당시"}]},
    {"keywords":["지체상금","지체","납기지연"],"category":"지체상금","recommendations":[{"law":"국가를당사자로하는계약에관한법률","type":"시행령","reason":"지체상금 비율·산정 (제74조)","priority":"필수"},{"law":"공기업ㆍ준정부기관계약사무규칙","type":"기획재정부령","reason":"공기업 지체상금 특례","priority":"필수"}]},
    {"keywords":["하도급","하청","재하도급","수급사업자"],"category":"하도급관리","recommendations":[{"law":"하도급거래공정화에관한법률","type":"법률","reason":"하도급 대금 지급, 부당행위 금지","priority":"필수"},{"law":"하도급거래공정화에관한법률","type":"시행령","reason":"하도급 대금 직접지급 사유","priority":"필수"},{"law":"건설산업기본법","type":"법률","reason":"건설공사 하도급 제한·통보 의무","priority":"해당시"}]},
    {"keywords":["청렴","부패","비리","뇌물","부정당"],"category":"청렴·부정당","recommendations":[{"law":"국가를당사자로하는계약에관한법률","type":"법률","reason":"청렴계약, 부정당업자 제재 (제27조)","priority":"필수"},{"law":"원전비리방지를위한원자력발전사업자등의관리ㆍ감독에관한법률","type":"법률","reason":"원전 납품비리 방지 특별법","priority":"필수"},{"law":"공공기관의운영에관한법률","type":"법률","reason":"공공기관 경영공시, 내부통제","priority":"권장"}]},
    {"keywords":["안전","산업재해","재해","사고","중대재해"],"category":"안전관리","recommendations":[{"law":"산업안전보건법","type":"법률","reason":"사업장 안전보건 의무","priority":"필수"},{"law":"산업안전보건기준에관한규칙","type":"법률","reason":"안전보건 기준 상세","priority":"필수"},{"law":"원자력안전법","type":"법률","reason":"원자력시설 안전규제","priority":"해당시"}]},
    {"keywords":["환경","환경영향","대기","수질","폐기물"],"category":"환경","recommendations":[{"law":"환경영향평가법","type":"법률","reason":"환경영향평가 대상·절차","priority":"필수"}]},
    {"keywords":["정보공개","공시","경영평가","감사"],"category":"공공기관 경영","recommendations":[{"law":"공공기관의운영에관한법률","type":"법률","reason":"공공기관 지정, 경영평가","priority":"필수"},{"law":"공공기관의정보공개에관한법률","type":"법률","reason":"정보공개 청구·절차","priority":"필수"}]},
    {"keywords":["독점","공정거래","담합","입찰담합"],"category":"공정거래","recommendations":[{"law":"독점규제및공정거래에관한법률","type":"법률","reason":"입찰담합 금지, 불공정거래행위","priority":"필수"}]},
    {"keywords":["민법","계약해제","손해배상","채무불이행","위약금"],"category":"민사일반","recommendations":[{"law":"민법","type":"법률","reason":"계약 총칙, 해제·해지, 손해배상","priority":"필수"}]},
    {"keywords":["방폐물","방사성폐기물","해체","원전해체"],"category":"방사성폐기물·해체","recommendations":[{"law":"방사성폐기물관리법","type":"법률","reason":"방사성폐기물 관리·처분 전반","priority":"필수"},{"law":"원자력안전법","type":"법률","reason":"원자력시설 해체 승인 절차","priority":"필수"},{"law":"환경영향평가법","type":"법률","reason":"해체 시 환경영향평가","priority":"해당시"}]},
]

# ===== Load Data =====
_index = None
def get_index():
    global _index
    if _index is not None:
        return _index
    _index = {}
    for fname in ["khnp_laws_1.json", "khnp_laws_2.json", "rest_laws.json"]:
        p = BASE / "data" / fname
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                _index.update(json.load(f))
    return _index

# ===== Search =====
def search_laws(query, category=None, limit=30):
    index = get_index()
    results = []
    keywords = query.lower().split()
    khnp_priority = set()
    for cat in KHNP_CATEGORIES.values():
        khnp_priority.update(cat["laws"])
    scope = index
    if category and category in KHNP_CATEGORIES:
        scope = {k: v for k, v in index.items() if k in KHNP_CATEGORIES[category]["laws"]}
    for law_name, law_data in scope.items():
        name_match = all(kw in law_name.lower() for kw in keywords)
        name_score = 100 if name_match else 0
        khnp_bonus = 200 if law_name in khnp_priority else 0
        for file_type, file_data in law_data["files"].items():
            meta = file_data.get("meta", {})
            title = meta.get("제목", law_name)
            if all(kw in title.lower() for kw in keywords):
                name_score = max(name_score, 90)
            matching = []
            for art in file_data.get("articles", []):
                art_text = f"{art['number']} {art['title']} {art['content']}".lower()
                if all(kw in art_text for kw in keywords):
                    s = ""
                    for kw in keywords:
                        idx = art['content'].lower().find(kw)
                        if idx >= 0:
                            s = "..." + art['content'][max(0,idx-60):idx+len(kw)+60] + "..."
                            break
                    matching.append({"number":art["number"],"title":art["title"],"snippet":s or art["content"][:150]+"...","score":50})
            if name_score > 0 or matching:
                results.append({"law_name":law_name,"file_type":file_type,"title":meta.get("제목",law_name),"meta":{"소관부처":meta.get("소관부처",[]),"공포일자":meta.get("공포일자",""),"상태":meta.get("상태",""),"출처":meta.get("출처","")},"matching_articles":sorted(matching,key=lambda x:-x["score"])[:5],"score":name_score+khnp_bonus+sum(a["score"] for a in matching[:5])})
    results.sort(key=lambda x:-x["score"])
    return results[:limit]

# ===== Advisor =====
def advise_keyword(query):
    q = query.lower()
    matched = []
    for s in ADVISOR_SCENARIOS:
        score = sum(len(kw) for kw in s["keywords"] if kw.lower() in q)
        if score > 0:
            matched.append({"category":s["category"],"score":score,"recommendations":s["recommendations"]})
    if not matched:
        recs = [{"law":"국가를당사자로하는계약에관한법률","type":"법률","reason":"국가계약 전반","priority":"참고"},{"law":"공기업ㆍ준정부기관계약사무규칙","type":"기획재정부령","reason":"공기업 계약사무","priority":"참고"}]
        for r in search_laws(query, limit=5):
            if not any(x["law"]==r["law_name"] for x in recs):
                recs.append({"law":r["law_name"],"type":r["file_type"],"reason":f"'{query}' 관련 조문 포함","priority":"참고"})
        matched.append({"category":"일반검색","score":1,"recommendations":recs[:8]})
    matched.sort(key=lambda x:-x["score"])
    seen,recs,cats = set(),[],[]
    for m in matched:
        cats.append(m["category"])
        for r in m["recommendations"]:
            k=(r["law"],r["type"])
            if k not in seen:
                seen.add(k); r["from_category"]=m["category"]; recs.append(r)
    po={"필수":0,"권장":1,"해당시":2,"참고":3}
    recs.sort(key=lambda x:po.get(x["priority"],9))
    return {"query":query,"categories":cats,"recommendations":recs,"total":len(recs),"source":"keyword"}

def call_solar(query, kw_result):
    if not SOLAR_API_KEY: return None
    kw_laws = "\n".join(f"- [{r['priority']}] {r['law']} ({r['type']}): {r['reason']}" for r in kw_result["recommendations"][:15])
    prompt = json.dumps({"model":SOLAR_MODEL,"messages":[{"role":"system","content":f"당신은 한수원 계약 법령 어드바이저입니다.\n키워드 매칭 결과:\n{kw_laws}\n\n사용자 질의를 분석하여 JSON으로 응답:\n{{\"analysis\":\"분석\",\"categories\":[],\"recommendations\":[{{\"law\":\"법령명\",\"type\":\"법률\",\"reason\":\"이유\",\"priority\":\"필수/권장/해당시\",\"key_articles\":\"제X조\"}}]}}"},{"role":"user","content":query}],"temperature":0.3,"max_tokens":2000}).encode()
    req = urllib.request.Request(SOLAR_API_URL,data=prompt,headers={"Authorization":f"Bearer {SOLAR_API_KEY}","Content-Type":"application/json"})
    try:
        ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
        with urllib.request.urlopen(req,timeout=30,context=ctx) as resp:
            c=json.loads(resp.read())["choices"][0]["message"]["content"].strip()
            if c.startswith("```"): c=c.split("```")[1]; c=c[4:] if c.startswith("json") else c
            return json.loads(c)
    except: return None

def advise(query):
    kw = advise_keyword(query)
    solar = call_solar(query, kw)
    if solar and "recommendations" in solar:
        index = get_index()
        recs,seen=[],set()
        for r in solar["recommendations"]:
            k=(r.get("law",""),r.get("type","법률"))
            if k not in seen and k[0] in index:
                seen.add(k); recs.append({**r,"from_category":""})
        for r in kw["recommendations"]:
            k=(r["law"],r["type"])
            if k not in seen and r["priority"]=="필수": seen.add(k); recs.append(r)
        po={"필수":0,"권장":1,"해당시":2,"참고":3}
        recs.sort(key=lambda x:po.get(x.get("priority",""),9))
        return {"query":query,"analysis":solar.get("analysis",""),"categories":solar.get("categories",kw["categories"]),"recommendations":recs,"total":len(recs),"source":"solar"}
    return kw

# ===== Summarize =====
def summarize(context, law_name, articles_text):
    if not SOLAR_API_KEY: return {"error":"no api key"}
    prompt = f"사용자 맥락: {context}\n법령: {law_name}\n\n아래 조문의 실무 핵심을 JSON으로 정리:\n{articles_text[:3000]}\n\n형식: {{\"summary\":\"한줄요약\",\"key_points\":[{{\"article\":\"제X조\",\"title\":\"\",\"point\":\"핵심\",\"warning\":\"주의\"}}],\"practical_tips\":[\"팁\"]}}"
    payload = json.dumps({"model":SOLAR_MODEL,"messages":[{"role":"system","content":"법령을 실무자 관점에서 JSON으로 요약하는 전문가"},{"role":"user","content":prompt}],"temperature":0.2,"max_tokens":2000}).encode()
    req = urllib.request.Request(SOLAR_API_URL,data=payload,headers={"Authorization":f"Bearer {SOLAR_API_KEY}","Content-Type":"application/json"})
    try:
        ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
        with urllib.request.urlopen(req,timeout=30,context=ctx) as resp:
            c=json.loads(resp.read())["choices"][0]["message"]["content"].strip()
            if c.startswith("```"): c=c.split("```")[1]; c=c[4:] if c.startswith("json") else c
            return json.loads(c)
    except Exception as e: return {"error":str(e)}

# ===== Routes =====
@app.route("/")
def home():
    return send_from_directory(str(BASE / "templates"), "index.html")

@app.route("/api/categories")
def api_categories():
    return jsonify(KHNP_CATEGORIES)

@app.route("/api/stats")
def api_stats():
    idx = get_index()
    return jsonify({"total_laws":len(idx),"total_files":sum(len(v["files"]) for v in idx.values()),"total_articles":sum(len(fd["articles"]) for v in idx.values() for fd in v["files"].values()),"khnp_categories":6,"khnp_law_count":28})

@app.route("/api/search")
def api_search():
    q = request.args.get("q","").strip()
    if not q: return jsonify([])
    return jsonify(search_laws(q, request.args.get("category") or None))

@app.route("/api/advisor")
def api_advisor():
    q = request.args.get("q","").strip()
    if not q: return jsonify({"error":"검색어를 입력해주세요"}),400
    return jsonify(advise(q))

@app.route("/api/law")
def api_law():
    idx = get_index()
    law_name = request.args.get("name","")
    ft = request.args.get("type","법률")
    law = idx.get(law_name)
    if not law: return jsonify({"error":"법령을 찾을 수 없습니다","searched":law_name}),404
    fd = law["files"].get(ft)
    if not fd:
        avail = list(law["files"].keys())
        if avail: fd=law["files"][avail[0]]; ft=avail[0]
        else: return jsonify({"error":"문서 없음"}),404
    return jsonify({"law_name":law_name,"file_type":ft,"title":fd["meta"].get("제목",law_name),"meta":fd["meta"],"articles":fd["articles"],"available_types":list(law["files"].keys())})

@app.route("/api/summarize", methods=["POST"])
def api_summarize():
    data = request.get_json()
    return jsonify(summarize(data.get("context",""), data.get("law_name",""), data.get("articles_text","")))

# Auth stubs for Vercel (no persistent DB)
@app.route("/api/auth/me")
def auth_me():
    return jsonify({"logged_in":False})

@app.route("/api/bookmarks")
def get_bm():
    return jsonify([])
