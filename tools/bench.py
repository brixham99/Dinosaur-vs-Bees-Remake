import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import time, numpy as np, game, sys
from dinobees.settings import DT
g=game.Game(game.parse_args(['--seed','5','--autoplay','--mute','--level','2','--highscore-file','/tmp/hs_p.json']))
rec=[]
N=int(sys.argv[1]) if len(sys.argv)>1 else 3000
for i in range(N):
    g.handle_events()
    t0=time.perf_counter(); g.update(DT); t1=time.perf_counter(); g.draw(); t2=time.perf_counter()
    rec.append(((t1-t0)*1000,(t2-t1)*1000, g.world.fade<1, g.world.star_alpha>0.02, g.world.volcano_amt>0.02, len(g.bees), len(g.particles)))
r=np.array(rec[40:],dtype=float)
tot=r[:,0]+r[:,1]
print('update avg %.2f draw avg %.2f total p95 %.2f p99 %.2f max %.2f'%(r[:,0].mean(), r[:,1].mean(), np.percentile(tot,95), np.percentile(tot,99), tot.max()))
for name,m in [('fading',r[:,2]==1),('not fading',r[:,2]==0),('stars',r[:,3]==1),('volcano',r[:,4]==1),('plain day',(r[:,3]==0)&(r[:,4]==0)&(r[:,2]==0))]:
    if m.sum(): print(name, int(m.sum()), 'avg %.2f p95 %.2f max %.2f'%(tot[m].mean(), np.percentile(tot[m],95), tot[m].max()))
