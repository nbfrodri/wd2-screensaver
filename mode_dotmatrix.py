"""The wallpaper's halftone hands, suspended in a quiet monochrome volume.

The bundled centroids are extracted from the reference wallpaper once, offline.
No wallpaper, filesystem activity, notifications or desktop data are read live.
Braille supplies eight independent round dots per terminal cell.
"""
import json
import math
from pathlib import Path
import numpy as np

NAME = 'DOTMATRIX'
BLACK = (0, 0, 0)
_BITS = ((1,8),(2,16),(4,32),(64,128))
_PALETTE = [(i,i,i) for i in range(256)]

class Mode:
    def __init__(self,w,h):
        self.w,self.h=w,h
        asset=json.loads((Path(__file__).parent/'assets'/'dot_hands.json').read_text())
        self.dots=np.array(asset['dots'],dtype=float)
        self.start=None
        # Dot size follows the original halftone; brighter dots lie nearer us.
        self.depth=(self.dots[:,2]-.5)*.7
        self.phase=self.dots[:,0]*10+self.dots[:,1]*6
        self.last=None
        ordered_word=self.word_points(len(self.dots))
        self.word=np.empty_like(ordered_word)
        self.word[np.argsort(self.dots[:,0])]=ordered_word
        self.rank=np.argsort(np.argsort(self.dots[:,0]))/max(1,len(self.dots)-1)

    @staticmethod
    def word_points(count):
        # A large original bitmap word, built entirely from halftone points.
        font={
            'D':('11110','10001','10001','10001','10001','10001','11110'),
            'E':('11111','10000','10000','11110','10000','10000','11111'),
            'S':('01111','10000','10000','01110','00001','00001','11110'),
            'C':('01111','10000','10000','10000','10000','10000','01111'),
        }
        dots=[]
        for letter,ch in enumerate('DEDSEC'):
            for row,line in enumerate(font[ch]):
                for col,on in enumerate(line):
                    if on=='1':
                        for yy in range(4):
                            for xx in range(4):
                                dots.append((.08+(letter*6+col+(xx+.5)/4)/35*.84,
                                             .33+(row+(yy+.5)/4)/7*.34))
        ordered=np.array(sorted(dots,key=lambda p:(p[0],p[1])))
        selected=ordered[np.linspace(0,len(ordered)-1,count).astype(int)]
        # Match left to right, avoiding a meaningless cloud of crossing paths.
        return selected

    def points(self,t):
        x=self.dots[:,0]-.5
        y=self.dots[:,1]-.5
        breath=1+.013*math.sin(t*.36)
        yaw=.055*math.sin(t*.19)
        tilt=.025*math.sin(t*.23+.7)
        px=x*breath+self.depth*math.sin(yaw)*.075
        py=y*breath+self.depth*math.sin(tilt)*.055
        # A slow travelling wave displaces the surface, without scrambling rows.
        wave=np.sin(self.phase-t*.55)*.0025
        px+=wave*self.depth
        py+=np.cos(self.phase*.7-t*.4)*.002*self.depth
        px+=.003*math.sin(t*.13)
        py+=.005*math.sin(t*.17)
        shimmer=.86+.09*np.sin(self.phase-t*.45)
        lum=(62+193*np.power(self.dots[:,2],.65))*shimmer
        # Four seconds of wallpaper hands, then a broad, long-held DEDSEC.
        cycle=t%32
        if cycle<4 or cycle>=29:
            amount=np.zeros(len(x))
        elif cycle<9:
            amount=np.clip((cycle-4)/4.25-self.rank*.17,0,1)
        elif cycle<24:
            amount=np.ones(len(x))
        else:
            amount=1-np.clip((cycle-24)/4.25-(1-self.rank)*.17,0,1)
        amount=amount*amount*(3-2*amount)
        hx,hy=px+.5,py+.5
        wx=self.word[:,0]+.0015*math.sin(t*.25)
        wy=self.word[:,1]+.002*math.sin(t*.3)
        # Small arcing paths carry every wallpaper point into the letters.
        arc=np.sin(amount*math.pi)
        outx=hx+(wx-hx)*amount
        outy=hy+(wy-hy)*amount+arc*.032*np.sin(self.phase)
        wordlum=213+32*np.sin(self.word[:,0]*6-t*.3)
        return outx,outy,lum+(wordlum-lum)*amount

    def draw(self,s,x,y,lum):
        s.bg=[[BLACK]*self.w for _ in range(self.h)]
        masks={}; levels={}
        # Preserve the wallpaper's whitespace and full left/right arm silhouette.
        xs=np.rint(x*(self.w*2-1)).astype(int)
        ys=np.rint(y*(self.h*4-1)).astype(int)
        for px,py,light in zip(xs,ys,lum):
            if not (0<=px<self.w*2 and 0<=py<self.h*4):continue
            cx,cy=int(px)//2,int(py)//4
            key=(cx,cy)
            masks[key]=masks.get(key,0)|_BITS[int(py)%4][int(px)%2]
            levels[key]=max(levels.get(key,0),int(light))
        for (cx,cy),mask in masks.items():
            s.put(cx,cy,chr(0x2800+mask),_PALETTE[max(0,min(255,levels[(cx,cy)]))])

    def spark(self,s,t,strength=1):
        # A rare contact spark occupies the empty gap, never becomes a HUD.
        period=t%17
        flash=max(0,1-abs(period-10.7)/.28)*strength
        if flash<=0:return
        cx=int(self.w*.475);cy=int(self.h*.5)
        level=int(255*flash)
        s.put(cx,cy,'+',_PALETTE[level])
        if flash>.45:
            s.put(cx-1,cy,'-',_PALETTE[int(level*.45)])
            s.put(cx+1,cy,'-',_PALETTE[int(level*.45)])
        if flash>.75:
            s.put(cx,cy-1,'|',_PALETTE[int(level*.35)])
            s.put(cx,cy+1,'|',_PALETTE[int(level*.35)])

    def step(self,s,now):
        if self.start is None:self.start=now
        t=now-self.start
        x,y,lum=self.points(t)
        self.last=(x,y,lum)
        self.draw(s,x,y,lum)
        if t%32<4 or t%32>=29:self.spark(s,t)

    def farewell(self,s,now,t):
        # Both hands yield their points to one brief spark, then complete black.
        t=max(0,min(1,t))
        if self.last is None:self.last=self.points(0)
        x,y,lum=self.last
        collapse=min(1,(t/.82)**2)
        # Depth-dependent delay lets the contour peel away in coherent layers.
        q=np.clip(collapse*(1.08+self.depth*.15),0,1)
        xx=x+(.475-x)*q
        yy=y+(.5-y)*q
        brightness=lum*max(0,1-t*.7)
        if t>=.88:
            s.bg=[[BLACK]*self.w for _ in range(self.h)]
            if t<1:s.put(int(self.w*.475),int(self.h*.5),'.',_PALETTE[int(255*(1-t)/.12)])
            return
        self.draw(s,xx,yy,brightness)
