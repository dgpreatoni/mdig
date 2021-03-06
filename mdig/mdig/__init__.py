#
#  Copyright (C) 2006,2008 Joel Pitt, Fruition Technology
#
#  This file is part of Modular Dispersal In GIS.
#
#  Modular Dispersal In GIS is free software: you can redistribute it and/or
#  modify it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or (at your
#  option) any later version.
#
#  Modular Dispersal In GIS is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
#  Public License for more details.
#
#  You should have received a copy of the GNU General Public License along
#  with Modular Dispersal In GIS.  If not, see <http://www.gnu.org/licenses/>.
#
__all__ = ["analysis","instance","model","displayer","event",
        "grass","grassmap","imageshow","lifestage","config",
        "outputformats","region","replicate","management","webui","bottle"]

version = "0.3.2"
version_name = "Digger"
version_string = "MDiG " + version + " - \"" + version_name + "\""

def compare_version(first,second):
    """
    returns:
    < 0 if first is earlier than second,
    0 if equal,
    > 0 if first is older than second
    """
    bits1=[int(x) for x in first.split('.')]
    bits2=[int(x) for x in second.split('.')]
    i = 0
    while i < len(bits1) and i < len(bits2):
        x = bits1[i] - bits2[i]
        if x != 0: return x
        i = i+1
    # if we get here, they are equal up the last common place, so longest is
    # newer
    return len(bits1) - len(bits2)

mdig_exit_codes = {
    "ok" : 0,
    "cmdline_error" : 2,
    "not_implement" : 10,
    "model_not_found" : 3,
    "instance_incomplete": 11,
    "invalid_replicate_index": 12,
    "missing_envelopes": 13,
    "exists": 14,
    "missing_popmod": 15,
    "no_initial_maps": 16,
    "popmod": 17,
    "invalid_lifestage": 18,
    "management": 39,
    "strategy": 40,
    "treatment": 41,
    "treatment_effect": 42,
    "coda_file": 60, # error loading coda file
    "tmatrix": 61, # error applying transition matrix
    "null_map": 62, # null in parameter map
    "up_to_date": 70, # model is all up to date, nothing to be done
    "migrate": 80, # migration of repostory required
    "config": 85, # bad config
    "grass_setup": 90, # grass setup error
    "unknown":101 # who knows?
}

repository = None

class NotEnoughHistoryException (Exception):
    pass

class OutputFileExistsException (Exception):
    def __init__(self, filename):
        self.filename = filename
