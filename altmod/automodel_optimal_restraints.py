from __future__ import print_function
import os
import csv
import time

from modeller import alignment
from modeller.automodel import automodel
from modeller.scripts import complete_pdb

from .altmod_utils import get_modeller_atom, get_modeller_dist
from .automodel_custom_restraints import Automodel_custom_restraints


class Automodel_optimal_restraints(Automodel_custom_restraints):
    """
    'automodel' child class used to perform homology model building with optimal
    parameters for homology-derived distance restraints (HDDR). This class can
    be used whenever a PDB file with an experimentally-determined structure for
    the target protein is available.
    """

    def set_defaults(self):
        """
        Overrides the original 'set_defaults' method.
        """
        super(Automodel_optimal_restraints, self).set_defaults()

        print("@ Setting 'Automodel_optimal_restraints' defaults.")


    def set_target_structure(self, target_filepath,
                             target_chain=None,
                             mod_tar_seqid_threshold=0.99,
                             use_target_distances=False,
                            #  max_delta_d_abs_val=6.5,
                            ):
        """
        This method must be called in order to build optimal HDDRs for a target
        protein.

        # Arguments
            target_filepath: path of the PDB file containing the target protein
                experimentally-determined structure.
            target_chain: if the PDB file specified in the 'target_filepath'
                argument has multiple chains, the user must provide in this
                argument the code of the chain corresponding to the target protein.
            mod_tar_seqid_threshold: minimum allowed sequence identity between
                the model and target sequence. The model sequence comes from the
                PIR alignment file provided when initializing an "automodel" object.
                The target sequence comes by parsing the PDB structure provided
                in 'target_filepath'. The two sequences are aligned and if the
                they have less than 'mod_tar_seqid_threshold' amino acid sequence
                identities, an error will be raised. Insertion and deletions are
                however allowed (since it common to see experimentally-determined
                structures lacking some regions due to low electron density).
            use_target_distances: if set to 'True' also the optimal location values
                for the HDDRs will be used. By default it is set to 'False',
                therefore only the optimal sigma and template-weight values are
                used. Using the optimal location values for 3D model building,
                usually results in near-perfect models, since the distances
                observed in the target experimentally-determined structures are
                used as location parameters for HDDRs (it would be like modeling
                having the target structure available as a template).
        """

        self.target_filepath = target_filepath
        self.target_chain = target_chain
        self.mod_tar_seqid_threshold = mod_tar_seqid_threshold
        self.use_target_distances = use_target_distances
        # self.max_delta_d_abs_val = max_delta_d_abs_val



    def homcsr(self, exit_stage):
        """
        Overrides the original 'homcsr' method in order to derive the delta_d values from the
        target-template pairs and to edit the restraints file generated by MODELLER.
        """

        # Checks if the 'set_target_structure' method was called.
        if not hasattr(self, "target_filepath"):
            raise ValueError("Please define a target filepath using the 'set_target_structure' method.")

        # Calls the original 'homcsr' method. This will build an initial PDB file of the model
        # and a restraints file.
        # automodel.homcsr(self, exit_stage)
        self.build_initial_files(exit_stage)

        # Sets the default optimal HDDR options. Users may have already called this method to change
        # some options.
        if not self._has_custom_hddr_options:
            self.set_custom_hddr_options()

        # Analyse the target-template pairs.
        self.analyse_target_template_pairs()

        # Rebuild the restraints file with optimal HDDRs.
        self.rebuild_restraints_file()


    def set_custom_hddr_options(self, *args, **params):
        """
        Calls the corresponding method from parent class. In this class, the first three arguments
        can not be changed by the caller.
        """

        # Initializes a list containing 'None' values. It will be populated with the actual filepaths
        # values in the 'analyse_target_template_pairs' method.
        hddr_params_filepaths = [None]*len(self.knowns)

        # Calls the parent method with pre-defined 'hddr_params_filepaths', 'sigma_col' and
        # 'location_col' arguments.
        if not self.use_target_distances:
            location_col = "GRP_DT"
        else:
            location_col = "GRP_DN"
        Automodel_custom_restraints.set_custom_hddr_options(self,
                                                            hddr_params_filepaths=hddr_params_filepaths,
                                                            sigma_col="GRP_DD",
                                                            location_col=location_col,
                                                            atom_i_col="MOD_ATOM_INDEX_I",
                                                            atom_j_col="MOD_ATOM_INDEX_J",
                                                            *args, **params)


    def analyse_target_template_pairs(self):
        """
        Check the compatibility between the target and model sequences and then
        extracts delta_d data from the target-template pairs in a series .csv files.
        These HDDR parameters files will be used by the 'rebuild_restraints_file'
        method of the 'Automodel_custom_restraints' class to edit the default
        restraints file of MODELLER.
        """

        aln = self.read_alignment()

        #------------------------------------------
        # Compare the model and target sequences. -
        #------------------------------------------

        # Get the model sequence.
        modeller_mod_seq = aln[self.sequence]
        if len(modeller_mod_seq.chains) > 1:
            raise NotImplementedError("Optimal restraints with multiple chain models are currently not implemented in altMOD.")
        mod_seq = "".join([r.code for r in modeller_mod_seq.residues])

        # Get the target sequence.
        modeller_tar_obj = complete_pdb(self.env, self.target_filepath)
        if len(modeller_tar_obj.chains) > 1:
            if self.target_chain == None:
                raise ValueError("The selected target structure has more than chain (%s). In order to extract optimal restraints, provide to the 'set_target_structure' the chain corresponding to the model." % len(modeller_tar_obj.chains))
            modeller_tar_obj = modeller_tar_obj.chains[self.target_chain]
        tar_seq = "".join([r.code for r in modeller_tar_obj.residues])

        # Check if they are compatible (by aligning them through salign).
        new_aln = alignment(self.env)
        new_aln.append_sequence(tar_seq)
        new_aln.append_sequence(mod_seq)
        new_aln.salign(gap_penalties_1d=(-900.0, -50.0)) # The as1.sim.mat similarity matrix is used by default.
        tar_aliseq = "".join([_get_modeller_res_code(p.get_residue(new_aln[0])) for p in new_aln.positions])
        mod_aliseq = "".join([_get_modeller_res_code(p.get_residue(new_aln[1])) for p in new_aln.positions])
        '''
        import random
        gr = lambda i: i if random.random() > 0.3 else random.choice("QWERTYIPASDFGHKLCVNM" + "-"*5)
        mod_aliseq = "".join([gr(i) for i in mod_aliseq])
        print (mod_aliseq)
        '''

        # Computes the sequence identity between the model and target sequences.
        matches_count = 0
        identities_count = 0
        for mod_p, tar_p in zip(mod_aliseq, tar_aliseq):
            if mod_p != "-" and tar_p != "-":
                if mod_p == tar_p:
                    identities_count += 1
                matches_count += 1
        mod_tar_seqid = identities_count/float(matches_count)

        # Allows only a small fraction of mismatches.
        if mod_tar_seqid < self.mod_tar_seqid_threshold:
            message = "The target and model sequence do not correspond:\n* Tar: %s\n* Mod: %s" % (tar_aliseq, mod_aliseq)
            raise ValueError(message)

        # Find the correspondance between the model and target residues.
        mod_c = 0
        tar_c = 0
        mod_tar_res_dict = {}
        for mod_pos, tar_pos in zip(mod_aliseq, tar_aliseq):
            if mod_pos != "-" and tar_pos != "-":
                mod_tar_res_dict[mod_c] = tar_c
            if mod_pos != "-":
                mod_c += 1
            if tar_pos != "-":
                tar_c += 1


        #---------------------------------------------
        # Analyse each of the target-template pairs. -
        #---------------------------------------------

        template_filepaths = self._get_template_filepaths(aln)

        for tem_idx, tem_name in enumerate(self.knowns):

            print("\n* Analysing target-tem_%s (%s) pair." % (tem_idx, tem_name))
            t1 = time.time()

            modeller_tem_seq = aln[tem_name]

            # Get the model-template matches from the 'Alignment' object from MODELLER (here, match
            # is defined as any couple of aligned residue). Each match is a tuple containing two
            # 'Residue' objects from MODELLER (the first from the template, the second from the
            # model).
            matches = []
            matches_dict = {}
            mod_c = 0
            for pos in aln.positions:
                mod_pos = pos.get_residue(modeller_mod_seq)
                tem_pos = pos.get_residue(modeller_tem_seq)
                if mod_pos != None and tem_pos != None:
                    matches.append((tem_pos, mod_pos))
                    matches_dict[mod_pos.index] = (mod_pos, tem_pos)
                if mod_pos != None:
                    # Assign an index (starting from 0) to the model residue.
                    mod_pos._id = mod_c
                    mod_c += 1

            '''
            for res in modeller_mod_seq.residues:
                print res, res.index
            '''

            # Iterate through the HDDRs found in the MODELLER restraints file.
            results_list = []
            for atm_1, atm_2 in self.hddr_dict["all"]:

                # Get atom types of the atoms engaged in the HDDRs.
                atm_1_type = self.atm_type_dict[atm_1]
                atm_2_type = self.atm_type_dict[atm_2]

                # Get the model and the equivalent template residues.
                try:
                    mod_res_1, tem_res_1 = matches_dict[self.atm_to_res_dict[atm_1]]
                    mod_res_2, tem_res_2 = matches_dict[self.atm_to_res_dict[atm_2]]
                except KeyError:
                    continue

                # Check if the model residue is also present in the target.
                if not mod_res_1._id in mod_tar_res_dict:
                    continue
                if not mod_res_2._id in mod_tar_res_dict:
                    continue

                # Get the target residues corresponding to the model residues.
                tar_res_1 = modeller_tar_obj.residues[mod_tar_res_dict[mod_res_1._id]]
                tar_res_2 = modeller_tar_obj.residues[mod_tar_res_dict[mod_res_2._id]]

                # Get the target and template residues.
                tem_atm_1 = get_modeller_atom(tem_res_1, atm_1_type)
                tem_atm_2 = get_modeller_atom(tem_res_2, atm_2_type)

                tar_atm_1 = get_modeller_atom(tar_res_1, atm_1_type)
                tar_atm_2 = get_modeller_atom(tar_res_2, atm_2_type)

                # Get the interatomic distances between all the heavy atoms of the two template
                # residues.
                if tem_atm_1 != None and tem_atm_2 != None:
                    grp_dt = get_modeller_dist(tem_atm_1, tem_atm_2)
                # The template residue may have different atoms with respect to the target/model residue.
                else:
                    continue

                # Get the iteratomic distances between the target heavy atoms.
                if tar_atm_1 != None and tar_atm_2 != None:
                    grp_dn = get_modeller_dist(tar_atm_1, tar_atm_2)
                else:
                    continue

                # Assigns the MODELLER code for the type of restraint.
                if atm_1_type == "CA" and atm_2_type == "CA":
                    grp_name = "9"
                elif (atm_1_type == "N" and atm_2_type == "O") or (atm_1_type == "O" and atm_2_type == "N"):
                    grp_name = "10"
                else:
                    if atm_1_type in main_chain_atoms or atm_2_type in main_chain_atoms:
                        grp_name = "23"
                    else:
                        grp_name = "26"

                # Get the delta_d value.
                grp_dd = grp_dn-grp_dt
                # if abs(grp_dd) >= self.max_delta_d_abs_val:
                #     continue

                # Prepare the main columns.
                pair_results = {"RST_GRP": grp_name,
                                "GRP_DN": grp_dn,
                                "GRP_DT": grp_dt,
                                "GRP_DD": grp_dd,
                                "MOD_ATOM_TYPE_I": atm_1_type,
                                "MOD_ATOM_TYPE_J": atm_2_type,
                                "MOD_ATOM_INDEX_I": atm_1,
                                "MOD_ATOM_INDEX_J": atm_2,}

                # Prepare additional columns.
                base_pair_results = {"MOD_RES_PDB_ID_I": mod_res_1.index, "MOD_RES_PDB_ID_J": mod_res_2.index,
                                     "MOD_RES_NAME_I": mod_res_1.code, "MOD_RES_NAME_J": mod_res_2.code,
                                     "TAR_RES_PDB_ID_I": tar_res_1.num, "TAR_RES_PDB_ID_J": tar_res_2.num,
                                     "TAR_RES_NAME_I": tar_res_1.code, "TAR_RES_NAME_J": tar_res_2.code,
                                     "TEM_RES_PDB_ID_I": tem_res_1.num, "TEM_RES_PDB_ID_J": tem_res_2.num,
                                     "TEM_RES_NAME_I": tem_res_1.code, "TEM_RES_NAME_J": tem_res_2.code,}
                pair_results.update(base_pair_results)

                # Add a row in the results .csv file.
                results_list.append(pair_results)


            #-------------------------------------------------------
            # Writes a results file for each target-template pair. -
            #-------------------------------------------------------

            t2 = time.time()

            print("- It took %s." % (t2-t1), len(results_list))
            analysis_filename = "%s_tar_tem_%s.csv" % (self.sequence, tem_idx)
            with open(analysis_filename, "w") as c_fh:
                if len(results_list) != 0:
                    column_names = list(sorted(results_list[0].keys()))
                    writer = csv.DictWriter(c_fh, fieldnames=column_names)
                    writer.writeheader()
                    for pair_results in results_list:
                        writer.writerow(pair_results)
            # Sets the custom HDDR params files of the class.
            self.hddr_params_filepaths[tem_idx] = analysis_filename


    def _get_template_filepaths(self, aln=None):
        """
        Gets the filepaths of the templates provided in the 'knowns' argument.
        """
        if aln == None:
            aln = self.read_alignment()

        # Scans each atom directory.
        atom_dirs_content_list = [os.listdir(adp) for adp in self.env.io.atom_files_directory]

        template_filepaths = []
        for tem_idx, tem_seq_obj in enumerate(aln):
            template_found = False
            # Checks if there exists a file named in the same way as the file provided in the PIR
            # alignment.
            if os.path.isfile(tem_seq_obj.atom_file):
                template_filepaths.append(tem_seq_obj.atom_file)
                template_found = True
            else:
                # Checks in each atom directory.
                for atom_dirpath, atom_dir_content in zip(self.env.io.atom_files_directory, atom_dirs_content_list):
                    # Checks for different file names.
                    for tem_seq_obj_code in (tem_seq_obj.code,
                                             tem_seq_obj.code + ".pdb",
                                             os.path.basename(tem_seq_obj.atom_file),
                                             os.path.basename(tem_seq_obj.atom_file) + ".pdb"):
                        if tem_seq_obj_code in atom_dir_content:
                            template_filepaths.append(os.path.join(atom_dirpath, tem_seq_obj_code))
                            template_found = True
                            break
            if not template_found:
                raise IOError("Structure file not found for template %s." % tem_seq_obj.code)
            if tem_idx+1 == len(self.knowns):
                break
        return template_filepaths


###############################################################################
# Functions used only in this module.                                         #
###############################################################################

def _get_modeller_res_code(modeller_res):
    if modeller_res == None:
        return "-"
    else:
        return modeller_res.code

main_chain_atoms = set(("CA", "N", "C", "O", "OXT"))
