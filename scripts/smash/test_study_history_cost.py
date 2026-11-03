import copy
import unittest

from study_history_cost import request_model,invented_node,manifest_node,payload_model,study


class HistoryCostStudy(unittest.TestCase):
    def test_split_is_not_always_cheaper_and_does_not_claim_a_real_capture(self):
        rows={r['name']:r for r in study()['cases']}
        self.assertEqual((rows['long_history_50_current_cold']['currentRequests'],rows['long_history_50_current_cold']['splitRequests']),(200,30))
        self.assertEqual(rows['all_current_cold']['splitRequests'],220)
        self.assertGreater(rows['all_current_cold']['extraRequests'],0)
        self.assertEqual(rows['long_history_same_page_size']['splitRequests'],210)
        self.assertEqual(study()['status'],'offline_simulation_not_a_capture')

    def test_per_player_page_rounding_and_shared_details_do_not_invent_cache_hits(self):
        short=request_model([5]*100,500,0)
        self.assertEqual((short['currentRequests'],short['lightListRequests'],short['splitRequests']),(100,100,200))
        shared=request_model([250]*4,500,400)
        self.assertEqual((shared['lightListRequests'],shared['detailRequests'],shared['splitRequests']),(20,20,40))
        self.assertEqual(shared['detailCacheMisses'],100)
        uncached=request_model([250]*4,500,0)
        self.assertEqual(uncached['detailCacheMisses'],500)
        self.assertEqual(request_model([],0,0)['splitRequests'],0)
        empty_roots=request_model([0]*5,0,0)
        self.assertEqual((empty_roots['currentRequests'],empty_roots['splitRequests']),(5,5))

    def test_invalid_counts_cannot_make_a_false_saving(self):
        for args,kwargs in ((([5],6,0),{}),(([5],3,4),{}),(([True],1,0),{}),
                            (([5],1,0),dict(light_page_size=0)),(([5],1,0),dict(light_page_size=51)),
                            (([-1],0,0),{}),(([5],1.5,0),{})):
            with self.subTest(args=args,kwargs=kwargs),self.assertRaises(ValueError):request_model(*args,**kwargs)

    def test_manifest_keeps_identity_corrections_visible_and_is_not_detail(self):
        node=invented_node(1);before=copy.deepcopy(node);manifest=manifest_node(node)
        self.assertEqual(node,before)
        self.assertNotIn('games',manifest)
        self.assertEqual(manifest['updatedAt'],node['updatedAt'])
        node['slots'][0]['entrant']['participants'][0]['player']['id']=99
        self.assertNotEqual(manifest_node(node),manifest) # Same timestamp alone cannot prove identical metadata.
        node=copy.deepcopy(before);node['winnerId']=20
        self.assertNotEqual(manifest_node(node),manifest)
        node=copy.deepcopy(before);node['displayScore']='Inventado DQ - Ejemplo 0'
        self.assertNotEqual(manifest_node(node),manifest)
        small=payload_model(5,manifest=True);full=payload_model(5)
        self.assertLess(small['jsonBytes'],full['jsonBytes'])
        self.assertLess(small['jsonObjects'],full['jsonObjects'])


if __name__=='__main__':unittest.main(verbosity=2)
