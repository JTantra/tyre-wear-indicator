"""Synthetic arithmetic fixtures only; no actual model measurements."""
import unittest
from scripts.cost_bounds import bounds
class BoundsTests(unittest.TestCase):
 def test_no_cache_short_long(self):
  b=bounds({'input_tokens':5000,'output_tokens':200,'total_tokens':5200,'input_tokens_details':{'cached_tokens':0,'cache_write_tokens':0}})
  self.assertAlmostEqual(b['usd_low'],.00066); self.assertAlmostEqual(b['usd_high'],.001265)
 def test_write_interpretations_and_reasoning_once(self):
  b=bounds({'input_tokens':5000,'output_tokens':200,'total_tokens':5200,'input_tokens_details':{'cached_tokens':1000,'cache_write_tokens':2000},'output_tokens_details':{'reasoning_tokens':100}})
  self.assertAlmostEqual(b['usd_low'],.000616); self.assertAlmostEqual(b['usd_high'],.001617)
 def test_absent_usage_unknown_never_zero(self):
  self.assertIsNone(bounds(None)['usd_high']); self.assertTrue(bounds(None)['unknown'])
 def test_absent_cache_details_ranged_not_zero(self):
  b=bounds({'input_tokens':100,'output_tokens':0,'total_tokens':100}); self.assertFalse(b['cache_details_complete']); self.assertAlmostEqual(b['usd_low'],.0000011); self.assertAlmostEqual(b['usd_high'],.0000495)
 def test_invalid_rejected(self):
  self.assertTrue(bounds({'input_tokens':1,'output_tokens':2,'total_tokens':4})['unknown'])
