import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from results import compare, write_samples, write_report
from vectors import generate, write_vectors


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.ref=self.root/'ref.csv'; self.actual=self.root/'actual.csv'
        write_samples(self.ref,[0,32767,-32768,-1])
        write_samples(self.actual,[0,32767,-32768,-1])

    def test_exact_signed_extremes(self):
        self.assertTrue(compare(self.ref,self.actual)['passed'])

    def test_numerical_mismatch_and_tolerance(self):
        write_samples(self.actual,[0,32766,-32768,0])
        self.assertEqual(compare(self.ref,self.actual)['mismatch_count'],2)
        self.assertTrue(compare(self.ref,self.actual,tolerance=1)['passed'])

    def test_truncated_and_extra_output_fail(self):
        for values in ([0,32767], [0,32767,-32768,-1,0,0]):
            write_samples(self.actual,values)
            with self.assertRaisesRegex(ValueError,'Length mismatch'): compare(self.ref,self.actual)

    def test_unknown_and_empty_output_fail(self):
        for contents in ('index,channel,value\n','index,channel,value\n0,0,x\n'):
            self.actual.write_text(contents)
            with self.assertRaises(ValueError): compare(self.ref,self.actual)

    def test_bad_indices_channels_and_rows_fail(self):
        for row in ('1,0,1','0,2,1','0,0,1,extra','0,0'):
            self.actual.write_text('index,channel,value\n'+row+'\n')
            with self.assertRaises(ValueError): compare(self.ref,self.actual)

    def test_channel_swap_fails_even_for_silence(self):
        self.actual.write_text('index,channel,value\n0,1,0\n1,0,32767\n2,1,-32768\n3,0,-1\n')
        self.assertEqual(compare(self.ref,self.actual)['mismatch_count'],4)

    def test_latency_is_explicit_and_preserves_length(self):
        write_samples(self.actual,[10,20,0,32767,-32768,-1])
        self.assertTrue(compare(self.ref,self.actual,latency_words=2)['passed'])
        with self.assertRaises(ValueError): compare(self.ref,self.actual)

    def test_out_of_range_is_not_wrapped(self):
        write_samples(self.actual,[0,32768,-32768,-1])
        with self.assertRaisesRegex(ValueError,'range'): compare(self.ref,self.actual)

    def test_invalid_tolerance_cannot_hide_mismatch(self):
        for tolerance in (-1,float('nan'),float('inf'),True,'0'):
            with self.assertRaises(ValueError): compare(self.ref,self.actual,tolerance=tolerance)

    def test_failed_and_blocked_are_not_success(self):
        result=write_report(self.root,[{'name':'bad','status':'failed','detail':'wrong <bits>'},
                                      {'name':'pending','status':'blocked','detail':'missing RTL'}])
        self.assertFalse(result['passed'])
        tree=ET.parse(self.root/'junit.xml')
        self.assertEqual(tree.getroot().attrib['failures'],'1')
        self.assertEqual(tree.getroot().attrib['skipped'],'1')

    def test_stimulus_is_deterministic_and_signed(self):
        for bits in (8,16,24,32):
            a=generate('random',100,bits,2026)
            self.assertEqual(a,generate('random',100,bits,2026))
            self.assertTrue(all(-(1<<(bits-1)) <= v < (1<<(bits-1)) for v in a))
        hexfile,_=write_vectors(self.root,[-32768,-1,0,32767],16)
        self.assertEqual(hexfile.read_text(),'8000\nffff\n0000\n7fff\n')


if __name__ == '__main__': unittest.main()
