---
name: ig-cardnews-visual
description: >-
  인스타그램 카드뉴스의 비주얼/레이아웃을 만들고 검수하는 스킬. 주제·카피가 정해진 뒤,
  1080×1350 캐러셀 카드의 배경·한글 타이포 합성·레이아웃·품질 감사를 담당한다.
  "카드뉴스 디자인", "카드 레이아웃", "제목/본문 크기", "그라데이션", "글 길이별 디자인",
  "카드 품질 감사", "대비/오버플로 검사" 같은 비주얼 작업에 사용한다.
  카피 작성(글쓰기)·주제 리서치/분석은 이 스킬 소관이 아니다(별도 스킬).
---

# ig-cardnews — 비주얼/디자인 스킬

주제와 승인된 카피(JSON)를 받아 **배경 이미지 생성 → 한글 타이포 합성 → 품질 감사**까지
비주얼만 책임진다. 생성 모델엔 텍스트 없는 사진만 맡기고, 한글은 Pillow가 1픽셀 단위로 얹는다.

## 범위

- **한다**: 레이아웃/타이포/색/그라데이션, 글 길이별 디자인, 카드 품질 감사(대비·오버플로·과밀·furniture).
- **안 한다**: 카피 문구 작성, 주제 리서치·내용 분석 (각각 별도 스킬).

## 작업 전에 읽을 것

- `README.md` — 파이프라인 전체 흐름, 설치, CLI(`instacards render/run/audit`).
- [`references/card-length-design-guide.md`](references/card-length-design-guide.md) —
  **글 길이별 제목/본문/배지 크기·텍스트 위치·그라데이션 기준.** 어느 렌더러 파일을 편집할지,
  실제 코드 상수값(검증됨)과 아직 미반영 제안을 분리해 정리.

## 렌더러 지도 (편집 전 대상 확인)

- `src/instacards/composer.py` — `instacards` CLI 캐노니컬 경로(`campaign.json`).
- `src/instacards/tips.py` + `cover.py` — 풀블리드 "AI tips" 캐러셀(`scripts/compose_tips_carousel.py`).
  글 길이별 가이드의 상수(`INTERIOR_TOP`, `KICKER_SIZE`, `TITLE_BODY_GAP`, 그라데이션 등)가 여기 있다.
- `src/instacards/probe.py` — 풀블리드 프로브 합성기(감사 연결됨). `editorial.py` — 교육형(감사 미연결, 남은 작업).
- **composer · tips/cover · probe** 가 카드별 `NN.layout.json`을 내보내고 같은 품질 감사(`src/instacards/audit.py`)가 판정한다.
  (레이아웃 요소 기록은 `src/instacards/layout_record.py` 공유 레코더로.)

## 품질 감사 게이트

합성된 카드를 실측해 대비(WCAG)·안전영역 이탈·과밀·브랜드 위치를 빨강/노랑/초록으로 판정한다.
빨강이 하나라도 있으면 실패(exit 1).

```bash
# composer 경로 (instacards CLI, campaign.json)
instacards render examples/campaign.json --audit   # 렌더 + 감사
instacards audit  examples/campaign.json            # 이미 렌더된 카드만 감사

# tips 캐러셀 경로 (scripts)
python scripts/compose_tips_carousel.py <spec> <backgrounds> <out> --audit
```

임계값은 `--rules audit_rules.json`으로 덮어쓴다(예: `examples/audit_rules.json`).
구현은 `src/instacards/audit.py`, README의 "비주얼 품질 감사(audit)" 절 참고.
