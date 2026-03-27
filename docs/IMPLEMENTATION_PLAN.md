# OpenUsage WSL Dashboard 구현 계획서

## 문서 목적

이 문서는 WSL Ubuntu에서 실행되는 사용량 수집 백엔드와 Windows 브라우저에서 확인하는 로컬 대시보드를 구현하기 위한 1차 계획서다.
목표는 macOS 메뉴바 앱을 그대로 포팅하는 것이 아니라, 현재 사용자 작업 환경에 맞는 구조로 OpenUsage의 핵심 기능만 재구성하는 것이다.

기준 근거:
- OpenUsage 개요 및 로컬 HTTP API: https://github.com/robinebers/openusage/blob/main/README.md
- OpenUsage 로컬 HTTP API 문서: https://github.com/robinebers/openusage/blob/main/docs/local-http-api.md
- Codex provider 문서: https://github.com/robinebers/openusage/blob/main/docs/providers/codex.md
- Claude provider 문서: https://github.com/robinebers/openusage/blob/main/docs/providers/claude.md
- Copilot provider 문서: https://github.com/robinebers/openusage/blob/main/docs/providers/copilot.md
- Plugin Host API 문서: https://github.com/robinebers/openusage/blob/main/docs/plugins/api.md

## 1. 목표 / 비목표

### 목표

- WSL Ubuntu 안에서 실행되는 로컬 사용량 수집 서비스를 만든다.
- Windows 브라우저에서 `localhost` 기반 UI로 Codex, Claude, Copilot 사용량을 한눈에 확인할 수 있게 한다.
- 현재 지원 provider는 3개로 제한하되, 이후 provider를 추가할 때 UI와 저장 구조를 다시 뜯지 않도록 설계한다.
- 각 provider의 요금제, 사용량 윈도우, 크레딧 구조가 바뀌더라도 가능하면 코드 수정 없이 응답 기반으로 표시되게 만든다.
- API 응답 실패, 인증 만료, 스키마 일부 변경에 대해 전체 시스템이 죽지 않고 provider 단위로 격리되게 한다.

### 비목표

- macOS 메뉴바 UX, tray icon, NSPanel 동작을 재현하지 않는다.
- 초기 단계에서 모바일 앱이나 Windows 네이티브 데스크톱 앱을 만들지 않는다.
- provider별 모든 부가 지표를 초기에 다 지원하지 않는다.
- 장기 보관용 분석 시스템이나 다중 사용자 서버를 만들지 않는다.
- 외부 공개 서비스 형태로 배포하지 않는다. 초기 범위는 개인 로컬 환경 전용이다.

## 2. 아키텍처

### 전체 구조

시스템은 4개 레이어로 분리한다.

1. `collector`
- WSL에서 실행되는 백엔드 프로세스
- 주기적으로 provider별 사용량을 조회
- 인증 파일 읽기, 토큰 갱신, 응답 정규화, 캐시 저장 담당

2. `provider adapters`
- `codex`, `claude`, `copilot` 각각을 담당하는 독립 모듈
- 공통 인터페이스를 구현하고 provider별 인증/요청/파싱만 캡슐화

3. `local api`
- 브라우저 UI가 읽는 로컬 HTTP API
- 최신 캐시 조회, provider 상태, 수동 새로고침 트리거 제공

4. `dashboard ui`
- Windows 브라우저에서 접속하는 React 기반 UI
- 백엔드의 정규화된 메트릭을 렌더링
- provider별로 다른 필드 구조를 직접 알지 않음

### 실행 경계

- 백엔드는 WSL 내부에서 실행한다.
- UI는 브라우저로 접근한다. 초기에는 백엔드가 정적 프론트 자산까지 함께 서빙하는 구성이 단순하다.
- 접속 주소는 기본적으로 `127.0.0.1:<port>`를 사용한다.
- Windows에서 WSL 로컬 서버에 접속 가능한 방식으로 포트를 바인딩한다.

### 권장 기술 스택

- 백엔드: Python 3.12 + FastAPI
- 스케줄러: APScheduler 또는 asyncio 기반 polling loop
- 저장소: SQLite
- 프론트엔드: React + Vite + TypeScript
- 스타일: Tailwind CSS 또는 단순 CSS 변수 기반

선정 이유:
- WSL 파일 시스템과 인증 파일 접근, JSON 처리, HTTP 요청, SQLite 다루기에 Python이 유리하다.
- FastAPI는 로컬 대시보드 API와 상태 엔드포인트를 빠르게 만들기 좋다.
- SQLite는 단일 사용자 로컬 도구에 충분하고, 캐시/히스토리/설정 저장을 한 곳에서 처리할 수 있다.

### 디렉터리 초안

```text
openusage-wsl-dashboard/
├── docs/
│   └── IMPLEMENTATION_PLAN.md
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── providers/
│   │   ├── services/
│   │   ├── storage/
│   │   └── models/
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   └── lib/
│   └── tests/
└── scripts/
```

## 3. 데이터 모델

핵심 원칙은 `provider별 원본 응답`과 `UI용 정규화 응답`을 분리하는 것이다.
요금제와 메트릭 구조가 바뀌어도 UI를 고치지 않으려면, 백엔드가 정규화 책임을 가져야 한다.

### 3.1 ProviderConfig

provider별 동작 정의를 가진다.

예상 필드:
- `provider_id`
- `display_name`
- `enabled`
- `poll_interval_seconds`
- `timeout_seconds`
- `auth_strategy`
- `supports_manual_refresh`

### 3.2 RawFetchRecord

원본 응답과 디버깅 정보를 저장한다.

예상 필드:
- `provider_id`
- `fetched_at`
- `http_status`
- `request_id`
- `raw_body`
- `parse_status`
- `error_code`
- `error_message`

용도:
- reverse-engineered API 변경 추적
- 파서 회귀 분석
- 장애 시 재현 근거 확보

### 3.3 UsageSnapshot

UI와 API에 노출하는 정규화 결과다.

예상 필드:
- `provider_id`
- `display_name`
- `plan`
- `status`
- `fetched_at`
- `source_state`
- `metrics`
- `meta`

`status` 예시:
- `ok`
- `auth_missing`
- `auth_expired`
- `request_failed`
- `parse_failed`
- `disabled`

### 3.4 Metric

중요 설계 포인트는 메트릭을 고정 필드가 아니라 배열로 두는 것이다.

예상 형태:

```json
{
  "type": "progress",
  "label": "5h",
  "used": 42,
  "limit": 100,
  "unit": "percent",
  "resetsAt": "2026-03-27T23:00:00Z",
  "periodDurationMs": 18000000,
  "meta": {
    "providerField": "rate_limit.primary_window"
  }
}
```

허용 타입:
- `progress`
- `text`
- `badge`

이 구조를 쓰면:
- Codex의 weekly review limit 추가
- Claude의 extra usage 노출
- Copilot 무료/유료 플랜 차이
를 모두 배열 항목 증감으로 흡수할 수 있다.

### 3.5 Provider별 정규화 원칙

Codex:
- `plan_type`을 `plan`으로 매핑
- `primary_window`, `secondary_window`, `code_review_rate_limit`, `credits`를 메트릭 배열로 변환

Claude:
- `subscriptionType` 또는 응답의 구독 정보가 있으면 `plan`으로 반영
- `five_hour`, `seven_day`, `seven_day_opus`, `extra_usage`를 메트릭 배열로 변환

Copilot:
- `copilot_plan` 또는 무료/유료 구분 필드를 `plan`으로 반영
- `quota_snapshots.chat`, `premium_interactions`, `limited_user_quotas.completions` 등을 메트릭 배열로 변환

원칙:
- UI는 provider별 JSON 경로를 절대 알지 않는다.
- UI는 `plan`, `status`, `metrics[]`만 사용한다.

## 4. Provider 확장 전략

### 확장 단위

provider 추가는 `어댑터 1개 + 테스트 1세트 + 설정 등록 1건`으로 끝나야 한다.

### 공통 인터페이스

각 provider는 아래 책임을 가진다.

- 인증 정보 찾기
- 필요 시 토큰 갱신
- API 요청 실행
- 원본 응답 검증
- 정규화 모델 생성
- 사용자 친화적 오류 메시지 반환

예상 인터페이스:

```python
class ProviderAdapter(Protocol):
    provider_id: str

    async def probe(self) -> UsageSnapshot:
        ...
```

### 플랜 변경 대응 전략

중요 원칙:
- 플랜 이름 하드코딩 금지
- 플랜별 한도표 하드코딩 금지
- 응답에 없는 값 추론 금지

대신:
- API 응답에서 제공하는 구독명, quota 필드, reset 시각을 그대로 정규화
- 새 필드가 생기면 `meta`에 담고, 표시 가능한 것은 메트릭으로 승격
- 예상 못 한 필드는 raw record에 남겨 후속 대응 가능하게 함

### 신규 provider 추가 절차

1. 인증 위치와 갱신 방식 문서화
2. 원본 응답 예시 확보
3. 정규화 매핑 작성
4. fixture 기반 파서 테스트 추가
5. UI smoke 확인

## 5. 구현 단계

### Phase 0. 저장소 스캐폴딩

산출물:
- 백엔드/프론트 기본 디렉터리
- 개발 명령
- 환경 변수 템플릿

완료 기준:
- 빈 FastAPI 앱 실행
- 빈 React 앱 표시

### Phase 1. 백엔드 코어

산출물:
- 설정 로더
- SQLite 저장소
- 스케줄러
- 공통 에러 모델
- UsageSnapshot 스키마

완료 기준:
- 더미 provider 1개로 poll -> 저장 -> API 응답 가능

### Phase 2. Local API

초기 엔드포인트:
- `GET /health`
- `GET /api/providers`
- `GET /api/usage`
- `GET /api/usage/{provider_id}`
- `POST /api/refresh`

완료 기준:
- 프론트 없이 curl로 최신 상태 조회 가능

### Phase 3. Provider 구현

순서:
1. Codex
2. Claude
3. Copilot

이 순서를 권장하는 이유:
- 현재 사용자 환경상 Codex/Claude가 WSL 홈과 더 직접 연결될 가능성이 높다.
- Copilot은 GitHub CLI 또는 토큰 확보 경로 정리가 추가로 필요하다.

완료 기준:
- 각 provider가 성공/인증실패/파싱실패 상태를 구분해 반환
- 최소 1개 이상의 fixture 테스트 보유

### Phase 4. 프론트엔드 대시보드

화면 구성:
- 전체 요약 헤더
- provider 카드 3개
- 각 카드에 plan, 마지막 갱신 시각, 상태, metrics 배열 표시
- 실패 시 오류 상태 표시
- 수동 새로고침 버튼

완료 기준:
- Windows 브라우저에서 현재 세 provider 상태를 한 페이지에서 확인 가능

### Phase 5. 운영 안정화

산출물:
- 로그 정리
- auth/refresh 실패 처리
- rate limit 방어
- 백엔드 자동 재시작 방식 문서화

완료 기준:
- 재시작 후 캐시 복구 가능
- provider 1개 실패가 전체 화면을 망치지 않음

## 6. 주요 리스크와 대응

### 리스크 1. Reverse-engineered API 변경

문제:
- Codex, Claude 문서가 모두 비공식/역공학 기반이다.

대응:
- 원본 응답 저장
- 파서와 정규화 단계 분리
- 필수 필드 누락 시 provider만 degraded 상태로 표시

### 리스크 2. 인증 저장 위치 차이

문제:
- Codex는 `~/.codex/auth.json` 또는 다른 경로를 쓸 수 있고, Claude/Copilot도 저장 위치가 다르다.

대응:
- 경로 탐색 순서를 설정 가능한 strategy로 분리
- 초기엔 파일 기반 경로를 우선 지원
- 키체인 전용 경로는 초기 범위에서 제외하거나 별도 후속 과제로 둔다

### 리스크 3. WSL과 Windows 브라우저 연결 이슈

문제:
- 바인딩 주소와 포트 접근 방식이 환경마다 다를 수 있다.

대응:
- 기본 `127.0.0.1` 우선
- 필요 시 `0.0.0.0` 옵션 제공
- 실행 가이드에 Windows 접속 방법 명시

### 리스크 4. Copilot 인증 의존성

문제:
- 문서상 `gh auth login` 또는 저장된 GitHub 토큰 경로가 필요하다.

대응:
- 초기 계획서에 사전 조건으로 명시
- 백엔드는 Copilot만 독립 실패 처리

### 리스크 5. 요금제/메트릭 구조 변경

문제:
- provider가 메트릭 필드를 추가, 삭제, 이름 변경할 수 있다.

대응:
- 메트릭 배열 중심 모델 채택
- 정규화되지 않은 추가 필드는 `meta`에 보존
- 플랜 이름/한도표를 코드에 상수로 두지 않음

## 7. MVP 범위와 후속 범위

### MVP 범위

- WSL 백엔드 실행
- Windows 브라우저 대시보드 접속
- Codex, Claude, Copilot 3개 provider 지원
- 최신 사용량 조회
- 마지막 성공 상태 캐시
- 수동 새로고침
- 기본 자동 polling
- provider별 오류 상태 분리 표시

### MVP 제외

- 로그인 UI
- 알림 시스템
- 장기 히스토리 차트
- provider 정렬/그룹화 설정
- 다중 사용자 지원
- Windows 네이티브 tray 앱

### 후속 범위

- provider 추가용 manifest/registry
- 일별 사용량 히스토리 그래프
- provider enable/disable 설정 UI
- `.env` 또는 설정 파일 기반 poll interval 변경
- Copilot/Claude/Codex 외 provider 플러그인화
- Windows 시작 시 자동 실행

## 권장 1차 의사결정

구현 전 아래를 확정하면 이후 속도가 빨라진다.

1. 백엔드는 Python FastAPI로 간다.
2. 프론트는 React + TypeScript로 간다.
3. 저장소는 SQLite로 간다.
4. 초기 인증 경로는 WSL 파일 기반만 우선 지원한다.
5. UI는 provider별 카드 3개를 보여주는 단일 페이지부터 시작한다.

## 1차 완료 기준

다음 조건을 만족하면 계획 단계 종료로 본다.

- 새 프로젝트 디렉터리 생성 완료
- 아키텍처와 데이터 모델 정의 완료
- 초기 provider 범위와 확장 전략 정의 완료
- 구현 순서와 MVP 범위가 문서화됨
- 다음 단계에서 바로 스캐폴딩 작업을 시작할 수 있음
