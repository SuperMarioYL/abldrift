#!/usr/bin/env python3
"""Construct portfolio SVG artwork from authored facts and the renderer palette."""
import argparse,json,math,random,shutil,textwrap
from pathlib import Path
from html import escape

def local(value):
    return str(value.get('en') or value.get('zh') or '') if isinstance(value,dict) else str(value or '')

def render(repo):
    facts=json.loads((repo/'docs/presentation.json').read_text())
    palette=json.loads((repo/'web/palette.json').read_text())
    site=json.loads((repo/'web/site.json').read_text())
    record=json.loads((repo/'docs/demo-results.json').read_text())
    name=facts['name'];tagline=facts['tagline']
    nodes=facts['architecture']['nodes'];edges=facts['architecture']['edges']
    assert 3<=len(nodes)<=6 and 3<=len(facts['process']['steps'])<=4 and 3<=len(facts['integrations']['items'])<=6
    assert all(0<=int(e[0])<len(nodes) and 0<=int(e[1])<len(nodes) for e in edges)
    folder=repo/'assets/presentation';web=repo/'web/assets/presentation'
    folder.mkdir(parents=True,exist_ok=True);web.mkdir(parents=True,exist_ok=True)
    for mode in ['dark','light']:
        p=palette[mode]
        def txt(x,y,s,size=20,color='ink',anchor='start',weight=400):
            return f'<text x="{x}" y="{y}" fill="{p[color]}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}">{escape(local(s))}</text>'
        def para(x,y,s,width,size=18,color='muted',limit=3,anchor='start'):
            rows=textwrap.wrap(local(s),max(8,int(width/(size*.57)))) or ['']
            if len(rows)>limit:rows=rows[:limit];rows[-1]=rows[-1].rstrip('.')+'…'
            return ''.join(txt(x,y+i*size*1.4,t,size,color,anchor) for i,t in enumerate(rows))
        def line(d,active=True):
            return f'<path d="{d}" fill="none" stroke="{p["primary"] if active else p["line"]}" stroke-width="1.5" marker-end="url(#arrow)"/>'+ (f'<path d="{d}" class="flow" fill="none" stroke="{p["highlight"]}" stroke-width="2"/>' if active else '')
        def card(x,y,w,title,detail,h=122):
            return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{p["panel"]}" stroke="{p["line"]}"/>'+para(x+18,y+31,title,w-36,21,'ink',2)+para(x+18,y+83,detail,w-36,17,'muted',2)
        def particles(cx,cy,rx,ry,count=360):
            rng=random.Random(name);s=''
            for i in range(count):
                a=rng.random()*math.tau;z=rng.uniform(-1,1);r=math.sqrt(1-z*z);x=cx+rx*r*math.cos(a);y=cy+ry*z
                s+=f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{rng.uniform(.6,1.7):.2f}" fill="{p["primary"] if i%3 else p["secondary"]}" opacity="{rng.uniform(.2,.8):.2f}"/>'
            return s
        def save(kind,w,h,title,description,body,mobile=False,static=False):
            slug=f'{kind}{"-mobile" if mobile else ""}-{mode}'
            css='text{font-family:Arial,"Noto Sans",sans-serif}.flow{stroke-dasharray:10 110;animation:flow 6s linear infinite}.pulse{animation:pulse 5s ease-in-out infinite}.turn{transform-box:fill-box;transform-origin:center;animation:turn 36s linear infinite}@keyframes flow{to{stroke-dashoffset:-360}}@keyframes pulse{0%,100%{opacity:.45}50%{opacity:1}}@keyframes turn{to{transform:rotate(360deg)}}@media(prefers-reduced-motion:reduce){*{animation:none!important;transform:none!important}.flow{display:none}}'
            if static:css+='*{animation:none!important;transform:none!important}.flow{display:none}'
            svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" data-palette="{palette['id']}" role="img" aria-labelledby="{slug}-title {slug}-desc"><title id="{slug}-title">{escape(title)}</title><desc id="{slug}-desc">{escape(description)}</desc><defs><linearGradient id="brand" gradientUnits="userSpaceOnUse" x2="{w}" y2="{h}"><stop stop-color="{p['primary']}"/><stop offset=".6" stop-color="{p['secondary']}"/><stop offset="1" stop-color="{p['highlight']}"/></linearGradient><radialGradient id="halo"><stop stop-color="{p['primary']}" stop-opacity=".22"/><stop offset="1" stop-color="{p['bg']}" stop-opacity="0"/></radialGradient><filter id="glow"><feGaussianBlur stdDeviation="5"/></filter><pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M40 0H0V40" fill="none" stroke="{p['line']}" stroke-opacity=".35" stroke-width=".6"/></pattern><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="m1 1 7 4-7 4" fill="none" stroke="{p['primary']}" stroke-width="1.5"/></marker></defs><style>{css}</style><rect width="{w}" height="{h}" rx="16" fill="{p['bg']}"/><rect width="{w}" height="{h}" rx="16" fill="url(#grid)"/><ellipse cx="{w*.63}" cy="{h*.43}" rx="{w*.5}" ry="{h*.7}" fill="url(#halo)"/>{body}</svg>'''
            out=folder/f'{slug}.svg';out.write_text(svg+'\n');shutil.copy2(out,web/out.name)
        for mobile in [False,True]:
            w=400 if mobile else 1000;h=510 if mobile else 390
            cx,cy,rx,ry=(250,362,190,140) if mobile else (825,225,260,210)
            b=particles(cx,cy,rx,ry)
            b+=txt(28 if mobile else 48,50 if mobile else 56,'PROJECT / OPEN SOURCE',13,'muted')
            size=min(46 if mobile else 74,(340 if mobile else 580)/max(1,len(name))/.58)
            b+=f'<text x="{28 if mobile else 48}" y="{117 if mobile else 182}" font-size="{size:.1f}" fill="url(#brand)" font-weight="700">{escape(name)}</text>'
            b+=para(28 if mobile else 50,163 if mobile else 242,tagline,340 if mobile else 530,21 if mobile else 24,'ink',3)
            pts=[(cx-rx*.65,cy+ry*.4),(cx-rx*.24,cy-ry*.15),(cx+rx*.15,cy+ry*.05),(cx+rx*.58,cy-ry*.5)]
            b+=line('M'+'L'.join(f'{x:.1f} {y:.1f}' for x,y in pts))
            for x,y in pts:b+=f'<circle cx="{x}" cy="{y}" r="12" fill="{p["highlight"]}" opacity=".5" filter="url(#glow)"/><circle class="pulse" cx="{x}" cy="{y}" r="3" fill="{p["highlight"]}"/>'
            save('hero',w,h,name,tagline,b,mobile)
            # Source-backed architecture: different graphs share a readable blueprint.
            h=150+len(nodes)*145 if mobile else 570
            b=txt(28 if mobile else 44,44,'ARCHITECTURE / DATA FLOW',13,'muted')+para(28 if mobile else 44,84,facts['architecture']['title'],344 if mobile else 900,25 if mobile else 30,'ink',2)
            coords=[(28,130+i*145,344) for i in range(len(nodes))] if mobile else [(44+(i%3)*316,142+(i//3)*230,276) for i in range(len(nodes))]
            for k,e in enumerate(edges):
                a,t=map(int,e[:2]);ax,ay,aw=coords[a];bx,by,bw=coords[t]
                if mobile:
                    if t==a+1:d=f'M{ax+aw/2} {ay+122}V{by}'
                    else:d=f'M{ax+aw} {ay+61}H{380+k%2*8}V{by+61}H{bx+bw}'
                elif ay==by and abs(a-t)==1:
                    d=f'M{ax+aw if bx>ax else ax} {ay+61}H{bx if bx>ax else bx+bw}'
                else:
                    sy=ay+122 if by>ay else ay;ty=by if by>ay else by+122;lane=(sy+ty)/2+k%3*8
                    if by==ay:sy=ay+122;ty=by+122;lane=sy+24+k%3*10
                    d=f'M{ax+aw/2} {sy}V{lane}H{bx+bw/2}V{ty}'
                b+=line(d)
            for n,(x,y,cw) in zip(nodes,coords):b+=card(x,y,cw,n['title'],n['detail'])
            save('architecture',w,h,name+' architecture',facts['architecture']['title'],b,mobile)
            # Ordered operation, with observed result held in a stable footer.
            steps=facts['process']['steps'];h=220+len(steps)*155 if mobile else 465
            b=txt(28 if mobile else 44,44,'PROCESS / FROM INPUT TO RESULT',13,'muted')+para(28 if mobile else 44,84,facts['process']['title'],344 if mobile else 900,25 if mobile else 30,'ink',2)
            if mobile:
                for i,s in enumerate(steps):
                    y=135+i*155
                    if i<len(steps)-1:b+=line(f'M200 {y+122}V{y+155}')
                    b+=card(28,y,344,f'{i+1:02}  '+s['title'],s['detail'])
                b+=para(28,h-65,facts['process']['result'],344,18,'highlight',2)
            else:
                cw=(912-(len(steps)-1)*24)/len(steps)
                for i,s in enumerate(steps):
                    x=44+i*(cw+24)
                    if i<len(steps)-1:b+=line(f'M{x+cw} 237H{x+cw+24}')
                    b+=card(x,176,cw,f'{i+1:02}  '+s['title'],s['detail'])
                b+=para(44,379,facts['process']['result'],900,20,'highlight',2)
            save('process',w,h,name+' process',facts['process']['result'],b,mobile)
            # Capability orbits are implemented routes, never a live connection claim.
            items=facts['integrations']['items'];h=270+len(items)*125 if mobile else 600
            b=txt(28 if mobile else 44,44,'CAPABILITIES / CONNECTIONS',13,'muted')+para(28 if mobile else 44,84,facts['integrations']['title'],344 if mobile else 900,25 if mobile else 30,'ink',2)
            if mobile:
                b+=f'<ellipse cx="200" cy="203" rx="132" ry="53" fill="none" stroke="{p["line"]}"/><circle cx="200" cy="203" r="43" fill="{p["panel"]}" stroke="{p["primary"]}"/>'+txt(200,213,name[:2].upper(),28,'primary','middle',700)
                for i,item in enumerate(items):b+=card(28,278+i*125,344,item['title'],item['detail'],112)
            else:
                b+=f'<ellipse cx="500" cy="337" rx="238" ry="176" fill="none" stroke="{p["line"]}"/><ellipse cx="500" cy="337" rx="193" ry="144" fill="none" stroke="{p["line"]}" stroke-dasharray="2 9"/><circle cx="500" cy="337" r="68" fill="{p["panel"]}" stroke="{p["primary"]}"/>'+txt(500,348,name[:2].upper(),34,'primary','middle',700)
                for i,item in enumerate(items):
                    side=i%2;y=156+(i//2)*146;x=40 if side==0 else 724
                    b+=line(f'M{276 if side==0 else 568} {y+55 if side==0 else 337}H{390 if side==0 else 662}V{337 if side==0 else y+55}H{432 if side==0 else 724}')
                    b+=card(x,y,236,item['title'],item['detail'],112)
            save('integrations',w,h,name+' integration routes',facts['integrations']['title'],b,mobile)
        # Same palette, genuinely static fallback (even without reduced-motion).
        b=particles(500,380,470,275,1600)
        b+=line('M210 415L365 304L520 352L748 240')
        save('scene',1000,700,name+' particle scene','Illustrative project particle field; no live result is represented.',b,static=True)
        for i,step in enumerate(record['steps']):
            label=local(site['demo']['steps'][i]['label']);body=local(site['demo']['steps'][i]['body'])
            b=txt(36,44,f'DEMO / STEP {i+1:02}',13,'muted')+para(36,89,label,688,28,'ink',2)+para(36,148,body,688,19,'muted',3)
            b+=f'<path d="M36 236H724" stroke="{p["line"]}"/>'+para(36,272,step['command'],688,16,'primary',2)
            save(f'demo-{i}',760,330,name+' demo '+str(i+1),body,b)
    print(name, palette['id'], 'SVG groups generated')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);args=ap.parse_args();render(args.repo.resolve())
