"""Finite numeric geometry. No expressions, scripts, imports or model calls."""
import math

from .ui_blocks import GeometryResult, geometry_scene_adapter


def compute_geometry(scene):
    scene = geometry_scene_adapter.validate_python(scene)
    points, segments, circles, arcs, metrics = [], [], [], [], []
    status = 'ok'
    def clean(value):
        return 0.0 if abs(value) < 1e-12 else float(value)
    def point(id, x, y, draggable=False, label=None):
        points.append(dict(id=id, label=label or id, x=clean(x), y=clean(y), draggable=draggable))
    def segment(start,end,style='edge'):
        segments.append(dict(start=start,end=end,style=style))
    def metric(key,value,unit='scalar'):
        metrics.append(dict(key=key,value=None if value is None else clean(value),unit=unit))
    def arc(cx,cy,radius,start,delta):
        if abs(delta)>1e-10:
            arcs.append({'points':[dict(x=clean(cx+radius*math.cos(start+delta*i/48)),y=clean(cy+radius*math.sin(start+delta*i/48))) for i in range(49)]})
    if scene.kind == 'unit_circle':
        angle=math.radians(scene.angle_degrees)
        x,y=math.cos(angle),math.sin(angle)
        point('O',0,0); point('P',x,y,True); point('H',x,0)
        segment('O','P'); segment('O','H','projection'); segment('H','P','projection')
        circles.append(dict(center='O',radius=1.0))
        arc(0,0,.25,0,angle)
        metric('angle_deg',scene.angle_degrees,'degrees'); metric('angle_rad',angle,'radians')
        metric('cos',x); metric('sin',y)
        bounds=dict(min=-1.3,max=1.3)
    elif scene.kind == 'triangle':
        vertices=scene.vertices
        for id,p in zip('ABC',vertices):point(id,p.x,p.y,True)
        for a,b in [('A','B'),('B','C'),('C','A')]:segment(a,b)
        lengths=[math.hypot(vertices[(i+1)%3].x-p.x,vertices[(i+1)%3].y-p.y) for i,p in enumerate(vertices)]
        cross=(vertices[1].x-vertices[0].x)*(vertices[2].y-vertices[0].y)-(vertices[1].y-vertices[0].y)*(vertices[2].x-vertices[0].x)
        area=abs(cross)/2
        metric('area',area,'area'); metric('perimeter',sum(lengths),'length')
        for key,length in zip(['length_AB','length_BC','length_CA'],lengths):metric(key,length,'length')
        status='degenerate' if area<1e-8 or min(lengths)<1e-8 else 'ok'
        for i,p in enumerate(vertices):
            a,b=vertices[(i+1)%3],vertices[(i+2)%3]
            ux,uy,vx,vy=a.x-p.x,a.y-p.y,b.x-p.x,b.y-p.y
            angle=None if status=='degenerate' else math.atan2(abs(ux*vy-uy*vx),ux*vx+uy*vy)
            metric('angle_'+ 'ABC'[i],None if angle is None else math.degrees(angle),'degrees')
            if angle is not None:
                start=math.atan2(uy,ux)
                delta=(math.atan2(vy,vx)-start+math.pi)%(2*math.pi)-math.pi
                arc(p.x,p.y,min(1,.22*math.hypot(ux,uy),.22*math.hypot(vx,vy)),start,delta)
    else:
        u,v=scene.u,scene.v
        point('O',0,0); point('U',u.x,u.y,True,'u'); point('V',v.x,v.y,True,'v'); point('S',u.x+v.x,u.y+v.y,False,'u+v')
        segment('O','U','vector'); segment('O','V','vector'); segment('O','S','vector')
        segment('U','S','projection'); segment('V','S','projection')
        lu,lv=math.hypot(u.x,u.y),math.hypot(v.x,v.y)
        dot=u.x*v.x+u.y*v.y
        angle=None if min(lu,lv)<1e-10 else math.atan2(abs(u.x*v.y-u.y*v.x),dot)
        status='zero_vector' if angle is None else 'ok'
        metric('length_u',lu,'length'); metric('length_v',lv,'length')
        metric('length_sum',math.hypot(u.x+v.x,u.y+v.y),'length'); metric('dot',dot)
        metric('between',None if angle is None else math.degrees(angle),'degrees')
        if angle is not None:
            start=math.atan2(u.y,u.x)
            delta=(math.atan2(v.y,v.x)-start+math.pi)%(2*math.pi)-math.pi
            arc(0,0,min(1,.25*lu,.25*lv),start,delta)
    if scene.kind!='unit_circle':
        values=[value for p in points for value in (p['x'],p['y'])]
        padding=max(.8,(max(values)-min(values))*.12)
        bounds=dict(min=min(values)-padding,max=max(values)+padding)
    return GeometryResult.model_validate(dict(status=status,scene=scene.model_dump(),bounds=bounds,
        points=points,segments=segments,circles=circles,arcs=arcs,metrics=metrics))
