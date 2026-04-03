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
    {"keywords":["공사","건설","시공","건축","토목","준공","착공","감리"],"category":"공사계약","recommendations":[{"law":"국가를당사자로하는계약에관한법률","type":"법률","reason":"공사계약의 입찰·체결·이행 전반 규율","priority":"필수","key_articles":"제7조, 제12조, 제14조"},{"law":"국가를당사자로하는계약에관한법률","type":"시행령","reason":"계약보증금, 지체상금, 물가변동 상세 기준","priority":"필수","key_articles":"제50조, 제64조, 제74조"},{"law":"공기업ㆍ준정부기관계약사무규칙","type":"기획재정부령","reason":"한수원 등 공기업 계약사무 특별규정","priority":"필수","key_articles":"제6조, 제15조"},{"law":"건설산업기본법","type":"법률","reason":"건설업 등록, 도급 한도, 하도급 제한","priority":"필수","key_articles":"제9조, 제29조"},{"law":"하도급거래공정화에관한법률","type":"법률","reason":"하도급 대금 지급, 기술유용 금지","priority":"권장"},{"law":"산업안전보건법","type":"법률","reason":"공사현장 안전관리","priority":"권장"},{"law":"환경영향평가법","type":"법률","reason":"일정 규모 이상 공사 시 환경영향평가","priority":"해당시"}]},
    {"keywords":["용역","기술용역","설계용역","엔지니어링","컨설팅","연구용역","SW","소프트웨어","IT"],"category":"용역계약","recommendations":[{"law":"국가를당사자로하는계약에관한법률","type":"법률","reason":"용역계약 입찰·체결 절차","priority":"필수","key_articles":"제7조"},{"law":"국가를당사자로하는계약에관한법률","type":"시행령","reason":"협상에 의한 계약, 적격심사 기준","priority":"필수","key_articles":"제43조, 제26조"},{"law":"공기업ㆍ준정부기관계약사무규칙","type":"기획재정부령","reason":"공기업 용역계약 특례","priority":"필수","key_articles":"제6조"},{"law":"전력기술관리법","type":"법률","reason":"전력기술용역 관련 자격·등록 요건","priority":"해당시"},{"law":"하도급거래공정화에관한법률","type":"법률","reason":"용역 하도급 시 대금 지급 의무","priority":"해당시"}]},
    {"keywords":["구매","물품","자재","조달","납품","장비","기자재","부품"],"category":"물품구매","recommendations":[{"law":"국가를당사자로하는계약에관한법률","type":"법률","reason":"물품 구매 입찰·계약 절차","priority":"필수","key_articles":"제7조"},{"law":"공기업ㆍ준정부기관계약사무규칙","type":"기획재정부령","reason":"공기업 물품구매 계약사무 규정","priority":"필수","key_articles":"제6조"},{"law":"조달사업에관한법률","type":"법률","reason":"조달청 계약·다수공급자계약(MAS)","priority":"권장"},{"law":"전자조달의이용및촉진에관한법률","type":"법률","reason":"나라장터 전자입찰 절차","priority":"권장"}]},
    {"keywords":["원전","원자력","핵","방사선","방사능","원자로","핵연료"],"category":"원자력사업","recommendations":[{"law":"원자력안전법","type":"법률","reason":"원자력시설 건설·운영 허가, 안전규제 전반","priority":"필수"},{"law":"원자력안전법","type":"시행령","reason":"허가 기준, 검사 절차 상세","priority":"필수"},{"law":"원자력시설등의방호및방사능방재대책법","type":"법률","reason":"원자력시설 물리적방호, 비상대응","priority":"필수"},{"law":"원자력손해배상법","type":"법률","reason":"원자력 사고 시 손해배상 책임","priority":"필수"},{"law":"원자력손해배상보상계약에관한법률","type":"법률","reason":"손해배상 보상계약 체결 의무","priority":"필수"},{"law":"원전비리방지를위한원자력발전사업자등의관리ㆍ감독에관한법률","type":"법률","reason":"납품비리 방지, 품질관리 의무","priority":"필수"},{"law":"원자력진흥법","type":"법률","reason":"원자력 연구개발, 기술자립 지원","priority":"권장"},{"law":"방사성폐기물관리법","type":"법률","reason":"방사성폐기물 처리·처분 의무","priority":"해당시"}]},
    {"keywords":["발전","전기","전력","송전","변전","배전","전력거래","계통"],"category":"전력사업","recommendations":[{"law":"전기사업법","type":"법률","reason":"발전·송전·배전사업 허가, 전력거래","priority":"필수","key_articles":"제7조"},{"law":"전력기술관리법","type":"법률","reason":"전력기술자, 전력시설물 설계·감리","priority":"필수","key_articles":"제2조"},{"law":"에너지법","type":"법률","reason":"국가에너지기본계획","priority":"권장"}]},
    {"keywords":["입찰","공고","경쟁입찰","제한경쟁","참가자격","입찰자격","PQ","사전심사"],"category":"입찰절차","recommendations":[{"law":"국가를당사자로하는계약에관한법률","type":"법률","reason":"입찰 방법·절차 (제7~10조)","priority":"필수","key_articles":"제7조, 제8조, 제10조, 제27조"},{"law":"국가를당사자로하는계약에관한법률","type":"시행령","reason":"입찰참가자격 제한, 보증금, 적격심사","priority":"필수","key_articles":"제12조, 제13조, 제21조, 제76조"},{"law":"공기업ㆍ준정부기관계약사무규칙","type":"기획재정부령","reason":"공기업 입찰참가자격·사전심사 특례","priority":"필수","key_articles":"제6조, 제7조, 제15조"},{"law":"전자조달의이용및촉진에관한법률","type":"법률","reason":"전자입찰 절차","priority":"권장"}]},
    {"keywords":["수의계약","수의","1인견적","긴급"],"category":"수의계약","recommendations":[{"law":"국가를당사자로하는계약에관한법률","type":"시행령","reason":"수의계약 사유 (시행령 제26조)","priority":"필수","key_articles":"제26조"},{"law":"공기업ㆍ준정부기관계약사무규칙","type":"기획재정부령","reason":"공기업 수의계약 한도·사유","priority":"필수","key_articles":"제7조"}]},
    {"keywords":["계약보증","보증금","이행보증","하자보증","선급금보증"],"category":"보증·보험","recommendations":[{"law":"국가를당사자로하는계약에관한법률","type":"법률","reason":"계약보증금 납부 의무 (제12조)","priority":"필수","key_articles":"제12조"},{"law":"국가를당사자로하는계약에관한법률","type":"시행령","reason":"보증금 비율, 면제 사유","priority":"필수","key_articles":"제50조, 제51조, 제52조"}]},
    {"keywords":["설계변경","물가변동","계약금액조정","에스컬레이션"],"category":"계약금액조정","recommendations":[{"law":"국가를당사자로하는계약에관한법률","type":"시행령","reason":"설계변경·물가변동 계약금액 조정 (제64~66조)","priority":"필수","key_articles":"제64조, 제65조, 제66조"},{"law":"국가를당사자로하는계약에관한법률","type":"시행규칙","reason":"물가변동 산출방법 상세","priority":"필수","key_articles":"제74조"}]},
    {"keywords":["하자","하자보수","하자담보","준공","검사","검수"],"category":"준공·하자","recommendations":[{"law":"국가를당사자로하는계약에관한법률","type":"법률","reason":"준공검사, 하자보수보증금 (제17~18조)","priority":"필수","key_articles":"제14조, 제18조"},{"law":"국가를당사자로하는계약에관한법률","type":"시행령","reason":"하자보수 기간, 보증금 비율","priority":"필수","key_articles":"제55조, 제60조"},{"law":"건설산업기본법","type":"법률","reason":"건설공사 하자담보책임 기간","priority":"해당시"}]},
    {"keywords":["지체상금","지체","납기지연"],"category":"지체상금","recommendations":[{"law":"국가를당사자로하는계약에관한법률","type":"시행령","reason":"지체상금 비율·산정 (제74조)","priority":"필수","key_articles":"제74조"},{"law":"공기업ㆍ준정부기관계약사무규칙","type":"기획재정부령","reason":"공기업 지체상금 특례","priority":"필수","key_articles":"제16조"}]},
    {"keywords":["하도급","하청","재하도급","수급사업자"],"category":"하도급관리","recommendations":[{"law":"하도급거래공정화에관한법률","type":"법률","reason":"하도급 대금 지급, 부당행위 금지","priority":"필수","key_articles":"제3조, 제13조"},{"law":"하도급거래공정화에관한법률","type":"시행령","reason":"하도급 대금 직접지급 사유","priority":"필수","key_articles":"제9조"},{"law":"건설산업기본법","type":"법률","reason":"건설공사 하도급 제한·통보 의무","priority":"해당시"}]},
    {"keywords":["청렴","부패","비리","뇌물","부정당"],"category":"청렴·부정당","recommendations":[{"law":"국가를당사자로하는계약에관한법률","type":"법률","reason":"청렴계약, 부정당업자 제재 (제27조)","priority":"필수","key_articles":"제27조"},{"law":"원전비리방지를위한원자력발전사업자등의관리ㆍ감독에관한법률","type":"법률","reason":"원전 납품비리 방지 특별법","priority":"필수","key_articles":"제3조, 제6조"},{"law":"공공기관의운영에관한법률","type":"법률","reason":"공공기관 경영공시, 내부통제","priority":"권장"}]},
    {"keywords":["안전","산업재해","재해","사고","중대재해"],"category":"안전관리","recommendations":[{"law":"산업안전보건법","type":"법률","reason":"사업장 안전보건 의무","priority":"필수","key_articles":"제5조, 제63조"},{"law":"산업안전보건기준에관한규칙","type":"법률","reason":"안전보건 기준 상세","priority":"필수"},{"law":"원자력안전법","type":"법률","reason":"원자력시설 안전규제","priority":"해당시"}]},
    {"keywords":["환경","환경영향","대기","수질","폐기물"],"category":"환경","recommendations":[{"law":"환경영향평가법","type":"법률","reason":"환경영향평가 대상·절차","priority":"필수","key_articles":"제2조, 제22조"}]},
    {"keywords":["정보공개","공시","경영평가","감사"],"category":"공공기관 경영","recommendations":[{"law":"공공기관의운영에관한법률","type":"법률","reason":"공공기관 지정, 경영평가","priority":"필수","key_articles":"제39조, 제48조"},{"law":"공공기관의정보공개에관한법률","type":"법률","reason":"정보공개 청구·절차","priority":"필수"}]},
    {"keywords":["독점","공정거래","담합","입찰담합"],"category":"공정거래","recommendations":[{"law":"독점규제및공정거래에관한법률","type":"법률","reason":"입찰담합 금지, 불공정거래행위","priority":"필수","key_articles":"제40조"}]},
    {"keywords":["민법","계약해제","손해배상","채무불이행","위약금"],"category":"민사일반","recommendations":[{"law":"민법","type":"법률","reason":"계약 총칙, 해제·해지, 손해배상","priority":"필수","key_articles":"제390조, 제544조"}]},
    {"keywords":["방폐물","방사성폐기물","해체","원전해체"],"category":"방사성폐기물·해체","recommendations":[{"law":"방사성폐기물관리법","type":"법률","reason":"방사성폐기물 관리·처분 전반","priority":"필수","key_articles":"제3조"},{"law":"원자력안전법","type":"법률","reason":"원자력시설 해체 승인 절차","priority":"필수","key_articles":"제28조"},{"law":"환경영향평가법","type":"법률","reason":"해체 시 환경영향평가","priority":"해당시"}]},
    {"keywords":["단가","단가계약","MAS","다수공급자","수산물","식품","농산물","식자재","급식"],"category":"단가계약·물품조달","recommendations":[{"law":"국가를당사자로하는계약에관한법률","type":"법률","reason":"물품 구매·단가계약 체결 절차 규율","priority":"필수","key_articles":"제7조, 제10조"},{"law":"국가를당사자로하는계약에관한법률","type":"시행령","reason":"단가계약 체결 방법, 이행 기준","priority":"필수","key_articles":"제22조, 제26조"},{"law":"공기업ㆍ준정부기관계약사무규칙","type":"기획재정부령","reason":"공기업 단가계약 특례 규정","priority":"필수","key_articles":"제6조, 제15조"},{"law":"조달사업에관한법률","type":"법률","reason":"조달청 다수공급자계약(MAS), 단가계약 근거","priority":"필수","key_articles":"제5조의2"},{"law":"전자조달의이용및촉진에관한법률","type":"법률","reason":"나라장터 전자입찰·단가계약 절차","priority":"권장"}]},
    {"keywords":["낙찰","적격심사","종합심사","최저가","2단계"],"category":"낙찰·심사","recommendations":[{"law":"국가를당사자로하는계약에관한법률","type":"법률","reason":"낙찰자 결정 방법 (제10조)","priority":"필수","key_articles":"제10조"},{"law":"국가를당사자로하는계약에관한법률","type":"시행령","reason":"적격심사, 종합심사낙찰제 세부 기준","priority":"필수","key_articles":"제42조, 제43조"},{"law":"공기업ㆍ준정부기관계약사무규칙","type":"기획재정부령","reason":"공기업 낙찰자 결정 특례","priority":"필수"}]},
    {"keywords":["대가지급","기성","선급금","대금","준공금"],"category":"대가지급","recommendations":[{"law":"국가를당사자로하는계약에관한법률","type":"법률","reason":"대가 지급 시기·방법 (제15조)","priority":"필수","key_articles":"제15조"},{"law":"국가를당사자로하는계약에관한법률","type":"시행령","reason":"선급금, 기성금 지급 절차","priority":"필수","key_articles":"제55조, 제58조"},{"law":"하도급거래공정화에관한법률","type":"법률","reason":"하도급 대금 직접 지급 의무","priority":"해당시"}]},
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
    prompt = json.dumps({"model":SOLAR_MODEL,"messages":[{"role":"system","content":f"당신은 한수원(한국수력원자력) 계약담당자의 법무 조언자입니다.\n\n키워드 매칭 결과:\n{kw_laws}\n\n사용자의 계약 상황을 분석하여 JSON으로 응답하세요.\n- analysis: 실무자 관점 분석 (2-3문장, 반드시 주의사항·리스크 포함)\n- categories: 매칭된 카테고리\n- recommendations: 각 법령에 대해 law, type, reason(구체적 실무 이유), priority, key_articles(핵심 조문번호)\n\n응답 형식: {{\"analysis\":\"...\",\"categories\":[],\"recommendations\":[{{\"law\":\"법령명\",\"type\":\"법률\",\"reason\":\"이유\",\"priority\":\"필수/권장/해당시\",\"key_articles\":\"제X조, 제Y조\"}}]}}"},{"role":"user","content":query}],"temperature":0.3,"max_tokens":2000}).encode()
    req = urllib.request.Request(SOLAR_API_URL,data=prompt,headers={"Authorization":f"Bearer {SOLAR_API_KEY}","Content-Type":"application/json"})
    try:
        ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
        with urllib.request.urlopen(req,timeout=30,context=ctx) as resp:
            c=json.loads(resp.read())["choices"][0]["message"]["content"].strip()
            if c.startswith("```"): c=c.split("```")[1]; c=c[4:] if c.startswith("json") else c
            return json.loads(c)
    except: return None

def parse_amount(query):
    """검색어에서 금액 추출 (단위: 원)"""
    patterns = [
        (r'(\d+(?:\.\d+)?)\s*억', 100000000),
        (r'(\d+(?:,\d{3})*)\s*만\s*원', 10000),
        (r'(\d+(?:\.\d+)?)\s*천만', 10000000),
        (r'(\d+(?:,\d{3})*)\s*원', 1),
    ]
    for pat, mult in patterns:
        m = re.search(pat, query)
        if m:
            num = float(m.group(1).replace(',',''))
            return int(num * mult)
    return None

def get_contract_method(amount, query):
    """금액·유형별 계약방식 판별"""
    q = query.lower()
    is_construction = any(kw in q for kw in ["공사","건설","시공","토목"])
    is_service = any(kw in q for kw in ["용역","설계","컨설팅","SW","IT"])

    result = {"amount": amount, "amount_display": "", "method": "", "details": [], "warnings": []}

    # 금액 표시
    if amount >= 100000000:
        result["amount_display"] = f"{amount/100000000:.1f}억원"
    elif amount >= 10000:
        result["amount_display"] = f"{amount/10000:.0f}만원"
    else:
        result["amount_display"] = f"{amount:,}원"

    # 공기업 기준 (한수원)
    if is_construction:
        if amount >= 30000000000:  # 300억 이상
            result["method"] = "국제경쟁입찰"
            result["details"] = ["WTO 정부조달협정 적용", "외국업체 참가 가능", "공고기간 40일 이상"]
        elif amount >= 300000000:  # 3억 이상
            result["method"] = "일반경쟁입찰 (제한경쟁 가능)"
            result["details"] = ["적격심사 또는 종합심사낙찰제", "시공능력평가액 이상 업체", "PQ 사전심사 가능"]
        elif amount >= 50000000:  # 5천만원 이상
            result["method"] = "일반경쟁입찰"
            result["details"] = ["소규모 공사 간이절차 가능", "적격심사 적용"]
        else:
            result["method"] = "수의계약 가능"
            result["details"] = ["추정가격 5천만원 미만", "2인 이상 견적서 징수", "시행령 제26조 적용"]
    elif is_service:
        if amount >= 20000000000:  # 200억 이상
            result["method"] = "국제경쟁입찰"
            result["details"] = ["WTO 정부조달협정 적용"]
        elif amount >= 200000000:  # 2억 이상
            result["method"] = "제한경쟁 또는 협상에 의한 계약"
            result["details"] = ["기술능력 평가 필수", "협상절차 (시행령 제43조)", "제안서 평가위원회 구성"]
        elif amount >= 50000000:  # 5천만원 이상
            result["method"] = "일반경쟁입찰"
            result["details"] = ["적격심사 적용"]
        else:
            result["method"] = "수의계약 가능"
            result["details"] = ["추정가격 5천만원 미만", "2인 이상 견적서 징수"]
    else:  # 물품
        if amount >= 20000000000:  # 200억 이상
            result["method"] = "국제경쟁입찰"
            result["details"] = ["WTO 정부조달협정 적용"]
        elif amount >= 50000000:  # 5천만원 이상
            result["method"] = "일반경쟁입찰"
            result["details"] = ["나라장터 전자입찰", "최저가 낙찰 또는 적격심사"]
            if amount >= 200000000:
                result["details"].append("계약심사위원회 심의 권장")
        elif amount >= 20000000:  # 2천만원 이상
            result["method"] = "일반경쟁 또는 수의계약"
            result["details"] = ["수의계약 시 2인 이상 견적", "소액수의계약 가능 범위 확인"]
        else:
            result["method"] = "수의계약 (소액)"
            result["details"] = ["추정가격 2천만원 미만", "1인 견적 가능 (공기업 기준)"]

    # 공통 경고
    if amount >= 100000000:
        result["warnings"].append("계약보증금 납부 필수 (계약금액의 10~15%)")
    if amount >= 300000000:
        result["warnings"].append("선급금 지급 시 선급금보증서 징구")
    if is_construction and amount >= 100000000:
        result["warnings"].append("건설공사보험 가입 확인")

    return result

PROCESS_FLOWS = {
    "입찰": [
        {"step":"수요확인","desc":"소요량·사양서 확정","law":""},
        {"step":"예정가격 작성","desc":"원가계산 또는 거래실례가격 조사","law":"시행령 제9조"},
        {"step":"입찰공고","desc":"7일 이상 (긴급시 5일)","law":"국가계약법 제7조"},
        {"step":"입찰참가등록","desc":"자격심사·PQ 사전확인","law":"시행령 제12조"},
        {"step":"개찰·낙찰","desc":"적격심사 또는 최저가","law":"국가계약법 제10조"},
        {"step":"계약체결","desc":"낙찰일로부터 10일 이내","law":"시행령 제46조"},
        {"step":"이행","desc":"납품·시공·용역 수행","law":""},
        {"step":"검수·준공","desc":"계약이행 확인","law":"국가계약법 제14조"},
    ],
    "공사": [
        {"step":"설계·사양 확정","desc":"실시설계 완료","law":"건설산업기본법 제22조"},
        {"step":"예정가격 작성","desc":"원가계산·실적공사비","law":"시행령 제9조"},
        {"step":"입찰공고","desc":"경쟁입찰 7일 이상","law":"국가계약법 제7조"},
        {"step":"적격심사","desc":"시공능력·실적·가격","law":"시행령 제42조"},
        {"step":"계약체결","desc":"공사도급계약서 작성","law":"시행령 제46조"},
        {"step":"착공·시공","desc":"감리·안전관리","law":"산업안전보건법 제63조"},
        {"step":"기성검사","desc":"부분준공·기성금 지급","law":"시행령 제55조"},
        {"step":"준공검사","desc":"하자보수보증금 납부","law":"국가계약법 제14조"},
        {"step":"하자담보","desc":"하자보수책임기간","law":"건설산업기본법 제28조"},
    ],
    "용역": [
        {"step":"과업지시서 작성","desc":"용역 범위·기간 확정","law":""},
        {"step":"예정가격 작성","desc":"노임단가·경비율 산정","law":"시행령 제9조"},
        {"step":"입찰·제안서 평가","desc":"기술능력 평가","law":"시행령 제43조"},
        {"step":"협상·계약","desc":"기술협상 후 계약","law":"시행령 제43조의2"},
        {"step":"착수·수행","desc":"주간·월간 보고","law":""},
        {"step":"중간성과 검토","desc":"기성금 지급 가능","law":"시행령 제55조"},
        {"step":"최종성과 납품","desc":"성과품 검수","law":"국가계약법 제14조"},
        {"step":"대가지급","desc":"검수 후 14일 이내","law":"국가계약법 제15조"},
    ],
    "구매": [
        {"step":"수요조사","desc":"물품 사양·수량 확정","law":""},
        {"step":"예정가격 작성","desc":"시장조사·거래실례","law":"시행령 제9조"},
        {"step":"입찰공고","desc":"나라장터 전자입찰","law":"전자조달법 제5조"},
        {"step":"개찰·낙찰","desc":"최저가 또는 적격심사","law":"국가계약법 제10조"},
        {"step":"계약체결","desc":"물품공급계약서","law":"시행령 제46조"},
        {"step":"납품","desc":"납품기한 내 인도","law":""},
        {"step":"검수","desc":"수량·품질·규격 확인","law":"국가계약법 제14조"},
        {"step":"대가지급","desc":"검수 후 14일 이내","law":"국가계약법 제15조"},
    ],
    "단가": [
        {"step":"수요예측","desc":"연간 소요량 산정","law":""},
        {"step":"단가 산정","desc":"시장조사·원가계산","law":"시행령 제9조"},
        {"step":"입찰·단가결정","desc":"경쟁 또는 MAS 활용","law":"시행령 제22조"},
        {"step":"단가계약 체결","desc":"단가만 확정, 수량 미확정","law":"공기업규칙 제15조"},
        {"step":"납품요청","desc":"수시 발주","law":""},
        {"step":"검수·대가지급","desc":"월별 정산","law":"국가계약법 제15조"},
    ],
    "수의계약": [
        {"step":"수의계약 사유 확인","desc":"시행령 제26조 해당 여부","law":"시행령 제26조"},
        {"step":"견적서 징수","desc":"2인 이상 견적서","law":"시행령 제30조"},
        {"step":"예정가격 결정","desc":"견적서 기반 산정","law":"시행령 제9조"},
        {"step":"계약심사","desc":"심사위원회 검토 (한도 초과 시)","law":"공기업규칙 제7조"},
        {"step":"계약체결","desc":"수의계약서 작성","law":""},
        {"step":"이행·검수","desc":"납품 확인","law":"국가계약법 제14조"},
    ],
}

def get_reference_data(query, recommendations):
    """검색어 + 추천 법령 기반 참고 조문·계약 사례 생성"""
    index = get_index()
    q = query.lower()
    keywords = [kw for kw in q.split() if len(kw) >= 1]
    ref = {"articles":[], "cases":[], "links":[], "query_keywords": keywords}

    # ── 0. 계약 프로세스 플로우 ──
    process = []
    for key, flow in PROCESS_FLOWS.items():
        if key in q:
            process = flow
            break
    if not process:
        for key in ["계약", "물품", "납품"]:
            if key in q:
                process = PROCESS_FLOWS.get("구매", [])
                break
    ref["process"] = process

    # ── 0.5. 금액별 계약방식 자동 판별 ──
    amount = parse_amount(query)
    if amount:
        ref["contract_method"] = get_contract_method(amount, query)

    # ── 1. 참고 조문: 추천 법령의 key_articles 전체 내용 추출 ──
    seen_arts = set()
    for r in recommendations[:8]:
        law_name = r.get("law","")
        file_type = r.get("type","법률")
        ka = r.get("key_articles","")
        if not ka or law_name not in index: continue
        fd = index[law_name]["files"].get(file_type)
        if not fd: continue
        art_nums = re.findall(r'제\d+조(?:의\d+)?', ka)
        for art in fd.get("articles",[]):
            if art["number"] in art_nums and art["number"] not in seen_arts:
                seen_arts.add(art["number"])
                # 전체 내용 전달 (프론트에서 펼치기/접기)
                ref["articles"].append({
                    "law": law_name, "type": file_type,
                    "number": art["number"], "title": art["title"],
                    "content": art["content"],
                    "reason": r.get("reason",""),
                    "priority": r.get("priority","참고"),
                })
                if len(ref["articles"]) >= 10: break
        if len(ref["articles"]) >= 10: break

    # 키워드 매칭으로 추가 관련 조문 보충 (전체 내용)
    if len(ref["articles"]) < 5:
        kws = keywords
        for law_name, law_data in index.items():
            for ft, fd in law_data["files"].items():
                for art in fd.get("articles",[]):
                    k = f"{law_name}:{art['number']}"
                    if k in seen_arts: continue
                    text = f"{art['title']} {art['content']}".lower()
                    if all(kw in text for kw in kws):
                        seen_arts.add(k)
                        ref["articles"].append({
                            "law": law_name, "type": ft,
                            "number": art["number"], "title": art["title"],
                            "content": art["content"],
                            "reason": f"'{query}' 키워드 포함 조문",
                            "priority": "참고",
                        })
                        if len(ref["articles"]) >= 10: break
                if len(ref["articles"]) >= 10: break
            if len(ref["articles"]) >= 10: break

    # ── 2. 계약 사례: 시나리오 기반 실무 사례 ──
    CASES = [
        {"keywords":["입찰","공고","참가자격","PQ"],"title":"입찰 참가자격 사전심사","desc":"한수원 물품·공사 입찰 시 참가자격 충족 여부를 사전 확인해야 합니다. 실적·자격등록·재무상태 등 자격 요건은 공기업 계약사무규칙 제6조~제7조에서 규정합니다.","laws":["국가를당사자로하는계약에관한법률 시행령 제12조","공기업ㆍ준정부기관계약사무규칙 제6조"],"checklist":["입찰참가자격 사전심사 통과 여부","실적증명서 유효기간 확인","면허·등록 유효 여부","재무비율 충족 확인"]},
        {"keywords":["계약","단가","수산물","식품","납품","급식"],"title":"단가계약 체결 및 이행","desc":"수산물·식품류 단가계약은 물품 수요가 계속적·반복적일 때 단가만 정하여 체결합니다. 공기업 계약사무규칙 제15조의 단가계약 특례를 확인하고, 나라장터 MAS(다수공급자계약) 활용 여부도 검토합니다.","laws":["국가를당사자로하는계약에관한법률 시행령 제22조","조달사업에관한법률 제5조의2"],"checklist":["단가계약 대상 물품 적합성","계약단가 산정 적정성","납품 검수 기준 명확화","다수공급자계약(MAS) 활용 가능 여부"]},
        {"keywords":["수의계약","수의","긴급","1인견적"],"title":"수의계약 체결 시 유의사항","desc":"수의계약은 경쟁입찰 예외로서, 시행령 제26조의 사유에 해당할 때만 가능합니다. 공기업은 규칙 제7조의2의 수의계약 한도액 이내에서 체결합니다.","laws":["국가를당사자로하는계약에관한법률 시행령 제26조","공기업ㆍ준정부기관계약사무규칙 제7조의2"],"checklist":["수의계약 사유 해당 여부 확인","추정가격 한도액 이내 확인","2인 이상 견적서 징수","계약심사위원회 심의 필요 여부"]},
        {"keywords":["공사","건설","시공","준공"],"title":"공사계약 준공검사 절차","desc":"공사 완료 후 준공검사를 통해 계약이행 적정성을 확인합니다. 하자보수보증금을 납부받고, 하자담보책임기간을 설정합니다.","laws":["국가를당사자로하는계약에관한법률 제14조","건설산업기본법 제28조"],"checklist":["준공검사 신청서 접수","설계도서 대비 시공 확인","하자보수보증금 납부","하자담보책임기간 설정"]},
        {"keywords":["보증금","이행보증","하자보증","계약보증"],"title":"계약보증금 관리","desc":"계약금액의 일정 비율을 보증금으로 납부받아야 합니다. 보증보험증권, 이행보증서 등으로 대체 가능하며, 시행령 제50조의 면제 사유를 확인합니다.","laws":["국가를당사자로하는계약에관한법률 제12조","국가를당사자로하는계약에관한법률 시행령 제50조"],"checklist":["보증금 비율 확인 (10~15%)","보증보험증권 유효기간 확인","보증금 면제 사유 해당 여부","하자보증금 비율·기간 설정"]},
        {"keywords":["지체상금","지체","납기지연","이행지체"],"title":"지체상금 부과 기준","desc":"이행기한 내 계약을 이행하지 않을 경우 지체상금을 부과합니다. 공사·물품·용역별 지체상금률이 다르며, 불가항력 사유 시 면제될 수 있습니다.","laws":["국가를당사자로하는계약에관한법률 시행령 제74조","공기업ㆍ준정부기관계약사무규칙 제16조"],"checklist":["지체상금률 확인 (공사1/1000, 물품0.75/1000)","지체일수 산정 기준","불가항력 면제 사유 검토","상한액 (계약보증금 상당액) 확인"]},
        {"keywords":["설계변경","물가변동","계약금액조정","에스컬"],"title":"계약금액 조정 절차","desc":"설계변경, 물가변동, 기타 계약내용 변경으로 계약금액을 조정할 수 있습니다. 물가변동 조정은 입찰일 기준 90일 이상 경과 + 3% 이상 등락 시 가능합니다.","laws":["국가를당사자로하는계약에관한법률 시행령 제64조","국가를당사자로하는계약에관한법률 시행령 제65조"],"checklist":["물가변동 조정 요건 충족 확인","품목·지수 조정방법 선택","설계변경 승인 절차 확인","조정금액 산출근거 서류 징구"]},
        {"keywords":["하도급","하청","재하도급","수급사업자"],"title":"하도급 관리 의무","desc":"하도급대금 적기지급, 기술자료 유용 금지 등 원사업자의 하도급 관리 의무가 있습니다. 위반 시 과징금·입찰참가자격 제한이 가능합니다.","laws":["하도급거래공정화에관한법률 제13조","하도급거래공정화에관한법률 제14조의2"],"checklist":["하도급대금 60일 이내 지급 확인","하도급 대금 직접지급 사유 검토","하도급 통보 의무 이행","재하도급 제한 요건 확인"]},
        {"keywords":["부정당","제재","비리","청렴","뇌물"],"title":"부정당업자 제재","desc":"허위서류 제출, 담합, 뇌물 등 부정행위가 확인되면 입찰참가자격을 제한합니다. 한수원은 원전비리방지법에 따른 가중제재도 적용됩니다.","laws":["국가를당사자로하는계약에관한법률 제27조","원전비리방지를위한원자력발전사업자등의관리ㆍ감독에관한법률 제6조"],"checklist":["부정당업자 제재 사유 해당 여부","제재기간 산정 (6개월~2년)","원전비리방지법 가중적용 여부","과징금 병과 가능 여부"]},
        {"keywords":["원전","원자력","핵","방사선","안전"],"title":"원자력 관련 계약 특례","desc":"원자력 시설 관련 계약은 원자력안전법에 따른 품질보증(QA) 요건과 원전비리방지법의 관리·감독 의무가 추가됩니다.","laws":["원자력안전법 제10조","원전비리방지를위한원자력발전사업자등의관리ㆍ감독에관한법률 제3조"],"checklist":["품질보증(QA) 등급 적용 여부","원전비리방지법 적용 대상 확인","안전등급 기기 해당 여부","품질검사 계획서 수립"]},
    ]
    for case in CASES:
        if any(kw in q for kw in case["keywords"]):
            ref["cases"].append(case)
    if not ref["cases"]:
        ref["cases"].append({"title":"일반 계약 체결 절차","desc":"공기업 계약은 국가계약법과 공기업 계약사무규칙에 따라 체결합니다. 입찰공고→입찰→낙찰자 결정→계약체결→이행→준공검사 순으로 진행됩니다.","laws":["국가를당사자로하는계약에관한법률 제7조","공기업ㆍ준정부기관계약사무규칙 제5조"],"checklist":["예정가격 작성","입찰공고 (7일 이상)","적격심사/종합심사","계약서 작성·체결"],"keywords":[]})

    # ── 3. 외부 링크 (간소화) ──
    links = [{"title":"국가법령정보센터","url":"https://www.law.go.kr","desc":"법률·시행령·판례 통합검색"}]
    if any(kw in q for kw in ["입찰","공고","계약","조달","구매","물품","공사","용역","단가","수의","납품"]):
        links.insert(0, {"title":"나라장터","url":"https://www.g2b.go.kr:8101/ep/tbid/tbidList.do","desc":"입찰공고·계약정보"})
    links.append({"title":"한수원 전자조달","url":"https://ebiz.khnp.co.kr","desc":"한수원 전자입찰시스템"})
    links.append({"title":"알리오","url":"https://www.alio.go.kr/organ/organDisclosureDtl.do?apbaId=C0220","desc":"한수원 경영정보 공시"})
    ref["links"] = links

    return ref

def get_related_queries(query):
    """시나리오 키워드 기반 유사 검색어 추천"""
    q = query.lower()
    related = set()
    for s in ADVISOR_SCENARIOS:
        if any(kw.lower() in q for kw in s["keywords"]):
            for kw in s["keywords"]:
                if kw.lower() not in q and len(kw) >= 2:
                    related.add(kw)
    return list(related)[:8]

def advise(query):
    kw = advise_keyword(query)
    solar = call_solar(query, kw)
    related_queries = get_related_queries(query)
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
        ref_data = get_reference_data(query, recs)
        return {"query":query,"analysis":solar.get("analysis",""),"categories":solar.get("categories",kw["categories"]),"recommendations":recs,"total":len(recs),"source":"solar","ref_data":ref_data,"related_queries":related_queries}
    ref_data = get_reference_data(query, kw["recommendations"])
    kw["ref_data"] = ref_data
    kw["related_queries"] = related_queries
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

# ===== 나라장터 입찰공고 프록시 =====
G2B_API_KEY = os.environ.get("G2B_API_KEY", "")
def fetch_g2b_bids(keyword, num=5):
    """나라장터 OpenAPI에서 입찰공고 검색 (공공데이터포털 키 필요)"""
    if not G2B_API_KEY: return []
    try:
        params = urllib.parse.urlencode({
            "ServiceKey": G2B_API_KEY,
            "numOfRows": str(num),
            "pageNo": "1",
            "inqryDiv": "1",
            "inqryBgnDt": "",
            "inqryEndDt": "",
            "bidNtceNm": keyword,
            "type": "json",
        })
        url = f"https://apis.data.go.kr/1230000/BidPublicInfoService04/getBidPblancListInfoThngPPSSrch01?{params}"
        ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            data = json.loads(resp.read())
        items = data.get("response",{}).get("body",{}).get("items","")
        if not items: return []
        item_list = items if isinstance(items, list) else items.get("item",[])
        if isinstance(item_list, dict): item_list = [item_list]
        results = []
        for it in item_list[:num]:
            results.append({
                "title": it.get("bidNtceNm",""),
                "org": it.get("ntceInsttNm",""),
                "date": it.get("bidNtceDt","")[:10] if it.get("bidNtceDt") else "",
                "deadline": it.get("bidClseDt","")[:10] if it.get("bidClseDt") else "",
                "amount": it.get("presmptPrce",""),
                "url": it.get("bidNtceDtlUrl",""),
                "method": it.get("bidMethdNm",""),
            })
        return results
    except: return []

# ===== Routes =====
@app.route("/")
def home():
    return send_from_directory(str(BASE / "templates"), "index.html")

@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory(str(BASE / "static"), filename)

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

@app.route("/api/bids")
def api_bids():
    q = request.args.get("q","").strip()
    if not q: return jsonify([])
    return jsonify(fetch_g2b_bids(q))

# Auth stubs for Vercel (no persistent DB)
@app.route("/api/auth/me")
def auth_me():
    return jsonify({"logged_in":False})

@app.route("/api/bookmarks")
def get_bm():
    return jsonify([])
