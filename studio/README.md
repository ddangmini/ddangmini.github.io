# Static Hour Shorts 수익화 파이프라인

기존 n8n 업로더(SlaticHour Uploader) 앞단에 붙는 **대본 → 정책 검사 → 렌더 → 업로드 대기열** 파이프라인과 수익 예측기.

## 왜 이 구조인가

| 사실 | 함의 |
|---|---|
| Shorts 광고 RPM ≈ $0.03–0.20 / 1,000뷰 | 광고만으로는 월 수백만 뷰여도 수십 달러 수준 |
| YPP 광고 수익 조건: 구독 1,000 + 90일 Shorts 1,000만 뷰, **2027-02-01 신청분부터 2,000만 뷰** | 신규 채널은 1년 내 광고 수익 진입이 어려움 |
| 2025-07 "inauthentic content" 정책, 2026-07 명확화(템플릿 반복물·건강/금융 AI 페르소나 수익화 불가) | 대량 자동 생성은 채널 전체가 YPP에서 제외될 위험 |

따라서 수익원 우선순위를 **① 설명란·고정댓글 링크(제휴/자체 상품, 1일차부터 발생) → ② YPP 광고(도달 시 보너스)** 로 두고,
자동화는 "양"이 아니라 **포맷 실험 속도**와 **정책 리스크 차단**에 씁니다.

`forecast` 기본 가정(일 2편, 편당 800뷰 시작, 월 25% 성장)으로 1년 순이익 약 $980, 낙관 가정(일 3편, 편당 5,000뷰, 월 35%)은 약 $13,300 — 두 경우 모두 **수익 100%가 링크에서** 나오고 광고는 기간 내 0입니다. 링크 클릭률(0.15%)·전환율(3%)·건당 수수료($8)는 검증되지 않은 가정이므로 실제 수치로 교체하세요.

## 구성

```
factory/
  writer.py    Claude(claude-opus-5-5) 구조화 출력으로 대본 생성 — 출처·채널 관점(perspective) 필수
  guard.py     과거 영상과 대본/제목 유사도, 관점·출처 누락, AI 음성 + 건강/금융 주제 차단
  render.py    Pillow 자막 카드 + ffmpeg → 1080x1920 mp4, 썸네일 (TTS 명령은 설정으로)
  planner.py   Studio 분석 CSV(제목·조회수)로 포맷별 톰슨 샘플링 → 다음 포맷 선택
  revenue.py   일 단위 시뮬레이션(YPP 규칙 변경일 반영)
  cli.py       make / plan / forecast
```

## 사용법

```bash
cd studio
pip install -r requirements.txt edge-tts      # TTS는 선택
cp config.example.json config.json            # niche, formats, links, font_path 수정
export ANTHROPIC_API_KEY=...

python -m factory make --count 3 [--analytics studio_export.csv]
python -m factory plan --analytics studio_export.csv
python -m factory forecast --set uploads_per_day=3 --set link_payout_usd=5
python -m factory make --dry-run              # API 없이 샘플로 렌더 확인
python -m pytest -q tests
```

`make` 결과는 `outbox/<id>/`에 `video.mp4`, `thumbnail.jpg`, `meta.json`(videos.insert 본문 그대로: snippet/status, `containsSyntheticMedia` 포함), `READY` 마커로 생성됩니다.
n8n 워크플로는 `READY`가 있는 폴더를 읽어 기존 videos.insert → thumbnails.set 순서로 올리고 폴더를 삭제하면 됩니다. 기본 `privacyStatus`는 `private`이니 검수 후 공개로 바꾸거나 설정에서 변경하세요.

## 운영 원칙

- 하루 2–3편, 포맷 3–4개를 돌리며 2주마다 `plan`으로 상위 포맷에 집중
- 대본은 업로드 전 사람이 한 번 읽고 사실 확인(출처는 `script.json`에 남음)
- 제휴 링크는 표시 문구 자동 삽입(공정위 추천·보증 심사지침), 링크는 영상 주제와 실제로 관련된 상품만
- 이 폴더는 `_config.yml`로 GitHub Pages 배포에서 제외되지만 **저장소가 공개라면 코드는 공개**됩니다. `config.json`은 `.gitignore` 처리됨
