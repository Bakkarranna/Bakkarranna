import re, os
name = [f for f in os.listdir('.') if f.endswith('ascii.svg')][0]
t = open(name, encoding='utf-8').read()
print('HEAD:', t[:200].replace('\n', ' '))
rows = re.findall(r'<text[^>]*x="([\d.]+)"[^>]*y="([\d.]+)"[^>]*>([^<]*)</text>', t)
print('rows:', len(rows))
xs = [float(x) for x, _, _ in rows]
print('x range:', min(xs), max(xs))
print('widths:', re.findall(r'width="([\d.]+)"', t))
print('row lens:', [len(s) for _, _, s in rows[:6]], '...', [len(s) for _,_,s in rows[-3:]])
print('sample:', repr(rows[10][2][:60]))
tm = re.search(r'<text[^>]*font-size="([\d.]+)"', t)
print('font-size:', tm.group(1) if tm else None)
