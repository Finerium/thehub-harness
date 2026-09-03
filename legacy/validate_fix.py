import os, re, subprocess, statistics, datetime, difflib
from collections import Counter
import openpyxl

BASE = "/home/claude/caliber_case/CALIBER 2026 - The Case/Supporting Data/Case 1_ Manufacturing Knowledge Hub"
opl_files=[]
for root,dirs,files in os.walk(BASE):
    if "__MACOSX" in root: continue
    for f in files:
        if f.startswith("._"): continue
        if re.match(r'OPL-',f) and f.endswith('.pdf'): opl_files.append(os.path.join(root,f))

wb = openpyxl.load_workbook(os.path.join(BASE,"Maintenance History (All Equipment).xlsx"), data_only=True)
ws = wb['Maintenance History (All Equipm']
hdr=[c.value for c in ws[1]]; idx={h:i for i,h in enumerate(hdr)}
rows=[list(r) for r in ws.iter_rows(min_row=2, values_only=True)]
def g(r,c): return r[idx[c]]
def num(v):
    try: return float(str(v).replace(',',''))
    except: return None
breakdowns=[r for r in rows if g(r,'Breakdown')=='Yes']
last_bd=max(g(r,'Report_Date') for r in breakdowns)

months={m.lower():i+1 for i,m in enumerate(['January','February','March','April','May','June','July','August','September','October','November','December'])}
dre=re.compile(r'(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})')
def pdf_text(p): return subprocess.run(['pdftotext','-layout',p,'-'],capture_output=True,text=True).stdout

opl_text={}; opl_date={}
for f in opl_files:
    key=re.search(r'(OPL-[A-Z]{2}-\d{4}[A-Z]?-\d{2})',os.path.basename(f)).group(1)
    t=pdf_text(f); opl_text[key]=t
    lines=t.splitlines(); d=None
    for i,l in enumerate(lines):
        if 'Date of Sharing' in l:
            for j in range(i, min(i+4, len(lines))):
                m=dre.search(lines[j])
                if m and m.group(2).lower() in months:
                    d=datetime.date(int(m.group(3)), months[m.group(2).lower()], int(m.group(1))); break
        if d: break
    opl_date[key]=d

dated={k:v for k,v in opl_date.items() if v}
undated=sorted(k for k,v in opl_date.items() if not v)
ds=sorted(dated.values())
print(f"OPL dated={len(dated)}/56  undated={undated}")
print(f"Date of Sharing: min={ds[0]} max={ds[-1]} span={(ds[-1]-ds[0]).days}d")
print(f"Gap earliest-OPL vs last-breakdown({last_bd.date()}): {(ds[0]-last_bd.date()).days}d ; any OPL before last breakdown? {any(v<=last_bd.date() for v in ds)}")
iv=sorted((b-a).days for a,b in zip(ds,ds[1:]))
print(f"Consecutive-interval median={statistics.median(iv)}d  mode={Counter(iv).most_common(2)}")

pairs=[('YD-2301','OPL-YD-2301-04',['tube','crack']),('DC-3401A','OPL-DC-3401A-07',['manway']),
       ('EA-5601','OPL-EA-5601-05',['tube-to-tubesheet','plug']),('LV-6701','OPL-LV-6701-03',['seiz']),
       ('EA-5601','OPL-EA-5601-06',['foul']),('FA-8901','OPL-FA-8901-07',['manway'])]
lat=[]
print("\nLATENCY:")
for tag,opl,kws in pairs:
    c=[r for r in rows if g(r,'Equipment_Tag')==tag and g(r,'Breakdown')=='Yes' and any(k in (str(g(r,'Problem_Description'))+' '+str(g(r,'Root_Cause'))).lower() for k in kws)]
    c.sort(key=lambda r:g(r,'Report_Date'))
    if c and opl_date.get(opl):
        # ambil event yang PALING SESUAI = pertama utk fouling/manway; utk EA tube leak ambil yang plugging
        fd=c[0]; L=(opl_date[opl]-g(fd,'Report_Date').date()).days; lat.append(L)
        print(f"  {tag} {g(fd,'Report_Date').date()} -> {opl} {opl_date[opl]} = {L}d | {str(g(fd,'Problem_Description'))[:55]}")
    else: print(f"  {tag}/{opl} FAILED cands={len(c)} date={opl_date.get(opl)}")
print(f"  median={statistics.median(sorted(lat))}d n={len(lat)}")

# Coverage: sliding window over normalized full text per tag
tag_full={}
for k,t in opl_text.items():
    tg=re.search(r'OPL-([A-Z]{2}-\d{4}[A-Z]?)-',k).group(1)
    tag_full[tg]=tag_full.get(tg,'')+' '+re.sub(r'\s+',' ',t.lower())

def best_ratio(f, corpus):
    fl=re.sub(r'\s+',' ',f.lower()).strip(); L=len(fl)
    if L<20: return 0.0
    if fl in corpus: return 1.0
    step=max(20,L//2); best=0.0
    for s in range(0,max(1,len(corpus)-L+1),step):
        w=corpus[s:s+L+step]
        sm=difflib.SequenceMatcher(None,fl,w)
        if sm.real_quick_ratio()<best: continue
        if sm.quick_ratio()<best: continue
        r=sm.ratio()
        if r>best: best=r
        if best>0.95: break
    return best

wo_best={}
for r in rows:
    tg=g(r,'Equipment_Tag'); corpus=tag_full.get(tg,'')
    b=0.0
    for cfield in ('Problem_Description','Root_Cause','Corrective_Action'):
        v=str(g(r,cfield) or '')
        if len(v)>=20:
            b=max(b,best_ratio(v,corpus))
            if b>0.95: break
    wo_best[g(r,'WO_Number')]=b

for th in (0.55,0.62,0.70,0.75):
    unc=[r for r in rows if wo_best[g(r,'WO_Number')]<=th]
    ubd=[r for r in breakdowns if wo_best[g(r,'WO_Number')]<=th]
    print(f"TH {th}: uncovered={len(unc)}/211 ({100*len(unc)/211:.1f}%)  unc_breakdowns={len(ubd)}/31  unc_bd_h={sum(num(g(r,'Downtime_Hours')) or 0 for r in ubd)}  unc_bd_IDR={sum(num(g(r,'Total_Cost_IDR')) or 0 for r in ubd):,.0f}")
