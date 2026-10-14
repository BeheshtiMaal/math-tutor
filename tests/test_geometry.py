"""Closed geometry scenes, measured mathematics and direct interaction API."""
import copy
import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from pydantic import ValidationError

import agent
from fakes import FakeModelClient, FakeRetrievalClient
from test_learning_graph import source,evidence
from test_web_refactors import make_app,config_for
from webapp.geometry import compute_geometry
from webapp.ui_blocks import GeometryRequest,GeometryBlock,GeometryUpdateRequest
from webapp.threads import new_thread_id
from lesson_presentation import automatic_blocks


def setUpModule():
    global tracing
    tracing=patch.dict(os.environ,{'LANGSMITH_TRACING':'false','LANGCHAIN_TRACING_V2':'false','LANGCHAIN_TRACING':'false'})
    tracing.start()


def tearDownModule():tracing.stop()


SCENES=[{'kind':'unit_circle','angle_degrees':45.},
        {'kind':'triangle','vertices':[{'x':0.,'y':0.},{'x':4.,'y':0.},{'x':0.,'y':3.}]},
        {'kind':'vectors','u':{'x':3.,'y':1.},'v':{'x':1.,'y':2.}}]


def request(scene=SCENES[0]):
    return {'type':'geometry_canvas','title':'Unit circle','fallback_text':'The radius is one and the point gives sine and cosine.',
            'params':{'scene':copy.deepcopy(scene),'language':'en'}}


class GeometryMathChecks(unittest.TestCase):
    def test_unit_circle_quadrants_and_radian_conversion(self):
        for angle,expected in [(0,(1,0)),(90,(0,1)),(180,(-1,0)),(270,(0,-1)),(360,(1,0))]:
            data=compute_geometry({'kind':'unit_circle','angle_degrees':float(angle)})
            point=next(p for p in data.points if p.id=='P')
            self.assertAlmostEqual(point.x,expected[0]);self.assertAlmostEqual(point.y,expected[1])
            self.assertAlmostEqual(point.x**2+point.y**2,1)
        data=compute_geometry(SCENES[0]);values={m.key:m.value for m in data.metrics}
        self.assertAlmostEqual(values['angle_rad'],3.141592653589793/4)

    def test_triangle_angles_area_and_orientation(self):
        for vertices in [SCENES[1]['vertices'],list(reversed(SCENES[1]['vertices']))]:
            data=compute_geometry({'kind':'triangle','vertices':vertices});values={m.key:m.value for m in data.metrics}
            self.assertEqual(values['area'],6);self.assertEqual(values['perimeter'],12)
            self.assertAlmostEqual(sum(values['angle_'+id] for id in 'ABC'),180)

    def test_degenerate_triangle_does_not_invent_interior_angles(self):
        for vertices in [[{'x':0,'y':0},{'x':1,'y':0},{'x':2,'y':0}],[{'x':0,'y':0}]*3]:
            data=compute_geometry({'kind':'triangle','vertices':vertices})
            self.assertEqual(data.status,'degenerate')
            self.assertTrue(all(m.value is None for m in data.metrics if m.key.startswith('angle_')))

    def test_vectors_sum_dot_angle_and_zero_case(self):
        data=compute_geometry(SCENES[2]);values={m.key:m.value for m in data.metrics}
        p=next(p for p in data.points if p.id=='S')
        self.assertEqual((p.x,p.y),(4,3));self.assertEqual(values['length_sum'],5)
        self.assertEqual(values['dot'],5);self.assertAlmostEqual(values['between'],45)
        data=compute_geometry({'kind':'vectors','u':{'x':0,'y':0},'v':{'x':1,'y':2}})
        self.assertEqual(data.status,'zero_vector')
        self.assertIsNone(next(m.value for m in data.metrics if m.key=='between'))

    def test_closed_input_rejects_scripts_computed_measurements_and_unbounded_values(self):
        for field in ['geometry','html','svg','script','measurements']:
            raw=request();raw['params'][field]='bad'
            with self.assertRaises(ValidationError):GeometryRequest.model_validate(raw)
        for angle in [-1,361,float('nan'),float('inf'),'90']:
            with self.assertRaises(ValidationError):compute_geometry({'kind':'unit_circle','angle_degrees':angle})
        with self.assertRaises(ValidationError):compute_geometry({'kind':'triangle','vertices':[{'x':0,'y':0}]*4})
        with self.assertRaises(ValidationError):compute_geometry({'kind':'vectors','u':{'x':11,'y':0},'v':{'x':1,'y':2}})

    def test_natural_defaults_preserve_question_coordinates_and_angle(self):
        note=source().model_copy(update={'topic':'geometry','text':'A triangle, unit circle, and vectors.'})
        block=automatic_blocks('geometry','An explanation',[note],'fa','دایره واحد با زاویه ۹۰ درجه را توضیح بده')[0]
        self.assertEqual(block['params']['scene']['angle_degrees'],90)
        block=automatic_blocks('geometry','An explanation',[note],'en','triangle (0,0), (3,0), (0,4)')[0]
        self.assertEqual(block['params']['scene']['vertices'][1]['x'],3)


class GeometryHTTPChecks(unittest.TestCase):
    def app(self):
        note=source().model_copy(update={'topic':'geometry','text':'The unit circle has radius one. Coordinates give sine and cosine.'})
        model=FakeModelClient([{'steps':[{'objective':'Circle','explanation':'The unit circle has radius one. Coordinates give sine and cosine.','source_ids':[note.id]}]},
                              {'explanation':'The radius is fixed at one. Changing angle changes coordinates.','source_ids':[note.id]}])
        return (*make_app(config=config_for(language='en'),model=model,retrieval=FakeRetrievalClient(source=evidence([note]))),model)

    def test_scene_updates_without_model_or_lesson_advance_and_old_block_stays_usable(self):
        app,service,graph,model=self.app();thread=new_thread_id()
        with TestClient(app) as http:
            first=http.post('/api/chat/turn',json={'thread_id':thread,'message':'Explain the unit circle','mode':'learn','delivery':'step','level':'beginner'}).json()
            block=first['blocks'][0];self.assertEqual(block['type'],'geometry_canvas')
            snapshot=graph.get_state({'configurable':{'thread_id':thread}}).values
            payload={'thread_id':thread,'block_id':block['id'],'scene':{'kind':'unit_circle','angle_degrees':90.}}
            changed=http.post('/api/ui/geometry',json=payload)
            self.assertEqual(changed.status_code,200)
            p=next(p for p in changed.json()['points'] if p['id']=='P');self.assertEqual((p['x'],p['y']),(0,1))
            self.assertEqual(len(model.calls),1)
            self.assertEqual(graph.get_state({'configurable':{'thread_id':thread}}).values['explanation_version'],snapshot['explanation_version'])
            next_turn=http.post('/api/chat/turn',json={'thread_id':thread,'action':'followup','message':'Why is the radius one?'}).json()
            self.assertEqual(next_turn['blocks'],[])
            self.assertEqual(http.post('/api/ui/geometry',json=payload).status_code,200)

    def test_update_requires_issued_block_same_scene_kind_and_valid_thread(self):
        app,service,_,_=self.app();thread=new_thread_id();service.registry.register(thread)
        raw=request();block=GeometryBlock(id='blk_'+'0'*26,title=raw['title'],fallback_text=raw['fallback_text'],type=raw['type'],
            params={**raw['params'],'geometry':compute_geometry(SCENES[0])})
        service.remember_blocks(thread,[block.model_dump(mode='json')])
        with TestClient(app) as http:
            payload={'thread_id':thread,'block_id':block.id,'scene':SCENES[2]}
            self.assertEqual(http.post('/api/ui/geometry',json=payload).status_code,422)
            payload['scene']=SCENES[0];payload['block_id']='blk_'+'1'*26
            self.assertEqual(http.post('/api/ui/geometry',json=payload).status_code,422)
            payload['block_id']=block.id;payload['thread_id']=new_thread_id()
            self.assertEqual(http.post('/api/ui/geometry',json=payload).status_code,404)
            payload['thread_id']=thread;payload['scene']={'kind':'unit_circle','angle_degrees':999}
            self.assertEqual(http.post('/api/ui/geometry',json=payload).status_code,400)
            self.assertFalse(hasattr(service._ui_blocks[thread][block.id].params,'geometry'))
