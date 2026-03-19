# Example Skill

데모용 예시 스킬입니다. `/autoimprove` 테스트에 사용됩니다.

## Trigger

```
/example <message>
```

`$ARGUMENTS`의 첫 번째 인자를 `message`로 사용합니다.

## Workflow

1. 사용자 입력(`message`) 읽기
2. 메시지를 대문자로 변환
3. 결과를 "Echo: <변환된 메시지>" 형식으로 출력

## Output Format

```
Echo: <UPPERCASED MESSAGE>
```

## Rules

- Do NOT 빈 메시지를 처리하지 않는다 — 오류 메시지를 반환
- Do NOT 500자 이상의 메시지를 허용하지 않는다

## Examples

```bash
# 기본 사용
/example hello world
# → Echo: HELLO WORLD

# 한국어
/example 안녕하세요
# → Echo: 안녕하세요
```

주의: 한국어는 대소문자 변환이 적용되지 않으며 원문 그대로 반환됩니다.
