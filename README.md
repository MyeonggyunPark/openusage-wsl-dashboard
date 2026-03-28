# OpenUsage WSL Dashboard

WSL Ubuntu에서 usage collector를 실행하고, Windows 브라우저에서 Codex, Claude, Copilot 사용량을 확인하는 로컬 대시보드 시작본이다.

## 현재 포함된 것

- FastAPI 기반 백엔드 골격
- provider adapter 구조
- `/api/v1/usage`, `/api/v1/refresh`, `/api/v1/health`
- React/Vite 기반 프론트엔드 골격
- 첨부 이미지 컨셉을 반영한 랜딩 + 운영 대시보드 UI
- 인증 정보가 없을 때도 화면을 확인할 수 있는 데모 모드

## 백엔드 실행

```bash
cd /home/m2cz/dev/openusage-wsl-dashboard
uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 6736
```

## 프론트엔드 실행

```bash
cd /home/m2cz/dev/openusage-wsl-dashboard/frontend
pnpm install
pnpm dev
```

기본 개발 프론트 주소는 `http://127.0.0.1:5173` 이다.

## 테스트

```bash
cd /home/m2cz/dev/openusage-wsl-dashboard
pytest
```
