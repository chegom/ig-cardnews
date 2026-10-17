# ig-cardnews

인스타그램 카드뉴스 캐러셀을 **내용과 이미지까지 자동으로** 만드는 파이프라인입니다.
주제와 카피를 JSON에 적으면 배경 사진은 생성 모델이 그리고, 한글은 Pillow가 1픽셀 단위로 올려
1080×1350 카드 8장을 뽑아냅니다.

```
scene_plan.json ──▶ 배경 생성 (gpt-image-2 / FLUX) ──▶ QC ──▶ 실패분만 재생성
                                                              │
copy.json ──────────────────────────────────────────▶ 합성 ──▶ cards/01~08.jpg
```

## 지금 되는 것

- **배경 이미지 자동 생성** — gpt-image-2(기본) 또는 로컬 FLUX
- **must_have 기반 QC** — 장면마다 들어가야 할 요소를 적어두고, 빠진 장만 다른 엔진으로 재생성
- **한글 타이포 합성** — 레이아웃 7종, 줄바꿈·자간·블록 위치를 코드가 계산
- **화면 캡처 배경** — 제품 소개용으로 웹페이지 캡처를 잘라 카드 배경으로 매팅

## 예정

- **인스타그램 자동 발행** — Graph API로 캐러셀을 바로 올리는 단계.
  `src/instacards/instagram.py`와 `hosting.py`에 코드가 들어 있지만 아직 실사용 검증 전입니다.
  현재 버전은 로컬에 카드 이미지를 만드는 데까지를 보장합니다.
- 캡션·해시태그 생성
- 발행 예약

## 왜 이렇게 만들었나

생성 모델에 한글을 맡기면 글자가 깨집니다. 그래서 **그림과 글자의 역할을 완전히 분리**했습니다.
모델은 텍스트가 전혀 없는 사진만 그리고, 승인된 문구는 Pillow가 정확히 올립니다.
덕분에 오타가 날 수 없고, 카피만 고쳐 다시 합성하면 이미지를 새로 뽑을 필요가 없습니다.

## 설치

```bash
git clone https://github.com/chegom/ig-cardnews
cd ig-cardnews
python3 -m venv .venv && .venv/bin/pip install -e .
```

배경 생성기는 둘 중 하나를 고릅니다.

| 엔진 | 준비물 | 비용 |
|---|---|---|
| **gpt-image-2** (기본) | `npm i -g @openai/codex && codex login` | ChatGPT 사용량 차감 |
| **FLUX** (선택) | ComfyUI + FLUX 모델, `fluxctl` | 무료 (자기 GPU) |

FLUX를 쓸 때만 환경변수가 필요합니다.

```bash
export FLUXCTL_BIN=/path/to/fluxctl
export COMFYUI_URL=http://127.0.0.1:8188
```

## 사용법

### 1. 배경 만들기

```bash
python scripts/render_auto_plan.py examples/cardnews/scene_plan.json jobs/demo/bg
python scripts/render_auto_plan.py examples/cardnews/scene_plan.json jobs/demo/bg --engine flux
```

### 2. 검수하고 필요한 장만 다시 뽑기

`jobs/demo/bg/qc/`에 컨택트 시트와 체크리스트가 생깁니다.
장면 플랜의 `must_have`와 대조해, 요소가 빠진 장만 지정합니다.

```bash
python scripts/render_auto_plan.py examples/cardnews/scene_plan.json jobs/demo/bg --escalate s04,s06
```

두 엔진의 차이는 선명도가 아니라 **프롬프트 준수**에서 갈립니다.
"안개 낀 계곡"을 주문했는데 밝은 숲이 나오는 실패는 픽셀 지표로 잡히지 않습니다.
실제로 한 장면은 FLUX 쪽 디테일 수치가 1.45배 높았는데도 지시를 안 따라 탈락했습니다.
그래서 판정 기준을 "예쁜가"가 아니라 `["계곡 물", "안개", "텐트 1동"]` 같은 체크리스트로 둡니다.

### 3. 카드 합성

```bash
python scripts/compose_tips_carousel.py \
  examples/cardnews/copy.json examples/cardnews/backgrounds.json jobs/demo/final
```

`jobs/demo/final/cards/01~08.jpg`와 컨택트 시트가 나옵니다.

## 카피 JSON

```jsonc
{
  "brand": "TRAVEL LOG",      // 상단 가운데 워터마크
  "accent": "#F0803C",        // 포인트 컬러 — 주제에 맞게 교체
  "slides": [
    { "slide_id": "s01", "layout": "cover", "badge": "TRAVEL | CAMPING",
      "title": "두 줄까지\n들어갑니다" }
  ]
}
```

| 레이아웃 | 쓰임 |
|---|---|
| `cover` | 표지. 알약 배지 + 초대형 헤드라인 |
| `photo_story` | 제목 + 본문 |
| `prompt` | 제목 + 반투명 코드 박스 (명령어·예시) |
| `points` | 제목 + 번호 매긴 항목 |
| `caution` | 제목 + 사각 불릿 항목 |
| `outro` | 닫는 장. 팔로우 버튼 + 핸들 |
| `brandcard` | 사진 없는 미니멀 브랜드 카드 |

| 옵션 키 | 설명 |
|---|---|
| `grade_brightness` · `grade_saturation` · `grade_contrast` | 배경 사진 보정. 밝은 사진을 어두운 세트에 맞출 때 |
| `veil` · `scrim_lead` | 스크림 세기와 시작 지점. 화면 캡처 배경이면 `veil: 0` |
| `handle` · `button` | 마지막 장의 계정명과 버튼 문구 |

내지 텍스트 블록은 모두 같은 y에서 시작하고(`INTERIOR_TOP`), 하한선(`INTERIOR_FLOOR`)을
넘으면 자동으로 당겨집니다. 카피 길이가 달라져도 넘길 때 글자 위치가 흔들리지 않습니다.

## 폰트

Pretendard(Bold/Regular)를 저장소에 포함했습니다. SIL Open Font License 1.1입니다.
이모지 글리프는 없으므로 카피에 이모지를 넣으면 네모로 깨집니다.

## 테스트

```bash
.venv/bin/python -m pytest -q
```

## 라이선스

코드는 MIT. 폰트는 OFL 1.1 (`assets/fonts/Pretendard-OFL.txt`).
