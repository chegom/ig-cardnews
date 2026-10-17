# Instacards

내 Mac의 **FLUX.2 Klein + ComfyUI**로 1080×1350 카드뉴스를 만들고, 공개 이미지 호스팅을 거쳐 Instagram 프로페셔널 계정에 캐러셀로 발행하는 로컬 자동화입니다.

## 구성

- 배경 생성: **gpt-image-2**(기본, Codex CLI) 또는 **FLUX**(선택, 로컬 ComfyUI)
- 한글 폰트: Pretendard(OFL 1.1), 프로젝트에 라이선스와 함께 포함
- FLUX를 쓸 경우 `FLUXCTL_BIN`과 `COMFYUI_URL` 환경변수로 경로를 지정합니다

## 흐름

1. `campaign.json`에 카드별 제목, 본문, 이미지 프롬프트를 작성합니다.
2. `fluxctl`이 ComfyUI의 FLUX.2 Klein 워크플로를 실행합니다.
3. 생성 이미지에는 글자를 맡기지 않고, Pillow가 승인된 문구를 정확히 합성합니다.
4. JPEG 카드를 Cloudinary 또는 지정한 공개 HTTPS 디렉터리에 올립니다.
5. Instagram API가 단일 이미지 또는 최대 10장의 캐러셀로 발행합니다.

## 시작

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
cp .env.example .env
```

ComfyUI를 실행합니다.

```bash
cd /path/to/comfyui
python main.py --listen 127.0.0.1 --port 8188
```

연결 상태를 확인합니다.

```bash
.venv/bin/instacards doctor
```

빠른 레이아웃 미리보기는 FLUX를 호출하지 않습니다.

```bash
.venv/bin/instacards render examples/campaign.json --draft --force
```

실제 FLUX 배경으로 렌더합니다.

```bash
.venv/bin/instacards render examples/campaign.json --force
```

완성 이미지는 `output/<slug>/production/cards/`에 저장됩니다. 빠른 초안은 `output/<slug>/draft/`로 완전히 분리됩니다. 같은 명령을 다시 실행하면 같은 모드의 기존 배경과 카드를 재사용하고, `--force`를 붙였을 때만 다시 생성합니다.

## 실제 Instagram 발행

Instagram 프로페셔널 계정과 Meta 앱이 필요합니다. Instagram 로그인 방식은 `instagram_business_basic`, `instagram_business_content_publish` 권한과 Instagram 사용자 액세스 토큰을 사용합니다. 이미지 파일은 게시 시 Meta 서버가 가져갈 수 있는 공개 HTTPS URL에 있어야 합니다.

`.env`에 다음 값을 설정합니다.

```dotenv
INSTAGRAM_USER_ID=...
INSTAGRAM_ACCESS_TOKEN=...
INSTAGRAM_API_VERSION=v26.0
```

기본 호스팅은 Cloudinary signed upload입니다.

```dotenv
MEDIA_HOST=cloudinary
CLOUDINARY_CLOUD_NAME=...
CLOUDINARY_API_KEY=...
CLOUDINARY_API_SECRET=...
CLOUDINARY_FOLDER=instacards
```

이미 운영 중인 웹 디렉터리가 있다면 다음처럼 쓸 수 있습니다.

```dotenv
MEDIA_HOST=static
MEDIA_PUBLIC_DIR=/absolute/path/to/public/instacards
MEDIA_PUBLIC_BASE_URL=https://example.com/instacards
```

미리보기까지만 하는 기본 실행:

```bash
.venv/bin/instacards run examples/campaign.json
```

실제 업로드와 발행까지 하는 실행:

```bash
.venv/bin/instacards run examples/campaign.json --publish
```

`--publish`가 없으면 Instagram 상태는 절대 변경하지 않습니다. `--draft`로 만든 테스트 배경은 발행할 수 없도록 막았습니다.

## 운영 권장사항

- 첫 운영은 테스트용 프로페셔널 계정으로 2장짜리 캐러셀부터 확인하세요.
- 액세스 토큰은 `.env` 밖으로 복사하지 말고, 저장소에 커밋하지 마세요.
- 예약 발행은 macOS `launchd`나 CI에서 `instacards run ... --publish`를 호출하면 됩니다.
- Instagram API는 현재 한 게시물에 최대 10개 슬라이드를 지원하며, 이미지 게시 형식은 JPEG입니다.
- 이 파이프라인은 AI 생성 카드의 부모 컨테이너에 `is_ai_generated=true`를 설정합니다.

공식 문서: [Instagram 콘텐츠 게시](https://developers.facebook.com/documentation/instagram-platform/content-publishing)

## 카드뉴스 캐러셀 생성기

`instacards`의 레이아웃 엔진 위에 올린, 8장짜리 인스타그램 캐러셀 제작 흐름입니다.
배경 사진은 생성 모델이 만들고, 한글은 Pillow가 정확히 올립니다.

### 1. 배경 만들기

기본은 **gpt-image-2**입니다. Codex CLI와 ChatGPT 로그인만 있으면 되고 API 키는 필요 없습니다.

```bash
npm install -g @openai/codex && codex login
python scripts/render_auto_plan.py examples/cardnews/scene_plan.json jobs/demo/bg
```

GPU가 있고 ComfyUI에 FLUX 모델을 띄워 뒀다면 무료로 돌릴 수 있습니다.

```bash
export FLUXCTL_BIN=/path/to/fluxctl
export COMFYUI_URL=http://127.0.0.1:8188
python scripts/render_auto_plan.py examples/cardnews/scene_plan.json jobs/demo/bg --engine flux
```

### 2. 검수하고 필요한 장만 다시 뽑기

렌더가 끝나면 `jobs/demo/bg/qc/`에 컨택트 시트와 체크리스트가 생깁니다.
장면 플랜의 `must_have` 항목과 대조해, 빠진 요소가 있는 장만 다른 엔진으로 재생성합니다.

```bash
python scripts/render_auto_plan.py examples/cardnews/scene_plan.json jobs/demo/bg --escalate s04,s06
```

두 엔진의 차이는 선명도가 아니라 **프롬프트 준수**에서 갈립니다.
"안개 낀 계곡"을 주문했는데 밝은 숲이 나오는 식의 실패는 픽셀 지표로 잡히지 않으므로,
장면마다 눈으로 확인할 수 있는 `must_have` 목록을 적어 두는 쪽이 확실합니다.

### 3. 카드 합성

```bash
python scripts/compose_tips_carousel.py \
  examples/cardnews/copy.json examples/cardnews/backgrounds.json jobs/demo/final
```

`jobs/demo/final/cards/01~08.jpg`(1080×1350)와 컨택트 시트가 나옵니다.

### 카피 JSON

| 키 | 설명 |
|---|---|
| `brand` | 상단 가운데 워터마크 |
| `accent` | 포인트 컬러 (키커·번호·버튼). 주제에 맞게 바꿉니다 |
| `layout` | `cover` · `photo_story` · `prompt` · `points` · `caution` · `outro` · `brandcard` |
| `badge` | 표지는 알약, 내지는 평문 키커로 렌더됩니다 |
| `grade_brightness` / `grade_saturation` / `grade_contrast` | 배경 사진 보정 |
| `veil` / `scrim_lead` | 스크림 세기와 시작 지점 (화면 캡처 배경일 때 조절) |
| `handle` / `button` | 마지막 장의 계정명과 팔로우 버튼 |

내지 텍스트 블록은 모두 같은 y에서 시작하고(`INTERIOR_TOP`), 하한선(`INTERIOR_FLOOR`)을
넘지 않도록 자동으로 당겨집니다.

### 폰트

Pretendard(Bold/Regular)를 저장소에 포함했습니다. SIL Open Font License 1.1입니다.
이모지 글리프는 없으므로 카피에 이모지를 넣으면 네모로 깨집니다.
