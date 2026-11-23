"""Editable draw.io + native SVG + 2x PNG, using installed NumPy/FreeType only.
Run with Conda agent-dev. No network, model, database, or application imports.
"""
from __future__ import annotations
import ctypes as C
from ctypes.util import find_library
import hashlib
import json
import math
from pathlib import Path
import struct
import zlib
import xml.etree.ElementTree as ET
import numpy as np

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
INK = '#172B4D'
MUTED = '#607086'
BLUE = '#245EA8'
PURPLE = '#6B48A5'
TEAL = '#167B78'
ORANGE = '#A96320'
BORDER = '#CCD5E0'
SCALE = 2

class Generic(C.Structure):
    _fields_ = [('data',C.c_void_p),('finalizer',C.c_void_p)]
class Vec(C.Structure):
    _fields_ = [('x',C.c_long),('y',C.c_long)]
class BBox(C.Structure):
    _fields_ = [('xMin',C.c_long),('yMin',C.c_long),('xMax',C.c_long),('yMax',C.c_long)]
class Bitmap(C.Structure):
    _fields_ = [('rows',C.c_uint),('width',C.c_uint),('pitch',C.c_int),('buffer',C.POINTER(C.c_ubyte)),('num_grays',C.c_ushort),('pixel_mode',C.c_ubyte),('palette_mode',C.c_ubyte),('palette',C.c_void_p)]
class Metrics(C.Structure):
    _fields_ = [(n,C.c_long) for n in ['width','height','horiBearingX','horiBearingY','horiAdvance','vertBearingX','vertBearingY','vertAdvance']]
class Slot(C.Structure):
    _fields_ = [('library',C.c_void_p),('face',C.c_void_p),('next',C.c_void_p),('glyph_index',C.c_uint),('generic',Generic),('metrics',Metrics),('linearHoriAdvance',C.c_long),('linearVertAdvance',C.c_long),('advance',Vec),('format',C.c_uint),('bitmap',Bitmap),('bitmap_left',C.c_int),('bitmap_top',C.c_int)]
class Face(C.Structure):
    _fields_ = [(n,C.c_long) for n in ['num_faces','face_index','face_flags','style_flags','num_glyphs']]+[('family_name',C.c_char_p),('style_name',C.c_char_p),('num_fixed_sizes',C.c_int),('available_sizes',C.c_void_p),('num_charmaps',C.c_int),('charmaps',C.c_void_p),('generic',Generic),('bbox',BBox),('units_per_EM',C.c_ushort)]+[(n,C.c_short) for n in ['ascender','descender','height','max_advance_width','max_advance_height','underline_position','underline_thickness']]+[('glyph',C.POINTER(Slot))]

class Fonts:
    def __init__(self):
        self.lib=C.CDLL(find_library('freetype'))
        self.lib.FT_Init_FreeType.argtypes=[C.POINTER(C.c_void_p)]
        self.lib.FT_New_Face.argtypes=[C.c_void_p,C.c_char_p,C.c_long,C.POINTER(C.POINTER(Face))]
        self.lib.FT_Set_Pixel_Sizes.argtypes=[C.POINTER(Face),C.c_uint,C.c_uint]
        self.lib.FT_Load_Char.argtypes=[C.POINTER(Face),C.c_ulong,C.c_int]
        self.library=C.c_void_p();assert self.lib.FT_Init_FreeType(C.byref(self.library))==0
        self.faces={};self.cache={}
        names={'sans':'DejaVuSans.ttf','bold':'DejaVuSans-Bold.ttf','mono':'DejaVuSansMono.ttf','mono-bold':'DejaVuSansMono-Bold.ttf'}
        for key,name in names.items():
            face=C.POINTER(Face)();path=Path('/usr/share/fonts/truetype/dejavu')/name
            assert self.lib.FT_New_Face(self.library,str(path).encode(),0,C.byref(face))==0
            self.faces[key]=face
    def glyph(self,char,size,font):
        key=(char,size,font)
        if key not in self.cache:
            face=self.faces[font];assert self.lib.FT_Set_Pixel_Sizes(face,0,round(size*SCALE))==0
            assert self.lib.FT_Load_Char(face,ord(char),4)==0
            s=face.contents.glyph.contents;b=s.bitmap
            mask=np.ctypeslib.as_array(b.buffer,shape=(b.rows*abs(b.pitch),)).reshape(b.rows,abs(b.pitch))[:,:b.width].copy() if b.rows and b.width else np.empty((0,0),np.uint8)
            self.cache[key]=(mask,s.bitmap_left,s.bitmap_top,s.advance.x/64)
        return self.cache[key]
    def width(self,text,size,font='sans'):
        return sum(self.glyph(c,size,font)[3] for c in text)/SCALE

FONTS=Fonts()
def rgb(color):return np.array([int(color[i:i+2],16) for i in (1,3,5)],dtype=np.uint8)

def png(path,array):
    h,w,_=array.shape
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    raw=b''.join(b'\0'+row.tobytes() for row in array)
    path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw,6))+chunk(b'IEND',b''))

class Page:
    def __init__(self,name,w,h,title,subtitle):
        self.name=name;self.w=w;self.h=h;self.items=[];self.text_boxes=[]
        self.rect(0,0,w,h,'#FFFFFF',None)
        self.text(64,62,title,32,'bold',INK)
        self.text(64,95,subtitle,16,'sans',MUTED)
    def rect(self,x,y,w,h,fill='#FFFFFF',stroke=BORDER,lw=1.2,ident=None):
        self.items.append(dict(kind='rect',x=x,y=y,w=w,h=h,fill=fill,stroke=stroke,lw=lw,id=ident))
        return ident
    def text(self,x,y,text,size=18,font='sans',color=INK,align='left',max_width=None):
        width=FONTS.width(text,size,font)
        if max_width is not None:assert width<=max_width,(self.name,text,width,max_width)
        if align=='center':x-=width/2
        if align=='right':x-=width
        assert x>=0 and x+width<=self.w+1,(self.name,text,'outside page')
        self.items.append(dict(kind='text',x=x,y=y,text=text,size=size,font=font,color=color,width=width))
        self.text_boxes.append((x,y-size,width,size,text))
    def poly(self,points,color=MUTED,lw=1.6,dash=False,arrow=False,source=None,target=None):
        self.items.append(dict(kind='line',points=points,color=color,lw=lw,dash=dash,arrow=arrow,source=source,target=target))
    def arrow(self,x1,y1,x2,y2,label=None,color=INK,dash=False,lw=1.5):
        self.poly([(x1,y1),(x2,y2)],color,lw,dash,True)
        if label:self.text((x1+x2)/2,y1-9,label,14,'sans',color,'center',max_width=abs(x2-x1)-22 if x1!=x2 else None)
    def card(self,ident,x,y,w,h,title,lines=(),color=INK):
        self.rect(x,y,w,h,'#FFFFFF',color,1.3,ident)
        self.text(x+w/2,y+31,title,21,'bold',color,'center',w-20)
        for i,line in enumerate(lines):self.text(x+w/2,y+58+i*23,line,15,'sans',MUTED,'center',w-22)
    def footer(self,text):
        self.poly([(64,self.h-57),(self.w-64,self.h-57)],BORDER,1)
        self.text(64,self.h-29,text,14,'sans',MUTED,max_width=self.w-128)
    def save(self):
        ns='http://www.w3.org/2000/svg';ET.register_namespace('',ns)
        svg=ET.Element('{'+ns+'}svg',{'width':str(self.w),'height':str(self.h),'viewBox':f'0 0 {self.w} {self.h}','role':'img','aria-label':self.name})
        ET.SubElement(svg,'title').text=self.name
        image=np.full((self.h*SCALE,self.w*SCALE,3),255,np.uint8)
        mx=ET.Element('mxfile',{'host':'app.diagrams.net','type':'device'})
        diagram=ET.SubElement(mx,'diagram',{'name':self.name,'id':self.name})
        model=ET.SubElement(diagram,'mxGraphModel',{'grid':'1','gridSize':'10','page':'1','pageWidth':str(self.w),'pageHeight':str(self.h)})
        root=ET.SubElement(model,'root');ET.SubElement(root,'mxCell',{'id':'0'});ET.SubElement(root,'mxCell',{'id':'1','parent':'0'})
        def rect_pixels(x,y,w,h,color):
            image[max(0,round(y*SCALE)):min(self.h*SCALE,round((y+h)*SCALE)),max(0,round(x*SCALE)):min(self.w*SCALE,round((x+w)*SCALE))]=rgb(color)
        def polygon(points,color):
            p=np.array(points)*SCALE;lo=np.floor(p.min(0)).astype(int);hi=np.ceil(p.max(0)).astype(int)
            lo=np.maximum(lo,0);hi=np.minimum(hi,[self.w*SCALE-1,self.h*SCALE-1])
            if np.any(hi<lo):return
            xx,yy=np.meshgrid(np.arange(lo[0],hi[0]+1)+.5,np.arange(lo[1],hi[1]+1)+.5)
            signs=[]
            for a,b in zip(p,np.roll(p,-1,axis=0)):signs.append((b[0]-a[0])*(yy-a[1])-(b[1]-a[1])*(xx-a[0]))
            mask=np.logical_or(np.logical_and.reduce([s>=0 for s in signs]),np.logical_and.reduce([s<=0 for s in signs]))
            image[lo[1]:hi[1]+1,lo[0]:hi[0]+1][mask]=rgb(color)
        def segment(a,b,color,lw):
            ax,ay=a;bx,by=b;length=math.hypot(bx-ax,by-ay)
            if not length:return
            dx=-(by-ay)/length*lw/2;dy=(bx-ax)/length*lw/2
            polygon([(ax+dx,ay+dy),(bx+dx,by+dy),(bx-dx,by-dy),(ax-dx,ay-dy)],color)
        for n,item in enumerate(self.items):
            ident=item.get('id') or 'cell-'+str(n)
            if item['kind']=='rect':
                x,y,w,h=(item[k] for k in ['x','y','w','h']);fill=item['fill'];stroke=item['stroke'];lw=item['lw']
                attrs={'x':str(x),'y':str(y),'width':str(w),'height':str(h),'fill':fill,'stroke':stroke or 'none','stroke-width':str(lw)};ET.SubElement(svg,'rect',attrs)
                rect_pixels(x,y,w,h,fill)
                if stroke:
                    for a,b in [((x,y),(x+w,y)),((x+w,y),(x+w,y+h)),((x+w,y+h),(x,y+h)),((x,y+h),(x,y))]:segment(a,b,stroke,lw)
                cell=ET.SubElement(root,'mxCell',{'id':ident,'parent':'1','vertex':'1','style':f'rounded=0;whiteSpace=wrap;fillColor={fill};strokeColor={stroke or "none"};strokeWidth={lw};'})
                ET.SubElement(cell,'mxGeometry',{'x':str(x),'y':str(y),'width':str(w),'height':str(h),'as':'geometry'})
            elif item['kind']=='text':
                x,y,text,size,font,color=(item[k] for k in ['x','y','text','size','font','color']);family='DejaVu Sans Mono' if font.startswith('mono') else 'DejaVu Sans';bold='bold' in font
                node=ET.SubElement(svg,'text',{'x':str(x),'y':str(y),'font-family':family+', Arial, sans-serif','font-size':str(size),'font-weight':'700' if bold else '400','fill':color,'style':'font-kerning:none;font-variant-ligatures:none'});node.text=text
                cursor=x*SCALE
                for c in text:
                    mask,left,top,advance=FONTS.glyph(c,size,font);height,width=mask.shape
                    px=round(cursor)+left;py=round(y*SCALE)-top
                    if width and height:
                        assert px>=0 and py>=0 and px+width<=self.w*SCALE and py+height<=self.h*SCALE,(self.name,text,'raster clipping')
                        patch=image[py:py+height,px:px+width];alpha=mask.astype(np.uint32)[:,:,None]
                        patch[:]=((patch.astype(np.uint32)*(255-alpha)+rgb(color).astype(np.uint32)*alpha+127)//255).astype(np.uint8)
                    cursor+=advance
                containers=[r for r in self.items if r['kind']=='rect' and r.get('id') and x>=r['x'] and x+item['width']<=r['x']+r['w'] and y-size>=r['y'] and y+2<=r['y']+r['h']]
                owner=min(containers,key=lambda r:r['w']*r['h']) if containers else None
                parent=owner['id'] if owner else '1'
                gx=x-owner['x'] if owner else x;gy=y-size-owner['y'] if owner else y-size
                cell=ET.SubElement(root,'mxCell',{'id':ident,'parent':parent,'vertex':'1','value':text,'style':f'text;html=0;align=left;verticalAlign=bottom;spacing=0;whiteSpace=wrap;fontFamily={family};fontSize={size};fontColor={color};fontStyle={1 if bold else 0};'})
                ET.SubElement(cell,'mxGeometry',{'x':str(gx),'y':str(gy),'width':str(item['width']+4),'height':str(size+4),'as':'geometry'})
            else:
                points=item['points'];color=item['color'];lw=item['lw'];dash=item['dash'];arrow=item['arrow']
                attrs={'points':' '.join(f'{x},{y}' for x,y in points),'fill':'none','stroke':color,'stroke-width':str(lw)}
                if dash:attrs['stroke-dasharray']='6 5'
                ET.SubElement(svg,'polyline',attrs)
                for a,b in zip(points,points[1:]):
                    length=math.hypot(b[0]-a[0],b[1]-a[1])
                    if dash:
                        for distance in np.arange(0,length,11):
                            t1=distance/length;t2=min(distance+6,length)/length
                            segment((a[0]+(b[0]-a[0])*t1,a[1]+(b[1]-a[1])*t1),(a[0]+(b[0]-a[0])*t2,a[1]+(b[1]-a[1])*t2),color,lw)
                    else:segment(a,b,color,lw)
                if arrow:
                    a,b=points[-2:];angle=math.atan2(b[1]-a[1],b[0]-a[0]);length=9+lw;wing=4+lw/2
                    triangle=[b,(b[0]-length*math.cos(angle)+wing*math.sin(angle),b[1]-length*math.sin(angle)-wing*math.cos(angle)),(b[0]-length*math.cos(angle)-wing*math.sin(angle),b[1]-length*math.sin(angle)+wing*math.cos(angle))]
                    ET.SubElement(svg,'polygon',{'points':' '.join(f'{x},{y}' for x,y in triangle),'fill':color});polygon(triangle,color)
                attrib={'id':ident,'parent':'1','edge':'1','style':f'edgeStyle=none;rounded=0;strokeColor={color};strokeWidth={lw};dashed={1 if dash else 0};endArrow={"block" if arrow else "none"};endFill=1;'}
                if item['source']:attrib['source']=item['source']
                if item['target']:attrib['target']=item['target']
                cell=ET.SubElement(root,'mxCell',attrib);geo=ET.SubElement(cell,'mxGeometry',{'relative':'1','as':'geometry'})
                ET.SubElement(geo,'mxPoint',{'x':str(points[0][0]),'y':str(points[0][1]),'as':'sourcePoint'});ET.SubElement(geo,'mxPoint',{'x':str(points[-1][0]),'y':str(points[-1][1]),'as':'targetPoint'})
                if len(points)>2:
                    arr=ET.SubElement(geo,'Array',{'as':'points'})
                    for x,y in points[1:-1]:ET.SubElement(arr,'mxPoint',{'x':str(x),'y':str(y)})
        ET.indent(svg);ET.ElementTree(svg).write(OUT/(self.name+'.svg'),encoding='utf-8',xml_declaration=True)
        ET.indent(mx);ET.ElementTree(mx).write(OUT/(self.name+'.drawio'),encoding='utf-8',xml_declaration=True)
        png(OUT/(self.name+'.png'),image)
        return {'name':self.name,'logical_size':[self.w,self.h],'png_size':[self.w*SCALE,self.h*SCALE],'editable_cells':len(self.items),'text_elements':len(self.text_boxes)}

# Figure specifications follow below. Every component/message is code-audited.

def system_architecture():
    p=Page('01-system-architecture',1920,1080,'AgentOps RCA | System architecture','Source-audited implementation · Layered single-host design · Not a live execution trace')
    bands=[(136,150,'#EBF3FC',BLUE,'01  CLIENT / API','Validated HTTP entry'),(310,166,'#F2EEFA',PURPLE,'02  ORCHESTRATION','One API process / worker'),(500,280,'#EAF7F5',TEAL,'03  TOOLS /','INTELLIGENCE'),(806,150,'#FDF2E7',ORANGE,'04  STATE /','OBSERVABILITY')]
    for y,h,bg,c,title,subtitle in bands:
        p.rect(60,y,1430,h,bg,None)
        p.text(84,y+49,title,19,'bold',c,max_width=245)
        p.text(84,y+79,subtitle,16,'sans',MUTED,max_width=245)
    p.text(1540,175,'RUNTIME BOUNDARY',17,'bold',MUTED,max_width=320)
    for i,t in enumerate(['Linux + Conda agent-dev','Single Uvicorn worker','No application container','MCP over local STDIO']):p.text(1540,209+i*28,t,16,'sans',MUTED,max_width=320)
    p.rect(1520,500,340,280,'#F2F4F7',None)
    p.text(1540,532,'EXTERNAL PROVIDER',17,'bold',MUTED,max_width=300)
    p.card('client',350,172,260,80,'Client / Tester',['HTTP message / decision'],BLUE)
    p.card('api',735,172,700,80,'FastAPI · app.main:app',['Request validation · Session API · Loopback only'],BLUE)
    p.card('runtime',350,350,320,96,'Traced Runtime',['Agent Runtime · lifecycle','Session guard · Trace context'],PURPLE)
    p.card('graph',750,350,360,96,'LangGraph Workflow',['Agent State · RCA / chat','Evidence validation → response'],PURPLE)
    p.card('hitl',1190,350,245,96,'HITL',['Conditional interrupt','Same-thread resume'],PURPLE)
    p.card('sdk',1100,540,335,86,'DeepSeek LLM Client',['Async Agent · Sync RAG'],TEAL)
    p.card('mcp',725,540,300,86,'MCP Clients',['STDIO · Tool / result checks'],TEAL)
    p.card('memory',350,540,300,86,'Long-term Memory',['Historical hints · JSON / FAISS'],TEAL)
    p.card('obs',350,658,330,98,'Observability MCP',['INC evidence','Synthetic metrics / logs / traces'],TEAL)
    p.card('utility',720,658,255,98,'Utility MCP',['Chat branch only','Optional demo tools'],TEAL)
    p.card('rag',1015,658,420,98,'RAG MCP + Local Retrieval',['Embedding · FAISS · Reranker','Chat only · LLM judge / generate'],TEAL)
    p.card('provider',1540,560,300,110,'DeepSeek API',['External LLM provider','Not inside host / Docker'],MUTED)
    p.text(1540,710,'CURRENT LIVE E2E',15,'bold',ORANGE)
    p.text(1540,740,'BLOCKED · Credentials missing',15,'sans',MUTED,max_width=300)
    p.rect(336,830,775,112,'#FFF9F2',ORANGE,1)
    p.text(350,824,'Docker Compose data services',13,'bold',ORANGE)
    p.card('pg',350,846,420,80,'PostgreSQL',['Session · Checkpoint · Simulation audit'],ORANGE)
    p.card('redis',825,846,270,80,'Redis',['Case cache · Rate limit'],ORANGE)
    p.text(1150,832,'API process + host file',13,'bold',MUTED)
    p.card('trace',1150,846,285,80,'Trace Collector',['Metadata → JSONL'],ORANGE)
    p.poly([(610,212),(735,212)],BLUE,3,arrow=True,source='client',target='api')
    p.poly([(850,252),(850,298),(510,298),(510,350)],BLUE,3,arrow=True,source='api',target='runtime')
    p.poly([(670,398),(750,398)],PURPLE,3,arrow=True,source='runtime',target='graph')
    p.poly([(1110,398),(1190,398)],PURPLE,1.7,True,True,source='graph',target='hitl')
    p.poly([(1300,446),(1300,468),(1050,468),(1050,446)],PURPLE,1.3,True,True,source='hitl',target='graph')
    p.text(1145,463,'human resume',11,'sans',PURPLE)
    for x in [500,875,1267]:p.poly([(930,446),(930,488),(x,488),(x,540)],TEAL,1.8,False,True)
    for x,dashed in [(515,False),(847,True),(1225,True)]:p.poly([(875,626),(875,644),(x,644),(x,658)],TEAL,1.6,dashed,True)
    p.poly([(1435,583),(1540,583)],MUTED,1.6,False,True,source='sdk',target='provider')
    p.text(1450,575,'SDK / API',12,'sans',MUTED)
    # One support bus avoids pretending storage and tracing are inference stages.
    p.poly([(365,446),(330,446),(330,792),(1293,792)],ORANGE,1.2,True)
    for x in [560,960,1293]:p.poly([(x,792),(x,846)],ORANGE,1.2,True,True)
    p.poly([(76,985),(124,985)],BLUE,3,arrow=True);p.text(136,991,'Main request',14,'sans',MUTED)
    p.poly([(340,985),(388,985)],TEAL,1.6,True,True);p.text(400,991,'Conditional call',14,'sans',MUTED)
    p.poly([(640,985),(688,985)],ORANGE,1.2,True,True);p.text(700,991,'Supporting state / Trace',14,'sans',MUTED)
    p.text(1120,991,'Arrows show calls; results are detailed in the sequence.',14,'sans',MUTED,max_width=700)
    p.footer('Synthetic telemetry and simulated actions only · Real DeepSeek E2E pending credentials · Source: main 4313fe1 + audited working tree')
    return p


def project_structure():
    p=Page('03-project-structure',1700,1260,'AgentOps RCA | Project structure','Responsibility-based packages · Core files only · Runtime data and model weights excluded')
    rows=[
      (0,'agentops-rca/','Audited repository root',True),
      (1,'app/','Python application',True),
      (2,'main.py','FastAPI entry: app.main:app',False),
      (2,'agent/','Runtime · LangGraph workflow · HITL · Recovery',True),
      (2,'api/','HTTP routes and request validation',True),
      (2,'core/','Configuration · Deployment paths · Context budget',True),
      (2,'memory/','Memory Store and semantic recall',True),
      (2,'rag/','Chunking · Embedding · Retrieval · Reranking',True),
      (2,'rca/','Evidence rules and synthetic incident data',True),
      (2,'storage/','PostgreSQL and Redis adapters',True),
      (2,'telemetry/','Collector · Trace callbacks · Reports',True),
      (2,'tools/','MCP clients / servers · STDIO launcher',True),
      (1,'docs/','Architecture · Deployment · Testing · Security',True),
      (2,'architecture/','Architecture diagrams and editable figure sources',True),
      (2,'refactor/','Migration maps and regression audits',True),
      (2,'release/','Preserved release evidence',True),
      (1,'scripts/','Operations · Deployment probes · Test runners',True),
      (1,'tests/','12 offline regression groups and fixtures',True),
      (1,'evaluation/','Standalone scoring and robustness rules',True),
      (1,'verification/','Sanitized evidence and validation results',True),
      (1,'documents/','Public synthetic knowledge base',True),
      (1,'deploy/','Redis configuration and model manifest',True),
      (1,'docker-compose.yml','PostgreSQL / Redis containers only',False),
      (1,'Dockerfile','Redis configuration image',False),
      (1,'requirements.txt','Runtime dependencies and version constraints',False),
      (1,'environment.yml','Conda agent-dev environment',False),
      (1,'README.md','GitHub project overview',False),
      (1,'LICENSE','Project license; upstream notices kept separately',False),
    ]
    # Validate names against real directories rather than copying a reference tree.
    appdirs=[r[1].rstrip('/') for r in rows if r[0]==2 and r[1].endswith('/')][:9]
    for name in appdirs:assert (ROOT/'app'/name).is_dir(),name
    for name in ['main.py']:assert (ROOT/'app'/name).is_file()
    for name in ['docs','scripts','tests','evaluation','verification','documents','deploy']:assert (ROOT/name).is_dir()
    p.text(84,147,'DIRECTORY / FILE',14,'bold',MUTED)
    p.text(660,147,'RESPONSIBILITY',14,'bold',MUTED)
    p.poly([(84,162),(1616,162)],BORDER,1)
    start=201;gap=34;indent=44
    for i,(depth,name,description,is_dir) in enumerate(rows):
        y=start+i*gap
        if depth:
            branch_x=96+(depth-1)*indent;name_x=branch_x+30
            # Parent stem stops at the last child in the current sibling range.
            last=True
            for later in rows[i+1:]:
                if later[0]<depth:break
                if later[0]==depth:last=False;break
            p.poly([(branch_x,y-gap+3),(branch_x,y-7 if last else y+gap-7)],'#BCC6D2',1)
            p.poly([(branch_x,y-7),(name_x-9,y-7)],'#BCC6D2',1)
            if depth==2:p.poly([(96,y-gap+3),(96,y+gap-7)],'#BCC6D2',1)
        else:name_x=84
        p.text(name_x,y,name,20,'mono-bold' if is_dir else 'mono',BLUE if is_dir else INK,max_width=530)
        p.text(660,y,description,18,'sans',MUTED,max_width=950)
    p.footer('Tree matches audited source paths · Architecture figures include editable sources · Generated indexes, secrets and state are omitted')
    return p

class Sequence:
    def __init__(self):
        self.y=290;self.events=[];self.frames=[];self.activations=[]
    def msg(self,a,b,text,reply=False):
        self.events.append(('msg',self.y,a,b,text,reply));self.y+=38
    def call(self,a,text):
        self.events.append(('self',self.y,a,text));self.y+=42
    def note(self,text):
        self.events.append(('note',self.y,text));self.y+=46
    def begin(self,label):
        start=self.y;self.y+=54;return (start,label)
    def end(self,token):
        self.frames.append((token[0],self.y+4,token[1]));self.y+=26
    def alternate(self,text):
        self.events.append(('else',self.y,text));self.y+=48


def request_sequence():
    q=Sequence()
    t=q.begin('opt  New Session only — existing sessions reuse their ID')
    q.msg('client','api','POST /sessions')
    q.msg('api','rt','create_session()')
    q.msg('rt','pg','INSERT session_id → thread_id; commit before exposure')
    q.msg('pg','rt','mapping committed',True)
    q.msg('rt','api','durable session_id',True)
    q.msg('api','client','201 Created',True)
    q.end(t)
    q.note('MESSAGE REQUEST  ·  HTTP validation and Redis quota precede traced ask')
    request_start=q.y
    q.msg('client','api','POST /messages')
    q.call('api','validate input')
    q.msg('api','rt','enforce_message_rate_limit')
    q.call('rt','validate Session')
    q.msg('rt','redis','Lua INCR / EXPIRE: message quota')
    q.msg('redis','rt','allowed + counter + TTL',True)
    q.msg('rt','api','quota accepted',True)
    q.msg('api','rt','ask(sid, message)')
    ask_start=q.y
    q.call('rt','create Trace scope')
    q.msg('rt','graph','aget_state(thread)')
    q.msg('graph','pg','read current Checkpoint')
    q.msg('pg','graph','saved state',True)
    q.msg('graph','rt','snapshot',True)
    q.call('rt','guard pending state')
    q.msg('rt','graph','ainvoke(question)')
    graph_start=q.y
    q.call('graph','retrieve_memory hints')
    planner_start=q.y
    q.msg('graph','llm','SDK: Planner JSON request')
    q.msg('llm','graph','JSON tool plan',True)
    planner_end=q.y
    q.call('graph','normalize whitelist')
    t=q.begin('loop  Each normalized read-only tool: metrics / logs / traces [+ topology]')
    mcp_start=q.y
    q.msg('graph','mcp','query_observability_tool')
    q.msg('mcp','obs','STDIO call_tool')
    q.msg('obs','mcp','synthetic observation',True)
    q.msg('mcp','graph','validated tool data',True)
    mcp_end=q.y
    q.end(t)
    q.call('graph','make evidence catalog')
    rca_start=q.y
    q.msg('graph','llm','SDK: structured RCA JSON request (max_tokens=2200)')
    q.msg('llm','graph','model hypotheses + evidence IDs',True)
    rca_end=q.y
    q.call('graph','validate_rca')
    t=q.begin('opt  Validation fails: regenerate once; final failure returns insufficient evidence')
    q.msg('graph','llm','validation feedback → one new JSON generation')
    q.msg('llm','graph','new JSON, then Python validates again',True)
    q.end(t)
    t=q.begin('alt  Eligible simulation proposal')
    q.call('graph','human_approval interrupt')
    q.alternate('else  No eligible proposal')
    q.call('graph','END without action')
    q.end(t)
    q.msg('graph','pg','Saver checkpoints at graph steps / interrupt (not only at END)')
    q.msg('pg','graph','durable state',True)
    q.msg('graph','rt','result or interrupted result',True)
    graph_end=q.y
    q.msg('rt','graph','aget_state(thread)')
    q.msg('graph','pg','read resulting Checkpoint')
    q.msg('pg','graph','completed / pending state',True)
    q.msg('graph','rt','snapshot',True)
    q.call('rt','finally: Trace JSONL')
    ask_end=q.y
    q.msg('rt','api','response summary',True)
    q.msg('api','client','200 completed / pending',True)
    request_end=q.y
    q.note('HITL RESUME  ·  Separate HTTP request, same Session / thread; no automatic approval')
    t=q.begin('opt  A human later sends a valid decision for the pending action_id')
    resume_start=q.y
    q.msg('client','api','POST /decisions')
    q.msg('api','rt','approve(action, decision)')
    q.call('rt','create new Trace scope')
    q.msg('rt','graph','aget_state(thread)')
    q.msg('graph','pg','read pending Checkpoint')
    q.msg('pg','graph','pending proposal',True)
    q.msg('graph','rt','pending state',True)
    q.call('rt','check pending / action_id')
    q.msg('rt','graph','ainvoke(Command(resume))')
    q.call('graph','re-enter human_approval')
    q.msg('graph','pg','Write simulated / rejected audit; Saver checkpoints are separate writes')
    q.msg('pg','graph','audit and state retained',True)
    q.msg('graph','rt','graph result',True)
    q.msg('rt','graph','aget_state(thread)')
    q.msg('graph','pg','read final Checkpoint')
    q.msg('pg','graph','state',True)
    q.msg('graph','rt','snapshot',True)
    q.call('rt','finally: Trace JSONL')
    q.msg('rt','api','updated summary',True)
    q.msg('api','client','200 · simulated result',True)
    resume_end=q.y
    q.end(t)
    q.note('Guard failures keep existing 4xx / 503 rules; LLM/tool failures retain conservative fallback behavior.')
    height=round(q.y+125)
    p=Page('02-request-sequence',2220,height,'AgentOps RCA | RCA request sequence','Source-defined INC path · Real DeepSeek E2E pending credentials · RAG / Utility chat branch is intentionally not shown')
    actors={
        'client':(130,'Client','Tester / human',BLUE),
        'api':(340,'FastAPI','Validation / routes',BLUE),
        'rt':(570,'Traced Runtime','Agent Runtime',PURPLE),
        'graph':(810,'LangGraph','State / LLM calls',PURPLE),
        'mcp':(1050,'MCP Client','Result validation',TEAL),
        'obs':(1290,'Observability','MCP Server',TEAL),
        'llm':(1540,'DeepSeek API','External provider',MUTED),
        'pg':(1790,'PostgreSQL','Saver / registry / audit',ORANGE),
        'redis':(2050,'Redis','Message quota',ORANGE),
    }
    # UML interaction frames behind all lifelines and messages.
    for start,end,label in sorted(q.frames,key=lambda row:row[1]-row[0],reverse=True):
        p.rect(64,start,2092,end-start,'#FFFFFF',BORDER,1)
    for x,w,label,c in [(245,910,'API process · Single worker',PURPLE),(1185,210,'STDIO subprocess',TEAL),(1435,210,'External service',MUTED),(1685,470,'Docker Compose',ORANGE)]:
        p.rect(x,118,w,27,'#F5F7FA',None)
        p.text(x+w/2,137,label,13,'bold',c,'center',w-10)
    bottom=height-100
    for key,(x,title,subtitle,color) in actors.items():
        p.poly([(x,224),(x,bottom)],'#ABB7C6',1,True)
        p.rect(x-92,151,184,73,'#FFFFFF',color,1.3,'actor-'+key)
        p.text(x,180,title,17,'bold',color,'center',174)
        p.text(x,204,subtitle,12,'sans',MUTED,'center',174)
    for key,start,end in [('api',request_start,request_end),('rt',ask_start,ask_end),('graph',graph_start,graph_end),('llm',planner_start,planner_end),('llm',rca_start,rca_end),('mcp',mcp_start,mcp_end),('obs',mcp_start+38,mcp_end-38),('api',resume_start,resume_end),('rt',resume_start+38,resume_end-38)]:
        x=actors[key][0];p.rect(x-5,start,10,max(18,end-start-18),'#F3EDFB',PURPLE,1)
    # Frame captions are foreground so activation bars never obscure the text.
    for start,end,label in q.frames:
        tabw=min(1800,FONTS.width(label,14,'bold')+28)
        p.rect(64,start,tabw,31,'#F6F8FB',BORDER,1)
        p.text(77,start+21,label,14,'bold',INK,max_width=2050)
    for event in q.events:
        kind,y,*args=event
        if kind=='msg':
            a,b,text,reply=args;ax=actors[a][0];bx=actors[b][0]
            p.arrow(ax,y,bx,y,text,MUTED if reply else INK,reply,1.3)
        elif kind=='self':
            a,text=args;x=actors[a][0]
            p.poly([(x,y),(x+66,y),(x+66,y+17),(x,y+17)],actors[a][3],1.2,False,True)
            nextx=min([v[0] for v in actors.values() if v[0]>x] or [2220])
            p.text(x+14,y-8,text,13,'sans',actors[a][3],max_width=nextx-x-24)
        elif kind=='note':
            p.rect(64,y-18,2092,34,'#F5F7FA',None)
            p.text(80,y+5,args[0],15,'bold',MUTED,max_width=2040)
        elif kind=='else':
            p.poly([(64,y),(2156,y)],BORDER,1,True)
            p.rect(76,y+5,450,28,'#FFFFFF',None)
            p.text(80,y+24,args[0],14,'bold',MUTED)
    p.footer('Solid = request / internal call · Dashed = return / lifeline · opt / alt / loop are source-defined · Synthetic evidence; simulated actions only')
    return p


def main():
    records=[]
    for builder in [system_architecture,request_sequence,project_structure]:
        page=builder();records.append(page.save());print(page.name+' exported',flush=True)
    (OUT/'export-manifest.json').write_text(json.dumps({'renderer':'Shared geometry → native SVG / editable mxGraph XML / FreeType 2x PNG','dependencies':'Existing NumPy and system FreeType; no installations or network','figures':records,'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.iterdir()) if p.suffix in {'.svg','.png','.drawio'}}},indent=2)+'\n')

if __name__=='__main__':main()
