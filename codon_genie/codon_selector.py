'''
CodonGenie (c) GeneGenie Bioinformatics Ltd. 2020

All rights reserved.

@author:  neilswainston
'''
import itertools
# pylint: disable=wrong-import-order
from collections import defaultdict
import re

import Bio.Data.CodonTable as CodonTable

from codon_genie.codon_utils import CodonOptimiser

CODONS = {'A': [['G', 'C', 'ACGT']],
          'C': [['T', 'G', 'CT']],
          'D': [['G', 'A', 'CT']],
          'E': [['G', 'A', 'AG']],
          'F': [['T', 'T', 'CT']],
          'G': [['G', 'G', 'ACGT']],
          'H': [['C', 'A', 'CT']],
          'I': [['A', 'T', 'ACT']],
          'K': [['A', 'A', 'AG']],
          'L': [['C', 'T', 'ACGT'], ['T', 'T', 'AG']],
          'M': [['A', 'T', 'G']],
          'N': [['A', 'A', 'CT']],
          'P': [['C', 'C', 'ACGT']],
          'Q': [['C', 'A', 'AG']],
          'R': [['C', 'G', 'ACGT'], ['A', 'G', 'AG']],
          'S': [['T', 'C', 'ACGT'], ['A', 'G', 'CT']],
          'T': [['A', 'C', 'ACGT']],
          'V': [['G', 'T', 'ACGT']],
          'W': [['T', 'G', 'G']],
          'Y': [['T', 'A', 'CT']],
          'Stop': [['T', 'A', 'AG'], ['T', 'G', 'A']]}

NUCL_CODES = {
    'A': 'A',
    'C': 'C',
    'G': 'G',
    'T': 'T',
    'AG': 'R',
    'CT': 'Y',
    'CG': 'S',
    'AT': 'W',
    'GT': 'K',
    'AC': 'M',
    'CGT': 'B',
    'AGT': 'D',
    'ACT': 'H',
    'ACG': 'V',
    'ACGT': 'N',
}

INV_NUCL_CODES = {val: key for key, val in NUCL_CODES.items()}

_EDIT_PATTERN = re.compile(r"([A-Z])(\d+)(-?)([A-Z]+)")

class CodonSelector():
    '''Class to optimise codon selection.'''

    def __init__(self, table_id=1):
        self.__codon_to_aa = \
            CodonTable.unambiguous_dna_by_id[table_id].forward_table
        self.__aa_to_codon = defaultdict(list)

        for codon, amino_acid in self.__codon_to_aa.items():
            self.__aa_to_codon[amino_acid].append(codon)

        self.__codon_opt = {}

    def optimise_codons_seq(self, aa_seq, edits, organism_id):
        edited_positions = dict()
        for edit in edits.split(','):
            if not edit:
                continue
            prev_aa, pos, new_aa = _parse_edit(edit)
            if pos >= len(aa_seq) or aa_seq[pos] != prev_aa:
                raise ValueError("Edit '{}' is invalid".format(edit))
            if pos in edited_positions:
                edited_positions[pos] = edited_positions[pos] + new_aa
            else:
                edited_positions[pos] = new_aa
        if not edited_positions:
            return []
        res = list()
        for pos in range(0, len(aa_seq)):
            if pos in edited_positions:
                codons = self.optimise_codons(edited_positions.get(pos), organism_id)
            else:
                codons = self.optimise_codons(aa_seq[pos], organism_id)
            res.append(codons[0])
        return res

    def optimise_codons(self, amino_acids, organism_id):
        '''Optimises codon selection.'''
        req_amino_acids = set(amino_acids.upper())

        codons = [CODONS[amino_acid] for amino_acid in req_amino_acids]

        results = [self.__analyse(combo, organism_id, req_amino_acids)
                   for combo in itertools.product(*codons)]

        return _format_results(results)

    def analyse_codon(self, ambig_codon, tax_id):
        '''Analyses an ambiguous codon.'''
        results = [[self.__analyse_ambig_codon(ambig_codon.upper(), tax_id)]]
        return _format_results(results)

    def __analyse(self, combo, tax_id, req_amino_acids):
        '''Analyses a combo, returning nucleotides, ambiguous nucleotides,
        amino acids encodes, and number of variants.'''
        transpose = [sorted(list(term)) for term in map(set, zip(*combo))]

        nucls = [[''.join(sorted(list(set(pos))))]
                 for pos in transpose[:2]] + [_optimise_pos_3(transpose[2])]

        ambig_codons = [''.join([NUCL_CODES[term] for term in cdn])
                        for cdn in itertools.product(*nucls)]

        results = [self.__analyse_ambig_codon(ambig_codon, tax_id,
                                              req_amino_acids)
                   for ambig_codon in ambig_codons]

        return results

    def __analyse_ambig_codon(self, ambig_codon, tax_id, req_amino_acids=None):
        '''Analyses a given ambiguous codon.'''
        if req_amino_acids is None:
            req_amino_acids = []

        ambig_codon_nucls = [INV_NUCL_CODES[nucl] for nucl in ambig_codon]

        codons = [''.join(c) for c in itertools.product(*ambig_codon_nucls)]

        amino_acids = defaultdict(dict)

        for codon in codons:
            self.__analyse_codon(codon, tax_id, req_amino_acids, amino_acids)

        amino_acids = [dict(val, **{'amino_acid': key})
                       for key, val in sorted(amino_acids.items(),
                                              key=lambda x: (-x[1]['type'],
                                                             x[0]))]

        result = {'ambiguous_codon': ambig_codon,
                  'ambiguous_codon_nucleotides': tuple(ambig_codon_nucls),
                  'ambiguous_codon_expansion': tuple(codons),
                  'amino_acids': amino_acids}

        if req_amino_acids:
            result.update({'score': _get_score(amino_acids)})

        return result

    def __analyse_codon(self, codon, tax_id, req_amino_acids, amino_acids):
        '''Analyses a specific codon.'''
        codon_opt = self.__get_codon_opt(tax_id)
        amino_acid = self.__codon_to_aa.get(codon, 'Stop')
        typ = _get_amino_acid_type(amino_acid, req_amino_acids)
        amino_acids[amino_acid]['type'] = typ

        if 'codons' not in amino_acids[amino_acid]:
            amino_acids[amino_acid]['codons'] = []

        amino_acids[amino_acid]['codons'].append(
            {'codon': codon,
             'probability': codon_opt.get_codon_prob(codon),
             'cai': codon_opt.get_cai(codon)})

    def __get_codon_opt(self, tax_id):
        '''Gets the CodonOptimiser for the supplied taxonomy.'''
        if tax_id not in self.__codon_opt:
            self.__codon_opt[tax_id] = CodonOptimiser(tax_id)

        return self.__codon_opt[tax_id]


def _parse_edit(edit):
    '''Parses an edit.'''
    match = _EDIT_PATTERN.match(edit)
    if not match:
        raise ValueError(f"Invalid edit: {edit}")
    orig = match.group(1)
    pos = int(match.group(2)) - 1
    invert = match.group(3) == '-'
    new = set(match.group(4))
    if invert:
        new = CODONS.keys() - new - {'Stop'}
    return (orig, pos, "".join(new))

def _optimise_pos_3(options):
    options = list({tuple(sorted(set(opt)))
                    for opt in itertools.product(*options)})
    options.sort(key=len)
    return [''.join(opt) for opt in options]


def _get_amino_acid_type(amino_acid, req_amino_acids):
    '''Gets amino acid type.'''
    return -1 if amino_acid == 'Stop' \
        else (1 if amino_acid in req_amino_acids
              else 0)


def _get_score(amino_acids):
    '''Scores a given amino acids collection.'''
    for vals in amino_acids:
        vals['codons'] = sorted(vals['codons'], key=lambda x: -x['cai'])

    scores = [codon['cai']
              if amino_acid['type'] == 1 else 0
              for amino_acid in amino_acids
              for codon in amino_acid['codons']]

    return sum(scores) / float(len(scores))


def _format_results(results):
    '''Formats results.'''
    return sorted([codon for result in results for codon in result],
                  key=lambda x: (len(x['ambiguous_codon_expansion']),
                                 -x['score'] if 'score' in x else 0))
