# CI 설정 (준비됨 — 활성화만 하면 됨)

GitHub Actions 워크플로 파일(`.github/workflows/…`)은 `workflow` 스코프가 있는 토큰으로만
푸시할 수 있다. 현재 `gh` 토큰 스코프는 `gist, read:org, repo`뿐이라 자동 푸시가 막혀서,
아래 레시피를 문서로 보관해 둔다. 스코프만 열면 3단계로 켜진다.

## 활성화 (한 번만)

```bash
# 1) 토큰에 workflow 스코프 추가 (브라우저가 한 번 열려 승인)
gh auth refresh -h github.com -s workflow

# 2) 워크플로 파일 생성
mkdir -p .github/workflows
# 아래 YAML을 .github/workflows/test.yml 로 저장 (다음 섹션 내용 그대로)

# 3) 커밋 & 푸시
git add .github/workflows/test.yml
git commit -m "CI 추가: push/PR마다 pytest 실행"
git push origin main
```

> 대안: GitHub 웹에서 `Add file → Create new file`로 `.github/workflows/test.yml`을
> 만들어 아래 내용을 붙여넣으면 스코프 없이도 바로 켤 수 있다.

## `.github/workflows/test.yml`

```yaml
name: tests

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - name: Install
        run: |
          python -m pip install --upgrade pip
          pip install -e . pytest
      - name: Run tests
        run: pytest -q
```

깨끗한 venv에서 `pip install -e . pytest && pytest -q`로 재현 검증 완료 (46 passed).

## 그때까지 — 로컬 pre-push 훅

CI가 켜지기 전까지의 회귀 보호로 `.git/hooks/pre-push`가 설치돼 있다
(버전관리 대상 아님, 이 머신에서만 작동). **푸시 전에 `pytest`를 돌려 실패하면 푸시를 막는다.**

```bash
# 한 번만 건너뛰기
git push --no-verify

# 훅 제거
rm .git/hooks/pre-push
```
