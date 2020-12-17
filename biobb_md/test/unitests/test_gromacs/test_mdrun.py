from biobb_common.tools import test_fixtures as fx
from biobb_md.gromacs.mdrun import mdrun
from biobb_md.gromacs.common import gmx_rms


class TestMdrun():
    def setUp(self):
        fx.test_setup(self, 'mdrun')

    def tearDown(self):
        #pass
        fx.test_teardown(self)

    def test_mdrun(self):
        returncode = mdrun(properties=self.properties, **self.paths)
        assert fx.not_empty(self.paths['output_trr_path'])
        assert gmx_rms(self.paths['output_trr_path'], self.paths['ref_output_trr_path'], self.paths['input_tpr_path'], self.properties.get('gmx_path','gmx'))
        assert fx.not_empty(self.paths['output_gro_path'])
        assert fx.not_empty(self.paths['output_edr_path'])
        assert fx.not_empty(self.paths['output_log_path'])
        assert fx.exe_success(returncode)
