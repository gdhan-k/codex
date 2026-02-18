# Webpage to Korean PDF

웹페이지 주소(URL)를 입력하면 페이지의 텍스트를 추출해 한국어로 번역하고 PDF로 저장하는 CLI 프로그램입니다.

## 설치

별도의 패키지 설치 없이 Python 3.10+에서 실행할 수 있습니다.

## 사용법

```bash
python webpage_to_korean_pdf.py "https://example.com" -o result.pdf
```

### 옵션

- `-o, --output`: 출력 PDF 경로 (기본값: `translated_webpage.pdf`)
- `--source-lang`: 원문 언어 코드 (기본값: `auto`)
- `--target-lang`: 번역 대상 언어 코드 (기본값: `ko`)

## 동작 방식

1. `urllib`로 웹페이지 HTML을 가져옵니다.
2. 표준 라이브러리 `HTMLParser`로 본문 텍스트를 추출합니다.
3. Google 번역 비공식 엔드포인트를 호출해 한국어로 번역합니다.
4. 번역 단계와 PDF 생성 단계의 진행률(%)을 콘솔에 표시합니다.
5. 내장 PDF writer 로직으로 번역 결과 PDF를 생성합니다.

## 참고

- PDF 줄바꿈 폭은 페이지 여백/폰트 크기를 기준으로 계산되어 오른쪽 잘림을 줄입니다.
4. 내장 PDF writer 로직으로 번역 결과 PDF를 생성합니다.

## 참고

- 번역 API 정책/네트워크 상태에 따라 실패할 수 있습니다.
- 일부 사이트는 봇 차단 정책으로 텍스트 추출이 어려울 수 있습니다.
