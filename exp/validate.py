import json,re,sys,collections
path=sys.argv[1]
D=[json.loads(l) for l in open(path,encoding='utf-8')]
fails=[];warns=[]
def F(m):fails.append(m)
def W(m):warns.append(m)
ST={'open','full','fulfilled','canceled'};LV={'L1','L3'};LG={'ZH','EN','MIX'}
if len(D)!=72:F(f'rows={len(D)}')
ids=[o['id'] for o in D]
if ids!=['A%02d'%i for i in range(1,73)]:F('ids not A01..A72 in order')
for o in D:
    i=o['id'];c=o['conversation']
    if set(o)-{'id','conversation','first_request','gold_status','level','lang','scenario','split','revised'}:F(f'{i}: unexpected fields')
    if o['gold_status'] not in ST:F(f'{i}: status {o["gold_status"]}')
    if o['level'] not in LV:F(f'{i}: level')
    if o['lang'] not in LG:F(f'{i}: lang')
    if o['first_request']!='m-03':F(f'{i}: first_request')
    if len(c)!=12:F(f'{i}: {len(c)} messages');continue
    for n,m in enumerate(c,1):
        if not m.startswith('m-%02d  '%n) and not m.startswith('m-%02d '%n):F(f'{i}: message {n} numbering')
        for tag in re.findall(r'\[[^\]]*m-\d\d\]',m):
            mm=re.fullmatch(r'\[reply m-(\d\d)\]',tag)
            if not mm:F(f'{i} m-{n:02d}: bad marker {tag}')
            elif not 1<=int(mm.group(1))<n:F(f'{i} m-{n:02d}: marker {tag} points forward/invalid')
    m9=c[8];mm=re.search(r'\[reply (m-\d\d)\]',m9)
    tgt=mm.group(1) if mm else None
    if o['level']=='L1' and tgt!='m-03':F(f'{i}: L1 but m-09 replies {tgt}')
    if o['level']=='L3' and tgt!='m-07':F(f'{i}: L3 but m-09 replies {tgt}')
    if o['level']=='L3' and '[reply m-03]' not in c[6]:F(f'{i}: L3 but m-07 does not reply m-03')
    sp=lambda m:m.split()[1].rstrip(':')
    if sp(c[2])!=sp(c[8]):W(f'{i}: m-03 speaker {sp(c[2])} != m-09 speaker {sp(c[8])}')
    blob=' '.join(c)
    if re.search(r'gold|STATUS:|gold_status|\bL[13]\b',blob):F(f'{i}: possible label leakage in text')
    body=lambda m:re.sub(r'^m-\d\d\s+\w+:\s*','',re.sub(r'\[reply m-\d\d\]','',m))
    cjk=lambda s:bool(re.search(r'[一-鿿]',s));lat=lambda s:re.findall(r'[A-Za-z]{2,}',s)
    if o['lang']=='EN' and any(cjk(body(m)) for m in c):W(f'{i}: EN contains CJK')
    if o['lang']!='EN' and re.search(r'reply',re.sub(r'\[reply m-\d\d\]','',blob)):W(f'{i}: "reply" inside ZH/MIX message text')
    if o['lang']=='ZH':
        bad=[(n+1,lat(body(m))) for n,m in enumerate(c) if lat(body(m))]
        bad=[b for b in bad if b[0]!=10]
        if bad:W(f'{i}: ZH contains Latin words {bad}')
    if o['lang']=='MIX':
        if not lat(body(c[8])):W(f'{i}: MIX but m-09 has no English word')
        if not any(cjk(body(m)) for m in c):W(f'{i}: MIX has no Chinese')
        if sum(1 for m in c if not cjk(body(m)))>6:W(f'{i}: MIX has many non-Chinese-matrix messages')
cell=collections.Counter((o['gold_status'],o['level']) for o in D)
if any(cell[(s,l)]!=9 for s in ST for l in LV):F(f'Status x Level not 9 each: {dict(cell)}')
if collections.Counter(o['lang'] for o in D)!={'ZH':24,'EN':24,'MIX':24}:F('lang not 24 each')
sc=collections.Counter(o['scenario'] for o in D)
if set(sc.values())!={6}:F(f'scenario counts {dict(sc)}')
if len({(o['scenario'],o['level'],o['lang']) for o in D})!=72:F('scenario x level x lang not unique')
print('FAIL:',len(fails));[print('  ✗',x) for x in fails]
print('WARN:',len(warns));[print('  !',x) for x in warns]
print('PASS' if not fails else 'NOT PASSED')
sys.exit(1 if fails else 0)
