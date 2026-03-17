# bamboo_spec_generator

초기 설계를 바탕으로 한 샘플 생성기 구현이 포함되어 있습니다. 현재 샘플은 `build_info_json/` 아래의 연도별 JSON 파일을 읽어 하나의 Bamboo Specs 샘플 프로젝트를 루트의 `bamboo-specs/` 아래에 생성합니다.

## 실행

```bash
PYTHONPATH=. python3 -m src.bamboo_spec_generator.cli
```

출력 경로를 바꾸려면 다음처럼 실행합니다.

```bash
PYTHONPATH=. python3 -m src.bamboo_spec_generator.cli --output-root bamboo-specs
```

## 테스트

```bash
PYTHONPATH=. python3 -m unittest discover -s tests
```
