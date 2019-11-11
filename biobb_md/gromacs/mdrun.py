#!/usr/bin/env python3

"""Module containing the MDrun class and the command line interface."""
import os
import argparse
from biobb_common.configuration import settings
from biobb_common.tools import file_utils as fu
from biobb_common.tools.file_utils import launchlogger
from biobb_common.command_wrapper import cmd_wrapper
from biobb_md.gromacs.common import get_gromacs_version
from biobb_md.gromacs.common import GromacsVersionError


class Mdrun:
    """Wrapper of the GROMACS of the mdrun (http://manual.gromacs.org/current/onlinehelp/gmx-mdrun.html) module.

    Args:
        input_tpr_path (str): Path to the portable binary run input file TPR.
        output_trr_path (str): Path to the GROMACS uncompressed raw trajectory file TRR.
        output_gro_path (str): Path to the output GROMACS structure GRO file.
        output_edr_path (str): Path to the output GROMACS portable energy file EDR.
        output_log_path (str): Path to the output GROMACS trajectory log file LOG.
        output_xtc_path (str)[Optional]: Path to the GROMACS compressed trajectory file XTC.
        output_cpt_path (str)[Optional]: Path to the output GROMACS checkpoint file CPT.
        output_dhdl_path (str)[Optional]: Path to the output dhdl.xvg file only used when free energy calculation is turned on.
        properties (dic):
            * **num_threads** (*int*) - (0) Let GROMACS guess. The number of threads that are going to be used.
            * **gmx_path** (*str*) - ("gmx") Path to the GROMACS executable binary.
            * **mpi_bin** (*str*) - (None) Path to the MPI runner. Usually "mpirun" or "srun".
            * **mpi_np** (*str*) - (None) Number of MPI processes. Usually an integer bigger than 1.
            * **mpi_hostlist** (*str*) - (None) Path to the MPI hostlist file.
            * **remove_tmp** (*bool*) - (True) [WF property] Remove temporal files.
            * **restart** (*bool*) - (False) [WF property] Do not execute if output files exist.
            * **container_path** (*string*) - (None)  Path to the binary executable of your container.
            * **container_image** (*string*) - ("gromacs/gromacs:latest") Container Image identifier.
            * **container_volume_path** (*string*) - ("/tmp") Path to an internal directory in the container.
            * **container_user_id** (*string*) - (None) User number id to be mapped inside the container.

    """

    def __init__(self, input_tpr_path, output_trr_path,
                 output_gro_path, output_edr_path,
                 output_log_path, output_xtc_path=None,
                 output_cpt_path=None, output_dhdl_path=None,
                 properties=None, **kwargs):
        properties = properties or {}

        # Input/Output files
        self.io_dict = {
            "in": {"input_tpr_path": input_tpr_path},
            "out": {"output_trr_path": output_trr_path, "output_gro_path": output_gro_path, "output_edr_path": output_edr_path, "output_log_path": output_log_path,
                    "output_xtc_path": output_xtc_path, "output_cpt_path": output_cpt_path, "output_dhdl_path": output_dhdl_path}
        }

        # Properties specific for BB
        self.num_threads = str(properties.get('num_threads', 0))
        self.mpi_bin = properties.get('mpi_bin')
        self.mpi_np = properties.get('mpi_np')
        self.mpi_hostlist = properties.get('mpi_hostlist')

        # container Specific
        self.container_path = properties.get('container_path')
        self.container_image = properties.get('container_image', 'gromacs/gromacs:latest')
        self.container_volume_path = properties.get('container_volume_path', '/tmp')
        self.container_user_id = properties.get('user_id', str(os.getuid()))

        # Properties common in all GROMACS BB
        self.gmx_path = properties.get('gmx_path', 'gmx')
        self.gmx_nobackup = properties.get('gmx_nobackup', True)
        self.gmx_nocopyright = properties.get('gmx_nocopyright', True)
        if self.gmx_nobackup:
            self.gmx_path += ' -nobackup'
        if self.gmx_nocopyright:
            self.gmx_path += ' -nocopyright'
        if (not self.mpi_bin) and (not self.container_path):
            self.gmx_version = get_gromacs_version(self.gmx_path)

        # Properties common in all BB
        self.can_write_console_log = properties.get('can_write_console_log', True)
        self.global_log = properties.get('global_log', None)
        self.prefix = properties.get('prefix', None)
        self.step = properties.get('step', None)
        self.path = properties.get('path', '')
        self.remove_tmp = properties.get('remove_tmp', True)
        self.restart = properties.get('restart', False)

        # Check the properties
        fu.check_properties(self, properties)

    @launchlogger
    def launch(self):
        """Launches the execution of the GROMACS mdrun module."""
        tmp_files = []

        # Get local loggers from launchlogger decorator
        out_log = getattr(self, 'out_log', None)
        err_log = getattr(self, 'err_log', None)

        # Check GROMACS version
        if (not self.mpi_bin) and (not self.container_path):
            if self.gmx_version < 512:
                raise GromacsVersionError("Gromacs version should be 5.1.2 or newer %d detected" % self.gmx_version)
            fu.log("GROMACS %s %d version detected" % (self.__class__.__name__, self.gmx_version), out_log)

        # Restart if needed
        if self.restart:
            if fu.check_complete_files(self.io_dict["out"].values()):
                fu.log('Restart is enabled, this step: %s will the skipped' % self.step, out_log, self.global_log)
                return 0

        container_io_dict = fu.copy_to_container(self.container_path, self.container_volume_path, self.io_dict)

        cmd = [self.gmx_path, 'mdrun',
               '-s', container_io_dict["in"]["input_tpr_path"],
               '-o', container_io_dict["out"]["output_trr_path"],
               '-c', container_io_dict["out"]["output_gro_path"],
               '-e', container_io_dict["out"]["output_edr_path"],
               '-g', container_io_dict["out"]["output_log_path"],
               '-nt', self.num_threads]

        if self.mpi_bin:
            mpi_cmd = [self.mpi_bin]
            if self.mpi_np:
                mpi_cmd.append('-np')
                mpi_cmd.append(str(self.mpi_np))
            if self.mpi_hostlist:
                mpi_cmd.append('-hostfile')
                mpi_cmd.append(self.mpi_hostlist)
            cmd = mpi_cmd + cmd
        if container_io_dict["out"].get("output_xtc_path"):
            cmd.append('-x')
            cmd.append(container_io_dict["out"]["output_xtc_path"])
        if container_io_dict["out"].get("output_cpt_path"):
            cmd.append('-cpo')
            cmd.append(container_io_dict["out"]["output_cpt_path"])
        if container_io_dict["out"].get("output_dhdl_path"):
            cmd.append('-dhdl')
            cmd.append(container_io_dict["out"]["output_dhdl_path"])

        cmd = fu.create_cmd_line(cmd, container_path=self.container_path, host_volume=container_io_dict.get("unique_dir"), container_volume=self.container_volume_path, user_uid=self.container_user_id, container_image=self.container_image, out_log=out_log, global_log=self.global_log)
        returncode = cmd_wrapper.CmdWrapper(cmd, out_log, err_log, self.global_log).launch()
        fu.copy_to_host(self.container_path, container_io_dict, self.io_dict)

        tmp_files.append(container_io_dict.get("unique_dir"))
        if self.remove_tmp:
            fu.rm_file_list(tmp_files, out_log=out_log)

        return returncode


def main():
    parser = argparse.ArgumentParser(description="Wrapper for the GROMACS mdrun module.",
                                     formatter_class=lambda prog: argparse.RawTextHelpFormatter(prog, width=99999))
    parser.add_argument('-c', '--config', required=False, help="This file can be a YAML file, JSON file or JSON string")
    parser.add_argument('--system', required=False,
                        help="Check 'https://biobb-common.readthedocs.io/en/latest/system_step.html' for help")
    parser.add_argument('--step', required=False,
                        help="Check 'https://biobb-common.readthedocs.io/en/latest/system_step.html' for help")

    # Specific args of each building block
    required_args = parser.add_argument_group('required arguments')
    required_args.add_argument('--input_tpr_path', required=True)
    required_args.add_argument('--output_trr_path', required=True)
    required_args.add_argument('--output_gro_path', required=True)
    required_args.add_argument('--output_edr_path', required=True)
    required_args.add_argument('--output_log_path', required=True)
    parser.add_argument('--output_xtc_path', required=False)
    parser.add_argument('--output_cpt_path', required=False)
    parser.add_argument('--output_dhdl_path', required=False)

    args = parser.parse_args()
    config = args.config if args.config else None
    properties = settings.ConfReader(config=config, system=args.system).get_prop_dic()
    if args.step:
        properties = properties[args.step]

    # Specific call of each building block
    Mdrun(input_tpr_path=args.input_tpr_path, output_trr_path=args.output_trr_path,
          output_gro_path=args.output_gro_path, output_edr_path=args.output_edr_path,
          output_log_path=args.output_log_path, output_xtc_path=args.output_xtc_path,
          output_cpt_path=args.output_cpt_path, output_dhdl_path=args.output_dhdl_path,
          properties=properties).launch()


if __name__ == '__main__':
    main()
