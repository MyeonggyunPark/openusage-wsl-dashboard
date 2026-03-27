# OpenUsage WSL Dashboard 계획서

## 1. 프로젝트 개요

이 프로젝트는 `OpenUsage`의 핵심 가치인 "여러 AI 코딩 도구 사용량을 한 곳에서 본다"를 유지하되, 실행 환경을 `macOS 메뉴바 앱`이 아니라 `WSL Ubuntu 백엔드 + Windows 브라우저 UI`로 재구성하는 것을 목표로 한다.

초기 대상 provider는 다음 3개다.

- `codex`
- `claude`
- `copilot`

프로젝트의 핵심 요구는 단순 조회 앱이 아니다. 다음 두 조건이 반드시 충족되어야 한다.

- 이후 provider가 추가되어도 구조 변경 없이 probe만 추가 가능해야 한다.
- 각 provider의 요금제, 사용량 한도, 추가 크레딧, 리셋 규칙이 바뀌어도 하드코딩 수정이 최소화되어야 한다.

## 2. 목표와 비목표

### 목표

- WSL Ubuntu에서 동작하는 사용량 수집 백엔드 구현
- Windows 브라우저에서 확인 가능한 로컬 대시보드 제공
- `codex`, `claude`, `copilot` 3개 provider 사용량 표시
- provider별 인증 정보와 상태를 WSL 환경에서 읽고 정규화
- 로컬 HTTP API 제공
- provider 추가를 위한 플러그인형 구조 설계
- 요금제/한도 변경에 대응 가능한 응답 기반 메트릭 모델 설계

### 비목표

- macOS 메뉴바 UX 복제
- Windows 시스템 트레이 앱을 이번 단계에서 직접 구현
- 모바일 대응
- 계정 로그인 UI 내장
- 원격 서버 배포

## 3. 기본 제약과 전제

- 실제 개발과 실행의 기준 환경은 WSL Ubuntu다.
- 화면은 Windows 브라우저에서 확인한다.
- provider API 일부는 비공식 또는 reverse-engineered일 수 있으므로, 실패와 스키마 변동을 정상 시나리오로 간주해야 한다.
- 인증 토큰 위치와 포맷은 provider별로 다르므로 공통 추상화가 필요하다.
- provider별 플랜 정보는 가능하면 응답값을 그대로 반영하고, 플랜별 하드코딩 분기를 최소화한다.

## 4. 근거가 되는 OpenUsage 관찰 내용

- 원본 앱은 로컬 HTTP API를 제공한다.
- provider별 probe 방식이 분리되어 있다.
- Codex, Claude는 reverse-engineered API 성격을 가진다.
- Copilot은 GitHub 토큰 기반 조회 구조다.
- 원본 macOS 앱은 패널/트레이 중심이므로 현재 목표 환경에는 직접 이식보다 재구성이 적합하다.

참고 문서:

- `https://github.com/robinebers/openusage/blob/main/README.md`
- `https://github.com/robinebers/openusage/blob/main/docs/local-http-api.md`
- `https://github.com/robinebers/openusage/blob/main/docs/providers/codex.md`
- `https://github.com/robinebers/openusage/blob/main/docs/providers/claude.md`
- `https://github.com/robinebers/openusage/blob/main/docs/providers/copilot.md`
- `https://github.com/robinebers/openusage/blob/main/docs/plugins/api.md`

## 5. 권장 기술 방향

초기 구현은 다음 조합을 권장한다.

- 백엔드: `Python 3.12+` + `FastAPI`
- 프론트엔드: `React` + `Vite` + `TypeScript`
- 저장소: `SQLite` 또는 경량 JSON 캐시
- 스케줄링: 백엔드 내부 polling job
- HTTP 통신: provider adapter 별 전용 client

### Python/FastAPI를 권장하는 이유

- WSL에서 실행과 디버깅이 간단하다.
- 백그라운드 수집기, 스케줄링, 파일 접근, 토큰 갱신 로직 구현이 수월하다.
- 로컬 HTTP API를 바로 열기 쉽다.
- 테스트 작성이 빠르다.

## 6. 목표 아키텍처

### 상위 구조

- `backend/`
  - provider probe 실행
  - 인증 정보 로드
  - 응답 정규화
  - 캐시 저장
  - 로컬 API 제공
- `frontend/`
  - provider 카드 UI
  - 상태/오류/마지막 갱신 시각 표시
  - 수동 새로고침
  - 자동 폴링
- `shared/` 또는 백엔드 기준 schema 모듈
  - 공통 데이터 모델
  - provider status enum
  - metric schema

### 런타임 흐름

1. 백엔드 시작
2. provider registry 로드
3. 각 provider probe 실행
4. 결과를 공통 schema로 정규화
5. 캐시 저장
6. 프론트엔드가 로컬 API 조회
7. 사용자 요청 또는 주기 도래 시 재수집

## 7. 핵심 설계 원칙

### 7.1 플랜 하드코딩 금지

`pro`, `plus`, `individual`, `team`, `free` 같은 플랜명을 UI 분기의 핵심 기준으로 쓰지 않는다.

대신:

- 플랜명은 표시용 문자열로만 취급
- 실제 UI 렌더링은 `metrics[]` 배열 기반으로 처리
- 응답에 없는 항목은 숨기고, 새 항목은 자동 노출 가능한 구조로 설계

### 7.2 메트릭 중심 정규화

공통 모델은 provider마다 달라지는 원본 응답을 직접 노출하지 않고, 다음 같은 형태로 정규화한다.

```json
{
  "providerId": "codex",
  "displayName": "Codex",
  "plan": "plus",
  "status": "ok",
  "fetchedAt": "2026-03-27T20:10:00Z",
  "metrics": [
    {
      "type": "progress",
      "label": "5h",
      "used": 12,
      "limit": 100,
      "unit": "percent",
      "resetsAt": "2026-03-27T23:00:00Z",
      "meta": {}
    }
  ],
  "warnings": []
}
```

### 7.3 실패는 데이터 모델의 일부

provider 실패는 예외가 아니라 정상 상태다.

각 provider는 최소 다음 상태 중 하나를 가져야 한다.

- `ok`
- `auth_missing`
- `auth_expired`
- `network_error`
- `provider_error`
- `parse_error`
- `unsupported_environment`

## 8. 백엔드 상세 설계

### 8.1 모듈 구조 초안

- `app/main.py`
- `app/api/routes_usage.py`
- `app/core/config.py`
- `app/core/scheduler.py`
- `app/core/cache.py`
- `app/models/usage.py`
- `app/providers/base.py`
- `app/providers/registry.py`
- `app/providers/codex.py`
- `app/providers/claude.py`
- `app/providers/copilot.py`
- `app/providers/shared/http.py`
- `app/providers/shared/auth.py`

### 8.2 Provider 인터페이스

모든 provider는 공통 인터페이스를 따른다.

- `load_credentials()`
- `refresh_credentials_if_needed()`
- `fetch_raw_usage()`
- `normalize_usage()`
- `probe()`

`probe()`는 최종적으로 정규화된 `ProviderUsageSnapshot`을 반환한다.

### 8.3 인증 처리

#### Codex

- `CODEX_HOME/auth.json`
- `~/.config/codex/auth.json`
- `~/.codex/auth.json`

우선순위대로 읽되, WSL 환경 기준으로 파일 저장 방식에 최적화한다.

#### Claude

- `~/.claude/.credentials.json`

토큰 만료 시 refresh 로직 포함.

#### Copilot

- WSL 내부의 `gh auth token` 활용 가능성 우선 검토
- 필요 시 별도 토큰 경로 지원

초기 구현에서는 "토큰 자동 탐색 + 실패 시 명확한 가이드 반환"이 중요하다.

### 8.4 캐시 전략

성공한 응답만 캐시에 반영한다.

- 마지막 성공 스냅샷 유지
- 일시적 실패 시 이전 성공값은 보존
- 오류 상태와 마지막 성공 시각을 함께 제공

### 8.5 스케줄링 전략

초기 기본값:

- 앱 시작 시 1회 전체 probe
- 5분 또는 15분 간격 자동 갱신
- 수동 갱신 endpoint 제공

후속 단계에서 provider별 개별 refresh도 지원할 수 있다.

## 9. 프론트엔드 상세 설계

### 9.1 페이지 구성

- 상단 요약 영역
- provider 카드 3개
- 마지막 동기화 시각
- 전체 새로고침 버튼
- provider별 상태 메시지

### 9.2 카드 정보

각 카드는 최소 다음을 보여준다.

- provider 이름
- 플랜 이름
- 주요 메트릭 진행률
- 리셋 시각 또는 다음 윈도우 정보
- 에러 또는 경고 상태
- 마지막 성공 조회 시각

### 9.3 렌더링 원칙

- provider별 UI 분기 최소화
- `metrics[]`를 순서대로 렌더링
- `progress`, `text`, `badge` 타입을 공통 컴포넌트로 처리

## 10. 로컬 API 초안

### `GET /api/v1/providers`

- 활성 provider 목록

### `GET /api/v1/usage`

- 전체 provider 현재 스냅샷 목록

### `GET /api/v1/usage/{provider_id}`

- 단일 provider 현재 스냅샷

### `POST /api/v1/refresh`

- 전체 refresh 트리거

### `POST /api/v1/refresh/{provider_id}`

- 단일 provider refresh 트리거

### `GET /api/v1/health`

- 앱 상태, 마지막 probe 요약

## 11. Provider 확장 전략

새 provider 추가 절차는 다음으로 고정한다.

1. 새 provider adapter 파일 추가
2. 인증 로더 구현
3. raw response parser 구현
4. 공통 schema normalize 구현
5. registry 등록
6. fixture 기반 테스트 추가

중요한 점은 프론트엔드는 provider 추가 시 수정이 거의 없어야 한다는 것이다.

## 12. 요금제 변경 대응 전략

요금제 변경 대응은 다음 규칙으로 처리한다.

- 플랜명은 provider 응답 원문을 우선 채택
- 한도 항목은 응답에 존재하는 윈도우/크레딧/보조 한도를 그대로 metric으로 변환
- 신규 한도 타입이 추가되면 normalize 레이어에서 metric 한 줄만 추가
- UI는 타입 기반 렌더링만 수행

즉, "플랜별 UI"가 아니라 "메트릭 기반 UI"로 설계해야 한다.

## 13. 보안 및 민감정보 원칙

- 액세스 토큰 원문은 로그에 남기지 않는다.
- 응답 원문 전체 저장 금지. 필요한 필드만 정규화 후 저장한다.
- 에러 메시지에는 경로/헤더/토큰을 직접 노출하지 않는다.
- 브라우저 UI에는 인증 정보 대신 상태만 노출한다.

## 14. 테스트 전략

### 백엔드

- provider별 parser 단위 테스트
- token refresh 로직 테스트
- cache 갱신 정책 테스트
- API endpoint 테스트

### 프론트엔드

- metric renderer 테스트
- provider 상태 카드 테스트
- 오류 상태 UI 테스트

### 회귀 방지

- provider별 fixture JSON 유지
- 응답 필드 변경을 빠르게 감지하는 parser 테스트 작성

## 15. 단계별 구현 계획

### Phase 1. 프로젝트 스캐폴딩

- 백엔드/프론트엔드 기본 구조 생성
- 공통 schema 정의
- 로컬 실행 환경 구성

### Phase 2. 백엔드 코어

- config
- scheduler
- cache
- registry
- 기본 API

### Phase 3. Provider 3종 구현

- codex adapter
- claude adapter
- copilot adapter

### Phase 4. 프론트엔드 MVP

- 대시보드 기본 화면
- provider 카드
- refresh UX
- 오류/경고 UI

### Phase 5. 검증 및 안정화

- fixture 테스트 보강
- 예외 케이스 정리
- polling 안정화

## 16. MVP 범위

MVP에서는 다음까지만 완료를 목표로 한다.

- WSL에서 백엔드 실행
- Windows 브라우저에서 접속 가능한 UI
- codex / claude / copilot 조회
- 5~15분 polling
- 수동 refresh
- 실패 상태 표시
- 마지막 성공 캐시 유지

## 17. 후속 범위

- provider enable/disable 설정 UI
- 정렬/핀 기능
- 히스토리 그래프
- 알림
- provider 추가용 manifest 기반 플러그인 시스템
- Windows tray wrapper

## 18. 주요 리스크와 대응

### 리스크 1. 비공식 API 변경

대응:

- parser와 normalize 레이어 분리
- fixture 기반 테스트 유지
- 오류를 전체 장애가 아닌 provider 단위 장애로 격리

### 리스크 2. 인증 저장 위치 차이

대응:

- provider별 다중 경로 탐색
- 경로 override 설정 지원
- 감지 실패 시 사용자 안내 메시지 제공

### 리스크 3. Copilot 인증 접근성

대응:

- `gh auth` 기반 탐색 우선
- 필요 시 토큰 환경변수 또는 명시 경로 지원

### 리스크 4. WSL과 Windows 브라우저 연결 문제

대응:

- 초기에는 `127.0.0.1` 또는 WSL 포트 포워딩 확인
- 로컬 개발 문서에 접속 경로를 명시

## 19. 완료 판단 기준

다음 조건을 만족하면 MVP 완료로 본다.

- 세 provider가 최소 1회 이상 정상 수집된다.
- provider 중 하나가 실패해도 나머지 provider는 정상 표시된다.
- 마지막 성공 스냅샷 보존이 동작한다.
- 브라우저 UI에서 플랜과 메트릭이 확인된다.
- 새 메트릭 추가 시 프론트엔드 구조 변경 없이 렌더링 가능하다.

## 20. 권장 다음 작업

다음 구현 단계는 아래 순서가 가장 적절하다.

1. 프로젝트 스캐폴딩
2. 공통 usage schema 정의
3. FastAPI 기본 API와 캐시 계층 구현
4. Codex provider부터 1개씩 붙이기
5. React 대시보드 연결

