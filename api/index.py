"""Vercel Serverless Flask App - 한수원 계약 법령 검색"""
import os, re, json, ssl, secrets, urllib.request, urllib.error, urllib.parse
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
    {"keywords":["공사","건설","시공","건축","토목","준공","착공","감리"],"category":"공사계약","recommendations":[{"law":"국가를당사자로하는계약에관한법률","type":"법률","reason":"공사계약의 입찰·체결·이행 전반 규율","priority":"필수","key_articles":"제7조, 제12조, 제14조"},{"law":"국가를당사자로하는계약에관한법률","type":"시행령","reason":"계약보증금, 지체상금, 물가변동 상세 기준","priority":"필수","key_articles":"제50조, 제64조, 제74조"},{"law":"공기업ㆍ준정부기관계약사무규칙","type":"기획재정부령","reason":"한수원 등 공기업 계약사무 특별규정","priority":"필수","key_articles":"제6조, 제15조"},{"law":"건설산업기본법","type":"법률","reason":"건설업 등록, 도급 한도, 하도급 제한","priority":"필수","key_articles":"제9조, 제29조"},{"law":"하도급거래공정화에관한법률","type":"법률","reason":"하도급 대금 지급, 기술유용 금지","priority":"권장","key_articles":"제3조, 제13조"},{"law":"산업안전보건법","type":"법률","reason":"공사현장 안전관리","priority":"권장","key_articles":"제5조, 제63조"},{"law":"환경영향평가법","type":"법률","reason":"일정 규모 이상 공사 시 환경영향평가","priority":"해당시","key_articles":"제22조"}]},
    {"keywords":["용역","기술용역","설계용역","엔지니어링","컨설팅","연구용역","SW","소프트웨어","IT"],"category":"용역계약","recommendations":[{"law":"국가를당사자로하는계약에관한법률","type":"법률","reason":"용역계약 입찰·체결 절차","priority":"필수","key_articles":"제7조"},{"law":"국가를당사자로하는계약에관한법률","type":"시행령","reason":"협상에 의한 계약, 적격심사 기준","priority":"필수","key_articles":"제43조, 제26조"},{"law":"공기업ㆍ준정부기관계약사무규칙","type":"기획재정부령","reason":"공기업 용역계약 특례","priority":"필수","key_articles":"제6조"},{"law":"전력기술관리법","type":"법률","reason":"전력기술용역 관련 자격·등록 요건","priority":"해당시","key_articles":"제2조, 제12조"},{"law":"하도급거래공정화에관한법률","type":"법률","reason":"용역 하도급 시 대금 지급 의무","priority":"해당시","key_articles":"제3조, 제13조"}]},
    {"keywords":["구매","물품","자재","조달","납품","장비","기자재","부품"],"category":"물품구매","recommendations":[{"law":"국가를당사자로하는계약에관한법률","type":"법률","reason":"물품 구매 입찰·계약 절차","priority":"필수","key_articles":"제7조"},{"law":"공기업ㆍ준정부기관계약사무규칙","type":"기획재정부령","reason":"공기업 물품구매 계약사무 규정","priority":"필수","key_articles":"제6조"},{"law":"조달사업에관한법률","type":"법률","reason":"조달청 계약·다수공급자계약(MAS)","priority":"권장","key_articles":"제5조, 제5조의2"},{"law":"전자조달의이용및촉진에관한법률","type":"법률","reason":"나라장터 전자입찰 절차","priority":"권장","key_articles":"제5조, 제9조"}]},
    {"keywords":["원전","원자력","핵","방사선","방사능","원자로","핵연료"],"category":"원자력사업","recommendations":[{"law":"원자력안전법","type":"법률","reason":"원자력시설 건설·운영 허가, 안전규제 전반","priority":"필수","key_articles":"제10조, 제20조, 제28조"},{"law":"원자력안전법","type":"시행령","reason":"허가 기준, 검사 절차 상세","priority":"필수","key_articles":"제30조, 제45조"},{"law":"원자력시설등의방호및방사능방재대책법","type":"법률","reason":"원자력시설 물리적방호, 비상대응","priority":"필수","key_articles":"제9조, 제20조"},{"law":"원자력손해배상법","type":"법률","reason":"원자력 사고 시 손해배상 책임","priority":"필수","key_articles":"제3조, 제4조"},{"law":"원자력손해배상보상계약에관한법률","type":"법률","reason":"손해배상 보상계약 체결 의무","priority":"필수","key_articles":"제3조"},{"law":"원전비리방지를위한원자력발전사업자등의관리ㆍ감독에관한법률","type":"법률","reason":"납품비리 방지, 품질관리 의무","priority":"필수","key_articles":"제3조, 제6조"},{"law":"원자력진흥법","type":"법률","reason":"원자력 연구개발, 기술자립 지원","priority":"권장","key_articles":"제3조, 제13조"},{"law":"방사성폐기물관리법","type":"법률","reason":"방사성폐기물 처리·처분 의무","priority":"해당시","key_articles":"제3조, 제9조"}]},
    {"keywords":["발전","전기","전력","송전","변전","배전","전력거래","계통"],"category":"전력사업","recommendations":[{"law":"전기사업법","type":"법률","reason":"발전·송전·배전사업 허가, 전력거래","priority":"필수","key_articles":"제7조"},{"law":"전력기술관리법","type":"법률","reason":"전력기술자, 전력시설물 설계·감리","priority":"필수","key_articles":"제2조"},{"law":"에너지법","type":"법률","reason":"국가에너지기본계획","priority":"권장","key_articles":"제2조, 제4조"}]},
    {"keywords":["입찰","공고","경쟁입찰","제한경쟁","참가자격","입찰자격","PQ","사전심사"],"category":"입찰절차","recommendations":[{"law":"국가를당사자로하는계약에관한법률","type":"법률","reason":"입찰 방법·절차 (제7~10조)","priority":"필수","key_articles":"제7조, 제8조, 제10조, 제27조"},{"law":"국가를당사자로하는계약에관한법률","type":"시행령","reason":"입찰참가자격 제한, 보증금, 적격심사","priority":"필수","key_articles":"제12조, 제13조, 제21조, 제76조"},{"law":"공기업ㆍ준정부기관계약사무규칙","type":"기획재정부령","reason":"공기업 입찰참가자격·사전심사 특례","priority":"필수","key_articles":"제6조, 제7조, 제15조"},{"law":"전자조달의이용및촉진에관한법률","type":"법률","reason":"전자입찰 절차","priority":"권장","key_articles":"제5조, 제9조"}]},
    {"keywords":["수의계약","수의","1인견적","긴급"],"category":"수의계약","recommendations":[{"law":"국가를당사자로하는계약에관한법률","type":"시행령","reason":"수의계약 사유 (시행령 제26조)","priority":"필수","key_articles":"제26조"},{"law":"공기업ㆍ준정부기관계약사무규칙","type":"기획재정부령","reason":"공기업 수의계약 한도·사유","priority":"필수","key_articles":"제7조"}]},
    {"keywords":["계약보증","보증금","이행보증","하자보증","선급금보증"],"category":"보증·보험","recommendations":[{"law":"국가를당사자로하는계약에관한법률","type":"법률","reason":"계약보증금 납부 의무 (제12조)","priority":"필수","key_articles":"제12조"},{"law":"국가를당사자로하는계약에관한법률","type":"시행령","reason":"보증금 비율, 면제 사유","priority":"필수","key_articles":"제50조, 제51조, 제52조"}]},
    {"keywords":["설계변경","물가변동","계약금액조정","에스컬레이션"],"category":"계약금액조정","recommendations":[{"law":"국가를당사자로하는계약에관한법률","type":"시행령","reason":"설계변경·물가변동 계약금액 조정 (제64~66조)","priority":"필수","key_articles":"제64조, 제65조, 제66조"},{"law":"국가를당사자로하는계약에관한법률","type":"시행규칙","reason":"물가변동 산출방법 상세","priority":"필수","key_articles":"제74조"}]},
    {"keywords":["하자","하자보수","하자담보","준공","검사","검수"],"category":"준공·하자","recommendations":[{"law":"국가를당사자로하는계약에관한법률","type":"법률","reason":"준공검사, 하자보수보증금 (제17~18조)","priority":"필수","key_articles":"제14조, 제18조"},{"law":"국가를당사자로하는계약에관한법률","type":"시행령","reason":"하자보수 기간, 보증금 비율","priority":"필수","key_articles":"제55조, 제60조"},{"law":"건설산업기본법","type":"법률","reason":"건설공사 하자담보책임 기간","priority":"해당시","key_articles":"제28조"}]},
    {"keywords":["지체상금","지체","납기지연"],"category":"지체상금","recommendations":[{"law":"국가를당사자로하는계약에관한법률","type":"시행령","reason":"지체상금 비율·산정 (제74조)","priority":"필수","key_articles":"제74조"},{"law":"공기업ㆍ준정부기관계약사무규칙","type":"기획재정부령","reason":"공기업 지체상금 특례","priority":"필수","key_articles":"제16조"}]},
    {"keywords":["하도급","하청","재하도급","수급사업자"],"category":"하도급관리","recommendations":[{"law":"하도급거래공정화에관한법률","type":"법률","reason":"하도급 대금 지급, 부당행위 금지","priority":"필수","key_articles":"제3조, 제13조"},{"law":"하도급거래공정화에관한법률","type":"시행령","reason":"하도급 대금 직접지급 사유","priority":"필수","key_articles":"제9조"},{"law":"건설산업기본법","type":"법률","reason":"건설공사 하도급 제한·통보 의무","priority":"해당시","key_articles":"제29조, 제31조"}]},
    {"keywords":["청렴","부패","비리","뇌물","부정당"],"category":"청렴·부정당","recommendations":[{"law":"국가를당사자로하는계약에관한법률","type":"법률","reason":"청렴계약, 부정당업자 제재 (제27조)","priority":"필수","key_articles":"제27조"},{"law":"원전비리방지를위한원자력발전사업자등의관리ㆍ감독에관한법률","type":"법률","reason":"원전 납품비리 방지 특별법","priority":"필수","key_articles":"제3조, 제6조"},{"law":"공공기관의운영에관한법률","type":"법률","reason":"공공기관 경영공시, 내부통제","priority":"권장","key_articles":"제39조, 제48조"}]},
    {"keywords":["안전","산업재해","재해","사고","중대재해"],"category":"안전관리","recommendations":[{"law":"산업안전보건법","type":"법률","reason":"사업장 안전보건 의무","priority":"필수","key_articles":"제5조, 제63조"},{"law":"산업안전보건기준에관한규칙","type":"법률","reason":"안전보건 기준 상세","priority":"필수","key_articles":"제3조, 제38조"},{"law":"원자력안전법","type":"법률","reason":"원자력시설 안전규제","priority":"해당시","key_articles":"제10조, 제20조"}]},
    {"keywords":["환경","환경영향","대기","수질","폐기물"],"category":"환경","recommendations":[{"law":"환경영향평가법","type":"법률","reason":"환경영향평가 대상·절차","priority":"필수","key_articles":"제2조, 제22조"}]},
    {"keywords":["정보공개","공시","경영평가","감사"],"category":"공공기관 경영","recommendations":[{"law":"공공기관의운영에관한법률","type":"법률","reason":"공공기관 지정, 경영평가","priority":"필수","key_articles":"제39조, 제48조"},{"law":"공공기관의정보공개에관한법률","type":"법률","reason":"정보공개 청구·절차","priority":"필수","key_articles":"제5조, 제9조"}]},
    {"keywords":["독점","공정거래","담합","입찰담합"],"category":"공정거래","recommendations":[{"law":"독점규제및공정거래에관한법률","type":"법률","reason":"입찰담합 금지, 불공정거래행위","priority":"필수","key_articles":"제40조"}]},
    {"keywords":["민법","계약해제","손해배상","채무불이행","위약금"],"category":"민사일반","recommendations":[{"law":"민법","type":"법률","reason":"계약 총칙, 해제·해지, 손해배상","priority":"필수","key_articles":"제390조, 제544조"}]},
    {"keywords":["방폐물","방사성폐기물","해체","원전해체"],"category":"방사성폐기물·해체","recommendations":[{"law":"방사성폐기물관리법","type":"법률","reason":"방사성폐기물 관리·처분 전반","priority":"필수","key_articles":"제3조"},{"law":"원자력안전법","type":"법률","reason":"원자력시설 해체 승인 절차","priority":"필수","key_articles":"제28조"},{"law":"환경영향평가법","type":"법률","reason":"해체 시 환경영향평가","priority":"해당시","key_articles":"제22조, 제42조"}]},
    {"keywords":["단가","단가계약","MAS","다수공급자","수산물","식품","농산물","식자재","급식"],"category":"단가계약·물품조달","recommendations":[{"law":"국가를당사자로하는계약에관한법률","type":"법률","reason":"물품 구매·단가계약 체결 절차 규율","priority":"필수","key_articles":"제7조, 제10조"},{"law":"국가를당사자로하는계약에관한법률","type":"시행령","reason":"단가계약 체결 방법, 이행 기준","priority":"필수","key_articles":"제22조, 제26조"},{"law":"공기업ㆍ준정부기관계약사무규칙","type":"기획재정부령","reason":"공기업 단가계약 특례 규정","priority":"필수","key_articles":"제6조, 제15조"},{"law":"조달사업에관한법률","type":"법률","reason":"조달청 다수공급자계약(MAS), 단가계약 근거","priority":"필수","key_articles":"제5조의2"},{"law":"전자조달의이용및촉진에관한법률","type":"법률","reason":"나라장터 전자입찰·단가계약 절차","priority":"권장","key_articles":"제5조, 제9조"}]},
    {"keywords":["낙찰","적격심사","종합심사","최저가","2단계"],"category":"낙찰·심사","recommendations":[{"law":"국가를당사자로하는계약에관한법률","type":"법률","reason":"낙찰자 결정 방법 (제10조)","priority":"필수","key_articles":"제10조"},{"law":"국가를당사자로하는계약에관한법률","type":"시행령","reason":"적격심사, 종합심사낙찰제 세부 기준","priority":"필수","key_articles":"제42조, 제43조"},{"law":"공기업ㆍ준정부기관계약사무규칙","type":"기획재정부령","reason":"공기업 낙찰자 결정 특례","priority":"필수","key_articles":"제6조, 제15조"}]},
    {"keywords":["대가지급","기성","선급금","대금","준공금"],"category":"대가지급","recommendations":[{"law":"국가를당사자로하는계약에관한법률","type":"법률","reason":"대가 지급 시기·방법 (제15조)","priority":"필수","key_articles":"제15조"},{"law":"국가를당사자로하는계약에관한법률","type":"시행령","reason":"선급금, 기성금 지급 절차","priority":"필수","key_articles":"제55조, 제58조"},{"law":"하도급거래공정화에관한법률","type":"법률","reason":"하도급 대금 직접 지급 의무","priority":"해당시","key_articles":"제13조, 제14조의2"}]},
    {"keywords":["해지","해제","계약종료","계약해제","계약해지","중도해지","파기"],"category":"계약해지·해제","recommendations":[
        {"law":"국가를당사자로하는계약에관한법률","type":"법률","reason":"계약 해제·해지 사유 및 절차","priority":"필수","key_articles":"제27조"},
        {"law":"국가를당사자로하는계약에관한법률","type":"시행령","reason":"계약해제·해지 시 정산 기준","priority":"필수","key_articles":"제76조, 제77조"},
        {"law":"민법","type":"법률","reason":"계약 해제·해지의 일반원칙, 손해배상","priority":"필수","key_articles":"제544조, 제546조, 제551조"},
        {"law":"공기업ㆍ준정부기관계약사무규칙","type":"기획재정부령","reason":"공기업 계약해지 시 특례","priority":"권장","key_articles":"제15조"},
    ]},
    {"keywords":["계약변경","내용변경","기간연장","수량변경","사양변경"],"category":"계약내용변경","recommendations":[
        {"law":"국가를당사자로하는계약에관한법률","type":"시행령","reason":"계약내용 변경 절차·조건","priority":"필수","key_articles":"제64조, 제65조, 제66조"},
        {"law":"국가를당사자로하는계약에관한법률","type":"시행규칙","reason":"물가변동 조정방법 상세","priority":"필수","key_articles":"제74조"},
        {"law":"공기업ㆍ준정부기관계약사무규칙","type":"기획재정부령","reason":"공기업 계약변경 특례","priority":"권장","key_articles":"제15조"},
    ]},
]

# 관련 법령 매핑 (같이 봐야 하는 법령들)
RELATED_LAWS = {
    "국가를당사자로하는계약에관한법률": [
        {"law":"국가를당사자로하는계약에관한법률","type":"시행령","reason":"계약 세부기준·절차"},
        {"law":"국가를당사자로하는계약에관한법률","type":"시행규칙","reason":"서식·산출방법"},
        {"law":"공기업ㆍ준정부기관계약사무규칙","type":"기획재정부령","reason":"한수원 등 공기업 특례"},
    ],
    "건설산업기본법": [
        {"law":"건설산업기본법","type":"시행령","reason":"건설업 등록·하도급 세부기준"},
        {"law":"국가를당사자로하는계약에관한법률","type":"시행령","reason":"공사계약 절차"},
        {"law":"산업안전보건법","type":"법률","reason":"공사현장 안전관리"},
    ],
    "원자력안전법": [
        {"law":"원자력안전법","type":"시행령","reason":"허가·검사 세부절차"},
        {"law":"원자력시설등의방호및방사능방재대책법","type":"법률","reason":"물리적 방호·비상대응"},
        {"law":"원전비리방지를위한원자력발전사업자등의관리ㆍ감독에관한법률","type":"법률","reason":"납품비리 방지"},
    ],
    "하도급거래공정화에관한법률": [
        {"law":"하도급거래공정화에관한법률","type":"시행령","reason":"하도급 대금지급 세부"},
        {"law":"건설산업기본법","type":"법률","reason":"건설 하도급 제한"},
    ],
    "조달사업에관한법률": [
        {"law":"전자조달의이용및촉진에관한법률","type":"법률","reason":"나라장터 전자입찰"},
        {"law":"국가를당사자로하는계약에관한법률","type":"법률","reason":"계약 일반원칙"},
    ],
    "공기업ㆍ준정부기관계약사무규칙": [
        {"law":"국가를당사자로하는계약에관한법률","type":"법률","reason":"계약 근거 법률"},
        {"law":"국가를당사자로하는계약에관한법률","type":"시행령","reason":"계약 세부기준"},
        {"law":"공공기관의운영에관한법률","type":"법률","reason":"공공기관 운영 근거"},
    ],
}

# ===== 법률-시행령 핵심 차이 매핑 =====
LAW_DECREE_DIFF = {
    "국가를당사자로하는계약에관한법률": [
        {"law_article":"제7조 (계약의 방법)","decree_article":"제12~26조","summary":"법률은 '경쟁입찰 원칙'만 규정. 시행령에서 제한경쟁·지명경쟁·수의계약의 구체적 사유와 절차를 규정"},
        {"law_article":"제10조 (낙찰자 결정)","decree_article":"제42~43조","summary":"법률은 '낙찰 기준' 위임. 시행령에서 적격심사·종합심사·협상계약의 세부 기준과 절차를 규정"},
        {"law_article":"제12조 (보증금)","decree_article":"제50~54조","summary":"법률은 '보증금 납부 의무' 규정. 시행령에서 비율(10~15%)·면제 사유·귀속 절차를 상세 규정"},
        {"law_article":"제14조 (검사·인수)","decree_article":"제55~57조","summary":"법률은 '검사 의무' 규정. 시행령에서 검사 기한(14일)·자동합격·부분검사 기준을 규정"},
        {"law_article":"제15조 (대가지급)","decree_article":"제58~59조","summary":"법률은 '적기 지급 의무' 규정. 시행령에서 선급금(70%)·기성금·지급기한(14일) 세부 규정"},
        {"law_article":"제27조 (부정당업자)","decree_article":"제76~76조의2","summary":"법률은 '제재 근거' 규정. 시행령에서 제재 사유별 기간(6월~2년)·감경 사유·과징금 기준을 규정"},
    ],
}

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
    except Exception:
        return None

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

SPECIAL_CLAUSES = {
    "공사": [
        {"title": "안전관리 특약", "text": "수급인은 산업안전보건법 제63조에 따라 안전관리계획을 수립하고, 안전관리비를 건설기술진흥법 시행규칙 별표 기준에 따라 사용하여야 한다. 안전사고 발생 시 수급인은 즉시 발주자에게 통보하여야 한다.", "law": "산업안전보건법 제63조"},
        {"title": "하도급 제한 특약", "text": "수급인은 계약 물량의 일부를 하도급하고자 할 때에는 사전에 발주자의 서면 승인을 받아야 한다. 승인 없는 하도급 적발 시 계약을 해제할 수 있다.", "law": "건설산업기본법 제29조"},
        {"title": "설계변경 특약", "text": "현장 여건 변경으로 인한 설계변경은 발주자의 사전 서면 승인을 받은 후 시행하여야 하며, 승인 없이 시행한 부분에 대해서는 대가를 지급하지 아니한다.", "law": "시행령 제65조"},
        {"title": "환경관리 특약", "text": "수급인은 공사 중 발생하는 분진·소음·폐기물에 대하여 관련 법령을 준수하고, 환경오염 발생 시 즉시 조치 후 발주자에게 보고하여야 한다.", "law": "환경영향평가법"},
    ],
    "물품": [
        {"title": "품질보증 특약", "text": "공급자는 납품 물품이 계약 규격 및 품질기준에 적합함을 보증하며, 부적합 판정 시 무상 교체 또는 환불한다. 품질보증기간은 납품일로부터 1년으로 한다.", "law": "국가계약법 제14조"},
        {"title": "납품지연 특약", "text": "공급자는 약정 납품기한 내에 물품을 인도하여야 하며, 납품이 지연될 경우 지체상금 외에 발주자의 긴급 조달비용을 별도 부담한다.", "law": "시행령 제74조"},
        {"title": "지식재산권 특약", "text": "납품 물품에 제3자의 특허권·실용신안권·디자인권 등 지식재산권 침해 문제가 발생한 경우 공급자가 전적으로 책임진다.", "law": ""},
    ],
    "용역": [
        {"title": "성과물 저작권 특약", "text": "용역 수행 결과물의 저작권 및 지식재산권은 발주자에게 귀속되며, 수급인은 발주자의 사전 동의 없이 제3자에게 제공하거나 다른 용도로 사용할 수 없다.", "law": "저작권법 제45조"},
        {"title": "비밀유지 특약", "text": "수급인은 용역 수행 과정에서 취득한 발주자의 업무상 비밀을 계약 종료 후에도 제3자에게 누설하여서는 아니 된다. 위반 시 손해배상 책임을 진다.", "law": ""},
        {"title": "인력교체 제한 특약", "text": "수급인은 투입 인력을 발주자의 사전 승인 없이 교체할 수 없으며, 핵심인력 교체 시 동등 이상의 경력자로 대체하여야 한다.", "law": ""},
        {"title": "하자담보 특약", "text": "용역 성과물에 하자가 발견된 경우 수급인은 하자 통보일로부터 30일 이내에 무상으로 보수하여야 한다. 하자담보기간은 검수일로부터 1년으로 한다.", "law": "시행령 제60조"},
    ],
    "원전": [
        {"title": "품질보증(QA) 특약", "text": "공급자는 원자력안전법 제10조 및 관련 기술기준에 따른 품질보증계획을 수립·이행하여야 하며, 발주자의 품질감사에 응하여야 한다.", "law": "원자력안전법 제10조"},
        {"title": "원전비리방지 특약", "text": "공급자는 원전비리방지법에 따른 관리·감독 의무를 준수하여야 하며, 시험성적서·인증서 등 서류의 위조·변조 시 계약을 즉시 해제하고 입찰참가자격을 제한한다.", "law": "원전비리방지법 제3조"},
    ],
    "단가": [
        {"title": "가격조정 특약", "text": "계약 기간 중 시장가격이 10% 이상 변동된 경우 쌍방 합의하여 단가를 조정할 수 있다. 조정 시 시장조사가격 또는 물가변동지수를 근거로 한다.", "law": "시행령 제64조"},
        {"title": "최소·최대 발주량 특약", "text": "발주자는 계약기간 내 최소 발주량을 보장하지 아니하며, 최대 발주량은 예산 범위 내로 한다.", "law": ""},
    ],
    "수의계약": [
        {"title": "수의계약 사유 명시 특약", "text": "본 계약은 국가계약법 시행령 제26조 제1항 제_호의 사유에 해당하여 수의계약으로 체결하며, 해당 사유가 소멸되는 경우 경쟁입찰로 전환한다.", "law": "시행령 제26조"},
    ],
}

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
    "해지": [
        {"step":"해지사유 발생","desc":"채무불이행·부정행위 등","law":"시행령 제76조"},
        {"step":"시정요구","desc":"상당 기간 정하여 이행 최고","law":"민법 제544조"},
        {"step":"해지 통보","desc":"서면 통보 (내용증명)","law":""},
        {"step":"기성정산","desc":"이행 완료 부분 검사·정산","law":"시행령 제77조"},
        {"step":"보증금 처리","desc":"계약보증금 귀속 여부","law":"국가계약법 제12조"},
        {"step":"후속조치","desc":"손해배상·부정당 제재","law":"국가계약법 제27조"},
    ],
}

def get_method_comparison(query):
    """계약방식 비교표 생성"""
    q = query.lower()
    is_construction = any(kw in q for kw in ["공사","건설","시공","토목"])
    is_service = any(kw in q for kw in ["용역","설계","컨설팅","SW","IT"])

    if is_construction:
        return {
            "type": "공사",
            "methods": [
                {"name":"일반경쟁","condition":"추정가격 5천만원 이상","pros":"공정성·투명성 확보","cons":"절차 복잡, 최저가 위주","duration":"공고 7일+심사 10일","law":"국가계약법 제7조"},
                {"name":"제한경쟁","condition":"특수 기술·실적 필요 시","pros":"적격 업체만 참가","cons":"경쟁 제한 사유 소명 필요","duration":"공고 5일+심사 10일","law":"시행령 제21조"},
                {"name":"지명경쟁","condition":"추정가격 1억 미만+특수","pros":"신속 계약 가능","cons":"매우 제한적 사유만 허용","duration":"통보 5일","law":"시행령 제23조"},
                {"name":"수의계약","condition":"추정가격 5천만원 미만","pros":"절차 간소, 신속","cons":"감사 지적 위험","duration":"견적 3~5일","law":"시행령 제26조"},
            ]
        }
    elif is_service:
        return {
            "type": "용역",
            "methods": [
                {"name":"일반경쟁","condition":"추정가격 5천만원 이상","pros":"공정성 확보","cons":"가격 위주 평가","duration":"공고 7일+심사 10일","law":"국가계약법 제7조"},
                {"name":"협상에 의한 계약","condition":"추정가격 2억 이상 기술용역","pros":"기술능력 중심 평가","cons":"제안서 평가 시간 소요","duration":"공고 10일+평가 14일","law":"시행령 제43조"},
                {"name":"제한경쟁","condition":"특수 기술·자격 필요","pros":"전문업체 확보","cons":"경쟁 제한 사유 필요","duration":"공고 5일+심사 10일","law":"시행령 제21조"},
                {"name":"수의계약","condition":"추정가격 5천만원 미만","pros":"절차 간소","cons":"감사 지적 위험","duration":"견적 3~5일","law":"시행령 제26조"},
            ]
        }
    else:  # 물품
        return {
            "type": "물품",
            "methods": [
                {"name":"일반경쟁","condition":"추정가격 5천만원 이상","pros":"가격 경쟁으로 절감","cons":"최저가 품질 위험","duration":"공고 7일+개찰 3일","law":"국가계약법 제7조"},
                {"name":"MAS(다수공급자)","condition":"규격 표준화 물품","pros":"즉시 구매 가능","cons":"가격 경쟁 제한","duration":"즉시~3일","law":"조달사업법 제5조의2"},
                {"name":"제3자 단가계약","condition":"반복 구매 물품","pros":"안정적 공급","cons":"단가 변동 리스크","duration":"단가계약 후 즉시","law":"시행령 제22조"},
                {"name":"수의계약","condition":"추정가격 2천만원 미만","pros":"신속 구매","cons":"감사 지적 위험","duration":"견적 1~3일","law":"시행령 제26조"},
            ]
        }

def get_required_docs(query, amount=None):
    """계약 유형·금액별 필수 서류 안내"""
    q = query.lower()
    docs = []

    # 공통 서류
    common = [
        {"name":"사업자등록증 사본","when":"모든 계약","required":True},
        {"name":"인감증명서","when":"모든 계약","required":True},
        {"name":"사용인감계","when":"대리인 계약 시","required":False},
    ]
    docs.extend(common)

    # 입찰 관련
    if any(kw in q for kw in ["입찰","공고","경쟁","참가자격","PQ"]):
        docs.extend([
            {"name":"입찰참가신청서","when":"경쟁입찰","required":True},
            {"name":"입찰보증금 납부 또는 보증서","when":"입찰금액의 5% 이상","required":True},
            {"name":"실적증명서","when":"제한경쟁·PQ","required":False},
            {"name":"기술능력 평가서류","when":"협상에 의한 계약","required":False},
            {"name":"청렴서약서","when":"모든 입찰","required":True},
        ])

    # 계약 체결
    if any(kw in q for kw in ["계약","체결","단가","수의","공사","용역","구매","물품"]):
        docs.extend([
            {"name":"계약보증금 납부 또는 보증서","when":"계약금액의 10~15%","required":True},
            {"name":"착공신고서 (공사)","when":"공사 계약","required":any(kw in q for kw in ["공사","건설","시공"])},
            {"name":"안전관리계획서 (공사)","when":"공사금액 1억 이상","required":any(kw in q for kw in ["공사","건설","시공"])},
            {"name":"산재보험 가입증명","when":"공사·용역","required":False},
        ])

    # 금액별 추가
    if amount:
        if amount >= 200000000:  # 2억 이상
            docs.append({"name":"계약심사위원회 심의조서","when":"추정가격 2억원 이상","required":True})
        if amount >= 100000000:  # 1억 이상
            docs.append({"name":"계약보증보험증권","when":"계약금액 1억원 이상","required":True})
        if amount >= 50000000:  # 5천만원 이상
            docs.append({"name":"예정가격 조서","when":"추정가격 5천만원 이상","required":True})
        if amount < 50000000:
            docs.append({"name":"견적서 (2인 이상)","when":"수의계약","required":True})

    # 선급금
    if any(kw in q for kw in ["선급","대가","기성"]):
        docs.extend([
            {"name":"선급금보증서","when":"선급금 지급 시","required":True},
            {"name":"기성검사조서","when":"기성금 지급 시","required":True},
        ])

    # 준공
    if any(kw in q for kw in ["준공","검수","검사","하자"]):
        docs.extend([
            {"name":"준공검사조서","when":"계약 완료 시","required":True},
            {"name":"하자보수보증금 납부 또는 보증서","when":"준공 시","required":True},
            {"name":"성과품 인수인계서","when":"용역 완료 시","required":any(kw in q for kw in ["용역","설계"])},
        ])

    # 원전
    if any(kw in q for kw in ["원전","원자력","핵"]):
        docs.extend([
            {"name":"품질보증계획서 (QA Plan)","when":"안전등급 기기","required":True},
            {"name":"시험성적서 (원본)","when":"원전 납품 물품","required":True},
            {"name":"원전비리방지 준수 서약서","when":"원전 관련 모든 계약","required":True},
        ])

    # 수의계약
    if any(kw in q for kw in ["수의계약","수의","긴급"]):
        docs.extend([
            {"name":"수의계약 사유서","when":"수의계약 체결 시","required":True},
            {"name":"긴급성 입증 자료","when":"긴급 수의계약","required":any(kw in q for kw in ["긴급"])},
        ])

    # 중복 제거
    seen = set()
    unique = []
    for d in docs:
        if d["name"] not in seen:
            seen.add(d["name"])
            unique.append(d)

    return unique

AUDIT_CASES = [
    {"keywords":["수의계약","수의"],"title":"수의계약 사유 부적합","desc":"추정가격 초과 또는 시행령 제26조 사유 미해당 상태에서 수의계약 체결","impact":"계약 무효·담당자 징계","prevention":"수의계약 사유서 사전 작성, 법무 검토 필수"},
    {"keywords":["수의계약","수의","견적"],"title":"견적서 미징수","desc":"2인 이상 견적서 징수 의무 미이행 (1인 견적으로 수의계약)","impact":"부당 특혜 의혹, 감사 지적","prevention":"반드시 2인 이상 견적서 징수, 견적 비교표 작성"},
    {"keywords":["입찰","공고","참가자격"],"title":"입찰참가자격 제한 부적정","desc":"합리적 사유 없이 특정 업체에 유리한 자격 제한 설정","impact":"입찰 취소·재입찰, 담당자 문책","prevention":"자격 제한 사유 명확화, 유사 발주 사례 참조"},
    {"keywords":["예정가격","가격"],"title":"예정가격 작성 부실","desc":"시장가격 조사 미흡으로 예정가격 과다 또는 과소 책정","impact":"예산 낭비 또는 유찰, 감사 지적","prevention":"3건 이상 거래실례가격 조사, 원가계산 근거 확보"},
    {"keywords":["보증금","계약보증","면제"],"title":"보증금 면제 사유 불인정","desc":"시행령 제37조·제50조 면제 사유에 해당하지 않는데 보증금 면제","impact":"채권 미확보, 손실 발생 시 배상 책임","prevention":"면제 사유 근거 서류 반드시 보관, 법무 확인"},
    {"keywords":["공사","건설","설계변경"],"title":"설계변경 미승인 시공","desc":"발주자 승인 없이 설계변경 시행 후 사후 정산 요구","impact":"추가 대가 불인정, 분쟁 발생","prevention":"반드시 사전 서면 승인, 변경 도면·내역 첨부"},
    {"keywords":["지체상금","지체","납기"],"title":"지체상금 미부과","desc":"납품·준공 지연에도 지체상금을 부과하지 않거나 감면","impact":"국가 재정 손실, 담당자 변상 책임","prevention":"지체일수 자동 산정 시스템 확인, 면제 사유 서면 확보"},
    {"keywords":["하도급","하청"],"title":"하도급대금 지연지급","desc":"원도급자에게 대금 지급 후 하도급대금 60일 초과 미지급","impact":"과징금 부과, 입찰참가자격 제한","prevention":"하도급대금 지급 확인서 징구, 직접지급 사유 모니터링"},
    {"keywords":["부정당","비리","담합"],"title":"담합 미적발","desc":"입찰 참가업체 간 담합 징후가 있었으나 발주자가 인지 못함","impact":"계약 무효, 과징금, 담당자 문책","prevention":"낙찰률·투찰패턴 분석, 공정위 협조 체계 구축"},
    {"keywords":["납품","검수","검사"],"title":"검수 부실","desc":"납품 물품의 규격·수량·품질 검사를 형식적으로 수행","impact":"부적합 물품 수령, 사고 위험, 배상 책임","prevention":"검수 체크리스트 활용, 전문검사관 참여"},
    {"keywords":["원전","원자력","QA"],"title":"품질보증 서류 미비","desc":"원전 납품 물품의 QA 서류(시험성적서 등) 확인 소홀","impact":"원전비리방지법 위반, 최대 2년 입찰제한","prevention":"QA 등급 확인 → 시험성적서 원본 대조 → 품질검사 입회"},
]

ROLE_MAP = [
    {"stage":"수요확인·사양서","roles":[
        {"dept":"수요부서","action":"소요량·사양서 확정, 기술규격서 작성","note":""},
        {"dept":"계약부서","action":"예산 확인, 계약 방식 사전 협의","note":""},
    ]},
    {"stage":"예정가격·원가","roles":[
        {"dept":"계약부서","action":"예정가격 작성, 원가계산 또는 거래실례 조사","note":"비밀유지 철저"},
        {"dept":"재무부서","action":"예산 배정 확인","note":""},
    ]},
    {"stage":"입찰·공고","roles":[
        {"dept":"계약부서","action":"입찰공고문 작성·게시, 질의응답 처리","note":"공고기간 7일 이상"},
        {"dept":"법무팀","action":"입찰조건·계약조건 법률 검토","note":"2억 이상 권장"},
    ]},
    {"stage":"심사·낙찰","roles":[
        {"dept":"계약부서","action":"개찰, 적격심사·종합심사 진행","note":""},
        {"dept":"기술부서","action":"기술평가, 제안서 심사 참여","note":"협상계약 시"},
        {"dept":"계약심사위원회","action":"계약심사 의결","note":"2억 이상"},
    ]},
    {"stage":"계약체결","roles":[
        {"dept":"계약부서","action":"계약서 작성, 보증금 징구, 계약 체결","note":""},
        {"dept":"법무팀","action":"계약서 조항 검토, 특약 사항 확인","note":"고액·특수 계약"},
        {"dept":"수요부서","action":"계약 내용 최종 확인","note":""},
    ]},
    {"stage":"이행·관리","roles":[
        {"dept":"수요부서","action":"계약 이행 감독, 기성검사","note":""},
        {"dept":"계약부서","action":"대가 지급, 선급금 관리, 계약변경 처리","note":""},
        {"dept":"안전환경팀","action":"현장 안전 점검","note":"공사 계약"},
        {"dept":"품질부서","action":"품질검사, QA 확인","note":"원전 관련"},
    ]},
    {"stage":"준공·검수","roles":[
        {"dept":"수요부서","action":"준공검사·물품 검수 실시","note":""},
        {"dept":"계약부서","action":"하자보수보증금 징구, 최종 대가 지급","note":""},
        {"dept":"감사팀","action":"계약 이행 적정성 사후 검토","note":"고액 계약"},
    ]},
]

LAW_SUMMARIES = {
    "국가를당사자로하는계약에관한법률": {"short":"국가기관 계약의 기본법", "scope":"입찰·계약·이행·검사·대가지급", "key":"경쟁입찰 원칙, 예외적 수의계약"},
    "공기업ㆍ준정부기관계약사무규칙": {"short":"한수원 등 공기업 계약 특례", "scope":"입찰·계약·보증금·부정당업자", "key":"국가계약법의 공기업 적용 특례"},
    "건설산업기본법": {"short":"건설업 등록·하도급·하자담보", "scope":"건설업 등록, 도급 한도, 하자보수", "key":"건설 하도급 제한, 하자담보책임기간"},
    "하도급거래공정화에관한법률": {"short":"하도급 대금 지급·공정거래", "scope":"하도급대금, 기술유용 금지", "key":"60일 이내 지급 의무, 직접지급"},
    "원자력안전법": {"short":"원자력시설 안전규제", "scope":"허가·검사·안전관리·방사선", "key":"시설 건설운영 허가, 품질보증(QA)"},
    "원전비리방지를위한원자력발전사업자등의관리ㆍ감독에관한법률": {"short":"원전 납품비리 방지", "scope":"품질관리, 시험성적서, 가중제재", "key":"허위성적서 형사처벌, 2년 입찰제한"},
    "조달사업에관한법률": {"short":"조달청 계약·MAS", "scope":"다수공급자계약, 우수조달물품", "key":"나라장터, MAS 단가계약"},
    "전자조달의이용및촉진에관한법률": {"short":"나라장터 전자입찰", "scope":"전자입찰, 전자계약", "key":"나라장터 의무 사용"},
    "산업안전보건법": {"short":"사업장 안전보건 의무", "scope":"안전관리, 중대재해, 보건관리", "key":"안전관리계획 수립, 안전보건비"},
    "민법": {"short":"계약 일반원칙", "scope":"계약 총칙, 해제·해지, 손해배상", "key":"채무불이행, 계약해제 요건"},
    "독점규제및공정거래에관한법률": {"short":"독점·담합 규제", "scope":"입찰담합, 불공정행위", "key":"담합 과징금, 공정위 신고"},
    "공공기관의운영에관한법률": {"short":"공공기관 운영·경영", "scope":"경영평가, 정보공개, 감사", "key":"경영공시 의무, 감사 근거"},
    "환경영향평가법": {"short":"환경영향평가", "scope":"환경영향평가 대상·절차", "key":"일정 규모 이상 사업"},
    "방사성폐기물관리법": {"short":"방사성폐기물 관리", "scope":"방폐물 처리·처분", "key":"처분시설 건설·운영"},
    "전기사업법": {"short":"전기사업 허가·전력거래", "scope":"발전·송전·배전사업", "key":"전력거래, 계통연계"},
    "전력기술관리법": {"short":"전력기술 관리", "scope":"전력기술자, 설계·감리", "key":"전력시설물 관리"},
    "에너지법": {"short":"에너지 정책", "scope":"국가에너지기본계획", "key":"에너지 전환 정책"},
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

    # ── 1.5. 실무 Q&A 매칭 ──
    qa_matches = []
    for qa in PRACTICAL_QA:
        if any(kw in q for kw in qa["keywords"]):
            qa_matches.append(qa)
    ref["qa"] = qa_matches[:5]

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
        {"keywords":["해지","해제","계약종료","파기"],"title":"계약 해지·해제 절차","desc":"계약상대자의 채무불이행, 부정행위 등으로 계약을 해지·해제할 수 있습니다. 해지 시 기성부분 정산, 보증금 귀속, 손해배상 청구 순서로 진행합니다.","laws":["국가를당사자로하는계약에관한법률 시행령 제76조","민법 제544조"],"checklist":["해지·해제 사유 해당 여부 확인","계약상대자 통보 (서면)","기성부분 검사·정산","계약보증금 귀속 여부 결정","손해배상 청구 검토","부정당업자 제재 검토"]},
        {"keywords":["계약변경","기간연장","수량변경","사양변경"],"title":"계약내용 변경 절차","desc":"설계변경, 물가변동, 수량 증감 등으로 계약내용을 변경할 수 있습니다. 계약금액 조정은 시행령 제64~66조에 따릅니다.","laws":["국가를당사자로하는계약에관한법률 시행령 제64조","국가를당사자로하는계약에관한법률 시행령 제65조"],"checklist":["변경 사유 발생 확인","설계변경 승인 (발주자)","변경 계약금액 산출","계약변경 합의서 체결","변경보증금 조정"]},
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

    # ── 4. 계약일정 자동 타임라인 ──
    if ref.get("process") and ref.get("contract_method"):
        timeline = []
        day = 0
        STEP_DAYS = {
            "수요확인": 5, "수요조사": 5, "수요예측": 5,
            "설계·사양 확정": 15, "과업지시서 작성": 10,
            "예정가격 작성": 7, "단가 산정": 7,
            "입찰공고": 7, "입찰·제안서 평가": 14, "입찰·단가결정": 10,
            "입찰참가등록": 7, "적격심사": 10,
            "개찰·낙찰": 3, "협상·계약": 10,
            "계약체결": 5, "단가계약 체결": 5,
            "착공·시공": 90, "이행": 30, "착수·수행": 60,
            "납품": 14, "납품요청": 3,
            "기성검사": 7, "중간성과 검토": 5,
            "검수": 5, "검수·대가지급": 7, "검수·준공": 7, "최종성과 납품": 5,
            "준공검사": 10, "대가지급": 14,
            "하자담보": 365,
            "수의계약 사유 확인": 3, "견적서 징수": 5, "예정가격 결정": 3,
            "계약심사": 5, "이행·검수": 14,
            "해지사유 발생": 0, "시정요구": 14, "해지 통보": 3,
            "기성정산": 14, "보증금 처리": 7, "후속조치": 30,
        }
        for step in ref["process"]:
            days = STEP_DAYS.get(step["step"], 7)
            timeline.append({**step, "start_day": day, "duration": days})
            day += days
        ref["timeline"] = {"steps": timeline, "total_days": day}

    # ── 5. 계약 리스크 체커 ──
    RISK_DB = [
        {"keywords":["공사","건설","시공"],"risks":[
            {"level":"high","title":"안전사고 리스크","desc":"공사현장 사망사고 시 중대재해처벌법 적용. 발주자도 안전관리의무 위반 시 형사처벌 가능.","law":"산업안전보건법 제63조"},
            {"level":"high","title":"하도급 대금 미지급","desc":"하도급대금 60일 이내 미지급 시 과징금 부과. 직접지급 사유 발생 시 원도급자 부담.","law":"하도급법 제13조"},
            {"level":"medium","title":"설계변경 분쟁","desc":"설계변경 범위·금액 산정 시 발주자-시공자 간 분쟁 빈발. 변경 전 서면 승인 필수.","law":"시행령 제65조"},
            {"level":"low","title":"물가변동 조정 누락","desc":"입찰일 기준 90일 경과 + 3% 등락 요건 확인 누락 시 계약금액 조정 기회 상실.","law":"시행령 제64조"},
        ]},
        {"keywords":["물품","구매","납품","자재","기자재","수산물","식품"],"risks":[
            {"level":"high","title":"납품 부적격 리스크","desc":"규격·품질 미달 납품 시 계약해제 사유. 원전 관련 물품은 원전비리방지법 적용.","law":"국가계약법 제27조"},
            {"level":"medium","title":"검수 지연","desc":"납품 후 14일 이내 검사 미완료 시 자동 검사 합격 간주 가능. 검수체계 사전 수립 필요.","law":"시행령 제55조"},
            {"level":"low","title":"단가 변동","desc":"단가계약 기간 중 시장가격 급등락 시 계약 조정 협의 필요.","law":"시행령 제22조"},
        ]},
        {"keywords":["용역","설계","컨설팅","SW","IT","엔지니어링"],"risks":[
            {"level":"high","title":"성과물 저작권 분쟁","desc":"용역 결과물의 저작권 귀속을 계약서에 명확히 규정하지 않으면 분쟁 발생.","law":"저작권법 제2조"},
            {"level":"medium","title":"과업범위 변경","desc":"추가 과업 요구 시 계약변경 없이 수행하면 추가비용 청구 불가.","law":"시행령 제65조"},
            {"level":"low","title":"기성금 정산 오류","desc":"투입인력·기간 기준 기성금 산정 시 실투입 확인 절차 미비로 과다지급 위험.","law":"시행령 제55조"},
        ]},
        {"keywords":["입찰","공고","경쟁","참가자격"],"risks":[
            {"level":"high","title":"입찰담합","desc":"2인 이상 업체 간 담합 적발 시 입찰참가자격 2년 제한 + 과징금.","law":"독점규제법 제40조"},
            {"level":"medium","title":"참가자격 하자","desc":"입찰참가자격 미충족 업체의 낙찰 시 계약 무효 가능. PQ 검증 철저히.","law":"시행령 제12조"},
            {"level":"low","title":"예정가격 유출","desc":"예정가격 사전 유출 시 입찰 무효 + 관련자 형사처벌.","law":"국가계약법 제27조"},
        ]},
        {"keywords":["수의계약","수의","긴급"],"risks":[
            {"level":"high","title":"수의계약 사유 부적합","desc":"수의계약 사유 미해당 시 감사 지적. 긴급성 입증 자료 사전 확보 필수.","law":"시행령 제26조"},
            {"level":"medium","title":"특혜 시비","desc":"특정 업체 반복 수의계약 시 특혜 의혹. 견적서 2인 이상 징수 + 업체 교차 선정.","law":"공기업규칙 제7조"},
        ]},
        {"keywords":["원전","원자력","핵","방사선"],"risks":[
            {"level":"high","title":"품질보증(QA) 부적합","desc":"안전등급 기기의 QA 미이행 시 원전비리방지법 적용. 최대 2년 입찰제한.","law":"원전비리방지법 제6조"},
            {"level":"high","title":"허위 시험성적서","desc":"시험성적서 위조 시 형사처벌 + 영구 입찰제한 가능.","law":"원전비리방지법 제3조"},
            {"level":"medium","title":"방사선 안전","desc":"방사선 작업 관련 계약 시 방사선 종사자 피폭관리 의무.","law":"원자력안전법 제91조"},
        ]},
        {"keywords":["보증금","이행보증","하자보증"],"risks":[
            {"level":"medium","title":"보증서 유효기간 만료","desc":"보증보험증권 유효기간이 계약기간보다 짧으면 보증 공백 발생. 연장 확인 필수.","law":"시행령 제50조"},
            {"level":"low","title":"보증금 면제 오남용","desc":"면제 사유 미해당 시 감사 지적. 면제 사유 근거 서류 반드시 보관.","law":"시행령 제37조"},
        ]},
        {"keywords":["해지","해제","계약종료"],"risks":[
            {"level":"high","title":"부당 해지","desc":"해지 사유 미충족 시 손해배상 청구 당할 수 있음. 법무 검토 필수.","law":"민법 제544조"},
            {"level":"medium","title":"기성정산 분쟁","desc":"해지 시점의 이행 완료 부분 산정에서 발주자-시공자 간 이견 빈발.","law":"시행령 제77조"},
        ]},
    ]

    risks = []
    for r in RISK_DB:
        if any(kw in q for kw in r["keywords"]):
            risks.extend(r["risks"])
    # 중복 제거 + 레벨 정렬
    seen_titles = set()
    unique_risks = []
    for r in risks:
        if r["title"] not in seen_titles:
            seen_titles.add(r["title"])
            unique_risks.append(r)
    level_order = {"high":0, "medium":1, "low":2}
    unique_risks.sort(key=lambda x: level_order.get(x["level"], 9))
    ref["risks"] = unique_risks[:8]

    # ── 6. 계약서 특약 조항 ──
    clauses = []
    for key, items in SPECIAL_CLAUSES.items():
        if key in q:
            clauses.extend(items)
    if not clauses:
        for key in ["계약","물품","납품","구매"]:
            if key in q:
                clauses.extend(SPECIAL_CLAUSES.get("물품", []))
                break
    ref["special_clauses"] = clauses[:6]

    # ── 계약방식 비교표 ──
    ref["method_comparison"] = get_method_comparison(query)

    # ── 필수 제출 서류 ──
    ref["required_docs"] = get_required_docs(query, ref.get("contract_method", {}).get("amount"))

    # ── 감사 지적 사례 ──
    audit = []
    for ac in AUDIT_CASES:
        if any(kw in q for kw in ac["keywords"]):
            audit.append(ac)
    ref["audit_cases"] = audit[:5]

    # ── 단계별 담당 부서·역할 ──
    ref["role_map"] = ROLE_MAP

    # ── 계약 서식 템플릿 매칭 ──
    templates = []
    for t in CONTRACT_TEMPLATES:
        if t["type"].lower() in q or any(kw in q for kw in t["type"].split("·")):
            templates.append(t)
    if not templates:
        templates = [CONTRACT_TEMPLATES[1]]  # 기본: 물품 계약서
    ref["templates"] = templates[:3]

    # ── 위험도 점수 계산 ──
    risk_score = 0
    risk_factors = []

    # 리스크 기반 (최대 40점)
    high_risks = len([r for r in ref.get("risks",[]) if r["level"]=="high"])
    med_risks = len([r for r in ref.get("risks",[]) if r["level"]=="medium"])
    risk_score += min(40, high_risks * 15 + med_risks * 5)
    if high_risks: risk_factors.append(f"고위험 항목 {high_risks}건")

    # 감사 지적 기반 (최대 20점)
    audit_count = len(ref.get("audit_cases",[]))
    risk_score += min(20, audit_count * 8)
    if audit_count: risk_factors.append(f"감사 지적 유의 {audit_count}건")

    # 금액 기반 (최대 20점)
    amt = ref.get("contract_method",{}).get("amount",0) or 0
    if amt >= 1000000000: risk_score += 20; risk_factors.append("10억 이상 고액 계약")
    elif amt >= 300000000: risk_score += 15; risk_factors.append("3억 이상 계약")
    elif amt >= 100000000: risk_score += 10; risk_factors.append("1억 이상 계약")

    # 원전 관련 (최대 20점)
    if any(kw in q for kw in ["원전","원자력","핵","방사선"]):
        risk_score += 20; risk_factors.append("원자력 관련 계약 (QA/비리방지법)")

    risk_score = min(100, risk_score)
    grade = "안전" if risk_score < 30 else "주의" if risk_score < 60 else "위험"
    ref["risk_score"] = {"score": risk_score, "grade": grade, "factors": risk_factors}

    # ── 9. 주요 법령 요약 카드 ──
    law_cards = []
    for r in recommendations[:6]:
        name = r.get("law","")
        if name in LAW_SUMMARIES:
            s = LAW_SUMMARIES[name]
            law_cards.append({"law":name, "type":r.get("type",""), "short":s["short"], "scope":s["scope"], "key":s["key"], "priority":r.get("priority","")})
    ref["law_cards"] = law_cards

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
    except Exception:
        return []

# ===== Glossary =====
CONTRACT_CLAUSES = [
    {"clause":"계약보증금","desc":"계약금액의 10% 이상 납부","laws":[{"law":"국가를당사자로하는계약에관한법률","type":"법률","article":"제12조"},{"law":"국가를당사자로하는계약에관한법률","type":"시행령","article":"제50조"}]},
    {"clause":"지체상금","desc":"이행지체 시 계약금액의 일정률 부과","laws":[{"law":"국가를당사자로하는계약에관한법률","type":"시행령","article":"제74조"}]},
    {"clause":"하자보수보증금","desc":"준공 후 하자보수 담보 (2~5%)","laws":[{"law":"국가를당사자로하는계약에관한법률","type":"시행령","article":"제62조"}]},
    {"clause":"선급금","desc":"계약금액의 70% 이내 선급 가능","laws":[{"law":"국가를당사자로하는계약에관한법률","type":"시행령","article":"제58조"}]},
    {"clause":"물가변동 조정","desc":"입찰일 기준 90일 경과 + 3% 이상 등락 시","laws":[{"law":"국가를당사자로하는계약에관한법률","type":"시행령","article":"제64조"},{"law":"국가를당사자로하는계약에관한법률","type":"시행령","article":"제65조"}]},
    {"clause":"설계변경","desc":"발주자 요청 또는 현장여건 변경 시","laws":[{"law":"국가를당사자로하는계약에관한법률","type":"시행령","article":"제65조"}]},
    {"clause":"계약해제·해지","desc":"채무불이행·부정행위 시 계약 종료","laws":[{"law":"국가를당사자로하는계약에관한법률","type":"시행령","article":"제76조"},{"law":"민법","type":"법률","article":"제544조"}]},
    {"clause":"대가지급","desc":"검사완료 후 14일 이내 대금 지급","laws":[{"law":"국가를당사자로하는계약에관한법률","type":"법률","article":"제15조"},{"law":"국가를당사자로하는계약에관한법률","type":"시행령","article":"제55조"}]},
    {"clause":"하도급 관리","desc":"하도급대금 지급·통보 의무","laws":[{"law":"하도급거래공정화에관한법률","type":"법률","article":"제13조"}]},
    {"clause":"산업안전","desc":"공사현장 안전관리 의무","laws":[{"law":"산업안전보건법","type":"법률","article":"제63조"}]},
    {"clause":"청렴의무","desc":"뇌물·담합 등 부정행위 금지","laws":[{"law":"국가를당사자로하는계약에관한법률","type":"법률","article":"제27조"}]},
    {"clause":"분쟁해결","desc":"계약 분쟁 시 중재·소송 절차","laws":[{"law":"민법","type":"법률","article":"제390조"}]},
    {"clause":"검사 및 인수","desc":"납품 후 검수·인수 절차","laws":[{"law":"국가를당사자로하는계약에관한법률","type":"법률","article":"제14조"}]},
    {"clause":"권리·의무 양도 금지","desc":"계약상 권리의무 제3자 양도 불가","laws":[{"law":"국가를당사자로하는계약에관한법률","type":"시행령","article":"제49조"}]},
    {"clause":"비밀유지","desc":"계약 수행 중 취득한 정보 비밀유지","laws":[{"law":"공기업ㆍ준정부기관계약사무규칙","type":"기획재정부령","article":"제15조"}]},
]

PRACTICAL_QA = [
    {"q":"수의계약 한도액은?","a":"공기업 기준: 추정가격 5천만원 미만 (물품·용역), 1억원 미만 (공사). 긴급 시 2배 적용 가능.","keywords":["수의계약","한도","금액"],"law":"시행령 제26조"},
    {"q":"입찰공고 기간은?","a":"일반경쟁 7일 이상, 제한경쟁 5일 이상, 긴급입찰 5일 이상. 국제입찰은 40일 이상.","keywords":["입찰","공고","기간","일수"],"law":"시행령 제33조"},
    {"q":"계약보증금 면제 사유는?","a":"국가·지자체, 보험사, 은행, 추정가격 5천만원 이하 물품 등. 시행령 제37조·제50조 참조.","keywords":["보증금","면제","사유"],"law":"시행령 제50조"},
    {"q":"지체상금률은?","a":"공사: 1/1000, 물품제조·구매: 0.75/1000, 용역: 1.25/1000 (1일당). 상한: 계약보증금 상당액.","keywords":["지체상금","비율","률"],"law":"시행령 제74조"},
    {"q":"선급금 비율은?","a":"계약금액의 70% 이내. 선급금보증서 필수 제출. 기성금 지급 시 선급금 정산.","keywords":["선급금","비율","한도"],"law":"시행령 제58조"},
    {"q":"물가변동 조정 요건은?","a":"①입찰일 기준 90일 이상 경과 ②등락률 3% 이상. 품목조정률 또는 지수조정률 방식 선택.","keywords":["물가변동","조정","요건","조건"],"law":"시행령 제64조"},
    {"q":"하자담보 기간은?","a":"건축공사 2년, 토목 3년, 조경 2년, 기계설비 2년, 전기·소방 2년. 건설산업기본법 시행령 별표4.","keywords":["하자","담보","기간","보증"],"law":"건설산업기본법 시행령 별표4"},
    {"q":"부정당업자 제재기간은?","a":"경미: 6개월, 중대: 1년, 담합: 2년. 원전비리방지법 적용 시 가중. 감경 사유 있으면 1/2 경감.","keywords":["부정당","제재","기간","자격제한"],"law":"시행령 제76조"},
    {"q":"낙찰하한율은?","a":"예정가격의 87.745% 이상 (물품·용역). 공사는 적격심사 기준 적용. 턴키는 별도.","keywords":["낙찰","하한","비율"],"law":"시행령 제42조"},
    {"q":"계약심사 대상 금액은?","a":"한수원 기준: 공사 3억 이상, 물품·용역 2억 이상. 수의계약은 5천만원 이상 시 심사.","keywords":["심사","대상","금액","위원회"],"law":"공기업규칙"},
]

GLOSSARY = {
    "추정가격": "물품·용역·공사 등의 조달에 소요되는 총비용을 말하며, 부가세 제외 금액입니다. 예정가격 작성의 기초가 됩니다. (시행령 제7조)",
    "예정가격": "입찰 또는 계약체결 전 미리 작성하여 밀봉하는 가격. 낙찰하한율의 기준이 됩니다. (시행령 제9조)",
    "적격심사": "최저가 입찰자에 대해 이행능력·실적·경영상태 등을 종합 심사하여 낙찰 여부를 결정하는 제도입니다. (시행령 제42조)",
    "종합심사낙찰제": "가격·기술·경영 등을 종합 평가하여 낙찰자를 결정하는 제도. 300억 이상 공사에 적용됩니다. (시행령 제42조의2)",
    "협상에 의한 계약": "기술·가격을 분리 평가하여 협상으로 계약하는 방식. 기술용역에 주로 적용됩니다. (시행령 제43조)",
    "제한경쟁": "실적·기술·자격 등으로 입찰참가를 제한하는 경쟁입찰. 특수한 기술이 필요할 때 사용합니다. (법 제7조)",
    "지명경쟁": "특정 업체를 지정하여 입찰에 참가하게 하는 방식. 매우 제한적으로만 허용됩니다. (법 제7조)",
    "수의계약": "경쟁입찰 없이 특정 상대방과 직접 계약하는 방식. 추정가격 5천만원 미만 등 제한적 사유에서만 가능합니다. (시행령 제26조)",
    "다수공급자계약": "MAS(Multiple Award Schedule). 규격·품질 등이 일정 기준을 충족하는 복수 공급자와 단가계약을 체결하는 방식입니다. (조달사업법 제5조의2)",
    "단가계약": "일정 기간 물품의 단가만 정하고, 필요할 때마다 수량을 정하여 납품받는 계약입니다. (시행령 제22조)",
    "계약보증금": "계약의 성실한 이행을 담보하기 위해 납부하는 금액. 계약금액의 10~15%입니다. (법 제12조, 시행령 제50조)",
    "하자보수보증금": "하자담보책임기간 동안 하자보수를 담보하기 위한 금액. 계약금액의 2~5%입니다. (시행령 제62조)",
    "지체상금": "이행기한 내 계약을 이행하지 못할 경우 부과되는 금액. 공사 1/1000, 물품 0.75/1000입니다. (시행령 제74조)",
    "부정당업자": "허위서류 제출, 담합, 뇌물 등 부정행위를 한 자로, 입찰참가자격이 제한됩니다. (법 제27조)",
    "선급금": "계약 이행 전 미리 지급하는 금액. 계약금액의 70% 이내이며 선급금보증서가 필요합니다. (시행령 제58조)",
    "기성금": "공사·용역 수행 중 이행 부분에 대해 지급하는 대가입니다. 기성검사 후 14일 이내 지급합니다.",
    "물가변동": "입찰일 기준 90일 이상 경과하고 3% 이상 등락 시 계약금액을 조정할 수 있습니다. (시행령 제64조)",
    "설계변경": "시공 중 설계도서의 내용을 변경하는 것. 계약금액 조정 사유가 됩니다. (시행령 제65조)",
    "PQ": "Pre-Qualification. 입찰 전 시공능력·실적 등을 사전 심사하여 적격자만 입찰에 참가시키는 제도입니다.",
    "낙찰하한율": "예정가격 대비 최저 입찰 가능 비율. 이 비율 미만으로 입찰하면 무효 처리됩니다.",
}

# ===== 계약 서식 템플릿 =====
CONTRACT_TEMPLATES = [
    {"name":"입찰공고문","type":"입찰","fields":["공고번호","공고명","계약방식(일반경쟁/제한경쟁)","추정가격","입찰참가자격","공고기간","개찰일시","입찰보증금","납품(이행)기한","담당부서·연락처"],"law":"시행령 제33조","note":"공고기간 7일 이상, 긴급 시 5일"},
    {"name":"계약서 (물품)","type":"물품","fields":["계약명","계약금액(부가세 별도/포함)","납품기한","납품장소","대가지급조건","계약보증금","하자보수보증금","지체상금","특약사항","계약상대자 정보"],"law":"국가계약법 제11조","note":"계약서 작성 후 쌍방 기명날인"},
    {"name":"계약서 (공사)","type":"공사","fields":["공사명","공사장소","공사기간(착공~준공)","계약금액","도급내역서","계약보증금(15%)","선급금 조건","설계변경 조건","안전관리계획","하자담보책임기간"],"law":"국가계약법 제11조","note":"공사도급계약 일반조건 첨부"},
    {"name":"계약서 (용역)","type":"용역","fields":["용역명","용역기간","계약금액","과업지시서","투입인력","성과물 목록","저작권 귀속","비밀유지 의무","기성금 지급조건","하자담보기간"],"law":"국가계약법 제11조","note":"과업지시서를 계약서의 일부로 첨부"},
    {"name":"수의계약 사유서","type":"수의계약","fields":["계약명","추정가격","수의계약 사유(시행령 제26조 제_호)","사유 상세 설명","견적서 징수 현황(2인 이상)","비교 검토 의견","계약상대자 선정 사유"],"law":"시행령 제26조","note":"사유의 적정성·긴급성 입증 자료 첨부"},
    {"name":"준공검사 조서","type":"준공","fields":["계약명","계약상대자","계약금액","계약기간","준공일","검사일","검사 결과(적합/부적합)","미시공 또는 하자 사항","하자보수보증금 산정","검사자 서명"],"law":"국가계약법 제14조","note":"검사 후 14일 이내 대가 지급"},
    {"name":"계약변경 합의서","type":"변경","fields":["원계약명","원계약금액","변경 사유","변경 내역(증감)","변경 후 계약금액","변경 후 이행기한","변경보증금 조정","쌍방 합의 확인"],"law":"시행령 제64~65조","note":"설계변경·물가변동·기타 내용 변경"},
]

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
    related = RELATED_LAWS.get(law_name, [])
    # 현재 열린 법령은 제외
    related = [r for r in related if not (r["law"] == law_name and r["type"] == ft)]
    # 법령 시행일·개정일 경고
    warnings = []
    from datetime import datetime
    meta = fd["meta"]
    try:
        enforcement = meta.get("시행일자","")
        if enforcement:
            enf_str = enforcement.replace(".","-")
            enf_date = datetime.strptime(enf_str, "%Y-%m-%d")
            if enf_date > datetime.now():
                warnings.append({"type":"future","msg":f"이 법령은 {enforcement}에 시행 예정입니다. 현재 시행 중인 법령과 다를 수 있습니다."})
            elif (datetime.now() - enf_date).days < 90:
                warnings.append({"type":"recent","msg":f"이 법령은 {enforcement}에 시행된 최근 개정 법령입니다. 변경 내용을 확인하세요."})
        promulgation = meta.get("공포일자","")
        if promulgation:
            pub_str = promulgation.replace(".","-")
            pub_date = datetime.strptime(pub_str, "%Y-%m-%d")
            if pub_date > datetime.now():
                warnings.append({"type":"future","msg":f"공포일: {promulgation} (아직 공포 전)"})
    except Exception:
        pass
    has_diff = law_name in LAW_DECREE_DIFF
    return jsonify({"law_name":law_name,"file_type":ft,"title":meta.get("제목",law_name),"meta":meta,"articles":fd["articles"],"available_types":list(law["files"].keys()),"related_laws":related[:5],"warnings":warnings,"has_diff":has_diff})

@app.route("/api/summarize", methods=["POST"])
def api_summarize():
    data = request.get_json() or {}
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

@app.route("/api/glossary")
def api_glossary():
    q = request.args.get("q","").strip()
    if q and q in GLOSSARY:
        return jsonify({"term": q, "definition": GLOSSARY[q]})
    return jsonify({"terms": GLOSSARY})

@app.route("/api/clauses")
def api_clauses():
    q = request.args.get("q","").strip().lower()
    if q:
        return jsonify([c for c in CONTRACT_CLAUSES if q in c["clause"].lower() or q in c["desc"].lower()])
    return jsonify(CONTRACT_CLAUSES)

@app.route("/api/bookmarks")
def get_bm():
    return jsonify([])

@app.route("/api/law-diff")
def api_law_diff():
    name = request.args.get("name","")
    if name in LAW_DECREE_DIFF:
        return jsonify({"law": name, "diffs": LAW_DECREE_DIFF[name]})
    return jsonify({"law": name, "diffs": []})

@app.route("/api/templates")
def api_templates():
    q = request.args.get("q","").strip().lower()
    if q:
        return jsonify([t for t in CONTRACT_TEMPLATES if q in t["name"].lower() or q in t["type"].lower()])
    return jsonify(CONTRACT_TEMPLATES)

@app.route("/api/check-updates")
def api_check_updates():
    """구독 법령의 메타 정보 반환 (프론트에서 변경 비교)"""
    names = request.args.get("names","").split(",")
    index = get_index()
    result = []
    for name in names:
        name = name.strip()
        if not name or name not in index: continue
        law = index[name]
        for ft, fd in law["files"].items():
            meta = fd.get("meta",{})
            result.append({
                "law": name,
                "type": ft,
                "enforcement": meta.get("시행일자",""),
                "promulgation": meta.get("공포일자",""),
                "status": meta.get("상태",""),
            })
    return jsonify(result)
