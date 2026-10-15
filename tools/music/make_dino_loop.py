import struct, numpy as np, random
SR=8363
N={'C':0,'C#':1,'Db':1,'D':2,'D#':3,'Eb':3,'E':4,'F':5,'F#':6,'Gb':6,'G':7,'G#':8,'Ab':8,'A':9,'A#':10,'Bb':10,'B':11}
def nn(s): return N[s[:-1]]+12*int(s[-1])+1  # XM note: C-0=1
# ---- samples (instrument 1 lead pulse25, 2 arp square, 3 bass saw, 4 kick, 5 snare, 6 hat)
def cyc(w):
    t=np.arange(32)/32
    if w=='sq': x=np.where(t<.5,1,-1)
    if w=='pu': x=np.where(t<.25,1,-1)
    if w=='saw': x=2*t-1
    return (x*90).astype(np.int8)
rng=np.random.default_rng(7); DR=22050
t=np.arange(int(DR*.25))/DR
kick=np.sin(2*np.pi*np.cumsum(50+180*np.exp(-t*30))/DR)*np.exp(-t*14)
st=np.arange(int(DR*.18))/DR
snare=(rng.uniform(-1,1,len(st))*.8+.5*np.sin(2*np.pi*190*st))*np.exp(-st*22)
ht=np.arange(int(DR*.05))/DR
hn=rng.uniform(-1,1,len(ht)); hn=np.diff(hn,prepend=0)/2
hat=hn*np.exp(-ht*70)
d=lambda x:(np.clip(x,-1,1)*120).astype(np.int8)
samples=[('Lead pulse',cyc('pu'),True,40),('Arp square',cyc('sq'),True,26),('Bass saw',cyc('saw'),True,48),
 ('Kick',d(kick),False,64),('Snare',d(snare),False,44),('Hat',d(hat),False,30)]
# drum rate fix: relnote/finetune so C-4 plays at 22050
import math; semi=12*math.log2(DR/8363); DREL=round(semi); DFT=int(round((semi-DREL)*128))
# ---- song: C major, playful
CH={'C':[0,4,7],'Am':[9,0,4],'F':[5,9,0],'G':[7,11,2],'Dm':[2,5,9],'Em':[4,7,11],'E':[4,8,11],'Bb':[10,2,5]}
ROOT={'C':'C','Am':'A','F':'F','G':'G','Dm':'D','Em':'E','E':'E','Bb':'Bb'}
pats=[['C','Am','F','G'],['C','Am','Dm','G'],['Am','F','C','G'],['F','G','Em','E'],['F','G','C','Am'],['Dm','Bb','G','G']]
order=[0,1,2,3,0,1,4,5]
SCALE=[0,2,4,5,7,9,11]
# rhythm motifs (row offsets, length)
RH=[[(0,3),(3,3),(6,2),(8,2),(10,2),(12,4)],[(0,2),(2,2),(4,4),(8,3),(11,1),(12,4)],
    [(0,4),(4,2),(6,2),(8,8)],[(0,2),(2,2),(4,2),(6,2),(8,2),(10,2),(12,2),(14,2)]]
random.seed(11)
def pc2note(pc,near):
    best=None
    for o in range(4,7):
        n=pc+12*o+1
        if 49<=n<=78 and (best is None or abs(n-near)<abs(best-near)): best=n
    return best
def build(pi,chords):
    rows=[[None]*6 for _ in range(64)]
    cur=nn('E5')
    for b,ch in enumerate(chords):
        tones=CH[ch]; base=b*16
        rh=RH[[0,1,0,2][b]] if pi in(0,1,4) else RH[[3,1,3,2][b]] if pi in(2,3) else RH[[1,3,0,2][b]]
        for k,(o,l) in enumerate(rh):
            if k==0 or o in(8,12) or l>=4: pc=random.choice(tones)
            else: pc=(SCALE[(SCALE.index(min(SCALE,key=lambda s:abs(s-(cur-1)%12)))+random.choice([-1,1,1,2]))%7])
            cur=pc2note(pc,cur+random.choice([0,2,-2,4]))
            fx=(0,0)
            if l>=4 and k==len(rh)-1 and random.random()<.5: fx=(3,0x30)  # portamento into note
            rows[base+o][0]=(cur,1,0x40-8*(k%2),*fx)
            for r in range(2,l):
                rows[base+o+r][0]=(0,0,0,4,0x46) if r<5 else (0,0,0,6,0x02)
        # arp
        m=0x37 if 3 in [(tones[1]-tones[0])%12] else 0x47
        for r in range(16):
            rows[base+r][1]=(nn(ROOT[ch]+'4'),2,0x30,0,m) if r%4==0 else (0,0,0,0,m)
            if r%4==3: rows[base+r][1]=(0,0,0,0xA,0x04)
        # bass octave jumps
        rt=ROOT[ch]
        for r in range(0,16,2):
            o='2' if r%4==0 else '3'
            n=nn(rt+o)
            if r==14: n=nn(rt+'2')+7
            rows[base+r][2]=(n,3,0x40,0xA,0x06) if r%4==2 else (n,3,0x40,0,0)
        # drums
        for r in (0,6,8,(11 if b%2 else 10)): rows[base+r][3]=(nn('C4'),4,0x40,0,0)
        for r in (4,12): rows[base+r][4]=(nn('C4'),5,0x40,0,0)
        for r in range(0,16,1 if pi in(2,3,4) else 2): rows[base+r][5]=(nn('C4' if r%4 else 'D4'),6,0x30 if r%4==2 else 0x20,0,0)
    if pi==5:
        for r,v in zip((52,54,56,58,60,61,62,63),(0x18,0x20,0x28,0x2c,0x30,0x34,0x38,0x40)): rows[r][4]=(nn('C4'),5,v,0,0)
    return rows
patterns=[build(i,c) for i,c in enumerate(pats)]
SPEED,BPM=6,136
def write(fn):
    h=b'Extended Module: '+b'Dino Loop'.ljust(20,b'\0')+b'\x1a'+b'GrokBot pyXM'.ljust(20,b'\0')+struct.pack('<H',0x104)
    h+=struct.pack('<IHHHHHHHH',276,len(order),0,6,len(patterns),len(samples),1,SPEED,BPM)+bytes(order).ljust(256,b'\0')
    for p in patterns:
        data=b''.join(bytes([c[0],c[1],c[2] and c[2]+0x10,c[3],c[4]]) if c else b'\x80' for row in p for c in row)
        h+=struct.pack('<IBHH',9,0,64,len(data))+data
    for i,(name,s,loop,vol) in enumerate(samples):
        env=[0]*24; npts=0; etype=0
        if i in(1,2): env[:6]=[0,64,6,40,40,24]; npts=3; etype=1
        ins=struct.pack('<I',263)+name.encode().ljust(22,b'\0')+struct.pack('<BHI',0,1,40)+bytes(96)
        ins+=struct.pack('<24H',*env)+bytes(48)+bytes([npts,0,0,0,0,0,0,0,etype,0,0,0,0,0])+struct.pack('<HH',0,0)
        ins=ins.ljust(263,b'\0')
        rel,ft=(0,0) if loop else (DREL,DFT)
        sh=struct.pack('<IIIBbBBbB',len(s),0,len(s) if loop else 0,vol,ft,1 if loop else 0,[128,96,128,128,140,160][i],rel,0)+name.encode().ljust(22,b'\0')
        dd=np.diff(s.astype(np.int16),prepend=0).astype(np.int8).tobytes()
        h+=ins+sh+dd
    open(fn,'wb').write(h)
write('out/dino_loop.xm')
