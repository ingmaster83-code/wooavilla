"""preview_page.py <상대경로> [글자수] - 빌드된 페이지 본문 텍스트를 한 줄로 출력"""
import html, re, sys

sys.stdout.reconfigure(encoding="utf-8")
p = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 1800
s = open(p, encoding="utf-8").read()
title = re.search(r"<title>(.*?)</title>", s, re.S).group(1)
body = s[s.find("<main"):s.find("</main>")]
t = re.sub(r"<script.*?</script>|<style.*?</style>", "", body, flags=re.S)
t = re.sub(r"<[^>]+>", "|", t)
t = re.sub(r"\|[\s|]*\|", "|", t)
t = re.sub(r"\s+", " ", t)
print("TITLE:", title)
print(html.unescape(t)[:n])
