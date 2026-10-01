"""A wet, densely inhabited street corner, borrowed from ctOS."""
import math
import random
from engine3d import Camera
from lib import BLACK, CYAN, PINK, YELLOW, GREEN, WHITE, blend
NAME = 'TRAFFIC'
RED = (245, 58, 45)

class Mode:
    def __init__(self,w,h):
        self.w,self.h=w,h
        self.cam=Camera(w,h,1.55)
        self.cam.pos=[25,32,-37]
        self.cam.yaw=-math.atan2(25,37)
        self.cam.pitch=math.atan2(32,math.hypot(25,37))
        self.cam.cy=h*.52
        self.start=None
        self.static=None
        self.z=None
        self.record=False

    def quad(self,s,pts,col):
        pp=[self.cam.project(p) for p in pts]
        if not all(pp): return
        depth=sum(p[2] for p in pp)/len(pp)
        pts=[(p[0],p[1]*2) for p in pp]
        ax,ay=pts[0]; bx,by=pts[1]; cx,cy=pts[2]
        det=(bx-ax)*(cy-ay)-(cx-ax)*(by-ay)
        if abs(det)<1e-7:return
        da,db,dc=1/pp[0][2],1/pp[1][2],1/pp[2][2]
        ux=((db-da)*(cy-ay)-(dc-da)*(by-ay))/det
        uy=((bx-ax)*(dc-da)-(cx-ax)*(db-da))/det
        uz=da-ux*ax-uy*ay
        ys=[p[1] for p in pts]
        for py in range(max(4,int(min(ys))),min(self.h*2-4,int(max(ys))+1)):
            xs=[]; yc=py+.5
            for i,(ax,ay) in enumerate(pts):
                bx,by=pts[(i+1)%len(pts)]
                if ay<=yc<by or by<=yc<ay: xs.append(ax+(yc-ay)/(by-ay)*(bx-ax))
            if len(xs)<2: continue
            row=(s.pb if py&1 else s.pt)[py>>1]
            zr=self.z[py]
            for x in range(max(0,int(min(xs))),min(self.w,int(max(xs))+1)):
                inv=ux*(x+.5)+uy*yc+uz
                dep=1/inv if inv>0 else depth
                if dep<=zr[x]+.12:
                    row[x]=col
                    if self.record: zr[x]=dep

    def plane(self,s,x,z,wx,wz,col,y=.02):
        self.quad(s,[(x-wx,y,z-wz),(x+wx,y,z-wz),(x+wx,y,z+wz),(x-wx,y,z+wz)],col)

    def box(self,s,x,z,wx,wz,height,col,base=0):
        # Far face first; the top and sunlit west wall provide solid volume.
        p=[(x-wx,base,z-wz),(x+wx,base,z-wz),(x+wx,base,z+wz),(x-wx,base,z+wz)]
        p += [(a,base+height,c) for a,_,c in p]
        for face,c in [((0,1,5,4),blend(col,BLACK,.22)),((1,2,6,5),blend(col,BLACK,.4)),((4,5,6,7),blend(col,WHITE,.12))]:
            self.quad(s,[p[i] for i in face],c)

    def stroke(self,s,a,b,col):
        pa,pb=self.cam.project(a),self.cam.project(b)
        if pa and pb: s.pixel_line(pa[0],pa[1]*2,pb[0],pb[1]*2,col)

    def building(self,s,x,z,wx,wz,hh,col,sign):
        self.box(s,x,z,wx,wz,hh,col,.2)
        self.box(s,x,z,wx+.15,wz+.15,.22,(87,83,87),hh+.2)
        self.box(s,x+.8,z+.8,wx*.4,wz*.4,.7,(53,61,65),hh+.45)
        # Brick courses and varied occupied windows on both visible walls.
        for y in range(1,int(hh)):
            self.quad(s,[(x-wx,y,z-wz-.04),(x+wx,y,z-wz-.04),(x+wx,y+.035,z-wz-.04),(x-wx,y+.035,z-wz-.04)],blend(col,BLACK,.32))
        for side in (0,1):
            span=wx if side==0 else wz
            for yy in range(3,int(hh),2):
                for j in range(-int(span)+1,int(span),2):
                    # A few occupied windows read as rooms; a bright checkerboard
                    # competes with the cars and destroys the building silhouette.
                    lit=(j+yy+int(x))%5<2
                    c=((119,104,77) if x<0 else (89,115,128)) if lit else (39,49,58)
                    if side==0:
                        pts=[(x+j-.58,yy,z-wz-.08),(x+j+.58,yy,z-wz-.08),(x+j+.58,yy+1.25,z-wz-.08),(x+j-.58,yy+1.25,z-wz-.08)]
                    else:
                        pts=[(x+wx+.08,yy,z+j-.58),(x+wx+.08,yy,z+j+.58),(x+wx+.08,yy+1.25,z+j+.58),(x+wx+.08,yy+1.25,z+j-.58)]
                    self.quad(s,pts,c)
        # Shop glass, door, projecting striped canvas awning.
        for j in range(-int(wx)+1,int(wx),2):
            self.quad(s,[(x+j-.7,.4,z-wz-.12),(x+j+.7,.4,z-wz-.12),(x+j+.7,2.3,z-wz-.12),(x+j-.7,2.3,z-wz-.12)],(37,83,94))
            self.quad(s,[(x+j-.65,.5,z-wz-.14),(x+j-.35,.5,z-wz-.14),(x+j+.5,2.2,z-wz-.14),(x+j+.2,2.2,z-wz-.14)],(67,112,118))
        for j in range(int(wx*2)):
            self.quad(s,[(x-wx+j,2.6,z-wz),(x-wx+j+1,2.6,z-wz),(x-wx+j+1,2.15,z-wz-1.1),(x-wx+j,2.15,z-wz-1.1)],(161,65,61) if j%2 else (180,158,121))
        neon = PINK if x < 0 else CYAN
        # Shop tubes and their broken reflections are attached to the facade
        # and wet pavement, keeping the intersection's DedSec night palette.
        self.quad(s,[(x-wx,2.7,z-wz-.15),(x+wx,2.7,z-wz-.15),
                     (x+wx,2.86,z-wz-.15),(x-wx,2.86,z-wz-.15)],neon)
        for k in range(7):
            rz = z-wz-1.4-k*.8
            self.plane(s,x+math.sin(k*3)*.4,rz,wx*(.45-k*.035),.055,
                       blend(neon,BLACK,.65+k*.045),.015)
        q=self.cam.project((x,2.9,z-wz-.2))
        if q and self.w>=120: s.text(int(q[0])-len(sign)//2,int(q[1]),sign,(222,185,128))

    def scenery(self,s):
        s.gradient_bg((13,18,29),(26,30,39))
        self.z=[[1e8]*self.w for _ in range(self.h*2)]
        self.record=True
        self.plane(s,0,0,33,30,(36,43,50),-.1)
        rng=random.Random(77)
        # Irregular wet asphalt aggregate and patched paving.
        for _ in range(700):
            x,z=rng.uniform(-32,32),rng.uniform(-29,29)
            self.plane(s,x,z,rng.uniform(.07,.45),rng.uniform(.05,.24),rng.choice([(40,47,54),(32,39,46),(43,50,57),(35,43,51)]),-.09)
        for x in (-19,19):
            for z in (-18,18):
                self.box(s,x,z,12,11,.3,(76,79,78))
                for a in range(-11,12,2):
                    for b in range(-10,11,2): self.plane(s,x+a,z+b,.94,.94,(79+(a+b)%3,81+(a+b)%3,78+(a+b)%3),.32)
        for v in range(-29,30,4):
            if abs(v)>9:
                self.plane(s,v,0,1,.09,(185,155,69))
                self.plane(s,0,v,.09,1,(185,155,69))
                self.plane(s,v,5.7,1.6,.07,(148,156,153))
                self.plane(s,5.7,v,.07,1.6,(148,156,153))
        for i in range(-5,6,2):
            for side in (-1,1):
                self.plane(s,i,side*8,.55,1.1,(175,182,177))
                self.plane(s,side*8,i,1.1,.55,(175,182,177))
        # Broken reflections in the wet wheel tracks.
        for i in range(26):
            x=-29+i*2.2
            self.plane(s,x,4.6,.65,.08,(56,76,84),.01)
            self.plane(s,-4.6,x,.08,.5,(73,60,67),.01)
        for x,z in [(-8,-12),(8,12),(-12,8),(12,-8)]:
            self.plane(s,x,z,.65,.65,(39,45,46),.34)
            for d in range(-3,4): self.plane(s,x+d*.15,z,.03,.55,(108,113,109),.35)
        # Buildings are arranged along the back and sides to expose the junction.
        for a in [(-17,18,7,7,12,(99,75,66),'CAFE 24'),(17,18,7,7,15,(71,81,91),'RECORDS'),(-22,-19,7,6,5,(109,93,76),'MARKET'),(22,-20,6,6,6,(89,77,82),'LAUNDRY')]: self.building(s,*a)
        for x,z in [(-8,-7),(8,7),(-8,7),(8,-7)]:
            self.box(s,x,z,.12,.12,4.6,(98,105,106),.3)
            self.box(s,x-1,z,.95,.13,.13,(124,130,129),4.75)
            self.box(s,x-1.8,z,.35,.28,.18,(213,199,137),4.55)
            self.box(s,x,z,.33,.28,1.05,(20,27,29),3.2)
        for x,z in [(-10,-5),(10,5),(-10,5),(10,-5)]:
            self.box(s,x,z,.45,.45,.95,(42,77,64),.35)
        for x,z in [(-12,-9),(12,9)]:
            self.box(s,x,z,1.2,.4,.2,(131,92,58),.9)
            self.box(s,x-1,z,.09,.1,.9,(54,60,62),.3)
            self.box(s,x+1,z,.09,.1,.9,(54,60,62),.3)
        self.record=False
        self.static=s.snapshot()

    def car(self,s,x,z,axis,col,direction):
        wx,wz=(1.9,.88) if axis==0 else (.88,1.9)
        self.plane(s,x+.25,z+.25,wx+.2,wz+.2,(20,27,31),.04)
        self.box(s,x,z,wx,wz,.65,col,.22)
        self.box(s,x,z,wx*.52,wz*.52,.6,(35,64,77),.87)
        self.box(s,x,z,wx*.48,wz*.48,.1,blend(col,WHITE,.18),1.47)
        for k in (-1,1):
            for j in (-1,1):
                xx=x+k*wx*.7 if axis==0 else x+k*wx
                zz=z+j*wz if axis==0 else z+j*wz*.7
                self.box(s,xx,zz,.28 if axis==0 else .12,.12 if axis==0 else .28,.37,(17,22,25),.12)
        for k in (-1,1):
            xx=x+direction*wx if axis==0 else x+k*.57
            zz=z+k*.57 if axis==0 else z+direction*wz
            self.box(s,xx,zz,.13,.13,.17,(239,224,165),.51)
            bx=x-direction*wx if axis==0 else x+k*.57
            bz=z+k*.57 if axis==0 else z-direction*wz
            self.box(s,bx,bz,.12,.12,.16,RED,.5)
        self.plane(s,x,z,wx*.8,wz*.16,blend(col,WHITE,.3),.89)

    def step(self,s,now):
        if self.start is None:self.start=now
        t=now-self.start
        if self.static is None:self.scenery(s)
        else:s.restore(self.static)
        phase=t%20
        hacked=16<=phase<19
        cars=[]
        for axis in (0,1):
            green=phase<7 if axis==0 else 8<=phase<15
            for lane in (-1,1):
                for i in range(4):
                    v=(t*3.2+i*15+axis*7)%62-31
                    if not green and not hacked and -16<v<-9:v=-9-(i%3)*4.6
                    v*=lane
                    x,z=(v,-lane*2.6) if axis==0 else (lane*2.6,v)
                    cars.append((self.cam.to_view((x,0,z))[2],x,z,axis,[(168,62,63),(56,113,142),(191,157,79),(139,146,145)][(i+axis)%4],lane))
        for _,x,z,a,c,d in sorted(cars,reverse=True):self.car(s,x,z,a,c,d)
        # Pedestrians wait through the red phase, then cross the zebra strip.
        for i in range(9):
            crossing=8<=phase<15
            x=-5+i*1.25 if crossing else -8-i%3*.6
            z=-8+(math.sin(t*.6+i)*.2 if crossing else i//3*.8)
            self.box(s,x,z,.16,.16,.65,[(140,88,78),(73,107,131),(159,146,84)][i%3],.6)
            self.box(s,x,z,.14,.14,.28,(187,148,118),1.25)
            self.box(s,x-.1,z,.07,.07,.6,(39,44,54),.05)
            self.box(s,x+.1,z+.1*math.sin(t*5+i),.07,.07,.6,(39,44,54),.05)
        for i,(x,z) in enumerate([(-8,-7),(8,7),(-8,7),(8,-7)]):
            green=(phase<7 if i%2==0 else 8<=phase<15)
            yellow=7<=phase<8 or 15<=phase<16
            if hacked:green=int(t*4+i)%3!=0
            for j,col in enumerate((RED,YELLOW,GREEN)):
                active=(j==2 and green) or (j==1 and yellow) or (j==0 and not green and not yellow)
                self.box(s,x,z-.31,.18,.07,.18,col if active else blend(col,BLACK,.86),4.02-j*.29)
        # A minute stabilized-camera drift keeps the solid scene cinematic.
        drift=round(math.sin(t*.16)*1.2)
        if drift:
            for row in range(2,self.h-2):s.shift_row(row,drift)
        s.fill(0,0,self.w,2)
        s.text(2,0,'DEDSEC / INTERSECTION 07',PINK)
        state='SIGNALS SPOOFED' if hacked else 'CROSS TRAFFIC' if 8<=phase<15 else 'LOCAL TRAFFIC'
        s.text(max(2,self.w-len(state)-2),1,state,YELLOW if hacked else CYAN)
        s.fill(0,self.h-2,self.w,2)
        s.text(2,self.h-2,'WET ASPHALT / NIGHT SHIFT / ctOS CAMERA 04', (151,169,178))
        s.text(2,self.h-1,'ALL GREEN. THANK YOU FOR YOUR COOPERATION.' if hacked else 'SIGNAL CYCLE %02d / 20   |   DEDSEC OWNS THE RIGHT OF WAY'%int(phase),PINK if hacked else CYAN)

    def farewell(self,s,now,t):
        from cinematic import exit_scene
        exit_scene(self,s,now,t,'pullback','ALL SIGNALS OFFLINE',RED)
        if t<.65:
            for x,z in [(-8,-7),(8,7),(-8,7),(8,-7)]:
                q=self.cam.project((x,4,z))
                if q:s.put(int(q[0]),int(q[1]),'x',blend(RED,BLACK,t))
