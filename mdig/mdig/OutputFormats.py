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

import sys
import logging
import pdb

import GRASSInterface
import DispersalModel
from DispersalInstance import DispersalInstance
from Replicate import Replicate

#TODO: move into classes
def createFilename(rep):
	if isinstance(rep,Replicate):
		i = rep.instance
		# Format of saved filename:
		# species_region_vars*_rep_lifestage.t
		fn = i.experiment.getName() + "_region_" + i.r_id
		if i.var_keys is not None:
			for v in i.var_keys:
				fn += "_" + v + "_"
				var_value=i.variables[i.var_keys.index(v)]
				if isinstance(var_value,str):
					fn += var_value
				else:
					fn += repr(var_value)
		fn += "_rep_" + repr(i.replicates.index(rep))
		return fn
	elif isinstance(rep,DispersalInstance):
		i = rep
		# Format of saved filename:
		# species_region_vars*_rep_lifestage.t
		fn = i.experiment.getName() + "_region_" + i.r_id
		if i.var_keys is not None:
			for v in i.var_keys:
				fn += "_" + v + "_"
				var_value=i.variables[i.var_keys.index(v)]
				if isinstance(var_value,str):
					fn += var_value
				else:
					fn += repr(var_value)
		return fn
	else:
		print "Unknown object to create filename for."
		return None
		

class PngOutput:
	def __init__(self,node):
		self.interval = 1
		self.show_year = False
		self.show_grid = False
		self.log = logging.getLogger("mdig.pngOutput")
		
		self.log.debug("Initialised pngOutput")
		
		for child in node:
			if child.tag == "interval":
				self.interval = int(child.text)
			elif child.tag == "showTime":
				if child.text.lower() == "true":
					self.show_year = True
			elif child.tag == "showGrid":
				if child.text.lower() == "true":
					self.show_year = True
		
		self.listeningTo = []
		
	def replicateUpdate(self,rep,t):
		g = GRASSInterface.getG()
		
		fn = None
		
		if rep.instance.experiment.intervalModulus(self.interval,t) == 0:
			
			fn = createFilename(rep)
			fn+="_"+repr(t)+".png"
			self.log.debug("Writing PNG %s" % fn)
			
			g.setOutput(fn,display=None)
			g.clearMonitor()
			
			current_region = rep.instance.experiment.getRegion(rep.instance.r_id)
			
			if current_region.getBackgroundMap():
				g.paintMap(current_region.getBackgroundMap().getMapFilename())
			
			for l in rep.temp_map_names.keys():
				g.paintMap(rep.temp_map_names[l][0])
			
			if self.show_grid:
				g.paintGrid(5)
			if self.show_year:
				g.paintYear(t)
				
			self.last_output = t
			g.closeOutput()
			
		return [ None, fn ]
		

class RasterOutput:
	
	_tag="RasterOutput"
	
	def __init__(self,node):
		self.interval = 1
		self.lifestage = None
		self.log = logging.getLogger("mdig.RasterOutput")
		
		self.log.debug("Initialised rasterOutput")
		
		for child in node:
			if child.tag == "interval":
				self.interval = int(child.text)
			elif child.tag == "lifestage":
				self.lifestage = child.text
		
		self.listeningTo = []
		
	def replicateUpdate(self,rep,t):
		g = GRASSInterface.getG()
		fn = None

		if rep.instance.experiment.intervalModulus(self.interval,t) == 0:
			for l in rep.temp_map_names.keys():
				if self.lifestage == l:
					fn = createFilename(rep)
					fn += "_ls_" + l + "_" + repr(t)
					self.log.debug("Writing raster %s" % fn)
					g.copyMap(rep.temp_map_names[l][0],fn,True)
			self.last_output = t
			
		return [ self.lifestage, fn ]
			
		
