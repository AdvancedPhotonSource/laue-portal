#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Lattice.py
#
# $Id:    $
# $URL: $
#
# Part of the "pydiffract" package
#

__version__ = "$Revision: $"
__author__  = "Jon Z. Tischler, <tischler@aps.anl.gov>" +\
              "Argonne National Laboratory"
__date__    = "$Date: $"
__id__      = "$Id: $"


import os
import sys
import math
import string
import zlib
import xml.dom.minidom
from JZTLaueSim.JZTunits import UnitsJZTdefault as units, ConvertTemperatureUnits
from JZTLaueSim.LatticeBase import atomXtal, bondType, LatticeBase3D, LatticeBase2D
import JZTLaueSim.atomGeneral as atomGeneral


NaN = float('nan')
Zmax = 109							# maximum atomic number

#	known database codes, saved as strings, not integers
#		ICSD	Inorganic Crystal Structure Database code
#		amcsd	American Mineralogical Society'
#		CAS		Chemical Abstracts
#		COD		Crystallography Open Database
#		CSD		Cambridge Structural Database
#		MDF		Metals Data File (metal structures)
#		NBS		NBS (NIST) Crystal Data Database (lattice parameters)
#		PDB		Protein Data Bank
#		PDF		Powder Diffraction File (JCPDS/ICDD)
knowDatabaseCodes =  ['icsd','ICSD','amcsd','CAS','COD','CSD','MDF','NBS','PDB','PDF']	# some old files use 'icsd' lower case


class readXTALcommon(object):
	""" A Class to help process CIF files, or the associated XML files.
		This contains the code common to any dimension, either 2 or 3
	"""

	def __init__(self, file):
		# print "dir =",dir(self)

		if file == 'dummy file name testing': return None	# just used for testing, does not read a file
		if not os.path.isfile(file): raise ValueError('readXTAL(), input file "%r" does not exist' % file)
		if os.path.getsize(file)<10: raise ValueError('readXTAL(), input file "%r" is too small to be OK' % file)

		self.file = file
		(fname,ext) = os.path.splitext(file)
		self.ext = ext.lower()
		self.dim = None

		self.fileChecking = []
		return None


	################################################################################
	#		Start of XML file reading
	def checkRequiredOptional(self, top, requred, optional):
		topName = top.nodeName
		names = []
		for node in top.childNodes:
			if not (node.nodeName[0] == '#'): names.append(node.nodeName)
		names = set(names)								# removes duplicates
		for item0 in requred:
			if type(item0) is str:
				if not (item0 in names): raise ValueError('readXTALcommon(), <%s> is missing <%s>' % (topName,item0))
				names.discard(item0)
			else:

				ok = False
				for item1 in item0:
					if type(item1) is str:
						ok = ok or (item1 in names)
						names.discard(item1)
					else:	
						ok2 = False
						for item2 in item1:
							ok2 = ok2 or (item2 in names)
							names.discard(item2)
						ok = ok or ok2
				if not ok: raise ValueError('readXTALcommon(), <%s> is missing 1 of: <%s>' % (topName,item0))

		optionalLC = []									# a strictly lower case version of the tags
		for item in optional: optionalLC.append(item.lower())
		cellTemp = list(names)
		for opt in cellTemp:
			if opt.lower() in optionalLC:
				if not (opt in optional): raise ValueError('readXTALcommon(), <%s> has wrong case' % (opt,))
				names.discard(opt)

		if len(names):	return 'Parsing the xml cif file,  unknown  <tags> in <%s> are: %r' % (topName,names)
		else:			return None


	def setxml_iso(self, name, atom_site, positive):
		try:
			node = atom_site.getElementsByTagName(name)[0]
			iso = float(node.firstChild.nodeValue)
			unit = node.getAttribute('unit')
			iso = self.ConvertLengthUnits(iso,unit,'nm^2',defaultUnit='Angstrom^2')		# want length in nm^2
			if positive and iso<=0: iso = float('nan')
		except:
			iso = float('nan')

		return iso


	def ForceXtalAtomNamesUnique(self,atoms):
		"""
		Forces all of the xtal atom names to be unique.
		This is particularly useful when labels were not passed in the xml file, only element symbols
		"""
		all = []											# temp array for fixing up labels
		for atom in atoms: all.append(atom.label)
		N = len(all)

		for j in range(N-1):
			labelj = all[j]									# check this label against others
			if len(labelj)<1: continue						# skip empty labels
			elif self.CountDuplicateNames(all,labelj)>1:	# found duplicates (always find 1)
				base,num = self.splitLabel(labelj)
				if num < 0:									# try to change "Cu" -> "Cu1"
					num = 1
					labelTest = base + str(num)
					if self.CountDuplicateNames(all,labelTest)<1:	# base+"1" does not exist
						all[j] = labelTest

				for i in range(j+1,N):						# look for matches to labelj
					if all[i].lower() == labelj.lower():	# need to change all[i]
						first = True
						while (self.CountDuplicateNames(all,labelTest) or first):
							num += 1
							labelTest = base + str(num)
							first = False
						all[i] = labelTest

		for j in range(N-1): atoms[j].label = all[j]	# update the correct labels into atoms
		return all										# this will be useful in validating bonds


	def splitLabel(self,label):
		""" for a label of the form "Ab0001", return ("Ab",1) """
		i = 0
		for c in label[::-1]:
			if not c.isdigit(): break
			else: i += 1

		if i>0:
			try:	num = int(label[-i:])
			except:	num = -1
		else:	num = -1
		N = len(label)
		base = label[:N-i]
		return (base,num)


	def CountDuplicateNames(self, ws,name):
		""" Counts how many times 'name' appers in ws. """
		name = name.lower()
		dup = 0
		for n in ws:
			if n.lower() == name: dup += 1
		return dup


	def process_xml_space_group(self, space_group):
		""" process the <space_group> tag """
		try:	SpaceGroupID = space_group.getElementsByTagName('id')[0].firstChild.nodeValue
		except:	SpaceGroupID = None
		if not SpaceGroupID:				# try using the H-M symbol to set the SpaceGroupID
			try:
				HMsym = space_group.getElementsByTagName('H-M')[0].firstChild.nodeValue
				idList = self.SymString2IDs(HMsym+'*',31)					# check everybody
				if len(idList)<1: idList = self.SymString2IDs(HMsym+'*',-1)	# ignore minus signs too
				SpaceGroupID = idList[0]
			except:	pass
		if not SpaceGroupID:				# use the default SpaceGroupID for this SG
			try:
				SG = int(space_group.getElementsByTagName('IT_number')[0].firstChild.nodeValue)
				SpaceGroupID = self.FindDefaultIDforSG(SG)
			except:	pass

		try:	self.validSpaceGroupID(SpaceGroupID)		# this raises an exception if SpaceGroupID is invalid
		except:												# try to identify SpaceGroupID using the <symops>
			symops = space_group.getElementsByTagName('symops')[0]
			if not symops: raise ValueError('ERROR -- process_xml_space_group(), Unable to find <symops>, when trying to set Space Group ID')
			opList = []
			try:
				for node in symops.getElementsByTagName('op'):
					op = node.firstChild.nodeValue
					op = op.replace("'",'"')				# change all single quotes to double-quotes
					op = op.replace('\t','')				# remove all tabs
					op = op.replace(' ','')					# remove all spaces
					op = op.replace('""',',')				# two double-quotes --> a comma
					op = op.strip('"')
					op = op.strip()							# operations will look like: '-y-1/4,-x-1/4,-z+1/4'
					opList.append(op)
			except:	pass									# done setting opsList (probably failed to turn <symops> into opList)
			SpaceGroupID = self.FindIDfromSymOps(opList)

		try:	self.validSpaceGroupID(SpaceGroupID)		# this raises an exception if SpaceGroupID is invalid
		except:	raise ValueError('ERROR -- process_xml_space_group(), Unable to set Space Group ID using <id>, <H-M>, or <symops>, give up.')
		return SpaceGroupID


	def process_xml_cell(self, cell):
		""" process the <cell> tag """
		out = {}

		try:
			node = cell.getElementsByTagName('a')[0]
			a = float(node.firstChild.nodeValue)
			unit = node.getAttribute('unit')
			a = self.ConvertLengthUnits(a,unit,'nm',defaultUnit='Angstrom')			# want length in nm
			out['a'] = a
		except:
			raise ValueError('process_xml_cell(), cannot find a')

		try:
			node = cell.getElementsByTagName('b')[0]
			b = float(node.firstChild.nodeValue)
			unit = node.getAttribute('unit')
			b = self.ConvertLengthUnits(b,unit,'nm',defaultUnit='Angstrom')			# want length in nm
			out['b'] = b
		except:
			raise ValueError('process_xml_cell(), cannot find b')

		try:
			node = cell.getElementsByTagName('alpha')[0]
			alpha = float(node.firstChild.nodeValue)
			unit = node.getAttribute('unit')
			if not len(unit): unit = 'deg'											# default input is degree
			#alpha = units((alpha,unit),'deg').num									# convert to degree
			out['alpha'] = alpha
		except:
			raise ValueError('process_xml_cell(), cannot find alpha')

		if self.dim >= 3:
			try:
				node = cell.getElementsByTagName('c')[0]
				c = float(node.firstChild.nodeValue)
				unit = node.getAttribute('unit')
				c = self.ConvertLengthUnits(c,unit,'nm',defaultUnit='Angstrom')		# want length in nm
				out['c'] = c
			except:
				raise ValueError('process_xml_cell(), cannot find c')

			try:
				node = cell.getElementsByTagName('beta')[0]
				beta = float(node.firstChild.nodeValue)
				unit = node.getAttribute('unit')
				if not len(unit): unit = 'deg'										# default input is degree
				#beta = units((beta,unit),'deg').num									# convert to degree
				out['beta'] = beta
			except:
				raise ValueError('process_xml_cell(), cannot find beta')

			try:
				node = cell.getElementsByTagName('gamma')[0]
				gamma = float(node.firstChild.nodeValue)
				unit = node.getAttribute('unit')
				if not len(unit): unit = 'deg'										# default input is degree
				#gamma = units((gamma,unit),'deg').num								# convert to degree
				out['gamma'] = gamma
			except:
				raise ValueError('process_xml_cell(), cannot find gamma')

		try:
			node = cell.getElementsByTagName('temperature')[0]
			Temperature = float(node.firstChild.nodeValue)
			unit = node.getAttribute('unit')
			if len(unit): Temperature = ConvertTemperatureUnits(Temperature,unit,'C',defaultUnit='C')
			out['Temperature'] = Temperature
		except:	pass

		try:	out['alphaT'] = float(cell.getElementsByTagName('alphaT')[0].firstChild.nodeValue)
		except:	pass

		try:											# thermal expansion table was found, save it
			expansion = cell.getElementsByTagName('thermalExpansion')[0]
			dLarrayStr = expansion.getElementsByTagName('dL_L')[0].firstChild.nodeValue

			Tnode = expansion.getElementsByTagName('T')[0].firstChild
			try:	Tunit = Tnode.getAttribute('unit')
			except:	Tunit = "K"
			TarrayStr = Tnode.nodeValue

			TarrayStr = TarrayStr.strip()				# trim off any whitespace
			dLarrayStr = dLarrayStr.strip()				# trim off any whitespace
			Tarray = TarrayStr.split()
			dLarray = dLarrayStr.split()
			N = len(dLarray)
			if N != len(Tarray) or N < 2: raise			# arrays must have same size
			for i in range(N):							# make sure I have floats, not strings or ints
				Tarray[i] = float(Tarray[i])
				dLarray[i] = float(dLarray[i])

			if Tunit != "K" or len(Tunit)>0:			# convert Temperatures to Kelvin
				for i in range(N):
					Ttemp = ConvertTemperatureUnits(float(Tarray[i]),Tunit,'K',defaultUnit='K')
					Tarray[i] = Ttemp

			expansionTable = []							# fill expansionTable[ (T,dL_L) ]
			Tlast = 0.0									# this is Kelvin, so 0 is lowest
			for i in range(N):
				TT = Tarray[i]							# T & strain point
				dL = dLarray[i]
				if TT<0 or math.isnan(TT+dL) or math.isinf(TT+dL): raise
				if Tlast > TT: raise					# Tarray[] must be monotonic
				Tlast = TT
				expansionTable.append((TT,dL))

			out['expansionTable'] = expansionTable
		except:	pass

		return out


	def process_xml_atom_site(self,atom_site):
		""" process one <atom_site> tag """
		try:	label = atom_site.getElementsByTagName('label')[0].firstChild.nodeValue
		except: label = ''
		try:	symbol = atom_site.getElementsByTagName('symbol')[0].firstChild.nodeValue
		except: symbol = label
		if len(label)<1: label = symbol		# if no label given, use the symbol (may not be unique)
		if len(label)+len(symbol) < 1: raise ValueError('process_xml_atom_site(), each atom site requires a label or a symbol')
#		Zatom will be assigned in the call to atomXtal()

		try:	valence = int(atom_site.getElementsByTagName('valence')[0].firstChild.nodeValue)
		except: valence = 0				# valence defaults to 0 (integer)

		z = 0							# not used for 2D
		try:
			xyz = atom_site.getElementsByTagName('fract')[0].firstChild.nodeValue.split()
			if self.dim==2:	x,y = xyz	# this line fails unless len(xyz)==2
			else:			x,y,z = xyz	# this line fails unless len(xyz)==3
			x = self.interpDouble(x)
			y = self.interpDouble(y)
			z = self.interpDouble(z)
		except:
			try:
				x = self.interpDouble(atom_site.getElementsByTagName('fract_x')[0].firstChild.nodeValue)
				y = self.interpDouble(atom_site.getElementsByTagName('fract_y')[0].firstChild.nodeValue)
				if self.dim>2: z = self.interpDouble(atom_site.getElementsByTagName('fract_z')[0].firstChild.nodeValue)
			except:
				x = y = z = float('nan')

		x = self.Condition_fractional(x)	# change 0.3333 -> 0.333333333333333 (exact)
		y = self.Condition_fractional(y)
		z = self.Condition_fractional(z)
		if math.isnan(x+y+z): raise ValueError('ERROR -- process_xml_atom_site(), unable to get fractional coordinates of atom "%s"' % (label,))
		if self.dim==2:	xyz = [x,y]		# reconstitute xyz as a float, not a list of strings
		else:			xyz = [x,y,z]

		try:	WyckoffSymbol = atom_site.getElementsByTagName('WyckoffSymbol')[0].firstChild.nodeValue
		except: WyckoffSymbol = ''

		mult = 1
		if (len(WyckoffSymbol) > 0) and (math.isnan(x+y+z)):	# try to set x,y,z using Wyckoff symbol
			(x,y,z) = self.ForceXYZtoWyckoff(SG,WyckoffSymbol,x,y,z)
			mult = self.MultiplicityFromWyckoff(SG,WyckoffSymbol)# find multiplicity

		if math.isnan(x+y+z):			# cannot find valid x,y,z, give up
			raise ValueError('readXTALcommon(), cannot find fractional x,y,z')

		try:	occ = self.interpDouble(atom_site.getElementsByTagName('occupancy')[0].firstChild.nodeValue)
		except: occ = 1.0

		try:
			node = atom_site.getElementsByTagName('DebyeTemperature')[0]
			DebyeT = float(node.firstChild.nodeValue)
			unit = node.getAttribute('unit')
			DebyeT = ConvertTemperatureUnits(DebyeT,unit,'K',defaultUnit='K')
			if DebyeT<=0: DebyeT = float('nan')
		except:
			DebyeT = float('nan')

		Biso = self.setxml_iso('Biso', atom_site, True)				# prefer "Biso" over "B_iso"
		Biso = self.setxml_iso('B_iso', atom_site, True) if self.numtype(Biso) else Biso
		Uiso = self.setxml_iso('Uiso', atom_site, True)				# prefer "Uiso" over "U_iso"
		Uiso = self.setxml_iso('U_iso', atom_site, True) if self.numtype(Uiso) else Uiso

		U11 = self.setxml_iso('U11', atom_site, False)				# prefer "U11" over "aniso_U_11"
		U11 = self.setxml_iso('aniso_U_11', atom_site, True) if self.numtype(U11) else U11
		U22 = self.setxml_iso('U22', atom_site, False)
		U22 = self.setxml_iso('aniso_U_22', atom_site, True) if self.numtype(U22) else U22
		U12 = self.setxml_iso('U12', atom_site, False)
		U12 = self.setxml_iso('aniso_U_12', atom_site, True) if self.numtype(U12) else U12

		Uij = (U11,U22, U12)
		if self.dim == 3:
			U33 = self.setxml_iso('U33', atom_site, False)
			U33 = self.setxml_iso('aniso_U_33', atom_site, True) if self.numtype(U33) else U33
			U13 = self.setxml_iso('U13', atom_site, False)
			U13 = self.setxml_iso('aniso_U_13', atom_site, True) if self.numtype(U13) else U13
			U23 = self.setxml_iso('U23', atom_site, False)
			U23 = self.setxml_iso('aniso_U_23', atom_site, True) if self.numtype(U23) else U23
			Uij = (U11,U22,U33, U12,U13,U23)

#		Biso = self.setxml_iso('B_iso', atom_site, True)
#		Uiso = self.setxml_iso('U_iso', atom_site, True)
#		U11 = self.setxml_iso('aniso_U_11', atom_site, False)
#		U22 = self.setxml_iso('aniso_U_22', atom_site, False)
#		U12 = self.setxml_iso('aniso_U_12', atom_site, False)
#		Uij = (U11,U22, U12)
#		if self.dim == 3:
#			U33 = self.setxml_iso('aniso_U_33', atom_site, False)
#			U13 = self.setxml_iso('aniso_U_13', atom_site, False)
#			U23 = self.setxml_iso('aniso_U_23', atom_site, False)
#			Uij = (U11,U22,U33, U12,U13,U23)

		atom = atomXtal(label, xyz, -1, valence, occ, WyckoffSymbol,None,mult, Biso,Uiso,Uij, DebyeT)
		return atom

	def interpDouble(self,str):
		# returns the double value of str, "1" --> 1.0,  "1/2" --> 0.5, "abc" --> NaN
		# this allow use of simple fractions in xml files to specify fractional coordinates and occupancy
		list = str.split('/')
		if len(list) == 2:
			value = float(list[0]) / float(list[1])
		else:
			value = float(str)
		return value


	def numtype(self,val):
		try:	d = float(val)
		except: return 1
		if math.isnan(d):	return 2
		elif math.isinf(d):	return 1
		else: 				return 0


	def process_xml_bond(self,bondNode, labels):
		""" process one <bond_chemical> tag """
		unit = bondNode.getAttribute('unit')
		n0 = bondNode.getAttribute('n0')
		n1 = bondNode.getAttribute('n1')
		try:	btype = int(bondNode.getAttribute('type'))
		except:	btype = 1

		sss = bondNode.firstChild.nodeValue
		try:
			lengths = [float(sss)]							# a single bond length
		except:
			lengths = bondNode.firstChild.nodeValue.split()	# a list of bond lengths
			for i in range(len(lengths)): lengths[i] = float(lengths[i])

		if len(n0)<1 or len(n1)<1 or len(lengths)<1:
			raise ValueError('process_xml_bond(), INVALID bond, n0="%s", n1="%s", lengths = "%r"' % (n0,n1,bondNode.firstChild.nodeValue))
		if not ( (n0 in labels) and (n1 in labels) ):
			raise ValueError('process_xml_bond(), INVALID bond, n0="%s", n1="%s", lengths = "%r", n0 or n1 not a label' % (n0,n1,bondNode.firstChild.nodeValue))
		if btype<1 or btype>6:
			raise ValueError('process_xml_bond(), INVALID bond type, '%r' must be in range [1,6]' % (btype,))

		factor = self.ConvertLengthUnits(1,unit,'nm',defaultUnit='Angstrom')	# want length in nm
		if not (factor==1.0):
			for i in range(len(lengths)):
				lengths[i] *= factor

		bond = bondType(n0,n1,lengths,btype)
		return bond


	def process_xml_database(self, cif):
		"""
		process the <database_code> tag
		returns databaseCodes[(dnName,codeValue)], from the xml file,  a list of tuples
		"""
		databaseCodes = []
		dbs = cif.getElementsByTagName('database_code')
		for db in dbs:
			try:
				codeValue = db.firstChild.nodeValue
				dbName = db.getAttribute('db')
				databaseCodes.append((dbName,codeValue))
			except:
				pass

		if not databaseCodes: return None
		return databaseCodes


	def read_xml(self):
		"""	Take a control xml file and parse out values needed by ProcessOneDataSet()
			This is the opposite of writeInputXMLfile()
			This calls read_Vers1() or read_Vers2() depending upon the cif xml version
		"""
		a = xml.dom.minidom.parse(self.file,parser=None)
		cif = a.childNodes[0]
		if not(cif.nodeName == u'cif'): raise ValueError('read_xml(), cannot find <cif> node in "%s"' % self.file)

		try:	cif_version = int(cif.getAttribute('version'))
		except:	cif_version = 1						# default is version 1

		if cif_version==1:		out = self.read_Vers1(cif)
		elif cif_version==2:	out = self.read_Vers2(cif)
		else:					raise ValueError('ERROR -- readXTALcommon.read_xml(), Only understand cif_version 1 or 2, not %r' % (cif_version,))
		return out
	#		End of Start of XML file reading
	################################################################################



	################################################################################
	#		Start of Official CIF file reading
	def parseCIFfile(self, file):
		""" Read a Standard CIF file, and fill in the Lattice. """
		try:
			f = open(file,'r')
			buf = f.read()
			f.close()
		except:
			raise IOError('Cannot read from "%s"' % file)

		buf = buf.replace('\r\n','\n')
		buf = buf.replace('\n\r','\n')				# this line should never be needed
		buf = buf.replace('\r','\n')
		buf = buf + '\n'

		i = buf.find('data_')						# find the _data section
		if (i>0): i = buf.find("\ndata_",0)			# _data is not first, it must start a line
		if i<0: raise ValueError('Cannot find any "data_" line in CIF file')
		buf = buf[i:]								# skip possible leading NL

		if buf.find('data_general')==0:
			i = buf.find("\ndata_",0)				# skip a leading data_general, goto next one
			if i<1: raise ValueError('Cannot find the correct "data_" line in CIF file')
			buf = buf[i+1:]							# skip leading NL

		i = buf.find('\ndata_',2)					# check for second data_ section
		if i>1: buf = buf[0:i-1]					# trim off any following "data_" sections
		if len(buf)<1: raise ValueError('No data in CIF file')

		buf = buf.replace('\r\n','\n')				# want line separators to be only NL, not CRLF or CR
		buf = buf.replace('\n\r','\n')				# this is just incase the file writer was really messed up
		buf = buf.replace('\r','\n')				# want LF, not CR
		return buf


	def ChangeCIFline2List(self,line):
		""" change a CIF data line to a semi-colon separated list """
		line = line.lstrip()							# remove any indents
		line = line.replace("\t"," ")

		lout = []
		long = len(line)+2
		while(len(line)):
			isp = line.find(" ")
			iqu = line.find("'")
			if isp<0: isp = long						# change not found (=-1) into long
			if iqu<0: iqu = long

			if isp<iqu:									# found both, but space is first
				ll = line[0:isp]
				line = line[isp+1:]
			elif (iqu<isp):								# found a quote separator
				line = line[iqu+1:]						# trim off opening quote and all before
				iqu = line.find("'")					# find closing quote
				ll = line[0:iqu]
				line = line[iqu+1:]
			elif iqu==long and isp==long:				# only one item
				ll = line
				line = line[iqu+1:]
			else:
				break									# did not find space or quote, done

			if len(ll): lout.append(ll)					# add to lout if not empty
		return lout


	def CIFloopEnd(self,line):
		""" returns True if a loop ending line """
		if len(line)<1: return True
		elif line.startswith('_'): return True
		elif line.find('loop_')>=0: return True
		return False


	def CIF_loop_Labels(self,lines,istart):
		"""
		Get the labels from the next loop_. Returns a list of the labels.
		And index to the line AFTER the labels
		"""
		index = istart
		labels = []
		Nlines = len(lines)
		for i in range(istart, Nlines):
			try:
				if 'loop_' == lines[i].split()[0]: break
			except:
				pass
			index += 1
		if index == Nlines: return (-1,labels)		# did not find next loop_
		for index in range(index+1, Nlines):
			try:
				if lines[index][0] == '_':
					labels.append(lines[index])
				else: raise
			except: break
		return (index,labels)


	def CIF_readNumberErr(self,key,lines):
		""" Get the number from a _CIF_key = number . """
		value = None
		for line in lines:
			try:
				keyValue = line.split()
				if key == keyValue[0]:
					value = keyValue[1]
					break
			except:
				continue

		try:
			num,err = self.CIF_str2NumErr(value)
		except:
			num = err = NaN
		return (num, err)


	def CIF_str2NumErr(self, value):
		""" takes a string like '123.4(5)', returns (123.4,0.5) """
		value = value.replace(')','').split('(')
		if len(value) == 1:
			num = float(value[0])
			if num.is_integer(): num = int(num)
			err =  None
		elif len(value)>1:
			num = float(value[0])
			if num.is_integer(): num = int(num)
			err = float(value[1])
			if err.is_integer(): err = int(err)
			vv = value[0].strip().split('.')	# part before and after decimal point
			if len(vv)>0:						# value[0] has a decimal point
				err *= 10**(-len(vv[1]))		# shift err by length of part after decimal

		return (num,err)


	def CIF_readString(self,key,lines):
		""" Get the string from a _CIF_key = 'string' . """
		for line in lines:
			try:
				keyValue = line.split()
				if key == keyValue[0]:	break
				else:					line = None
			except:
				continue
		if not line: return ''

		i0 = line.find("'")
		i1 = line.find('"')
		if i0<0 and i1<0:				# no quote of either kind, just return all of line after key
			return string.join(keyValue[1:]).strip()

		if i0<0:						# using double-quotes
			quote = '"'
			i0 = i1+1
		else:							# using single-quotes
			quote = "'"
			i0 += 1

		i1 = line.find(quote,i0)
		if (i0<1 or i1<i0): return ''
		return line[i0:i1].strip()


	def CIF_fill_databaseCodes(self,lines):
		""" returns databaseCodes[(dnName,codeValue)], from the CIF file lines """
		dbLead = '_database_code_'					# all database code lines start with '_database_code_', '_database_code_ICSD'
		itrim = len(dbLead)
		databaseCodes = []
		for line in lines:
			try:
				if not line.startswith(dbLead): raise
				arr = line.split()
				if len(arr) < 2 : raise
				db = arr[0]
				db = db[itrim:].strip()				# trim off "_database_code_"
				if not db: raise
				del arr[0]							# remove db name from list
				codeValue = " ".join(arr)			# put back together what is left
				codeValue = codeValue.strip()
				if not codeValue: raise
				databaseCodes.append((db,codeValue))
			except:
				pass
		if not databaseCodes: return None
		return databaseCodes
	#		End of Official CIF file reading
	################################################################################



	################################################################################
	#		Start of common routines
	def FindIDfromSymOps(self,symOpList):
		try:
			symOpList = set(symOpList)					# need to compare sets, not lists
			Nop = len(symOpList)
			for id in self.allIDs:
				idList = self.symOpsList(id)
				if len(idList) != Nop: continue			# number of operations must match
				if set(idList) == symOpList: return id	# done
		except:	pass
		return None										# failed to set SpaceGroupID using symOpList
	#		End of common routines
	################################################################################



	################################################################################
	#		Start of utilities
	def Condition_fractional(self,val):
		"""
		val is a fractional coordinate, if it is close to 1/3 or 1/6, make it exact
		1/2 & 1/4 don't need this.
		val must be within 4 places to be close enough, e.g. 0.333 will not be changed.
		"""
		if type(val) is int: return val
		elif val.is_integer(): return val
		elif val==0 or math.isnan(val) or math.isinf(val): return val

		places = self.placesOfPrecision(val % 1)		# always in range [1,18]
		places = min(places,12)							# limit to 12 places
#		print '  places =',places
		if places<4: return val

		tens = float( 10**places )
#		print '  tens =',tens
		tol6 = 3.9 / tens
		err6 = abs(round(6*val) - (6*val))
#		print '  err6 =',err6,'    tol6 =',tol6
		if err6>0 and err6<tol6: val = round(val*6)/6 
		return val


	def placesOfPrecision(self,a):
		# number of significant figures in a number (at most 16)

		if a==0 or math.isinf(a): return 1
		elif math.isnan(a): return 0
		a = self.roundSignificant(abs(a),17)
		for i in range(1,18):			# i = [1,17]
			if abs(a - self.roundSignificant(a,i))/a < 1e-15: break
		return i


	def roundSignificant(self,val,N):
		# round val to N significant figures
		# val			input value to round
		# N				number of significant figures
		if val==0 or math.isnan(val) or math.isinf(val): return val
		sign = math.copysign(1, val)
		val = abs(val)
		tens = 10**(N - math.floor(math.log10(val))-1)
		return sign*round(val*tens)/tens



	def ConvertLengthUnits(self, ValueIn, unitIN, unitOUT=None, defaultUnit='m'):
		"""
		converts ValueIn[unitIN] --> out[unitOUT]
		if unitIN is empty, then assume unitIN=defalutUnit
		"""
		if not unitIN: unitIN = defaultUnit
		if not unitOUT: unitOUT = defaultUnit
		# comment DS
		#return units((ValueIn,unitIN), unitOUT).num
		return ValueIn
	#		End of utilities
	################################################################################



####################################################################################
#		Start of read in an Official 3D CIF file
class read3Dcif(LatticeBase3D, readXTALcommon):
	""" A Class to read in 3D CIF files. """

	def __init__(self, file):
		readXTALcommon.__init__(self, file)			# sets some big lists and provides some utility functions
		LatticeBase3D.__init__(self)	# sets some big lists and provides some utility functions
		return None


	def read(self):
		buf = self.parseCIFfile(self.file)		# read in a standard CIF file
		return self.CIF_interpret(buf)			# interpret the *.cif file


	def CIF_interpret(self, buf):
		"""
		Interpret a buffer with a single CIF lattice.
		buf is assumed to have each line ONLY terminated with a single "\n"
		and there are no "\cr" characters.
		lines is an array of individual lines from the CIF file.
		Each line has been trimmed front and back of white space.
		"""
		self.dim = 3
		# create a list of clean lines from the buffer
		linesTemp = buf.split('\n')					# a list of all lines in buf
		lines = []									# this will hold the cleaned up list of lines
		for i in range(len(linesTemp)):				# strip off all white space from every line
			try:
				line = linesTemp[i].strip()
				if line[0] == '#': continue			# skip comments
				lines.append(line)					# not a comment & cleaned up, append to lines
			except: pass

		formula = self.CIF_readString("_chemical_formula_structural",lines)
		desc = formula
		if len(desc)<1: desc = self.CIF_readString('_chemical_name_systematic',lines)
		if len(desc)<1: desc = self.CIF_readString('_chemical_name_mineral',lines)
		if len(desc)<1: desc = self.CIF_readString('_pd_phase_name',lines)
		if len(desc)<1: desc = self.CIF_readString('_pd_phase_id',lines)
		databaseCodes = self.CIF_fill_databaseCodes(lines)				# fill databaseCodes[] with (dbName,codeValue) tuples

		# find lattice constants
		a = self.CIF_readNumberErr("_cell_length_a",lines)[0]/10		# want nm, cif is in Angstroms
		b = self.CIF_readNumberErr("_cell_length_b",lines)[0]/10
		c = self.CIF_readNumberErr("_cell_length_c",lines)[0]/10
		alpha = self.CIF_readNumberErr("_cell_angle_alpha",lines)[0]	# angle in degree
		beta = self.CIF_readNumberErr("_cell_angle_beta",lines)[0]
		gamma = self.CIF_readNumberErr("_cell_angle_gamma",lines)[0]
		if math.isnan(a+b+c+alpha+beta+gamma):
			raise ValueError('Cannot get valid lattice constants from CIF file')

		# find Space Group
		try:	SpaceGroupID = self.CIF_readString("_space_group_id",lines)
		except:	SpaceGroupID = None
		if not SpaceGroupID:				# try using the H-M symbol to set the SpaceGroupID
			try:
				HMsym = self.CIF_readString("_symmetry_space_group_name_H-M",lines)
				if len(HMsym)<1: raise
				idList = self.SymString2IDs(HMsym+'*',31)					# check everybody
				if len(idList)<1: idList = self.SymString2IDs(HMsym+'*',-1)	# ignore minus signs too
				SpaceGroupID = idList[0]
			except:	pass
		if not SpaceGroupID:				# try using the symmetry operations
			symOpslist = self.GetSymOpsFromCIFbuffer(lines)
			SpaceGroupID = self.FindIDfromSymOps(symOpslist)
			# print 'found SpaceGroupID = "%s" from the symmetry ops' % (SpaceGroupID,)
		if not SpaceGroupID:				# use the default SpaceGroupID for this SG
			try:
				SG = int(self.CIF_readNumberErr("_symmetry_Int_Tables_number",lines)[0])
				SpaceGroupID = self.FindDefaultIDforSG(SG)
			except:	pass
		try:	self.validSpaceGroupID(SpaceGroupID)						# raises exception if not a valid Space Group ID
		except:	SpaceGroupID = self.FindDefaultIDforSG(SpaceGroupID)		#   or if not an integer in [1-230] either
		if not self.validSpaceGroupID(SpaceGroupID): raise ValueError('CIF_interpret(), Unable to set Space Group ID')
		SG = int(SpaceGroupID.split(':')[0])	# Space Group number, from International Tables

		if len(desc)<1: 'struct%s' % SpaceGroupID

		Temperature = self.CIF_readNumberErr("_cell_measurement_temperature",lines)[0]	# temperature (K) for cell parameters

		# find the atoms
		atoms = []
		bonds = tuple()

		index = 0
		while index >= 0:
			index,labels = self.CIF_loop_Labels(lines,index)
			if '_atom_site_fract_x' in labels: break

		if len(labels)>2:
			for index in range(index,len(lines)):
				line = lines[index]
				if self.CIFloopEnd(line): break					# loop until you get an empty line, over all symmetry ops
				elif line.startswith('#'): continue				# skip any blank lines starting with '#'
				line = self.ChangeCIFline2List(line)			# make line a list
				try:
					iname = labels.index('_atom_site_label')
					label = line[iname]
				except:
					break										# must have a label

				try:
					x = self.CIF_str2NumErr(line[labels.index('_atom_site_fract_x')])[0]
					y = self.CIF_str2NumErr(line[labels.index('_atom_site_fract_y')])[0]
					z = self.CIF_str2NumErr(line[labels.index('_atom_site_fract_z')])[0]
					x = self.Condition_fractional(x)			# change 0.3333 -> 0.333333333333333 (exact)
					y = self.Condition_fractional(y)
					z = self.Condition_fractional(z)
				except:
					break										# must have fractional coords

				try:	WyckoffSymbol = line[labels.index('_atom_site_Wyckoff_symbol')]
				except:	WyckoffSymbol = ''
				try:	occ = self.CIF_str2NumErr(line[labels.index('_atom_site_occupancy')])[0]
				except:	occ = 1
				try:	Biso =  self.CIF_str2NumErr(line[labels.index('_atom_site_B_iso_or_equiv')])[0]/100	# assume value in Angstrom^2
				except:	Biso = NaN
				try:	Uiso =  self.CIF_str2NumErr(line[labels.index('_atom_site_U_iso_or_equiv')])[0]/100	# assume value in Angstrom^2
				except:	Uiso = NaN
				occ = min(1.0,occ)
				try:
					U11 = self.CIF_str2NumErr(line[labels.index('_atom_site_aniso_U_11')])[0]/100	# assume value in Angstrom^2
					U22 = self.CIF_str2NumErr(line[labels.index('_atom_site_aniso_U_22')])[0]/100
					U33 = self.CIF_str2NumErr(line[labels.index('_atom_site_aniso_U_33')])[0]/100
					try:
						U12 = self.CIF_str2NumErr(line[labels.index('_atom_site_aniso_U_12')])[0]/100
						U13 = self.CIF_str2NumErr(line[labels.index('_atom_site_aniso_U_13')])[0]/100
						U23 = self.CIF_str2NumErr(line[labels.index('_atom_site_aniso_U_33')])[0]/100
					except:
						U12 = U13 = U23 = NaN
				except:
					U11 = U22 = U33 = U12 = U13 = U23 = NaN

				try:
					mult = self.CIF_str2NumErr(line[labels.index('_atom_site_symmetry_multiplicity')])[0]
					if not mult: mult = 1
				except:
					mult = 1

				try:	sss = line[labels.index('_atom_site_type_symbol')]
				except: sss = ''
				if sss.endswith('-'):	valence = -1
				elif sss.endswith('+'):	valence = 1
				else:					valence = 0
				try:	valence *= int(sss[-2])
				except:	pass

				# Zatom will be assigned in the call to atomXtal()
				atom = atomXtal(label, (x,y,z), -1, valence, occ, WyckoffSymbol, None, mult, Biso,Uiso,(U11,U22,U33,U12,U13,U23))
				atoms.append(atom)

		return {'SpaceGroupID':SpaceGroupID, 'a':a, 'b':b, 'c':c, 'alpha':alpha, 'beta':beta, 'gamma':gamma, 'desc':desc, 
			'formula':formula, 'Temperature':Temperature, 'atoms':atoms, 'bonds':bonds, 'databaseCodes':databaseCodes, 'dim':self.dim}


#	def SymOpsMatchesID(self,id,symList):
#		"""
#		check that the given list of sym ops match my list using id
#		returns True if a match, False if not match
#		id				SpaceGroupID
#		symList			list of sym ops from a cif file
#		"""
#		internal = self.GetSymmetryOperations(id)	# returns matrices
#		N = len(internal)
#		if len(symList) != N: return False		# number of operations differ, cannot match
#
#		symV = []
#		for op in symList:
#			symV.append(self.symOpList2number(op))
#
#		internalV = []
#		for mat in internal:
#			mx = mat[0][0]
#			my = mat[0][1]
#			mz = mat[0][2]
#			b  = mat[0][3]
#			crc = zlib.crc32("%d%d%d%.4f" % (mx,my,mz,b), 0)
#
#			mx = mat[1][0]
#			my = mat[1][1]
#			mz = mat[1][2]
#			b  = mat[1][3]
#			crc = zlib.crc32("%d%d%d%.4f" % (mx,my,mz,b), crc)
#
#			mx = mat[2][0]
#			my = mat[2][1]
#			mz = mat[2][2]
#			b  = mat[2][3]
#			crc = zlib.crc32("%d%d%d%.4f" % (mx,my,mz,b), crc)
#
#			internalV.append(crc)
#
#		return len(set(symV).intersection(internalV))==N
#
#
#	def symOpList2number(self,symOp):
#		""" takes a list of symOps, e.g. "x+1/2,y+1/2,z" and returns a unique number """
#		terms = symOp.split(',')
#		crc = self.expr2number(terms[0],0)		# x term
#		crc = self.expr2number(terms[1],crc)	# y term
#		crc = self.expr2number(terms[2],crc)	# z term
#		return crc
#
#
#	def expr2number(self, expression,crc):
#		mx,my,mz,b = self.ParseOneSymEquation(expression)
#		return zlib.crc32("%d%d%d%.4f" % (mx,my,mz,b), crc)
#
#
#	def ParseOneSymEquation(self, expression):
#		""" parse one expression of form "-x+y"  or "-x", or "-x+y, etc. """
#		first = expression[0]
#		if first!='+' and first!='-': expression = "+" + expression		# so add a leading '+'
#		expression = expression.lower()					# only lower case
#		expression = expression.replace(' ','')			# no spaces
#		mx = my = mz = b = 0
#
#		# only certain fractions are allowed as constants
#		fractions = {'+1/2':0.5,'-1/2':-0.5,'+1/3':1./3.,'-1/3':-1./3.,'+2/3':2./3.,'-2/3':-2./3.,'+1/4':0.25,'-1/4':-0.25,'+3/4':0.75,'-3/4':-0.75,'+1/6':1./6.,'-1/6':-1./6.,'+5/6':5./6.,'-5/6':-5./6.}
#		for key in fractions:							# find the constant part, b
#			if expression.find(key)>=0:
#				b = fractions[key]
#				break
#
#		if expression.find('+x')>=0:	mx = 1			# find the x part mx
#		elif expression.find('-x')>=0:	mx = -1
#
#		if expression.find('+y')>=0:	my = 1			# find the y part my
#		elif expression.find('-y')>=0:	my = -1
#
#		if expression.find('+z')>=0:	mz = 1			# find the z part mz
#		elif expression.find('-z')>=0:	mz = -1
#		return (mx,my,mz,b)


	def GetSymOpsFromCIFbuffer(self,lines):
		"""
		get the sym ops from a CIF file buffer
		find loop_ with symmetry ops
		"""
		symTag = ""
		index = 0
		while index >= 0:
			index,labels = self.CIF_loop_Labels(lines,index)
			if '_symmetry_equiv_pos_as_xyz' in labels:
				symTag = "_symmetry_equiv_pos_as_xyz"
				break
			if '_space_group_symop_operation_xyz' in labels:
				symTag = "_space_group_symop_operation_xyz"
				break

		if len(symTag)<1: return None							# not found
		try:	isym = labels.index(symTag)
		except:	return None

		symOpsList = []
		for index in range(index,len(lines)):
			line = lines[index]
			if self.CIFloopEnd(line): break					# loop until you get an empty line, over all symmetry ops
			elif line.startswith('#'): continue				# skip any blank lines starting with '#'
			line = self.ChangeCIFline2List(line)			# make line a list
			try:	op = line[isym]
			except:	break									# must have a sym op
			op = op.replace('\t','')						# remove all tabs
			op = op.replace(' ','')							# remove all spaces
			op = op.strip()									# operations now look like: 'x,y,z'  or  '-y-1/4,-x-1/4,-z+1/4'
			symOpsList.append(op)

		return symOpsList

#		End of read in an Official 3D CIF file
####################################################################################



####################################################################################
#		Start of read in a 3D XML file
class read3Dxml(LatticeBase3D, readXTALcommon):
	""" A Class to read in 3D XML files. """

	def __init__(self, file):
		readXTALcommon.__init__(self, file)			# sets some big lists and provides some utility functions
		LatticeBase3D.__init__(self)				# sets some big lists and provides some utility functions
		return None


	def read(self):
		return self.read_xml()


	def read_Vers2(self,cif):
		""" take a control xml file and parse out values needed by ProcessOneDataSet()
		This is the opposite of writeInputXMLfile() """

		cifRequired = ['chemical_name_common', 'cell', 'space_group']
		cifOptional = ['chemical_formula', 'chemical_formula_structural', 'database_code', 'cell', 'atom_site', 'bond_chemical', 'citation', 'volume', 'temperature', 'audit', 'R_factor_all']
		check = self.checkRequiredOptional(cif, cifRequired, cifOptional)
		if check: self.fileChecking.append(check)

		try:	self.dim = int(cif.getAttribute('dim'))
		except:	self.dim = None
		if not self.dim:
			try:	self.dim = int( cif.getElementsByTagName('dim')[0].firstChild.nodeValue )
			except:	self.dim = 3						# default is 3D (other choice is 2D)
		if self.dim!=3: raise ValueError('read3Dxml(), dim must be 3, not %r' %(self.dim,))
		out = {'dim':self.dim}

		# process the <space_group> tag
		try:	space_group = cif.getElementsByTagName('space_group')[0]
		except:	raise IndexError('read3Dxml(), could not find "<space_group>"')
		sgRequired = [('id','IT_number','H-M','symops')]
		sgOptional = ['Hall', 'setting']
		check = self.checkRequiredOptional(space_group, sgRequired, sgOptional)
		if check: self.fileChecking.append(check)
		out['SpaceGroupID'] = self.process_xml_space_group(space_group)

		# process generic info in <cif> tag
		try:	desc = cif.getElementsByTagName('chemical_name_common')[0].firstChild.nodeValue
		except:	desc = 'struct%s' % SpaceGroupID
		out.update({'desc':desc})
		try:	out.update({'formula':cif.getElementsByTagName('chemical_formula')[0].firstChild.nodeValue})
		except:	
				try:	out.update({'formula':cif.getElementsByTagName('chemical_formula_structural')[0].firstChild.nodeValue})
				except:	pass
		databaseCodes = self.process_xml_database(cif)			# get all <database_code>, returns databaseCodes[(dnName,codeValue)]
		if databaseCodes: out.update({'databaseCodes':databaseCodes})

		# process the <cell> tag
		try:	cell = cif.getElementsByTagName('cell')[0]
		except:	raise IndexError('read3Dxml(), could not find "<cell>"')
		cellRequired = ['a', 'b', 'c', 'alpha', 'beta', 'gamma']
		cellOptional = ['temperature', 'alphaT', 'volume', 'thermalExpansion']
		check = self.checkRequiredOptional(cell, cellRequired, cellOptional)
		if check: 
			self.fileChecking.append(check)
		out.update(self.process_xml_cell(cell))

		# process the <atom_sites> tags
		atoms = list()
		atom_sites = cif.getElementsByTagName('atom_site')
		atomRequired = [('label', 'symbol'), ('fract','fract_x','fract_y','fract_z')]
		atomOptional = ['occupancy', 'oxidation', 'WyckoffSymbol', 'DebyeTemperature', 'Uiso', 'Biso', 'U11', 'U22', 'U33', 'U12', 'U13', 'U23']
		atomOptional += [ 'valence', 'U_iso', 'B_iso', 'aniso_U_11', 'aniso_U_22', 'aniso_U_33', 'aniso_U_12', 'aniso_U_13', 'aniso_U_23']
		for atom_site in atom_sites:
			check = self.checkRequiredOptional(atom_site, atomRequired, atomOptional)
			if check: self.fileChecking.append(check)
			atom = self.process_xml_atom_site(atom_site)
			atoms.append(atom)
		out.update({'atoms':atoms})

		labels = self.ForceXtalAtomNamesUnique(atoms)					# force all atom labels to be unique
		bonds = list()
		bondNodes = cif.getElementsByTagName('bond_chemical')
		for bondNode in bondNodes:
			bond = self.process_xml_bond(bondNode,labels)
			bonds.append(bond)
		out.update({'bonds':bonds})

		if self.fileChecking: out['fileChecking'] = self.fileChecking
		return out

	def read_Vers1(self,cif):
		""" take a control xml file and parse out values needed by ProcessOneDataSet()
		This is the opposite of writeInputXMLfile() """

		cifRequired = ['chemical_name_common', 'cell', ('space_group_id', 'space_group_IT_number', 'H-M', 'symmetry_equiv_pos_as_xyz', 'space_group_symop_operation_xyz')]
		cifOptional = ['chemical_formula_structural', 'Hall', 'database_code', 'cell', 'atom_site', 'bond_chemical', 'citation', 'volume', 'temperature', 'R_factor_all', 'dim']
		check = self.checkRequiredOptional(cif, cifRequired, cifOptional)
		if check: self.fileChecking.append(check)

		try:	self.dim = int( cif.getElementsByTagName('dim')[0].firstChild.nodeValue )
		except:	self.dim = 3						# default is 3D (other choice is 2D)
		if self.dim != 3: raise ValueError('read3Dxml(), dim must be 3, not %r' %(self.dim,))

		try:	SpaceGroupID = cif.getElementsByTagName('space_group_id')[0].firstChild.nodeValue
		except:	SpaceGroupID = None
		if not SpaceGroupID:				# try using the H-M symbol to set the SpaceGroupID
			try:
				HMsym = cif.getElementsByTagName('H-M')[0].firstChild.nodeValue
				idList = self.SymString2IDs(HMsym+'*',31)					# check every body
				if len(idList)<1: idList = self.SymString2IDs(HMsym+'*',-1)	# ignore minus signs too
				SpaceGroupID = idList[0]
			except:	pass
		if not SpaceGroupID:				# use the default SpaceGroupID for this SG
			try:
				SG = int(cif.getElementsByTagName('space_group_IT_number')[0].firstChild.nodeValue)
				SpaceGroupID = self.FindDefaultIDforSG(SG)
			except:	pass
		try:	self.validSpaceGroupID(SpaceGroupID)						# raises exception if not a valid Space Group ID
		except:	SpaceGroupID = self.FindDefaultIDforSG(SpaceGroupID)		#   or if not an integer in [1-230] either
		if not self.validSpaceGroupID(SpaceGroupID): raise ValueError('read3Dxml(), Unable to set Space Group ID')
		SG = int(SpaceGroupID.split(':')[0])	# Space Group number, from International Tables

		try:	desc = cif.getElementsByTagName('chemical_name_common')[0].firstChild.nodeValue
		except:	desc = 'struct%s' % SpaceGroupID

		try:	formula = cif.getElementsByTagName('chemical_formula_structural')[0].firstChild.nodeValue
		except:	formula = None

		databaseCodes = []										# all <database_code>, databaseCodes[(dnName,codeValue)]
		for code in knowDatabaseCodes:
			try:			# add all of the old <code> tags to databaseCodes[]
				for node in cif.getElementsByTagName(code): databaseCodes = [(code, node.firstChild.nodeValue)]
			except: pass

		try:
			cell = cif.getElementsByTagName('cell')[0]
		except:
			raise IndexError('read3Dxml(), could not find "<cell>"')
		cellRequired = ['a', 'b', 'c', 'alpha', 'beta', 'gamma']
		cellOptional = ['temperature', 'alphaT', 'volume']
		check = self.checkRequiredOptional(cell, cellRequired, cellOptional)
		if check: self.fileChecking.append(check)

		try:
			node = cif.getElementsByTagName('a')[0]
			a = float(node.firstChild.nodeValue)
			unit = node.getAttribute('unit')
			a = self.ConvertLengthUnits(a,unit,'nm',defaultUnit='Angstrom')		# want length in nm
		except:
			raise ValueError('read3Dxml(), cannot find a')

		try:
			node = cif.getElementsByTagName('b')[0]
			b = float(node.firstChild.nodeValue)
			unit = node.getAttribute('unit')
			b = self.ConvertLengthUnits(b,unit,'nm',defaultUnit='Angstrom')		# want length in nm
		except:
			raise ValueError('read3Dxml(), cannot find b')

		try:
			node = cif.getElementsByTagName('c')[0]
			c = float(node.firstChild.nodeValue)
			unit = node.getAttribute('unit')
			c = self.ConvertLengthUnits(c,unit,'nm',defaultUnit='Angstrom')		# want length in nm
		except:
			raise ValueError('read3Dxml(), cannot find c')

		try:
			node = cif.getElementsByTagName('alpha')[0]
			alpha = float(node.firstChild.nodeValue)
			unit = node.getAttribute('unit')
			if not len(unit): unit = 'deg'										# default input is degree
			alpha = units((alpha,unit),'deg').num								# convert to degree
		except:
			raise ValueError('read3Dxml(), cannot find alpha')

		try:
			node = cif.getElementsByTagName('beta')[0]
			beta = float(node.firstChild.nodeValue)
			unit = node.getAttribute('unit')
			if not len(unit): unit = 'deg'										# default input is degree
			beta = units((beta,unit),'deg').num									# convert to degree
		except:
			raise ValueError('read3Dxml(), cannot find beta')

		try:
			node = cif.getElementsByTagName('gamma')[0]
			gamma = float(node.firstChild.nodeValue)
			unit = node.getAttribute('unit')
			if not len(unit): unit = 'deg'										# default input is degree
			gamma = units((gamma,unit),'deg').num								# convert to degree
		except:
			raise ValueError('read3Dxml(), cannot find gamma')

		try:
			node = cif.getElementsByTagName('temperature')[0]
			Temperature = float(node.firstChild.nodeValue)
			unit = node.getAttribute('unit')
			if len(unit): Temperature = ConvertTemperatureUnits(Tin,unit,'C',defaultUnit='C')
		except:
			Temperature = None

		try:	alphaT = float(cif.getElementsByTagName('alphaT')[0].firstChild.nodeValue)
		except:	alphaT = None

		atoms = list()
		atom_sites = cif.getElementsByTagName('atom_site')
		atomRequired = [('label', 'symbol'), ('fract_xyz', ('fract_x', 'fract_y', 'fract_z'))]
		atomOptional = ['occupancy', 'valence', 'WyckoffSymbol', 'DebyeTemperature', 'U_iso', 'B_iso', 'aniso_U_11', 'aniso_U_22', 'aniso_U_33', 'aniso_U_12', 'aniso_U_13', 'aniso_U_23']
		for atom_site in atom_sites:
			check = self.checkRequiredOptional(atom_site, atomRequired, atomOptional)
			if check: self.fileChecking.append(check)

			try:	label = atom_site.getElementsByTagName('label')[0].firstChild.nodeValue
			except: label = ''
			try:	symbol = atom_site.getElementsByTagName('symbol')[0].firstChild.nodeValue
			except: symbol = label
			if len(label)<1: label = symbol		# if no label given, use the symbol (may not be unique)
			if len(label)+len(symbol) < 1: raise ValueError('read3Dxml(), each atom site requires a label or a symbol')
#			Zatom will be assigned in the call to atomXtal()

			try:	valence = int(atom_site.getElementsByTagName('valence')[0].firstChild.nodeValue)
			except: valence = 0				# valence defaults to 0 (integer)

			try:
				xyz = atom_site.getElementsByTagName('fract_xyz')[0].firstChild.nodeValue.split()
				x,y,z = xyz					# this line fails unless len(xyz)==3
				x = float(x)
				y = float(y)
				z = float(z)
			except:
				try:
					x = float(atom_site.getElementsByTagName('fract_x')[0].firstChild.nodeValue)
					y = float(atom_site.getElementsByTagName('fract_y')[0].firstChild.nodeValue)
					z = float(atom_site.getElementsByTagName('fract_z')[0].firstChild.nodeValue)
				except:
					x = y = z = float('nan')

			x = self.Condition_fractional(x)	# change 0.3333 -> 0.333333333333333 (exact)
			y = self.Condition_fractional(y)
			z = self.Condition_fractional(z)
			xyz = [x,y,z]						# reconstitute xyz as a float, not a list of strings

			if math.isnan(x+y+z):			# cannot find valid x,y,z, give up
				raise ValueError('read3Dxml(), cannot find fractional x,y,z')

			try:	WyckoffSymbol = atom_site.getElementsByTagName('WyckoffSymbol')[0].firstChild.nodeValue
			except: WyckoffSymbol = ''

			mult = 1
			if (len(WyckoffSymbol) > 0) and (math.isnan(x+y+z)):	# try to set x,y,z using Wyckoff symbol
				(x,y,z) = self.ForceXYZtoWyckoff(SG,WyckoffSymbol,x,y,z)
				mult = self.MultiplicityFromWyckoff(SG,WyckoffSymbol)# find multiplicity

			try:	occ = float(atom_site.getElementsByTagName('occupancy')[0].firstChild.nodeValue)
			except: occ = 1.0

			try:
				node = atom_site.getElementsByTagName('DebyeTemperature')[0]
				DebyeT = float(node.firstChild.nodeValue)
				unit = node.getAttribute('unit')
				DebyeT = ConvertTemperatureUnits(DebyeT,unit,'K',defaultUnit='K')
				if DebyeT<=0: DebyeT = float('nan')
			except:
				DebyeT = float('nan')

			Biso = self.setxml_iso('B_iso', atom_site, True)
			Uiso = self.setxml_iso('U_iso', atom_site, True)
			U11 = self.setxml_iso('aniso_U_11', atom_site, False)
			U22 = self.setxml_iso('aniso_U_22', atom_site, False)
			U33 = self.setxml_iso('aniso_U_33', atom_site, False)
			U12 = self.setxml_iso('aniso_U_12', atom_site, False)
			U13 = self.setxml_iso('aniso_U_13', atom_site, False)
			U23 = self.setxml_iso('aniso_U_23', atom_site, False)
			Uij = (U11,U22,U33,U12,U13,U23)

			atom = atomXtal(label, xyz, -1, valence, occ, WyckoffSymbol,None,mult, Biso,Uiso,Uij, DebyeT)
			atoms.append(atom)

		labels = self.ForceXtalAtomNamesUnique(atoms)					# force all atom labels to be unique

		bonds = list()
		bondNodes = cif.getElementsByTagName('bond_chemical')
		for node in bondNodes:
			unit = node.getAttribute('unit')
			n0 = node.getAttribute('n0')
			n1 = node.getAttribute('n1')

			sss = node.firstChild.nodeValue
			try:
				lengths = [float(sss)]							# a single bond length
			except:
				lengths = node.firstChild.nodeValue.split()		# a list of bond lengths
				for i in range(len(lengths)): lengths[i] = float(lengths[i])

			if len(n0)<1 or len(n1)<1 or len(lengths)<1:
				raise ValueError('read3Dxml(), INVALID bond, n0="%s", n1="%s", lengths = "%r"' % (n0,n1,node.firstChild.nodeValue))
			if not ( (n0 in labels) and (n1 in labels) ):
				raise ValueError('read3Dxml(), INVALID bond, n0="%s", n1="%s", lengths = "%r", n0 or n1 not a label' % (n0,n1,node.firstChild.nodeValue))

			factor = self.ConvertLengthUnits(1,unit,'nm',defaultUnit='Angstrom')	# want length in nm
			if not (factor==1.0):
				for i in range(len(lengths)):
					lengths[i] *= factor

			bond = bondType(n0,n1,lengths)
			bonds.append(bond)

		# set the values
		out = {'SpaceGroupID':SpaceGroupID, 'a':a, 'b':b, 'c':c, 'alpha':alpha, 'beta':beta, 'gamma':gamma, 'desc':desc, 
			'formula':formula, 'Temperature':Temperature, 'atoms':atoms, 'bonds':bonds, 'alphaT':alphaT, 'databaseCodes':databaseCodes, 'dim':self.dim}
		if self.fileChecking: out['fileChecking'] = self.fileChecking
		return out
#		End of read in a 3D XML file
####################################################################################



####################################################################################
#		Start of read in a 2D XML file
class read2Dxml(readXTALcommon, LatticeBase2D):
	""" A Class to read in 2D XML files. """

	def __init__(self, file):
		readXTALcommon.__init__(self, file)			# sets some big lists and provides some utility functions
		LatticeBase2D.__init__(self)				# sets some big lists and provides some utility functions
		return None


	def read(self):
		return self.read_xml()

	def read_Vers2(self, cif):
		""" take a control xml file and parse out values needed by ProcessOneDataSet()
		This is the opposite of writeInputXMLfile() """
		cifRequired = ['chemical_name_common', 'cell', 'space_group']
		cifOptional = ['chemical_formula', 'chemical_formula_structural', 'database_code', 'cell', 'atom_site', 'bond_chemical', 'citation', 'area', 'temperature', 'audit', 'R_factor_all']
		check = self.checkRequiredOptional(cif, cifRequired, cifOptional)
		if check: self.fileChecking.append(check)
		try:	self.dim = int(cif.getAttribute('dim'))
		except:	self.dim = None
		if not self.dim:
			try:	self.dim = int( cif.getElementsByTagName('dim')[0].firstChild.nodeValue )
			except:	self.dim = 3					# this must be present and have value of 2
		if self.dim != 2: raise ValueError('read2Dxml(), dim must be 2, not %r' %(self.dim,))
		out = {'dim':self.dim}

		# process the <space_group> tag
		try:	space_group = cif.getElementsByTagName('space_group')[0]
		except:	raise IndexError('read2Dxml(), could not find "<space_group>"')
		sgRequired = [('id','IT_number','H-M','symops')]
		sgOptional = ['Hall', 'setting']
		check = self.checkRequiredOptional(space_group, sgRequired, sgOptional)
		if check: self.fileChecking.append(check)
		out['SpaceGroupID'] = self.process_xml_space_group(space_group)

		# process generic info in <cif> tag
		try:	desc = cif.getElementsByTagName('chemical_name_common')[0].firstChild.nodeValue
		except:	desc = 'struct%s' % SpaceGroupID
		out.update({'desc':desc})
		try:	out.update({'formula':cif.getElementsByTagName('chemical_formula')[0].firstChild.nodeValue})
		except:	
				try:	out.update({'formula':cif.getElementsByTagName('chemical_formula_structural')[0].firstChild.nodeValue})
				except:	pass
		databaseCodes = []										# all <database_code>, databaseCodes[(dnName,codeValue)]
		for code in knowDatabaseCodes:
			try:			# add all of the old <code> tags to databaseCodes[]
				for node in cif.getElementsByTagName(code): databaseCodes = [(code, node.firstChild.nodeValue)]
			except: pass
		if databaseCodes: out['databaseCodes'] = databaseCodes

		# process the <cell> tag
		try:	cell = cif.getElementsByTagName('cell')[0]
		except:	raise IndexError('read2Dxml(), could not find "<cell>"')
		cellRequired = ['a', 'b', 'alpha']
		cellOptional = ['temperature', 'alphaT', 'thermalExpansion', 'area']
		check = self.checkRequiredOptional(cell, cellRequired, cellOptional)
		if check: self.fileChecking.append(check)
		out.update(self.process_xml_cell(cell))

		# process the <atom_sites> tags
		atoms = list()
		atom_sites = cif.getElementsByTagName('atom_site')
		atomRequired = [('label', 'symbol'), ('fract','fract_x','fract_y')]
		atomOptional = ['occupancy', 'oxidation', 'WyckoffSymbol', 'DebyeTemperature', 'Uiso', 'Biso', 'U11', 'U22', 'U12']
		atomOptional += ['valence', 'U_iso', 'B_iso', 'aniso_U_11', 'aniso_U_22', 'aniso_U_12']
		for atom_site in atom_sites:
			check = self.checkRequiredOptional(atom_site, atomRequired, atomOptional)
			if check: self.fileChecking.append(check)
			atom = self.process_xml_atom_site(atom_site)
			atoms.append(atom)
		out.update({'atoms':atoms})

		labels = self.ForceXtalAtomNamesUnique(atoms)			# force all atom labels to be unique

		bonds = list()
		bondNodes = cif.getElementsByTagName('bond_chemical')
		for bondNode in bondNodes:
			bond = self.process_xml_bond(bondNode,labels)
			bonds.append(bond)
		out.update({'bonds':bonds})

		if self.fileChecking: out['fileChecking'] = self.fileChecking
		return out


	def read_Vers1(self, cif):
		""" You CANNOT read a 2D file in cif xml version 1 """
		raise ValueError('ERROR -- read2Dxml(), You CANNOT read a 2D file in cif xml version 1, you need at least version 2.')
#		End of read in a 2D XML file
####################################################################################




class readXTAL(object):
	""" A Class to read crystal info from 3D CIF files, or the equivalent 2D or 3D XML files. """

	def __init__(self, file):
		if file == 'dummy file name testing': return None	# just used for testing, does not read a file
		if not os.path.isfile(file): raise ValueError('readXTAL(), input file "%r" does not exist' % file)
		if os.path.getsize(file)<10: raise ValueError('readXTAL(), input file "%r" is too small to be OK' % file)

		self.file = file
		(fname,ext) = os.path.splitext(file)
		self.ext = ext.lower()
		self.fileChecking = []

		return None


	def read(self):
		(dtype,dim) = self.fileTypeDim()

		if not (dim==2 or dim==3):		raise ValueError('Can only read files of dimension 2 or 3, not %r' % (dim,))
		elif dtype=='cif' and dim!=3:	raise ValueError('*.cif files can only be of dimension 3, no %r' % (dim,))
		elif dtype=='cif':				reader = read3Dcif(self.file).read()
		elif dim == 3:					reader = read3Dxml(self.file).read()
		elif dim == 2:					reader = read2Dxml(self.file).read()
		return reader


	def fileTypeDim(self):
		""" return (type,dim), where type is 'xml' or 'cif', and dim is 2 or 3"""
		if self.ext == '.cif':	type = 'cif'
		else:					type = 'xml'

		if type=='cif': return (type,3)			# *.cif files are only 3D

		# an xml file, look inside
		try:
			f = open(self.file,'r')
			buf = f.read()
			f.close()
		except:
			raise IOError('Cannot read from file:  "%s"' % file)

		dim = 3									# the default
		i0 = buf.find('<cif ')
		i1 = buf.find('</cif>',max(0,i0))
		if (i0>0) and (i0<i1):
			i0 = buf.find(' dim="')		
			if i0>0 and i0<i1:
				try:	dim = int(buf[i0+6])	# value after 'dim="'
				except:	dim = 3					# default
		return (type,dim)





if __name__ == '__main__':
	"""
	Main function for readCIF.py.

	Test cases for Lattice class to verify correct behavior.
	"""
	from JZTutil import JZTtesting
	testing = JZTtesting(__file__)


	def test_Condition_fractional(val, desired):
		rCIF = readXTALcommon('dummy file name testing')
		result = rCIF.Condition_fractional(val)
		if abs(desired-result) > 1e-15:
			print ('ERROR -- Condition_fractional(%r) = %r,  should be %r' % (val, result, desired))
			return True
		else:
			return False


	if testing.doit('check numeric utilities'):			#  2**0 = 1
		err = False
		err = test_Condition_fractional(0.5, 1.0/2.0) or err
		err = test_Condition_fractional(0.25, 1.0/4.0) or err
		err = test_Condition_fractional(0.75, 3.0/4.0) or err
		err = test_Condition_fractional(1.33, 1.33) or err
		err = test_Condition_fractional(-1.33, -1.33) or err
		err = test_Condition_fractional(1.333, 1.333) or err
		err = test_Condition_fractional(-1.333, -1.333) or err
		err = test_Condition_fractional(0.33, 0.33) or err
		err = test_Condition_fractional(0.333, 0.333) or err
		err = test_Condition_fractional(-0.33, -0.33) or err
		err = test_Condition_fractional(-0.333, -0.333) or err
		err = test_Condition_fractional(0.3333, 1.0/3.0) or err
		err = test_Condition_fractional(0.16667, 1.0/6.0) or err
		err = test_Condition_fractional(0.16667, 1.0/6.0) or err
		err = test_Condition_fractional(0.66667, 2.0/3.0) or err
		err = test_Condition_fractional(0.83333, 5.0/6.0) or err
		if err: testing.addErr()

	if testing.doit('check reading YBa2Cu3O7.xtal'):		#  2**1 = 2
		err = False
		rCIF = readXTAL('materials/YBCO/YBa2Cu3O7.xtal')
		YBCOfile = rCIF.read()
		print (YBCOfile)
		if err: testing.addErr()

	if testing.doit('check reading GaAs.xtal'):			#  2**2 = 4
		err = False
		GaAsfile = readXTAL('materials/GaAs.xtal').read()
		print (GaAsfile)
		if err: testing.addErr()

	if testing.doit('check reading Pu-alpha.xtal'):		#  2**3 = 8
		err = False
		PuAlpha = readXTAL('materials/Pu-alpha.xtal').read()
		print (PuAlpha)
		if err: testing.addErr()

	if testing.doit('check reading Si.xtal'):			#  2**4 = 16
		err = False
		SiFile = readXTAL('materials/Si.xtal').read()
		print (SiFile)
		if err: testing.addErr()

	if testing.doit('check reading bad.xtal'):			#  2**5 = 32
		err = True
		try:	badFile = readXTAL('test/bad.xml').read()		# should Fail
		except Exception as e: err = False
		if err:
			print (badFile)
			testing.addErr()
		else: print(e)

	if testing.doit('check reading bad2.xtal'):			#  2**6 = 64
		try:
			badFile = readXTAL('test/bad2.xml').read()		# should be OK
			print (badFile)
		except:
			print ('failed on: ,"test/bad2.xml", as it should')
			testing.addErr()

	if testing.doit('check reading PigeoniteJZT.cif'):	#  2**7 = 128
		err = False
		testCIF = readXTAL('test/PigeoniteJZT.cif').read()
		print (testCIF)
		if err: testing.addErr()

	if testing.doit('check reading NiTi_Cubic.cif'):	#  2**8 = 256
		err = False
		testCIF = readXTAL('test/NiTi_Cubic.cif').read()
		print (testCIF)
		if err: testing.addErr()

	if testing.doit('check reading V2O3_Mono_95762.cif'):		#  2**9 = 512
		err = False
		testCIF = readXTAL('test/V2O3_Mono_95762.cif').read()
		print (testCIF)
		if err: testing.addErr()

	if testing.doit('check reading V2O3_Mono_onlySymOps.cif'):	#  2**10 = 1024
		testCIF = readXTAL('test/V2O3_Mono_onlySymOps.cif').read()
		err = '15:b3' != testCIF['SpaceGroupID']
		if err:
			print (testCIF)
			testing.addErr()

	if testing.doit('check reading Chakraborty.cif'):	#  2**11 = 2048
		testCIF = readXTAL('test/Chakraborty.cif').read()
		err = '176' != testCIF['SpaceGroupID']
		if err:
			print (testCIF)
			testing.addErr()

	if testing.doit('check reading unknown file'):		#  2**12 = 4096
		try:
			YBCOfile = readXTAL('unknown_file.xtal').read()
			testing.addErr()
			raise
		except:	print ('readXTAL("unknown_file.xtal").read()  is supposed to fail')

	if testing.doit('check reading V2O3.xtal'):			#  2**13 = 8192
		err = False
		try:
			V2O3File = readXTAL('test/V2O3.xml').read()
			print (V2O3File)
		except:	print ('failed to read: ,"test/V2O3.xml"')
		if err: testing.addErr()

	if testing.doit('check reading V2O3 Monoclinic.xtal'):	#  2**14 = 16384
		err = False
		try:
			V2O3File = readXTAL('test/V2O3 Monoclinic.xml').read()
			print (V2O3File)
		except:	print ('failed to read: ,"test/V2O3 Monoclinic.xml"')
		if err: testing.addErr()

	if testing.doit('check reading a 2D xml file'):		#  2**15 = 32768
		err = False
		try:
			file2D = readXTAL('test/2D.xml').read()
			print (file2D)
		except:	print ('failed to read: ,"test/2D.xml"')
		if err: testing.addErr()

	if testing.doit('check reading a new (version 2) xml file'):	#  2**16 = 65536
		err = False
		try:
			SiFile2 = readXTAL('test/Si_NEW.xml').read()
			print (SiFile2)
			print (SiFile2['alphaT'])
			print (str(SiFile2['bonds'][0]),'        ', SiFile2['bonds'])
		except:	print ('failed to read: ,"test/Si_NEW.xml"')
		if err: testing.addErr()

	if testing.doit('check reading a new (version 2) xml file'):	#  2**17 = 131072
		err = False
		try:
			Nbeta = readXTAL('materials/Nitrogen_beta.xtal').read()
			print (Nbeta)
			print (str(Nbeta['bonds'][0]),'        ', Nbeta['bonds'])
		except:	print ('failed to read: ,"test/Nitrogen_beta.xml"')
		if err: testing.addErr()

	if testing.doit('check reading a new (version 2) xml file'):	#  2**18 = 262144
		NdP5O14 = readXTAL('/Users/tischler/Documents/materials/NdP5O14.xtal').read()
		print (str(NdP5O14))


	testing.ending()
