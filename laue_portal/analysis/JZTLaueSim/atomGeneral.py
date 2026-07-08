#!/usr/bin/env python
#
#  by Jon Tischler (APS/ANL)
#	The numbers come from various places on the web.

"""
	--- Contains the following Classes: ---

class baseAtom:
		A basic element class, only contains enough info to identify element, (Z, symbol, name, amu)

class elementInfo(baseAtom):
		Based on baseAtom class, returns information commonly found in a periodic table

class xrayLinesAtom(baseAtom):
		This class contains everything in baseAtom() plus X-ray binding energies and emmision lines

class isotope(baseAtom):
		This class contains everything in baseAtom() plus isotopes with their natural abundances

class CromerAtom(baseAtom):
		This class contains everything in baseAtom() plus Cromer calculation for f0

class atom(xrayLinesAtom,isotope):
		A combination of xrayLinesAtom() and isotope(), so with this class you can get everything
"""


import sys
import os
import xml.dom.minidom
import fnmatch
import math
import numpy as np
basestring = str
from JZTLaueSim.JZTunits import UnitsJZTdefault as units
NaN = float('nan')
# XML_DATA_FILE = 'elementData.xml'
# ISOTOPE_DATA_FILE = 'isotopes.xml'
XML_DATA_FILE = os.path.join(os.path.dirname(__file__), 'elementData.xml')
ISOTOPE_DATA_FILE = os.path.join(os.path.dirname(__file__), 'isotopes.xml')

ParsedElementData = None			# a cache of all the element data
ParsedIsotopeData = None			# a cache of all the isotope data

""" ============================================================================
	============================ Start of base atom ============================
"""

class baseAtom(object):
	""" The most basic atom information, just Z, symbol, & name.
	The argument can be either the atomic number or atomic symbol, e.g. for Copper you
	can use either 29 or 'Cu'.  Then call one of the methods to get the associated value.
	To print everything, use:
	a = baseAtom('Cu')
	varialbles for this method are:
		self.Z			atomic number
		self.sym		element symbol
		self.name		element name
		self.amu		atomic mass
		self.valence	valence
		self.Eunits		preferred energy units (default = 'eV')
	also implements the methods:
		symbol2Z(self,sym):
		Z2symbol(self,Z):
		__eq__()		overrides for comparison
		__ne__()
	"""
################# Dina change on 2026-06-18
	# def __init__(self,ele, valence=None, Eunits='eV'):
	# 	print(f"{ele=} {valence=}")
	# 	print(type(ele), repr(ele))
	# 	if hasattr(ele, '__iter__'): ele = ele[0]	# only the first one if many are passed

	# 	print(type(ele), repr(ele))
	# 	ele = str(ele)
	# 	print(f"{ele=}")

	# 	try:	symb = int(ele)
	# 	except:	symb = 0
	# 	if not symb and isinstance(ele,basestring):	# try to interpret ele as an atomic symbol
	# 		ele = ele.strip()
	# 		try:	symb = ele[0].upper()
	# 		except:	raise ValueError('ERROR -- baseAtom cannot figure out the atom from "%s"' % (ele,))
	# 		try:	c2 = ele[1].lower()
	# 		except:	c2 = ''
	# 		if c2.isalpha(): symb += c2

	# 	self.sym = symb
	# 	self.info = self.readElementInfo(basic=True)
	# 	self.name = self.info['name']				# full name of element (e.g. 'Helium')
	# 	self.amu = self.info['amu']					# atomic mass (amu)
	# 	self._neqStr = None

	# 	if not (type(valence) is int) and isinstance(ele,basestring):
	# 		if ele.find('+')>0 or ele.find('-')>0:	# must have a sign
	# 			# try to set the valence from ele, e.g. "Zr+2".
	# 			v = 0									# try to find valence in ele name
	# 			si = 1
	# 			num = ''
	# 			for c in ele:
	# 				if c.isalpha(): continue
	# 				elif c == '-': si = -1
	# 				elif c.isdigit(): num += c
	# 			try:	valence = si * int(num)
	# 			except:	valence = None

	# 	try:	self.valence = int(valence)		# fails if valence is still None, will over ride a valence in the name
	# 	except:	self.valence = 0				# default if no valence passed

	# 	if self.valence:	self.symExtended = "%s%+d" % (self.sym,self.valence)
	# 	else:				self.symExtended = self.sym

	# 	if not Eunits:		self.Eunits = 'eV'
	# 	else:				self.Eunits = Eunits
	# 	return None
####################### Dina 
	def __init__(self, ele, valence=None, Eunits='eV'):
		#print(f"{ele=} {valence=}")
		#print(type(ele), repr(ele))

		# Python 3 fix:
		# strings like "Ni" are iterable, but we do NOT want "Ni"[0] -> "N"
		if not isinstance(ele, (str, bytes)) and hasattr(ele, '__iter__'):
			ele = ele[0]  # only the first one if many are passed
			#print("I'm here")

		#print(type(ele), repr(ele))

		ele = str(ele)
		#print(f"{ele=}")

		try:
			symb = int(ele)
		except Exception:
			symb = 0
		#print(f"{symb=}")
		# Python 3: basestring -> str
		if not symb and isinstance(ele, str):
			#print("if not symb and isinstance(ele, str):")
			ele = ele.strip()

			try:
				symb = ele[0].upper()
			except Exception:
				raise ValueError(
					'ERROR -- baseAtom cannot figure out the atom from "%s"' % (ele,)
				)

			try:
				c2 = ele[1].lower()
			except Exception:
				c2 = ''

			if c2.isalpha():
				symb += c2
		#print(self.sym)
		self.sym = symb
		self.info = self.readElementInfo(basic=True)
		self.name = self.info['name']
		self.amu = self.info['amu']
		self._neqStr = None

		if not (type(valence) is int) and isinstance(ele, str):
			if ele.find('+') > 0 or ele.find('-') > 0:
				# try to set valence from ele, e.g. "Zr+2"
				v = 0
				si = 1
				num = ''

				for c in ele:
					if c.isalpha():
						continue
					elif c == '-':
						si = -1
					elif c == '+':
						si = 1
					elif c.isdigit():
						num += c

				try:
					valence = si * int(num)
				except Exception:
					valence = None

		try:
			self.valence = int(valence)
		except Exception:
			self.valence = 0

		if self.valence:
			self.symExtended = "%s%+d" % (self.sym, self.valence)
		else:
			self.symExtended = self.sym

		if not Eunits:
			self.Eunits = 'eV'
		else:
			self.Eunits = Eunits
		#print(f"{self.sym=} {self.valence=} {self.symExtended=}, {self.info=}, {self.name=}, {self.amu=}, {self._neqStr=}, {self.Eunits=}")
		return None
######################################## Dina 


	def __str__(self):
		""" Return string value for baseAtom. """
		return unicode(self).encode('ascii', errors='backslashreplace')

	def __unicode__(self):
		""" Return unicode value for baseAtom. """
		return u'atom(%s, %d, valence=%d)' % (self.symExtended, self.Z, self.valence)


	def __repr__(self):
		""" Return representation value for baseAtom. """
		return 'baseAtom[sym=%r, symExtended=%r, Z=%r, %r, valence=%r, amu=%r, Zmax=%r]' % (self.sym, self.symExtended, self.Z, self.name, self.valence, self.amu, self.Zmax)


	def symbol2Z(self,sym):
		"""returns Z for an atomic symbol (NOT case sensitive, e.g. Lu and LU are the same)"""
		l = len(sym)
		if l<1: return 0			# unable to find symbol
		if l>2: sym = sym[0:2]		# at most 2 chars long
		sym = sym.capitalize()		# first char capitalized second lower case
		if l>1 and not sym[1].islower(): sym = sym[0]
		try:				z = self.symbols.index(sym) + 1
		except ValueError:	z = 0
		return z


	def Z2symbol(self,Z):
		"""returns atomic symbol from Z the atomic number"""
		if Z<=0: return ''
		try:				sym = self.symbols[Z-1]
		except IndexError:	sym = ''
		except TypeError:	sym = ''
		return str(sym)


	def eV2units(self, eV):
		""" converts energy in eV to local units given by (self.Eunits). """
		if len(self.Eunits)<1:	outUnits = 'eV'
		else:					outUnits = self.Eunits
		return units((eV,'eV'),outUnits).num


	def units2eV(self, energy):
		""" converts energy in local units (self.Eunits) to eV. """
		if len(self.Eunits)<1:	inUnits = 'eV'
		else:					inUnits = self.Eunits
		return units((energy,inUnits),'eV').num


	def readElementInfo(self,basic=False, xray=False, xmlFileName=XML_DATA_FILE):
		global ParsedElementData
		""" 
			xmlFileName is an xml file with all of the element info.
			symb is the atomic symbol (just 'Fe', NOT 'Fe+3', it may also be the the atomic number
			if basic is True, then only returns dict with symbol, name, and amu
			if basic is False, then returns info dict with all of the info
			if xray is True, then returns x-ray edges and emission line dicts too
		"""
		symb = self.sym

		if not ParsedElementData:				# ParsedElementData has not yet been read in
			if not os.path.isfile(xmlFileName): raise ValueError('readElementInfo(), input file "%r" does not exist' % xmlFileName)
			if os.path.getsize(xmlFileName)<10: raise ValueError('readElementInfo(), input file "%r" is too small to be OK' % xmlFileName)
			a = xml.dom.minidom.parse(xmlFileName,parser=None)
			ParsedElementData = a.childNodes[0]	# save ParsedElementData for later use, for subsequent instances of baseAtom

		if not(ParsedElementData.nodeName == u'element_xray'):
			raise ValueError('readElementInfo(), cannot find <element_xray> node in "%s"' % xmlFileName)

		try:	self.Zmax = int(ParsedElementData.getElementsByTagName('Zmax')[0].firstChild.nodeValue)
		except:	self.Zmax = None
		try:	self.symbols = (ParsedElementData.getElementsByTagName('symbols')[0].firstChild.nodeValue).split()
		except:	self.symbols = None
		if self.Zmax != len(self.symbols): raise ValueError('readElementInfo(), Zmax does not match number of atomic symbols')

		try:	Z = int(symb)
		except:
			try:	Z = self.symbols.index(symb) + 1
			except:	raise ValueError('readElementInfo(), Cannot find Z of element "%s"' % (symb,))

		try:	Zdata = ParsedElementData.getElementsByTagName('Z'+str(Z))[0]
		except:	raise ValueError('readElementInfo(), Cannot find data for element with Z = %r' % (Z,))

		self.Z = Z
		self.info = {'Z':Z}
		if basic:
			try:	self.info['name'] = str(Zdata.getElementsByTagName('name')[0].firstChild.nodeValue)
			except:	raise ValueError('readElementInfo(), Cannot find name for Z = %r' % (Z,))
			try:	self.info['amu'] = float(Zdata.getElementsByTagName('amu')[0].firstChild.nodeValue)
			except:	raise ValueError('readElementInfo(), Cannot find amu for Z = %r' % (Z,))
			try:	self.sym = str(Zdata.getElementsByTagName('symb')[0].firstChild.nodeValue)
			except:	raise ValueError('readElementInfo(), Cannot find atomic symbol for Z = %r' % (Z,))
			self.info['symb'] = self.sym
			return self.info

		for node in Zdata.childNodes:
			if node.firstChild:
				value = node.firstChild.nodeValue.strip()
				if len(value)<1 or node.nodeType != 1: continue
				tag = str(node.nodeName)

				tryMore = False
				try:	value = int(value)			
				except:	tryMore = True

				if tryMore:	
					try:	value = float(value)
					except:	tryMore = True

				if tryMore:
					try:	value = str(value)
					except:	continue

				self.info[tag] = value

		try:	name = self.info['name']
		except:	raise ValueError('readElementInfo(), Cannot find name for Z = %r' % (Z,))
		try:	amu = self.info['amu']
		except:	raise ValueError('readElementInfo(), Cannot find amu for Z = %r' % (Z,))

		try:											# .info['valence'] must alwasy be a list of ints or None
			try:	ltemp  = self.info['valence'].split()
			except:	ltemp = [self.info['valence']]		# ltemp is always a list
			lout = list()
			for item in ltemp: lout.append(int(item))	# a list of ints
			self.info['valence'] = lout
		except:
			pass										# or nothing

		if not xray: return self.info

		if xray:
			# get <edges>
			try:
				edgesXML = Zdata.getElementsByTagName('edges')[0].getElementsByTagName('edge')
				self.edges = {}
				for edge in edgesXML:
					label_eV = edge.firstChild.nodeValue.split()
					label = str(label_eV[0])
					ene = self.eV2units(float(label_eV[1]))
					self.edges[label] = ene
			except: self.edges = None

			# get <emissionLines>
			try:
				emissionXML = Zdata.getElementsByTagName('emissionLines')[0].getElementsByTagName('line')
				self.emissionLines = {}
				for line in emissionXML:
					label_eV_S = line.firstChild.nodeValue.split()
					label = str(label_eV_S[0])
					ene = self.eV2units(float(label_eV_S[1]))
					strength = float(label_eV_S[2])
					self.emissionLines[label] = (ene,strength)

			except: self.emissionLines = None
			return (self.info,self.edges,self.emissionLines)


#	symbols = [None,'H','He','Li','Be','B','C','N','O','F','Ne','Na','Mg','Al', \
#		'Si','P','S','Cl','Ar','K','Ca','Sc','Ti','V','Cr','Mn','Fe','Co','Ni','Cu', \
#		'Zn','Ga','Ge','As','Se','Br','Kr','Rb','Sr','Y','Zr','Nb','Mo','Tc','Ru','Rh', \
#		'Pd','Ag','Cd','In','Sn','Sb','Te','I','Xe','Cs','Ba','La','Ce','Pr','Nd','Pm', \
#		'Sm','Eu','Gd','Tb','Dy','Ho','Er','Tm','Yb','Lu','Hf','Ta','W','Re','Os','Ir', \
#		'Pt','Au','Hg','Tl','Pb','Bi','Po','At','Rn','Fr','Ra','Ac','Th','Pa','U','Np', \
#		'Pu','Am','Cm','Bk','Cf','Es','Fm','Md','No','Lr','Rf','Db','Sg','Bh','Hs','Mt', \
#		'Ds','Rg','Cn','Nh','Fl','Mc','Lv','Ts','Og']
#
#	elementNames = [None,'Hydrogen','Helium','Lithium','Beryllium','Boron','Carbon','Nitrogen','Oxygen',\
#		'Fluorine','Neon','Sodium','Magnesium','Aluminum','Silicon','Phosphorus','Sulfur',\
#		'Chlorine','Argon','Potassium','Calcium','Scandium','Titanium','Vanadium',\
#		'Chromium','Manganese','Iron','Cobalt','Nickel','Copper','Zinc','Gallium',\
#		'Germanium','Arsenic','Selenium','Bromine','Krypton','Rubidium','Strontium',\
#		'Yttrium','Zirconium','Niobium','Molybdenum','Technetium','Ruthenium',\
#		'Rhodium','Palladium','Silver','Cadmium','Indium','Tin','Antimony','Tellurium',\
#		'Iodine','Xenon','Cesium','Barium','Lanthanum','Cerium','Praseodymium',\
#		'Neodymium','Promethium','Samarium','Europium','Gadolinium','Terbium',\
#		'Dysprosium','Holmium','Erbium','Thulium','Ytterbium','Lutetium',\
#		'Hafnium','Tantalum','Tungsten','Rhenium','Osmium','Iridium','Platinum','Gold',\
#		'Mercury','Thallium','Lead','Bismuth','Polonium','Astatine','Radon','Francium',\
#		'Radium','Actinium','Thorium','Protactinium','Uranium','Neptunium','Plutonium',\
#		'Americium','Curium','Berkelium','Californium','Einsteinium','Fermium',\
#		'Mendelevium','Nobelium','Lawrencium','Rutherfordium','Dubnium','Seaborgium',\
#		'Bohrium','Hassium','Meitnerium','Darmstadtium','Roentgenium','Copernicium',\
#		'Nihonium','Flerovium','Moscovium','Livermorium','Tennessine','Oganesson']
#
#	amuList = [None,1.00794,4.002602,6.941,9.012182,10.811,12.0107,14.0067,15.9994,18.9984032,\
#		20.1797,22.98977,24.305,26.981538,28.0855,30.973761,32.065,35.453,39.948,39.0983,\
#		40.078,44.95591,47.867,50.9415,51.9961,54.938049,55.845,58.9332,58.6934,63.546,\
#		65.409,69.723,72.64,74.9216,78.96,79.904,83.798,85.4678,87.62,88.90585,91.224,\
#		92.90638,95.94,98,101.07,102.9055,106.42,107.8682,112.411,114.818,118.71,121.76,\
#		127.6,126.90447,131.293,132.90545,137.327,138.9055,140.116,140.90765,144.24,145,\
#		150.36,151.964,157.25,158.92534,162.5,164.93032,167.259,168.93421,173.04,174.967,\
#		178.49,180.9479,183.84,186.207,190.23,192.217,195.078,196.96655,200.59,204.3833,\
#		207.2,208.98038,209,210,222,223,226,227,232.0381,231.03588,238.02891,237,\
#		244,243,247,247,251,252,257,258,259,262,261,262,266,264,277,268,\
#		281,282,285,286,289,290,293,294,294]


	def __eq__(self, other):
		if not( type(other) is type(self) ): return NotImplemented	# can only compare objects of the same type

#		equal = (self.name == other.name)
#		equal = equal and (self.Z == other.Z)
#		equal = equal and (self.sym == other.sym)
#		equal = equal and (self.amu == other.amu)
#		equal = equal and (self.valence == other.valence)
#		equal = equal and (self.Eunits == other.Eunits)
#		self._neqStr = 'self.neqStr = something'
#		other._neqStr = 'other.neqStr = something'
#		return equal

		other._neqStr = self._neqStr = ''		# describes what is not equal about the two atoms
		if (self.sym != other.sym):
			self._neqStr = other._neqStr = 'atomic symbols differ, "%s" != "%s"' % (self.sym, other.sym)
			return False
		elif (self.Z != other.Z):
			self._neqStr = self._neqStr = 'Z differs, %r != %r' % (self.Z, other.Z)
			return False
		elif (self.name != other.name):
			self._neqStr = self._neqStr = 'Names differ, "%s" != "%s"' % (self.name, other.name)
			return False
		elif (self.amu != other.amu):
			self._neqStr = self._neqStr = 'amu differs, %r != %r' % (self.amu, other.amu)
			return False
		elif (self.valence != other.valence):
			self._neqStr = self._neqStr = 'valence differs, %r != %r' % (self.valence, other.valence)
			return False
		elif (self.Eunits != other.Eunits):
			self._neqStr = self._neqStr = 'Eunits differs, "%s" != "%s"' % (self.Eunits, other.Eunits)
			return False
		return True


	def __ne__(self, other):
		if type(other) is type(self):
			return not self.__eq__(other)
		return NotImplemented

""" ============================= End of base atom =============================
	============================================================================
"""



""" ============================================================================
	=========================== Start of elementInfo ===========================
"""

class elementInfo(baseAtom):
	""" Provides a set of values that you might see on a periodic table.
	The values provided refer to a bulk sample of the pure element.
	The argument can be either the atomic number or atomic symbol, e.g. for Copper you
	can use either 29 or 'Cu'.  Then all of the values are set and ready to use.
	To print everything, use:
	e = elementInfo('Cu')
	print repr(e)
	"""

	def __init__(self,ele, valence=None):
		baseAtom.__init__(self, ele, valence=valence)	# sets Z, symbol, & name

		self.readElementInfo(basic=False, xray=False)

		# set all the variables
		try:	self.density = float(self.info['density'])			# density (g/cm^3)
		except:	self.density = None
		try:	self.valences = self.info['valence']				# known valences is a list
		except:	self.valences = None								# or nothing
		try:	self.state = str(self.info['state'])					# state (g/l/s)
		except:	self.state = None
		try:	self.firstIon = float(self.info['firstIon'])				# first ionization energy
		except:	self.firstIon = None
		try:	self.heatFusion = float(self.info['fusion'])			# heat fusionion
		except:	self.heatFusion = None
		try:	self.heatVapor = float(self.info['vapor'])			# heat of vaporization
		except:	self.heatVapor = None
		try:	self.thermConduc = float(self.info['thermalConduc'])	# thermal conductivity
		except:	self.thermConduc = None
		try:	self.specificHeat = float(self.info['specificHeat'])		# specific heat
		except:	self.specificHeat = None
		try:	self.atomRadius = float(self.info['radius'])			# atomic radius
		except:	self.atomRadius = None
		try:	self.meltPoint = float(self.info['melt'])				# melting point
		except:	self.meltPoint = None
		try:	self.boilPoint = float(self.info['boil'])				# boiling point
		except:	self.boilPoint = None
		try:	self.covRadius = float(self.info['covRadius'])		# covalent radius
		except:	self.covRadius = None
		try:	self.elecConduc = float(self.info['elecConduc'])		# elecConduc
		except:	self.elecConduc = None
		try:	self.electroneg = float(self.info['electroneg'])		# electroneg
		except:	self.electroneg = None
		try:	self.atomVol = float(self.info['atomVol'])			# atomic volume
		except:	self.atomVol = None
		try:	self.DebyeT = float(self.info['DebyeT'])			# Debye Temperature (K)
		except:	self.DebyeT = None
		try:	self.config = self.info['config']					# electronic configureation
		except:	self.config = None
		return None


	def __str__(self):
		""" Return string value for elementInfo. """
		return unicode(self).encode('ascii', errors='backslashreplace')

	def __unicode__(self):
		""" Return unicode value for elementInfo. """
		out = baseAtom.__unicode__(self)
		out = out.replace('baseAtom','elementInfo')

		try:	out += '\n\tdensity = %g' % self.density
		except:	pass
		if not (self.valences is None):
			try:	out += '\n\tvalences = %r' % self.valences
			except:	pass
		if not (self.state is None):
			try:	out += '\n\tstate = %s' % self.state
			except:	pass
		try:	out += '\n\tfirstIon = %g' % self.firstIon
		except:	pass
		try:	out += '\n\theatFusion = %g' % self.heatFusion
		except:	pass
		try:	out += '\n\theatVapor = %g' % self.heatVapor
		except:	pass
		try:	out += '\n\tthermConduc = %g' % self.thermConduc
		except:	pass
		try:	out += '\n\tspecificHeat = %g' % self.specificHeat
		except:	pass
		try:	out += '\n\tatomRadius = %g' % self.atomRadius
		except:	pass
		try:	out += '\n\tmeltPoint = %g' % self.meltPoint
		except:	pass
		try:	out += '\n\tboilPoint = %g' % self.boilPoint
		except:	pass
		try:	out += '\n\tcovRadius = %g' % self.covRadius
		except:	pass
		try:	out += '\n\telecConduc = %g' % self.elecConduc
		except:	pass
		try:	out += '\n\telectroneg = %g' % self.electroneg
		except:	pass
		try:	out += '\n\tatomVol = %g' % self.atomVol
		except:	pass
		try:	out += '\n\tDebyeT = %g' % self.DebyeT
		except:	pass
		if not (self.config is None):
			try:	out += '\n\tconfiguration = %s' % self.config
			except:	pass
		return out


	def __repr__(self):
		""" Return representation value for elementInfo. """
		out = baseAtom.__repr__(self)
		out = out.replace('baseAtom','elementInfo')
		out += ' + [density=%r, valences=%r, state=%r, firstIon=%r, ' % (self.density,self.valences,self.state,self.firstIon)
		out += 'heatFusion=%r, heatVapor=%r, thermConduc=%r, specificHeat=%r, ' % (self.heatFusion,self.heatVapor,self.thermConduc,self.specificHeat)
		out += 'atomRadius=%r, meltPoint=%r, boilPoint=%r, covRadius=%r, ' % (self.atomRadius,self.meltPoint,self.boilPoint,self.covRadius)
		out += 'elecConduc=%r, electroneg=%r, atomVol=%r, DebyeT=%r, config=%r]' % (self.elecConduc,self.electroneg,self.atomVol,self.DebyeT,self.config)
		return out

""" ============================ End of elementInfo ============================
	============================================================================
"""




""" ============================================================================
	=========================== Start of X-ray lines ===========================
"""

"""
	testing:
import atomGeneral
a = atomGeneral.xrayLinesAtom('Cu')
a.binding_energy('K')
print a.emissionLine_type('Ka1')
print a.emissionLine_type('K')
print str(a)
print "best =   ",a.findBestElement(10543,'K*',dE=90)
"""

class xrayLinesAtom(baseAtom):
	""" Provides information on the absorption edges and emission lines for an element.
	The argument can be either the atomic number or atomic symbol, e.g. for Copper you
	can use either 29 or 'Cu'.  Then call one of the methods to get the associated value.

	self.edges			list of edges for this element
	self.emission		list of all emission lines for this element
	self.emissionLabels	list of emission line labels for this element

	To print everything, use:
	e = xrayLinesAtom('Cu')
	print str(e)
	Note, this class inherits from baseAtom, so all of the baseAtom methods are available here.
	"""

	def __init__(self,ele, valence=None, Eunits='eV'):
		baseAtom.__init__(self, ele, valence=valence, Eunits=Eunits)

		self.readElementInfo(basic=False, xray=True)
		return None


	def binding_energy(self,edgeType):
		""" return energy from one edge (self.Eunits) """
		if not isinstance(edgeType,basestring): return None
		try:	ene = self.edges[edgeType]
		except:	ene = None
		return ene


	def emissionLine_type(self,lineType):
		"""
		return energy from one emission line (self.Eunits)
		Note: if lineType is specific like 'Ka1', then energy and relative strength are returned
		if lineType is non-specific like 'K' or 'Ka', then the weighted average is returned and strength is sum of strengths
		use: self.emissionLine_type("")["strength"] to get the sum of all strengths if needed for normalizing
		It also returns the lo and high range of the lines used, for a single line lo==hi==ene
		For lines that are multiple, lo<ene<hi
		"""
		eneSum = strongSum = ene = 0.0
		N = 0
		lo = float('Inf')
		hi = -float('Inf')
		lines = []
		for label in self.emissionLines:
			if not label.startswith(lineType): continue
			(ene,strong) = self.emissionLines[label]
			lines.append((ene,strong,label))
			eneSum += ene * strong
			strongSum += strong
			lo = min(lo,ene)
			hi = max(hi,ene)
			N += 1

		if N>1:
			ene = eneSum/strongSum		# the weighted average energy
			strong = strongSum

		if not ( ene>0.0 and not math.isinf(ene) ): return None
		return {'avg':ene, 'strength':strong, 'lo':lo, 'hi':hi, 'lineType':lineType, 'lineList':lines}


	def __str__(self):
		""" return printable string with everything about the element """
		return unicode(self).encode('ascii', errors='backslashreplace')

	def __unicode__(self):
		""" return unicode printable string with everything about the element """
		out = baseAtom.__unicode__(self)
		if out is None: return None
		out += '\n'+self.printBindingAll()+'\n'
		out += self.printEmissionAll()
		return out


	def __repr__(self):
		""" return printable string with everything about the element """
		out = baseAtom.__repr__(self)
		if out is None: return None
		out += ' + [ ' + repr(self.edges) + ', ' + repr(self.emission) + ']'
		return out


	def printBindingAll(self):
		""" return printable string with the binding energies for this element """
		if self.Z==0: return None
		out = '  Binding Energies:\n'
		if self.edges is None:
			out += '\tempty\n'
		else:
			out += '\tlabel \tEnergy ('+self.Eunits+')\n'
			for item in sorted(self.edges.iteritems(), key=lambda k,v    : (v,k), reverse=True):
				out += '\t%s \t%g\n' % (item[0],item[1])
		return out


	def printEmissionAll(self):
		""" return printable string with the emission lines for this element """
		if self.Z==0: return None
		out = '  Emission lines:\n'
		if self.emissionLines is None:	out += '\tempty\n'
		else:							out += '\tlabel \tEnergy ('+self.Eunits+') \tStrength\n'

		for item in sorted(self.emissionLines.iteritems(), key=lambda k,v: (v,k), reverse=True):
			out += '\t%s \t%g\t\t%g\n' % (item[0],item[1][0],item[1][1])
		return out


	def findBestElement(self,ene,acceptableLines, dE=0):
		""" Finds the 'best' match to an energy 'ene'.
		if acceptableLines is '', then check all lines, other wise only chek the specified lines.
		format for acceptableLines is something like:
			'K*', '', 'Lb1', '*L*', or ('Ka*','Kb*')
		the optional dE is the resolution, find strongest line within ene+-dE,
			for dE==0, just use closest line
		"""
		dE = max(dE,0)
		dEmin = float('inf')
		strengthBest = -float('inf')
		for Z in range(1,92+1):									# for each element
			emission,emissionLabels = self.getEmissionLines(Z=Z)# a tuple of emission lines for element Z
			if not(type(emission) is tuple): continue
			for item in emission:								# item contains (eni, line, strength)
				if not self.__acceptableLine(acceptableLines,item[1]): continue	#if line is not of desired type, continue
				deltaE = abs(item[0]-ene)
				better = (deltaE<dE and item[2]>strengthBest)	# energy is close enough, look for best line, dE>0
				better = better or (dE==0 and deltaE<dEmin)		# find closest line, no width specified
				if better:
					itemBest = item
					dEmin = deltaE
					Zmin = Z
					strengthBest = item[2]
		return ((self.Z2symbol(Zmin),Zmin),itemBest)

	def __acceptableLine(self,acceptableLines,line):
		""" returns True is line is a member of acceptableLines,
		acceptableLines is from findBestElement()
		format for acceptableLines is something like:
			'K*', '', 'Lb1', '*L*', or ('Ka*','Kb*')
		"""
		if len(acceptableLines)<1: return True	# all lines are acceptable when empty

		if isinstance(acceptableLines,basestring):	tlines = (acceptableLines,) # need a tuple not a str
		else:										tlines = acceptableLines
		for testPattern in tlines:				# check each string in tuple
			testPattern = str(testPattern)
			if fnmatch.fnmatch(line,testPattern): return True
		return False

	def getEmissionLines(self, Z=-1):
		if Z<=0: Z = self.Z				# allows user to get emission lines from a DIFFERENT element

		aTemp = baseAtom(Z)
		aTemp.readElementInfo(basic=False, xray=True)
		try:	emissionLines = aTemp.emissionLines
		except:	emissionLines = None

		labels = list()
		energies = list()
		for item in sorted(emissionLines.iteritems(), key=lambda k,v: (v,k), reverse=True):
			try:
				labels.append(item[0])
				ene = self.eV2units(float(item[1][0]))
				energies.append(ene)
			except:
				continue

		return (energies,labels)

""" ============================ End of X-ray lines ============================
	============================================================================
"""



""" ============================================================================
	============================ Start of Isotopes =============================
"""

"""
	testing:
import atomGeneral
i = atomGeneral.isotope('Cu')
print i.printIsotopes()
print i.amu_abundance(65)
"""

class isotope(baseAtom):
	""" Provides information on the isotope abundances and masses for an element.
	The argument can be either the atomic number or atomic symbol, e.g. for Copper you
	can use either 29 or 'Cu'.  Then call one of the methods to get the associated value.
	To print everything, use:
	e = isotope('Cu')
	print str(e)
	Note, this class inherits from baseAtom, so all of the baseAtom methods are available here.
	"""

	def __init__(self,ele, valence=None):
		baseAtom.__init__(self, ele, valence=valence)
		self.isotopes = self.readIsotopeInfo()
		return None


	def __str__(self):
		""" return printable string with everything about the isotope """
		return unicode(self).encode('ascii', errors='backslashreplace')

	def __unicode__(self):
		""" return unicode printable string with everything about the isotope """
		out = baseAtom.__unicode__(self)
		if out is None: return None
		out += '\n'+self.printIsotopes()
		return out


	def __repr__(self):
		""" return printable string with everything about the element """
		out = baseAtom.__repr__(self)
		if out is None: return None
		out += ' + [ ' + repr(self.isotopes) + ']'
		return out


	def printIsotopes(self):
		""" return printable string with the isotopes for this isotope """
		if self.Z==0: return None
		out = '  Isotopes:\n'
		if self.isotopes is None:
			out += '\tempty\n'
		else:
			out += '    MassNumber\t amu \t  Natural Abundance\n'
			massNumbers = list()
			for massNumber in self.isotopes:
				if type(massNumber) is int: massNumbers.append(massNumber)
			massNumbers.sort()
			for massNumber in massNumbers:
				amu,frac = self.isotopes[massNumber]	#	1:(1.0078250321,0.999885)
				out += '\t%r \t%.4f \t%g\n' % (massNumber,amu,frac)
		return out


	def isotopeListAll(self):
		""" returns list of all known isotopes, needed because self.isotopes is private """
		if self.Z<=0: return None
		return self.isotopes

	def isotopeListNatural(self):
		""" returns list of ONLY naturally occurring isotopes """
		if self.Z==0: return None
		if not(type(self.isotopes) is dict): return None
		massNumbers = list()
		for massNumber in self.isotopes:
			if type(massNumber) is int: massNumbers.append(massNumber)
		massNumbers.sort()							# order by mass number
		out = tuple()
		for massNumber in massNumbers:
			amu,frac = self.isotopes[massNumber]
			if frac>0:
				out += ((amu,frac),)
		return out


	def amu_abundance(self,massNumber):
		""" returns tuple with (amu, NaturalAbundance) """
		try:
			amuFrac = self.isotopes[massNumber]		#	1:(1.0078250321,0.999885)
		except:
			amuFrac = None
		return amuFrac


	def readIsotopeInfo(self, Z=-1, isotopeFileName=ISOTOPE_DATA_FILE):
		global ParsedIsotopeData
		""" 
			isotopeFileName is an xml file with all of the isotope info.
			returns the isotope dict
		"""
		try:	Z = int(Z)
		except:	Z = self.Z
		if Z<1: Z = self.Z			# default to current atom

		if not ParsedIsotopeData:				# ParsedIsotopeData has not yet been read in
			if not os.path.isfile(isotopeFileName): raise ValueError('readIsotopeInfo(), input file "%r" does not exist' % isotopeFileName)
			if os.path.getsize(isotopeFileName)<10: raise ValueError('readIsotopeInfo(), input file "%r" is too small to be OK' % isotopeFileName)
			a = xml.dom.minidom.parse(isotopeFileName,parser=None)
			ParsedIsotopeData = a.childNodes[0]	# save ParsedElementData for later use, for subsequent instances of baseAtom

		if not(ParsedIsotopeData.nodeName == u'isotopes'):
			raise ValueError('readIsotopeInfo(), cannot find <element_xray> node in "%s"' % isotopeFileName)

		try:	Zdata = ParsedIsotopeData.getElementsByTagName('Z'+str(Z))[0]
		except:	raise ValueError('readIsotopeInfo(), Cannot find isotope data for atoms of Z = %r' % (Z,))

		try:
			isotopes = {'Z':Z, 'symb':self.Z2symbol(Z)}
			for isoLine in Zdata.getElementsByTagName('is'):	# for each isotope of this Z
				iii = isoLine.firstChild.nodeValue.split()		# Mass Number,  Atomic Mass,  Natural Fraction
				isotopes[int(iii[0])] = (float(iii[1]),float(iii[2]))
		except:	isotopes = None

		return isotopes

""" ============================= End of Isotopes ==============================
	============================================================================
"""



""" ============================================================================
	=========================== Start of CromerAtom ============================
"""
class CromerAtom(baseAtom):
	""" Provides a calculation of the atomic scattering factor for an element.
	The argument can be either the atomic number or atomic symbol, e.g. for Copper you
	can use either 29 or 'Cu'.  Then call one of the methods to get the associated value.
	used to get energy INDEPENDENT atomic structure factor from:
	FUNCTION TYPE GIVEN IN CROMER AND LIBERMAN, J. CHEM. PHYS. 53,1891-1898(1970)
	sym is atomic symbol, e.g. "Cu"
	valence is an integer with the desired valence, (0 is alwasy valid and is the default, see __init__)

	self.use_Z is a means of bypassing the Cromer calculation and setting f0=Z

	To print everything, use:
	e = CromerAtom('Cu')
	print e.f0()
	Note, this class inherits from baseAtom, so all of the baseAtom methods are available here.
	"""

	def __init__(self,ele, keV=None, valence=None, use_Z=False):
		#print(f"{ele=}")
  		
		baseAtom.__init__(self, ele, valence=valence)
		
		try:	self.use_Z = bool(use_Z)
		except:	self.use_Z = False

		try:
			if keV<=0 or math.isnan(keV) or math.isinf(keV): raise		# energy must be positive definite, also fails on strings or None
			self.keV = keV
		except:	self.keV = None		# this means no energy

		self.fanomalous = None
		self.ElementDict = None
		self.nord = 2				# order of interpolation
		if self.nord<0 or self.nord>5:
			raise ValueError('Cromer-Liberman nord = "%r" not in range [0,5]' % (self.nord,))

		if not self.use_Z:			# do not need ABC or worry about knowValences, f0 = Z-valence
			# knownValences is has the available valences for all the elements in Cromer
			try:	vs = self.knownValences[self.sym]	# get tuple of known valences
			except:	raise IndexError('CromerAtom.f0, cannot find atomic symbol %r' % self.sym)
			# reset valence to a known Cromer value
			
			try:	self.valenceC = min(vs, key=lambda x:abs(x-self.valence))	# get valence closest to available values from vs
			except:	raise ValueError('CromerAtom.f0, cannot find valence for  %r' % self.sym)
			
			# reset symExtended to match new valence
			self.symExtended = self.sym

			if self.valenceC: self.symExtended += '%+d' % self.valenceC	# symbol to hunt for in self.ABCs
			try:	self.ABC = self.ABCs[self.symExtended]; 
			except:	raise ValueError('Cannot identify atom type %r' % self.symExtended)
			self.reset_keV(keV)

		else:
			self.valenceC = self.valence

		return None


	def __str__(self):
		""" Return string value for CromerAtom. """
		return unicode(self).encode('ascii', errors='backslashreplace')

	def __unicode__(self):
		""" Return unicode value for CromerAtom. """
		if self.use_Z:	out = baseAtom.__unicode__(self) + '+ (use_Z)'
		else:			out = baseAtom.__unicode__(self)
		try:
			if self.keV > 0: out = out + '+ (E=%g keV)' % (self.keV)
		except:	pass
		return out


	def __repr__(self):
		""" Return representation value for CromerAtom. """
		out = baseAtom.__repr__(self)
		out = out.replace('baseAtom','CromerAtom')
		out += ' + [use_Z=%r, E = %r keV' % (self.use_Z, self.keV)
		try:
			if self.keV > 0:	out += ",  f'=%r, f''=%r" % (self.fanomalous.real, self.fanomalous.imag)
		except:	pass
		out += "]"
		return out


	def fatom(self, Q, keV='NOTHING_PASSED_JZT'):
		"""
		Compute the full complex fatom = f0 + f' + f''
		Note, an enegy of tuple() will just use the existing energy, tuple() is really invalid
		"""
		if keV != 'NOTHING_PASSED_JZT':	# something was passed, CHANGE the energy
			try:
				if keV<=0 or math.isnan(keV) or math.isinf(keV): raise		# energy must be positive definite, also fails on strings or None
			except:
				keV = None				# energy is invalid
			self.reset_keV(keV)			# set self.keV and recalculate fp

		f0 = self.f0(Q)
		if self.fanomalous:	return complex(f0,0) + self.fanomalous
		else:				return f0


	def f0(self,Q):
		""" returns energy INDEPENDENT atomic structure factor, f0
		Q = 4*PI * sin(theta)/lambda,  it has the 2PI, and lambda in nm
		FUNCTION TYPE GIVEN IN CROMER AND LIBERMAN, J. CHEM. PHYS. 53,1891-1898(1970)

		Q is in 1/nm
		sym is atomic symbol, e.g. "Cu"
		valence is an integer with the desired valence, (0 is alwasy valid and is the default, see __init__)
		"""
		if self.use_Z: return (self.Z - self.valence)

		(A,B,C) = self.ABC				# coefficients found at __init__
		S = (Q*0.1)/(4*math.pi)			# convert Q to sin(theta)/lambda (1/Angstrom), the 0.1 converts (1/nm) --> (1/Angstrom)
		sum = float(C)
		for i in range(4):
			sum += A[i] * math.exp(-S*S*B[i])
		return sum


	def reset_keV(self,keV):
		"""
		Change the energy, not the element.
		This ALWAYS sets self.keV, whether or not keV is valid
		if keV is different than what it was, then call calc_fp()
		"""
		keV_last = self.keV				# save existing value for a comparison
		try:
			if keV<=0 or math.isnan(keV) or math.isinf(keV): raise # energy must be positive definite
		except:
			self.fanomalous = None		# keV is in valid, so no anomalous part
			self.keV = None
			return

		self.keV = keV

		# Check that the element is in the database and that self.ElementDict is set
		if not self.ElementDict:
			keV_last = NaN				# forces the call to self.calc_fp()
			try:	self.ElementDict  = self.setElementDict()
			except:	raise ValueError('Element not in Cromer-Liberman database %r' % (self.sym,))

		if not(keV_last == self.keV): self.fanomalous = self.calc_fp()	# keV has changed, recalculate fp


	def calc_fp(self):
		au = 2.80022e7
		C = 137.0367
		C1 = 0.02721
		pi = math.pi

		# now define the needed waves and variables
		# waves will be longer by 1 then needed, since we will not use the index 0 usually..
		self.sigg = np.zeros(6)		# we need 5 fields, 0 element will not be used...
		eg = np.zeros(6)

		self.cx = 0.0				# these will probably need to be global
		self.bb = 0.0
		self.rx = 0.0
		self.sedge = 0.0
		self.icount = 0

		# these should be local variables
		zz = 0.0					# compute simple Z electron point
		iz = self.Z					# atomic number
		nat = self.sym				# atomic symbol

		fp = np.zeros(26)			# accumulates f'
		fpp = np.zeros(26)			# accumulates f''

#		SVAR AtomInformation=$("root:Packages:CromerCalculations:'"+num2str(iz)+"'")
#		//Wave CurElementWv=$(num2str(CurElementNumber)+"Wv")
#		//the idexes are: p - number of triplet lines, q - up to 11 numbers, r - in r=0 we have energies, in r=1 we have cross sections in barns
#		Wave CurElementWv=$("root:Packages:CromerCalculations:'"+num2str(iz)+"Wv'")

		eterm = self.ElementDict['ETERM']	# eterm from data
		no = self.ElementDict['NSHELLS']
		allShells = self.ElementDict['shells']

		# Now we can do for each orbital the calcualtion
		for j in range(1,no+1):		# for each orbital (shell)
			# ew - energy in keV			- these are in the wave
			# sig - cross section in barns	- again, in the wave
			# be  - binding energy
			# IFvalue

			shellInfo = allShells[j-1]
			IFvalue = shellInfo['Func']
			be = shellInfo['BindEnergy']

			# reset the length here for this orbital
			ew = np.zeros(12)			# energy in keV
			sig = np.zeros(12)			# cross section in barns
			el = np.zeros(12)			# ln(ew)
			sl = np.zeros(12)

			ewArray = shellInfo['ew']
			sigArray = shellInfo['sig']

			# now extract 10 corrections and stuff them in ew and sig
			for k in range(1,11):					# [1,..,10]
				ew[k] = ewArray[k-1]				# CurElementWv indexed from 0, ew from 1
				sig[k] = sigArray[k-1]				# CurElementWv indexed from 0, sig from 1

			# ow extract first 5 corrections and stuff them in eg and sigg
			for k in range(1,6):				# [1,2,3,4,5]
				eg[k] = ewArray[5+k-1]			# CurElementWv indexed from 0, ew from 1
				self.sigg[k] = sigArray[5+k-1]	# CurElementWv indexed from 0, sig from 1

			nx = 10
			if IFvalue==0:						# if IFvalue==0, then we have 11th energy
				nx=nx+1
				ew[11] = ewArray[10]			# CurElementWv indexed from 0, ew from 1
				sig[11] = sigArray[10]			# CurElementWv indexed from 0, sig from 1
				sigedg = sig[11]				# will need the sigedg later....
			else:
				np.resize(ew,11)				# # shorten arrays by 1
				np.resize(sig,11)
				np.resize(el,11)
				np.resize(sl,11)

			# end of reading enegies and corrections, hopefully
			self.bb = be/C1						# convert binding energy and sigmas to internal funny units
			self.sigg = self.sigg / au
			self.Csort_fp(nx,ew, sig)			# sort them, use this function so do not have to worry about elements...
			self.Csort_fp(5,eg, self.sigg)

			for i in range(len(ew)):
				if ew[i] > 0.0: el[i] = math.log(ew[i])

			sl.fill(0.0)
			for k in range(1,nx+1):
				if sig[k]!=0: sl[k] = math.log(sig[k])

			mf = 0
			zx = math.log(self.keV)				# zx is log of X-ray energy in keV
			self.cx = 0
			if be <= self.keV:
				if self.nord == 0:
					self.Cxsect(zx,el,sl,self.cx,nx)
				else:
					for m in range(1,nx+1):
						n1 = m
						if sl[m]!=0: break

					mm = nx - n1 +1
					elc = np.copy(el)
					slc = np.copy(sl)
					iend = max(0,len(el)+1-n1)
					for i in range(0,iend):
						elc[i] = el[i+n1-1]		# elc = el[p+n1-1]
						slc[i] = sl[i+n1-1]		# slc = sl[p+n1-1]

					self.cx = self.cAknint(zx,mm,self.nord,elc,slc)
					self.cx = math.exp(self.cx)

				self.cx /= au					# change cx to atomic units...

			self.icount = 6
			self.rx = (self.keV)/C1				# xray energy in au
			if (IFvalue != 0) or (be < (self.keV)):
				if IFvalue>=0 and IFvalue<=2: fp[j] = self.Cromer_Cgauss(IFvalue) * C / (2*pi*pi)
			else:
				self.sedge = sigedg / au		# sedge is Xsection in atomic units and energy = 1.001 * BE
				self.cx = 0
				fp[j] = self.Cromer_Cgauss(3) * C / (2*pi*pi)
				mf = 3

			fpp[j] = 0
			if (self.cx)!=0: fpp[j] = C * (self.cx) * (self.rx)/(4*pi)
			corr = 0
			if (self.cx)!=0: corr = -(self.cx) * (self.rx) * 0.5 * math.log(((self.rx)+(self.bb))/((self.rx)-(self.bb)))*C/(2*pi*pi)
			if mf==3: corr = 0.5 * (self.sedge) * (self.bb) * (self.bb) * math.log((-(self.bb)+(self.rx))/(-(self.bb)-(self.rx)))/(self.rx) * C/(2*pi*pi)
			fp[j]=fp[j]+corr

		sumfp = 0.0
		for j in range(1,no+1): sumfp +=fp[j]

		# xjensn = -0.5 * iz * ((self.keV)/C1/137.0367/137.0367)**2
		sumfp = sumfp + eterm				# + xjensn
		# jensen correction was removed, according to NIST web site (10/09/2003, physics.nist.gov/PhysRevData/FFast/Text1995/chap10.html
		# the correction is incorrect. Also, NIST web site comments, that appropriate relativistic correction is only 3/5ths of Cromer-Leiberman
		# value. This 3/5ths were not implemented in this code...
		# for deatails see http://physics.nist.gov/PhysRefData/FFast/Text1995/contents1995.html

		sumfpp = 0.0
		for j in range(1,no+1): sumfpp += fpp[j]

		fprime = complex(sumfp,sumfpp)

#		Cromer_RecordData(AtomType, (self.keV), sumfp,sumfpp)			# store new result, in the database
		return fprime


	def Csort_fp(self,n,aMatrix,bMatrix):
		# variable n
		# arrays aMatrix, bMatrix
		for i in range(1,n):
			for j in range(i+1,n+1):
				if aMatrix[j] <= aMatrix[i]:
					x = aMatrix[j]
					y = aMatrix[i]
					aMatrix[i]  = x
					aMatrix[j] = y
					x = bMatrix[j]
					y = bMatrix[i]
					bMatrix[i] = x
					bMatrix[j] = y


	def Cxsect(self, zx, el, sl, nx):
		# zx is log of X-ray energy in keV
		# variable nx
		# wave el, sl

		er=1000000.0
		ll = 0
		for l in range(1,nx+1):
			p = abs(zx-el[l])
			if p <= er:
				er = p
				ll = l

		ll -= 1
		if ll == 0: ll = 1
		if ll == 12: ll = 11
		if sl[ll] == 0.0 : ll += 1

		det = el[ll+2]*el[ll+2]*(el[ll+1]-el[ll])+el[ll+1]*el[ll+1]*(el[ll]-el[ll+2])+el[ll]*el[ll]*(el[ll+2]-el[ll+1])
		a0 = (el[ll]*el[ll]*(sl[ll+1]*el[ll+2]-sl[ll+2]*el[ll+1])+el[ll+1]*el[ll+1]*(sl[ll+2]*el[ll]-sl[ll]*el[ll+2])+el[ll+2]*el[ll+2]*(sl[ll]*el[ll+1]-sl[ll+1]*el[ll]))/det
		a1 = (el[ll]*el[ll]*(sl[ll+2]-sl[ll+1])+el[ll+1]*el[ll+1]*(sl[ll]-sl[ll+2])+el[ll+2]*el[ll+2]*(sl[ll+1]-sl[ll]))/det
		a2 = (sl[ll]*(el[ll+2]-el[ll+1])+sl[ll+1]*(el[ll]-el[ll+2])+sl[ll+2]*(el[ll+1]-el[ll]))/det
		cx = exp(a0+a1*zx+a2*zx*zx)
		return cx


	def cAknint(self, xbar,inn,im, xMatrix,yMatrix):
		n = abs(inn)
		m = im
		if m >= n:
			print("aknint warning, order of interpolation too large")
			m = n - 1

		k = n - 1
		if n < 2:
			print("aknint n<2, ybar returned as y[1]")
			return yMatrix[1]

		s = xMatrix[2] - xMatrix[1]
		if (inn>=0) and (n!=2):
			for i in range(3,n+1):
				z = (xMatrix[i] - xMatrix[i-1]) * s
				if z <= 0:
					print ("aknint x(i) not sequenced properly")
					print ("aknint n.lt.2 ybar returned as y[1]")
					return yMatrix[1]

		if s < 0:
			for j in range(1,n+1):
				if xbar>=xMatrix[j]: break
			if xbar<xMatrix[j]: j = n
		else:
			for j in range(1,n+1):
				if xbar<=xMatrix[j]: break
			if xbar>xMatrix[j]: j = n

		TMatrix = np.zeros(82)			# TMatrix

		k = m
		m += 1
		j = j - math.trunc(m/2)
		j = max(j,1)
		j = min(j,n-k)
		mend = j + k
		for i in range(j,mend+1):
			kk = i - j +1
			TMatrix[kk] = yMatrix[i]
			TMatrix[kk+m] = xMatrix[i] - xbar

		for i in range(1,k+1):
			for jj in range(i+1,m+1):
				TMatrix[jj] = (TMatrix[i]*TMatrix[jj+m]-TMatrix[jj]*TMatrix[i+m])/(xMatrix[jj+j-1] - xMatrix[i+j-1])

		return TMatrix[m]


	def Cromer_Cgauss(self, y):
		g = a = z = 0.0
		for j in range(1,6):
			(a,z) = self.clgndr(5,j)
			g += a * (self.Cromer_Csigma(y,z))
		return g

	def Cromer_Csigma(self, which, xPar):
		if which==0:	return self.Csigma0(xPar)
		elif which==1:	return self.Csigma1(xPar)
		elif which==2:	return self.Csigma2(xPar)
		elif which==3:	return self.Csigma3(xPar)

	def Csigma0(self, xPar):
		self.icount -= 1
		sumRes = self.sigg[self.icount] * ((self.bb)**3)/(xPar**2)/((self.rx)**2*xPar**2 - (self.bb)**2) - (self.bb)*(self.cx)*((self.rx)**2)/((self.rx)**2*xPar**2-(self.bb)**2)
		return sumRes

	def Csigma1(self, xPar):
		self.icount -= 1
		sumRes = 0.5 * (self.bb)**3 * self.sigg[self.icount] / (math.sqrt(xPar) * ((self.rx)**2*xPar**2 - (self.bb)**2 * xPar))
		return sumRes

	def Csigma2(self, xPar):
		self.icount -= 1
		x2  = xPar**2
		rx2 = (self.rx)**2
		bb2 = (self.bb)**2
		denom = xPar**3*rx2 - bb2/xPar
		sumRes = (2 * (self.bb)**3 * self.sigg[self.icount]) / (xPar**4 * denom) - (2 * (self.bb) *(self.cx) * rx2 /denom)
		return sumRes

	def Csigma3(self, xPar):
		self.icount -= 1
		sumRes = (self.bb)**3 * (self.sigg[self.icount] - (self.sedge) * xPar**2) / (xPar**2 *(xPar**2 * (self.rx)**2 - (self.bb)**2))
		return sumRes


	def clgndr (self, m,k):		# this sets a & z
		XMatrixData = [0, .06943184420297, .33000947820757, .04691007703067,.23076534494716, .03376524289992, .16939530676687,.38069040695840, .02544604382862, .12923440720030, \
			.29707742431130, .01985507175123, .10166676129319,.23723379504184, .40828267875217, .01591988024619,.08198444633668, .19331428364971, .33787328829809, \
			.01304673574141, .06746831665551, .16029521585049, .28330230293537, .42556283050918, .01088567092697, .05646870011595, .13492399721298, .24045193539659, \
			.36522842202382, .00921968287664, .04794137181476,.11504866290285, .20634102285669, .31608425050091, .43738329574426, .00790847264071, .04120080038851, \
			.09921095463335, .17882533027983, .27575362448178,.38477084202243, .00685809565159, .03578255816821,.08639934246512, .15635354759416, .24237568182092, \
			.34044381553605, .44597252564632, .00600374098758,.031363303799647, .075896708294787, .13779113431991,.21451391369574, .30292432646121, .39940295300128, \
			.00529953250417, .02771248846338, .06718439880608,.12229779582250, .19106187779868, .27099161117138,.35919822461038, .45249374508118]

		AMatrixData = [0,.17392742256873, .32607257743127, .11846344252810,.23931433524968, .28444444444444, .085662246189585,.18038078652407, .23395696728635, .06474248308443, \
			.13985269574464, .19091502525256, .20897959183674,.05061426814519, .11119051722669, .15685332293894,.18134189168918, .04063719418079, .09032408034743, \
			.13030534820147, .03333567215434, .15617353852000,.16511967750063, .07472567457529, .10954318125799,.13463335965500, .14776211235738, .02783428355809, \
			.06279018473245, .09314510546387, .11659688229599,.13140227225512, .13646254338895, .02358766819326,.05346966299766, .08003916427167, .10158371336153, \
			.11674626826918, .12457352290670, .02024200238266,.04606074991886, .06943675510989, .08907299038097,.10390802376845, .11314159013145, .11627577661544, \
			.01755973016588, .04007904357988, .06075928534395,.07860158357910, .09276919873897, .10259923186065,.10763192673158, .01537662099806, .03518302374405, \
			.05357961023359, .06978533896308, .08313460290850,.09308050000778, .09921574266356, .10128912096278,.01357622970588, .03112676196932, .04757925584125, \
			.06231448562777, .07479799440829, .08457825969750,.09130170752246, .09472530522754]

		kk = k
		if (m>16) or (m<4): kk = 4
		iss = 0
		ih = math.trunc((m+1)/2)
		z = 0.5
		if (m % 2) > 0.3: iss = -1

		ip = kk
		tt = 0
		if ip > ih:
			ip=m+1-ip
			tt = -1

		i4 = m - 4
		#integer math here.  Needed to force int.
		ia = int((i4*(m+4)+iss)/4 + ip)
		aa = AMatrixData[ia]
		if (ip==ih) and (iss<0): return (aa,z)

		ia = ia - int( math.trunc((i4+iss)/2) )
		if tt < 0:	z = -tt - XMatrixData[ia]
		else:		z = -tt + XMatrixData[ia]

		return (aa,z)



	ABCs = {'H':((0.39875,0.31285,0.2144,0.07135),(58.3331,14.7175,236.7147,3.4848),0.00125),
		'H-1':((0.7975,0.6257,0.4288,0.1427),(58.3331,14.7175,236.7147,3.4848),0.00125), 
		'He':((0.76844,0.72694,0.27631,0.21572),(10.9071,4.30779,1.33127,25.6848),0.01249), 
		'Li':((0.99279,0.87402,0.84240,0.23131),(4.33979,1.26006,98.7088,212.088),0.05988),
		'Li+1':((6.08475,0.86773,0.80588,0.17720),(0.00498,1.53730,4.28524,9.81413),-5.93560),
		'Be':((2.22744,1.55249,1.40060,0.58290),(0.04965,42.9165,1.66379,100.361),-1.76339),
		'Be+2':((5.69034,1.19706,1.03057,0.20150),(-0.01336,0.39000,1.97441,4.90642),-6.11950),
		'B':((2.03876,1.41491,1.11609,0.73273),(23.0888,0.97848,59.8985,0.08538),-0.30409),
		'C':((1.93019,1.87812,1.57415,0.37108),(12.7188,28.6498,0.59645,65.0337),0.24637),
		'N':((12.7913,3.28546,1.76483,0.54709),(0.02064,10.7018,30.7773,1.48044),-11.3926),
		'O':((2.95648,2.45240,1.50510,0.78135),(13.8964,5.91765,0.34537,34.0811),0.30413),
		'O-1':((3.22563,3.01717,1.42553,0.90525),(18.4991,6.65680,0.40589,61.1889),0.42362),
		'F':((3.30393,3.01753,1.35754,0.83645),(11.2651,4.66504,0.33760,27.9898),0.48398),
		'F-1':((3.63220,3.51057,1.26064,0.94071),(5.27756,14.7353,0.44226,47.3437),0.65340),
		'Na':((5.26400,2.17549,1.36690,1.08859),(4.02579,10.4796,0.84222,133.617),1.09912),
		'Na+1':((3.99479,3.37245,1.13877,0.65118),(3.11047,7.14318,0.40692,15.7319),0.84267),
		'Mg':((5.59229,2.68206,1.72235,0.73055),(4.41142,1.36549,93.4885,32.5281),1.26883),
		'Mg+2':((4.30491,3.14719,1.12859,0.49034),(2.55961,5.60660,0.41574,11.4840),0.92893),
		'Al':((5.35047,2.92451,2.27309,1.16531),(3.48665,1.20535,42.6051,107.170),1.28489),
		'Al+3':((4.17448,3.38760,1.20296,0.52814),(1.93816,4.14553,0.22875,8.28524),0.70679),
		'Si':((5.79411,3.22390,2.42795,1.32149),(2.57104,34.1775,0.86937,85.3410),1.23139),
		'Si+4':((4.43918,3.20345,1.19453,0.41653),(1.64167,3.43757,0.21490,6.65365),0.74630),
		'P':((6.92073,4.14396,2.01697,1.53860),(1.83778,27.0198,0.21318,67.1086),0.37870),
		'S':((7.18742,5.88671,5.15858,1.64403),(1.43280,0.02865,22.1101,55.4651),-3.87732),
		'Cl':((9.83957,7.53181,6.07100,1.87128),(-0.00053,1.11119,18.0846,45.3666),-8.31430),
		'Cl-1':((18.0842,7.47202,6.46337,2.43918),(0.00129,1.12976,19.3079,59.0633),-16.4654),
		'Ar':((16.8752,8.32256,6.91326,2.18515),(-0.01456,0.83310,14.9177,37.2256),-16.2972),
		'K':((8.11756,7.48062,1.07795,0.97218),(12.6684,0.76409,211.222,37.2727),1.35009),
		'K+1':((9.70659,7.37245,5.67228,1.90668),(0.59947,11.8765,-0.08359,26.7668),-6.65819),
		'Ca':((8.60272,7.50769,1.75117,0.96216),(10.2636,0.62794,149.301,60.2274),1.17430),
		'Ca+2':((13.2063,11.0586,7.73221,1.72057),(0.39466,-0.08204,9.62976,20.3341),-15.7176),
		'Sc':((9.06482,7.55526,2.05017,1.28745),(8.77431,0.53306,123.880,36.8890),1.03849),
		'Sc+3':((13.4008,8.02730,1.65943,1.57936),(0.29854,7.96290,-0.28604,16.0662),-6.66668),
		'Ti':((9.54969,7.60067,2.17223,1.75438),(7.60579,0.45899,109.099,27.5715),0.91762),
		'Ti+3':((17.7344,8.73816,5.25691,1.92134),(0.22061,7.04716,-0.15762,15.9768),-14.6519),
		'Ti+4':((19.5114,8.23473,2.01341,1.52080),(0.17885,6.67018,-0.29263,12.9464),-13.2803),
		'V':((10.0661,7.61420,2.23551,2.23170),(6.67721,0.40322,98.5954,22.5720),0.84574),
		'V+2':((9.34513,7.68833,2.94531,0.26998),(6.49985,0.39491,15.9868,41.0832),0.75143),
		'V+3':((9.43141,7.74190,2.15343,0.01686),(6.39535,0.38335,15.1908,63.9690),0.65657),
		'V+5':((15.6887,8.14208,2.03081,-9.57602),(0.67900,5.40135,9.97278,0.94046),1.71430),
		'Cr':((10.4757,7.51402,3.50115,1.54902),(6.01658,0.37426,19.0654,97.4599),0.95226),
		'Cr+2':((9.54034,7.75090,3.58274,0.50911),(5.66078,0.34426,13.3075,32.4224),0.61690),
		'Cr+3':((9.68090,7.81136,2.87603,0.11357),(5.59463,0.33439,12.8288,32.8761),0.51827),
		'Mn':((11.2519,7.36935,3.04107,2.27703),(5.34818,0.34373,17.4089,84.2139),1.05195),
		'Mn+2':((9.78094,7.79153,4.18544,0.72736),(4.98303,0.30421,11.4399,27.7750),0.51454),
		'Mn+3':((9.84521,7.87194,3.56531,0.32361),(4.91797,0.29439,10.8171,24.1281),0.39397),
		'Mn+4':((9.96253,7.97057,2.76067,0.05445),(4.84850,0.28330,10.4852,27.5730),0.25188),
		'Fe':((11.9185,7.04848,3.34326,2.27228),(4.87394,0.34023,15.9330,79.0339),1.40818),
		'Fe+2':((10.1270,7.78007,4.71825,0.89547),(4.44133,0.27418,10.1451,24.8302),0.47888),
		'Fe+3':((10.0333,7.90625,4.20562,0.55048),(4.36007,0.26250,9.35847,20.4105),0.30429),
		'Co':((12.6158,6.62642,3.57722,2.25644),(4.48994,0.35459,14.8402,74.7352),1.91452),
		'Co+2':((10.5942,7.67791,5.15947,1.01440),(4.00858,0.25410,9.21931,22.7516),0.55358),
		'Co+3':((10.3380,7.88173,4.76795,0.72559),(3.90969,0.23867,8.35583,18.3491),0.28667),
		'Ni':((13.3239,6.18746,3.74792,2.23195),(4.17742,0.38682,14.0123,71.1195),2.49899),
		'Ni+2':((11.1650,7.45636,5.51106,1.09496),(3.65944,0.24397,8.52556,21.1647),0.77218),
		'Ni+3':((10.7806,7.75868,5.22746,0.84711),(3.54770,0.22314,7.64468,16.9673),0.38604),
		'Cu':((13.9352,5.84833,4.64221,1.44753),(3.97779,0.44555,13.3971,74.1605),3.11686),
		'Cu+1':((12.4655,6.63111,5.76679,1.34230),(3.54270,0.28920,9.31140,26.9799),1.79285),
		'Cu+2':((11.8168,7.11181,5.78135,1.14523),(3.37484,0.24408,7.98760,19.8970),1.14431),
		'Zn':((14.6744,5.62816,3.92540,2.16398),(3.71486,0.50033,12.8862,65.4071),3.59838),
		'Zn+2':((12.5225,6.68507,5.98382,1.17317),(3.13961,0.25431,7.55544,18.8543),1.63497),
		'Ga':((15.3412,5.74150,3.10733,2.52764),(3.63868,0.65640,16.0719,70.7609),4.26842),
		'Ga+3':((12.6920,6.69883,6.06692,1.00660),(2.80262,0.22789,6.36441,14.4122),1.53545),
		'Ge':((15.4378,6.00432,3.05158,2.93572),(3.39715,0.73097,18.9533,63.7969),4.56068),
		'As':((15.4043,6.13723,3.74679,3.01390),(3.07517,0.74113,21.0014,57.7446),4.69149),
		'Se':((15.5372,5.98288,4.83996,2.93549),(2.71530,0.68962,21.0079,52.4308),4.70026),
		'Br':((15.9934,6.02439,5.51599,2.88716),(2.35651,19.7393,0.58143,47.3323),4.57602),
		'Br-1':((15.4080,6.78083,6.00715,2.99332),(2.43532,22.0832,0.68621,64.9193),4.80234),
		'Kr':((16.8494,7.19790,4.92564,2.91606),(2.01856,18.0409,0.39741,42.5054),4.10864),
		'Rb':((11.4809,9.46904,9.16981,1.42608),(1.08140,18.2800,2.38825,185.293),5.43921),
		'Rb+1':((17.8943,8.59341,7.91428,2.47499),(1.71750,0.09258,15.4484,32.5110),-.087756),
		'Sr':((11.6164,9.73009,8.68081,2.60986),(1.85574,14.6109,0.89852,139.830),5.34841),
		'Sr+2':((18.2430,8.90811,1.69192,-32.1118),(1.51215,13.6536,27.8238,-0.01488),39.2691),
		'Y':((19.0567,6.50783,4.81524,2.84786),(1.24615,9.68019,18.8903,121.353),5.76121),
		'Y+3':((18.4207,9.75213,1.05270,-33.4755),(1.34457,12.0631,25.1684,-0.01023),40.2513),
		'Zr':((19.2273,10.1378,2.48177,2.42892),(1.15488,10.7877,120.126,33.3722),5.71886),
		'Zr+4':((19.1301,10.1098,0.98896,-0.00004),(1.16051,10.4084,20.7214,-3.20442),5.77164),
		'Nb':((19.3496,10.8737,3.47687,1.64516),(1.06626,10.5977,32.6174,120.397),5.65073),
		'Nb+3':((19.1248,18.2989,11.0121,2.04325),(1.07235,0.00315,10.3385,25.9292),-12.4799),
		'Nb+5':((19.0175,10.7591,1.09900,0.48469),(1.06028,9.36239,0.03765,20.9764),4.64045),
		'Mo':((19.3885,11.8308,3.75919,1.46772),(0.97877,10.0885,31.9738,117.932),5.55047),
		'Mo+3':((19.6761,18.0893,11.7086,2.50624),(0.95118,-0.00669,9.61097,24.0356),-12.9813),
		'Mo+5':((19.6054,17.9292,11.3451,1.04247),(0.94029,-0.00795,8.76715,19.3690),-12.9217),
		'Mo+6':((19.4800,17.6328,11.0940,0.37154),(0.94043,-0.00723,8.29745,18.9700),-12.5778),
		'Tc':((19.3597,12.8087,3.41372,1.99926),(0.89356,9.27497,32.3513,107.406),5.41556),
		'Ru':((19.4316,13.7309,4.26537,1.28720),(0.82092,8.97737,28.2621,111.501),5.28192),
		'Ru+3':((20.8024,13.2995,3.27542,2.21026),(0.74711,8.36626,20.6179,-0.14664),1.41087),
		'Ru+4':((41.5821,12.9936,2.71276,-24.2593),(0.61466,7.99801,18.1564,0.43857),6.97025),
		'Rh':((19.4524,14.6845,4.50240,1.24740),(0.75019,8.42622,26.1564,107.780),5.11007),
		'Rh+3':((25.0958,14.1510,3.64428,-12.5768),(0.61346,7.80244,19.0932,0.13532),11.6838),
		'Rh+4':((41.5236,13.8272,3.07969,-25.9694),(0.52905,7.49419,16.9498,0.32686),8.53824),
		'Pd':((19.5123,15.3800,5.38330,0.81015),(0.68583,7.95714,23.1808,65.9295),4.91427),
		'Pd+2':((19.4652,15.5805,4.04748,0.02216),(0.68159,7.80880,20.9573,110.020),4.88510),
		'Pd+4':((51.1288,14.6979,3.41607,-38.2678),(0.43734,7.03139,15.8623,0.26589),11.0241),
		'Ag':((19.5284,16.5811,4.99150,1.21404),(0.62387,7.39504,22.2282,100.226),4.68114),
		'Ag+1':((19.5416,16.4239,5.12995,0.24053),(0.62273,7.39663,20.5530,59.0604),4.66470),
		'Ag+2':((19.5152,16.4852,4.32525,0.02777),(0.62050,73.0347,19.3673,92.9184),4.64695),
		'Cd':((19.5528,17.5717,4.47374,1.98562),(0.56604,6.79630,21.2907,85.2777),4.41158),
		'Cd+2':((19.5901,17.3740,4.62594,0.03770),(0.56389,6.83082,17.8856,76.2909),4.37269),
		'In':((19.5872,18.7169,4.02722,2.51452),(0.51510,6.29430,22.7308,88.5675),4.14542),
		'In+3':((19.6698,18.1942,4.09851,0.00365),(0.50926,6.28098,15.4189,160.227),4.03396),
		'Sn':((19.6527,19.5108,3.86895,3.14764),(0.46604,5.76321,24.0627,78.1533),3.81227),
		'Sn+2':((19.7166,18.9265,3.79775,1.86248),(0.46027,5.66448,17.7248,42.8086),3.69648),
		'Sn+4':((19.7914,18.9162,3.64761,0.00000),(0.45879,5.76682,13.3733,0.00000),3.64494),
		'Sb':((20.0755,19.7766,4.30389,3.44952),(5.24328,0.41858,26.0178,70.1646),3.38881),
		'Sb+3':((19.8617,19.5199,3.73465,1.61027),(0.41409,5.18292,16.8529,35.1406),3.27356),
		'Sb+5':((19.9613,19.5889,3.24333,0.00000),(0.41262,5.30028,11.7603,0.00000),3.20701),
		'Te':((20.4608,20.0336,5.38664,3.33079),(4.74225,0.37041,27.3458,65.0573),2.78462),
		'I':((20.7492,20.5640,6.86158,2.97589),(4.27091,0.31960,27.3186,61.5375),1.84739),
		'I-1':((20.8307,20.4454,7.52618,3.18616),(4.29514,0.32402,29.8990,81.4344),2.00513),
		'Xe':((21.6679,21.0085,8.43382,2.62265),(0.26422,3.83526,26.2297,58.4830),0.26635),
		'Cs':((22.3163,21.1792,10.7382,1.46163),(0.23092,3.49464,25.1864,232.829),-0.70709),
		'Cs+1':((23.9649,21.2204,9.76727,1.61550),(0.20448,3.43876,23.4941,49.7057),-2.56728),
		'Ba':((27.7489,21.3777,11.0400,2.68186),(0.15152,3.09817,20.6774,178.819),-6.85854),
		'Ba+2':((29.2996,21.4669,10.9209,0.80126),(0.14047,3.08785,20.8818,46.8842),-8.48753),
		'La':((33.2109,21.7181,11.6222,3.17239),(0.11040,2.83641,19.3886,144.438),-12.7404),
		'La+3':((43.6346,21.7192,11.7264,0.32945),(0.07854,2.78360,18.4930,49.2222),-23.4085),
		'Ce':((29.4100,22.2428,11.9818,3.19259),(0.12335,2.74837,18.3794,139.603),-8.84560),
		'Ce+3':((49.1105,22.3499,11.8399,0.67455),(0.06535,2.67229,17.2040,38.1904),-28.9739),
		'Ce+4':((66.7693,21.8563,12.2486,0.09617),(0.04464,2.53711,16.4477,64.4675),-46.9691),
		'Pr':((22.9220,22.2518,12.2269,2.72431),(2.78604,0.18015,17.6663,160.915),-1.13930),
		'Pr+3':((49.4655,22.9705,11.8015,1.12179),(0.06197,2.57634,16.0371,32.3673),-29.3586),
		'Pr+4':((62.6752,22.4952,12.4946,0.20294),(0.04586,2.45900,15.5713,46.5889),-42.8667),
		'Nd':((23.4069,19.7073,12.5016,2.72850),(2.71587,0.20950,16.9122,156.556),1.64038),
		'Nd+3':((49.4292,23.6116,11.6190,1.68986),(0.05936,2.48611,14.9366,28.4515),-29.3493),
		'Pm':((23.8480,17.5535,12.7324,2.72975),(2.65746,0.24780,16.2463,152.682),4.12018),
		'Pm+3':((49.2699,24.2700,11.3481,2.32869),(0.05709,2.40059,13.9124,25.6906),-29.2165),
		'Sm':((24.2242,15.9132,12.9238,2.72836),(2.60993,0.29475,15.6554,149.221),6.19355),
		'Sm+3':((36.3271,24.8202,11.3426,2.62300),(0.07823,2.33602,13.1872,24.3996),-16.1429),
		'Eu':((24.5148,14.8058,13.0799,2.72477),(2.57225,0.34930,15.1280,146.103),7.85731),
		'Eu+2':((25.6516,23.9387,10.5738,4.05853),(2.36073,0.13260,12.6495,25.0026),-3.22358),
		'Eu+3':((33.2862,25.5041,11.1494,3.13496),(0.08350,2.26275,12.3883,22.8351),-13.0748),
		'Gd':((24.4004,14.0308,13.1754,3.24472),(2.47491,0.40238,14.4670,119.738),9.12488),
		'Gd+3':((29.0290,26.1387,11.0510,3.52244),(0.09521,2.19696,11.7141,21.6929),-8.74150),
		'Tb':((24.3736,13.8649,13.2510,3.24435),(2.46637,0.47517,14.0424,117.446),10.2420),
		'Tb+3':((26.7821,25.9463,10.9724,3.88172),(2.13333,0.10597,11.0974,20.7042),-5.58307),
		'Dy':((24.6193,14.2735,13.3567,2.70316),(2.52208,0.54556,13.8487,138.385),11.0290),
		'Dy+3':((27.3805,22.2062,10.9975,4.10030),(2.07832,0.12643,10.5960,19.9671),-1.68516),
		'Ho':((24.3162,14.9012,13.3895,2.69309),(2.52724,0.61572,13.5041,136.246),11.6817),
		'Ho+3':((27.9956,19.9560,11.0106,4.33205),(2.02324,0.14275,10.1165,19.2589),0.70499),
		'Er':((23.8201,15.8796,13.3938,2.68190),(2.54419,0.68445,13.1932,134.282),12.2062),
		'Er+3':((28.5315,17.4316,11.1113,4.43156),(1.97796,0.17182,9.73821,18.7294),3.49325),
		'Tm':((23.1386,17.1707,13.3703,2.66981),(2.57320,0.74948,12.9126,132.468),12.6322),
		'Tm+3':((29.0215,15.6168,11.2288,4.49403),(1.93707,0.20467,9.40342,18.2607),5.63812),
		'Yb':((22.3028,18.7202,13.3200,2.65701),(2.61393,0.80868,12.6590,130.783),12.9818),
		'Yb+2':((29.1313,13.5855,11.4132,4.69659),(1.99979,0.32335,9.59277,20.3507),9.17182),
		'Yb+3':((29.4761,14.4357,11.3446,4.54681),(1.89879,0.23793,9.09408,17.8206),7.19600),
		'Lu':((21.1866,20.1760,13.0532,3.21190),(0.88654,2.68610,12.2746,107.128),13.3489),
		'Lu+3':((29.8480,13.6268,11.4750,4.56009),(1.86596,0.27623,8.82479,17.4364),8.48923),
		'Hf':((24.6725,17.2295,12.8069,3.55970),(0.97400,2.89038,12.2897,93.4381),13.7049),
		'Ta':((28.1757,14.4288,12.6412,3.74436),(1.04034,3.20784,12.5054,85.0183),13.9824),
		'W':((31.0935,12.5273,12.3769,3.79138),(1.07885,12.8331,3.63298,79.7647),14.1842),
		'Re':((33.2961,12.3497,11.2819,3.72367),(1.09315,13.2559,4.16736,76.6562),14.3239),
		'Os':((34.8667,11.9524,11.1851,3.56436),(1.08840,13.8042,4.79179,75.1399),14.4097),
		'Ir':((35.9454,11.9980,11.2501,3.34312),(1.06924,5.43443,14.4983,74.7918),14.4449),
		'Pt':((36.8102,13.0747,11.3323,2.31421),(1.04422,6.07340,15.7018,73.8375),14.4526),
		'Au':((37.3027,14.9306,10.3425,2.01229),(1.00810,6.52550,16.5100,76.9117),14.3992),
		'Hg':((37.5186,17.0353,8.51121,2.63340),(0.96455,6.65786,16.8438,76.7228),14.2911),
		'Tl':((37.6947,19.7195,6.38290,3.00960),(0.92263,6.78248,19.2435,85.9267),14.1800),
		'Pb':((37.7383,21.3394,5.17527,3.71604),(0.87755,6.58964,21.2437,78.8094),14.0203),
		'Bi':((37.7143,22.4542,4.84549,4.14816),(0.83222,6.27051,24.4693,72.1558),13.8301),
		'Po':((37.6297,23.1323,5.59203,4.04218),(0.78640,5.86644,27.8678,68.1617),13.5991),
		'At':((37.4971,23.5635,7.15953,3.45924),(0.74012,5.42694,29.8350,66.3564),13.3183),
		'Rn':((37.3308,23.8933,9.02222,2.77349),(0.69354,4.98696,30.0338,65.5799),12.9796),
		'Fr':((37.1902,24.1306,11.5026,1.47980),(0.65303,4.61305,29.2597,257.965),12.6868),
		'Ra':((36.9820,24.2495,11.8719,2.72428),(0.60394,4.17857,24.3782,200.024),12.1642),
		'Ac':((36.8705,24.7131,12.3889,3.26501),(0.56458,3.88776,23.1506,161.726),11.7484),
		'Th':((36.7754,25.2506,13.0681,3.63791),(0.52510,3.61658,22.3410,139.164),11.2497),
		'Pa':((37.1457,25.2998,13.7846,3.29611),(0.52020,3.66300,20.6539,150.973),11.4561),
		'U':((37.2808,25.6563,14.3501,3.30732),(0.50239,3.58562,19.6342,146.633),11.3864),
		'Np':((37.3968,26.0671,14.8366,3.31586),(0.48676,3.52325,18.7419,142.798),11.3632),
		'Pu':((37.6407,26.5603,15.4492,2.79814),(0.47976,3.57178,17.9814,165.232),11.5358),
		'Am':((37.6909,27.1436,15.7842,2.79600),(0.46617,3.52195,17.3069,161.931),11.5685),
		'Cm':((37.5543,27.6657,15.8858,3.32758),(0.44932,3.38713,16.6498,133.547),11.5431),
		'Bk':((37.5273,28.3202,16.1181,3.32793),(0.43930,3.35014,16.1000,131.027),11.6823),
		'Cf':((37.6111,29.2465,16.4566,2.78216),(0.43255,3.39285,15.6791,153.766),11.8853),
		'Es':((37.4979,30.0495,16.5881,2.77596),(0.42353,3.35234,15.2381,151.474),12.0698),
		'Fm':((37.3380,30.8936,16.6818,2.76929),(0.41562,3.31193,14.8362,149.344),12.2983),
		'Md':((37.1301,31.7721,16.7422,2.76232),(0.40883,3.27132,14.4683,147.353),12.5741),
		'No':((36.8731,32.6784,16.7732,2.75513),(0.40324,3.23045,14.1302,145.481),12.9008),
		'Lr':((36.3813,33.1999,16.6469,3.31406),(0.40165,3.13608,13.7255,119.377),13.4313) }


	knownValences = {'H':(0,-1),'He':(0,),'Li':(0,1),'Be':(0,2),'B':(0,),'C':(0,),'N':(0,), \
		'O':(0,-1),'F':(0,-1),'Na':(0,1),'Mg':(0,2),'Al':(0,3),'Si':(0,4),'P':(0,),'S':(0,), \
		'Cl':(0,-1),'Ar':(0,),'K':(0,1),'Ca':(0,2),'Sc':(0,3),'Ti':(0,3,4),'V':(0,2,3,5), \
		'Cr':(0,2,3),'Mn':(0,2,3,4),'Fe':(0,2,3),'Co':(0,2,3),'Ni':(0,2,3),'Cu':(0,1,2), \
		'Zn':(0,2),'Ga':(0,3),'Ge':(0,),'As':(0,),'Se':(0,),'Br':(0,-1),'Kr':(0,),'Rb':(0,1), \
		'Sr':(0,2),'Y':(0,3),'Zr':(0,4),'Nb':(0,3,5),'Mo':(0,3,5,6),'Tc':(0,),'Ru':(0,3,4), \
		'Rh':(0,3,4),'Pd':(0,2,4),'Ag':(0,1,2),'Cd':(0,2),'In':(0,3),'Sn':(0,2,4),'Sb':(0,3,5), \
		'Te':(0,),'I':(0,-1),'Xe':(0,),'Cs':(0,1),'Ba':(0,2),'La':(0,3),'Ce':(0,3,4), \
		'Pr':(0,3,4),'Nd':(0,3),'Pm':(0,3),'Sm':(0,3),'Eu':(0,2,3),'Gd':(0,3),'Tb':(0,3), \
		'Dy':(0,3),'Ho':(0,3),'Er':(0,3),'Tm':(0,3),'Yb':(0,2,3),'Lu':(0,3),'Hf':(0,), \
		'Ta':(0,),'W':(0,),'Re':(0,),'Os':(0,),'Ir':(0,),'Pt':(0,),'Au':(0,),'Hg':(0,), \
		'Tl':(0,),'Pb':(0,),'Bi':(0,),'Po':(0,),'At':(0,),'Rn':(0,),'Fr':(0,),'Ra':(0,), \
		'Ac':(0,),'Th':(0,),'Pa':(0,),'U':(0,),'Np':(0,),'Pu':(0,),'Am':(0,),'Cm':(0,), \
		'Bk':(0,),'Cf':(0,),'Es':(0,),'Fm':(0,),'Md':(0,),'No':(0,),'Lr':(0,)}


	def setElementDict(self):
		AllElementsInfo = { 'Li':{'NSHELLS':2, 'ETERM':-0.001,  'shells':[
			{'Shell':'1S1/2', 'Func':2, 'BindEnergy':0.05475, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,24.8801,1.02812,0.219,0.092527,0.060272,0],
			'sig':[0.001302,0.051677,2.04573,73.6827,2367.26,0.065318,2174.79,189730,1618910,3022230,0]},
			{'Shell':'2S1/2', 'Func':2, 'BindEnergy':0.00534, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,2.42666,0.100277,0.02136,0.009025,0.005879,0],
			'sig':[2.5e-05,0.000866,0.03219,1.14365,35.4626,2.25543,17745.8,440576,1333730,1448480,0]}] },
			'Be':{'NSHELLS':2, 'ETERM':-0.001,  'shells':[
			{'Shell':'1S1/2', 'Func':2, 'BindEnergy':0.111, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,50.4418,2.0844,0.444,0.187588,0.122196,0],
			'sig':[0.005502,0.216351,8.28357,277.734,7976.13,0.025604,866.963,81105.1,771925,2051790,0]},
			{'Shell':'2S1/2', 'Func':2, 'BindEnergy':0.00842, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,3.82631,0.158114,0.03368,0.01423,0.009269,0],
			'sig':[0.000208,0.007329,0.263835,8.65201,237.105,4.02922,31112.8,621490,1648230,1031230,0]}] },
			'B':{'NSHELLS':3, 'ETERM':-0.002,  'shells':[
			{'Shell':'1S1/2', 'Func':2, 'BindEnergy':0.188, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,85.433,3.53034,0.752,0.317717,0.206962,0],
			'sig':[0.01652,0.639404,23.6174,741.658,19577.5,0.01336,447.895,43871.6,435450,1167090,0]},
			{'Shell':'2S1/2', 'Func':2, 'BindEnergy':0.01347, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,6.12118,0.252945,0.05388,0.022764,0.014829,0],
			'sig':[0.000828,0.029313,1.02559,31.2025,776.769,3.39596,26979.3,581240,1365940,870619,0]},
			{'Shell':'2P1/2', 'Func':2, 'BindEnergy':0.0047, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,2.13582,0.088258,0.0188,0.007943,0.005174,0],
			'sig':[0,1.3e-05,0.001205,0.104659,7.67966,0.400328,30321.8,1377610,6894480,1.44485e+07,0]}] },
			'C':{'NSHELLS':3, 'ETERM':-0.003,  'shells':[
			{'Shell':'1S1/2', 'Func':2, 'BindEnergy':0.2838, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,128.967,5.32931,1.1352,0.479617,0.312424,0],
			'sig':[0.040228,1.5275,54.3805,1610.34,39562.1,0.00832,275.13,27737.3,281873,765563,0]},
			{'Shell':'2S1/2', 'Func':2, 'BindEnergy':0.01951, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,8.86594,0.366367,0.07804,0.032972,0.021478,0],
			'sig':[0.002235,0.078572,2.65592,75.4174,1707.1,2.68838,21804.6,492388,1077520,678007,0]},
			{'Shell':'2P1/2', 'Func':2, 'BindEnergy':0.0064, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,2.90836,0.120182,0.0256,0.010816,0.007046,0],
			'sig':[2e-06,0.000131,0.011822,0.941144,63.7416,1.0633,76115.4,3070110,1.1208e+07,1.8939e+07,0]}] },
			'N':{'NSHELLS':4, 'ETERM':-0.005,  'shells':[
			{'Shell':'1S1/2', 'Func':2, 'BindEnergy':0.4016, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,182.499,7.54141,1.6064,0.678697,0.442106,0],
			'sig':[0.08474,3.15485,108.397,3054.15,70342.9,0.005561,182.453,18816.3,196109,545683,0]},
			{'Shell':'2S1/2', 'Func':2, 'BindEnergy':0.02631, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,11.9561,0.49406,0.10524,0.044464,0.028964,0],
			'sig':[0.004934,0.170915,5.56366,148.862,3093.78,2.1979,17981.1,406346,854338,509075,0]},
			{'Shell':'2P1/2', 'Func':2, 'BindEnergy':0.0092, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,4.18076,0.172761,0.0368,0.015548,0.010128,0],
			'sig':[6e-06,0.000451,0.039588,2.99486,182.204,0.817082,60970.4,2508750,7526410,1.07059e+07,0]},
			{'Shell':'2P3/2', 'Func':2, 'BindEnergy':0.0092, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,4.18076,0.172761,0.0368,0.015548,0.010128,0],
			'sig':[2e-06,0.000212,0.019391,1.48127,90.3186,0.402362,30338.7,1251750,3764250,5362580,0]}] },
			'O':{'NSHELLS':4, 'ETERM':-0.007,  'shells':[
			{'Shell':'1S1/2', 'Func':2, 'BindEnergy':0.532, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,241.757,9.99011,2.128,0.899071,0.585658,0],
			'sig':[0.160505,5.85707,194.312,5221.69,111658,0.004204,135.4,14075.4,147498,417833,0]},
			{'Shell':'2S1/2', 'Func':2, 'BindEnergy':0.0237, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,10.77,0.445048,0.0948,0.040053,0.02609,0],
			'sig':[0.009547,0.325385,10.1911,256.266,4902.52,5.65028,33413.8,514644,839020,466361,0]},
			{'Shell':'2P1/2', 'Func':2, 'BindEnergy':0.0071, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,3.22646,0.133327,0.0284,0.011999,0.007816,0],
			'sig':[1.6e-05,0.001246,0.105102,7.5827,419.397,5.73374,230141,3959250,8621530,1.06326e+07,0]},
			{'Shell':'2P3/2', 'Func':2, 'BindEnergy':0.0071, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,3.22646,0.133327,0.0284,0.011999,0.007816,0],
			'sig':[1.3e-05,0.001175,0.102652,7.48369,415.102,5.65494,228981,3953840,8638010,1.06738e+07,0]}] },
			'F':{'NSHELLS':4, 'ETERM':-0.009,  'shells':[
			{'Shell':'1S1/2', 'Func':2, 'BindEnergy':0.6854, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,311.467,12.8707,2.7416,1.15831,0.75453,0],
			'sig':[0.280725,10.0407,322.388,8296.85,164968,0.003362,102.272,10744,113532,328531,0]},
			{'Shell':'2S1/2', 'Func':2, 'BindEnergy':0.031, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,14.0874,0.582131,0.124,0.052389,0.034127,0],
			'sig':[0.016849,0.564889,17.0782,405.709,7241.6,4.16126,25509.6,409592,663627,342295,0]},
			{'Shell':'2P1/2', 'Func':2, 'BindEnergy':0.0086, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,3.9081,0.161494,0.0344,0.014534,0.009467,0],
			'sig':[3.8e-05,0.002953,0.240616,16.3674,847.312,6.02639,224444,3326680,6272800,6917330,0]},
			{'Shell':'2P3/2', 'Func':2, 'BindEnergy':0.0086, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,3.9081,0.161494,0.0344,0.014534,0.009467,0],
			'sig':[4.8e-05,0.004174,0.351481,24.1646,1255.79,8.86774,334560,4983430,9439700,1.04397e+07,0]}] },
			'Ne':{'NSHELLS':4, 'ETERM':-0.011,  'shells':[
			{'Shell':'1S1/2', 'Func':2, 'BindEnergy':0.8669, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,393.946,16.279,3.4676,1.46505,0.954336,0],
			'sig':[0.461049,16.176,504.383,12497,235837,0.002751,77.5975,8264.12,88571,262355,0]},
			{'Shell':'2S1/2', 'Func':2, 'BindEnergy':0.045, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,20.4494,0.845028,0.18,0.076049,0.049539,0],
			'sig':[0.027831,0.915888,26.7598,604.639,10104.4,2.0982,14937.4,281952,503242,240853,0]},
			{'Shell':'2P1/2', 'Func':2, 'BindEnergy':0.0183, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,8.31608,0.343645,0.0732,0.030927,0.020146,0],
			'sig':[8.1e-05,0.006273,0.495196,31.896,1569.14,0.647713,45953.1,1562450,3068620,2868420,0]},
			{'Shell':'2P3/2', 'Func':2, 'BindEnergy':0.0183, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,8.31608,0.343645,0.0732,0.030927,0.020146,0],
			'sig':[0.000136,0.011774,0.960985,62.6071,3095.17,1.25662,91012,3113750,6153210,5780000,0]}] },
			'Na':{'NSHELLS':4, 'ETERM':-0.014,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':1.0721, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,22.8544,4.64584,2.1442,1.39372,1.12487,1.07317],
			'sig':[0.719679,24.7575,749.832,17837.6,0,40.4996,5139.83,44760.4,137346,242031,194894]},
			{'Shell':'2S1/2', 'Func':2, 'BindEnergy':0.0633, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,28.7655,1.18867,0.2532,0.106976,0.069684,0],
			'sig':[0.04549,1.47549,41.7577,896.968,13934.5,1.17296,9320.54,201357,518225,355564,0]},
			{'Shell':'2P1/2', 'Func':2, 'BindEnergy':0.0311, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,14.1328,0.584009,0.1244,0.052559,0.034237,0],
			'sig':[0.000179,0.013787,1.06471,65.0138,2978.45,0.172414,16576.1,938348,2437550,1397260,0]},
			{'Shell':'2P3/2', 'Func':2, 'BindEnergy':0.0311, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,14.1328,0.584009,0.1244,0.052559,0.034237,0],
			'sig':[0.0003,0.025871,2.06277,127.486,5874.6,0.329745,32774.9,1869310,4888040,2814550,0]}] },
			'Mg':{'NSHELLS':4, 'ETERM':-0.018,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':1.305, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,27.8192,5.6551,2.61,1.69649,1.36923,1.30631],
			'sig':[1.07749,36.359,1071.03,24479.3,0,31.9453,4077.84,35751.2,110367,192796,195278]},
			{'Shell':'2S1/2', 'Func':2, 'BindEnergy':0.0894, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,40.6261,1.67879,0.3576,0.151084,0.098417,0],
			'sig':[0.071234,2.27468,62.3695,1277.61,18539.2,0.615425,5559.93,139329,436743,487871,0]},
			{'Shell':'2P1/2', 'Func':2, 'BindEnergy':0.0514, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,23.3577,0.96521,0.2056,0.086865,0.056584,0],
			'sig':[0.000358,0.02731,2.05053,119.007,5120.12,0.04636,5738.63,450838,2111520,1121000,0]},
			{'Shell':'2P3/2', 'Func':2, 'BindEnergy':0.0514, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,23.3577,0.96521,0.2056,0.086865,0.056584,0],
			'sig':[0.000599,0.051063,3.96211,232.971,10091.8,0.086936,11313,896493,4229250,2257600,0]}] },
			'Al':{'NSHELLS':5, 'ETERM':-0.021,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':1.5596, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,33.2466,6.75838,3.1192,2.02747,1.63636,1.56116],
			'sig':[1.55751,51.5725,1478.34,32428.1,0,25.9101,3315.87,29194.7,90483.6,157688,167248]},
			{'Shell':'2S1/2', 'Func':2, 'BindEnergy':0.1177, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,53.4865,2.21022,0.4708,0.198911,0.129571,0],
			'sig':[0.107319,3.36706,89.3895,1748.37,23709.2,0.384381,3783.99,104031,369607,494166,0]},
			{'Shell':'2P1/2', 'Func':2, 'BindEnergy':0.0731, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,33.2189,1.3727,0.2924,0.123538,0.080473,0],
			'sig':[0.000667,0.050235,3.65229,201.835,8114.77,0.021483,2929.54,269588,1592400,1433480,0]},
			{'Shell':'2P3/2', 'Func':2, 'BindEnergy':0.0731, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,33.2189,1.3727,0.2924,0.123538,0.080473,0],
			'sig':[0.001113,0.093484,7.03664,394.388,15981.2,0.039481,5758.07,535215,3186260,2885160,0]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.00837567, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,3.80616,0.157282,0.033503,0.014155,0.00922,0],
			'sig':[0.00788,0.224163,5.65237,109.529,1489.21,58.856,45791.7,266194,71344.8,347981,0]}] },
			'Si':{'NSHELLS':6, 'ETERM':-0.026,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':1.8389, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,39.2005,7.9687,3.6778,2.39056,1.92941,1.84074],
			'sig':[2.18637,71.0673,1984.18,41782,0,21.3957,2740.58,24228.9,75374.5,131083,142536]},
			{'Shell':'2S1/2', 'Func':2, 'BindEnergy':0.1487, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,67.5739,2.79235,0.5948,0.2513,0.163698,0],
			'sig':[0.156228,4.81015,123.655,2312.42,29410.8,0.263393,2770.07,81446.5,310727,444896,0]},
			{'Shell':'2P1/2', 'Func':2, 'BindEnergy':0.0992, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,45.0795,1.86282,0.3968,0.167646,0.109205,0],
			'sig':[0.001176,0.087148,6.12823,323.64,12196.5,0.011261,1652.95,172008,1209020,1656120,0]},
			{'Shell':'2P3/2', 'Func':2, 'BindEnergy':0.0992, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,45.0795,1.86282,0.3968,0.167646,0.109205,0],
			'sig':[0.00196,0.161602,11.7721,631.226,24000.8,0.020111,3237.93,340892,2417060,3331670,0]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.0113572, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,5.16105,0.21327,0.045429,0.019193,0.012503,0],
			'sig':[0.014118,0.401187,9.8767,183.103,2358.03,44.4429,42208.6,313736,162653,80005.2,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.00508305, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,2.3099,0.095452,0.020332,0.00859,0.005596,0],
			'sig':[6.2e-05,0.003997,0.261709,13.4453,475.203,32.8314,122244,216557,1.1215e+07,3.22906e+07,0]}] },
			'P':{'NSHELLS':7, 'ETERM':-0.03,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':2.1455, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,45.7364,9.29732,4.291,2.78914,2.2511,2.14765],
			'sig':[2.9911,95.5345,2601.35,52644.3,0,17.7681,2290.76,20345.6,63556.1,110514,121778]},
			{'Shell':'2S1/2', 'Func':2, 'BindEnergy':0.1893, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,86.0237,3.55475,0.7572,0.319914,0.208393,0],
			'sig':[0.220794,6.66794,166.183,2980.13,35851.7,0.176891,1945.69,61948.1,254934,385899,0]},
			{'Shell':'2P1/2', 'Func':2, 'BindEnergy':0.1322, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,60.0757,2.48251,0.5288,0.223416,0.145534,0],
			'sig':[0.001978,0.144056,9.80049,496.498,17670.9,0.006065,949.57,110776,887976,1629470,0]},
			{'Shell':'2P3/2', 'Func':2, 'BindEnergy':0.1322, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,60.0757,2.48251,0.5288,0.223416,0.145534,0],
			'sig':[0.003279,0.265864,18.7692,966.597,34750.7,0.010498,1852.48,219094,1773570,3276620,0]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.0144615, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,6.57175,0.271564,0.057846,0.02444,0.01592,0],
			'sig':[0.022434,0.631072,15.114,268.41,3296.84,34.8709,38114.9,321233,227968,4926.23,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.00638493, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,2.90151,0.119899,0.02554,0.01079,0.007029,0],
			'sig':[0.000134,0.008599,0.548111,26.8109,882.156,30.0271,129890,204304,1.29018e+07,3.07272e+07,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.00633669, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,2.87959,0.118993,0.025347,0.010709,0.006976,0],
			'sig':[5.5e-05,0.003981,0.261432,12.9882,431.339,14.9381,65373.7,102237,6433920,1.5426e+07,0]}] },
			'S':{'NSHELLS':7, 'ETERM':-0.035,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':2.472, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,52.6966,10.7122,4.944,3.21358,2.59367,2.47447],
			'sig':[4.00298,125.645,3336.6,64908.3,0,15.0582,1949.68,17367.5,54399.4,94464.6,105087]},
			{'Shell':'2S1/2', 'Func':2, 'BindEnergy':0.2292, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,104.156,4.30401,0.9168,0.387344,0.252317,0],
			'sig':[0.303694,8.99559,217.438,3737.79,42614.6,0.130291,1515.56,50511.8,218042,344550,0]},
			{'Shell':'2P1/2', 'Func':2, 'BindEnergy':0.1648, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,74.8902,3.09468,0.6592,0.278509,0.181422,0],
			'sig':[0.003195,0.22841,15.0264,729.671,24527.1,0.0041,656.269,81419.6,699896,1532040,0]},
			{'Shell':'2P3/2', 'Func':2, 'BindEnergy':0.1648, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,74.8902,3.09468,0.6592,0.278509,0.181422,0],
			'sig':[0.005275,0.419764,28.6902,1417.98,48208.4,0.00684,1274.83,160726,1396900,3080350,0]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.0176882, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,8.03808,0.332157,0.070753,0.029893,0.019472,0],
			'sig':[0.033368,0.925767,21.5492,366.829,4318.39,28.5174,34478,311271,263840,5097.2,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.00781363, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,3.55075,0.146728,0.031255,0.013205,0.008602,0],
			'sig':[0.000253,0.016165,0.997794,46.4189,1431.6,26.2621,127480,190661,1.33369e+07,2.62736e+07,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.00773488, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,3.51497,0.145249,0.03094,0.013072,0.008515,0],
			'sig':[0.000208,0.014854,0.948393,44.8676,1397.85,26.2267,128772,192191,1.33504e+07,2.64808e+07,0]}] },
			'Cl':{'NSHELLS':7, 'ETERM':-0.041,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':2.8224, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,60.1662,12.2306,5.6448,3.6691,2.96132,2.82522],
			'sig':[5.25414,162.141,4201.45,78930.9,0,12.965,1677.9,14986.1,47054.5,81640.6,91375.3]},
			{'Shell':'2S1/2', 'Func':2, 'BindEnergy':0.2702, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,122.787,5.07393,1.0808,0.456633,0.297452,0],
			'sig':[0.408017,11.8551,278.076,4582.91,49648.3,0.106113,1241.04,42662.8,190255,310957,0]},
			{'Shell':'2P1/2', 'Func':2, 'BindEnergy':0.2016, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,91.6132,3.78573,0.8064,0.340701,0.221933,0],
			'sig':[0.004982,0.34948,22.261,1037.19,33091.2,0.002998,469.981,61464.8,560663,1384550,0]},
			{'Shell':'2P3/2', 'Func':2, 'BindEnergy':0.2, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,90.8862,3.75568,0.8,0.337997,0.220172,0],
			'sig':[0.008186,0.639392,42.3526,2009.42,64820.1,0.004982,933.104,123397,1131530,2813500,0]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.0175, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,7.95254,0.328622,0.07,0.029575,0.019265,0],
			'sig':[0.047339,1.29462,29.296,478.583,5403.12,39.7703,42692.9,342223,275203,19442.5,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.0068, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,3.09013,0.127693,0.0272,0.011492,0.007486,0],
			'sig':[0.000439,0.027814,1.66259,73.4912,2122.91,66.6478,197430,462804,2.05936e+07,2.86715e+07,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.0068, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,3.09013,0.127693,0.0272,0.011492,0.007486,0],
			'sig':[0.000539,0.038119,2.36164,106.295,3105.21,96.3641,295092,665788,3.05136e+07,4.30496e+07,0]}] },
			'Ar':{'NSHELLS':7, 'ETERM':-0.047,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':3.2029, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,68.2774,13.8795,6.4058,4.16375,3.36054,3.2061],
			'sig':[6.78046,205.873,5211.41,0,0,11.2207,1451.26,13007.6,40969.4,71071.4,79858.5]},
			{'Shell':'2S1/2', 'Func':2, 'BindEnergy':0.32, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,145.418,6.00909,1.28,0.540795,0.352275,0],
			'sig':[0.537746,15.3216,349.145,5530.57,57250,0.080581,990.483,35425.1,163750,276381,0]},
			{'Shell':'2P1/2', 'Func':2, 'BindEnergy':0.2473, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,112.381,4.6439,0.9892,0.417933,0.272243,0],
			'sig':[0.007536,0.518802,32.0661,1437.98,43965,0.002034,325.794,45366.8,443202,1192490,0]},
			{'Shell':'2P3/2', 'Func':2, 'BindEnergy':0.2452, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,111.426,4.60447,0.9808,0.414384,0.269931,0],
			'sig':[0.012321,0.945011,60.8128,2780.08,86040.4,0.00325,644.775,91015.1,894592,2427440,0]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.0253, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,11.4971,0.475094,0.1012,0.042757,0.027852,0],
			'sig':[0.064864,1.74861,38.5278,606.493,6609.77,19.1251,27166.3,268914,284672,42450.8,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.0124, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,5.63494,0.232852,0.0496,0.020956,0.013651,0],
			'sig':[0.000718,0.045013,2.61,110.124,3000.18,13.2102,91612.4,198423,1.02757e+07,1.52583e+07,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.0124, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,5.63494,0.232852,0.0496,0.020956,0.013651,0],
			'sig':[0.001171,0.081758,4.92371,211.845,5842.47,25.1586,181295,407273,2.01355e+07,3.05613e+07,0]}] },
			'K':{'NSHELLS':7, 'ETERM':-0.053,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':3.6074, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,76.9003,15.6323,7.2148,4.6896,3.78495,3.61101],
			'sig':[8.61559,257.381,6361.01,0,0,9.75315,1266.26,11374.3,35897.3,62242.5,70476.5]},
			{'Shell':'2S1/2', 'Func':2, 'BindEnergy':0.3771, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,171.366,7.08134,1.5084,0.637293,0.415134,0],
			'sig':[0.695426,19.444,430.745,6562.67,64891.7,0.063388,788.968,29275.8,139686,254293,0]},
			{'Shell':'2P1/2', 'Func':2, 'BindEnergy':0.2963, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,134.648,5.56404,1.1852,0.500742,0.326185,0],
			'sig':[0.011099,0.749247,44.923,1933.98,56408.5,0.001547,238.655,34589,352951,918932,0]},
			{'Shell':'2P3/2', 'Func':2, 'BindEnergy':0.2936, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,133.421,5.51334,1.1744,0.496179,0.323213,0],
			'sig':[0.018051,1.35873,84.9236,3731.18,110303,0.002378,470.764,69328.6,712622,1866130,0]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.0339, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,15.4052,0.636588,0.1356,0.05729,0.037319,0],
			'sig':[0.089548,2.38757,51.3166,778.872,8213.99,11.3997,19505.7,222586,398011,198677,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.0178, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,8.08887,0.334256,0.0712,0.030082,0.019595,0],
			'sig':[0.001234,0.077721,4.4042,177.011,4530.33,6.19071,62596.1,371855,2104740,2.65728e+07,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.0178, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,8.08887,0.334256,0.0712,0.030082,0.019595,0],
			'sig':[0.002019,0.141052,8.31027,341.028,8845.39,11.7073,123851,762296,4081950,5.26527e+07,0]}] },
			'Ca':{'NSHELLS':7, 'ETERM':-0.06,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':4.0381, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,86.0817,17.4987,8.0762,5.2495,4.23685,4.04214],
			'sig':[10.8012,317.5,7660.65,0,0,8.5894,1112.52,10011.3,31645.1,54821.8,62620.8]},
			{'Shell':'2S1/2', 'Func':2, 'BindEnergy':0.4378, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,198.95,8.22119,1.7512,0.739875,0.481957,0],
			'sig':[0.886401,24.3066,523.446,7676.93,72531.1,0.051926,645.349,24651.1,120791,221150,0]},
			{'Shell':'2P1/2', 'Func':2, 'BindEnergy':0.35, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,159.051,6.57244,1.4,0.591494,0.385301,0],
			'sig':[0.015982,1.05744,61.5381,2544.06,70789.5,0.00116,180.251,26956.6,284359,774664,0]},
			{'Shell':'2P3/2', 'Func':2, 'BindEnergy':0.3464, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,157.415,6.50484,1.3856,0.58541,0.381338,0],
			'sig':[0.025875,1.90958,115.956,4897.31,138283,0.001727,354.881,54049.8,574529,1575390,0]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.0437, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,19.8586,0.820617,0.1748,0.073852,0.048108,0],
			'sig':[0.121024,3.18752,66.8213,979.66,10024.4,7.39178,14683.5,186835,421673,383247,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.0254, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,11.5425,0.476972,0.1016,0.042926,0.027962,0],
			'sig':[0.001984,0.123838,6.82275,261.555,6312.28,2.69191,38421.4,406731,350113,4626080,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.0254, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,11.5425,0.476972,0.1016,0.042926,0.027962,0],
			'sig':[0.003221,0.223583,12.849,503.65,12333.3,5.03576,75807.6,827791,700752,9119560,0]}] },
			'Sc':{'NSHELLS':7, 'ETERM':-0.068,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':4.4928, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,95.7747,19.4691,8.9856,5.84061,4.71393,4.49729],
			'sig':[13.3755,387.105,9124.26,0,0,7.63246,985.741,8887.64,28145.2,48765.3,55765.9]},
			{'Shell':'2S1/2', 'Func':2, 'BindEnergy':0.5004, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,227.397,9.39672,2.0016,0.845667,0.550871,0],
			'sig':[1.11467,29.9885,628.362,8892.74,80391.9,0.044459,544.733,21299.1,106496,198788,0]},
			{'Shell':'2P1/2', 'Func':2, 'BindEnergy':0.4067, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,184.817,7.63718,1.6268,0.687316,0.44772,0],
			'sig':[0.022595,1.46456,82.8303,3300.46,88189.6,0.000955,142.254,21884,237792,660498,0]},
			{'Shell':'2P3/2', 'Func':2, 'BindEnergy':0.4022, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,182.772,7.55268,1.6088,0.679711,0.442766,0],
			'sig':[0.036338,2.63203,155.574,6340.28,172182,0.001371,279.05,43849.2,480607,1344320,0]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.0538, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,24.4484,1.01028,0.2152,0.090921,0.059226,0],
			'sig':[0.157317,4.07192,83.1233,1180.57,11781.1,5.22514,11549.5,158023,381183,393902,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.0323, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,14.6781,0.606543,0.1292,0.054586,0.035558,0],
			'sig':[0.002941,0.180803,9.67006,354.716,8119.83,1.61627,27698.7,365879,277918,1868140,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.0323, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,14.6781,0.606543,0.1292,0.054586,0.035558,0],
			'sig':[0.00476,0.325097,18.1513,681.727,15855.3,2.99189,54482.3,742811,575778,3671600,0]}] },
			'Ti':{'NSHELLS':7, 'ETERM':-0.075,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':4.9664, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,105.871,21.5214,9.9328,6.45629,5.21084,4.97137],
			'sig':[16.3784,466.73,10741.3,0,0,6.81414,881.865,7959.78,25236.7,43721.9,50025.1]},
			{'Shell':'2S1/2', 'Func':2, 'BindEnergy':0.5637, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,256.163,10.5854,2.2548,0.952643,0.620555,0],
			'sig':[1.38361,36.5285,744.958,10184.5,88024.5,0.036959,473.03,18804.6,95396.1,180584,0]},
			{'Shell':'2P1/2', 'Func':2, 'BindEnergy':0.4615, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,209.72,8.66624,1.846,0.779927,0.508047,0],
			'sig':[0.031345,1.98985,109.355,4199.17,107379,0.000847,120.095,18723.8,206432,581896,0]},
			{'Shell':'2P3/2', 'Func':2, 'BindEnergy':0.4555, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,206.993,8.55357,1.822,0.769787,0.501442,0],
			'sig':[0.050112,3.55952,204.702,8047.53,209401,0.001191,235.652,37602.8,418222,1187200,0]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.0603, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,27.4022,1.13234,0.2412,0.101906,0.066382,0],
			'sig':[0.199401,5.07217,100.854,1388.92,13522.4,4.71482,10629.3,147303,361211,393500,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.0346, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,15.7233,0.649733,0.1384,0.058473,0.03809,0],
			'sig':[0.004219,0.254281,13.1719,462.252,10030.3,1.74593,28436.2,360343,275575,1358420,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.0346, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,15.7233,0.649733,0.1384,0.058473,0.03809,0],
			'sig':[0.006784,0.454848,24.6371,886.507,19570.9,3.21036,55870.5,732971,575839,2673430,0]}] },
			'V':{'NSHELLS':8, 'ETERM':-0.084,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':5.4651, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,116.502,23.6825,10.9302,7.10459,5.73409,5.47057],
			'sig':[19.8593,557.294,12524.9,0,0,6.15257,793.151,7166.37,22744.7,39397.2,45205.3]},
			{'Shell':'2S1/2', 'Func':2, 'BindEnergy':0.6282, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,285.473,11.7966,2.5128,1.06165,0.691561,0],
			'sig':[1.69736,43.981,873.232,11541.9,95371.7,0.033135,418.87,16851.1,86395.5,165305,0]},
			{'Shell':'2P1/2', 'Func':2, 'BindEnergy':0.5205, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,236.531,9.77416,2.082,0.879636,0.572998,0],
			'sig':[0.042749,2.65845,142.065,5268.32,129183,0.000721,102.273,16152.1,180568,515993,0]},
			{'Shell':'2P3/2', 'Func':2, 'BindEnergy':0.5129, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,233.078,9.63145,2.0516,0.866792,0.564631,0],
			'sig':[0.067928,4.73336,265.038,10073.7,251757,0.001,200.471,32481.7,366493,1054870,0]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.0665, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,30.2196,1.24876,0.266,0.112384,0.073207,0],
			'sig':[0.248242,6.2066,120.278,1608.43,15290.3,4.3891,9963.04,138626,342481,385243,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.0378, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,17.1775,0.709824,0.1512,0.063881,0.041612,0],
			'sig':[0.005895,0.348193,17.4781,587.836,12128.7,1.71744,27477.4,344221,266125,1052710,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.0378, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,17.1775,0.709824,0.1512,0.063881,0.041612,0],
			'sig':[0.009414,0.619589,32.5734,1124.9,23648.6,3.13178,53901.5,701182,560652,2076640,0]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.0022, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,0.999748,0.041313,0.0088,0.003718,0.002422,0],
			'sig':[8e-06,0.001303,0.193255,20.0691,1380.06,1381.32,5239240,9182670,1.04128e+07,1.07105e+07,0]}] },
			'Cr':{'NSHELLS':9, 'ETERM':-0.093,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':5.9892, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,127.674,25.9536,11.9784,7.78592,6.28398,5.99519],
			'sig':[23.8584,659.702,14486.9,0,0,5.58467,716.949,6486.02,20613.4,35712.6,40917]},
			{'Shell':'2S1/2', 'Func':2, 'BindEnergy':0.6946, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,315.648,13.0435,2.7784,1.17386,0.764658,0],
			'sig':[2.06218,52.4386,1014.19,12981,102526,0.030258,375.974,15277.2,79048.1,151559,0]},
			{'Shell':'2P1/2', 'Func':2, 'BindEnergy':0.5837, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,265.251,10.961,2.3348,0.986443,0.642572,0],
			'sig':[0.057447,3.50119,182.162,6545.92,154517,0.000645,87.9408,14092.8,160078,468846,0]},
			{'Shell':'2P3/2', 'Func':2, 'BindEnergy':0.5745, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,261.07,10.7882,2.298,0.970895,0.632444,0],
			'sig':[0.090777,6.20592,338.715,12490.8,301108,0.000881,171.92,28343.9,325226,960945,0]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.0741, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,33.6733,1.39148,0.2964,0.125228,0.081574,0],
			'sig':[0.302707,7.43204,140.45,1828.28,17014.7,3.90113,9012.98,126690,309776,321822,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.0425, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,19.3133,0.798082,0.17,0.071824,0.046787,0],
			'sig':[0.007974,0.460968,22.4342,725.294,14298.7,1.47913,24397,310076,223924,1302580,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.0425, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,19.3133,0.798082,0.17,0.071824,0.046787,0],
			'sig':[0.012638,0.815584,41.6369,1384.22,27850.7,2.66807,47729,632149,472556,2572400,0]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.0023, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1.04519,0.04319,0.0092,0.003887,0.002532,0],
			'sig':[1.6e-05,0.00249,0.352081,35.3094,2332.49,1990.5,5731100,1.11038e+07,1.59004e+07,1.7579e+07,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.0023, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1.04519,0.04319,0.0092,0.003887,0.002532,0],
			'sig':[2e-06,0.000472,0.077981,8.36031,565.273,482.099,1422490,2800120,4079130,4554580,0]}] },
			'Mn':{'NSHELLS':9, 'ETERM':-0.102,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':6.539, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,139.394,28.3361,13.078,8.50066,6.86084,6.54554],
			'sig':[28.4209,774.183,16600.4,0,0,5.09475,650.5,5888.91,18730.2,32452.1,37298.3]},
			{'Shell':'2S1/2', 'Func':2, 'BindEnergy':0.769, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,349.457,14.4406,3.076,1.2996,0.846562,0],
			'sig':[2.47826,61.8828,1166.32,14460,109372,0.027375,333.641,13715.9,71665.8,139515,0]},
			{'Shell':'2P1/2', 'Func':2, 'BindEnergy':0.6514, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,296.016,12.2323,2.6056,1.10085,0.7171,0],
			'sig':[0.076023,4.54018,229.839,7990.76,180338,0.00058,75.9,12276.9,140811,412272,0]},
			{'Shell':'2P3/2', 'Func':2, 'BindEnergy':0.6403, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,290.972,12.0238,2.5612,1.0821,0.704881,0],
			'sig':[0.119361,8.00909,425.921,15215.7,351553,0.000786,148.009,24697,286420,845586,0]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.0839, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,38.1267,1.57551,0.3356,0.14179,0.092362,0],
			'sig':[0.369769,8.92679,164.651,2087.09,18974.7,3.25346,7935.61,114449,292233,339665,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.0486, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,22.0853,0.912631,0.1944,0.082133,0.053502,0],
			'sig':[0.010851,0.614777,29.0171,900.749,16910.5,1.21344,20973.2,287629,238536,650342,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.0486, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,22.0853,0.912631,0.1944,0.082133,0.053502,0],
			'sig':[0.017044,1.08166,53.6816,1716.15,32937.6,2.16277,40929.8,586109,510701,1289950,0]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.00726159, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,3.29989,0.136361,0.029046,0.012272,0.007994,0],
			'sig':[2.8e-05,0.004537,0.637379,61.796,3924.17,42.0985,1352010,6780920,5107830,3621650,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.00714378, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,3.24635,0.134149,0.028575,0.012073,0.007864,0],
			'sig':[4e-06,0.000859,0.141584,14.6815,954.535,10.6564,346167,1705720,1301680,926459,0]}] },
			'Fe':{'NSHELLS':9, 'ETERM':-0.113,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':7.112, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,151.609,30.8192,14.224,9.24555,7.46205,7.11911],
			'sig':[33.5967,901.827,18909.1,0,0,4.64799,593.258,5374.18,17106.8,29643.8,34122.9]},
			{'Shell':'2S1/2', 'Func':2, 'BindEnergy':0.8461, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,384.494,15.8884,3.3844,1.42989,0.931438,0],
			'sig':[2.95298,72.4341,1331.5,16011.6,115667,0.025147,299.204,12430,65528.4,128504,0]},
			{'Shell':'2P1/2', 'Func':2, 'BindEnergy':0.7211, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,327.69,13.5411,2.8844,1.21865,0.79383,0],
			'sig':[0.099439,5.81886,286.808,9667.26,209152,0.000534,66.8126,10892.3,126080,372604,0]},
			{'Shell':'2P3/2', 'Func':2, 'BindEnergy':0.7081, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,321.782,13.297,2.8324,1.19668,0.779519,0],
			'sig':[0.155009,10.2135,529.72,18373.7,407789,0.00072,129.786,21899.7,256621,765136,0]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.0929, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,42.2166,1.74451,0.3716,0.156999,0.10227,0],
			'sig':[0.443231,10.5244,189.635,2345,20846.9,2.90282,7199.49,105066,271252,318037,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.054, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,24.5393,1.01403,0.216,0.091259,0.059446,0],
			'sig':[0.01434,0.796495,36.4943,1089.9,19528.9,1.07615,18903.8,265301,225421,544294,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.054, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,24.5393,1.01403,0.216,0.091259,0.059446,0],
			'sig':[0.022411,1.39497,67.2663,2072.01,38024.9,1.89622,36796,540919,485733,1083630,0]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.0036, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1.63595,0.067602,0.0144,0.006084,0.003963,0],
			'sig':[4.4e-05,0.006916,0.943885,88.1911,5344.89,904.588,4360850,6479450,6033490,5995080,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.0036, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1.63595,0.067602,0.0144,0.006084,0.003963,0],
			'sig':[1.2e-05,0.002617,0.418636,41.8461,2598.33,436.013,2171090,3276080,3056090,3007960,0]}] },
			'Co':{'NSHELLS':9, 'ETERM':-0.123,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':7.7089, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,164.334,33.4058,15.4178,10.0215,8.08832,7.71661],
			'sig':[39.4313,1043.13,21369.3,0,0,4.28147,543.329,4923.98,15684,27185,31321.7]},
			{'Shell':'2S1/2', 'Func':2, 'BindEnergy':0.9256, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,420.621,17.3813,3.7024,1.56425,1.01896,0],
			'sig':[3.4921,84.1282,1508.71,17605.8,121267,0.023473,270.817,11345.9,60245.5,118856,0]},
			{'Shell':'2P1/2', 'Func':2, 'BindEnergy':0.7936, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,360.636,14.9025,3.1744,1.34117,0.873643,0],
			'sig':[0.128448,7.37003,353.904,11571.7,239974,0.000496,59.511,9754.96,113755,338722,0]},
			{'Shell':'2P3/2', 'Func':2, 'BindEnergy':0.7786, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,353.82,14.6209,3.1144,1.31582,0.85713,0],
			'sig':[0.199024,12.8762,651.492,21956.6,468721,0.000673,115.055,19594.4,231615,696498,0]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.1007, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,45.7612,1.89099,0.4028,0.170181,0.110857,0],
			'sig':[0.52708,12.2973,216.458,2613.66,22692.3,2.735,6767.11,98785.2,255470,301436,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.0595, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,27.0386,1.11732,0.238,0.100554,0.065501,0],
			'sig':[0.018688,1.01761,45.2824,1302.38,22269.2,0.973131,17233.9,245676,212414,467092,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.0595, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,27.0386,1.11732,0.238,0.100554,0.065501,0],
			'sig':[0.028988,1.77266,83.1539,2470.61,43352.5,1.69354,33457.5,501270,460572,933397,0]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.0029, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1.31785,0.054457,0.0116,0.004901,0.003192,0],
			'sig':[6.6e-05,0.010247,1.36049,122.745,7140.05,2703.99,5272270,5839490,6107420,6859510,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.0029, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1.31785,0.054457,0.0116,0.004901,0.003192,0],
			'sig':[2.8e-05,0.005796,0.90328,87.2195,5200.96,1960.57,3948210,4443490,4623940,5131740,0]}] },
			'Ni':{'NSHELLS':9, 'ETERM':-0.135,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':8.3328, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,177.633,36.1094,16.6656,10.8326,8.74293,8.34113],
			'sig':[45.9693,1198.95,23975.1,0,0,3.95673,499.031,4524.92,14424.6,25003.7,28779.6]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':1.0081, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,21.4901,4.36851,2.0162,1.31052,1.05772,1.00911],
			'sig':[4.09878,97.0019,1697.91,19234.2,0,175.453,8759.1,41247.2,85691,115743,125380]},
			{'Shell':'2P1/2', 'Func':2, 'BindEnergy':0.8719, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,396.218,16.3729,3.4876,1.4735,0.95984,0],
			'sig':[0.164238,9.24036,432.608,13745.7,277654,0.00046,52.9346,8730.52,102717,308361,0]},
			{'Shell':'2P3/2', 'Func':2, 'BindEnergy':0.8547, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,388.402,16.0499,3.4188,1.44443,0.940905,0],
			'sig':[0.252629,16.0623,793.753,26041.1,541307,0.000634,101.765,17515,209194,634733,0]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.1118, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,50.8054,2.09943,0.4472,0.18894,0.123076,0],
			'sig':[0.620444,14.2437,245.278,2896.93,24583.4,2.3225,6039.98,89677.1,235189,278220,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.0681, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,30.9467,1.27881,0.2724,0.115088,0.074969,0],
			'sig':[0.024099,1.28517,55.5597,1541.97,25191.4,0.763313,14306.6,218936,199738,384962,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.0681, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,30.9467,1.27881,0.2724,0.115088,0.074969,0],
			'sig':[0.0371,2.22666,101.645,2918.95,49043.5,1.30891,27669.1,446311,435479,771988,0]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.0036, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1.63595,0.067602,0.0144,0.006084,0.003963,0],
			'sig':[9.7e-05,0.014839,1.91603,167.095,9355.45,1645.67,4322540,4872570,4804620,5332220,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.0036, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1.63595,0.067602,0.0144,0.006084,0.003963,0],
			'sig':[5.4e-05,0.011158,1.69258,158.038,9076.38,1582.1,4310800,4948050,4847300,5294120,0]}] },
			'Cu':{'NSHELLS':9, 'ETERM':-0.146,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':8.9789, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,191.407,38.9092,17.9578,11.6725,9.42083,8.98788],
			'sig':[53.2752,1370.02,0,0,0,3.67558,460.388,4176.02,13321.4,23094.6,26531.4]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':1.0961, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,23.366,4.74985,2.1922,1.42492,1.15005,1.0972],
			'sig':[4.777,111.155,1901.58,20946.1,0,159.816,8044.52,38107.2,79578.4,107952,98264.7]},
			{'Shell':'2P1/2', 'Func':2, 'BindEnergy':0.951, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,432.164,17.8583,3.804,1.60717,1.04692,0],
			'sig':[0.207877,11.4774,524.465,16219.5,335328,0.000435,47.9886,7946.92,94237.9,285755,0]},
			{'Shell':'2P3/2', 'Func':2, 'BindEnergy':0.9311, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,423.12,17.4846,3.7244,1.57354,1.02501,0],
			'sig':[0.317747,19.8556,959.083,30679.8,642350,0.000614,91.8376,15938,192159,590128,0]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.1198, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,54.4408,2.24965,0.4792,0.20246,0.131883,0],
			'sig':[0.722816,16.2981,274.494,3175.11,26342.5,2.21426,5730.03,84846.8,216483,234566,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.0736, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,33.4461,1.38209,0.2944,0.124383,0.081023,0],
			'sig':[0.030504,1.59164,66.8568,1792.96,27991.2,0.722356,13405.5,202316,164978,484288,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.0736, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,33.4461,1.38209,0.2944,0.124383,0.081023,0],
			'sig':[0.046487,2.73926,121.781,3385.16,54478.8,1.22389,25846.1,413025,362459,968524,0]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.0016, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,0.727089,0.030046,0.0064,0.002704,0.001761,0],
			'sig':[0.000134,0.019556,2.42353,204.524,11062.7,31380.8,4706220,6409200,8098560,9343090,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.0016, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,0.727089,0.030046,0.0064,0.002704,0.001761,0],
			'sig':[0.000112,0.021889,3.18954,288.272,16006.7,45622.2,7098640,9932950,1.25758e+07,1.43644e+07,0]}] },
			'Zn':{'NSHELLS':9, 'ETERM':-0.159,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':9.6586, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,205.896,41.8546,19.3172,12.5561,10.134,9.66826],
			'sig':[61.3851,1556.51,0,0,0,3.41738,424.862,3855.02,12305.7,21342.2,24597.9]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':1.1936, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,25.4444,5.17235,2.3872,1.55167,1.25235,1.19479],
			'sig':[5.5323,126.53,2115.27,22648.3,0,144.204,7324.25,34937.4,73252.3,99417.8,107037]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':1.0428, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,22.2298,4.51888,2.0856,1.35563,1.09413,1.04384],
			'sig':[0.260641,14.1196,629.83,18958.2,0,27.0906,5521.71,53473.5,167395,300248,1333240]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':1.0197, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,21.7373,4.41877,2.0394,1.3256,1.06989,1.02072],
			'sig':[0.395632,24.304,1147.85,35802.5,0,51.2062,11047.6,108700,343778,622573,2775660]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.1359, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,61.7571,2.55199,0.5436,0.229669,0.149607,0],
			'sig':[0.843118,18.7137,308.697,3499.22,28351.6,1.81062,4876.26,74630.9,200414,237135,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.0866, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,39.3537,1.62621,0.3464,0.146353,0.095335,0],
			'sig':[0.038758,1.98363,81.0585,2100.58,31268.1,0.500795,10337.1,176976,176503,277111,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.0866, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,39.3537,1.62621,0.3464,0.146353,0.095335,0],
			'sig':[0.058645,3.39699,147.176,3960.26,60918.1,0.83181,19836.2,360243,388555,559753,0]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.0081, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,3.68089,0.152105,0.0324,0.013689,0.008917,0],
			'sig':[0.000197,0.029217,3.58538,293.222,15270.9,132.655,1802450,3597670,2548660,2326430,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.0081, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,3.68089,0.152105,0.0324,0.013689,0.008917,0],
			'sig':[0.000164,0.032747,4.72995,414.447,22173.5,185.929,2675330,5466530,3880210,3443700,0]}] },
			'Ga':{'NSHELLS':9, 'ETERM':-0.172,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':10.3671, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,220.999,44.9249,20.7342,13.4772,10.8774,10.3775],
			'sig':[70.3515,1759.01,0,0,0,3.18605,392.892,3565.46,11387.9,19762.4,22863.1]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':1.2977, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,27.6636,5.62346,2.5954,1.687,1.36157,1.299],
			'sig':[6.3688,143.187,2339.8,24352.5,0,130.088,6664.98,32003,67459.7,93002.2,97879.9]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':1.1423, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,24.3508,4.95005,2.2846,1.48498,1.19852,1.14344],
			'sig':[0.32396,17.223,750.23,21983.4,0,23.8706,4887.52,47695.4,150168,264293,1161610]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':1.1154, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,23.7774,4.83348,2.2308,1.45001,1.1703,1.11652],
			'sig':[0.488046,29.4899,1362.55,41448.9,0,44.8493,9771.77,97009.1,308733,547965,2423530]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.1581, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,71.8455,2.96887,0.6324,0.267186,0.174046,0],
			'sig':[0.980048,21.4168,346.233,3849.91,30489.5,1.32788,3933.51,63336.6,180888,223852,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.1068, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,48.5332,2.00553,0.4272,0.18049,0.117572,0],
			'sig':[0.048897,2.45786,97.8323,2453.61,34869.2,0.302032,7056.1,145256,194212,153909,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.1029, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,46.7609,1.9323,0.4116,0.173899,0.113279,0],
			'sig':[0.073582,4.18987,176.937,4610.37,67755.8,0.55634,14740.5,307470,427068,334535,0]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.0174, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,7.90709,0.326744,0.0696,0.029406,0.019155,0],
			'sig':[0.000286,0.042668,5.15594,408.521,20417.8,8.49055,496642,3697580,1791700,1466860,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.0174, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,7.90709,0.326744,0.0696,0.029406,0.019155,0],
			'sig':[0.000236,0.047747,6.80613,578.011,29699.8,11.316,733049,5574050,2732380,2190760,0]}] },
			'Ge':{'NSHELLS':9, 'ETERM':-0.186,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':11.1031, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,236.689,48.1142,22.2062,14.434,11.6496,11.1142],
			'sig':[80.2246,1978.03,0,0,0,2.97958,364.208,3305.44,10563.3,18339.8,21252.5]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':1.4143, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,30.1492,6.12874,2.8286,1.83858,1.48391,1.41571],
			'sig':[7.28965,161.232,2578.18,26116.6,0,116.148,6021.06,29166.1,61864.9,85900.5,91946.8]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':1.2478, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,26.5998,5.40722,2.4956,1.62213,1.30922,1.24905],
			'sig':[0.399252,20.8421,887.159,25319,0,21.1209,4340.14,42661.2,135140,236204,1025460]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':1.2167, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,25.9369,5.27246,2.4334,1.5817,1.27658,1.21792],
			'sig':[0.597487,35.5078,1605.67,47667.3,0,39.4249,8668.75,86800.5,278111,490046,2151650]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.18, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,81.7975,3.38011,0.72,0.304197,0.198155,0],
			'sig':[1.13551,24.4314,387.218,4224.91,32690.7,1.06691,3305.14,55324.2,165297,210960,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.1279, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,58.1217,2.40176,0.5116,0.216149,0.1408,0],
			'sig':[0.061461,3.03055,117.449,2851.64,38661,0.194859,5125.18,121457,203937,119521,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.1208, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,54.8952,2.26843,0.4832,0.20415,0.132984,0],
			'sig':[0.091695,5.13813,211.667,5344.66,75049.7,0.374449,11211.9,263859,451812,274453,0]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.0287, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,13.0422,0.53894,0.1148,0.048503,0.031595,0],
			'sig':[0.000411,0.060921,7.22077,554.85,26606.2,1.4095,170373,2955300,1788000,925162,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.0287, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,13.0422,0.53894,0.1148,0.048503,0.031595,0],
			'sig':[0.000338,0.068171,9.52997,785.182,38736,1.78751,250344,4433120,2723440,1394700,0]}] },
			'As':{'NSHELLS':9, 'ETERM':-0.2,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':11.8667, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,252.967,51.4232,23.7334,15.4266,12.4508,11.8786],
			'sig':[91.059,2214.21,0,0,0,2.77999,338.074,3071.3,9819.92,17059.8,19765.8]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':1.5265, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,32.541,6.61494,3.053,1.98444,1.60163,1.52803],
			'sig':[8.30234,180.56,2823.69,27807.4,0,106.029,5528.85,26914.7,57309.3,79884,86638.8]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':1.3586, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,28.9618,5.88737,2.7172,1.76617,1.42547,1.35996],
			'sig':[0.488622,25.0426,1041.92,28968.4,0,18.8089,3873.25,38317.7,122052,212554,910311]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':1.3231, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,28.205,5.73353,2.6462,1.72002,1.38822,1.32442],
			'sig':[0.725964,42.4438,1879.38,54474.2,0,34.8414,7723.31,77956.7,251347,441192,1911490]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.2035, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,92.4767,3.82141,0.814,0.343912,0.224025,0],
			'sig':[1.31027,27.7612,431.583,4623.31,34990.6,0.875532,2808.81,48673.5,152044,200913,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.1464, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,66.5287,2.74916,0.5856,0.247414,0.161166,0],
			'sig':[0.07672,3.71009,139.957,3287.16,42463.3,0.146437,4137.73,106420,207359,121933,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.1405, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,63.8475,2.63837,0.562,0.237443,0.154671,0],
			'sig':[0.113692,6.2629,251.659,6162.21,82752.8,0.268082,8669.27,226514,457978,282961,0]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.0412, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,18.7225,0.773671,0.1648,0.069627,0.045355,0],
			'sig':[0.000581,0.08526,9.88842,737.481,33899,0.40828,74780.5,2276190,1982260,636077,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.0412, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,18.7225,0.773671,0.1648,0.069627,0.045355,0],
			'sig':[0.000477,0.095275,13.0436,1043.5,49382.6,0.488065,109408,3403490,3013130,961700,0]}] },
			'Se':{'NSHELLS':9, 'ETERM':-0.215,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':12.6578, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,269.831,54.8514,25.3156,16.4551,13.2808,12.6705],
			'sig':[102.904,2467.75,0,0,0,2.61309,314.814,2859.96,9148.33,15902.4,18405.3]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':1.6539, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,35.2568,7.16702,3.3078,2.15006,1.7353,1.65555],
			'sig':[9.41355,201.409,3084.02,29570.9,0,95.5265,5028.9,24670.2,52813.6,73890.2,80790.6]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':1.4762, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,31.4687,6.39697,2.9524,1.91905,1.54886,1.47768],
			'sig':[0.593882,29.8914,1216.39,32970.7,0,16.7941,3464.04,34490.5,110469,192158,806455]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':1.4358, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,30.6075,6.22191,2.8716,1.86653,1.50647,1.43724],
			'sig':[0.875946,50.3963,2186.66,61936.4,0,30.863,6894.74,70160.9,227645,399124,1695920]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.2315, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,105.201,4.3472,0.926,0.391231,0.254849,0],
			'sig':[1.50731,31.4317,479.497,5048.24,37444.2,0.671761,2349.34,42372.9,138260,189296,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.1682, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,76.4353,3.15853,0.6728,0.284255,0.185165,0],
			'sig':[0.095102,4.51131,165.747,3769.6,46480.4,0.111424,3291.01,92255.6,204267,134721,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.1619, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,73.5723,3.04022,0.6476,0.273608,0.178229,0],
			'sig':[0.139977,7.5812,297.262,7063.01,90829.4,0.190036,6817.17,195496,450909,315884,0]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.0567, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,25.7662,1.06474,0.2268,0.095822,0.062419,0],
			'sig':[0.000809,0.117164,13.2909,963.809,42543.8,0.137164,34927.3,1639090,2139140,459565,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.0567, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,25.7662,1.06474,0.2268,0.095822,0.062419,0],
			'sig':[0.000662,0.130726,17.5189,1363.39,62003.9,0.154018,50843.1,2443790,3244720,694652,0]}] },
			'Br':{'NSHELLS':9, 'ETERM':-0.231,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':13.4737, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,287.224,58.387,26.9474,17.5157,14.1369,13.4872],
			'sig':[115.802,2738.54,0,0,0,2.46436,293.933,2669.65,8542.26,14855.8,17168.5]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':1.782, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,37.9876,7.72213,3.564,2.31659,1.86971,1.78378],
			'sig':[10.6242,223.629,3352.69,31288.8,0,87.0762,4614.44,22768.4,48947.4,68661.3,75400.8]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':1.596, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,34.0225,6.91612,3.192,2.07479,1.67455,1.5976],
			'sig':[0.717057,35.4426,1410.52,37236.2,0,15.1906,3129.47,31291.9,100619,174957,717155]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':1.5499, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,33.0398,6.71635,3.0998,2.01486,1.62618,1.55145],
			'sig':[1.04939,59.4306,2526.9,69876.8,0,27.7122,6221.36,63677,207571,364118,1505880]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.2565, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,116.561,4.81666,1.026,0.433481,0.282371,0],
			'sig':[1.72406,35.4126,530.381,5485.79,39851.4,0.576584,2067.88,38239.4,128470,181361,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.1893, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,86.0237,3.55475,0.7572,0.319914,0.208393,0],
			'sig':[0.117057,5.44646,194.888,4290.67,50516.1,0.091259,2744.77,81830.7,199422,151312,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.1815, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,82.4792,3.40828,0.726,0.306732,0.199806,0],
			'sig':[0.171111,9.11056,348.548,8031.59,98925,0.153153,5720.56,174394,441952,357867,0]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.0701, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,31.8556,1.31637,0.2804,0.118468,0.07717,0],
			'sig':[0.001109,0.158324,17.5431,1235.59,52167.1,0.072766,21845.5,1291750,2164520,369368,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.069, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,31.3557,1.29571,0.276,0.116609,0.075959,0],
			'sig':[0.000903,0.176224,23.0946,1745.57,75881.3,0.084068,33285.6,1971110,3277090,564616,0]}] },
			'Kr':{'NSHELLS':9, 'ETERM':-0.247,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':14.3256, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,305.384,62.0786,28.6512,18.6232,15.0307,14.3399],
			'sig':[129.996,3029.05,0,0,0,2.32621,274.61,2494.08,7984.88,13894.3,16032.1]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':1.921, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,40.9507,8.32447,3.842,2.49729,2.01555,1.92292],
			'sig':[11.942,247.393,3634.13,33032.5,0,78.645,4222.16,20975.1,45307.5,63711.9,70149.7]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':1.7272, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,36.8194,7.48466,3.4544,2.24535,1.81221,1.72893],
			'sig':[0.860746,41.8031,1629.11,41976.5,0,13.6486,2812.36,28296.9,91485.9,159344,637128]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':1.6749, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,35.7045,7.25802,3.3498,2.17736,1.75734,1.67657],
			'sig':[1.25033,69.7209,2908.56,78711.8,0,24.6885,5580.73,57580.1,188882,332067,1340000]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.28833, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,131.026,5.41438,1.15332,0.487273,0.317411,0],
			'sig':[1.9637,39.7446,584.966,5951.28,42458.3,0.475202,1761.07,33711.1,117090,170235,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.2227, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,101.202,4.18195,0.8908,0.376359,0.245162,0],
			'sig':[0.143167,6.53822,228.273,4881.63,55085.3,0.061402,2028.23,67512.3,185535,159879,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.2138, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,97.1573,4.01482,0.8552,0.361318,0.235364,0],
			'sig':[0.208088,10.8913,407.198,9133.87,108258,0.098876,4190.49,143477,410401,378941,0]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.0889, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,40.3989,1.6694,0.3556,0.150239,0.097866,0],
			'sig':[0.001499,0.21086,22.8474,1567.29,63664.2,0.033608,12333.9,935435,2128650,295130,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.0889, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,40.3989,1.6694,0.3556,0.150239,0.097866,0],
			'sig':[0.001217,0.23433,30.0604,2215.64,92852.2,0.033555,17778.7,1389060,3219010,444753,0]}] },
			'Rb':{'NSHELLS':9, 'ETERM':-0.264,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':15.1997, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,324.018,65.8665,30.3994,19.7595,15.9478,15.2149],
			'sig':[145.151,3335.25,0,0,0,2.2037,257.035,2335.37,7478.15,13017,15004.7]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':2.0651, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,44.0225,8.94892,4.1302,2.68462,2.16674,2.06717],
			'sig':[13.3685,272.546,3922.28,34714.9,0,71.6624,3874.45,19358.7,41990.6,59185.3,64918.3]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':1.8639, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,39.7335,8.07704,3.7278,2.42306,1.95564,1.86576],
			'sig':[1.02673,49.0009,1869.27,46924.1,0,12.3343,2535.96,25624.3,83175.5,145148,169550]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':1.8044, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,38.4651,7.8192,3.6088,2.34571,1.89321,1.8062],
			'sig':[1.48078,81.2901,3325.67,87919.5,0,22.134,5025.32,52153.3,171870,302482,355350]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.3221, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,146.372,6.04853,1.2884,0.544344,0.354587,0],
			'sig':[2.2292,44.4258,642.403,6425.02,45004,0.379439,1512.92,29823.3,106568,166563,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.2474, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,112.426,4.64578,0.9896,0.418102,0.272353,0],
			'sig':[0.173849,7.78626,264.756,5475.89,59050.4,0.051995,1728.85,60143.7,179116,170479,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.2385, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,108.382,4.47865,0.954,0.403061,0.262555,0],
			'sig':[0.250937,12.9118,471.177,10247.4,116534,0.080014,3515.19,126855,395169,401145,0]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.1118, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,50.8054,2.09943,0.4472,0.18894,0.123076,0],
			'sig':[0.001996,0.276898,29.3405,1958.4,76366.9,0.015699,6946.48,651207,2144910,288034,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.1103, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,50.1237,2.07126,0.4412,0.186405,0.121425,0],
			'sig':[0.001618,0.307256,38.5445,2763.94,111083,0.015646,10406.1,990322,3254540,431920,0]}] },
			'Sr':{'NSHELLS':12, 'ETERM':-0.282,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':16.1046, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,343.308,69.7878,32.2092,20.9359,16.8973,16.1207],
			'sig':[161.514,3660.2,0,0,0,2.09155,241.109,2189.63,7012.84,12210.7,14059.6]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':2.2163, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,47.2457,9.60413,4.4326,2.88118,2.32538,2.21852],
			'sig':[14.9101,299.185,4219.24,36356.2,0,65.4292,3560.54,17888.5,38957.2,55047.2,60405.6]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':2.0068, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,42.7797,8.69628,4.0136,2.60883,2.10557,2.00881],
			'sig':[1.21865,57.1402,2133.74,52165.9,0,11.1423,2294.35,23263.1,75764.2,132248,150196]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':1.9396, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,41.3472,8.40508,3.8792,2.52147,2.03507,1.94154],
			'sig':[1.74423,94.2743,3783.11,97674.4,0,19.8181,4538.41,47343.8,156658,275883,315142]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.3575, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,162.459,6.71328,1.43,0.604169,0.393558,0],
			'sig':[2.51823,49.4546,703.054,6912.59,47542.8,0.320202,1313.71,26578,97467.2,153494,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.2798, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,127.15,5.2542,1.1192,0.472857,0.308021,0],
			'sig':[0.209908,9.22296,305.694,6123.25,63259.9,0.041409,1399.07,51847.1,167731,180221,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.2691, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,122.287,5.05327,1.0764,0.454774,0.296242,0],
			'sig':[0.300864,15.2228,542.592,11453,125274,0.062027,2845.77,109598,370478,422458,0]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.135, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,61.3482,2.53509,0.54,0.228148,0.148616,0],
			'sig':[0.002633,0.359632,37.2269,2414.14,90173.9,0.00888,4397.25,476698,2032990,424227,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.1331, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,60.4847,2.49941,0.5324,0.224937,0.146525,0],
			'sig':[0.002129,0.398271,48.8483,3404.98,131124,0.00841,6564.34,725246,3091870,635317,0]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.0377, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,17.132,0.707946,0.1508,0.063712,0.041502,0],
			'sig':[0.378551,7.14978,99.8567,995.346,7467.84,21.425,13344.4,124350,205973,104677,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.0199, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,9.04317,0.37369,0.0796,0.033631,0.021907,0],
			'sig':[0.025904,1.0726,34.124,668.743,7179.05,32.5393,33407.7,113940,2081550,1.57893e+07,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.0199, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,9.04317,0.37369,0.0796,0.033631,0.021907,0],
			'sig':[0.036948,1.76024,60.2213,1243.12,14006.3,57.3782,68820.8,243546,3774910,3.06771e+07,0]}] },
			'Y':{'NSHELLS':12, 'ETERM':-0.3,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':17.0384, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,363.214,73.8343,34.0768,22.1498,17.877,17.0554],
			'sig':[179.147,4003.61,0,0,0,1.98953,226.568,2056.58,6588.13,11473.5,13194.2]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':2.3725, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,50.5755,10.281,4.745,3.08423,2.48927,2.37487],
			'sig':[16.5723,327.37,4525.75,38015.5,0,60.0164,3284.6,16586.6,36256.3,51340.9,56210.5]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':2.1555, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,45.9496,9.34066,4.311,2.80214,2.26159,2.15766],
			'sig':[1.4394,66.3264,2426.01,57802.7,0,10.1674,2085.79,21221,69344.6,121139,138702]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':2.08, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,44.3402,9.01348,4.16,2.70399,2.18238,2.08208],
			'sig':[2.04443,108.828,4286.78,108219,0,17.9095,4117.66,43180,143478,252981,291438]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.3936, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,178.864,7.39118,1.5744,0.665177,0.433299,0],
			'sig':[2.83639,54.8694,767.066,7417.85,50142.6,0.276592,1157.78,23958.2,89794.3,144308,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.3124, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,141.964,5.86638,1.2496,0.527951,0.343909,0],
			'sig':[0.251976,10.8623,351.09,6813.45,67504.2,0.032961,1167.86,45512.6,156651,183206,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.3003, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,136.466,5.63916,1.2012,0.507502,0.330588,0],
			'sig':[0.358618,17.846,621.632,12742.9,134270,0.050004,2364.53,96150.6,346162,429719,0]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.1596, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,72.5271,2.99703,0.6384,0.269721,0.175697,0],
			'sig':[0.00344,0.462345,46.7641,2949.67,105897,0.005328,2960.23,360749,1858940,552809,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.1574, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,71.5274,2.95572,0.6296,0.266003,0.173275,0],
			'sig':[0.002773,0.510966,61.291,4158.11,153978,0.004748,4387.53,547964,2829980,828897,0]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.0454, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,20.6312,0.85254,0.1816,0.076725,0.049979,0],
			'sig':[0.45118,8.43212,116.127,1141.38,8498.56,15.9779,11141,112213,209914,150483,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.0256, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,11.6334,0.480727,0.1024,0.043264,0.028182,0],
			'sig':[0.03378,1.38149,42.9767,816.079,8485.08,19.2198,27772.7,103375,1032200,6357130,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.0256, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,11.6334,0.480727,0.1024,0.043264,0.028182,0],
			'sig':[0.047902,2.26003,75.7655,1518.7,16619,33.3942,56679.7,234335,1845420,1.22216e+07,0]}] },
			'Zr':{'NSHELLS':13, 'ETERM':-0.319,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':17.9976, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,383.662,77.9909,35.9952,23.3968,18.8834,18.0156],
			'sig':[198.085,4365.35,0,0,0,1.89753,213.37,1935.44,6200.75,10803.5,12404]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':2.5316, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,53.9671,10.9705,5.0632,3.29106,2.6562,2.53413],
			'sig':[18.3579,357.057,4839.55,39608.9,0,55.0787,3045.33,15444.5,33866.7,48042.5,52498.1]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':2.3067, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,49.1728,9.99587,4.6134,2.99869,2.42023,2.30901],
			'sig':[1.69196,76.6253,2745.35,63772.3,0,9.37019,1911.56,19491.3,63848.4,111592,128467]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':2.2223, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,47.3736,9.63013,4.4446,2.88898,2.33168,2.22452],
			'sig':[2.38462,125.03,4834.98,119323,0,16.342,3766.08,39653.8,132204,233354,270296]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.4303, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,195.542,8.08035,1.7212,0.7272,0.4737,0],
			'sig':[3.17947,60.6364,834.237,7938.18,52774.7,0.243396,1033.27,21803.2,83217.4,135922,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.3442, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,156.415,6.46353,1.3768,0.581692,0.378916,0],
			'sig':[0.301005,12.7232,400.983,7538.53,71666.1,0.028413,1006.95,40732.1,147046,182757,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.3305, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,150.189,6.20626,1.322,0.558539,0.363834,0],
			'sig':[0.425387,20.8068,708.235,14099.4,143236,0.040151,2032.82,86105.8,325501,429293,0]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.1824, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,82.8882,3.42518,0.7296,0.308253,0.200797,0],
			'sig':[0.004447,0.588056,58.1128,3562.13,122820,0.003797,2218.65,291803,1696030,631847,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.18, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,81.7975,3.38011,0.72,0.304197,0.198155,0],
			'sig':[0.00357,0.648276,76.0761,5019.27,178620,0.00321,3261.68,442122,2581910,947469,0]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.0513, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,23.3123,0.963332,0.2052,0.086696,0.056474,0],
			'sig':[0.529819,9.78068,132.754,1287.17,9516.61,13.6867,10142.8,105999,209340,171249,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.0287, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,13.0422,0.53894,0.1148,0.048503,0.031595,0],
			'sig':[0.04301,1.72927,52.4892,965.795,9737.62,16.6749,26720.5,106705,768987,4248020,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.0287, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,13.0422,0.53894,0.1148,0.048503,0.031595,0],
			'sig':[0.060573,2.81652,92.3254,1797.19,19125.4,28.6847,54410.8,245642,1375090,8130740,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.00402345, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1.82838,0.075554,0.016094,0.0068,0.004429,0],
			'sig':[0.000156,0.017516,1.57012,90.4215,2764.08,465.709,26196.9,1.11986e+07,1.34794e+07,1.27192e+07,0]}] },
			'Nb':{'NSHELLS':13, 'ETERM':-0.338,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':18.9856, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,404.723,82.2723,37.9712,24.6812,19.9201,19.0046],
			'sig':[218.421,4747.14,0,0,0,1.81406,201.295,1824.37,5845.46,10199,11666.8]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':2.6977, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,57.5079,11.6902,5.3954,3.50699,2.83048,2.7004],
			'sig':[20.2746,388.375,5163.63,41282.5,0,50.8884,2828.09,14406.4,31691.5,45017.4,49136.9]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':2.4647, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,52.5409,10.6805,4.9294,3.20409,2.58601,2.46716],
			'sig':[1.9803,88.1779,3097.13,70272.1,0,8.61603,1756.82,17960.6,58998.6,103245,118983]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':2.3705, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,50.5329,10.2723,4.741,3.08163,2.48717,2.37287],
			'sig':[2.76925,143.079,5436.61,131535,0,14.9522,3454.31,36536.4,122268,216200,250722]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.4684, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,212.855,8.79581,1.8736,0.791588,0.515643,0],
			'sig':[3.55403,66.8008,904.766,8477.39,55445.9,0.217098,928.644,19960.2,77480.9,127575,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.3784, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,171.957,7.10575,1.5136,0.63949,0.416566,0],
			'sig':[0.357288,14.8226,455.977,8313.55,75939.4,0.024614,870.915,36546.6,137495,179672,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.363, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,164.958,6.81656,1.452,0.613464,0.399612,0],
			'sig':[0.501356,24.1269,803.455,15553.3,152661,0.03377,1751.86,77277,305102,423001,0]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.2074, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,94.2489,3.89464,0.8296,0.350502,0.228318,0],
			'sig':[0.005694,0.741096,71.6301,4274.31,142226,0.002645,1681.38,238178,1534820,582568,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.2046, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,92.9765,3.84206,0.8184,0.345771,0.225236,0],
			'sig':[0.004561,0.815524,93.6538,6019.17,206829,0.002153,2458.73,360692,2338200,869593,0]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.0581, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,26.4024,1.09103,0.2324,0.098188,0.06396,0],
			'sig':[0.61275,11.1584,149.254,1429.06,10510.5,11.4717,9049.18,97834.3,196611,157352,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.0339, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,15.4052,0.636588,0.1356,0.05729,0.037319,0],
			'sig':[0.053333,2.10468,62.3245,1112.89,10910.9,11.9794,23103.1,102424,574272,3695230,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.0339, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,15.4052,0.636588,0.1356,0.05729,0.037319,0],
			'sig':[0.074476,3.40728,109.204,2067.71,21464.4,20.2748,46713,237588,1027880,7088900,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.0032, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1.45418,0.060091,0.0128,0.005408,0.003523,0],
			'sig':[0.000421,0.046035,4.00765,222.856,6501.55,2256.23,360910,2.13674e+07,2.76537e+07,2.90495e+07,0]}] },
			'Mo':{'NSHELLS':14, 'ETERM':-0.359,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':19.9995, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,426.337,86.666,39.999,25.9992,20.9839,20.0195],
			'sig':[240.097,5144.73,0,0,0,1.73783,190.097,1722.39,5518.71,9627.55,11005]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':2.8655, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,61.085,12.4174,5.731,3.72513,3.00654,2.86837],
			'sig':[22.3213,421.096,5490.91,42420.2,0,47.3239,2639.04,13488.5,29747.5,42304,46096.3]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':2.6251, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,55.9603,11.3756,5.2502,3.41261,2.7543,2.62773],
			'sig':[2.30739,101.004,3476.33,77040.2,0,8.02374,1624.74,16628.2,54710.8,95766.4,109727]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':2.5202, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,53.7241,10.9211,5.0404,3.27624,2.64424,2.52272],
			'sig':[3.20123,162.97,6082.3,144061,0,13.7183,3188.79,33827.1,113491,200843,231035]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.5046, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,229.306,9.47559,2.0184,0.852765,0.555494,0],
			'sig':[3.9583,73.3244,977.727,9017.91,57976.3,0.199403,851.258,18528.2,72779.8,121043,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.4097, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,186.18,7.69351,1.6388,0.692386,0.451022,0],
			'sig':[0.422186,17.176,515.355,9102.09,79867.8,0.022427,782.379,33536.2,130016,176863,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.3923, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,178.273,7.36677,1.5692,0.66298,0.431868,0],
			'sig':[0.588181,27.8265,905.91,17032.8,161458,0.030096,1572.46,71061.7,289480,417791,0]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.2303, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,104.655,4.32467,0.9212,0.389203,0.253528,0],
			'sig':[0.007225,0.925237,87.4036,5065.71,162128,0.002093,1372.98,203375,1406530,614488,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.227, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,103.156,4.2627,0.908,0.383626,0.249895,0],
			'sig':[0.005769,1.01593,114.13,7128.85,235719,0.001657,2001.52,308183,2145400,914660,0]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.0618, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,28.0838,1.16051,0.2472,0.104441,0.068033,0],
			'sig':[0.703809,12.6619,167.027,1579,11535.5,11.1805,8929.44,96923.2,196240,165728,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.0348, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,15.8142,0.653489,0.1392,0.058811,0.03831,0],
			'sig':[0.065677,2.54781,73.6351,1275.05,12151.5,13.2324,24509.7,107404,547930,3136450,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.0348, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,15.8142,0.653489,0.1392,0.058811,0.03831,0],
			'sig':[0.091011,4.10335,128.649,2367.61,23964.4,22.2596,49670.8,251517,985744,6027430,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.0018, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,0.817975,0.033801,0.0072,0.003042,0.001982,0],
			'sig':[0.000615,0.067146,5.73747,308.015,8571.79,14348.6,7814270,2.572e+07,3.33482e+07,3.68589e+07,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.0018, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,0.817975,0.033801,0.0072,0.003042,0.001982,0],
			'sig':[8e-05,0.012051,1.22095,70.6676,2032.78,3417.12,1867870,6514210,8738790,9799360,0]}] },
			'Tc':{'NSHELLS':14, 'ETERM':-0.38,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':21.044, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,448.603,91.1922,42.088,27.3571,22.0798,21.065],
			'sig':[263.218,5561.27,0,0,0,1.66741,179.844,1627.83,5215.59,9100.88,10391.3]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':3.0425, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,64.8581,13.1844,6.085,3.95523,3.19225,3.04554],
			'sig':[24.5052,455.364,5825.05,0,0,43.9736,2460.91,12623.2,27913.6,39756,43286.4]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':2.7932, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,59.5437,12.1041,5.5864,3.63114,2.93068,2.79599],
			'sig':[2.67747,115.234,3886.97,83721.4,0,7.4787,1503.18,15398.1,50740.6,88811.3,101944]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':2.6769, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,57.0645,11.6001,5.3538,3.47995,2.80865,2.67958],
			'sig':[3.68525,184.883,6779.14,157491,0,12.6492,2943.57,31316.2,105332,186493,215055]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.5476, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,248.846,10.2831,2.1904,0.925435,0.602831,0],
			'sig':[4.39064,80.225,1054.03,9577.98,60510.1,0.167935,766.106,16960.5,67560.5,114273,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.4449, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,202.176,8.35451,1.7796,0.751873,0.489773,0],
			'sig':[0.496396,19.8073,579.824,9923.72,83685,0.020203,694.726,30512,122120,171241,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.425, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,193.133,7.98082,1.7,0.718243,0.467866,0],
			'sig':[0.686616,31.9366,1016.76,18575.6,170209,0.026551,1396.54,64830,272704,405984,0]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.2564, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,116.516,4.81478,1.0256,0.433312,0.282261,0],
			'sig':[0.009093,1.14577,105.811,5955.5,183483,0.001629,1102.36,171081,1266380,811328,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.2529, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,114.926,4.74906,1.0116,0.427397,0.278408,0],
			'sig':[0.007237,1.25537,138.003,8377.7,266887,0.001249,1592.07,258446,1929500,1213100,0]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.0684, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,31.0831,1.28444,0.2736,0.115595,0.075299,0],
			'sig':[0.80747,14.333,186.407,1740.92,12638.6,9.87279,8206.64,91428.9,195055,189214,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.0389, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,17.6774,0.73048,0.1556,0.06574,0.042824,0],
			'sig':[0.080674,3.07626,86.7981,1458.62,13531.8,11.2235,22794.4,109566,395359,1882570,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.0389, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,17.6774,0.73048,0.1556,0.06574,0.042824,0],
			'sig':[0.111049,4.934,151.376,2710.18,26790.4,18.661,46080.8,257801,728720,3596760,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.00701158, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,3.18628,0.131666,0.028046,0.01185,0.007719,0],
			'sig':[0.000926,0.103054,8.74146,454.143,12115.6,370.902,161809,1.81668e+07,1.28347e+07,8273540,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.00672942, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,3.05806,0.126368,0.026918,0.011373,0.007408,0],
			'sig':[0.000121,0.018618,1.87551,105.119,2899.72,98.5036,38843.9,4626660,3323490,2198280,0]}] },
			'Ru':{'NSHELLS':14, 'ETERM':-0.401,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':22.1172, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,471.481,95.8428,44.2344,28.7522,23.2058,22.1393],
			'sig':[287.872,6000.27,0,0,0,1.59924,170.412,1540.85,4937.02,8611.95,9830.63]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':3.224, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,68.7272,13.9709,6.448,4.19118,3.38268,3.22722],
			'sig':[26.835,491.313,6168.33,0,0,41.0158,2302.53,11851.9,26274.7,37438.1,40693.2]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':2.9669, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,63.2465,12.8568,5.9338,3.85695,3.11293,2.96987],
			'sig':[3.09603,131.069,4337.21,97572.5,0,6.9994,1396.53,14326,47300.7,82868,93226.6]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':2.8379, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,60.4966,12.2978,5.6758,3.68925,2.97758,2.84074],
			'sig':[4.2271,209.091,7540.31,170757,0,11.7137,2729.48,29138.4,98301,174311,196049]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.585, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,265.842,10.9854,2.34,0.98864,0.644003,0],
			'sig':[4.85759,87.5168,1132.91,10143.5,62980.8,0.155832,712.179,15922,64010.1,108311,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.4828, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,219.399,9.06622,1.9312,0.815924,0.531495,0],
			'sig':[0.581027,22.7495,650.461,10807.7,87569.1,0.018236,617.007,27822.9,114441,165762,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.4606, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,209.311,8.64934,1.8424,0.778406,0.507056,0],
			'sig':[0.797202,36.4975,1138.06,20246.6,179560,0.023343,1236.63,59170.6,256475,394525,0]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.2836, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,128.877,5.32556,1.1344,0.479279,0.312204,0],
			'sig':[0.011367,1.40931,127.388,6982.28,208328,0.001303,903.104,146946,1154550,683887,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.2794, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,126.968,5.24669,1.1176,0.472181,0.30758,0],
			'sig':[0.009016,1.54062,165.916,9814.37,302963,0.000978,1300.55,222253,1762290,1013430,0]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.0749, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,34.0369,1.4065,0.2996,0.12658,0.082454,0],
			'sig':[0.910864,15.9583,204.765,1891.68,13675.8,8.82271,7577.25,85910.5,181338,162905,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.0431, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,19.586,0.809349,0.1724,0.072838,0.047447,0],
			'sig':[0.096565,3.61468,99.5735,1626.65,14724.6,9.53223,20959.4,105125,355984,1938330,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.0431, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,19.586,0.809349,0.1724,0.072838,0.047447,0],
			'sig':[0.131692,5.75846,172.905,3016.98,29205.1,15.6216,42190.3,248404,657352,3728870,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.002, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,0.908862,0.037557,0.008,0.00338,0.002202,0],
			'sig':[0.001168,0.126145,10.3602,519.234,13235.6,16849.3,9683040,1.89192e+07,2.11323e+07,2.24732e+07,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.002, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,0.908862,0.037557,0.008,0.00338,0.002202,0],
			'sig':[0.000456,0.067722,6.61126,357.741,9436.86,12039.8,6975330,1.45233e+07,1.65834e+07,1.75883e+07,0]}] },
			'Rh':{'NSHELLS':14, 'ETERM':-0.424,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':23.2199, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,494.987,100.621,46.4398,30.1857,24.3628,23.2431],
			'sig':[314.038,6447.44,0,0,0,1.53989,161.669,1460.09,4677.98,8160.65,9308.91]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':3.4119, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,72.7328,14.7851,6.8238,4.43545,3.57983,3.41531],
			'sig':[29.3085,528.739,6515.35,0,0,38.0844,2156.86,11137.7,24749.6,35295.7,38326.3]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':3.1461, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,67.0666,13.6333,6.2922,4.08991,3.30095,3.14925],
			'sig':[3.56632,148.508,4819.84,0,0,6.57411,1300.57,13350.1,44139.1,77349.2,85781.7]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':3.0038, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,64.0331,13.0167,6.0076,3.90492,3.15164,3.0068],
			'sig':[4.82996,235.563,8353.98,0,0,10.8769,2535.84,27146.9,91811.1,162952,181020]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.6271, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,284.974,11.7759,2.5084,1.05979,0.69035,0],
			'sig':[5.35818,95.2024,1214.72,10722.5,65303.4,0.143014,655.645,14831.9,60216.8,102613,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.521, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,236.758,9.78355,2.084,0.880481,0.573548,0],
			'sig':[0.67643,26.0001,726.102,11706.2,91176.9,0.01583,554.689,25534.1,107596,159663,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.4962, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,225.489,9.31785,1.9848,0.83857,0.546247,0],
			'sig':[0.922077,41.5248,1267.58,21949.5,188446,0.020986,1109.5,54388.3,241933,381713,0]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.3117, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,141.646,5.85323,1.2468,0.526768,0.343138,0],
			'sig':[0.014107,1.7206,152.195,8114.73,234224,0.001021,751.62,127058,1049450,715685,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.307, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,139.51,5.76497,1.228,0.518825,0.337964,0],
			'sig':[0.011141,1.87617,197.973,11399.4,340687,0.000753,1075.53,191978,1602120,1057860,0]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.081, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,36.8089,1.52105,0.324,0.136889,0.08917,0],
			'sig':[1.02415,17.7333,224.654,2052.98,14765.4,8.12298,7134.24,81918.4,174729,160097,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.0479, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,21.7672,0.899486,0.1916,0.08095,0.052731,0],
			'sig':[0.115625,4.24856,114.261,1814.73,16040.8,8.03506,19158.6,102680,292163,1562780,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.0479, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,21.7672,0.899486,0.1916,0.08095,0.052731,0],
			'sig':[0.156398,6.73033,197.786,3364.05,31917.5,12.9801,38417,243174,550758,3011170,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.0025, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1.13608,0.046946,0.01,0.004225,0.002752,0],
			'sig':[0.001554,0.166203,13.368,647.824,15844.1,11416.8,6163890,1.55928e+07,1.58303e+07,1.62228e+07,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.0025, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1.13608,0.046946,0.01,0.004225,0.002752,0],
			'sig':[0.000806,0.11871,11.3626,594.924,15067.2,10823,5871010,1.59413e+07,1.64741e+07,1.66816e+07,0]}] },
			'Pd':{'NSHELLS':14, 'ETERM':-0.447,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':24.3503, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,519.085,105.52,48.7006,31.6552,25.5488,24.3747],
			'sig':[341.821,6929.89,0,0,0,1.48557,153.624,1385.51,4438.49,7752.14,8818.31]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':3.6043, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,76.8342,15.6189,7.2086,4.68557,3.7817,3.6079],
			'sig':[31.9331,567.749,6867.77,0,0,35.6739,2025.89,10492.4,23366.1,33331.4,36074.6]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':3.3303, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,70.9933,14.4315,6.6606,4.32937,3.49421,3.33363],
			'sig':[4.09528,167.752,5341.66,0,0,6.16705,1215.63,12484.5,41325.7,72403,74949.1]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':3.1733, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,67.6464,13.7512,6.3466,4.12527,3.32949,3.17647],
			'sig':[5.50118,264.561,9230.24,0,0,10.1477,2365.25,25387.8,86059.5,152841,156775]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.6699, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,304.423,12.5797,2.6796,1.13212,0.737466,0],
			'sig':[5.89325,103.292,1299.57,11316.5,67682.6,0.132441,607.18,13884.3,56833.7,97394.3,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.5591, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,254.072,10.499,2.2364,0.944869,0.615491,0],
			'sig':[0.78481,29.6038,807.573,12640.7,94440.4,0.014618,505.421,23651.6,101696,154143,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.5315, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,241.53,9.98073,2.126,0.898226,0.585107,0],
			'sig':[1.06201,47.0543,1406.77,23728.9,197114,0.01815,1009.28,50481.6,229668,370053,0]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.34, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,154.506,6.38466,1.36,0.574594,0.374293,0],
			'sig':[0.017374,2.08656,180.793,9387.09,262496,0.000852,640.334,111922,965542,597959,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.3347, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,152.098,6.28513,1.3388,0.565637,0.368458,0],
			'sig':[0.013687,2.27085,234.874,13178.6,381904,0.000622,911.242,169022,1475320,876122,0]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.0864, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,39.2628,1.62245,0.3456,0.146015,0.095114,0],
			'sig':[1.14679,19.5808,244.713,2213.71,15841.4,7.48869,6840.04,78827.9,166242,137746,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.0511, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,23.2214,0.959577,0.2044,0.086358,0.056254,0],
			'sig':[0.136756,4.93307,129.563,2002.12,17290.7,7.61037,18528.8,100142,282794,1683920,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.0511, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,23.2214,0.959577,0.2044,0.086358,0.056254,0],
			'sig':[0.183273,7.76307,223.362,3706.4,34494.4,12.1436,37082,238696,533498,3273070,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.00544663, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,2.47512,0.102279,0.021786,0.009205,0.005996,0],
			'sig':[0.001932,0.200469,15.6424,734.318,17329.5,1353.56,96768,1.12832e+07,9874700,7802600,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.00501841, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,2.28052,0.094238,0.020074,0.008481,0.005525,0],
			'sig':[0.001496,0.21252,19.7039,999.83,24445.4,2400.72,231654,1.70246e+07,1.62584e+07,1.3481e+07,0]}] },
			'Ag':{'NSHELLS':14, 'ETERM':-0.471,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':25.514, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,543.892,110.563,51.028,33.168,26.7698,25.5395],
			'sig':[371.174,7404.36,0,0,0,1.43481,146.068,1315.53,4213.75,7359.55,8367.53]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':3.8058, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,81.1297,16.4921,7.6116,4.94751,3.99312,3.80961],
			'sig':[34.7085,608.203,7222.56,0,0,33.4021,1901.81,9878.92,22047.5,31481.5,34135]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':3.5237, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,75.1161,15.2696,7.0474,4.58079,3.69713,3.52722],
			'sig':[4.68518,188.83,5899.14,0,0,5.80971,1135.12,11660.7,38641.9,67712.8,72616.8]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':3.3511, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,71.4367,14.5217,6.7022,4.35641,3.51604,3.35445],
			'sig':[6.24195,296.091,10163.8,0,0,9.39601,2202.82,23704.6,80536.9,143151,152821]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.7175, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,326.054,13.4735,2.87,1.21256,0.789867,0],
			'sig':[6.46324,111.763,1386.7,11912.9,69822,0.12166,557.752,12908,53366.1,92075.2,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.6024, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,273.749,11.3121,2.4096,1.01805,0.663158,0],
			'sig':[0.906831,33.5687,894.525,13595.2,97441.9,0.013284,453.93,21669.6,95233.3,146966,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.5714, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,259.662,10.73,2.2856,0.965656,0.629032,0],
			'sig':[1.21801,53.0989,1554.82,25551.3,205387,0.016239,905.297,46351.4,215771,354874,0]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.3728, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,169.412,7.00059,1.4912,0.630026,0.410401,0],
			'sig':[0.021278,2.5145,213.351,10782.4,292004,0.000691,531.765,96376.8,867885,780111,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.3667, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,166.64,6.88604,1.4668,0.619717,0.403686,0],
			'sig':[0.016689,2.7297,276.807,15126.3,424862,0.000502,752.546,145540,1326620,1146640,0]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.0952, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,43.2618,1.7877,0.3808,0.160886,0.104802,0],
			'sig':[1.27912,21.5915,266.563,2387.34,16980.2,6.52393,6185.69,73095.5,159422,149676,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.0626, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,28.4474,1.17553,0.2504,0.105793,0.068914,0],
			'sig':[0.161788,5.73901,147.378,2218.77,18746.2,4.71469,14223.8,92560.6,182654,980772,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.0559, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,25.4027,1.04971,0.2236,0.09447,0.061538,0],
			'sig':[0.215594,8.98779,253.145,4098.16,37397.3,10.5392,34347.1,236129,444850,2185660,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.0033, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1.49962,0.061969,0.0132,0.005577,0.003633,0],
			'sig':[0.002605,0.273271,21.0784,955.893,21619,7536.34,3400270,1.16352e+07,1.06178e+07,1.08824e+07,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.0033, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1.49962,0.061969,0.0132,0.005577,0.003633,0],
			'sig':[0.002015,0.291225,26.798,1314.86,30838.4,10630.4,4795130,1.78539e+07,1.6372e+07,1.62604e+07,0]}] },
			'Cd':{'NSHELLS':14, 'ETERM':-0.496,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':26.7112, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,569.413,115.75,53.4224,34.7244,28.0259,26.7379],
			'sig':[402.193,0,0,0,0,1.38744,139.002,1250.04,4003.47,6993.01,7938.74]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':4.018, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,85.6532,17.4116,8.036,5.22337,4.21576,4.02202],
			'sig':[37.6538,650.31,7583.03,0,0,31.2528,1783.92,9296.46,20793.3,29788.5,32232.9]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':3.727, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,79.4499,16.1506,7.454,4.84508,3.91044,3.73073],
			'sig':[5.34351,211.952,6498.78,0,0,5.47051,1059.4,10888.5,36130.9,63333.4,70256.5]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':3.5375, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,75.4102,15.3294,7.075,4.59873,3.71161,3.54104],
			'sig':[7.06005,330.427,11165.4,0,0,8.73649,2050.07,22124.6,75358.8,134078,148945]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.7702, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,350.003,14.4631,3.0808,1.30162,0.847883,0],
			'sig':[7.07009,120.648,1476.84,12524.3,71821.1,0.111077,508.901,11937,49828.3,87278.6,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.6507, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,295.698,12.2191,2.6028,1.09967,0.71633,0],
			'sig':[1.04393,37.9316,987.711,14587.1,100178,0.011943,403.859,19719.8,88850.5,138627,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.6165, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,280.157,11.5769,2.466,1.04187,0.67868,0],
			'sig':[1.39177,59.7121,1713.34,27461.4,213595,0.014338,801.577,42172.7,201693,335676,0]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.4105, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,186.544,7.70854,1.642,0.693738,0.451903,0],
			'sig':[0.025909,3.01359,250.568,12343.2,324397,0.000548,432.802,81783,773230,1046750,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.4037, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,183.454,7.58084,1.6148,0.682246,0.444417,0],
			'sig':[0.020251,3.26426,324.691,17305.3,472221,0.000399,607.127,123269,1181360,1555560,0]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.1076, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,48.8967,2.02056,0.4304,0.181842,0.118453,0],
			'sig':[1.42604,23.7744,289.901,2572.53,18192.9,5.35037,5335.2,65342,151706,158377,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.0669, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,30.4014,1.25628,0.2676,0.11306,0.073648,0],
			'sig':[0.19079,6.65183,166.874,2444.55,20169.3,4.45544,13676,92448.1,160555,692736,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.0669, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,30.4014,1.25628,0.2676,0.11306,0.073648,0],
			'sig':[0.25244,10.3764,286.514,4532.95,40641.8,6.85289,27041,218305,345192,1344780,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.0093, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,4.22621,0.174639,0.0372,0.015717,0.010238,0],
			'sig':[0.003445,0.363392,27.6696,1215.86,26505.6,395.825,203485,1.49145e+07,6239630,4870770,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.0093, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,4.22621,0.174639,0.0372,0.015717,0.010238,0],
			'sig':[0.00267,0.388388,35.3343,1681.06,38035.3,537.642,312977,2.21286e+07,9579850,7131410,0]}] },
			'In':{'NSHELLS':14, 'ETERM':-0.521,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':27.9399, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,595.605,121.075,55.8798,36.3217,29.3151,27.9678],
			'sig':[434.918,0,0,0,0,1.34354,132.4,1188.88,3806.96,6656.97,7536.04]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':4.2375, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,90.3324,18.3628,8.475,5.50872,4.44607,4.24174],
			'sig':[40.7498,693.81,7944.26,0,0,29.2774,1675.01,8755.65,19626.2,28158.9,30508.6]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':3.938, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,83.9478,17.065,7.876,5.11937,4.13182,3.94194],
			'sig':[6.07568,237.184,7137.36,0,0,5.16042,989.901,10175.7,33801.4,59266.4,68483.9]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':3.7301, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,79.516,16.164,7.4602,4.84911,3.91369,3.73383],
			'sig':[7.96011,367.611,12227.7,0,0,8.13599,1910.12,20666.8,70551.7,125639,145913]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.8256, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,375.178,15.5035,3.3024,1.39525,0.90887,0],
			'sig':[7.71466,129.927,1569.22,13137.8,73556.2,0.10187,464.899,11044.7,46562.8,82384.8,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.7022, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,319.101,13.1862,2.8088,1.18671,0.773024,0],
			'sig':[1.19739,42.7072,1086.68,15595.7,102573,0.010753,359.388,17930.1,82653.4,131364,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.6643, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,301.878,12.4745,2.6572,1.12266,0.731302,0],
			'sig':[1.58444,66.9062,1881.26,29413.7,221525,0.012726,710.295,38356.5,188043,317845,0]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.4508, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,204.857,8.46531,1.8032,0.761844,0.496268,0],
			'sig':[0.031347,3.59038,292.593,14046.5,358033,0.000439,353.923,69448.6,684299,1362900,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.4431, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,201.358,8.32071,1.7724,0.748831,0.487791,0],
			'sig':[0.024434,3.88134,378.674,19679.2,521345,0.000324,492.438,104545,1045670,2049510,0]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.1219, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,55.3951,2.28909,0.4876,0.206009,0.134195,0],
			'sig':[1.58318,26.0998,314.572,2766.4,19425.9,4.18846,4565.29,58088.5,144033,158710,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.0774, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,35.1729,1.45345,0.3096,0.130805,0.085207,0],
			'sig':[0.224246,7.685,188.437,2689.43,21684.6,3.29574,11402.6,87467.2,132859,445683,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.0774, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,35.1729,1.45345,0.3096,0.130805,0.085207,0],
			'sig':[0.294053,11.9301,323.08,4995.25,43961.4,4.95171,22385.5,204828,312472,859850,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.0162, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,7.36178,0.30421,0.0648,0.027378,0.017834,0],
			'sig':[0.004494,0.474454,35.5744,1514.22,31813,71.5568,237795,6435900,6812900,3388420,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.0162, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,7.36178,0.30421,0.0648,0.027378,0.017834,0],
			'sig':[0.003483,0.507674,45.5485,2100.53,45842.3,93.443,355700,9263120,1.04357e+07,5075460,0]}] },
			'Sn':{'NSHELLS':14, 'ETERM':-0.547,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':29.2001, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,622.47,126.536,58.4002,37.9599,30.6373,29.2293],
			'sig':[469.336,0,0,0,0,1.30278,126.259,1131.64,3622.85,6329.85,7176.65]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':4.4647, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,95.1757,19.3474,8.9294,5.80408,4.68445,4.46916],
			'sig':[44.0109,738.827,8308.23,0,0,27.4633,1574.34,8254.04,18540.7,26645.6,28882.6]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':4.1561, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,88.5972,18.0101,8.3122,5.4029,4.36066,4.16026],
			'sig':[6.88819,264.686,7817.5,0,0,4.87964,926.75,9525.74,31671,55551.7,64946.3]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':3.9288, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,83.7517,17.0251,7.8576,5.10741,4.12217,3.93273],
			'sig':[8.94867,407.853,13358.3,0,0,7.59024,1782.53,19333.7,66145.1,117903,138816]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.8838, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,401.626,16.5964,3.5352,1.49361,0.97294,0],
			'sig':[8.39794,139.619,1664.25,13759.5,75257.2,0.09385,425.282,10229.7,43525.4,77673.9,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.7564, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,343.731,14.204,3.0256,1.2783,0.832691,0],
			'sig':[1.36877,47.9281,1191.89,16629.6,104685,0.009724,320.816,16334.1,76944.7,124711,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.7144, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,324.645,13.4153,2.8576,1.20732,0.786455,0],
			'sig':[1.79763,74.7223,2059.41,31430,228987,0.011391,631.475,34957.2,175521,302965,0]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.4933, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,224.171,9.26339,1.9732,0.833669,0.543054,0],
			'sig':[0.037761,4.25706,340.03,15917,393437,0.000357,292.079,59357.6,608254,1563260,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.4848, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,220.308,9.10377,1.9392,0.819304,0.533697,0],
			'sig':[0.029306,4.59072,439.543,22287.4,573263,0.000269,402.348,89147.6,928811,2384800,0]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.1365, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,62.0298,2.56325,0.546,0.230683,0.150267,0],
			'sig':[1.75389,28.5943,340.728,2970.67,20701.4,3.48242,3979.11,52240.4,135490,154490,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.0886, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,40.2626,1.66377,0.3544,0.149732,0.097536,0],
			'sig':[0.262703,8.84936,212.117,2951.29,23259.4,2.44925,9630.53,82213.9,119546,314799,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.0886, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,40.2626,1.66377,0.3544,0.149732,0.097536,0],
			'sig':[0.342184,13.6839,363.286,5493.02,47471.6,3.59649,18782.9,191162,299461,616534,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.0239, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,10.8609,0.448804,0.0956,0.040391,0.026311,0],
			'sig':[0.005804,0.608824,44.7936,1847.77,37422.2,21.2291,173032,872345,1.10451e+07,2410030,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.0239, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,10.8609,0.448804,0.0956,0.040391,0.026311,0],
			'sig':[0.004493,0.65129,57.4127,2567.69,54067.2,26.5791,256065,1202450,1.66817e+07,3680550,0]}] },
			'Sb':{'NSHELLS':14, 'ETERM':-0.575,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':30.4912, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,649.993,132.131,60.9824,39.6384,31.9919,30.5217],
			'sig':[505.496,0,0,0,0,1.26503,120.534,1078.21,3450.95,6030.91,6829.84]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':4.6983, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,100.155,20.3596,9.3966,6.10776,4.92955,4.703],
			'sig':[47.4398,785.261,8672.92,0,0,25.6545,1482.06,7791.75,17536.2,25232.7,27353.9]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':4.3804, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,93.3787,18.9821,8.7608,5.69449,4.596,4.38478],
			'sig':[7.78759,294.564,8538.69,0,0,4.62827,869.749,8935.7,29728.7,52155.5,61254.6]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':4.1322, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,88.0877,17.9065,8.2644,5.37183,4.33558,4.13633],
			'sig':[10.0334,451.272,14553.6,0,0,7.10404,1667.57,18124.2,62121.7,110941,131078]},
			{'Shell':'3S1/2', 'Func':2, 'BindEnergy':0.9437, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,428.846,17.7212,3.7748,1.59484,1.03888,0],
			'sig':[9.12129,149.717,1761.59,14384,76311.2,0.08717,390.636,9503.69,40772.2,73333.1,0]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.8119, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,368.952,15.2462,3.2476,1.3721,0.893789,0],
			'sig':[1.55958,53.6119,1303.03,17677.1,106433,0.008891,288.707,14956.7,71811.7,118305,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.7656, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,347.912,14.3768,3.0624,1.29385,0.842819,0],
			'sig':[2.03268,83.1817,2247.33,33490.4,236239,0.010336,565.779,32018.3,164209,288258,0]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.5369, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,243.984,10.0821,2.1476,0.907352,0.591052,0],
			'sig':[0.045259,5.0224,393.185,17949.8,429913,0.000279,244.953,51304.2,542743,1568720,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.5275, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,239.712,9.90561,2.11,0.891466,0.580704,0],
			'sig':[0.034999,5.40406,507.655,25119.6,626949,0.000219,334.194,76888,828476,2417230,0]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.152, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,69.0735,2.85432,0.608,0.256877,0.167331,0],
			'sig':[1.94081,31.264,368.241,3183.98,22000.8,2.83088,3493.35,47218.7,127795,150779,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.0984, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,44.716,1.8478,0.3936,0.166294,0.108325,0],
			'sig':[0.306472,10.1464,237.725,3225.06,24828.3,2.04247,8548.25,78516.3,115484,241015,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.0984, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,44.716,1.8478,0.3936,0.166294,0.108325,0],
			'sig':[0.397217,15.6379,406.767,6016.45,51029.3,2.94446,16596.7,181994,300498,492359,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.0314, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,14.2691,0.589642,0.1256,0.053066,0.034567,0],
			'sig':[0.007412,0.769713,55.4781,2218.22,43305.5,9.27482,126240,148987,1.81632e+07,1913120,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.0314, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,14.2691,0.589642,0.1256,0.053066,0.034567,0],
			'sig':[0.005727,0.822775,71.1409,3086.08,62696.1,11.1955,185710,206236,2.69918e+07,2937260,0]}] },
			'Te':{'NSHELLS':14, 'ETERM':-0.602,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':31.8138, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,678.187,137.862,63.6276,41.3577,33.3796,31.8456],
			'sig':[543.458,0,0,0,0,1.23006,115.191,1028.25,3290.15,5755.03,6500.19]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':4.9392, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,105.291,21.4036,9.8784,6.42093,5.1823,4.94414],
			'sig':[51.0388,833.152,9037.27,0,0,24.1355,1396.82,7363.06,16601.9,23920.2,25939]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':4.612, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,98.3158,19.9857,9.224,5.99557,4.839,4.61661],
			'sig':[8.78302,327.008,9303.8,0,0,4.37503,817.693,8395.02,27941.9,49082,57618.5]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':4.3414, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,92.5473,18.8131,8.6828,5.64379,4.55508,4.34574],
			'sig':[11.2164,498.024,15818.7,0,0,6.65949,1562.57,17016.8,58433,104471,123284]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':1.006, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,21.4453,4.35941,2.012,1.30779,1.05551,1.00701],
			'sig':[9.88543,160.228,1861.39,15013.2,0,268.347,7620.71,29398.9,55816.5,72969.3,78514.3]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.8697, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,395.218,16.3316,3.4788,1.46978,0.957418,0],
			'sig':[1.77139,59.7895,1420.44,18742.4,107932,0.008182,260.86,13730.6,67091.4,112187,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.8187, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,372.042,15.3739,3.2748,1.38359,0.901274,0],
			'sig':[2.29134,92.3205,2445.54,35605.1,243247,0.009464,509.013,29406.5,153819,274295,0]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.5825, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,264.706,10.9384,2.33,0.984415,0.641251,0],
			'sig':[0.053957,5.89682,452.654,20165.3,467900,0.000232,207.141,44610.1,485887,1451070,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.5721, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,259.98,10.7431,2.2884,0.966839,0.629802,0],
			'sig':[0.041602,6.33225,583.755,28203.6,682898,0.00019,279.898,66722.5,741277,2247020,0]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.1683, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,76.4807,3.16041,0.6732,0.284424,0.185275,0],
			'sig':[2.13859,34.0774,397.046,3406.03,23322,2.39971,3090.33,42859.2,120638,147176,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.1102, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,50.0783,2.06938,0.4408,0.186236,0.121315,0],
			'sig':[0.356053,11.5856,265.414,3513.79,26433.6,1.61186,7437.32,73759.4,112976,191477,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.1102, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,50.0783,2.06938,0.4408,0.186236,0.121315,0],
			'sig':[0.458347,17.7873,453.763,6571.94,54741.1,2.26832,14359,170265,300900,417149,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.0398, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,18.0863,0.747381,0.1592,0.067261,0.043814,0],
			'sig':[0.009369,0.960885,67.7794,2628.52,49492,4.53559,91436.7,153574,1.68841e+07,1665410,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.0398, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,18.0863,0.747381,0.1592,0.067261,0.043814,0],
			'sig':[0.007223,1.02602,86.9254,3659.91,71778.8,5.26038,133818,240598,2.48383e+07,2550610,0]}] },
			'I':{'NSHELLS':14, 'ETERM':-0.631,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':33.1694, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,707.085,143.736,66.3388,43.12,34.802,33.2026],
			'sig':[583.245,0,0,0,0,1.19741,110.185,981.341,3138.85,5488.68,6199.58]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':5.1881, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,110.597,22.4821,10.3762,6.7445,5.44345,5.19329],
			'sig':[54.8252,882.531,9402.86,0,0,22.7374,1317.68,6963.47,15728.3,22737.3,24558.5]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':4.8521, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,103.434,21.0261,9.7042,6.3077,5.09092,4.85695],
			'sig':[9.87877,362.167,10115.5,0,0,4.16131,769.584,7895.64,26294,46208,54148.6]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':4.5571, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,97.1454,19.7478,9.1142,5.9242,4.7814,4.56166],
			'sig':[12.5069,548.317,17158.8,0,0,6.21549,1465.91,15995.8,55028,98476.7,116015]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':1.0721, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,22.8544,4.64584,2.1442,1.39372,1.12487,1.07317],
			'sig':[10.6919,171.168,1963.88,15650.5,0,246.686,7083.81,27512.2,52495.8,68881,74222.1]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.9305, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,422.848,17.4733,3.722,1.57253,1.02435,0],
			'sig':[2.00615,66.492,1544.36,19827.4,108353,0.007553,236.124,12618.8,62695.5,106306,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.8746, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,397.445,16.4236,3.4984,1.47806,0.962812,0],
			'sig':[2.5751,102.177,2654.61,37784.1,250097,0.008724,458.36,27024.3,144082,260778,0]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.6313, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,286.882,11.8548,2.5252,1.06689,0.694973,0],
			'sig':[0.064089,6.896,519.144,22592.2,509126,0.000193,175.291,38821.4,435246,1298460,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.6194, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,281.474,11.6313,2.4776,1.04678,0.681873,0],
			'sig':[0.04923,7.38825,668.624,31571.2,743101,0.000166,235.064,58034.3,664276,2012410,0]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.1864, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,84.7059,3.5003,0.7456,0.315013,0.2052,0],
			'sig':[2.35338,37.0663,427.166,3637.14,24670.4,2.03495,2725.11,38797.5,113234,142574,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.1227, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,55.7587,2.30411,0.4908,0.207361,0.135076,0],
			'sig':[0.412523,13.18,295.147,3815.27,28041,1.32523,6511.54,69118.1,111561,161006,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.1227, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,55.7587,2.30411,0.4908,0.207361,0.135076,0],
			'sig':[0.526673,20.1479,504.201,7155.67,58536.2,1.81927,12502,159002,301011,377584,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.0496, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,22.5398,0.931409,0.1984,0.083823,0.054603,0],
			'sig':[0.011712,1.18566,81.8602,3081.74,56009.5,2.33227,65372.1,245734,7527100,1628420,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.0496, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,22.5398,0.931409,0.1984,0.083823,0.054603,0],
			'sig':[0.009004,1.26441,104.972,4293.62,81361.2,2.58737,95179.1,385469,1.09908e+07,2475890,0]}] },
			'Xe':{'NSHELLS':14, 'ETERM':-0.66,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':34.5614, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,736.759,149.769,69.1228,44.9296,36.2625,34.596],
			'sig':[624.903,0,0,0,0,1.16669,105.468,937.121,2996.3,5237.45,5917.15]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':5.4528, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,116.239,23.6292,10.9056,7.0886,5.72118,5.45825],
			'sig':[58.7912,933.677,9777.1,0,0,21.3622,1240.57,6577.08,14887.8,21553.2,23289.6]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':5.1037, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,108.798,22.1164,10.2074,6.63478,5.3549,5.1088],
			'sig':[11.0864,400.324,10981.6,0,0,3.95615,724.057,7425.86,24750.1,43523.1,50915.9]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':4.7822, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,101.944,20.7232,9.5644,6.21683,5.01757,4.78698],
			'sig':[13.9128,602.491,18586.6,0,0,5.82589,1374.63,15035.8,51837.3,92885.4,109282]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':1.1446, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,24.3999,4.96002,2.2892,1.48797,1.20094,1.14574],
			'sig':[11.5423,182.56,2069.69,16305.2,0,225.554,6558.44,25666.5,49240.8,64829.5,69698.7]},
			{'Shell':'3P1/2', 'Func':2, 'BindEnergy':0.999, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,453.976,18.7596,3.996,1.68829,1.09976,0],
			'sig':[2.26599,73.7759,1676.36,20961.7,125156,0.006453,211.358,11509.2,58277.1,100208,0]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.937, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,425.802,17.5954,3.748,1.58351,1.03151,0],
			'sig':[2.88629,112.822,2876.84,40080.6,254937,0.008,408.549,24666.2,134316,246849,0]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.6854, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,311.467,12.8707,2.7416,1.15831,0.75453,0],
			'sig':[0.075814,8.03452,593.646,25286.1,554710,0.000159,146.911,33567.7,388216,1148920,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.6723, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,305.514,12.6247,2.6892,1.13618,0.740108,0],
			'sig':[0.058017,8.5884,763.666,35315.5,810876,0.000146,194.78,50045.7,592061,1774540,0]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.2081, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,94.567,3.90779,0.8324,0.351685,0.229089,0],
			'sig':[2.58266,40.2187,458.667,3879.22,26078.5,1.62306,2361.2,34653.8,104899,136051,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.1467, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,66.665,2.75479,0.5868,0.24792,0.161496,0],
			'sig':[0.475487,14.9393,327.582,4144.67,29800.2,0.845944,4936.92,59695.7,104646,133242,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.1467, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,66.665,2.75479,0.5868,0.24792,0.161496,0],
			'sig':[0.603809,22.761,559.288,7799.19,62819.4,1.11512,9363.08,135641,282985,336482,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.064, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,29.0836,1.20182,0.256,0.108159,0.070455,0],
			'sig':[0.014529,1.44995,97.9827,3587.87,63078.9,1.0298,41673,314020,2160810,2001500,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.064, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,29.0836,1.20182,0.256,0.108159,0.070455,0],
			'sig':[0.011113,1.54286,125.608,5001.28,91777.7,1.07194,60255.1,485718,3088150,2997720,0]}] },
			'Cs':{'NSHELLS':17, 'ETERM':-0.69,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':35.9846, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,767.097,155.936,71.9692,46.7797,37.7557,36.0206],
			'sig':[668.321,0,0,0,0,1.13831,101.049,895.577,2862.36,5007.01,5643.02]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':5.7143, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,121.814,24.7624,11.4286,7.42855,5.99555,5.72001],
			'sig':[62.9148,985.462,10133.6,0,0,20.2039,1173.68,6234.7,14132,20480.5,22111.3]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':5.3594, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,114.248,23.2245,10.7188,6.96718,5.62318,5.36476],
			'sig':[12.4089,441.206,11877.7,0,0,3.77664,683.333,6998.49,23326.8,41032,48133.7]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':5.0119, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,106.841,21.7186,10.0238,6.51544,5.25858,5.01691],
			'sig':[15.44,660.235,20066.7,0,0,5.47628,1291.51,14149.7,48858.8,87793.4,103287]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':1.2171, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,25.9454,5.27419,2.4342,1.58222,1.277,1.21832],
			'sig':[12.4346,194.303,2176.17,16932.8,0,207.813,6103.19,24027.2,46306.2,61175.3,66349.1]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':1.065, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,22.703,4.61508,2.13,1.38449,1.11742,1.06607],
			'sig':[2.55166,81.5792,1811.98,22041.4,0,132.541,8887.51,41439.9,78768.7,99256.3,116908]},
			{'Shell':'3P3/2', 'Func':2, 'BindEnergy':0.9976, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,453.34,18.7333,3.9904,1.68593,1.09822,0],
			'sig':[3.22513,124.162,3105.35,42307.9,286715,0.007031,369.943,22729.2,125856,234658,0]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.7395, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,336.052,13.8866,2.958,1.24974,0.814086,0],
			'sig':[0.089295,9.31652,674.936,28080.4,598648,0.000135,125.516,29354.2,347528,1013740,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.7255, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,329.69,13.6237,2.902,1.22608,0.798674,0],
			'sig':[0.068073,9.9369,867.317,39209.4,875926,0.000131,164.26,43590.2,529143,1566130,0]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.2308, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,104.883,4.33406,0.9232,0.390048,0.254079,0],
			'sig':[2.82313,43.5039,491.151,4124.46,27439.5,1.3566,2063.27,31075.7,96953.9,136826,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.1723, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,78.2984,3.23552,0.6892,0.291184,0.189678,0],
			'sig':[0.545892,16.8632,362.008,4482.42,31513.5,0.584037,3832.93,51790.3,99812.5,119685,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.1616, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,73.436,3.03459,0.6464,0.273101,0.177899,0],
			'sig':[0.688148,25.5705,616.47,8429.51,66677.3,0.917055,8224.6,126087,282214,341443,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.0788, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,35.8091,1.47974,0.3152,0.133171,0.086748,0],
			'sig':[0.01783,1.75545,116.102,4130.71,70102.8,0.542042,28382.7,333746,509264,3.31728e+07,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.0765, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,34.764,1.43655,0.306,0.129284,0.084216,0],
			'sig':[0.013596,1.86467,148.681,5751.56,101874,0.606637,43811.3,516660,794425,4.03871e+07,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.0227, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,10.3156,0.42627,0.0908,0.038363,0.02499,0],
			'sig':[0.472456,6.9532,76.9159,654.312,4590.28,56.5034,17553.1,113059,88327.2,39314.5,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.0131, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,5.95304,0.245997,0.0524,0.022139,0.014421,0],
			'sig':[0.073155,2.10897,43.6368,542.001,4002.73,117.951,22826.2,299503,6245060,3.47826e+07,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.0114, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,5.18051,0.214074,0.0456,0.019266,0.01255,0],
			'sig':[0.08945,3.08563,71.4838,977.464,8012.71,281.478,62977.7,667454,1.41872e+07,7.52073e+07,0]}] },
			'Ba':{'NSHELLS':17, 'ETERM':-0.721,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':37.4406, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,798.136,162.245,74.8812,48.6725,39.2834,37.478],
			'sig':[713.582,0,0,0,0,1.1118,96.9028,856.469,2735.9,4783.98,5391.82]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':5.9888, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,127.666,25.9519,11.9776,7.7854,6.28356,5.99479],
			'sig':[67.2285,1038.76,10493.2,0,0,19.0881,1109.39,5906.62,13409.1,19454.9,20961]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':5.6236, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,119.88,24.3693,11.2472,7.31064,5.90039,5.62922],
			'sig':[13.8606,485.22,12817,0,0,3.61123,645.643,6601.72,22001.9,38780.4,45369.6]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':5.247, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,111.852,22.7374,10.494,6.82107,5.50525,5.25225],
			'sig':[17.0906,721.81,21613.9,0,0,5.15737,1215.44,13334.4,46105.4,82941.5,97501.9]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':1.2928, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,27.5591,5.60223,2.5856,1.68063,1.35643,1.29409],
			'sig':[13.3712,206.458,2284.67,17555.7,0,191.704,5684,22503.7,43555.9,57755.9,62266]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':1.1367, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,24.2315,4.92578,2.2734,1.4777,1.19265,1.13784],
			'sig':[2.8661,89.9967,1954.59,23138.8,0,120.215,8159.1,38513.3,74012.3,93928.9,108999]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':1.0622, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,22.6433,4.60294,2.1244,1.38085,1.11448,1.06326],
			'sig':[3.59444,136.313,3344.86,44586,0,227.146,17394.1,87520.3,177929,235299,271843]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.7961, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,361.772,14.9495,3.1844,1.3454,0.876395,0],
			'sig':[0.104761,10.7617,764.411,31069.1,644373,0.000116,107.815,25759.7,311501,900985,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.7807, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,354.774,14.6603,3.1228,1.31937,0.859442,0],
			'sig':[0.079563,11.4524,981.137,43359.9,943256,0.000121,139.529,38155.8,473915,1389460,0]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.253, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,114.971,4.75094,1.012,0.427566,0.278518,0],
			'sig':[3.08263,46.9716,524.797,4374.58,28774.8,1.17017,1838.28,28246.4,90572.1,129712,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.1918, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,87.1598,3.6017,0.7672,0.324139,0.211145,0],
			'sig':[0.625213,18.9667,398.201,4820.64,33107.3,0.47875,3297.27,47314.4,97750,109831,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.1797, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,81.6612,3.37448,0.7188,0.30369,0.197825,0],
			'sig':[0.781741,28.6365,677.619,9093.28,70677.2,0.729823,7054.22,115113,276223,328282,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.0925, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,42.0348,1.737,0.37,0.156323,0.10183,0],
			'sig':[0.021734,2.10992,136.5,4715.9,77176.7,0.333375,21233.9,328205,191382,5116670,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.0899, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,40.8533,1.68818,0.3596,0.151929,0.098967,0],
			'sig':[0.016552,2.23914,174.732,6567.91,112285,0.355158,32598.9,509330,286084,8133640,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.0391, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,17.7682,0.734236,0.1564,0.066078,0.043044,0],
			'sig':[0.551031,8.08316,88.9187,753.341,5275.69,20.1814,8736.7,76697.9,119735,46879.7,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.0166, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,7.54355,0.311722,0.0664,0.028054,0.018274,0],
			'sig':[0.093692,2.68614,54.6888,664.929,4825.65,82.7137,21627.6,176768,2802740,1.4047e+07,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.0146, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,6.63469,0.274165,0.0584,0.024674,0.016073,0],
			'sig':[0.115232,3.96815,90.7736,1219.18,9861.19,193.208,59549.1,412173,5905090,3.08598e+07,0]}] },
			'La':{'NSHELLS':17, 'ETERM':-0.753,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':38.9246, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,829.771,168.676,77.8492,50.6017,40.8404,38.9635],
			'sig':[760.623,0,0,0,0,1.08747,93.0395,819.901,2617.47,4574.85,5157.29]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':6.2663, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,133.581,27.1544,12.5326,8.14615,6.57472,6.27257],
			'sig':[71.7344,1093.24,10849.6,0,0,18.1027,1051.48,5608.29,12748.3,18545.6,19904.4]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':5.8906, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,125.572,25.5264,11.7812,7.65774,6.18053,5.89649],
			'sig':[15.4447,532.368,13792.9,0,0,3.46829,612.458,6248.76,20815,36688.4,41857.5]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':5.4827, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,116.877,23.7588,10.9654,7.12747,5.75255,5.48818],
			'sig':[18.8738,787.28,23222.8,0,0,4.88159,1148.78,12612.4,43647.7,78571,89963.7]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':1.3613, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,29.0194,5.89907,2.7226,1.76968,1.4283,1.36266],
			'sig':[14.3575,218.964,2393.1,18141.1,0,180.241,5369.85,21318.7,41354.8,55034.1,58846.9]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':1.2044, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,25.6747,5.21915,2.4088,1.56571,1.26368,1.2056],
			'sig':[3.21071,99.0048,2101.87,24202.1,0,111.235,7595.97,36149.3,70033.2,89405.4,104330]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':1.1234, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,23.9479,4.86815,2.2468,1.46041,1.17869,1.12452],
			'sig':[3.99531,149.249,3592.68,46846.2,0,208.944,16194.6,82333,168956,224955,259558]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.8485, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,385.584,15.9335,3.394,1.43395,0.93408,0],
			'sig':[0.122429,12.3796,861.627,34171.9,689898,0.000103,95.9333,23207.4,284373,819914,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.8317, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,377.95,15.618,3.3268,1.40556,0.915586,0],
			'sig':[0.092621,13.1446,1104.65,47668.8,1009630,0.000116,122.896,34300.4,432386,1263590,0]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.2704, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,122.878,5.07768,1.0816,0.456971,0.297673,0],
			'sig':[3.35369,50.5716,559.346,4626.13,30044,1.07607,1714.86,26598.3,86576.2,125810,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.2058, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,93.5218,3.8646,0.8232,0.347798,0.226557,0],
			'sig':[0.712527,21.2413,436.218,5161.82,34613.3,0.422869,3052.05,45007.7,97081.1,109125,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.1914, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,86.978,3.59419,0.7656,0.323463,0.210705,0],
			'sig':[0.885865,31.9588,741.742,9764.77,74519.5,0.670627,6612.56,110712,276994,337661,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.0989, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,44.9432,1.85718,0.3956,0.167139,0.108875,0],
			'sig':[0.026345,2.51743,159.059,5327.98,83920.8,0.305605,19869.8,330691,173071,1769130,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.0989, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,44.9432,1.85718,0.3956,0.167139,0.108875,0],
			'sig':[0.019999,2.66825,203.688,7435.59,122601,0.280723,28343.7,502299,256710,2599750,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.0323, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,14.6781,0.606543,0.1292,0.054586,0.035558,0],
			'sig':[0.63412,9.22574,100.573,845.609,5863.56,34.9374,13069.1,102414,145775,82583.3,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.0144, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,6.5438,0.270409,0.0576,0.024336,0.015852,0],
			'sig':[0.115328,3.26671,65.2264,776.052,5532.49,138.578,28625.3,268284,3371860,1.17015e+07,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.0144, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,6.5438,0.270409,0.0576,0.024336,0.015852,0],
			'sig':[0.141208,4.82152,108.561,1432.34,11431.7,237.853,70301.6,474000,5534420,2.15342e+07,0]}] },
			'Ce':{'NSHELLS':18, 'ETERM':-0.786,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':40.443, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,862.139,175.256,80.886,52.5756,42.4336,40.4834],
			'sig':[809.808,0,0,0,0,1.06495,89.4197,785.679,2507.05,4384.17,4934.35]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':6.5488, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,139.603,28.3786,13.0976,8.5134,6.87113,6.55535],
			'sig':[76.4518,1149.86,11217.6,0,0,17.2116,999.253,5340.45,12156.2,17694.3,18956.3]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':6.1642, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,131.405,26.712,12.3284,8.01342,6.4676,6.17036],
			'sig':[17.1871,583.775,14862.6,0,0,3.34047,582.965,5939.5,19788.4,34880.5,39648.7]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':5.7234, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,122.008,24.8018,11.4468,7.44038,6.0051,5.72912],
			'sig':[20.8197,858.343,24986.5,0,0,4.63359,1089.41,11981.7,41540.1,74921.2,87887.3]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':1.4346, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,30.5819,6.2167,2.8692,1.86497,1.50521,1.43603],
			'sig':[15.3995,232.21,2510.77,18812,0,169.18,5079,20256.5,39390,52409.6,56607.8]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':1.2728, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,27.1328,5.51556,2.5456,1.65463,1.33545,1.27407],
			'sig':[3.59319,108.887,2263.31,25395.1,0,103.819,7137.41,34230.4,66648,85321.3,100858]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':1.1854, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,25.2696,5.13682,2.3708,1.54101,1.24374,1.18659],
			'sig':[4.43626,163.382,3865.47,49440.2,0,193.664,15214.8,78193.3,161654,216239,250859]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.9013, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,409.578,16.925,3.6052,1.52318,0.992205,0],
			'sig':[0.142988,14.249,974.597,37971.5,766256,9.4e-05,86.6941,21337,266197,783598,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.8833, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,401.399,16.587,3.5332,1.49276,0.97239,0],
			'sig':[0.107753,15.095,1248.11,52964.7,1117030,0.000113,109.799,31450.6,404560,1208480,0]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.2896, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,131.603,5.43823,1.1584,0.489419,0.318809,0],
			'sig':[3.61079,53.8377,589.919,4852.89,31144.9,0.976828,1578.11,24810.5,80955.2,117011,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.2233, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,101.474,4.19322,0.8932,0.377373,0.245822,0],
			'sig':[0.800607,23.4364,471.346,5469.03,35751.9,0.367918,2727.52,41595.9,90040.5,99440.4,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.2072, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,94.1581,3.89089,0.8288,0.350164,0.228098,0],
			'sig':[0.984948,35.029,799.215,10361.4,77732.6,0.551236,5903.73,102664,259701,312581,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.11, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,49.9874,2.06563,0.44,0.185898,0.121095,0],
			'sig':[0.03089,2.9031,179.589,5875.51,89656,0.22479,16450.4,302829,155294,2181360,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.11, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,49.9874,2.06563,0.44,0.185898,0.121095,0],
			'sig':[0.023297,3.06572,229.53,8191.42,131030,0.198385,23346.7,458748,230270,3252530,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.0859, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,39.0356,1.61307,0.3436,0.14517,0.094564,0],
			'sig':[1e-05,0.003611,0.808585,99.4774,7211.28,0.000505,1200,226162,939982,176164,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.0378, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,17.1775,0.709824,0.1512,0.063881,0.041612,0],
			'sig':[0.651443,9.37104,101.202,846.456,5819,25.0342,10096.8,82769.1,119175,54989.6,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.0198, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,8.99773,0.371813,0.0792,0.033462,0.021797,0],
			'sig':[0.12141,3.36806,65.7644,767.276,5356.13,63.9939,19259.3,134978,2124580,1.04848e+07,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.0198, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,8.99773,0.371813,0.0792,0.033462,0.021797,0],
			'sig':[0.146372,4.90951,108.452,1408.65,11072.6,105.411,45629.7,262445,3349820,1.91557e+07,0]}] },
			'Pr':{'NSHELLS':18, 'ETERM':-0.819,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':41.9906, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,895.13,181.962,83.9812,54.5875,44.0573,42.0326],
			'sig':[860.712,0,0,0,0,1.04404,86.0257,753.415,2402.43,4199.05,4728.58]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':6.8348, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,145.7,29.618,13.6696,8.8852,7.1712,6.84163],
			'sig':[81.3396,1207.11,11565.8,0,0,16.3109,951.27,5091.45,11600.6,16877.1,18157.7]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':6.4404, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,137.292,27.9089,12.8808,8.37248,6.75739,6.44684],
			'sig':[19.0796,638.303,15951.5,0,0,3.22955,556.464,5655.64,18830.7,33142.2,37849.7]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':5.9643, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,127.143,25.8457,11.9286,7.75355,6.25786,5.97026],
			'sig':[22.9037,933.04,26775.6,0,0,4.416,1036.27,11404.4,39572.1,71370.7,83811.2]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':1.511, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,32.2106,6.54778,3.022,1.96429,1.58537,1.51251],
			'sig':[16.4826,245.755,2628.28,19448.9,0,158.747,4798.38,19215.7,37455.7,49881.5,54007.9]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':1.3374, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,28.5099,5.7955,2.6748,1.73861,1.40323,1.33874],
			'sig':[4.00849,119.32,2425.9,26482.9,0,98.305,6764.59,32577.5,63681.1,81833.3,95781.8]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':1.2422, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,26.4805,5.38296,2.4844,1.61485,1.30334,1.24344],
			'sig':[4.9123,178.217,4139.19,51840.8,0,182.81,14453.5,74755.5,155398,208608,243150]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.9511, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,432.209,17.8601,3.8044,1.60734,1.04703,0],
			'sig':[0.16618,16.3103,1094.48,41736.1,853500,8.8e-05,79.955,19838.4,249923,741483,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.931, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,423.075,17.4827,3.724,1.57337,1.0249,0],
			'sig':[0.124732,17.2377,1399.79,58175.7,1234410,0.000113,100.572,29242.9,380224,1145310,0]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.3045, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,138.374,5.71803,1.218,0.5146,0.335212,0],
			'sig':[3.88805,57.3575,622.517,5085.46,32177.2,0.930876,1505.27,23761.2,77547.6,112280,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.2363, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,107.382,4.43734,0.9452,0.399343,0.260133,0],
			'sig':[0.899813,25.8757,509.42,5787.86,36860.5,0.347548,2571.42,39730.1,86691,95286.7,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.2176, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,98.8841,4.08618,0.8704,0.36774,0.239547,0],
			'sig':[1.09892,38.4813,862.007,10987.8,80905.6,0.521491,5636.46,99302.7,253925,306985,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.1132, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,51.4416,2.12572,0.4528,0.191306,0.124617,0],
			'sig':[0.036379,3.36318,203.367,6471.14,95183.7,0.234063,16634,300942,155594,1859520,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.1132, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,51.4416,2.12572,0.4528,0.191306,0.124617,0],
			'sig':[0.02732,3.54276,259.574,9017.2,139187,0.20385,23572.2,456057,231231,2776130,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.0035, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1.59051,0.065724,0.014,0.005915,0.003853,0],
			'sig':[2.2e-05,0.007403,1.58399,180.477,11228.9,2134.21,3177410,1800970,1281230,1149310,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.0374, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,16.9957,0.702313,0.1496,0.063205,0.041172,0],
			'sig':[0.698365,9.93235,106.227,882.847,6008.07,27.0434,10559.7,83490.3,114421,52936,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.0223, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,10.1338,0.418759,0.0892,0.037687,0.024549,0],
			'sig':[0.134909,3.68197,70.4403,805.636,5511.18,50.8948,17093,110354,1795620,9865040,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.0223, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,10.1338,0.418759,0.0892,0.037687,0.024549,0],
			'sig':[0.160756,5.32211,115.589,1477.57,11442.8,82.3359,40193.4,223770,2781510,1.79796e+07,0]}] },
			'Nd':{'NSHELLS':18, 'ETERM':-0.854,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':43.5689, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,928.775,188.802,87.1378,56.6393,45.7133,43.6125],
			'sig':[913.447,0,0,0,0,1.02491,82.8396,723.044,2304.07,4028.5,4529.64]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':7.126, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,151.908,30.8799,14.252,9.26375,7.47673,7.13313],
			'sig':[86.4296,1265.46,11914.8,0,0,15.5731,906.955,4859.87,11082.7,16151.5,17348.4]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':6.7215, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,143.285,29.127,13.443,8.73791,7.05233,6.72822],
			'sig':[21.1416,696.521,17076.6,0,0,3.13181,532.389,5395.26,17946.9,31614.8,36935.4]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':6.2079, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,132.336,26.9014,12.4158,8.07023,6.51345,6.21411],
			'sig':[25.1437,1012.18,28640.4,0,0,4.22006,987.991,10876.2,37762.2,68143.7,79710.7]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':1.5753, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,33.5813,6.82642,3.1506,2.04788,1.65283,1.57688],
			'sig':[17.6077,259.519,2743.41,20013.7,0,152.315,4609.48,18466.1,35998,47936,51975.1]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':1.4028, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,29.904,6.0789,2.8056,1.82363,1.47184,1.4042],
			'sig':[4.46138,130.456,2594.32,27548.6,0,93.4612,6428.93,31062.5,60916.7,78521.6,91443.5]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':1.2974, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,27.6572,5.62216,2.5948,1.68661,1.36126,1.2987],
			'sig':[5.42337,193.899,4421.4,54216.1,0,174.004,13811.8,71773.1,149866,201881,238360]},
			{'Shell':'3D3/2', 'Func':2, 'BindEnergy':0.9995, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,454.204,18.769,3.998,1.68914,1.10031,0],
			'sig':[0.192459,18.6036,1224.46,45675.4,1.02588e+07,7.8e-05,74.7326,18626.2,236190,705053,0]},
			{'Shell':'3D5/2', 'Func':2, 'BindEnergy':0.9777, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,444.297,18.3597,3.9108,1.6523,1.07631,0],
			'sig':[0.143891,19.6167,1564.23,63646,1330190,0.000108,93.2128,27422.8,359431,1089680,0]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.3152, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,143.237,5.91895,1.2608,0.532683,0.346991,0],
			'sig':[4.17607,60.9532,655.201,5311.16,33073.5,0.87696,1476.41,23229.2,75376.3,109103,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.2433, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,110.563,4.56879,0.9732,0.411173,0.267839,0],
			'sig':[1.0077,28.4614,548.302,6095.67,37795,0.357061,2562.56,39166.2,84976.8,93437.1,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.2246, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,102.065,4.21763,0.8984,0.37957,0.247253,0],
			'sig':[1.22021,42.1038,926.316,11606.7,83823.7,0.521504,5574.42,98074.6,251389,305621,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.1175, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,53.3956,2.20646,0.47,0.198573,0.129351,0],
			'sig':[0.042616,3.87616,229.197,7099.17,100679,0.234245,16402.5,296048,154744,1601790,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.1175, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,53.3956,2.20646,0.47,0.198573,0.129351,0],
			'sig':[0.031916,4.07501,292.152,9887.37,147313,0.200787,23199,448627,230926,2393270,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.003, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1.36329,0.056335,0.012,0.00507,0.003303,0],
			'sig':[3.8e-05,0.012911,2.73084,303.52,18331.5,6201.41,4246960,1898920,1260280,900741,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.0375, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,17.0412,0.70419,0.15,0.063374,0.041282,0],
			'sig':[0.744406,10.4885,111.216,918.484,6185.99,28.2905,10784.8,82883.8,109374,51805.9,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.0211, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,9.58849,0.396224,0.0844,0.035659,0.023228,0],
			'sig':[0.149897,4.01507,75.1643,842.401,5641.87,62.5229,18275,129761,2142590,1.14939e+07,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.0211, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,9.58849,0.396224,0.0844,0.035659,0.023228,0],
			'sig':[0.176585,5.75602,122.752,1543.74,11766.4,101.254,43792.4,248609,3320070,2.10397e+07,0]}] },
			'Pm':{'NSHELLS':18, 'ETERM':-0.889,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':45.184, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,963.205,195.801,90.368,58.7389,47.4079,45.2292],
			'sig':[968.105,0,0,0,0,1.00673,79.8226,694.224,2210.45,3862.62,4345.93]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':7.4279, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,158.343,32.1881,14.8558,9.65622,7.79349,7.43533],
			'sig':[91.7074,1325.11,12264,0,0,14.866,864.577,4639.05,10588.8,15432.6,16601.2]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':7.0128, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,149.495,30.3893,14.0256,9.11659,7.35796,7.01981],
			'sig':[23.3821,758.867,18264.5,0,0,3.018,509.44,5148.71,17113.2,30120.6,35252.3]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':6.4593, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,137.695,27.9908,12.9186,8.39705,6.77722,6.46576],
			'sig':[27.5587,1096.41,30605.2,0,0,4.03356,942.017,10375.3,36054,65171.4,76039.9]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':1.6465, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,35.0991,7.13495,3.293,2.14044,1.72754,1.64815],
			'sig':[18.7907,273.776,2861.63,20585.4,0,145.21,4405.81,17676.4,34478.2,45973,49837.2]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':1.4714, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,31.3664,6.37617,2.9428,1.91281,1.54382,1.47287],
			'sig':[4.95716,142.365,2769.53,28606.3,0,88.7884,6105.68,29603.1,58231,75172.7,87920]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':1.3569, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,28.9256,5.88,2.7138,1.76396,1.42369,1.35826],
			'sig':[5.97503,210.569,4716.79,56664.7,0,164.719,13151.1,68740.4,144250,195117,227490]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':1.0515, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,22.4152,4.55658,2.103,1.36694,1.10325,1.05255],
			'sig':[0.222329,21.1643,1367.03,49949.5,0,42.2864,13450.2,140667,436547,768295,9587680]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':1.0269, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,21.8908,4.44997,2.0538,1.33496,1.07744,1.02793],
			'sig':[0.165465,22.2593,1743.82,69536.2,0,51.1324,19737.7,213320,671214,1194340,1.47254e+07]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.3304, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,150.144,6.20439,1.3216,0.55837,0.363724,0],
			'sig':[4.48026,64.674,688.634,5541.97,33968,0.835677,1411.66,22272,72218.2,104548,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.2544, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,115.607,4.77723,1.0176,0.429932,0.280059,0],
			'sig':[1.12527,31.2218,588.891,6411.08,38681.1,0.34893,2468.01,37817,82121.3,90096.3,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.236, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,107.246,4.4317,0.944,0.398836,0.259803,0],
			'sig':[1.35085,45.9449,993.455,12249.7,86818.5,0.489623,5293.72,94433.6,244521,298490,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.1204, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,54.7135,2.26092,0.4816,0.203474,0.132544,0],
			'sig':[0.049676,4.44508,257.014,7749.39,105897,0.246039,16661.4,293729,154142,1425010,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.1204, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,54.7135,2.26092,0.4816,0.203474,0.132544,0],
			'sig':[0.037039,4.66135,327.163,10787.4,155039,0.208176,23532,445345,229930,2132980,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.004, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1.81772,0.075114,0.016,0.00676,0.004403,0],
			'sig':[6e-05,0.020645,4.31517,468.574,27527.3,3282.39,4659900,2167960,1106790,625465,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.0375, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,17.0412,0.70419,0.15,0.063374,0.041282,0],
			'sig':[0.793454,11.057,116.162,953.136,6350.88,29.7003,11026.4,82262.7,104472,51364.2,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.0211, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,9.58849,0.396224,0.0844,0.035659,0.023228,0],
			'sig':[0.165404,4.35853,79.9593,878.541,5760.63,66.6086,18324.8,136199,2281660,1.23652e+07,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.0211, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,9.58849,0.396224,0.0844,0.035659,0.023228,0],
			'sig':[0.192575,6.19664,129.967,1609.01,12074.4,107.336,44408.6,253856,3515570,2.2673e+07,0]}] },
			'Sm':{'NSHELLS':18, 'ETERM':-0.925,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':46.8342, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,998.383,202.952,93.6684,60.8842,49.1393,46.881],
			'sig':[1024.61,0,0,0,0,0.98999,76.9717,666.948,2122.07,3709.04,4167.85]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':7.7368, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,164.928,33.5267,15.4736,10.0578,8.1176,7.74454],
			'sig':[97.18,1385.83,12577.5,0,0,14.2097,824.944,4431.95,10124.3,14750.4,15886.4]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':7.3118, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,155.868,31.685,14.6236,9.50529,7.67168,7.31911],
			'sig':[25.8145,825.376,19507,0,0,2.92831,488.057,4918.68,16334.6,28715.2,33631.8]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':6.7162, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,143.172,29.104,13.4324,8.73102,7.04676,6.72292],
			'sig':[30.1455,1185.64,32645.9,0,0,3.85828,899.062,9907.23,34452.4,62228,73187.8]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':1.7228, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,36.7256,7.46559,3.4456,2.23963,1.80759,1.72452],
			'sig':[20.0157,288.433,2982.33,21155.1,0,137.93,4200.35,16887.6,32973.1,43966.6,47779.8]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':1.5407, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,32.8437,6.67648,3.0814,2.0029,1.61653,1.54224],
			'sig':[5.49369,155.005,2950.28,29631.3,0,84.6666,5814.6,28265.8,55739.7,72101.7,84933]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':1.4198, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,30.2664,6.15257,2.8396,1.84573,1.48968,1.42122],
			'sig':[6.56906,228.257,5024.91,59169.5,0,155.506,12499.7,65756.6,138697,188337,217892]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':1.106, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,23.577,4.79275,2.212,1.43779,1.16044,1.10711],
			'sig':[0.255927,24.0064,1522.65,54543.4,0,39.2381,12562.8,132371,413445,727642,8914730]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':1.0802, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,23.027,4.68095,2.1604,1.40425,1.13337,1.08128],
			'sig':[0.189811,25.1966,1940.55,75954.5,0,46.8156,18364.2,200433,635389,1130760,1.35959e+07]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.3457, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,157.097,6.4917,1.3828,0.584227,0.380567,0],
			'sig':[4.79181,68.4668,722.491,5771.56,34794.7,0.798738,1352.47,21380.3,69235.2,100162,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.2656, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,120.697,4.98755,1.0624,0.448859,0.292389,0],
			'sig':[1.25434,34.1672,630.851,6726.21,39463.3,0.3425,2380.82,36525.8,79284.4,86797,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.2474, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,112.426,4.64578,0.9896,0.418102,0.272353,0],
			'sig':[1.49108,49.9956,1062.77,12899.4,89694.5,0.462455,5043.36,91066.2,237873,291452,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.129, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,58.6216,2.42241,0.516,0.218008,0.142011,0],
			'sig':[0.05767,5.07888,287.475,8456.42,111497,0.214876,15080.8,279951,151400,1231860,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.129, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,58.6216,2.42241,0.516,0.218008,0.142011,0],
			'sig':[0.042803,5.3122,365.43,11766.2,163379,0.176703,21222.6,423829,228382,1842800,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.0055, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,2.49937,0.103281,0.022,0.009295,0.006055,0],
			'sig':[9.1e-05,0.031203,6.44168,684.032,39105.1,1407.57,4632810,2616720,1052930,517782,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.0374, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,16.9957,0.702313,0.1496,0.063205,0.041172,0],
			'sig':[0.841388,11.6188,121.064,986.825,6502.88,31.284,11289.4,81614.6,99689.8,51566.5,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.0213, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,9.67937,0.39998,0.0852,0.035997,0.023448,0],
			'sig':[0.182548,4.72201,84.8162,913.745,5864.53,69.1399,18138.5,140177,2382270,1.31218e+07,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.0213, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,9.67937,0.39998,0.0852,0.035997,0.023448,0],
			'sig':[0.210071,6.65772,137.216,1672.8,12359.5,110.742,44411.8,255105,3646090,2.40888e+07,0]}] },
			'Eu':{'NSHELLS':18, 'ETERM':-0.962,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':48.519, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1034.3,210.253,97.038,63.0744,50.9071,48.5675],
			'sig':[1082.96,0,0,0,0,0.974171,74.2786,641.096,2037.96,3560.11,4002.51]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':8.052, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,171.648,34.8926,16.104,10.4675,8.44831,8.06005],
			'sig':[102.862,1447.52,12906.6,0,0,13.6051,788.036,4237.81,9688.2,14137.8,15188.8]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':7.6171, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,162.377,33.008,15.2342,9.90218,7.99201,7.62472],
			'sig':[28.4541,896.137,20760.3,0,0,2.84694,468.369,4705.22,15609,27462.2,32092.1]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':6.9769, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,148.729,30.2337,13.9538,9.06992,7.3203,6.98388],
			'sig':[32.9149,1279.88,34769.1,0,0,3.67584,859.465,9473.74,32965.3,59528.5,70212.1]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':1.8, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,38.3713,7.80013,3.6,2.33999,1.88859,1.8018],
			'sig':[21.2897,303.461,3104.04,21702.4,0,131.339,4011.77,16156.6,31568.2,42096.6,45800.5]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':1.6139, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,34.4041,6.99368,3.2278,2.09806,1.69333,1.61551],
			'sig':[6.07634,168.462,3137.87,30639.5,0,80.5751,5529.35,26960.1,53302.8,69107.1,80889.2]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':1.4806, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,31.5625,6.41604,2.9612,1.92477,1.55347,1.48208],
			'sig':[7.20968,246.911,5340.7,61623.9,0,148.135,11953.8,63179.3,133790,182081,211428]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':1.1606, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,24.741,5.02935,2.3212,1.50877,1.21772,1.16176],
			'sig':[0.293706,27.149,1690.92,59373,0,36.6632,11795,125045,392674,691059,8393960]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':1.1309, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,24.1078,4.90065,2.2618,1.47016,1.18656,1.13203],
			'sig':[0.216937,28.4228,2151.36,82561.7,0,43.5729,17289.3,189922,605157,1076520,1.27517e+07]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.3602, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,163.686,6.76398,1.4408,0.608732,0.39653,0],
			'sig':[5.11583,72.3587,756.797,5998.94,35548.2,0.771125,1304.56,20625.2,66597.2,96260,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.2839, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,129.013,5.33119,1.1356,0.479786,0.312534,0],
			'sig':[1.39358,37.3072,675.029,7056.3,40208.6,0.312349,2182.68,34230.8,75077.7,81696.9,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.2566, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,116.607,4.81854,1.0264,0.43365,0.282481,0],
			'sig':[1.64342,54.2823,1134.03,13547.3,92375.8,0.452581,4910.61,88969.9,233275,287084,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.1332, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,60.5302,2.50128,0.5328,0.225106,0.146635,0],
			'sig':[0.066679,5.77828,319.998,9173.61,116564,0.217282,14959.1,275113,149905,1111820,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.1332, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,60.5302,2.50128,0.5328,0.225106,0.146635,0],
			'sig':[0.049269,6.02835,406.215,12758.1,170930,0.176096,21010.7,416564,226318,1665860,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.00291151, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1.32308,0.054674,0.011646,0.00492,0.003205,0],
			'sig':[0.000115,0.039012,7.91907,820.722,45399.4,17581.6,5085650,1741770,1076830,847386,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.0318, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,14.4509,0.597153,0.1272,0.053741,0.035007,0],
			'sig':[0.893049,12.1991,125.938,1018.71,6625.91,46.2835,14583.2,92570.1,99155.5,59714.5,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.022, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,9.99748,0.413125,0.088,0.03718,0.024219,0],
			'sig':[0.200392,5.09999,89.8085,948.917,5960.55,67.7625,17511.7,136996,2374780,1.3462e+07,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.022, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,9.99748,0.413125,0.088,0.03718,0.024219,0],
			'sig':[0.228656,7.13864,144.625,1736.84,12636.8,107.58,43169,246648,3599110,2.47084e+07,0]}] },
			'Gd':{'NSHELLS':19, 'ETERM':-1,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':50.2391, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1070.97,217.706,100.478,65.3105,52.7118,50.2893],
			'sig':[1143.11,0,0,0,0,0.959366,71.7254,616.497,1957.81,3417.84,3844.55]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':8.3756, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,178.546,36.2949,16.7512,10.8882,8.78784,8.38398],
			'sig':[108.706,1509.59,13262.7,0,0,13.0327,752.893,4052.27,9269.2,13526.1,14527.7]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':7.9303, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,169.053,34.3652,15.8606,10.3093,8.32062,7.93823],
			'sig':[31.2972,970.748,22037,0,0,2.77001,449.688,4501.18,14910.6,26208,29811.5]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':7.2428, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,154.398,31.386,14.4856,9.41559,7.59928,7.25004],
			'sig':[35.8705,1378.49,36935.6,0,0,3.52496,821.969,9058.12,31526.7,57033.3,67089.6]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':1.8808, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,40.0937,8.15027,3.7616,2.44503,1.97337,1.88268],
			'sig':[22.6053,318.705,3224.01,22194.4,0,124.234,3824.29,15422.9,30159.1,40230.5,43631.1]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':1.6883, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,35.9901,7.31609,3.3766,2.19478,1.7714,1.68999],
			'sig':[6.70397,182.571,3325.8,31544.6,0,76.8524,5260.09,25697.6,50940.1,66192.6,77765.5]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':1.544, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,32.914,6.69078,3.088,2.00719,1.61999,1.54554],
			'sig':[7.8895,266.344,5659.06,63945.4,0,140.8,11401.4,60519.7,128701,175722,205292]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':1.2172, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,25.9475,5.27462,2.4344,1.58235,1.27711,1.21842],
			'sig':[0.335776,30.574,1868.08,64148.2,0,34.2141,11034.3,117431,370179,640742,7457940]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':1.1852, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,25.2654,5.13595,2.3704,1.54075,1.24353,1.18639],
			'sig':[0.247009,31.9363,2374.02,89178.1,0,40.2313,16143.1,178307,570634,998727,1.17904e+07]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.3758, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,170.775,7.05693,1.5032,0.635096,0.413703,0],
			'sig':[5.46481,76.5115,792.899,6229.29,36273,0.74298,1255.48,19840,64191.5,93504.5,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.2885, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,131.103,5.41757,1.154,0.48756,0.317598,0],
			'sig':[1.54828,40.7002,720.488,7362.81,40852.5,0.332672,2226.52,34165,74950.7,83071.2,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.2709, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,123.105,5.08707,1.0836,0.457816,0.298223,0],
			'sig':[1.81182,58.9971,1211.79,14245.9,95347.7,0.417873,4602.7,84913.4,227769,286891,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.1405, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,63.8475,2.63837,0.562,0.237443,0.154671,0],
			'sig':[0.077354,6.59424,357.122,9967.38,122044,0.202336,14063.8,268269,165320,712463,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.1405, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,63.8475,2.63837,0.562,0.237443,0.154671,0],
			'sig':[0.056926,6.86587,452.948,13862.3,179168,0.160692,19700.3,405766,255306,1038430,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.0092794, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,4.21685,0.174252,0.037118,0.015682,0.010215,0],
			'sig':[0.000138,0.050502,10.4638,1061.44,56876.5,267.741,3219000,2688460,642600,712302,0]},
			{'Shell':'4F7/2', 'Func':2, 'BindEnergy':0.00852419, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,3.87366,0.160071,0.034097,0.014406,0.009384,0],
			'sig':[2.2e-05,0.007653,1.61883,167.512,9102.13,59.6806,582469,432664,113484,131451,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.0361, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,16.405,0.677901,0.1444,0.061008,0.039741,0],
			'sig':[0.981479,13.3113,136.46,1096.66,7067.84,38.4085,12845.2,87107,106089,71148.1,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.0203, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,9.22494,0.381202,0.0812,0.034307,0.022348,0],
			'sig':[0.233047,5.84595,100.984,1045.94,6441.27,92.7022,20351.8,175720,2570080,1.01585e+07,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.0203, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,9.22494,0.381202,0.0812,0.034307,0.022348,0],
			'sig':[0.263996,8.17296,163.253,1930.43,13845.1,149.189,51857.5,306966,3910140,1.8497e+07,0]}] },
			'Tb':{'NSHELLS':19, 'ETERM':-1.039,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':51.9957, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1108.41,225.318,103.991,67.5941,54.5549,52.0477],
			'sig':[1205.35,0,0,0,0,0.94595,69.3186,593.315,1882.57,3287.11,3693.98]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':8.708, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,185.632,37.7353,17.416,11.3203,9.1366,8.71671],
			'sig':[114.815,1573.87,13375.8,0,0,12.5002,720.185,3880.37,8883.49,12978.5,13936.4]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':8.2516, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,175.903,35.7575,16.5032,10.727,8.65773,8.25985],
			'sig':[34.3973,1051.35,23490.7,0,0,2.69981,432.708,4317.92,14290.9,25130,29369]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':7.514, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,160.179,32.5612,15.028,9.76815,7.88383,7.52151],
			'sig':[39.0477,1484.5,39273.8,0,0,3.3851,787.803,8687.36,30263.5,54709.1,64491.1]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':1.9675, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,41.9419,8.52598,3.935,2.55774,2.06434,1.96947],
			'sig':[23.9997,334.799,3353.48,22756,0,117.801,3644.35,14739.8,28850.6,38510.2,41981.4]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':1.7677, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,37.6827,7.66016,3.5354,2.298,1.8547,1.76947],
			'sig':[7.39435,197.907,3531.17,32558.9,0,73.1972,5008.93,24554,48755.4,63337.9,75171.7]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':1.6113, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,34.3487,6.98242,3.2226,2.09468,1.69061,1.61291],
			'sig':[8.62681,287.36,6009.16,66647.3,0,133.596,10891.3,58180.1,124257,170151,197384]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':1.275, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,27.1797,5.52509,2.55,1.65749,1.33775,1.27627],
			'sig':[0.383781,34.4529,2070.81,69956.4,0,32.1262,10430.4,111924,355110,624042,7105360]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':1.2412, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,26.4591,5.37862,2.4824,1.61355,1.30229,1.24244],
			'sig':[0.281034,35.9007,2629.07,97290.9,0,37.2869,15211,169811,547589,974825,1.09446e+07]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.3979, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,180.818,7.47193,1.5916,0.672444,0.438032,0],
			'sig':[5.80675,80.4826,827.448,6460.79,36959.6,0.68606,1169.97,18663.3,60345.1,87095.2,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.3102, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,140.964,5.82506,1.2408,0.524233,0.341487,0],
			'sig':[1.7072,44.1262,766.399,7688.83,41268.1,0.283821,2007.78,31646.3,69303.9,75000.9,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.285, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,129.513,5.35185,1.14,0.481645,0.313745,0],
			'sig':[1.97988,63.5598,1285.21,14906.1,97783.3,0.387637,4321.58,81055.1,217234,268993,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.147, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,66.8013,2.76043,0.588,0.248427,0.161826,0],
			'sig':[0.088292,7.40487,392.962,10726.9,126636,0.185696,13399.8,256613,146052,902967,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.147, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,66.8013,2.76043,0.588,0.248427,0.161826,0],
			'sig':[0.064642,7.686,497.457,14906,186049,0.144533,18709.6,388001,222528,1354790,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.0094, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,4.27165,0.176517,0.0376,0.015886,0.010348,0],
			'sig':[0.000172,0.061804,12.5332,1244.16,64718.2,299.457,3195600,2391840,624618,773388,0]},
			{'Shell':'4F7/2', 'Func':2, 'BindEnergy':0.0086, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,3.9081,0.161494,0.0344,0.014534,0.009467,0],
			'sig':[5.3e-05,0.018682,3.86978,392.015,20690,135.322,1153530,769300,221515,285723,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.039, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,17.7228,0.732358,0.156,0.065909,0.042934,0],
			'sig':[1.03394,13.9011,141.431,1129.08,7199.44,33.8754,11612.3,80027.3,98025.5,66108.4,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.0254, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,11.5425,0.476972,0.1016,0.042926,0.027962,0],
			'sig':[0.254086,6.27169,106.286,1080.55,6513.52,56.7003,16049.1,111103,1789580,8258510,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.0254, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,11.5425,0.476972,0.1016,0.042926,0.027962,0],
			'sig':[0.285247,8.70331,171.063,1995.06,14106.6,88.2458,39786.8,217100,2625970,1.48892e+07,0]}] },
			'Dy':{'NSHELLS':19, 'ETERM':-1.079,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':53.7885, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1146.63,233.087,107.577,69.9247,56.4359,53.8423],
			'sig':[1269.04,0,0,0,0,0.933117,67.0328,571.2,1810.45,3159.2,3552.2]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':9.0458, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,192.833,39.1991,18.0916,11.7595,9.49102,9.05485],
			'sig':[121.073,1638.19,0,0,0,12.0056,689.449,3717.62,8515.12,12437,13368.8]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':8.5806, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,182.916,37.1832,17.1612,11.1547,9.00293,8.58918],
			'sig':[37.7271,1136.07,24637.6,0,0,2.63353,416.575,4142.22,13691.4,24045,28127.1]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':7.7901, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,166.065,33.7577,15.5802,10.1271,8.17352,7.79789],
			'sig':[42.4298,1595.16,41594.8,0,0,3.25433,755.406,8330.67,29036.6,52571.1,61865.3]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':2.0468, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,43.6324,8.86962,4.0936,2.66083,2.14754,2.04885],
			'sig':[25.4214,350.885,3476.93,23219.5,0,112.961,3499.95,14161.8,27715.1,36980.9,40356.7]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':1.8418, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,39.2624,7.98127,3.6836,2.39433,1.93245,1.84364],
			'sig':[8.131,213.815,3732.61,33409.3,0,70.5572,4805.43,23562.8,46824.8,60916.7,71674.4]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':1.6756, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,35.7194,7.26106,3.3512,2.17827,1.75807,1.67728],
			'sig':[9.41306,309.149,6356.03,69104.3,0,127.894,10452.7,56052.5,120101,164736,191838]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':1.3325, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,28.4054,5.77426,2.665,1.73224,1.39808,1.33383],
			'sig':[0.436786,38.6511,2282.51,75612.9,0,30.322,9870.32,106393,338903,594703,6478020]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':1.2949, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,27.6039,5.61133,2.5898,1.68336,1.35863,1.29619],
			'sig':[0.318683,40.1826,2893.49,105063,0,34.9681,14408.7,161739,523697,931776,1.02922e+07]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.4163, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,189.18,7.81745,1.6652,0.70354,0.458288,0],
			'sig':[6.16891,84.6835,863.45,6687.7,37538.9,0.654099,1115.98,17845.1,57640.8,83085.8,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.3318, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,150.78,6.23068,1.3272,0.560736,0.365265,0],
			'sig':[1.88587,47.8831,815.259,8020.15,41676.6,0.256207,1830.93,29529.2,65308.7,70211.6,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.2929, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,133.103,5.5002,1.1716,0.494996,0.322442,0],
			'sig':[2.16416,68.5139,1362.91,15563.1,100089,0.38895,4276.52,79927.8,214024,265998,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.1542, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,70.0732,2.89563,0.6168,0.260595,0.169753,0],
			'sig':[0.101031,8.34041,433.51,11552.5,131407,0.174231,12695.8,247717,144066,825162,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.1542, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,70.0732,2.89563,0.6168,0.260595,0.169753,0],
			'sig':[0.073626,8.63463,548.028,16047.1,193262,0.13282,17672.1,374286,220294,1239740,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.0042, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1.90861,0.078869,0.0168,0.007098,0.004624,0],
			'sig':[0.000219,0.072335,13.9175,1352.66,68482.2,7500.48,4132830,1385390,828736,883879,0]},
			{'Shell':'4F7/2', 'Func':2, 'BindEnergy':0.0042, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1.90861,0.078869,0.0168,0.007098,0.004624,0],
			'sig':[0.000139,0.043908,8.51859,845.185,43485.9,4717.45,2783730,1026050,612731,501246,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.0629, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,28.5837,1.18116,0.2516,0.1063,0.069244,0],
			'sig':[1.05231,13.9913,141.3,1124.24,7125.84,12.0562,5477.91,47303.6,71032.5,36958.8,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.0263, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,11.9515,0.493872,0.1052,0.044447,0.028953,0],
			'sig':[0.263115,6.353,105.326,1050.54,6179.1,51.8146,14368,105506,1987610,1.28972e+07,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.0263, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,11.9515,0.493872,0.1052,0.044447,0.028953,0],
			'sig':[0.289452,8.66674,167.292,1923.85,13377,79.1424,35618.5,194357,2880930,2.35359e+07,0]}] },
			'Ho':{'NSHELLS':19, 'ETERM':-1.119,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':55.6177, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1185.62,241.014,111.235,72.3026,58.3551,55.6733],
			'sig':[1334.61,0,0,0,0,0.921625,64.8668,550.196,1742.12,3040.19,3414.99]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':9.3942, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,200.26,40.7089,18.7884,12.2124,9.85657,9.40359],
			'sig':[127.541,1703.47,0,0,0,11.5333,660.078,3562.11,8163.54,11921.4,12839]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':8.9178, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,190.104,38.6445,17.8356,11.5931,9.35672,8.92672],
			'sig':[41.3183,1225.85,0,0,0,2.57156,401.452,3977.12,13127.6,23027.8,27011.9]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':8.0711, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,172.055,34.9754,16.1422,10.4924,8.46835,8.07917],
			'sig':[46.0264,1711.56,44107.8,0,0,3.13175,725.036,7996.14,27882.3,50455.7,59582.2]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':2.1283, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,45.3698,9.22279,4.2566,2.76678,2.23305,2.13043],
			'sig':[26.8941,367.327,3601.06,23651.2,0,108.356,3362,13608.3,26627.5,35508.3,38797.9]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':1.9228, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,40.9891,8.33227,3.8456,2.49963,2.01744,1.92472],
			'sig':[8.92686,230.693,3941.91,34243.9,0,67.2341,4589.65,22539.3,44850.5,58392.8,69366.3]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':1.7412, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,37.1178,7.54533,3.4824,2.26355,1.8269,1.74294],
			'sig':[10.2482,331.991,6713.11,71558.1,0,122.531,10040.1,54037.6,116146,159646,188161]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':1.3915, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,29.6631,6.02993,2.783,1.80894,1.45999,1.39289],
			'sig':[0.495855,43.2558,2510.43,81572.3,0,28.6561,9351.13,101241,323746,568443,6167650]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':1.3514, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,28.8083,5.85617,2.7028,1.75681,1.41791,1.35275],
			'sig':[0.360296,44.869,3179.04,113356,0,32.678,13619.7,153860,500478,889989,9361720]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.4357, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,197.995,8.18175,1.7428,0.736326,0.479645,0],
			'sig':[6.54965,89.0066,899.932,6912.59,38045.3,0.623715,1062.71,17037.9,54990.2,79177.1,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.3435, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,156.097,6.45038,1.374,0.580509,0.378146,0],
			'sig':[2.07605,51.7957,864.183,8324.96,41912.6,0.255674,1787.68,28664.5,63006.2,67616.2,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.3066, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,139.328,5.75746,1.2264,0.518149,0.337524,0],
			'sig':[2.36102,73.7349,1444.1,16252.6,102490,0.350761,4059.06,76799,207235,258289,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.161, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,73.1634,3.02332,0.644,0.272087,0.177239,0],
			'sig':[0.115379,9.36776,476.764,12403.8,135893,0.166401,12151.8,239900,141879,761919,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.161, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,73.1634,3.02332,0.644,0.272087,0.177239,0],
			'sig':[0.083694,9.67334,601.872,17223.3,200079,0.124392,16865.4,362281,217465,1146450,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.0037, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1.68139,0.06948,0.0148,0.006253,0.004073,0],
			'sig':[0.000267,0.087515,16.5284,1573.18,77197.4,13586.2,3802450,1208610,892396,1131810,0]},
			{'Shell':'4F7/2', 'Func':2, 'BindEnergy':0.0037, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1.68139,0.06948,0.0148,0.006253,0.004073,0],
			'sig':[0.00021,0.066187,12.6179,1226.53,61204.3,10686.1,3229000,1132930,786885,737857,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.0512, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,23.2669,0.961455,0.2048,0.086527,0.056364,0],
			'sig':[1.10694,14.5888,146.122,1151.68,7187.4,19.6704,7636.68,57470.5,72151.3,45606.9,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.0203, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,9.22494,0.381202,0.0812,0.034307,0.022348,0],
			'sig':[0.28634,6.8015,110.562,1080.75,6214.21,101.692,18338.1,212051,3549130,2.03666e+07,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.0203, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,9.22494,0.381202,0.0812,0.034307,0.022348,0],
			'sig':[0.311033,9.19705,174.799,1979.67,13542.6,159.988,48520.7,316385,5354900,3.7786e+07,0]}] },
			'Er':{'NSHELLS':19, 'ETERM':-1.161,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':57.4855, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1225.44,249.108,114.971,74.7308,60.3149,57.543],
			'sig':[1402.23,0,0,0,0,0.910494,62.8086,530.176,1676.71,2924.08,3286.57]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':9.7513, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,207.872,42.2563,19.5026,12.6766,10.2312,9.76105],
			'sig':[134.225,1769.51,0,0,0,11.0919,632.329,3414.58,7830.03,11448.8,12303.9]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':9.2643, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,197.491,40.146,18.5286,12.0435,9.72028,9.27356],
			'sig':[45.1934,1320.92,0,0,0,2.51335,387.176,3820.94,12594.4,22104.4,25883.6]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':8.3579, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,178.169,36.2182,16.7158,10.8652,8.76927,8.36626],
			'sig':[49.8605,1834.04,46768.1,0,0,3.0166,696.404,7680.22,26794,48556,57260.2]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':2.2065, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,47.0368,9.56166,4.413,2.86844,2.3151,2.20871],
			'sig':[28.4245,384.056,3723.59,24031.4,0,104.604,3244.12,13121.6,25649.2,34204.8,37387.2]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':2.0058, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,42.7584,8.69195,4.0116,2.60753,2.10452,2.00781],
			'sig':[9.78788,248.512,4155.96,35022.6,0,64.4949,4388.03,21574.4,42972.7,55936.1,66895.4]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':1.8118, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,38.6228,7.85127,3.6236,2.35533,1.90097,1.81361],
			'sig':[11.1441,356.092,7084.56,74073.6,0,116.85,9610.55,51969.5,112101,154344,183118]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':1.4533, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,30.9806,6.29774,2.9066,1.88928,1.52483,1.45475],
			'sig':[0.561815,48.3106,2756.41,87908.3,0,27.0312,8847.35,96264.1,309125,542705,5805500]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':1.4093, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,30.0426,6.10707,2.8186,1.83208,1.47866,1.41071],
			'sig':[0.406346,49.9847,3485.59,122086,0,30.5725,12886.5,146503,478717,852600,8976750]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.4491, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,204.085,8.43338,1.7964,0.758971,0.494396,0],
			'sig':[6.93704,93.375,936.192,7123.01,38406.9,0.617027,1041.07,16609.8,53253.5,76497.2,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.3662, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,166.413,6.87665,1.4648,0.618872,0.403135,0],
			'sig':[2.28188,55.9662,915.904,8649.78,42045.2,0.232939,1638.24,26802.6,59393.1,63320.2,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.32, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,145.418,6.00909,1.28,0.540795,0.352275,0],
			'sig':[2.57316,79.228,1527.53,16944.2,104755,0.332286,3873.15,74026.2,201023,251265,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.1767, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,80.2979,3.31815,0.7068,0.29862,0.194522,0],
			'sig':[0.131258,10.4976,524.155,13348.2,140833,0.129287,10204.2,221112,141987,671700,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.1676, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,76.1626,3.14726,0.6704,0.283241,0.184504,0],
			'sig':[0.094728,10.8005,659.166,18436.4,206537,0.11773,16194.7,351368,214191,1068540,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.0043, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1.95405,0.080747,0.0172,0.007267,0.004734,0],
			'sig':[0.000327,0.105457,19.513,1820.59,86677.7,9084.1,3613570,1161610,818143,1083410,0]},
			{'Shell':'4F7/2', 'Func':2, 'BindEnergy':0.0043, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1.95405,0.080747,0.0172,0.007267,0.004734,0],
			'sig':[0.000307,0.095434,17.8338,1700.11,82362.4,8540.37,3669610,1304630,859613,804831,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.0598, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,27.175,1.12295,0.2392,0.101061,0.065831,0],
			'sig':[1.16628,15.2216,151.309,1184.74,7322.17,14.6506,6117.94,48891,66023.3,41461.6,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.0294, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,13.3603,0.552085,0.1176,0.049686,0.032365,0],
			'sig':[0.312212,7.2853,116.162,1114.95,6270.96,43.9072,12625.1,90044.6,1784280,1.25721e+07,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.0294, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,13.3603,0.552085,0.1176,0.049686,0.032365,0],
			'sig':[0.334919,9.76586,182.851,2044.66,13802.1,65.2826,31433.4,168210,2505130,2.28294e+07,0]}] },
			'Tm':{'NSHELLS':19, 'ETERM':-1.204,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':59.3896, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1266.03,257.359,118.779,77.2061,62.3127,59.449],
			'sig':[1471.39,0,0,0,0,0.900794,60.8579,511.149,1614.7,2815.89,3162.2]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':10.1157, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,215.64,43.8354,20.2314,13.1503,10.6136,10.1258],
			'sig':[141.088,1836.07,0,0,0,10.677,606.148,3275.28,7513.66,10981.3,11814.1]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':9.6169, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,205.007,41.6739,19.2338,12.5019,10.0902,9.62652],
			'sig':[49.3521,1421.06,0,0,0,2.46012,373.953,3675.54,12095.4,21194.7,24834.6]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':8.648, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,184.353,37.4753,17.296,11.2423,9.07365,8.65665],
			'sig':[53.9229,1962.26,48693.2,0,0,2.91011,669.808,7385.81,25773.7,46685.1,55122]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':2.3068, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,49.1749,9.9963,4.6136,2.99882,2.42034,2.30911],
			'sig':[30.0097,401.449,3854.01,24460.3,0,98.967,3083.91,12506.7,24474.6,32640.4,35710.5]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':2.0898, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,44.5491,9.05595,4.1796,2.71673,2.19266,2.09189],
			'sig':[10.7099,267.222,4373.77,35729.5,0,62.0312,4203.4,20678.1,41215.6,53704.4,63454.3]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':1.8845, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,40.1726,8.1663,3.769,2.44984,1.97725,1.88638],
			'sig':[12.0934,381.321,7467.22,76588.1,0,110.84,9201.05,49991,108227,149432,174450]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':1.5146, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,32.2873,6.56338,3.0292,1.96897,1.58915,1.51611],
			'sig':[0.634686,53.8141,3018.67,94442.4,0,25.6605,8411.94,91863.4,295954,518979,5293580]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':1.4677, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,31.2875,6.36014,2.9354,1.908,1.53994,1.46917],
			'sig':[0.457369,55.5603,3813.18,131185,0,28.7138,12225.7,139788,458624,816952,8491170]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.4717, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,214.355,8.85778,1.8868,0.797165,0.519276,0],
			'sig':[7.33888,97.8807,973.763,7345.05,38792.2,0.582199,982.923,15753.3,50548.6,72527.2,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.3859, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,175.365,7.24659,1.5436,0.652164,0.424822,0],
			'sig':[2.50547,60.366,968.579,8961.89,42031.1,0.220133,1537.44,25404.3,56425.7,59866.6,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.3366, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,152.961,6.32081,1.3464,0.568848,0.37055,0],
			'sig':[2.79648,84.9697,1614.07,17656.4,106992,0.306047,3628.44,70536.4,193485,242423,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.1796, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,81.6158,3.3726,0.7184,0.303521,0.197715,0],
			'sig':[0.14881,11.7135,572.791,14228.7,144490,0.137195,10440.7,219469,138376,642768,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.1796, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,81.6158,3.3726,0.7184,0.303521,0.197715,0],
			'sig':[0.106935,12.033,721.105,19745.8,213307,0.097865,14379.4,330647,213969,969476,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.0053, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,2.40848,0.099526,0.0212,0.008957,0.005835,0],
			'sig':[0.000395,0.125986,22.9035,2096.22,96838.8,4822.57,3442960,1159070,719061,957709,0]},
			{'Shell':'4F7/2', 'Func':2, 'BindEnergy':0.0053, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,2.40848,0.099526,0.0212,0.008957,0.005835,0],
			'sig':[0.000437,0.133366,24.3661,2279.2,107211,5262.51,4053070,1512070,890228,796651,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.0532, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,24.1757,0.999011,0.2128,0.089907,0.058566,0],
			'sig':[1.22701,15.855,156.278,1212.51,7389.15,19.6424,7400.31,53884.4,65175.8,49021.1,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.0323, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,14.6781,0.606543,0.1292,0.054586,0.035558,0],
			'sig':[0.338816,7.7806,121.763,1146.57,6304.62,36.6903,11354.3,76200.6,1554980,1.16416e+07,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.0323, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,14.6781,0.606543,0.1292,0.054586,0.035558,0],
			'sig':[0.35996,10.3489,190.831,2105,14006.3,53.4861,28089.1,148433,2130200,2.10171e+07,0]}] },
			'Yb':{'NSHELLS':19, 'ETERM':-1.248,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':61.3323, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1307.44,265.778,122.665,79.7316,64.351,61.3936],
			'sig':[1541.72,0,0,0,0,0.891276,59.0039,493.002,1555.28,2710.34,3045.12]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':10.4864, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,223.543,45.4418,20.9728,13.6323,11.0025,10.4969],
			'sig':[148.159,1903.05,0,0,0,10.2957,581.686,3144.11,7215.61,10556.7,11334.2]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':9.9782, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,212.709,43.2396,19.9564,12.9716,10.4693,9.98818],
			'sig':[53.8273,1526.74,0,0,0,2.41082,361.533,3538.26,11624.1,20376,23828.7]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':8.9436, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,190.654,38.7563,17.8872,11.6266,9.38379,8.95254],
			'sig':[58.2434,2096.82,0,0,0,2.81024,644.728,7107.53,24811,44999.6,53053]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':2.3981, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,51.1212,10.3919,4.7962,3.11751,2.51613,2.4005],
			'sig':[31.6498,419.014,3980.24,24817.1,0,94.8273,2958.56,12004.4,23485.4,31333.7,34275.4]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':2.173, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,46.3227,9.41649,4.346,2.82489,2.27995,2.17517],
			'sig':[11.6993,286.826,4593.76,36350.1,0,59.9592,4040.46,19866.2,39596.7,51595.8,61729.1]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':1.9498, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,41.5646,8.44928,3.8996,2.53473,2.04577,1.95175],
			'sig':[13.0981,407.447,7849.08,78921,0,107.206,8900.72,48445.7,105082,145282,172125]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':1.5763, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,33.6026,6.83075,3.1526,2.04918,1.65388,1.57788],
			'sig':[0.715344,59.8062,3298.46,101215,0,24.4503,8020.99,87857.6,283851,498112,5105320]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':1.5278, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,32.5687,6.62058,3.0556,1.98613,1.603,1.52933],
			'sig':[0.513392,61.6185,4163.96,140750,0,26.9675,11601.7,133430,439541,782702,7711610]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.4872, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,221.399,9.14884,1.9488,0.82336,0.536339,0],
			'sig':[7.75942,102.477,1010.94,7549.7,39027.4,0.573738,957.574,15289,48781.7,69840.4,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.3967, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,180.273,7.4494,1.5868,0.670416,0.436711,0],
			'sig':[2.74266,64.9364,1021.22,9246.31,41915.9,0.224003,1520.11,24818.7,54561.5,57819.7,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.3435, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,156.097,6.45038,1.374,0.580509,0.378146,0],
			'sig':[3.03557,90.9326,1700.32,18316.3,108793,0.312239,3632.25,70013.8,191273,240423,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.1981, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,90.0227,3.72,0.7924,0.334786,0.21808,0],
			'sig':[0.168597,13.0655,627.023,15258.5,148995,0.104631,8614.63,200359,139437,566869,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.1849, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,84.0242,3.47213,0.7396,0.312478,0.203549,0],
			'sig':[0.120509,13.3664,785.54,21021,218893,0.097044,14176.2,323828,209292,922033,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.0063, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,2.86291,0.118304,0.0252,0.010647,0.006935,0],
			'sig':[0.000478,0.150039,26.7413,2401.42,107613,2872.09,3231040,1160470,645745,861925,0]},
			{'Shell':'4F7/2', 'Func':2, 'BindEnergy':0.0063, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,2.86291,0.118304,0.0252,0.010647,0.006935,0],
			'sig':[0.000601,0.180948,32.4297,2977.81,135967,3564.33,4325050,1725410,922834,786039,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.0541, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,24.5847,1.01591,0.2164,0.091428,0.059556,0],
			'sig':[1.28677,16.4927,161.412,1242.09,7478.63,19.698,7301.85,52230.4,62098.7,51460.8,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.0234, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,10.6337,0.439415,0.0936,0.039546,0.02576,0],
			'sig':[0.368141,8.30017,127.265,1173.85,6308.04,84.3703,15436.2,179142,3209780,2.0651e+07,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.0234, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,10.6337,0.439415,0.0936,0.039546,0.02576,0],
			'sig':[0.384862,10.9296,198.542,2156.73,14119.8,128.185,41605.4,259133,4670220,3.80349e+07,0]}] },
			'Lu':{'NSHELLS':19, 'ETERM':-1.293,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':63.3138, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1349.68,274.364,126.628,82.3075,66.43,63.3771],
			'sig':[1613.49,0,0,0,0,0.883233,57.2371,475.654,1498.61,2611.31,2931]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':10.8704, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,231.728,47.1059,21.7408,14.1314,11.4054,10.8813],
			'sig':[155.393,1970.14,0,0,0,9.9206,557.767,3016.22,6924.04,10125.5,10887.1]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':10.3486, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,220.605,44.8447,20.6972,13.4531,10.8579,10.3589],
			'sig':[58.6059,1637.08,0,0,0,2.36311,349.59,3405.75,11166.2,19539.6,22904.4]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':9.2441, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,197.06,40.0584,18.4882,12.0173,9.69908,9.25334],
			'sig':[62.794,2236.17,0,0,0,2.71536,620.747,6838.92,23871.2,43283.6,51212.6]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':2.4912, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,53.1059,10.7954,4.9824,3.23854,2.61381,2.49369],
			'sig':[33.3202,436.624,4102.15,25088.8,0,90.3469,2837.82,11514.2,22520.4,30028.7,32739.8]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':2.2635, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,48.2519,9.80866,4.527,2.94254,2.37491,2.26576],
			'sig':[12.7612,307.311,4814.4,36885.4,0,57.6274,3863.49,19000.8,37902.2,49390.7,59108.8]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':2.0236, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,43.1379,8.76908,4.0472,2.63067,2.1232,2.02562],
			'sig':[14.1667,434.67,8237.32,81203.2,0,102.608,8537.14,46617.8,101414,140450,166391]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':1.6394, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,34.9477,7.10419,3.2788,2.13121,1.72009,1.64104],
			'sig':[0.80412,66.2429,3587.74,107705,0,23.3029,7631.87,83671.5,270692,470974,4747010]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':1.5885, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,33.8627,6.88362,3.177,2.06504,1.66668,1.59009],
			'sig':[0.574538,68.0976,4525.44,149874,0,25.3744,10999.2,126918,419047,740054,7348300]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.5062, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,230.033,9.50563,2.0248,0.855469,0.557256,0],
			'sig':[8.19799,107.265,1049.34,7751.49,39244.8,0.527745,922.144,14694.9,46854.3,67806.1,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.4101, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,186.362,7.70103,1.6404,0.693062,0.451463,0],
			'sig':[3.00205,69.8311,1076.06,9526.98,41866.4,0.224305,1484.57,24069.8,53115.8,57030.2,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.3593, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,163.277,6.74708,1.4372,0.607211,0.395539,0],
			'sig':[3.29422,97.3661,1793.27,19027.5,110932,0.293063,3441.92,67151.7,186272,238990,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.2048, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,93.0674,3.84582,0.8192,0.346109,0.225456,0],
			'sig':[0.190909,14.5593,684.131,16224.4,152659,0.099877,8417,196324,150398,419206,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.195, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,88.614,3.66179,0.78,0.329547,0.214668,0],
			'sig':[0.135901,14.8691,857.072,22396.7,225082,0.086545,13099.8,310840,230789,645990,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.0069, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,3.13557,0.129571,0.0276,0.011661,0.007596,0],
			'sig':[0.000549,0.180792,32.543,2858.24,123095,2413.56,3257710,1017190,744482,1443660,0]},
			{'Shell':'4F7/2', 'Func':2, 'BindEnergy':0.0069, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,3.13557,0.129571,0.0276,0.011661,0.007596,0],
			'sig':[0.000655,0.215257,39.6647,3566.22,156586,3008.99,4377750,1460490,957146,1859930,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.0568, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,25.8117,1.06661,0.2272,0.095991,0.062529,0],
			'sig':[1.39114,17.712,172.23,1314.03,7828.32,19.0485,7102.07,51647.8,66721.9,55492.9,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.028, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,12.7241,0.525795,0.112,0.04732,0.030824,0],
			'sig':[0.419142,9.31658,140.337,1269.65,6687.05,60.9941,13675.3,119010,2060830,9758690,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.028, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,12.7241,0.525795,0.112,0.04732,0.030824,0],
			'sig':[0.437313,12.2985,220.535,2363.43,15287.6,90.7494,36299.1,200420,2854340,1.76178e+07,0]}] },
			'Hf':{'NSHELLS':20, 'ETERM':-1.338,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':65.3508, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1393.11,283.192,130.702,84.9556,68.5673,65.4162],
			'sig':[1688.2,0,0,0,0,0.874796,55.5282,458.902,1443.76,2514.03,2823.04]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':11.2707, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,240.262,48.8405,22.5414,14.6518,11.8254,11.282],
			'sig':[162.862,2038.15,0,0,0,9.50246,534.485,2891.83,6642.31,9725.18,10437]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':10.7394, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,228.936,46.5382,21.4788,13.9611,11.268,10.7501],
			'sig':[63.7537,1754.6,0,0,0,2.31085,337.441,3274.01,10717.6,18738.5,21985.8]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':9.5607, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,203.809,41.4304,19.1214,12.4288,10.0313,9.57026],
			'sig':[67.6439,2383.94,0,0,0,2.61657,596.337,6570.36,22947.2,41677.6,49231.2]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':2.6009, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,55.4444,11.2708,5.2018,3.38115,2.72891,2.6035],
			'sig':[35.0507,454.803,4229.04,25362.3,0,85.5043,2697.14,10965.4,21466.5,28631.3,31063.2]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':2.3654, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,50.4241,10.2502,4.7308,3.075,2.48182,2.36777],
			'sig':[13.8977,328.929,5043.81,37395.7,0,54.8441,3668.77,18083.7,36142.6,47197.6,55615.5]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':2.1076, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,44.9285,9.13309,4.2152,2.73987,2.21133,2.10971],
			'sig':[15.2976,463.294,8645.3,83623.2,0,97.0692,8123.26,44606.1,97459.6,135487,157065]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':1.7164, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,36.5892,7.43786,3.4328,2.23131,1.80088,1.71812],
			'sig':[0.902078,73.3129,3907.99,115234,0,21.6249,7123.05,78621.8,255715,441644,4246290]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':1.6617, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,35.4231,7.20082,3.3234,2.1602,1.74349,1.66336],
			'sig':[0.642105,75.2016,4923.74,160372,0,23.2588,10237.4,119206,395984,693805,6792580]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.5381, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,244.529,10.1047,2.1524,0.90938,0.592373,0],
			'sig':[8.65831,112.285,1090.13,7975.21,39552.9,0.480294,849.728,13673.6,44007,64164,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.437, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,198.586,8.20617,1.748,0.738523,0.481076,0],
			'sig':[3.28429,75.095,1134.99,9836.73,41694.1,0.205113,1359.13,22479.2,50541.5,54532.5,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.3804, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,172.865,7.14331,1.5216,0.64287,0.418767,0],
			'sig':[3.57296,104.23,1892.04,19789.2,113294,0.264104,3174.73,63355.3,179580,234114,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.2238, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,101.702,4.20261,0.8952,0.378218,0.246373,0],
			'sig':[0.216102,16.2323,748.214,17346.5,157134,0.078532,7099.69,181098,164955,298311,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.2137, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,97.1118,4.01295,0.8548,0.361149,0.235254,0],
			'sig':[0.153188,16.5431,936.577,23953.7,232305,0.06262,10912.8,285928,257060,446284,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.0171, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,7.77077,0.321111,0.0684,0.028899,0.018825,0],
			'sig':[0.000668,0.220822,39.3832,3398.26,141960,71.2155,1770790,1856730,476388,709763,0]},
			{'Shell':'4F7/2', 'Func':2, 'BindEnergy':0.0171, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,7.77077,0.321111,0.0684,0.028899,0.018825,0],
			'sig':[0.00079,0.262668,48.0901,4250.57,181162,87.1912,2318390,2598050,641885,975641,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.0649, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,29.4926,1.21872,0.2596,0.10968,0.071446,0],
			'sig':[1.51112,19.0875,184.36,1395.63,8246.86,15.4165,6106.86,47050,67087.8,55035.6,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.0381, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,17.3138,0.715457,0.1524,0.064388,0.041943,0],
			'sig':[0.47728,10.4594,154.856,1375.18,7105.66,31.8035,10495.1,64203.3,1095130,5265650,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.0306, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,13.9056,0.574619,0.1224,0.051714,0.033686,0],
			'sig':[0.495674,13.8011,244.304,2582.97,16523.8,80.3887,35074.5,189363,2306190,1.24633e+07,0]},
			{'Shell':'5D3/2', 'Func':2, 'BindEnergy':0.005, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,2.27215,0.093892,0.02,0.00845,0.005504,0],
			'sig':[0.005636,0.354511,14.7646,333.032,3140.32,648.28,102470,7361420,1.1662e+07,1.23846e+07,0]}] },
			'Ta':{'NSHELLS':20, 'ETERM':-1.385,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':67.4164, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1437.14,292.143,134.833,87.6409,70.7346,67.4838],
			'sig':[1764.08,0,0,0,0,0.868328,53.9224,443.058,1391.93,2423.33,2718.73]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':11.6815, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,249.019,50.6207,23.363,15.1859,12.2565,11.6932],
			'sig':[170.51,2106.44,0,0,0,9.15232,511.63,2773.24,6372.74,9331.02,10000.8]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':11.1361, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,237.392,48.2572,22.2722,14.4769,11.6842,11.1472],
			'sig':[69.2645,1877.57,0,0,0,2.26494,326.307,3151.53,10298.1,18016.5,20370]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':9.8811, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,210.639,42.8188,19.7622,12.8454,10.3674,9.89098],
			'sig':[72.7586,2537.9,0,0,0,2.52462,573.538,6318.84,22075.8,40093.8,47404.6]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':2.708, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,57.7275,11.7349,5.416,3.52038,2.84128,2.71071],
			'sig':[36.84,473.192,4352.82,25634.1,0,81.4039,2574.12,10475.6,20512.1,27388.7,29542]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':2.4687, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,52.6262,10.6979,4.9374,3.20929,2.59021,2.47117],
			'sig':[15.1125,351.514,5274.74,37790,0,52.0739,3491.1,17234.5,34495.3,45095.2,53710.7]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':2.194, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,46.7703,9.50749,4.388,2.85219,2.30199,2.19619],
			'sig':[16.5007,493.183,9062.79,86019,0,91.911,7732.41,42691.4,93661.7,130547,151170]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':1.7932, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,38.2263,7.77066,3.5864,2.33115,1.88146,1.79499],
			'sig':[1.00969,80.95,4246.05,122892,0,20.2029,6680.41,74131.8,242188,416389,3998760]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':1.7351, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,36.9878,7.51889,3.4702,2.25562,1.8205,1.73684],
			'sig':[0.715727,82.85,5344.45,171114,0,21.4328,9566.49,112277,374942,652197,6060170]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.5655, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,256.981,10.6192,2.262,0.955685,0.622537,0],
			'sig':[9.13685,117.435,1131.15,8187.01,39774.8,0.450499,800.082,12929.4,41821.4,61330.8,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.4648, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,211.219,8.72821,1.8592,0.785504,0.51168,0],
			'sig':[3.5921,80.6878,1195.9,10142.8,41449.9,0.189176,1248.69,21034.2,48140.9,52246.7,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.4045, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,183.817,7.59587,1.618,0.683598,0.445298,0],
			'sig':[3.87173,111.501,1995.66,20583.1,115725,0.234615,2898.2,59393,172378,228287,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.2413, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,109.654,4.53123,0.9652,0.407793,0.265638,0],
			'sig':[0.244224,18.067,816.785,18500.5,161460,0.06521,6196.16,169042,178055,224480,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.2293, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,104.201,4.30589,0.9172,0.387513,0.252427,0],
			'sig':[0.172409,18.3737,1021.24,25537.4,239193,0.051505,9607.1,268493,279922,331132,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.025, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,11.3608,0.46946,0.1,0.04225,0.027522,0],
			'sig':[0.000816,0.268452,47.1837,3992.98,161294,15.8367,1023420,2180540,449507,567392,0]},
			{'Shell':'4F7/2', 'Func':2, 'BindEnergy':0.025, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,11.3608,0.46946,0.1,0.04225,0.027522,0],
			'sig':[0.000959,0.318981,57.6664,5002.07,206290,19.2783,1330570,3008530,611872,797209,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.0711, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,32.31,1.33514,0.2844,0.120158,0.078271,0],
			'sig':[1.6404,20.5572,197.213,1480.76,8680.73,13.6645,5590.11,44458,67152.6,56622.5,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.0449, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,20.4039,0.843151,0.1796,0.07588,0.049429,0],
			'sig':[0.541975,11.7062,170.307,1483.92,7528.13,23.3909,9218.46,50637.6,783714,3727580,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.0364, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,16.5413,0.683534,0.1456,0.061515,0.040071,0],
			'sig':[0.56123,15.4432,269.733,2815.32,17838.5,56.7247,30256.5,162222,1595020,8489140,0]},
			{'Shell':'5D3/2', 'Func':2, 'BindEnergy':0.0057, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,2.59026,0.107037,0.0228,0.009633,0.006275,0],
			'sig':[0.011507,0.728107,30.0322,661.442,6055.98,944.121,119037,1.16225e+07,1.48829e+07,1.25247e+07,0]}] },
			'W':{'NSHELLS':20, 'ETERM':-1.433,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':69.525, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1482.09,301.28,139.05,90.382,72.9469,69.5945],
			'sig':[1839.59,0,0,0,0,0.861603,52.3897,427.892,1342.07,2334.81,2620.14]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':12.0998, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,257.936,52.4333,24.1996,15.7297,12.6953,12.1119],
			'sig':[178.336,2174.81,0,0,0,8.82646,490.719,2661.26,6117.27,8952,9617.08]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':11.544, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,246.088,50.0248,23.088,15.0071,12.1122,11.5555],
			'sig':[75.1552,2006.75,0,0,0,2.2083,315.302,3034.93,9898.47,17287.4,19599]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':10.2068, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,217.582,44.2302,20.4136,13.2688,10.7092,10.217],
			'sig':[78.169,2698.55,0,0,0,2.43909,552.123,6081.45,21254.2,38657.4,45660.6]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':2.8196, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,60.1065,12.2185,5.6392,3.66546,2.95838,2.82242],
			'sig':[38.6691,491.845,4476.15,25778.7,0,77.4272,2455.25,10003.3,19595.5,26147.5,28204.7]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':2.5749, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,54.8901,11.1581,5.1498,3.34735,2.70163,2.57747],
			'sig':[16.4159,375.142,5507.76,38107.6,0,49.7714,3324.68,16432.9,32928.4,43064.9,51348.9]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':2.281, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,48.6249,9.8845,4.562,2.96528,2.39327,2.28328],
			'sig':[17.7658,524.186,9487.11,88367.6,0,87.2588,7375.7,40920.2,90119,125967,147796]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':1.8716, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,39.8976,8.1104,3.7432,2.43307,1.96372,1.87347],
			'sig':[1.12826,89.2119,4604.43,130793,0,18.8366,6276.4,69987.9,229587,393426,3693190]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':1.8092, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,38.5674,7.84,3.6184,2.35195,1.89825,1.81101],
			'sig':[0.796106,91.0867,5788.83,182139,0,19.8287,8965.35,105974,355593,616300,5715920]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.595, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,270.386,11.1732,2.38,1.00554,0.655012,0],
			'sig':[9.6418,122.773,1173.08,8399.04,39935.6,0.421602,751.282,12201.4,39692.8,58542,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.4916, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,223.398,9.23147,1.9664,0.830796,0.541183,0],
			'sig':[3.92076,86.5612,1258.35,10439.9,41147.6,0.177314,1160.64,19814.2,46024.1,50295,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.4253, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,193.269,7.98646,1.7012,0.71875,0.468196,0],
			'sig':[4.19067,119.129,2102.09,21368.9,118119,0.216527,2712.24,56548.5,167151,224852,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.2588, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,117.607,4.85985,1.0352,0.437368,0.284903,0],
			'sig':[0.275549,20.0755,890.19,19696.6,165692,0.055269,5477.47,158390,189602,177491,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.2454, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,111.517,4.60822,0.9816,0.414722,0.270151,0],
			'sig':[0.193729,20.3752,1112,27188.5,246115,0.042908,8504.04,252342,300490,259115,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.0365, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,16.5867,0.685412,0.146,0.061684,0.040181,0],
			'sig':[0.000991,0.324058,56.1427,4666.75,182839,3.27545,496493,2512080,442646,433334,0]},
			{'Shell':'4F7/2', 'Func':2, 'BindEnergy':0.0336, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,15.2689,0.630955,0.1344,0.056783,0.036989,0],
			'sig':[0.001164,0.385088,68.5707,5836.61,232993,5.84087,776562,3326170,600367,668056,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.0771, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,35.0366,1.44782,0.3084,0.130298,0.084876,0],
			'sig':[1.7779,22.106,210.645,1568.56,9127.76,12.3787,5189.84,42301.6,66690.7,58239.9,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.0468, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,21.2674,0.87883,0.1872,0.079091,0.05152,0],
			'sig':[0.614716,13.0612,186.514,1593.65,7943.89,23.3992,9255.58,50394.6,732290,3191620,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.0356, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,16.1777,0.668511,0.1424,0.060163,0.039191,0],
			'sig':[0.630772,17.1804,296.237,3050.07,19139.9,66.5594,33376.7,178938,1679720,7773800,0]},
			{'Shell':'5D3/2', 'Func':2, 'BindEnergy':0.0061, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,2.77203,0.114548,0.0244,0.010309,0.006715,0],
			'sig':[0.019813,1.2519,50.9601,1095.76,9751.23,1327.14,150278,1.63717e+07,1.73529e+07,1.27071e+07,0]}] },
			'Re':{'NSHELLS':21, 'ETERM':-1.482,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':71.6764, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1527.95,310.603,143.353,93.1788,75.2042,71.7481],
			'sig':[1915.94,0,0,0,0,0.856772,50.9275,413.388,1294.55,2251.55,2524.55]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':12.5267, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,267.036,54.2833,25.0534,16.2846,13.1433,12.5392],
			'sig':[186.363,2243.05,0,0,0,8.52172,470.999,2555.02,5874.97,8606.57,9233.93]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':11.9587, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,254.928,51.8219,23.9174,15.5462,12.5473,11.9707],
			'sig':[81.4502,2141.64,0,0,0,2.16743,305.454,2925.9,9523.16,16639,18821.6]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':10.5353, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,224.585,45.6537,21.0706,13.6958,11.0538,10.5458],
			'sig':[83.8584,2865.33,0,0,0,2.35974,532.164,5859.45,20479,37230.5,42373.4]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':2.9317, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,62.4962,12.7042,5.8634,3.81119,3.076,2.93463],
			'sig':[40.5476,510.697,4597.08,25755.3,0,73.8408,2346.29,9565.46,18739.3,25000.2,26851.6]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':2.6816, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,57.1647,11.6205,5.3632,3.48606,2.81359,2.68428],
			'sig':[17.7997,399.694,5740.3,38368.5,0,47.7428,3174.26,15695.8,31477.2,41229.5,48126.6]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':2.3673, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,50.4646,10.2585,4.7346,3.07747,2.48382,2.36967],
			'sig':[19.0996,556.301,9915.43,90657.9,0,83.2026,7056.9,39308.4,86865.2,121819,139127]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':1.9489, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,41.5454,8.44538,3.8978,2.53356,2.04482,1.95085],
			'sig':[1.25757,98.0826,4979.8,138712,0,17.7672,5929.14,66329.9,218231,373205,3301170]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':1.8829, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,40.1385,8.15937,3.7658,2.44776,1.97557,1.88478],
			'sig':[0.884033,99.9367,6255.14,193281,0,18.3719,8438.24,100325,337943,584597,5269130]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.625, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,284.019,11.7365,2.5,1.05624,0.688038,0],
			'sig':[10.1583,128.224,1215.59,8605.82,40085.9,0.396186,707.321,11537.1,37729.2,55959.3,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.5179, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,235.35,9.72534,2.0716,0.875242,0.570136,0],
			'sig':[4.27405,92.7415,1322.24,10726.3,40762.2,0.159107,1087.44,18750.3,44108.5,48576.1,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.4444, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,201.949,8.34513,1.7776,0.751028,0.489222,0],
			'sig':[4.53424,127.161,2211.55,22153.6,120494,0.204284,2572.77,54298.7,162975,222608,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.2737, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,124.378,5.13965,1.0948,0.462548,0.301305,0],
			'sig':[0.310283,22.2606,967.831,20901.1,169630,0.049611,5023.96,150751,199682,149001,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.2602, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,118.243,4.88614,1.0408,0.439734,0.286444,0],
			'sig':[0.217295,22.552,1208.34,28870.9,252725,0.037302,7712.63,239449,318652,215458,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.0406, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,18.4499,0.762403,0.1624,0.068613,0.044695,0],
			'sig':[0.001201,0.388672,66.1322,5375.47,202675,2.35556,417514,2530010,432044,420179,0]},
			{'Shell':'4F7/2', 'Func':2, 'BindEnergy':0.0406, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,18.4499,0.762403,0.1624,0.068613,0.044695,0],
			'sig':[0.001404,0.461421,80.8668,6745.74,260033,2.82714,538840,3440590,593334,597202,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.0828, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,37.6269,1.55485,0.3312,0.139931,0.091151,0],
			'sig':[1.92073,23.7257,224.696,1659.16,9583.94,11.4298,4883.95,40571.8,66197.8,60112.1,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.0456, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,20.722,0.856296,0.1824,0.077063,0.050199,0],
			'sig':[0.693706,14.519,203.63,1705.74,8358.35,27.6799,10018.4,56246,783516,2965130,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.0346, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,15.7233,0.649733,0.1384,0.058473,0.03809,0],
			'sig':[0.708792,19.0751,324.471,3295.99,20495.3,79.1134,37051.2,198683,1777100,7157210,0]},
			{'Shell':'5D3/2', 'Func':2, 'BindEnergy':0.00606267, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,2.75506,0.113847,0.024251,0.010246,0.006674,0],
			'sig':[0.024987,1.57436,63.2084,1326.85,11485.3,1627,192283,1.79794e+07,1.55464e+07,1.07691e+07,0]},
			{'Shell':'5D5/2', 'Func':2, 'BindEnergy':0.00520913, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,2.36719,0.097819,0.020837,0.008803,0.005735,0],
			'sig':[0.002776,0.249567,12.276,284.824,2630.48,502.536,73570,4687250,4525270,3534140,0]}] },
			'Os':{'NSHELLS':21, 'ETERM':-1.532,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':73.8708, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1574.73,320.112,147.742,96.0316,77.5066,73.9447],
			'sig':[1998.91,0,0,0,0,0.85144,49.5324,399.505,1248.81,2170.24,2434.48]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':12.968, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,276.444,56.1956,25.936,16.8583,13.6063,12.981],
			'sig':[194.573,2311.51,0,0,0,8.22621,451.904,2452.53,5641.01,8263.15,8874.19]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':12.385, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,264.016,53.6692,24.77,16.1004,12.9946,12.3974],
			'sig':[88.168,2283.05,0,0,0,2.12792,296.024,2821.88,9165.03,15993.6,18093.2]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':10.8709, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,231.739,47.108,21.7418,14.1321,11.406,10.8818],
			'sig':[89.8696,3039.39,0,0,0,2.28465,513.147,5647.55,19742.6,35937.1,40865.8]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':3.0485, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,64.986,13.2104,6.097,3.96303,3.19854,3.05155],
			'sig':[42.4908,529.875,4717.13,0,0,70.3948,2240.75,9141.83,17910.1,23923.6,25566]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':2.7922, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,59.5224,12.0997,5.5844,3.62984,2.92963,2.79499],
			'sig':[19.2819,425.341,5974.6,38379.8,0,45.8187,3030.62,14990.5,30079.5,39400.7,45775]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':2.4572, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,52.3811,10.648,4.9144,3.19434,2.57814,2.45966],
			'sig':[20.5142,589.784,10354.5,92906.2,0,78.8293,6746.39,37738.3,83675.9,117594,133297]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':2.0308, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,43.2913,8.80028,4.0616,2.64003,2.13075,2.03283],
			'sig':[1.39927,107.673,5380.7,147113,0,16.695,5585.86,62751,207209,354913,3120920]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':1.9601, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,41.7842,8.49391,3.9202,2.54812,2.05657,1.96206],
			'sig':[0.979503,109.459,6751.13,205035,0,17.0489,7928.56,94875,320961,555184,4692290]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.6543, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,297.334,12.2867,2.6172,1.10576,0.720293,0],
			'sig':[10.6939,133.809,1258.5,8806.45,40180.1,0.375633,669.973,10958.3,35978.1,53634.4,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.5465, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,248.346,10.2624,2.186,0.923576,0.60162,0],
			'sig':[4.65388,99.2523,1388.01,11008.4,40285.1,0.149091,1014.8,17698.9,42183,46797.1,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.4682, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,212.764,8.79205,1.8728,0.79125,0.515423,0],
			'sig':[4.89679,135.598,2326.23,22975.7,122933,0.187398,2393.86,51509.3,157549,218335,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.2894, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,131.512,5.43447,1.1576,0.489081,0.318589,0],
			'sig':[0.348784,24.6409,1050.64,22148.4,173515,0.044529,4606.27,143339,208318,130931,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.2728, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,123.969,5.12275,1.0912,0.461027,0.300315,0],
			'sig':[0.243262,24.9115,1310.11,30572.1,259095,0.034032,7209.49,230275,334488,191419,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.0463, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,21.0401,0.86944,0.1852,0.078246,0.05097,0],
			'sig':[0.001448,0.463261,77.4304,6157.8,223774,1.48724,326497,2556640,422423,388640,0]},
			{'Shell':'4F7/2', 'Func':2, 'BindEnergy':0.0463, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,21.0401,0.86944,0.1852,0.078246,0.05097,0],
			'sig':[0.001687,0.54952,94.672,7731.37,287447,1.77697,420702,3466840,580206,554103,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.0837, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,38.0359,1.57175,0.3348,0.141452,0.092142,0],
			'sig':[2.07421,25.42,239.049,1749.08,10019.4,11.9897,5035.51,41312.4,67346.7,65126.1,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.058, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,26.357,1.08915,0.232,0.098019,0.06385,0],
			'sig':[0.781922,16.1035,221.873,1824.39,8787.28,16.6444,7928.81,40503.5,488540,2061220,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.0454, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,20.6312,0.85254,0.1816,0.076725,0.049979,0],
			'sig':[0.793199,21.1034,354.555,3559.82,21988.5,42.5161,27586.8,154678,1046580,4693890,0]},
			{'Shell':'5D3/2', 'Func':2, 'BindEnergy':0.00705265, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,3.20494,0.132437,0.028211,0.011919,0.007764,0],
			'sig':[0.030706,1.9273,76.2971,1563.94,13180.5,1332.17,118386,1.70223e+07,1.32498e+07,8565130,0]},
			{'Shell':'5D5/2', 'Func':2, 'BindEnergy':0.00602794, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,2.73928,0.113195,0.024112,0.010187,0.006636,0],
			'sig':[0.006824,0.613249,29.7935,675.615,6084.07,842.826,94287.1,9001080,7622130,5465840,0]}] },
			'Ir':{'NSHELLS':21, 'ETERM':-1.583,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':76.111, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1622.49,329.82,152.222,98.9438,79.8571,76.1871],
			'sig':[2084.32,0,0,0,0,0.848373,48.1984,386.204,1205.15,2093.69,2346.69]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':13.4185, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,286.047,58.1478,26.837,17.444,14.0789,13.4319],
			'sig':[202.978,2379.83,0,0,0,7.94962,433.875,2355.21,5418.98,7944.38,8525.54]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':12.8241, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,273.376,55.572,25.6482,16.6712,13.4553,12.8369],
			'sig':[95.3508,2431.26,0,0,0,2.08959,286.992,2722.28,8823.25,15401.6,17388.1]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':11.2152, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,239.079,48.6,22.4304,14.5797,11.7672,11.2264],
			'sig':[96.2004,3221.25,0,0,0,2.21084,494.704,5443.54,19033.6,34653.4,39425]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':3.1737, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,67.655,13.7529,6.3474,4.12579,3.32991,3.17687],
			'sig':[44.4767,549.368,4837.61,0,0,66.8703,2134.54,8720.2,17093.2,22808.8,24449.3]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':2.9087, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,62.0059,12.6046,5.8174,3.78129,3.05186,2.91161],
			'sig':[20.8564,452.088,6211.6,38778.6,0,43.8914,2889.77,14303.1,28721.6,37636.6,44253.2]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':2.5507, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,54.3742,11.0532,5.1014,3.31589,2.67624,2.55325],
			'sig':[21.9989,624.556,10804.3,95120.4,0,74.971,6445.2,36214.7,80581.5,113507,130228]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':2.1161, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,45.1097,9.16992,4.2322,2.75092,2.22025,2.11822],
			'sig':[1.55474,118.027,5806.81,155937,0,15.6756,5258.8,59341.4,196701,337881,2871180]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':2.0404, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,43.496,8.84188,4.0808,2.65251,2.14083,2.04244],
			'sig':[1.08376,119.71,7277.57,217373,0,15.8039,7443.31,89684,304796,528760,4303920]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.6901, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,313.603,12.959,2.7604,1.16626,0.759704,0],
			'sig':[11.2494,139.566,1302.67,9012.44,40174.4,0.349639,625.133,10294,34029.6,51012.5,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.5771, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,262.252,10.837,2.3084,0.975289,0.635307,0],
			'sig':[5.06145,106.1,1455.52,11283.8,39719.6,0.139375,945.074,16682.5,40277.3,44989.5,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.4943, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,224.625,9.28217,1.9772,0.835359,0.544155,0],
			'sig':[5.28275,144.459,2445.39,23822.8,125402,0.170844,2215.44,48694.1,151871,213374,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.3114, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,141.51,5.8476,1.2456,0.526261,0.342808,0],
			'sig':[0.391451,27.2449,1140.3,23494.5,177508,0.035539,4019.15,132923,214696,117753,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.2949, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,134.012,5.53775,1.1796,0.498376,0.324644,0],
			'sig':[0.271959,27.4968,1421.43,32464.8,266096,0.027196,6175.18,212257,346230,172286,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.0634, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,28.8109,1.19055,0.2536,0.107145,0.069794,0],
			'sig':[0.001736,0.549802,90.5001,7081.02,250508,0.377159,152774,2498330,461862,300964,0]},
			{'Shell':'4F7/2', 'Func':2, 'BindEnergy':0.0605, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,27.4931,1.13609,0.242,0.102244,0.066602,0],
			'sig':[0.002017,0.651284,110.502,8871.02,320563,0.563207,223357,3402950,615074,444890,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.0952, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,43.2618,1.7877,0.3808,0.160886,0.104802,0],
			'sig':[2.23526,27.1869,254.041,1844.42,10506.7,9.46363,4318.92,37110.8,63932.7,62294.8,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.063, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,28.6291,1.18304,0.252,0.106469,0.069354,0],
			'sig':[0.877922,17.7858,240.621,1940.79,9193.33,14.8904,7501.68,37936.2,423220,1749260,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.0505, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,22.9488,0.94831,0.202,0.085344,0.055593,0],
			'sig':[0.883788,23.2416,385.564,3824.13,23458,35.0852,25319.4,146989,863663,3837080,0]},
			{'Shell':'5D3/2', 'Func':2, 'BindEnergy':0.00806274, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,3.66396,0.151406,0.032251,0.013626,0.008876,0],
			'sig':[0.037284,2.32002,90.3582,1808.82,14857.1,1107.31,77534.5,1.59996e+07,1.1557e+07,7199740,0]},
			{'Shell':'5D5/2', 'Func':2, 'BindEnergy':0.00685456, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,3.11492,0.128718,0.027418,0.011584,0.007546,0],
			'sig':[0.01241,1.10908,53.0883,1176.7,10343.3,1072.8,94213.7,1.29276e+07,9863560,6704390,0]}] },
			'Pt':{'NSHELLS':21, 'ETERM':-1.636,  'shells':[
			{'Shell':'1S1/2', 'Func':0, 'BindEnergy':78.3948, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,1671.17,339.717,156.79,101.913,82.2533,78.4732],
			'sig':[2152.87,0,0,0,0,0.846432,46.9266,373.48,1163.34,2020.09,2262.84]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':13.8799, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,295.883,60.1472,27.7598,18.0438,14.5631,13.8938],
			'sig':[211.556,2448.27,0,0,0,7.68704,416.657,2262.5,5206.62,7630.9,8209.95]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':13.2726, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,282.937,57.5156,26.5452,17.2543,13.9259,13.2859],
			'sig':[103.003,2586.15,0,0,0,2.05388,278.499,2628.66,8500.88,14814.5,16786.4]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':11.5637, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,246.508,50.1102,23.1274,15.0327,12.1329,11.5753],
			'sig':[102.875,3410.68,0,0,0,2.13092,476.97,5252.7,18371.8,33486.6,38127.1]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':3.296, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,70.2621,14.2829,6.592,4.28478,3.45823,3.2993],
			'sig':[46.5232,569.038,4954.47,0,0,63.4836,2041.33,8343.53,16352,21835.5,23311.3]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':3.0265, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,64.5171,13.1151,6.053,3.93443,3.17546,3.02953],
			'sig':[22.5319,479.917,6448.81,0,0,42.1727,2761.56,13670.1,27461.3,36029.4,40899.1]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':2.6454, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,56.393,11.4636,5.2908,3.439,2.7756,2.64805],
			'sig':[23.5708,660.747,11264.9,97432,0,71.4618,6167.74,34803.3,77696.3,109724,123099]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':2.2019, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,46.9387,9.54173,4.4038,2.86246,2.31028,2.2041],
			'sig':[1.72389,129.157,6258.43,165190,0,14.7783,4969.4,56307,187320,322146,2506650]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':2.1216, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,45.227,9.19376,4.2432,2.75807,2.22602,2.12372],
			'sig':[1.19665,130.709,7836.31,230390,0,14.696,7008.56,85020.5,290271,504087,4003910]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.722, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,328.099,13.558,2.888,1.22017,0.794821,0],
			'sig':[11.8233,145.44,1346.93,9208.6,40178,0.332288,592.279,9783.35,32463.5,48631.2,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.6092, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,276.839,11.4398,2.4368,1.02954,0.670644,0],
			'sig':[5.50269,113.329,1525.04,11554.3,38976.5,0.130481,880.565,15729.4,38386.3,43068,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.519, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,235.85,9.74599,2.076,0.877101,0.571347,0],
			'sig':[5.69252,153.742,2568.58,24683.3,127953,0.149948,2075.38,46410.1,147090,209243,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.3308, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,150.326,6.2119,1.3232,0.559046,0.364165,0],
			'sig':[0.438516,30.0672,1235.32,24872.6,181224,0.031049,3631.54,125298,218162,112476,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.3133, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,142.373,5.88328,1.2532,0.529472,0.3449,0],
			'sig':[0.303463,30.2909,1539.01,34389.4,272765,0.022411,5549.03,200042,352991,165764,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.0743, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,33.7642,1.39524,0.2972,0.125566,0.081794,0],
			'sig':[0.002074,0.648876,105.027,8065.94,276767,0.201936,105968,2356520,450271,288862,0]},
			{'Shell':'4F7/2', 'Func':2, 'BindEnergy':0.0711, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,32.31,1.33514,0.2844,0.120158,0.078271,0],
			'sig':[0.002402,0.767768,128.176,10105,354411,0.297192,154105,3225300,597038,432387,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.1017, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,46.2156,1.90976,0.4068,0.171871,0.111958,0],
			'sig':[2.39787,28.9441,268.689,1934.87,10957,8.76206,4065.82,35385.5,60787.7,60415.6,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.0653, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,29.6743,1.22623,0.2612,0.110356,0.071886,0],
			'sig':[0.977953,19.4884,258.886,2048.15,9545.52,14.9105,7464.91,37688.8,426001,1793900,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.0517, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,23.4941,0.970844,0.2068,0.087372,0.056915,0],
			'sig':[0.973817,25.313,414.666,4062.57,24760,35.813,25837,149481,885650,4116500,0]},
			{'Shell':'5D3/2', 'Func':2, 'BindEnergy':0.00743991, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,3.38092,0.13971,0.02976,0.012573,0.00819,0],
			'sig':[0.042771,2.60824,99.3904,1943.16,15571.6,1458.41,130757,1.55733e+07,1.06328e+07,7138560,0]},
			{'Shell':'5D5/2', 'Func':2, 'BindEnergy':0.00612538, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,2.78356,0.115025,0.024502,0.010352,0.006743,0],
			'sig':[0.023465,2.04996,95.8907,2077.52,17845.8,2485.03,306833,1.97856e+07,1.57389e+07,1.15312e+07,0]}] },
			'Au':{'NSHELLS':21, 'ETERM':-1.689,  'shells':[
			{'Shell':'1S1/2', 'Func':1, 'BindEnergy':80.7249, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,372.713,168.044,114.162,92.0403,82.6876,0],
			'sig':[0,0,0,0,0,38.6293,324.667,902.222,1572.69,2059.22,0]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':14.3528, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,305.964,62.1965,28.7056,18.6585,15.0592,14.3672],
			'sig':[220.632,2516.2,0,0,0,7.43845,400.268,2173.7,5003.65,7338.01,7891.48]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':13.7336, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,292.764,59.5133,27.4672,17.8536,14.4096,13.7473],
			'sig':[111.16,2747.68,0,0,0,2.01955,270.382,2538.77,8191.92,14277.1,16157.2]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':11.9187, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,254.075,51.6486,23.8374,15.4942,12.5053,11.9306],
			'sig':[109.872,3607.07,0,0,0,2.06537,460.46,5069.53,17732,32306.1,36908.1]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':3.4249, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,73.0099,14.8415,6.8498,4.45235,3.59347,3.42832],
			'sig':[48.6085,588.897,5069.57,0,0,60.4823,1949.15,7972.6,15626.1,20858.4,22135.5]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':3.1478, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,67.1029,13.6407,6.2956,4.09212,3.30273,3.15095],
			'sig':[24.3186,508.802,6683.99,0,0,40.569,2639.75,13064.5,26247,34417.6,38574.1]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':2.743, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,58.4736,11.8865,5.486,3.56588,2.87801,2.74574],
			'sig':[25.2148,698.128,11731.1,99664.2,0,68.0885,5900.46,33435.5,74900.1,106049,113810]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':2.2911, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,48.8403,9.92827,4.5822,2.97842,2.40387,2.29339],
			'sig':[1.90877,141.108,6733.83,174732,0,13.9223,4690.48,53360.9,178147,308141,2278070]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':2.2057, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,47.0197,9.55819,4.4114,2.8674,2.31426,2.20791],
			'sig':[1.31899,142.47,8423.35,243802,0,13.6534,6592.49,80502.8,276057,481926,3517300]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.7588, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,344.822,14.2491,3.0352,1.28236,0.835333,0],
			'sig':[12.4246,151.486,1391.8,9401.99,40092.7,0.312763,555.852,9229.88,30793.1,46336.5,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.6437, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,292.517,12.0877,2.5748,1.08784,0.708624,0],
			'sig':[5.97069,120.866,1595.74,11811.2,38153.7,0.121744,818.143,14799,36558.1,41252.3,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.5454, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,247.847,10.2417,2.1816,0.921717,0.600409,0],
			'sig':[6.13134,163.471,2695.16,25549.3,130381,0.137876,1938.36,44127.2,142208,204849,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.352, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,159.96,6.61,1.408,0.594874,0.387503,0],
			'sig':[0.490304,33.1185,1335.73,26275.9,184692,0.026898,3259.02,117528,221380,109209,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.3339, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,151.734,6.27011,1.3356,0.564285,0.367577,0],
			'sig':[0.337983,33.3066,1663.36,36360,279084,0.018936,4930.04,187188,359200,162360,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.0864, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,39.2628,1.62245,0.3456,0.146015,0.095114,0],
			'sig':[0.002465,0.761895,121.243,9131,303589,0.108959,73797.4,2183820,473625,254615,0]},
			{'Shell':'4F7/2', 'Func':2, 'BindEnergy':0.0828, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,37.6269,1.55485,0.3312,0.139931,0.091151,0],
			'sig':[0.002847,0.900383,147.877,11437.8,388956,0.162118,107022,3008850,623508,379320,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.1078, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,48.9876,2.02431,0.4312,0.18218,0.118673,0],
			'sig':[2.5722,30.813,284.109,2028.68,11406.4,8.25963,3872.29,34036.7,59422.1,61084.4,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.0717, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,32.5827,1.34641,0.2868,0.121172,0.078932,0],
			'sig':[1.09061,21.3786,278.904,2164.77,9921.42,12.9298,6920.78,34738.8,363106,1527340,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.0537, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,24.4029,1.0084,0.2148,0.090752,0.059116,0],
			'sig':[1.07683,27.6668,447.594,4332.26,26230.9,35.2958,25916.7,151242,843603,3729800,0]},
			{'Shell':'5D3/2', 'Func':2, 'BindEnergy':0.00830839, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,3.77559,0.156018,0.033234,0.014041,0.009146,0],
			'sig':[0.050855,3.07416,115.277,2201.76,17229.4,1262.5,93408.2,1.49533e+07,9368700,6231520,0]},
			{'Shell':'5D5/2', 'Func':2, 'BindEnergy':0.00679032, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,3.08573,0.127511,0.027161,0.011475,0.007475,0],
			'sig':[0.033386,2.9008,133.738,2833.18,23805.3,2647.12,271471,2.27683e+07,1.64741e+07,1.16807e+07,0]}] },
			'Hg':{'NSHELLS':22, 'ETERM':-1.743,  'shells':[
			{'Shell':'1S1/2', 'Func':1, 'BindEnergy':83.1023, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,383.69,172.993,117.524,94.751,85.1228,0],
			'sig':[0,0,0,0,0,37.6709,314.211,871.379,1518.19,1988.59,0]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':14.8393, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,316.335,64.3047,29.6786,19.291,15.5697,14.8541],
			'sig':[229.523,2583.53,0,0,0,7.19899,384.036,2088.1,4807.28,7049.55,7582.37]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':14.2087, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,302.892,61.5721,28.4174,18.4712,14.908,14.2229],
			'sig':[119.988,2916.04,0,0,0,1.98558,262.48,2451.87,7892.88,13737.7,15523.7]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':12.2839, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,261.861,53.2311,24.5678,15.969,12.8885,12.2962],
			'sig':[117.239,3811.51,0,0,0,2.00101,444.345,4891.01,17112.7,31212.6,35622.9]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':3.5616, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,75.924,15.4339,7.1232,4.63006,3.7369,3.56516],
			'sig':[50.7449,608.995,5182.55,0,0,57.4882,1857.46,7605.57,14912.5,19887.8,21237.7]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':3.2785, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,69.889,14.2071,6.557,4.26203,3.43986,3.28178],
			'sig':[26.2121,538.838,6920.41,0,0,38.627,2514.96,12453.9,25036.1,32819.9,37971.6]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':2.8471, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,60.6927,12.3376,5.6942,3.70121,2.98723,2.84995],
			'sig':[26.9522,736.975,12208.2,101485,0,64.6448,5628.21,32045.2,72048.2,102182,110843]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':2.3849, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,50.8398,10.3347,4.7698,3.10035,2.50228,2.38728],
			'sig':[2.10924,153.906,7234.73,184604,0,13.076,4416.37,50452.9,169043,294713,2243730]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':2.2949, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,48.9213,9.94473,4.5898,2.98335,2.40785,2.29719],
			'sig':[1.45195,155.072,9043.05,257821,0,12.6302,6177.84,75985.2,261801,461423,3343580]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.8003, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,363.681,15.0284,3.2012,1.35249,0.881019,0],
			'sig':[13.0368,157.634,1437.09,9591.42,39842.3,0.291844,517.652,8656.08,29067.2,44198.2,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.6769, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,307.604,12.7111,2.7076,1.14395,0.745172,0],
			'sig':[6.46968,128.708,1666.59,12044.7,37353.2,0.115271,767.519,13999.4,34956.6,39751.7,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.571, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,259.48,10.7225,2.284,0.96498,0.628591,0],
			'sig':[6.59016,173.533,2823.67,26396.6,132725,0.128319,1824.18,42133.5,137870,200981,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.3783, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,171.911,7.10387,1.5132,0.639321,0.416455,0],
			'sig':[0.547235,36.4217,1442.55,27737,187947,0.022318,2837.85,108309,223220,109609,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.3598, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,163.504,6.75647,1.4392,0.608056,0.39609,0],
			'sig':[0.375783,36.5667,1795.8,38421.8,285280,0.015292,4230.52,171749,362658,165933,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.1022, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,46.4428,1.91915,0.4088,0.172716,0.112508,0],
			'sig':[0.002916,0.890594,139.378,10294,331972,0.054329,47886.6,1922910,565485,208792,0]},
			{'Shell':'4F7/2', 'Func':2, 'BindEnergy':0.0985, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,44.7614,1.84967,0.394,0.166463,0.108435,0],
			'sig':[0.00336,1.05118,169.904,12895.8,425758,0.076155,68313.9,2655410,744125,302197,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.1203, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,54.668,2.25904,0.4812,0.203305,0.132434,0],
			'sig':[2.75942,32.809,300.53,2128.76,11891,6.72156,3397.79,30976,57560.2,60507.3,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.0805, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,36.5817,1.51166,0.322,0.136044,0.088619,0],
			'sig':[1.21736,23.4723,300.727,2289.89,10319.1,10.6393,6229.2,31394.5,282175,1138390,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.0576, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,26.1752,1.08164,0.2304,0.097343,0.06341,0],
			'sig':[1.19494,30.3489,484.944,4637.8,27901.3,32.0235,24897.1,149796,723184,2809720,0]},
			{'Shell':'5D3/2', 'Func':2, 'BindEnergy':0.0064, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,2.90836,0.120182,0.0256,0.010816,0.007046,0],
			'sig':[0.062019,3.7505,138.965,2591.22,19821.2,2782.54,354707,1.73634e+07,9453460,8431510,0]},
			{'Shell':'5D5/2', 'Func':2, 'BindEnergy':0.0064, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,2.90836,0.120182,0.0256,0.010816,0.007046,0],
			'sig':[0.04086,3.58066,163.794,3392,27899.6,3650.29,417584,2.57298e+07,1.53454e+07,1.23142e+07,0]},
			{'Shell':'6S1/2', 'Func':2, 'BindEnergy':0.00771361, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,3.5053,0.144849,0.030854,0.013036,0.008492,0],
			'sig':[0.243562,2.62276,22.9375,163.816,958.839,125.571,11494.9,45396,1154200,5944230,0]}] },
			'Tl':{'NSHELLS':22, 'ETERM':-1.799,  'shells':[
			{'Shell':'1S1/2', 'Func':1, 'BindEnergy':85.5304, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,394.9,178.047,120.958,97.5194,87.61,0],
			'sig':[0,0,0,0,0,36.7505,304.159,841.72,1465.03,1917.29,0]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':15.3467, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,327.151,66.5035,30.6934,19.9506,16.102,15.362],
			'sig':[238.656,2650.93,0,0,0,6.96273,368.51,2004.36,4616.49,6773.05,7278.8]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':14.6979, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,313.321,63.692,29.3958,19.1072,15.4213,14.7126],
			'sig':[129.226,3091.14,0,0,0,1.95264,254.905,2368.22,7605.98,13237,14920.7]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':12.6575, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,269.825,54.8501,25.315,16.4547,13.2805,12.6702],
			'sig':[124.958,4023.65,0,0,0,1.93868,428.747,4718.6,16512.6,30123.9,34298.8]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':3.7041, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,78.9617,16.0514,7.4082,4.81531,3.88641,3.7078],
			'sig':[52.9444,629.299,5292.6,0,0,54.6171,1768.81,7250.07,14218.6,19002.5,20241.8]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':3.4157, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,72.8138,14.8016,6.8314,4.44039,3.58382,3.41912],
			'sig':[28.2293,570.03,7155.32,0,0,36.942,2393.4,11859.8,23856.9,31273.2,36988.3]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':2.9566, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,63.027,12.8121,5.9132,3.84356,3.10212,2.95956],
			'sig':[28.7685,777.151,12694.7,107800,0,61.2214,5359.05,30669,69222.8,98373.5,113082]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':2.4851, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,52.9758,10.7689,4.9702,3.23061,2.60741,2.48759],
			'sig':[2.32726,167.646,7766.12,195036,0,12.1543,4141.64,47547.8,159970,281338,2133380]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':2.3893, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,50.9336,10.3538,4.7786,3.10607,2.5069,2.39169],
			'sig':[1.59528,168.537,9697.69,272518,0,11.6308,5770.27,71525.1,247681,440288,3370420]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.8455, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,384.221,15.8771,3.382,1.42888,0.930777,0],
			'sig':[13.6684,163.903,1482.6,9774.77,39569.7,0.271509,480.142,8090.29,27381.4,41939.8,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.7213, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,327.781,13.5449,2.8852,1.21898,0.794051,0],
			'sig':[7.00395,136.961,1740.1,12279.1,36269.2,0.104859,698.99,12999.3,33023.7,37786.6,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.609, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,276.748,11.4361,2.436,1.0292,0.670424,0],
			'sig':[7.07736,184.147,2959.82,27318.2,135200,0.112246,1642.63,39087.8,131049,192620,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.4066, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,184.772,7.6353,1.6264,0.687147,0.44761,0],
			'sig':[0.60968,39.9802,1555.04,29221.6,190982,0.018479,2464.54,99482.9,224271,117338,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.3862, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,175.501,7.25222,1.5448,0.652671,0.425152,0],
			'sig':[0.417017,40.0668,1934.58,40495.5,291232,0.012583,3661.52,157913,365015,181976,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.1228, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,55.8041,2.30599,0.4912,0.20753,0.135186,0],
			'sig':[0.003436,1.03689,159.68,11575.1,362794,0.023893,28986.4,1593840,749133,184318,0]},
			{'Shell':'4F7/2', 'Func':2, 'BindEnergy':0.1185, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,53.85,2.22524,0.474,0.200263,0.130452,0],
			'sig':[0.003948,1.2222,194.503,14495.2,465411,0.033166,41200.3,2209710,983727,257940,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.1363, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,61.9389,2.5595,0.5452,0.230345,0.150047,0],
			'sig':[2.95545,34.8802,317.41,2230.55,12376.1,5.45352,2901.15,27592.9,54876.2,56690,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.0996, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,45.2613,1.87033,0.3984,0.168322,0.109646,0],
			'sig':[1.35343,25.7043,323.764,2419.94,10712,6.59765,4895.48,25824.5,174385,777126,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.0754, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,34.2641,1.41589,0.3016,0.127425,0.083005,0],
			'sig':[1.32109,33.2295,525.349,4973.02,29784.2,16.8683,17707.3,122690,433154,1640880,0]},
			{'Shell':'5D3/2', 'Func':2, 'BindEnergy':0.0153, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,6.95279,0.28731,0.0612,0.025857,0.016843,0],
			'sig':[0.074891,4.53407,166.225,3031.79,22667.3,343.808,39589.9,6899230,9519480,4303450,0]},
			{'Shell':'5D5/2', 'Func':2, 'BindEnergy':0.0131, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,5.95304,0.245997,0.0524,0.022139,0.014421,0],
			'sig':[0.049695,4.37703,198.448,4021.9,32401,667.043,60946.3,1.39761e+07,1.45311e+07,7702540,0]},
			{'Shell':'6S1/2', 'Func':2, 'BindEnergy':0.00966483, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,4.392,0.18149,0.038659,0.016333,0.01064,0],
			'sig':[0.322028,3.49257,30.564,216.845,1261.87,112.208,11709.5,38995.6,972106,5652070,0]}] },
			'Pb':{'NSHELLS':23, 'ETERM':-1.856,  'shells':[
			{'Shell':'1S1/2', 'Func':1, 'BindEnergy':88.0045, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,406.323,183.198,124.457,100.34,90.1442,0],
			'sig':[0,0,0,0,0,35.8717,294.524,813.227,1414.64,1851.96,0]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':15.8608, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,338.111,68.7313,31.7216,20.6189,16.6415,15.8767],
			'sig':[247.877,2717.18,0,0,0,6.74367,353.93,1925.36,4434.96,6505.57,6997.19]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':15.2, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,324.024,65.8678,30.4,19.7599,15.9481,15.2152],
			'sig':[139.016,3272.98,0,0,0,1.92085,247.397,2288.32,7330.95,12735.9,14381]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':13.0352, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,277.876,56.4868,26.0704,16.9457,13.6768,13.0482],
			'sig':[133.052,4242.77,0,0,0,1.88079,414.138,4556.14,15947.2,29116.5,33094.9]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':3.8507, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,82.0868,16.6866,7.7014,5.00588,4.04023,3.85455],
			'sig':[55.1787,649.717,5399.47,0,0,51.9043,1684.87,6912.61,13559.9,18136,19197.5]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':3.5542, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,75.7662,15.4018,7.1084,4.62044,3.72913,3.55775],
			'sig':[30.3573,602.176,7385.02,0,0,35.4398,2282.72,11311.4,22763.2,29838.5,35104.1]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':3.0664, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,65.3676,13.288,6.1328,3.9863,3.21732,3.06947],
			'sig':[30.68,818.621,13184.6,0,0,58.1819,5114.12,29399.6,66591.7,94860.9,109804]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':2.5856, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,55.1182,11.2045,5.1712,3.36126,2.71286,2.58819],
			'sig':[2.56441,182.313,8320.6,205728,0,11.4095,3897.82,44929.1,151687,268430,2024230]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':2.484, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,52.9524,10.7642,4.968,3.22918,2.60626,2.48648],
			'sig':[1.7505,182.878,10380.9,287412,0,10.7044,5407.71,67492,234747,419984,3163860]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.8936, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,406.079,16.7804,3.5744,1.51017,0.983729,0],
			'sig':[14.3185,170.298,1528.43,9952.65,39227.1,0.252745,444.717,7553.37,25753.2,39676.5,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.7639, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,347.14,14.3448,3.0556,1.29098,0.840947,0],
			'sig':[7.57276,145.542,1813.84,12491.1,35186.3,0.097209,644.845,12162.3,31334.1,36176.1,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.6445, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,292.881,12.1027,2.578,1.08919,0.709505,0],
			'sig':[7.59156,195.161,3098.27,28227.5,137553,0.100782,1504.73,36656.7,125313,186196,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.4352, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,197.768,8.17236,1.7408,0.735481,0.479094,0],
			'sig':[0.678053,43.8103,1673.46,30730.9,193727,0.015561,2162.64,91739.7,223298,131121,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.4129, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,187.634,7.75361,1.6516,0.697794,0.454545,0],
			'sig':[0.461994,43.8263,2080.63,42607.8,296820,0.010584,3199.59,145721,364429,208738,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.1429, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,64.9382,2.68343,0.5716,0.241499,0.157313,0],
			'sig':[0.004032,1.20229,182.168,12949.9,394024,0.012623,19181.7,1324030,962868,169274,0]},
			{'Shell':'4F7/2', 'Func':2, 'BindEnergy':0.1381, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,62.7569,2.5933,0.5524,0.233387,0.152029,0],
			'sig':[0.004621,1.41521,221.728,16211.8,505706,0.017377,27119.9,1836850,1265560,233725,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.1473, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,66.9376,2.76606,0.5892,0.248934,0.162157,0],
			'sig':[3.16178,37.0365,334.695,2332,12834.1,4.73888,2667.75,25855.6,53445.4,55956.1,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.1048, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,47.6243,1.96798,0.4192,0.17711,0.11537,0],
			'sig':[1.50197,28.0812,347.392,2546.1,11081.9,6.37304,4764.16,25354.5,153903,663843,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.086, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,39.081,1.61494,0.344,0.145339,0.094674,0],
			'sig':[1.45889,36.3288,567.994,5318.39,31683.6,12.5285,15330.2,114309,348896,1225270,0]},
			{'Shell':'5D3/2', 'Func':2, 'BindEnergy':0.0218, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,9.90659,0.409369,0.0872,0.036842,0.023999,0],
			'sig':[0.089543,5.39927,195.322,3483.39,25483.1,141.211,48489.7,2526930,1.3927e+07,3251420,0]},
			{'Shell':'5D5/2', 'Func':2, 'BindEnergy':0.0192, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,8.72507,0.360545,0.0768,0.032448,0.021136,0],
			'sig':[0.059543,5.24107,234.87,4658.67,36794.3,249.896,77629.7,4999400,1.9581e+07,5958860,0]},
			{'Shell':'6S1/2', 'Func':2, 'BindEnergy':0.0116904, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,5.31247,0.219527,0.046762,0.019756,0.012869,0],
			'sig':[0.393189,4.27342,37.3254,262.933,1523.9,97.1955,11322.2,38387.8,706199,4520770,0]},
			{'Shell':'6P1/2', 'Func':2, 'BindEnergy':0.00491166, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,2.23201,0.092233,0.019647,0.008301,0.005407,0],
			'sig':[0.097781,1.60369,18.6228,137.449,629.869,216.538,37120.3,2332260,1.44774e+07,3.34783e+07,0]}] },
			'Bi':{'NSHELLS':23, 'ETERM':-1.914,  'shells':[
			{'Shell':'1S1/2', 'Func':1, 'BindEnergy':90.5259, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,417.965,188.446,128.023,103.215,92.7269,0],
			'sig':[0,0,0,0,0,35.0313,285.287,785.885,1365.58,1786.27,0]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':16.3875, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,349.339,71.0137,32.775,21.3036,17.1941,16.4039],
			'sig':[257.295,2782.75,0,0,0,6.53683,340.037,1849.79,4261.91,6253.21,6720.55]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':15.7111, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,334.92,68.0826,31.4222,20.4243,16.4844,15.7268],
			'sig':[149.416,3460.82,0,0,0,1.8922,240.638,2213.1,7071.68,12280.5,13831.9]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':13.4186, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,286.049,58.1482,26.8372,17.4441,14.079,13.432],
			'sig':[141.511,4469.1,0,0,0,1.82588,400.201,4401.36,15404.9,28119.5,32014.2]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':3.9991, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,85.2503,17.3297,7.9982,5.1988,4.19593,4.0031],
			'sig':[57.4725,670.226,5501.38,0,0,49.4341,1606.95,6596.79,12940.5,17344.5,18283.1]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':3.6963, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,78.7954,16.0176,7.3926,4.80517,3.87823,3.7],
			'sig':[32.6096,635.364,7610.21,0,0,34.0435,2178.88,10793,21720.8,28461.8,34004.9]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':3.1769, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,67.7232,13.7668,6.3538,4.12995,3.33326,3.18008],
			'sig':[32.6707,861.232,13676.7,0,0,55.4123,4888.97,28219.5,64132.8,91479.3,105628]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':2.6876, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,57.2926,11.6465,5.3752,3.49386,2.81988,2.69029],
			'sig':[2.8204,197.929,8899.63,216495,0,10.736,3675.46,42511.4,143959,255535,1912360]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':2.5796, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,54.9903,11.1785,5.1592,3.35346,2.70657,2.58218],
			'sig':[1.91708,198.1,11092.5,302748,0,9.93103,5079.46,63789.9,222771,401488,2956410]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.9382, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,426.347,17.6179,3.7528,1.58554,1.03283,0],
			'sig':[14.995,176.798,1573.42,10112.5,38650.6,0.239858,417.084,7116.51,24382.7,37838.4,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.8053, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,365.953,15.1223,3.2212,1.36094,0.886523,0],
			'sig':[8.18304,154.479,1887.63,12679.9,34116.4,0.091529,600.692,11441.8,29811.4,34709.4,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.6789, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,308.513,12.7487,2.7156,1.14733,0.747374,0],
			'sig':[8.13324,206.587,3239.15,29128,139812,0.091959,1392.1,34588.4,120338,181400,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.4636, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,210.674,8.70567,1.8544,0.783476,0.510359,0],
			'sig':[0.752777,47.9184,1797.39,32245.8,196220,0.01335,1920.67,85025.9,221362,148494,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.44, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,199.95,8.2625,1.76,0.743592,0.484379,0],
			'sig':[0.510925,47.8554,2233.8,44745,302076,0.009049,2817.76,134831,361423,242470,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.1619, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,73.5723,3.04022,0.6476,0.273608,0.178229,0],
			'sig':[0.004714,1.38842,206.899,14403.5,424836,0.00737,13740.1,1117140,1183280,157518,0]},
			{'Shell':'4F7/2', 'Func':2, 'BindEnergy':0.1574, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,71.5274,2.95572,0.6296,0.266003,0.173275,0],
			'sig':[0.005388,1.63211,251.696,18037.6,546186,0.009793,19018,1538130,1575190,216121,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.1593, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,72.3908,2.9914,0.6372,0.269214,0.175367,0],
			'sig':[3.37275,39.2506,352.373,2434.27,13285.8,4.2297,2445.93,24154.9,52025.5,55566.9,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.1168, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,53.0775,2.19332,0.4672,0.19739,0.12858,0],
			'sig':[1.66626,30.6352,372.132,2675.41,11441.5,5.13349,4271.24,23504.8,121862,547338,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.0928, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,42.1712,1.74264,0.3712,0.15683,0.10216,0],
			'sig':[1.60768,39.6253,612.517,5670.96,33584.3,11.0835,14409.6,111980,313722,1009970,0]},
			{'Shell':'5D3/2', 'Func':2, 'BindEnergy':0.0265, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,12.0424,0.497628,0.106,0.044785,0.029173,0],
			'sig':[0.106654,6.36826,226.64,3950.73,28295.7,89.7415,51561.1,1270820,2.03368e+07,2788150,0]},
			{'Shell':'5D5/2', 'Func':2, 'BindEnergy':0.0244, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,11.0881,0.458193,0.0976,0.041236,0.026861,0],
			'sig':[0.070755,6.19856,273.989,5317.55,41195,136.017,83653.1,2191220,2.97113e+07,5008160,0]},
			{'Shell':'6S1/2', 'Func':2, 'BindEnergy':0.0142334, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,6.46809,0.26728,0.056934,0.024054,0.015669,0],
			'sig':[0.468858,5.1022,44.4556,311.039,1796.66,80.6937,10730.6,40150.2,452449,3054770,0]},
			{'Shell':'6P1/2', 'Func':2, 'BindEnergy':0.00616991, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,2.8038,0.115861,0.02468,0.010427,0.006792,0],
			'sig':[0.144044,2.36591,27.2263,197.456,895.055,219.574,28690.1,2224830,1.55997e+07,3.25345e+07,0]}] },
			'Po':{'NSHELLS':24, 'ETERM':-1.973,  'shells':[
			{'Shell':'1S1/2', 'Func':1, 'BindEnergy':93.105, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,429.873,193.815,131.67,106.156,95.3687,0],
			'sig':[0,0,0,0,0,34.2208,276.376,759.478,1318.86,1725.67,0]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':16.9393, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,361.102,73.4049,33.8786,22.021,17.773,16.9562],
			'sig':[266.873,2848.69,0,0,0,6.32812,326.251,1775.42,4091.75,6004.2,6452.11]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':16.2443, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,346.286,70.3932,32.4886,21.1175,17.0438,16.2605],
			'sig':[160.467,3658,0,0,0,1.8615,233.861,2139.08,6818,11823.7,13289.2]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':13.8138, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,294.474,59.8608,27.6276,17.9579,14.4937,13.8276],
			'sig':[150.406,4705.51,0,0,0,1.77159,386.574,4250.65,14882.3,27186.2,30899.6]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':4.1494, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,88.4543,17.981,8.2988,5.39419,4.35363,4.15355],
			'sig':[59.7954,690.733,5598.09,0,0,47.1483,1534.45,6301.3,12359.1,16543.8,17596.1]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':3.8541, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,82.1593,16.7014,7.7082,5.0103,4.04379,3.85795],
			'sig':[35.0147,670.142,7840.28,0,0,32.478,2068.59,10257.8,20659,27085.4,32381.4]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':3.3019, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,70.3879,14.3085,6.6038,4.29245,3.46442,3.3052],
			'sig':[34.7691,905.965,14199.1,0,0,51.9325,4640.2,26946.1,61510.3,87958,102044]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':2.798, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,59.646,12.1249,5.596,3.63738,2.93571,2.8008],
			'sig':[3.0993,214.751,9521.85,227992,0,10.0361,3448.91,40089.5,136317,242564,1774240]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':2.683, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,57.1945,11.6265,5.366,3.48788,2.81505,2.68568],
			'sig':[2.09772,214.449,11856.2,319487,0,9.14649,4746.34,60081.3,210905,381530,2765610]},
			{'Shell':'4S1/2', 'Func':2, 'BindEnergy':0.9953, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,452.295,18.6902,3.9812,1.68204,1.09569,0],
			'sig':[15.6848,183.453,1620,10283.5,40372.1,0.207704,383.014,6601.27,22815.6,35706,0]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.851, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,386.721,15.9804,3.404,1.43818,0.936832,0],
			'sig':[8.82796,163.77,1962.6,12855.4,32902.6,0.085503,556.334,10723.9,28273.2,33159,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.705, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,320.374,13.2388,2.82,1.19144,0.776107,0],
			'sig':[8.70745,218.373,3379.2,29970,142041,0.088004,1331.04,33340.2,117201,178629,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.5002, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,227.306,9.39296,2.0008,0.845329,0.55065,0],
			'sig':[0.834614,52.3688,1930.89,33889.9,198118,0.010863,1641.41,77060.2,216239,163055,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.4734, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,215.128,8.8897,1.8936,0.800038,0.521147,0],
			'sig':[0.564271,52.2018,2397.89,47040,306972,0.007494,2406.56,122601,353810,272669,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.175344, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,79.6816,3.29268,0.701375,0.296328,0.193029,0],
			'sig':[0.00549,1.59623,233.665,15881.8,452387,0.005607,11417.5,1004740,1346150,148291,0]},
			{'Shell':'4F7/2', 'Func':2, 'BindEnergy':0.169362, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,76.9632,3.18035,0.677447,0.286219,0.186444,0],
			'sig':[0.006258,1.87339,283.922,19864.8,580929,0.00769,16142.8,1399410,1789340,204765,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.170906, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,77.6651,3.20935,0.683625,0.288829,0.188144,0],
			'sig':[3.59758,41.5541,370.383,2536.76,13722.8,3.84613,2268.73,22722.3,50754.2,55935.4,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.125695, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,57.1198,2.36036,0.502781,0.212423,0.138373,0],
			'sig':[1.84124,33.3192,397.509,2802.8,11776.9,4.65631,4009.55,22531.4,105179,468122,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.0983141, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,44.677,1.84618,0.393257,0.166149,0.10823,0],
			'sig':[1.77056,43.142,658.957,6033.04,35510.2,10.319,13909.5,111364,296457,870142,0]},
			{'Shell':'5D3/2', 'Func':2, 'BindEnergy':0.0314, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,14.2691,0.589642,0.1256,0.053066,0.034567,0],
			'sig':[0.125401,7.42411,260.13,4433.51,31103,60.4447,51791.2,671769,2.16562e+07,2575330,0]},
			{'Shell':'5D5/2', 'Func':2, 'BindEnergy':0.0314, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,14.2691,0.589642,0.1256,0.053066,0.034567,0],
			'sig':[0.083185,7.24629,315.867,6001.97,45624.4,68.0741,80080.9,830642,3.11941e+07,4331100,0]},
			{'Shell':'6S1/2', 'Func':2, 'BindEnergy':0.0167777, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,7.62429,0.315058,0.067111,0.028354,0.01847,0],
			'sig':[0.542585,5.90712,51.3193,356.646,2053.42,68.6136,10094.2,41401.6,322850,2148360,0]},
			{'Shell':'6P1/2', 'Func':2, 'BindEnergy':0.00755974, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,3.43538,0.14196,0.030239,0.012776,0.008322,0],
			'sig':[0.191404,3.1285,35.5647,253.443,1136.24,204.103,22289.7,1829070,1.54445e+07,3.04998e+07,0]},
			{'Shell':'6P3/2', 'Func':2, 'BindEnergy':0.00539477, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,2.45155,0.101305,0.021579,0.009117,0.005939,0],
			'sig':[0.072355,1.55668,22.3733,205.543,1246.63,294.815,26750.7,1685100,1.48137e+07,3.51544e+07,0]}] },
			'At':{'NSHELLS':24, 'ETERM':-2.033,  'shells':[
			{'Shell':'1S1/2', 'Func':1, 'BindEnergy':95.7299, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,441.992,199.279,135.383,109.149,98.0575,0],
			'sig':[0,0,0,0,0,33.4478,267.846,734.165,1273.4,1664.62,0]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':17.493, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,372.905,75.8043,34.986,22.7408,18.354,17.5105],
			'sig':[276.585,2912.15,0,0,0,6.14143,313.562,1706.16,3932.88,5771.07,6200.07]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':16.7847, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,357.806,72.7349,33.5694,21.82,17.6108,16.8015],
			'sig':[172.179,3860.64,0,0,0,1.83472,227.643,2070.03,6580.41,11404.3,12789.5]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':14.2135, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,302.995,61.5929,28.427,18.4775,14.9131,14.2277],
			'sig':[159.926,4949.45,0,0,0,1.72084,373.738,4108.2,14386.8,26292.6,29845.1]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':4.317, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,92.0271,18.7073,8.634,5.61207,4.52948,4.32132],
			'sig':[62.1955,711.726,5696.38,0,0,44.6913,1457.78,5995.04,11764.1,15779.8,16738.9]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':4.008, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,85.4401,17.3683,8.016,5.21037,4.20527,4.01201],
			'sig':[37.5389,705.636,8058.36,0,0,31.1981,1973.78,9784.15,19706.2,25816.9,30766.2]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':3.426, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,73.0333,14.8463,6.852,4.45378,3.59462,3.42943],
			'sig':[36.9702,951.975,14722.3,0,0,49.1684,4418.11,25790.4,59101.8,84776,97927.8]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':2.9087, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,62.0059,12.6046,5.8174,3.78129,3.05186,2.91161],
			'sig':[3.39954,232.615,10169.8,245535,0,9.42239,3247.66,37907.2,129372,231362,1661650]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':2.7867, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,59.4051,12.0759,5.5734,3.62269,2.92386,2.78949],
			'sig':[2.29123,231.772,12651.3,335992,0,8.46073,4449.71,56726.9,200026,362109,2547310]},
			{'Shell':'4S1/2', 'Func':0, 'BindEnergy':1.042, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,22.2127,4.51541,2.084,1.35459,1.09329,1.04304],
			'sig':[16.3889,190.113,1664.52,10423.3,0,278.481,5473.95,17455.6,29099.9,35251.9,36664.2]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.886, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,402.626,16.6377,3.544,1.49732,0.975362,0],
			'sig':[9.50923,173.291,2035.14,12990.9,31972.7,0.08351,532.281,10250.1,27125.6,32082.9,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.74, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,336.279,13.896,2.96,1.25059,0.814637,0],
			'sig':[9.30828,230.684,3526.37,30878,144277,0.0813,1240.1,31601.6,112773,173837,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.5332, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,242.302,10.0126,2.1328,0.901099,0.586979,0],
			'sig':[0.923649,57.1134,2069.05,35504.5,199756,0.008757,1450.81,71079.7,211478,175527,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.475385, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,216.029,8.92697,1.90154,0.803392,0.523332,0],
			'sig':[0.62127,56.6601,2550.73,48721.7,312525,0.008164,2526.78,124632,362389,312909,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.197076, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,89.5572,3.70077,0.788303,0.333054,0.216953,0],
			'sig':[0.006375,1.83108,263.774,17566.9,485917,0.003499,8310.04,839269,1534910,132977,0]},
			{'Shell':'4F7/2', 'Func':2, 'BindEnergy':0.190577, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,86.6041,3.57874,0.762309,0.322072,0.209799,0],
			'sig':[0.007248,2.14576,320.238,21964.8,624340,0.00475,11686.7,1168260,2054850,183563,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.185617, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,84.35,3.48559,0.742467,0.313689,0.204338,0],
			'sig':[3.83146,43.9284,388.764,2640.74,14159.3,3.40237,2059.04,21035.6,48738.2,55508.9,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.138499, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,62.9384,2.6008,0.553998,0.234062,0.152468,0],
			'sig':[2.03309,36.1748,423.726,2930.54,12088.5,3.9784,3629.36,21085.7,88093.5,389902,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.108426, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,49.2721,2.03607,0.433704,0.183238,0.119362,0],
			'sig':[1.94542,46.8733,707.781,6413.44,37545.8,8.31841,12550.9,105897,270470,729714,0]},
			{'Shell':'5D3/2', 'Func':2, 'BindEnergy':0.0415942, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,18.9017,0.781073,0.166377,0.070294,0.045789,0],
			'sig':[0.147015,8.5974,296.193,4941.33,33948,27.7018,44771.9,226887,1.20365e+07,2545710,0]},
			{'Shell':'5D5/2', 'Func':2, 'BindEnergy':0.0376618, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,17.1147,0.707229,0.150647,0.063648,0.04146,0],
			'sig':[0.097448,8.40332,360.462,6706.19,50046.8,41.8762,74827.9,402869,2.20614e+07,4196650,0]},
			{'Shell':'6S1/2', 'Func':2, 'BindEnergy':0.019339, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,8.78823,0.363155,0.077356,0.032683,0.021289,0],
			'sig':[0.619182,6.72206,58.1309,401.327,2302.45,59.5307,9449.21,41729.9,253141,1605020,0]},
			{'Shell':'6P1/2', 'Func':2, 'BindEnergy':0.00903104, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,4.10398,0.169589,0.036124,0.015262,0.009942,0],
			'sig':[0.239918,3.89794,43.7475,306.357,1357.96,184.36,18016.7,1456160,1.46502e+07,2.85703e+07,0]},
			{'Shell':'6P3/2', 'Func':2, 'BindEnergy':0.0062445, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,2.83769,0.117262,0.024978,0.010553,0.006874,0],
			'sig':[0.139622,3.0098,43.044,391.754,2370.47,433.118,39754.8,2284650,2.30078e+07,5.23318e+07,0]}] },
			'Rn':{'NSHELLS':24, 'ETERM':-2.095,  'shells':[
			{'Shell':'1S1/2', 'Func':1, 'BindEnergy':98.404, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,454.339,204.846,139.164,112.198,100.797,0],
			'sig':[0,0,0,0,0,32.7082,259.658,709.806,1230.24,1608.56,0]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':18.049, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,384.757,78.2137,36.098,23.4636,18.9374,18.067],
			'sig':[286.324,2972.9,0,0,0,5.97115,301.75,1641.26,3782.34,5549.05,5963.91]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':17.3371, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,369.582,75.1287,34.6742,22.5381,18.1904,17.3544],
			'sig':[184.544,4069.38,0,0,0,1.80936,221.736,2004.34,6352.87,10987.9,12345.5]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':14.6194, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,311.647,63.3518,29.2388,19.0051,15.339,14.634],
			'sig':[169.612,5201.73,0,0,0,1.67248,361.448,3972.32,13912.1,25430.2,28817.9]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':4.482, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,95.5445,19.4223,8.964,5.82657,4.7026,4.48648],
			'sig':[64.6179,732.538,5786.85,0,0,42.5357,1389.39,5717.68,11219.5,15059.7,15867.4]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':4.159, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,88.659,18.0226,8.318,5.40667,4.3637,4.16316],
			'sig':[40.2068,741.914,8263.9,0,0,30.1537,1891.12,9358.38,18830.8,24668.5,29424.5]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':3.538, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,75.4209,15.3316,7.076,4.59938,3.71214,3.54154],
			'sig':[39.2417,998.335,15222.5,0,0,47.1777,4247.64,24860.7,57111.9,81949.2,94896.7]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':3.0215, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,64.4105,13.0934,6.043,3.92793,3.17021,3.02452],
			'sig':[3.72481,251.647,10847.9,0,0,8.86661,3063.1,35888.9,122888,219814,1555680]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':2.8924, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,61.6584,12.5339,5.7848,3.7601,3.03476,2.89529],
			'sig':[2.49989,250.187,13483.7,359265,0,7.84288,4177.11,53618.8,189896,344056,2367020]},
			{'Shell':'4S1/2', 'Func':0, 'BindEnergy':1.097, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,23.3852,4.75375,2.194,1.42609,1.15099,1.0981],
			'sig':[17.1225,196.95,1709.78,10565.5,0,259.228,5127.47,16426.5,27496.6,33384,34959.8]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.929, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,422.166,17.4451,3.716,1.56999,1.0227,0],
			'sig':[10.2345,183.233,2109.27,13117,30837.3,0.079913,501.215,9699.65,25842.4,30759.3,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.768, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,349.003,14.4218,3.072,1.29791,0.845461,0],
			'sig':[9.93726,243.325,3672.86,31733.1,146492,0.077895,1185.84,30463,109737,170845,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.5666, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,257.48,10.6398,2.2664,0.957544,0.623747,0],
			'sig':[1.0205,62.1884,2213.63,37139.5,201149,0.007512,1292.48,65799.8,206197,184907,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.537, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,244.029,10.084,2.148,0.907521,0.591162,0],
			'sig':[0.684727,61.7869,2747.37,51662.2,315464,0.005323,1855.35,104140,337458,316494,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.219631, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,99.807,4.12432,0.878523,0.371172,0.241783,0],
			'sig':[0.007387,2.09459,296.885,19373,520579,0.002186,6192.97,704436,1681180,119903,0]},
			{'Shell':'4F7/2', 'Func':2, 'BindEnergy':0.212588, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,96.6063,3.99206,0.85035,0.359269,0.234029,0],
			'sig':[0.008377,2.45078,360.116,24213.7,669276,0.002965,8667.49,979375,2265210,165191,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.200831, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,91.2637,3.77129,0.803324,0.339401,0.221087,0],
			'sig':[4.0739,46.3649,407.379,2744.47,14580.5,3.03717,1877.47,19520.7,46664.3,54876.1,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.151771, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,68.9695,2.85002,0.607085,0.256491,0.167079,0],
			'sig':[2.23659,39.1639,450.547,3056.47,12372.7,3.31904,3301.2,19788.7,75461.7,327917,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.118817, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,53.9939,2.23119,0.475266,0.200798,0.1308,0],
			'sig':[2.12871,50.7741,758.426,6803.63,39616.2,6.97234,11398,100880,252484,626282,0]},
			{'Shell':'5D3/2', 'Func':2, 'BindEnergy':0.0486912, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,22.1268,0.914342,0.194765,0.082287,0.053602,0],
			'sig':[0.170608,9.86709,334.364,5458.49,36754,18.7007,40889.3,129309,7570710,2955380,0]},
			{'Shell':'5D5/2', 'Func':2, 'BindEnergy':0.044255, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,20.1109,0.831039,0.17702,0.07479,0.048719,0],
			'sig':[0.11292,9.6538,407.839,7431.88,54478.7,27.1053,68483.9,222145,1.36986e+07,4497880,0]},
			{'Shell':'6S1/2', 'Func':2, 'BindEnergy':0.0219397, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,9.97006,0.411992,0.087759,0.037078,0.024153,0],
			'sig':[0.697725,7.55133,64.9881,445.701,2547.71,52.4516,8863.21,41573.1,212389,1263300,0]},
			{'Shell':'6P1/2', 'Func':2, 'BindEnergy':0.0105726, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,4.80452,0.198537,0.04229,0.017867,0.011639,0],
			'sig':[0.29086,4.6922,51.9614,357.584,1567.24,165.204,15162.7,1169020,1.35398e+07,2.69445e+07,0]},
			{'Shell':'6P3/2', 'Func':2, 'BindEnergy':0.00712588, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,3.23822,0.133813,0.028503,0.012043,0.007845,0],
			'sig':[0.23038,4.94895,70.249,633.439,3824.14,551.077,52583,2657890,3.05865e+07,6.79243e+07,0]}] },
			'Fr':{'NSHELLS':24, 'ETERM':-2.157,  'shells':[
			{'Shell':'1S1/2', 'Func':1, 'BindEnergy':101.137, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,466.957,210.535,143.029,115.314,103.596,0],
			'sig':[0,0,0,0,0,31.9944,251.756,686.284,1188.5,1554.37,0]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':18.639, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,397.335,80.7704,37.278,24.2306,19.5564,18.6576],
			'sig':[296.321,3034.51,0,0,0,5.79519,289.815,1576.21,3633.45,5330.5,5726.51]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':17.9065, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,381.72,77.5961,35.813,23.2783,18.7878,17.9244],
			'sig':[197.661,4284.53,0,0,0,1.78469,216.021,1940.71,6133.7,10599.9,11879.3]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':15.0312, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,320.426,65.1363,30.0624,19.5405,15.771,15.0462],
			'sig':[179.735,5460.53,0,0,0,1.62679,349.418,3842.15,13457.4,24601.6,27843.1]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':4.652, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,99.1685,20.159,9.304,6.04757,4.88097,4.65665],
			'sig':[67.0797,753.291,5871.18,0,0,40.2351,1324.11,5452.16,10698.2,14343.7,15202.4]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':4.327, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,92.2403,18.7506,8.654,5.62507,4.53997,4.33133],
			'sig':[43.0241,779.583,8468.99,0,0,28.9278,1801.75,8913.32,17933.8,23499.7,24925]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':3.663, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,78.0856,15.8733,7.326,4.76188,3.84329,3.66666],
			'sig':[41.6333,1046.61,15742.7,0,0,44.9014,4058.74,23851.7,54968.7,79106.7,91997.1]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':3.1362, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,66.8556,13.5904,6.2724,4.07704,3.29056,3.13934],
			'sig':[4.07376,271.747,11546.3,0,0,8.35686,2892.12,33985.3,116673,208211,1432290]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':2.9997, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,2.92915,1,63.9457,12.9989,5.9994,3.89959,3.14734,3.0027],
			'sig':[2.72258,269.586,14340.2,0,0,7.28322,3925.11,50692.1,180248,327725,2252030]},
			{'Shell':'4S1/2', 'Func':0, 'BindEnergy':1.153, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,24.5789,4.99642,2.306,1.49889,1.20975,1.15415],
			'sig':[17.8634,203.805,1753.94,10689.8,0,241.903,4810.64,15469.8,25993.2,31721.2,33730]},
			{'Shell':'4P1/2', 'Func':2, 'BindEnergy':0.98, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,445.342,18.4028,3.92,1.65618,1.07884,0],
			'sig':[11.0043,193.56,2184.04,13225.4,29552.3,0.070723,465.379,9094.54,24473.5,29371,0]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.81, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,368.089,15.2105,3.24,1.36889,0.891697,0],
			'sig':[10.6014,256.58,3827.44,32666.9,148676,0.070961,1090.48,28607,104814,165224,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.6033, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,274.158,11.329,2.4132,1.01957,0.664149,0],
			'sig':[1.12571,67.602,2364.32,38783.4,202301,0.006375,1142.47,60534.3,200026,191195,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.577, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,262.207,10.8351,2.308,0.97512,0.635196,0],
			'sig':[0.753192,67.1091,2937,54118.7,319031,0.004454,1579.8,94146.7,324777,324697,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.246488, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,112.012,4.62866,0.985954,0.416561,0.271349,0],
			'sig':[0.008525,2.38788,333.179,21303.7,556148,0.001353,4465.52,575198,1800090,109305,0]},
			{'Shell':'4F7/2', 'Func':2, 'BindEnergy':0.238863, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,108.547,4.48547,0.955452,0.403674,0.262955,0],
			'sig':[0.009641,2.78954,403.793,26616.8,715483,0.001831,6212.44,797996,2448280,148537,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.220035, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,99.9909,4.13192,0.880142,0.371856,0.242228,0],
			'sig':[4.31973,48.8407,426.18,2847.6,14988.2,2.51213,1672.81,17778,43958.2,55705.2,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.169009, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,76.803,3.17373,0.676037,0.285623,0.186056,0],
			'sig':[2.45826,42.3176,477.886,3179.37,12626.6,2.73785,2921.14,18260.5,62075.5,251624,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.132957, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,60.42,2.49673,0.53183,0.224696,0.146368,0],
			'sig':[2.32741,54.9005,810.926,7203.27,41725.6,5.50117,9947.13,93407.4,232022,531928,0]},
			{'Shell':'5D3/2', 'Func':2, 'BindEnergy':0.0595378, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,27.0558,1.11803,0.238151,0.100618,0.065543,0],
			'sig':[0.197201,11.259,374.992,5991.9,39558,10.7603,34290.3,76739.5,3658160,1.61853e+07,0]},
			{'Shell':'5D5/2', 'Func':2, 'BindEnergy':0.0545529, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,24.7905,1.02442,0.218212,0.092193,0.060055,0],
			'sig':[0.130039,11.0168,458.344,8182.58,58945.6,14.4818,57083,127450,6339320,1.80061e+07,0]},
			{'Shell':'6S1/2', 'Func':2, 'BindEnergy':0.0278679, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,12.664,0.523314,0.111471,0.047096,0.030679,0],
			'sig':[0.786665,8.52336,73.1453,498.472,2841.09,37.4133,7173.57,38451.9,127379,560245,0]},
			{'Shell':'6P1/2', 'Func':2, 'BindEnergy':0.015165, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,6.89143,0.284774,0.06066,0.025628,0.016694,0],
			'sig':[0.361461,5.8364,64.0224,433.053,1879.62,105.093,9165.91,527249,7122330,3.01741e+07,0]},
			{'Shell':'6P3/2', 'Func':2, 'BindEnergy':0.0106123, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,4.82254,0.199281,0.042449,0.017934,0.011683,0],
			'sig':[0.30905,6.73806,95.7927,856.511,5166.66,348.738,41605.1,1091980,1.84381e+07,7.23773e+07,0]}] },
			'Ra':{'NSHELLS':24, 'ETERM':-2.221,  'shells':[
			{'Shell':'1S1/2', 'Func':1, 'BindEnergy':103.922, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,479.815,216.333,146.968,118.489,106.449,0],
			'sig':[0,0,0,0,0,31.3101,244.164,663.638,1147.82,1499.78,0]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':19.2367, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,410.076,83.3604,38.4734,25.0076,20.1835,19.2559],
			'sig':[306.344,3094.58,0,0,0,5.63081,278.547,1514.61,3491.29,5121.87,5501.39]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':18.4843, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,394.037,80.1,36.9686,24.0295,19.3941,18.5028],
			'sig':[211.453,4504.41,0,0,0,1.76241,210.69,1880.82,5925.33,10222,11428.8]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':15.4444, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,329.234,66.9269,30.8888,20.0776,16.2046,15.4598],
			'sig':[190.221,5724.52,0,0,0,1.58467,338.503,3719.79,13024.6,23807.6,26958.5]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':4.822, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,102.792,20.8957,9.644,6.26857,5.05933,4.82682],
			'sig':[69.5919,773.903,5947.18,0,0,38.3974,1264.32,5205.85,10210.7,13711.1,14467.4]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':4.4895, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,95.7044,19.4548,8.979,5.83632,4.71047,4.49399],
			'sig':[45.9796,817.758,8657.51,0,0,27.9549,1725.49,8520.22,17128.5,22414.1,23930.2]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':3.7918, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,80.8312,16.4314,7.5836,4.92932,3.97843,3.79559],
			'sig':[44.1171,1096.23,16268.6,0,0,42.7194,3877.76,22881.2,52901.8,76370.6,82590.9]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':3.2484, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,69.2474,14.0766,6.4968,4.2229,3.40828,3.25165],
			'sig':[4.4483,292.899,12257.7,0,0,7.8897,2745.01,32304.5,111104,198679,177188]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':3.1049, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,66.1883,13.4548,6.2098,4.03635,3.25772,3.108],
			'sig':[2.96144,289.993,15213.8,0,0,6.81388,3706.68,48087.6,171447,311221,214833]},
			{'Shell':'4S1/2', 'Func':0, 'BindEnergy':1.2084, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,25.7599,5.23649,2.4168,1.57091,1.26788,1.20961],
			'sig':[18.6202,210.706,1796.99,10796.8,0,226.922,4529.74,14609.6,24648.9,30129.3,32176.1]},
			{'Shell':'4P1/2', 'Func':0, 'BindEnergy':1.0576, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,22.5453,4.58301,2.1152,1.37487,1.10965,1.05866],
			'sig':[11.8346,204.558,2264.34,13339.9,0,305.868,7298.84,19680.3,26306.8,27586.1,29280.1]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.8791, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,399.49,16.5081,3.5164,1.48566,0.967766,0],
			'sig':[11.3144,270.821,3999.07,33804.2,150626,0.059388,935.522,25656.3,96879.2,155201,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.6359, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,288.973,11.9412,2.5436,1.07466,0.700037,0],
			'sig':[1.24039,73.3497,2518.4,40360,203749,0.005655,1039.39,56579.8,194991,198087,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.6027, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,273.885,11.3177,2.4108,1.01855,0.663489,0],
			'sig':[0.826027,72.6434,3123.74,56255.7,323509,0.004171,1465.79,89226.8,319067,341851,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.2989, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,135.829,5.61287,1.1956,0.505136,0.329047,0],
			'sig':[0.009833,2.7248,376.081,23819.8,611913,0.000558,2402.49,393223,1755930,120076,0]},
			{'Shell':'4F7/2', 'Func':2, 'BindEnergy':0.2989, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,135.829,5.61287,1.1956,0.505136,0.329047,0],
			'sig':[0.011098,3.1818,456.725,29953.4,797489,0.000652,2963.93,509080,2362530,161797,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.2544, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,115.607,4.77723,1.0176,0.429932,0.280059,0],
			'sig':[4.58084,51.4268,445.766,2958.89,15452.6,1.90909,1359.27,15092.7,39370,50218.1,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.2004, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,91.0679,3.76319,0.8016,0.338673,0.220612,0],
			'sig':[2.69416,45.6471,506.502,3306.69,12853.6,1.91933,2339.1,15853.7,47174.8,179422,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.1528, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,69.437,2.86934,0.6112,0.258229,0.168211,0],
			'sig':[2.53645,59.2412,866.092,7624.39,43971.8,3.861,8254.29,83413.6,208302,416361,0]},
			{'Shell':'5D3/2', 'Func':2, 'BindEnergy':0.0672, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,30.5377,1.26191,0.2688,0.113567,0.073978,0],
			'sig':[0.226391,12.7725,418.154,6537.44,42370.3,8.06064,31118.6,70931.6,2077290,2.70863e+07,0]},
			{'Shell':'5D5/2', 'Func':2, 'BindEnergy':0.0672, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,30.5377,1.26191,0.2688,0.113567,0.073978,0],
			'sig':[0.149073,12.5122,512.666,8971.58,63542.8,7.59292,45706.8,114508,2777720,4.40593e+07,0]},
			{'Shell':'6S1/2', 'Func':2, 'BindEnergy':0.0435, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,19.7677,0.816861,0.174,0.073514,0.047887,0],
			'sig':[0.886056,9.5844,81.9342,555.459,3162.23,17.5091,4264.08,28889.4,65586.4,260056,0]},
			{'Shell':'6P1/2', 'Func':2, 'BindEnergy':0.0188, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,8.5433,0.353034,0.0752,0.031772,0.020696,0],
			'sig':[0.436373,7.01217,75.9711,505.078,2168.34,82.3294,7616.54,335531,4094730,1.9157e+07,0]},
			{'Shell':'6P3/2', 'Func':2, 'BindEnergy':0.0188, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,8.5433,0.353034,0.0752,0.031772,0.020696,0],
			'sig':[0.385011,8.42786,119.413,1059.34,6383.58,130.73,25809.3,308458,4742940,3.13458e+07,0]}] },
			'Ac':{'NSHELLS':24, 'ETERM':-2.287,  'shells':[
			{'Shell':'1S1/2', 'Func':1, 'BindEnergy':106.755, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,492.897,222.231,150.975,121.719,109.351,0],
			'sig':[0,0,0,0,0,30.6567,236.888,641.889,1109.16,1449.54,0]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':19.84, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,422.937,85.9748,39.68,25.7919,20.8165,19.8598],
			'sig':[316.477,3151.5,0,0,0,5.48201,267.834,1456.67,3357.55,4923.82,5289.56]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':19.0832, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,406.804,82.6953,38.1664,24.808,20.0225,19.1023],
			'sig':[226.114,4733.35,0,0,0,1.74003,205.478,1822.6,5724.74,9864.78,11008.4]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':15.871, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,338.328,68.7755,31.742,20.6322,16.6522,15.8869],
			'sig':[201.241,6000.46,0,0,0,1.54255,327.728,3600.14,12607.2,23046.6,26069.3]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':5.002, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,106.63,21.6757,10.004,6.50257,5.24819,5.007],
			'sig':[72.138,794.611,6019.7,0,0,36.5615,1205.21,4964.37,9734.85,13080.3,13720.7]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':4.656, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,99.2537,20.1763,9.312,6.05277,4.88516,4.66066],
			'sig':[49.1042,856.942,8836.01,0,0,26.8873,1653.85,8148.22,16358.6,21413.1,22850.3]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':3.909, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,83.3296,16.9393,7.818,5.08167,4.1014,3.91291],
			'sig':[46.6983,1146.29,16771.6,0,0,41.1374,3736.7,22090.3,51169.1,74077.4,79779.9]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':3.3702, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,71.8438,14.6044,6.7404,4.38124,3.53608,3.37357],
			'sig':[4.85433,315.625,13025.1,0,0,7.43538,2592.81,30611.1,105577,188527,195329]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':3.219, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,68.6207,13.9492,6.438,4.18468,3.37744,3.22222],
			'sig':[3.21742,311.81,16155.4,0,0,6.32329,3482.08,45468.4,162752,295088,338237]},
			{'Shell':'4S1/2', 'Func':0, 'BindEnergy':1.269, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,27.0518,5.49909,2.538,1.64969,1.33146,1.27027],
			'sig':[19.3955,217.705,1840.07,10899.6,0,211.896,4251.28,13759.6,23289,28643.3,29793.4]},
			{'Shell':'4P1/2', 'Func':0, 'BindEnergy':1.08, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,23.0228,4.68008,2.16,1.40399,1.13316,1.08108],
			'sig':[12.6863,215.212,2330.64,13359.8,0,305.483,7156.79,19147,25651.1,27067,29640.3]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.89, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,404.443,16.7128,3.56,1.50408,0.979766,0],
			'sig':[12.033,284.425,4142.14,34493.1,152799,0.061493,947.457,25668.3,96631.9,155587,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.6749, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,306.695,12.6735,2.6996,1.14057,0.742971,0],
			'sig':[1.36414,79.5076,2682.74,42052,204244,0.004857,925.639,52212,188150,202630,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.637, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,289.472,11.9618,2.548,1.07652,0.701248,0],
			'sig':[0.904943,78.5925,3324.62,58619.4,326985,0.003751,1309.66,82803.7,309027,346923,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.303944, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,138.121,5.70758,1.21577,0.51366,0.3346,0],
			'sig':[0.011268,3.0785,416.33,25565.7,630210,0.000588,2465.2,390488,1801450,137988,0]},
			{'Shell':'4F7/2', 'Func':2, 'BindEnergy':0.295067, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,134.088,5.54089,1.18027,0.498658,0.324828,0],
			'sig':[0.012679,3.58471,503.618,31914,811952,0.000799,3393.06,539409,2470860,183959,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.261255, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,118.722,4.90596,1.04502,0.441517,0.287606,0],
			'sig':[4.84824,54.0132,464.316,3051.77,15752.6,1.90676,1345.01,14846,39057.3,50900,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.206171, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,93.6906,3.87157,0.824686,0.348426,0.226966,0],
			'sig':[2.9485,49.0861,534.17,3416.87,13048.9,1.87781,2321.25,15658.4,45475.8,160936,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.163234, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,74.1788,3.06528,0.652938,0.275863,0.179698,0],
			'sig':[2.76166,63.7891,922.139,8038.07,46089.5,3.45411,7736.16,80580.1,203540,375717,0]},
			{'Shell':'5D3/2', 'Func':2, 'BindEnergy':0.0831361, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,37.7796,1.56116,0.332544,0.140499,0.091521,0],
			'sig':[0.259258,14.4386,464.839,7122.89,45260.4,4.385,24185,72250.3,1012150,6806870,0]},
			{'Shell':'5D5/2', 'Func':2, 'BindEnergy':0.0769389, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,34.9634,1.44479,0.307756,0.130025,0.084699,0],
			'sig':[0.170383,14.1435,570.173,9780.2,68143.5,5.16855,39766.3,124322,1605790,1.14353e+07,0]},
			{'Shell':'6S1/2', 'Func':2, 'BindEnergy':0.0404636, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,18.3879,0.759842,0.161854,0.068383,0.044545,0],
			'sig':[0.98714,10.6504,90.5672,609.544,3449.4,22.465,5156.59,33851.1,80294.4,275116,0]},
			{'Shell':'6P1/2', 'Func':2, 'BindEnergy':0.0251851, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,11.4449,0.472936,0.10074,0.042562,0.027725,0],
			'sig':[0.515478,8.19325,87.4149,571.222,2425.96,52.8047,5783.99,182337,2409590,9638920,0]},
			{'Shell':'6P3/2', 'Func':2, 'BindEnergy':0.0184021, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,8.36247,0.345562,0.073608,0.031099,0.020258,0],
			'sig':[0.456029,9.97208,140.421,1234.91,7425.08,161.046,30990.6,365110,4785400,2.33296e+07,0]}] },
			'Th':{'NSHELLS':24, 'ETERM':-2.353,  'shells':[
			{'Shell':'1S1/2', 'Func':1, 'BindEnergy':109.651, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,506.266,228.258,155.07,125.021,112.317,0],
			'sig':[0,0,0,0,0,30.0256,229.868,620.88,1071.32,1398.48,0]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':20.4721, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,436.412,88.7139,40.9442,26.6136,21.4797,20.4926],
			'sig':[326.748,3206.74,0,0,0,5.32942,257.386,1399.47,3225.71,4730.33,5081.21]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':19.6932, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,419.807,85.3386,39.3864,25.601,20.6625,19.7129],
			'sig':[241.548,4967.71,0,0,0,1.71924,200.575,1767.55,5533.5,9516.23,10637.3]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':16.3003, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,347.48,70.6358,32.6006,21.1903,17.1026,16.3166],
			'sig':[212.661,6283.76,0,0,0,1.50324,317.606,3487.48,12211.1,22325.4,25228.9]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':5.1823, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,110.473,22.457,10.3646,6.73696,5.43737,5.18748],
			'sig':[74.7322,815.166,6084.66,0,0,34.9096,1150.95,4740.58,9292.07,12494.1,13091.6]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':4.8304, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,102.971,20.9321,9.6608,6.27949,5.06815,4.83523],
			'sig':[52.3884,897.195,9006.38,0,0,25.9803,1583.89,7787.53,15613.9,20437,21649.2]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':4.0461, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,86.2523,17.5334,8.0922,5.2599,4.24524,4.05015],
			'sig':[49.4018,1199.05,17318.7,0,0,39.1069,3568.88,21193.2,49261.1,71324.7,77849]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':3.4908, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,74.4147,15.1271,6.9816,4.53802,3.66261,3.49429],
			'sig':[5.28866,339.584,13815.9,0,0,7.04424,2459.69,29104.2,100584,179252,217436]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':3.332, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,71.0295,14.4389,6.664,4.33158,3.496,3.33533],
			'sig':[3.49079,334.797,17127.4,0,0,5.86713,3284.89,43138.1,154990,281640,284613]},
			{'Shell':'4S1/2', 'Func':0, 'BindEnergy':1.3295, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,28.3415,5.76126,2.659,1.72834,1.39494,1.33083],
			'sig':[20.1967,224.785,1882.17,10988.6,0,198.75,4002.68,12988.8,22050.8,27266.7,27966.6]},
			{'Shell':'4P1/2', 'Func':0, 'BindEnergy':1.1682, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,24.903,5.06229,2.3364,1.51865,1.2257,1.16937],
			'sig':[13.611,227.001,2411.93,13423.8,0,267.613,6459.7,17602.9,23771.5,25100.9,26531]},
			{'Shell':'4P3/2', 'Func':2, 'BindEnergy':0.9673, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,439.571,18.1644,3.8692,1.63472,1.06486,0],
			'sig':[12.812,299.763,4325.42,35709,154997,0.051513,808.67,22940.1,89038.3,145700,0]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.7141, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,324.509,13.4097,2.8564,1.20682,0.786124,0],
			'sig':[1.49804,86.0589,2854,43763.2,204403,0.004223,831.181,48406.7,181424,203291,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.6764, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,307.377,12.7017,2.7056,1.1431,0.744622,0],
			'sig':[0.990161,84.9544,3537.86,61136.7,329523,0.003323,1151.62,76118,296862,351033,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.3444, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,156.506,6.46728,1.3776,0.58203,0.379136,0],
			'sig':[0.012916,3.48762,465.507,28162.8,678549,0.000332,1685.94,305011,1679500,175044,0]},
			{'Shell':'4F7/2', 'Func':2, 'BindEnergy':0.3352, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,152.325,6.29452,1.3408,0.566482,0.369008,0],
			'sig':[0.014497,4.05466,562.678,35155.7,875816,0.000454,2291.96,418691,2306520,230359,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.2902, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,131.876,5.44949,1.1608,0.490433,0.31947,0],
			'sig':[5.12544,56.6922,483.871,3157.56,16144.9,1.59335,1164.63,13204.6,35900.1,47830,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.2294, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,104.246,4.30777,0.9176,0.387682,0.252537,0],
			'sig':[3.22147,52.7174,563.079,3531.9,13205.3,1.54382,2036.42,14326.3,39397.6,133588,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.1818, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,82.6155,3.41392,0.7272,0.307239,0.200136,0],
			'sig':[3.00122,68.5812,981.034,8479.3,48400.3,2.7294,6723.08,73879.3,190434,334628,0]},
			{'Shell':'5D3/2', 'Func':2, 'BindEnergy':0.0943, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,42.8528,1.7708,0.3772,0.159365,0.103811,0],
			'sig':[0.295376,16.2332,513.687,7711.88,48096.1,3.09335,21043.4,77838.1,631898,3774980,0]},
			{'Shell':'5D5/2', 'Func':2, 'BindEnergy':0.0879, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,39.9445,1.65062,0.3516,0.14855,0.096766,0],
			'sig':[0.193716,15.9033,630.955,10614.9,72772,3.4173,34181.9,135001,965734,5904870,0]},
			{'Shell':'6S1/2', 'Func':2, 'BindEnergy':0.0595, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,27.0386,1.11732,0.238,0.100554,0.065501,0],
			'sig':[1.09475,11.742,99.2632,664.997,3763.64,11.45,3186.36,24798.4,56315.6,174274,0]},
			{'Shell':'6P1/2', 'Func':2, 'BindEnergy':0.049, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,22.2671,0.920142,0.196,0.082809,0.053942,0],
			'sig':[0.599824,9.40907,98.811,635.234,2668.69,14.2234,2937.01,40275.6,688249,3604660,0]},
			{'Shell':'6P3/2', 'Func':2, 'BindEnergy':0.043, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,19.5405,0.807472,0.172,0.072669,0.047337,0],
			'sig':[0.530632,11.5331,161.25,1410.66,8507.93,25.3249,11615.6,91773.8,862096,6226570,0]}] },
			'Pa':{'NSHELLS':24, 'ETERM':-2.421,  'shells':[
			{'Shell':'1S1/2', 'Func':1, 'BindEnergy':112.601, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,519.889,234.4,159.242,128.385,115.339,0],
			'sig':[0,0,0,0,0,29.4218,223.136,600.697,1035.43,1351.73,0]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':21.1046, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,449.895,91.4548,42.2092,27.4358,22.1433,21.1257],
			'sig':[337.117,3259.91,0,0,0,5.19537,247.797,1346.48,3103.39,4549.07,4889.18]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':20.3137, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,433.035,88.0275,40.6274,26.4077,21.3135,20.334],
			'sig':[257.906,5207.94,0,0,0,1.70157,195.931,1716.46,5356.15,9198.3,10276.6]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':16.7331, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,356.706,72.5113,33.4662,21.7529,17.5567,16.7498],
			'sig':[224.646,6579.08,0,0,0,1.46702,308.214,3383.15,11847.1,21659.8,24503.1]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':5.3669, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,114.408,23.257,10.7338,6.97693,5.63105,5.37227],
			'sig':[77.3622,835.907,6148.07,0,0,33.3526,1100.02,4531.1,8875.43,11910.4,12559.3]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':5.0009, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,106.606,21.6709,10.0018,6.50114,5.24704,5.0059],
			'sig':[55.8596,938.531,9165.86,0,0,25.2571,1523.98,7469.33,14942.2,19542.1,20611.7]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':4.1738, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,88.9745,18.0868,8.3476,5.42591,4.37923,4.17797],
			'sig':[52.2286,1253.23,17866.4,0,0,37.5625,3435.59,20462.5,47677.2,69167.1,75423.3]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':3.6112, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,76.9813,15.6488,7.2224,4.69454,3.78894,3.61481],
			'sig':[5.75961,365.342,14669,0,0,6.70612,2344.94,27821.3,96391,172092,199770]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':3.4418, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,73.3702,14.9147,6.8836,4.47432,3.6112,3.44524],
			'sig':[3.78539,359.354,18164.5,0,0,5.52109,3122.33,41225.8,148619,270617,243040]},
			{'Shell':'4S1/2', 'Func':0, 'BindEnergy':1.3871, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,29.5693,6.01087,2.7742,1.80322,1.45537,1.38849],
			'sig':[21.0021,231.889,1923.85,11070,0,187.91,3793.62,12330.1,20968.8,25971.4,26566.7]},
			{'Shell':'4P1/2', 'Func':0, 'BindEnergy':1.2243, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,26.0989,5.30539,2.4486,1.59158,1.28456,1.22552],
			'sig':[14.5761,238.804,2485.85,13426.3,0,251.955,6102.92,16669.3,22509.7,23724.2,26403.7]},
			{'Shell':'4P3/2', 'Func':0, 'BindEnergy':1.0067, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,21.4602,4.36244,2.0134,1.3087,1.05625,1.00771],
			'sig':[13.6209,315.044,4494.87,36691.6,0,555.757,18990.6,68248.2,119065,148119,170990]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.7434, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,337.824,13.9599,2.9736,1.25633,0.81838,0],
			'sig':[1.6423,92.9963,3031,45459.7,204357,0.003935,784.074,46293.4,177026,205539,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.7082, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,321.828,13.2989,2.8328,1.19685,0.779629,0],
			'sig':[1.08177,91.7049,3760.6,63706.5,331340,0.00311,1058.86,71959.9,288209,349292,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.3712, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,168.685,6.97055,1.4848,0.627322,0.408639,0],
			'sig':[0.014752,3.93604,518.093,30809.9,723687,0.000254,1390.44,268268,1602620,154226,0]},
			{'Shell':'4F7/2', 'Func':2, 'BindEnergy':0.3595, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,163.368,6.75084,1.438,0.607549,0.395759,0],
			'sig':[0.016514,4.56707,625.224,38389.3,933007,0.000364,1922.26,372285,2212280,202474,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.3096, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,140.692,5.8138,1.2384,0.523219,0.340826,0],
			'sig':[5.39868,59.2882,502.306,3254.18,16468.6,1.38926,1076.48,12352.9,33862.8,45490.1,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.233624, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,106.166,4.38708,0.934495,0.39482,0.257187,0],
			'sig':[3.50053,56.2885,589.69,3624.11,13284.5,1.60461,2043.36,14154.7,39618.5,134923,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.18305, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,83.1836,3.43739,0.7322,0.309351,0.201513,0],
			'sig':[3.23309,73.0762,1033.86,8852.53,50242.8,2.88204,6938,75841,194803,341960,0]},
			{'Shell':'5D3/2', 'Func':2, 'BindEnergy':0.0966789, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,43.9339,1.81548,0.386716,0.163386,0.10643,0],
			'sig':[0.33087,17.9034,556.263,8182.76,50086.1,3.14749,21223.2,79335.7,639017,3930550,0]},
			{'Shell':'5D5/2', 'Func':2, 'BindEnergy':0.0892408, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,40.5538,1.6758,0.356963,0.150815,0.098242,0],
			'sig':[0.215998,17.4952,682.323,11258.5,75960.1,3.56515,35011.5,137911,1001620,6357600,0]},
			{'Shell':'6S1/2', 'Func':2, 'BindEnergy':0.0454585, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,20.6578,0.853639,0.181834,0.076824,0.050044,0],
			'sig':[1.13141,12.0351,100.865,670.138,3754.41,20.0665,4731.22,31794.9,81578,277155,0]},
			{'Shell':'6P1/2', 'Func':2, 'BindEnergy':0.0285451, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,12.9718,0.536032,0.11418,0.048241,0.031424,0],
			'sig':[0.630836,9.71265,99.9531,630.238,2609.6,47.175,5376.1,160319,2133790,8486700,0]},
			{'Shell':'6P3/2', 'Func':2, 'BindEnergy':0.0203206, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,9.23429,0.381588,0.081282,0.034341,0.02237,0],
			'sig':[0.545299,11.6767,161,1393.06,8330.91,148.433,30669.7,333496,4265280,2.10507e+07,0]}] },
			'U':{'NSHELLS':24, 'ETERM':-2.49,  'shells':[
			{'Shell':'1S1/2', 'Func':1, 'BindEnergy':115.606, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,533.762,240.655,163.492,131.811,118.417,0],
			'sig':[0,0,0,0,0,28.842,216.663,581.248,1000.75,1306.56,0]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':21.7574, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,463.811,94.2837,43.5148,28.2845,22.8283,21.7792],
			'sig':[347.512,3312.69,0,0,0,5.0467,238.441,1294.84,2983.78,4374.05,4702.31]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':20.9476, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,446.548,90.7745,41.8952,27.2317,21.9786,20.9685],
			'sig':[275.066,5450.26,0,0,0,1.68461,191.638,1667.37,5184.47,8887,9914.98]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':17.1663, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,365.941,74.3886,34.3326,22.3161,18.0112,17.1835],
			'sig':[237.039,6878.43,0,0,0,1.43384,299.444,3284.61,11500.2,21017.8,23796.3]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':5.548, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,118.269,24.0417,11.096,7.21236,5.82107,5.55355],
			'sig':[80.0253,856.125,6198.5,0,0,31.9934,1054.08,4338.33,8489.07,11394.7,11993.2]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':5.1822, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,110.471,22.4566,10.3644,6.73683,5.43726,5.18738],
			'sig':[59.4962,980.76,9314.13,0,0,24.4867,1463.06,7151.4,14279.7,18608.2,19801.9]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':4.3034, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,91.7372,18.6484,8.6068,5.59439,4.51521,4.3077],
			'sig':[55.1472,1308.35,18408.4,0,0,36.0961,3308.43,19758.1,46138.5,67105.4,72027.1]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':3.7276, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,79.4627,16.1532,7.4552,4.84586,3.91107,3.73133],
			'sig':[6.25987,392.13,15519.8,0,0,6.42884,2246.63,26677.9,92562.4,165678,161129]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':3.5517, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,75.7129,15.391,7.1034,4.61719,3.72651,3.55525],
			'sig':[4.09871,385.03,19217.3,0,0,5.21098,2972.63,39420.2,142481,259586,218466]},
			{'Shell':'4S1/2', 'Func':0, 'BindEnergy':1.4408, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,30.7141,6.24357,2.8816,1.87303,1.51171,1.44224],
			'sig':[21.8197,238.938,1962.87,11122.6,0,179.129,3616.7,11754.9,20010.6,24775.6,25608.9]},
			{'Shell':'4P1/2', 'Func':0, 'BindEnergy':1.2726, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,27.1285,5.51469,2.5452,1.65437,1.33524,1.27387],
			'sig':[15.5962,250.808,2555.26,13389.1,0,241.629,5830.26,15898.3,21466.6,22644.9,25456.2]},
			{'Shell':'4P3/2', 'Func':0, 'BindEnergy':1.0449, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,22.2745,4.52798,2.0898,1.35836,1.09633,1.04594],
			'sig':[14.4561,330.643,4663.99,37632.7,0,529.207,18250.5,66057.5,115953,145725,141867]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.7804, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,354.638,14.6547,3.1216,1.31886,0.859111,0],
			'sig':[1.79939,100.412,3217.19,47229.1,203494,0.003539,720.359,43531.6,171140,204808,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.7377, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,335.234,13.8528,2.9508,1.2467,0.812105,0],
			'sig':[1.18061,98.8115,3986.34,66153.6,333878,0.002971,987.694,68520.5,280925,351001,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.3913, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,177.819,7.34799,1.5652,0.66129,0.430767,0],
			'sig':[0.016799,4.42458,573.095,33343.7,759709,0.00022,1242.75,246723,1552040,155875,0]},
			{'Shell':'4F7/2', 'Func':2, 'BindEnergy':0.3809, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,173.093,7.1527,1.5236,0.643715,0.419318,0],
			'sig':[0.018759,5.12652,691.397,41594.4,982997,0.00031,1681.14,338206,2135760,203558,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.3237, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,147.099,6.07857,1.2948,0.547047,0.356349,0],
			'sig':[5.68614,61.9412,520.421,3343.24,16722.4,1.32322,1028.75,11836.5,32616,44416,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.2593, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,117.834,4.86924,1.0372,0.438213,0.285453,0],
			'sig':[3.80144,60.0876,617.836,3722.44,13322.1,1.32734,1789.1,12876.5,34906.5,119073,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.1951, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,88.6594,3.66367,0.7804,0.329716,0.214778,0],
			'sig':[3.48344,77.9059,1090.79,9263.06,52299.2,2.57604,6471.06,72662.8,188445,325468,0]},
			{'Shell':'5D3/2', 'Func':2, 'BindEnergy':0.105, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,47.7152,1.97173,0.42,0.177448,0.11559,0],
			'sig':[0.370926,19.7877,604.218,8715.61,52328.7,2.62085,19450.3,81746.1,509537,3205390,0]},
			{'Shell':'5D5/2', 'Func':2, 'BindEnergy':0.0963, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,43.7617,1.80836,0.3852,0.162745,0.106013,0],
			'sig':[0.241214,19.3023,740.695,11996,79632,2.94554,32409.4,142581,805837,5159190,0]},
			{'Shell':'6S1/2', 'Func':2, 'BindEnergy':0.0707, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,32.1283,1.32763,0.2828,0.119482,0.077831,0],
			'sig':[1.19681,12.658,105.485,698.402,3911.92,8.77221,2555.12,20492.1,50161.7,174645,0]},
			{'Shell':'6P1/2', 'Func':2, 'BindEnergy':0.0423, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,19.2224,0.794327,0.1692,0.071486,0.046566,0],
			'sig':[0.688192,10.4296,105.452,653.459,2669.1,21.7012,3465.79,66133.6,1070070,5223840,0]},
			{'Shell':'6P3/2', 'Func':2, 'BindEnergy':0.0323, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,14.6781,0.606543,0.1292,0.054586,0.035558,0],
			'sig':[0.585495,12.4282,169.844,1460.21,8725.38,54.2631,17623.2,145705,1739230,1.14419e+07,0]}] },
			'Np':{'NSHELLS':24, 'ETERM':-2.561,  'shells':[
			{'Shell':'1S1/2', 'Func':1, 'BindEnergy':118.678, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,547.945,247.05,167.836,135.313,121.564,0],
			'sig':[0,0,0,0,0,28.2804,210.404,562.409,966.828,1260.97,0]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':22.4268, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,478.081,97.1844,44.8536,29.1547,23.5306,22.4492],
			'sig':[358.021,3363.82,0,0,0,4.92013,229.467,1245.22,2869.32,4204.15,4522.81]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':21.6005, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,460.466,93.6037,43.201,28.0805,22.6637,21.6221],
			'sig':[293.221,5701.02,0,0,0,1.66862,187.488,1619.99,5019.8,8590.77,9578.12]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':17.61, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,375.399,76.3113,35.22,22.8929,18.4767,17.6276],
			'sig':[249.917,7188.11,0,0,0,1.40063,290.806,3188.48,11160.8,20406.2,23114.1]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':5.7232, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,122.004,24.801,11.4464,7.44012,6.00489,5.72892],
			'sig':[82.6886,875.77,6237.14,0,0,30.8207,1013.33,4163.82,8134.54,10917.4,11430.9]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':5.3662, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,114.393,23.2539,10.7324,6.97602,5.63032,5.37157],
			'sig':[63.3256,1023.74,9445.92,0,0,23.7918,1406.44,6851.91,13648.6,17771.2,18879.8]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':4.4347, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,94.5362,19.2174,8.8694,5.76508,4.65297,4.43913],
			'sig':[58.1929,1364.92,18954,0,0,34.7374,3188.69,19091.8,44680.2,65136.8,69643.9]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':3.8503, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,82.0783,16.6849,7.7006,5.00536,4.03981,3.85415],
			'sig':[6.79913,420.668,16422.2,0,0,6.14496,2147.91,25546.4,88784.6,158912,146705]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':3.6658, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,78.1453,15.8854,7.3316,4.76552,3.84623,3.66947],
			'sig':[4.43223,412.201,20326.2,0,0,4.90918,2827.04,37674.6,136563,248966,254815]},
			{'Shell':'4S1/2', 'Func':0, 'BindEnergy':1.5007, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,31.991,6.50314,3.0014,1.9509,1.57456,1.5022],
			'sig':[22.6633,246.084,2001.5,11170.1,0,169.774,3432,11163.2,19031.6,23651.3,24237.7]},
			{'Shell':'4P1/2', 'Func':0, 'BindEnergy':1.3277, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,28.3031,5.75346,2.6554,1.726,1.39305,1.32903],
			'sig':[16.665,263.161,2624.28,13324.2,0,229.717,5537.27,15095.4,20377.1,21490.2,24530.6]},
			{'Shell':'4P3/2', 'Func':0, 'BindEnergy':1.0868, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,23.1677,4.70955,2.1736,1.41283,1.14029,1.08789],
			'sig':[15.3379,346.846,4837.91,38605.5,0,501.071,17473.7,63754.7,112587,141943,135961]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.8159, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,370.77,15.3213,3.2636,1.37886,0.898192,0],
			'sig':[1.96732,108.228,3409.01,48979.2,202572,0.003233,669.419,41220.9,165915,202651,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.7703, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,350.048,14.465,3.0812,1.30179,0.847993,0],
			'sig':[1.28595,106.333,4222.97,68694.3,335440,0.002817,913.38,64906.4,272650,352826,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.415, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,188.589,7.79304,1.66,0.701343,0.456857,0],
			'sig':[0.019085,4.96375,633.198,36101.9,799233,0.000186,1083.16,223569,1489900,157314,0]},
			{'Shell':'4F7/2', 'Func':2, 'BindEnergy':0.4044, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,183.772,7.59399,1.6176,0.683429,0.445188,0],
			'sig':[0.021256,5.74193,763.298,45035.2,1035870,0.000264,1456.13,305420,2046790,206386,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.323735, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,147.115,6.07923,1.29494,0.547107,0.356387,0],
			'sig':[5.97099,64.5436,537.474,3418.4,16873.3,1.39665,1058.48,11987.7,32718.3,45181.7,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.2834, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,128.786,5.3218,1.1336,0.478941,0.311984,0],
			'sig':[4.12362,64.0137,645.588,3811.54,13313.1,1.14798,1600.13,11851.1,31477,107533,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.2061, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,93.6582,3.87023,0.8244,0.348305,0.226887,0],
			'sig':[3.74916,82.9004,1148.31,9672.45,54308.5,2.26945,6114.09,70203.7,183511,313201,0]},
			{'Shell':'5D3/2', 'Func':2, 'BindEnergy':0.1093, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,49.6693,2.05248,0.4372,0.184715,0.120324,0],
			'sig':[0.414069,21.7738,653.189,9236.74,54432.6,2.44803,19083.3,83930.6,458382,2766690,0]},
			{'Shell':'5D5/2', 'Func':2, 'BindEnergy':0.1013, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,46.0338,1.90225,0.4052,0.171195,0.111517,0],
			'sig':[0.268242,21.2055,800.543,12726.7,83133.5,2.67541,31203.2,146622,699684,4388130,0]},
			{'Shell':'6S1/2', 'Func':2, 'BindEnergy':0.0496075, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,22.5432,0.93155,0.19843,0.083836,0.054611,0],
			'sig':[1.2601,13.2373,109.376,717.506,3969.33,18.5169,4399.45,29880.6,85173.1,294023,0]},
			{'Shell':'6P1/2', 'Func':2, 'BindEnergy':0.0312007, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,14.1785,0.585899,0.124803,0.052729,0.034348,0],
			'sig':[0.748399,11.1332,110.328,670.86,2701.27,43.9923,5026.18,151541,2019850,8169040,0]},
			{'Shell':'6P3/2', 'Func':2, 'BindEnergy':0.0215627, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,9.79875,0.404913,0.086251,0.036441,0.023737,0],
			'sig':[0.627067,13.154,177.685,1513.72,8989.63,143.882,30503.5,320979,4110260,2.10998e+07,0]}] },
			'Pu':{'NSHELLS':24, 'ETERM':-2.633,  'shells':[
			{'Shell':'1S1/2', 'Func':1, 'BindEnergy':122.011, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,563.335,253.989,172.55,139.114,124.978,0],
			'sig':[0,0,0,0,0,27.6589,203.863,543.037,932.557,1216.44,0]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':22.9714, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,489.69,99.5443,45.9428,29.8626,24.102,22.9944],
			'sig':[367.729,3396.91,0,0,0,4.86641,223.531,1208.83,2779.04,4067.42,4373.52]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':22.1644, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,472.487,96.0473,44.3288,28.8136,23.2553,22.1866],
			'sig':[311.379,5925.53,0,0,0,1.67089,185.498,1587.81,4892.07,8344.1,9326.02]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':17.9039, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,381.664,77.5849,35.8078,23.275,18.7851,17.9218],
			'sig':[262.019,7425.42,0,0,0,1.40636,289.034,3149.56,10976.1,20016.3,22676.2]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':5.83572, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,124.402,25.2886,11.6714,7.5864,6.12295,5.84156],
			'sig':[85.3042,893.161,6244.39,0,0,30.4892,993.894,4057.85,7892.47,10576.4,11062.1]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':5.46938, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,116.593,23.701,10.9388,7.11016,5.73858,5.47485],
			'sig':[67.1786,1062.95,9510.37,0,0,24.0966,1394.67,6712.42,13268.9,17222,18054.4]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':4.48219, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,95.5486,19.4232,8.96439,5.82682,4.7028,4.48668],
			'sig':[61.198,1415.44,19313.7,0,0,35.4085,3204.42,19024.3,44315.2,64500.9,68563.8]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':3.90746, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,83.2968,16.9326,7.81492,5.07967,4.09978,3.91137],
			'sig':[7.35285,447.757,17101.7,0,0,6.27243,2157.6,25363.4,87442,155715,152188]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':3.70962, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,79.0795,16.0753,7.41925,4.82249,3.89221,3.71333],
			'sig':[4.77491,437.751,21126.4,0,0,5.0214,2852.05,37555.8,134965,245065,195620]},
			{'Shell':'4S1/2', 'Func':0, 'BindEnergy':1.50245, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,32.0282,6.51071,3.00489,1.95317,1.5764,1.50395],
			'sig':[23.4858,252.653,2029,11128.9,0,174.167,3455.89,11104.7,18853.8,23260,25298.6]},
			{'Shell':'4P1/2', 'Func':0, 'BindEnergy':1.33662, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,28.4932,5.79211,2.67324,1.7376,1.40241,1.33796],
			'sig':[17.7766,275.221,2680.62,13212.6,0,236.806,5535.34,14822.2,19881.2,21007.9,24203.4]},
			{'Shell':'4P3/2', 'Func':0, 'BindEnergy':1.07618, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,22.9414,4.66354,2.15237,1.39903,1.12915,1.07726],
			'sig':[16.2236,362.33,4983.04,39169.7,0,535.813,18163.6,65394.9,114983,144185,174532]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.813765, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,369.8,15.2812,3.25506,1.37525,0.895842,0],
			'sig':[2.14437,116.096,3582.24,50177.3,207407,0.003609,717.054,42542.4,168416,210807,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.766256, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,348.21,14.3891,3.06502,1.29496,0.843541,0],
			'sig':[1.39684,113.903,4436.46,70429.5,343121,0.003134,985.586,67331.6,278058,363045,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.420633, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,191.149,7.89882,1.68253,0.710863,0.463058,0],
			'sig':[0.021626,5.5453,694.632,38589.2,826358,0.000197,1123.02,226209,1499210,125730,0]},
			{'Shell':'4F7/2', 'Func':2, 'BindEnergy':0.408012, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,185.413,7.66182,1.63205,0.689534,0.449164,0],
			'sig':[0.024004,6.40051,836.103,48065.2,1069790,0.000287,1534.39,312322,2072390,163709,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.334984, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,152.227,6.29046,1.33993,0.566117,0.36877,0],
			'sig':[6.25839,67.1514,554.618,3498.36,17051.4,1.3584,1026.17,11610.9,31646.9,44190.3,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.269481, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,122.46,5.06042,1.07792,0.455418,0.296661,0],
			'sig':[4.45187,67.857,670.282,3871.65,13290.7,1.42235,1782.82,12409.3,34837,118919,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.205866, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,93.5517,3.86583,0.823463,0.34791,0.226629,0],
			'sig':[4.01316,87.7984,1203.22,10046.7,56026,2.44279,6373.84,72398.4,188139,322806,0]},
			{'Shell':'5D3/2', 'Func':2, 'BindEnergy':0.110411, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,50.1743,2.07335,0.441646,0.186593,0.121548,0],
			'sig':[0.458602,23.7738,700.824,9719.63,56182.2,2.60039,19611.4,84586.8,489790,2944720,0]},
			{'Shell':'5D5/2', 'Func':2, 'BindEnergy':0.100979, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,45.8879,1.89622,0.403916,0.170653,0.111164,0],
			'sig':[0.296179,23.1048,857.66,13386.4,86037.2,2.97228,32789.4,148381,774187,4934890,0]},
			{'Shell':'6S1/2', 'Func':2, 'BindEnergy':0.0486186, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,22.0938,0.912979,0.194474,0.082165,0.053522,0],
			'sig':[1.29459,13.4919,110.574,720.643,3955.14,19.6163,4508.09,29780.5,96618.5,344780,0]},
			{'Shell':'6P1/2', 'Func':2, 'BindEnergy':0.0298109, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,13.547,0.559801,0.119244,0.05038,0.032818,0],
			'sig':[0.781207,11.4099,110.866,661.611,2621.77,48.9274,5199.76,182419,2407820,1.1601e+07,0]},
			{'Shell':'6P3/2', 'Func':2, 'BindEnergy':0.0199005, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,9.0434,0.3737,0.079602,0.033631,0.021908,0],
			'sig':[0.635721,13.1531,175.566,1484.29,8772.58,169.568,32570.3,382322,5384570,3.35049e+07,0]}] },
			'Am':{'NSHELLS':24, 'ETERM':-2.707,  'shells':[
			{'Shell':'1S1/2', 'Func':1, 'BindEnergy':125.027, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,577.259,260.267,176.815,142.552,128.067,0],
			'sig':[0,0,0,0,0,27.2104,198.525,526.594,902.563,1175.51,0]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':23.7729, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,506.776,103.018,47.5458,30.9046,24.943,23.7967],
			'sig':[378.896,3446.49,0,0,0,4.70256,213.303,1154.72,2658.31,3891.89,4187.01]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':22.944, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,489.106,99.4257,45.888,29.827,24.0733,22.9669],
			'sig':[332.366,6215.47,0,0,0,1.63605,179.94,1532.51,4712.97,8032.95,8973.34]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':18.5041, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,394.459,80.1858,37.0082,24.0552,19.4149,18.5226],
			'sig':[277.174,7829.22,0,0,0,1.34128,275.126,3012.89,10541.5,19273.1,21851.9]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':6.1205, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,130.473,26.5226,12.241,7.95661,6.42174,6.12662],
			'sig':[88.1699,915.517,6306.73,0,0,28.2682,927.602,3807.73,7424.05,9940.4,10475]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':5.7102, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,121.727,24.7446,11.4204,7.42322,5.99125,5.71591],
			'sig':[71.4766,1109.92,9638.3,0,0,22.9186,1319.04,6355.2,12561.9,16307.7,17011.5]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':4.667, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,99.4882,20.224,9.334,6.06707,4.8967,4.67167],
			'sig':[64.5588,1479.16,19982,0,0,32.7829,3019.02,18084.5,42379.7,61679.8,67405.6]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':4.0921, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,87.2329,17.7327,8.1842,5.3197,4.29351,4.09619],
			'sig':[7.99079,482.375,18315.4,0,0,5.68456,1984.07,23630.2,82284.9,147281,134812]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':3.8869, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,82.8585,16.8435,7.7738,5.05294,4.07821,3.89079],
			'sig':[5.16591,470.692,22639.7,0,0,4.43433,2591.07,34787.3,126683,231779,123843]},
			{'Shell':'4S1/2', 'Func':0, 'BindEnergy':1.6171, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,34.4723,7.00755,3.2342,2.10222,1.69669,1.61872],
			'sig':[24.376,260.294,2073.83,11216.8,0,154.359,3118.19,10140.6,17323.4,21438,23474.7]},
			{'Shell':'4P1/2', 'Func':0, 'BindEnergy':1.4118, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,30.0959,6.1179,2.8236,1.83533,1.48129,1.41321],
			'sig':[18.967,288.393,2749.34,13087.3,0,218.815,5159.85,13885.9,18624.5,19652.9,22412.3]},
			{'Shell':'4P3/2', 'Func':0, 'BindEnergy':1.1357, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,24.2101,4.92145,2.2714,1.4764,1.1916,1.13684],
			'sig':[17.1795,379.781,5172.49,40275.8,0,488.888,16968.5,61953.1,109874,139533,127605]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.8787, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,399.308,16.5006,3.5148,1.48499,0.967326,0],
			'sig':[2.3425,125.194,3809.43,52418.4,200723,0.002871,603.738,37952,157666,202329,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.8276, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,376.087,15.541,3.3104,1.39863,0.911072,0],
			'sig':[1.52019,122.632,4717.55,73742.4,339031,0.002671,816.903,59882.4,260183,348573,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.44524, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,202.331,8.36091,1.78096,0.752449,0.490147,0],
			'sig':[0.024453,6.19302,764.267,41631.9,866939,0.000167,983.024,205561,1433360,124910,0]},
			{'Shell':'4F7/2', 'Func':2, 'BindEnergy':0.431764, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,196.207,8.10784,1.72705,0.729673,0.475312,0],
			'sig':[0.027093,7.13709,918.971,51829.4,1123860,0.000248,1341,283791,1984010,161935,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.350755, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,159.394,6.58662,1.40302,0.592769,0.386132,0],
			'sig':[6.55454,69.8074,571.756,3576.58,17213.3,1.28493,973.916,11059.5,30329.4,42984.4,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.283096, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,128.647,5.31609,1.13238,0.478427,0.311649,0],
			'sig':[4.80465,71.9431,696.63,3938.71,13220.8,1.3597,1694.56,11809.5,33181.7,113359,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.214591, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,97.5169,4.02969,0.858366,0.362656,0.236235,0],
			'sig':[4.30167,93.0616,1261.84,10453,57906,2.31292,6153.88,70836.7,185015,314723,0]},
			{'Shell':'5D3/2', 'Func':2, 'BindEnergy':0.1158, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,52.6231,2.17454,0.4632,0.1957,0.12748,0],
			'sig':[0.50968,26.0218,753.492,10253.4,58137.1,2.42271,18907.8,86035.3,435780,2544090,0]},
			{'Shell':'5D5/2', 'Func':2, 'BindEnergy':0.1033, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,46.9427,1.93981,0.4132,0.174575,0.113719,0],
			'sig':[0.327267,25.2206,920.99,14114.8,89304.2,2.9907,32992.8,152063,730138,4334410,0]},
			{'Shell':'6S1/2', 'Func':2, 'BindEnergy':0.0504377, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,22.9204,0.947139,0.201751,0.085239,0.055525,0],
			'sig':[1.35952,14.0566,114.26,739.902,4030.88,18.9848,4357.69,29032,100303,357761,0]},
			{'Shell':'6P1/2', 'Func':2, 'BindEnergy':0.0308816, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,14.0335,0.579907,0.123526,0.052189,0.033996,0],
			'sig':[0.844831,12.1136,115.392,675.75,2639.08,47.7973,5036.55,181236,2388410,1.18047e+07,0]},
			{'Shell':'6P3/2', 'Func':2, 'BindEnergy':0.0202617, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,9.20755,0.380483,0.081047,0.034242,0.022305,0],
			'sig':[0.67519,13.8139,182.453,1531.52,9012.87,169.501,32552.1,380779,5448340,3.51662e+07,0]}] },
			'Cm':{'NSHELLS':24, 'ETERM':-2.782,  'shells':[
			{'Shell':'1S1/2', 'Func':1, 'BindEnergy':128.22, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,592.001,266.913,181.33,146.193,131.338,0],
			'sig':[0,0,0,0,0,26.7319,193.084,510.021,872.869,1136.69,0]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':24.46, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,521.423,105.995,48.92,31.7978,25.6639,24.4845],
			'sig':[389.254,3484.11,0,0,0,4.60466,205.806,1112.44,2559.13,3746.11,4031.63]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':23.779, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,506.906,103.044,47.558,30.9125,24.9494,23.8028],
			'sig':[354.847,6513.25,0,0,0,1.59658,174.11,1476.22,4532.83,7720.8,8611.08]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':18.93, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,403.538,82.0314,37.86,24.6089,19.8617,18.9489],
			'sig':[291.286,8144.84,0,0,0,1.31987,268.852,2939.02,10272.6,18765.9,21292.1]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':6.288, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,134.044,27.2485,12.576,8.17436,6.59749,6.29429],
			'sig':[90.8906,933.536,6314.98,0,0,27.4715,897.079,3670.12,7137.22,9551.22,10047.8]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':5.895, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,125.666,25.5454,11.79,7.66346,6.18515,5.90089],
			'sig':[75.8409,1153.99,9709.61,0,0,22.4446,1274.99,6110.88,12035.2,15536.4,16447.8]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':4.797, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,102.259,20.7873,9.594,6.23607,5.0331,4.8018],
			'sig':[67.9421,1539.06,20518.1,0,0,31.7287,2923.57,17538.3,41158.6,60002.8,65611.3]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':4.227, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,90.1086,18.3173,8.454,5.49507,4.43505,4.23123],
			'sig':[8.65314,516.255,19355.4,0,0,5.42139,1894.78,22622.2,78958.2,141517,118531]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':3.971, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,84.6513,17.208,7.942,5.16227,4.16645,3.97497],
			'sig':[5.56113,500.597,23680.7,0,0,4.35046,2536.89,33949,123299,225093,96089.6]},
			{'Shell':'4S1/2', 'Func':0, 'BindEnergy':1.643, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,35.0245,7.11979,3.286,2.13589,1.72387,1.64464],
			'sig':[25.2283,266.966,2101.08,11174.3,0,153.534,3066.73,9898.49,16860.4,21025.4,21546.2]},
			{'Shell':'4P1/2', 'Func':0, 'BindEnergy':1.44, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,30.697,6.24011,2.88,1.87199,1.51088,1.44144],
			'sig':[20.1905,301.109,2803.64,12926.4,0,218.743,5054.02,13436.1,17945.4,18976.2,19639.3]},
			{'Shell':'4P3/2', 'Func':0, 'BindEnergy':1.154, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,24.6003,5.00075,2.308,1.50019,1.2108,1.15515],
			'sig':[18.1611,396.757,5336.77,41033.7,0,489.804,16874.8,61478.5,109140,138930,122011]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.884263, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,401.836,16.6051,3.53705,1.49439,0.97345,0],
			'sig':[2.54694,133.995,3996.05,53659.5,205218,0.003077,628.428,38479.9,158438,204625,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.83101, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,377.636,15.605,3.32404,1.40439,0.914826,0],
			'sig':[1.64705,131.07,4947.71,75560.1,346749,0.002873,853.985,60946.3,262488,361040,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.470135, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,213.644,8.82838,1.88054,0.79452,0.517553,0],
			'sig':[0.027587,6.90108,839.131,44826.6,907827,0.000145,866.927,187735,1370930,124047,0]},
			{'Shell':'4F7/2', 'Func':2, 'BindEnergy':0.455751, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,207.107,8.55828,1.823,0.770212,0.501718,0],
			'sig':[0.030486,7.9391,1007.93,55782.6,1178230,0.000217,1181.62,259178,1898700,159868,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.385, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,174.956,7.22969,1.54,0.650643,0.423831,0],
			'sig':[6.8632,72.5335,589.459,3663.72,17411.8,1.09076,851.983,9899.2,27736.7,39880.6,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.296927, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,134.933,5.57582,1.18771,0.501802,0.326876,0],
			'sig':[5.1767,76.1335,722.479,3996.56,13120.4,1.30545,1611.55,11232.1,31662.9,108555,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.223245, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,101.449,4.19219,0.892981,0.377281,0.245762,0],
			'sig':[4.59705,98.4342,1321.28,10860,59751,2.19861,5953.67,69376.2,182006,307293,0]},
			{'Shell':'5D3/2', 'Func':2, 'BindEnergy':0.121646, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,55.2795,2.28431,0.486583,0.205579,0.133915,0],
			'sig':[0.563844,28.3844,807.884,10789.8,59982.8,2.23741,18131,87057.5,387950,2219000,0]},
			{'Shell':'5D5/2', 'Func':2, 'BindEnergy':0.110701, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,50.3057,2.07878,0.442802,0.187082,0.121866,0],
			'sig':[0.361245,27.4817,987.403,14876.7,92563.2,2.43578,30535.8,153749,612902,3694840,0]},
			{'Shell':'6S1/2', 'Func':2, 'BindEnergy':0.0522254, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,23.7328,0.980709,0.208901,0.08826,0.057493,0],
			'sig':[1.42124,14.6017,117.798,758.078,4096.47,18.4037,4212.07,28373,104466,372138,0]},
			{'Shell':'6P1/2', 'Func':2, 'BindEnergy':0.0319399, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,14.5145,0.599781,0.12776,0.053978,0.035161,0],
			'sig':[0.908098,12.8065,119.69,687.69,2645.62,46.7158,4874.21,180501,2373900,1.20672e+07,0]},
			{'Shell':'6P3/2', 'Func':2, 'BindEnergy':0.0205731, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,9.34904,0.38633,0.082292,0.034768,0.022648,0],
			'sig':[0.712296,14.4478,189.077,1576.04,9230.75,170.007,32523.4,381003,5542610,3.71901e+07,0]}] },
			'Bk':{'NSHELLS':24, 'ETERM':-2.858,  'shells':[
			{'Shell':'1S1/2', 'Func':1, 'BindEnergy':131.59, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,607.561,273.929,186.096,150.035,134.789,0],
			'sig':[0,0,0,0,0,26.2294,187.583,493.41,843.192,1097.93,0]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':25.275, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,538.797,109.527,50.55,32.8573,26.519,25.3003],
			'sig':[400.321,3543.02,0,0,0,4.46647,196.87,1064.45,2451.04,3587.86,3864.64]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':24.385, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,519.824,105.67,48.77,31.7003,25.5852,24.4094],
			'sig':[375.9,6738.4,0,0,0,1.60631,172.541,1448.44,4421.18,7507.2,8367.01]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':19.452, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,414.666,84.2934,38.904,25.2875,20.4094,19.4715],
			'sig':[306.806,8522.33,0,0,0,1.28075,259.626,2842.08,9947.62,18179.2,20652.6]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':6.556, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,139.757,28.4098,13.112,8.52276,6.87868,6.56256],
			'sig':[93.7629,954.315,6348.63,0,0,25.806,845.155,3467.95,6751.52,9044.18,9456.9]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':6.147, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,131.038,26.6374,12.294,7.99106,6.44955,6.15315],
			'sig':[80.5566,1202.23,9795.7,0,0,21.4268,1208.58,5792.74,11398.8,14706.5,15543.9]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':4.977, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,106.097,21.5674,9.954,6.47007,5.22196,4.98198],
			'sig':[71.5392,1605.03,21173.2,0,0,29.8382,2773.65,16757.2,39518.7,57887.7,61344.6]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':4.366, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,93.0717,18.9197,8.732,5.67577,4.58089,4.37037],
			'sig':[9.35919,552.067,20445,0,0,5.1665,1809.37,21661.2,75817.1,136162,75948]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':4.132, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,88.0834,17.9056,8.264,5.37157,4.33537,4.13613],
			'sig':[5.9988,536.098,25208,0,0,3.94841,2350.2,31883.8,116828,214118,145324]},
			{'Shell':'4S1/2', 'Func':0, 'BindEnergy':1.755, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,37.412,7.60513,3.51,2.28149,1.84138,1.75676],
			'sig':[26.127,274.463,2141.54,11221.1,0,137.996,2795.45,9109.34,15613.5,19364.3,21295.1]},
			{'Shell':'4P1/2', 'Func':0, 'BindEnergy':1.554, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,33.1272,6.73411,3.108,2.02019,1.63049,1.55555],
			'sig':[21.5312,315.413,2874.97,12715.2,0,192.62,4563.64,12308.8,16461.3,17324.7,17860.9]},
			{'Shell':'4P3/2', 'Func':0, 'BindEnergy':1.235, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,26.327,5.35176,2.47,1.60549,1.29579,1.23623],
			'sig':[19.2086,415.718,5545.71,42313.4,0,431.074,15381.8,57204.6,102640,129846,165074]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.920204, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,418.169,17.28,3.68082,1.55513,1.01302,0],
			'sig':[2.76951,143.675,4213.03,55406.3,204363,0.002857,590.683,36690.5,153790,204433,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.863912, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,392.588,16.2229,3.45565,1.46,0.951046,0],
			'sig':[1.78555,140.354,5216.03,78155.7,347143,0.002774,798.249,58110.4,255019,357307,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.495366, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,225.109,9.30218,1.98146,0.837159,0.545328,0],
			'sig':[0.031055,7.67389,919.479,48178.7,949346,0.000126,769.367,172051,1308300,122328,0]},
			{'Shell':'4F7/2', 'Func':2, 'BindEnergy':0.480032, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,218.141,9.01423,1.92013,0.811246,0.528448,0],
			'sig':[0.034231,8.81226,1103.27,59926.5,1233490,0.000194,1047.5,237630,1815870,157553,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.398, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,180.863,7.47381,1.592,0.672613,0.438142,0],
			'sig':[7.16696,75.1719,605.557,3730.8,17496.5,1.0623,824.301,9559.27,26875,39262.5,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.311035, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,141.344,5.84075,1.24414,0.525645,0.342407,0],
			'sig':[5.5742,80.4537,747.755,4044.82,12995.5,1.20221,1534.1,10674.1,30268.7,104429,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.231895, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,105.38,4.35461,0.927579,0.391898,0.255284,0],
			'sig':[4.90425,103.946,1381.36,11267.7,61547.2,2.09674,5764.2,67958.9,179005,300424,0]},
			{'Shell':'5D3/2', 'Func':2, 'BindEnergy':0.127215, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,57.8105,2.3889,0.508861,0.214991,0.140046,0],
			'sig':[0.62214,30.8821,864.037,11329.6,61741.1,2.09594,17490.9,87825.5,350626,1961380,0]},
			{'Shell':'5D5/2', 'Func':2, 'BindEnergy':0.115465, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,52.4709,2.16825,0.46186,0.195134,0.127111,0],
			'sig':[0.39697,29.8414,1055.29,15629.7,95661.1,2.25736,29551.8,155614,554493,3261110,0]},
			{'Shell':'6S1/2', 'Func':2, 'BindEnergy':0.0540424, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,24.5585,1.01483,0.21617,0.091331,0.059493,0],
			'sig':[1.48578,15.1436,121.145,774.492,4153.72,17.8368,4067.78,27773.8,108859,386890,0]},
			{'Shell':'6P1/2', 'Func':2, 'BindEnergy':0.0330119, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,15.0016,0.619912,0.132048,0.05579,0.036341,0],
			'sig':[0.976491,13.5161,123.783,697.621,2642.9,45.6278,4710.82,179855,2361520,1.2332e+07,0]},
			{'Shell':'6P3/2', 'Func':2, 'BindEnergy':0.0208517, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,9.47565,0.391561,0.083407,0.035239,0.022955,0],
			'sig':[0.752469,15.096,195.534,1618.72,9430.76,170.863,32473.1,382369,5659310,3.93271e+07,0]}] },
			'Cf':{'NSHELLS':24, 'ETERM':-2.936,  'shells':[
			{'Shell':'1S1/2', 'Func':1, 'BindEnergy':135.354, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,624.938,281.763,191.419,154.326,138.645,0],
			'sig':[0,0,0,0,0,25.6364,181.615,475.77,811.781,1056.03,0]},
			{'Shell':'2S1/2', 'Func':0, 'BindEnergy':25.9027, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,552.178,112.247,51.8054,33.6733,27.1776,25.9286],
			'sig':[410.055,3567.11,0,0,0,4.41323,191.319,1031.06,2369.22,3465.11,3728.29]},
			{'Shell':'2P1/2', 'Func':0, 'BindEnergy':25.0203, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,533.367,108.423,50.0406,32.5262,26.2518,25.0453],
			'sig':[398.041,6994.76,0,0,0,1.61356,170.759,1419.73,4307.99,7289.4,8141.19]},
			{'Shell':'2P3/2', 'Func':0, 'BindEnergy':19.7527, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,421.075,85.5963,39.5053,25.6783,20.7249,19.7724],
			'sig':[320.488,8771.53,0,0,0,1.2872,258.194,2810.97,9792.21,17859.9,20260.7]},
			{'Shell':'3S1/2', 'Func':0, 'BindEnergy':6.66573, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,142.096,28.8853,13.3315,8.66541,6.99382,6.6724],
			'sig':[96.4062,969.135,6316.71,0,0,25.6613,831.562,3385.84,6557.69,8767.72,9164.04]},
			{'Shell':'3P1/2', 'Func':0, 'BindEnergy':6.26603, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,133.575,27.1533,12.5321,8.1458,6.57444,6.2723],
			'sig':[85.1619,1242.61,9789.68,0,0,21.6863,1196.9,5664.72,11056,14226.3,14758.8]},
			{'Shell':'3P3/2', 'Func':0, 'BindEnergy':5.03215, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,107.272,21.8064,10.0643,6.54177,5.27983,5.03719],
			'sig':[74.9851,1659.45,21519.1,0,0,30.3085,2781.17,16671.9,39147.1,57274.4,60365.4]},
			{'Shell':'3D3/2', 'Func':0, 'BindEnergy':4.41774, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,94.1746,19.1439,8.83548,5.74303,4.63517,4.42216],
			'sig':[10.072,584.268,21133.6,0,0,5.3178,1828.75,21601.2,74913.5,133790,60161.1]},
			{'Shell':'3D5/2', 'Func':0, 'BindEnergy':4.17726, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,89.0483,18.1018,8.35453,5.43041,4.38286,4.18144],
			'sig':[6.43263,566.593,26058.6,0,0,4.04182,2372.35,31795.6,115481,210664,1179700]},
			{'Shell':'4S1/2', 'Func':0, 'BindEnergy':1.75697, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,37.454,7.61367,3.51394,2.28405,1.84345,1.75873],
			'sig':[26.9964,280.771,2160.28,11124.9,0,141.308,2807.69,9037.68,15421.4,19133.2,21258.9]},
			{'Shell':'4P1/2', 'Func':0, 'BindEnergy':1.57404, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,33.5544,6.82095,3.14808,2.04624,1.65151,1.57561],
			'sig':[22.8708,328.405,2920.21,12495.4,0,195.516,4510.23,11970,15901.6,16750.9,19372]},
			{'Shell':'4P3/2', 'Func':0, 'BindEnergy':1.24194, 'NumXsect':11,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,26.4749,5.38182,2.48388,1.61451,1.30306,1.24318],
			'sig':[20.2615,433.272,5705.16,42955.5,0,442.796,15559.1,57470.7,102959,130267,172616]},
			{'Shell':'4D3/2', 'Func':2, 'BindEnergy':0.956658, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,434.735,17.9645,3.82663,1.61674,1.05315,0],
			'sig':[3.00938,153.896,4436.77,57152.9,192331,0.002667,556.507,35022.5,149221,201664,0]},
			{'Shell':'4D5/2', 'Func':2, 'BindEnergy':0.89718, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,407.706,16.8476,3.58872,1.51622,0.98767,0],
			'sig':[1.93219,150.093,5492.85,80763.5,348317,0.002687,747.983,55498.9,247908,348896,0]},
			{'Shell':'4F5/2', 'Func':2, 'BindEnergy':0.520934, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,236.728,9.78231,2.08373,0.880369,0.573475,0],
			'sig':[0.034889,8.51623,1005.58,51692.6,991337,0.000105,687.006,158355,1251420,122152,0]},
			{'Shell':'4F7/2', 'Func':2, 'BindEnergy':0.504621, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,229.316,9.47599,2.01849,0.852802,0.555518,0],
			'sig':[0.038355,9.76136,1205.27,64265.8,1289600,0.000175,934.337,218638,1735640,154971,0]},
			{'Shell':'5S1/2', 'Func':2, 'BindEnergy':0.399858, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,181.708,7.5087,1.59943,0.675753,0.440188,0],
			'sig':[7.47339,77.7741,620.547,3785.29,17520.5,1.1032,836.504,9569.13,26768,39809.6,0]},
			{'Shell':'5P1/2', 'Func':2, 'BindEnergy':0.325483, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,147.909,6.11204,1.30193,0.55006,0.358311,0],
			'sig':[5.9863,84.8372,772.302,4082.97,12851.6,1.15507,1461.09,10133.4,28983.2,100800,0]},
			{'Shell':'5P3/2', 'Func':2, 'BindEnergy':0.240559, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,109.317,4.51731,0.962235,0.40654,0.264822,0],
			'sig':[5.22913,109.635,1442.04,11675.8,63290.1,2.00713,5590.19,66575.5,176016,294117,0]},
			{'Shell':'5D3/2', 'Func':2, 'BindEnergy':0.13277, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,60.3346,2.4932,0.531079,0.224378,0.146161,0],
			'sig':[0.684877,33.5229,922.039,11873.3,63409.4,1.97453,16893.1,88319.3,319606,1750300,0]},
			{'Shell':'5D5/2', 'Func':2, 'BindEnergy':0.120199, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,54.6222,2.25715,0.480797,0.203135,0.132323,0],
			'sig':[0.435123,32.3234,1125.18,16386.3,98628.9,2.10353,28646.9,157040,505720,2908250,0]},
			{'Shell':'6S1/2', 'Func':2, 'BindEnergy':0.0558717, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,25.3898,1.04918,0.223487,0.094422,0.061507,0],
			'sig':[1.54708,15.6672,124.361,789.984,4203.05,17.2841,3927,27241.8,113707,402479,0]},
			{'Shell':'6P1/2', 'Func':2, 'BindEnergy':0.0340771, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,15.4857,0.639913,0.136308,0.05759,0.037514,0],
			'sig':[1.04537,14.227,127.762,705.863,2635.83,44.6241,4550.15,180030,2354980,1.26116e+07,0]},
			{'Shell':'6P3/2', 'Func':2, 'BindEnergy':0.0211275, 'NumXsect':10,
			'ew':[80.0003,26.7001,8.89996,3.00003,1,9.60099,0.396741,0.08451,0.035705,0.023258,0],
			'sig':[0.792541,15.7282,201.657,1658.01,9606.45,171.403,32351.5,382394,5780810,4.14391e+07,0]}] } }
		
		try:	ElementDict = AllElementsInfo[self.sym]
		except:	raise ValueError('Element not in Cromer-Liberman database (AllElementsInfo) %r' % (self.sym,))
		return ElementDict


""" ============================ End of CromerAtom =============================
	============================================================================
"""



""" ============================================================================
	=========================== Start of whole atom ============================
"""

"""
	testing:
from atomGeneral import atom
a = atom('Cu')
print str(a)
"""

class atom(xrayLinesAtom,isotope,elementInfo):
	"""the argument can be either the atomic number or atomic symbol, e.g. for Copper you
	can use either 29 or 'Cu'.  Then call one of the methods to get the associated value.
	To print everything, use:
	a = atom('Cu')
	print str(a)
	"""

	def __init__(self,ele):
		elementInfo.__init__(self,ele)			# init the xray data (this also inits the element data)
		xrayLinesAtom.__init__(self,ele)		# init the xray data (this also inits the element data)
		isotope.__init__(self,ele)	# init the isotope data
		return None

	def __str__(self):
		""" return printable string with everything about the atom """
		return unicode(self).encode('ascii', errors='backslashreplace')

	def __unicode__(self):
		""" return unicode printable string with everything about the atom """
		out = elementInfo.__unicode__(self)
		if out is None: return None
		out += '\n'+self.printBindingAll()+'\n'
		out += self.printEmissionAll()+'\n'
		out += self.printIsotopes()
		return out


""" ============================= End of whole atom =============================
	=============================================================================
"""






if __name__ == '__main__':
	"""
	Main function for atomGeneral.py.
	Test cases for for class to verify correct behavior.
	"""
	from JZTutil import JZTtesting
	testing = JZTtesting(__file__)

	def test_Cromer(sym,keV,Q, fr=NaN,fi=NaN):
		Q_nm = Q
		try:
			atom = CromerAtom(sym,keV)
		except Exception as inst:
			print ("\nERROR -- test_Cromer(%r, %r):   %s" % (sym,keV,inst))
			return True

		print ('\n         test of CromerAtom: %r, %r keV, Q=%r (1/nm),' % (sym,keV,Q_nm))
		print ('         str --> ',str(atom))
		print ('         repr --> ',repr(atom))

		try:						fatom = atom.fatom(Q_nm)
		except Exception as inst:	fatom = complex(NaN,NaN)

		if abs(fatom-complex(fr,fi)) < 1e-4:
			print ('         atom.fatom(Q = %g 1/nm) = %g + %g i' % (Q_nm,fatom.real, fatom.imag))
			return False
		else:
			print ("ERROR -- atom.fatom(Q = %g 1/nm) = %g + %g i,  but should be %g + %g i" % (Q_nm,fatom.real, fatom.imag, fr,fi))
			return True


	if testing.doit('check Cu'):						#  2**0 = 1
		if test_Cromer('Cu at 10keV',10,0, fr=27.6619, fi=3.23703): testing.addErr()

	if testing.doit('check Cu no energy'):				#  2**1 = 2
		if test_Cromer('Cu',NaN,0, fr=28.9901,fi=0): testing.addErr()

	if testing.doit('check Mo(19keV)'):					#  2**2 = 4
		if test_Cromer('Mo',19,0, fr=39.3915, fi=0.589055): testing.addErr()

	if testing.doit('check Mo(20keV)'):					#  2**3 = 8
		if test_Cromer('Mo',21,0, fr=39.7552 , fi=3.37847): testing.addErr()

	if testing.doit('check U'):							#  2**4 = 16
		if test_Cromer('U',40,0, fr=89.8386, fi=4.16349): testing.addErr()

	if testing.doit('check U'):							#  2**5 = 32
		if test_Cromer('Pu',40,0, fr=91.6573, fi=4.51613): testing.addErr()

	if testing.doit('check Fe'):						#  2**6 = 64
		if test_Cromer('Fe',10,0, fr=25.9162, fi=2.24122): testing.addErr()

	if testing.doit('check Cu(Q=0)'):					#  2**7 = 128
		if test_Cromer('Cu',0,0, fr=28.9901,fi=0): testing.addErr()

	if testing.doit('check Cu(-1 keV)'):				#  2**8 = 256
		if test_Cromer('Cu',-1.0,0, fr=28.9901,fi=0): testing.addErr()

	if testing.doit('check Cu(1e9 keV)'):				#  2**9 = 512
		if test_Cromer('Cu',1e9,0, fr=28.8441, fi=0): testing.addErr()


	if testing.doit('check Si(E = None keV'):			#  2**10 = 1024
		err = False
		err |= test_Cromer('Si',None,0, fr=13.9988, fi=0)
		err |= test_Cromer('Si',None,Q=10, fr=12.7128, fi=0)
		err |= test_Cromer('Si',keV=None,Q=20.0382156264, fr=10.53659, fi=0)
		if err: testing.addErr()

	if testing.doit('check Si(10kev)'):					#  2**11 = 2048
		err |= test_Cromer('Si',10,0, fr=14.1829, fi=0.216297)
		err |= test_Cromer('Si',10,Q=10, fr=12.8969, fi=0.216297)
		if err: testing.addErr()

	if testing.doit('check Si(more checks)'):			#  2**12 = 4096
		err |= test_Cromer('Si',keV=-1,Q=0, fr=13.9988,fi=0)
		err |= test_Cromer('Si',keV=None,Q=0, fr=13.9988,fi=0)
		err |= test_Cromer('Si',keV=10,Q=0, fr=14.1829, fi=0.216297)
		err |= test_Cromer('Si',keV=10,Q=10, fr=12.8969, fi=0.216297)
		if err: testing.addErr()

	if testing.doit('check valences'):					#  2**13 = 8192
		err |= test_Cromer('V',  keV=10,Q=0,   fr=23.282012,fi=1.4563686)
		err |= test_Cromer('V+3',keV=10,Q=0, fr=20.288932,fi=1.4563686)
		err |= test_Cromer('O',  keV=10,Q=0, fr=8.0305228,fi=0.0203544)
		err |= test_Cromer('O-2',keV=10,Q=0, fr=9.0282628,fi=0.02035444)
		if err: testing.addErr()

	if testing.doit('check baseAtom'):					#  2**14 = 16384
		err = False
		ab = baseAtom("20")
		print ('test "20",  ',ab)

		ab = baseAtom("20", valence=2)
		print ('test "20, val=2",  ',ab)

		ab = baseAtom('V')
		print ('test "V",  ',ab)

		ab = baseAtom('V',valence=1)
		print ('test "V,val=1",  ',ab)

		ab = baseAtom('V+2')
		print ('test "V+2",  ',ab)

		ab = baseAtom('V-2')
		print ('test "V-2",  ',ab)

		ab = baseAtom('V+0')
		print ('test "V+0",  ',ab)

		ab = baseAtom('V-0')
		print ('test "V-0",  ',ab)
		if err: testing.addErr()

	if testing.doit('check baseAtom & Cromer'):			#  2**15 = 32768
		err = False
		ab = baseAtom('V+3')
		print ('test "V,val=3",  ',repr(ab))
		ca = CromerAtom('V+3', 10, valence=3)
		print (' ')
		print ('  and the Cromer atom:  ',repr(ca))
		if err: testing.addErr()

	if testing.doit('check xrayLinesAtom'):				#  2**16 = 65536
		err = False
		xr = xrayLinesAtom('Fe', Eunits='keV')
		print ('test "Fe"  using "keV",  ',xr)
		print (' ')
		print ('27', xr.getEmissionLines(27))
		print (xr.Z, xr.getEmissionLines())
		print (' ')

		print ('Kb1,3 ->',xr.emissionLine_type('Kb1,3'))
		print ('Ka1 ->',xr.emissionLine_type('Ka1'))
		print ('Ka2 ->',xr.emissionLine_type('Ka2'))
		print ('Ka ->',xr.emissionLine_type('Ka'))
		print ('K ->',xr.emissionLine_type('K'))
		print ('emissionLine_type("")["strength"] (to get sum of all strengths) ->',xr.emissionLine_type('')['strength'])
		if err: testing.addErr()

	if testing.doit('check isotope'):					#  2**17 = 131072
		err = False
		ist = isotope('Fe')
		print (ist)
		print ('abumdance 57',ist.amu_abundance(57))
		print (' ')
		print (ist.isotopes)
		print (' ')
		print (ist.readIsotopeInfo(Z=110))
		print (' ')
		print (ist.isotopes)
		if err: testing.addErr()

	if testing.doit('check elementInfo'):				#  2**18 = 262144
		err = False
		e = elementInfo('N')
		print ('\n',e)
		e = elementInfo('Na')
		print ('\n',e)
		e = elementInfo('Ts')
		print ('\n',e)
		if err: testing.addErr()

	testing.ending()


