# 한수원 계약 법령 검색 시스템 (KHNP Law Search)

한국수력원자력(한수원) 계약담당자를 위한 법령 검색 및 AI 자문 시스템.

---

## 시스템 아키텍처

```
[Browser]  <-->  [Vercel Serverless]  <-->  [Upstage Solar LLM API]
                   |
                   +-- Flask (api/index.py)
                   |     +-- 키워드 매칭 어드바이저
                   |     +-- Solar LLM 연동
                   |     +-- 법령 검색 엔진
                   |     +-- 나라장터 입찰공고 프록시
                   |
                   +-- 정적 데이터 (data/*.json)
                   |     +-- khnp_laws_1.json (14개 핵심 법령)
                   |     +-- khnp_laws_2.json (14개 핵심 법령)
                   |     +-- rest_laws.json   (3,000+ 일반 법령)
                   |
                   +-- SPA 프론트엔드 (templates/index.html)
```

### 기술 스택

| 구분 | 기술 |
|------|------|
| 백엔드 | Python 3 + Flask |
| 프론트엔드 | Vanilla JS SPA (단일 HTML) |
| AI/LLM | Upstage Solar Mini |
| 배포 | Vercel Serverless Functions |
| 데이터 | JSON 파일 기반 (빌드 시 생성) |
| 외부 API | 나라장터 공공데이터 OpenAPI |

### 디렉토리 구조

```
lawsearch/
  api/
    index.py          # Flask 서버리스 앱 (모든 API 엔드포인트)
  templates/
    index.html         # SPA 프론트엔드 (HTML+CSS+JS 단일 파일)
  static/              # 정적 파일
  data/
    khnp_laws_1.json   # 한수원 핵심 법령 데이터 (14개)
    khnp_laws_2.json   # 한수원 핵심 법령 데이터 (14개)
    rest_laws.json     # 전체 법령 데이터 (3,000+개)
  build_index.py       # legalize-kr 원본에서 JSON 인덱스 빌드
  vercel.json          # Vercel 배포 설정
  requirements.txt     # Python 의존성 (flask, pyyaml)
```

---

## 주요 기능

### 1. AI 어드바이저 (스마트 검색)

자연어 질의를 분석하여 관련 법령을 추천하는 핵심 기능.

- **키워드 매칭 엔진**: 20개 시나리오(공사, 용역, 물품, 원자력, 전력, 입찰, 수의계약, 보증, 계약금액조정, 준공/하자, 지체상금, 하도급, 청렴/부정당, 안전, 환경, 공공기관경영, 공정거래, 민사, 방폐물/해체, 단가계약, 낙찰/심사, 대가지급)에 대해 키워드 기반 즉시 매칭
- **Solar LLM 보강**: Upstage Solar Mini 모델이 키워드 결과를 참고하여 실무 분석과 추천 생성
- **핵심 조문(key_articles)**: 각 추천 법령에 핵심 조문 번호를 명시하여 법령 뷰어에서 하이라이트
- **참고 데이터**: 관련 조문 전문, 계약 실무 사례, 외부 링크(나라장터, 법령정보센터 등) 제공

### 2. 법령 검색

키워드 기반 법령 및 조문 전문 검색.

- 법령명 매칭 + 조문 내용 매칭 결합 스코어링
- 한수원 핵심 28개 법령 우선 표시 (KHNP 보너스 점수)
- 6개 카테고리(계약핵심, 공공기관운영, 원자력/전력, 건설/하도급, 공정거래/민상법, 안전/환경) 필터링

### 3. 법령 뷰어

법령 조문을 구조화하여 표시하는 뷰어.

- 항(①②③), 호(1. 2. 3.), 목(가. 나. 다.) 구조 파싱
- 어드바이저 연동 시 핵심 조문 하이라이트 및 포커스 모드
- TOC(목차) 자동 생성, 핵심 조문 표시
- 조문 내 "제X조" 참조를 클릭 가능한 링크로 변환 (동일 법령 내 이동)
- AI 요약 (Solar LLM 기반 실무 핵심 정리)
- 북마크 (localStorage 기반)

### 4. 나라장터 입찰공고 연동

공공데이터포털 API를 통해 나라장터 입찰공고를 실시간 검색.

### 5. 법령 카테고리 브라우징

한수원 업무별 6개 카테고리로 분류된 28개 핵심 법령 탐색.

### 6. 계약 프로세스 플로우

검색 키워드에 따라 해당 계약 유형의 전체 프로세스를 단계별로 시각화하는 기능.

- **6가지 계약 유형 지원**: 입찰, 공사, 용역, 구매, 단가, 수의계약
- **단계별 정보**: 각 단계의 명칭, 설명, 관련 법령 조문 표시
- **시각적 플로우**: 좌에서 우로 흐르는 프로세스 플로우 다이어그램으로 표현
- **키워드 자동 매칭**: 검색어에 포함된 키워드로 적절한 프로세스 유형을 자동 선택
- **기본값 제공**: "계약", "물품", "납품" 등 일반 키워드 검색 시 구매 프로세스를 기본 표시

| 프로세스 유형 | 단계 수 | 주요 법령 |
|---------------|---------|-----------|
| 입찰 | 8단계 | 국가계약법, 시행령 |
| 공사 | 9단계 | 건설산업기본법, 산업안전보건법 |
| 용역 | 8단계 | 시행령 제43조, 국가계약법 |
| 구매 | 8단계 | 전자조달법, 국가계약법 |
| 단가 | 6단계 | 시행령 제22조, 공기업규칙 |
| 수의계약 | 6단계 | 시행령 제26조, 공기업규칙 |

### 7. 실무 편의 기능
- **조문 복사**: 법령 뷰어에서 조문을 클립보드에 복사 (보고서·기안문 작성용)
- **키보드 단축키**: `/` 검색 포커스, `Esc` 뒤로가기, `Ctrl+H` 홈
- **목차 토글**: 조문이 많을 때 목차를 접어서 화면 공간 확보
- **법령 비교**: 법률↔시행령 같은 조문번호 좌우 비교
- **인쇄**: 검색 결과를 인쇄 최적화 레이아웃으로 출력

---

## API 엔드포인트

| 메서드 | 경로 | 설명 | 파라미터 |
|--------|------|------|----------|
| GET | `/` | SPA 메인 페이지 | - |
| GET | `/api/categories` | 한수원 법령 카테고리 목록 | - |
| GET | `/api/stats` | 전체 법령 통계 | - |
| GET | `/api/search` | 법령 검색 | `q` (검색어), `category` (선택) |
| GET | `/api/advisor` | AI 어드바이저 | `q` (자연어 질의) |
| GET | `/api/law` | 법령 조문 조회 | `name` (법령명), `type` (법률/시행령 등) |
| POST | `/api/summarize` | AI 조문 요약 | JSON body: `context`, `law_name`, `articles_text` |
| GET | `/api/bids` | 나라장터 입찰공고 | `q` (검색어) |
| GET | `/api/glossary` | 계약 용어사전 | `q` (선택, 특정 용어 조회) |
| GET | `/api/clauses` | 계약서 조항 ↔ 법령 매핑 | `q` (선택, 키워드 필터) |
| GET | `/api/law-diff` | 법률↔시행령 차이 요약 | `name` (법령명) |
| GET | `/api/templates` | 계약 서식 템플릿 목록 | `q` (선택, 키워드 필터) |
| GET | `/api/check-updates` | 구독 법령 변경 체크 | `names` (법령명 쉼표 구분) |
| GET | `/api/auth/me` | 인증 상태 (stub) | - |
| GET | `/api/bookmarks` | 북마크 목록 (stub) | - |

### 어드바이저 응답 구조

```json
{
  "query": "원전 기자재 납품",
  "analysis": "원전 기자재 납품은 원전비리방지법의 적용을 받으며...",
  "categories": ["원자력사업", "물품구매"],
  "recommendations": [
    {
      "law": "국가를당사자로하는계약에관한법률",
      "type": "법률",
      "reason": "물품 구매 입찰·계약 절차",
      "priority": "필수",
      "key_articles": "제7조",
      "from_category": "물품구매"
    }
  ],
  "total": 8,
  "source": "solar",
  "ref_data": {
    "articles": [...],
    "cases": [...],
    "links": [...]
  }
}
```

---

## 데이터 구조

### 법령 JSON 인덱스

`build_index.py`가 `legalize-kr/` 마크다운 원본에서 JSON 인덱스를 생성한다.

```json
{
  "법령명": {
    "files": {
      "법률": {
        "meta": {
          "제목": "법령 정식명칭",
          "소관부처": ["부처명"],
          "공포일자": "YYYY.MM.DD",
          "시행일자": "YYYY.MM.DD",
          "상태": "현행",
          "출처": "https://www.law.go.kr/..."
        },
        "articles": [
          {
            "number": "제1조",
            "title": "목적",
            "content": "조문 전문 텍스트..."
          }
        ]
      },
      "시행령": { ... },
      "시행규칙": { ... }
    }
  }
}
```

### 한수원 핵심 법령 (28개)

| 카테고리 | 법령 |
|----------|------|
| 계약 핵심 | 국가계약법, 공기업계약사무규칙, 조달사업법, 전자조달법, 지방계약법 |
| 공공기관 운영 | 공공기관운영법, 정보공개법, 회계감사규칙, 갈등예방규정 |
| 원자력/전력 | 원자력안전법, 원자력진흥법, 원자력손해배상법, 손배보상계약법, 방호방재법, 원안위법, 안전정보공개법, 원전비리방지법, 전기사업법, 전력기술관리법, 에너지법, 방사성폐기물관리법 |
| 건설/하도급 | 건설산업기본법, 하도급법 |
| 공정거래/민상법 | 독점규제법, 민법 |
| 안전/환경 | 산업안전보건법, 환경영향평가법, 산업안전보건기준규칙 |

---

## 배포 방법

### Vercel 배포

1. GitHub 리포지토리 연결 후 Vercel 프로젝트 생성
2. 환경 변수 설정:
   - `UPSTAGE_API_KEY`: Upstage Solar API 키 (AI 기능용, 없으면 키워드만 동작)
   - `G2B_API_KEY`: 공공데이터포털 나라장터 API 키 (입찰공고용, 선택)
   - `SECRET_KEY`: Flask 세션 시크릿 (선택, 미설정 시 자동 생성)
3. `vercel.json` 설정에 따라 자동 빌드/배포

### 로컬 개발

```bash
pip install -r requirements.txt
# 환경변수 설정 (.env)
export UPSTAGE_API_KEY=your_key_here

# Flask 개발 서버
python app.py
# 또는
cd api && python -c "from index import app; app.run(debug=True, port=5001)"
```

### 데이터 빌드

```bash
# legalize-kr 원본 데이터에서 JSON 인덱스 생성
python build_index.py
```

---

## 고도화 로드맵

### Tier 1 - 단기 (1-2주)

- [x] 전 시나리오 key_articles 완비
- [x] Solar LLM 프롬프트 개선 (실무 분석, 리스크 포함)
- [x] 조문 간 참조 링크화 ("제X조" 클릭 이동)
- [x] 법령 간 교차 참조 링크 (다른 법령의 조문으로 이동)
- [ ] 검색 결과 하이라이팅 (매칭 키워드 강조)
- [x] 최근 검색 기록 (localStorage)

### Tier 2 - 중기 (1-2개월)

- [ ] 벡터 임베딩 기반 시맨틱 검색 (법률 용어 유사도)
- [ ] 판례 데이터 연동 (대법원 판례 검색 API)
- [ ] 사용자 인증 및 북마크/메모 서버 저장 (DB 연동)
- [ ] 계약 유형별 체크리스트 PDF 내보내기
- [ ] 법령 개정 알림 (법령정보센터 RSS 연동)
- [ ] 다국어 지원 (영문 법령명 매핑)

### Tier 3 - 장기 (3-6개월)

- [ ] RAG (Retrieval-Augmented Generation) 파이프라인: 조문 원문 기반 답변 생성
- [ ] 계약서 자동 검토: 계약서 업로드 후 법령 위반 사항 점검
- [ ] 조문 비교 (신구 대조표 자동 생성)
- [ ] 관련 행정규칙/예규/고시 통합 (한수원 내부규정 연동)
- [ ] 모바일 앱 (PWA 또는 React Native)
- [ ] 부서별 맞춤 대시보드 (계약, 안전, 품질 등)

---

## 변경 이력

| 날짜 | 변경 내용 |
|------|-----------|
| 2026-04-04 | **8차 QA (최종)**: console.log 제거, CSS 중복 검사 (0건), DOCS.md 정리 (API 3개 추가, 기능 69개, 변경이력 압축), import 테스트 PASS |
| 2026-04-04 | 7차 QA (최종 정리): 랜딩 페이지 도구 모음 접기 토글, 검색 결과 섹션 19단계 최적 순서 재배치, API 자동 재시도 (1회), 전체 데이터 무결성 검증 PASS (0 error/0 warning) |
| 2026-04-04 | 6차 QA (최종 안정화): JS 에러 핸들링 전수 조사 및 보강 (17개 async 함수 try-catch 추가), 전역 에러 핸들러 추가, API 응답 검증 강화, DOM null 체크 보강, 미사용 CSS/HTML 정리, 전체 API 라우트 통합 테스트 PASS |
| 2026-04-04 | 5차 QA: CSS 변수 정합성 (--bg-card 미정의 수정), 데이터 무결성 6건 수정, 검색 Enter 시 모바일 키보드 닫힘, 맨 위로 스크롤 버튼 추가 |
| 2026-04-04 | 4차 QA: Vercel 배포 검증, 엣지케이스 방어 강화, UX 개선 (스켈레톤 로딩, 첫 방문 안내, 뒤로가기 히스토리 스택), app.py 동기화 목록 정리 |
| 2026-04-04 | 3차 QA: 성능 최적화 (응답 크기 축소, 검색 조기종료), 접근성 개선 (aria-label, 색상 대비), 보안 강화 (XSS 방어, 입력 길이 제한), font-display: swap |
| 2026-04-03 | 2차 QA + 고도화: key_articles 누락 27건 보완, refData 변수 참조 버그 수정, 접기/펼치기 섹션 4종 추가, 로딩 인디케이터 개선, 에러 메시지 사용자 친화적 개선 |
| 2026-04-03 | 3차 고도화: 금액별 계약방식 자동 판별 (공사/용역/물품, 6단계 금액 구간), 최근 검색 이력 (localStorage, 최대 10건), 유사 검색어 추천 (시나리오 키워드 기반) |
| 2026-04-03 | 계약 프로세스 플로우 기능 추가: 검색 키워드 기반 6가지 계약 유형(입찰, 공사, 용역, 구매, 단가, 수의계약)의 단계별 프로세스를 시각적으로 표시. 백엔드 `PROCESS_FLOWS` 데이터 및 `get_reference_data` 연동, 프론트엔드 프로세스 다이어그램 렌더링 구현. |

### 2026-04-04 (7차 QA - 최종 정리)
- **랜딩 페이지 정리 (사용자 압도감 제거)**:
  - 나의 계약/검색 이력/구독 법령/활동 타임라인/통계: 이미 데이터 없을 때 빈 상태 확인 (기존 정상)
  - 하단 도구 버튼들(위자드, 시뮬레이터, 업무일지, 퀴즈, 오프라인 관리 등)을 "도구 모음" 접기/펼치기 토글로 묶음 (`toggleLandingTools`)
  - 첫 방문 시(데이터 없을 때) 검색창 + 예시 + 시나리오 칩만 깔끔하게 표시
- **검색 결과 섹션 순서 최적화 (renderSmartResults)**:
  - 실무자 우선순위에 맞게 19단계로 재배치:
    1. 배너 (추론 질문)
    2. 요약 대시보드 + 위험도 점수
    3. AI 분석 (Solar)
    4. 추천 법령 (우선순위별)
    5. 금액별 계약방식 + 계산기
    6. 계약방식 비교표
    7. 프로세스 플로우 + 타임라인 + 일정 계산기
    8. Q&A
    9. 리스크 체커 + 감사 지적
    10. 필수 서류
    11. 부서 역할
    12. 참고 조문 (하이라이트)
    13. 계약 사례 + 체크리스트
    14. 특약 조항
    15. 서식 템플릿
    16. 계약서 조항 매핑
    17. 나라장터 입찰공고
    18. 외부 링크 + 유사 검색어
    19. 버튼 (종합리포트, 검토요청서, 기안문요지, 체크리스트)
  - 주요 변경: 대시보드+위험도를 AI분석 앞으로 이동, Q&A를 프로세스 뒤로 이동, 필수서류를 리스크 뒤로 이동, 버튼을 최하단으로 이동
  - `refData0`/`refData` 변수 통합 (별칭 alias)
- **에러 복구 개선 (API 자동 재시도)**:
  - `api()` 헬퍼: 네트워크 오류 시 1초 대기 후 자동 1회 재시도. 2회째 실패 시 `null` 반환 + 콘솔 로그
  - `post()` 헬퍼: `api()` 기반이므로 동일하게 재시도 적용
- **전체 데이터 무결성 검증 PASS**:
  - ADVISOR_SCENARIOS 22개 시나리오 77개 법령 참조: 전수 인덱스 존재 확인 (0 error)
  - PROCESS_FLOWS 7개 유형 56개 step: 전수 STEP_DAYS 매핑 확인 (0 error)
  - RELATED_LAWS 6개 법령 14개 관련법: 전수 인덱스 존재 확인 (0 error)
  - key_articles 전수 조문 존재 확인 (0 error)
  - LAW_SUMMARIES 18개, CONTRACT_CLAUSES 15개: 전수 검증 (0 warning)
- **통합 테스트 (15개 라우트 전체 PASS)**
- **총 수정 건수**: 약 105건+ (기존 100건 + 5건)

### 2026-04-04 (6차 QA - 최종 안정화)
- **JS 에러 핸들링 전수 조사 (17개 async 함수)**:
  - try-catch 추가: `checkAuth`, `doLogin`, `doRegister`, `doLogout`, `loadBookmarks`, `showBookmarks`, `saveMemo`, `removeBookmark`, `loadCategories`, `loadStats`, `loadGlossary`, `checkSubscriptionUpdates`, `compareContracts`, `toggleCompareView`, `showLawDiff`, `viewAllBookmarkedArticles`, `openLawArticle`
  - 이미 try-catch 있는 함수 확인: `doSearch`, `doAdvisor`, `openLaw`, `loadBidResults`, `loadClauses`, `summarizeArticle`
  - catch 블록에서 `console.error`로 디버깅 정보 출력 + `toast()`로 사용자 안내
- **API 응답 검증 강화**:
  - `api()` 헬퍼에 HTTP 에러 상태 로깅 추가
  - `checkAuth`: `data.logged_in` 접근 전 `data && data.logged_in` null 체크
  - `loadBookmarks`: `Array.isArray(data)` 검증 추가 (배열이 아닌 응답 방어)
  - `loadCategories`: `cats` 객체 유효성 검증 추가
  - `loadStats`: `s.total_laws` 접근 전 null 체크 + fallback 0
  - `checkSubscriptionUpdates`: `Array.isArray(data)` 검증 추가
  - `doLogin/doRegister`: `res?.error` optional chaining으로 null 안전 접근
- **DOM null 체크 보강**:
  - `printLaw()`: `viewerTitle`, `viewerMeta`, `lawBody` 요소 null 체크 추가
  - `loadCategories`: `filter` 요소 null 체크 (`if (filter)`)
  - `loadStats`: `statLaws`, `statArticles` 요소 null 체크
  - `showBookmarks`: `bmFolders` 요소 null 체크
  - `toggleCompareView`: `viewerView` 요소 null 체크
  - `showLawDiff`: `aiSummaryArea` 요소 null 체크
  - `viewAllBookmarkedArticles`: 6개 DOM 요소 null 체크 추가
- **전역 에러 핸들러 추가**:
  - `window.addEventListener('error', ...)`: 예기치 않은 JS 에러 콘솔 로깅
  - `window.addEventListener('unhandledrejection', ...)`: 미처리 Promise rejection 감지 + `preventDefault()`로 사용자 노출 방지
- **미사용 코드 정리**:
  - CSS: `.alio-ref-*` 클래스 7개 제거 (HTML/JS에서 미참조)
  - CSS: `.res-meta`, `.res-art` 관련 클래스 5개 제거 (HTML/JS에서 미참조)
  - CSS: `.flow-steps`, `.flow-arrow` 미디어쿼리 규칙 제거 (HTML/JS에서 미참조)
  - HTML: 비어있는 `<div id="welcomeView"></div>` 제거 (JS에서 미참조)
- **통합 테스트 (13개 라우트 전체 PASS)**:
  - `/api/categories` 200, `/api/stats` 200, `/api/search?q=입찰` 200
  - `/api/advisor?q=공사` 200, `/api/law?name=국가를당사자로하는계약에관한법률&type=법률` 200
  - `/api/glossary` 200, `/api/clauses` 200, `/api/templates` 200
  - `/api/law-diff?name=국가를당사자로하는계약에관한법률` 200
  - `/api/check-updates?names=국가를당사자로하는계약에관한법률` 200
  - `/api/bids?q=한수원` 200, `/api/auth/me` 200, `/api/bookmarks` 200
  - 에러 케이스: `/api/advisor` (쿼리 없음) 400, `/api/law?name=없는법률` 404
- **총 수정 건수**: 80건째~약 100건 (기존 79건 + 약 21건)

### 2026-04-04 (5차 QA)
- **CSS 일관성 수정**:
  - `--bg-card` 변수가 `:root`와 `[data-theme="dark"]` 어디에도 정의되지 않은 채 `.skeleton-card`, `.skeleton-line`에서 참조되던 문제 수정 (light: `#ffffff`, dark: `#1a1d27` 추가)
  - 미사용 CSS 클래스 21개 확인 (`.alio-ref-*` 6개, `.res-*` 5개, `.flow-*` 2개 등) -- 향후 정리 대상으로 기록
  - 다크모드 하드코딩 색상 검사: modal overlay `rgba(0,0,0,0.3)` 2곳은 양 모드에서 정상 동작 확인
- **데이터 정합성 수정 (6건)**:
  - `전기사업법` type `법률` -> `시행령` (법률 파일 미존재)
  - `에너지법` type `법률` -> `시행규칙` (법률 파일 미존재)
  - `산업안전보건기준에관한규칙` type `법률` -> `고용노동부령` (법률 파일 미존재)
  - `조달사업에관한법률` key_articles `제5조의2` -> `제5조` (2곳, 해당 조문 미존재)
  - `하도급거래공정화에관한법률` key_articles `제14조의2` -> `제14조` (해당 조문 미존재)
  - LAW_SUMMARIES, RELATED_LAWS 전수 검증 완료 (이상 없음)
- **실사용 시나리오 테스트**: 4개 시나리오 전체 PASS
  - "입찰 공고 방법" 검색: 추천 3건 이상 확인
  - "물품 구매 3천만원" 검색: 계약방식 자동 판별 정상
  - 국가계약법 조문 조회: 44개 조문 로드 확인
  - 용어사전 20개 중 19개 법령 데이터 내 존재 확인 (PQ는 약어로 정상)
- **UX 개선**:
  - 검색 input Enter 키 시 `blur()` 추가 (모바일에서 가상 키보드 자동 닫힘)
  - 맨 위로 스크롤 버튼 추가 (페이지 400px 이상 스크롤 시 좌하단에 표시, 법령 뷰어 스크롤도 초기화)

### 2026-04-04 (4차 QA)
- **Vercel 배포 설정 검증**: vercel.json 라우트 우선순위(static -> api -> fallback) 정상, .vercelignore에서 data/*.json 및 static/frames/*.webp 미제외 확인, requirements.txt 패키지(flask, pyyaml) 완비 확인
- **엣지케이스 방어 (백엔드)**:
  - `parse_amount`: "1조" 단위 지원 추가, "1.5만원" 소수점 지원, 음수 금액("-5억") 거부를 위한 negative lookbehind 추가
  - `get_contract_method`: amount=0/None/-1 방어 처리 추가, "1조원" 이상 금액 표시 지원
- **엣지케이스 방어 (프론트엔드)**:
  - `escHtml()`: 배열/객체 입력 시 `[object Object]` 대신 의미 있는 문자열로 변환 (Array.join, JSON.stringify)
- **UX 개선**:
  - 첫 방문 안내 배너: localStorage 기반 1회만 표시, 12초 후 자동 소멸, AI 어드바이저/금액 검색 안내
  - 스켈레톤 로딩 UI: 검색 결과/어드바이저 로딩 시 shimmer 애니메이션 카드 표시
  - 뒤로가기 히스토리 스택: `previousView` 단일 변수에서 `viewHistory` 배열로 변경, viewer->viewer(교차참조) 시 올바른 뷰로 복귀

#### app.py 동기화 필요 목록

api/index.py 기준으로 app.py에 누락된 항목:

| 구분 | 항목 | 상세 |
|------|------|------|
| 시나리오 | 계약해지/해제, 계약내용변경 | 2개 시나리오 미반영 |
| key_articles | ADVISOR_SCENARIOS 전체 | api/index.py 77건 vs app.py 2건 (Solar 프롬프트 내 예시만) |
| 함수 (20개) | parse_amount, get_contract_method, get_reference_data, get_related_queries, get_method_comparison, get_required_docs, fetch_g2b_bids, summarize 등 | 금액 판별, 참고 데이터, 나라장터, AI 요약 등 핵심 기능 |
| 라우트 (8개) | /api/bids, /api/glossary, /api/clauses, /api/law-diff, /api/templates, /api/check-updates, /api/law(query param 방식), /static/ | API 엔드포인트 미반영 |
| 상수 (12개) | PROCESS_FLOWS, SPECIAL_CLAUSES, AUDIT_CASES, ROLE_MAP, LAW_SUMMARIES, GLOSSARY, PRACTICAL_QA, CONTRACT_TEMPLATES, CONTRACT_CLAUSES, LAW_DECREE_DIFF, RELATED_LAWS | 프로세스 플로우, 특약, 감사사례, 용어사전 등 데이터 |

app.py에만 있는 항목 (Vercel에서 미사용):

| 구분 | 항목 | 비고 |
|------|------|------|
| DB/인증 | get_db, init_db, hash_password, verify_password, login_required | SQLite DB + 세션 인증 (Vercel에서는 stub 처리) |
| 인증 라우트 | /api/auth/login, /api/auth/register, /api/auth/logout | Vercel에서는 /api/auth/me만 stub |
| 북마크 | add/delete/update/check_bookmark, bookmark_folders | 서버사이드 북마크 (Vercel에서는 localStorage만) |
| 법령 빌드 | build_index, parse_frontmatter, extract_articles | legalize-kr 마크다운 파싱 (Vercel에서는 JSON 사용) |
| 라우트 형식 | /api/law/<path:law_name> | Vercel은 /api/law?name= 방식 |

### 2026-04-04 (3차 QA)
- **성능 최적화 (백엔드)**:
  - `get_reference_data`: 참고 조문 content를 1000자로 제한 (응답 크기 축소)
  - `search_laws`: khnp_priority 캐싱, 조문 매칭 5개 도달 시 조기 종료, 불필요한 `.lower()` 재계산 제거
  - `_get_khnp_priority()` 캐시 함수 분리
- **성능 최적화 (프론트엔드)**:
  - Pretendard 폰트에 `font-display: swap` 적용 (폰트 로딩 중에도 텍스트 표시)
  - `loadBidResults`, `loadClauses`는 이미 비동기(async) 호출로 최적화 확인 완료
- **접근성(a11y) 개선**:
  - 검색 input 2개에 `aria-label` 추가 (법령 검색, AI 어드바이저 검색)
  - 카테고리 select에 `aria-label` 추가
  - 테마 토글 버튼에 `aria-label` 추가
  - 음성 검색 버튼 2개에 `aria-label` 추가
  - 검색 버튼 2개, 즐겨찾기 버튼에 `aria-label` 추가
  - 다크모드 `--text-muted` 색상을 `#636a7e` → `#8890a4`로 변경 (WCAG AA 대비율 4.5:1 이상 충족)
- **보안 강화**:
  - 모든 API 엔드포인트에 입력 길이 제한 추가 (`/api/search` 200자, `/api/advisor` 500자, `/api/bids` 100자, `/api/summarize` context 500자/law_name 200자/articles_text 5000자, `/api/check-updates` 2000자·30개 제한)
  - `/api/search`의 category 파라미터 화이트리스트 검증 추가
  - `viewerMeta` innerHTML에 `escHtml()` 적용 (소관부처, 공포일자, 시행일자, 상태)
  - `typeTabs` 버튼 렌더링에 `escHtml()` 적용 (lawName, type)
  - `renderArticles`의 `a.number`, `a.title` 표시에 `escHtml()` 적용
  - `tocGrid` 목차의 `a.number`, `a.title`에 `escHtml()` 적용
  - `escHtml()` 적용 여부 전수 검사: `structureBody`, `hlContent`, `hlContentGlobal` 모두 escHtml 선행 처리 확인 완료
  - localStorage: searchHistory(10개), activityLog(50개), lawCache(10개) 크기 제한 확인 완료


### 2026-04-03 (이전 이력 요약)
- **2차 QA**: key_articles 누락 27건 보완, refData 버그 수정, 접기/펼치기 4종, 로딩·에러 UX 개선
- **30차**: urllib.parse import, bare except 제거, 다크모드 하드코딩 7곳 CSS 변수화, safeLSSet 래퍼
- **29차**: 두 계약 비교 분석, 주간 업무 리포트
- **28차**: 계약 완료 보고서, 주요 법령 요약 카드 17개
- **27차**: 종합 위험도 점수 (0~100점), 법령 개인 노트
- **26차**: 음성 검색, 활동 타임라인
- **25차**: 다크모드 토글, 법령 PDF 다운로드
- **24차**: 오프라인 저장, 모바일 반응형 전면 개선
- **23차**: 계약 캘린더, 구독 법령 변경 체크
- **22차**: 비용 시뮬레이터, 북마크 공유 코드
- **21차**: 종합 리포트 생성 (10개 섹션), 서식 템플릿 7종
- **20차**: 나의 계약 대시보드, 법령 학습 퀴즈
- **19차**: 기안문 요지 자동 생성, 담당자 역할 안내
- **18차**: 필수 서류 안내, 감사 지적 사례 11개
- **17차**: 체크리스트 출력, 법률-시행령 차이 요약
- **16차**: 관심 법령 구독, 계약 방식 비교표
- **15차**: 검토 요청서, 조문별 AI 요약
- **14차**: 날짜 기반 일정 계산기, 업무 일지 내보내기
- **13차**: 특약 조항 생성기, 북마크 보고서 내보내기
- **12차**: 리스크 체커, 법령 간 상호참조 링크
- **11차**: 계약유형 위자드, 즐겨찾기 모아보기, 개정 하이라이트
- **10차**: 조항-법령 매핑 15개, 실무 Q&A 10개, 요약 대시보드
- **9차**: 용어사전 20개, 최근 법령 탭, 조문 메모
- **8차**: 계약일정 타임라인, 시행일 경고, 검색 통계
- **7차**: 계약금액 계산기, 조문 URL 공유, 즐겨찾기 내보내기
- **6차**: 조문 필터, 관련 법령 추천, 체크리스트 저장
- **5차**: 조문 복사, 키보드 단축키, 목차 토글
- **4차**: 법률-시행령 비교, 인쇄, 계약해지·변경 시나리오
