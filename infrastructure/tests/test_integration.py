import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from run import ROOT, Toolchain, regression, simulate


class HDLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tc=Toolchain()
        try:
            cls.compiler=cls.tc.find('iverilog'); cls.runtime=cls.tc.find('vvp')
        except FileNotFoundError as exc: raise unittest.SkipTest(str(exc))

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='phase04-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def compile_protocol(self):
        files=[ROOT/'infrastructure/hdl/i2s_driver.sv',ROOT/'infrastructure/hdl/i2s_monitor.sv',
               ROOT/'infrastructure/fixtures/tb_protocol.sv']
        binary=self.root/'test.vvp'
        self.tc.run([self.compiler,'-g2012','-s','tb_protocol','-o',binary,*files],self.root,self.root/'compile.log')
        return binary

    def test_literal_wire_protocol(self):
        binary=self.compile_protocol()
        output=self.tc.run([self.runtime,binary],self.root,self.root/'run.log')
        self.assertIn('PROTOCOL_PASS',output)

    def test_unknown_early_and_missing_lr_are_rejected(self):
        binary=self.compile_protocol()
        for fault, reason in [(1,'Unknown serial'),(2,'Unexpected LRCLK'),(3,'Missing LRCLK')]:
            with self.subTest(fault=fault):
                log=self.root/f'fault{fault}.log'
                with self.assertRaises(RuntimeError):
                    self.tc.run([self.runtime,binary,f'+FAULT={fault}'],self.root,log)
                self.assertIn(reason,log.read_text())

    def test_reference_command_and_fst_capture(self):
        fixture=ROOT/'infrastructure/fixtures'
        spec={'sources':[str(fixture/'loopback.sv')],
              'reference_command':['{python}',str(fixture/'reference_identity.py'),'{input}','{output}'],
              'reference_sources':[str(fixture/'reference_identity.py')]}
        simulate(self.tc,self.root,spec,{'frames':8,'stimulus':'edges'},self.root/'model-contract','fst')
        self.assertTrue((self.root/'model-contract/wave.fst').stat().st_size > 0)
        self.assertIn('FST info',(self.root/'model-contract/simulation.log').read_text())

    def test_rtl_mismatch_fails_and_retains_artifacts(self):
        adapter=self.root/'invert.sv'
        adapter.write_text('module phase4_dut(input clk,rst,bclk,lrclk,sd_in,output sd_out); assign sd_out=~sd_in; endmodule\n')
        manifest=self.root/'mismatch.json'
        manifest.write_text(json.dumps({'schema_version':1,'ready':True,'kind':'infrastructure_fixture',
            'simulation':{'sources':[str(adapter)],'fixture_reference':'identity'},
            'cases':[{'name':'mismatch','frames':4}]}))
        output=self.root/'results'; output.mkdir()
        self.assertEqual(regression(self.tc,manifest,output),1)
        result=json.loads((output/'mismatch/comparison.json').read_text())
        self.assertFalse(result['passed'])
        self.assertTrue((output/'junit.xml').exists())


if __name__ == '__main__': unittest.main()
