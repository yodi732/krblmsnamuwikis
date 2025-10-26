#!/usr/bin/env python3
import io, os, sys, re

ROOT = os.path.dirname(os.path.abspath(__file__))
signup_path = os.path.join(ROOT, "templates", "signup.html")

TERMS_INC = '{% include "legal/_terms_body.html" %}'
PRIV_INC  = '{% include "legal/_privacy_body.html" %}'

def run():
    if not os.path.exists(signup_path):
        print("[!] templates/signup.html 이(가) 보이지 않습니다. 레포 루트에서 실행했는지 확인하세요.")
        sys.exit(1)

    with open(signup_path, "r", encoding="utf-8") as f:
        html = f.read()

    before = html

    # 가장 흔했던 자리표시 문구를 치환
    html = html.replace("여기에 서비스 이용약관 전문을 넣으세요.", TERMS_INC)
    html = html.replace("여기에 개인정보처리방침 전문을 넣으세요.", PRIV_INC)

    # 다른 형태로 남았을 수도 있는 문구까지 보수적으로 커버
    html = re.sub(r"여기에\s*서비스\s*이용약관\s*전문을\s*넣으세요[^\n<]*", TERMS_INC, html)
    html = re.sub(r"여기에\s*개인정보처리방침\s*전문을\s*넣으세요[^\n<]*", PRIV_INC, html)

    if html == before:
        print("[!] 자동 치환할 문자열을 찾지 못했습니다.")
        print("    signup.html에서 다음 두 줄을 알맞은 위치에 직접 넣어주세요:")
        print("    -", TERMS_INC)
        print("    -", PRIV_INC)
        sys.exit(2)

    with open(signup_path, "w", encoding="utf-8") as f:
        f.write(html)

    print("[OK] signup.html에 전문 include를 삽입했습니다.")

if __name__ == "__main__":
    run()
