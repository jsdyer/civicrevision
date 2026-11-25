import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import collect
class CollectionTests(unittest.TestCase):
 def test_config_expands_beyond_starter(self):
  config=json.loads((collect.ROOT/'sources.json').read_text());config['topics'].append({'id':'custom','label':'Custom','articles':['A new article']});self.assertIn('A new article',collect.validate_config(config))
 def test_unsafe_titles_and_limits_rejected(self):
  c=json.loads((collect.ROOT/'sources.json').read_text());c['revisions_per_article']=100
  with self.assertRaises(ValueError):collect.validate_config(c)
 def test_citation_changes_and_named_reuses(self):
  d=collect.compare('A<ref>https://example.com/old</ref><ref name="a"/>','A<ref>https://example.com/new</ref>')
  self.assertEqual(len(d['citations_added']),1);self.assertEqual(len(d['citations_removed']),1)
 def test_readable_diff_and_truncation(self):
  d=collect.compare('Old [[Page|label]]','New '+('x'*4000));self.assertTrue(d['changes'][0]['truncated']);self.assertEqual(d['changes'][0]['before'],'Old label')
 def test_merge_retains_first_observation_and_old_topic(self):
  old={'id':'en:1','timestamp':'2026-11-01','topics':['old'],'comment':'original'};new={**old,'topics':['new'],'comment':'revised'}
  self.assertEqual(collect.merge_records([old],[new]),[old])
 def test_missing_parent_does_not_invent_diff(self):
  p={'title':'Test','revisions':[{'revid':2,'parentid':99,'timestamp':'2026-11-25T00:00:00Z'},{'revid':1,'parentid':0,'timestamp':'2026-11-24T00:00:00Z'}]}
  r=collect.revision_records(p,['test'],'en','2026-11-25T01:00:00Z')[0];self.assertFalse(r['comparison_available']);self.assertEqual(r['bytes_delta'],None)
 def test_reversion_is_explicit_signal(self):
  p={'title':'Test','revisions':[{'revid':2,'parentid':1,'timestamp':'2026-11-25T00:00:00Z','tags':['mw-undo']},{'revid':1,'timestamp':'2026-11-24T00:00:00Z'}]}
  self.assertIn('tagged',collect.revision_records(p,['test'],'en','2026-11-25T01:00:00Z')[0]['reversion'])
 def test_source_failure_preserves_previous_capture(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);(root/'web/data/history').mkdir(parents=True);(root/'sources.json').write_text((collect.ROOT/'sources.json').read_text());(root/'web/data/status.json').write_text('preserve')
   with patch.object(collect,'request',side_effect=RuntimeError('offline')):
    with self.assertRaises(RuntimeError):collect.collect(root)
   self.assertEqual((root/'web/data/status.json').read_text(),'preserve')
 def test_corrupt_history_fails_before_network(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);(root/'web/data/history').mkdir(parents=True);(root/'sources.json').write_text((collect.ROOT/'sources.json').read_text());(root/'web/data/history/2020-01.json').write_text('{}')
   with patch.object(collect,'request') as request:
    with self.assertRaises(ValueError):collect.collect(root)
    request.assert_not_called()
 def test_rss_escapes_source_content(self):
  record={'id':'en:1','title':'A&B','comment':'<script>','source_url':'https://example.com','timestamp':'2026-11-25T00:00:00Z','citations_added':[],'citations_removed':[]}
  xml=collect.rss([record],'Test','https://example.com','2026-11-25T01:00:00Z').decode();self.assertIn('&lt;script&gt;',xml);self.assertNotIn('<script>',xml)
if __name__=='__main__':unittest.main()
