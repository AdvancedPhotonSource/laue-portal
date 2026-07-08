#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# LatticeBase.py
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




import sys
from fnmatch import fnmatch
import numpy as np
import math
import string
import inspect
import JZTLaueSim.atomGeneral as atomGeneral

basestring = str

NaN = float('nan')
Zmax = 109							# maximum atomic number

MIN_FRACTIONAL_DIST = 1e-3			# atoms that differ by this fractional distance are considered the same position
DebyeT_TOL = 0.01					# tolerance on Debye Temperature (if two DebyeT are this close then they are the same)
B_TOL = 0.01						# tolerance on Biso (if two Biso are this close then they are the same)
U_TOL = 0.001						# tolerance on Uij & Uiso (if two U's are this close then they are the same)
AMU_TOL = 1e-5						# tolerance on amu (if two amu's are this close then they are the same)
OCC_TOL = 1e-5						# tolerance on occupation (if two occupations are this close then they are the same)
BOND_LEN_TOL = 0.0003				# tolerance on bond lengths (nm) (if two bond lengths are this close then they are the same)

amu_eV = 931.4940954e6				# energy of one amu (eV),  these 4 numbers only used by Debye-Waller calculation
hbar = 6.582119514e-16				# h/2PI (eV-sec)
c_ms = 299792458					# speed of light (m/sec)
kB = 8.6173303e-5					# Boltzmann constant (eV/K)



class atomXtal(atomGeneral.CromerAtom):
	""" A Class that contains the information about the atom in a crystal.
		If you give it one atom position (x,y,z) and the symmetry operations (symOps),
		then it will also calculate and store all of the symmetry equivalent atom 
		positions for this crystal.
		It will also hold the thermal parameters for the atom, and can return atomic structure factor given a Q
	"""
	# note, atomGeneral.CromerAtom is only neede to provide f0, if you do not include it, the fatom method will still work

	def __init__(self, label, xyz, Zatom=-1, valence=None, occ=1.0, WyckoffSymbol='', symOps=None, mult=1, Biso=NaN,Uiso=NaN,Uij=None, DebyeT=NaN, dim=None):
		"""
		Initialize the atomXtal instance.
		xyz is a SINGLE atom xyz, not a set. xyz=[x,y,z]		for 2d, only [x,y]
		"""
		try:	Zatom = int(Zatom)
		except:	Zatom = -1
		if not(Zatom>=1 and Zatom<=Zmax): Zatom = label	# try to get Zatom from label
		atomGeneral.CromerAtom.__init__(self, Zatom, valence=valence)

		self.label = str(label)			# label for this atom, usually starts with atomic symbol
		self.occ = float(occ)			# occupancy of this atom

		try:	dim = int(dim)
		except:	dim = None

		if not (dim in [2,3]):			# valid dim was not passed, try to figure it out
			try:	dim = len(xyz)		# set dim, to either 2 or 3
			except:	dim = None
		if not (dim in [2,3]):			# valid dim was not passed, try to figure it out
			try:	dim = self.findDimension(symOps)	# set dim, to either 2 or 3
			except:	dim = None
		if not (dim in [2,3]): dim = 3	# give up, use the default
		self.dim = dim

		x = xyz[0] - math.floor(float(xyz[0]))	# reduce to first cell, range [0,1)
		self.x = 0 if (x<1e-12) else (x % 1)	# if fractional coord < 1e-12 is 0, and translate into [0,1)
		y = xyz[1] - math.floor(float(xyz[1]))
		self.y = 0 if (y<1e-12) else (y % 1)
		if dim>2:
			z = xyz[2] - math.floor(float(xyz[2]))
			self.z = 0 if (z<1e-12) else (z % 1)

		try:	self.mult = int(mult)	# (number of symOps) = (multiplicity) + (site symmetry)
		except:	self.mult = 1
		self.mult = max(1,self.mult)	# got to have at least 1
		self.xyz = None					# only used with the lattice

		if type(WyckoffSymbol) is str: WyckoffSymbol = str(WyckoffSymbol)
		self.WyckoffSymbol = WyckoffSymbol	# a single letter, e.g. 'a', also called the Wyckoff letter
		self.siteSymmetry = None			# to be set later (if at all)

		self.DebyeT = float(DebyeT)		# Debye Temperature (K),  for DebyeT, B, Uiso, & U_ij, use only one method
		self.Biso = float(Biso)			# B-factor (nm^2) using:   exp(-M) = exp(-B * sin^2(theta)/lam^2)		B = 8 * PI^2 * <u^2> =  8 * PI^2 * Uiso,	exp[-B*q^2 / (16 PI^2) ]
		self.Uiso = float(Uiso)			# isotropic U (nm^2)

		try:	self.U11 = float(Uij[0])# anisotropic U(11) (nm^2)
		except: self.U11 = NaN
		try:	self.U22 = float(Uij[1])# anisotropic U(22) (nm^2)
		except: self.U22 = NaN
		if self.dim == 2:
			try:	self.U12 = float(Uij[2])# anisotropic U(12) (nm^2)
			except: self.U12 = NaN
		else:
			try:	self.U33 = float(Uij[2])# anisotropic U(33) (nm^2)
			except: self.U33 = NaN
			try:	self.U12 = float(Uij[3])# anisotropic U(12) (nm^2)
			except: self.U12 = NaN
			try:	self.U13 = float(Uij[4])# anisotropic U(13) (nm^2)
			except: self.U13 = NaN
			try:	self.U23 = float(Uij[5])# anisotropic U(23) (nm^2)
			except: self.U23 = NaN

		# if one of the Uij is NOT nan, then set others to 0
		if self.dim == 2:
			if (not math.isnan(self.U11)) or (not math.isnan(self.U22)):	# one of U11, U22 is valid number
				if math.isnan(self.U11): self.U11 = 0
				if math.isnan(self.U22): self.U22 = 0
		else:
			if (not math.isnan(self.U11)) or (not math.isnan(self.U22)) or (not math.isnan(self.U33)):
				if math.isnan(self.U11): self.U11 = 0
				if math.isnan(self.U22): self.U22 = 0
				if math.isnan(self.U33): self.U33 = 0
			if (not math.isnan(self.U12)) or (not math.isnan(self.U13)) or (not math.isnan(self.U23)):
				if math.isnan(self.U12): self.U12 = 0
				if math.isnan(self.U13): self.U13 = 0
				if math.isnan(self.U23): self.U23 = 0

		self.SetHasThermalInfo()		# True if atom has DebyeT, Biso, Uiso, or Uij
		if self.bad(): raise ValueError('atom values are INVALID')

		if not(symOps is None):			# calculate all atom positions from symOps, this can be done later
			if  self.dim == 2:	self.calcAllAtomPositions2D(symOps)
			else:				self.calcAllAtomPositions3D(symOps)
		return None


	def findDimension(self, symOps):
		""" returns  dim number """
		dim = None

		if not dim:
			try:
				ccc = inspect.currentframe().f_back.f_locals['LatticeBase3D']
				dim = 3
			except: pass

		if not dim:
			try:
				ccc = inspect.currentframe().f_back.f_locals['LatticeBase2D']
				dim = 2
			except: pass

		if not dim:
			try:
				second = symOps.shape[1]	# look at dimensionality of symOps
				dim = int(second)
			except:
				pass

		if not dim:
			try:
				if math.isnan(self.z): dim = 3	# just check if z is nan
			except:	pass

		if not dim: raise ValueError('Cannot set the dimension')
		return dim


	def __str__(self):
		""" Return string value for atomXtal. """
		return str(self).encode('ascii', errors='backslashreplace')

	def __str__(self):
		""" Return str value for atomXtal. """
		if self.valence==0:	vstr = ''
		else:				vstr = ', v=%+d' % self.valence

		if self.xyz:		xyzStr = ''
		elif self.dim==2:	xyzStr = '\t{%g,  %g}\t' % (self.x,self.y)
		else:				xyzStr = '\t{%g,  %g,  %g}\t' % (self.x,self.y,self.z)

		if self.siteSymmetry:
			out = u"%s (Z=%g%s)\t%s (%s)%s" % (self.label,self.Z,vstr,self.WyckoffSymbol,self.siteSymmetry,xyzStr)
		elif len(self.WyckoffSymbol):
			out = u"%s (Z=%g%s)\t%s%s" % (self.label,self.Z,vstr,self.WyckoffSymbol,xyzStr)
		else:
			out = u"%s (Z=%g%s)%s" % (self.label,self.Z,vstr,xyzStr)

		if self.occ != 1:	out += "\tocc = %.12g" % self.occ
		if self.mult > 1:	out += "\tmultiplicity = %d" % self.mult

		# Thermal vibration information, print at most one kind of info
		Angstrom2 = u'\u00C5\u00B2'
		if self.DebyeT > 0:	out += "\tDebye Temperature = %g K" % self.DebyeT
		elif self.Biso > 0:	out += u"\tIsotropic B = %g (%s)" % (self.Biso * 100, Angstrom2)
		elif self.Uiso > 0:	out += u"\tIsotropic U = %g (%s)" % (self.Uiso * 100, Angstrom2)
		if not math.isnan(self.U11):
			out += "\tAnisotropic U:, U11=%+g, U22=%+g" % ((self.U11 *100),(self.U22 *100))
			if self.dim>2: out += ", U33=%+g" % ((self.U33 *100),)
			if not ( math.isnan(self.U12) ):
				out += ",  U12=%+g" % ((self.U12 *100),)
				if self.dim>2: out += ", U13=%+g, U23=%+g" % ((self.U13 *100),(self.U23 *100))
			out += u' ('+Angstrom2+')'

		if self.xyz:
			i = 0
			for xyz in self.xyz:
				if self.dim == 2:	out += '\n\t%d\t{%g,  %g}' % (i+1,xyz[0],xyz[1])
				else:				out += '\n\t%d\t{%g,  %g,  %g}' % (i+1,xyz[0],xyz[1],xyz[2])
				i += 1

		return out


	def __repr__(self):
		""" Return representation value for atomXtal. """
		if self.dim == 2:
			out = 'atomXtal[%r, %r, Z=%r, valence=%r, xy=(%r, %r)' % (self.label,self.sym,self.Z,self.valence,self.x,self.y)
		else:
			out = 'atomXtal[%r, %r, Z=%r, valence=%r, xyz=(%r, %r, %r)' % (self.label,self.sym,self.Z,self.valence,self.x,self.y,self.z)
		if len(self.WyckoffSymbol): out += ', Wyckoff=%r' % self.WyckoffSymbol
		if self.siteSymmetry: out += ', siteSymmetry=%r' % self.siteSymmetry
		if not (self.occ == 1): out += ', occ=%r' % self.occ
		if not (self.mult == 1): out += ', mult=%r' % self.mult

		# Thermal vibration information, print at most one kind of info
		if self.DebyeT > 0:	out += ', DebyeT=%r' % self.DebyeT
		elif self.Biso > 0:	out += ', Biso= %r' % self.Biso
		elif self.Uiso > 0:	out += ', Uiso= %r' % self.Uiso

		if not math.isnan(self.U11):
			out += ', U11=%g, U22=%r' % (self.U11,self.U22)
			if self.dim > 2: out += ', U33=%r' % (self.U33,)
			if not math.isnan(self.U12):
				out += ', U12=%r' % (self.U12,)
				if self.dim == 2: out += ', U13=%r, U23=%r' % (self.U13,self.U23)
		out += ']'
		if self.xyz:
			i = 0
			for xyz in self.xyz:
				if self.dim == 2:	out += '\n\t%d\t{%.13g,  %.13g}' % (i+1,xyz[0],xyz[1])
				else:				out += '\n\t%d\t{%.13g,  %.13g,  %.13g}' % (i+1,xyz[0],xyz[1],xyz[2])
				i += 1
		return out


	def bad(self):
		if len(self.label)<1: return True
		if not (self.x >= 0 and self.y >= 0): return True
		if (self.dim != 2) and (not (self.z >= 0)): return True
		if not (self.occ > 0 and self.occ <= 1): return True
		if not (type(self.Z) is int or type(self.Z) is long): return True
		if not (self.Z >=1 and self.Z <= Zmax): return True
		if not isinstance(self.WyckoffSymbol,basestring): return True
		if len(self.WyckoffSymbol)>1: return True

		if self.DebyeT < 0: return True			# no negatives in isotropic values, but NaN is OK
		if self.Biso < 0: return True
		if self.Uiso < 0: return True
		# anisotropic U's can be negative

		# I am allowing multiple ways of defining the thermal parameters
		#	usingT = 0
		#	if self.DebyeT > 0: usingT += 1
		#	if self.Biso > 0: usingT += 1
		#	if self.Uiso > 0: usingT += 1
		#	if (self.U11 > 0 or self.U22 > 0 or self.U33 > 0): usingT += 1
		#	if usingT>1: return True			# too many thermal vibration methods

		if self.dim == 2:
			if not ( math.isnan(self.U11) and math.isnan(self.U22) ):
				# at least one Uii is valid, then all must be
				if math.isnan(self.U11) or math.isnan(self.U22): return True
		else:
			if not ( math.isnan(self.U11) and math.isnan(self.U22) and math.isnan(self.U33) ):
				# at least one Uii is valid, then all must be
				if math.isnan(self.U11) or math.isnan(self.U22) or math.isnan(self.U33): return True
				if not ( math.isnan(self.U12) and math.isnan(self.U13) and math.isnan(self.U23) ):
					# at least one Uij is valid, then all must be
					if math.isnan(self.U12) or math.isnan(self.U13) or math.isnan(self.U23): return True

		return False							# all OK


	def ZfromLabel(self, label):
		""" Try to find the atomic number from a label """
		if len(label)<1: return -1
		symb = label[0].upper()
		if len(label) > 1:
			if label[1] in string.ascii_letters:
				symb += label[1].lower()
	
		try:	Zatom = atomGeneral.baseAtom.symbols.index(symb)
		except:	Zatom = -1
		return Zatom


	def SetHasThermalInfo(self):
		""" sets the kind of thermal/vibrational info present in this atom """
		if self.dim == 2:	Usum = abs(self.U11) + abs(self.U22)
		else:				Usum = abs(self.U11) + abs(self.U22) + abs(self.U33)
		Tinfo = Vinfo = False
		if self.DebyeT > 0: Tinfo = True
		elif self.Biso > 0: Vinfo = True
		elif self.Uiso > 0: Vinfo = True
		elif (not math.isnan(Usum)) and Usum>0: Vinfo = True
		self.hasThermalInfo = Vinfo or Tinfo	# True if atom has DebyeT, Biso, Uiso, or Uij
		self.Tinfo = Tinfo
		self.Vinfo = Vinfo


	def DW_factor_M(self,T,thetaM,Q):
		""" calculates the M in exp(-M), no I/O
		This is the x-ray Debye-Waller factor, that's what the '_M' means.
		T			# Temperature (K)
		thetaM		# Debye Temperature (K)
		Q			# length of q vector (1/nm)
		amu			# mass of atom (amu)
		"""
		if T<0 or thetaM<0 or Q<0 or self.amu<0: return float('nan')
		elif T<=0:	return 0.0
		xx = float(thetaM) / float(T)
		if xx>50000.0: return 0.0
		Phi = simpsonIntegral(self.PhiIntegrand,0,xx).calc() / xx
		B = (3*hbar*hbar * T * c_ms*c_ms)/(2*(self.amu*amu_eV)*kB*thetaM*thetaM)* (Phi + xx/4)
		M = B *(Q*Q*1.e18)						# Q is in 1/nm, but we need it in 1/m
		return M

	def PhiIntegrand(self,xx):
		""" this is the function we need to integrate from DW_factor_M()
		this function should never be called with xx<0
		"""
		if xx>0:	return xx / ( math.exp(xx) - 1 )
		else:		return 1.0


	def calcAllAtomPositions3D(self,symOps):
		""" calculate all the atom positions from the symOps
		symOps are the symmetry operations for this atom, supplied by calling function
		symOps are a set of equivX1, each equivX1 is a 3x4 matrix
		results are stored in self.xyz
		self.mult is also set here
		"""
		self.xyz = list()					# init to empty list
		xyz1 = np.matrix([self.x, self.y, self.z, 1.0])
		for symOp in symOps:
			symOp = np.matrix(symOp)
			xyzTest = symOp * xyz1.T
			x = float(xyzTest[0])			# the "float()" is REQUIRED to get rid of numpy stuff
			y = float(xyzTest[1])
			z = float(xyzTest[2])
			x = x - math.floor(x)			# reduce to first cell, range [0,1)
			y = y - math.floor(y)
			z = z - math.floor(z)
			x = 0 if (x<1e-12) else (x % 1)	# if fractional coord < 1e-12 is 0, and translate into [0,1)
			y = 0 if (y<1e-12) else (y % 1)
			z = 0 if (z<1e-12) else (z % 1)
			dup = False
			for xyzHave in self.xyz:		# check for duplicates
				if (self.fracDist(xyzHave[0],x)+self.fracDist(xyzHave[1],y)+self.fracDist(xyzHave[2],z))<MIN_FRACTIONAL_DIST:
					dup = True
					break

			if not dup:						# not a duplicate, so add to the list of positions
				self.xyz.append((x,y,z))

		self.mult = len(self.xyz)


	def calcAllAtomPositions2D(self,symOps):
		""" calculate all the atom positions from the symOps
		symOps are the symmetry operations for this atom, supplied by calling function
		symOps are a set of equivX1
		results are stored in self.xyz
		self.mult is also set here
		"""
		self.xyz = list()					# init to empty list, note it really only 2 values x & y
		xy1 = np.matrix([self.x, self.y, 1.0])
		for symOp in symOps:
			symOp = np.matrix(symOp)
			xyTest = symOp * xy1.T
			"""
			x = float(xyTest[0]) % 1.		# translate back in to unit cell, so value in [0,1)
			y = float(xyTest[1]) % 1.
			x = 0 if abs(x)<1e-12 else x	# fractional coords < 1e-12 are just 0
			y = 0 if abs(y)<1e-12 else y
			"""
			x = float(xyTest[0])			# the "float()" is REQUIRED to get rid of numpy stuff
			y = float(xyTest[1])
			x = x - math.floor(x)			# reduce to first cell, range [0,1)
			y = y - math.floor(y)
			x = 0 if (x<1e-12) else (x % 1)	# if fractional coord < 1e-12 is 0, and translate into [0,1)
			y = 0 if (y<1e-12) else (y % 1)
			dup = False
			for xyHave in self.xyz:			# check for duplicates
				if (self.fracDist(xyHave[0],x)+self.fracDist(xyHave[1],y))<MIN_FRACTIONAL_DIST:
					dup = True
					break

			if not dup:						# not a duplicate, so add to the list of positions
				self.xyz.append((x,y))

		self.mult = len(self.xyz)


	def fracDist(self,a,b):					# fractional distance between a-b, e.g. (0.01, 0.99) --> 0.02
		return min((a-b)%1, (b-a)%1)


	def fatom(self,Q,keV):
		""" This Cromer & Liberman values
		Q		|Q| (1/nm)
		keV		energy (keV)
		Note, if CromerAtom.f0 has NOT been imported, then this method still works.
		"""
		try:
			zf = atomGeneral.CromerAtom.fatom(self, Q, keV=keV)
			if type(zf) is float:
				zf = complex(zf,0)			# only f0 was computed
			elif type(zf) is complex:
				pass						# f0 + f' + f'' was computed
			else:
				zf = complex(NaN,NaN)		# this should never happen
		except:
			zf = complex(float(max(self.Z - self.valence,0)), 0)
		return zf


	def __eq__(self, other):
		"""
		returns True if the atoms self.* and other.* are equal, otherwise False
		"""
		if not atomGeneral.baseAtom.__eq__(self, other): return False
		other._neqStr = self._neqStr = ''

		fractErrStr = ''							# not a difference if the atom (xyz) all match

		if self.dim != 2:
			if ( abs(self.z - other.z) ) > MIN_FRACTIONAL_DIST: fractErrStr = '"z" fractional coords differ on '+str(self.label)
		if ( abs(self.y - other.y) ) > MIN_FRACTIONAL_DIST: fractErrStr = '"y" fractional coords differ on '+str(self.label)
		if ( abs(self.x - other.x) ) > MIN_FRACTIONAL_DIST: fractErrStr = '"x" fractional coordsdiffer on '+str(self.label)

		if abs(self.occ - other.occ) > OCC_TOL:
			other._neqStr = self._neqStr = 'occupations differ on '+str(self.label)
			return False

		if self.mult != other.mult:
			other._neqStr = self._neqStr = 'multiplicity differs on '+str(self.label)
			return False

		if self.label != other.label:
			other._neqStr = self._neqStr = 'labels on atoms differ, %r and %r' %(self.label, other.label)
			return False
		if self.WyckoffSymbol != other.WyckoffSymbol: 
			other._neqStr = self._neqStr = 'WyckoffSymbols differ on '+str(self.label)
			return False

		if optionalNumbersDiffer(self.DebyeT,other.DebyeT,DebyeT_TOL):
			other._neqStr = self._neqStr = 'Debye Temperatures differ on '+str(self.label)
			return False
		elif optionalNumbersDiffer(self.Biso,other.Biso,B_TOL):
			other._neqStr = self._neqStr = 'Biso differs on '+str(self.label)
			return False
		elif optionalNumbersDiffer(self.Uiso,other.Uiso,U_TOL):
			other._neqStr = self._neqStr = 'Uiso differs on '+str(self.label)
			return False
		elif optionalNumbersDiffer(self.U11,other.U11,U_TOL):
			other._neqStr = self._neqStr = 'U11 differs on '+str(self.label)
			return False
		elif optionalNumbersDiffer(self.U22,other.U22,U_TOL):
			other._neqStr = self._neqStr = 'U22 differs on '+str(self.label)
			return False
		elif optionalNumbersDiffer(self.U12,other.U12,U_TOL):
			other._neqStr = self._neqStr = 'U12 differs on '+str(self.label)
			return False
		elif self.dim > 2:
			if optionalNumbersDiffer(self.U33,other.U33,U_TOL):
				other._neqStr = self._neqStr = 'U33 differs on '+str(self.label)
				return False
			elif optionalNumbersDiffer(self.U13,other.U13,U_TOL):
				other._neqStr = self._neqStr = 'U13 differs on '+str(self.label)
				return False
			elif optionalNumbersDiffer(self.U23,other.U23,U_TOL):
				other._neqStr = self._neqStr = 'U23 differs on '+str(self.label)

		N = len(self.xyz)
		if N<1:
			other._neqStr = self._neqStr = fractErrStr	# no fractional coordinates, just use fractErrStr
			return False
		elif N != len(other.xyz):
			other._neqStr = self._neqStr = 'different number of atoms %r and %r' % (N,len(other.xyz))
			return False

		for xyz1 in self.xyz:							# check if all of the atomic positions match, they might be out of order
			foundMatch = False

			if self.dim == 2:
				for xy2 in other.xyz:					# compare each xy2 from other.xyz with this xyz1
					if max(abs(xyz1[0]-xy2[0]), abs(xyz1[1]-xy2[1])) < MIN_FRACTIONAL_DIST: foundMatch = True
			else:
				for xyz2 in other.xyz:					# compare each xyz2 from other.xyz with this xyz1
					if max(abs(xyz1[0]-xyz2[0]), abs(xyz1[1]-xyz2[1]), abs(xyz1[2]-xyz2[2])) < MIN_FRACTIONAL_DIST: foundMatch = True

			if not foundMatch:
				other._neqStr = self._neqStr = 'no match for some of the fractional atom position %r' % (xyz1,)

		return True


	def atomListsDiffer(self, a1in, a2in):
		"""
		a1in & a2in are either individual atoms or lists of atoms
		the atom order is irrelevant
		return a string if they differ
		return an empty string if they are the same.
		"""
		if a1in is None: return 'The first atom list is empty'
		if a2in is None: return 'The second atom list is empty'

		# ensure that a1List & a2list are lists, and not just single atoms
		try:
			iter(a1in)				# OK if a1in is iterable, i.e. list or tuple
			a1list = a1in
		except TypeError as te:
			a1list = [a1in]			# ensure that a1list is interable

		try:
			iter(a2in)				# OK if a2in is iterable, i.e. list or tuple
			a2list = a2in
		except TypeError as te:
			a2list = [a2in]			# ensure that a2list is interable

		if len(a1list) != len(a2list): return 'atom list mismatch, they have a different number of atoms: %r and %r' % (len(a1list),len(a2list))

		for a1 in a1list:
			foundMatch = False
			for a2 in a2list:
				if a1 == a2:
					foundMatch = True				# found a match, stop looking
					break
			if not foundMatch: return a1._neqStr	# no matching atom found
	
		return ''					# no difference



class bondType(object):
	""" A Class that the definition of a bond in a crystal.
		It store the label of the atoms at each end, and the bond length.
		The bond length (lengths) can be a tuple if more than one length is possible.
	"""

	def __init__(self, label0,label1,lengths, btype=1):
		"""
		Initialize the bondType instance.
		this bond goes between atoms label0 and label1 with a length of lengths

		label0			label for first atom, usually starts with atomic symbol, e.g. Si001
		label1			label for second atom, usually starts with atomic symbol
		lengths			tuple with bond lengths (nm) e.g. (1,) or 0.2 or (1.0, 1.5)
		btype			optional bond type (e.g. 1 for single bonds, 2 for double bonds ...)
		"""
		if not isinstance(label0,basestring):
			raise ValueError('bond label0 is not a string')
		if not isinstance(label1,basestring):
			raise ValueError('bond label1 is not a string')
		if len(label0) < 1:
			raise ValueError('bond label0 is an empty string')
		if len(label1) < 1:
			raise ValueError('bond label1 is an empty string')
		self.label0 = label0			# label for first atom, usually starts with atomic symbol
		self.label1 = label1			# label for second atom, usually starts with atomic symbol
		self._neqStr = None

		if type(lengths) is int or type(lengths) is float:
			lengths = (float(lengths),)	# a single number was entered, make it a tuple of floats
		self.lengths = tuple()			# length of bond (possibly multiple values) (nm)
		for l in lengths:
			if type(l) is float: self.lengths += (l,)
			else: raise ValueError('bond length is not a float')

		if len(self.lengths) < 1:
			raise ValueError('there is no bond lengths')

		try:
			self.btype = int(btype)		# bond type is a positive int > 0
		except:
			raise ValueError('bond type is not a positive integer, btype = %r' % btype)
		if self.btype<1: raise ValueError('bond multiplicity is not a positive integer, btype = %r' % btype)


	def __str__(self):
		""" Return string value for bondType. """
		return str(self).encode('ascii', errors='backslashreplace')

	def __str__(self):
		""" Return str value for bondType. """
		lenStr = ''
		for l in self.lengths:
			if len(lenStr): lenStr += ', '
			lenStr += "%.4g" % l

		sbnd = '<-->'
		try:
			if self.btype > 1: sbnd = '<==>'
		except:	pass

		try:
			sbtype = ['single','double','triple','quadruple','quintuple'][self.btype - 1]
		except:
			sbtype = '%r-tuple' % self.btype
		return u'     [%s] %s [%s]:  %s nm,  %s bond' % (self.label0,sbnd,self.label1,lenStr,sbtype)


	def __repr__(self):
		""" Return printable representation for bondType. """
		return 'bondType[%s, %s, %r, %d]' % (self.label0,self.label1,self.lengths,self.btype)


	def __eq__(self, other):
		"""
		if self.* & other.* are two individual bonds, return False if they differ, also set self.neqStr
		"""
		if not( type(other) is type(self) ): return NotImplemented	# can only compare objects of the same type

		other._neqStr = self._neqStr = ''
		if self.label0 != other.label0 and self.label0 != other.label1:
			other._neqStr = self._neqStr = 'label0 differs on bond'
			return False
		if self.label1 != other.label1 and self.label1 != other.label0:
			other._neqStr = self._neqStr = 'label1 differs on bond'
			return False
		if self.btype != other.btype:
			other._neqStr = self._neqStr = 'bond types differs on bond, %r <--> %r' % (self.label0,self.label1)
			return False

		n = max(len(self.lengths),len(other.lengths))
		for i in range(n):
			try:
				if abs(self.lengths[i] - other.lengths[i])>BOND_LEN_TOL: raise
			except:
				self._neqStr = 'bond lengths differs on bond %r <--> %r' % (self.label0,self.label1)
				break

		other._neqStr = self._neqStr
		return (len(self._neqStr) < 1)

	def __ne__(self, other):
		if type(other) is type(self):
			return not self.__eq__(other)
		return NotImplemented


	def bondListsDiffer(self, b1in, b2in):
		"""
		b1in & b2in are either individual bonds or lists of bonds
		the bond order is irrelevant
		return a string if they differ
		return an empty string if they are the same.
		"""
		if b1in is None: return 'The first bond list is empty'
		if b2in is None: return 'The second bond list is empty'

		# ensure that b1List & b2list are lists, and not just single bonds
		try:
			iter(b1in)				# OK if b1in is iterable, i.e. list or tuple
			b1list = b1in
		except TypeError as te:
			b1list = [b1in]			# ensure that b1list is interable

		try:
			iter(b2in)				# OK if b2in is iterable, i.e. list or tuple
			b2list = b2in
		except TypeError as te:
			b2list = [b2in]			# ensure that b1list is interable

		if len(b1list) != len(b2list): return 'Bond list mismatch, they have a different number of bonds: %r and %r' % (len(b1list),len(b2list))

		for b1 in b1list:
			foundMatch = False
			for b2 in b2list:
				if b1 == b2:
					foundMatch = True				# found a match, stop looking
					break
			if not foundMatch: return b1._neqStr	# no matching bond found
	
		return ''					# no difference



class simpsonIntegral(object):
	""" calculate a definite integral using adaptive Simpson's rule, only used in DW_factor_M() """

	def __init__(self, f, lo,hi, eps=1e-10, maxIter=2000):
		"""
		Initialize the simpsonIntegral instance.
		f		function to integrate, must be able to just call f(x)
		lo,hi	range to integrate, must have lo <= hi
		eps		tolerance, adjusts convergence
		maxIter	maximum allowed number of iterations

		Example:
			print simpsonIntegral(math.sin,0,math.pi/2).calc()
			# this should return 1
		"""
		self.iter = 0
		try:
			self.lo = float(lo)
			self.hi = float(hi)
			self.eps = float(eps)
			self.maxIter = int(maxIter)
		except:
			raise ValueError('simpsonIntegral(), check values of lo=%r, hi=%r, eps=%r,  maxIter=%r' % (lo,hi,eps,maxIter))

		try:
			vLo = f(self.lo)					# test that f is a function that we can call
			valHi = f(self.hi)
		except:	raise ValueError('simpsonIntegral(), f = "%r" does not appear to be function' % f)
		self.f = f
		self.area = None

		if self.maxIter<=1 or self.eps <=0 or self.hi<self.lo:
			raise ValueError('simpsonIntegral(), check values of lo=%r, hi=%r, eps=%r,  maxIter=%r' % (lo,hi,eps,maxIter))

	def __str__(self):
		""" Return string value for simpsonIntegral. """
		return str(self).encode('ascii', errors='backslashreplace')

	def __str__(self):
		""" Return str value for simpsonIntegral. """
		if self.area is None:
			return u'Integral{"%s" [%g, %g]}' % (self.f.__name__,self.lo,self.hi)
		else:
			return u'Integral{"%s" [%g, %g]} = %g' % (self.f.__name__,self.lo,self.hi,self.area)

	def __repr__(self):
		""" Return printable representation for simpsonIntegral. """
		out = 'simpsonIntegral[f=%r, lo=%r, hi=%r, eps=%g, maxIter=%r, area=%r]' % (self.f.__name__,self.lo,self.hi,self.eps,self.maxIter,self.area)
		return out

	def calc(self):
		"Calculate integral of f from a to b with max error of eps."
		if self.lo == self.hi: self.area = 0.0
		self.area = self.recursive_asr(self.lo,self.hi,self.eps,self.simpsons_rule(self.lo,self.hi))
		return self.area

	def simpsons_rule(self,a,b):
		c = (a+b) / 2.0
		h3 = abs(b-a) / 6.0
		return h3*(self.f(a) + 4.0*self.f(c) + self.f(b))

	def recursive_asr(self,a,b,eps,whole):
		"Recursive implementation of adaptive Simpson's rule."
		self.iter += 1
		c = (a+b) / 2.0
		left = self.simpsons_rule(a,c)
		right = self.simpsons_rule(c,b)
		if abs(left + right - whole) <= 15*eps:
			return left + right + (left + right - whole)/15.0
		elif self.iter > self.maxIter:
			return left + right + (left + right - whole)/15.0
		return self.recursive_asr(a,c,eps/2.0,left) + self.recursive_asr(c,b,eps/2.0,right)



class LatticeBase0(object):
	""" A Class that the defines has a lot of the things in Lattice, but without actually defining one.
		Used as a base for both 2D & 3D SpaceGroup Lattices
		Mostly utility things and lists of constants
		some useful utility type routines:
		getHMboth(SpaceGroupID)
		getHMsym(SpaceGroupID)
		getFullHMSym(SpaceGroupID)
		SymString2IDs(symFind,type)		# returns list of possible space groups
										# symFind, requested symbol, with possible '*'
										# type, 0=all, 1=Hermann-Mauguin, 2=Full Hermann-Mauguin, 4=Lattice System, 8=SpaceGroupID
	"""

	def __init__(self):
		self.latticeSystemNames = []
		self.MaxIDnum = 0
		self.allIDs = []
		self.RhomIDs = None

		self.HM1 = []					# short and log symmetry symbol
		self.HM2 = []
		self.Hall = []
		self.PointGroup = []
		self.LaueGroup = []
		self.Schoenflies = []
		self.SystemIDs = {}

		return None


	def SymString2IDs(self,symFind,type):
		""" finds space group of a Hermann-Mauguin or Hall symbol, wild '*' cards allowed
		symFind			requested symbol, if empty, then a dialog will come up
		type			-1=all, 1=Hermann-Mauguin, 2=Full Hermann-Mauguin, 4=Hall, 8=Lattice System, 16=SpaceGroupID, 32=ignore minus signs
		returns a list of Space Group numbers that match
		"""
		type = int(type)
		symFind = str(symFind)
		symFind = symFind.replace(' ','')	# do not include spaces in search
		symFind = symFind.lower()			# search is case insensitive
		noMinus = bool(type & 32)

		if noMinus:
			symFind = symFind.replace('-','')	# do not include minus signs

		tlist = list()
		if type & 1:						# Hermann-Mauguin symbols
			m = 0
			for sym in self.HM1:			# check all of the space goups types
				sym = sym.replace(' ','')	# do not include spaces in search
				sym = sym.lower()			# search is case insensitive
				if noMinus: sym = sym.replace('-','')
				if fnmatch(sym,symFind): tlist.append(self.allIDs[m])
				m += 1

		if type & 2:						# full Hermann-Mauguin symbols
			m = 0
			for sym in self.HM2:			# check all of the space goups types
				sym = sym.replace(' ','')	# do not include spaces in search
				sym = sym.lower()			# search is case insensitive
				if noMinus: sym = sym.replace('-','')
				if fnmatch(sym,symFind): tlist.append(self.allIDs[m])
				m += 1

		if type & 4:						# Hall symbols
			m = 0
			for sym in self.Hall:			# check all of the space goups types
				sym = sym.replace(' ','')	# do not include spaces in search
				sym = sym.lower()			# search is case insensitive
				if noMinus: sym = sym.replace('-','')
				if fnmatch(sym,symFind): tlist.append(self.allIDs[m])
				m += 1

		if type & 8:						# Lattice Systems
			idList = []
			for system in self.latticeSystemNames:
				if fnmatch(system.lower(), symFind):
					idList += self.SystemIDs[system]				# adds list of these IDnums, index-1 into allIDs[]
			for idNum in idList: tlist.append(self.allIDs[idNum-1])	# put actual ID's onto tlist

			if self.RhomIDs:										# 3D Space Groups with possible 'rhombohedral'
				if fnmatch('rhombohedral',symFind): tlist += self.RhomIDs

		if type & 16:						# Space Group ID's, e.g. "15:b3"
			for id in self.allIDs:			# check all of the space goups types
				id = id.replace(' ','')		# do not include spaces in search
				id = id.lower()				# search is case insensitive
				if fnmatch(id,symFind): tlist.append(id)

		tlist = list(set(tlist))			# remove possible duplicates
		return tlist


	def validSpaceGroupID(self, id):
		""" returns TRUE if id is valid space group id, e.g. '15' or '15:-b2' """
		try:
			idNum = self.allIDs.index(str(id)) + 1
			if idNum<1 or idNum>self.MaxIDnum: raise
		except:	raise ValueError('id = %r, is not a valid Space Group ID, it should be something like "15:-b2"' % (id,))
		return True


	def FindDefaultIDforSG(self, SG):
		"""Returns the default ID for SG (an int in range [1-MaxIDnum]). """
		try:	SG = SG.split(':')[0]	# if an id was passed
		except:	pass
		try:	SG = int(SG)			# actually want the SG number [1,self.MaxIDnum]
		except:	ValueError('Cannot find default id for Space Group = %r' % (SG,))

		# find first space group in allIDs starting with the number SG
		for id in self.allIDs:
			try:
				if (int(id.split(':')[0])) == SG: return id
			except:
				pass

		raise ValueError('Cannot find default id for Space Group = %r' % (SG,))


	def symOpsList(self, SpaceGroupID):
		"""
		returns a list of symmetry operations for SpaceGroupID
		returns something like:   ['x,y,z', '-x+1/4,-y+1/4,-z+1/4', '-y+1/4,x+1/4,z+1/4', '-x,-y,z', ...]
		"""
		equivX1 = self.GetSymmetryOperations(SpaceGroupID)
		opList = []
		for mat in equivX1:
			op = self.symOpRow2str(mat[0])
			op += ',' + self.symOpRow2str(mat[1])
			try:	op += ',' + self.symOpRow2str(mat[2])
			except:	pass
			opList.append(op)
		return opList


	def symOpRow2str(self, vec):
		try:
			c = vec[3]
			dim = 3
		except:
			dim = 2

		out = ''
		if vec[0] == 1.0:	out +='+x'
		elif vec[0] == -1.0:	out +='-x'
		elif vec[0] != 0.0:	raise ValueError('ERROR -- symOpRow2str() encountered a coefficient that is not {-1,0,+1} for x')

		if vec[1] == 1.0:	out +='+y'
		elif vec[1] == -1.0:	out +='-y'
		elif vec[1] != 0.0:	raise ValueError('ERROR -- symOpRow2str() encountered a coefficient that is not {-1,0,+1} for y')

		if dim>2:
			if vec[2] == 1.0:	out +='+z'
			elif vec[2] == -1.0:	out +='-z'
			elif vec[2] != 0.0:	raise ValueError('ERROR -- symOpRow2str() encountered a coefficient that is not {-1,0,+1} for z')

		if dim==2:	c = vec[2]
		else:		c = vec[3]	
		if c != 0.0:			# and the constant
			if c<0: sign = '-'
			else: sign = '+'
			c = abs(c)
			if   abs(2.0*c - 1.0) < 1e-4: sc = '1/2'
			elif abs(3.0*c - 1.0) < 1e-4: sc = '1/3'
			elif abs(3.0*c - 2.0) < 1e-4: sc = '2/3'
			elif abs(4.0*c - 1.0) < 1e-4: sc = '1/4'
			elif abs(4.0*c - 3.0) < 1e-4: sc = '3/4'
			elif abs(6.0*c - 1.0) < 1e-4: sc = '1/6'
			elif abs(6.0*c - 5.0) < 1e-4: sc = '5/6'
			out += sign + sc

		out = out.lstrip('+')			# no leading '+'
		if len(out)<1: out = '0'
		return out


	def getHMboth(self,id):
		""" returns short and (full) Hermann-Mauguin symbol """
		id = str(id)
		short = self.getHMsym(id)
		full = self.getFullHMSym(id)
		if short == full:	return short
		else:				return short + '  ('+full+')'


	def getHMsym(self,id):
		""" returns short Hermann-Mauguin symbol, there are self.MaxIDnum symbols in the list """
		id = str(id)
		try:	return self.HM1[ self.allIDs.index(id) ]
		except:	ValueError('id = %r is not a valid Space Group ID' % (id,))


	def getFullHMSym(self, id):
		""" returns full Hermann-Mauguin symbol, mostly the same as getHMsym """
		id = str(id)
		try:	return self.HM2[ self.allIDs.index(id) ]
		except:	ValueError('id = %r is not a valid Space Group ID' % (id,))


	def getHallSymbol(self, id):
		""" Hall Symbols, there are self.MaxIDnum items in this list """
		if len(self.Hall)<1: raise ValueError('There are no Hall Symbols')
		id = str(id)
		try:	return self.Hall[ self.allIDs.index(id) ]
		except:	ValueError('id = %r is not a valid Space Group ID' % (id,))


	def getPointGroupSymbol(self, id):
		""" Point Group Symbols, there are self.MaxIDnum items in this list """
		if len(self.PointGroup)<1: raise ValueError('There are no Point Group Symbols')
		id = str(id)
		try:	return self.PointGroup[ self.allIDs.index(id) ]
		except:	ValueError('id = %r is not a valid Space Group ID' % (id,))


	def getLaueGroupSymbol(self, id):
		""" Laue Group Symbols, there are self.MaxIDnum items in this list """
		if len(self.LaueGroup)<1: raise ValueError('There are no Laue Group Symbols')
		id = str(id)
		try:	return self.LaueGroup[ self.allIDs.index(id) ]
		except:	ValueError('id = %r is not a valid Space Group ID' % (id,))


	def getSchoenfliesSymbol(self, id):
		""" Schoenflies Symbols, there are self.MaxIDnum items in this list """
		if len(self.Schoenflies)<1: raise ValueError('There are no Schoenflies Symbols')
		id = str(id)
		try:	return self.Schoenflies[ self.allIDs.index(id) ]
		except:	ValueError('id = %r is not a valid Space Group ID' % (id,))


	def FindWyckoffSymbol1(self, id):
		"""	Over ride this, this is just a place holder.
			This returns a tuple:  (Wyckoff symbol, mult)
		"""
		raise ValueError('This should have been overridden.')


	def ForceFractionalToWyckoff(self, id,symbol):
		"""	Over ride this, this is just a place holder. """
		raise ValueError('This should have been overridden.')


	def MultiplicityFromWyckoff(self, id,symbol):
		""" returns multiplicity """
		WyckList = self.GetWyckoffSymList(id)
		for item in WyckList:
			if item[0] == symbol: return int(item[2])
		return 0


	def GetSiteSymmetry(self,id,symbol):
		"""	Over ride this, this is just a place holder. """
		WyckList = self.GetWyckoffSymList(id)
		if WyckList is None: return None
		for item in WyckList:
			if item[0] == symbol: return item[3]
		return None


	def GetWyckoffSymList(self, id):
		"""	Over ride this, this is just a place holder. """
		raise ValueError('This should have been overridden.')


	def GetSettingTransForm(self, id):
		"""	Over ride this, this is just a place holder.
			returns a 4x4 CBM matrix for converting the setting
		"""
		raise ValueError('Cannot Transform Setting in SpaceGroups, needs an implementation')


	def SetSymmetryOperations(self, SpaceGroupID):
		"""
		Sets the symmetry operations for a SpaceGroup as an array of numpy matricies
		SpaceGroupID is the ID, not just an integer e.g. "15:b3"
		This just calls GetSymmetryOperations(), but this SETS self.equivX1, GetSymmetryOperations() does not
		"""
		self.equivX1 = self.GetSymmetryOperations(SpaceGroupID)
		return self.equivX1


	def GetSymmetryOperations(self, SpaceGroupID):
		"""	Over ride this, this is just a place holder.
		Sets the symmetry operations for a SpaceGroup as an array of numpy matricies
		SpaceGroupID is the ID, not just an integer e.g. "15:b3"
		"""
		raise ValueError('ERROR -- LatticeBase2D or LatticeBase3D Should have overridden this')


class LatticeBase2D(LatticeBase0):
	""" A Class that the defines has a lot of the things in Lattice, but without actually defining one.
		Mostly utility things and lists of constants
		some useful utility type routines:
		getHMboth(SpaceGroupID)
		getHMsym(SpaceGroupID)
		getFullHMSym(SpaceGroupID)
		SymString2IDs(symFind,type)		# returns list of possible space groups
										# symFind, requested symbol, with possible '*'
										# type, 0=all, 1=Hermann-Mauguin, 2=Full Hermann-Mauguin, 4=Lattice System, 8=SpaceGroupID

		http://www.cryst.ehu.es/#planetop
		https://sites.google.com/a/uw.edu/diffraction-resources/symmetry-resources/2d-symmetry-groups
		http://www.cryst.ehu.es/plane/get_plane_wp.html

		 #1		p1		p1		Oblique
		 #2		p2		p2		Oblique
		 #3		pm		p1m1	Rectangular
		 #4		pg		p1g1	Rectangular
		 #5		cm		c1m1	Rhombic
		 #6		pmm		p2mm	Rectangular
		 #7		pmg		p2mg	Rectangular
		 #8		pgg		p2gg	Rectangular
		 #9		cmm		c2mm	Rhombic
		#10		p4		p4		Square
		#11		p4m		p4mm	Square
		#12		p4g		p4gm	Square
		#13		p3		p3		Hexagonal
		#14		p3m1	p3m1	Hexagonal
		#15		p31m	p31m	Hexagonal
		#16		p6		p6		Hexagonal
		#17		p6m		p6mm	Hexagonal
	"""

	def __init__(self):
		LatticeBase0.__init__(self)		# no parameters needed

		self.Oblique = 0
		self.Rectangular = 1
		self.Rhombic = 2
		self.Square = 3
		self.Hexagonal = 4
		self.latticeSystemNames = ['Oblique','Rectangular','Rhombic','Square','Hexagonal']
		self.MaxIDnum = 17

		self.allIDs = ['1','2','3','4','5','6','7','8','9','10','11','12','13','14','15','16','17']
		self.RhomIDs = None
		"""
		returns info about the symmetry of a structure
		sym holds the symmetry info on return, and xy holds the atom positions.  It returns the number of atom positions 
		put in xy which is always at least 1.  If you call with a bad wave ref for xy, then it only returns the sym string, 
		and the returned value is 0
		"""
		""" returns short and log symmetry symbol """
		self.HM1 = ['p1','p2','pm','pg','cm','pmm','pmg','pgg','cmm','p4','p4m','p4g','p3','p3m1','p31m','p6','p6m']
		self.HM2 = ['p1','p2','p1m1','p1g1','c1m1','p2mm','p2mg','p2gg','c2mm','p4','p4mm','p4gm','p3','p3m1','p31m','p6','p6mm']
		self.Schoenflies = ['C1','C2','D1','D1','D1','D2','D2','D2','D2','C4','D4','D4','C3','D3','D3','C6','D6']
		self.PointGroup = ['1','2','m','m','m','2mm','2mm','2mm','2mm','4','4mm','4mm','3','3mm','3mm','6','6mm'] # International Tables Table 1.5.4.3
		self.LaueGroup = ['2','2','2mm','2mm','2mm','2mm','2mm','2mm','2mm','4','4mm','4mm','6','6mm','6mm','6','6mm'] # https://it.iucr.org/Ac/ch2o1v0001/sec2o1o1.pdf
		self.Hall = []
		self.SystemIDs = {}
		self.SystemIDs['Oblique'] = [1,2]
		self.SystemIDs['Rectangular'] = [3,4,6,7,8]		# NOT 5
		self.SystemIDs['Rhombic'] = [5,9]
		self.SystemIDs['Square'] = [10,11,12]
		self.SystemIDs['Hexagonal'] = [13,14,15,16,17]

		return None


	def FindWyckoffSymbol1(self, id,x,y):
		"""
		NOTE, this does NOT test the symmetry equivalent positions of (x,y)
		This returns a tuple:  (Wyckoff_symbol, mult, siteSymmetry)
		"""
		WyckList = self.GetWyckoffSymList(id)
		xy = (x,y)
		for item in WyckList:
			OK = True
			for op,val in zip(item[1],xy):
				op = op.replace('x',str(float(x)))
				op = op.replace('y',str(float(y)))
				try:	OK = OK and (abs(val-eval(op)) < MIN_FRACTIONAL_DIST)
				except:	OK = False

			if OK: return (item[0],item[2],item[3])	# returns (Wyckoff_Symbol, mult, siteSymmetry)
		raise ValueError('Cannot find wyckoff symbol corresponding to xy={%r, %r} for Space Group %r' % (x,y,id))


	def ForceFractionalToWyckoff(self, id,symbol,x0,y0):
		WyckList = self.GetWyckoffSymList(id)
		for item in WyckList:
			if item[0] == symbol: break
		if not(item[0] == symbol): raise ValueError('Did not find Wyckoff symbol %r in SG = %r' % (symbol,id))

		out = tuple()
		for op in item[1]:
			op = op.replace('x',str(float(x0)))
			op = op.replace('y',str(float(y0)))
			out += (eval(op),)

		return out


	def GetWyckoffSymList(self, id):
		"""
		id is either the space group number or the space group id (a string), for 2D they are the same (no multiple settings)
		"""
		try:	id = str(id)				# this needed when an int was passed
		except:	ValueError('SG = %r is not supported, SG can only be a valid id of the %d 2D Space Groups' % (id,self.MaxIDnum))
		if   id=='1' : WyckList = [('a',('x','y'),1,'1')]
		elif id=='2' : WyckList = [('a',('0','0'),1,'2'),('b',('0','0.5'),1,'2'),('c',('0.5','0'),1,'2'),('d',('0.5','0.5'),1,'2'),('e',('x','y'),2,'1')]
		elif id=='3' : WyckList = [('a',('0','y'),1,'.m.'),('b',('0.5','y'),1,'.m.'),('c',('x','y'),2,'1')]
		elif id=='4' : WyckList = [('a',('x','y'),2,'1')]
		elif id=='5' : WyckList = [('a',('0','y'),2,'.m.'),('b',('x','y'),4,'1')]
		elif id=='6' : WyckList = [('a',('0','0'),1,'2mm'),('b',('0','0.5'),1,'2mm'),('c',('0.5','0'),1,'2mm'),('d',('0.5','0.5'),1,'2mm'),('e',('x','0'),2,'..m'),('f',('x','0.5'),2,'..m'),('g',('0','y'),2,'.m.'),('h',('0.5','y'),2,'.m.'),('i',('x','y'),4,'1')]
		elif id=='7' : WyckList = [('a',('0','0'),2,'2..'),('b',('0','0.5'),2,'2..'),('c',('0.25','y'),2,'.m.'),('d',('x','y'),4,'1')]
		elif id=='8' : WyckList = [('a',('0','0'),2,'2..'),('b',('0.5','0'),2,'2..'),('c',('x','y'),4,'1')]
		elif id=='9' : WyckList = [('a',('0','0'),2,'2mm'),('b',('0','0.5'),2,'2mm'),('c',('0.25','0.25'),4,'2..'),('d',('x','0'),4,'..m'),('e',('0','y'),4,'.m.'),('f',('x','y'),8,'1')]
		elif id=='10': WyckList = [('a',('0','0'),1,'4..'),('b',('0.5','0.5'),1,'4..'),('c',('0.5','0'),2,'2..'),('d',('x','y'),4,'1')]
		elif id=='11': WyckList = [('a',('0','0'),1,'4mm'),('b',('0.5','0.5'),1,'4mm'),('c',('0.5','0'),2,'2mm.'),('d',('x','0'),4,'.m.'),('e',('x','0.5'),4,'.m.'),('f',('x','x'),4,'..m'),('g',('x','y'),8,'1')]
		elif id=='12': WyckList = [('a',('0','0'),2,'4..'),('b',('0.5','0'),2,'2.mm'),('c',('x','x+0.5'),4,'..m'),('d',('x','y'),8,'1')]
		elif id=='13': WyckList = [('a',('0','0'),1,'3..'),('b',('1/3.','2/3.'),1,'3..'),('c',('2/3.','1/3.'),1,'3..'),('d',('x','y'),3,'1')]
		elif id=='14': WyckList = [('a',('0','0'),1,'3m.'),('b',('1/3.','2/3.'),1,'3m.'),('c',('2/3.','1/3.'),1,'3m.'),('d',('x','-x'),3,'.m.'),('e',('x','y'),6,'1')]
		elif id=='15': WyckList = [('a',('0','0'),1,'3.m'),('b',('1/3.','2/3.'),2,'3..'),('c',('x','0'),3,'..m'),('d',('x','y'),6,'1')]
		elif id=='16': WyckList = [('a',('0','0'),1,'6..'),('b',('1/3.','2/3.'),2,'3..'),('c',('0.5','0'),3,'2..'),('d',('x','y'),6,'1')]
		elif id=='17': WyckList = [('a',('0','0'),1,'6mm'),('b',('1/3.','2/3.'),2,'3m.'),('c',('0.5','0'),3,'2mm'),('d',('x','0'),6,'..m'),('e',('x','-x'),6,'.m.'),('f',('x','y'),12,'1')]
		else:
			WyckList = []
			ValueError('SG = %r is not supported, SG can only be one of the %d 2D Space Groups' % (id,self.MaxIDnum))
		return WyckList


	def GetSettingTransForm(self, id):
		"""
		for 2D, returns a 3x3 CBM matrix for converting the setting
		This matrix is always just the identity matrix for 2D
		"""
		try:
			id = str(id)
			if not (id in self.allIDs): raise
		except: ValueError('Cannot find the space group for id = %r, it should be something like "152"' % (id,))

		# always the identity matrix in 2D
		CBM = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
		return CBM.astype(float)


	def GetSymmetryOperations(self, SpaceGroupID):
		"""
		Returns the symmetry operations for a SpaceGroup as an array of numpy matricies
		SpaceGroupID is the ID, not just an integer e.g. "15:b3"
		"""
		SpaceGroupID = str(SpaceGroupID)		# in case an integer was passed, e.g. both 1 and "1" work

		if SpaceGroupID=='1':
			equivXY1 = np.array( [ [ [1.,0., 0], [0.,1., 0] ] ] )
		elif SpaceGroupID=='2':
			equivXY1 = np.array( [ [ [1.,0., 0], [0.,1., 0] ],
			[ [-1.,0., 0], [0.,-1., 0] ] ] )
		elif SpaceGroupID=='3':
			equivXY1 = np.array( [ [ [1.,0., 0], [0.,1., 0] ],
			[ [-1.,0., 0], [0.,1., 0] ] ] )
		elif SpaceGroupID=='4':
			equivXY1 = np.array( [ [ [1.,0., 0], [0.,1., 0] ],
			[ [-1.,0., 0], [0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='5':
			equivXY1 = np.array( [ [ [1.,0., 0], [0.,1., 0] ],
			[ [-1.,0., 0], [0.,1., 0] ],
			[ [1.,0., 1/2.], [0.,1., 1/2.] ],
			[ [-1.,0., 1/2.], [0.,1., 1/2.] ] ])
		elif SpaceGroupID=='6':
			equivXY1 = np.array( [ [ [1.,0., 0], [0.,1., 0] ],
			[ [-1.,0., 0], [0.,-1., 0] ],
			[ [-1.,0., 0], [0.,1., 0] ],
			[ [1.,0., 0], [0.,-1., 0] ] ])
		elif SpaceGroupID=='7':
			equivXY1 = np.array( [ [ [1.,0., 0], [0.,1., 0] ],
			[ [-1.,0., 0], [0.,-1., 0] ],
			[ [-1.,0., 1/2.], [0.,1., 0] ],
			[ [1.,0., 1/2.], [0.,-1., 0] ] ])
		elif SpaceGroupID=='8':
			equivXY1 = np.array( [ [ [1.,0., 0], [0.,1., 0] ],
			[ [-1.,0., 0], [0.,-1., 0] ],
			[ [-1.,0., 1/2.], [0.,1., 1/2.] ],
			[ [1.,0., 1/2.], [0.,-1., 1/2.] ] ])
		elif SpaceGroupID=='9':
			equivXY1 = np.array( [ [ [1.,0., 0], [0.,1., 0] ],
			[ [-1.,0., 0], [0.,-1., 0] ],
			[ [-1.,0., 0], [0.,1., 0] ],
			[ [1.,0., 0], [0.,-1., 0] ],
			[ [1.,0., 1/2.], [0.,1., 1/2.] ],
			[ [-1.,0., 1/2.], [0.,-1., 1/2.] ],
			[ [-1.,0., 1/2.], [0.,1., 1/2.] ],
			[ [1.,0., 1/2.], [0.,-1., 1/2.] ] ])
		elif SpaceGroupID=='10':
			equivXY1 = np.array( [ [ [1.,0., 0], [0.,1., 0] ],
			[ [-1.,0., 0], [0.,-1., 0] ],
			[ [0.,1., 0], [-1.,0., 0] ],
			[ [0.,-1., 0], [1.,0., 0] ] ])
		elif SpaceGroupID=='11':
			equivXY1 = np.array( [ [ [1.,0., 0], [0.,1., 0] ],
			[ [-1.,0., 0], [0.,-1., 0] ],
			[ [0.,1., 0], [-1.,0., 0] ],
			[ [0.,-1., 0], [1.,0., 0] ],
			[ [-1.,0., 0], [0.,1., 0] ],
			[ [1.,0., 0], [0.,-1., 0] ],
			[ [0.,1., 0], [1.,0., 0] ],
			[ [0.,-1., 0], [-1.,0., 0] ] ])
		elif SpaceGroupID=='12':
			equivXY1 = np.array( [ [ [1.,0., 0], [0.,1., 0] ],
			[ [-1.,0., 0], [0.,-1., 0] ],
			[ [0.,1., 0], [-1.,0., 0] ],
			[ [0.,-1., 0], [1.,0., 0] ],
			[ [-1.,0., 1/2.], [0.,1., 1/2.] ],
			[ [1.,0., 1/2.], [0.,-1., 1/2.] ],
			[ [0.,1., 1/2.], [1.,0., 1/2.] ],
			[ [0.,-1., 1/2.], [-1.,0., 1/2.] ] ])
		elif SpaceGroupID=='13':
			equivXY1 = np.array( [ [ [1.,0., 0], [0.,1., 0] ],
			[ [0.,-1., 0], [1.,-1., 0] ],
			[ [-1.,1., 0], [-1.,0., 0] ] ])
		elif SpaceGroupID=='14':
			equivXY1 = np.array( [ [ [1.,0., 0], [0.,1., 0] ],
			[ [0.,-1., 0], [1.,-1., 0] ],
			[ [-1.,1., 0], [-1.,0., 0] ],
			[ [0.,-1., 0], [-1.,0., 0] ],
			[ [-1.,1., 0], [0.,1., 0] ],
			[ [1.,0., 0], [1.,-1., 0] ] ])
		elif SpaceGroupID=='15':
			equivXY1 = np.array( [ [ [1.,0., 0], [0.,1., 0] ],
			[ [0.,-1., 0], [1.,-1., 0] ],
			[ [-1.,1., 0], [-1.,0., 0] ],
			[ [0.,1., 0], [1.,0., 0] ],
			[ [1.,-1., 0], [0.,-1., 0] ],
			[ [-1.,0., 0], [-1.,1., 0] ] ])
		elif SpaceGroupID=='16':
			equivXY1 = np.array( [ [ [1.,0., 0], [0.,1., 0] ],
			[ [0.,-1., 0], [1.,-1., 0] ],
			[ [-1.,1., 0], [-1.,0., 0] ],
			[ [-1.,0., 0], [0.,-1., 0] ],
			[ [0.,1., 0], [-1.,1., 0] ],
			[ [1.,-1., 0], [1.,0., 0] ] ])
		elif SpaceGroupID=='17':
			equivXY1 = np.array( [ [ [1.,0., 0], [0.,1., 0] ],
			[ [0.,-1., 0], [1.,-1., 0] ],
			[ [-1.,1., 0], [-1.,0., 0] ],
			[ [-1.,0., 0], [0.,-1., 0] ],
			[ [0.,1., 0], [-1.,1., 0] ],
			[ [1.,-1., 0], [1.,0., 0] ],
			[ [0.,-1., 0], [-1.,0., 0] ],
			[ [-1.,1., 0], [0.,1., 0] ],
			[ [1.,0., 0], [1.,-1., 0] ],
			[ [0.,1., 0], [1.,0., 0] ],
			[ [1.,-1., 0], [0.,-1., 0] ],
			[ [-1.,0., 0], [-1.,1., 0] ] ])

		else:
			equivXY1 = None
			raise ValueError('INVALID SpaceGroupID, %r (type=%s) is not a valid id' % (SpaceGroupID,type(SpaceGroupID)))

		return equivXY1



class LatticeBase3D(LatticeBase0):
	""" A Class that the defines has a lot of the things in 3D Lattice, but without actually defining one.
		Mostly utility things and lists of constants
		some useful utility type routines:
		getHMboth(SpaceGroupID)
		getHMsym(SpaceGroupID)
		getFullHMSym(SpaceGroupID)
		getHallSymbol(SpaceGroupID)
		SymString2IDs(symFind,type)		# returns list of possible space groups
										# symFind, requested symbol, with possible '*'
										# type, 0=all, 1=Hermann-Mauguin, 2=Full Hermann-Mauguin, 3=Hall, 4=Lattice System
	"""

	def __init__(self):
		LatticeBase0.__init__(self)		# no parameters needed

		self.CUBIC = 6
		self.HEXAGONAL = 5
		self.TRIGONAL = 4
		self.TETRAGONAL = 3
		self.ORTHORHOMBIC = 2
		self.MONOCLINIC = 1
		self.TRICLINIC = 0
		self.latticeSystemNames = ['Triclinic','Monoclinic','Orthorhombic','Tetragonal','Trigonal','Hexagonal','Cubic']
		self.MaxIDnum = 530

		self.allIDs = ['1','2','3:b','3:c','3:a','4:b','4:c','4:a','5:b1','5:b2','5:b3','5:c1','5:c2','5:c3','5:a1','5:a2',
		'5:a3','6:b','6:c','6:a','7:b1','7:b2','7:b3','7:c1','7:c2','7:c3','7:a1','7:a2','7:a3','8:b1','8:b2','8:b3',
		'8:c1','8:c2','8:c3','8:a1','8:a2','8:a3','9:b1','9:b2','9:b3','9:-b1','9:-b2','9:-b3','9:c1','9:c2',
		'9:c3','9:-c1','9:-c2','9:-c3','9:a1','9:a2','9:a3','9:-a1','9:-a2','9:-a3','10:b','10:c','10:a','11:b',
		'11:c','11:a','12:b1','12:b2','12:b3','12:c1','12:c2','12:c3','12:a1','12:a2','12:a3','13:b1','13:b2',
		'13:b3','13:c1','13:c2','13:c3','13:a1','13:a2','13:a3','14:b1','14:b2','14:b3','14:c1','14:c2','14:c3',
		'14:a1','14:a2','14:a3','15:b1','15:b2','15:b3','15:-b1','15:-b2','15:-b3','15:c1','15:c2','15:c3',
		'15:-c1','15:-c2','15:-c3','15:a1','15:a2','15:a3','15:-a1','15:-a2','15:-a3','16','17','17:cab','17:bca',
		'18','18:cab','18:bca','19','20','20:cab','20:bca','21','21:cab','21:bca','22','23','24','25','25:cab','25:bca',
		'26','26:ba-c','26:cab','26:-cba','26:bca','26:a-cb','27','27:cab','27:bca','28','28:ba-c','28:cab',
		'28:-cba','28:bca','28:a-cb','29','29:ba-c','29:cab','29:-cba','29:bca','29:a-cb','30','30:ba-c',
		'30:cab','30:-cba','30:bca','30:a-cb','31','31:ba-c','31:cab','31:-cba','31:bca','31:a-cb','32',
		'32:cab','32:bca','33','33:ba-c','33:cab','33:-cba','33:bca','33:a-cb','34','34:cab','34:bca','35',
		'35:cab','35:bca','36','36:ba-c','36:cab','36:-cba','36:bca','36:a-cb','37','37:cab','37:bca','38',
		'38:ba-c','38:cab','38:-cba','38:bca','38:a-cb','39','39:ba-c','39:cab','39:-cba','39:bca','39:a-cb',
		'40','40:ba-c','40:cab','40:-cba','40:bca','40:a-cb','41','41:ba-c','41:cab','41:-cba','41:bca',
		'41:a-cb','42','42:cab','42:bca','43','43:cab','43:bca','44','44:cab','44:bca','45','45:cab','45:bca',
		'46','46:ba-c','46:cab','46:-cba','46:bca','46:a-cb','47','48:1','48:2','49','49:cab','49:bca','50:1',
		'50:2','50:1cab','50:2cab','50:1bca','50:2bca','51','51:ba-c','51:cab','51:-cba','51:bca','51:a-cb',
		'52','52:ba-c','52:cab','52:-cba','52:bca','52:a-cb','53','53:ba-c','53:cab','53:-cba','53:bca',
		'53:a-cb','54','54:ba-c','54:cab','54:-cba','54:bca','54:a-cb','55','55:cab','55:bca','56','56:cab',
		'56:bca','57','57:ba-c','57:cab','57:-cba','57:bca','57:a-cb','58','58:cab','58:bca','59:1','59:2',
		'59:1cab','59:2cab','59:1bca','59:2bca','60','60:ba-c','60:cab','60:-cba','60:bca','60:a-cb','61',
		'61:ba-c','62','62:ba-c','62:cab','62:-cba','62:bca','62:a-cb','63','63:ba-c','63:cab','63:-cba',
		'63:bca','63:a-cb','64','64:ba-c','64:cab','64:-cba','64:bca','64:a-cb','65','65:cab','65:bca','66',
		'66:cab','66:bca','67','67:ba-c','67:cab','67:-cba','67:bca','67:a-cb','68:1','68:2','68:1ba-c',
		'68:2ba-c','68:1cab','68:2cab','68:1-cba','68:2-cba','68:1bca','68:2bca','68:1a-cb','68:2a-cb',
		'69','70:1','70:2','71','72','72:cab','72:bca','73','73:ba-c','74','74:ba-c','74:cab','74:-cba','74:bca',
		'74:a-cb','75','76','77','78','79','80','81','82','83','84','85:1','85:2','86:1','86:2','87','88:1','88:2','89','90',
		'91','92','93','94','95','96','97','98','99','100','101','102','103','104','105','106','107','108','109','110','111','112',
		'113','114','115','116','117','118','119','120','121','122','123','124','125:1','125:2','126:1','126:2','127',
		'128','129:1','129:2','130:1','130:2','131','132','133:1','133:2','134:1','134:2','135','136','137:1','137:2',
		'138:1','138:2','139','140','141:1','141:2','142:1','142:2','143','144','145','146:H','146:R','147','148:H',
		'148:R','149','150','151','152','153','154','155:H','155:R','156','157','158','159','160:H','160:R','161:H',
		'161:R','162','163','164','165','166:H','166:R','167:H','167:R','168','169','170','171','172','173','174','175',
		'176','177','178','179','180','181','182','183','184','185','186','187','188','189','190','191','192','193','194',
		'195','196','197','198','199','200','201:1','201:2','202','203:1','203:2','204','205','206','207','208','209',
		'210','211','212','213','214','215','216','217','218','219','220','221','222:1','222:2','223','224:1','224:2',
		'225','226','227:1','227:2','228:1','228:2','229','230']
		"""
		In these 530 Space Group ID's, there are:
		  140 Space Groups of   1 types
		   30 Space Groups of   2 types
		   26 Space Groups of   3 types
		   25 Space Groups of   6 types
		   6 Space Groups of   9 types
		    1 Space Groups of  12 types
		    2 Space Groups of  18 types

		returns info about the symmetry of a structure
		sym holds the symmetry info on return, and xyz holds the atom positions.  It returns the number of atom positions 
		put in xyz which is always at least 1.  If you call with a bad wave ref for xyz, then it only returns the sym string, 
		and the returned value is 0

		Extensions
		----------
		Monoclinic			unique axis b		unique axis c		unique axis a
								abc  c-ba		abc   ba-c			abc	-acb
							------------		------------ 		------------
		cell choice 1		  :b1 	:-b1		:c1 	:-c1			:a1	:-a1
					2		  :b2 	:-b2		:c2  	:-c2			:a2	:-a2
					3		  :b3 	:-b3		:c3  	:-c3			:a3	:-a3

	   Orthorhombic	:ba-c	change of basis abc -> ba-c
					:1		origin choice 1
					:2ba-c	origin choice 2, change of basis abc -> ba-c

	   Tetragonal	:1		origin choice 1
			 Cubic	:2		origin choice 2

	   Trigonal		:H		hexagonal    axes
					:R		rhombohedral axes
		"""

		# the only Space Group IDs that actually expect Rhombohedral lattice constants
		self.RhomIDs = ['146:R','148:R','155:R','160:R','161:R','166:R','167:R']

		""" returns short Hermann-Mauguin symbol, there are 530 symbols in the list """
		self.HM1 = ['P1','P-1','P2:b','P2:c','P2:a','P21:b','P21:c','P21:a','C2:b1','C2:b2','C2:b3','C2:c1','C2:c2','C2:c3','C2:a1','C2:a2','C2:a3','Pm:b','Pm:c','Pm:a','Pc:b1','Pc:b2','Pc:b3',
		'Pc:c1','Pc:c2','Pc:c3','Pc:a1','Pc:a2','Pc:a3','Cm:b1','Cm:b2','Cm:b3','Cm:c1','Cm:c2','Cm:c3','Cm:a1','Cm:a2','Cm:a3','Cc:b1','Cc:b2','Cc:b3','Cc:-b1','Cc:-b2','Cc:-b3',
		'Cc:c1','Cc:c2','Cc:c3','Cc:-c1','Cc:-c2','Cc:-c3','Cc:a1','Cc:a2','Cc:a3','Cc:-a1','Cc:-a2','Cc:-a3','P2/m:b','P2/m:c','P2/m:a','P21/m:b','P21/m:c','P21/m:a','C2/m:b1',
		'C2/m:b2','C2/m:b3','C2/m:c1','C2/m:c2','C2/m:c3','C2/m:a1','C2/m:a2','C2/m:a3','P2/c:b1','P2/c:b2','P2/c:b3','P2/c:c1','P2/c:c2','P2/c:c3','P2/c:a1','P2/c:a2',
		'P2/c:a3','P21/c:b1','P21/c:b2','P21/c:b3','P21/c:c1','P21/c:c2','P21/c:c3','P21/c:a1','P21/c:a2','P21/c:a3','C2/c:b1','C2/c:b2','C2/c:b3','C2/c:-b1','C2/c:-b2',
		'C2/c:-b3','C2/c:c1','C2/c:c2','C2/c:c3','C2/c:-c1','C2/c:-c2','C2/c:-c3','C2/c:a1','C2/c:a2','C2/c:a3','C2/c:-a1','C2/c:-a2','C2/c:-a3','P222','P2221','P2122',
		'P2212','P21212','P22121','P21221','P212121','C2221','A2122','B2212','C222','A222','B222','F222','I222','I212121','Pmm2','P2mm','Pm2m','Pmc21','Pcm21','P21ma','P21am','Pb21m',
		'Pm21b','Pcc2','P2aa','Pb2b','Pma2','Pbm2','P2mb','P2cm','Pc2m','Pm2a','Pca21','Pbc21','P21ab','P21ca','Pc21b','Pb21a','Pnc2','Pcn2','P2na','P2an','Pb2n','Pn2b','Pmn21','Pnm21',
		'P21mn','P21nm','Pn21m','Pm21n','Pba2','P2cb','Pc2a','Pna21','Pbn21','P21nb','P21cn','Pc21n','Pn21a','Pnn2','P2nn','Pn2n','Cmm2','A2mm','Bm2m','Cmc21','Ccm21','A21ma','A21am',
		'Bb21m','Bm21b','Ccc2','A2aa','Bb2b','Amm2','Bmm2','B2mm','C2mm','Cm2m','Am2m','Abm2','Bma2','B2cm','C2mb','Cm2a','Ac2m','Ama2','Bbm2','B2mb','C2cm','Cc2m','Am2a','Aba2','Bba2',
		'B2cb','C2cb','Cc2a','Ac2a','Fmm2','F2mm','Fm2m','Fdd2','F2dd','Fd2d','Imm2','I2mm','Im2m','Iba2','I2cb','Ic2a','Ima2','Ibm2','I2mb','I2cm','Ic2m','Im2a','Pmmm','Pnnn:1','Pnnn:2',
		'Pccm','Pmaa','Pbmb','Pban:1','Pban:2','Pncb:1','Pncb:2','Pcna:1','Pcna:2','Pmma','Pmmb','Pbmm','Pcmm','Pmcm','Pmam','Pnna','Pnnb','Pbnn','Pcnn','Pncn','Pnan','Pmna','Pnmb',
		'Pbmn','Pcnm','Pncm','Pman','Pcca','Pccb','Pbaa','Pcaa','Pbcb','Pbab','Pbam','Pmcb','Pcma','Pccn','Pnaa','Pbnb','Pbcm','Pcam','Pmca','Pmab','Pbma','Pcmb','Pnnm','Pmnn','Pnmn',
		'Pmmn:1','Pmmn:2','Pnmm:1','Pnmm:2','Pmnm:1','Pmnm:2','Pbcn','Pcan','Pnca','Pnab','Pbna','Pcnb','Pbca','Pcab','Pnma','Pmnb','Pbnm','Pcmn','Pmcn','Pnam','Cmcm','Ccmm','Amma',
		'Amam','Bbmm','Bmmb','Cmca','Ccmb','Abma','Acam','Bbcm','Bmab','Cmmm','Ammm','Bmmm','Cccm','Amaa','Bbmb','Cmma','Cmmb','Abmm','Acmm','Bmcm','Bmam','Ccca:1','Ccca:2','Cccb:1',
		'Cccb:2','Abaa:1','Abaa:2','Acaa:1','Acaa:2','Bbcb:1','Bbcb:2','Bbab:1','Bbab:2','Fmmm','Fddd:1','Fddd:2','Immm','Ibam','Imcb','Icma','Ibca','Icab','Imma','Immb','Ibmm',
		'Icmm','Imcm','Imam','P4','P41','P42','P43','I4','I41','P-4','I-4','P4/m','P42/m','P4/n:1','P4/n:2','P42/n:1','P42/n:2','I4/m','I41/a:1','I41/a:2','P422','P4212','P4122','P41212',
		'P4222','P42212','P4322','P43212','I422','I4122','P4mm','P4bm','P42cm','P42nm','P4cc','P4nc','P42mc','P42bc','I4mm','I4cm','I41md','I41cd','P-42m','P-42c','P-421m','P-421c',
		'P-4m2','P-4c2','P-4b2','P-4n2','I-4m2','I-4c2','I-42m','I-42d','P4/mmm','P4/mcc','P4/nbm:1','P4/nbm:2','P4/nnc:1','P4/nnc:2','P4/mbm','P4/mnc','P4/nmm:1','P4/nmm:2',
		'P4/ncc:1','P4/ncc:2','P42/mmc','P42/mcm','P42/nbc:1','P42/nbc:2','P42/nnm:1','P42/nnm:2','P42/mbc','P42/mnm','P42/nmc:1','P42/nmc:2','P42/ncm:1','P42/ncm:2',
		'I4/mmm','I4/mcm','I41/amd:1','I41/amd:2','I41/acd:1','I41/acd:2','P3','P31','P32','R3:H','R3:R','P-3','R-3:H','R-3:R','P312','P321','P3112','P3121','P3212','P3221','R32:H',
		'R32:R','P3m1','P31m','P3c1','P31c','R3m:H','R3m:R','R3c:H','R3c:R','P-31m','P-31c','P-3m1','P-3c1','R-3m:H','R-3m:R','R-3c:H','R-3c:R','P6','P61','P65','P62','P64','P63','P-6',
		'P6/m','P63/m','P622','P6122','P6522','P6222','P6422','P6322','P6mm','P6cc','P63cm','P63mc','P-6m2','P-6c2','P-62m','P-62c','P6/mmm','P6/mcc','P63/mcm','P63/mmc','P23','F23',
		'I23','P213','I213','Pm-3','Pn-3:1','Pn-3:2','Fm-3','Fd-3:1','Fd-3:2','Im-3','Pa-3','Ia-3','P432','P4232','F432','F4132','I432','P4332','P4132','I4132','P-43m','F-43m','I-43m',
		'P-43n','F-43c','I-43d','Pm-3m','Pn-3n:1','Pn-3n:2','Pm-3n','Pn-3m:1','Pn-3m:2','Fm-3m','Fm-3c','Fd-3m:1','Fd-3m:2','Fd-3c:1','Fd-3c:2','Im-3m','Ia-3d']

		""" returns full Hermann-Mauguin symbol
		Full H-M symbols only differ from the regular ones (in getHMsym)
		for Space Groups: 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15
		There are 530 symbols in the list
		"""
		self.HM2  = ['P1','P-1','P121','P112','P211','P1211','P1121','P2111','C121','A121','I121','A112','B112','I112','B211','C211','I211','P1m1','P11m','Pm11','P1c1','P1n1','P1a1','P11a','P11n','P11b',
		'Pb11','Pn11','Pc11','C1m1','A1m1','I1m1','A11m','B11m','I11m','Bm11','Cm11','Im11','C1c1','A1n1','I1a1','A1a1','C1n1','I1c1','A11a','B11n','I11b','B11b','A11n','I11a','Bb11','Cn11',
		'Ic11','Cc11','Bn11','Ib11','P12/m1','P112/m','P2/m11','P121/m1','P1121/m','P21/m11','C12/m1','A12/m1','I12/m1','A112/m','B112/m','I112/m','B2/m11','C2/m11','I2/m11',
		'P12/c1','P12/n1','P12/a1','P112/a','P112/n','P112/b','P2/b11','P2/n11','P2/c11','P121/c1','P121/n1','P121/a1','P1121/a','P1121/n','P1121/b','P21/b11','P21/n11',
		'P21/c11','C12/c1','A12/n1','I12/a1','A12/a1','C12/n1','I12/c1','A112/a','B112/n','I112/b','B112/b','A112/n','I112/a','B2/b11','C2/n11','I2/c11','C2/c11','B2/n11',
		'I2/b11','P222','P2221','P2122','P2212','P21212','P22121','P21221','P212121','C2221','A2122','B2212','C222','A222','B222','F222','I222','I212121','Pmm2','P2mm','Pm2m','Pmc21',
		'Pcm21','P21ma','P21am','Pb21m','Pm21b','Pcc2','P2aa','Pb2b','Pma2','Pbm2','P2mb','P2cm','Pc2m','Pm2a','Pca21','Pbc21','P21ab','P21ca','Pc21b','Pb21a','Pnc2','Pcn2','P2na','P2an',
		'Pb2n','Pn2b','Pmn21','Pnm21','P21mn','P21nm','Pn21m','Pm21n','Pba2','P2cb','Pc2a','Pna21','Pbn21','P21nb','P21cn','Pc21n','Pn21a','Pnn2','P2nn','Pn2n','Cmm2','A2mm','Bm2m',
		'Cmc21','Ccm21','A21ma','A21am','Bb21m','Bm21b','Ccc2','A2aa','Bb2b','Amm2','Bmm2','B2mm','C2mm','Cm2m','Am2m','Abm2','Bma2','B2cm','C2mb','Cm2a','Ac2m','Ama2','Bbm2','B2mb','C2cm',
		'Cc2m','Am2a','Aba2','Bba2','B2cb','C2cb','Cc2a','Ac2a','Fmm2','F2mm','Fm2m','Fdd2','F2dd','Fd2d','Imm2','I2mm','Im2m','Iba2','I2cb','Ic2a','Ima2','Ibm2','I2mb','I2cm','Ic2m','Im2a',
		'Pmmm','Pnnn:1','Pnnn:2','Pccm','Pmaa','Pbmb','Pban:1','Pban:2','Pncb:1','Pncb:2','Pcna:1','Pcna:2','Pmma','Pmmb','Pbmm','Pcmm','Pmcm','Pmam','Pnna','Pnnb','Pbnn','Pcnn','Pncn',
		'Pnan','Pmna','Pnmb','Pbmn','Pcnm','Pncm','Pman','Pcca','Pccb','Pbaa','Pcaa','Pbcb','Pbab','Pbam','Pmcb','Pcma','Pccn','Pnaa','Pbnb','Pbcm','Pcam','Pmca','Pmab','Pbma','Pcmb','Pnnm',
		'Pmnn','Pnmn','Pmmn:1','Pmmn:2','Pnmm:1','Pnmm:2','Pmnm:1','Pmnm:2','Pbcn','Pcan','Pnca','Pnab','Pbna','Pcnb','Pbca','Pcab','Pnma','Pmnb','Pbnm','Pcmn','Pmcn','Pnam','Cmcm',
		'Ccmm','Amma','Amam','Bbmm','Bmmb','Cmca','Ccmb','Abma','Acam','Bbcm','Bmab','Cmmm','Ammm','Bmmm','Cccm','Amaa','Bbmb','Cmma','Cmmb','Abmm','Acmm','Bmcm','Bmam','Ccca:1','Ccca:2',
		'Cccb:1','Cccb:2','Abaa:1','Abaa:2','Acaa:1','Acaa:2','Bbcb:1','Bbcb:2','Bbab:1','Bbab:2','Fmmm','Fddd:1','Fddd:2','Immm','Ibam','Imcb','Icma','Ibca','Icab','Imma','Immb',
		'Ibmm','Icmm','Imcm','Imam','P4','P41','P42','P43','I4','I41','P-4','I-4','P4/m','P42/m','P4/n:1','P4/n:2','P42/n:1','P42/n:2','I4/m','I41/a:1','I41/a:2','P422','P4212','P4122',
		'P41212','P4222','P42212','P4322','P43212','I422','I4122','P4mm','P4bm','P42cm','P42nm','P4cc','P4nc','P42mc','P42bc','I4mm','I4cm','I41md','I41cd','P-42m','P-42c','P-421m',
		'P-421c','P-4m2','P-4c2','P-4b2','P-4n2','I-4m2','I-4c2','I-42m','I-42d','P4/mmm','P4/mcc','P4/nbm:1','P4/nbm:2','P4/nnc:1','P4/nnc:2','P4/mbm','P4/mnc','P4/nmm:1',
		'P4/nmm:2','P4/ncc:1','P4/ncc:2','P42/mmc','P42/mcm','P42/nbc:1','P42/nbc:2','P42/nnm:1','P42/nnm:2','P42/mbc','P42/mnm','P42/nmc:1','P42/nmc:2','P42/ncm:1',
		'P42/ncm:2','I4/mmm','I4/mcm','I41/amd:1','I41/amd:2','I41/acd:1','I41/acd:2','P3','P31','P32','R3:H','R3:R','P-3','R-3:H','R-3:R','P312','P321','P3112','P3121','P3212',
		'P3221','R32:H','R32:R','P3m1','P31m','P3c1','P31c','R3m:H','R3m:R','R3c:H','R3c:R','P-31m','P-31c','P-3m1','P-3c1','R-3m:H','R-3m:R','R-3c:H','R-3c:R','P6','P61','P65','P62',
		'P64','P63','P-6','P6/m','P63/m','P622','P6122','P6522','P6222','P6422','P6322','P6mm','P6cc','P63cm','P63mc','P-6m2','P-6c2','P-62m','P-62c','P6/mmm','P6/mcc','P63/mcm',
		'P63/mmc','P23','F23','I23','P213','I213','Pm-3','Pn-3:1','Pn-3:2','Fm-3','Fd-3:1','Fd-3:2','Im-3','Pa-3','Ia-3','P432','P4232','F432','F4132','I432','P4332','P4132','I4132',
		'P-43m','F-43m','I-43m','P-43n','F-43c','I-43d','Pm-3m','Pn-3n:1','Pn-3n:2','Pm-3n','Pn-3m:1','Pn-3m:2','Fm-3m','Fm-3c','Fd-3m:1','Fd-3m:2','Fd-3c:1','Fd-3c:2','Im-3m',
		'Ia-3d']

		""" Hall Symbols, there are 530 items in this list """
		self.Hall  = ['P 1','-P 1','P 2y','P 2','P 2x','P 2yb','P 2c','P 2xa','C 2y','A 2y','I 2y','A 2','B 2','I 2','B 2x','C 2x','I 2x','P -2y','P -2','P -2x','P -2yc','P -2yac','P -2ya','P -2a',''
		'P -2ab','P -2b','P -2xb','P -2xbc','P -2xc','C -2y','A -2y','I -2y','A -2','B -2','I -2','B -2x','C -2x','I -2x','C -2yc','A -2yac','I -2ya','A -2ya','C -2ybc','I -2yc',''
		'A -2a','B -2bc','I -2b','B -2b','A -2ac','I -2a','B -2xb','C -2xbc','I -2xc','C -2xc','B -2xbc','I -2xb','-P 2y','-P 2','-P 2x','-P 2yb','-P 2c','-P 2xa','-C 2y',''
		'-A 2y','-I 2y','-A 2','-B 2','-I 2','-B 2x','-C 2x','-I 2x','-P 2yc','-P 2yac','-P 2ya','-P 2a','-P 2ab','-P 2b','-P 2xb','-P 2xbc','-P 2xc','-P 2ybc','-P 2yn',''
		'-P 2yab','-P 2ac','-P 2n','-P 2bc','-P 2xab','-P 2xn','-P 2xac','-C 2yc','-A 2yac','-I 2ya','-A 2ya','-C 2ybc','-I 2yc','-A 2a','-B 2bc','-I 2b','-B 2b','-A 2ac',''
		'-I 2a','-B 2xb','-C 2xbc','-I 2xc','-C 2xc','-B 2xbc','-I 2xb','P 2 2','P 2c 2','P 2a 2a','P 2 2b','P 2 2ab','P 2bc 2','P 2ac 2ac','P 2ac 2ab','C 2c 2','A 2a 2a',''
		'B 2 2b','C 2 2','A 2 2','B 2 2','F 2 2','I 2 2','I 2b 2c','P 2 -2','P -2 2','P -2 -2','P 2c -2','P 2c -2c','P -2a 2a','P -2 2a','P -2 -2b','P -2b -2','P 2 -2c',''
		'P -2a 2','P -2b -2b','P 2 -2a','P 2 -2b','P -2b 2','P -2c 2','P -2c -2c','P -2a -2a','P 2c -2ac','P 2c -2b','P -2b 2a','P -2ac 2a','P -2bc -2c','P -2a -2ab',''
		'P 2 -2bc','P 2 -2ac','P -2ac 2','P -2ab 2','P -2ab -2ab','P -2bc -2bc','P 2ac -2','P 2bc -2bc','P -2ab 2ab','P -2 2ac','P -2 -2bc','P -2ab -2','P 2 -2ab',''
		'P -2bc 2','P -2ac -2ac','P 2c -2n','P 2c -2ab','P -2bc 2a','P -2n 2a','P -2n -2ac','P -2ac -2n','P 2 -2n','P -2n 2','P -2n -2n','C 2 -2','A -2 2','B -2 -2',''
		'C 2c -2','C 2c -2c','A -2a 2a','A -2 2a','B -2 -2b','B -2b -2','C 2 -2c','A -2a 2','B -2b -2b','A 2 -2','B 2 -2','B -2 2','C -2 2','C -2 -2','A -2 -2','A 2 -2c',''
		'B 2 -2c','B -2c 2','C -2b 2','C -2b -2b','A -2c -2c','A 2 -2a','B 2 -2b','B -2b 2','C -2c 2','C -2c -2c','A -2a -2a','A 2 -2ac','B 2 -2bc','B -2bc 2',''
		'C -2bc 2','C -2bc -2bc','A -2ac -2ac','F 2 -2','F -2 2','F -2 -2','F 2 -2d','F -2d 2','F -2d -2d','I 2 -2','I -2 2','I -2 -2','I 2 -2c','I -2a 2','I -2b -2b',''
		'I 2 -2a','I 2 -2b','I -2b 2','I -2c 2','I -2c -2c','I -2a -2a','-P 2 2','P 2 2 -1n','-P 2ab 2bc','-P 2 2c','-P 2a 2','-P 2b 2b','P 2 2 -1ab','-P 2ab 2b',''
		'P 2 2 -1bc','-P 2b 2bc','P 2 2 -1ac','-P 2a 2c','-P 2a 2a','-P 2b 2','-P 2 2b','-P 2c 2c','-P 2c 2','-P 2 2a','-P 2a 2bc','-P 2b 2n','-P 2n 2b','-P 2ab 2c',''
		'-P 2ab 2n','-P 2n 2bc','-P 2ac 2','-P 2bc 2bc','-P 2ab 2ab','-P 2 2ac','-P 2 2bc','-P 2ab 2','-P 2a 2ac','-P 2b 2c','-P 2a 2b','-P 2ac 2c','-P 2bc 2b',''
		'-P 2b 2ab','-P 2 2ab','-P 2bc 2','-P 2ac 2ac','-P 2ab 2ac','-P 2ac 2bc','-P 2bc 2ab','-P 2c 2b','-P 2c 2ac','-P 2ac 2a','-P 2b 2a','-P 2a 2ab','-P 2bc 2c',''
		'-P 2 2n','-P 2n 2','-P 2n 2n','P 2 2ab -1ab','-P 2ab 2a','P 2bc 2 -1bc','-P 2c 2bc','P 2ac 2ac -1ac','-P 2c 2a','-P 2n 2ab','-P 2n 2c','-P 2a 2n',''
		'-P 2bc 2n','-P 2ac 2b','-P 2b 2ac','-P 2ac 2ab','-P 2bc 2ac','-P 2ac 2n','-P 2bc 2a','-P 2c 2ab','-P 2n 2ac','-P 2n 2a','-P 2c 2n','-C 2c 2','-C 2c 2c',''
		'-A 2a 2a','-A 2 2a','-B 2 2b','-B 2b 2','-C 2bc 2','-C 2bc 2bc','-A 2ac 2ac','-A 2 2ac','-B 2 2bc','-B 2bc 2','-C 2 2','-A 2 2','-B 2 2','-C 2 2c','-A 2a 2',''
		'-B 2b 2b','-C 2b 2','-C 2b 2b','-A 2c 2c','-A 2 2c','-B 2 2c','-B 2c 2','C 2 2 -1bc','-C 2b 2bc','C 2 2 -1bc','-C 2b 2c','A 2 2 -1ac','-A 2a 2c',''
		'A 2 2 -1ac','-A 2ac 2c','B 2 2 -1bc','-B 2bc 2b','B 2 2 -1bc','-B 2b 2bc','-F 2 2','F 2 2 -1d','-F 2uv 2vw','-I 2 2','-I 2 2c','-I 2a 2','-I 2b 2b',''
		'-I 2b 2c','-I 2a 2b','-I 2b 2','-I 2a 2a','-I 2c 2c','-I 2 2b','-I 2 2a','-I 2c 2','P 4','P 4w','P 4c','P 4cw','I 4','I 4bw','P -4','I -4','-P 4','-P 4c','P 4ab -1ab',''
		'-P 4a','P 4n -1n','-P 4bc','-I 4','I 4bw -1bw','-I 4ad','P 4 2','P 4ab 2ab','P 4w 2c','P 4abw 2nw','P 4c 2','P 4n 2n','P 4cw 2c','P 4nw 2abw','I 4 2',''
		'I 4bw 2bw','P 4 -2','P 4 -2ab','P 4c -2c','P 4n -2n','P 4 -2c','P 4 -2n','P 4c -2','P 4c -2ab','I 4 -2','I 4 -2c','I 4bw -2','I 4bw -2c','P -4 2','P -4 2c',''
		'P -4 2ab','P -4 2n','P -4 -2','P -4 -2c','P -4 -2ab','P -4 -2n','I -4 -2','I -4 -2c','I -4 2','I -4 2bw','-P 4 2','-P 4 2c','P 4 2 -1ab','-P 4a 2b',''
		'P 4 2 -1n','-P 4a 2bc','-P 4 2ab','-P 4 2n','P 4ab 2ab -1ab','-P 4a 2a','P 4ab 2n -1ab','-P 4a 2ac','-P 4c 2','-P 4c 2c','P 4n 2c -1n','-P 4ac 2b',''
		'P 4n 2 -1n','-P 4ac 2bc','-P 4c 2ab','-P 4n 2n','P 4n 2n -1n','-P 4ac 2a','P 4n 2ab -1n','-P 4ac 2ac','-I 4 2','-I 4 2c','I 4bw 2bw -1bw','-I 4bd 2',''
		'I 4bw 2aw -1bw','-I 4bd 2c','P 3','P 31','P 32','R 3','P 3*','-P 3','-R 3','-P 3*','P 3 2','P 3 2\'','P 31 2c (0 0 1)','P 31 2\'','P 32 2c (0 0 -1)','P 32 2\'',''
		'R 3 2\'','P 3* 2','P 3 -2\'','P 3 -2','P 3 -2\'c','P 3 -2c','R 3 -2\'','P 3* -2','R 3 -2\'c','P 3* -2n','-P 3 2','-P 3 2c','-P 3 2\'','-P 3 2\'c','-R 3 2\'',''
		'-P 3* 2','-R 3 2\'c','-P 3* 2n','P 6','P 61','P 65','P 62','P 64','P 6c','P -6','-P 6','-P 6c','P 6 2','P 61 2 (0 0 -1)','P 65 2 (0 0 1)','P 62 2c (0 0 1)',''
		'P 64 2c (0 0 -1)','P 6c 2c','P 6 -2','P 6 -2c','P 6c -2','P 6c -2c','P -6 2','P -6c 2','P -6 -2','P -6c -2c','-P 6 2','-P 6 2c','-P 6c 2','-P 6c 2c','P 2 2 3',''
		'F 2 2 3','I 2 2 3','P 2ac 2ab 3','I 2b 2c 3','-P 2 2 3','P 2 2 3 -1n','-P 2ab 2bc 3','-F 2 2 3','F 2 2 3 -1d','-F 2uv 2vw 3','-I 2 2 3','-P 2ac 2ab 3',''
		'-I 2b 2c 3','P 4 2 3','P 4n 2 3','F 4 2 3','F 4d 2 3','I 4 2 3','P 4acd 2ab 3','P 4bd 2ab 3','I 4bd 2c 3','P -4 2 3','F -4 2 3','I -4 2 3','P -4n 2 3',''
		'F -4c 2 3','I -4bd 2c 3','-P 4 2 3','P 4 2 3 -1n','-P 4a 2bc 3','-P 4n 2 3','P 4n 2 3 -1n','-P 4bc 2bc 3','-F 4 2 3','-F 4c 2 3','F 4d 2 3 -1d',''
		'-F 4vw 2vw 3','F 4d 2 3 -1cd','-F 4cvw 2vw 3','-I 4 2 3','-I 4bd 2c 3']

		""" PointGroup Symbols, there are 530 items in this list """
		self.PointGroup = ['1','-1','2','2','2','2','2','2','2','2','2','2','2','2','2','2','2','m','m','m','m','m','m','m','m','m','m','m','m',
		'm','m','m','m','m','m','m','m','m','m','m','m','m','m','m','m','m','m','m','m','m','m','m','m','m','m','m','2/m','2/m','2/m','2/m','2/m',
		'2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m',
		'2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m',
		'222','222','222','222','222','222','222','222','222','222','222','222','222','222','222','222','222','mm2','mm2','mm2','mm2','mm2','mm2',
		'mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2',
		'mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2',
		'mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2',
		'mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2','mm2',
		'mm2','mm2','mm2','mm2','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm',
		'mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm',
		'mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm',
		'mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm',
		'mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm',
		'mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','4','4','4','4','4','4','-4','-4','4/m','4/m','4/m','4/m','4/m','4/m',
		'4/m','4/m','4/m','422','422','422','422','422','422','422','422','422','422','4mm','4mm','4mm','4mm','4mm','4mm','4mm','4mm','4mm','4mm',
		'4mm','4mm','-42m','-42m','-42m','-42m','-4m2','-4m2','-4m2','-4m2','-4m2','-4m2','-42m','-42m','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm',
		'4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm',
		'4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','3','3','3','3','3','-3','-3','-3','312','321','312','321','312','321',
		'321','32','3m1','31m','3m1','31m','3m1','3m','3m1','3m','-31m','-31m','-3m1','-3m1','-3m1','-3m','-3m1','-3m','6','6','6','6','6','6',
		'-6','6/m','6/m','622','622','622','622','622','622','6mm','6mm','6mm','6mm','-6m2','-6m2','-62m','-62m','6/mmm','6/mmm','6/mmm','6/mmm',
		'23','23','23','23','23','m-3','m-3','m-3','m-3','m-3','m-3','m-3','m-3','m-3','432','432','432','432','432','432','432','432','-43m',
		'-43m','-43m','-43m','-43m','-43m','m-3m','m-3m','m-3m','m-3m','m-3m','m-3m','m-3m','m-3m','m-3m','m-3m','m-3m','m-3m','m-3m','m-3m']

		""" LaueGroup Symbols, there are 530 items in this list """
		self.LaueGroup = ['-1','-1','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m',
		'2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m',
		'2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m',
		'2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m',
		'2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','2/m','mmm','mmm','mmm','mmm','mmm',
		'mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm',
		'mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm',
		'mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm',
		'mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm',
		'mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm',
		'mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm',
		'mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm',
		'mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm',
		'mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm',
		'mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm','mmm',
		'mmm','mmm','mmm','mmm','mmm','mmm','4/m','4/m','4/m','4/m','4/m','4/m','4/m','4/m','4/m','4/m','4/m','4/m','4/m','4/m','4/m','4/m','4/m',
		'4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm',
		'4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm',
		'4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm',
		'4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','4/mmm','-3','-3','-3','-3','-3','-3',
		'-3','-3','-31m','-3m1','-31m','-3m1','-31m','-3m1','-3m1','-3m','-3m1','-31m','-3m1','-31m','-3m1','-3m','-3m1','-3m','-31m','-31m',
		'-3m1','-3m1','-3m1','-3m','-3m1','-3m','6/m','6/m','6/m','6/m','6/m','6/m','6/m','6/m','6/m','6/mmm','6/mmm','6/mmm','6/mmm','6/mmm',
		'6/mmm','6/mmm','6/mmm','6/mmm','6/mmm','6/mmm','6/mmm','6/mmm','6/mmm','6/mmm','6/mmm','6/mmm','6/mmm','m-3','m-3','m-3','m-3','m-3',
		'm-3','m-3','m-3','m-3','m-3','m-3','m-3','m-3','m-3','m-3m','m-3m','m-3m','m-3m','m-3m','m-3m','m-3m','m-3m','m-3m','m-3m','m-3m',
		'm-3m','m-3m','m-3m','m-3m','m-3m','m-3m','m-3m','m-3m','m-3m','m-3m','m-3m','m-3m','m-3m','m-3m','m-3m','m-3m','m-3m']

		""" Schoenflies Symbols, there are 530 items in this list """
		self.Schoenflies = ['C1^1','Ci^1','C2^1','C2^1','C2^1','C2^2','C2^2','C2^2','C2^3','C2^3','C2^3','C2^3','C2^3','C2^3','C2^3','C2^3','C2^3',
		'Cs^1','Cs^1','Cs^1','Cs^2','Cs^2','Cs^2','Cs^2','Cs^2','Cs^2','Cs^2','Cs^2','Cs^2','Cs^3','Cs^3','Cs^3','Cs^3','Cs^3','Cs^3','Cs^3','Cs^3',
		'Cs^3','Cs^4','Cs^4','Cs^4','Cs^4','Cs^4','Cs^4','Cs^4','Cs^4','Cs^4','Cs^4','Cs^4','Cs^4','Cs^4','Cs^4','Cs^4','Cs^4','Cs^4','Cs^4','C2h^1',
		'C2h^1','C2h^1','C2h^2','C2h^2','C2h^2','C2h^3','C2h^3','C2h^3','C2h^3','C2h^3','C2h^3','C2h^3','C2h^3','C2h^3','C2h^4','C2h^4','C2h^4',
		'C2h^4','C2h^4','C2h^4','C2h^4','C2h^4','C2h^4','C2h^5','C2h^5','C2h^5','C2h^5','C2h^5','C2h^5','C2h^5','C2h^5','C2h^5','C2h^6','C2h^6',
		'C2h^6','C2h^6','C2h^6','C2h^6','C2h^6','C2h^6','C2h^6','C2h^6','C2h^6','C2h^6','C2h^6','C2h^6','C2h^6','C2h^6','C2h^6','C2h^6','D2^1',
		'D2^2','D2^2','D2^2','D2^3','D2^3','D2^3','D2^4','D2^5','D2^5','D2^5','D2^6','D2^6','D2^6','D2^7','D2^8','D2^9','C2v^1','C2v^1','C2v^1',
		'C2v^2','C2v^2','C2v^2','C2v^2','C2v^2','C2v^2','C2v^3','C2v^3','C2v^3','C2v^4','C2v^4','C2v^4','C2v^4','C2v^4','C2v^4','C2v^5','C2v^5',
		'C2v^5','C2v^5','C2v^5','C2v^5','C2v^6','C2v^6','C2v^6','C2v^6','C2v^6','C2v^6','C2v^7','C2v^7','C2v^7','C2v^7','C2v^7','C2v^7','C2v^8',
		'C2v^8','C2v^8','C2v^9','C2v^9','C2v^9','C2v^9','C2v^9','C2v^9','C2v^10','C2v^10','C2v^10','C2v^11','C2v^11','C2v^11','C2v^12','C2v^12',
		'C2v^12','C2v^12','C2v^12','C2v^12','C2v^13','C2v^13','C2v^13','C2v^14','C2v^14','C2v^14','C2v^14','C2v^14','C2v^14','C2v^15','C2v^15',
		'C2v^15','C2v^15','C2v^15','C2v^15','C2v^16','C2v^16','C2v^16','C2v^16','C2v^16','C2v^16','C2v^17','C2v^17','C2v^17','C2v^17','C2v^17',
		'C2v^17','C2v^18','C2v^18','C2v^18','C2v^19','C2v^19','C2v^19','C2v^20','C2v^20','C2v^20','C2v^21','C2v^21','C2v^21','C2v^22','C2v^22',
		'C2v^22','C2v^22','C2v^22','C2v^22','D2h^1','D2h^2','D2h^2','D2h^3','D2h^3','D2h^3','D2h^4','D2h^4','D2h^4','D2h^4','D2h^4','D2h^4',
		'D2h^5','D2h^5','D2h^5','D2h^5','D2h^5','D2h^5','D2h^6','D2h^6','D2h^6','D2h^6','D2h^6','D2h^6','D2h^7','D2h^7','D2h^7','D2h^7','D2h^7',
		'D2h^7','D2h^8','D2h^8','D2h^8','D2h^8','D2h^8','D2h^8','D2h^9','D2h^9','D2h^9','D2h^10','D2h^10','D2h^10','D2h^11','D2h^11','D2h^11',
		'D2h^11','D2h^11','D2h^11','D2h^12','D2h^12','D2h^12','D2h^13','D2h^13','D2h^13','D2h^13','D2h^13','D2h^13','D2h^14','D2h^14','D2h^14',
		'D2h^14','D2h^14','D2h^14','D2h^15','D2h^15','D2h^16','D2h^16','D2h^16','D2h^16','D2h^16','D2h^16','D2h^17','D2h^17','D2h^17','D2h^17',
		'D2h^17','D2h^17','D2h^18','D2h^18','D2h^18','D2h^18','D2h^18','D2h^18','D2h^19','D2h^19','D2h^19','D2h^20','D2h^20','D2h^20','D2h^21',
		'D2h^21','D2h^21','D2h^21','D2h^21','D2h^21','D2h^22','D2h^22','D2h^22','D2h^22','D2h^22','D2h^22','D2h^22','D2h^22','D2h^22','D2h^22',
		'D2h^22','D2h^22','D2h^23','D2h^24','D2h^24','D2h^25','D2h^26','D2h^26','D2h^26','D2h^27','D2h^27','D2h^28','D2h^28','D2h^28','D2h^28',
		'D2h^28','D2h^28','C4^1','C4^2','C4^3','C4^4','C4^5','C4^6','S4^1','S4^2','C4h^1','C4h^2','C4h^3','C4h^3','C4h^4','C4h^4','C4h^5',
		'C4h^6','C4h^6','D4^1','D4^2','D4^3','D4^4','D4^5','D4^6','D4^7','D4^8','D4^9','D4^10','C4v^1','C4v^2','C4v^3','C4v^4','C4v^5','C4v^6',
		'C4v^7','C4v^8','C4v^9','C4v^10','C4v^11','C4v^12','D2d^1','D2d^2','D2d^3','D2d^4','D2d^5','D2d^6','D2d^7','D2d^8','D2d^9','D2d^10',
		'D2d^11','D2d^12','D4h^1','D4h^2','D4h^3','D4h^3','D4h^4','D4h^4','D4h^5','D4h^6','D4h^7','D4h^7','D4h^8','D4h^8','D4h^9','D4h^10',
		'D4h^11','D4h^11','D4h^12','D4h^12','D4h^13','D4h^14','D4h^15','D4h^15','D4h^16','D4h^16','D4h^17','D4h^18','D4h^19','D4h^19','D4h^20',
		'D4h^20','C3^1','C3^2','C3^3','C3^4','C3^4','C3i^1','C3i^2','C3i^2','D3^1','D3^2','D3^3','D3^4','D3^5','D3^6','D3^7','D3^7','C3v^1',
		'C3v^2','C3v^3','C3v^4','C3v^5','C3v^5','C3v^6','C3v^6','D3d^1','D3d^2','D3d^3','D3d^4','D3d^5','D3d^5','D3d^6','D3d^6','C6^1','C6^2',
		'C6^3','C6^4','C6^5','C6^6','C3h^1','C6h^1','C6h^2','D6^1','D6^2','D6^3','D6^4','D6^5','D6^6','C6v^1','C6v^2','C6v^3','C6v^4','D3h^1',
		'D3h^2','D3h^3','D3h^4','D6h^1','D6h^2','D6h^3','D6h^4','T^1','T^2','T^3','T^4','T^5','Th^1','Th^2','Th^2','Th^3','Th^4','Th^4','Th^5',
		'Th^6','Th^7','O^1','O^2','O^3','O^4','O^5','O^6','O^7','O^8','Td^1','Td^2','Td^3','Td^4','Td^5','Td^6','Oh^1','Oh^2','Oh^2','Oh^3',
		'Oh^4','Oh^4','Oh^5','Oh^6','Oh^7','Oh^7','Oh^8','Oh^8','Oh^9','Oh^10']

		self.SystemIDs['Triclinic'] = [1,2]				# [1-2], these are IDnums, not SG
		self.SystemIDs['Monoclinic'] = range(3,108)		# [3-107]
		self.SystemIDs['Orthorhombic'] = range(108,349)	# [108-348]
		self.SystemIDs['Tetragonal'] = range(349,430)	# [349-429]
		self.SystemIDs['Trigonal'] = range(430,462)		# [430-461]
		self.SystemIDs['Hexagonal'] = range(462,489)	# [462-488]
		self.SystemIDs['Cubic'] = range(489,531)		# [489-530]

		return None


	def FindWyckoffSymbol1(self, id,x,y,z):
		"""
		NOTE, this does NOT test the symmetry equivalent positions of (x,y,z)
		This returns a tuple:  (Wyckoff symbol, mult, siteSymmetry)
		"""
		WyckList = self.GetWyckoffSymList(id)
		isOsapphire = abs(x-0.3523) <= 1e-4
		if isOsapphire: print ("\n\nO in Sapphire (rhomb)     @@@@@@@@")
		xyz = (x,y,z)
		for item in WyckList:
			if isOsapphire: print ("\nitem =",item,"   xyz=",x,y,z)		#@@@@@@@@@@
			OK = True
			for op,val in zip(item[1],xyz):
				op = op.replace('x',str(float(x)))
				op = op.replace('y',str(float(y)))
				op = op.replace('z',str(float(z)))
				if isOsapphire: print ("op =",op)		#@@@@@@@@@@
				try:	OK = OK and (abs(val-eval(op)) < MIN_FRACTIONAL_DIST)
				except:	OK = False

			if OK: return (item[0],item[2],item[3])	# returns (Wyckoff symbol, mult, siteSymmetry)
		raise ValueError('Cannot find wyckoff symbol corresponding to xyz={%r, %r, %r} for Space Group %r' % (x,y,z,id))


	def ForceFractionalToWyckoff(self, id,symbol,x0,y0,z0):
		WyckList = self.GetWyckoffSymList(id)
		for item in WyckList:
			if item[0] == symbol: break
		if not(item[0] == symbol): return None

		out = tuple()
		for op in item[1]:
			op = op.replace('x',str(float(x0)))
			op = op.replace('y',str(float(y0)))
			op = op.replace('z',str(float(z0)))
			out += (eval(op),)

		return out


	def GetWyckoffSymList(self, id):
		"""
		id is either the space group number or the space group id (a string)
		"""
		if type(id) is int:	id = self.FindDefaultIDforSG(id)	# an int was passed
		try:	id = str(id)
		except:	ValueError('SG = %r is not supported, SG can only be a valid id of the %d 3D Space Groups' % (id,self.MaxIDnum))

		# id is now probably a valid id string
		if   id=='1': WyckList = [('a',('x','y','z'),1,'1')]
		elif id=='2': WyckList = [('a',('0','0','0'),1,'-1'),('b',('0','0','1./2.'),1,'-1'),('c',('0','1./2.','0'),1,'-1'),('d',('1./2.','0','0'),1,'-1'),('e',('1./2.','1./2.','0'),1,'-1'),('f',('1./2.','0','1./2.'),1,'-1'),('g',('0','1./2.','1./2.'),1,'-1'),('h',('1./2.','1./2.','1./2.'),1,'-1'),('i',('x','y','z'),2,'1')]
		elif id=='3:b': WyckList = [('a',('0','y','0'),1,'2'),('b',('0','y','1./2.'),1,'2'),('c',('1./2.','y','0'),1,'2'),('d',('1./2.','y','1./2.'),1,'2'),('e',('x','y','z'),2,'1')]
		elif id=='3:c': WyckList = [('a',('0','0','y'),1,'2'),('b',('1./2.','0','y'),1,'2'),('c',('0','1./2.','y'),1,'2'),('d',('1./2.','1./2.','y'),1,'2'),('e',('x','y','z'),2,'1')]
		elif id=='3:a': WyckList = [('a',('y','0','0'),1,'2'),('b',('y','1./2.','0'),1,'2'),('c',('y','0','1./2.'),1,'2'),('d',('y','1./2.','1./2.'),1,'2'),('e',('x','y','z'),2,'1')]
		elif id=='4:b': WyckList = [('a',('x','y','z'),2,'1')]
		elif id=='4:c': WyckList = [('a',('x','y','z'),2,'1')]
		elif id=='4:a': WyckList = [('a',('x','y','z'),2,'1')]
		elif id=='5:b1': WyckList = [('a',('0','y','0'),2,'2'),('b',('0','y','1./2.'),2,'2'),('c',('x','y','z'),4,'1')]
		elif id=='5:b2': WyckList = [('a',('0','y','0'),2,'2'),('b',('1./2.','y','1./2.'),2,'2'),('c',('x','y','z'),4,'1')]
		elif id=='5:b3': WyckList = [('a',('0','y','0'),2,'2'),('b',('1./2.','y','0'),2,'2'),('c',('x','y','z'),4,'1')]
		elif id=='5:c1': WyckList = [('a',('0','0','y'),2,'2'),('b',('1./2.','0','y'),2,'2'),('c',('x','y','z'),4,'1')]
		elif id=='5:c2': WyckList = [('a',('0','0','y'),2,'2'),('b',('1./2.','1./2.','y'),2,'2'),('c',('x','y','z'),4,'1')]
		elif id=='5:c3': WyckList = [('a',('0','0','y'),2,'2'),('b',('0','1./2.','y'),2,'2'),('c',('x','y','z'),4,'1')]
		elif id=='5:a1': WyckList = [('a',('y','0','0'),2,'2'),('b',('y','1./2.','0'),2,'2'),('c',('x','y','z'),4,'1')]
		elif id=='5:a2': WyckList = [('a',('y','0','0'),2,'2'),('b',('y','1./2.','1./2.'),2,'2'),('c',('x','y','z'),4,'1')]
		elif id=='5:a3': WyckList = [('a',('y','0','0'),2,'2'),('b',('y','0','1./2.'),2,'2'),('c',('x','y','z'),4,'1')]
		elif id=='6:b': WyckList = [('a',('x','0','z'),1,'m'),('b',('x','1./2.','z'),1,'m'),('c',('x','y','z'),2,'1')]
		elif id=='6:c': WyckList = [('a',('z','x','0'),1,'m'),('b',('z','x','1./2.'),1,'m'),('c',('x','y','z'),2,'1')]
		elif id=='6:a': WyckList = [('a',('0','z','x'),1,'m'),('b',('1./2.','z','x'),1,'m'),('c',('x','y','z'),2,'1')]
		elif id=='7:b1': WyckList = [('a',('x','y','z'),2,'1')]
		elif id=='7:b2': WyckList = [('a',('x','y','z'),2,'1')]
		elif id=='7:b3': WyckList = [('a',('x','y','z'),2,'1')]
		elif id=='7:c1': WyckList = [('a',('x','y','z'),2,'1')]
		elif id=='7:c2': WyckList = [('a',('x','y','z'),2,'1')]
		elif id=='7:c3': WyckList = [('a',('x','y','z'),2,'1')]
		elif id=='7:a1': WyckList = [('a',('x','y','z'),2,'1')]
		elif id=='7:a2': WyckList = [('a',('x','y','z'),2,'1')]
		elif id=='7:a3': WyckList = [('a',('x','y','z'),2,'1')]
		elif id=='8:b1': WyckList = [('a',('x','0','z'),2,'m'),('b',('x','y','z'),4,'1')]
		elif id=='8:b2': WyckList = [('a',('-z','0','x-z'),2,'m'),('b',('x','y','z'),4,'1')]
		elif id=='8:b3': WyckList = [('a',('-x+z','0','-x'),2,'m'),('b',('x','y','z'),4,'1')]
		elif id=='8:c1': WyckList = [('a',('z','x','0'),2,'m'),('b',('x','y','z'),4,'1')]
		elif id=='8:c2': WyckList = [('a',('x-z','-z','0'),2,'m'),('b',('x','y','z'),4,'1')]
		elif id=='8:c3': WyckList = [('a',('-x','-x+z','0'),2,'m'),('b',('x','y','z'),4,'1')]
		elif id=='8:a1': WyckList = [('a',('0','z','x'),2,'m'),('b',('x','y','z'),4,'1')]
		elif id=='8:a2': WyckList = [('a',('0','x-z','-z'),2,'m'),('b',('x','y','z'),4,'1')]
		elif id=='8:a3': WyckList = [('a',('0','-x','-x+z'),2,'m'),('b',('x','y','z'),4,'1')]
		elif id=='9:b1': WyckList = [('a',('x','y','z'),4,'1')]
		elif id=='9:b2': WyckList = [('a',('x','y','z'),4,'1')]
		elif id=='9:b3': WyckList = [('a',('x','y','z'),4,'1')]
		elif id=='9:-b1': WyckList = [('a',('x','y','z'),4,'1')]
		elif id=='9:-b2': WyckList = [('a',('x','y','z'),4,'1')]
		elif id=='9:-b3': WyckList = [('a',('x','y','z'),4,'1')]
		elif id=='9:c1': WyckList = [('a',('x','y','z'),4,'1')]
		elif id=='9:c2': WyckList = [('a',('x','y','z'),4,'1')]
		elif id=='9:c3': WyckList = [('a',('x','y','z'),4,'1')]
		elif id=='9:-c1': WyckList = [('a',('x','y','z'),4,'1')]
		elif id=='9:-c2': WyckList = [('a',('x','y','z'),4,'1')]
		elif id=='9:-c3': WyckList = [('a',('x','y','z'),4,'1')]
		elif id=='9:a1': WyckList = [('a',('x','y','z'),4,'1')]
		elif id=='9:a2': WyckList = [('a',('x','y','z'),4,'1')]
		elif id=='9:a3': WyckList = [('a',('x','y','z'),4,'1')]
		elif id=='9:-a1': WyckList = [('a',('x','y','z'),4,'1')]
		elif id=='9:-a2': WyckList = [('a',('x','y','z'),4,'1')]
		elif id=='9:-a3': WyckList = [('a',('x','y','z'),4,'1')]
		elif id=='10:b': WyckList = [('a',('0','0','0'),1,'2/m'),('b',('0','1./2.','0'),1,'2/m'),('c',('0','0','1./2.'),1,'2/m'),('d',('1./2.','0','0'),1,'2/m'),('e',('1./2.','1./2.','0'),1,'2/m'),('f',('0','1./2.','1./2.'),1,'2/m'),('g',('1./2.','0','1./2.'),1,'2/m'),('h',('1./2.','1./2.','1./2.'),1,'2/m'),('i',('0','y','0'),2,'2'),('j',('1./2.','y','0'),2,'2'),('k',('0','y','1./2.'),2,'2'),('l',('1./2.','y','1./2.'),2,'2'),('m',('x','0','z'),2,'m'),('n',('x','1./2.','z'),2,'m'),('o',('x','y','z'),4,'1')]
		elif id=='10:c': WyckList = [('a',('0','0','0'),1,'2/m'),('b',('0','0','1./2.'),1,'2/m'),('c',('1./2.','0','0'),1,'2/m'),('d',('0','1./2.','0'),1,'2/m'),('e',('0','1./2.','1./2.'),1,'2/m'),('f',('1./2.','0','1./2.'),1,'2/m'),('g',('1./2.','1./2.','0'),1,'2/m'),('h',('1./2.','1./2.','1./2.'),1,'2/m'),('i',('0','0','y'),2,'2'),('j',('0','1./2.','y'),2,'2'),('k',('1./2.','0','y'),2,'2'),('l',('1./2.','1./2.','y'),2,'2'),('m',('z','x','0'),2,'m'),('n',('z','x','1./2.'),2,'m'),('o',('x','y','z'),4,'1')]
		elif id=='10:a': WyckList = [('a',('0','0','0'),1,'2/m'),('b',('1./2.','0','0'),1,'2/m'),('c',('0','1./2.','0'),1,'2/m'),('d',('0','0','1./2.'),1,'2/m'),('e',('1./2.','0','1./2.'),1,'2/m'),('f',('1./2.','1./2.','0'),1,'2/m'),('g',('0','1./2.','1./2.'),1,'2/m'),('h',('1./2.','1./2.','1./2.'),1,'2/m'),('i',('y','0','0'),2,'2'),('j',('y','0','1./2.'),2,'2'),('k',('y','1./2.','0'),2,'2'),('l',('y','1./2.','1./2.'),2,'2'),('m',('0','z','x'),2,'m'),('n',('1./2.','z','x'),2,'m'),('o',('x','y','z'),4,'1')]
		elif id=='11:b': WyckList = [('a',('0','0','0'),2,'-1'),('b',('1./2.','0','0'),2,'-1'),('c',('0','0','1./2.'),2,'-1'),('d',('1./2.','0','1./2.'),2,'-1'),('e',('x','1./4.','z'),2,'m'),('f',('x','y','z'),4,'1')]
		elif id=='11:c': WyckList = [('a',('0','0','0'),2,'-1'),('b',('0','1./2.','0'),2,'-1'),('c',('1./2.','0','0'),2,'-1'),('d',('1./2.','1./2.','0'),2,'-1'),('e',('z','x','1./4.'),2,'m'),('f',('x','y','z'),4,'1')]
		elif id=='11:a': WyckList = [('a',('0','0','0'),2,'-1'),('b',('0','0','1./2.'),2,'-1'),('c',('0','1./2.','0'),2,'-1'),('d',('0','1./2.','1./2.'),2,'-1'),('e',('1./4.','z','x'),2,'m'),('f',('x','y','z'),4,'1')]
		elif id=='12:b1': WyckList = [('a',('0','0','0'),2,'2/m'),('b',('0','1./2.','0'),2,'2/m'),('c',('0','0','1./2.'),2,'2/m'),('d',('0','1./2.','1./2.'),2,'2/m'),('e',('1./4.','1./4.','0'),4,'-1'),('f',('1./4.','1./4.','1./2.'),4,'-1'),('g',('0','y','0'),4,'2'),('h',('0','y','1./2.'),4,'2'),('i',('x','0','z'),4,'m'),('j',('x','y','z'),8,'1')]
		elif id=='12:b2': WyckList = [('a',('0','0','0'),2,'2/m'),('b',('0','1./2.','0'),2,'2/m'),('c',('1./2.','0','1./2.'),2,'2/m'),('d',('1./2.','1./2.','1./2.'),2,'2/m'),('e',('0','1./4.','1./4.'),4,'-1'),('f',('1./2.','1./4.','3./4.'),4,'-1'),('g',('0','y','0'),4,'2'),('h',('1./2.','y','1./2.'),4,'2'),('i',('-z','0','x-z'),4,'m'),('j',('x','y','z'),8,'1')]
		elif id=='12:b3': WyckList = [('a',('0','0','0'),2,'2/m'),('b',('0','1./2.','0'),2,'2/m'),('c',('1./2.','0','0'),2,'2/m'),('d',('1./2.','1./2.','0'),2,'2/m'),('e',('3./4.','1./4.','3./4.'),4,'-1'),('f',('1./4.','1./4.','3./4.'),4,'-1'),('g',('0','y','0'),4,'2'),('h',('1./2.','y','0'),4,'2'),('i',('-x+z','0','-x'),4,'m'),('j',('x','y','z'),8,'1')]
		elif id=='12:c1': WyckList = [('a',('0','0','0'),2,'2/m'),('b',('0','0','1./2.'),2,'2/m'),('c',('1./2.','0','0'),2,'2/m'),('d',('1./2.','0','1./2.'),2,'2/m'),('e',('0','1./4.','1./4.'),4,'-1'),('f',('1./2.','1./4.','1./4.'),4,'-1'),('g',('0','0','y'),4,'2'),('h',('1./2.','0','y'),4,'2'),('i',('z','x','0'),4,'m'),('j',('x','y','z'),8,'1')]
		elif id=='12:c2': WyckList = [('a',('0','0','0'),2,'2/m'),('b',('0','0','1./2.'),2,'2/m'),('c',('1./2.','1./2.','0'),2,'2/m'),('d',('1./2.','1./2.','1./2.'),2,'2/m'),('e',('1./4.','0','1./4.'),4,'-1'),('f',('3./4.','1./2.','1./4.'),4,'-1'),('g',('0','0','y'),4,'2'),('h',('1./2.','1./2.','y'),4,'2'),('i',('x-z','-z','0'),4,'m'),('j',('x','y','z'),8,'1')]
		elif id=='12:c3': WyckList = [('a',('0','0','0'),2,'2/m'),('b',('0','0','1./2.'),2,'2/m'),('c',('0','1./2.','0'),2,'2/m'),('d',('0','1./2.','1./2.'),2,'2/m'),('e',('3./4.','3./4.','1./4.'),4,'-1'),('f',('3./4.','1./4.','1./4.'),4,'-1'),('g',('0','0','y'),4,'2'),('h',('0','1./2.','y'),4,'2'),('i',('-x','-x+z','0'),4,'m'),('j',('x','y','z'),8,'1')]
		elif id=='12:a1': WyckList = [('a',('0','0','0'),2,'2/m'),('b',('1./2.','0','0'),2,'2/m'),('c',('0','1./2.','0'),2,'2/m'),('d',('1./2.','1./2.','0'),2,'2/m'),('e',('1./4.','0','1./4.'),4,'-1'),('f',('1./4.','1./2.','1./4.'),4,'-1'),('g',('y','0','0'),4,'2'),('h',('y','1./2.','0'),4,'2'),('i',('0','z','x'),4,'m'),('j',('x','y','z'),8,'1')]
		elif id=='12:a2': WyckList = [('a',('0','0','0'),2,'2/m'),('b',('1./2.','0','0'),2,'2/m'),('c',('0','1./2.','1./2.'),2,'2/m'),('d',('1./2.','1./2.','1./2.'),2,'2/m'),('e',('1./4.','1./4.','0'),4,'-1'),('f',('1./4.','3./4.','1./2.'),4,'-1'),('g',('y','0','0'),4,'2'),('h',('y','1./2.','1./2.'),4,'2'),('i',('0','x-z','-z'),4,'m'),('j',('x','y','z'),8,'1')]
		elif id=='12:a3': WyckList = [('a',('0','0','0'),2,'2/m'),('b',('1./2.','0','0'),2,'2/m'),('c',('0','0','1./2.'),2,'2/m'),('d',('1./2.','0','1./2.'),2,'2/m'),('e',('1./4.','3./4.','3./4.'),4,'-1'),('f',('1./4.','3./4.','1./4.'),4,'-1'),('g',('y','0','0'),4,'2'),('h',('y','0','1./2.'),4,'2'),('i',('0','-x','-x+z'),4,'m'),('j',('x','y','z'),8,'1')]
		elif id=='13:b1': WyckList = [('a',('0','0','0'),2,'-1'),('b',('1./2.','1./2.','0'),2,'-1'),('c',('0','1./2.','0'),2,'-1'),('d',('1./2.','0','0'),2,'-1'),('e',('0','y','1./4.'),2,'2'),('f',('1./2.','y','1./4.'),2,'2'),('g',('x','y','z'),4,'1')]
		elif id=='13:b2': WyckList = [('a',('0','0','0'),2,'-1'),('b',('0','1./2.','1./2.'),2,'-1'),('c',('0','1./2.','0'),2,'-1'),('d',('0','0','1./2.'),2,'-1'),('e',('3./4.','y','3./4.'),2,'2'),('f',('3./4.','y','1./4.'),2,'2'),('g',('x','y','z'),4,'1')]
		elif id=='13:b3': WyckList = [('a',('0','0','0'),2,'-1'),('b',('1./2.','1./2.','1./2.'),2,'-1'),('c',('0','1./2.','0'),2,'-1'),('d',('1./2.','0','1./2.'),2,'-1'),('e',('1./4.','y','0'),2,'2'),('f',('3./4.','y','1./2.'),2,'2'),('g',('x','y','z'),4,'1')]
		elif id=='13:c1': WyckList = [('a',('0','0','0'),2,'-1'),('b',('0','1./2.','1./2.'),2,'-1'),('c',('0','0','1./2.'),2,'-1'),('d',('0','1./2.','0'),2,'-1'),('e',('1./4.','0','y'),2,'2'),('f',('1./4.','1./2.','y'),2,'2'),('g',('x','y','z'),4,'1')]
		elif id=='13:c2': WyckList = [('a',('0','0','0'),2,'-1'),('b',('1./2.','0','1./2.'),2,'-1'),('c',('0','0','1./2.'),2,'-1'),('d',('1./2.','0','0'),2,'-1'),('e',('3./4.','3./4.','y'),2,'2'),('f',('1./4.','3./4.','y'),2,'2'),('g',('x','y','z'),4,'1')]
		elif id=='13:c3': WyckList = [('a',('0','0','0'),2,'-1'),('b',('1./2.','1./2.','1./2.'),2,'-1'),('c',('0','0','1./2.'),2,'-1'),('d',('1./2.','1./2.','0'),2,'-1'),('e',('0','1./4.','y'),2,'2'),('f',('1./2.','3./4.','y'),2,'2'),('g',('x','y','z'),4,'1')]
		elif id=='13:a1': WyckList = [('a',('0','0','0'),2,'-1'),('b',('1./2.','0','1./2.'),2,'-1'),('c',('1./2.','0','0'),2,'-1'),('d',('0','0','1./2.'),2,'-1'),('e',('y','1./4.','0'),2,'2'),('f',('y','1./4.','1./2.'),2,'2'),('g',('x','y','z'),4,'1')]
		elif id=='13:a2': WyckList = [('a',('0','0','0'),2,'-1'),('b',('1./2.','1./2.','0'),2,'-1'),('c',('1./2.','0','0'),2,'-1'),('d',('0','1./2.','0'),2,'-1'),('e',('y','3./4.','3./4.'),2,'2'),('f',('y','1./4.','3./4.'),2,'2'),('g',('x','y','z'),4,'1')]
		elif id=='13:a3': WyckList = [('a',('0','0','0'),2,'-1'),('b',('1./2.','1./2.','1./2.'),2,'-1'),('c',('1./2.','0','0'),2,'-1'),('d',('0','1./2.','1./2.'),2,'-1'),('e',('y','0','1./4.'),2,'2'),('f',('y','1./2.','3./4.'),2,'2'),('g',('x','y','z'),4,'1')]
		elif id=='14:b1': WyckList = [('a',('0','0','0'),2,'-1'),('b',('1./2.','0','0'),2,'-1'),('c',('0','0','1./2.'),2,'-1'),('d',('1./2.','0','1./2.'),2,'-1'),('e',('x','y','z'),4,'1')]
		elif id=='14:b2': WyckList = [('a',('0','0','0'),2,'-1'),('b',('0','0','1./2.'),2,'-1'),('c',('1./2.','0','1./2.'),2,'-1'),('d',('1./2.','0','0'),2,'-1'),('e',('x','y','z'),4,'1')]
		elif id=='14:b3': WyckList = [('a',('0','0','0'),2,'-1'),('b',('1./2.','0','1./2.'),2,'-1'),('c',('1./2.','0','0'),2,'-1'),('d',('0','0','1./2.'),2,'-1'),('e',('x','y','z'),4,'1')]
		elif id=='14:c1': WyckList = [('a',('0','0','0'),2,'-1'),('b',('0','1./2.','0'),2,'-1'),('c',('1./2.','0','0'),2,'-1'),('d',('1./2.','1./2.','0'),2,'-1'),('e',('x','y','z'),4,'1')]
		elif id=='14:c2': WyckList = [('a',('0','0','0'),2,'-1'),('b',('1./2.','0','0'),2,'-1'),('c',('1./2.','1./2.','0'),2,'-1'),('d',('0','1./2.','0'),2,'-1'),('e',('x','y','z'),4,'1')]
		elif id=='14:c3': WyckList = [('a',('0','0','0'),2,'-1'),('b',('1./2.','1./2.','0'),2,'-1'),('c',('0','1./2.','0'),2,'-1'),('d',('1./2.','0','0'),2,'-1'),('e',('x','y','z'),4,'1')]
		elif id=='14:a1': WyckList = [('a',('0','0','0'),2,'-1'),('b',('0','0','1./2.'),2,'-1'),('c',('0','1./2.','0'),2,'-1'),('d',('0','1./2.','1./2.'),2,'-1'),('e',('x','y','z'),4,'1')]
		elif id=='14:a2': WyckList = [('a',('0','0','0'),2,'-1'),('b',('0','1./2.','0'),2,'-1'),('c',('0','1./2.','1./2.'),2,'-1'),('d',('0','0','1./2.'),2,'-1'),('e',('x','y','z'),4,'1')]
		elif id=='14:a3': WyckList = [('a',('0','0','0'),2,'-1'),('b',('0','1./2.','1./2.'),2,'-1'),('c',('0','0','1./2.'),2,'-1'),('d',('0','1./2.','0'),2,'-1'),('e',('x','y','z'),4,'1')]
		elif id=='15:b1': WyckList = [('a',('0','0','0'),4,'-1'),('b',('0','1./2.','0'),4,'-1'),('c',('1./4.','1./4.','0'),4,'-1'),('d',('1./4.','1./4.','1./2.'),4,'-1'),('e',('0','y','1./4.'),4,'2'),('f',('x','y','z'),8,'1')]
		elif id=='15:b2': WyckList = [('a',('0','0','0'),4,'-1'),('b',('0','1./2.','0'),4,'-1'),('c',('0','1./4.','1./4.'),4,'-1'),('d',('1./2.','1./4.','3./4.'),4,'-1'),('e',('3./4.','y','3./4.'),4,'2'),('f',('x','y','z'),8,'1')]
		elif id=='15:b3': WyckList = [('a',('0','0','0'),4,'-1'),('b',('0','1./2.','0'),4,'-1'),('c',('3./4.','1./4.','3./4.'),4,'-1'),('d',('1./4.','1./4.','3./4.'),4,'-1'),('e',('1./4.','y','0'),4,'2'),('f',('x','y','z'),8,'1')]
		elif id=='15:-b1': WyckList = [('a',('0','3./4.','1./4.'),4,'-1'),('b',('0','1./4.','1./4.'),4,'-1'),('c',('0','0','1./2.'),4,'-1'),('d',('1./2.','0','0'),4,'-1'),('e',('3./4.','y-1./4.','0'),4,'2'),('f',('x','y','z'),8,'1')]
		elif id=='15:-b2': WyckList = [('a',('3./4.','3./4.','0'),4,'-1'),('b',('3./4.','1./4.','0'),4,'-1'),('c',('0','0','0'),4,'-1'),('d',('0','0','1./2.'),4,'-1'),('e',('3./4.','y-1./4.','1./4.'),4,'2'),('f',('x','y','z'),8,'1')]
		elif id=='15:-b3': WyckList = [('a',('3./4.','3./4.','3./4.'),4,'-1'),('b',('3./4.','1./4.','3./4.'),4,'-1'),('c',('1./2.','0','1./2.'),4,'-1'),('d',('0','0','1./2.'),4,'-1'),('e',('0','y-1./4.','3./4.'),4,'2'),('f',('x','y','z'),8,'1')]
		elif id=='15:c1': WyckList = [('a',('0','0','0'),4,'-1'),('b',('0','0','1./2.'),4,'-1'),('c',('0','1./4.','1./4.'),4,'-1'),('d',('1./2.','1./4.','1./4.'),4,'-1'),('e',('1./4.','0','y'),4,'2'),('f',('x','y','z'),8,'1')]
		elif id=='15:c2': WyckList = [('a',('0','0','0'),4,'-1'),('b',('0','0','1./2.'),4,'-1'),('c',('1./4.','0','1./4.'),4,'-1'),('d',('3./4.','1./2.','1./4.'),4,'-1'),('e',('3./4.','3./4.','y'),4,'2'),('f',('x','y','z'),8,'1')]
		elif id=='15:c3': WyckList = [('a',('0','0','0'),4,'-1'),('b',('0','0','1./2.'),4,'-1'),('c',('3./4.','3./4.','1./4.'),4,'-1'),('d',('3./4.','1./4.','1./4.'),4,'-1'),('e',('0','1./4.','y'),4,'2'),('f',('x','y','z'),8,'1')]
		elif id=='15:-c1': WyckList = [('a',('1./4.','0','3./4.'),4,'-1'),('b',('1./4.','0','1./4.'),4,'-1'),('c',('1./2.','0','0'),4,'-1'),('d',('0','1./2.','0'),4,'-1'),('e',('0','3./4.','y-1./4.'),4,'2'),('f',('x','y','z'),8,'1')]
		elif id=='15:-c2': WyckList = [('a',('0','3./4.','3./4.'),4,'-1'),('b',('0','3./4.','1./4.'),4,'-1'),('c',('0','0','0'),4,'-1'),('d',('1./2.','0','0'),4,'-1'),('e',('1./4.','3./4.','y-1./4.'),4,'2'),('f',('x','y','z'),8,'1')]
		elif id=='15:-c3': WyckList = [('a',('3./4.','3./4.','3./4.'),4,'-1'),('b',('3./4.','3./4.','1./4.'),4,'-1'),('c',('1./2.','1./2.','0'),4,'-1'),('d',('1./2.','0','0'),4,'-1'),('e',('3./4.','0','y-1./4.'),4,'2'),('f',('x','y','z'),8,'1')]
		elif id=='15:a1': WyckList = [('a',('0','0','0'),4,'-1'),('b',('1./2.','0','0'),4,'-1'),('c',('1./4.','0','1./4.'),4,'-1'),('d',('1./4.','1./2.','1./4.'),4,'-1'),('e',('y','1./4.','0'),4,'2'),('f',('x','y','z'),8,'1')]
		elif id=='15:a2': WyckList = [('a',('0','0','0'),4,'-1'),('b',('1./2.','0','0'),4,'-1'),('c',('1./4.','1./4.','0'),4,'-1'),('d',('1./4.','3./4.','1./2.'),4,'-1'),('e',('y','3./4.','3./4.'),4,'2'),('f',('x','y','z'),8,'1')]
		elif id=='15:a3': WyckList = [('a',('0','0','0'),4,'-1'),('b',('1./2.','0','0'),4,'-1'),('c',('1./4.','3./4.','3./4.'),4,'-1'),('d',('1./4.','3./4.','1./4.'),4,'-1'),('e',('y','0','1./4.'),4,'2'),('f',('x','y','z'),8,'1')]
		elif id=='15:-a1': WyckList = [('a',('3./4.','1./4.','0'),4,'-1'),('b',('1./4.','1./4.','0'),4,'-1'),('c',('0','1./2.','0'),4,'-1'),('d',('0','0','1./2.'),4,'-1'),('e',('y-1./4.','0','3./4.'),4,'2'),('f',('x','y','z'),8,'1')]
		elif id=='15:-a2': WyckList = [('a',('3./4.','0','1./4.'),4,'-1'),('b',('1./4.','0','1./4.'),4,'-1'),('c',('0','0','1./2.'),4,'-1'),('d',('0','1./2.','1./2.'),4,'-1'),('e',('y-1./4.','1./4.','1./4.'),4,'2'),('f',('x','y','z'),8,'1')]
		elif id=='15:-a3': WyckList = [('a',('3./4.','3./4.','3./4.'),4,'-1'),('b',('1./4.','3./4.','3./4.'),4,'-1'),('c',('0','1./2.','1./2.'),4,'-1'),('d',('0','1./2.','0'),4,'-1'),('e',('y-1./4.','3./4.','0'),4,'2'),('f',('x','y','z'),8,'1')]
		elif id=='16': WyckList = [('a',('0','0','0'),1,'222'),('b',('1./2.','0','0'),1,'222'),('c',('0','1./2.','0'),1,'222'),('d',('0','0','1./2.'),1,'222'),('e',('1./2.','1./2.','0'),1,'222'),('f',('1./2.','0','1./2.'),1,'222'),('g',('0','1./2.','1./2.'),1,'222'),('h',('1./2.','1./2.','1./2.'),1,'222'),('i',('x','0','0'),2,'2..'),('j',('x','0','1./2.'),2,'2..'),('k',('x','1./2.','0'),2,'2..'),('l',('x','1./2.','1./2.'),2,'2..'),('m',('0','y','0'),2,'.2.'),('n',('0','y','1./2.'),2,'.2.'),('o',('1./2.','y','0'),2,'.2.'),('p',('1./2.','y','1./2.'),2,'.2.'),('q',('0','0','z'),2,'..2'),('r',('1./2.','0','z'),2,'..2'),('s',('0','1./2.','z'),2,'..2'),('t',('1./2.','1./2.','z'),2,'..2'),('u',('x','y','z'),4,'1')]
		elif id=='17': WyckList = [('a',('x','0','0'),2,'2..'),('b',('x','1./2.','0'),2,'2..'),('c',('0','y','1./4.'),2,'.2.'),('d',('1./2.','y','1./4.'),2,'.2.'),('e',('x','y','z'),4,'1')]
		elif id=='17:cab': WyckList = [('a',('0','x','0'),2,'2..'),('b',('0','x','1./2.'),2,'2..'),('c',('1./4.','0','y'),2,'.2.'),('d',('1./4.','1./2.','y'),2,'.2.'),('e',('x','y','z'),4,'1')]
		elif id=='17:bca': WyckList = [('a',('0','0','x'),2,'2..'),('b',('1./2.','0','x'),2,'2..'),('c',('y','1./4.','0'),2,'.2.'),('d',('y','1./4.','1./2.'),2,'.2.'),('e',('x','y','z'),4,'1')]
		elif id=='18': WyckList = [('a',('0','0','z'),2,'..2'),('b',('0','1./2.','z'),2,'..2'),('c',('x','y','z'),4,'1')]
		elif id=='18:cab': WyckList = [('a',('z','0','0'),2,'..2'),('b',('z','0','1./2.'),2,'..2'),('c',('x','y','z'),4,'1')]
		elif id=='18:bca': WyckList = [('a',('0','z','0'),2,'..2'),('b',('1./2.','z','0'),2,'..2'),('c',('x','y','z'),4,'1')]
		elif id=='19': WyckList = [('a',('x','y','z'),4,'1')]
		elif id=='20': WyckList = [('a',('x','0','0'),4,'2..'),('b',('0','y','1./4.'),4,'.2.'),('c',('x','y','z'),8,'1')]
		elif id=='20:cab': WyckList = [('a',('0','x','0'),4,'2..'),('b',('1./4.','0','y'),4,'.2.'),('c',('x','y','z'),8,'1')]
		elif id=='20:bca': WyckList = [('a',('0','0','x'),4,'2..'),('b',('y','1./4.','0'),4,'.2.'),('c',('x','y','z'),8,'1')]
		elif id=='21': WyckList = [('a',('0','0','0'),2,'222'),('b',('0','1./2.','0'),2,'222'),('c',('1./2.','0','1./2.'),2,'222'),('d',('0','0','1./2.'),2,'222'),('e',('x','0','0'),4,'2..'),('f',('x','0','1./2.'),4,'2..'),('g',('0','y','0'),4,'.2.'),('h',('0','y','1./2.'),4,'.2.'),('i',('0','0','z'),4,'..2'),('j',('0','1./2.','z'),4,'..2'),('k',('1./4.','1./4.','z'),4,'..2'),('l',('x','y','z'),8,'1')]
		elif id=='21:cab': WyckList = [('a',('0','0','0'),2,'222'),('b',('0','0','1./2.'),2,'222'),('c',('1./2.','1./2.','0'),2,'222'),('d',('1./2.','0','0'),2,'222'),('e',('0','x','0'),4,'2..'),('f',('1./2.','x','0'),4,'2..'),('g',('0','0','y'),4,'.2.'),('h',('1./2.','0','y'),4,'.2.'),('i',('z','0','0'),4,'..2'),('j',('z','0','1./2.'),4,'..2'),('k',('z','1./4.','1./4.'),4,'..2'),('l',('x','y','z'),8,'1')]
		elif id=='21:bca': WyckList = [('a',('0','0','0'),2,'222'),('b',('1./2.','0','0'),2,'222'),('c',('0','1./2.','1./2.'),2,'222'),('d',('0','1./2.','0'),2,'222'),('e',('0','0','x'),4,'2..'),('f',('0','1./2.','x'),4,'2..'),('g',('y','0','0'),4,'.2.'),('h',('y','1./2.','0'),4,'.2.'),('i',('0','z','0'),4,'..2'),('j',('1./2.','z','0'),4,'..2'),('k',('1./4.','z','1./4.'),4,'..2'),('l',('x','y','z'),8,'1')]
		elif id=='22': WyckList = [('a',('0','0','0'),4,'222'),('b',('0','0','1./2.'),4,'222'),('c',('1./4.','1./4.','1./4.'),4,'222'),('d',('1./4.','1./4.','3./4.'),4,'222'),('e',('x','0','0'),8,'2..'),('f',('0','y','0'),8,'.2.'),('g',('0','0','z'),8,'..2'),('h',('1./4.','1./4.','z'),8,'..2'),('i',('1./4.','y','1./4.'),8,'.2.'),('j',('x','1./4.','1./4.'),8,'2..'),('k',('x','y','z'),16,'1')]
		elif id=='23': WyckList = [('a',('0','0','0'),2,'222'),('b',('1./2.','0','0'),2,'222'),('c',('0','0','1./2.'),2,'222'),('d',('0','1./2.','0'),2,'222'),('e',('x','0','0'),4,'2..'),('f',('x','0','1./2.'),4,'2..'),('g',('0','y','0'),4,'.2.'),('h',('1./2.','y','0'),4,'.2.'),('i',('0','0','z'),4,'..2'),('j',('0','1./2.','z'),4,'..2'),('k',('x','y','z'),8,'1')]
		elif id=='24': WyckList = [('a',('x','0','1./4.'),4,'2..'),('b',('1./4.','y','0'),4,'.2.'),('c',('0','1./4.','z'),4,'..2'),('d',('x','y','z'),8,'1')]
		elif id=='25': WyckList = [('a',('0','0','z'),1,'mm2'),('b',('0','1./2.','z'),1,'mm2'),('c',('1./2.','0','z'),1,'mm2'),('d',('1./2.','1./2.','z'),1,'mm2'),('e',('x','0','z'),2,'.m.'),('f',('x','1./2.','z'),2,'.m.'),('g',('0','y','z'),2,'m..'),('h',('1./2.','y','z'),2,'m..'),('i',('x','y','z'),4,'1')]
		elif id=='25:cab': WyckList = [('a',('z','0','0'),1,'mm2'),('b',('z','0','1./2.'),1,'mm2'),('c',('z','1./2.','0'),1,'mm2'),('d',('z','1./2.','1./2.'),1,'mm2'),('e',('z','x','0'),2,'.m.'),('f',('z','x','1./2.'),2,'.m.'),('g',('z','0','y'),2,'m..'),('h',('z','1./2.','y'),2,'m..'),('i',('x','y','z'),4,'1')]
		elif id=='25:bca': WyckList = [('a',('0','z','0'),1,'mm2'),('b',('1./2.','z','0'),1,'mm2'),('c',('0','z','1./2.'),1,'mm2'),('d',('1./2.','z','1./2.'),1,'mm2'),('e',('0','z','x'),2,'.m.'),('f',('1./2.','z','x'),2,'.m.'),('g',('y','z','0'),2,'m..'),('h',('y','z','1./2.'),2,'m..'),('i',('x','y','z'),4,'1')]
		elif id=='26': WyckList = [('a',('0','y','z'),2,'m..'),('b',('1./2.','y','z'),2,'m..'),('c',('x','y','z'),4,'1')]
		elif id=='26:ba-c': WyckList = [('a',('y','0','-z'),2,'m..'),('b',('y','1./2.','-z'),2,'m..'),('c',('x','y','z'),4,'1')]
		elif id=='26:cab': WyckList = [('a',('z','0','y'),2,'m..'),('b',('z','1./2.','y'),2,'m..'),('c',('x','y','z'),4,'1')]
		elif id=='26:-cba': WyckList = [('a',('-z','y','0'),2,'m..'),('b',('-z','y','1./2.'),2,'m..'),('c',('x','y','z'),4,'1')]
		elif id=='26:bca': WyckList = [('a',('y','z','0'),2,'m..'),('b',('y','z','1./2.'),2,'m..'),('c',('x','y','z'),4,'1')]
		elif id=='26:a-cb': WyckList = [('a',('0','-z','y'),2,'m..'),('b',('1./2.','-z','y'),2,'m..'),('c',('x','y','z'),4,'1')]
		elif id=='27': WyckList = [('a',('0','0','z'),2,'..2'),('b',('0','1./2.','z'),2,'..2'),('c',('1./2.','0','z'),2,'..2'),('d',('1./2.','1./2.','z'),2,'..2'),('e',('x','y','z'),4,'1')]
		elif id=='27:cab': WyckList = [('a',('z','0','0'),2,'..2'),('b',('z','0','1./2.'),2,'..2'),('c',('z','1./2.','0'),2,'..2'),('d',('z','1./2.','1./2.'),2,'..2'),('e',('x','y','z'),4,'1')]
		elif id=='27:bca': WyckList = [('a',('0','z','0'),2,'..2'),('b',('1./2.','z','0'),2,'..2'),('c',('0','z','1./2.'),2,'..2'),('d',('1./2.','z','1./2.'),2,'..2'),('e',('x','y','z'),4,'1')]
		elif id=='28': WyckList = [('a',('0','0','z'),2,'..2'),('b',('0','1./2.','z'),2,'..2'),('c',('1./4.','y','z'),2,'m..'),('d',('x','y','z'),4,'1')]
		elif id=='28:ba-c': WyckList = [('a',('0','0','-z'),2,'..2'),('b',('1./2.','0','-z'),2,'..2'),('c',('y','1./4.','-z'),2,'m..'),('d',('x','y','z'),4,'1')]
		elif id=='28:cab': WyckList = [('a',('z','0','0'),2,'..2'),('b',('z','0','1./2.'),2,'..2'),('c',('z','1./4.','y'),2,'m..'),('d',('x','y','z'),4,'1')]
		elif id=='28:-cba': WyckList = [('a',('-z','0','0'),2,'..2'),('b',('-z','1./2.','0'),2,'..2'),('c',('-z','y','1./4.'),2,'m..'),('d',('x','y','z'),4,'1')]
		elif id=='28:bca': WyckList = [('a',('0','z','0'),2,'..2'),('b',('1./2.','z','0'),2,'..2'),('c',('y','z','1./4.'),2,'m..'),('d',('x','y','z'),4,'1')]
		elif id=='28:a-cb': WyckList = [('a',('0','-z','0'),2,'..2'),('b',('0','-z','1./2.'),2,'..2'),('c',('1./4.','-z','y'),2,'m..'),('d',('x','y','z'),4,'1')]
		elif id=='29': WyckList = [('a',('x','y','z'),4,'1')]
		elif id=='29:ba-c': WyckList = [('a',('x','y','z'),4,'1')]
		elif id=='29:cab': WyckList = [('a',('x','y','z'),4,'1')]
		elif id=='29:-cba': WyckList = [('a',('x','y','z'),4,'1')]
		elif id=='29:bca': WyckList = [('a',('x','y','z'),4,'1')]
		elif id=='29:a-cb': WyckList = [('a',('x','y','z'),4,'1')]
		elif id=='30': WyckList = [('a',('0','0','z'),2,'..2'),('b',('1./2.','0','z'),2,'..2'),('c',('x','y','z'),4,'1')]
		elif id=='30:ba-c': WyckList = [('a',('0','0','-z'),2,'..2'),('b',('0','1./2.','-z'),2,'..2'),('c',('x','y','z'),4,'1')]
		elif id=='30:cab': WyckList = [('a',('z','0','0'),2,'..2'),('b',('z','1./2.','0'),2,'..2'),('c',('x','y','z'),4,'1')]
		elif id=='30:-cba': WyckList = [('a',('-z','0','0'),2,'..2'),('b',('-z','0','1./2.'),2,'..2'),('c',('x','y','z'),4,'1')]
		elif id=='30:bca': WyckList = [('a',('0','z','0'),2,'..2'),('b',('0','z','1./2.'),2,'..2'),('c',('x','y','z'),4,'1')]
		elif id=='30:a-cb': WyckList = [('a',('0','-z','0'),2,'..2'),('b',('1./2.','-z','0'),2,'..2'),('c',('x','y','z'),4,'1')]
		elif id=='31': WyckList = [('a',('0','y','z'),2,'m..'),('b',('x','y','z'),4,'1')]
		elif id=='31:ba-c': WyckList = [('a',('y','0','-z'),2,'m..'),('b',('x','y','z'),4,'1')]
		elif id=='31:cab': WyckList = [('a',('z','0','y'),2,'m..'),('b',('x','y','z'),4,'1')]
		elif id=='31:-cba': WyckList = [('a',('-z','y','0'),2,'m..'),('b',('x','y','z'),4,'1')]
		elif id=='31:bca': WyckList = [('a',('y','z','0'),2,'m..'),('b',('x','y','z'),4,'1')]
		elif id=='31:a-cb': WyckList = [('a',('0','-z','y'),2,'m..'),('b',('x','y','z'),4,'1')]
		elif id=='32': WyckList = [('a',('0','0','z'),2,'..2'),('b',('0','1./2.','z'),2,'..2'),('c',('x','y','z'),4,'1')]
		elif id=='32:cab': WyckList = [('a',('z','0','0'),2,'..2'),('b',('z','0','1./2.'),2,'..2'),('c',('x','y','z'),4,'1')]
		elif id=='32:bca': WyckList = [('a',('0','z','0'),2,'..2'),('b',('1./2.','z','0'),2,'..2'),('c',('x','y','z'),4,'1')]
		elif id=='33': WyckList = [('a',('x','y','z'),4,'1')]
		elif id=='33:ba-c': WyckList = [('a',('x','y','z'),4,'1')]
		elif id=='33:cab': WyckList = [('a',('x','y','z'),4,'1')]
		elif id=='33:-cba': WyckList = [('a',('x','y','z'),4,'1')]
		elif id=='33:bca': WyckList = [('a',('x','y','z'),4,'1')]
		elif id=='33:a-cb': WyckList = [('a',('x','y','z'),4,'1')]
		elif id=='34': WyckList = [('a',('0','0','z'),2,'..2'),('b',('0','1./2.','z'),2,'..2'),('c',('x','y','z'),4,'1')]
		elif id=='34:cab': WyckList = [('a',('z','0','0'),2,'..2'),('b',('z','0','1./2.'),2,'..2'),('c',('x','y','z'),4,'1')]
		elif id=='34:bca': WyckList = [('a',('0','z','0'),2,'..2'),('b',('1./2.','z','0'),2,'..2'),('c',('x','y','z'),4,'1')]
		elif id=='35': WyckList = [('a',('0','0','z'),2,'mm2'),('b',('0','1./2.','z'),2,'mm2'),('c',('1./4.','1./4.','z'),4,'..2'),('d',('x','0','z'),4,'.m.'),('e',('0','y','z'),4,'m..'),('f',('x','y','z'),8,'1')]
		elif id=='35:cab': WyckList = [('a',('z','0','0'),2,'mm2'),('b',('z','0','1./2.'),2,'mm2'),('c',('z','1./4.','1./4.'),4,'..2'),('d',('z','x','0'),4,'.m.'),('e',('z','0','y'),4,'m..'),('f',('x','y','z'),8,'1')]
		elif id=='35:bca': WyckList = [('a',('0','z','0'),2,'mm2'),('b',('1./2.','z','0'),2,'mm2'),('c',('1./4.','z','1./4.'),4,'..2'),('d',('0','z','x'),4,'.m.'),('e',('y','z','0'),4,'m..'),('f',('x','y','z'),8,'1')]
		elif id=='36': WyckList = [('a',('0','y','z'),4,'m..'),('b',('x','y','z'),8,'1')]
		elif id=='36:ba-c': WyckList = [('a',('y','0','-z'),4,'m..'),('b',('x','y','z'),8,'1')]
		elif id=='36:cab': WyckList = [('a',('z','0','y'),4,'m..'),('b',('x','y','z'),8,'1')]
		elif id=='36:-cba': WyckList = [('a',('-z','y','0'),4,'m..'),('b',('x','y','z'),8,'1')]
		elif id=='36:bca': WyckList = [('a',('y','z','0'),4,'m..'),('b',('x','y','z'),8,'1')]
		elif id=='36:a-cb': WyckList = [('a',('0','-z','y'),4,'m..'),('b',('x','y','z'),8,'1')]
		elif id=='37': WyckList = [('a',('0','0','z'),4,'..2'),('b',('0','1./2.','z'),4,'..2'),('c',('1./4.','1./4.','z'),4,'..2'),('d',('x','y','z'),8,'1')]
		elif id=='37:cab': WyckList = [('a',('z','0','0'),4,'..2'),('b',('z','0','1./2.'),4,'..2'),('c',('z','1./4.','1./4.'),4,'..2'),('d',('x','y','z'),8,'1')]
		elif id=='37:bca': WyckList = [('a',('0','z','0'),4,'..2'),('b',('1./2.','z','0'),4,'..2'),('c',('1./4.','z','1./4.'),4,'..2'),('d',('x','y','z'),8,'1')]
		elif id=='38': WyckList = [('a',('0','0','z'),2,'mm2'),('b',('1./2.','0','z'),2,'mm2'),('c',('x','0','z'),4,'.m.'),('d',('0','y','z'),4,'m..'),('e',('1./2.','y','z'),4,'m..'),('f',('x','y','z'),8,'1')]
		elif id=='38:ba-c': WyckList = [('a',('0','0','-z'),2,'mm2'),('b',('0','1./2.','-z'),2,'mm2'),('c',('0','x','-z'),4,'.m.'),('d',('y','0','-z'),4,'m..'),('e',('y','1./2.','-z'),4,'m..'),('f',('x','y','z'),8,'1')]
		elif id=='38:cab': WyckList = [('a',('z','0','0'),2,'mm2'),('b',('z','1./2.','0'),2,'mm2'),('c',('z','x','0'),4,'.m.'),('d',('z','0','y'),4,'m..'),('e',('z','1./2.','y'),4,'m..'),('f',('x','y','z'),8,'1')]
		elif id=='38:-cba': WyckList = [('a',('-z','0','0'),2,'mm2'),('b',('-z','0','1./2.'),2,'mm2'),('c',('-z','0','x'),4,'.m.'),('d',('-z','y','0'),4,'m..'),('e',('-z','y','1./2.'),4,'m..'),('f',('x','y','z'),8,'1')]
		elif id=='38:bca': WyckList = [('a',('0','z','0'),2,'mm2'),('b',('0','z','1./2.'),2,'mm2'),('c',('0','z','x'),4,'.m.'),('d',('y','z','0'),4,'m..'),('e',('y','z','1./2.'),4,'m..'),('f',('x','y','z'),8,'1')]
		elif id=='38:a-cb': WyckList = [('a',('0','-z','0'),2,'mm2'),('b',('1./2.','-z','0'),2,'mm2'),('c',('x','-z','0'),4,'.m.'),('d',('0','-z','y'),4,'m..'),('e',('1./2.','-z','y'),4,'m..'),('f',('x','y','z'),8,'1')]
		elif id=='39': WyckList = [('a',('0','0','z'),4,'..2'),('b',('1./2.','0','z'),4,'..2'),('c',('x','1./4.','z'),4,'.m.'),('d',('x','y','z'),8,'1')]
		elif id=='39:ba-c': WyckList = [('a',('0','0','-z'),4,'..2'),('b',('0','1./2.','-z'),4,'..2'),('c',('1./4.','x','-z'),4,'.m.'),('d',('x','y','z'),8,'1')]
		elif id=='39:cab': WyckList = [('a',('z','0','0'),4,'..2'),('b',('z','1./2.','0'),4,'..2'),('c',('z','x','1./4.'),4,'.m.'),('d',('x','y','z'),8,'1')]
		elif id=='39:-cba': WyckList = [('a',('-z','0','0'),4,'..2'),('b',('-z','0','1./2.'),4,'..2'),('c',('-z','1./4.','x'),4,'.m.'),('d',('x','y','z'),8,'1')]
		elif id=='39:bca': WyckList = [('a',('0','z','0'),4,'..2'),('b',('0','z','1./2.'),4,'..2'),('c',('1./4.','z','x'),4,'.m.'),('d',('x','y','z'),8,'1')]
		elif id=='39:a-cb': WyckList = [('a',('0','-z','0'),4,'..2'),('b',('1./2.','-z','0'),4,'..2'),('c',('x','-z','1./4.'),4,'.m.'),('d',('x','y','z'),8,'1')]
		elif id=='40': WyckList = [('a',('0','0','z'),4,'..2'),('b',('1./4.','y','z'),4,'m..'),('c',('x','y','z'),8,'1')]
		elif id=='40:ba-c': WyckList = [('a',('0','0','-z'),4,'..2'),('b',('y','1./4.','-z'),4,'m..'),('c',('x','y','z'),8,'1')]
		elif id=='40:cab': WyckList = [('a',('z','0','0'),4,'..2'),('b',('z','1./4.','y'),4,'m..'),('c',('x','y','z'),8,'1')]
		elif id=='40:-cba': WyckList = [('a',('-z','0','0'),4,'..2'),('b',('-z','y','1./4.'),4,'m..'),('c',('x','y','z'),8,'1')]
		elif id=='40:bca': WyckList = [('a',('0','z','0'),4,'..2'),('b',('y','z','1./4.'),4,'m..'),('c',('x','y','z'),8,'1')]
		elif id=='40:a-cb': WyckList = [('a',('0','-z','0'),4,'..2'),('b',('1./4.','-z','y'),4,'m..'),('c',('x','y','z'),8,'1')]
		elif id=='41': WyckList = [('a',('0','0','z'),4,'..2'),('b',('x','y','z'),8,'1')]
		elif id=='41:ba-c': WyckList = [('a',('0','0','-z'),4,'..2'),('b',('x','y','z'),8,'1')]
		elif id=='41:cab': WyckList = [('a',('z','0','0'),4,'..2'),('b',('x','y','z'),8,'1')]
		elif id=='41:-cba': WyckList = [('a',('-z','0','0'),4,'..2'),('b',('x','y','z'),8,'1')]
		elif id=='41:bca': WyckList = [('a',('0','z','0'),4,'..2'),('b',('x','y','z'),8,'1')]
		elif id=='41:a-cb': WyckList = [('a',('0','-z','0'),4,'..2'),('b',('x','y','z'),8,'1')]
		elif id=='42': WyckList = [('a',('0','0','z'),4,'mm2'),('b',('1./4.','1./4.','z'),8,'..2'),('c',('0','y','z'),8,'m..'),('d',('x','0','z'),8,'.m.'),('e',('x','y','z'),16,'1')]
		elif id=='42:cab': WyckList = [('a',('z','0','0'),4,'mm2'),('b',('z','1./4.','1./4.'),8,'..2'),('c',('z','0','y'),8,'m..'),('d',('z','x','0'),8,'.m.'),('e',('x','y','z'),16,'1')]
		elif id=='42:bca': WyckList = [('a',('0','z','0'),4,'mm2'),('b',('1./4.','z','1./4.'),8,'..2'),('c',('y','z','0'),8,'m..'),('d',('0','z','x'),8,'.m.'),('e',('x','y','z'),16,'1')]
		elif id=='43': WyckList = [('a',('0','0','z'),8,'..2'),('b',('x','y','z'),16,'1')]
		elif id=='43:cab': WyckList = [('a',('z','0','0'),8,'..2'),('b',('x','y','z'),16,'1')]
		elif id=='43:bca': WyckList = [('a',('0','z','0'),8,'..2'),('b',('x','y','z'),16,'1')]
		elif id=='44': WyckList = [('a',('0','0','z'),2,'mm2'),('b',('0','1./2.','z'),2,'mm2'),('c',('x','0','z'),4,'.m.'),('d',('0','y','z'),4,'m..'),('e',('x','y','z'),8,'1')]
		elif id=='44:cab': WyckList = [('a',('z','0','0'),2,'mm2'),('b',('z','0','1./2.'),2,'mm2'),('c',('z','x','0'),4,'.m.'),('d',('z','0','y'),4,'m..'),('e',('x','y','z'),8,'1')]
		elif id=='44:bca': WyckList = [('a',('0','z','0'),2,'mm2'),('b',('1./2.','z','0'),2,'mm2'),('c',('0','z','x'),4,'.m.'),('d',('y','z','0'),4,'m..'),('e',('x','y','z'),8,'1')]
		elif id=='45': WyckList = [('a',('0','0','z'),4,'..2'),('b',('0','1./2.','z'),4,'..2'),('c',('x','y','z'),8,'1')]
		elif id=='45:cab': WyckList = [('a',('z','0','0'),4,'..2'),('b',('z','0','1./2.'),4,'..2'),('c',('x','y','z'),8,'1')]
		elif id=='45:bca': WyckList = [('a',('0','z','0'),4,'..2'),('b',('1./2.','z','0'),4,'..2'),('c',('x','y','z'),8,'1')]
		elif id=='46': WyckList = [('a',('0','0','z'),4,'..2'),('b',('1./4.','y','z'),4,'m..'),('c',('x','y','z'),8,'1')]
		elif id=='46:ba-c': WyckList = [('a',('0','0','-z'),4,'..2'),('b',('y','1./4.','-z'),4,'m..'),('c',('x','y','z'),8,'1')]
		elif id=='46:cab': WyckList = [('a',('z','0','0'),4,'..2'),('b',('z','1./4.','y'),4,'m..'),('c',('x','y','z'),8,'1')]
		elif id=='46:-cba': WyckList = [('a',('-z','0','0'),4,'..2'),('b',('-z','y','1./4.'),4,'m..'),('c',('x','y','z'),8,'1')]
		elif id=='46:bca': WyckList = [('a',('0','z','0'),4,'..2'),('b',('y','z','1./4.'),4,'m..'),('c',('x','y','z'),8,'1')]
		elif id=='46:a-cb': WyckList = [('a',('0','-z','0'),4,'..2'),('b',('1./4.','-z','y'),4,'m..'),('c',('x','y','z'),8,'1')]
		elif id=='47': WyckList = [('a',('0','0','0'),1,'mmm'),('b',('1./2.','0','0'),1,'mmm'),('c',('0','0','1./2.'),1,'mmm'),('d',('1./2.','0','1./2.'),1,'mmm'),('e',('0','1./2.','0'),1,'mmm'),('f',('1./2.','1./2.','0'),1,'mmm'),('g',('0','1./2.','1./2.'),1,'mmm'),('h',('1./2.','1./2.','1./2.'),1,'mmm'),('i',('x','0','0'),2,'2mm'),('j',('x','0','1./2.'),2,'2mm'),('k',('x','1./2.','0'),2,'2mm'),('l',('x','1./2.','1./2.'),2,'2mm'),('m',('0','y','0'),2,'m2m'),('n',('0','y','1./2.'),2,'m2m'),('o',('1./2.','y','0'),2,'m2m'),('p',('1./2.','y','1./2.'),2,'m2m'),('q',('0','0','z'),2,'mm2'),('r',('0','1./2.','z'),2,'mm2'),('s',('1./2.','0','z'),2,'mm2'),('t',('1./2.','1./2.','z'),2,'mm2'),('u',('0','y','z'),4,'m..'),('v',('1./2.','y','z'),4,'m..'),('w',('x','0','z'),4,'.m.'),('x',('x','1./2.','z'),4,'.m.'),('y',('x','y','0'),4,'..m'),('z',('x','y','1./2.'),4,'..m'),('A',('x','y','z'),8,'1')]
		elif id=='48:1': WyckList = [('a',('0','0','0'),2,'222'),('b',('1./2.','0','0'),2,'222'),('c',('0','0','1./2.'),2,'222'),('d',('0','1./2.','0'),2,'222'),('e',('1./4.','1./4.','1./4.'),4,'-1'),('f',('3./4.','3./4.','3./4.'),4,'-1'),('g',('x','0','0'),4,'2..'),('h',('x','0','1./2.'),4,'2..'),('i',('0','y','0'),4,'.2.'),('j',('1./2.','y','0'),4,'.2.'),('k',('0','0','z'),4,'..2'),('l',('0','1./2.','z'),4,'..2'),('m',('x','y','z'),8,'1')]
		elif id=='48:2': WyckList = [('a',('1./4.','1./4.','1./4.'),2,'222'),('b',('3./4.','1./4.','1./4.'),2,'222'),('c',('1./4.','1./4.','3./4.'),2,'222'),('d',('1./4.','3./4.','1./4.'),2,'222'),('e',('1./2.','1./2.','1./2.'),4,'-1'),('f',('0','0','0'),4,'-1'),('g',('x+1./4.','1./4.','1./4.'),4,'2..'),('h',('x+1./4.','1./4.','3./4.'),4,'2..'),('i',('1./4.','y+1./4.','1./4.'),4,'.2.'),('j',('3./4.','y+1./4.','1./4.'),4,'.2.'),('k',('1./4.','1./4.','z+1./4.'),4,'..2'),('l',('1./4.','3./4.','z+1./4.'),4,'..2'),('m',('x','y','z'),8,'1')]
		elif id=='49': WyckList = [('a',('0','0','0'),2,'..2/m'),('b',('1./2.','1./2.','0'),2,'..2/m'),('c',('0','1./2.','0'),2,'..2/m'),('d',('1./2.','0','0'),2,'..2/m'),('e',('0','0','1./4.'),2,'222'),('f',('1./2.','0','1./4.'),2,'222'),('g',('0','1./2.','1./4.'),2,'222'),('h',('1./2.','1./2.','1./4.'),2,'222'),('i',('x','0','1./4.'),4,'2..'),('j',('x','1./2.','1./4.'),4,'2..'),('k',('0','y','1./4.'),4,'.2.'),('l',('1./2.','y','1./4.'),4,'.2.'),('m',('0','0','z'),4,'..2'),('n',('1./2.','1./2.','z'),4,'..2'),('o',('0','1./2.','z'),4,'..2'),('p',('1./2.','0','z'),4,'..2'),('q',('x','y','0'),4,'..m'),('r',('x','y','z'),8,'1')]
		elif id=='49:cab': WyckList = [('a',('0','0','0'),2,'..2/m'),('b',('0','1./2.','1./2.'),2,'..2/m'),('c',('0','0','1./2.'),2,'..2/m'),('d',('0','1./2.','0'),2,'..2/m'),('e',('1./4.','0','0'),2,'222'),('f',('1./4.','1./2.','0'),2,'222'),('g',('1./4.','0','1./2.'),2,'222'),('h',('1./4.','1./2.','1./2.'),2,'222'),('i',('1./4.','x','0'),4,'2..'),('j',('1./4.','x','1./2.'),4,'2..'),('k',('1./4.','0','y'),4,'.2.'),('l',('1./4.','1./2.','y'),4,'.2.'),('m',('z','0','0'),4,'..2'),('n',('z','1./2.','1./2.'),4,'..2'),('o',('z','0','1./2.'),4,'..2'),('p',('z','1./2.','0'),4,'..2'),('q',('0','x','y'),4,'..m'),('r',('x','y','z'),8,'1')]
		elif id=='49:bca': WyckList = [('a',('0','0','0'),2,'..2/m'),('b',('1./2.','0','1./2.'),2,'..2/m'),('c',('1./2.','0','0'),2,'..2/m'),('d',('0','0','1./2.'),2,'..2/m'),('e',('0','1./4.','0'),2,'222'),('f',('0','1./4.','1./2.'),2,'222'),('g',('1./2.','1./4.','0'),2,'222'),('h',('1./2.','1./4.','1./2.'),2,'222'),('i',('0','1./4.','x'),4,'2..'),('j',('1./2.','1./4.','x'),4,'2..'),('k',('y','1./4.','0'),4,'.2.'),('l',('y','1./4.','1./2.'),4,'.2.'),('m',('0','z','0'),4,'..2'),('n',('1./2.','z','1./2.'),4,'..2'),('o',('1./2.','z','0'),4,'..2'),('p',('0','z','1./2.'),4,'..2'),('q',('y','0','x'),4,'..m'),('r',('x','y','z'),8,'1')]
		elif id=='50:1': WyckList = [('a',('0','0','0'),2,'222'),('b',('1./2.','0','0'),2,'222'),('c',('1./2.','0','1./2.'),2,'222'),('d',('0','0','1./2.'),2,'222'),('e',('1./4.','1./4.','0'),4,'-1'),('f',('1./4.','1./4.','1./2.'),4,'-1'),('g',('x','0','0'),4,'2..'),('h',('x','0','1./2.'),4,'2..'),('i',('0','y','0'),4,'.2.'),('j',('0','y','1./2.'),4,'.2.'),('k',('0','0','z'),4,'..2'),('l',('0','1./2.','z'),4,'..2'),('m',('x','y','z'),8,'1')]
		elif id=='50:2': WyckList = [('a',('1./4.','1./4.','0'),2,'222'),('b',('3./4.','1./4.','0'),2,'222'),('c',('3./4.','1./4.','1./2.'),2,'222'),('d',('1./4.','1./4.','1./2.'),2,'222'),('e',('1./2.','1./2.','0'),4,'-1'),('f',('1./2.','1./2.','1./2.'),4,'-1'),('g',('x+1./4.','1./4.','0'),4,'2..'),('h',('x+1./4.','1./4.','1./2.'),4,'2..'),('i',('1./4.','y+1./4.','0'),4,'.2.'),('j',('1./4.','y+1./4.','1./2.'),4,'.2.'),('k',('1./4.','1./4.','z'),4,'..2'),('l',('1./4.','3./4.','z'),4,'..2'),('m',('x','y','z'),8,'1')]
		elif id=='50:1cab': WyckList = [('a',('0','0','0'),2,'222'),('b',('0','1./2.','0'),2,'222'),('c',('1./2.','1./2.','0'),2,'222'),('d',('1./2.','0','0'),2,'222'),('e',('0','1./4.','1./4.'),4,'-1'),('f',('1./2.','1./4.','1./4.'),4,'-1'),('g',('0','x','0'),4,'2..'),('h',('1./2.','x','0'),4,'2..'),('i',('0','0','y'),4,'.2.'),('j',('1./2.','0','y'),4,'.2.'),('k',('z','0','0'),4,'..2'),('l',('z','0','1./2.'),4,'..2'),('m',('x','y','z'),8,'1')]
		elif id=='50:2cab': WyckList = [('a',('0','1./4.','1./4.'),2,'222'),('b',('0','3./4.','1./4.'),2,'222'),('c',('1./2.','3./4.','1./4.'),2,'222'),('d',('1./2.','1./4.','1./4.'),2,'222'),('e',('0','1./2.','1./2.'),4,'-1'),('f',('1./2.','1./2.','1./2.'),4,'-1'),('g',('0','x+1./4.','1./4.'),4,'2..'),('h',('1./2.','x+1./4.','1./4.'),4,'2..'),('i',('0','1./4.','y+1./4.'),4,'.2.'),('j',('1./2.','1./4.','y+1./4.'),4,'.2.'),('k',('z','1./4.','1./4.'),4,'..2'),('l',('z','1./4.','3./4.'),4,'..2'),('m',('x','y','z'),8,'1')]
		elif id=='50:1bca': WyckList = [('a',('0','0','0'),2,'222'),('b',('0','0','1./2.'),2,'222'),('c',('0','1./2.','1./2.'),2,'222'),('d',('0','1./2.','0'),2,'222'),('e',('1./4.','0','1./4.'),4,'-1'),('f',('1./4.','1./2.','1./4.'),4,'-1'),('g',('0','0','x'),4,'2..'),('h',('0','1./2.','x'),4,'2..'),('i',('y','0','0'),4,'.2.'),('j',('y','1./2.','0'),4,'.2.'),('k',('0','z','0'),4,'..2'),('l',('1./2.','z','0'),4,'..2'),('m',('x','y','z'),8,'1')]
		elif id=='50:2bca': WyckList = [('a',('1./4.','0','1./4.'),2,'222'),('b',('1./4.','0','3./4.'),2,'222'),('c',('1./4.','1./2.','3./4.'),2,'222'),('d',('1./4.','1./2.','1./4.'),2,'222'),('e',('1./2.','0','1./2.'),4,'-1'),('f',('1./2.','1./2.','1./2.'),4,'-1'),('g',('1./4.','0','x+1./4.'),4,'2..'),('h',('1./4.','1./2.','x+1./4.'),4,'2..'),('i',('y+1./4.','0','1./4.'),4,'.2.'),('j',('y+1./4.','1./2.','1./4.'),4,'.2.'),('k',('1./4.','z','1./4.'),4,'..2'),('l',('3./4.','z','1./4.'),4,'..2'),('m',('x','y','z'),8,'1')]
		elif id=='51': WyckList = [('a',('0','0','0'),2,'.2/m.'),('b',('0','1./2.','0'),2,'.2/m.'),('c',('0','0','1./2.'),2,'.2/m.'),('d',('0','1./2.','1./2.'),2,'.2/m.'),('e',('1./4.','0','z'),2,'mm2'),('f',('1./4.','1./2.','z'),2,'mm2'),('g',('0','y','0'),4,'.2.'),('h',('0','y','1./2.'),4,'.2.'),('i',('x','0','z'),4,'.m.'),('j',('x','1./2.','z'),4,'.m.'),('k',('1./4.','y','z'),4,'m..'),('l',('x','y','z'),8,'1')]
		elif id=='51:ba-c': WyckList = [('a',('0','0','0'),2,'.2/m.'),('b',('1./2.','0','0'),2,'.2/m.'),('c',('0','0','1./2.'),2,'.2/m.'),('d',('1./2.','0','1./2.'),2,'.2/m.'),('e',('0','1./4.','-z'),2,'mm2'),('f',('1./2.','1./4.','-z'),2,'mm2'),('g',('y','0','0'),4,'.2.'),('h',('y','0','1./2.'),4,'.2.'),('i',('0','x','-z'),4,'.m.'),('j',('1./2.','x','-z'),4,'.m.'),('k',('y','1./4.','-z'),4,'m..'),('l',('x','y','z'),8,'1')]
		elif id=='51:cab': WyckList = [('a',('0','0','0'),2,'.2/m.'),('b',('0','0','1./2.'),2,'.2/m.'),('c',('1./2.','0','0'),2,'.2/m.'),('d',('1./2.','0','1./2.'),2,'.2/m.'),('e',('z','1./4.','0'),2,'mm2'),('f',('z','1./4.','1./2.'),2,'mm2'),('g',('0','0','y'),4,'.2.'),('h',('1./2.','0','y'),4,'.2.'),('i',('z','x','0'),4,'.m.'),('j',('z','x','1./2.'),4,'.m.'),('k',('z','1./4.','y'),4,'m..'),('l',('x','y','z'),8,'1')]
		elif id=='51:-cba': WyckList = [('a',('0','0','0'),2,'.2/m.'),('b',('0','1./2.','0'),2,'.2/m.'),('c',('1./2.','0','0'),2,'.2/m.'),('d',('1./2.','1./2.','0'),2,'.2/m.'),('e',('-z','0','1./4.'),2,'mm2'),('f',('-z','1./2.','1./4.'),2,'mm2'),('g',('0','y','0'),4,'.2.'),('h',('1./2.','y','0'),4,'.2.'),('i',('-z','0','x'),4,'.m.'),('j',('-z','1./2.','x'),4,'.m.'),('k',('-z','y','1./4.'),4,'m..'),('l',('x','y','z'),8,'1')]
		elif id=='51:bca': WyckList = [('a',('0','0','0'),2,'.2/m.'),('b',('1./2.','0','0'),2,'.2/m.'),('c',('0','1./2.','0'),2,'.2/m.'),('d',('1./2.','1./2.','0'),2,'.2/m.'),('e',('0','z','1./4.'),2,'mm2'),('f',('1./2.','z','1./4.'),2,'mm2'),('g',('y','0','0'),4,'.2.'),('h',('y','1./2.','0'),4,'.2.'),('i',('0','z','x'),4,'.m.'),('j',('1./2.','z','x'),4,'.m.'),('k',('y','z','1./4.'),4,'m..'),('l',('x','y','z'),8,'1')]
		elif id=='51:a-cb': WyckList = [('a',('0','0','0'),2,'.2/m.'),('b',('0','0','1./2.'),2,'.2/m.'),('c',('0','1./2.','0'),2,'.2/m.'),('d',('0','1./2.','1./2.'),2,'.2/m.'),('e',('1./4.','-z','0'),2,'mm2'),('f',('1./4.','-z','1./2.'),2,'mm2'),('g',('0','0','y'),4,'.2.'),('h',('0','1./2.','y'),4,'.2.'),('i',('x','-z','0'),4,'.m.'),('j',('x','-z','1./2.'),4,'.m.'),('k',('1./4.','-z','y'),4,'m..'),('l',('x','y','z'),8,'1')]
		elif id=='52': WyckList = [('a',('0','0','0'),4,'-1'),('b',('0','0','1./2.'),4,'-1'),('c',('1./4.','0','z'),4,'..2'),('d',('x','1./4.','1./4.'),4,'2..'),('e',('x','y','z'),8,'1')]
		elif id=='52:ba-c': WyckList = [('a',('0','0','0'),4,'-1'),('b',('0','0','1./2.'),4,'-1'),('c',('0','1./4.','-z'),4,'..2'),('d',('1./4.','x','3./4.'),4,'2..'),('e',('x','y','z'),8,'1')]
		elif id=='52:cab': WyckList = [('a',('0','0','0'),4,'-1'),('b',('1./2.','0','0'),4,'-1'),('c',('z','1./4.','0'),4,'..2'),('d',('1./4.','x','1./4.'),4,'2..'),('e',('x','y','z'),8,'1')]
		elif id=='52:-cba': WyckList = [('a',('0','0','0'),4,'-1'),('b',('1./2.','0','0'),4,'-1'),('c',('-z','0','1./4.'),4,'..2'),('d',('3./4.','1./4.','x'),4,'2..'),('e',('x','y','z'),8,'1')]
		elif id=='52:bca': WyckList = [('a',('0','0','0'),4,'-1'),('b',('0','1./2.','0'),4,'-1'),('c',('0','z','1./4.'),4,'..2'),('d',('1./4.','1./4.','x'),4,'2..'),('e',('x','y','z'),8,'1')]
		elif id=='52:a-cb': WyckList = [('a',('0','0','0'),4,'-1'),('b',('0','1./2.','0'),4,'-1'),('c',('1./4.','-z','0'),4,'..2'),('d',('x','3./4.','1./4.'),4,'2..'),('e',('x','y','z'),8,'1')]
		elif id=='53': WyckList = [('a',('0','0','0'),2,'2/m..'),('b',('1./2.','0','0'),2,'2/m..'),('c',('1./2.','1./2.','0'),2,'2/m..'),('d',('0','1./2.','0'),2,'2/m..'),('e',('x','0','0'),4,'2..'),('f',('x','1./2.','0'),4,'2..'),('g',('1./4.','y','1./4.'),4,'.2.'),('h',('0','y','z'),4,'m..'),('i',('x','y','z'),8,'1')]
		elif id=='53:ba-c': WyckList = [('a',('0','0','0'),2,'2/m..'),('b',('0','1./2.','0'),2,'2/m..'),('c',('1./2.','1./2.','0'),2,'2/m..'),('d',('1./2.','0','0'),2,'2/m..'),('e',('0','x','0'),4,'2..'),('f',('1./2.','x','0'),4,'2..'),('g',('y','1./4.','3./4.'),4,'.2.'),('h',('y','0','-z'),4,'m..'),('i',('x','y','z'),8,'1')]
		elif id=='53:cab': WyckList = [('a',('0','0','0'),2,'2/m..'),('b',('0','1./2.','0'),2,'2/m..'),('c',('0','1./2.','1./2.'),2,'2/m..'),('d',('0','0','1./2.'),2,'2/m..'),('e',('0','x','0'),4,'2..'),('f',('0','x','1./2.'),4,'2..'),('g',('1./4.','1./4.','y'),4,'.2.'),('h',('z','0','y'),4,'m..'),('i',('x','y','z'),8,'1')]
		elif id=='53:-cba': WyckList = [('a',('0','0','0'),2,'2/m..'),('b',('0','0','1./2.'),2,'2/m..'),('c',('0','1./2.','1./2.'),2,'2/m..'),('d',('0','1./2.','0'),2,'2/m..'),('e',('0','0','x'),4,'2..'),('f',('0','1./2.','x'),4,'2..'),('g',('3./4.','y','1./4.'),4,'.2.'),('h',('-z','y','0'),4,'m..'),('i',('x','y','z'),8,'1')]
		elif id=='53:bca': WyckList = [('a',('0','0','0'),2,'2/m..'),('b',('0','0','1./2.'),2,'2/m..'),('c',('1./2.','0','1./2.'),2,'2/m..'),('d',('1./2.','0','0'),2,'2/m..'),('e',('0','0','x'),4,'2..'),('f',('1./2.','0','x'),4,'2..'),('g',('y','1./4.','1./4.'),4,'.2.'),('h',('y','z','0'),4,'m..'),('i',('x','y','z'),8,'1')]
		elif id=='53:a-cb': WyckList = [('a',('0','0','0'),2,'2/m..'),('b',('1./2.','0','0'),2,'2/m..'),('c',('1./2.','0','1./2.'),2,'2/m..'),('d',('0','0','1./2.'),2,'2/m..'),('e',('x','0','0'),4,'2..'),('f',('x','0','1./2.'),4,'2..'),('g',('1./4.','3./4.','y'),4,'.2.'),('h',('0','-z','y'),4,'m..'),('i',('x','y','z'),8,'1')]
		elif id=='54': WyckList = [('a',('0','0','0'),4,'-1'),('b',('0','1./2.','0'),4,'-1'),('c',('0','y','1./4.'),4,'.2.'),('d',('1./4.','0','z'),4,'..2'),('e',('1./4.','1./2.','z'),4,'..2'),('f',('x','y','z'),8,'1')]
		elif id=='54:ba-c': WyckList = [('a',('0','0','0'),4,'-1'),('b',('1./2.','0','0'),4,'-1'),('c',('y','0','3./4.'),4,'.2.'),('d',('0','1./4.','-z'),4,'..2'),('e',('1./2.','1./4.','-z'),4,'..2'),('f',('x','y','z'),8,'1')]
		elif id=='54:cab': WyckList = [('a',('0','0','0'),4,'-1'),('b',('0','0','1./2.'),4,'-1'),('c',('1./4.','0','y'),4,'.2.'),('d',('z','1./4.','0'),4,'..2'),('e',('z','1./4.','1./2.'),4,'..2'),('f',('x','y','z'),8,'1')]
		elif id=='54:-cba': WyckList = [('a',('0','0','0'),4,'-1'),('b',('0','1./2.','0'),4,'-1'),('c',('3./4.','y','0'),4,'.2.'),('d',('-z','0','1./4.'),4,'..2'),('e',('-z','1./2.','1./4.'),4,'..2'),('f',('x','y','z'),8,'1')]
		elif id=='54:bca': WyckList = [('a',('0','0','0'),4,'-1'),('b',('1./2.','0','0'),4,'-1'),('c',('y','1./4.','0'),4,'.2.'),('d',('0','z','1./4.'),4,'..2'),('e',('1./2.','z','1./4.'),4,'..2'),('f',('x','y','z'),8,'1')]
		elif id=='54:a-cb': WyckList = [('a',('0','0','0'),4,'-1'),('b',('0','0','1./2.'),4,'-1'),('c',('0','3./4.','y'),4,'.2.'),('d',('1./4.','-z','0'),4,'..2'),('e',('1./4.','-z','1./2.'),4,'..2'),('f',('x','y','z'),8,'1')]
		elif id=='55': WyckList = [('a',('0','0','0'),2,'..2/m'),('b',('0','0','1./2.'),2,'..2/m'),('c',('0','1./2.','0'),2,'..2/m'),('d',('0','1./2.','1./2.'),2,'..2/m'),('e',('0','0','z'),4,'..2'),('f',('0','1./2.','z'),4,'..2'),('g',('x','y','0'),4,'..m'),('h',('x','y','1./2.'),4,'..m'),('i',('x','y','z'),8,'1')]
		elif id=='55:cab': WyckList = [('a',('0','0','0'),2,'..2/m'),('b',('1./2.','0','0'),2,'..2/m'),('c',('0','0','1./2.'),2,'..2/m'),('d',('1./2.','0','1./2.'),2,'..2/m'),('e',('z','0','0'),4,'..2'),('f',('z','0','1./2.'),4,'..2'),('g',('0','x','y'),4,'..m'),('h',('1./2.','x','y'),4,'..m'),('i',('x','y','z'),8,'1')]
		elif id=='55:bca': WyckList = [('a',('0','0','0'),2,'..2/m'),('b',('0','1./2.','0'),2,'..2/m'),('c',('1./2.','0','0'),2,'..2/m'),('d',('1./2.','1./2.','0'),2,'..2/m'),('e',('0','z','0'),4,'..2'),('f',('1./2.','z','0'),4,'..2'),('g',('y','0','x'),4,'..m'),('h',('y','1./2.','x'),4,'..m'),('i',('x','y','z'),8,'1')]
		elif id=='56': WyckList = [('a',('0','0','0'),4,'-1'),('b',('0','0','1./2.'),4,'-1'),('c',('1./4.','1./4.','z'),4,'..2'),('d',('1./4.','3./4.','z'),4,'..2'),('e',('x','y','z'),8,'1')]
		elif id=='56:cab': WyckList = [('a',('0','0','0'),4,'-1'),('b',('1./2.','0','0'),4,'-1'),('c',('z','1./4.','1./4.'),4,'..2'),('d',('z','1./4.','3./4.'),4,'..2'),('e',('x','y','z'),8,'1')]
		elif id=='56:bca': WyckList = [('a',('0','0','0'),4,'-1'),('b',('0','1./2.','0'),4,'-1'),('c',('1./4.','z','1./4.'),4,'..2'),('d',('3./4.','z','1./4.'),4,'..2'),('e',('x','y','z'),8,'1')]
		elif id=='57': WyckList = [('a',('0','0','0'),4,'-1'),('b',('1./2.','0','0'),4,'-1'),('c',('x','1./4.','0'),4,'2..'),('d',('x','y','1./4.'),4,'..m'),('e',('x','y','z'),8,'1')]
		elif id=='57:ba-c': WyckList = [('a',('0','0','0'),4,'-1'),('b',('0','1./2.','0'),4,'-1'),('c',('1./4.','x','0'),4,'2..'),('d',('y','x','3./4.'),4,'..m'),('e',('x','y','z'),8,'1')]
		elif id=='57:cab': WyckList = [('a',('0','0','0'),4,'-1'),('b',('0','1./2.','0'),4,'-1'),('c',('0','x','1./4.'),4,'2..'),('d',('1./4.','x','y'),4,'..m'),('e',('x','y','z'),8,'1')]
		elif id=='57:-cba': WyckList = [('a',('0','0','0'),4,'-1'),('b',('0','0','1./2.'),4,'-1'),('c',('0','1./4.','x'),4,'2..'),('d',('3./4.','y','x'),4,'..m'),('e',('x','y','z'),8,'1')]
		elif id=='57:bca': WyckList = [('a',('0','0','0'),4,'-1'),('b',('0','0','1./2.'),4,'-1'),('c',('1./4.','0','x'),4,'2..'),('d',('y','1./4.','x'),4,'..m'),('e',('x','y','z'),8,'1')]
		elif id=='57:a-cb': WyckList = [('a',('0','0','0'),4,'-1'),('b',('1./2.','0','0'),4,'-1'),('c',('x','0','1./4.'),4,'2..'),('d',('x','3./4.','y'),4,'..m'),('e',('x','y','z'),8,'1')]
		elif id=='58': WyckList = [('a',('0','0','0'),2,'..2/m'),('b',('0','0','1./2.'),2,'..2/m'),('c',('0','1./2.','0'),2,'..2/m'),('d',('0','1./2.','1./2.'),2,'..2/m'),('e',('0','0','z'),4,'..2'),('f',('0','1./2.','z'),4,'..2'),('g',('x','y','0'),4,'..m'),('h',('x','y','z'),8,'1')]
		elif id=='58:cab': WyckList = [('a',('0','0','0'),2,'..2/m'),('b',('1./2.','0','0'),2,'..2/m'),('c',('0','0','1./2.'),2,'..2/m'),('d',('1./2.','0','1./2.'),2,'..2/m'),('e',('z','0','0'),4,'..2'),('f',('z','0','1./2.'),4,'..2'),('g',('0','x','y'),4,'..m'),('h',('x','y','z'),8,'1')]
		elif id=='58:bca': WyckList = [('a',('0','0','0'),2,'..2/m'),('b',('0','1./2.','0'),2,'..2/m'),('c',('1./2.','0','0'),2,'..2/m'),('d',('1./2.','1./2.','0'),2,'..2/m'),('e',('0','z','0'),4,'..2'),('f',('1./2.','z','0'),4,'..2'),('g',('y','0','x'),4,'..m'),('h',('x','y','z'),8,'1')]
		elif id=='59:1': WyckList = [('a',('0','0','z'),2,'mm2'),('b',('0','1./2.','z'),2,'mm2'),('c',('1./4.','1./4.','0'),4,'-1'),('d',('1./4.','1./4.','1./2.'),4,'-1'),('e',('0','y','z'),4,'m..'),('f',('x','0','z'),4,'.m.'),('g',('x','y','z'),8,'1')]
		elif id=='59:2': WyckList = [('a',('1./4.','1./4.','z'),2,'mm2'),('b',('1./4.','3./4.','z'),2,'mm2'),('c',('1./2.','1./2.','0'),4,'-1'),('d',('1./2.','1./2.','1./2.'),4,'-1'),('e',('1./4.','y+1./4.','z'),4,'m..'),('f',('x+1./4.','1./4.','z'),4,'.m.'),('g',('x','y','z'),8,'1')]
		elif id=='59:1cab': WyckList = [('a',('z','0','0'),2,'mm2'),('b',('z','0','1./2.'),2,'mm2'),('c',('0','1./4.','1./4.'),4,'-1'),('d',('1./2.','1./4.','1./4.'),4,'-1'),('e',('z','0','y'),4,'m..'),('f',('z','x','0'),4,'.m.'),('g',('x','y','z'),8,'1')]
		elif id=='59:2cab': WyckList = [('a',('z','1./4.','1./4.'),2,'mm2'),('b',('z','1./4.','3./4.'),2,'mm2'),('c',('0','1./2.','1./2.'),4,'-1'),('d',('1./2.','1./2.','1./2.'),4,'-1'),('e',('z','1./4.','y+1./4.'),4,'m..'),('f',('z','x+1./4.','1./4.'),4,'.m.'),('g',('x','y','z'),8,'1')]
		elif id=='59:1bca': WyckList = [('a',('0','z','0'),2,'mm2'),('b',('1./2.','z','0'),2,'mm2'),('c',('1./4.','0','1./4.'),4,'-1'),('d',('1./4.','1./2.','1./4.'),4,'-1'),('e',('y','z','0'),4,'m..'),('f',('0','z','x'),4,'.m.'),('g',('x','y','z'),8,'1')]
		elif id=='59:2bca': WyckList = [('a',('1./4.','z','1./4.'),2,'mm2'),('b',('3./4.','z','1./4.'),2,'mm2'),('c',('1./2.','0','1./2.'),4,'-1'),('d',('1./2.','1./2.','1./2.'),4,'-1'),('e',('y+1./4.','z','1./4.'),4,'m..'),('f',('1./4.','z','x+1./4.'),4,'.m.'),('g',('x','y','z'),8,'1')]
		elif id=='60': WyckList = [('a',('0','0','0'),4,'-1'),('b',('0','1./2.','0'),4,'-1'),('c',('0','y','1./4.'),4,'.2.'),('d',('x','y','z'),8,'1')]
		elif id=='60:ba-c': WyckList = [('a',('0','0','0'),4,'-1'),('b',('1./2.','0','0'),4,'-1'),('c',('y','0','3./4.'),4,'.2.'),('d',('x','y','z'),8,'1')]
		elif id=='60:cab': WyckList = [('a',('0','0','0'),4,'-1'),('b',('0','0','1./2.'),4,'-1'),('c',('1./4.','0','y'),4,'.2.'),('d',('x','y','z'),8,'1')]
		elif id=='60:-cba': WyckList = [('a',('0','0','0'),4,'-1'),('b',('0','1./2.','0'),4,'-1'),('c',('3./4.','y','0'),4,'.2.'),('d',('x','y','z'),8,'1')]
		elif id=='60:bca': WyckList = [('a',('0','0','0'),4,'-1'),('b',('1./2.','0','0'),4,'-1'),('c',('y','1./4.','0'),4,'.2.'),('d',('x','y','z'),8,'1')]
		elif id=='60:a-cb': WyckList = [('a',('0','0','0'),4,'-1'),('b',('0','0','1./2.'),4,'-1'),('c',('0','3./4.','y'),4,'.2.'),('d',('x','y','z'),8,'1')]
		elif id=='61': WyckList = [('a',('0','0','0'),4,'-1'),('b',('0','0','1./2.'),4,'-1'),('c',('x','y','z'),8,'1')]
		elif id=='61:ba-c': WyckList = [('a',('0','0','0'),4,'-1'),('b',('0','0','1./2.'),4,'-1'),('c',('x','y','z'),8,'1')]
		elif id=='62': WyckList = [('a',('0','0','0'),4,'-1'),('b',('0','0','1./2.'),4,'-1'),('c',('x','1./4.','z'),4,'.m.'),('d',('x','y','z'),8,'1')]
		elif id=='62:ba-c': WyckList = [('a',('0','0','0'),4,'-1'),('b',('0','0','1./2.'),4,'-1'),('c',('1./4.','x','-z'),4,'.m.'),('d',('x','y','z'),8,'1')]
		elif id=='62:cab': WyckList = [('a',('0','0','0'),4,'-1'),('b',('1./2.','0','0'),4,'-1'),('c',('z','x','1./4.'),4,'.m.'),('d',('x','y','z'),8,'1')]
		elif id=='62:-cba': WyckList = [('a',('0','0','0'),4,'-1'),('b',('1./2.','0','0'),4,'-1'),('c',('-z','1./4.','x'),4,'.m.'),('d',('x','y','z'),8,'1')]
		elif id=='62:bca': WyckList = [('a',('0','0','0'),4,'-1'),('b',('0','1./2.','0'),4,'-1'),('c',('1./4.','z','x'),4,'.m.'),('d',('x','y','z'),8,'1')]
		elif id=='62:a-cb': WyckList = [('a',('0','0','0'),4,'-1'),('b',('0','1./2.','0'),4,'-1'),('c',('x','-z','1./4.'),4,'.m.'),('d',('x','y','z'),8,'1')]
		elif id=='63': WyckList = [('a',('0','0','0'),4,'2/m..'),('b',('0','1./2.','0'),4,'2/m..'),('c',('0','y','1./4.'),4,'m2m'),('d',('1./4.','1./4.','0'),8,'-1'),('e',('x','0','0'),8,'2..'),('f',('0','y','z'),8,'m..'),('g',('x','y','1./4.'),8,'..m'),('h',('x','y','z'),16,'1')]
		elif id=='63:ba-c': WyckList = [('a',('0','0','0'),4,'2/m..'),('b',('1./2.','0','0'),4,'2/m..'),('c',('y','0','3./4.'),4,'m2m'),('d',('1./4.','1./4.','0'),8,'-1'),('e',('0','x','0'),8,'2..'),('f',('y','0','-z'),8,'m..'),('g',('y','x','3./4.'),8,'..m'),('h',('x','y','z'),16,'1')]
		elif id=='63:cab': WyckList = [('a',('0','0','0'),4,'2/m..'),('b',('0','0','1./2.'),4,'2/m..'),('c',('1./4.','0','y'),4,'m2m'),('d',('0','1./4.','1./4.'),8,'-1'),('e',('0','x','0'),8,'2..'),('f',('z','0','y'),8,'m..'),('g',('1./4.','x','y'),8,'..m'),('h',('x','y','z'),16,'1')]
		elif id=='63:-cba': WyckList = [('a',('0','0','0'),4,'2/m..'),('b',('0','1./2.','0'),4,'2/m..'),('c',('3./4.','y','0'),4,'m2m'),('d',('0','1./4.','1./4.'),8,'-1'),('e',('0','0','x'),8,'2..'),('f',('-z','y','0'),8,'m..'),('g',('3./4.','y','x'),8,'..m'),('h',('x','y','z'),16,'1')]
		elif id=='63:bca': WyckList = [('a',('0','0','0'),4,'2/m..'),('b',('1./2.','0','0'),4,'2/m..'),('c',('y','1./4.','0'),4,'m2m'),('d',('1./4.','0','1./4.'),8,'-1'),('e',('0','0','x'),8,'2..'),('f',('y','z','0'),8,'m..'),('g',('y','1./4.','x'),8,'..m'),('h',('x','y','z'),16,'1')]
		elif id=='63:a-cb': WyckList = [('a',('0','0','0'),4,'2/m..'),('b',('0','0','1./2.'),4,'2/m..'),('c',('0','3./4.','y'),4,'m2m'),('d',('1./4.','0','1./4.'),8,'-1'),('e',('x','0','0'),8,'2..'),('f',('0','-z','y'),8,'m..'),('g',('x','3./4.','y'),8,'..m'),('h',('x','y','z'),16,'1')]
		elif id=='64': WyckList = [('a',('0','0','0'),4,'2/m..'),('b',('1./2.','0','0'),4,'2/m..'),('c',('1./4.','1./4.','0'),8,'-1'),('d',('x','0','0'),8,'2..'),('e',('1./4.','y','1./4.'),8,'.2.'),('f',('0','y','z'),8,'m..'),('g',('x','y','z'),16,'1')]
		elif id=='64:ba-c': WyckList = [('a',('0','0','0'),4,'2/m..'),('b',('0','1./2.','0'),4,'2/m..'),('c',('1./4.','1./4.','0'),8,'-1'),('d',('0','x','0'),8,'2..'),('e',('y','1./4.','3./4.'),8,'.2.'),('f',('y','0','-z'),8,'m..'),('g',('x','y','z'),16,'1')]
		elif id=='64:cab': WyckList = [('a',('0','0','0'),4,'2/m..'),('b',('0','1./2.','0'),4,'2/m..'),('c',('0','1./4.','1./4.'),8,'-1'),('d',('0','x','0'),8,'2..'),('e',('1./4.','1./4.','y'),8,'.2.'),('f',('z','0','y'),8,'m..'),('g',('x','y','z'),16,'1')]
		elif id=='64:-cba': WyckList = [('a',('0','0','0'),4,'2/m..'),('b',('0','0','1./2.'),4,'2/m..'),('c',('0','1./4.','1./4.'),8,'-1'),('d',('0','0','x'),8,'2..'),('e',('3./4.','y','1./4.'),8,'.2.'),('f',('-z','y','0'),8,'m..'),('g',('x','y','z'),16,'1')]
		elif id=='64:bca': WyckList = [('a',('0','0','0'),4,'2/m..'),('b',('0','0','1./2.'),4,'2/m..'),('c',('1./4.','0','1./4.'),8,'-1'),('d',('0','0','x'),8,'2..'),('e',('y','1./4.','1./4.'),8,'.2.'),('f',('y','z','0'),8,'m..'),('g',('x','y','z'),16,'1')]
		elif id=='64:a-cb': WyckList = [('a',('0','0','0'),4,'2/m..'),('b',('1./2.','0','0'),4,'2/m..'),('c',('1./4.','0','1./4.'),8,'-1'),('d',('x','0','0'),8,'2..'),('e',('1./4.','3./4.','y'),8,'.2.'),('f',('0','-z','y'),8,'m..'),('g',('x','y','z'),16,'1')]
		elif id=='65': WyckList = [('a',('0','0','0'),2,'mmm'),('b',('1./2.','0','0'),2,'mmm'),('c',('1./2.','0','1./2.'),2,'mmm'),('d',('0','0','1./2.'),2,'mmm'),('e',('1./4.','1./4.','0'),4,'..2/m'),('f',('1./4.','1./4.','1./2.'),4,'..2/m'),('g',('x','0','0'),4,'2mm'),('h',('x','0','1./2.'),4,'2mm'),('i',('0','y','0'),4,'m2m'),('j',('0','y','1./2.'),4,'m2m'),('k',('0','0','z'),4,'mm2'),('l',('0','1./2.','z'),4,'mm2'),('m',('1./4.','1./4.','z'),8,'..2'),('n',('0','y','z'),8,'m..'),('o',('x','0','z'),8,'.m.'),('p',('x','y','0'),8,'..m'),('q',('x','y','1./2.'),8,'..m'),('r',('x','y','z'),16,'1')]
		elif id=='65:cab': WyckList = [('a',('0','0','0'),2,'mmm'),('b',('0','1./2.','0'),2,'mmm'),('c',('1./2.','1./2.','0'),2,'mmm'),('d',('1./2.','0','0'),2,'mmm'),('e',('0','1./4.','1./4.'),4,'..2/m'),('f',('1./2.','1./4.','1./4.'),4,'..2/m'),('g',('0','x','0'),4,'2mm'),('h',('1./2.','x','0'),4,'2mm'),('i',('0','0','y'),4,'m2m'),('j',('1./2.','0','y'),4,'m2m'),('k',('z','0','0'),4,'mm2'),('l',('z','0','1./2.'),4,'mm2'),('m',('z','1./4.','1./4.'),8,'..2'),('n',('z','0','y'),8,'m..'),('o',('z','x','0'),8,'.m.'),('p',('0','x','y'),8,'..m'),('q',('1./2.','x','y'),8,'..m'),('r',('x','y','z'),16,'1')]
		elif id=='65:bca': WyckList = [('a',('0','0','0'),2,'mmm'),('b',('0','0','1./2.'),2,'mmm'),('c',('0','1./2.','1./2.'),2,'mmm'),('d',('0','1./2.','0'),2,'mmm'),('e',('1./4.','0','1./4.'),4,'..2/m'),('f',('1./4.','1./2.','1./4.'),4,'..2/m'),('g',('0','0','x'),4,'2mm'),('h',('0','1./2.','x'),4,'2mm'),('i',('y','0','0'),4,'m2m'),('j',('y','1./2.','0'),4,'m2m'),('k',('0','z','0'),4,'mm2'),('l',('1./2.','z','0'),4,'mm2'),('m',('1./4.','z','1./4.'),8,'..2'),('n',('y','z','0'),8,'m..'),('o',('0','z','x'),8,'.m.'),('p',('y','0','x'),8,'..m'),('q',('y','1./2.','x'),8,'..m'),('r',('x','y','z'),16,'1')]
		elif id=='66': WyckList = [('a',('0','0','1./4.'),4,'222'),('b',('0','1./2.','1./4.'),4,'222'),('c',('0','0','0'),4,'..2/m'),('d',('0','1./2.','0'),4,'..2/m'),('e',('1./4.','1./4.','0'),4,'..2/m'),('f',('1./4.','3./4.','0'),4,'..2/m'),('g',('x','0','1./4.'),8,'2..'),('h',('0','y','1./4.'),8,'.2.'),('i',('0','0','z'),8,'..2'),('j',('0','1./2.','z'),8,'..2'),('k',('1./4.','1./4.','z'),8,'..2'),('l',('x','y','0'),8,'..m'),('m',('x','y','z'),16,'1')]
		elif id=='66:cab': WyckList = [('a',('1./4.','0','0'),4,'222'),('b',('1./4.','0','1./2.'),4,'222'),('c',('0','0','0'),4,'..2/m'),('d',('0','0','1./2.'),4,'..2/m'),('e',('0','1./4.','1./4.'),4,'..2/m'),('f',('0','1./4.','3./4.'),4,'..2/m'),('g',('1./4.','x','0'),8,'2..'),('h',('1./4.','0','y'),8,'.2.'),('i',('z','0','0'),8,'..2'),('j',('z','0','1./2.'),8,'..2'),('k',('z','1./4.','1./4.'),8,'..2'),('l',('0','x','y'),8,'..m'),('m',('x','y','z'),16,'1')]
		elif id=='66:bca': WyckList = [('a',('0','1./4.','0'),4,'222'),('b',('1./2.','1./4.','0'),4,'222'),('c',('0','0','0'),4,'..2/m'),('d',('1./2.','0','0'),4,'..2/m'),('e',('1./4.','0','1./4.'),4,'..2/m'),('f',('3./4.','0','1./4.'),4,'..2/m'),('g',('0','1./4.','x'),8,'2..'),('h',('y','1./4.','0'),8,'.2.'),('i',('0','z','0'),8,'..2'),('j',('1./2.','z','0'),8,'..2'),('k',('1./4.','z','1./4.'),8,'..2'),('l',('y','0','x'),8,'..m'),('m',('x','y','z'),16,'1')]
		elif id=='67': WyckList = [('a',('1./4.','0','0'),4,'222'),('b',('1./4.','0','1./2.'),4,'222'),('c',('0','0','0'),4,'2/m..'),('d',('0','0','1./2.'),4,'2/m..'),('e',('1./4.','1./4.','0'),4,'.2/m.'),('f',('1./4.','1./4.','1./2.'),4,'.2/m.'),('g',('0','1./4.','z'),4,'mm2'),('h',('x','0','0'),8,'2..'),('i',('x','0','1./2.'),8,'2..'),('j',('1./4.','y','0'),8,'.2.'),('k',('1./4.','y','1./2.'),8,'.2.'),('l',('1./4.','0','z'),8,'..2'),('m',('0','y','z'),8,'m..'),('n',('x','1./4.','z'),8,'.m.'),('o',('x','y','z'),16,'1')]
		elif id=='67:ba-c': WyckList = [('a',('0','3./4.','0'),4,'222'),('b',('0','3./4.','1./2.'),4,'222'),('c',('3./4.','3./4.','0'),4,'2/m..'),('d',('3./4.','3./4.','1./2.'),4,'2/m..'),('e',('0','0','0'),4,'.2/m.'),('f',('0','0','1./2.'),4,'.2/m.'),('g',('3./4.','0','z'),4,'mm2'),('h',('x-1./4.','3./4.','0'),8,'2..'),('i',('x-1./4.','3./4.','1./2.'),8,'2..'),('j',('0','y-1./4.','0'),8,'.2.'),('k',('0','y-1./4.','1./2.'),8,'.2.'),('l',('0','3./4.','z'),8,'..2'),('m',('3./4.','y-1./4.','z'),8,'m..'),('n',('x-1./4.','0','z'),8,'.m.'),('o',('x','y','z'),16,'1')]
		elif id=='67:cab': WyckList = [('a',('0','1./4.','0'),4,'222'),('b',('1./2.','1./4.','0'),4,'222'),('c',('0','0','0'),4,'2/m..'),('d',('1./2.','0','0'),4,'2/m..'),('e',('0','1./4.','1./4.'),4,'.2/m.'),('f',('1./2.','1./4.','1./4.'),4,'.2/m.'),('g',('z','0','1./4.'),4,'mm2'),('h',('0','x','0'),8,'2..'),('i',('1./2.','x','0'),8,'2..'),('j',('0','1./4.','y'),8,'.2.'),('k',('1./2.','1./4.','y'),8,'.2.'),('l',('z','1./4.','0'),8,'..2'),('m',('z','0','y'),8,'m..'),('n',('z','x','1./4.'),8,'.m.'),('o',('x','y','z'),16,'1')]
		elif id=='67:-cba': WyckList = [('a',('0','0','3./4.'),4,'222'),('b',('1./2.','0','3./4.'),4,'222'),('c',('0','3./4.','3./4.'),4,'2/m..'),('d',('1./2.','3./4.','3./4.'),4,'2/m..'),('e',('0','0','0'),4,'.2/m.'),('f',('1./2.','0','0'),4,'.2/m.'),('g',('z','3./4.','0'),4,'mm2'),('h',('0','x-1./4.','3./4.'),8,'2..'),('i',('1./2.','x-1./4.','3./4.'),8,'2..'),('j',('0','0','y-1./4.'),8,'.2.'),('k',('1./2.','0','y-1./4.'),8,'.2.'),('l',('z','0','3./4.'),8,'..2'),('m',('z','3./4.','y-1./4.'),8,'m..'),('n',('z','x-1./4.','0'),8,'.m.'),('o',('x','y','z'),16,'1')]
		elif id=='67:bca': WyckList = [('a',('0','0','1./4.'),4,'222'),('b',('0','1./2.','1./4.'),4,'222'),('c',('0','0','0'),4,'2/m..'),('d',('0','1./2.','0'),4,'2/m..'),('e',('1./4.','0','1./4.'),4,'.2/m.'),('f',('1./4.','1./2.','1./4.'),4,'.2/m.'),('g',('1./4.','z','0'),4,'mm2'),('h',('0','0','x'),8,'2..'),('i',('0','1./2.','x'),8,'2..'),('j',('y','0','1./4.'),8,'.2.'),('k',('y','1./2.','1./4.'),8,'.2.'),('l',('0','z','1./4.'),8,'..2'),('m',('y','z','0'),8,'m..'),('n',('1./4.','z','x'),8,'.m.'),('o',('x','y','z'),16,'1')]
		elif id=='67:a-cb': WyckList = [('a',('3./4.','0','1./2.'),4,'222'),('b',('3./4.','1./2.','1./2.'),4,'222'),('c',('3./4.','0','1./4.'),4,'2/m..'),('d',('3./4.','1./2.','1./4.'),4,'2/m..'),('e',('0','0','1./2.'),4,'.2/m.'),('f',('0','1./2.','1./2.'),4,'.2/m.'),('g',('0','z','1./4.'),4,'mm2'),('h',('3./4.','0','x+1./4.'),8,'2..'),('i',('3./4.','1./2.','x+1./4.'),8,'2..'),('j',('y-1./4.','0','1./2.'),8,'.2.'),('k',('y-1./4.','1./2.','1./2.'),8,'.2.'),('l',('3./4.','z','1./2.'),8,'..2'),('m',('y-1./4.','z','1./4.'),8,'m..'),('n',('0','z','x+1./4.'),8,'.m.'),('o',('x','y','z'),16,'1')]
		elif id=='68:1': WyckList = [('a',('0','0','0'),4,'222'),('b',('0','0','1./2.'),4,'222'),('c',('1./4.','0','1./4.'),8,'-1'),('d',('0','1./4.','1./4.'),8,'-1'),('e',('x','0','0'),8,'2..'),('f',('0','y','0'),8,'.2.'),('g',('0','0','z'),8,'..2'),('h',('1./4.','1./4.','z'),8,'..2'),('i',('x','y','z'),16,'1')]
		elif id=='68:2': WyckList = [('a',('0','1./4.','1./4.'),4,'222'),('b',('0','1./4.','3./4.'),4,'222'),('c',('1./4.','1./4.','1./2.'),8,'-1'),('d',('0','1./2.','1./2.'),8,'-1'),('e',('x','1./4.','1./4.'),8,'2..'),('f',('0','y+1./4.','1./4.'),8,'.2.'),('g',('0','1./4.','z+1./4.'),8,'..2'),('h',('1./4.','1./2.','z+1./4.'),8,'..2'),('i',('x','y','z'),16,'1')]
		elif id=='68:1ba-c': WyckList = [('a',('0','0','0'),4,'222'),('b',('0','0','1./2.'),4,'222'),('c',('1./4.','0','1./4.'),8,'-1'),('d',('0','1./4.','1./4.'),8,'-1'),('e',('x','0','0'),8,'2..'),('f',('0','y','0'),8,'.2.'),('g',('0','0','z'),8,'..2'),('h',('1./4.','1./4.','z'),8,'..2'),('i',('x','y','z'),16,'1')]
		elif id=='68:2ba-c': WyckList = [('a',('3./4.','0','1./4.'),4,'222'),('b',('3./4.','0','3./4.'),4,'222'),('c',('0','0','1./2.'),8,'-1'),('d',('3./4.','1./4.','1./2.'),8,'-1'),('e',('x-1./4.','0','1./4.'),8,'2..'),('f',('3./4.','y','1./4.'),8,'.2.'),('g',('3./4.','0','z+1./4.'),8,'..2'),('h',('0','1./4.','z+1./4.'),8,'..2'),('i',('x','y','z'),16,'1')]
		elif id=='68:1cab': WyckList = [('a',('0','0','0'),4,'222'),('b',('1./2.','0','0'),4,'222'),('c',('1./4.','1./4.','0'),8,'-1'),('d',('1./4.','0','1./4.'),8,'-1'),('e',('0','x','0'),8,'2..'),('f',('0','0','y'),8,'.2.'),('g',('z','0','0'),8,'..2'),('h',('z','1./4.','1./4.'),8,'..2'),('i',('x','y','z'),16,'1')]
		elif id=='68:2cab': WyckList = [('a',('1./4.','0','1./4.'),4,'222'),('b',('3./4.','0','1./4.'),4,'222'),('c',('1./2.','1./4.','1./4.'),8,'-1'),('d',('1./2.','0','1./2.'),8,'-1'),('e',('1./4.','x','1./4.'),8,'2..'),('f',('1./4.','0','y+1./4.'),8,'.2.'),('g',('z+1./4.','0','1./4.'),8,'..2'),('h',('z+1./4.','1./4.','1./2.'),8,'..2'),('i',('x','y','z'),16,'1')]
		elif id=='68:1-cba': WyckList = [('a',('0','0','0'),4,'222'),('b',('1./2.','0','0'),4,'222'),('c',('1./4.','1./4.','0'),8,'-1'),('d',('1./4.','0','1./4.'),8,'-1'),('e',('0','x','0'),8,'2..'),('f',('0','0','y'),8,'.2.'),('g',('z','0','0'),8,'..2'),('h',('z','1./4.','1./4.'),8,'..2'),('i',('x','y','z'),16,'1')]
		elif id=='68:2-cba': WyckList = [('a',('1./4.','3./4.','0'),4,'222'),('b',('3./4.','3./4.','0'),4,'222'),('c',('1./2.','0','0'),8,'-1'),('d',('1./2.','3./4.','1./4.'),8,'-1'),('e',('1./4.','x-1./4.','0'),8,'2..'),('f',('1./4.','3./4.','y'),8,'.2.'),('g',('z+1./4.','3./4.','0'),8,'..2'),('h',('z+1./4.','0','1./4.'),8,'..2'),('i',('x','y','z'),16,'1')]
		elif id=='68:1bca': WyckList = [('a',('0','0','0'),4,'222'),('b',('0','1./2.','0'),4,'222'),('c',('0','1./4.','1./4.'),8,'-1'),('d',('1./4.','1./4.','0'),8,'-1'),('e',('0','0','x'),8,'2..'),('f',('y','0','0'),8,'.2.'),('g',('0','z','0'),8,'..2'),('h',('1./4.','z','1./4.'),8,'..2'),('i',('x','y','z'),16,'1')]
		elif id=='68:2bca': WyckList = [('a',('3./4.','1./4.','0'),4,'222'),('b',('3./4.','3./4.','0'),4,'222'),('c',('3./4.','1./2.','1./4.'),8,'-1'),('d',('0','1./2.','0'),8,'-1'),('e',('3./4.','1./4.','x'),8,'2..'),('f',('y-1./4.','1./4.','0'),8,'.2.'),('g',('3./4.','z+1./4.','0'),8,'..2'),('h',('0','z+1./4.','1./4.'),8,'..2'),('i',('x','y','z'),16,'1')]
		elif id=='68:1a-cb': WyckList = [('a',('0','0','0'),4,'222'),('b',('0','1./2.','0'),4,'222'),('c',('0','1./4.','1./4.'),8,'-1'),('d',('1./4.','1./4.','0'),8,'-1'),('e',('0','0','x'),8,'2..'),('f',('y','0','0'),8,'.2.'),('g',('0','z','0'),8,'..2'),('h',('1./4.','z','1./4.'),8,'..2'),('i',('x','y','z'),16,'1')]
		elif id=='68:2a-cb': WyckList = [('a',('0','1./4.','1./4.'),4,'222'),('b',('0','3./4.','1./4.'),4,'222'),('c',('0','1./2.','1./2.'),8,'-1'),('d',('1./4.','1./2.','1./4.'),8,'-1'),('e',('0','1./4.','x+1./4.'),8,'2..'),('f',('y','1./4.','1./4.'),8,'.2.'),('g',('0','z+1./4.','1./4.'),8,'..2'),('h',('1./4.','z+1./4.','1./2.'),8,'..2'),('i',('x','y','z'),16,'1')]
		elif id=='69': WyckList = [('a',('0','0','0'),4,'mmm'),('b',('0','0','1./2.'),4,'mmm'),('c',('0','1./4.','1./4.'),8,'2/m..'),('d',('1./4.','0','1./4.'),8,'.2/m.'),('e',('1./4.','1./4.','0'),8,'..2/m'),('f',('1./4.','1./4.','1./4.'),8,'222'),('g',('x','0','0'),8,'2mm'),('h',('0','y','0'),8,'m2m'),('i',('0','0','z'),8,'mm2'),('j',('1./4.','1./4.','z'),16,'..2'),('k',('1./4.','y','1./4.'),16,'.2.'),('l',('x','1./4.','1./4.'),16,'2..'),('m',('0','y','z'),16,'m..'),('n',('x','0','z'),16,'.m.'),('o',('x','y','0'),16,'..m'),('p',('x','y','z'),32,'1')]
		elif id=='70:1': WyckList = [('a',('0','0','0'),8,'222'),('b',('0','0','1./2.'),8,'222'),('c',('1./8.','1./8.','1./8.'),16,'-1'),('d',('5./8.','5./8.','5./8.'),16,'-1'),('e',('x','0','0'),16,'2..'),('f',('0','y','0'),16,'.2.'),('g',('0','0','z'),16,'..2'),('h',('x','y','z'),32,'1')]
		elif id=='70:2': WyckList = [('a',('7./8.','7./8.','7./8.'),8,'222'),('b',('7./8.','7./8.','3./8.'),8,'222'),('c',('0','0','0'),16,'-1'),('d',('1./2.','1./2.','1./2.'),16,'-1'),('e',('x-1./8.','7./8.','7./8.'),16,'2..'),('f',('7./8.','y-1./8.','7./8.'),16,'.2.'),('g',('7./8.','7./8.','z-1./8.'),16,'..2'),('h',('x','y','z'),32,'1')]
		elif id=='71': WyckList = [('a',('0','0','0'),2,'mmm'),('b',('0','1./2.','1./2.'),2,'mmm'),('c',('1./2.','1./2.','0'),2,'mmm'),('d',('1./2.','0','1./2.'),2,'mmm'),('e',('x','0','0'),4,'2mm'),('f',('x','1./2.','0'),4,'2mm'),('g',('0','y','0'),4,'m2m'),('h',('0','y','1./2.'),4,'m2m'),('i',('0','0','z'),4,'mm2'),('j',('1./2.','0','z'),4,'mm2'),('k',('1./4.','1./4.','1./4.'),8,'-1'),('l',('0','y','z'),8,'m..'),('m',('x','0','z'),8,'.m.'),('n',('x','y','0'),8,'..m'),('o',('x','y','z'),16,'1')]
		elif id=='72': WyckList = [('a',('0','0','1./4.'),4,'222'),('b',('1./2.','0','1./4.'),4,'222'),('c',('0','0','0'),4,'..2/m'),('d',('1./2.','0','0'),4,'..2/m'),('e',('1./4.','1./4.','1./4.'),8,'-1'),('f',('x','0','1./4.'),8,'2..'),('g',('0','y','1./4.'),8,'.2.'),('h',('0','0','z'),8,'..2'),('i',('0','1./2.','z'),8,'..2'),('j',('x','y','0'),8,'..m'),('k',('x','y','z'),16,'1')]
		elif id=='72:cab': WyckList = [('a',('1./4.','0','0'),4,'222'),('b',('1./4.','1./2.','0'),4,'222'),('c',('0','0','0'),4,'..2/m'),('d',('0','1./2.','0'),4,'..2/m'),('e',('1./4.','1./4.','1./4.'),8,'-1'),('f',('1./4.','x','0'),8,'2..'),('g',('1./4.','0','y'),8,'.2.'),('h',('z','0','0'),8,'..2'),('i',('z','0','1./2.'),8,'..2'),('j',('0','x','y'),8,'..m'),('k',('x','y','z'),16,'1')]
		elif id=='72:bca': WyckList = [('a',('0','1./4.','0'),4,'222'),('b',('0','1./4.','1./2.'),4,'222'),('c',('0','0','0'),4,'..2/m'),('d',('0','0','1./2.'),4,'..2/m'),('e',('1./4.','1./4.','1./4.'),8,'-1'),('f',('0','1./4.','x'),8,'2..'),('g',('y','1./4.','0'),8,'.2.'),('h',('0','z','0'),8,'..2'),('i',('1./2.','z','0'),8,'..2'),('j',('y','0','x'),8,'..m'),('k',('x','y','z'),16,'1')]
		elif id=='73': WyckList = [('a',('0','0','0'),8,'-1'),('b',('1./4.','1./4.','1./4.'),8,'-1'),('c',('x','0','1./4.'),8,'2..'),('d',('1./4.','y','0'),8,'.2.'),('e',('0','1./4.','z'),8,'..2'),('f',('x','y','z'),16,'1')]
		elif id=='73:ba-c': WyckList = [('a',('1./4.','3./4.','3./4.'),8,'-1'),('b',('1./2.','0','0'),8,'-1'),('c',('x+1./4.','3./4.','0'),8,'2..'),('d',('1./2.','y-1./4.','3./4.'),8,'.2.'),('e',('1./4.','0','z-1./4.'),8,'..2'),('f',('x','y','z'),16,'1')]
		elif id=='74': WyckList = [('a',('0','0','0'),4,'2/m..'),('b',('0','0','1./2.'),4,'2/m..'),('c',('1./4.','1./4.','1./4.'),4,'.2/m.'),('d',('1./4.','1./4.','3./4.'),4,'.2/m.'),('e',('0','1./4.','z'),4,'mm2'),('f',('x','0','0'),8,'2..'),('g',('1./4.','y','1./4.'),8,'.2.'),('h',('0','y','z'),8,'m..'),('i',('x','1./4.','z'),8,'.m.'),('j',('x','y','z'),16,'1')]
		elif id=='74:ba-c': WyckList = [('a',('1./4.','3./4.','3./4.'),4,'2/m..'),('b',('1./4.','3./4.','1./4.'),4,'2/m..'),('c',('1./2.','0','0'),4,'.2/m.'),('d',('1./2.','0','1./2.'),4,'.2/m.'),('e',('1./4.','0','z-1./4.'),4,'mm2'),('f',('x+1./4.','3./4.','3./4.'),8,'2..'),('g',('1./2.','y-1./4.','0'),8,'.2.'),('h',('1./4.','y-1./4.','z-1./4.'),8,'m..'),('i',('x+1./4.','0','z-1./4.'),8,'.m.'),('j',('x','y','z'),16,'1')]
		elif id=='74:cab': WyckList = [('a',('0','0','0'),4,'2/m..'),('b',('1./2.','0','0'),4,'2/m..'),('c',('1./4.','1./4.','1./4.'),4,'.2/m.'),('d',('3./4.','1./4.','1./4.'),4,'.2/m.'),('e',('z','0','1./4.'),4,'mm2'),('f',('0','x','0'),8,'2..'),('g',('1./4.','1./4.','y'),8,'.2.'),('h',('z','0','y'),8,'m..'),('i',('z','x','1./4.'),8,'.m.'),('j',('x','y','z'),16,'1')]
		elif id=='74:-cba': WyckList = [('a',('3./4.','1./4.','3./4.'),4,'2/m..'),('b',('1./4.','1./4.','3./4.'),4,'2/m..'),('c',('0','1./2.','0'),4,'.2/m.'),('d',('1./2.','1./2.','0'),4,'.2/m.'),('e',('z-1./4.','1./4.','0'),4,'mm2'),('f',('3./4.','x+1./4.','3./4.'),8,'2..'),('g',('0','1./2.','y-1./4.'),8,'.2.'),('h',('z-1./4.','1./4.','y-1./4.'),8,'m..'),('i',('z-1./4.','x+1./4.','0'),8,'.m.'),('j',('x','y','z'),16,'1')]
		elif id=='74:bca': WyckList = [('a',('0','0','0'),4,'2/m..'),('b',('0','1./2.','0'),4,'2/m..'),('c',('1./4.','1./4.','1./4.'),4,'.2/m.'),('d',('1./4.','3./4.','1./4.'),4,'.2/m.'),('e',('1./4.','z','0'),4,'mm2'),('f',('0','0','x'),8,'2..'),('g',('y','1./4.','1./4.'),8,'.2.'),('h',('y','z','0'),8,'m..'),('i',('1./4.','z','x'),8,'.m.'),('j',('x','y','z'),16,'1')]
		elif id=='74:a-cb': WyckList = [('a',('3./4.','3./4.','1./4.'),4,'2/m..'),('b',('3./4.','1./4.','1./4.'),4,'2/m..'),('c',('0','0','1./2.'),4,'.2/m.'),('d',('0','1./2.','1./2.'),4,'.2/m.'),('e',('0','z-1./4.','1./4.'),4,'mm2'),('f',('3./4.','3./4.','x+1./4.'),8,'2..'),('g',('y-1./4.','0','1./2.'),8,'.2.'),('h',('y-1./4.','z-1./4.','1./4.'),8,'m..'),('i',('0','z-1./4.','x+1./4.'),8,'.m.'),('j',('x','y','z'),16,'1')]
		elif id=='75': WyckList = [('a',('0','0','z'),1,'4..'),('b',('1./2.','1./2.','z'),1,'4..'),('c',('0','1./2.','z'),2,'2..'),('d',('x','y','z'),4,'1')]
		elif id=='76': WyckList = [('a',('x','y','z'),4,'1')]
		elif id=='77': WyckList = [('a',('0','0','z'),2,'2..'),('b',('1./2.','1./2.','z'),2,'2..'),('c',('0','1./2.','z'),2,'2..'),('d',('x','y','z'),4,'1')]
		elif id=='78': WyckList = [('a',('x','y','z'),4,'1')]
		elif id=='79': WyckList = [('a',('0','0','z'),2,'4..'),('b',('0','1./2.','z'),4,'2..'),('c',('x','y','z'),8,'1')]
		elif id=='80': WyckList = [('a',('0','0','z'),4,'2..'),('b',('x','y','z'),8,'1')]
		elif id=='81': WyckList = [('a',('0','0','0'),1,'-4..'),('b',('0','0','1./2.'),1,'-4..'),('c',('1./2.','1./2.','0'),1,'-4..'),('d',('1./2.','1./2.','1./2.'),1,'-4..'),('e',('0','0','z'),2,'2..'),('f',('1./2.','1./2.','z'),2,'2..'),('g',('0','1./2.','z'),2,'2..'),('h',('x','y','z'),4,'1')]
		elif id=='82': WyckList = [('a',('0','0','0'),2,'-4..'),('b',('0','0','1./2.'),2,'-4..'),('c',('0','1./2.','1./4.'),2,'-4..'),('d',('0','1./2.','3./4.'),2,'-4..'),('e',('0','0','z'),4,'2..'),('f',('0','1./2.','z'),4,'2..'),('g',('x','y','z'),8,'1')]
		elif id=='83': WyckList = [('a',('0','0','0'),1,'4/m..'),('b',('0','0','1./2.'),1,'4/m..'),('c',('1./2.','1./2.','0'),1,'4/m..'),('d',('1./2.','1./2.','1./2.'),1,'4/m..'),('e',('0','1./2.','0'),2,'2/m..'),('f',('0','1./2.','1./2.'),2,'2/m..'),('g',('0','0','z'),2,'4..'),('h',('1./2.','1./2.','z'),2,'4..'),('i',('0','1./2.','z'),4,'2..'),('j',('x','y','0'),4,'m..'),('k',('x','y','1./2.'),4,'m..'),('l',('x','y','z'),8,'1')]
		elif id=='84': WyckList = [('a',('0','0','0'),2,'2/m..'),('b',('1./2.','1./2.','0'),2,'2/m..'),('c',('0','1./2.','0'),2,'2/m..'),('d',('0','1./2.','1./2.'),2,'2/m..'),('e',('0','0','1./4.'),2,'-4..'),('f',('1./2.','1./2.','1./4.'),2,'-4..'),('g',('0','0','z'),4,'2..'),('h',('1./2.','1./2.','z'),4,'2..'),('i',('0','1./2.','z'),4,'2..'),('j',('x','y','0'),4,'m..'),('k',('x','y','z'),8,'1')]
		elif id=='85:1': WyckList = [('a',('0','0','0'),2,'-4..'),('b',('0','0','1./2.'),2,'-4..'),('c',('0','1./2.','z'),2,'4..'),('d',('1./4.','1./4.','0'),4,'-1'),('e',('1./4.','1./4.','1./2.'),4,'-1'),('f',('0','0','z'),4,'2..'),('g',('x','y','z'),8,'1')]
		elif id=='85:2': WyckList = [('a',('1./4.','3./4.','0'),2,'-4..'),('b',('1./4.','3./4.','1./2.'),2,'-4..'),('c',('1./4.','1./4.','z'),2,'4..'),('d',('1./2.','0','0'),4,'-1'),('e',('1./2.','0','1./2.'),4,'-1'),('f',('1./4.','3./4.','z'),4,'2..'),('g',('x','y','z'),8,'1')]
		elif id=='86:1': WyckList = [('a',('0','0','0'),2,'-4..'),('b',('0','0','1./2.'),2,'-4..'),('c',('1./4.','1./4.','1./4.'),4,'-1'),('d',('1./4.','1./4.','3./4.'),4,'-1'),('e',('0','1./2.','z'),4,'2..'),('f',('0','0','z'),4,'2..'),('g',('x','y','z'),8,'1')]
		elif id=='86:2': WyckList = [('a',('3./4.','3./4.','3./4.'),2,'-4..'),('b',('3./4.','3./4.','1./4.'),2,'-4..'),('c',('0','0','0'),4,'-1'),('d',('0','0','1./2.'),4,'-1'),('e',('3./4.','1./4.','z-1./4.'),4,'2..'),('f',('3./4.','3./4.','z-1./4.'),4,'2..'),('g',('x','y','z'),8,'1')]
		elif id=='87': WyckList = [('a',('0','0','0'),2,'4/m..'),('b',('0','0','1./2.'),2,'4/m..'),('c',('0','1./2.','0'),4,'2/m..'),('d',('0','1./2.','1./4.'),4,'-4..'),('e',('0','0','z'),4,'4..'),('f',('1./4.','1./4.','1./4.'),8,'-1'),('g',('0','1./2.','z'),8,'2..'),('h',('x','y','0'),8,'m..'),('i',('x','y','z'),16,'1')]
		elif id=='88:1': WyckList = [('a',('0','0','0'),4,'-4..'),('b',('0','0','1./2.'),4,'-4..'),('c',('0','1./4.','1./8.'),8,'-1'),('d',('0','1./4.','5./8.'),8,'-1'),('e',('0','0','z'),8,'2..'),('f',('x','y','z'),16,'1')]
		elif id=='88:2': WyckList = [('a',('1./2.','1./4.','7./8.'),4,'-4..'),('b',('1./2.','1./4.','3./8.'),4,'-4..'),('c',('1./2.','1./2.','0'),8,'-1'),('d',('1./2.','1./2.','1./2.'),8,'-1'),('e',('1./2.','1./4.','z-1./8.'),8,'2..'),('f',('x','y','z'),16,'1')]
		elif id=='89': WyckList = [('a',('0','0','0'),1,'422'),('b',('0','0','1./2.'),1,'422'),('c',('1./2.','1./2.','0'),1,'422'),('d',('1./2.','1./2.','1./2.'),1,'422'),('e',('1./2.','0','0'),2,'222 .'),('f',('1./2.','0','1./2.'),2,'222 .'),('g',('0','0','z'),2,'4..'),('h',('1./2.','1./2.','z'),2,'4..'),('i',('0','1./2.','z'),4,'2..'),('j',('x','x','0'),4,'..2'),('k',('x','x','1./2.'),4,'..2'),('l',('x','0','0'),4,'.2.'),('m',('x','1./2.','1./2.'),4,'.2.'),('n',('x','0','1./2.'),4,'.2.'),('o',('x','1./2.','0'),4,'.2.'),('p',('x','y','z'),8,'1')]
		elif id=='90': WyckList = [('a',('0','0','0'),2,'2.2 2'),('b',('0','0','1./2.'),2,'2.2 2'),('c',('0','1./2.','z'),2,'4..'),('d',('0','0','z'),4,'2..'),('e',('x','x','0'),4,'..2'),('f',('x','x','1./2.'),4,'..2'),('g',('x','y','z'),8,'1')]
		elif id=='91': WyckList = [('a',('0','y','0'),4,'.2.'),('b',('1./2.','y','0'),4,'.2.'),('c',('x','x','3./8.'),4,'..2'),('d',('x','y','z'),8,'1')]
		elif id=='92': WyckList = [('a',('x','x','0'),4,'..2'),('b',('x','y','z'),8,'1')]
		elif id=='93': WyckList = [('a',('0','0','0'),2,'222 .'),('b',('1./2.','1./2.','0'),2,'222 .'),('c',('0','1./2.','0'),2,'222 .'),('d',('0','1./2.','1./2.'),2,'222 .'),('e',('0','0','1./4.'),2,'2.2 2'),('f',('1./2.','1./2.','1./4.'),2,'2.2 2'),('g',('0','0','z'),4,'2..'),('h',('1./2.','1./2.','z'),4,'2..'),('i',('0','1./2.','z'),4,'2..'),('j',('x','0','0'),4,'.2.'),('k',('x','1./2.','1./2.'),4,'.2.'),('l',('x','0','1./2.'),4,'.2.'),('m',('x','1./2.','0'),4,'.2.'),('n',('x','x','1./4.'),4,'..2'),('o',('x','x','3./4.'),4,'..2'),('p',('x','y','z'),8,'1')]
		elif id=='94': WyckList = [('a',('0','0','0'),2,'2.2 2'),('b',('0','0','1./2.'),2,'2.2 2'),('c',('0','0','z'),4,'2..'),('d',('0','1./2.','z'),4,'2..'),('e',('x','x','0'),4,'..2'),('f',('x','x','1./2.'),4,'..2'),('g',('x','y','z'),8,'1')]
		elif id=='95': WyckList = [('a',('0','y','0'),4,'.2.'),('b',('1./2.','y','0'),4,'.2.'),('c',('x','x','5./8.'),4,'..2'),('d',('x','y','z'),8,'1')]
		elif id=='96': WyckList = [('a',('x','x','0'),4,'..2'),('b',('x','y','z'),8,'1')]
		elif id=='97': WyckList = [('a',('0','0','0'),2,'422'),('b',('0','0','1./2.'),2,'422'),('c',('0','1./2.','0'),4,'222 .'),('d',('0','1./2.','1./4.'),4,'2.2 2'),('e',('0','0','z'),4,'4..'),('f',('0','1./2.','z'),8,'2..'),('g',('x','x','0'),8,'..2'),('h',('x','0','0'),8,'.2.'),('i',('x','0','1./2.'),8,'.2.'),('j',('x','x+1./2.','1./4.'),8,'..2'),('k',('x','y','z'),16,'1')]
		elif id=='98': WyckList = [('a',('0','0','0'),4,'2.2 2'),('b',('0','0','1./2.'),4,'2.2 2'),('c',('0','0','z'),8,'2..'),('d',('x','x','0'),8,'..2'),('e',('-x','x','0'),8,'..2'),('f',('x','1./4.','1./8.'),8,'.2.'),('g',('x','y','z'),16,'1')]
		elif id=='99': WyckList = [('a',('0','0','z'),1,'4mm'),('b',('1./2.','1./2.','z'),1,'4mm'),('c',('1./2.','0','z'),2,'2mm .'),('d',('x','x','z'),4,'..m'),('e',('x','0','z'),4,'.m.'),('f',('x','1./2.','z'),4,'.m.'),('g',('x','y','z'),8,'1')]
		elif id=='100': WyckList = [('a',('0','0','z'),2,'4..'),('b',('1./2.','0','z'),2,'2.m m'),('c',('x','x+1./2.','z'),4,'..m'),('d',('x','y','z'),8,'1')]
		elif id=='101': WyckList = [('a',('0','0','z'),2,'2.m m'),('b',('1./2.','1./2.','z'),2,'2.m m'),('c',('0','1./2.','z'),4,'2..'),('d',('x','x','z'),4,'..m'),('e',('x','y','z'),8,'1')]
		elif id=='102': WyckList = [('a',('0','0','z'),2,'2.m m'),('b',('0','1./2.','z'),4,'2..'),('c',('x','x','z'),4,'..m'),('d',('x','y','z'),8,'1')]
		elif id=='103': WyckList = [('a',('0','0','z'),2,'4..'),('b',('1./2.','1./2.','z'),2,'4..'),('c',('0','1./2.','z'),4,'2..'),('d',('x','y','z'),8,'1')]
		elif id=='104': WyckList = [('a',('0','0','z'),2,'4..'),('b',('0','1./2.','z'),4,'2..'),('c',('x','y','z'),8,'1')]
		elif id=='105': WyckList = [('a',('0','0','z'),2,'2mm .'),('b',('1./2.','1./2.','z'),2,'2mm .'),('c',('0','1./2.','z'),2,'2mm .'),('d',('x','0','z'),4,'.m.'),('e',('x','1./2.','z'),4,'.m.'),('f',('x','y','z'),8,'1')]
		elif id=='106': WyckList = [('a',('0','0','z'),4,'2..'),('b',('0','1./2.','z'),4,'2..'),('c',('x','y','z'),8,'1')]
		elif id=='107': WyckList = [('a',('0','0','z'),2,'4mm'),('b',('0','1./2.','z'),4,'2mm .'),('c',('x','x','z'),8,'..m'),('d',('x','0','z'),8,'.m.'),('e',('x','y','z'),16,'1')]
		elif id=='108': WyckList = [('a',('0','0','z'),4,'4..'),('b',('1./2.','0','z'),4,'2.m m'),('c',('x','x+1./2.','z'),8,'..m'),('d',('x','y','z'),16,'1')]
		elif id=='109': WyckList = [('a',('0','0','z'),4,'2mm .'),('b',('0','y','z'),8,'.m.'),('c',('x','y','z'),16,'1')]
		elif id=='110': WyckList = [('a',('0','0','z'),8,'2..'),('b',('x','y','z'),16,'1')]
		elif id=='111': WyckList = [('a',('0','0','0'),1,'-42m'),('b',('1./2.','1./2.','1./2.'),1,'-42m'),('c',('0','0','1./2.'),1,'-42m'),('d',('1./2.','1./2.','0'),1,'-42m'),('e',('1./2.','0','0'),2,'222 .'),('f',('1./2.','0','1./2.'),2,'222 .'),('g',('0','0','z'),2,'2.m m'),('h',('1./2.','1./2.','z'),2,'2.m m'),('i',('x','0','0'),4,'.2.'),('j',('x','1./2.','1./2.'),4,'.2.'),('k',('x','0','1./2.'),4,'.2.'),('l',('x','1./2.','0'),4,'.2.'),('m',('0','1./2.','z'),4,'2..'),('n',('x','x','z'),4,'..m'),('o',('x','y','z'),8,'1')]
		elif id=='112': WyckList = [('a',('0','0','1./4.'),2,'222 .'),('b',('1./2.','0','1./4.'),2,'222 .'),('c',('1./2.','1./2.','1./4.'),2,'222 .'),('d',('0','1./2.','1./4.'),2,'222 .'),('e',('0','0','0'),2,'-4..'),('f',('1./2.','1./2.','0'),2,'-4..'),('g',('x','0','1./4.'),4,'.2.'),('h',('1./2.','y','1./4.'),4,'.2.'),('i',('x','1./2.','1./4.'),4,'.2.'),('j',('0','y','1./4.'),4,'.2.'),('k',('0','0','z'),4,'2..'),('l',('1./2.','1./2.','z'),4,'2..'),('m',('0','1./2.','z'),4,'2..'),('n',('x','y','z'),8,'1')]
		elif id=='113': WyckList = [('a',('0','0','0'),2,'-4..'),('b',('0','0','1./2.'),2,'-4..'),('c',('0','1./2.','z'),2,'2.m m'),('d',('0','0','z'),4,'2..'),('e',('x','x+1./2.','z'),4,'..m'),('f',('x','y','z'),8,'1')]
		elif id=='114': WyckList = [('a',('0','0','0'),2,'-4..'),('b',('0','0','1./2.'),2,'-4..'),('c',('0','0','z'),4,'2..'),('d',('0','1./2.','z'),4,'2..'),('e',('x','y','z'),8,'1')]
		elif id=='115': WyckList = [('a',('0','0','0'),1,'-4m2'),('b',('1./2.','1./2.','0'),1,'-4m2'),('c',('1./2.','1./2.','1./2.'),1,'-4m2'),('d',('0','0','1./2.'),1,'-4m2'),('e',('0','0','z'),2,'2mm .'),('f',('1./2.','1./2.','z'),2,'2mm .'),('g',('0','1./2.','z'),2,'2mm .'),('h',('x','x','0'),4,'..2'),('i',('x','x','1./2.'),4,'..2'),('j',('x','0','z'),4,'.m.'),('k',('x','1./2.','z'),4,'.m.'),('l',('x','y','z'),8,'1')]
		elif id=='116': WyckList = [('a',('0','0','1./4.'),2,'2.2 2'),('b',('1./2.','1./2.','1./4.'),2,'2.2 2'),('c',('0','0','0'),2,'-4..'),('d',('1./2.','1./2.','0'),2,'-4..'),('e',('x','x','1./4.'),4,'..2'),('f',('x','x','3./4.'),4,'..2'),('g',('0','0','z'),4,'2..'),('h',('1./2.','1./2.','z'),4,'2..'),('i',('0','1./2.','z'),4,'2..'),('j',('x','y','z'),8,'1')]
		elif id=='117': WyckList = [('a',('0','0','0'),2,'-4..'),('b',('0','0','1./2.'),2,'-4..'),('c',('0','1./2.','0'),2,'2.2 2'),('d',('0','1./2.','1./2.'),2,'2.2 2'),('e',('0','0','z'),4,'2..'),('f',('0','1./2.','z'),4,'2..'),('g',('x','x+1./2.','0'),4,'..2'),('h',('x','x+1./2.','1./2.'),4,'..2'),('i',('x','y','z'),8,'1')]
		elif id=='118': WyckList = [('a',('0','0','0'),2,'-4..'),('b',('0','0','1./2.'),2,'-4..'),('c',('0','1./2.','1./4.'),2,'2.2 2'),('d',('0','1./2.','3./4.'),2,'2.2 2'),('e',('0','0','z'),4,'2..'),('f',('x','-x+1./2.','1./4.'),4,'..2'),('g',('x','x+1./2.','1./4.'),4,'..2'),('h',('0','1./2.','z'),4,'2..'),('i',('x','y','z'),8,'1')]
		elif id=='119': WyckList = [('a',('0','0','0'),2,'-4m2'),('b',('0','0','1./2.'),2,'-4m2'),('c',('0','1./2.','1./4.'),2,'-4m2'),('d',('0','1./2.','3./4.'),2,'-4m2'),('e',('0','0','z'),4,'2mm .'),('f',('0','1./2.','z'),4,'2mm .'),('g',('x','x','0'),8,'..2'),('h',('x','x+1./2.','1./4.'),8,'..2'),('i',('x','0','z'),8,'.m.'),('j',('x','y','z'),16,'1')]
		elif id=='120': WyckList = [('a',('0','0','1./4.'),4,'2.2 2'),('b',('0','0','0'),4,'-4..'),('c',('0','1./2.','1./4.'),4,'-4..'),('d',('0','1./2.','0'),4,'2.2 2'),('e',('x','x','1./4.'),8,'..2'),('f',('0','0','z'),8,'2..'),('g',('0','1./2.','z'),8,'2..'),('h',('x','x+1./2.','0'),8,'..2'),('i',('x','y','z'),16,'1')]
		elif id=='121': WyckList = [('a',('0','0','0'),2,'-42m'),('b',('0','0','1./2.'),2,'-42m'),('c',('0','1./2.','0'),4,'222 .'),('d',('0','1./2.','1./4.'),4,'-4..'),('e',('0','0','z'),4,'2.m m'),('f',('x','0','0'),8,'.2.'),('g',('x','0','1./2.'),8,'.2.'),('h',('0','1./2.','z'),8,'2..'),('i',('x','x','z'),8,'..m'),('j',('x','y','z'),16,'1')]
		elif id=='122': WyckList = [('a',('0','0','0'),4,'-4..'),('b',('0','0','1./2.'),4,'-4..'),('c',('0','0','z'),8,'2..'),('d',('x','1./4.','1./8.'),8,'.2.'),('e',('x','y','z'),16,'1')]
		elif id=='123': WyckList = [('a',('0','0','0'),1,'4/mmm'),('b',('0','0','1./2.'),1,'4/mmm'),('c',('1./2.','1./2.','0'),1,'4/mmm'),('d',('1./2.','1./2.','1./2.'),1,'4/mmm'),('e',('0','1./2.','1./2.'),2,'mmm .'),('f',('0','1./2.','0'),2,'mmm .'),('g',('0','0','z'),2,'4mm'),('h',('1./2.','1./2.','z'),2,'4mm'),('i',('0','1./2.','z'),4,'2mm .'),('j',('x','x','0'),4,'m.2 m'),('k',('x','x','1./2.'),4,'m.2 m'),('l',('x','0','0'),4,'m2m .'),('m',('x','0','1./2.'),4,'m2m .'),('n',('x','1./2.','0'),4,'m2m .'),('o',('x','1./2.','1./2.'),4,'m2m .'),('p',('x','y','0'),8,'m..'),('q',('x','y','1./2.'),8,'m..'),('r',('x','x','z'),8,'..m'),('s',('x','0','z'),8,'.m.'),('t',('x','1./2.','z'),8,'.m.'),('u',('x','y','z'),16,'1')]
		elif id=='124': WyckList = [('a',('0','0','1./4.'),2,'422'),('b',('0','0','0'),2,'4/m..'),('c',('1./2.','1./2.','1./4.'),2,'422'),('d',('1./2.','1./2.','0'),2,'4/m..'),('e',('0','1./2.','0'),4,'2/m..'),('f',('0','1./2.','1./4.'),4,'222 .'),('g',('0','0','z'),4,'4..'),('h',('1./2.','1./2.','z'),4,'4..'),('i',('0','1./2.','z'),8,'2..'),('j',('x','x','1./4.'),8,'..2'),('k',('x','0','1./4.'),8,'.2.'),('l',('x','1./2.','1./4.'),8,'.2.'),('m',('x','y','0'),8,'m..'),('n',('x','y','z'),16,'1')]
		elif id=='125:1': WyckList = [('a',('0','0','0'),2,'422'),('b',('0','0','1./2.'),2,'422'),('c',('0','1./2.','0'),2,'-42m'),('d',('0','1./2.','1./2.'),2,'-42m'),('e',('1./4.','1./4.','0'),4,'..2/m'),('f',('1./4.','1./4.','1./2.'),4,'..2/m'),('g',('0','0','z'),4,'4..'),('h',('0','1./2.','z'),4,'2.m m'),('i',('x','x','0'),8,'..2'),('j',('x','x','1./2.'),8,'..2'),('k',('x','0','0'),8,'.2.'),('l',('x','0','1./2.'),8,'.2.'),('m',('x','x+1./2.','z'),8,'..m'),('n',('x','y','z'),16,'1')]
		elif id=='125:2': WyckList = [('a',('1./4.','1./4.','0'),2,'422'),('b',('1./4.','1./4.','1./2.'),2,'422'),('c',('1./4.','3./4.','0'),2,'-42m'),('d',('1./4.','3./4.','1./2.'),2,'-42m'),('e',('1./2.','1./2.','0'),4,'..2/m'),('f',('1./2.','1./2.','1./2.'),4,'..2/m'),('g',('1./4.','1./4.','z'),4,'4..'),('h',('1./4.','3./4.','z'),4,'2.m m'),('i',('x+1./4.','x+1./4.','0'),8,'..2'),('j',('x+1./4.','x+1./4.','1./2.'),8,'..2'),('k',('x+1./4.','1./4.','0'),8,'.2.'),('l',('x+1./4.','1./4.','1./2.'),8,'.2.'),('m',('x+1./4.','x+3./4.','z'),8,'..m'),('n',('x','y','z'),16,'1')]
		elif id=='126:1': WyckList = [('a',('0','0','0'),2,'422'),('b',('0','0','1./2.'),2,'422'),('c',('1./2.','0','0'),4,'222 .'),('d',('1./2.','0','1./4.'),4,'-4..'),('e',('0','0','z'),4,'4..'),('f',('1./4.','1./4.','1./4.'),8,'-1'),('g',('1./2.','0','z'),8,'2..'),('h',('x','x','0'),8,'..2'),('i',('x','0','0'),8,'.2.'),('j',('x','0','1./2.'),8,'.2.'),('k',('x','y','z'),16,'1')]
		elif id=='126:2': WyckList = [('a',('1./4.','1./4.','1./4.'),2,'422'),('b',('1./4.','1./4.','3./4.'),2,'422'),('c',('3./4.','1./4.','1./4.'),4,'222 .'),('d',('3./4.','1./4.','1./2.'),4,'-4..'),('e',('1./4.','1./4.','z+1./4.'),4,'4..'),('f',('1./2.','1./2.','1./2.'),8,'-1'),('g',('3./4.','1./4.','z+1./4.'),8,'2..'),('h',('x+1./4.','x+1./4.','1./4.'),8,'..2'),('i',('x+1./4.','1./4.','1./4.'),8,'.2.'),('j',('x+1./4.','1./4.','3./4.'),8,'.2.'),('k',('x','y','z'),16,'1')]
		elif id=='127': WyckList = [('a',('0','0','0'),2,'4/m..'),('b',('0','0','1./2.'),2,'4/m..'),('c',('0','1./2.','1./2.'),2,'m.m m'),('d',('0','1./2.','0'),2,'m.m m'),('e',('0','0','z'),4,'4..'),('f',('0','1./2.','z'),4,'2.m m'),('g',('x','x+1./2.','0'),4,'m.2 m'),('h',('x','x+1./2.','1./2.'),4,'m.2 m'),('i',('x','y','0'),8,'m..'),('j',('x','y','1./2.'),8,'m..'),('k',('x','x+1./2.','z'),8,'..m'),('l',('x','y','z'),16,'1')]
		elif id=='128': WyckList = [('a',('0','0','0'),2,'4/m..'),('b',('0','0','1./2.'),2,'4/m..'),('c',('0','1./2.','0'),4,'2/m..'),('d',('0','1./2.','1./4.'),4,'2.2 2'),('e',('0','0','z'),4,'4..'),('f',('0','1./2.','z'),8,'2..'),('g',('x','x+1./2.','1./4.'),8,'..2'),('h',('x','y','0'),8,'m..'),('i',('x','y','z'),16,'1')]
		elif id=='129:1': WyckList = [('a',('0','0','0'),2,'-4m2'),('b',('0','0','1./2.'),2,'-4m2'),('c',('0','1./2.','z'),2,'4mm'),('d',('1./4.','1./4.','0'),4,'..2/m'),('e',('1./4.','1./4.','1./2.'),4,'..2/m'),('f',('0','0','z'),4,'2mm .'),('g',('x','x','0'),8,'..2'),('h',('x','x','1./2.'),8,'..2'),('i',('0','y','z'),8,'.m.'),('j',('x','x+1./2.','z'),8,'..m'),('k',('x','y','z'),16,'1')]
		elif id=='129:2': WyckList = [('a',('1./4.','3./4.','0'),2,'-4m2'),('b',('1./4.','3./4.','1./2.'),2,'-4m2'),('c',('1./4.','1./4.','z'),2,'4mm'),('d',('1./2.','0','0'),4,'..2/m'),('e',('1./2.','0','1./2.'),4,'..2/m'),('f',('1./4.','3./4.','z'),4,'2mm .'),('g',('x+1./4.','x-1./4.','0'),8,'..2'),('h',('x+1./4.','x-1./4.','1./2.'),8,'..2'),('i',('1./4.','y-1./4.','z'),8,'.m.'),('j',('x+1./4.','x+1./4.','z'),8,'..m'),('k',('x','y','z'),16,'1')]
		elif id=='130:1': WyckList = [('a',('0','0','1./4.'),4,'2.2 2'),('b',('0','0','0'),4,'-4..'),('c',('0','1./2.','z'),4,'4..'),('d',('1./4.','1./4.','0'),8,'-1'),('e',('0','0','z'),8,'2..'),('f',('x','x','1./4.'),8,'..2'),('g',('x','y','z'),16,'1')]
		elif id=='130:2': WyckList = [('a',('1./4.','3./4.','1./4.'),4,'2.2 2'),('b',('1./4.','3./4.','0'),4,'-4..'),('c',('1./4.','1./4.','z'),4,'4..'),('d',('1./2.','0','0'),8,'-1'),('e',('1./4.','3./4.','z'),8,'2..'),('f',('x+1./4.','x-1./4.','1./4.'),8,'..2'),('g',('x','y','z'),16,'1')]
		elif id=='131': WyckList = [('a',('0','0','0'),2,'mmm .'),('b',('1./2.','1./2.','0'),2,'mmm .'),('c',('0','1./2.','0'),2,'mmm .'),('d',('0','1./2.','1./2.'),2,'mmm .'),('e',('0','0','1./4.'),2,'-4m2'),('f',('1./2.','1./2.','1./4.'),2,'-4m2'),('g',('0','0','z'),4,'2mm .'),('h',('1./2.','1./2.','z'),4,'2mm .'),('i',('0','1./2.','z'),4,'2mm .'),('j',('x','0','0'),4,'m2m .'),('k',('x','1./2.','1./2.'),4,'m2m .'),('l',('x','0','1./2.'),4,'m2m .'),('m',('x','1./2.','0'),4,'m2m .'),('n',('x','x','1./4.'),8,'..2'),('o',('0','y','z'),8,'.m.'),('p',('1./2.','y','z'),8,'.m.'),('q',('x','y','0'),8,'m..'),('r',('x','y','z'),16,'1')]
		elif id=='132': WyckList = [('a',('0','0','0'),2,'m.m m'),('b',('0','0','1./4.'),2,'-42m'),('c',('1./2.','1./2.','0'),2,'m.m m'),('d',('1./2.','1./2.','1./4.'),2,'-42m'),('e',('0','1./2.','1./4.'),4,'222 .'),('f',('0','1./2.','0'),4,'2/m..'),('g',('0','0','z'),4,'2.m m'),('h',('1./2.','1./2.','z'),4,'2.m m'),('i',('x','x','0'),4,'m.2 m'),('j',('x','x','1./2.'),4,'m.2 m'),('k',('0','1./2.','z'),8,'2..'),('l',('x','0','1./4.'),8,'.2.'),('m',('x','1./2.','1./4.'),8,'.2.'),('n',('x','y','0'),8,'m..'),('o',('x','x','z'),8,'..m'),('p',('x','y','z'),16,'1')]
		elif id=='133:1': WyckList = [('a',('0','1./2.','1./4.'),4,'222 .'),('b',('0','0','1./4.'),4,'222 .'),('c',('0','1./2.','0'),4,'2.2 2'),('d',('0','0','0'),4,'-4..'),('e',('1./4.','1./4.','1./4.'),8,'-1'),('f',('0','1./2.','z'),8,'2..'),('g',('0','0','z'),8,'2..'),('h',('x','0','1./4.'),8,'.2.'),('i',('x','0','3./4.'),8,'.2.'),('j',('x','x+1./2.','0'),8,'..2'),('k',('x','y','z'),16,'1')]
		elif id=='133:2': WyckList = [('a',('1./4.','1./4.','0'),4,'222 .'),('b',('1./4.','3./4.','0'),4,'222 .'),('c',('1./4.','1./4.','3./4.'),4,'2.2 2'),('d',('1./4.','3./4.','3./4.'),4,'-4..'),('e',('1./2.','0','0'),8,'-1'),('f',('1./4.','1./4.','z-1./4.'),8,'2..'),('g',('1./4.','3./4.','z-1./4.'),8,'2..'),('h',('x+1./4.','3./4.','0'),8,'.2.'),('i',('x+1./4.','3./4.','1./2.'),8,'.2.'),('j',('x+1./4.','x+1./4.','3./4.'),8,'..2'),('k',('x','y','z'),16,'1')]
		elif id=='134:1': WyckList = [('a',('0','0','0'),2,'-42m'),('b',('0','0','1./2.'),2,'-42m'),('c',('0','1./2.','0'),4,'222 .'),('d',('0','1./2.','1./4.'),4,'2.2 2'),('e',('1./4.','1./4.','1./4.'),4,'..2/m'),('f',('3./4.','3./4.','3./4.'),4,'..2/m'),('g',('0','0','z'),4,'2.m m'),('h',('0','1./2.','z'),8,'2..'),('i',('x','0','0'),8,'.2.'),('j',('x','0','1./2.'),8,'.2.'),('k',('x','x+1./2.','1./4.'),8,'..2'),('l',('x','x+1./2.','3./4.'),8,'..2'),('m',('x','x','z'),8,'..m'),('n',('x','y','z'),16,'1')]
		elif id=='134:2': WyckList = [('a',('1./4.','3./4.','1./4.'),2,'-42m'),('b',('1./4.','3./4.','3./4.'),2,'-42m'),('c',('1./4.','1./4.','1./4.'),4,'222 .'),('d',('1./4.','1./4.','1./2.'),4,'2.2 2'),('e',('1./2.','0','1./2.'),4,'..2/m'),('f',('0','1./2.','0'),4,'..2/m'),('g',('1./4.','3./4.','z+1./4.'),4,'2.m m'),('h',('1./4.','1./4.','z+1./4.'),8,'2..'),('i',('x+1./4.','3./4.','1./4.'),8,'.2.'),('j',('x+1./4.','3./4.','3./4.'),8,'.2.'),('k',('x+1./4.','x+1./4.','1./2.'),8,'..2'),('l',('x+1./4.','x+1./4.','0'),8,'..2'),('m',('x+1./4.','x-1./4.','z+1./4.'),8,'..m'),('n',('x','y','z'),16,'1')]
		elif id=='135': WyckList = [('a',('0','0','0'),4,'2/m..'),('b',('0','0','1./4.'),4,'-4..'),('c',('0','1./2.','0'),4,'2/m..'),('d',('0','1./2.','1./4.'),4,'2.2 2'),('e',('0','0','z'),8,'2..'),('f',('0','1./2.','z'),8,'2..'),('g',('x','x+1./2.','1./4.'),8,'..2'),('h',('x','y','0'),8,'m..'),('i',('x','y','z'),16,'1')]
		elif id=='136': WyckList = [('a',('0','0','0'),2,'m.m m'),('b',('0','0','1./2.'),2,'m.m m'),('c',('0','1./2.','0'),4,'2/m..'),('d',('0','1./2.','1./4.'),4,'-4..'),('e',('0','0','z'),4,'2.m m'),('f',('x','x','0'),4,'m.2 m'),('g',('x','-x','0'),4,'m.2 m'),('h',('0','1./2.','z'),8,'2..'),('i',('x','y','0'),8,'m..'),('j',('x','x','z'),8,'..m'),('k',('x','y','z'),16,'1')]
		elif id=='137:1': WyckList = [('a',('0','0','0'),2,'-4m2'),('b',('0','0','1./2.'),2,'-4m2'),('c',('0','0','z'),4,'2mm .'),('d',('0','1./2.','z'),4,'2mm .'),('e',('1./4.','1./4.','1./4.'),8,'-1'),('f',('x','x','0'),8,'..2'),('g',('0','y','z'),8,'.m.'),('h',('x','y','z'),16,'1')]
		elif id=='137:2': WyckList = [('a',('1./4.','3./4.','3./4.'),2,'-4m2'),('b',('1./4.','3./4.','1./4.'),2,'-4m2'),('c',('1./4.','3./4.','z-1./4.'),4,'2mm .'),('d',('1./4.','1./4.','z-1./4.'),4,'2mm .'),('e',('1./2.','0','0'),8,'-1'),('f',('x+1./4.','x-1./4.','3./4.'),8,'..2'),('g',('1./4.','y-1./4.','z-1./4.'),8,'.m.'),('h',('x','y','z'),16,'1')]
		elif id=='138:1': WyckList = [('a',('0','0','1./4.'),4,'2.2 2'),('b',('0','0','0'),4,'-4..'),('c',('1./4.','1./4.','1./4.'),4,'..2/m'),('d',('1./4.','1./4.','3./4.'),4,'..2/m'),('e',('0','1./2.','z'),4,'2.m m'),('f',('0','0','z'),8,'2..'),('g',('x','x','1./4.'),8,'..2'),('h',('x','x','3./4.'),8,'..2'),('i',('x','x+1./2.','z'),8,'..m'),('j',('x','y','z'),16,'1')]
		elif id=='138:2': WyckList = [('a',('1./4.','3./4.','1./2.'),4,'2.2 2'),('b',('1./4.','3./4.','1./4.'),4,'-4..'),('c',('1./2.','0','1./2.'),4,'..2/m'),('d',('1./2.','0','0'),4,'..2/m'),('e',('1./4.','1./4.','z+1./4.'),4,'2.m m'),('f',('1./4.','3./4.','z+1./4.'),8,'2..'),('g',('x+1./4.','x-1./4.','1./2.'),8,'..2'),('h',('x+1./4.','x-1./4.','0'),8,'..2'),('i',('x+1./4.','x+1./4.','z+1./4.'),8,'..m'),('j',('x','y','z'),16,'1')]
		elif id=='139': WyckList = [('a',('0','0','0'),2,'4/mmm'),('b',('0','0','1./2.'),2,'4/mmm'),('c',('0','1./2.','0'),4,'mmm .'),('d',('0','1./2.','1./4.'),4,'-4m2'),('e',('0','0','z'),4,'4mm'),('f',('1./4.','1./4.','1./4.'),8,'..2/m'),('g',('0','1./2.','z'),8,'2mm .'),('h',('x','x','0'),8,'m.2 m'),('i',('x','0','0'),8,'m2m .'),('j',('x','1./2.','0'),8,'m2m .'),('k',('x','x+1./2.','1./4.'),16,'..2'),('l',('x','y','0'),16,'m..'),('m',('x','x','z'),16,'..m'),('n',('0','y','z'),16,'.m.'),('o',('x','y','z'),32,'1')]
		elif id=='140': WyckList = [('a',('0','0','1./4.'),4,'422'),('b',('0','1./2.','1./4.'),4,'-42m'),('c',('0','0','0'),4,'4/m..'),('d',('0','1./2.','0'),4,'m.m m'),('e',('1./4.','1./4.','1./4.'),8,'..2/m'),('f',('0','0','z'),8,'4..'),('g',('0','1./2.','z'),8,'2.m m'),('h',('x','x+1./2.','0'),8,'m.2 m'),('i',('x','x','1./4.'),16,'..2'),('j',('x','0','1./4.'),16,'.2.'),('k',('x','y','0'),16,'m..'),('l',('x','x+1./2.','z'),16,'..m'),('m',('x','y','z'),32,'1')]
		elif id=='141:1': WyckList = [('a',('0','0','0'),4,'-4m2'),('b',('0','0','1./2.'),4,'-4m2'),('c',('0','1./4.','1./8.'),8,'.2/m.'),('d',('0','1./4.','5./8.'),8,'.2/m.'),('e',('0','0','z'),8,'2mm .'),('f',('x','1./4.','1./8.'),16,'.2.'),('g',('x','x','0'),16,'..2'),('h',('0','y','z'),16,'.m.'),('i',('x','y','z'),32,'1')]
		elif id=='141:2': WyckList = [('a',('0','1./4.','7./8.'),4,'-4m2'),('b',('0','1./4.','3./8.'),4,'-4m2'),('c',('0','1./2.','0'),8,'.2/m.'),('d',('0','1./2.','1./2.'),8,'.2/m.'),('e',('0','1./4.','z-1./8.'),8,'2mm .'),('f',('x','1./2.','0'),16,'.2.'),('g',('x','x+1./4.','7./8.'),16,'..2'),('h',('0','y+1./4.','z-1./8.'),16,'.m.'),('i',('x','y','z'),32,'1')]
		elif id=='142:1': WyckList = [('a',('0','0','0'),8,'-4..'),('b',('0','0','1./4.'),8,'2.2 2'),('c',('0','1./4.','1./8.'),16,'-1'),('d',('0','0','z'),16,'2..'),('e',('1./4.','y','1./8.'),16,'.2.'),('f',('x','x','1./4.'),16,'..2'),('g',('x','y','z'),32,'1')]
		elif id=='142:2': WyckList = [('a',('0','1./4.','7./8.'),8,'-4..'),('b',('0','1./4.','1./8.'),8,'2.2 2'),('c',('0','1./2.','0'),16,'-1'),('d',('0','1./4.','z-1./8.'),16,'2..'),('e',('1./4.','y+1./4.','0'),16,'.2.'),('f',('x','x+1./4.','1./8.'),16,'..2'),('g',('x','y','z'),32,'1')]
		elif id=='143': WyckList = [('a',('0','0','z'),1,'3..'),('b',('1./3.','2./3.','z'),1,'3..'),('c',('2./3.','1./3.','z'),1,'3..'),('d',('x','y','z'),3,'1')]
		elif id=='144': WyckList = [('a',('x','y','z'),3,'1')]
		elif id=='145': WyckList = [('a',('x','y','z'),3,'1')]
		elif id=='146:H': WyckList = [('a',('0','0','z'),3,'3.'),('b',('x','y','z'),9,'1')]
		elif id=='146:R': WyckList = [('a',('z','z','z'),3,'3.'),('b',('x','y','z'),9,'1')]
		elif id=='147': WyckList = [('a',('0','0','0'),1,'-3..'),('b',('0','0','1./2.'),1,'-3..'),('c',('0','0','z'),2,'3..'),('d',('1./3.','2./3.','z'),2,'3..'),('e',('1./2.','0','0'),3,'-1'),('f',('1./2.','0','1./2.'),3,'-1'),('g',('x','y','z'),6,'1')]
		elif id=='148:H': WyckList = [('a',('0','0','0'),3,'-3.'),('b',('0','0','1./2.'),3,'-3.'),('c',('0','0','z'),6,'3.'),('d',('1./2.','0','1./2.'),9,'-1'),('e',('1./2.','0','0'),9,'-1'),('f',('x','y','z'),18,'1')]
		elif id=='148:R': WyckList = [('a',('0','0','0'),3,'-3.'),('b',('1./2.','1./2.','1./2.'),3,'-3.'),('c',('z','z','z'),6,'3.'),('d',('0','0','1./2.'),9,'-1'),('e',('1./2.','1./2.','0'),9,'-1'),('f',('x','y','z'),18,'1')]
		elif id=='149': WyckList = [('a',('0','0','0'),1,'3.2'),('b',('0','0','1./2.'),1,'3.2'),('c',('1./3.','2./3.','0'),1,'3.2'),('d',('1./3.','2./3.','1./2.'),1,'3.2'),('e',('2./3.','1./3.','0'),1,'3.2'),('f',('2./3.','1./3.','1./2.'),1,'3.2'),('g',('0','0','z'),2,'3..'),('h',('1./3.','2./3.','z'),2,'3..'),('i',('2./3.','1./3.','z'),2,'3..'),('j',('x','-x','0'),3,'..2'),('k',('x','-x','1./2.'),3,'..2'),('l',('x','y','z'),6,'1')]
		elif id=='150': WyckList = [('a',('0','0','0'),1,'32.'),('b',('0','0','1./2.'),1,'32.'),('c',('0','0','z'),2,'3..'),('d',('1./3.','2./3.','z'),2,'3..'),('e',('x','0','0'),3,'.2.'),('f',('x','0','1./2.'),3,'.2.'),('g',('x','y','z'),6,'1')]
		elif id=='151': WyckList = [('a',('x','-x','1./3.'),3,'..2'),('b',('x','-x','5./6.'),3,'..2'),('c',('x','y','z'),6,'1')]
		elif id=='152': WyckList = [('a',('x','0','1./3.'),3,'.2.'),('b',('x','0','5./6.'),3,'.2.'),('c',('x','y','z'),6,'1')]
		elif id=='153': WyckList = [('a',('x','-x','2./3.'),3,'..2'),('b',('x','-x','1./6.'),3,'..2'),('c',('x','y','z'),6,'1')]
		elif id=='154': WyckList = [('a',('x','0','2./3.'),3,'.2.'),('b',('x','0','1./6.'),3,'.2.'),('c',('x','y','z'),6,'1')]
		elif id=='155:H': WyckList = [('a',('0','0','0'),3,'32'),('b',('0','0','1./2.'),3,'32'),('c',('0','0','z'),6,'3.'),('d',('x','0','0'),9,'.2'),('e',('x','0','1./2.'),9,'.2'),('f',('x','y','z'),18,'1')]
		elif id=='155:R': WyckList = [('a',('0','0','0'),3,'32'),('b',('1./2.','1./2.','1./2.'),3,'32'),('c',('z','z','z'),6,'3.'),('d',('x','-x','0'),9,'.2'),('e',('x+1./2.','-x+1./2.','1./2.'),9,'.2'),('f',('x','y','z'),18,'1')]
		elif id=='156': WyckList = [('a',('0','0','z'),1,'3m.'),('b',('1./3.','2./3.','z'),1,'3m.'),('c',('2./3.','1./3.','z'),1,'3m.'),('d',('x','-x','z'),3,'.m.'),('e',('x','y','z'),6,'1')]
		elif id=='157': WyckList = [('a',('0','0','z'),1,'3.m'),('b',('1./3.','2./3.','z'),2,'3..'),('c',('x','0','z'),3,'..m'),('d',('x','y','z'),6,'1')]
		elif id=='158': WyckList = [('a',('0','0','z'),2,'3..'),('b',('1./3.','2./3.','z'),2,'3..'),('c',('2./3.','1./3.','z'),2,'3..'),('d',('x','y','z'),6,'1')]
		elif id=='159': WyckList = [('a',('0','0','z'),2,'3..'),('b',('1./3.','2./3.','z'),2,'3..'),('c',('x','y','z'),6,'1')]
		elif id=='160:H': WyckList = [('a',('0','0','z'),3,'3m'),('b',('x','-x','z'),9,'.m'),('c',('x','y','z'),18,'1')]
		elif id=='160:R': WyckList = [('a',('z','z','z'),3,'3m'),('b',('x+z','-2x+z','x+z'),9,'.m'),('c',('x','y','z'),18,'1')]
		elif id=='161:H': WyckList = [('a',('0','0','z'),6,'3.'),('b',('x','y','z'),18,'1')]
		elif id=='161:R': WyckList = [('a',('z','z','z'),6,'3.'),('b',('x','y','z'),18,'1')]
		elif id=='162': WyckList = [('a',('0','0','0'),1,'-3.m'),('b',('0','0','1./2.'),1,'-3.m'),('c',('1./3.','2./3.','0'),2,'3.2'),('d',('1./3.','2./3.','1./2.'),2,'3.2'),('e',('0','0','z'),2,'3.m'),('f',('1./2.','0','0'),3,'..2/m'),('g',('1./2.','0','1./2.'),3,'..2/m'),('h',('1./3.','2./3.','z'),4,'3..'),('i',('x','-x','0'),6,'..2'),('j',('x','-x','1./2.'),6,'..2'),('k',('x','0','z'),6,'..m'),('l',('x','y','z'),12,'1')]
		elif id=='163': WyckList = [('a',('0','0','1./4.'),2,'3.2'),('b',('0','0','0'),2,'-3..'),('c',('1./3.','2./3.','1./4.'),2,'3.2'),('d',('2./3.','1./3.','1./4.'),2,'3.2'),('e',('0','0','z'),4,'3..'),('f',('1./3.','2./3.','z'),4,'3..'),('g',('1./2.','0','0'),6,'-1'),('h',('x','-x','1./4.'),6,'..2'),('i',('x','y','z'),12,'1')]
		elif id=='164': WyckList = [('a',('0','0','0'),1,'-3m.'),('b',('0','0','1./2.'),1,'-3m.'),('c',('0','0','z'),2,'3m.'),('d',('1./3.','2./3.','z'),2,'3m.'),('e',('1./2.','0','0'),3,'.2/m.'),('f',('1./2.','0','1./2.'),3,'.2/m.'),('g',('x','0','0'),6,'.2.'),('h',('x','0','1./2.'),6,'.2.'),('i',('x','-x','z'),6,'.m.'),('j',('x','y','z'),12,'1')]
		elif id=='165': WyckList = [('a',('0','0','1./4.'),2,'32.'),('b',('0','0','0'),2,'-3..'),('c',('0','0','z'),4,'3..'),('d',('1./3.','2./3.','z'),4,'3..'),('e',('1./2.','0','0'),6,'-1'),('f',('x','0','1./4.'),6,'.2.'),('g',('x','y','z'),12,'1')]
		elif id=='166:H': WyckList = [('a',('0','0','0'),3,'-3m'),('b',('0','0','1./2.'),3,'-3m'),('c',('0','0','z'),6,'3m'),('d',('1./2.','0','1./2.'),9,'.2/m'),('e',('1./2.','0','0'),9,'.2/m'),('f',('x','0','0'),18,'.2'),('g',('x','0','1./2.'),18,'.2'),('h',('x','-x','z'),18,'.m'),('i',('x','y','z'),36,'1')]
		elif id=='166:R': WyckList = [('a',('0','0','0'),3,'-3m'),('b',('1./2.','1./2.','1./2.'),3,'-3m'),('c',('z','z','z'),6,'3m'),('d',('0','0','1./2.'),9,'.2/m'),('e',('1./2.','1./2.','0'),9,'.2/m'),('f',('x','-x','0'),18,'.2'),('g',('x+1./2.','-x+1./2.','1./2.'),18,'.2'),('h',('x+z','-2x+z','x+z'),18,'.m'),('i',('x','y','z'),36,'1')]
		elif id=='167:H': WyckList = [('a',('0','0','1./4.'),6,'32'),('b',('0','0','0'),6,'-3.'),('c',('0','0','z'),12,'3.'),('d',('1./2.','0','0'),18,'-1'),('e',('x','0','1./4.'),18,'.2'),('f',('x','y','z'),36,'1')]
		elif id=='167:R': WyckList = [('a',('1./4.','1./4.','1./4.'),6,'32'),('b',('0','0','0'),6,'-3.'),('c',('z','z','z'),12,'3.'),('d',('1./2.','1./2.','0'),18,'-1'),('e',('x+1./4.','-x+1./4.','1./4.'),18,'.2'),('f',('x','y','z'),36,'1')]
		elif id=='168': WyckList = [('a',('0','0','z'),1,'6..'),('b',('1./3.','2./3.','z'),2,'3..'),('c',('1./2.','0','z'),3,'2..'),('d',('x','y','z'),6,'1')]
		elif id=='169': WyckList = [('a',('x','y','z'),6,'1')]
		elif id=='170': WyckList = [('a',('x','y','z'),6,'1')]
		elif id=='171': WyckList = [('a',('0','0','z'),3,'2..'),('b',('1./2.','1./2.','z'),3,'2..'),('c',('x','y','z'),6,'1')]
		elif id=='172': WyckList = [('a',('0','0','z'),3,'2..'),('b',('1./2.','1./2.','z'),3,'2..'),('c',('x','y','z'),6,'1')]
		elif id=='173': WyckList = [('a',('0','0','z'),2,'3..'),('b',('1./3.','2./3.','z'),2,'3..'),('c',('x','y','z'),6,'1')]
		elif id=='174': WyckList = [('a',('0','0','0'),1,'-6..'),('b',('0','0','1./2.'),1,'-6..'),('c',('1./3.','2./3.','0'),1,'-6..'),('d',('1./3.','2./3.','1./2.'),1,'-6..'),('e',('2./3.','1./3.','0'),1,'-6..'),('f',('2./3.','1./3.','1./2.'),1,'-6..'),('g',('0','0','z'),2,'3..'),('h',('1./3.','2./3.','z'),2,'3..'),('i',('2./3.','1./3.','z'),2,'3..'),('j',('x','y','0'),3,'m..'),('k',('x','y','1./2.'),3,'m..'),('l',('x','y','z'),6,'1')]
		elif id=='175': WyckList = [('a',('0','0','0'),1,'6/m..'),('b',('0','0','1./2.'),1,'6/m..'),('c',('1./3.','2./3.','0'),2,'-6..'),('d',('1./3.','2./3.','1./2.'),2,'-6..'),('e',('0','0','z'),2,'6..'),('f',('1./2.','0','0'),3,'2/m..'),('g',('1./2.','0','1./2.'),3,'2/m..'),('h',('1./3.','2./3.','z'),4,'3..'),('i',('1./2.','0','z'),6,'2..'),('j',('x','y','0'),6,'m..'),('k',('x','y','1./2.'),6,'m..'),('l',('x','y','z'),12,'1')]
		elif id=='176': WyckList = [('a',('0','0','1./4.'),2,'-6..'),('b',('0','0','0'),2,'-3..'),('c',('1./3.','2./3.','1./4.'),2,'-6..'),('d',('2./3.','1./3.','1./4.'),2,'-6..'),('e',('0','0','z'),4,'3..'),('f',('1./3.','2./3.','z'),4,'3..'),('g',('1./2.','0','0'),6,'-1'),('h',('x','y','1./4.'),6,'m..'),('i',('x','y','z'),12,'1')]
		elif id=='177': WyckList = [('a',('0','0','0'),1,'622'),('b',('0','0','1./2.'),1,'622'),('c',('1./3.','2./3.','0'),2,'3.2'),('d',('1./3.','2./3.','1./2.'),2,'3.2'),('e',('0','0','z'),2,'6..'),('f',('1./2.','0','0'),3,'222'),('g',('1./2.','0','1./2.'),3,'222'),('h',('1./3.','2./3.','z'),4,'3..'),('i',('1./2.','0','z'),6,'2..'),('j',('x','0','0'),6,'.2.'),('k',('x','0','1./2.'),6,'.2.'),('l',('x','-x','0'),6,'..2'),('m',('x','-x','1./2.'),6,'..2'),('n',('x','y','z'),12,'1')]
		elif id=='178': WyckList = [('a',('x','0','0'),6,'.2.'),('b',('x','2x','1./4.'),6,'..2'),('c',('x','y','z'),12,'1')]
		elif id=='179': WyckList = [('a',('x','0','0'),6,'.2.'),('b',('x','2x','3./4.'),6,'..2'),('c',('x','y','z'),12,'1')]
		elif id=='180': WyckList = [('a',('0','0','0'),3,'222'),('b',('0','0','1./2.'),3,'222'),('c',('1./2.','0','0'),3,'222'),('d',('1./2.','0','1./2.'),3,'222'),('e',('0','0','z'),6,'2..'),('f',('1./2.','0','z'),6,'2..'),('g',('x','0','0'),6,'.2.'),('h',('x','0','1./2.'),6,'.2.'),('i',('x','2x','0'),6,'..2'),('j',('x','2x','1./2.'),6,'..2'),('k',('x','y','z'),12,'1')]
		elif id=='181': WyckList = [('a',('0','0','0'),3,'222'),('b',('0','0','1./2.'),3,'222'),('c',('1./2.','0','0'),3,'222'),('d',('1./2.','0','1./2.'),3,'222'),('e',('0','0','z'),6,'2..'),('f',('1./2.','0','z'),6,'2..'),('g',('x','0','0'),6,'.2.'),('h',('x','0','1./2.'),6,'.2.'),('i',('x','2x','0'),6,'..2'),('j',('x','2x','1./2.'),6,'..2'),('k',('x','y','z'),12,'1')]
		elif id=='182': WyckList = [('a',('0','0','0'),2,'32.'),('b',('0','0','1./4.'),2,'3.2'),('c',('1./3.','2./3.','1./4.'),2,'3.2'),('d',('1./3.','2./3.','3./4.'),2,'3.2'),('e',('0','0','z'),4,'3..'),('f',('1./3.','2./3.','z'),4,'3..'),('g',('x','0','0'),6,'.2.'),('h',('x','2x','1./4.'),6,'..2'),('i',('x','y','z'),12,'1')]
		elif id=='183': WyckList = [('a',('0','0','z'),1,'6mm'),('b',('1./3.','2./3.','z'),2,'3m.'),('c',('1./2.','0','z'),3,'2mm'),('d',('x','0','z'),6,'..m'),('e',('x','-x','z'),6,'.m.'),('f',('x','y','z'),12,'1')]
		elif id=='184': WyckList = [('a',('0','0','z'),2,'6..'),('b',('1./3.','2./3.','z'),4,'3..'),('c',('1./2.','0','z'),6,'2..'),('d',('x','y','z'),12,'1')]
		elif id=='185': WyckList = [('a',('0','0','z'),2,'3.m'),('b',('1./3.','2./3.','z'),4,'3..'),('c',('x','0','z'),6,'..m'),('d',('x','y','z'),12,'1')]
		elif id=='186': WyckList = [('a',('0','0','z'),2,'3m.'),('b',('1./3.','2./3.','z'),2,'3m.'),('c',('x','-x','z'),6,'.m.'),('d',('x','y','z'),12,'1')]
		elif id=='187': WyckList = [('a',('0','0','0'),1,'-6m2'),('b',('0','0','1./2.'),1,'-6m2'),('c',('1./3.','2./3.','0'),1,'-6m2'),('d',('1./3.','2./3.','1./2.'),1,'-6m2'),('e',('2./3.','1./3.','0'),1,'-6m2'),('f',('2./3.','1./3.','1./2.'),1,'-6m2'),('g',('0','0','z'),2,'3m.'),('h',('1./3.','2./3.','z'),2,'3m.'),('i',('2./3.','1./3.','z'),2,'3m.'),('j',('x','-x','0'),3,'mm2'),('k',('x','-x','1./2.'),3,'mm2'),('l',('x','y','0'),6,'m..'),('m',('x','y','1./2.'),6,'m..'),('n',('x','-x','z'),6,'.m.'),('o',('x','y','z'),12,'1')]
		elif id=='188': WyckList = [('a',('0','0','0'),2,'3.2'),('b',('0','0','1./4.'),2,'-6..'),('c',('1./3.','2./3.','0'),2,'3.2'),('d',('1./3.','2./3.','1./4.'),2,'-6..'),('e',('2./3.','1./3.','0'),2,'3.2'),('f',('2./3.','1./3.','1./4.'),2,'-6..'),('g',('0','0','z'),4,'3..'),('h',('1./3.','2./3.','z'),4,'3..'),('i',('2./3.','1./3.','z'),4,'3..'),('j',('x','-x','0'),6,'..2'),('k',('x','y','1./4.'),6,'m..'),('l',('x','y','z'),12,'1')]
		elif id=='189': WyckList = [('a',('0','0','0'),1,'-62m'),('b',('0','0','1./2.'),1,'-62m'),('c',('1./3.','2./3.','0'),2,'-6..'),('d',('1./3.','2./3.','1./2.'),2,'-6..'),('e',('0','0','z'),2,'3.m'),('f',('x','0','0'),3,'m2m'),('g',('x','0','1./2.'),3,'m2m'),('h',('1./3.','2./3.','z'),4,'3..'),('i',('x','0','z'),6,'..m'),('j',('x','y','0'),6,'m..'),('k',('x','y','1./2.'),6,'m..'),('l',('x','y','z'),12,'1')]
		elif id=='190': WyckList = [('a',('0','0','0'),2,'32.'),('b',('0','0','1./4.'),2,'-6..'),('c',('1./3.','2./3.','1./4.'),2,'-6..'),('d',('2./3.','1./3.','1./4.'),2,'-6..'),('e',('0','0','z'),4,'3..'),('f',('1./3.','2./3.','z'),4,'3..'),('g',('x','0','0'),6,'.2.'),('h',('x','y','1./4.'),6,'m..'),('i',('x','y','z'),12,'1')]
		elif id=='191': WyckList = [('a',('0','0','0'),1,'6/mmm'),('b',('0','0','1./2.'),1,'6/mmm'),('c',('1./3.','2./3.','0'),2,'-6m2'),('d',('1./3.','2./3.','1./2.'),2,'-6m2'),('e',('0','0','z'),2,'6mm'),('f',('1./2.','0','0'),3,'mmm'),('g',('1./2.','0','1./2.'),3,'mmm'),('h',('1./3.','2./3.','z'),4,'3m.'),('i',('1./2.','0','z'),6,'2mm'),('j',('x','0','0'),6,'m2m'),('k',('x','0','1./2.'),6,'m2m'),('l',('x','2x','0'),6,'mm2'),('m',('x','2x','1./2.'),6,'mm2'),('n',('x','0','z'),12,'..m'),('o',('x','2x','z'),12,'.m.'),('p',('x','y','0'),12,'m..'),('q',('x','y','1./2.'),12,'m..'),('r',('x','y','z'),24,'1')]
		elif id=='192': WyckList = [('a',('0','0','1./4.'),2,'622'),('b',('0','0','0'),2,'6/m..'),('c',('1./3.','2./3.','1./4.'),4,'3.2'),('d',('1./3.','2./3.','0'),4,'-6..'),('e',('0','0','z'),4,'6..'),('f',('1./2.','0','1./4.'),6,'222'),('g',('1./2.','0','0'),6,'2/m..'),('h',('1./3.','2./3.','z'),8,'3..'),('i',('1./2.','0','z'),12,'2..'),('j',('x','0','1./4.'),12,'.2.'),('k',('x','2x','1./4.'),12,'..2'),('l',('x','y','0'),12,'m..'),('m',('x','y','z'),24,'1')]
		elif id=='193': WyckList = [('a',('0','0','1./4.'),2,'-62m'),('b',('0','0','0'),2,'-3.m'),('c',('1./3.','2./3.','1./4.'),4,'-6..'),('d',('1./3.','2./3.','0'),4,'3.2'),('e',('0','0','z'),4,'3.m'),('f',('1./2.','0','0'),6,'..2/m'),('g',('x','0','1./4.'),6,'m2m'),('h',('1./3.','2./3.','z'),8,'3..'),('i',('x','2x','0'),12,'..2'),('j',('x','y','1./4.'),12,'m..'),('k',('x','0','z'),12,'..m'),('l',('x','y','z'),24,'1')]
		elif id=='194': WyckList = [('a',('0','0','0'),2,'-3m.'),('b',('0','0','1./4.'),2,'-6m2'),('c',('1./3.','2./3.','1./4.'),2,'-6m2'),('d',('1./3.','2./3.','3./4.'),2,'-6m2'),('e',('0','0','z'),4,'3m.'),('f',('1./3.','2./3.','z'),4,'3m.'),('g',('1./2.','0','0'),6,'.2/m.'),('h',('x','2x','1./4.'),6,'mm2'),('i',('x','0','0'),12,'.2.'),('j',('x','y','1./4.'),12,'m..'),('k',('x','2x','z'),12,'.m.'),('l',('x','y','z'),24,'1')]
		elif id=='195': WyckList = [('a',('0','0','0'),1,'23.'),('b',('1./2.','1./2.','1./2.'),1,'23.'),('c',('0','1./2.','1./2.'),3,'222 . .'),('d',('1./2.','0','0'),3,'222 . .'),('e',('x','x','x'),4,'.3.'),('f',('x','0','0'),6,'2..'),('g',('x','0','1./2.'),6,'2..'),('h',('x','1./2.','0'),6,'2..'),('i',('x','1./2.','1./2.'),6,'2..'),('j',('x','y','z'),12,'1')]
		elif id=='196': WyckList = [('a',('0','0','0'),4,'23.'),('b',('1./2.','1./2.','1./2.'),4,'23.'),('c',('1./4.','1./4.','1./4.'),4,'23.'),('d',('3./4.','3./4.','3./4.'),4,'23.'),('e',('x','x','x'),16,'.3.'),('f',('x','0','0'),24,'2..'),('g',('x','1./4.','1./4.'),24,'2..'),('h',('x','y','z'),48,'1')]
		elif id=='197': WyckList = [('a',('0','0','0'),2,'23.'),('b',('0','1./2.','1./2.'),6,'222 . .'),('c',('x','x','x'),8,'.3.'),('d',('x','0','0'),12,'2..'),('e',('x','1./2.','0'),12,'2..'),('f',('x','y','z'),24,'1')]
		elif id=='198': WyckList = [('a',('x','x','x'),4,'.3.'),('b',('x','y','z'),12,'1')]
		elif id=='199': WyckList = [('a',('x','x','x'),8,'.3.'),('b',('x','0','1./4.'),12,'2..'),('c',('x','y','z'),24,'1')]
		elif id=='200': WyckList = [('a',('0','0','0'),1,'m-3.'),('b',('1./2.','1./2.','1./2.'),1,'m-3.'),('c',('0','1./2.','1./2.'),3,'mmm . .'),('d',('1./2.','0','0'),3,'mmm . .'),('e',('x','0','0'),6,'mm2 . .'),('f',('x','0','1./2.'),6,'mm2 . .'),('g',('x','1./2.','0'),6,'mm2 . .'),('h',('x','1./2.','1./2.'),6,'mm2 . .'),('i',('x','x','x'),8,'.3.'),('j',('0','y','z'),12,'m..'),('k',('1./2.','y','z'),12,'m..'),('l',('x','y','z'),24,'1')]
		elif id=='201:1': WyckList = [('a',('0','0','0'),2,'23.'),('b',('1./4.','1./4.','1./4.'),4,'.-3.'),('c',('3./4.','3./4.','3./4.'),4,'.-3.'),('d',('0','1./2.','1./2.'),6,'222 . .'),('e',('x','x','x'),8,'.3.'),('f',('x','0','0'),12,'2..'),('g',('x','1./2.','0'),12,'2..'),('h',('x','y','z'),24,'1')]
		elif id=='201:2': WyckList = [('a',('1./4.','1./4.','1./4.'),2,'23.'),('b',('1./2.','1./2.','1./2.'),4,'.-3.'),('c',('0','0','0'),4,'.-3.'),('d',('1./4.','3./4.','3./4.'),6,'222 . .'),('e',('x+1./4.','x+1./4.','x+1./4.'),8,'.3.'),('f',('x+1./4.','1./4.','1./4.'),12,'2..'),('g',('x+1./4.','3./4.','1./4.'),12,'2..'),('h',('x','y','z'),24,'1')]
		elif id=='202': WyckList = [('a',('0','0','0'),4,'m-3.'),('b',('1./2.','1./2.','1./2.'),4,'m-3.'),('c',('1./4.','1./4.','1./4.'),8,'23.'),('d',('0','1./4.','1./4.'),24,'2/m..'),('e',('x','0','0'),24,'mm2 . .'),('f',('x','x','x'),32,'.3.'),('g',('x','1./4.','1./4.'),48,'2..'),('h',('0','y','z'),48,'m..'),('i',('x','y','z'),96,'1')]
		elif id=='203:1': WyckList = [('a',('0','0','0'),8,'23.'),('b',('1./2.','1./2.','1./2.'),8,'23.'),('c',('1./8.','1./8.','1./8.'),16,'.-3.'),('d',('5./8.','5./8.','5./8.'),16,'.-3.'),('e',('x','x','x'),32,'.3.'),('f',('x','0','0'),48,'2..'),('g',('x','y','z'),96,'1')]
		elif id=='203:2': WyckList = [('a',('7./8.','7./8.','7./8.'),8,'23.'),('b',('3./8.','3./8.','3./8.'),8,'23.'),('c',('0','0','0'),16,'.-3.'),('d',('1./2.','1./2.','1./2.'),16,'.-3.'),('e',('x-1./8.','x-1./8.','x-1./8.'),32,'.3.'),('f',('x-1./8.','7./8.','7./8.'),48,'2..'),('g',('x','y','z'),96,'1')]
		elif id=='204': WyckList = [('a',('0','0','0'),2,'m-3.'),('b',('0','1./2.','1./2.'),6,'mmm . .'),('c',('1./4.','1./4.','1./4.'),8,'.-3.'),('d',('x','0','0'),12,'mm2 . .'),('e',('x','0','1./2.'),12,'mm2 . .'),('f',('x','x','x'),16,'.3.'),('g',('0','y','z'),24,'m..'),('h',('x','y','z'),48,'1')]
		elif id=='205': WyckList = [('a',('0','0','0'),4,'.-3.'),('b',('1./2.','1./2.','1./2.'),4,'.-3.'),('c',('x','x','x'),8,'.3.'),('d',('x','y','z'),24,'1')]
		elif id=='206': WyckList = [('a',('0','0','0'),8,'.-3.'),('b',('1./4.','1./4.','1./4.'),8,'.-3.'),('c',('x','x','x'),16,'.3.'),('d',('x','0','1./4.'),24,'2..'),('e',('x','y','z'),48,'1')]
		elif id=='207': WyckList = [('a',('0','0','0'),1,'432'),('b',('1./2.','1./2.','1./2.'),1,'432'),('c',('0','1./2.','1./2.'),3,'42. 2'),('d',('1./2.','0','0'),3,'42. 2'),('e',('x','0','0'),6,'4..'),('f',('x','1./2.','1./2.'),6,'4..'),('g',('x','x','x'),8,'.3.'),('h',('x','1./2.','0'),12,'2..'),('i',('0','y','y'),12,'..2'),('j',('1./2.','y','y'),12,'..2'),('k',('x','y','z'),24,'1')]
		elif id=='208': WyckList = [('a',('0','0','0'),2,'23.'),('b',('1./4.','1./4.','1./4.'),4,'.32'),('c',('3./4.','3./4.','3./4.'),4,'.32'),('d',('0','1./2.','1./2.'),6,'222 . .'),('e',('1./4.','0','1./2.'),6,'2.2 2'),('f',('1./4.','1./2.','0'),6,'2.2 2'),('g',('x','x','x'),8,'.3.'),('h',('x','0','0'),12,'2..'),('i',('x','0','1./2.'),12,'2..'),('j',('x','1./2.','0'),12,'2..'),('k',('1./4.','y','-y+1./2.'),12,'..2'),('l',('1./4.','y','y+1./2.'),12,'..2'),('m',('x','y','z'),24,'1')]
		elif id=='209': WyckList = [('a',('0','0','0'),4,'432'),('b',('1./2.','1./2.','1./2.'),4,'432'),('c',('1./4.','1./4.','1./4.'),8,'23.'),('d',('0','1./4.','1./4.'),24,'2.2 2'),('e',('x','0','0'),24,'4..'),('f',('x','x','x'),32,'.3.'),('g',('0','y','y'),48,'..2'),('h',('1./2.','y','y'),48,'..2'),('i',('x','1./4.','1./4.'),48,'2..'),('j',('x','y','z'),96,'1')]
		elif id=='210': WyckList = [('a',('0','0','0'),8,'23.'),('b',('1./2.','1./2.','1./2.'),8,'23.'),('c',('1./8.','1./8.','1./8.'),16,'.32'),('d',('5./8.','5./8.','5./8.'),16,'.32'),('e',('x','x','x'),32,'.3.'),('f',('x','0','0'),48,'2..'),('g',('1./8.','y','-y+1./4.'),48,'..2'),('h',('x','y','z'),96,'1')]
		elif id=='211': WyckList = [('a',('0','0','0'),2,'432'),('b',('0','1./2.','1./2.'),6,'42. 2'),('c',('1./4.','1./4.','1./4.'),8,'.32'),('d',('1./4.','1./2.','0'),12,'2.2 2'),('e',('x','0','0'),12,'4..'),('f',('x','x','x'),16,'.3.'),('g',('x','1./2.','0'),24,'2..'),('h',('0','y','y'),24,'..2'),('i',('1./4.','y','-y+1./2.'),24,'..2'),('j',('x','y','z'),48,'1')]
		elif id=='212': WyckList = [('a',('1./8.','1./8.','1./8.'),4,'.32'),('b',('5./8.','5./8.','5./8.'),4,'.32'),('c',('x','x','x'),8,'.3.'),('d',('1./8.','y','-y+1./4.'),12,'..2'),('e',('x','y','z'),24,'1')]
		elif id=='213': WyckList = [('a',('3./8.','3./8.','3./8.'),4,'.32'),('b',('7./8.','7./8.','7./8.'),4,'.32'),('c',('x','x','x'),8,'.3.'),('d',('1./8.','y','y+1./4.'),12,'..2'),('e',('x','y','z'),24,'1')]
		elif id=='214': WyckList = [('a',('1./8.','1./8.','1./8.'),8,'.32'),('b',('7./8.','7./8.','7./8.'),8,'.32'),('c',('1./8.','0','1./4.'),12,'2.2 2'),('d',('5./8.','0','1./4.'),12,'2.2 2'),('e',('x','x','x'),16,'.3.'),('f',('x','0','1./4.'),24,'2..'),('g',('1./8.','y','y+1./4.'),24,'..2'),('h',('1./8.','y','-y+1./4.'),24,'..2'),('i',('x','y','z'),48,'1')]
		elif id=='215': WyckList = [('a',('0','0','0'),1,'-43m'),('b',('1./2.','1./2.','1./2.'),1,'-43m'),('c',('0','1./2.','1./2.'),3,'-42. m'),('d',('1./2.','0','0'),3,'-42. m'),('e',('x','x','x'),4,'.3m'),('f',('x','0','0'),6,'2.m m'),('g',('x','1./2.','1./2.'),6,'2.m m'),('h',('x','1./2.','0'),12,'2..'),('i',('x','x','z'),12,'..m'),('j',('x','y','z'),24,'1')]
		elif id=='216': WyckList = [('a',('0','0','0'),4,'-43m'),('b',('1./2.','1./2.','1./2.'),4,'-43m'),('c',('1./4.','1./4.','1./4.'),4,'-43m'),('d',('3./4.','3./4.','3./4.'),4,'-43m'),('e',('x','x','x'),16,'.3m'),('f',('x','0','0'),24,'2.m m'),('g',('x','1./4.','1./4.'),24,'2.m m'),('h',('x','x','z'),48,'..m'),('i',('x','y','z'),96,'1')]
		elif id=='217': WyckList = [('a',('0','0','0'),2,'-43m'),('b',('0','1./2.','1./2.'),6,'-42. m'),('c',('x','x','x'),8,'.3m'),('d',('1./4.','1./2.','0'),12,'-4..'),('e',('x','0','0'),12,'2.m m'),('f',('x','1./2.','0'),24,'2..'),('g',('x','x','z'),24,'..m'),('h',('x','y','z'),48,'1')]
		elif id=='218': WyckList = [('a',('0','0','0'),2,'23.'),('b',('0','1./2.','1./2.'),6,'222 . .'),('c',('1./4.','1./2.','0'),6,'-4..'),('d',('1./4.','0','1./2.'),6,'-4..'),('e',('x','x','x'),8,'.3.'),('f',('x','0','0'),12,'2..'),('g',('x','1./2.','0'),12,'2..'),('h',('x','0','1./2.'),12,'2..'),('i',('x','y','z'),24,'1')]
		elif id=='219': WyckList = [('a',('0','0','0'),8,'23.'),('b',('1./4.','1./4.','1./4.'),8,'23.'),('c',('0','1./4.','1./4.'),24,'-4..'),('d',('1./4.','0','0'),24,'-4..'),('e',('x','x','x'),32,'.3.'),('f',('x','0','0'),48,'2..'),('g',('x','1./4.','1./4.'),48,'2..'),('h',('x','y','z'),96,'1')]
		elif id=='220': WyckList = [('a',('3./8.','0','1./4.'),12,'-4..'),('b',('7./8.','0','1./4.'),12,'-4..'),('c',('x','x','x'),16,'.3.'),('d',('x','0','1./4.'),24,'2..'),('e',('x','y','z'),48,'1')]
		elif id=='221': WyckList = [('a',('0','0','0'),1,'m-3m'),('b',('1./2.','1./2.','1./2.'),1,'m-3m'),('c',('0','1./2.','1./2.'),3,'4/mm. m'),('d',('1./2.','0','0'),3,'4/mm. m'),('e',('x','0','0'),6,'4m. m'),('f',('x','1./2.','1./2.'),6,'4m. m'),('g',('x','x','x'),8,'.3m'),('h',('x','1./2.','0'),12,'mm2 . .'),('i',('0','y','y'),12,'m.m 2'),('j',('1./2.','y','y'),12,'m.m 2'),('k',('0','y','z'),24,'m..'),('l',('1./2.','y','z'),24,'m..'),('m',('x','x','z'),24,'..m'),('n',('x','y','z'),48,'1')]
		elif id=='222:1': WyckList = [('a',('0','0','0'),2,'432'),('b',('0','1./2.','1./2.'),6,'42. 2'),('c',('1./4.','1./4.','1./4.'),8,'.-3.'),('d',('1./4.','0','1./2.'),12,'-4..'),('e',('x','0','0'),12,'4..'),('f',('x','x','x'),16,'.3.'),('g',('x','0','1./2.'),24,'2..'),('h',('0','y','y'),24,'..2'),('i',('x','y','z'),48,'1')]
		elif id=='222:2': WyckList = [('a',('1./4.','1./4.','1./4.'),2,'432'),('b',('1./4.','3./4.','3./4.'),6,'42. 2'),('c',('1./2.','1./2.','1./2.'),8,'.-3.'),('d',('1./2.','1./4.','3./4.'),12,'-4..'),('e',('x+1./4.','1./4.','1./4.'),12,'4..'),('f',('x+1./4.','x+1./4.','x+1./4.'),16,'.3.'),('g',('x+1./4.','1./4.','3./4.'),24,'2..'),('h',('1./4.','y+1./4.','y+1./4.'),24,'..2'),('i',('x','y','z'),48,'1')]
		elif id=='223': WyckList = [('a',('0','0','0'),2,'m-3.'),('b',('0','1./2.','1./2.'),6,'mmm . .'),('c',('1./4.','0','1./2.'),6,'-4m. 2'),('d',('1./4.','1./2.','0'),6,'-4m. 2'),('e',('1./4.','1./4.','1./4.'),8,'.32'),('f',('x','0','0'),12,'mm2 . .'),('g',('x','0','1./2.'),12,'mm2 . .'),('h',('x','1./2.','0'),12,'mm2 . .'),('i',('x','x','x'),16,'.3.'),('j',('1./4.','y','y+1./2.'),24,'..2'),('k',('0','y','z'),24,'m..'),('l',('x','y','z'),48,'1')]
		elif id=='224:1': WyckList = [('a',('0','0','0'),2,'-43m'),('b',('1./4.','1./4.','1./4.'),4,'.-3m'),('c',('3./4.','3./4.','3./4.'),4,'.-3m'),('d',('0','1./2.','1./2.'),6,'-42. m'),('e',('x','x','x'),8,'.3m'),('f',('1./4.','0','1./2.'),12,'2.2 2'),('g',('x','0','0'),12,'2.m m'),('h',('x','0','1./2.'),24,'2..'),('i',('1./4.','y','-y+1./2.'),24,'..2'),('j',('1./4.','y','y+1./2.'),24,'..2'),('k',('x','x','z'),24,'..m'),('l',('x','y','z'),48,'1')]
		elif id=='224:2': WyckList = [('a',('3./4.','3./4.','3./4.'),2,'-43m'),('b',('0','0','0'),4,'.-3m'),('c',('1./2.','1./2.','1./2.'),4,'.-3m'),('d',('3./4.','1./4.','1./4.'),6,'-42. m'),('e',('x-1./4.','x-1./4.','x-1./4.'),8,'.3m'),('f',('0','3./4.','1./4.'),12,'2.2 2'),('g',('x-1./4.','3./4.','3./4.'),12,'2.m m'),('h',('x-1./4.','3./4.','1./4.'),24,'2..'),('i',('0','y-1./4.','-y+1./4.'),24,'..2'),('j',('0','y-1./4.','y+1./4.'),24,'..2'),('k',('x-1./4.','x-1./4.','z-1./4.'),24,'..m'),('l',('x','y','z'),48,'1')]
		elif id=='225': WyckList = [('a',('0','0','0'),4,'m-3m'),('b',('1./2.','1./2.','1./2.'),4,'m-3m'),('c',('1./4.','1./4.','1./4.'),8,'-43m'),('d',('0','1./4.','1./4.'),24,'m.m m'),('e',('x','0','0'),24,'4m. m'),('f',('x','x','x'),32,'.3m'),('g',('x','1./4.','1./4.'),48,'2.m m'),('h',('0','y','y'),48,'m.m 2'),('i',('1./2.','y','y'),48,'m.m 2'),('j',('0','y','z'),96,'m..'),('k',('x','x','z'),96,'..m'),('l',('x','y','z'),192,'1')]
		elif id=='226': WyckList = [('a',('1./4.','1./4.','1./4.'),8,'432'),('b',('0','0','0'),8,'m-3.'),('c',('1./4.','0','0'),24,'-4m. 2'),('d',('0','1./4.','1./4.'),24,'4/m..'),('e',('x','0','0'),48,'mm2 . .'),('f',('x','1./4.','1./4.'),48,'4..'),('g',('x','x','x'),64,'.3.'),('h',('1./4.','y','y'),96,'..2'),('i',('0','y','z'),96,'m..'),('j',('x','y','z'),192,'1')]
		elif id=='227:1': WyckList = [('a',('0','0','0'),8,'-43m'),('b',('1./2.','1./2.','1./2.'),8,'-43m'),('c',('1./8.','1./8.','1./8.'),16,'.-3m'),('d',('5./8.','5./8.','5./8.'),16,'.-3m'),('e',('x','x','x'),32,'.3m'),('f',('x','0','0'),48,'2.m m'),('g',('x','x','z'),96,'..m'),('h',('1./8.','y','-y+1./4.'),96,'..2'),('i',('x','y','z'),192,'1')]
		elif id=='227:2': WyckList = [('a',('7./8.','7./8.','7./8.'),8,'-43m'),('b',('3./8.','3./8.','3./8.'),8,'-43m'),('c',('0','0','0'),16,'.-3m'),('d',('1./2.','1./2.','1./2.'),16,'.-3m'),('e',('x-1./8.','x-1./8.','x-1./8.'),32,'.3m'),('f',('x-1./8.','7./8.','7./8.'),48,'2.m m'),('g',('x-1./8.','x-1./8.','z-1./8.'),96,'..m'),('h',('0','y-1./8.','-y+1./8.'),96,'..2'),('i',('x','y','z'),192,'1')]
		elif id=='228:1': WyckList = [('a',('0','0','0'),16,'23.'),('b',('1./8.','1./8.','1./8.'),32,'.32'),('c',('3./8.','3./8.','3./8.'),32,'.-3.'),('d',('1./4.','0','0'),48,'-4..'),('e',('x','x','x'),64,'.3.'),('f',('x','0','0'),96,'2..'),('g',('1./8.','y','-y+1./4.'),96,'..2'),('h',('x','y','z'),192,'1')]
		elif id=='228:2': WyckList = [('a',('5./8.','5./8.','5./8.'),16,'23.'),('b',('3./4.','3./4.','3./4.'),32,'.32'),('c',('0','0','0'),32,'.-3.'),('d',('7./8.','5./8.','5./8.'),48,'-4..'),('e',('x-3./8.','x-3./8.','x-3./8.'),64,'.3.'),('f',('x-3./8.','5./8.','5./8.'),96,'2..'),('g',('3./4.','y-3./8.','-y-1./8.'),96,'..2'),('h',('x','y','z'),192,'1')]
		elif id=='229': WyckList = [('a',('0','0','0'),2,'m-3m'),('b',('0','1./2.','1./2.'),6,'4/mm. m'),('c',('1./4.','1./4.','1./4.'),8,'.-3m'),('d',('1./4.','0','1./2.'),12,'-4m. 2'),('e',('x','0','0'),12,'4m. m'),('f',('x','x','x'),16,'.3m'),('g',('x','0','1./2.'),24,'mm2 . .'),('h',('0','y','y'),24,'m.m 2'),('i',('1./4.','y','-y+1./2.'),48,'..2'),('j',('0','y','z'),48,'m..'),('k',('x','x','z'),48,'..m'),('l',('x','y','z'),96,'1')]
		elif id=='230': WyckList = [('a',('0','0','0'),16,'.-3.'),('b',('1./8.','1./8.','1./8.'),16,'.32'),('c',('1./8.','0','1./4.'),24,'2.2 2'),('d',('3./8.','0','1./4.'),24,'-4..'),('e',('x','x','x'),32,'.3.'),('f',('x','0','1./4.'),48,'2..'),('g',('1./8.','y','-y+1./4.'),48,'..2'),('h',('x','y','z'),96,'1')]
		else: 
			WyckList = []
			ValueError('SG = %r is not supported, SG can only be a valid id of the %d 3D Space Groups' % (id,self.MaxIDnum))

		return WyckList


	def GetSettingTransForm(self, id):
		"""
		returns a 4x4 CBM matrix for converting the setting
		"""
		try:
			id = str(id)
			if not (id in self.allIDs): raise
		except: ValueError('Cannot find the space group for id = %r, it should be something like "15:-b2"' % (id,))

		if id=='1': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='2': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='3:b': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='3:c': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='3:a': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='4:b': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='4:c': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='4:a': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='5:b1': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='5:b2': CBM = np.array([[-1, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='5:b3': CBM = np.array([[0, 0, -1, 0], [0, 1, 0, 0], [1, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='5:c1': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='5:c2': CBM = np.array([[1, -1, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]])
		elif id=='5:c3': CBM = np.array([[-1, 0, 0, 0], [0, 0, 1, 0], [-1, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='5:a1': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='5:a2': CBM = np.array([[0, 1, -1, 0], [1, 0, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='5:a3': CBM = np.array([[0, -1, 0, 0], [1, 0, 0, 0], [0, -1, 1, 0], [0, 0, 0, 1]])
		elif id=='6:b': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='6:c': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='6:a': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='7:b1': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='7:b2': CBM = np.array([[-1, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='7:b3': CBM = np.array([[0, 0, -1, 0], [0, 1, 0, 0], [1, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='7:c1': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='7:c2': CBM = np.array([[1, -1, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]])
		elif id=='7:c3': CBM = np.array([[-1, 0, 0, 0], [0, 0, 1, 0], [-1, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='7:a1': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='7:a2': CBM = np.array([[0, 1, -1, 0], [1, 0, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='7:a3': CBM = np.array([[0, -1, 0, 0], [1, 0, 0, 0], [0, -1, 1, 0], [0, 0, 0, 1]])
		elif id=='8:b1': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='8:b2': CBM = np.array([[-1, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='8:b3': CBM = np.array([[0, 0, -1, 0], [0, 1, 0, 0], [1, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='8:c1': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='8:c2': CBM = np.array([[1, -1, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]])
		elif id=='8:c3': CBM = np.array([[-1, 0, 0, 0], [0, 0, 1, 0], [-1, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='8:a1': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='8:a2': CBM = np.array([[0, 1, -1, 0], [1, 0, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='8:a3': CBM = np.array([[0, -1, 0, 0], [1, 0, 0, 0], [0, -1, 1, 0], [0, 0, 0, 1]])
		elif id=='9:b1': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='9:b2': CBM = np.array([[-1, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='9:b3': CBM = np.array([[0, 0, -1, 0], [0, 1, 0, 0], [1, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='9:-b1': CBM = np.array([[-1, 0, 1, 0], [0, 1, 0, 0.25], [-1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='9:-b2': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, -0.25], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='9:-b3': CBM = np.array([[0, 0, -1, 0], [0, 1, 0, 0.25], [1, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='9:c1': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='9:c2': CBM = np.array([[1, -1, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]])
		elif id=='9:c3': CBM = np.array([[-1, 0, 0, 0], [0, 0, 1, 0], [-1, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='9:-c1': CBM = np.array([[1, -1, 0, 0], [0, 0, 1, 0.25], [0, -1, 0, 0], [0, 0, 0, 1]])
		elif id=='9:-c2': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, -0.25], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='9:-c3': CBM = np.array([[-1, 0, 0, 0], [0, 0, 1, 0.25], [-1, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='9:a1': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='9:a2': CBM = np.array([[0, 1, -1, 0], [1, 0, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='9:a3': CBM = np.array([[0, -1, 0, 0], [1, 0, 0, 0], [0, -1, 1, 0], [0, 0, 0, 1]])
		elif id=='9:-a1': CBM = np.array([[0, 1, -1, 0], [1, 0, 0, 0.25], [0, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='9:-a2': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0.25], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='9:-a3': CBM = np.array([[0, -1, 0, 0], [1, 0, 0, 0.25], [0, -1, 1, 0], [0, 0, 0, 1]])
		elif id=='10:b': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='10:c': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='10:a': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='11:b': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='11:c': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='11:a': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='12:b1': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='12:b2': CBM = np.array([[-1, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='12:b3': CBM = np.array([[0, 0, -1, 0], [0, 1, 0, 0], [1, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='12:c1': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='12:c2': CBM = np.array([[1, -1, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]])
		elif id=='12:c3': CBM = np.array([[-1, 0, 0, 0], [0, 0, 1, 0], [-1, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='12:a1': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='12:a2': CBM = np.array([[0, 1, -1, 0], [1, 0, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='12:a3': CBM = np.array([[0, -1, 0, 0], [1, 0, 0, 0], [0, -1, 1, 0], [0, 0, 0, 1]])
		elif id=='13:b1': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='13:b2': CBM = np.array([[-1, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='13:b3': CBM = np.array([[0, 0, -1, 0], [0, 1, 0, 0], [1, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='13:c1': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='13:c2': CBM = np.array([[1, -1, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]])
		elif id=='13:c3': CBM = np.array([[-1, 0, 0, 0], [0, 0, 1, 0], [-1, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='13:a1': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='13:a2': CBM = np.array([[0, 1, -1, 0], [1, 0, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='13:a3': CBM = np.array([[0, -1, 0, 0], [1, 0, 0, 0], [0, -1, 1, 0], [0, 0, 0, 1]])
		elif id=='14:b1': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='14:b2': CBM = np.array([[-1, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='14:b3': CBM = np.array([[0, 0, -1, 0], [0, 1, 0, 0], [1, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='14:c1': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='14:c2': CBM = np.array([[1, -1, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]])
		elif id=='14:c3': CBM = np.array([[-1, 0, 0, 0], [0, 0, 1, 0], [-1, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='14:a1': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='14:a2': CBM = np.array([[0, 1, -1, 0], [1, 0, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='14:a3': CBM = np.array([[0, -1, 0, 0], [1, 0, 0, 0], [0, -1, 1, 0], [0, 0, 0, 1]])
		elif id=='15:b1': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='15:b2': CBM = np.array([[-1, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='15:b3': CBM = np.array([[0, 0, -1, 0], [0, 1, 0, 0], [1, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='15:-b1': CBM = np.array([[-1, 0, 1, -0.25], [0, 1, 0, 0.25], [-1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='15:-b2': CBM = np.array([[1, 0, 0, 0.25], [0, 1, 0, 0.25], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='15:-b3': CBM = np.array([[0, 0, -1, -0.25], [0, 1, 0, 0.25], [1, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='15:c1': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='15:c2': CBM = np.array([[1, -1, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]])
		elif id=='15:c3': CBM = np.array([[-1, 0, 0, 0], [0, 0, 1, 0], [-1, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='15:-c1': CBM = np.array([[1, -1, 0, -0.25], [0, 0, 1, 0.25], [0, -1, 0, 0], [0, 0, 0, 1]])
		elif id=='15:-c2': CBM = np.array([[0, 1, 0, 0.25], [0, 0, 1, 0.25], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='15:-c3': CBM = np.array([[-1, 0, 0, -0.25], [0, 0, 1, 0.25], [-1, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='15:a1': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='15:a2': CBM = np.array([[0, 1, -1, 0], [1, 0, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='15:a3': CBM = np.array([[0, -1, 0, 0], [1, 0, 0, 0], [0, -1, 1, 0], [0, 0, 0, 1]])
		elif id=='15:-a1': CBM = np.array([[0, 1, -1, -0.25], [1, 0, 0, 0.25], [0, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='15:-a2': CBM = np.array([[0, 0, 1, -0.25], [1, 0, 0, 0.25], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='15:-a3': CBM = np.array([[0, -1, 0, -0.25], [1, 0, 0, 0.25], [0, -1, 1, 0], [0, 0, 0, 1]])
		elif id=='16': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='17': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='17:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='17:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='18': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='18:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='18:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='19': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='20': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='20:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='20:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='21': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='21:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='21:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='22': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='23': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='24': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='25': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='25:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='25:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='26': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='26:ba-c': CBM = np.array([[0, 1, 0, 0], [1, 0, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='26:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='26:-cba': CBM = np.array([[0, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='26:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='26:a-cb': CBM = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]])
		elif id=='27': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='27:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='27:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='28': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='28:ba-c': CBM = np.array([[0, 1, 0, 0], [1, 0, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='28:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='28:-cba': CBM = np.array([[0, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='28:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='28:a-cb': CBM = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]])
		elif id=='29': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='29:ba-c': CBM = np.array([[0, 1, 0, 0], [1, 0, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='29:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='29:-cba': CBM = np.array([[0, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='29:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='29:a-cb': CBM = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]])
		elif id=='30': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='30:ba-c': CBM = np.array([[0, 1, 0, 0], [1, 0, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='30:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='30:-cba': CBM = np.array([[0, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='30:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='30:a-cb': CBM = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]])
		elif id=='31': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='31:ba-c': CBM = np.array([[0, 1, 0, 0], [1, 0, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='31:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='31:-cba': CBM = np.array([[0, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='31:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='31:a-cb': CBM = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]])
		elif id=='32': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='32:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='32:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='33': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='33:ba-c': CBM = np.array([[0, 1, 0, 0], [1, 0, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='33:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='33:-cba': CBM = np.array([[0, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='33:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='33:a-cb': CBM = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]])
		elif id=='34': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='34:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='34:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='35': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='35:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='35:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='36': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='36:ba-c': CBM = np.array([[0, 1, 0, 0], [1, 0, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='36:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='36:-cba': CBM = np.array([[0, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='36:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='36:a-cb': CBM = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]])
		elif id=='37': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='37:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='37:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='38': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='38:ba-c': CBM = np.array([[0, 1, 0, 0], [1, 0, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='38:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='38:-cba': CBM = np.array([[0, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='38:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='38:a-cb': CBM = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]])
		elif id=='39': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='39:ba-c': CBM = np.array([[0, 1, 0, 0], [1, 0, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='39:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='39:-cba': CBM = np.array([[0, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='39:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='39:a-cb': CBM = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]])
		elif id=='40': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='40:ba-c': CBM = np.array([[0, 1, 0, 0], [1, 0, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='40:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='40:-cba': CBM = np.array([[0, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='40:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='40:a-cb': CBM = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]])
		elif id=='41': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='41:ba-c': CBM = np.array([[0, 1, 0, 0], [1, 0, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='41:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='41:-cba': CBM = np.array([[0, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='41:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='41:a-cb': CBM = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]])
		elif id=='42': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='42:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='42:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='43': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='43:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='43:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='44': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='44:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='44:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='45': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='45:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='45:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='46': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='46:ba-c': CBM = np.array([[0, 1, 0, 0], [1, 0, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='46:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='46:-cba': CBM = np.array([[0, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='46:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='46:a-cb': CBM = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]])
		elif id=='47': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='48:1': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='48:2': CBM = np.array([[1, 0, 0, -0.25], [0, 1, 0, -0.25], [0, 0, 1, -0.25], [0, 0, 0, 1]])
		elif id=='49': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='49:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='49:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='50:1': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='50:2': CBM = np.array([[1, 0, 0, -0.25], [0, 1, 0, -0.25], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='50:1cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='50:2cab': CBM = np.array([[0, 1, 0, -0.25], [0, 0, 1, -0.25], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='50:1bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='50:2bca': CBM = np.array([[0, 0, 1, -0.25], [1, 0, 0, -0.25], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='51': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='51:ba-c': CBM = np.array([[0, 1, 0, 0], [1, 0, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='51:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='51:-cba': CBM = np.array([[0, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='51:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='51:a-cb': CBM = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]])
		elif id=='52': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='52:ba-c': CBM = np.array([[0, 1, 0, 0], [1, 0, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='52:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='52:-cba': CBM = np.array([[0, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='52:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='52:a-cb': CBM = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]])
		elif id=='53': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='53:ba-c': CBM = np.array([[0, 1, 0, 0], [1, 0, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='53:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='53:-cba': CBM = np.array([[0, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='53:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='53:a-cb': CBM = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]])
		elif id=='54': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='54:ba-c': CBM = np.array([[0, 1, 0, 0], [1, 0, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='54:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='54:-cba': CBM = np.array([[0, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='54:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='54:a-cb': CBM = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]])
		elif id=='55': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='55:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='55:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='56': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='56:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='56:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='57': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='57:ba-c': CBM = np.array([[0, 1, 0, 0], [1, 0, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='57:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='57:-cba': CBM = np.array([[0, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='57:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='57:a-cb': CBM = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]])
		elif id=='58': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='58:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='58:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='59:1': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='59:2': CBM = np.array([[1, 0, 0, -0.25], [0, 1, 0, -0.25], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='59:1cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='59:2cab': CBM = np.array([[0, 1, 0, -0.25], [0, 0, 1, -0.25], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='59:1bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='59:2bca': CBM = np.array([[0, 0, 1, -0.25], [1, 0, 0, -0.25], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='60': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='60:ba-c': CBM = np.array([[0, 1, 0, 0], [1, 0, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='60:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='60:-cba': CBM = np.array([[0, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='60:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='60:a-cb': CBM = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]])
		elif id=='61': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='61:ba-c': CBM = np.array([[0, 1, 0, 0], [1, 0, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='62': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='62:ba-c': CBM = np.array([[0, 1, 0, 0], [1, 0, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='62:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='62:-cba': CBM = np.array([[0, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='62:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='62:a-cb': CBM = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]])
		elif id=='63': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='63:ba-c': CBM = np.array([[0, 1, 0, 0], [1, 0, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='63:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='63:-cba': CBM = np.array([[0, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='63:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='63:a-cb': CBM = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]])
		elif id=='64': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='64:ba-c': CBM = np.array([[0, 1, 0, 0], [1, 0, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
		elif id=='64:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='64:-cba': CBM = np.array([[0, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='64:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='64:a-cb': CBM = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]])
		elif id=='65': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='65:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='65:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='66': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='66:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='66:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='67': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='67:ba-c': CBM = np.array([[1, 0, 0, 0.25], [0, 1, 0, 0.25], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='67:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='67:-cba': CBM = np.array([[0, 1, 0, 0.25], [0, 0, 1, 0.25], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='67:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='67:a-cb': CBM = np.array([[0, 0, 1, -0.25], [1, 0, 0, 0.25], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='68:1': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='68:2': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, -0.25], [0, 0, 1, -0.25], [0, 0, 0, 1]])
		elif id=='68:1ba-c': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='68:2ba-c': CBM = np.array([[1, 0, 0, 0.25], [0, 1, 0, 0], [0, 0, 1, -0.25], [0, 0, 0, 1]])
		elif id=='68:1cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='68:2cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, -0.25], [1, 0, 0, -0.25], [0, 0, 0, 1]])
		elif id=='68:1-cba': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='68:2-cba': CBM = np.array([[0, 1, 0, 0.25], [0, 0, 1, 0], [1, 0, 0, -0.25], [0, 0, 0, 1]])
		elif id=='68:1bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='68:2bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0.25], [0, 1, 0, -0.25], [0, 0, 0, 1]])
		elif id=='68:1a-cb': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='68:2a-cb': CBM = np.array([[0, 0, 1, -0.25], [1, 0, 0, 0], [0, 1, 0, -0.25], [0, 0, 0, 1]])
		elif id=='69': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='70:1': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='70:2': CBM = np.array([[1, 0, 0, 0.125], [0, 1, 0, 0.125], [0, 0, 1, 0.125], [0, 0, 0, 1]])
		elif id=='71': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='72': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='72:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='72:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='73': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='73:ba-c': CBM = np.array([[1, 0, 0, -0.25], [0, 1, 0, 0.25], [0, 0, 1, 0.25], [0, 0, 0, 1]])
		elif id=='74': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='74:ba-c': CBM = np.array([[1, 0, 0, -0.25], [0, 1, 0, 0.25], [0, 0, 1, 0.25], [0, 0, 0, 1]])
		elif id=='74:cab': CBM = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]])
		elif id=='74:-cba': CBM = np.array([[0, 1, 0, -0.25], [0, 0, 1, 0.25], [1, 0, 0, 0.25], [0, 0, 0, 1]])
		elif id=='74:bca': CBM = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
		elif id=='74:a-cb': CBM = np.array([[0, 0, 1, -0.25], [1, 0, 0, 0.25], [0, 1, 0, 0.25], [0, 0, 0, 1]])
		elif id=='75': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='76': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='77': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='78': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='79': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='80': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='81': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='82': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='83': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='84': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='85:1': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='85:2': CBM = np.array([[1, 0, 0, -0.25], [0, 1, 0, 0.25], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='86:1': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='86:2': CBM = np.array([[1, 0, 0, 0.25], [0, 1, 0, 0.25], [0, 0, 1, 0.25], [0, 0, 0, 1]])
		elif id=='87': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='88:1': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='88:2': CBM = np.array([[1, 0, 0, 0.5], [0, 1, 0, -0.25], [0, 0, 1, 0.125], [0, 0, 0, 1]])
		elif id=='89': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='90': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='91': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='92': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='93': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='94': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='95': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='96': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='97': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='98': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='99': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='100': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='101': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='102': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='103': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='104': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='105': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='106': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='107': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='108': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='109': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='110': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='111': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='112': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='113': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='114': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='115': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='116': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='117': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='118': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='119': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='120': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='121': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='122': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='123': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='124': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='125:1': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='125:2': CBM = np.array([[1, 0, 0, -0.25], [0, 1, 0, -0.25], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='126:1': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='126:2': CBM = np.array([[1, 0, 0, -0.25], [0, 1, 0, -0.25], [0, 0, 1, -0.25], [0, 0, 0, 1]])
		elif id=='127': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='128': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='129:1': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='129:2': CBM = np.array([[1, 0, 0, -0.25], [0, 1, 0, 0.25], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='130:1': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='130:2': CBM = np.array([[1, 0, 0, -0.25], [0, 1, 0, 0.25], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='131': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='132': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='133:1': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='133:2': CBM = np.array([[1, 0, 0, -0.25], [0, 1, 0, 0.25], [0, 0, 1, 0.25], [0, 0, 0, 1]])
		elif id=='134:1': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='134:2': CBM = np.array([[1, 0, 0, -0.25], [0, 1, 0, 0.25], [0, 0, 1, -0.25], [0, 0, 0, 1]])
		elif id=='135': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='136': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='137:1': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='137:2': CBM = np.array([[1, 0, 0, -0.25], [0, 1, 0, 0.25], [0, 0, 1, 0.25], [0, 0, 0, 1]])
		elif id=='138:1': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='138:2': CBM = np.array([[1, 0, 0, -0.25], [0, 1, 0, 0.25], [0, 0, 1, -0.25], [0, 0, 0, 1]])
		elif id=='139': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='140': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='141:1': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='141:2': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, -0.25], [0, 0, 1, 0.125], [0, 0, 0, 1]])
		elif id=='142:1': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='142:2': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, -0.25], [0, 0, 1, 0.125], [0, 0, 0, 1]])
		elif id=='143': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='144': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='145': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='146:H': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='146:R': CBM = np.array([[2./3., -1./3., -1./3., 0], [1./3., 1./3., -2./3., 0], [1./3., 1./3., 1./3., 0], [0, 0, 0, 1]])
		elif id=='147': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='148:H': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='148:R': CBM = np.array([[2./3., -1./3., -1./3., 0], [1./3., 1./3., -2./3., 0], [1./3., 1./3., 1./3., 0], [0, 0, 0, 1]])
		elif id=='149': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='150': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='151': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='152': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='153': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='154': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='155:H': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='155:R': CBM = np.array([[2./3., -1./3., -1./3., 0], [1./3., 1./3., -2./3., 0], [1./3., 1./3., 1./3., 0], [0, 0, 0, 1]])
		elif id=='156': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='157': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='158': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='159': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='160:H': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='160:R': CBM = np.array([[2./3., -1./3., -1./3., 0], [1./3., 1./3., -2./3., 0], [1./3., 1./3., 1./3., 0], [0, 0, 0, 1]])
		elif id=='161:H': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='161:R': CBM = np.array([[2./3., -1./3., -1./3., 0], [1./3., 1./3., -2./3., 0], [1./3., 1./3., 1./3., 0], [0, 0, 0, 1]])
		elif id=='162': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='163': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='164': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='165': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='166:H': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='166:R': CBM = np.array([[2./3., -1./3., -1./3., 0], [1./3., 1./3., -2./3., 0], [1./3., 1./3., 1./3., 0], [0, 0, 0, 1]])
		elif id=='167:H': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='167:R': CBM = np.array([[2./3., -1./3., -1./3., 0], [1./3., 1./3., -2./3., 0], [1./3., 1./3., 1./3., 0], [0, 0, 0, 1]])
		elif id=='168': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='169': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='170': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='171': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='172': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='173': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='174': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='175': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='176': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='177': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='178': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='179': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='180': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='181': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='182': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='183': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='184': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='185': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='186': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='187': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='188': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='189': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='190': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='191': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='192': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='193': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='194': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='195': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='196': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='197': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='198': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='199': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='200': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='201:1': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='201:2': CBM = np.array([[1, 0, 0, -0.25], [0, 1, 0, -0.25], [0, 0, 1, -0.25], [0, 0, 0, 1]])
		elif id=='202': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='203:1': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='203:2': CBM = np.array([[1, 0, 0, 0.125], [0, 1, 0, 0.125], [0, 0, 1, 0.125], [0, 0, 0, 1]])
		elif id=='204': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='205': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='206': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='207': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='208': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='209': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='210': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='211': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='212': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='213': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='214': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='215': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='216': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='217': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='218': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='219': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='220': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='221': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='222:1': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='222:2': CBM = np.array([[1, 0, 0, -0.25], [0, 1, 0, -0.25], [0, 0, 1, -0.25], [0, 0, 0, 1]])
		elif id=='223': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='224:1': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='224:2': CBM = np.array([[1, 0, 0, 0.25], [0, 1, 0, 0.25], [0, 0, 1, 0.25], [0, 0, 0, 1]])
		elif id=='225': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='226': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='227:1': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='227:2': CBM = np.array([[1, 0, 0, 0.125], [0, 1, 0, 0.125], [0, 0, 1, 0.125], [0, 0, 0, 1]])
		elif id=='228:1': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='228:2': CBM = np.array([[1, 0, 0, 0.375], [0, 1, 0, 0.375], [0, 0, 1, 0.375], [0, 0, 0, 1]])
		elif id=='229': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
		elif id=='230': CBM = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])

		return CBM.astype(float)


#	def calcInvCBM(self, CBM):						# returns the Inv(CBM)
#		"""
#		both CBM and InvCBM are (4,3)
#		{x,y,z}(standard) = CBM x {x,y,z,1}(id)
#		{xyz}(id) = InvCBM x {x,y,z,1}(standard)
#		"""
#		mat = CBM[0:3,0:3]					# the first 3 columns make a square mat
#		cbmi = np.linalg.inv(CBM[0:3,0:3])	# inverse of the (3,3) part
#		offseti = -cbmi.dot(CBM[0:3,3])		# inverse of offset = -cbmi x CBM[0:3,3]
#		InvCBM = np.copy(CBM)				# mat to hold output (also 3,4)
#		InvCBM[0:3,0:3] = cbmi				# set the (3,3) part
#		InvCBM[0:3,3] = offseti				# set the last column
#		return InvCBM


	def GetSymmetryOperations(self, SpaceGroupID):
		"""
		Returns the symmetry operations for a SpaceGroup as an array of numpy matricies
		SpaceGroupID is the ID, not just an integer e.g. "15:b3"
		"""
		SpaceGroupID = str(SpaceGroupID)		# in case an integer was passed, e.g. both 1 and "1" work

		if SpaceGroupID=='1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='3:b':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='3:c':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='3:a':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='4:b':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='4:c':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='4:a':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='5:b1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='5:b2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='5:b3':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='5:c1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='5:c2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='5:c3':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='5:a1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='5:a2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='5:a3':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='6:b':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='6:c':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='6:a':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='7:b1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='7:b2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='7:b3':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='7:c1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='7:c2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='7:c3':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='7:a1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='7:a2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='7:a3':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='8:b1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='8:b2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='8:b3':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='8:c1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='8:c2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='8:c3':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='8:a1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='8:a2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='8:a3':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='9:b1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='9:b2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='9:b3':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='9:-b1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='9:-b2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='9:-b3':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='9:c1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='9:c2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='9:c3':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='9:-c1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='9:-c2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='9:-c3':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='9:a1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='9:a2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='9:a3':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='9:-a1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='9:-a2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='9:-a3':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='10:b':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='10:c':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='10:a':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='11:b':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='11:c':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='11:a':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='12:b1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='12:b2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='12:b3':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='12:c1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='12:c2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='12:c3':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='12:a1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='12:a2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='12:a3':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='13:b1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='13:b2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='13:b3':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='13:c1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='13:c2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='13:c3':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='13:a1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='13:a2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='13:a3':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='14:b1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='14:b2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='14:b3':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='14:c1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='14:c2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='14:c3':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='14:a1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='14:a2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='14:a3':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='15:b1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='15:b2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='15:b3':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='15:-b1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='15:-b2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='15:-b3':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='15:c1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='15:c2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='15:c3':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='15:-c1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='15:-c2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='15:-c3':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='15:a1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='15:a2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='15:a3':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='15:-a1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='15:-a2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='15:-a3':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='16':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='17':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='17:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='17:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='18':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='18:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='18:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='19':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='20':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='20:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='20:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='21':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='21:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='21:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='22':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='23':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='24':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='25':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='25:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='25:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='26':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='26:ba-c':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='26:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='26:-cba':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='26:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='26:a-cb':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='27':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='27:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='27:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='28':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='28:ba-c':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='28:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='28:-cba':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='28:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='28:a-cb':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='29':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='29:ba-c':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='29:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='29:-cba':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='29:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='29:a-cb':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='30':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='30:ba-c':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='30:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='30:-cba':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='30:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='30:a-cb':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='31':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='31:ba-c':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='31:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='31:-cba':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='31:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='31:a-cb':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='32':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='32:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='32:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='33':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='33:ba-c':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='33:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='33:-cba':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='33:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='33:a-cb':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='34':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='34:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='34:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='35':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='35:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='35:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='36':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='36:ba-c':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='36:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='36:-cba':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='36:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='36:a-cb':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='37':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='37:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='37:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='38':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='38:ba-c':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='38:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='38:-cba':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='38:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='38:a-cb':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='39':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='39:ba-c':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='39:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='39:-cba':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='39:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='39:a-cb':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='40':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='40:ba-c':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='40:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='40:-cba':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='40:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='40:a-cb':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='41':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='41:ba-c':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='41:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='41:-cba':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='41:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='41:a-cb':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='42':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='42:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='42:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='43':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/4.], [0.,1.,0., 1/4.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,-1.,0., 1/4.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/4.], [0.,1.,0., -1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,-1.,0., -1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., -1/4.], [0.,1.,0., 1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,-1.,0., 1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., -1/4.], [0.,1.,0., -1/4.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,-1.,0., -1/4.], [0.,0.,1., 1/4.] ] ] )
		elif SpaceGroupID=='43:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/4.], [0.,1.,0., 1/4.], [0.,0.,-1., 1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,-1.,0., 1/4.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/4.], [0.,1.,0., -1/4.], [0.,0.,-1., -1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,-1.,0., -1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., -1/4.], [0.,1.,0., 1/4.], [0.,0.,-1., -1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,-1.,0., 1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., -1/4.], [0.,1.,0., -1/4.], [0.,0.,-1., 1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,-1.,0., -1/4.], [0.,0.,1., 1/4.] ] ] )
		elif SpaceGroupID=='43:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/4.], [0.,1.,0., 1/4.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,1.,0., 1/4.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/4.], [0.,1.,0., -1/4.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,1.,0., -1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., -1/4.], [0.,1.,0., 1/4.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,1.,0., 1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., -1/4.], [0.,1.,0., -1/4.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,1.,0., -1/4.], [0.,0.,1., 1/4.] ] ] )
		elif SpaceGroupID=='44':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='44:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='44:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='45':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='45:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='45:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='46':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='46:ba-c':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='46:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='46:-cba':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='46:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='46:a-cb':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='47':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='48:1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='48:2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='49':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='49:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='49:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='50:1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='50:2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='50:1cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='50:2cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='50:1bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='50:2bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='51':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='51:ba-c':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='51:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='51:-cba':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='51:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='51:a-cb':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='52':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='52:ba-c':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='52:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='52:-cba':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='52:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='52:a-cb':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='53':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='53:ba-c':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='53:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='53:-cba':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='53:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='53:a-cb':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='54':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='54:ba-c':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='54:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='54:-cba':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='54:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='54:a-cb':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='55':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='55:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='55:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='56':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='56:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='56:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='57':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='57:ba-c':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='57:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='57:-cba':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='57:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='57:a-cb':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='58':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='58:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='58:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='59:1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='59:2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='59:1cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='59:2cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='59:1bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='59:2bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='60':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='60:ba-c':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='60:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='60:-cba':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='60:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='60:a-cb':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='61':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='61:ba-c':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='62':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='62:ba-c':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='62:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='62:-cba':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='62:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='62:a-cb':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='63':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='63:ba-c':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='63:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='63:-cba':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='63:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='63:a-cb':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='64':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='64:ba-c':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='64:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='64:-cba':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='64:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='64:a-cb':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='65':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='65:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='65:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='66':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='66:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='66:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='67':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='67:ba-c':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='67:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='67:-cba':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='67:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='67:a-cb':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='68:1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='68:2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='68:1ba-c':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='68:2ba-c':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='68:1cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='68:2cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='68:1-cba':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='68:2-cba':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='68:1bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='68:2bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='68:1a-cb':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='68:2a-cb':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='69':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='70:1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/4.], [0.,-1.,0., 1/4.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/4.], [0.,1.,0., 1/4.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,1.,0., 1/4.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,-1.,0., 1/4.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/4.], [0.,-1.,0., -1/4.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/4.], [0.,1.,0., -1/4.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,1.,0., -1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,-1.,0., -1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., -1/4.], [0.,-1.,0., 1/4.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., -1/4.], [0.,1.,0., 1/4.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,1.,0., 1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,-1.,0., 1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., -1/4.], [0.,-1.,0., -1/4.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., -1/4.], [0.,1.,0., -1/4.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,1.,0., -1/4.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,-1.,0., -1/4.], [0.,0.,1., 1/4.] ] ] )
		elif SpaceGroupID=='70:2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/4.], [0.,-1.,0., 1/4.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/4.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,1.,0., 0], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., -1/4.], [0.,1.,0., -1/4.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., -1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,-1.,0., 0], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/4.], [0.,-1.,0., -1/4.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., -1/4.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,1.,0., 1/2.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., -1/4.], [0.,1.,0., 1/4.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/4.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., -1/4.], [0.,-1.,0., 1/4.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/4.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,1.,0., 0], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/4.], [0.,1.,0., -1/4.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., -1/4.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,-1.,0., 0], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., -1/4.], [0.,-1.,0., -1/4.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., -1/4.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/4.], [0.,1.,0., 1/4.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,-1.,0., 1/2.], [0.,0.,1., -1/4.] ] ] )
		elif SpaceGroupID=='71':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='72':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='72:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='72:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='73':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='73:ba-c':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='74':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='74:ba-c':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='74:cab':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='74:-cba':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='74:bca':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='74:a-cb':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='75':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='76':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., -1/4.] ] ] )
		elif SpaceGroupID=='77':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='78':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., -1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/4.] ] ] )
		elif SpaceGroupID=='79':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='80':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,1., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,1., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,1., -1/4.] ] ] )
		elif SpaceGroupID=='81':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='82':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='83':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='84':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='85:1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='85:2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='86:1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='86:2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='87':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='88:1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/4.] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,1., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,1., 1/4.] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., -1/4.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,1., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,1., -1/4.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., -1/4.] ] ] )
		elif SpaceGroupID=='88:2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., -1/4.], [1.,0.,0., 1/4.], [0.,0.,1., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/4.], [-1.,0.,0., 1/4.], [0.,0.,1., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 1/4.], [-1.,0.,0., -1/4.], [0.,0.,-1., -1/4.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., -1/4.], [1.,0.,0., -1/4.], [0.,0.,-1., -1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/4.], [1.,0.,0., -1/4.], [0.,0.,1., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., -1/4.], [-1.,0.,0., -1/4.], [0.,0.,1., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., -1/4.], [-1.,0.,0., 1/4.], [0.,0.,-1., 1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/4.], [1.,0.,0., 1/4.], [0.,0.,-1., 1/4.] ] ] )
		elif SpaceGroupID=='89':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='90':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='91':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., -1/4.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 1/4.] ] ] )
		elif SpaceGroupID=='92':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/4.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='93':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='94':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='95':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., -1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 1/4.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., -1/4.] ] ] )
		elif SpaceGroupID=='96':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., -1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., -1/4.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='97':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='98':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,1., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/4.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,1., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., -1/4.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='99':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='100':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='101':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='102':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='103':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='104':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='105':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='106':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='107':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='108':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='109':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,1., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,1., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,1., 1/4.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,1., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,1., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,1., -1/4.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,1., -1/4.] ] ] )
		elif SpaceGroupID=='110':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,1., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,1., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,1., 1/4.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,1., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,1., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,1., -1/4.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,1., -1/4.] ] ] )
		elif SpaceGroupID=='111':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='112':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='113':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='114':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='115':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='116':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='117':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='118':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='119':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='120':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='121':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='122':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/4.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,1., 1/4.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., -1/4.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,1., -1/4.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,1., -1/4.] ] ] )
		elif SpaceGroupID=='123':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='124':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='125:1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='125:2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='126:1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='126:2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='127':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='128':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='129:1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='129:2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='130:1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='130:2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='131':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='132':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='133:1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='133:2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='134:1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='134:2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='135':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='136':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='137:1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='137:2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='138:1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='138:2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='139':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='140':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='141:1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/4.] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,1., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,1., 1/4.] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/4.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,1., 1/4.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., -1/4.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,1., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,1., -1/4.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., -1/4.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,1., -1/4.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,1., -1/4.] ] ] )
		elif SpaceGroupID=='141:2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/4.], [1.,0.,0., -1/4.], [0.,0.,1., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/4.], [-1.,0.,0., 1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 1/4.], [1.,0.,0., -1/4.], [0.,0.,-1., 1/4.] ],
			[ [0.,-1.,0., 1/4.], [-1.,0.,0., 1/4.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., -1/4.], [-1.,0.,0., 1/4.], [0.,0.,-1., -1/4.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., -1/4.], [1.,0.,0., -1/4.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,-1.,0., -1/4.], [-1.,0.,0., 1/4.], [0.,0.,1., -1/4.] ],
			[ [0.,1.,0., -1/4.], [1.,0.,0., -1/4.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., -1/4.], [1.,0.,0., 1/4.], [0.,0.,1., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., -1/4.], [-1.,0.,0., -1/4.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., -1/4.], [1.,0.,0., 1/4.], [0.,0.,-1., -1/4.] ],
			[ [0.,-1.,0., -1/4.], [-1.,0.,0., -1/4.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 1/4.], [-1.,0.,0., -1/4.], [0.,0.,-1., 1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/4.], [1.,0.,0., 1/4.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/4.], [-1.,0.,0., -1/4.], [0.,0.,1., 1/4.] ],
			[ [0.,1.,0., 1/4.], [1.,0.,0., 1/4.], [0.,0.,1., -1/4.] ] ] )
		elif SpaceGroupID=='142:1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/4.] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,1., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,1., 1/4.] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/4.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,1., 1/4.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., -1/4.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,1., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,1., -1/4.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., -1/4.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,1., -1/4.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,1., -1/4.] ] ] )
		elif SpaceGroupID=='142:2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/4.], [1.,0.,0., -1/4.], [0.,0.,1., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/4.], [-1.,0.,0., 1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., -1/4.], [1.,0.,0., 1/4.], [0.,0.,-1., 1/4.] ],
			[ [0.,-1.,0., 1/4.], [-1.,0.,0., 1/4.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., -1/4.], [-1.,0.,0., 1/4.], [0.,0.,-1., -1/4.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., -1/4.], [1.,0.,0., -1/4.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/4.], [-1.,0.,0., -1/4.], [0.,0.,1., -1/4.] ],
			[ [0.,1.,0., -1/4.], [1.,0.,0., -1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., -1/4.], [1.,0.,0., 1/4.], [0.,0.,1., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., -1/4.], [-1.,0.,0., -1/4.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 1/4.], [1.,0.,0., -1/4.], [0.,0.,-1., -1/4.] ],
			[ [0.,-1.,0., -1/4.], [-1.,0.,0., -1/4.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 1/4.], [-1.,0.,0., -1/4.], [0.,0.,-1., 1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/4.], [1.,0.,0., 1/4.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., -1/4.], [-1.,0.,0., 1/4.], [0.,0.,1., 1/4.] ],
			[ [0.,1.,0., 1/4.], [1.,0.,0., 1/4.], [0.,0.,1., 1/4.] ] ] )
		elif SpaceGroupID=='143':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='144':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 1/3.] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., -1/3.] ] ] )
		elif SpaceGroupID=='145':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., -1/3.] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/3.] ] ] )
		elif SpaceGroupID=='146:H':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., -1/3.], [0.,1.,0., 1/3.], [0.,0.,1., 1/3.] ],
			[ [0.,-1.,0., -1/3.], [1.,-1.,0., 1/3.], [0.,0.,1., 1/3.] ],
			[ [-1.,1.,0., -1/3.], [-1.,0.,0., 1/3.], [0.,0.,1., 1/3.] ],
			[ [1.,0.,0., 1/3.], [0.,1.,0., -1/3.], [0.,0.,1., -1/3.] ],
			[ [0.,-1.,0., 1/3.], [1.,-1.,0., -1/3.], [0.,0.,1., -1/3.] ],
			[ [-1.,1.,0., 1/3.], [-1.,0.,0., -1/3.], [0.,0.,1., -1/3.] ] ] )
		elif SpaceGroupID=='146:R':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ] ] )
		elif SpaceGroupID=='147':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [-1.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='148:H':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [-1.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., -1/3.], [0.,1.,0., 1/3.], [0.,0.,1., 1/3.] ],
			[ [0.,-1.,0., -1/3.], [1.,-1.,0., 1/3.], [0.,0.,1., 1/3.] ],
			[ [-1.,1.,0., -1/3.], [-1.,0.,0., 1/3.], [0.,0.,1., 1/3.] ],
			[ [-1.,0.,0., -1/3.], [0.,-1.,0., 1/3.], [0.,0.,-1., 1/3.] ],
			[ [0.,1.,0., -1/3.], [-1.,1.,0., 1/3.], [0.,0.,-1., 1/3.] ],
			[ [1.,-1.,0., -1/3.], [1.,0.,0., 1/3.], [0.,0.,-1., 1/3.] ],
			[ [1.,0.,0., 1/3.], [0.,1.,0., -1/3.], [0.,0.,1., -1/3.] ],
			[ [0.,-1.,0., 1/3.], [1.,-1.,0., -1/3.], [0.,0.,1., -1/3.] ],
			[ [-1.,1.,0., 1/3.], [-1.,0.,0., -1/3.], [0.,0.,1., -1/3.] ],
			[ [-1.,0.,0., 1/3.], [0.,-1.,0., -1/3.], [0.,0.,-1., -1/3.] ],
			[ [0.,1.,0., 1/3.], [-1.,1.,0., -1/3.], [0.,0.,-1., -1/3.] ],
			[ [1.,-1.,0., 1/3.], [1.,0.,0., -1/3.], [0.,0.,-1., -1/3.] ] ] )
		elif SpaceGroupID=='148:R':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ] ] )
		elif SpaceGroupID=='149':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,1.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [1.,-1.,0., 0], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='150':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [-1.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='151':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 1/3.] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., -1/3.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., -1/3.] ],
			[ [-1.,1.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/3.] ],
			[ [1.,0.,0., 0], [1.,-1.,0., 0], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='152':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 1/3.] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., -1/3.] ],
			[ [1.,-1.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., -1/3.] ],
			[ [-1.,0.,0., 0], [-1.,1.,0., 0], [0.,0.,-1., 1/3.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='153':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., -1/3.] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/3.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 1/3.] ],
			[ [-1.,1.,0., 0], [0.,1.,0., 0], [0.,0.,-1., -1/3.] ],
			[ [1.,0.,0., 0], [1.,-1.,0., 0], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='154':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., -1/3.] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/3.] ],
			[ [1.,-1.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/3.] ],
			[ [-1.,0.,0., 0], [-1.,1.,0., 0], [0.,0.,-1., -1/3.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='155:H':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [-1.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., -1/3.], [0.,1.,0., 1/3.], [0.,0.,1., 1/3.] ],
			[ [0.,-1.,0., -1/3.], [1.,-1.,0., 1/3.], [0.,0.,1., 1/3.] ],
			[ [-1.,1.,0., -1/3.], [-1.,0.,0., 1/3.], [0.,0.,1., 1/3.] ],
			[ [1.,-1.,0., -1/3.], [0.,-1.,0., 1/3.], [0.,0.,-1., 1/3.] ],
			[ [-1.,0.,0., -1/3.], [-1.,1.,0., 1/3.], [0.,0.,-1., 1/3.] ],
			[ [0.,1.,0., -1/3.], [1.,0.,0., 1/3.], [0.,0.,-1., 1/3.] ],
			[ [1.,0.,0., 1/3.], [0.,1.,0., -1/3.], [0.,0.,1., -1/3.] ],
			[ [0.,-1.,0., 1/3.], [1.,-1.,0., -1/3.], [0.,0.,1., -1/3.] ],
			[ [-1.,1.,0., 1/3.], [-1.,0.,0., -1/3.], [0.,0.,1., -1/3.] ],
			[ [1.,-1.,0., 1/3.], [0.,-1.,0., -1/3.], [0.,0.,-1., -1/3.] ],
			[ [-1.,0.,0., 1/3.], [-1.,1.,0., -1/3.], [0.,0.,-1., -1/3.] ],
			[ [0.,1.,0., 1/3.], [1.,0.,0., -1/3.], [0.,0.,-1., -1/3.] ] ] )
		elif SpaceGroupID=='155:R':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,-1., 0], [0.,-1.,0., 0] ],
			[ [0.,0.,-1., 0], [0.,-1.,0., 0], [-1.,0.,0., 0] ] ] )
		elif SpaceGroupID=='156':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='157':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [-1.,1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='158':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='159':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,-1.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [-1.,1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='160:H':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., -1/3.], [0.,1.,0., 1/3.], [0.,0.,1., 1/3.] ],
			[ [0.,-1.,0., -1/3.], [1.,-1.,0., 1/3.], [0.,0.,1., 1/3.] ],
			[ [-1.,1.,0., -1/3.], [-1.,0.,0., 1/3.], [0.,0.,1., 1/3.] ],
			[ [-1.,1.,0., -1/3.], [0.,1.,0., 1/3.], [0.,0.,1., 1/3.] ],
			[ [1.,0.,0., -1/3.], [1.,-1.,0., 1/3.], [0.,0.,1., 1/3.] ],
			[ [0.,-1.,0., -1/3.], [-1.,0.,0., 1/3.], [0.,0.,1., 1/3.] ],
			[ [1.,0.,0., 1/3.], [0.,1.,0., -1/3.], [0.,0.,1., -1/3.] ],
			[ [0.,-1.,0., 1/3.], [1.,-1.,0., -1/3.], [0.,0.,1., -1/3.] ],
			[ [-1.,1.,0., 1/3.], [-1.,0.,0., -1/3.], [0.,0.,1., -1/3.] ],
			[ [-1.,1.,0., 1/3.], [0.,1.,0., -1/3.], [0.,0.,1., -1/3.] ],
			[ [1.,0.,0., 1/3.], [1.,-1.,0., -1/3.], [0.,0.,1., -1/3.] ],
			[ [0.,-1.,0., 1/3.], [-1.,0.,0., -1/3.], [0.,0.,1., -1/3.] ] ] )
		elif SpaceGroupID=='160:R':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,0.,1., 0], [0.,1.,0., 0] ],
			[ [0.,0.,1., 0], [0.,1.,0., 0], [1.,0.,0., 0] ] ] )
		elif SpaceGroupID=='161:H':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., -1/3.], [0.,1.,0., 1/3.], [0.,0.,1., 1/3.] ],
			[ [0.,-1.,0., -1/3.], [1.,-1.,0., 1/3.], [0.,0.,1., 1/3.] ],
			[ [-1.,1.,0., -1/3.], [-1.,0.,0., 1/3.], [0.,0.,1., 1/3.] ],
			[ [-1.,1.,0., -1/3.], [0.,1.,0., 1/3.], [0.,0.,1., -1/6.] ],
			[ [1.,0.,0., -1/3.], [1.,-1.,0., 1/3.], [0.,0.,1., -1/6.] ],
			[ [0.,-1.,0., -1/3.], [-1.,0.,0., 1/3.], [0.,0.,1., -1/6.] ],
			[ [1.,0.,0., 1/3.], [0.,1.,0., -1/3.], [0.,0.,1., -1/3.] ],
			[ [0.,-1.,0., 1/3.], [1.,-1.,0., -1/3.], [0.,0.,1., -1/3.] ],
			[ [-1.,1.,0., 1/3.], [-1.,0.,0., -1/3.], [0.,0.,1., -1/3.] ],
			[ [-1.,1.,0., 1/3.], [0.,1.,0., -1/3.], [0.,0.,1., 1/6.] ],
			[ [1.,0.,0., 1/3.], [1.,-1.,0., -1/3.], [0.,0.,1., 1/6.] ],
			[ [0.,-1.,0., 1/3.], [-1.,0.,0., -1/3.], [0.,0.,1., 1/6.] ] ] )
		elif SpaceGroupID=='161:R':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,1.,0., 1/2.], [1.,0.,0., 1/2.] ] ] )
		elif SpaceGroupID=='162':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,1.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [1.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [-1.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [-1.,1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='163':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,1.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [1.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [-1.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,-1.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [-1.,1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='164':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [-1.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [-1.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,1.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='165':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [-1.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [-1.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,1.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='166:H':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [-1.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [-1.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,1.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., -1/3.], [0.,1.,0., 1/3.], [0.,0.,1., 1/3.] ],
			[ [0.,-1.,0., -1/3.], [1.,-1.,0., 1/3.], [0.,0.,1., 1/3.] ],
			[ [-1.,1.,0., -1/3.], [-1.,0.,0., 1/3.], [0.,0.,1., 1/3.] ],
			[ [1.,-1.,0., -1/3.], [0.,-1.,0., 1/3.], [0.,0.,-1., 1/3.] ],
			[ [-1.,0.,0., -1/3.], [-1.,1.,0., 1/3.], [0.,0.,-1., 1/3.] ],
			[ [0.,1.,0., -1/3.], [1.,0.,0., 1/3.], [0.,0.,-1., 1/3.] ],
			[ [-1.,0.,0., -1/3.], [0.,-1.,0., 1/3.], [0.,0.,-1., 1/3.] ],
			[ [0.,1.,0., -1/3.], [-1.,1.,0., 1/3.], [0.,0.,-1., 1/3.] ],
			[ [1.,-1.,0., -1/3.], [1.,0.,0., 1/3.], [0.,0.,-1., 1/3.] ],
			[ [-1.,1.,0., -1/3.], [0.,1.,0., 1/3.], [0.,0.,1., 1/3.] ],
			[ [1.,0.,0., -1/3.], [1.,-1.,0., 1/3.], [0.,0.,1., 1/3.] ],
			[ [0.,-1.,0., -1/3.], [-1.,0.,0., 1/3.], [0.,0.,1., 1/3.] ],
			[ [1.,0.,0., 1/3.], [0.,1.,0., -1/3.], [0.,0.,1., -1/3.] ],
			[ [0.,-1.,0., 1/3.], [1.,-1.,0., -1/3.], [0.,0.,1., -1/3.] ],
			[ [-1.,1.,0., 1/3.], [-1.,0.,0., -1/3.], [0.,0.,1., -1/3.] ],
			[ [1.,-1.,0., 1/3.], [0.,-1.,0., -1/3.], [0.,0.,-1., -1/3.] ],
			[ [-1.,0.,0., 1/3.], [-1.,1.,0., -1/3.], [0.,0.,-1., -1/3.] ],
			[ [0.,1.,0., 1/3.], [1.,0.,0., -1/3.], [0.,0.,-1., -1/3.] ],
			[ [-1.,0.,0., 1/3.], [0.,-1.,0., -1/3.], [0.,0.,-1., -1/3.] ],
			[ [0.,1.,0., 1/3.], [-1.,1.,0., -1/3.], [0.,0.,-1., -1/3.] ],
			[ [1.,-1.,0., 1/3.], [1.,0.,0., -1/3.], [0.,0.,-1., -1/3.] ],
			[ [-1.,1.,0., 1/3.], [0.,1.,0., -1/3.], [0.,0.,1., -1/3.] ],
			[ [1.,0.,0., 1/3.], [1.,-1.,0., -1/3.], [0.,0.,1., -1/3.] ],
			[ [0.,-1.,0., 1/3.], [-1.,0.,0., -1/3.], [0.,0.,1., -1/3.] ] ] )
		elif SpaceGroupID=='166:R':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,-1., 0], [0.,-1.,0., 0] ],
			[ [0.,0.,-1., 0], [0.,-1.,0., 0], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,0.,1., 0], [0.,1.,0., 0] ],
			[ [0.,0.,1., 0], [0.,1.,0., 0], [1.,0.,0., 0] ] ] )
		elif SpaceGroupID=='167:H':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [-1.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [-1.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,1.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., -1/3.], [0.,1.,0., 1/3.], [0.,0.,1., 1/3.] ],
			[ [0.,-1.,0., -1/3.], [1.,-1.,0., 1/3.], [0.,0.,1., 1/3.] ],
			[ [-1.,1.,0., -1/3.], [-1.,0.,0., 1/3.], [0.,0.,1., 1/3.] ],
			[ [1.,-1.,0., -1/3.], [0.,-1.,0., 1/3.], [0.,0.,-1., -1/6.] ],
			[ [-1.,0.,0., -1/3.], [-1.,1.,0., 1/3.], [0.,0.,-1., -1/6.] ],
			[ [0.,1.,0., -1/3.], [1.,0.,0., 1/3.], [0.,0.,-1., -1/6.] ],
			[ [-1.,0.,0., -1/3.], [0.,-1.,0., 1/3.], [0.,0.,-1., 1/3.] ],
			[ [0.,1.,0., -1/3.], [-1.,1.,0., 1/3.], [0.,0.,-1., 1/3.] ],
			[ [1.,-1.,0., -1/3.], [1.,0.,0., 1/3.], [0.,0.,-1., 1/3.] ],
			[ [-1.,1.,0., -1/3.], [0.,1.,0., 1/3.], [0.,0.,1., -1/6.] ],
			[ [1.,0.,0., -1/3.], [1.,-1.,0., 1/3.], [0.,0.,1., -1/6.] ],
			[ [0.,-1.,0., -1/3.], [-1.,0.,0., 1/3.], [0.,0.,1., -1/6.] ],
			[ [1.,0.,0., 1/3.], [0.,1.,0., -1/3.], [0.,0.,1., -1/3.] ],
			[ [0.,-1.,0., 1/3.], [1.,-1.,0., -1/3.], [0.,0.,1., -1/3.] ],
			[ [-1.,1.,0., 1/3.], [-1.,0.,0., -1/3.], [0.,0.,1., -1/3.] ],
			[ [1.,-1.,0., 1/3.], [0.,-1.,0., -1/3.], [0.,0.,-1., 1/6.] ],
			[ [-1.,0.,0., 1/3.], [-1.,1.,0., -1/3.], [0.,0.,-1., 1/6.] ],
			[ [0.,1.,0., 1/3.], [1.,0.,0., -1/3.], [0.,0.,-1., 1/6.] ],
			[ [-1.,0.,0., 1/3.], [0.,-1.,0., -1/3.], [0.,0.,-1., -1/3.] ],
			[ [0.,1.,0., 1/3.], [-1.,1.,0., -1/3.], [0.,0.,-1., -1/3.] ],
			[ [1.,-1.,0., 1/3.], [1.,0.,0., -1/3.], [0.,0.,-1., -1/3.] ],
			[ [-1.,1.,0., 1/3.], [0.,1.,0., -1/3.], [0.,0.,1., 1/6.] ],
			[ [1.,0.,0., 1/3.], [1.,-1.,0., -1/3.], [0.,0.,1., 1/6.] ],
			[ [0.,-1.,0., 1/3.], [-1.,0.,0., -1/3.], [0.,0.,1., 1/6.] ] ] )
		elif SpaceGroupID=='167:R':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,1.,0., 1/2.], [1.,0.,0., 1/2.] ] ] )
		elif SpaceGroupID=='168':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='169':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/6.] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 1/3.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., -1/3.] ],
			[ [0.,1.,0., 0], [-1.,1.,0., 0], [0.,0.,1., -1/6.] ] ] )
		elif SpaceGroupID=='170':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., -1/6.] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., -1/3.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/3.] ],
			[ [0.,1.,0., 0], [-1.,1.,0., 0], [0.,0.,1., 1/6.] ] ] )
		elif SpaceGroupID=='171':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/3.] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., -1/3.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/3.] ],
			[ [0.,1.,0., 0], [-1.,1.,0., 0], [0.,0.,1., -1/3.] ] ] )
		elif SpaceGroupID=='172':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., -1/3.] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 1/3.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., -1/3.] ],
			[ [0.,1.,0., 0], [-1.,1.,0., 0], [0.,0.,1., 1/3.] ] ] )
		elif SpaceGroupID=='173':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='174':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='175':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [-1.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='176':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 0], [-1.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='177':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [-1.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,1.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [1.,-1.,0., 0], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='178':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/6.] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 1/3.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., -1/3.] ],
			[ [0.,1.,0., 0], [-1.,1.,0., 0], [0.,0.,1., -1/6.] ],
			[ [1.,-1.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [-1.,1.,0., 0], [0.,0.,-1., -1/3.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 1/3.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., -1/6.] ],
			[ [-1.,1.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [1.,-1.,0., 0], [0.,0.,-1., 1/6.] ] ] )
		elif SpaceGroupID=='179':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., -1/6.] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., -1/3.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/3.] ],
			[ [0.,1.,0., 0], [-1.,1.,0., 0], [0.,0.,1., 1/6.] ],
			[ [1.,-1.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [-1.,1.,0., 0], [0.,0.,-1., 1/3.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., -1/3.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 1/6.] ],
			[ [-1.,1.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [1.,-1.,0., 0], [0.,0.,-1., -1/6.] ] ] )
		elif SpaceGroupID=='180':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/3.] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., -1/3.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/3.] ],
			[ [0.,1.,0., 0], [-1.,1.,0., 0], [0.,0.,1., -1/3.] ],
			[ [1.,-1.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [-1.,1.,0., 0], [0.,0.,-1., 1/3.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., -1/3.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., -1/3.] ],
			[ [-1.,1.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [1.,-1.,0., 0], [0.,0.,-1., 1/3.] ] ] )
		elif SpaceGroupID=='181':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., -1/3.] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 1/3.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., -1/3.] ],
			[ [0.,1.,0., 0], [-1.,1.,0., 0], [0.,0.,1., 1/3.] ],
			[ [1.,-1.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [-1.,1.,0., 0], [0.,0.,-1., -1/3.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 1/3.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 1/3.] ],
			[ [-1.,1.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [1.,-1.,0., 0], [0.,0.,-1., -1/3.] ] ] )
		elif SpaceGroupID=='182':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,-1.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [-1.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,1.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [1.,-1.,0., 0], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='183':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [-1.,1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='184':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,-1.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [-1.,1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='185':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,1.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [-1.,1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='186':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,1.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,-1.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [-1.,1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='187':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,1.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [1.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,1.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='188':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,1.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [1.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,1.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='189':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,-1.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [-1.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [-1.,1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='190':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,-1.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [-1.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,-1.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [-1.,1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='191':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [-1.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,1.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [1.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [-1.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,1.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [-1.,1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='192':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [-1.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,1.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [1.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [-1.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,1.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,-1.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [-1.,1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='193':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,-1.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [-1.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,1.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [1.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 0], [-1.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,1.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [-1.,1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='194':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,-1.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [-1.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,1.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [1.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 0], [-1.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,1.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [1.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,-1.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [-1.,1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='195':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='196':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,0.,1., 0], [1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 0], [0.,0.,1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 0], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ] ] )
		elif SpaceGroupID=='197':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='198':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='199':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ] ] )
		elif SpaceGroupID=='200':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='201:1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='201:2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='202':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,0.,1., 0], [1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 0], [0.,0.,1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,1.,0., 0], [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 0], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 0], [1.,0.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.], [1.,0.,0., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ] ] )
		elif SpaceGroupID=='203:1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/4.], [0.,-1.,0., 1/4.], [0.,0.,-1., 1/4.] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 1/4.], [-1.,0.,0., 1/4.], [0.,-1.,0., 1/4.] ],
			[ [0.,-1.,0., 1/4.], [0.,0.,-1., 1/4.], [-1.,0.,0., 1/4.] ],
			[ [0.,1.,0., 1/4.], [0.,0.,1., 1/4.], [-1.,0.,0., 1/4.] ],
			[ [0.,0.,-1., 1/4.], [1.,0.,0., 1/4.], [0.,1.,0., 1/4.] ],
			[ [0.,1.,0., 1/4.], [0.,0.,-1., 1/4.], [1.,0.,0., 1/4.] ],
			[ [0.,0.,1., 1/4.], [1.,0.,0., 1/4.], [0.,-1.,0., 1/4.] ],
			[ [0.,0.,1., 1/4.], [-1.,0.,0., 1/4.], [0.,1.,0., 1/4.] ],
			[ [0.,-1.,0., 1/4.], [0.,0.,1., 1/4.], [1.,0.,0., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/4.], [0.,1.,0., 1/4.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,1.,0., 1/4.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,-1.,0., 1/4.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/4.], [0.,-1.,0., -1/4.], [0.,0.,-1., -1/4.] ],
			[ [0.,0.,1., 0], [1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 0], [0.,0.,1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/4.], [-1.,0.,0., -1/4.], [0.,-1.,0., -1/4.] ],
			[ [0.,-1.,0., 1/4.], [0.,0.,-1., -1/4.], [-1.,0.,0., -1/4.] ],
			[ [0.,1.,0., 1/4.], [0.,0.,1., -1/4.], [-1.,0.,0., -1/4.] ],
			[ [0.,0.,-1., 1/4.], [1.,0.,0., -1/4.], [0.,1.,0., -1/4.] ],
			[ [0.,1.,0., 1/4.], [0.,0.,-1., -1/4.], [1.,0.,0., -1/4.] ],
			[ [0.,0.,1., 1/4.], [1.,0.,0., -1/4.], [0.,-1.,0., -1/4.] ],
			[ [0.,0.,1., 1/4.], [-1.,0.,0., -1/4.], [0.,1.,0., -1/4.] ],
			[ [0.,-1.,0., 1/4.], [0.,0.,1., -1/4.], [1.,0.,0., -1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/4.], [0.,1.,0., -1/4.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,1.,0., -1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,-1.,0., -1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., -1/4.], [0.,-1.,0., 1/4.], [0.,0.,-1., -1/4.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., -1/4.], [-1.,0.,0., 1/4.], [0.,-1.,0., -1/4.] ],
			[ [0.,-1.,0., -1/4.], [0.,0.,-1., 1/4.], [-1.,0.,0., -1/4.] ],
			[ [0.,1.,0., -1/4.], [0.,0.,1., 1/4.], [-1.,0.,0., -1/4.] ],
			[ [0.,0.,-1., -1/4.], [1.,0.,0., 1/4.], [0.,1.,0., -1/4.] ],
			[ [0.,1.,0., -1/4.], [0.,0.,-1., 1/4.], [1.,0.,0., -1/4.] ],
			[ [0.,0.,1., -1/4.], [1.,0.,0., 1/4.], [0.,-1.,0., -1/4.] ],
			[ [0.,0.,1., -1/4.], [-1.,0.,0., 1/4.], [0.,1.,0., -1/4.] ],
			[ [0.,-1.,0., -1/4.], [0.,0.,1., 1/4.], [1.,0.,0., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., -1/4.], [0.,1.,0., 1/4.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,1.,0., 1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,-1.,0., 1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., -1/4.], [0.,-1.,0., -1/4.], [0.,0.,-1., 1/4.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., -1/4.], [-1.,0.,0., -1/4.], [0.,-1.,0., 1/4.] ],
			[ [0.,-1.,0., -1/4.], [0.,0.,-1., -1/4.], [-1.,0.,0., 1/4.] ],
			[ [0.,1.,0., -1/4.], [0.,0.,1., -1/4.], [-1.,0.,0., 1/4.] ],
			[ [0.,0.,-1., -1/4.], [1.,0.,0., -1/4.], [0.,1.,0., 1/4.] ],
			[ [0.,1.,0., -1/4.], [0.,0.,-1., -1/4.], [1.,0.,0., 1/4.] ],
			[ [0.,0.,1., -1/4.], [1.,0.,0., -1/4.], [0.,-1.,0., 1/4.] ],
			[ [0.,0.,1., -1/4.], [-1.,0.,0., -1/4.], [0.,1.,0., 1/4.] ],
			[ [0.,-1.,0., -1/4.], [0.,0.,1., -1/4.], [1.,0.,0., 1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., -1/4.], [0.,1.,0., -1/4.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,1.,0., -1/4.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,-1.,0., -1/4.], [0.,0.,1., 1/4.] ] ] )
		elif SpaceGroupID=='203:2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 1/4.], [0.,0.,-1., 1/4.], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 1/4.], [0.,-1.,0., 1/4.] ],
			[ [0.,-1.,0., 1/4.], [0.,0.,1., 0], [-1.,0.,0., 1/4.] ],
			[ [0.,0.,-1., 1/4.], [-1.,0.,0., 1/4.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/4.], [1.,0.,0., 0], [0.,-1.,0., 1/4.] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 1/4.], [-1.,0.,0., 1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,-1.,0., 1/4.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/4.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,1.,0., 0], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,1.,0., -1/4.], [0.,0.,1., -1/4.], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., -1/4.], [0.,1.,0., -1/4.] ],
			[ [0.,1.,0., -1/4.], [0.,0.,-1., 0], [1.,0.,0., -1/4.] ],
			[ [0.,0.,1., -1/4.], [1.,0.,0., -1/4.], [0.,-1.,0., 0] ],
			[ [0.,0.,1., -1/4.], [-1.,0.,0., 0], [0.,1.,0., -1/4.] ],
			[ [0.,-1.,0., 0], [0.,0.,1., -1/4.], [1.,0.,0., -1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,1.,0., -1/4.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., -1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,-1.,0., 0], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,0.,1., 0], [1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 0], [0.,0.,1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 1/4.], [0.,0.,-1., -1/4.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [-1.,0.,0., -1/4.], [0.,-1.,0., -1/4.] ],
			[ [0.,-1.,0., 1/4.], [0.,0.,1., 1/2.], [-1.,0.,0., -1/4.] ],
			[ [0.,0.,-1., 1/4.], [-1.,0.,0., -1/4.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/4.], [1.,0.,0., 1/2.], [0.,-1.,0., -1/4.] ],
			[ [0.,1.,0., 0], [0.,0.,-1., -1/4.], [-1.,0.,0., -1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,-1.,0., -1/4.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., -1/4.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,1.,0., 1/2.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,1.,0., -1/4.], [0.,0.,1., 1/4.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 1/4.], [0.,1.,0., 1/4.] ],
			[ [0.,1.,0., -1/4.], [0.,0.,-1., 1/2.], [1.,0.,0., 1/4.] ],
			[ [0.,0.,1., -1/4.], [1.,0.,0., 1/4.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., -1/4.], [-1.,0.,0., 1/2.], [0.,1.,0., 1/4.] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 1/4.], [1.,0.,0., 1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,1.,0., 1/4.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/4.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., -1/4.], [0.,0.,-1., 1/4.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 1/4.], [0.,-1.,0., -1/4.] ],
			[ [0.,-1.,0., -1/4.], [0.,0.,1., 0], [-1.,0.,0., -1/4.] ],
			[ [0.,0.,-1., -1/4.], [-1.,0.,0., 1/4.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., -1/4.], [1.,0.,0., 0], [0.,-1.,0., -1/4.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 1/4.], [-1.,0.,0., -1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,-1.,0., 1/4.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/4.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,1.,0., 0], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,1.,0., 1/4.], [0.,0.,1., -1/4.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., -1/4.], [0.,1.,0., 1/4.] ],
			[ [0.,1.,0., 1/4.], [0.,0.,-1., 0], [1.,0.,0., 1/4.] ],
			[ [0.,0.,1., 1/4.], [1.,0.,0., -1/4.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 1/4.], [-1.,0.,0., 0], [0.,1.,0., 1/4.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., -1/4.], [1.,0.,0., 1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,1.,0., -1/4.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., -1/4.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,-1.,0., 0], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,-1.,0., -1/4.], [0.,0.,-1., -1/4.], [1.,0.,0., 0] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., -1/4.], [0.,-1.,0., 1/4.] ],
			[ [0.,-1.,0., -1/4.], [0.,0.,1., 1/2.], [-1.,0.,0., 1/4.] ],
			[ [0.,0.,-1., -1/4.], [-1.,0.,0., -1/4.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., -1/4.], [1.,0.,0., 1/2.], [0.,-1.,0., 1/4.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., -1/4.], [-1.,0.,0., 1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,-1.,0., -1/4.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., -1/4.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 1/4.], [0.,0.,1., 1/4.], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 1/4.], [0.,1.,0., -1/4.] ],
			[ [0.,1.,0., 1/4.], [0.,0.,-1., 1/2.], [1.,0.,0., -1/4.] ],
			[ [0.,0.,1., 1/4.], [1.,0.,0., 1/4.], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 1/4.], [-1.,0.,0., 1/2.], [0.,1.,0., -1/4.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 1/4.], [1.,0.,0., -1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,1.,0., 1/4.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,-1.,0., 1/2.], [0.,0.,1., -1/4.] ] ] )
		elif SpaceGroupID=='204':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='205':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.], [1.,0.,0., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='206':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.], [1.,0.,0., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ] ] )
		elif SpaceGroupID=='207':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,0.,-1., 0], [0.,1.,0., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,0.,1., 0], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 0], [0.,1.,0., 0], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,0.,-1., 0], [0.,1.,0., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,1., 0], [0.,1.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,-1., 0], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 0], [0.,-1.,0., 0], [1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [0.,-1.,0., 0], [-1.,0.,0., 0] ] ] )
		elif SpaceGroupID=='208':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.] ] ] )
		elif SpaceGroupID=='209':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,0.,-1., 0], [0.,1.,0., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,0.,1., 0], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 0], [0.,1.,0., 0], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,0.,-1., 0], [0.,1.,0., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,1., 0], [0.,1.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,-1., 0], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 0], [0.,-1.,0., 0], [1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [0.,-1.,0., 0], [-1.,0.,0., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 0], [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,0.,-1., 0], [0.,1.,0., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 0], [0.,0.,1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,0.,1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 0], [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,-1., 0], [0.,1.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,1., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,1.,0., 0], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,1.,0., 0], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,1., 0], [0.,1.,0., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,-1., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,-1.,0., 0], [1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,-1.,0., 0], [-1.,0.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,1.,0., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 1/2.], [0.,1.,0., 1/2.], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.], [1.,0.,0., 0] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,1.,0., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.], [1.,0.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.], [-1.,0.,0., 0] ] ] )
		elif SpaceGroupID=='210':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/4.], [1.,0.,0., 1/4.], [0.,0.,1., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/4.], [-1.,0.,0., 1/4.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,0.,-1., 1/4.], [0.,1.,0., 1/4.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/4.], [0.,0.,1., 1/4.], [0.,-1.,0., 1/4.] ],
			[ [0.,0.,1., 1/4.], [0.,1.,0., 1/4.], [-1.,0.,0., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,0.,-1., 1/4.], [0.,1.,0., 1/4.], [1.,0.,0., 1/4.] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 1/4.], [1.,0.,0., 1/4.], [0.,0.,-1., 1/4.] ],
			[ [0.,-1.,0., 1/4.], [-1.,0.,0., 1/4.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,0.,1., 1/4.], [0.,1.,0., 1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,0.,-1., 1/4.], [0.,-1.,0., 1/4.] ],
			[ [0.,0.,1., 1/4.], [0.,-1.,0., 1/4.], [1.,0.,0., 1/4.] ],
			[ [0.,0.,-1., 1/4.], [0.,-1.,0., 1/4.], [-1.,0.,0., 1/4.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/4.], [1.,0.,0., -1/4.], [0.,0.,1., -1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/4.], [-1.,0.,0., -1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,0.,-1., -1/4.], [0.,1.,0., -1/4.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/4.], [0.,0.,1., -1/4.], [0.,-1.,0., -1/4.] ],
			[ [0.,0.,1., 1/4.], [0.,1.,0., -1/4.], [-1.,0.,0., -1/4.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,0.,-1., 1/4.], [0.,1.,0., -1/4.], [1.,0.,0., -1/4.] ],
			[ [0.,0.,1., 0], [1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 0], [0.,0.,1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,1.,0., 1/4.], [1.,0.,0., -1/4.], [0.,0.,-1., -1/4.] ],
			[ [0.,-1.,0., 1/4.], [-1.,0.,0., -1/4.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,0.,1., -1/4.], [0.,1.,0., -1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,0.,-1., -1/4.], [0.,-1.,0., -1/4.] ],
			[ [0.,0.,1., 1/4.], [0.,-1.,0., -1/4.], [1.,0.,0., -1/4.] ],
			[ [0.,0.,-1., 1/4.], [0.,-1.,0., -1/4.], [-1.,0.,0., -1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., -1/4.], [1.,0.,0., 1/4.], [0.,0.,1., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., -1/4.], [-1.,0.,0., 1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,0.,-1., 1/4.], [0.,1.,0., -1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., -1/4.], [0.,0.,1., 1/4.], [0.,-1.,0., -1/4.] ],
			[ [0.,0.,1., -1/4.], [0.,1.,0., 1/4.], [-1.,0.,0., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,0.,-1., -1/4.], [0.,1.,0., 1/4.], [1.,0.,0., -1/4.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,1.,0., -1/4.], [1.,0.,0., 1/4.], [0.,0.,-1., -1/4.] ],
			[ [0.,-1.,0., -1/4.], [-1.,0.,0., 1/4.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,0.,1., 1/4.], [0.,1.,0., -1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,0.,-1., 1/4.], [0.,-1.,0., -1/4.] ],
			[ [0.,0.,1., -1/4.], [0.,-1.,0., 1/4.], [1.,0.,0., -1/4.] ],
			[ [0.,0.,-1., -1/4.], [0.,-1.,0., 1/4.], [-1.,0.,0., -1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,-1.,0., -1/4.], [1.,0.,0., -1/4.], [0.,0.,1., 1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., -1/4.], [-1.,0.,0., -1/4.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,0.,-1., -1/4.], [0.,1.,0., 1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., -1/4.], [0.,0.,1., -1/4.], [0.,-1.,0., 1/4.] ],
			[ [0.,0.,1., -1/4.], [0.,1.,0., -1/4.], [-1.,0.,0., 1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,0.,-1., -1/4.], [0.,1.,0., -1/4.], [1.,0.,0., 1/4.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,1.,0., -1/4.], [1.,0.,0., -1/4.], [0.,0.,-1., 1/4.] ],
			[ [0.,-1.,0., -1/4.], [-1.,0.,0., -1/4.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,0.,1., -1/4.], [0.,1.,0., 1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,0.,-1., -1/4.], [0.,-1.,0., 1/4.] ],
			[ [0.,0.,1., -1/4.], [0.,-1.,0., -1/4.], [1.,0.,0., 1/4.] ],
			[ [0.,0.,-1., -1/4.], [0.,-1.,0., -1/4.], [-1.,0.,0., 1/4.] ] ] )
		elif SpaceGroupID=='211':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,0.,-1., 0], [0.,1.,0., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,0.,1., 0], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 0], [0.,1.,0., 0], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,0.,-1., 0], [0.,1.,0., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,1., 0], [0.,1.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,-1., 0], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 0], [0.,-1.,0., 0], [1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [0.,-1.,0., 0], [-1.,0.,0., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.] ] ] )
		elif SpaceGroupID=='212':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., -1/4.], [1.,0.,0., 1/4.], [0.,0.,1., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., -1/4.], [-1.,0.,0., -1/4.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,0.,-1., -1/4.], [0.,1.,0., 1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/4.], [0.,0.,1., -1/4.], [0.,-1.,0., -1/4.] ],
			[ [0.,0.,1., 1/4.], [0.,1.,0., -1/4.], [-1.,0.,0., -1/4.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,0.,-1., -1/4.], [0.,1.,0., 1/4.], [1.,0.,0., -1/4.] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 1/4.], [1.,0.,0., -1/4.], [0.,0.,-1., -1/4.] ],
			[ [0.,-1.,0., 1/4.], [-1.,0.,0., 1/4.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,0.,1., 1/4.], [0.,1.,0., -1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,0.,-1., 1/4.], [0.,-1.,0., 1/4.] ],
			[ [0.,0.,1., -1/4.], [0.,-1.,0., -1/4.], [1.,0.,0., 1/4.] ],
			[ [0.,0.,-1., 1/4.], [0.,-1.,0., 1/4.], [-1.,0.,0., 1/4.] ] ] )
		elif SpaceGroupID=='213':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/4.], [1.,0.,0., -1/4.], [0.,0.,1., 1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/4.], [-1.,0.,0., 1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,0.,-1., 1/4.], [0.,1.,0., -1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., -1/4.], [0.,0.,1., 1/4.], [0.,-1.,0., 1/4.] ],
			[ [0.,0.,1., -1/4.], [0.,1.,0., 1/4.], [-1.,0.,0., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,0.,-1., 1/4.], [0.,1.,0., -1/4.], [1.,0.,0., 1/4.] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,1.,0., -1/4.], [1.,0.,0., 1/4.], [0.,0.,-1., 1/4.] ],
			[ [0.,-1.,0., -1/4.], [-1.,0.,0., -1/4.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,0.,1., -1/4.], [0.,1.,0., 1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,0.,-1., -1/4.], [0.,-1.,0., -1/4.] ],
			[ [0.,0.,1., 1/4.], [0.,-1.,0., 1/4.], [1.,0.,0., -1/4.] ],
			[ [0.,0.,-1., -1/4.], [0.,-1.,0., -1/4.], [-1.,0.,0., -1/4.] ] ] )
		elif SpaceGroupID=='214':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/4.], [1.,0.,0., -1/4.], [0.,0.,1., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/4.], [-1.,0.,0., 1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,0.,-1., 1/4.], [0.,1.,0., -1/4.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., -1/4.], [0.,0.,1., 1/4.], [0.,-1.,0., 1/4.] ],
			[ [0.,0.,1., -1/4.], [0.,1.,0., 1/4.], [-1.,0.,0., 1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,0.,-1., 1/4.], [0.,1.,0., -1/4.], [1.,0.,0., 1/4.] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,1.,0., -1/4.], [1.,0.,0., 1/4.], [0.,0.,-1., 1/4.] ],
			[ [0.,-1.,0., 1/4.], [-1.,0.,0., 1/4.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,0.,1., -1/4.], [0.,1.,0., 1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,0.,-1., 1/4.], [0.,-1.,0., 1/4.] ],
			[ [0.,0.,1., 1/4.], [0.,-1.,0., 1/4.], [1.,0.,0., -1/4.] ],
			[ [0.,0.,-1., 1/4.], [0.,-1.,0., 1/4.], [-1.,0.,0., 1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., -1/4.], [1.,0.,0., 1/4.], [0.,0.,1., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., -1/4.], [-1.,0.,0., -1/4.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,0.,-1., -1/4.], [0.,1.,0., 1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/4.], [0.,0.,1., -1/4.], [0.,-1.,0., -1/4.] ],
			[ [0.,0.,1., 1/4.], [0.,1.,0., -1/4.], [-1.,0.,0., -1/4.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,0.,-1., -1/4.], [0.,1.,0., 1/4.], [1.,0.,0., -1/4.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 1/4.], [1.,0.,0., -1/4.], [0.,0.,-1., -1/4.] ],
			[ [0.,-1.,0., -1/4.], [-1.,0.,0., -1/4.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,0.,1., 1/4.], [0.,1.,0., -1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,0.,-1., -1/4.], [0.,-1.,0., -1/4.] ],
			[ [0.,0.,1., -1/4.], [0.,-1.,0., -1/4.], [1.,0.,0., 1/4.] ],
			[ [0.,0.,-1., -1/4.], [0.,-1.,0., -1/4.], [-1.,0.,0., -1/4.] ] ] )
		elif SpaceGroupID=='215':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,1., 0], [0.,-1.,0., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,-1., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [0.,-1.,0., 0], [1.,0.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,0.,1., 0], [0.,-1.,0., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,0.,-1., 0], [0.,-1.,0., 0] ],
			[ [1.,0.,0., 0], [0.,0.,1., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [0.,1.,0., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [0.,1.,0., 0], [1.,0.,0., 0] ] ] )
		elif SpaceGroupID=='216':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,1., 0], [0.,-1.,0., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,-1., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [0.,-1.,0., 0], [1.,0.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,0.,1., 0], [0.,-1.,0., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,0.,-1., 0], [0.,-1.,0., 0] ],
			[ [1.,0.,0., 0], [0.,0.,1., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [0.,1.,0., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [0.,1.,0., 0], [1.,0.,0., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,0.,1., 0], [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 0], [0.,0.,1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [1.,0.,0., 0], [0.,0.,1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [0.,1.,0., 1/2.], [1.,0.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,1., 0], [0.,-1.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,-1., 0], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,-1.,0., 0], [1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,-1.,0., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,-1., 0], [0.,-1.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,1., 0], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,1.,0., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,1.,0., 0], [1.,0.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,-1.,0., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.], [1.,0.,0., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,-1.,0., 0] ],
			[ [1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,0.,1., 1/2.], [0.,1.,0., 1/2.], [1.,0.,0., 0] ] ] )
		elif SpaceGroupID=='217':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,1., 0], [0.,-1.,0., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,-1., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [0.,-1.,0., 0], [1.,0.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,0.,1., 0], [0.,-1.,0., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,0.,-1., 0], [0.,-1.,0., 0] ],
			[ [1.,0.,0., 0], [0.,0.,1., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [0.,1.,0., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [0.,1.,0., 0], [1.,0.,0., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,1.,0., 1/2.], [1.,0.,0., 1/2.] ] ] )
		elif SpaceGroupID=='218':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,1.,0., 1/2.], [1.,0.,0., 1/2.] ] ] )
		elif SpaceGroupID=='219':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,0.,1., 0], [0.,-1.,0., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,-1., 0], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [0.,-1.,0., 0], [1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,0.,1., 0], [0.,-1.,0., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,0.,-1., 0], [0.,-1.,0., 1/2.] ],
			[ [1.,0.,0., 0], [0.,0.,1., 0], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [0.,1.,0., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [0.,1.,0., 0], [1.,0.,0., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,1., 1/2.], [0.,-1.,0., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,0.,-1., 1/2.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [0.,-1.,0., 1/2.], [1.,0.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,0.,1., 0], [0.,-1.,0., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 0], [0.,0.,1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,0.,-1., 1/2.], [0.,-1.,0., 0] ],
			[ [1.,0.,0., 0], [0.,0.,1., 1/2.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [0.,1.,0., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [0.,1.,0., 1/2.], [1.,0.,0., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,1., 0], [0.,-1.,0., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,-1., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [0.,-1.,0., 0], [1.,0.,0., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,-1.,0., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,0.,-1., 0], [0.,-1.,0., 0] ],
			[ [1.,0.,0., 1/2.], [0.,0.,1., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [0.,1.,0., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,1., 1/2.], [0.,1.,0., 0], [1.,0.,0., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,1.,0., 1/2.], [1.,0.,0., 1/2.] ] ] )
		elif SpaceGroupID=='220':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/4.], [-1.,0.,0., -1/4.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/4.], [1.,0.,0., 1/4.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,0.,1., 1/4.], [0.,-1.,0., -1/4.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., -1/4.], [0.,0.,-1., 1/4.], [0.,1.,0., 1/4.] ],
			[ [0.,0.,-1., -1/4.], [0.,-1.,0., 1/4.], [1.,0.,0., 1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,0.,1., 1/4.], [0.,-1.,0., -1/4.], [-1.,0.,0., 1/4.] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., -1/4.], [-1.,0.,0., 1/4.], [0.,0.,1., 1/4.] ],
			[ [0.,1.,0., 1/4.], [1.,0.,0., 1/4.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,0.,-1., -1/4.], [0.,-1.,0., 1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,0.,1., 1/4.], [0.,1.,0., 1/4.] ],
			[ [0.,0.,-1., 1/4.], [0.,1.,0., 1/4.], [-1.,0.,0., -1/4.] ],
			[ [0.,0.,1., 1/4.], [0.,1.,0., 1/4.], [1.,0.,0., 1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., -1/4.], [-1.,0.,0., 1/4.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., -1/4.], [1.,0.,0., -1/4.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,0.,1., -1/4.], [0.,-1.,0., 1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/4.], [0.,0.,-1., -1/4.], [0.,1.,0., -1/4.] ],
			[ [0.,0.,-1., 1/4.], [0.,-1.,0., -1/4.], [1.,0.,0., -1/4.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,0.,1., -1/4.], [0.,-1.,0., 1/4.], [-1.,0.,0., -1/4.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,-1.,0., 1/4.], [-1.,0.,0., -1/4.], [0.,0.,1., -1/4.] ],
			[ [0.,1.,0., -1/4.], [1.,0.,0., -1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,0.,-1., 1/4.], [0.,-1.,0., -1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,0.,1., -1/4.], [0.,1.,0., -1/4.] ],
			[ [0.,0.,-1., -1/4.], [0.,1.,0., -1/4.], [-1.,0.,0., 1/4.] ],
			[ [0.,0.,1., -1/4.], [0.,1.,0., -1/4.], [1.,0.,0., -1/4.] ] ] )
		elif SpaceGroupID=='221':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,0.,-1., 0], [0.,1.,0., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,0.,1., 0], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 0], [0.,1.,0., 0], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,0.,-1., 0], [0.,1.,0., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,1., 0], [0.,1.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,-1., 0], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 0], [0.,-1.,0., 0], [1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [0.,-1.,0., 0], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,1., 0], [0.,-1.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,-1., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [0.,-1.,0., 0], [1.,0.,0., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,0.,1., 0], [0.,-1.,0., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,0.,-1., 0], [0.,-1.,0., 0] ],
			[ [1.,0.,0., 0], [0.,0.,1., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [0.,1.,0., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [0.,1.,0., 0], [1.,0.,0., 0] ] ] )
		elif SpaceGroupID=='222:1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,0.,-1., 0], [0.,1.,0., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,0.,1., 0], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 0], [0.,1.,0., 0], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,0.,-1., 0], [0.,1.,0., 0], [1.,0.,0., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,1., 0], [0.,1.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,-1., 0], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 0], [0.,-1.,0., 0], [1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [0.,-1.,0., 0], [-1.,0.,0., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,1.,0., 1/2.], [1.,0.,0., 1/2.] ] ] )
		elif SpaceGroupID=='222:2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,0.,-1., 1/2.], [0.,1.,0., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,0.,1., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 0], [0.,1.,0., 0], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,1.,0., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,1., 0], [0.,1.,0., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 0], [0.,-1.,0., 1/2.], [1.,0.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,1., 1/2.], [0.,-1.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,0.,-1., 0], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [0.,-1.,0., 0], [1.,0.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,-1.,0., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,-1., 0], [0.,-1.,0., 0] ],
			[ [1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [0.,1.,0., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,0.,1., 1/2.], [0.,1.,0., 1/2.], [1.,0.,0., 1/2.] ] ] )
		elif SpaceGroupID=='223':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,1.,0., 1/2.], [1.,0.,0., 1/2.] ] ] )
		elif SpaceGroupID=='224:1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,1., 0], [0.,-1.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,-1., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [0.,-1.,0., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [0.,-1.,0., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,0.,-1., 0], [0.,-1.,0., 0] ],
			[ [1.,0.,0., 0], [0.,0.,1., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [0.,1.,0., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [0.,1.,0., 0], [1.,0.,0., 0] ] ] )
		elif SpaceGroupID=='224:2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,-1., 0], [0.,1.,0., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 1/2.], [0.,1.,0., 1/2.], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,0.,-1., 0], [0.,1.,0., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,0.,-1., 0], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 1/2.], [0.,-1.,0., 0], [1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [0.,-1.,0., 0], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,1., 0], [0.,-1.,0., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.], [1.,0.,0., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,0.,1., 0], [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [1.,0.,0., 0], [0.,0.,1., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [0.,1.,0., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [0.,1.,0., 0], [1.,0.,0., 0] ] ] )
		elif SpaceGroupID=='225':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,0.,-1., 0], [0.,1.,0., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,0.,1., 0], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 0], [0.,1.,0., 0], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,0.,-1., 0], [0.,1.,0., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,1., 0], [0.,1.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,-1., 0], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 0], [0.,-1.,0., 0], [1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [0.,-1.,0., 0], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,1., 0], [0.,-1.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,-1., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [0.,-1.,0., 0], [1.,0.,0., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,0.,1., 0], [0.,-1.,0., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,0.,-1., 0], [0.,-1.,0., 0] ],
			[ [1.,0.,0., 0], [0.,0.,1., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [0.,1.,0., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [0.,1.,0., 0], [1.,0.,0., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 0], [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,0.,-1., 0], [0.,1.,0., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 0], [0.,0.,1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,0.,1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 0], [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,0.,1., 0], [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,1.,0., 0], [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [1.,0.,0., 0], [0.,0.,1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [0.,1.,0., 1/2.], [1.,0.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,-1., 0], [0.,1.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,1., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,1.,0., 0], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,1.,0., 0], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,1., 0], [0.,1.,0., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,-1., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,-1.,0., 0], [1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,-1.,0., 0], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,1., 0], [0.,-1.,0., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,-1., 0], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,-1.,0., 0], [1.,0.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,-1.,0., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,-1., 0], [0.,-1.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,1., 0], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,1.,0., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,1.,0., 0], [1.,0.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,1.,0., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 1/2.], [0.,1.,0., 1/2.], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.], [1.,0.,0., 0] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,1.,0., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.], [1.,0.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,-1.,0., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.], [1.,0.,0., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,-1.,0., 0] ],
			[ [1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,0.,1., 1/2.], [0.,1.,0., 1/2.], [1.,0.,0., 0] ] ] )
		elif SpaceGroupID=='226':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,0.,-1., 0], [0.,1.,0., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,0.,1., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 0], [0.,1.,0., 0], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,0.,-1., 0], [0.,1.,0., 0], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,0.,1., 0], [0.,1.,0., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,0.,-1., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 0], [0.,-1.,0., 0], [1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [0.,-1.,0., 0], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,0.,1., 0], [0.,-1.,0., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,-1., 0], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [0.,-1.,0., 0], [1.,0.,0., 1/2.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,0.,1., 0], [0.,-1.,0., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,0.,-1., 0], [0.,-1.,0., 1/2.] ],
			[ [1.,0.,0., 0], [0.,0.,1., 0], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [0.,1.,0., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [0.,1.,0., 0], [1.,0.,0., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,0.,-1., 1/2.], [0.,1.,0., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,0.,1., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 0], [0.,1.,0., 1/2.], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,0.,-1., 0], [0.,1.,0., 1/2.], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 0], [0.,0.,1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,1., 1/2.], [0.,1.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,-1., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 0], [0.,-1.,0., 1/2.], [1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [0.,-1.,0., 1/2.], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,1., 1/2.], [0.,-1.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,0.,-1., 1/2.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [0.,-1.,0., 1/2.], [1.,0.,0., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,0.,1., 0], [0.,-1.,0., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,1.,0., 0], [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,0.,-1., 1/2.], [0.,-1.,0., 0] ],
			[ [1.,0.,0., 0], [0.,0.,1., 1/2.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [0.,1.,0., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [0.,1.,0., 1/2.], [1.,0.,0., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,0.,-1., 0], [0.,1.,0., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,1., 0], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 1/2.], [0.,1.,0., 0], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,1.,0., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,1., 0], [0.,1.,0., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,-1., 0], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 1/2.], [0.,-1.,0., 0], [1.,0.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [0.,-1.,0., 0], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,1., 0], [0.,-1.,0., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,-1., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [0.,-1.,0., 0], [1.,0.,0., 0] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,-1.,0., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,0.,-1., 0], [0.,-1.,0., 0] ],
			[ [1.,0.,0., 1/2.], [0.,0.,1., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [0.,1.,0., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,1., 1/2.], [0.,1.,0., 0], [1.,0.,0., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,1.,0., 1/2.], [1.,0.,0., 1/2.] ] ] )
		elif SpaceGroupID=='227:1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/4.], [0.,-1.,0., 1/4.], [0.,0.,-1., 1/4.] ],
			[ [0.,-1.,0., 1/4.], [1.,0.,0., 1/4.], [0.,0.,1., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/4.], [-1.,0.,0., 1/4.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,0.,-1., 1/4.], [0.,1.,0., 1/4.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/4.], [0.,0.,1., 1/4.], [0.,-1.,0., 1/4.] ],
			[ [0.,0.,1., 1/4.], [0.,1.,0., 1/4.], [-1.,0.,0., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,0.,-1., 1/4.], [0.,1.,0., 1/4.], [1.,0.,0., 1/4.] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,1., 0], [0.,-1.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,-1., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [0.,-1.,0., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [0.,-1.,0., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 1/4.], [-1.,0.,0., 1/4.], [0.,-1.,0., 1/4.] ],
			[ [0.,-1.,0., 1/4.], [0.,0.,-1., 1/4.], [-1.,0.,0., 1/4.] ],
			[ [0.,1.,0., 1/4.], [0.,0.,1., 1/4.], [-1.,0.,0., 1/4.] ],
			[ [0.,0.,-1., 1/4.], [1.,0.,0., 1/4.], [0.,1.,0., 1/4.] ],
			[ [0.,1.,0., 1/4.], [0.,0.,-1., 1/4.], [1.,0.,0., 1/4.] ],
			[ [0.,0.,1., 1/4.], [1.,0.,0., 1/4.], [0.,-1.,0., 1/4.] ],
			[ [0.,0.,1., 1/4.], [-1.,0.,0., 1/4.], [0.,1.,0., 1/4.] ],
			[ [0.,-1.,0., 1/4.], [0.,0.,1., 1/4.], [1.,0.,0., 1/4.] ],
			[ [0.,1.,0., 1/4.], [1.,0.,0., 1/4.], [0.,0.,-1., 1/4.] ],
			[ [0.,-1.,0., 1/4.], [-1.,0.,0., 1/4.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,0.,1., 1/4.], [0.,1.,0., 1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,0.,-1., 1/4.], [0.,-1.,0., 1/4.] ],
			[ [0.,0.,1., 1/4.], [0.,-1.,0., 1/4.], [1.,0.,0., 1/4.] ],
			[ [0.,0.,-1., 1/4.], [0.,-1.,0., 1/4.], [-1.,0.,0., 1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,1.,0., 1/4.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,1.,0., 1/4.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,-1.,0., 1/4.], [0.,0.,1., 1/4.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,0.,-1., 0], [0.,-1.,0., 0] ],
			[ [1.,0.,0., 0], [0.,0.,1., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [0.,1.,0., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [0.,1.,0., 0], [1.,0.,0., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/4.], [0.,-1.,0., -1/4.], [0.,0.,-1., -1/4.] ],
			[ [0.,-1.,0., 1/4.], [1.,0.,0., -1/4.], [0.,0.,1., -1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/4.], [-1.,0.,0., -1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,0.,-1., -1/4.], [0.,1.,0., -1/4.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/4.], [0.,0.,1., -1/4.], [0.,-1.,0., -1/4.] ],
			[ [0.,0.,1., 1/4.], [0.,1.,0., -1/4.], [-1.,0.,0., -1/4.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,0.,-1., 1/4.], [0.,1.,0., -1/4.], [1.,0.,0., -1/4.] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 0], [0.,0.,1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/4.], [-1.,0.,0., -1/4.], [0.,-1.,0., -1/4.] ],
			[ [0.,-1.,0., 1/4.], [0.,0.,-1., -1/4.], [-1.,0.,0., -1/4.] ],
			[ [0.,1.,0., 1/4.], [0.,0.,1., -1/4.], [-1.,0.,0., -1/4.] ],
			[ [0.,0.,-1., 1/4.], [1.,0.,0., -1/4.], [0.,1.,0., -1/4.] ],
			[ [0.,1.,0., 1/4.], [0.,0.,-1., -1/4.], [1.,0.,0., -1/4.] ],
			[ [0.,0.,1., 1/4.], [1.,0.,0., -1/4.], [0.,-1.,0., -1/4.] ],
			[ [0.,0.,1., 1/4.], [-1.,0.,0., -1/4.], [0.,1.,0., -1/4.] ],
			[ [0.,-1.,0., 1/4.], [0.,0.,1., -1/4.], [1.,0.,0., -1/4.] ],
			[ [0.,1.,0., 1/4.], [1.,0.,0., -1/4.], [0.,0.,-1., -1/4.] ],
			[ [0.,-1.,0., 1/4.], [-1.,0.,0., -1/4.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,0.,1., -1/4.], [0.,1.,0., -1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,0.,-1., -1/4.], [0.,-1.,0., -1/4.] ],
			[ [0.,0.,1., 1/4.], [0.,-1.,0., -1/4.], [1.,0.,0., -1/4.] ],
			[ [0.,0.,-1., 1/4.], [0.,-1.,0., -1/4.], [-1.,0.,0., -1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,1.,0., -1/4.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,1.,0., -1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,-1.,0., -1/4.], [0.,0.,1., -1/4.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [1.,0.,0., 0], [0.,0.,1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [0.,1.,0., 1/2.], [1.,0.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., -1/4.], [0.,-1.,0., 1/4.], [0.,0.,-1., -1/4.] ],
			[ [0.,-1.,0., -1/4.], [1.,0.,0., 1/4.], [0.,0.,1., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., -1/4.], [-1.,0.,0., 1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,0.,-1., 1/4.], [0.,1.,0., -1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., -1/4.], [0.,0.,1., 1/4.], [0.,-1.,0., -1/4.] ],
			[ [0.,0.,1., -1/4.], [0.,1.,0., 1/4.], [-1.,0.,0., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,0.,-1., -1/4.], [0.,1.,0., 1/4.], [1.,0.,0., -1/4.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,1., 0], [0.,-1.,0., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,-1., 0], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,-1.,0., 0], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,-1.,0., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., -1/4.], [-1.,0.,0., 1/4.], [0.,-1.,0., -1/4.] ],
			[ [0.,-1.,0., -1/4.], [0.,0.,-1., 1/4.], [-1.,0.,0., -1/4.] ],
			[ [0.,1.,0., -1/4.], [0.,0.,1., 1/4.], [-1.,0.,0., -1/4.] ],
			[ [0.,0.,-1., -1/4.], [1.,0.,0., 1/4.], [0.,1.,0., -1/4.] ],
			[ [0.,1.,0., -1/4.], [0.,0.,-1., 1/4.], [1.,0.,0., -1/4.] ],
			[ [0.,0.,1., -1/4.], [1.,0.,0., 1/4.], [0.,-1.,0., -1/4.] ],
			[ [0.,0.,1., -1/4.], [-1.,0.,0., 1/4.], [0.,1.,0., -1/4.] ],
			[ [0.,-1.,0., -1/4.], [0.,0.,1., 1/4.], [1.,0.,0., -1/4.] ],
			[ [0.,1.,0., -1/4.], [1.,0.,0., 1/4.], [0.,0.,-1., -1/4.] ],
			[ [0.,-1.,0., -1/4.], [-1.,0.,0., 1/4.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,0.,1., 1/4.], [0.,1.,0., -1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,0.,-1., 1/4.], [0.,-1.,0., -1/4.] ],
			[ [0.,0.,1., -1/4.], [0.,-1.,0., 1/4.], [1.,0.,0., -1/4.] ],
			[ [0.,0.,-1., -1/4.], [0.,-1.,0., 1/4.], [-1.,0.,0., -1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,1.,0., 1/4.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,1.,0., 1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,-1.,0., 1/4.], [0.,0.,1., -1/4.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,-1., 0], [0.,-1.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,1., 0], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,1.,0., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,1.,0., 0], [1.,0.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., -1/4.], [0.,-1.,0., -1/4.], [0.,0.,-1., 1/4.] ],
			[ [0.,-1.,0., -1/4.], [1.,0.,0., -1/4.], [0.,0.,1., 1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., -1/4.], [-1.,0.,0., -1/4.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,0.,-1., -1/4.], [0.,1.,0., 1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., -1/4.], [0.,0.,1., -1/4.], [0.,-1.,0., 1/4.] ],
			[ [0.,0.,1., -1/4.], [0.,1.,0., -1/4.], [-1.,0.,0., 1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,0.,-1., -1/4.], [0.,1.,0., -1/4.], [1.,0.,0., 1/4.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,-1.,0., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.], [1.,0.,0., 0] ],
			[ [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., -1/4.], [-1.,0.,0., -1/4.], [0.,-1.,0., 1/4.] ],
			[ [0.,-1.,0., -1/4.], [0.,0.,-1., -1/4.], [-1.,0.,0., 1/4.] ],
			[ [0.,1.,0., -1/4.], [0.,0.,1., -1/4.], [-1.,0.,0., 1/4.] ],
			[ [0.,0.,-1., -1/4.], [1.,0.,0., -1/4.], [0.,1.,0., 1/4.] ],
			[ [0.,1.,0., -1/4.], [0.,0.,-1., -1/4.], [1.,0.,0., 1/4.] ],
			[ [0.,0.,1., -1/4.], [1.,0.,0., -1/4.], [0.,-1.,0., 1/4.] ],
			[ [0.,0.,1., -1/4.], [-1.,0.,0., -1/4.], [0.,1.,0., 1/4.] ],
			[ [0.,-1.,0., -1/4.], [0.,0.,1., -1/4.], [1.,0.,0., 1/4.] ],
			[ [0.,1.,0., -1/4.], [1.,0.,0., -1/4.], [0.,0.,-1., 1/4.] ],
			[ [0.,-1.,0., -1/4.], [-1.,0.,0., -1/4.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,0.,1., -1/4.], [0.,1.,0., 1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,0.,-1., -1/4.], [0.,-1.,0., 1/4.] ],
			[ [0.,0.,1., -1/4.], [0.,-1.,0., -1/4.], [1.,0.,0., 1/4.] ],
			[ [0.,0.,-1., -1/4.], [0.,-1.,0., -1/4.], [-1.,0.,0., 1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,1.,0., -1/4.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,1.,0., -1/4.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,-1.,0., -1/4.], [0.,0.,1., 1/4.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,-1.,0., 0] ],
			[ [1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,0.,1., 1/2.], [0.,1.,0., 1/2.], [1.,0.,0., 0] ] ] )
		elif SpaceGroupID=='227:2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 1/4.], [0.,0.,1., 1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,-1.,0., 1/4.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/4.], [-1.,0.,0., 0], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,0.,-1., 0], [0.,1.,0., 1/4.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/4.], [0.,0.,-1., 1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,0.,1., 1/4.], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 1/4.], [0.,1.,0., 1/4.], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 1/4.], [0.,1.,0., 0], [0.,0.,-1., 1/4.] ],
			[ [0.,0.,-1., 0], [0.,1.,0., 1/4.], [1.,0.,0., 1/4.] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 1/4.], [0.,0.,-1., 1/4.], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 1/4.], [0.,-1.,0., 1/4.] ],
			[ [0.,-1.,0., 1/4.], [0.,0.,1., 0], [-1.,0.,0., 1/4.] ],
			[ [0.,0.,-1., 1/4.], [-1.,0.,0., 1/4.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/4.], [1.,0.,0., 0], [0.,-1.,0., 1/4.] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 1/4.], [-1.,0.,0., 1/4.] ],
			[ [0.,1.,0., 1/4.], [1.,0.,0., 1/4.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,1., 1/4.], [0.,1.,0., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,0.,-1., 0], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 1/4.], [0.,-1.,0., 0], [1.,0.,0., 1/4.] ],
			[ [0.,0.,-1., 0], [0.,-1.,0., 0], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., -1/4.], [0.,0.,-1., -1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,1.,0., -1/4.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., -1/4.], [1.,0.,0., 0], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,0.,1., 0], [0.,-1.,0., -1/4.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., -1/4.], [0.,0.,1., -1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,0.,-1., -1/4.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., -1/4.], [0.,-1.,0., -1/4.], [1.,0.,0., 0] ],
			[ [1.,0.,0., -1/4.], [0.,-1.,0., 0], [0.,0.,1., -1/4.] ],
			[ [0.,0.,1., 0], [0.,-1.,0., -1/4.], [-1.,0.,0., -1/4.] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,1.,0., -1/4.], [0.,0.,1., -1/4.], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., -1/4.], [0.,1.,0., -1/4.] ],
			[ [0.,1.,0., -1/4.], [0.,0.,-1., 0], [1.,0.,0., -1/4.] ],
			[ [0.,0.,1., -1/4.], [1.,0.,0., -1/4.], [0.,-1.,0., 0] ],
			[ [0.,0.,1., -1/4.], [-1.,0.,0., 0], [0.,1.,0., -1/4.] ],
			[ [0.,-1.,0., 0], [0.,0.,1., -1/4.], [1.,0.,0., -1/4.] ],
			[ [0.,-1.,0., -1/4.], [-1.,0.,0., -1/4.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,0.,-1., -1/4.], [0.,-1.,0., -1/4.] ],
			[ [1.,0.,0., 0], [0.,0.,1., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., -1/4.], [0.,1.,0., 0], [-1.,0.,0., -1/4.] ],
			[ [0.,0.,1., 0], [0.,1.,0., 0], [1.,0.,0., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 0], [1.,0.,0., -1/4.], [0.,0.,1., -1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,-1.,0., -1/4.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/4.], [-1.,0.,0., 1/2.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,0.,-1., 1/2.], [0.,1.,0., -1/4.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., -1/4.], [0.,0.,-1., -1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,0.,1., -1/4.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 1/4.], [0.,1.,0., -1/4.], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 1/4.], [0.,1.,0., 1/2.], [0.,0.,-1., -1/4.] ],
			[ [0.,0.,-1., 0], [0.,1.,0., -1/4.], [1.,0.,0., -1/4.] ],
			[ [0.,0.,1., 0], [1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 0], [0.,0.,1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 1/4.], [0.,0.,-1., -1/4.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [-1.,0.,0., -1/4.], [0.,-1.,0., -1/4.] ],
			[ [0.,-1.,0., 1/4.], [0.,0.,1., 1/2.], [-1.,0.,0., -1/4.] ],
			[ [0.,0.,-1., 1/4.], [-1.,0.,0., -1/4.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/4.], [1.,0.,0., 1/2.], [0.,-1.,0., -1/4.] ],
			[ [0.,1.,0., 0], [0.,0.,-1., -1/4.], [-1.,0.,0., -1/4.] ],
			[ [0.,1.,0., 1/4.], [1.,0.,0., -1/4.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,0.,1., -1/4.], [0.,1.,0., -1/4.] ],
			[ [-1.,0.,0., 0], [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 1/4.], [0.,-1.,0., 1/2.], [1.,0.,0., -1/4.] ],
			[ [0.,0.,-1., 0], [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 1/4.], [0.,0.,-1., 1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,1.,0., 1/4.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., -1/4.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,0.,1., 1/2.], [0.,-1.,0., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/4.], [0.,0.,1., 1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,0.,-1., 1/4.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., -1/4.], [0.,-1.,0., 1/4.], [1.,0.,0., 1/2.] ],
			[ [1.,0.,0., -1/4.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/4.] ],
			[ [0.,0.,1., 0], [0.,-1.,0., 1/4.], [-1.,0.,0., 1/4.] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,1.,0., -1/4.], [0.,0.,1., 1/4.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 1/4.], [0.,1.,0., 1/4.] ],
			[ [0.,1.,0., -1/4.], [0.,0.,-1., 1/2.], [1.,0.,0., 1/4.] ],
			[ [0.,0.,1., -1/4.], [1.,0.,0., 1/4.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., -1/4.], [-1.,0.,0., 1/2.], [0.,1.,0., 1/4.] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 1/4.], [1.,0.,0., 1/4.] ],
			[ [0.,-1.,0., -1/4.], [-1.,0.,0., 1/4.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,0.,-1., 1/4.], [0.,-1.,0., 1/4.] ],
			[ [1.,0.,0., 0], [0.,0.,1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., -1/4.], [0.,1.,0., 1/2.], [-1.,0.,0., 1/4.] ],
			[ [0.,0.,1., 0], [0.,1.,0., 1/2.], [1.,0.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/4.], [0.,0.,1., -1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,-1.,0., 1/4.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., -1/4.], [-1.,0.,0., 0], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,0.,-1., 0], [0.,1.,0., -1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/4.], [0.,0.,-1., -1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,0.,1., 1/4.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., -1/4.], [0.,1.,0., 1/4.], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., -1/4.], [0.,1.,0., 0], [0.,0.,-1., -1/4.] ],
			[ [0.,0.,-1., 1/2.], [0.,1.,0., 1/4.], [1.,0.,0., -1/4.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., -1/4.], [0.,0.,-1., 1/4.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 1/4.], [0.,-1.,0., -1/4.] ],
			[ [0.,-1.,0., -1/4.], [0.,0.,1., 0], [-1.,0.,0., -1/4.] ],
			[ [0.,0.,-1., -1/4.], [-1.,0.,0., 1/4.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., -1/4.], [1.,0.,0., 0], [0.,-1.,0., -1/4.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 1/4.], [-1.,0.,0., -1/4.] ],
			[ [0.,1.,0., -1/4.], [1.,0.,0., 1/4.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,1., 1/4.], [0.,1.,0., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,-1., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., -1/4.], [0.,-1.,0., 0], [1.,0.,0., -1/4.] ],
			[ [0.,0.,-1., 1/2.], [0.,-1.,0., 0], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., -1/4.], [0.,0.,-1., 1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,1.,0., -1/4.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/4.], [1.,0.,0., 0], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,0.,1., 0], [0.,-1.,0., 1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., -1/4.], [0.,0.,1., 1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,0.,-1., -1/4.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/4.], [0.,-1.,0., -1/4.], [1.,0.,0., 1/2.] ],
			[ [1.,0.,0., 1/4.], [0.,-1.,0., 0], [0.,0.,1., 1/4.] ],
			[ [0.,0.,1., 1/2.], [0.,-1.,0., -1/4.], [-1.,0.,0., 1/4.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,1.,0., 1/4.], [0.,0.,1., -1/4.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., -1/4.], [0.,1.,0., 1/4.] ],
			[ [0.,1.,0., 1/4.], [0.,0.,-1., 0], [1.,0.,0., 1/4.] ],
			[ [0.,0.,1., 1/4.], [1.,0.,0., -1/4.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 1/4.], [-1.,0.,0., 0], [0.,1.,0., 1/4.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., -1/4.], [1.,0.,0., 1/4.] ],
			[ [0.,-1.,0., 1/4.], [-1.,0.,0., -1/4.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,-1., -1/4.], [0.,-1.,0., 1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,1., 0], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/4.], [0.,1.,0., 0], [-1.,0.,0., 1/4.] ],
			[ [0.,0.,1., 1/2.], [0.,1.,0., 0], [1.,0.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., -1/4.], [0.,0.,1., 1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,-1.,0., -1/4.], [0.,0.,1., 0] ],
			[ [0.,1.,0., -1/4.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,0.,-1., 1/2.], [0.,1.,0., 1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., -1/4.], [0.,0.,-1., 1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,0.,1., -1/4.], [0.,-1.,0., 0] ],
			[ [0.,0.,1., -1/4.], [0.,1.,0., -1/4.], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., -1/4.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/4.] ],
			[ [0.,0.,-1., 1/2.], [0.,1.,0., -1/4.], [1.,0.,0., 1/4.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,-1.,0., -1/4.], [0.,0.,-1., -1/4.], [1.,0.,0., 0] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., -1/4.], [0.,-1.,0., 1/4.] ],
			[ [0.,-1.,0., -1/4.], [0.,0.,1., 1/2.], [-1.,0.,0., 1/4.] ],
			[ [0.,0.,-1., -1/4.], [-1.,0.,0., -1/4.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., -1/4.], [1.,0.,0., 1/2.], [0.,-1.,0., 1/4.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., -1/4.], [-1.,0.,0., 1/4.] ],
			[ [0.,1.,0., -1/4.], [1.,0.,0., -1/4.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,1., -1/4.], [0.,1.,0., 1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,0.,1., -1/4.], [0.,-1.,0., 1/2.], [1.,0.,0., 1/4.] ],
			[ [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/4.], [0.,0.,-1., -1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,1.,0., 1/4.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 1/4.], [1.,0.,0., 1/2.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,0.,1., 1/2.], [0.,-1.,0., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/4.], [0.,0.,1., -1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,0.,-1., 1/4.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/4.], [0.,-1.,0., 1/4.], [1.,0.,0., 0] ],
			[ [1.,0.,0., 1/4.], [0.,-1.,0., 1/2.], [0.,0.,1., -1/4.] ],
			[ [0.,0.,1., 1/2.], [0.,-1.,0., 1/4.], [-1.,0.,0., -1/4.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 1/4.], [0.,0.,1., 1/4.], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 1/4.], [0.,1.,0., -1/4.] ],
			[ [0.,1.,0., 1/4.], [0.,0.,-1., 1/2.], [1.,0.,0., -1/4.] ],
			[ [0.,0.,1., 1/4.], [1.,0.,0., 1/4.], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 1/4.], [-1.,0.,0., 1/2.], [0.,1.,0., -1/4.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 1/4.], [1.,0.,0., -1/4.] ],
			[ [0.,-1.,0., 1/4.], [-1.,0.,0., 1/4.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,0.,-1., 1/4.], [0.,-1.,0., -1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/4.], [0.,1.,0., 1/2.], [-1.,0.,0., -1/4.] ],
			[ [0.,0.,1., 1/2.], [0.,1.,0., 1/2.], [1.,0.,0., 0] ] ] )
		elif SpaceGroupID=='228:1':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 1/4.], [0.,-1.,0., 1/4.], [0.,0.,-1., -1/4.] ],
			[ [0.,-1.,0., 1/4.], [1.,0.,0., 1/4.], [0.,0.,1., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/4.], [-1.,0.,0., 1/4.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,0.,-1., 1/4.], [0.,1.,0., 1/4.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/4.], [0.,0.,1., 1/4.], [0.,-1.,0., 1/4.] ],
			[ [0.,0.,1., 1/4.], [0.,1.,0., 1/4.], [-1.,0.,0., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,0.,-1., 1/4.], [0.,1.,0., 1/4.], [1.,0.,0., 1/4.] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,0.,1., 0], [0.,-1.,0., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,0.,-1., 0], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [0.,-1.,0., 0], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [0.,-1.,0., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 1/4.], [-1.,0.,0., 1/4.], [0.,-1.,0., -1/4.] ],
			[ [0.,-1.,0., 1/4.], [0.,0.,-1., 1/4.], [-1.,0.,0., -1/4.] ],
			[ [0.,1.,0., 1/4.], [0.,0.,1., 1/4.], [-1.,0.,0., -1/4.] ],
			[ [0.,0.,-1., 1/4.], [1.,0.,0., 1/4.], [0.,1.,0., -1/4.] ],
			[ [0.,1.,0., 1/4.], [0.,0.,-1., 1/4.], [1.,0.,0., -1/4.] ],
			[ [0.,0.,1., 1/4.], [1.,0.,0., 1/4.], [0.,-1.,0., -1/4.] ],
			[ [0.,0.,1., 1/4.], [-1.,0.,0., 1/4.], [0.,1.,0., -1/4.] ],
			[ [0.,-1.,0., 1/4.], [0.,0.,1., 1/4.], [1.,0.,0., -1/4.] ],
			[ [0.,1.,0., 1/4.], [1.,0.,0., 1/4.], [0.,0.,-1., 1/4.] ],
			[ [0.,-1.,0., 1/4.], [-1.,0.,0., 1/4.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,0.,1., 1/4.], [0.,1.,0., 1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,0.,-1., 1/4.], [0.,-1.,0., 1/4.] ],
			[ [0.,0.,1., 1/4.], [0.,-1.,0., 1/4.], [1.,0.,0., 1/4.] ],
			[ [0.,0.,-1., 1/4.], [0.,-1.,0., 1/4.], [-1.,0.,0., 1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,1.,0., 1/4.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,1.,0., 1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,-1.,0., 1/4.], [0.,0.,1., -1/4.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,0.,-1., 0], [0.,-1.,0., 1/2.] ],
			[ [1.,0.,0., 0], [0.,0.,1., 0], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [0.,1.,0., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [0.,1.,0., 0], [1.,0.,0., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/4.], [0.,-1.,0., -1/4.], [0.,0.,-1., 1/4.] ],
			[ [0.,-1.,0., 1/4.], [1.,0.,0., -1/4.], [0.,0.,1., -1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/4.], [-1.,0.,0., -1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,0.,-1., -1/4.], [0.,1.,0., -1/4.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/4.], [0.,0.,1., -1/4.], [0.,-1.,0., -1/4.] ],
			[ [0.,0.,1., 1/4.], [0.,1.,0., -1/4.], [-1.,0.,0., -1/4.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,0.,-1., 1/4.], [0.,1.,0., -1/4.], [1.,0.,0., -1/4.] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,1., 1/2.], [0.,-1.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,-1., 1/2.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [0.,-1.,0., 1/2.], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [0.,-1.,0., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 0], [0.,0.,1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/4.], [-1.,0.,0., -1/4.], [0.,-1.,0., 1/4.] ],
			[ [0.,-1.,0., 1/4.], [0.,0.,-1., -1/4.], [-1.,0.,0., 1/4.] ],
			[ [0.,1.,0., 1/4.], [0.,0.,1., -1/4.], [-1.,0.,0., 1/4.] ],
			[ [0.,0.,-1., 1/4.], [1.,0.,0., -1/4.], [0.,1.,0., 1/4.] ],
			[ [0.,1.,0., 1/4.], [0.,0.,-1., -1/4.], [1.,0.,0., 1/4.] ],
			[ [0.,0.,1., 1/4.], [1.,0.,0., -1/4.], [0.,-1.,0., 1/4.] ],
			[ [0.,0.,1., 1/4.], [-1.,0.,0., -1/4.], [0.,1.,0., 1/4.] ],
			[ [0.,-1.,0., 1/4.], [0.,0.,1., -1/4.], [1.,0.,0., 1/4.] ],
			[ [0.,1.,0., 1/4.], [1.,0.,0., -1/4.], [0.,0.,-1., -1/4.] ],
			[ [0.,-1.,0., 1/4.], [-1.,0.,0., -1/4.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,0.,1., -1/4.], [0.,1.,0., -1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,0.,-1., -1/4.], [0.,-1.,0., -1/4.] ],
			[ [0.,0.,1., 1/4.], [0.,-1.,0., -1/4.], [1.,0.,0., -1/4.] ],
			[ [0.,0.,-1., 1/4.], [0.,-1.,0., -1/4.], [-1.,0.,0., -1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,1.,0., -1/4.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,1.,0., -1/4.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,-1.,0., -1/4.], [0.,0.,1., 1/4.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,0.,-1., 1/2.], [0.,-1.,0., 0] ],
			[ [1.,0.,0., 0], [0.,0.,1., 1/2.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [0.,1.,0., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [0.,1.,0., 1/2.], [1.,0.,0., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., -1/4.], [0.,-1.,0., 1/4.], [0.,0.,-1., 1/4.] ],
			[ [0.,-1.,0., -1/4.], [1.,0.,0., 1/4.], [0.,0.,1., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., -1/4.], [-1.,0.,0., 1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,0.,-1., 1/4.], [0.,1.,0., -1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., -1/4.], [0.,0.,1., 1/4.], [0.,-1.,0., -1/4.] ],
			[ [0.,0.,1., -1/4.], [0.,1.,0., 1/4.], [-1.,0.,0., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,0.,-1., -1/4.], [0.,1.,0., 1/4.], [1.,0.,0., -1/4.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,1., 0], [0.,-1.,0., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,-1., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [0.,-1.,0., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 1/2.], [0.,-1.,0., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., -1/4.], [-1.,0.,0., 1/4.], [0.,-1.,0., 1/4.] ],
			[ [0.,-1.,0., -1/4.], [0.,0.,-1., 1/4.], [-1.,0.,0., 1/4.] ],
			[ [0.,1.,0., -1/4.], [0.,0.,1., 1/4.], [-1.,0.,0., 1/4.] ],
			[ [0.,0.,-1., -1/4.], [1.,0.,0., 1/4.], [0.,1.,0., 1/4.] ],
			[ [0.,1.,0., -1/4.], [0.,0.,-1., 1/4.], [1.,0.,0., 1/4.] ],
			[ [0.,0.,1., -1/4.], [1.,0.,0., 1/4.], [0.,-1.,0., 1/4.] ],
			[ [0.,0.,1., -1/4.], [-1.,0.,0., 1/4.], [0.,1.,0., 1/4.] ],
			[ [0.,-1.,0., -1/4.], [0.,0.,1., 1/4.], [1.,0.,0., 1/4.] ],
			[ [0.,1.,0., -1/4.], [1.,0.,0., 1/4.], [0.,0.,-1., -1/4.] ],
			[ [0.,-1.,0., -1/4.], [-1.,0.,0., 1/4.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,0.,1., 1/4.], [0.,1.,0., -1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,0.,-1., 1/4.], [0.,-1.,0., -1/4.] ],
			[ [0.,0.,1., -1/4.], [0.,-1.,0., 1/4.], [1.,0.,0., -1/4.] ],
			[ [0.,0.,-1., -1/4.], [0.,-1.,0., 1/4.], [-1.,0.,0., -1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,1.,0., 1/4.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,1.,0., 1/4.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,-1.,0., 1/4.], [0.,0.,1., 1/4.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,0.,-1., 0], [0.,-1.,0., 0] ],
			[ [1.,0.,0., 1/2.], [0.,0.,1., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [0.,1.,0., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,1., 1/2.], [0.,1.,0., 0], [1.,0.,0., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., -1/4.], [0.,-1.,0., -1/4.], [0.,0.,-1., -1/4.] ],
			[ [0.,-1.,0., -1/4.], [1.,0.,0., -1/4.], [0.,0.,1., 1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., -1/4.], [-1.,0.,0., -1/4.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,0.,-1., -1/4.], [0.,1.,0., 1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., -1/4.], [0.,0.,1., -1/4.], [0.,-1.,0., 1/4.] ],
			[ [0.,0.,1., -1/4.], [0.,1.,0., -1/4.], [-1.,0.,0., 1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,0.,-1., -1/4.], [0.,1.,0., -1/4.], [1.,0.,0., 1/4.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., -1/4.], [-1.,0.,0., -1/4.], [0.,-1.,0., -1/4.] ],
			[ [0.,-1.,0., -1/4.], [0.,0.,-1., -1/4.], [-1.,0.,0., -1/4.] ],
			[ [0.,1.,0., -1/4.], [0.,0.,1., -1/4.], [-1.,0.,0., -1/4.] ],
			[ [0.,0.,-1., -1/4.], [1.,0.,0., -1/4.], [0.,1.,0., -1/4.] ],
			[ [0.,1.,0., -1/4.], [0.,0.,-1., -1/4.], [1.,0.,0., -1/4.] ],
			[ [0.,0.,1., -1/4.], [1.,0.,0., -1/4.], [0.,-1.,0., -1/4.] ],
			[ [0.,0.,1., -1/4.], [-1.,0.,0., -1/4.], [0.,1.,0., -1/4.] ],
			[ [0.,-1.,0., -1/4.], [0.,0.,1., -1/4.], [1.,0.,0., -1/4.] ],
			[ [0.,1.,0., -1/4.], [1.,0.,0., -1/4.], [0.,0.,-1., 1/4.] ],
			[ [0.,-1.,0., -1/4.], [-1.,0.,0., -1/4.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,0.,1., -1/4.], [0.,1.,0., 1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,0.,-1., -1/4.], [0.,-1.,0., 1/4.] ],
			[ [0.,0.,1., -1/4.], [0.,-1.,0., -1/4.], [1.,0.,0., 1/4.] ],
			[ [0.,0.,-1., -1/4.], [0.,-1.,0., -1/4.], [-1.,0.,0., 1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,1.,0., -1/4.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,1.,0., -1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,-1.,0., -1/4.], [0.,0.,1., -1/4.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,1.,0., 1/2.], [1.,0.,0., 1/2.] ] ] )
		elif SpaceGroupID=='228:2':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 1/4.], [0.,0.,1., -1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,-1.,0., 1/4.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/4.], [-1.,0.,0., 0], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,0.,-1., 0], [0.,1.,0., -1/4.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/4.], [0.,0.,-1., 1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,0.,1., -1/4.], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 1/4.], [0.,1.,0., -1/4.], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 1/4.], [0.,1.,0., 0], [0.,0.,-1., 1/4.] ],
			[ [0.,0.,-1., 0], [0.,1.,0., 1/4.], [1.,0.,0., -1/4.] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 1/4.], [0.,0.,-1., 1/4.], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 1/4.], [0.,-1.,0., 1/4.] ],
			[ [0.,-1.,0., 1/4.], [0.,0.,1., 0], [-1.,0.,0., 1/4.] ],
			[ [0.,0.,-1., 1/4.], [-1.,0.,0., 1/4.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/4.], [1.,0.,0., 0], [0.,-1.,0., 1/4.] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 1/4.], [-1.,0.,0., 1/4.] ],
			[ [0.,1.,0., 1/4.], [1.,0.,0., -1/4.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,0.,1., 1/4.], [0.,1.,0., -1/4.] ],
			[ [-1.,0.,0., 0], [0.,0.,-1., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 1/4.], [0.,-1.,0., 0], [1.,0.,0., -1/4.] ],
			[ [0.,0.,-1., 0], [0.,-1.,0., 0], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., -1/4.], [0.,0.,-1., 1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,1.,0., -1/4.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., -1/4.], [1.,0.,0., 0], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,0.,1., 0], [0.,-1.,0., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., -1/4.], [0.,0.,1., -1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,0.,-1., 1/4.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., -1/4.], [0.,-1.,0., 1/4.], [1.,0.,0., 0] ],
			[ [1.,0.,0., -1/4.], [0.,-1.,0., 0], [0.,0.,1., -1/4.] ],
			[ [0.,0.,1., 0], [0.,-1.,0., -1/4.], [-1.,0.,0., 1/4.] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,1.,0., -1/4.], [0.,0.,1., -1/4.], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., -1/4.], [0.,1.,0., -1/4.] ],
			[ [0.,1.,0., -1/4.], [0.,0.,-1., 0], [1.,0.,0., -1/4.] ],
			[ [0.,0.,1., -1/4.], [1.,0.,0., -1/4.], [0.,-1.,0., 0] ],
			[ [0.,0.,1., -1/4.], [-1.,0.,0., 0], [0.,1.,0., -1/4.] ],
			[ [0.,-1.,0., 0], [0.,0.,1., -1/4.], [1.,0.,0., -1/4.] ],
			[ [0.,-1.,0., -1/4.], [-1.,0.,0., 1/4.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 0], [0.,0.,-1., -1/4.], [0.,-1.,0., 1/4.] ],
			[ [1.,0.,0., 0], [0.,0.,1., 0], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., -1/4.], [0.,1.,0., 0], [-1.,0.,0., 1/4.] ],
			[ [0.,0.,1., 0], [0.,1.,0., 0], [1.,0.,0., 1/2.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 0], [1.,0.,0., -1/4.], [0.,0.,1., 1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,-1.,0., -1/4.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/4.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,0.,-1., 1/2.], [0.,1.,0., 1/4.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., -1/4.], [0.,0.,-1., -1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,0.,1., 1/4.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 1/4.], [0.,1.,0., 1/4.], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 1/4.], [0.,1.,0., 1/2.], [0.,0.,-1., -1/4.] ],
			[ [0.,0.,-1., 0], [0.,1.,0., -1/4.], [1.,0.,0., 1/4.] ],
			[ [0.,0.,1., 0], [1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 0], [0.,0.,1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 1/4.], [0.,0.,-1., -1/4.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 0], [-1.,0.,0., -1/4.], [0.,-1.,0., -1/4.] ],
			[ [0.,-1.,0., 1/4.], [0.,0.,1., 1/2.], [-1.,0.,0., -1/4.] ],
			[ [0.,0.,-1., 1/4.], [-1.,0.,0., -1/4.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/4.], [1.,0.,0., 1/2.], [0.,-1.,0., -1/4.] ],
			[ [0.,1.,0., 0], [0.,0.,-1., -1/4.], [-1.,0.,0., -1/4.] ],
			[ [0.,1.,0., 1/4.], [1.,0.,0., 1/4.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,1., -1/4.], [0.,1.,0., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,0.,-1., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 1/4.], [0.,-1.,0., 1/2.], [1.,0.,0., 1/4.] ],
			[ [0.,0.,-1., 0], [0.,-1.,0., 1/2.], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 1/4.], [0.,0.,-1., -1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,1.,0., 1/4.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., -1/4.], [1.,0.,0., 1/2.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,0.,1., 1/2.], [0.,-1.,0., -1/4.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/4.], [0.,0.,1., 1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,0.,-1., -1/4.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., -1/4.], [0.,-1.,0., -1/4.], [1.,0.,0., 1/2.] ],
			[ [1.,0.,0., -1/4.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/4.] ],
			[ [0.,0.,1., 0], [0.,-1.,0., 1/4.], [-1.,0.,0., -1/4.] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,1.,0., -1/4.], [0.,0.,1., 1/4.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 1/4.], [0.,1.,0., 1/4.] ],
			[ [0.,1.,0., -1/4.], [0.,0.,-1., 1/2.], [1.,0.,0., 1/4.] ],
			[ [0.,0.,1., -1/4.], [1.,0.,0., 1/4.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., -1/4.], [-1.,0.,0., 1/2.], [0.,1.,0., 1/4.] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 1/4.], [1.,0.,0., 1/4.] ],
			[ [0.,-1.,0., -1/4.], [-1.,0.,0., -1/4.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 0], [1.,0.,0., 1/2.], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,0.,-1., 1/4.], [0.,-1.,0., -1/4.] ],
			[ [1.,0.,0., 0], [0.,0.,1., 1/2.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., -1/4.], [0.,1.,0., 1/2.], [-1.,0.,0., -1/4.] ],
			[ [0.,0.,1., 0], [0.,1.,0., 1/2.], [1.,0.,0., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/4.], [0.,0.,1., 1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,-1.,0., 1/4.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., -1/4.], [-1.,0.,0., 0], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,0.,-1., 0], [0.,1.,0., 1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/4.], [0.,0.,-1., -1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,0.,1., -1/4.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., -1/4.], [0.,1.,0., -1/4.], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., -1/4.], [0.,1.,0., 0], [0.,0.,-1., -1/4.] ],
			[ [0.,0.,-1., 1/2.], [0.,1.,0., 1/4.], [1.,0.,0., 1/4.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., -1/4.], [0.,0.,-1., 1/4.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 1/4.], [0.,-1.,0., -1/4.] ],
			[ [0.,-1.,0., -1/4.], [0.,0.,1., 0], [-1.,0.,0., -1/4.] ],
			[ [0.,0.,-1., -1/4.], [-1.,0.,0., 1/4.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., -1/4.], [1.,0.,0., 0], [0.,-1.,0., -1/4.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 1/4.], [-1.,0.,0., -1/4.] ],
			[ [0.,1.,0., -1/4.], [1.,0.,0., -1/4.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,1., 1/4.], [0.,1.,0., 1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,-1., 0], [0.,-1.,0., 0] ],
			[ [0.,0.,1., -1/4.], [0.,-1.,0., 0], [1.,0.,0., 1/4.] ],
			[ [0.,0.,-1., 1/2.], [0.,-1.,0., 0], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., -1/4.], [0.,0.,-1., -1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,1.,0., -1/4.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/4.], [1.,0.,0., 0], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,0.,1., 0], [0.,-1.,0., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., -1/4.], [0.,0.,1., 1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,0.,-1., 1/4.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/4.], [0.,-1.,0., 1/4.], [1.,0.,0., 1/2.] ],
			[ [1.,0.,0., 1/4.], [0.,-1.,0., 0], [0.,0.,1., 1/4.] ],
			[ [0.,0.,1., 1/2.], [0.,-1.,0., -1/4.], [-1.,0.,0., -1/4.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,1.,0., 1/4.], [0.,0.,1., -1/4.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., -1/4.], [0.,1.,0., 1/4.] ],
			[ [0.,1.,0., 1/4.], [0.,0.,-1., 0], [1.,0.,0., 1/4.] ],
			[ [0.,0.,1., 1/4.], [1.,0.,0., -1/4.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 1/4.], [-1.,0.,0., 0], [0.,1.,0., 1/4.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., -1/4.], [1.,0.,0., 1/4.] ],
			[ [0.,-1.,0., 1/4.], [-1.,0.,0., 1/4.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 1/2.], [0.,0.,-1., -1/4.], [0.,-1.,0., -1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,1., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/4.], [0.,1.,0., 0], [-1.,0.,0., -1/4.] ],
			[ [0.,0.,1., 1/2.], [0.,1.,0., 0], [1.,0.,0., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., -1/4.], [0.,0.,1., -1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,-1.,0., -1/4.], [0.,0.,1., 0] ],
			[ [0.,1.,0., -1/4.], [-1.,0.,0., 1/2.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,0.,-1., 1/2.], [0.,1.,0., -1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., -1/4.], [0.,0.,-1., 1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,0.,1., 1/4.], [0.,-1.,0., 0] ],
			[ [0.,0.,1., -1/4.], [0.,1.,0., 1/4.], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., -1/4.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/4.] ],
			[ [0.,0.,-1., 1/2.], [0.,1.,0., -1/4.], [1.,0.,0., -1/4.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,-1.,0., -1/4.], [0.,0.,-1., -1/4.], [1.,0.,0., 0] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., -1/4.], [0.,-1.,0., 1/4.] ],
			[ [0.,-1.,0., -1/4.], [0.,0.,1., 1/2.], [-1.,0.,0., 1/4.] ],
			[ [0.,0.,-1., -1/4.], [-1.,0.,0., -1/4.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., -1/4.], [1.,0.,0., 1/2.], [0.,-1.,0., 1/4.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., -1/4.], [-1.,0.,0., 1/4.] ],
			[ [0.,1.,0., -1/4.], [1.,0.,0., 1/4.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,1., -1/4.], [0.,1.,0., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., -1/4.], [0.,-1.,0., 1/2.], [1.,0.,0., -1/4.] ],
			[ [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/4.], [0.,0.,-1., 1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,1.,0., 1/4.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 1/4.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,0.,1., 1/2.], [0.,-1.,0., 1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/4.], [0.,0.,1., -1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,0.,-1., -1/4.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/4.], [0.,-1.,0., -1/4.], [1.,0.,0., 0] ],
			[ [1.,0.,0., 1/4.], [0.,-1.,0., 1/2.], [0.,0.,1., -1/4.] ],
			[ [0.,0.,1., 1/2.], [0.,-1.,0., 1/4.], [-1.,0.,0., 1/4.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 1/4.], [0.,0.,1., 1/4.], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 1/4.], [0.,1.,0., -1/4.] ],
			[ [0.,1.,0., 1/4.], [0.,0.,-1., 1/2.], [1.,0.,0., -1/4.] ],
			[ [0.,0.,1., 1/4.], [1.,0.,0., 1/4.], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 1/4.], [-1.,0.,0., 1/2.], [0.,1.,0., -1/4.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 1/4.], [1.,0.,0., -1/4.] ],
			[ [0.,-1.,0., 1/4.], [-1.,0.,0., -1/4.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,-1., 1/4.], [0.,-1.,0., 1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/4.], [0.,1.,0., 1/2.], [-1.,0.,0., 1/4.] ],
			[ [0.,0.,1., 1/2.], [0.,1.,0., 1/2.], [1.,0.,0., 1/2.] ] ] )
		elif SpaceGroupID=='229':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,0.,-1., 0], [0.,1.,0., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,0.,1., 0], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 0], [0.,1.,0., 0], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,0.,-1., 0], [0.,1.,0., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,1., 0], [0.,1.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,-1., 0], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 0], [0.,-1.,0., 0], [1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [0.,-1.,0., 0], [-1.,0.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., 0], [-1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., 0], [1.,0.,0., 0], [0.,0.,-1., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,1., 0], [0.,-1.,0., 0] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [-1.,0.,0., 0], [0.,0.,-1., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [0.,-1.,0., 0], [1.,0.,0., 0] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,0.,1., 0], [0.,-1.,0., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [-1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [0.,1.,0., 0], [1.,0.,0., 0], [0.,0.,1., 0] ],
			[ [1.,0.,0., 0], [0.,0.,-1., 0], [0.,-1.,0., 0] ],
			[ [1.,0.,0., 0], [0.,0.,1., 0], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 0], [0.,1.,0., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [0.,1.,0., 0], [1.,0.,0., 0] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.], [1.,0.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [-1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., 1/2.], [1.,0.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,-1., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [1.,0.,0., 1/2.], [0.,0.,1., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [0.,1.,0., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [0.,1.,0., 1/2.], [1.,0.,0., 1/2.] ] ] )
		elif SpaceGroupID=='230':
			equivXYZ1 = np.array( [ [ [1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,-1.,0., 1/4.], [1.,0.,0., -1/4.], [0.,0.,1., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [0.,1.,0., 1/4.], [-1.,0.,0., 1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,0.,-1., 1/4.], [0.,1.,0., -1/4.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [1.,0.,0., -1/4.], [0.,0.,1., 1/4.], [0.,-1.,0., 1/4.] ],
			[ [0.,0.,1., -1/4.], [0.,1.,0., 1/4.], [-1.,0.,0., 1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,0.,-1., 1/4.], [0.,1.,0., -1/4.], [1.,0.,0., 1/4.] ],
			[ [0.,0.,1., 0], [1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 0], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,1.,0., -1/4.], [1.,0.,0., 1/4.], [0.,0.,-1., 1/4.] ],
			[ [0.,-1.,0., 1/4.], [-1.,0.,0., 1/4.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,0.,1., -1/4.], [0.,1.,0., 1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,0.,-1., 1/4.], [0.,-1.,0., 1/4.] ],
			[ [0.,0.,1., 1/4.], [0.,-1.,0., 1/4.], [1.,0.,0., -1/4.] ],
			[ [0.,0.,-1., 1/4.], [0.,-1.,0., 1/4.], [-1.,0.,0., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,-1.,0., 0], [0.,0.,-1., 0] ],
			[ [0.,1.,0., -1/4.], [-1.,0.,0., 1/4.], [0.,0.,-1., -1/4.] ],
			[ [1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [0.,-1.,0., -1/4.], [1.,0.,0., -1/4.], [0.,0.,-1., 1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,0.,1., -1/4.], [0.,-1.,0., 1/4.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [-1.,0.,0., 1/4.], [0.,0.,-1., -1/4.], [0.,1.,0., -1/4.] ],
			[ [0.,0.,-1., 1/4.], [0.,-1.,0., -1/4.], [1.,0.,0., -1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 0] ],
			[ [0.,0.,1., -1/4.], [0.,-1.,0., 1/4.], [-1.,0.,0., -1/4.] ],
			[ [0.,0.,-1., 0], [-1.,0.,0., 0], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,-1., 0], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 0], [1.,0.,0., 0] ],
			[ [0.,0.,1., 0], [1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 0], [0.,1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 1/4.], [-1.,0.,0., -1/4.], [0.,0.,1., -1/4.] ],
			[ [0.,1.,0., -1/4.], [1.,0.,0., -1/4.], [0.,0.,1., -1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,0.,-1., 1/4.], [0.,-1.,0., -1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,0.,1., -1/4.], [0.,1.,0., -1/4.] ],
			[ [0.,0.,-1., -1/4.], [0.,1.,0., -1/4.], [-1.,0.,0., 1/4.] ],
			[ [0.,0.,1., -1/4.], [0.,1.,0., -1/4.], [1.,0.,0., -1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,-1.,0., -1/4.], [1.,0.,0., 1/4.], [0.,0.,1., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 0], [0.,0.,1., 1/2.] ],
			[ [0.,1.,0., -1/4.], [-1.,0.,0., -1/4.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., -1/4.], [0.,0.,-1., -1/4.], [0.,1.,0., 1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 0] ],
			[ [1.,0.,0., 1/4.], [0.,0.,1., -1/4.], [0.,-1.,0., -1/4.] ],
			[ [0.,0.,1., 1/4.], [0.,1.,0., -1/4.], [-1.,0.,0., -1/4.] ],
			[ [-1.,0.,0., 0], [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,0.,-1., -1/4.], [0.,1.,0., 1/4.], [1.,0.,0., -1/4.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 0], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 0] ],
			[ [0.,-1.,0., 0], [0.,0.,1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 0], [0.,1.,0., 1/2.] ],
			[ [0.,0.,-1., 0], [1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 0] ],
			[ [0.,1.,0., 1/4.], [1.,0.,0., -1/4.], [0.,0.,-1., -1/4.] ],
			[ [0.,-1.,0., -1/4.], [-1.,0.,0., -1/4.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,0.,1., 1/4.], [0.,1.,0., -1/4.] ],
			[ [-1.,0.,0., -1/4.], [0.,0.,-1., -1/4.], [0.,-1.,0., -1/4.] ],
			[ [0.,0.,1., -1/4.], [0.,-1.,0., -1/4.], [1.,0.,0., 1/4.] ],
			[ [0.,0.,-1., -1/4.], [0.,-1.,0., -1/4.], [-1.,0.,0., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.] ],
			[ [0.,1.,0., 1/4.], [-1.,0.,0., -1/4.], [0.,0.,-1., 1/4.] ],
			[ [1.,0.,0., 1/2.], [0.,1.,0., 0], [0.,0.,-1., 1/2.] ],
			[ [0.,-1.,0., 1/4.], [1.,0.,0., 1/4.], [0.,0.,-1., -1/4.] ],
			[ [-1.,0.,0., 1/4.], [0.,0.,1., 1/4.], [0.,-1.,0., -1/4.] ],
			[ [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.], [0.,0.,1., 0] ],
			[ [-1.,0.,0., -1/4.], [0.,0.,-1., 1/4.], [0.,1.,0., 1/4.] ],
			[ [0.,0.,-1., -1/4.], [0.,-1.,0., 1/4.], [1.,0.,0., 1/4.] ],
			[ [1.,0.,0., 0], [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.] ],
			[ [0.,0.,1., 1/4.], [0.,-1.,0., -1/4.], [-1.,0.,0., 1/4.] ],
			[ [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.], [0.,-1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,-1., 1/2.], [-1.,0.,0., 1/2.] ],
			[ [0.,1.,0., 1/2.], [0.,0.,1., 0], [-1.,0.,0., 1/2.] ],
			[ [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.], [0.,1.,0., 0] ],
			[ [0.,1.,0., 0], [0.,0.,-1., 1/2.], [1.,0.,0., 1/2.] ],
			[ [0.,0.,1., 1/2.], [1.,0.,0., 0], [0.,-1.,0., 1/2.] ],
			[ [0.,0.,1., 0], [-1.,0.,0., 1/2.], [0.,1.,0., 1/2.] ],
			[ [0.,-1.,0., 1/2.], [0.,0.,1., 1/2.], [1.,0.,0., 0] ],
			[ [0.,-1.,0., -1/4.], [-1.,0.,0., 1/4.], [0.,0.,1., 1/4.] ],
			[ [0.,1.,0., 1/4.], [1.,0.,0., 1/4.], [0.,0.,1., 1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,0.,-1., -1/4.], [0.,-1.,0., 1/4.] ],
			[ [1.,0.,0., 1/4.], [0.,0.,1., 1/4.], [0.,1.,0., 1/4.] ],
			[ [0.,0.,-1., 1/4.], [0.,1.,0., 1/4.], [-1.,0.,0., -1/4.] ],
			[ [0.,0.,1., 1/4.], [0.,1.,0., 1/4.], [1.,0.,0., 1/4.] ] ] )
		else:
			equivXYZ1 = None
			raise ValueError('INVALID SpaceGroupID, %r (type=%s) is not a valid id' % (SpaceGroupID,type(SpaceGroupID)))

		return equivXYZ1



def optionalNumbersDiffer(a,b,tol):
	"""
	returns True if a and b differ
	returns False if neither is a number, that is the optional part
	"""
	anum = isinstance(a, (int, long, float))		# a is a number you can test
	bnum = isinstance(b, (int, long, float))		# b is a number you can test
	if (not anum) and (not bnum): return False		# neither is a number so these are equal
	elif anum != bnum: return True					# one is a number, the other is not, differ
	return (abs(a - b) > tol)						# differ if not equal




if __name__ == '__main__':
	"""
	Main function for LatticeBase.py.

	Test cases for LatticeBase2D & LatticeBase3D class to verify correct behavior.
	"""
	from JZTutil import JZTtesting

	def test_SymString2IDs(LB,id,type, length, bad=False):
		try:
			l = LB.SymString2IDs(id,type)
			ll = len(l)
		except:
			if not bad: raise
			ll = -1

		if length == ll and ll>=0:
			print ('     SymString2IDs("%s", %g) = %r' % (id,type, l))
			return False
		elif bad and ll<0:
			print ('     SymString2IDs("%s", %g) is supposed to raise an exception' % (id,type))
			return False
		elif bad:
			print ('     SymString2IDs("%s", %g) = %r,  Should have %r elements in the list, this is supposed to fail' % (id,type, l, length))
			return False
		print ('ERR  SymString2IDs("%s", %g) = %r   there should be %r elements in the list' % (id,type, l, ll))
		return True

	def test_FindWyckoffSymbol3D(LB, SGid, x0,y0,z0, wy,mu, bad=False):
		"""
		wy is the correct Wyckoff letter
		mu is the correct multiplitity
		if bad is True, then this shold fail
		"""
		try:	(symbol,mult,siteSym) = LB.FindWyckoffSymbol1(SGid,x0,y0,z0)
		except:
			if not bad: raise
			mult = -1
			symbol = siteSym =''

		if symbol == wy and mu == mult:			# correct
			print ('     Find1(SG="%s", %g,%g,%g) --> Wyckoff = "%s",  mult = %g,  siteSym = "%s"  OK' % (SGid,x0,y0,z0,symbol,mult,siteSym))
			return False
		elif bad and mult<0:
			print ('     Find1(SG="%s", %g,%g,%g) is supposed to raise an exception' % (SGid,x0,y0,z0))
			return False
		elif bad:
			print ('     Find1(SG="%s", %g,%g,%g) --> Wyckoff = "%s",  mult = %g,  Should have  Wyckoff = "%s",  mult = %g,  this is supposed to fail' % (SGid,x0,y0,z0,symbol,mult,wy,mu))
			return False

		print ('ERR  Find1(SG="%s", %g,%g,%g) --> Wyckoff = "%s",  mult = %g,  Should have  Wyckoff = "%s",  mult = %g' % (SGid,x0,y0,z0,symbol,mult,wy,mu))
		return True

	def test_ForceFractionalToWyckoff3D(LB, SG, symbol,x0,y0,z0, desired, bad=False):
		try:	(x,y,z) = LB.ForceFractionalToWyckoff(SG,symbol,x0,y0,z0)
		except:
			if not bad: raise
			x = float('nan')
			z = y = x

		if x==desired[0] and y==desired[1] and z==desired[2]:			# correct
			print ('     %r, Wyckoff="%s",   {%g, %g, %g} --> {%g, %g, %g}' % (SG,symbol,x0,y0,z0, x,y,z))
			return False
		elif bad and math.isnan(x):
			print ('     %r, Wyckoff="%s",   {%g, %g, %g}  is supposed to raise an exception' % (SG,x0,y0,z0))
			return False
		elif bad:
			print ('     %r, Wyckoff="%s",   {%g, %g, %g} --> {%g, %g, %g},  Should have been %r, this is supposed to fail' % (SG,symbol,x0,y0,z0, x,y,z, desired))
			return False

		print ('ERR  %r, Wyckoff="%s",   {%g, %g, %g} --> {%g, %g, %g},  Should have been %r' % (SG,symbol,x0,y0,z0, x,y,z, desired))
		return True

	def test_getHMboth(LB, id, bad=False):
		result = LB.getHMboth(id)
		failed = result is None
		err = False
		if failed and bad==True:	print ('getHMboth(%r) should fail, the id must be a complete and valid string' % (id,))
		else:						print ('%r  ->  "%s"' % (id,result))
		if failed and bad == False: err = True
		return err

	def test_SetSymmetryOperations(LB, id, bad=False):
		print (' ')
		err = False
		try:
			result = LB.SetSymmetryOperations(id)
			print ('SetSymmetryOperations(%r) -->\n%s' % (id,result))
		except:
			if bad: print ('LB.SetSymmetryOperations(%r), should fail' % (id,))
			else:
				err = True
				print ('FAILED: SetSymmetryOperations(%r)' % (id,))
		return err

	def test_SetCBMmatrix(LB, id, bad=False):
		print (' ')
		err = False
		try:
			CBM = LB.GetSettingTransForm(id)
			print ('GetSettingTransForm(%r) -->\n%s' % (id,CBM))
		except:
			if bad:
				print ('LB.GetSettingTransForm(%r), should fail' % (id,))
				return err
			else:
				err = True
				print ('FAILED: GetSettingTransForm(%r)' % (id,))
		try:
			InvCBM = np.linalg.inv(CBM)			# inverse of the (4,4) CBM matrix
			print ('Inv(CBM) -->\n%s' % (InvCBM,))
		except:
			err = True
			print ('FAILED: GetSettingTransForm(%r),  CBM matrix is SINGULAR' % (id,))

		return err

	def test_equal_not_equal(a1,a2, expected):
		isEq = a1 == a2
		if expected == isEq:
			print ('     (%s == %s) = %r    %s' % (a1.label,a2.label,isEq,a1._neqStr))
			err = False
		else:
			print ('Err: (%s == %s) = %r    %s' % (a1.label,a2.label,isEq,a1._neqStr))
			err = True
		return err

	def test_FindWyckoffSymbol2D(LB, SGid, x0,y0, wy,mu, bad=False):
		"""
		wy is the correct Wyckoff letter
		mu is the correct multiplitity
		if bad is True, then this shold fail
		"""
		try:
			(symbol,mult,siteSym) = LB.FindWyckoffSymbol1(SGid,x0,y0)
		except:
			if not bad: raise
			mult = -1
			symbol = siteSym = ''

		if symbol == wy and mu == mult:			# correct
			print ('     Find1(SG="%s", %g,%g) --> Wyckoff = "%s",  mult = %g,  siteSym = "%s"  OK' % (SGid,x0,y0,symbol,mult,siteSym))
			return False
		elif bad and mult<0:
			print ('     Find1(SG="%s", %g,%g) is supposed to raise an exception' % (SGid,x0,y0))
			return False
		elif bad:
			print ('     Find1(SG="%s", %g,%g) --> Wyckoff = "%s",  mult = %g,  Should have  Wyckoff = "%s",  mult = %g,  this is supposed to fail' % (SGid,x0,y0,symbol,mult,wy,mu))
			return False

		print ('ERR  Find1(SG="%s", %g,%g) --> Wyckoff = "%s",  mult = %g,  Should have  Wyckoff = "%s",  mult = %g' % (SGid,x0,y0,symbol,mult,wy,mu))
		return True

	def test_ForceFractionalToWyckoff2D(LB, SG, symbol,x0,y0, desired, bad=False):
		try:	(x,y) = LB.ForceFractionalToWyckoff(SG,symbol,x0,y0)
		except:
			if not bad: raise
			x = float('nan')
			y = x

		if x==desired[0] and y==desired[1]:		# correct
			print ('     #%d, Wyckoff="%s",   {%g, %g} --> {%g, %g}' % (SG,symbol,x0,y0, x,y))
			return False
		elif bad and math.isnan(x):
			print ('     #%d, Wyckoff="%s",   {%g, %g}  is supposed to raise an exception' % (SG,symbol,x0,y0))
			return False
		elif bad:
			print ('     #%d, Wyckoff="%s",   {%g, %g} --> {%g, %g},  Should have been %r, this is supposed to fail' % (SG,symbol,x0,y0, x,y, desired))
			return False

		print ('ERR  #%d, Wyckoff="%s",   {%g, %g} --> {%g, %g},  Should have been %r' % (SG,symbol,x0,y0, x,y, desired))
		return True


	testing = JZTtesting(__file__)

	LB3D = LatticeBase3D()

	if testing.doit("check finding SpaceGroupID's from all or part of a symmetry string"):	#  2**0 = 1
		err = 	test_SymString2IDs(LB3D,'P63*',1, 7)
		err |= 	test_SymString2IDs(LB3D,'P63*',-1, 7)
		err |= 	test_SymString2IDs(LB3D,'P63*2',-1, 1)
		err |= 	test_SymString2IDs(LB3D,'P6*',-1, 27)
		err |= 	test_SymString2IDs(LB3D,'*2b*',1, 4)
		err |= 	test_SymString2IDs(LB3D,'*2b*',2, 4)
		err |= 	test_SymString2IDs(LB3D,'*2b*',8, 0)
		err |= 	test_SymString2IDs(LB3D,'*2b*',16, 4)
		err |= 	test_SymString2IDs(LB3D,'15:*',16, 18)
		err |= 	test_SymString2IDs(LB3D,'Tri*c',8, 2)
		err |= 	test_SymString2IDs(LB3D,'HEXAGONAL',8, 27)
		err |= 	test_SymString2IDs(LB3D,'rhom*',8, 7)
		err |= 	test_SymString2IDs(LB3D,'*2b*',8, 3, bad=True)
		if err: testing.addErr()

	if testing.doit('check finding Wyckoff letter from an atom position'):	#  2**1 = 2
		print ('\t*** NOTE, this does NOT check all the symmetry equivalent positions ***')
		err = False

		err |= test_FindWyckoffSymbol3D(LB3D,"43:cab", 0.3, 0, 0, 'a',8)

		if False:
			err |= test_FindWyckoffSymbol3D(LB3D,"43", 0, 0.5, 0.3765, 'b',16)
			err |= test_FindWyckoffSymbol3D(LB3D,"43", 0, 0, 0.3, 'a',8)
			err |= test_FindWyckoffSymbol3D(LB3D,"43:cab", 0.3, 0, 0, 'a',8)
			err |= test_FindWyckoffSymbol3D(LB3D,"43:bca", 0, 0.3, 0, 'a',8)
			err |= test_FindWyckoffSymbol3D(LB3D,"47", 0, 0.5, 0.3765, 'r',2)
			err |= test_FindWyckoffSymbol3D(LB3D,"47", 0.11, 0.5, 0.3765, 'x',4)
			err |= test_FindWyckoffSymbol3D(LB3D,"47", 0.11, 0.2, 0.3765,  'A',8)
			err |= test_FindWyckoffSymbol3D(LB3D,"47", 0,0,0,  'a',1)
			err |= test_FindWyckoffSymbol3D(LB3D,"47", float('nan'),0,0, '',0, bad=True)
			err |= test_FindWyckoffSymbol3D(LB3D,"75", 0,  0,  0.2,  'a',1)
			err |= test_FindWyckoffSymbol3D(LB3D,"75", 0.5,0.5,0.2,  'b',1)
			err |= test_FindWyckoffSymbol3D(LB3D,"75", 0,  0.5,0.2,  'c',2)
			err |= test_FindWyckoffSymbol3D(LB3D,"75", 0.5,0,  0.2,  'c',2, bad=True)
			err |= test_FindWyckoffSymbol3D(LB3D,"75", 0.1,0.2,0.3,  'd',4)
			err |= test_FindWyckoffSymbol3D(LB3D,"227:1", 0,0,0,  'a',8)
			err |= test_FindWyckoffSymbol3D(LB3D,"227:2", 0.875,0.875,0.875,  'a',8)
			err |= test_FindWyckoffSymbol3D(LB3D,"227:2", 0.125,0.125,0.125,  'a',8)
		if err: testing.addErr()

	if testing.doit('check forcing an atom position to the Wyckoff letter'):#  2**2 = 4
		err = test_ForceFractionalToWyckoff3D(LB3D,47, 'A',0.1,0.2,0.3, [0.1, 0.2, 0.3] )
		err |= test_ForceFractionalToWyckoff3D(LB3D,47, 'a',0.1,0.2,0.3, [0, 0, 0] )
		err |= test_ForceFractionalToWyckoff3D(LB3D,47, 'j',0.1,0.2,0.3, [0.1, 0, 0.5] )
		err |= test_ForceFractionalToWyckoff3D(LB3D,47, 'j',0.1,0.2,0.3, [0.1, 0, 0.6], bad=True )
		err |= test_ForceFractionalToWyckoff3D(LB3D,47, 'j',0.1,0.2,0.3, [0.1, 0, 0.6], bad=True )
		err |= test_ForceFractionalToWyckoff3D(LB3D,43, 'a',0.1,0.2,0.3, [0, 0, 0.3] )
		err |= test_ForceFractionalToWyckoff3D(LB3D,'43:cab', 'a',0.1,0.2,0.3, [0.3, 0, 0] )
		err |= test_ForceFractionalToWyckoff3D(LB3D,'43:bca', 'a',0.1,0.2,0.3, [0, 0.3, 0] )
		err |= test_ForceFractionalToWyckoff3D(LB3D,'227:1', 'a',0.1,0.2,0.3, [0, 0, 0] )
		err |= test_ForceFractionalToWyckoff3D(LB3D,'227:2', 'a',0.1,0.2,0.3, [0.875, 0.875, 0.875] )
		if err: testing.addErr()

	if testing.doit('check getting H-M symbols'):							#  2**3 = 8
		err = test_getHMboth(LB3D, '15:b3')
		err |= test_getHMboth(LB3D, '15:-b3')
		err |= test_getHMboth(LB3D, '229')
		err |= test_getHMboth(LB3D, 229)
		err |= test_getHMboth(LB3D, "15",bad=True)
		err |= test_getHMboth(LB3D, 15,bad=True)
		if err: testing.addErr()

	if testing.doit('check getting symmetry operations'):					#  2**4 = 16
		err = test_SetSymmetryOperations(LB3D, 1)
		err |= test_SetSymmetryOperations(LB3D, "1")
		err |= test_SetSymmetryOperations(LB3D, '15:b3')
		err |= test_SetSymmetryOperations(LB3D, '15', bad=True)
		if err: testing.addErr()

	if testing.doit('check using atomXtal class'):							#  2**5 = 32
		print (atomXtal('Fe1', (0,0,0)))

		SGid = '2'
		symOps = LB3D.SetSymmetryOperations(SGid)
		print ('for space group "%s", number of symOps = %d,   they are:' % (SGid,len(symOps)))
		print (symOps)
		atom = atomXtal('Fe1', (0,0.25,0), valence=2, occ=0.9, symOps=symOps, DebyeT=500)
		(symbol,mult,siteSym) = LB3D.FindWyckoffSymbol1(SGid,0,0.25,0)
		print ('\n for SG =',SGid)
		print (atom)

		if symbol=='i' and mult==2:
			print ('     FindWyckoffSymbol1  -->  Wyckoff = "%s",  mult = %g,  siteSym = "%s"\t' % (symbol,mult,siteSym))
		else:
			print ('ERR  FindWyckoffSymbol1  -->  Wyckoff = "%s",  mult = %g,  should be "i" and 2\t' % (symbol,mult))
			testing.addErr()
		print ("ERR  remove me") ; testing.addErr()	# a place holder for more tests

	if testing.doit('check using atomXtal class, fractional atom positions'):	#  2**6 = 64
		SGid = '75'
		symOps = LB3D.SetSymmetryOperations(SGid)
		print ('for space group "%s", number of symOps = %d,   they are:' % (SGid,len(symOps)))
		print (symOps)
		atom = atomXtal('Ti1', (0.002,0.002,0.002), symOps=symOps)
		err = (atom.mult != 4)
		print ('\n for fractional positions = 0.002 > 0.001')
		print (atom)

		atom = atomXtal('Ti1', (0.0002,0.0002,0.0002), symOps=symOps)
		print ('\n for fractional positions = 0.0002 < 0.001')
		err |= (atom.mult != 1)
		print (atom)

		if err:
			print ('ERR  first multiplicity should be 4, second should be 1')
			testing.addErr()

	if testing.doit('check using atomXtal class, overriding "==" and "!="'):	#  2**7 = 128
		SGid = '75'
		symOps = LB3D.SetSymmetryOperations(SGid)
		a1 = atomXtal('Ti1', (0.002,0.002,0.002), symOps=symOps)
		a2 = atomXtal('Ti2', (0.002,0.002,0.002), symOps=symOps)
		a3 = atomXtal('Cu2', (0.002,0.002,0.002), symOps=symOps)
		# print 'for space group "%s", number of symOps = %d,   they are:' % (SGid,len(symOps))
		# print a1
		# print a2
		# print a3
		err = test_equal_not_equal(a1,a2, False)
		err = err or test_equal_not_equal(a1,a3, False)
		err = err or test_equal_not_equal(a2,a3, False)
		err = err or test_equal_not_equal(a1,a1, True)
		err = err or test_equal_not_equal(a2,a2, True)
		err = err or test_equal_not_equal(a3,a3, True)
		if err:
			print ('ERR  testing atom1==atom2')
			testing.addErr()

	if testing.doit('check simpsonIntegral class'):							#  2**8 = 256
		iii = simpsonIntegral(math.sin,0,math.pi/2)	# init values for integration
		print (iii)				# print, but note there is no value
		iii.calc()				# calculate the integral
		print (iii)				# print again, note that there is a value this time
		print ('%r' % iii)		# print the representation
		value =  simpsonIntegral(math.sin,0,math.pi/2).calc()
		print ('Integral(sin) over [0,PI/2] = ',value)
		if math.fabs(value-1.0)>1e-9: testing.addErr()

	if testing.doit('check getting CBM operations'):						#  2**9 = 512
		err = test_SetCBMmatrix(LB3D, 1)
		err |= test_SetCBMmatrix(LB3D, "1")
		err |= test_SetCBMmatrix(LB3D, '15:b3')
		err |= test_SetCBMmatrix(LB3D, '15', bad=True)
		err |= test_SetCBMmatrix(LB3D, '167:H')
		err |= test_SetCBMmatrix(LB3D, '167:R')
		err |= test_SetCBMmatrix(LB3D, '62:bca')
		err |= test_SetCBMmatrix(LB3D, '86:2')
		err |= test_SetCBMmatrix(LB3D, '227:2')
		if err: testing.addErr()



	# start of the 2D testing
	LB2D = LatticeBase2D()

	if testing.doit("2D -- check finding SpaceGroupID's from all or part of a symmetry string"):	#  2**10 = 1024
		err = False
		err |= 	test_SymString2IDs(LB2D,'pg*',1, 2)
		err |= 	test_SymString2IDs(LB2D,'pm*',1, 3)
		err |= 	test_SymString2IDs(LB2D,'c2',1, 0)
		err |= 	test_SymString2IDs(LB2D,'c2mm',2, 1)
		err |= 	test_SymString2IDs(LB2D,'c2*',2, 1)
		err |= 	test_SymString2IDs(LB2D,'cm*',1, 2)
		err |= 	test_SymString2IDs(LB2D,'obliq*',-1, 2)
		err |= 	test_SymString2IDs(LB2D,'obliq*',8, 2)
		err |= 	test_SymString2IDs(LB2D,'hexagonal',8, 5)
		err |= 	test_SymString2IDs(LB2D,'rhom*',8, 2)
		err |= 	test_SymString2IDs(LB2D,'*2b*',8, 3, bad=True)
		if err: testing.addErr()

	if testing.doit('2D -- check finding Wyckoff letter from an atom position'):	#  2**11 = 2048
		print ('\t*** NOTE, this does NOT check all the symmetry equivalent positions ***')
		err = False

		err |= test_FindWyckoffSymbol2D(LB2D,"6",   0,   0, 'a',1)
		err |= test_FindWyckoffSymbol2D(LB2D,"6",   0, 0.5, 'b',1)
		err |= test_FindWyckoffSymbol2D(LB2D,"6", 0.5,   0, 'c',1)
		err |= test_FindWyckoffSymbol2D(LB2D,"6", 0.5, 0.5, 'd',1)
		err |= test_FindWyckoffSymbol2D(LB2D,"6", 0.1,   0, 'e',2)
		err |= test_FindWyckoffSymbol2D(LB2D,"6", 0.1, 0.5, 'f',2)
		err |= test_FindWyckoffSymbol2D(LB2D,"6",   0, 0.2, 'g',2)
		err |= test_FindWyckoffSymbol2D(LB2D,"6", 0.5, 0.2, 'h',2)
		err |= test_FindWyckoffSymbol2D(LB2D,"6", 0.1, 0.2, 'i',4)

		err |= test_FindWyckoffSymbol2D(LB2D,"7", 0, 0,   'a',2)
		err |= test_FindWyckoffSymbol2D(LB2D,"7", 0, 0.5, 'b',2)
		err |= test_FindWyckoffSymbol2D(LB2D,"7", 0.25, 0.1, 'c',2)
		err |= test_FindWyckoffSymbol2D(LB2D,"7", 0.1, 0.1, 'd',4)

		err |= test_FindWyckoffSymbol2D(LB2D,"13", 1/3., 2/3., 'b',1)
		err |= test_FindWyckoffSymbol2D(LB2D,"13", 2/3., 1/3., 'c',1)
		err |= test_FindWyckoffSymbol2D(LB2D,"13", 0.11, 0.12, 'd',3)

		err |= test_FindWyckoffSymbol2D(LB2D,"16", 0, 0, 'a',1)
		err |= test_FindWyckoffSymbol2D(LB2D,"16", 1/3., 2/3., 'b',2)
		err |= test_FindWyckoffSymbol2D(LB2D,"16", 1/2., 0., 'c',3)

		err |= test_FindWyckoffSymbol2D(LB2D,"17",    0,    0, 'a',1)
		err |= test_FindWyckoffSymbol2D(LB2D,"17", 1/3., 2/3., 'b',2)
		err |= test_FindWyckoffSymbol2D(LB2D,"17", 0.50,    0, 'c',3)
		err |= test_FindWyckoffSymbol2D(LB2D,"17", 0.11,    0, 'd',6)
		err |= test_FindWyckoffSymbol2D(LB2D,"17", 0.11, -.11, 'e',6)
		err |= test_FindWyckoffSymbol2D(LB2D,"17", 0.11, -.12, 'f',12)
		err |= test_FindWyckoffSymbol2D(LB2D,"17", 0.11, 0.12, 'f',12)
		if err: testing.addErr()

	if testing.doit('2D -- check forcing an atom position to the Wyckoff letter'):	#  2**12 = 4096
		err  = test_ForceFractionalToWyckoff2D(LB2D,6, 'i',0.1,0.2, [0.1, 0.2] )
		err |= test_ForceFractionalToWyckoff2D(LB2D,7, 'a',0.1,0.2, [0, 0] )
		err |= test_ForceFractionalToWyckoff2D(LB2D,7, 'b',0.1,0.2, [0, 0.5] )
		err |= test_ForceFractionalToWyckoff2D(LB2D,7, 'c',0.1,0.2, [0.25, 0.2] )
		err |= test_ForceFractionalToWyckoff2D(LB2D,7, 'd',0.1,0.2, [0.1, 0.2] )
		err |= test_ForceFractionalToWyckoff2D(LB2D,7, 'j',0.1,0.2, [0.1, 0], bad=True )
		err |= test_ForceFractionalToWyckoff2D(LB2D,7, 'j',0.1,0.2, [0.1, 0], bad=True )
		if err: testing.addErr()

	if testing.doit('2D -- check getting H-M symbols'):						#  2**13 = 8192
		err  = test_getHMboth(LB2D, '3')
		err  = test_getHMboth(LB2D, '15')
		err  = test_getHMboth(LB2D, '17')
		err  = test_getHMboth(LB2D, 17)
		if err: testing.addErr()

	if testing.doit('2D -- check getting symmetry operations'):				#  2**14 = 16384
		err = test_SetSymmetryOperations(LB2D, 2)
		err |= test_SetSymmetryOperations(LB2D, "2")
		err |= test_SetSymmetryOperations(LB2D, '7')
		err |= test_SetSymmetryOperations(LB2D, '15')
		if err: testing.addErr()

	if testing.doit('2D -- check using atomXtal class'):					#  2**15 = 32768
		print (atomXtal('Fe1', (0,0), dim=2))

		SGid = '6'
		symOps = LB2D.SetSymmetryOperations(SGid)
		print ('for space group "%s", number of symOps = %d,   they are:' % (SGid,len(symOps)))
		print (symOps)
		atom = atomXtal('Fe1', (0,0.25), valence=2, occ=0.9, symOps=symOps, DebyeT=500, dim=2)
		(symbol,mult,siteSym) = LB2D.FindWyckoffSymbol1(SGid,0,0.25)
		print ('\n for SG =',SGid)
		print (atom)

		if symbol=='g' and mult==2:
			print ('     FindWyckoffSymbol1  -->  Wyckoff = "%s",  mult = %g,  siteSym = "%s"\t' % (symbol,mult,siteSym))
		else:
			print ('ERR  FindWyckoffSymbol1  -->  Wyckoff = "%s",  mult = %g,  should be "i" and 2\t' % (symbol,mult))
			testing.addErr()

	if testing.doit('2D -- check using atomXtal class, fractional atom positions'):	#  2**16 = 65536
		SGid = '7'
		symOps = LB2D.SetSymmetryOperations(SGid)
		print ('for space group "%s", number of symOps = %d,   they are:' % (SGid,len(symOps)))
		print (symOps)
		atom = atomXtal('Ti1', (0.002,0.002), symOps=symOps)
		err = (atom.mult != 4)
		print ('\n for fractional positions = 0.002 > 0.001')
		print (atom)

		atom = atomXtal('Ti1', (0.0002,0.0002), symOps=symOps)
		print ('\n for fractional positions = 0.0002 < 0.001')
		err |= (atom.mult != 2)
		print (atom)

		if err:
			print ('ERR  first multiplicity should be 4, second should be 1')
			testing.addErr()

	if testing.doit('2D -- check using atomXtal class, overriding "==" and "!="'):	#  2**17 = 131072
		SGid = '6'
		symOps = LB2D.SetSymmetryOperations(SGid)
		a1 = atomXtal('Ti1', (0.002,0.002), symOps=symOps)
		a2 = atomXtal('Ti2', (0.002,0.002), symOps=symOps)
		a3 = atomXtal('Cu2', (0.002,0.002), symOps=symOps)
		# print 'for space group "%s", number of symOps = %d,   they are:' % (SGid,len(symOps))
		# print a1
		# print a2
		# print a3
		err = test_equal_not_equal(a1,a2, False)
		err = err or test_equal_not_equal(a1,a3, False)
		err = err or test_equal_not_equal(a2,a3, False)
		err = err or test_equal_not_equal(a1,a1, True)
		err = err or test_equal_not_equal(a2,a2, True)
		err = err or test_equal_not_equal(a3,a3, True)
		if err:
			print ('ERR  testing atom1==atom2')
			testing.addErr()


	testing.ending()

