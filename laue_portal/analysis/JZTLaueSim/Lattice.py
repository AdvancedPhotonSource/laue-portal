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
import cmath
import string
basestring = str
import numpy as np
from JZTLaueSim.JZTunits import UnitsJZTdefault as units, ConvertTemperatureUnits
from JZTLaueSim.JZTutil import hkl2str, findGCF, JZTtesting
#from symrange import symrange
import JZTLaueSim.LatticeBase as LatticeBase
import JZTLaueSim.readCIF as readCIF
import JZTLaueSim.atomGeneral as atomGeneral
import JZTLaueSim.bondCalc as bondCalc				# note, bond calculation is NOT done automatically, only when requested


NaN = float('nan')
NA = 6.022140857e23					# Avagadro's number
hc_keVnm = 1.2398419739				# h*c (keV-nm)
re_nm = 2.8179403227e-06			# Thompson, classical electron radius (nm)
NormalTemp_C = 20					# Normal Temperature (C), the default temperature
NormalTemp_K = NormalTemp_C + 273.15# Normal Temperature (K), the default temperature
Absolute0_C = -273.15				# absolute 0°C



class LatticeCommon(object):
	""" A Class that the defines a crystal lattice with all of its atoms.
		All parameters are forced to be consistent with the space group number.
		It can also calculate the structure factor F(hkl)
	"""

	def __init__(self, keV=None, allowed_F_N=0.01):
		"""
		Initialize the Lattice instance.

		values that are passed to the __init__()
		self.desc = desc						# name or decription of this crystal (str)
		self.SpaceGroupID					# Space Group ID from international tables, something like "15:-b2", not just an integer anymore
		self.atoms							# optional: a tuple of atomXtal's (no atoms are required)
		self.bonds							# optional: a tuple of bondType's (no bonds are required)
		self.keV							# optional: default energy used for calculating Fstruct() & mu()
		self.allowed_F_N					# optional: number of electrons/atom (e.g. |F|/Natmos) for an allowed reflection, (default=0.01)

		the following values are calculated at __init__()
		self.density						# calculated density (g/cm^3)
		self.direct							# calculated direct lattice (nm)
		self.recip							# calculated reciprocal lattice (1/nm), has the 2pi in it

		important methods:
		def SetWyckoffSymbols(self, force=False):	# Sets the Wyckoff Symbol, multiplicity, and site symmetry for all of the atoms
		def FindWyckoffSymbol(self, atom):			# this tests all of the equivalent xyz for each atom
		def uvw2ZoneDir(self,[uIn])					# compute zone direction of vector for (u,v,w) or [u,v,w], also works for (u,v)
		def angleBetweenZones(self,u1,v1,w1, u2,v2,w2)	# find angle between two zones: (u1,v1,w1) and (u2,v2,w2)
		def dSpacing(self, hkl, T=None)				# returns d-spacing (nm) for the hkl=(h,k,l) or hk=(h,k)
		def Fstruct(self, hkl, keV=None,T_K=None)	# returns the complex structure factor, (not yet includes T)
		def allowedHKL(self, hkl):					# True if hkl is allowed, hkl = (h,k,l) or (h,k)
		def pwd(self, hkl1, hkl2)					# find angle between (h1,k1,l1) and (h2,k2,l2)
		def hkl2Q(self, hkl )						# compute qvector for hkl=(h,k,l) or (h,k) (nm^1) contains the 2*PI
		def MinimalChemFormula(self)				# Create a minimal chemical formula for this structure

		self.databaseCodes							# list of crystal database codes, e.g. [('ICSD','123'), ('amcsd',3344566')]
		known database codes, saved as strings, not integers
			ICSD	Inorganic Crystal Structure Database code
			amcsd	American Mineralogical Society'
			CAS		Chemical Abstracts
			COD		Crystallography Open Database
			CSD		Cambridge Structural Database
			MDF		Metals Data File (metal structures)
			NBS		NBS (NIST) Crystal Data Database (lattice parameters)
			PDB		Protein Data Bank
			PDF		Powder Diffraction File (JCPDS/ICDD)
		"""
		try:	self.allowed_F_N = float(allowed_F_N)# an allowed reflection has |F|/Natoms > ALLOWED_F_N, must have at least 0.01 electrons/atom
		except: self.allowed_F_N = 0.01

		try:
			if keV<=0 or math.isnan(keV) or math.isinf(keV): raise		# energy must be positive definite, also fails on strings or None
			self.keV = keV						# a valid energy was passed
		except:	self.keV = None

		self.dim = 3							# the default
		self.SpaceGroupID = None
		self.desc = u''
		self.formulaStructural = None
		self.direct = self.recip = None
		self.density = None
		self.atoms = tuple()
		self.bonds = tuple()
		self.Temperature0 = None				# T at read in
		self.Temperature = None					# Temperature=T for calculating
		self.databaseCodes = []					# set elsewhere

		self.system = None
		self._neqStr = 'initial value' # None
		self._eq_all = self._eq_desc = True


	def calcDensity(self):
		""" calculate the density (g/cm^3) or (g/cm^2) """
		try:	dim = int(self.dim)
		except:	raise ValueError('dim must be 2 or 3, not %r' % (self.dim,))
		if dim==2:	V = float(self.Ac)
		else:		V = float(self.Vc)
		amuAll = 0.0								# atomic mass of all atoms in cell
		for atom in self.atoms:
			amuAll += atom.amu * atom.mult * atom.occ
		convert = (1e-7)**dim						# convert from nm --> cm
		self.density = (amuAll/NA)/(V * convert)
		if amuAll==0: self.density = float('nan')
		return self.density


	def __ne__(self, other):
		if type(other) is type(self):
			return not self.__eq__(other)
		return NotImplemented


	def SetWyckoffSymbols(self, force=False):	# Sets the Wyckoff Symbol, multiplicitym and site symmetry for all of the atoms
		for atom in self.atoms:
			if len(atom.WyckoffSymbol)==1 and not force: continue
			try:	(atom.WyckoffSymbol, atom.mult, atom.siteSymmetry) = self.FindWyckoffSymbol(atom, force=force)
			except:	pass


	def FindWyckoffSymbol(self, atom, force=False):	# this tests all of the equivalent xyz for each atom
		symbol = siteSym = ''
		mult = atom.mult					# start with existing values
		symbol = atom.WyckoffSymbol
		if force:	isymbol = 1000
		else:		isymbol = self.__WyckoffSymbolOrder(symbol)
		for xyz in atom.xyz:				# loop over the equivalent atom positions for atom
			(letter,mm,symm) = self.FindWyckoffSymbol1(self.SpaceGroupID,xyz[0],xyz[1],xyz[2])
			isym = self.__WyckoffSymbolOrder(letter)
			if isym < isymbol:
				mult = mm					# a higher symmetry point, save it
				symbol = letter
				siteSym = symm
				isymbol = isym

		if atom.WyckoffSymbol != symbol and len(atom.WyckoffSymbol) == 1:	# given symbol does not match found symbol
			print ('ERROR -- "%s" for %r: given Wyckoff=%r, but found %r @@@' % (self.desc, atom.label,atom.WyckoffSymbol,letter))
			raise ValueError('ERROR -- %r for %r: given Wyckoff=%r, but found %r @@@' % (str(self.desc), atom.label,atom.WyckoffSymbol,letter))
		if len(symbol) != 1: raise ValueError('Could not find Wyckoff symbol for atom = %r' % (atom.label,))
		return (symbol, mult, siteSym)


	def __WyckoffSymbolOrder(self,sym):		# returns an int representing the order of a Wyckoff symbol, starts with 'a'=1, to 'Z'=52
		try:	n = ord(sym[0])
		except:	return 1000					# not found, a big number
		if n >= 97:	offset = 96				# for 'a'=1, to 'z'=26
		else:		offset = 38				# for 'A'=27, to 'Z'=52
		offset += 1
		return (n - offset)


	def direct2str(self):
		try:	dim = self.direct.shape[0]
		except:	dim = None
		out = 'Direct Lattice (nm):'
		if dim == 2:
			aLen = math.sqrt( self.direct[0,0]**2 + self.direct[1,0]**2 )
			bLen = math.sqrt( self.direct[0,1]**2 + self.direct[1,1]**2 )
			out += '\n\ta = {%g, %g}     |a| = %g' % (self.direct[0,0], self.direct[1,0], aLen)
			out += '\n\tb = {%g, %g}     |b| = %g' % (self.direct[0,1], self.direct[1,1], bLen)
		elif dim == 3:
			aLen = math.sqrt( self.direct[0,0]**2 + self.direct[1,0]**2 + self.direct[2,0]**2 )
			bLen = math.sqrt( self.direct[0,1]**2 + self.direct[1,1]**2 + self.direct[2,1]**2 )
			cLen = math.sqrt( self.direct[0,2]**2 + self.direct[1,2]**2 + self.direct[2,2]**2 )
			out += '\n\ta = {%g, %g, %g}     |a| = %g' % (self.direct[0,0], self.direct[1,0], self.direct[2,0],aLen)
			out += '\n\tb = {%g, %g, %g}     |b| = %g' % (self.direct[0,1], self.direct[1,1], self.direct[2,1],bLen)
			out += '\n\tc = {%g, %g, %g}     |c| = %g' % (self.direct[0,2], self.direct[1,2], self.direct[2,2],cLen)
			return out
		else:
			raise ValueError('Cannot find a valid direct lattice')
		return out


	def recip2str(self):
		try:	dim = self.recip.shape[0]
		except:	dim = None
		out = 'Reciprocal Lattice (1/nm):'
		if dim == 2:
			asLen = math.sqrt( self.recip[0,0]**2 + self.recip[1,0]**2 + self.recip[2,0]**2 )
			bsLen = math.sqrt( self.recip[0,1]**2 + self.recip[1,1]**2 + self.recip[2,1]**2 )
			out += '\n\ta* = {%g, %g}     |a*| = %g' % (self.recip[0,0], self.recip[1,0], asLen)
			out += '\n\tb* = {%g, %g}     |b*| = %g' % (self.recip[0,1], self.recip[1,1], bsLen)
		elif dim == 3:
			asLen = math.sqrt( self.recip[0,0]**2 + self.recip[1,0]**2 + self.recip[2,0]**2 )
			bsLen = math.sqrt( self.recip[0,1]**2 + self.recip[1,1]**2 + self.recip[2,1]**2 )
			csLen = math.sqrt( self.recip[0,2]**2 + self.recip[1,2]**2 + self.recip[2,2]**2 )
			out += '\n\ta* = {%g, %g, %g}     |a*| = %g' % (self.recip[0,0], self.recip[1,0], self.recip[2,0],asLen)
			out += '\n\tb* = {%g, %g, %g}     |b*| = %g' % (self.recip[0,1], self.recip[1,1], self.recip[2,1],bsLen)
			out += '\n\tc* = {%g, %g, %g}     |c*| = %g' % (self.recip[0,2], self.recip[1,2], self.recip[2,2],csLen)
		else:
			raise ValueError('Cannot find a valid reciprocal lattice')
		return out


	def uvw2ZoneDir(self,uIn):
		""" compute zone direction of vector for uIn=(u,v,v) or uIn=(u,v) """
		u = np.matrix(uIn)
		vec = self.direct * u.T					# vec =  direct x u
		return vec


	def angleBetweenZones(self, uIn1, uIn2):
		""" find angle between two zones: uIn1=(u1,v1,w1) and uIn2=(u2,v2,w2),  or uIn = (u,v) """
		u1 = np.matrix(uIn1)
		u2 = np.matrix(uIn2)
		vec1 = self.direct * u1.T				# vec =  direct x u
		vec2 = self.direct * u2.T
		n1 = np.linalg.norm(vec1)
		n2 = np.linalg.norm(vec2)
		dot = float((vec1.T * vec2)[0]) / (n1*n2)

		if dot>=1.0: return 0.0
		elif dot<=-1.0: return 180.0
		return math.acos(dot) * 180/math.pi


	def dSpacing(self,hkl, T=None):
		"""
		returns d-spacing (nm) for the hkl=(h,k,l) or (h,k)
		T is in °C
		"""
		hklv = np.matrix(hkl)
		qvec = self.recip * hklv.T				# qvec =  recip x hklv
		norm = np.linalg.norm(qvec)
		if norm <= 0.0: return float('inf')
		d = 2*(math.pi) / norm					# q = 2PI/d

		try:
			try: T = float(T)					# get T, the target temperature (°C)
			except: T = float(self.Temperature)
			if T<Absolute0_C or not isfinite(T): raise
		except:
			return d							# no target Temperature, we are done

		try:									# first try expansion table, then alphaT
			strain = __interpPoints(T-Absolute0_C, expansionTable, extrapolate=True)	# expansionTable uses Kelvin, always extrapolate
			if not isfinite(strain): raise
			d = d * (1 + strain)
		except:									# expansionTable failed, try alphaT
			try:
				alphaT = float(self.alphaT)
				if not isfinite(alphaT+T): raise
				try:	T0 = self.Temperature0			# temperature where d was measured (Celsius)
				except:	T0 = NormalTemp_C				# default value when no self.Temperature0
				if T0<Absolute0_C or not isfinite(T0): raise
				d = d*(1+alphaT*(T-T0))	# apply temperature correction
			except:
				pass
		return d

	def __interpPoints(x, xy, extrapolate=False):
		N = len(xy)
		if N < 1: raise ValueError('ERROR -- interpPoints(), xy array is empty')
		xlast = xy[N-1][0]

		if (not extrapolate) and (not(xy[0][0] <= x and x <= xlast)):
			raise ValueError('ERROR -- interpPoints(), cannot interpolate outside of range when extrapolate=False')

		if N == 1:										# just 1 point, we are done, cannot really extrapolate
			return xy[0][1]
		elif x < xy[0][0]:								# before first point
			lo = xy[0],  hi = xy[0+1]
			slope  = (hi[1] - lo[1]) / (hi[0] - lo[0])
			return (x - lo[0])*slope + lo[1]
		elif xlast < x:									# after last point
			lo = xy[N-2],  hi = xy[N-1]
			slope  = (hi[1] - lo[1]) / (hi[0] - lo[0])
			return (x - lo[0])*slope + lo[1]

		xPrev = xy[0][0]
		for pt in xy:									# x's must be monotonic, but discontinuities are allowed
			if not isfinite(pt[0]): raise ValueError('ERROR -- interpPoints(), x values are all finite')
			if xPrev > pt[0]: raise ValueError('ERROR -- interpPoints(), x values are not monotonic increasing')
			xPrev = pt[0]
	
		# find imid that brackets x, using a binary search
		ilo = 0
		ihi = N-1
		imid = (ilo + ihi)/2
		while (x < xy[imid][0] or xy[imid+1][0] < x):			# continue until xy[imid][0] <= x <= xy[imid+1][0]
			if xy[imid+1][0] < x: ilo = imid + 1
			else: ihi = imid - 1
			imid = (ilo + ihi)/2								# integer math rounds down
		lo = xy[imid]
		hi = xy[imid+1]
		slope  = (hi[1] - lo[1]) / (hi[0] - lo[0])				# linear interpolate x between lo and hi
		return (x - lo[0])*slope + lo[1]


	def Fstruct(self, hkl, keV='NOTHING_PASSED_JZT', T_K=None):
		""" returns the structure factor,
		keV is optional. Note, an energy of <=0 is really bad and will raise exceptions. Use None or NaN instead
		Temperature (K), used to calculate Debye-Waller factor, not used yet.
		"""
		if keV != 'NOTHING_PASSED_JZT':	# something was passed, CHANGE self.keV
			try:
				if keV<=0 or math.isnan(keV) or math.isinf(keV): raise		# energy must be positive definite, also fails on strings or None
			except:
				keV = None
			self.keV = keV				# whatever was passed, use it, for default energy, do not pass a keV

		keV = self.keV

		try:	T_K = float(T_K)
		except:	T_K = -1.0
		zero = complex(0.0, 0.0)
		try:	h,k,l = hkl
		except:	h,k = hkl

		if self.dim ==3:
			usingHexAxes = (abs(90-self.alpha)+abs(90-self.beta)+abs(120-self.gam))<1e-6
			if not(h%1 or k%1 or l%1):						# non-integral, always allowed
				sym = self.getHMsym(self.SpaceGroupID)		# get symmetry symbol
				sym = sym[0]

				if sym == 'F':
					if not self._ALLOW_FC(h,k,l): return zero
				elif sym == 'I':
					if not self._ALLOW_BC(h,k,l): return zero
				elif sym == 'C':
					if not self._ALLOW_CC(h,k,l): return zero
				elif sym == 'A':
					if not self._ALLOW_AC(h,k,l): return zero
				elif sym == 'R' and usingHexAxes:
					if not self._ALLOW_RHOM_HEX(h,k,l): return zero # rhombohedral cell with hexagonal axes
				if self.system==self.HEXAGONAL:			# Hexagonal
					if not self._ALLOW_HEXAGONAL(h,k,l): return zero

		Q = 2.0 * math.pi / self.dSpacing(hkl)			# |Q| vector (nm)
		if self.Vibrate and self.atoms[0].U11 > 0:		# need Q-vector too.
			hklv = np.matrix(hkl)
			qvec = self.recip * hklv.T				# qvec =  recip x hklv
			# NOTE, qvec is a 2D <numpy matrix>, and a simle list or 1D array
		if len(self.atoms)<1: return complex(1.0,0.0)

		Freal = Fimag = fatomArg = 0.0
		for atom in self.atoms:
			fatomC = atom.fatom(Q, keV)
			# print 'f(%r, Q=%g, keV=%r) = %r' % (atom.symExtended, Q,keV, fatomC)
			fatomArg = cmath.phase(fatomC)
			fatomMag = abs(fatomC) * atom.occ
			if self.Vibrate:
				# M = B*(sin^2(theta)/lam^2) --> M = B/(16 π^2) * Q^2
				# exp(-B * sin^2(theta)/lam^2)		B = 8 * π^2 * <u^2> =  8 * π^2 * Uiso
				thetaM = atom.DebyeT
				Biso = atom.Biso								# B-factor (nmÍ^2)
				Uiso = atom.Uiso
				Usum = abs(atom.U11) + abs(atom.U22)
				Uansum = abs(atom.U12)
				if self.dim > 2:
					Usum += abs(atom.U33)
					Uansum += abs(atom.U13) + abs(atom.U23)

				if isfinite(thetaM + T_K) and T_K>0:					# have a valid Temperature and Debye Temperature
					amu = atom.amu							# mass of atom (amu)
					DW = math.exp(-atom.DW_factor_M(T_K,thetaM,Q))	# calculates the M in exp(-M), no I/O
					if DW>0: fatomMag *= DW
				elif Usum>0:									# qUq = q^t x U x q
					q0 = qvec.item(0)
					q1 = qvec.item(1)
					qUq = (atom.U11)*q0**2 + (atom.U22)*q1**2
					if self.dim > 2:
						q2 = qvec.item(2)
						qUq += (atom.U33)*q2**2
					if Uansum>0:
						qUq += 2*(atom.U12)*q0*q1
						if self.dim == 3: qUq += 2*(atom.U23)*q1*q2 + 2*(atom.U13)*q2*q0
					if isfinite(qUq): DW = math.exp(-qUq/2)
					else: DW = 1.0
					if DW>0.0: fatomMag *= DW
				elif (Biso>0):
					fatomMag *= math.exp(-Biso * (Q/(4*math.pi))**2)	# exp[-B * (sin(theta)/lam)^2 ]
				elif (Uiso>0):
					fatomMag *= math.exp(-Q*Q*Uiso/2)				# B = (8*π^2 U)

			# deltaf = (fatomMag*math.cos(fatomArg) - fatomC.real, fatomMag*math.sin(fatomArg) - fatomC.imag)
			# print u'after thermal: \u0394f(%r, Q=%g, keV=%r) = %r    T_K=%g, hkl = %d %d %d' % (atom.symExtended, Q,keV,deltaf, T_K,h,k,l)
			for xyz in atom.xyz:
				dot = h*xyz[0] + k*xyz[1]
				if self.dim == 3: dot += l*xyz[2]
				arg = 2*math.pi*dot + fatomArg
				Freal += fatomMag * math.cos(arg)
				Fimag += fatomMag * math.sin(arg)

		if abs(Freal)<1e-8: Freal = 0.0
		if abs(Fimag)<1e-8: Fimag = 0.0
		return complex(Freal,Fimag)


	def allowedHKL(self,hkl):	# note: hkl can be either (h,k,l) or (h,k)
		Fc = self.Fstruct(hkl)
		if len(self.atoms)>1:	N = float(len(self.atoms))
		else:					N = 1.0
		return abs(Fc)/N > self.allowed_F_N	# allowed means more than 0.01 electron/atom


	def EwPoCalc(self, d, F2, keV):				# Kinematic Bragg, extended face,  Warren pg. 46, eqn 4.7
		lam = hc_keVnm/keV 						# wavelength (nm)
		sin2Theta = math.sin(2* math.asin(lam/(2*d)) )	

		lam *= 0.001							# convert units (nm --> µm), wavelength (µm)
		re_micron = re_nm * 0.001				# Classical radius of electron (µm)
		muval = self.mu(keV)						# µ of xtal (µm⁻¹)
		Vc = self.Vc * 1e-9						# volume of real space space unit cell (µm³)
		Lorentz = 1 / sin2Theta					# Lorentz factor is 1/sin(2θ)
		#print(mu)    
		EwPo = re_micron*re_micron * math.pow(lam,3) * F2 / (Vc*Vc) / (2*muval) * Lorentz # if infinity
		return EwPo

	def EwIoCalc(self, d, F2, keV, dV):				# Kinematic Bragg, extended face,  Warren pg. 46, eqn 4.7
		lam = hc_keVnm/keV 						# wavelength (nm)
		sin2Theta = math.sin(2* math.asin(lam/(2*d)) )	

		lam *= 0.001							# convert units (nm --> µm), wavelength (µm)
		re_micron = re_nm * 0.001				# Classical radius of electron (µm)
		muval = self.mu(keV)						# µ of xtal (µm⁻¹)
		Vc = self.Vc * 1e-9						# volume of real space space unit cell (µm³)
		Lorentz = 1 / sin2Theta					# Lorentz factor is 1/sin(2θ)
		#print(mu)    
		EwIo = re_micron*re_micron * math.pow(lam,3) * F2 * dV / (Vc*Vc) * Lorentz # if small element
		return (EwIo, muval)

	
	def angleBetweenHKLs(self,hkl1, hkl2):
		""" find angle between hkl1 and hkl2, hkl1 = (h1,k1,l1) or (h1,k1) """
		hkl1v = np.matrix(hkl1)
		hkl2v = np.matrix(hkl2)
		qvec1 = self.recip * hkl1v.T		# qvec =  recip x hkl
		qvec2 = self.recip * hkl2v.T
		n1 = np.linalg.norm(qvec1)
		n2 = np.linalg.norm(qvec2)
		dot = float((qvec1.T * qvec2)[0]) / (n1*n2)

		if dot>=1.0: return 0.0
		elif dot<=-1.0: return 180.0
		return math.acos(dot) * 180/math.pi


	def hkl2Q(self, hkl):
		""" compute qvector for hkl = (h,k,l) or (h,k) """
		hklv = np.matrix(hkl)
		qvec = self.recip * hklv.T			# qvec =  recip x hklv
		return qvec


	def isValidExpansionTable(self, xy='no argument passed'):
		"""
		checks that xy is a valid expansion table
		Temperature must be >= 0 and monotonic
		no infs, and no nans
		this uses self.expansionTable if xy not provided
		"""
		try:
			if xy == 'no argument passed': xy = self.expansionTable
			N = len(xy)								# number of points in table
			if N < 1: return False					# must have at least one point
			Tprev = xy[0][0]
			for pt in xy: 							# T's must be monotonic, but discontinuities are allowed
				if not isfinite(pt[1]): raise		# ∆L/L values must be all finite
				if not isfinite(pt[0]): raise		# T values must be all finite
				if Tprev > pt[0]: raise				# T values are not monotonic increasing
				Tprev = pt[0]
		except: return False
		return True


	def data2xml(self, symOps=False):
		"""for a Lattice type object (2D or 3D), convert all of is data into a version 2 xml file """
		if not self.isValid(): raise ValueError('ERROR -- data2xml(), data is bad')
		dim = self.dim

		formula = None
		if self.formulaStructural: formula = self.formulaStructural
		elif self.formulaMin: formula = self.formulaMin

		try:
			temperature = float(self.Temperature0)		# in file store Temperature0, not Temperature
			if temperature < Absolute0_C: raise
			if not isfinite(temperature): raise
		except:
			temperature = None

		try:
			alphaT = float(self.alphaT)
			if not isnonzero(alphaT): raise
		except:
			alphaT = None

		try:
			if not self.isValidExpansionTable(self.expansionTable): raise
			expansionTable = self.expansionTable
		except:
			expansionTable = None

		try:
			pressure = float(self.Pressure) * 1e-3		# P stored in Pa, but write P in kPa
			if pressure < 0: raise
			if not isnonzero(pressure): raise
		except:
			pressure = None

		out = u'<?xml version="1.0" encoding="UTF-8" ?>\n\n<cif version="2" dim="%s">\n' % (dim,)
		if self.desc: out += '\t<chemical_name_common>%s</chemical_name_common>\n' % (self.desc,)
		if formula: out += '\t<chemical_formula>%s</chemical_formula>\n' % (formula,)

		try:
			for db,code in self.databaseCodes:
				if db and code: out += '\t<database_code db="%s">%s</database_code>\n' % (db, code)
		except: pass

		out += '\t<space_group>\n'
		SG = int(self.SpaceGroupID.split(':')[0])		# Space Group number, from International Tables
		out += '\t\t<IT_number>%d</IT_number>\n' % (SG,)
		out += '\t\t<id>%s</id>\n' % (self.SpaceGroupID,)
		out += '\t\t<system>%s</system>\n' % (self.latticeSystemName.lower(),)
		out += '\t\t<H-M>%s</H-M>\n' % (self.getFullHMSym(self.SpaceGroupID),)
		try:	out += '\t\t<Hall>%s</Hall>\n' % (self.getHallSymbol(self.SpaceGroupID),)
		except:	pass							# 2D does not have Hall symbols
		if symOps:
			equivX1 = self.equivX1
			out += '\t\t<symops N="%d">\n' % (len(equivX1),)
			if dim==2: 
				for mat in equivX1: out += '\t\t\t<op>"%s" "%s"</op>\n' % (self.symOpRow2str(mat[0]), self.symOpRow2str(mat[1]))
			else:
				for mat in equivX1: out += '\t\t\t<op>"%s" "%s" "%s"</op>\n' % (self.symOpRow2str(mat[0]), self.symOpRow2str(mat[1]), self.symOpRow2str(mat[2]))
			out += '\t\t</symops>\n'
		out += '\t</space_group>\n'

		out += '\t<cell>\n'
		out += '\t\t<a unit="nm">%r</a>\n' % (self.a,)		# write lengths in nm
		out += '\t\t<b unit="nm">%r</b>\n' % (self.b,)
		if dim>2:
			out += '\t\t<c unit="nm">%r</c>\n' % (self.c,)
		out += '\t\t<alpha>%r</alpha>\n' % (self.alpha,)	# write angles in degree
		if dim>2:
			out += '\t\t<beta>%r</beta>\n' % (self.beta,)
			out += '\t\t<gamma>%r</gamma>\n' % (self.gam,)
		if isnonzero(pressure): out += '\t\t<pressure unit="kPa">%r</pressure>\n' % (pressure,)
		if isfinite(temperature): out += '\t\t<temperature unit="C">%r</temperature>\n' % (temperature,)
		if isnonzero(alphaT): out += '\t\t<alphaT>%r</alphaT>\t\t\t<!-- a = ao*(1+alphaT*(TempC-20)) -->\n' % (alphaT,)
		try:					# try to construct xml for expansionTable
			if not expansionTable: raise
			tstr = ''
			lstr = ''
			for tt,ll in expansionTable:
				tstr += float(tt) + ' '
				lstr += float(ll) + ' '
			tstr = tstr.strip()
			tlStr = '\t\t<thermalExpansion>\n\t\t\t<T unit="K">'+tstr+'</T>\n\t\t\t<dL_L>'+lstr+'</dL_L>\n\t\t</thermalExpansion>\n'
			out += tlStr
		except: pass
		out += '\t</cell>\n'

		for atom in self.atoms:
			out += '\t<atom_site>\n'
			out += '\t\t<label>%s</label>\n' % (atom.label,)
			out += '\t\t<symbol>%s</symbol>\n' % (atom.sym,)
			if dim>2:	out += '\t\t<fract>%r %r %r</fract>\n' % (atom.x,atom.y,atom.z)
			else:		out += '\t\t<fract>%r %r</fract>\n' % (atom.x,atom.y)
			if atom.occ != 1:		out += '\t\t<occupancy>%r</occupancy>\n' % (atom.occ,)
			if atom.valence != 0:	out += '\t\t<valence>%r</valence>\n' % (atom.valence,)
			if atom.WyckoffSymbol:	out += '\t\t<WyckoffSymbol>%s</WyckoffSymbol>\n' % (atom.WyckoffSymbol,)
			if isnonzero(atom.DebyeT): out += '\t\t<DebyeTemperature unit="K">%g</DebyeTemperature>\n' % (atom.DebyeT,)
			if isnonzero(atom.Biso):	out += u'\t\t<Biso unit="Å^2">%g</Biso>\n' % (atom.Biso * 100.,)	# convert nm^2 --> Å^2
			if isnonzero(atom.Uiso):	out += u'\t\t<Uiso unit="Å^2">%g</Uiso>\n' % (atom.Uiso * 100.,)	# convert nm^2 --> Å^2

			writeUii = isfinite(atom.U11) or isfinite(atom.U22)							# is at least one of the Uii valid?
			if dim>2: writeUii = writeUii or isfinite(atom.U33)
			writeUij = isfinite(atom.U12)												# is at least one of the Uij valid?
			if dim>2: writeUij = writeUij or isfinite(atom.U13) or isfinite(atom.U23)
			if writeUii:																# if one  Uii is valid, write them all
				out += u'\t\t<U11 unit="Å^2">%r</U11>\n' % (atom.U11 * 100.,)			# convert nm^2 --> Å^2
				out += u'\t\t<U22 unit="Å^2">%r</U22>\n' % (atom.U22 * 100.,)
				if dim>2: out += u'\t\t<U33 unit="Å^2">%r</U33>\n' % (atom.U33 * 100.,)	
			if writeUij:																# if one  Uij is valid, write them all
				out += u'\t\t<U12 unit="Å^2">%r</U12>\n' % (atom.U12 * 100.,)			# convert nm^2 --> Å^2
				if dim>2:
					out += u'\t\t<U13 unit="Å^2">%r</U13>\n' % (atom.U13 * 100.,)
					out += u'\t\t<U23 unit="Å^2">%r</U23>\n' % (atom.U23 * 100.,)
			out += '\t</atom_site>\n'

		for bond in self.bonds:
			ls = ''
			for ll in bond.lengths: ls += str(ll) + ' '
			ls = ls.strip()
			out += '\t<bond_chemical unit="nm" n0="%s" n1="%s">%s</bond_chemical>\n' % (bond.label0, bond.label1, ls)

		out += '</cif>\n'
		return out


	def MinimalChemFormula(self):
		""" Create a minimal chemical formula for this structure """
		if len(self.atoms)<1:
			self.formulaMin = ''
			return ''

		atomList = list()
		fdict = {}
		for atom in self.atoms:
			value = float(atom.occ * atom.mult)
			if value <= 0: continue
			symbol = atom.sym
			try:
				prev = fdict[symbol]			# previous amount of this element
			except:
				prev = 0					# this element was not yet encountered
				atomList.append(symbol)		# atomList needed because dicts do not preserve order
			fdict[symbol] = prev + value		# increment element 'symbol'

		nums = list()
		for item in fdict: nums.append(fdict[item])

		allInts = True
		for i in nums: allInts = allInts and (i).is_integer()
		if allInts:							# remove common factors
			gcf = findGCF(nums)
			if gcf>1:						# divide out factor
				for item in fdict: fdict[item] = int(fdict[item] / gcf)

		# now create formula from fdict
		formula = ''
		for symbol in atomList:
			val = fdict[symbol]
			if val<=0:	continue
			formula += str(symbol)
			if val!=1:
				if val == round(val): val = int(val)
				formula += str(val)

			if not allInts: formula += ' '

		self.formulaMin = formula.strip()
		return self.formulaMin
#
#	def MinimalChemFormula(self):
#		""" Create a minimal chemical formula for this structure """
#		if len(self.atoms)<1:
#			self.formulaMin = ''
#			return ''
#
#		atomList = list()
#		fdict = {}
#		for atom in self.atoms:
#			value = atom.occ * atom.mult
#			if value <= 0: continue
#			symbol = atom.sym
#			try:
#				prev = fdict[symbol]		# previous amount of this element
#			except:
#				prev = 0					# this element was not yet encountered
#				atomList.append(symbol)		# atomList needed because dicts do not preserve order
#			fdict[symbol] = prev + value	# increment element 'symbol'
#
#		nums = list()
#		for item in fdict: nums.append(fdict[item])
#
#		allInts = True
#		for i in nums: allInts = allInts and (i).is_integer()
#		iMax = int(math.ceil(max(nums)))
#
#		if allInts:							# remove common factors
#			for factor in range(iMax,0,-1):	# check factor
#				allDivide = True
#				for i in nums:
#					if not(i % factor == 0):
#						allDivide = False
#						break
#				if allDivide: break
#			if factor>1:					# divide out factor
#				for item in fdict:
#					val = fdict[item] / factor
#					fdict[item] = int(val)
#
#		# now create formula from fdict
#		formula = ''
#		for symbol in atomList:
#			val = fdict[symbol]
#			if val<=0:	continue
#			formula += str(symbol)
#			if val!=1:
#				if val == round(val): val = int(val)
#				formula += str(val)
#
#		self.formulaMin = formula
#		return formula




"""
	Rhombohedral Transformation:

	for Rhombohedral (hkl), and Hexagonal (HKL)
		h = (2H+K+L)/3
		k = (-H+K+L)/3
		l = (-H-2K+L)/3
		and the condition (-H+K+L) = 3n (where n is an integer) for allowed reflections, three Rhombohedral cells per Hexagonal cell

		H = h-k
		K = k-l
		L = h+k+l

	for Hexagonal lattice constants aH,cH (alpha=beta=90, gamma=120)
	a(Rhom) = sqrt(3*aH^2 + cH^2)/3
	sin(alpha(Rhom)/2) = 1.5/sqrt(3+(cH/aH)^2)
	These equations are implented in the routines:  Hex2Rhom(aH,cH)  &  Rhom2Hex(aR,alpha)


	Although not used here, note that the following also works:
		NOTE Inv(A^t) = Inv(A)^t, so the order of Inv() and ^t do not matter
		MatrixOP recipLatice   = 2*PI * (Inv(directLattice))^t
		MatrixOP directLattice = 2*PI * Inv(recipLatice^t)
		Vc      = MatrixDet(directLattice)		// Volume of unit cell
		VcRecip = MatrixDet(recipLatice)	// Volume of reciprocal lattice cell

	And:
		kf^ = ki^ - 2*(ki^ . q^)*q^		note: (ki^ . q^) must be NEGATIVE (both Bragg & Laue)
"""
class Lattice3D(LatticeCommon, readCIF.readXTAL, LatticeBase.LatticeBase3D, bondCalc.bondCalc):
	""" A Class that the defines a crystal lattice with all of its atoms.
		It can NOT load all the information from a file
		All parameters are forced to be consistent with the space group number.
		It can also calculate the structure factor F(hkl)
	"""

	def __init__(self, SpaceGroupID, LC, desc=u'', Temperature=None,alphaT=None,expansionTable=None,atoms=tuple(),bonds=tuple(),keV=None, allowed_F_N=0.01, databaseCodes=None, formulaStructural=None):
		"""
		LC					a tuple or list of 6 lattice constants [a,b,c,alpha,beta,gamma]

		Initialize the Lattice instance.

		values that are passed to the __init__()
		self.desc = desc				# name or decription of this crystal (str)
		self.SpaceGroupID				# Space Group ID from international tables, something like "15:-b2", not just an integer anymore
		self.a = float(a)				# lattice constant (nm)
		self.b = float(b)
		self.c = float(c)
		self.alpha = float(alpha)		# angles (degree)
		self.beta = float(beta)
		self.gam = float(gam)
		self.alphaT = alphaT			# optional: coef of thermal expansion, a = ao*(1+alphaT*(TempC-NormalTemp_C))
		self.expansionTable				# optional: table of ∆L/L vs T an array of tuples [ (T,∆L/L) ], T in Kelvin
		self.Temperature0 = Temperature	# optional: temperature for these values, default is NormalTemp_C (Celsius)
		self.atoms						# optional: a tuple of atomXtal's (no atoms are required)
		self.bonds						# optional: a tuple of bondType's (no bonds are required)
		self.keV						# optional: default energy used for calculating Fstruct() & mu()
		self.allowed_F_N				# optional: number of electrons/atom (e.g. |F|/Natmos) for an allowed reflection, (default=0.01)
		self.databaseCodes				# optional: list of crystal database codes, e.g. [('ICSD','123'), ('amcsd',3344566')]
		self.formulaStructural			# optional: structural formula, probably from  a CIF file.

		the following values are calculated at __init__()
		self.latticeSystemName			# Cubic, Hexagonal, Trigonal, Tetragonal, Orthorhombic, Monoclinic, Triclinic
		self.density					# calculated density (g/cm^3)
		self.formulaMin					# calculated minimal chemical formula for this structure
		self.direct						# calculated direct lattice (nm)
		self.recip						# calculated reciprocal lattice (1/nm), has the 2pi in it

		important methods:
		def Hex2Rhom(self,aH,cH)		# convert Hexagonal lattice constants to Rhombohedral
		def Rhom2Hex(self,aR,alpha)		# convert Rhombohedral lattice constants to Hexagonal
		def findClosestHKL(self,dIN)	# Find the hkl(s) closest to given d-spacing (nm)
		def mu(self,keV):				# linear absorption factor mu (1/micron), transmission = exp(-mu * t)
		def isValid(self)					Check if lattice constants are valid, returns True if all 6 are valid
		def SetWyckoffSymbols(self, force=False):	# Sets the Wyckoff Symbol, multiplicity, and site symmetry for all of the atoms
		def FindWyckoffSymbol(self, atom):	# this tests all of the equivalent xyz for each atom
		"""
		LatticeBase.LatticeBase3D.__init__(self)		# sets some big lists and provides some utility functions
		bondCalc.bondCalc.__init__(self)			# note, bond calculation is NOT done automatically, only when requested
		LatticeCommon.__init__(self, keV=keV, allowed_F_N=allowed_F_N)

		self.dim = 3
		self.read = None
		try:	a,b,c,alpha,beta,gam = LC
		except:	raise ValueError('Must have either 6 lattice constants for Lattice3D, not %r' % (LC,))

		SpaceGroupID = str(SpaceGroupID)
		try:	self.validSpaceGroupID(SpaceGroupID)						# raises exception if not a valid Space Group ID
		except:	SpaceGroupID = self.FindDefaultIDforSG(SpaceGroupID)		#   or if not an integer in [1-230] either
		self.SpaceGroupID = SpaceGroupID	# self.SpaceGroupID is now a string like "15:-b2", or 229

		self.desc = str(desc)			# name or decription of this crystal (str)

		self.a = float(a)					# lattice constant (nm)
		self.b = float(b)
		self.c = float(c)
		self.alpha = float(alpha)			# angles (degree)
		self.beta = float(beta)
		self.gam = float(gam)
		self.databaseCodes = databaseCodes
		self.formulaStructural = formulaStructural
		self.atoms = atoms
		self.bonds = bonds

		if isinstance(self.formulaStructural,basestring):
			if len(self.formulaStructural) < 1 : self.formulaStructural = None

		try:									# self,
			Temperature = float(Temperature)
			if not isfinite(Temperature): raise
		except: Temperature = None				# not a valid Temperature, set to None
		if isinstance(Temperature, (int, int, float)):
			if Temperature < Absolute0_C: raise ValueError("Temperature (C) is %r, which must be >= %g" % (Temperature,Absolute0_C))
		self.Temperature0 = Temperature
		self.Temperature = Temperature

		try:
			alphaT = float(alphaT)
			if not isfinite(alphaT): raise
		except: alphaT = None					# not a valid alphaT, set to None
		self.alphaT = alphaT

		if self.isValidExpansionTable(expansionTable): self.expansionTable = expansionTable
		else: self.expansionTable = None

		self.system = self.__latticeSystemNum()		# get lattice system from SpaceGroupID
		self.latticeSystemName = self.latticeSystemNames[self.system]
		self._neqStr = 'initial value' 				# None
		self._eq_all = self._eq_desc = True

		self.SetSymmetryOperations(self.SpaceGroupID)	# these are needed to calculate the atom positions
		self.__ForceLatticeToStructure()			# force a,b,c, alpha,beta,gam to match Space Group, sets Vc, direct & recip too
		self.__setDirectRecip()					# set direct & reicp lattices, also calc Vc

		# set miscelaneous things in lattice
		self.Vibrate = self.haveDebyeT = False
		for atom in self.atoms:
			if atom.hasThermalInfo: self.Vibrate = True	# True if some Thermal vibration info present in xtal (for any atom) 
			if atom.DebyeT > 0: self.haveDebyeT = True	# True if some one of the atoms has a Debye Temperature

		for atom in self.atoms:					# check that all atoms are valid
			if len(self.equivX1): atom.calcAllAtomPositions3D(self.equivX1)	# have the symmetry operation matricies, use them
		self.calcDensity()						# now that I have all of the atom positions, can calc density
		self.MinimalChemFormula()					# set the minimal chemical formula

		# done setting, now check that everything is valid
		if not (self.a >= 0 and self.b >= 0 and self.c >= 0): raise ValueError('INVALID a=%r, b=%r, c=%r' % (self.a,self.b,self.c))
		if not (self.alpha > 0 and self.beta > 0 and self.gam > 0): raise ValueError('INVALID alpha=%r, beta=%r, gamma=%r' % (self.alpha,self.beta,self.gam))
		if not (self.alpha < 180 and self.beta < 180 and self.gam < 180): raise ValueError('INVALID alpha=%r, beta=%r, gamma=%r' % (self.alpha,self.beta,self.gam))
		if (self.Vibrate or self.haveDebyeT) and len(self.atoms) < 1:
			raise ValueError("Inavlid, have Vibrate or DebyeT, but no atoms")

#			Tinfo = Vinfo = False					# check for consistent Thermal/Vibrational info
#			for atom in self.atoms:
#				if atom.bad(): raise ValueError('bad atom')
#				Tinfo = Tinfo or atom.Tinfo
#				Vinfo = Vinfo or atom.Vinfo
#			if Tinfo and Vinfo: raise ValueError('there are some atoms Vibrational info and some with Debye Temperature, cannot mix')

		labels = list()							# check for duplicate atoms labels
		for atom in self.atoms:
			labels.append(atom.label)
		if len(set(labels))<len(labels): raise ValueError('there are atoms with duplicate labels')

		self.SetWyckoffSymbols(force=True)			# Sets the Wyckoff Symbol, multiplicity, and site symmetry for all of the atoms, that have not been set yet
#		self.SetWyckoffSymbols(force=False)			# Sets the Wyckoff Symbol, multiplicity, and site symmetry for all of the atoms, that have not been set yet

		#		double Unconventional00,Unconventional01,Unconventional02	// transform matrix for an unconventional unit cel
		#		double Unconventional10,Unconventional11,Unconventional12
		#		double Unconventional20,Unconventional21,Unconventional22
		#		char hashID[HASHID_LEN]	// hash function for this strucutre (needs to hold at least 64 chars), This MUST be the last item

		if not self.isValid(): raise ValueError('Lattice constants are INVALID:  a=%g, b=%g, c=%g, alpha=%g, beta=%g, gamma=%g' % (self.a,self.b,self.c, self.alpha,self.beta,self.gam))


	def isValid(self):
		""" Check if lattice constants are valid, returns True if all 6 are valid """
		self.validSpaceGroupID(self.SpaceGroupID)

		a = self.a
		b = self.b
		c = self.c
		alpha = self.alpha
		beta = self.beta
		gam = self.gam

		if not isfinite(a+b+c+alpha+beta+gam): return False
		if not (a>0 and b>0 and c>0 and alpha>0 and beta>0 and gam>0): return False
		if not (alpha<180 and beta<180 and gam<180): return False

		if self.system == self.CUBIC:
			if not (a == b and a == c): return False
			if not (alpha==90.0 and beta==90.0 and gam==90.): return False
		elif self.system == self.HEXAGONAL:
			if not (a == b): return False
			if not (alpha==90.0 and beta==90.0 and gam==120.): return False
		elif self.system == self.TRIGONAL:
			if self.isRhombohedral:
				if not (a == b): return False
				if not (a == c): return False
				if not (alpha == beta): return False
				if not (alpha == gam): return False
			else:
				if not (a == b): return False
				if not (alpha==90.0 and beta==90.0 and gam==120.): return False
		elif self.system == self.TETRAGONAL:
			if not (a == b): return False
			if not (alpha==90.0 and beta==90.0 and gam==90.): return False
		elif self.system == self.ORTHORHOMBIC:
			if not (alpha==90.0 and beta==90.0 and gam==90.): return False
		elif self.system == self.MONOCLINIC:
			if not (alpha==90.0 and gam==90.): return False
		else:							# Triclinic
			pass

		return True


	def __ForceLatticeToStructure(self):
		""" Forces lattice constants to match the Space Group number (e.g. for cubic, forces b and c to be a, and all angles 90)
		Cubic			[195,230]		a
		Hexagonal		[168,194]		a,c
		Trigonal		[143,167]		a,alpha
		Tetragonal		[75,142]		a,c
		Orthorhombic	[16,74]			a,b,c
		Monoclinic		[3,15]			a,b,c,gamma
		Triclinic		[1,2]			a,b,c,alpha,beta,gamma
		"""
		self.isRhombohedral = False			# True if it is a rhombohedral space group with rhombohedral axes
		system = self.system
		if system == self.CUBIC:
			self.b = self.c = self.a
			self.alpha = self.beta = self.gam = 90
		elif system == self.HEXAGONAL:
			self.b = self.a
			self.alpha = self.beta = 90
			self.gam = 120
		elif system == self.TRIGONAL:	# Trigonal (generally hexagonal cell), for rhomohedral use rhomohedral cell, unless obviously the hexagonal
			if self.SpaceGroupID.find(':R') >= 0:	# Rhombohedral Space Group, with rhombohedral cell, only for [146,148,155,160,161,166,167]
				self.isRhombohedral = True
				self.b = self.c = self.a
				self.beta = self.gam = self.alpha
			else:							# using Hexagonal axes
				self.b = self.a
				self.alpha = self.beta = 90
				self.gam = 120
		elif system == self.TETRAGONAL:		# Tetragonal
			self.b = self.a
			self.alpha = self.beta = self.gam = 90
		elif system == self.ORTHORHOMBIC:		# Orthorhombic
			self.alpha = self.beta = self.gam = 90
		elif system == self.MONOCLINIC:			# Monoclinic
			self.alpha = self.gam = 90
		else:								# Triclinic
			pass

		# finally check for valid numbers, i.e. all greater than 0 and angles < 180
		if not(self.a > 0 or self.b > 0 or self.c > 0): 
			raise ValueError('Lattice constants must be >= 0, a=%g, b=%g, c=%g' % (self.a,self.b,self.c))
		elif not ((self.alpha > 0 and self.alpha < 180) or (self.beta > 0 and self.beta < 180) or (self.gam > 0 and self.gam < 180)):
			raise ValueError('Lattice angles must be in (0,180 degree), alpha=%g, beta=%g, gamma=%g' % (self.alpha,self.beta,self.gam))


	def __setDirectRecip(self):
		""" set direct and recip lattice vectors from {a,b,c,alpha,beta,gamma}, also calculates Vc """
		a = self.a
		b = self.b
		c = self.c
		ca = math.cos((self.alpha)* math.pi /180.)
		cb = math.cos((self.beta)* math.pi /180.)
		cg = math.cos((self.gam)* math.pi /180.)
		sg = math.sin((self.gam)* math.pi /180.)
		phi = math.sqrt(1.0 - ca*ca - cb*cb - cg*cg + 2*ca*cb*cg)	# = Vc/(a*b*c)
		self.Vc = a*b*c * phi					# volume of unit cell
		pv = (2*math.pi) / (self.Vc)			# used for scaling

		# calculate components of the direct lattice vectors
		if not self.isRhombohedral:
			# second choice International Tables (2006) Vol. B, chapter 3.3 page 360 (bottom of first column)
			a0 = a			; a1 = 0.0				; a2 = 0.0			# a || x
			b0 = b*cg		; b1 = b*sg				; b2=0
			c0 = c*cb		; c1 = c*(ca-cb*cg)/sg	; c2=c*phi/sg		# z || c* (or axb)
			a0 = zeroOut(a0) ; a1 = zeroOut(a1) ; a2 = zeroOut(a2)
			b1 = zeroOut(b1) ; b2 = zeroOut(b2)
			c2 = zeroOut(c2)
		else:
			# Rhombohedral cell choice International Tables (2006) Vol. B, chapter 3.3 page 360 (top of second column)
			# a,b,c are symmetric about the 111 direction, or (a+b+c) == {x,x,x}
			p = math.sqrt(1.0 + 2*ca)
			q = math.sqrt(1.0 - ca)
			pmq = (a/3.0)*(p-q)
			p2q = (a/3.0)*(p+2*q)
			a0 = p2q		; a1 = pmq				; a2 = pmq
			b0 = pmq		; b1 = p2q				; b2 = pmq
			c0 = pmq		; c1 = pmq				; c2 = p2q
		self.direct = np.matrix([ [a0,b0,c0], [a1,b1,c1], [a2,b2,c2] ])

		as0 = zeroOut((b1*c2-b2*c1)*pv)			# (b x c)*2PI/Vc
		as1 = zeroOut((b2*c0-b0*c2)*pv)
		as2 = zeroOut((b0*c1-b1*c0)*pv)
		bs0 = zeroOut((c1*a2-c2*a1)*pv)			# (c x a)*2PI/Vc
		bs1 = zeroOut((c2*a0-c0*a2)*pv)
		bs2 = zeroOut((c0*a1-c1*a0)*pv)
		cs0 = zeroOut((a1*b2-a2*b1)*pv)			# (a x b)*2PI/Vc
		cs1 = zeroOut((a2*b0-a0*b2)*pv)
		cs2 = zeroOut((a0*b1-a1*b0)*pv)
		self.recip = np.matrix([ [as0, bs0, cs0], [as1, bs1, cs1], [as2, bs2, cs2] ] )


	def __eq__(self, other):
		"""
		returns True if two Lattice classes are equal
		if desc is True, then check that descriptions are equal
		"""
		if not( type(other) is type(self) ): return NotImplemented	# can only compare objects of the same type
		other._neqStr = self._neqStr = ''

		if not( type(other) is type(self) ): return NotImplemented	# can only compare objects of the same type
		if self.SpaceGroupID != other.SpaceGroupID:
			other._neqStr = self._neqStr = 'SpaceGroupID differ, "%s" != "%s"' %(self.SpaceGroupID, other.SpaceGroupID)
			return False
		elif ( abs(self.a - other.a) + abs(self.b - other.b) + abs(self.c - other.c) ) > 1e-5:
			other._neqStr = self._neqStr = 'a, b, or c differ'
			return False
		elif ( abs(self.alpha - other.alpha) + abs(self.beta - other.beta) + abs(self.gam - other.gam) ) > 1e-5:
			other._neqStr = self._neqStr = 'alpha, beta, or gamma differ'
			return False
		elif self.system != other.system:
			other._neqStr = self._neqStr = 'crystal system mismatch, %r != %r' % (self.system, other.system)
			return False
		elif self.formulaMin != other.formulaMin:
			other._neqStr = self._neqStr = 'formulaMin differ'
			return False
		elif self.isRhombohedral != other.isRhombohedral:
			other._neqStr = self._neqStr = 'isRhombohedral differ'
			return False
		elif abs(self.density - other.density) > 1e-4:
			other._neqStr = self._neqStr = 'density differ'
			return False
		elif abs(self.Vc - other.Vc) > 1e-7:
			other._neqStr = self._neqStr = 'Vc differ'
			return False
		elif isinstance(self.Temperature0, (int, int, float)) and isinstance(other.Temperature0, (int, int, float)):
			if self.Temperature0>0 and other.Temperature0>0:
				if abs(self.Temperature0 - other.Temperature0) > 1e-3:
					other._neqStr = self._neqStr = "Temperature0's differ"
					return False
		elif isinstance(self.Temperature, (int, int, float)) and isinstance(other.Temperature, (int, int, float)):
			if self.Temperature>0 and other.Temperature>0:
				if abs(self.Temperature - other.Temperature) > 1e-3:
					other._neqStr = self._neqStr = 'Temperatures differ'
					return False
		elif isinstance(self.alphaT, (int, int, float)) and isinstance(other.alphaT, (int, int, float)):
			if self.alphaT>0 and other.alphaT>0:
				if abs(self.alphaT - other.alphaT) > 1e-6:
					other._neqStr = self._neqStr = 'alphaT differ'
					return False

		elif (self.expansionTable != other.expansionTable):
				other._neqStr = self._neqStr = 'expansionTable differ'
				return False

		astr = LatticeBase.atomXtal('H',(0,0,0)).atomListsDiffer(self.atoms, other.atoms)
		if len(astr)>0:
			other._neqStr = self._neqStr = astr
			return False

		bstr = LatticeBase.bondType('a','b', 1.0).bondListsDiffer(self.bonds, other.bonds)
		if len(bstr)>0:
			other._neqStr = self._neqStr = bstr
			return False

		if not (self._eq_all and other._eq_all): return True

		if self._eq_desc:
			if self.desc != other.desc:
				other._neqStr = self._neqStr = 'descriptions differ'
				return False

		elif not (self.databaseCodes is None and other.databaseCodes is None):
			if set(self.databaseCodes) != set(other.databaseCodes):
				other._neqStr = self._neqStr = 'databaseCodes differ'
				return False
		elif not (self.formulaStructural is None and other.formulaStructural is None):
			if self.formulaStructural != other.formulaStructural:
				other._neqStr = self._neqStr = 'formulaStructural differ'
				return False
		elif isinstance(self.keV, (int, int, float)) and isinstance(other.keV, (int, int, float)):
			if self.keV>0 and other.keV>0:
				if abs(self.keV - other.keV) > 1e-4: 
					other._neqStr = self._neqStr = 'keV differ'
					return False

		return True


	def Hex2Rhom(self,aH,cH):
		""" convert lattice constants
		aH,cH	Hexagonal lattice constants
		returns aR,alpha as a tuple, Rhombohedral lattice constants
		"""
		aR = math.sqrt(3.0*aH*aH + cH*cH) / 3.0
		alpha = 2 * math.asin( 1.5 / math.sqrt(3.0+(cH/aH)**2) )
		return (aR, alpha * (180.0/math.pi))

	def Rhom2Hex(self,aR,alpha):
		""" convert lattice constants
		aR, alpha				Rhombohedral lattice constants
		returns tumpe(aH,cH)	Hexagonal lattice constants
		"""
		alpha *= math.pi / 180.0		# convert degree --> radian
		aH = 2.0 * aR * math.sin(alpha/2)
		cH = aR * math.sqrt( 3.0 + 6.0 * math.cos(alpha) )
		return (aH,cH)

	def Rhom2HexFractional(self, printIt=True):
		"""
		This is just a DEMONSTRATION, change it to make it useful
		converts rhombohedral --> hexagonal, fractional coordinates
		"""
		directR = np.matrix(self.direct)			# Obverse Rhombohedral lattice vectors
		H2Ctrans = np.matrix([ [2,-1,-1], [1,1,-2], [1,1,1] ])
		H2Ctrans = H2Ctrans / 3.0
		directH = directR * np.linalg.inv(H2Ctrans)	# Hexagonal direct lattice from Obverse Rhombohedral

		for atom in self.atoms:
			xyzR = np.matrix([atom.x, atom.y, atom.z])
			xyzH = np.linalg.inv(directH) * directR * xyzR.T
			xyzH = xyzH.T
			arrayZeroThresh(xyzH)
			xyzH = np.mod(xyzH, 1.0)			# fractional hexagonal coordinates in one cell
			arrayZeroThresh(xyzH)

			if printIt: print ('     fractional: Rhom=%s  -->  Hex=%s' % (xyzR, xyzH))

	def Hex2RhomFractional(self, printIt=True):
		"""
		This is just a DEMONSTRATION, change it to make it useful
		converts hexagonal --> rhombohedral, fractional coordinates
		"""
		directH = np.matrix(self.direct)			# hexagonal lattice vectors
		H2Ctrans = np.matrix([ [2,-1,-1], [1,1,-2], [1,1,1] ])
		H2Ctrans = H2Ctrans / 3.0
		directR = directH * H2Ctrans			# Obverse Rhombohedral direct lattice from Hexagonal

		for atom in self.atoms:
			xyzH = np.matrix([atom.x, atom.y, atom.z])
			xyzR = np.linalg.inv(directR) * directH * xyzH.T
			xyzR = xyzR.T
			arrayZeroThresh(xyzR)
			xyzR = np.mod(xyzR, 1.0)			# fractional rhombohedral coordinates in one cell
			arrayZeroThresh(xyzR)

			if printIt: print ('     fractional: Hex=%s  -->  Rhom=%s' % (xyzH, xyzR))


	def _ALLOW_FC(self,h,k,l):
		""" face-centered, hkl must be all even or all odd """
		return (h+k) % 2 == 0 and (k+l) % 2 == 0

	def _ALLOW_BC(sefl,h,k,l):
		""" body-centered, !mod(round(h+k+l),2), sum must be even """
		return (h+k+l) % 2 == 0

	def _ALLOW_CC(self,h,k,l):
		""" C-centered, !mod(round(h+k),2) """
		return ((h+k) % 2)==0

	def _ALLOW_AC(self,h,k,l):
		""" A-centered, !mod(round(k+l),2) """
		return ((k+l) % 2)==0

	def _ALLOW_RHOM_HEX(self,h,k,l):
		""" rhombohedral hexagonal, allowed are -H+K+L=3n or H-K+L=3n """
		return (-h+k+l)%3 == 0 or (h-k+l)%3 == 0

	def _ALLOW_HEXAGONAL(self,h,k,l):
		""" hexagonal, forbidden are: H+2K=3N with L odd """
		return bool((h+2*k)%3) or not bool(l%2)


	def findClosestHKL(self,dIN):
		""" Find the hkl(s) closest to given d-spacing (nm) """
		hmax = math.ceil(self.dSpacing((1,0,0))/dIN) + 1
		kmax = math.ceil(self.dSpacing((0,1,0))/dIN) + 1
		lmax = math.ceil(self.dSpacing((0,0,1))/dIN) + 1

		saved = list()						# list of hkl closest to dIN, each element is a dict
		err0 = float('inf')
		if len(self.atoms)>1:	N = float(len(self.atoms))
		else:					N = 1.0
		for l in symrange(lmax):				# 0,1,-1,2,-2,3,-3,... lmax,-lmax
			for k in symrange(kmax):
				for h in symrange(hmax):
					Fhkl = self.Fstruct((h,k,l))
					if abs(Fhkl)/N < self.allowed_F_N: continue	# only consider allowed hkl (if too small skip it)
					dhkl = self.dSpacing((h,k,l))
					derr = abs(dhkl-dIN)
					if derr<err0:			# found a new best one
						err0 = derr
						saved = list()
					if derr<=err0:			# a duplicate best one
						saved.append({'h':h, 'k':k, 'l':l, 'dhkl':dhkl, 'Fhkl':Fhkl})

		# remove entry from saved if hkl == -hkl
		short = list()						# the new shorter list
		for d in saved:
			# check if -d is in short
			skip = False
			for ds in short:
				skip = skip or (abs(ds['h']+d['h']) + abs(ds['k']+d['k']) + abs(ds['l']+d['l']))==0
			if not skip: short.append(d)

		return short


	def mu(self,keV):
		""" returns the absorption factor mu (1/micron),
		transmission = exp(-mu * t)
		keV is required.

		f" = sigma / (2 * re * lambda)  in the forward direction (Q=0)
		sigma = f" * (2 * re * lambda)
		sigma = mu/n = mu*Vc				# 1/V = n, number density
		mu = 2*re*lambda*f" / Vc

		Note, f"==0 --> no absorption, mu-->0, (1/mu --> inf)
		also f" cannot be negative (or we have a source, not absorption)
		"""
		try:
			if keV<=0 or math.isnan(keV) or math.isinf(keV): raise		# energy must be positive definite, also fails on strings or None
		except:	return float('nan')				# energy is invalid 
		
		Fpp = 0.0
		for atom in self.atoms:					# accumulate imag part of fatom at Q=0
			Fpp += atom.fatom(0.0,keV).imag * (atom.mult * atom.occ)

		if not(Fpp >= 0.0): return float('nan')			# f" is negative or nan, both are invalid
		mu = 2*re_nm*(hc_keVnm/keV)*Fpp / (self.Vc)

		return (mu*1000)						#  convert mu from 1/nm --> 1/µm


	def __str__(self):
		""" Return string value for Lattice. """
		return str(self).encode('ascii', errors='backslashreplace')

	def __str__(self):
		""" Return str value for Lattice. """
		super3 = u'\u00B3'		# str superscript 3
		out = u''
		if len(self.desc):		out = u'"%s"   ' % self.desc
		out += u'Space Group=%s   %s   %s       Vc = %g (nm%s)' % (self.SpaceGroupID,self.latticeSystemName, self.getHMboth(self.SpaceGroupID),self.Vc,super3)
		if self.density > 0:	out += u'       density = %g (g/cm%s)' % (self.density,super3)
		if not (self.alphaT is None):
			superMinus1 = u'\u207B\u00B9'		# str superscript -1
			alpha = u'\u03B1'					# str greek alpha
			degree = u'\u00B0'					# str degree symbol
			out += u'     %s = %g (%sC%s)' % (alpha,self.alphaT,degree,superMinus1)	# coefficient of thermal expansion
		if self.isValidExpansionTable(): out += u'     [thermal expansion table, %d pnts]' % (len(self.expansionTable),)

		try:
			if self.databaseCodes:
				temp = ''
				for code,val in self.databaseCodes: temp += u'%s="%s"' % (str(code), str(val))
				if temp: out += u'\n'+temp
		except: pass

		a = self.a
		b = self.b
		c = self.c

		if self.system == self.CUBIC:
			out += '\nlattice constant =  %.13g nm' % a
		elif self.system == self.HEXAGONAL:
			out += '\nlattice constants  a = %.13g nm, c = %.13g nm' % (a,c)
		elif self.system==self.TRIGONAL:
			if self.isRhombohedral:				# using Rhombohedral Lattice Constants
				out += '\nRhombohedral lattice constants, aRhom = %.8g nm,   alpha(Rhom) = %.8g\n' % (a, self.alpha)
				(aHex,cHex) = self.Rhom2Hex(a,self.alpha)
				out += '\n   Hexagonal lattice constants  a = %.13g nm, c = %.13g nm' % (aHex,cHex)
			else:								# using Hexagonal Lattice Constants
				out += '\nHexagonal lattice constants  a = %.13g nm, c = %.13g nm' % (a,c)
				if self.SpaceGroupID.find(':R') >= 0:	# only possible for Space Groups [146,148,155,160,161,166,167]
					(aRhom, alphaRhom) = self.Hex2Rhom(a,c)
					out += '   Rhombohedral lattice constants, aRhom = %.8g nm,   alpha(Rhom) = %.8g\n' % (aRhom,alphaRhom)
		elif self.system == self.TETRAGONAL:
			out += '\nlattice constants  a = %.13gnm, c = %.13gnm' % (a,c)
		elif self.system == self.ORTHORHOMBIC:
			out += '\nlattice constants  a = %.13gnm, b = %.13gnm, c = %.13gnm' % (a,b,c)
		else:									# Monoclinic or Triclinic
			out += '\nlattice constants  { %.13gnm, %.13gnm, %.13gnm,   %.13g, %.13g, %.13g }' % (a,b,c,self.alpha,self.beta,self.gam)

		if not (self.Temperature0 is None):
			if self.Temperature0 >= Absolute0_C:
				Temperature = self.Temperature0		# self.Temperature0 is always C
				if Temperature < -100:	unit = 'K'	# display in Kelvin
				else:					unit = "C"
				Temperature = ConvertTemperatureUnits(Temperature,"C",unit)	# self.Temperature is always C
				out += ',   Temperature = %g %s' % (Temperature,unit)

		out += '\n'

		if len(self.atoms)<1:
			out += 'No Atoms Defined\n'
		else:
			if self.formulaStructural:
				out += 'atom type locations:\t chemical formula = "%s"\n' % self.formulaStructural
			elif len(self.formulaMin)>0:
				out += 'atom type locations:\t chemical formula = "%s"\n' % self.formulaMin
			else:
				out += 'atom type locations:\n'

			for atom in self.atoms: out += u'%s\n' % atom

			if self.bonds:
				out += '     %r bonds:\n' % (len(self.bonds),)
				for bond in self.bonds: out += str(bond) + '\n'

				# print list of those atoms not associated with a bond
				if self.unassociated:	out += 'The following atom types do not have any bonds: '+str(self.unbondedAtoms)
				else:				out += '    All atom types are associated with a bond.'
		return out


	def __repr__(self):
		""" Return printable representation for a Lattice. """
		out = 'Lattice[desc=%r, SpaceGroupID=%r' % (self.desc,self.SpaceGroupID)
		out += ', a=%r, b=%r, c=%r, alpha=%r, beta=%r, gam=%r' % (self.a,self.b,self.c,self.alpha,self.beta,self.gam)
		out +=  ', Temperature0=%r, alphaT=%r,' % (self.Temperature0, self.alphaT)
		if self.isValidExpansionTable(): out += ' [valid thermal expansion table, %r pnts]' % (len(self.expansionTable),)
		out += '\n  Vc=%r, density=%r, Vibrate=%r, haveDebyeT=%r, formulaStructural=%r, formulaMin=%r,' % (self.Vc, self.density, self.Vibrate, self.haveDebyeT,self.formulaStructural,self.formulaMin) 
		out += '\n' + self.direct2str()
		out += '\n' + self.recip2str()
		for atom in self.atoms: out += '\n%r' % atom
		for bond in self.bonds: out += '\n%r' % bond
		if len(self.atoms) or len(self.bonds): out += '\n'
		out += ']'
		return out


	def __latticeSystemNum(self):
		# returns number, 0=Triclinic,1=Monoclinic,2=Orthorhombic,3=Tetragonal,4=Trigonal,5=Hexagonal,6=Cubic
		SG = int(self.SpaceGroupID.split(':')[0])	# Space Group number, from International Tables
		if SG > 230:	raise ValueError('Space Group is not in [1,230]')
		elif SG >= 195:	return self.CUBIC
		elif SG >= 168:	return self.HEXAGONAL
		elif SG >= 143:	return self.TRIGONAL		# probably using the hexagonal cell axes
		elif SG >= 75:	return self.TETRAGONAL
		elif SG >= 16:	return self.ORTHORHOMBIC
		elif SG >= 3:	return self.MONOCLINIC
		elif SG >= 0:	return self.TRICLINIC
		else:			raise ValueError('Space Group is not in [1,230]')


	def ConvertSetting(self, target):
		"""
		Convert the current space group setting to target
		change the current SpaceGroupID to target
		change the lattice constants: a,b,c, alpha, beta, gamma
		change the direct & reciprocal latticies
		change the xyz of all the atoms
		change possibly self.desc
		"""
		source = self.SpaceGroupID						# current SpaceGroupID
		defalt = self.FindDefaultIDforSG(source)		# default SpaceGroupID

		if not self.validSpaceGroupID(source): return None		# if source is invalid, do nothing
		if not self.validSpaceGroupID(target): target = defalt	# if target is invalid, set to the default setting for this space group
		if source==target: return False					# converting to itself, nothing to do

		self.SpaceGroupID = target						# space group setting is changed

		CBM = self.GetSettingTransForm(target)			# converts Defalt --> Target
		CBM0 = self.GetSettingTransForm(source)			# converts Defalt --> Source
		cbm = CBM[0:3,0:3]								# only want the first 3 columns make a square mat
		cbm0 = CBM0[0:3,0:3]

		DL = self.direct								# the real space lattice
		GS = np.dot(np.transpose(DL), DL)				# MatrixOp/FREE GS = DL^t x DL

		# 1st convert source --> default,  GD is default metrical matrix
		cbm0t = np.transpose(cbm0)						# cbm0^t
		Inv_cbm0t = np.linalg.inv(cbm0t)				# Inv(cbm0^t)
		temp = np.dot(Inv_cbm0t,GS)						# temp = Inv(cbm0^t) x GS
		GD = np.dot(temp,np.linalg.inv(cbm0))			# GD = Inv(cbm0^t) x GS x Inv(cbm0)

		# 2nd convert default --> target,  target metrical matrix
		cbmt = np.transpose(cbm)						# cbm^t
		temp = np.dot(cbmt,GD)							# temp = cbm^t x GD
		GT = np.dot(temp,cbm)							# GT = cbm^t x GD x cbm

		# calculate the new lattice constants from target metrical matrix
		a = math.sqrt(GT.item(0,0))						# a = sqrt(GT[0][0])
		b = math.sqrt(GT.item(1,1))						# b = sqrt(GT[1][1])
		c = math.sqrt(GT.item(2,2))						# c = sqrt(GT[2][2])
		self.a = a
		self.b = b
		self.c = c
		self.alpha = math.acos( GT.item(1,2)/(b*c) ) * 180 / math.pi	# = acos( GT[1][2]/(b*c) ) * 180/pi
		self.beta  = math.acos( GT.item(0,2)/(a*c) ) * 180 / math.pi	# = acos( GT[0][2]/(a*c) ) * 180/pi
		self.gam   = math.acos( GT.item(0,1)/(a*b) ) * 180 / math.pi	# = acos( GT[0][1]/(a*b) ) * 180/pi

		self.SetSymmetryOperations(self.SpaceGroupID)	# these are reset, then calculate atom positions
		self.__ForceLatticeToStructure()
		self.__setDirectRecip()							# update the other values (Vc, direct, recip, ...)
		#	The formula for the transformation of the metrical matrix G(A) of Setting A to the metrical matrix G(B) of Setting B is (see e.g. Boisen & Gibbs [2]):
		#			G(B) = transpose(Invcbmx) * G(A) * Invcbmx
		#
		#						a•a		a•b		a•c
		#	metrical matrix =	a•b		b•b		b•c
		#						a•c		b•c		c•c
		#
		#						a^2					a*b*cos(gamma)	a*c*cos(beta)
		#	metrical matrix = 	a*b*cos(gamma)		b^2				b*c*cos(alpha)
		#						a*c*cos(beta)		b*c*cos(alpha)		c^2
		#
		#		if DL = {a,b,c}, where a,b,c are all column vectors
		#		metrical matrix = G = DL^t x DL

		# the lattice vectors have been changed, now deal with the atom positions
		# transform the coordinate of each atom:
		CC = np.dot(np.linalg.inv(CBM), CBM0)			# CC = Inv(CBM) x CBM0
		for atom in self.atoms:
			fracS = np.array( [atom.x, atom.y, atom.z, 1] )	# need the augmented xyz --> xyz1
			fracT = np.dot(CC, fracS)					# convert: source --> default --> target (only use first three of fracT)
			fracT[0] = fracT[0] - math.floor(fracT[0])	# reduce to first cell
			fracT[1] = fracT[1] - math.floor(fracT[1])
			fracT[2] = fracT[2] - math.floor(fracT[2])
			fracT[0] = 0 if (fracT[0]<1e-12) else (fracT[0] % 1)	# a fractional coord < 1e-12 is 0
			fracT[1] = 0 if (fracT[1]<1e-12) else (fracT[1] % 1)
			fracT[2] = 0 if (fracT[2]<1e-12) else (fracT[2] % 1)
			atom.x = fracT[0]
			atom.y = fracT[1]
			atom.z = fracT[2]
			if len(self.equivX1):
				atom.calcAllAtomPositions3D(self.equivX1)		# have the symmetry operation matricies, use them

		# try to fix name when changing between Hexagonal and Rhombohedral
		if source.find(':H')>0 and target.find(':R')>0:			# Hexagonal --> Rhombohedral
			self.desc = self.desc.replace('Hexagonal','Rhombohedral')
			self.desc = self.desc.replace('hexagonal','rhombohedral')
			self.desc = self.desc.replace('Hex','Rhom')
			self.desc = self.desc.replace('hex','rhom')
		if source.find(':R')>0 and target.find(':H')>0:			# Rhombohedral --> Hexagonal
			self.desc = self.desc.replace('Rhombohedral','Hexagonal')
			self.desc = self.desc.replace('rhombohedral','hexagonal')
			self.desc = self.desc.replace('Rhom','Hex')
			self.desc = self.desc.replace('rhom','hex')

		return 0




class Lattice2D(LatticeCommon, readCIF.readXTAL, LatticeBase.LatticeBase2D, bondCalc.bondCalc):
	""" A Class that the defines a crystal lattice with all of its atoms.
		It can NOT load all the information from a file
		All parameters are forced to be consistent with the space group number.
		It can also calculate the structure factor F(hk)
	"""

	def __init__(self, SpaceGroupID, LC, desc='', Temperature=None,alphaT=None,expansionTable=None,atoms=tuple(),bonds=tuple(), keV=None, allowed_F_N=0.01, databaseCodes=None, formulaStructural=None):
		"""
		LC					a tuple or list of 3 lattice constants [a,b,alpha]

		Initialize the Lattice instance.

		values that are passed to the __init__()
		self.desc = desc				# name or decription of this crystal (str)
		self.SpaceGroupID				# Space Group ID from international tables, something like "15:-b2", not just an integer anymore
		self.a = float(a)				# lattice constant (nm)
		self.b = float(b)
		self.alpha = float(alpha)		# angles (degree)
		self.alphaT = alphaT			# optional: coef of thermal expansion, a = ao*(1+alphaT*(TempC-NormalTemp_C))
		self.expansionTable				# optional: table of ∆L/L vs T an array of tuples [ (T,∆L/L) ], T in Kelvin
		self.Temperature0 = Temperature	# optional: temperature for theses values, default is NormalTemp_C (Celsius)
		self.atoms						# optional: a tuple of atomXtal's (no atoms are required)
		self.bonds						# optional: a tuple of bondType's (no bonds are required)
		self.keV						# optional: default energy used for calculating Fstruct()
		self.allowed_F_N				# optional: number of electrons/atom (e.g. |F|/Natmos) for an allowed reflection, (default=0.01)
		self.databaseCodes				# list of crystal database codes, e.g. [('ICSD','123'), ('amcsd',3344566')]
		self.formulaStructural			# structural formula, probably from  a CIF file.

		the following values are calculated at __init__()
		self.latticeSystemName			# Cubic, Hexagonal, Trigonal, Tetragonal, Orthorhombic, Monoclinic, Triclinic
		self.density					# calculated density (g/cm^2)
		self.formulaMin					# calculated minimal chemical formula for this structure
		self.direct						# calculated direct lattice (nm)
		self.recip						# calculated reciprocal lattice (1/nm), has the 2pi in it

		important methods:
		def Hex2Rhom(self,aH,cH)			# convert Hexagonal lattice constants to Rhombohedral
		def Rhom2Hex(self,aR,alpha)			# convert Rhombohedral lattice constants to Hexagonal
		def isValid(self)					# Check if lattice constants are valid, returns True if all 6 are valid
		def SetWyckoffSymbols(self, force=False):	# Sets the Wyckoff Symbol, multiplicity, and site symmetry for all of the atoms
		def FindWyckoffSymbol(self, atom):	# this tests all of the equivalent xyz for each atom
		def findClosestHK(self,dIN)			# Find the hk(s) closest to given d-spacing (nm)
		"""

		LatticeBase.LatticeBase2D.__init__(self)		# sets some big lists and provides some utility functions
		bondCalc.bondCalc.__init__(self)			# note, bond calculation is NOT done automatically, only when requested
		LatticeCommon.__init__(self, keV=keV, allowed_F_N=allowed_F_N)
		self.dim = 2
		self.read = None
		try:	a,b,alpha= LC
		except:	raise ValueError('Must have either 3 lattice constants for Lattice2D, not %r' % (LC,))

		SpaceGroupID = str(SpaceGroupID)
		try:	self.validSpaceGroupID(SpaceGroupID)		# raises exception if not a valid Space Group ID
		except:	SpaceGroupID = self.FindDefaultIDforSG(SpaceGroupID)		#   or if not an integer in [1-230] either
		self.SpaceGroupID = SpaceGroupID			# self.SpaceGroupID is now a string like "15:-b2", or 229

		self.desc = str(desc)					# name or decription of this crystal (str)
		self.a = float(a)							# lattice constant (nm)
		self.b = float(b)
		self.alpha = float(alpha)					# angles (degree)
		self.databaseCodes = databaseCodes			# list of crystal database codes, e.g. [('ICSD','123'), ('amcsd',3344566')]
		self.formulaStructural = formulaStructural
		self.atoms = atoms
		self.bonds = bonds

		if isinstance(self.formulaStructural,basestring):
			if len(self.formulaStructural) < 1 : self.formulaStructural = None

		try:									# self,
			Temperature = float(Temperature)
			if not isfinite(Temperature): raise
		except: Temperature = None				# not a valid Temperature, set to None
		if isinstance(Temperature, (int, int, float)):
			if Temperature < Absolute0_C: raise ValueError("Temperature (C) is %r, which must be >= %g" % (Temperature,Absolute0_C))
		self.Temperature0 = Temperature
		self.Temperature = Temperature

		try:
			alphaT = float(alphaT)
			if not isfinite(alphaT): raise
		except: alphaT = None					# not a valid alphaT, set to None
		self.alphaT = alphaT

		if self.isValidExpansionTable(expansionTable): self.expansionTable = expansionTable
		else: self.expansionTable = None

		self.system = self.__latticeSystemNum()		# get lattice system from SpaceGroupID
		self.latticeSystemName = self.latticeSystemNames[self.system]
		self._neqStr = 'initial value' 				# None
		self._eq_all = self._eq_desc = True

		self.SetSymmetryOperations(self.SpaceGroupID)	# these are needed to calculate the atom positions
		self.__ForceLatticeToStructure()			# force a,b, alpha to match Space Group, sets Ac, direct & recip too
		self.__setDirectRecip()					# set direct & reicp lattices, also calc Ac

		# set miscelaneous things in lattice
		self.Vibrate = self.haveDebyeT = False
		for atom in self.atoms:
			if atom.hasThermalInfo: self.Vibrate = True	# True if some Thermal vibration info present in xtal (for any atom) 
			if atom.DebyeT > 0: self.haveDebyeT = True	# True if some one of the atoms has a Debye Temperature

		for atom in self.atoms:					# check that all atoms are valid
			if len(self.equivX1): atom.calcAllAtomPositions2D(self.equivX1)	# have the symmetry operation matricies, use them
		self.calcDensity()						# now that I have all of the atom positions, can calc density
		self.MinimalChemFormula()					# set the minimal chemical formula

		# done setting, now check that everything is valid
		if not (self.a >= 0 and self.b >= 0): raise ValueError('INVALID a=%r, b=%r' % (self.a,self.b))
		if not (self.alpha > 0): raise ValueError('INVALID alpha=%r' % (self.alpha,))
		if not (self.alpha < 180): raise ValueError('INVALID alpha=%r,' % (self.alpha,))
		if (self.Vibrate or self.haveDebyeT) and len(self.atoms) < 1:
			raise ValueError("Inavlid, have Vibrate or DebyeT, but no atoms")

#			Tinfo = Vinfo = False					# check for consistent Thermal/Vibrational info
#			for atom in self.atoms:
#				if atom.bad(): raise ValueError('bad atom')
#				Tinfo = Tinfo or atom.Tinfo
#				Vinfo = Vinfo or atom.Vinfo
#			if Tinfo and Vinfo: raise ValueError('there are some atoms Vibrational info and some with Debye Temperature, cannot mix')

		labels = list()							# check for duplicate atoms labels
		for atom in self.atoms:
			labels.append(atom.label)
		if len(set(labels))<len(labels): raise ValueError('there are atoms with duplicate labels')

		self.SetWyckoffSymbols(force=False)			# Sets the Wyckoff Symbol, multiplicity, and site symmetry for all of the atoms, that have not been set yet

		#		double Unconventional00,Unconventional01,Unconventional02	// transform matrix for an unconventional unit cel
		#		double Unconventional10,Unconventional11,Unconventional12
		#		double Unconventional20,Unconventional21,Unconventional22
		#		char hashID[HASHID_LEN]	// hash function for this strucutre (needs to hold at least 64 chars), This MUST be the last item

		if not self.isValid(): raise ValueError('Lattice constants are INVALID:  a=%g, b=%g, alpha=%g' % (self.a,self.b, self.alpha))


	def isValid(self):
		""" Check if lattice constants are valid, returns True if all 6 are valid """
		self.validSpaceGroupID(self.SpaceGroupID)

		a = self.a
		b = self.b
		alpha = self.alpha

		if not isfinite(a+b+alpha): return False
		if not (a>0 and b>0 and alpha>0): return False
		if not (alpha<180): return False

		if self.system == self.Hexagonal:
			if not (a == b): return False
			if not (alpha==120.): return False
		elif self.system == self.Square:
			if not (a == b): return False
			if not (alpha==90.0): return False
		elif self.system == self.Rhombic:
			if not (a == b): return False
		elif self.system == self.Rectangular:
			if not (alpha==90.0): return False
		elif self.system == self.Oblique:
			pass

		return True


	def __ForceLatticeToStructure(self):
		""" Forces lattice constants to match the Space Group number (e.g. for cubic, forces b and c to be a, and all angles 90)
		Hexagonal		[13,14,15,16,17]	a			(a=b & alpha=120)
		Square			[10,11,12]			a			(a=b & alpha=90)
		Rhombic			[5,9]				a,alpha		(a=b)
		Rectangular		[3,4,6,7,8]			a,b			(alpha=90)
		Oblique			[1,2]				a,b,alpha
		"""
		system = self.system
		if system == self.Hexagonal:
			self.b = self.a
			self.alpha = 120
		elif system == self.Square:
			self.b = self.a
			self.alpha = 90
		elif system == self.Rhombic:	# Rhombic
			self.b = self.a
		elif system == self.Rectangular:	# Rectangular
			self.alpha = 90
		elif system == self.Oblique:		# Oblique
			pass

		# finally check for valid numbers, i.e. all greater than 0 and angles < 180
		if not(self.a > 0 or self.b > 0): 
			raise ValueError('Lattice constants must be >= 0, a=%g, b=%g' % (self.a,self.b))
		elif not ((self.alpha > 0 and self.alpha < 180)):
			raise ValueError('Lattice angle must be in [0,180 degree), alpha=%g' % (self.alpha,))


	def __setDirectRecip(self):
		""" set direct and recip lattice vectors from {a,b,alpha}, also calculates Ac """
		a = self.a
		b = self.b
		alpha = self.alpha * math.pi/180.0

		# Direct Lattice:  a=[a0,a1], b=[b0,b1], 
		a0 = a					;	a1 = 0.0
		b0 = b*math.cos(alpha)	;	b1 = b*math.sin(alpha)
		detDL = a0*b1 - b0*a1			# determinant(DL)
		self.direct = np.matrix([ [a0,b0], [a1,b1] ])
		self.Ac = detDL					# area of cell is the determinant

		# Reciprocal Lattice a*=[as0,as1], b*=[bs0,bs1]
		pv = 2*math.pi / detDL			# RL = 2*PI * (Inv(DL))^t
		as0 = b1*pv			;	as1 = -b0*pv
		bs0 = -a1*pv			;	bs1 = a0*pv
		self.recip = np.matrix([ [as0, bs0], [as1, bs1] ] )


	def __eq__(self, other):
		"""
		returns True if two Lattice classes are equal
		if desc is True, then check that descriptions are equal
		"""
		if not( type(other) is type(self) ): return NotImplemented	# can only compare objects of the same type
		other._neqStr = self._neqStr = ''

		if not( type(other) is type(self) ): return NotImplemented	# can only compare objects of the same type
		if self.SpaceGroupID != other.SpaceGroupID:
			other._neqStr = self._neqStr = 'SpaceGroupID differ, "%s" != "%s"' %(self.SpaceGroupID, other.SpaceGroupID)
			return False
		elif ( abs(self.a - other.a) + abs(self.b - other.b) ) > 1e-5:
			other._neqStr = self._neqStr = 'a, or b differ'
			return False
		elif ( abs(self.alpha - other.alpha) ) > 1e-5:
			other._neqStr = self._neqStr = 'alpha differs'
			return False
		elif self.system != other.system:
			other._neqStr = self._neqStr = 'crystal system mismatch, %r != %r' % (self.system, other.system)
			return False
		elif self.formulaMin != other.formulaMin:
			other._neqStr = self._neqStr = 'formulaMin differ'
			return False
		elif abs(self.density - other.density) > 1e-4:
			other._neqStr = self._neqStr = 'density differ'
			return False
		elif abs(self.Ac - other.Ac) > 1e-7:
			other._neqStr = self._neqStr = 'Ac differ'
			return False
		elif isinstance(self.Temperature0, (int, int, float)) and isinstance(other.Temperature0, (int, int, float)):
			if self.Temperature0>0 and other.Temperature0>0:
				if abs(self.Temperature0 - other.Temperature0) > 1e-3:
					other._neqStr = self._neqStr = "Temperature0's differ"
					return False
		elif isinstance(self.Temperature, (int, int, float)) and isinstance(other.Temperature, (int, int, float)):
			if self.Temperature>0 and other.Temperature>0:
				if abs(self.Temperature - other.Temperature) > 1e-3:
					other._neqStr = self._neqStr = 'Temperatures differ'
					return False
		elif isinstance(self.alphaT, (int, int, float)) and isinstance(other.alphaT, (int, int, float)):
			if self.alphaT>0 and other.alphaT>0:
				if abs(self.alphaT - other.alphaT) > 1e-6:
					other._neqStr = self._neqStr = 'alphaT differ'
					return False

		elif (self.expansionTable != other.expansionTable):
				other._neqStr = self._neqStr = 'expansionTable differ'
				return False

		astr = LatticeBase.atomXtal('H',(0,0,0)).atomListsDiffer(self.atoms, other.atoms)
		if len(astr)>0:
			other._neqStr = self._neqStr = astr
			return False

		bstr = LatticeBase.bondType('a','b', 1.0).bondListsDiffer(self.bonds, other.bonds)
		if len(bstr)>0:
			other._neqStr = self._neqStr = bstr
			return False

		if not (self._eq_all and other._eq_all): return True

		if self._eq_desc:
			if self.desc != other.desc:
				other._neqStr = self._neqStr = 'descriptions differ'
				return False

		elif not (self.databaseCodes is None and other.databaseCodes is None):
			if set(self.databaseCodes) != set(other.databaseCodes):
				other._neqStr = self._neqStr = 'databaseCodes differ'
				return False
		elif not (self.formulaStructural is None and other.formulaStructural is None):
			if self.formulaStructural != other.formulaStructural:
				other._neqStr = self._neqStr = 'formulaStructural differ'
				return False
		elif isinstance(self.keV, (int, int, float)) and isinstance(other.keV, (int, int, float)):
			if self.keV>0 and other.keV>0:
				if abs(self.keV - other.keV) > 1e-4: 
					other._neqStr = self._neqStr = 'keV differ'
					return False

		return True


	def findClosestHK(self,dIN):
		""" Find the hk(s) closest to given d-spacing (nm) """
		hmax = math.ceil(self.dSpacing((1,0))/dIN) + 1
		kmax = math.ceil(self.dSpacing((0,1))/dIN) + 1

		saved = list()						# list of hk closest to dIN, each element is a dict
		err0 = float('inf')
		if len(self.atoms)>1:	N = float(len(self.atoms))
		else:					N = 1.0
		for k in symrange(kmax):
			for h in symrange(hmax):
				Fhk = self.Fstruct((h,k))
				if abs(Fhk)/N < self.allowed_F_N: continue	# only consider allowed hk (if too small skip it)
				dhk = self.dSpacing((h,k))
				derr = abs(dhk-dIN)
				if derr<err0:				# found a new best one
					err0 = derr
					saved = list()
				if derr<=err0:				# a duplicate best one
					saved.append({'h':h, 'k':k, 'dhk':dhk, 'Fhk':Fhk})

		# remove entry from saved if hk == -hk
		short = list()						# the new shorter list
		for d in saved:
			# check if -d is in short
			skip = False
			for ds in short:
				skip = skip or (abs(ds['h']+d['h']) + abs(ds['k']+d['k']))==0
			if not skip: short.append(d)

		return short


	def __str__(self):
		""" Return string value for Lattice. """
		return str(self).encode('ascii', errors='backslashreplace')

	def __str__(self):
		""" Return str value for Lattice. """
		a = self.a
		b = self.b

		out = u''
		if len(self.desc):		out = u'"%s"   ' % self.desc
#		out += 'Space Group=%s   %s   %s       Ac = %g (nm^2)' % (self.SpaceGroupID,self.latticeSystemName, self.getHMboth(self.SpaceGroupID),self.Ac)
#		if self.density > 0:	out += '       density = %g (g/cm^2)' % self.density
		super2 = u'\u00B2'		# str superscript 2
		out += 'Space Group=%s   %s   %s       Ac = %g (nm%s)' % (self.SpaceGroupID,self.latticeSystemName, self.getHMboth(self.SpaceGroupID),self.Ac,super2)
		if self.density > 0:	out += '       density = %g (g/cm%s)' % (self.density,super2)

		if not (self.alphaT is None):
			superMinus1 = u'\u207B\u00B9'		# str superscript -1
			alpha = u'\u03B1'					# str greek alpha
			degree = u'\u00B0'					# str degree symbol
			out += u'     %s = %g (%sC%s)' % (alpha,self.alphaT,degree,superMinus1)	# coefficient of thermal expansion
		if self.isValidExpansionTable(): out += u'     [thermal expansion table, %d pnts]' % (len(self.expansionTable),)

		if self.databaseCodes:
			temp = ''
			for code,val in self.databaseCodes: temp += u'%s="%s"' % (str(code), str(val))
			if temp: out += u'\n'+temp

		if self.system == self.Square:
			out += '\nlattice constant =  %.13g nm' % (a,)
		elif self.system == self.Hexagonal:
			out += '\nlattice constants  a = %.13g nm' % (a,)
		elif self.system == self.Rhombic:
			out += '\nlattice constants  a = %.13gnm, b = %.13gnm' % (a,b)
		elif self.system == self.Rectangular:
			out += '\nlattice constants  a = %.13gnm, b = %.13gnm' % (a,b)
		else:									# Monoclinic or Triclinic
			out += '\nlattice constants  { %.13gnm, %.13gnm,   %.13g }' % (a,b,self.alpha)

		if not (self.Temperature0 is None):
			if self.Temperature0 >= Absolute0_C:
				Temperature = self.Temperature0		# self.Temperature0 is always C
				if Temperature < -100:	unit = 'K'	# display in Kelvin
				else:					unit = "C"
				Temperature = ConvertTemperatureUnits(Temperature,"C",unit)	# self.Temperature0 is always C
				out += ',   Temperature = %g %s' % (Temperature,unit)

		out += '\n'

		if len(self.atoms)<1:
			out += 'No Atoms Defined\n'
		else:
			if self.formulaStructural:
				out += 'atom type locations:\t chemical formula = "%s"\n' % self.formulaStructural
			elif len(self.formulaMin)>0:
				out += 'atom type locations:\t chemical formula = "%s"\n' % self.formulaMin
			else:
				out += 'atom type locations:\n'

			for atom in self.atoms: out += '%s\n' % atom

			if self.bonds:
				out += '     %r bonds:\n' % (len(self.bonds),)
				for bond in self.bonds: out += str(bond) + '\n'

				# print list of those atoms not associated with a bond
				if self.unassociated:	out += 'The following atom types do not have any bonds: '+str(self.unbondedAtoms)
				else:					out += '    All atom types are associated with a bond.'
		return out


	def __repr__(self):
		""" Return printable representation for a Lattice. """
		out = 'Lattice[desc=%r, SpaceGroupID=%r' % (self.desc,self.SpaceGroupID)
		out += ', a=%r, b=%r, alpha=%r' % (self.a,self.b,self.alpha)
		out +=  ', Temperature0=%r, alphaT=%r,' % (self.Temperature0, self.alphaT)
		if self.isValidExpansionTable(): out += ' [valid thermal expansion table, %r pnts]' % (len(self.expansionTable),)
		out += '\n  Ac=%r, density=%r, Vibrate=%r, haveDebyeT=%r, formulaStructural=%r, formulaMin=%r,' % (self.Ac, self.density, self.Vibrate, self.haveDebyeT,self.formulaStructural,self.formulaMin) 
		out += '\n' + self.direct2str()
		out += '\n' + self.recip2str()
		for atom in self.atoms: out += '\n%r' % atom
		for bond in self.bonds: out += '\n%r' % bond
		if len(self.atoms) or len(self.bonds): out += '\n'
		out += ']'
		return out


	def __latticeSystemNum(self):
		""" returns number, 0=Oblique,1=Rectangular,2=Rhombic,3=Square,4=Hexagonal """
		SG = int(self.SpaceGroupID.split(':')[0])	# Space Group number, from International Tables
		if SG in [13,14,15,16,17]:		return self.Hexagonal
		elif SG in [10,11,12]:			return self.Square
		elif SG in [5,9]:				return self.Rhombic
		elif SG in [3,4,6,7,8]:			return self.Rectangular
		elif SG in [1,2]:				return self.Oblique
		else:			raise ValueError('Space Group=%r is not in [1,17]' % (SG,))




# this is a function (not a class) that returns a Lattice3D or Lattice2D object
def LatticeFile(file='', keV=None, allowed_F_N=0.01):
	"""
	A function that the defines a crystal lattice with all of its atoms.
	It can load all the information from a file
	All parameters are forced to be consistent with the space group number.

	Initialize the Lattice instance.
	values that are passed to the __init__()
	file			name of file to read
	keV				optional: default energy used for calculating Fstruct() & mu()
	allowed_F_N		optional: number of electrons/atom (e.g. |F|/Natmos) for an allowed reflection, (default=0.01)

	use:   lat = LatticeFile(fileName)			# to read a lattice of 2D or 3D
	"""

	try:	allowed_F_N = float(allowed_F_N)	# an allowed reflection has |F|/Natoms > ALLOWED_F_N, must have at least 0.01 electrons/atom
	except: allowed_F_N = 0.01

	try:
		if keV<=0 or math.isnan(keV) or math.isinf(keV): raise		# energy must be positive definite, also fails on strings or None
	except:	keV = None

	cif = readCIF.readXTAL(file).read()

	try:	dim = cif['dim']
	except:	dim = 3

	SpaceGroupID = cif['SpaceGroupID']
	desc = cif['desc']
	a = cif['a']							# lattice constant (nm)
	b = cif['b']
	alpha = cif['alpha']					# angles (degree)

	try:	databaseCodes = cif['databaseCodes']
	except:	databaseCodes = None
	try:	formulaStructural = cif['formula']
	except:	formulaStructural = None
	try:	alphaT = cif['alphaT']
	except:	alphaT = None
	try:	expansionTable = cif['expansionTable']
	except:	expansionTable = None
	try:	Temperature = cif['Temperature']	# in Celsius
	except:	Temperature = None
	atoms = cif['atoms']
	bonds = cif['bonds']
	if dim == 3:
		c = cif['c']
		beta = cif['beta']
		gam = cif['gamma']

	if dim == 3:
		LC = (a,b,c,alpha,beta,gam)
		lat = Lattice3D(SpaceGroupID, LC, desc, Temperature,alphaT,expansionTable,atoms,bonds, keV, allowed_F_N, databaseCodes, formulaStructural)
	elif dim == 2:
		LC = (a,b,alpha)
		lat = Lattice2D(SpaceGroupID, LC, desc, Temperature,alphaT,expansionTable,atoms,bonds,keV, allowed_F_N, databaseCodes, formulaStructural)
	else:
		raise ValueError('LatticeFile(), dim must be 2 or 3, not %r' %(dim,))

	for atom in lat.atoms:
		siteSym = lat.GetSiteSymmetry(None,atom.WyckoffSymbol)
		if siteSym:	atom.siteSymmetry = siteSym
		else:		atom.siteSymmetry = None

	try:
		fileChecking = cif['fileChecking']
		if fileChecking: lat.fileChecking = fileChecking	# set value if fileChecking exists, and it is NOT empty
	except:	pass

	return lat




# this is a function (not a class) that returns a Lattice3D or Lattice2D object
def Lattice(SpaceGroupID='', LC=None, desc='', atoms=tuple(),bonds=tuple(), Temperature=None, alphaT=None, expansionTable=None, keV=None, allowed_F_N=0.01, databaseCodes=None, formulaStructural=None, file=''):
	"""
	file				name of file to read from, either *.xml or *.cif
	NOTE: if file is not empty, then only the arguments {keV & allowed_F_N} are used, all others are ignored.

	if not reading from a file, then SpaceGroupID, and LC are required
	SpaceGroupID		Space Group ID from international tables, something like "15:-b2", not just an integer anymore
	LC					a tuple or list of lattice constants [a,b,c,alpha,beta,gamma] or [a,b,alpha], this determines DIMENSION 2 or 3
	desc				optional: name or decription of this crystal
	alphaT				optional: coef of thermal expansion, a = ao*(1+alphaT*(TempC-NormalTemp_C))
	expansionTable		optional: table of ∆L/L vs T an array of tuples [ (T,∆L/L) ], T in Kelvin
	Temperature			optional: temperature for theses values, default is NormalTemp_C (Celsius)
	atoms				optional: a tuple of atomXtal's (no atoms are required)
	bonds				optional: a tuple of bondType's (no bonds are required)
	keV					optional: default energy used for calculating Fstruct() & mu()
	allowed_F_N			optional: number of electrons/atom (e.g. |F|/Natmos) for an allowed reflection, (default=0.01)
	databaseCodes		optional: list of crystal database codes, e.g. [('ICSD','123'), ('amcsd',3344566')]
	formulaStructural	optional: structural formula, probably from  a CIF file.
	"""
	try:
		if not isinstance(file, basestring): raise		# file must be 'string' type
	except:	file = ''

	try:
		if len(file):		pass			# input says read a file
		elif len(LC)==6:	dim = 3		# input looks like 3D lattice
		elif len(LC)==3:	dim = 2		# input looks like 2D lattice
		else:				raise		# cannot figure out from the input
	except:
		raise ValueError('Must have either 6 lattice constants for 3D, or 3 constants for 2D, not %r' % (LC,))

	if file:						# read from a file
		return LatticeFile(file=file, keV=keV, allowed_F_N=allowed_F_N)
	elif dim==3:					# 3D lattice
		return Lattice3D(SpaceGroupID, LC, desc, Temperature,alphaT,expansionTable, atoms, bonds,keV, allowed_F_N, databaseCodes, formulaStructural)
	elif dim==2:					# 2D lattice
		return Lattice2D(SpaceGroupID, LC, desc, Temperature,alphaT,expansionTable, atoms, bonds, keV, allowed_F_N, databaseCodes, formulaStructural)
	else:
		raise ValueError('Must have either 6 lattice constants for 3D, or 3 constants for 2D, not %r' % (LC,))




"""
some useful utility type routines:
separate utilities:
zeroOut(value)					# sets values close enough to zero to really zero
isfinite(x)						# True if x is a number (not None) and not Inf or NaN
"""


def isfinite(x):
	""" Returns True if x is a finite number (int or float), False if not a number or Inf or NaN """
	try:
		x = float(x)
		if math.isnan(x) or math.isinf(x): raise
		return True
	except:
		return False


def isnonzero(x):
	if not isfinite(x): return False
	if float(x)==0.0 : return False
	return True


def zeroOut(val):
	""" sets numbers close enough to zero to really zero """
	if abs(val)<1e-13: return 0.0
	else:	return val


def arrayZeroThresh(m,threshold=1e-13):
	""" set all values with absolute value less than threshold to zero """
	for x in np.nditer(m, op_flags=['readwrite']):
		if abs(x)<threshold: x[...] = 0


def ZfromLabel(label):
	""" Try to find the atomic number from a label """
	if len(label)<1: return -1
	symb = label[0].upper()
	if len(label) > 1:
		if label[1] in string.ascii_letters:
			symb += label[1].lower()

	try:	Zatom = atomGeneral.baseAtom.symbols.index(symb)
	except:	Zatom = -1
	return Zatom




if __name__ == '__main__':
	"""
	Main function for Lattice.py.

	Test cases for Lattice class to verify correct behavior.
	"""
	testing = JZTtesting(__file__)
	degree = u'\u00B0'					# str degree symbol


	def make_Silicon(setting=1):		# 1-->227:1,  2-->227:2
		id = '227:1'
		xyz = (0,0,0)
		if setting == 2:
			id = '227:2'
			xyz = (0.125,0.125,0.125)
		atomSi = LatticeBase.atomXtal('Si',xyz,WyckoffSymbol='a',DebyeT=645)
		bondSi = LatticeBase.bondType('Si','Si', 0.23517)
		return Lattice(id, (0.54310206,0,0, 0,0,0), desc='Silicon',Temperature=NormalTemp_C,alphaT=2.56e-6, atoms=(atomSi,), bonds=(bondSi,))

	def make_GaAs():
		atomGa = LatticeBase.atomXtal('Ga001',(0,0,0),WyckoffSymbol='a',DebyeT=370)
		atomAs = LatticeBase.atomXtal('As001',(0.25,0.25,0.25),WyckoffSymbol='c',DebyeT=370.1)
		bondGaAs = LatticeBase.bondType('Ga001','As001',0.2448)
		return Lattice(216, (0.56534,0,0, 0,0,0), desc='GaAs',atoms=(atomGa,atomAs),bonds=(bondGaAs,))

	def make_SapphireHex():
		atomAl = LatticeBase.atomXtal('Al1',(0,0,0.352), WyckoffSymbol='c', valence=3, Uij=(0.0000277, 0.0000277, 0.0000296, 0.00001385, 0, 0))
		atomO = LatticeBase.atomXtal('O1',(0.306,0,0.25), WyckoffSymbol='e', valence=-2, Uij=(0.0000327, 0.0000345, 0.0000362, 0.00001725, 0.000003, 0.000006))
		return Lattice('167:H', (0.47589,0.47589,1.2991, 90,90,120), desc='Sapphire,Corundum (hexagonal)',atoms=(atomAl,atomO))

	def make_SapphireRhom():
		atomAl = LatticeBase.atomXtal('Al1',(0.3523,0.3523,0.3523), WyckoffSymbol='c', valence=+3,DebyeT=1047)
		atomO = LatticeBase.atomXtal('O1',(0.5564,0.9436,0.25), WyckoffSymbol='e', valence=-2,DebyeT=1047)
		aH = 0.47589
		cH = 1.2991
		aRhom = math.sqrt(3*(aH*aH) + (cH*cH))/3
		alphaRhom = 2*math.asin(1.5/math.sqrt(3+(cH/aH)**2)) * 180/math.pi
		return Lattice('167:R', (aRhom,aRhom,aRhom, alphaRhom,alphaRhom,alphaRhom), desc='Sapphire (Rhombohedral)',atoms=(atomAl,atomO))

	def make_YBCObonds():
		bond1 = LatticeBase.bondType('Y','O3', 0.2418)
		bond2 = LatticeBase.bondType('Y','O4', 0.2399)
		bond3 = LatticeBase.bondType('Ba','O1', 0.2891)
		bond4 = LatticeBase.bondType('Ba','O2', 0.275)
		bond5 = LatticeBase.bondType('Ba','O3', 0.298)
		bond6 = LatticeBase.bondType('Ba','O4', 0.2948)
		bond7 = LatticeBase.bondType('Cu1','O1', 0.1947)
		bond8 = LatticeBase.bondType('Cu1','O2', 0.1834)
		bond9 = LatticeBase.bondType('Cu2','O2', 0.2341)
		bond10 = LatticeBase.bondType('Cu2','O3', 0.1929)
		bond11 = LatticeBase.bondType('Cu2','O4', 0.1961)
		return (bond1,bond2,bond3,bond4,bond5,bond6,bond7,bond8,bond9,bond10,bond11)

	def make_YBCO():
		atomY = LatticeBase.atomXtal('Y',(0.5, 0.5, 0.5),WyckoffSymbol='h', valence=2)
		atomBa = LatticeBase.atomXtal('Ba',(0.5, 0.5, 0.185),WyckoffSymbol='t', valence=2)
		atomCu1 = LatticeBase.atomXtal('Cu1',(0.0, 0.0, 0.0),WyckoffSymbol='a', valence=2)
		atomCu2 = LatticeBase.atomXtal('Cu2',(0.0, 0.0, 0.3565),WyckoffSymbol='q', valence=3)
		atomO1 = LatticeBase.atomXtal('O1',(0.0, 0.5, 0.0), WyckoffSymbol='e', valence=-2)
		atomO2 = LatticeBase.atomXtal('O2',(0.0, 0.0, 0.1566), WyckoffSymbol='q', valence=-2)
		atomO3 = LatticeBase.atomXtal('O3',(0.5, 0.0, 0.3776), WyckoffSymbol='s', valence=-2)
		atomO4 = LatticeBase.atomXtal('O4',(0.0, 0.5, 0.3765), WyckoffSymbol='r', valence=-2)
		atoms = (atomY,atomBa,atomCu1,atomCu2,atomO1,atomO2,atomO3,atomO4)
		bonds = make_YBCObonds()
		return Lattice(47, (0.3827,0.3893,1.1699, 90,90,90), desc='YBa2Cu3O7',atoms=atoms,bonds=bonds)

	def make_Pu():
		atomPu1 = LatticeBase.atomXtal('Pu',(0.345,0.25,0.152))
		atoms = (atomPu1,)
		return Lattice(11, (0.6183,0.4822,1.0963, 90,101.79,90), desc='alpha-Pu',atoms=atoms)
		return Lattice(47, (0.3827,0.3893,1.1699, 90,90,90), desc='YBa2Cu3O7',atoms=atoms,bonds=bonds)

	def make_Pigeonite():
		atomMg1 = LatticeBase.atomXtal('Mg1',(0.25080,0.65480,0.23280), occ=0.72000,Uij=(0.00729e-3,0.00649e-3,0.00977e-3, 0.00042e-3,0.00301e-3,0.00023e-3))
		atomFe1 = LatticeBase.atomXtal('Fe1',(0.25080,0.65480,0.23280), occ=0.28000,Uij=(0.00729e-3,0.00649e-3,0.00977e-3, 0.00042e-3,0.00301e-3,0.00023e-3))
		atomFe2 = LatticeBase.atomXtal('Fe2',(0.25640,0.01830,0.23080), occ=0.76000,Uij=(0.01201e-3,0.01826e-3,0.01428e-3, 0.00209e-3,0.00162e-3,0.00113e-3))
		atomCa2 = LatticeBase.atomXtal('Ca2',(0.25640,0.01830,0.23080), occ=0.18000,Uij=(0.01201e-3,0.01826e-3,0.01428e-3, 0.00209e-3,0.00162e-3,0.00113e-3))
		atomMg2 = LatticeBase.atomXtal('Mg2',(0.25640,0.01830,0.23080), occ=0.06000,Uij=(0.01201e-3,0.01826e-3,0.01428e-3, 0.00209e-3,0.00162e-3,0.00113e-3))
		atomSiA = LatticeBase.atomXtal('SiA',(0.04270,0.33980,0.27970), occ=1.00000,Uij=(0.00729e-3,0.00609e-3,0.00864e-3,-0.00042e-3,0.00232e-3,-0.00271e-3))
		atomSiB = LatticeBase.atomXtal('SiB',(0.55040,0.83670,0.23720), occ=1.00000,Uij=(0.00600e-3,0.00649e-3,0.00651e-3,-0.00167e-3,0.00185e-3,0.00135e-3))
		atomO1A = LatticeBase.atomXtal('O1A',(0.86590,0.34040,0.17150), occ=1.00000,Uij=(0.00472e-3,0.00933e-3,0.00839e-3,-0.00167e-3,0.00070e-3,-0.00293e-3))
		atomO2A = LatticeBase.atomXtal('O2A',(0.12200,0.49700,0.33060), occ=1.00000,Uij=(0.01758e-3,0.00528e-3,0.00952e-3,-0.00083e-3,0.00742e-3,-0.00180e-3))
		atomO3A = LatticeBase.atomXtal('O3A',(0.10370,0.26330,0.57790), occ=1.00000,Uij=(0.00600e-3,0.01217e-3,0.01516e-3,-0.00250e-3,0.00185e-3,0.00519e-3))
		atomO1B = LatticeBase.atomXtal('O1B',(0.37430,0.83420,0.13440), occ=1.00000,Uij=(0.00986e-3,0.00649e-3,0.00701e-3, 0.00125e-3,0.00394e-3,-0.00158e-3))
		atomO2B = LatticeBase.atomXtal('O2B',(0.62900,0.98770,0.37650), occ=1.00000,Uij=(0.00943e-3,0.01826e-3,0.01741e-3,-0.00751e-3,0.00765e-3,-0.00744e-3))
		atomO3B = LatticeBase.atomXtal('O3B',(0.60530,0.70870,0.47730), occ=1.00000,Uij=(0.00429e-3,0.01542e-3,0.01328e-3,-0.00209e-3,0.00070e-3,0.00541e-3))
		atoms = (atomMg1,atomFe1,atomFe2,atomCa2,atomMg2,atomSiA,atomSiB,atomO1A,atomO2A,atomO3A,atomO1B,atomO2B,atomO3B)
		return Lattice(14, (0.9706,0.8950,0.5246, 90,108.59,90), desc='Pigeonite',atoms=atoms, databaseCodes=[('amcsd',209)])

	def make_Autunite():
		atomU = LatticeBase.atomXtal('U',(0.1250,0.5412,0.7498), Uiso=0.00012)
		atomP = LatticeBase.atomXtal('P',(0.1245,0.5003,0.2478), Uiso=0.00013)
		atomCa = LatticeBase.atomXtal('Ca',(0.1251,0.7500,0.4501), Uiso=0.00029, occ=0.860)
		atomO1 = LatticeBase.atomXtal('O1',(0.1235,0.4551,0.7482), Uiso=0.00026)
		atomO2 = LatticeBase.atomXtal('O2',(0.1250,0.6278,0.7472), Uiso=0.00021)
		atomO3 = LatticeBase.atomXtal('O3',(0.1252,0.544,0.0733), Uiso=0.00029)
		atomO4 = LatticeBase.atomXtal('O4',(0.0373,0.456,0.2451), Uiso=0.00028)
		atomO5 = LatticeBase.atomXtal('O5',(0.2118,0.4557,0.2553), Uiso=0.00032)
		atomO6 = LatticeBase.atomXtal('O6',(0.1206,0.5452,0.4226), Uiso=0.00023)
		atomO7 = LatticeBase.atomXtal('O7',(0.7591,0.25,0.2851), Uiso=0.00041)
		atomO8 = LatticeBase.atomXtal('O8',(0.2368,0.6647,0.351), Uiso=0.00072)
		atomO9 = LatticeBase.atomXtal('O9',(0.0126,0.6645,0.3438), Uiso=0.00063)
		atomO10 = LatticeBase.atomXtal('O10',(0.0002,0.25,0.2833), Uiso=0.00055)
		atomO11 = LatticeBase.atomXtal('O11',(0.1263,0.75,0.0757), Uiso=0.00039)
		atomO12 = LatticeBase.atomXtal('O12',(0.3257,0.6614,-0.0255), Uiso=0.00062)
		atomO13 = LatticeBase.atomXtal('O13',(0.0759,0.3379,0.0243), Uiso=0.00057)
		atomH1 = LatticeBase.atomXtal('H1',(0.726,0.283,0.222), Uiso=0.0005)
		atomH2 = LatticeBase.atomXtal('H2',(0.197,0.633,0.412), Uiso=0.0005)
		atomH3 = LatticeBase.atomXtal('H3',(0.221,0.654,0.215), Uiso=0.0005)
		atomH4 = LatticeBase.atomXtal('H4',(0.033,0.6191,0.335), Uiso=0.0005)
		atomH5 = LatticeBase.atomXtal('H5',(0.008,0.665,0.201), Uiso=0.0005)
		atomH6 = LatticeBase.atomXtal('H6',(0.037,0.2851,0.233), Uiso=0.0005)
		atomH7 = LatticeBase.atomXtal('H7',(0.130,0.7056,0.044), Uiso=0.0005)
		atomH8 = LatticeBase.atomXtal('H8',(0.272,0.674,0.058), Uiso=0.0005)
		atomH9 = LatticeBase.atomXtal('H9',(0.3972,0.655,-0.027), Uiso=0.0005)
		atomH10 = LatticeBase.atomXtal('H10',(0.068,0.3819,0.075), Uiso=0.0005)
		atomH11 = LatticeBase.atomXtal('H11',(0.1483,0.336,0.022), Uiso=0.0005)
		atoms = (atomU,atomP,atomCa,atomO1,atomO2,atomO3,atomO4,atomO5,atomO6,atomO7,atomO8,atomO9,atomO10,atomO11,atomO12,atomO13,atomH1,atomH2,atomH3,atomH4,atomH5,atomH6,atomH7,atomH8,atomH9,atomH10,atomH11)
		return Lattice(62, (1.40135,2.07121,0.69959, 90,90,90), desc='Autunite',atoms=atoms, databaseCodes=[('amcsd',2977)], formulaStructural='Ca[(UO2)(PO4)]2(H2O)11')

	def make_PZT_hex():
		atomPb = LatticeBase.atomXtal('Pb',(0,0,0.28422))
		atomZr = LatticeBase.atomXtal('Zr',(0,0,0.01512))
		atomO  = LatticeBase.atomXtal('O',(0.14526,0.31851,0.0833))
		return Lattice('167:H', (0.5832,0.5832,1.4425, 90,90,120), desc='PZT (hex axes, hard to index)',atoms=(atomPb,atomZr,atomO))

	def make_NiTi():
		atomNi = LatticeBase.atomXtal('Ni(1)',(0.0,0.0,0.0), occ=1, Uiso=0.005/100)
		atomTi = LatticeBase.atomXtal('Ti(2)',(0.5,0.5,0.5), occ=1, Uiso=0.005/100)
		atoms = (atomNi,atomTi)
		return Lattice(221, (0.3016,0.3016,0.3016, 90,90,90), desc='NiTi_Cubic',atoms=atoms)

	def make_V2O3():
		atomV = LatticeBase.atomXtal('V',(0.3449,0.009,0.2983),valence=3)
			# <WyckoffSymbol>f</WyckoffSymbol>
		atomO1 = LatticeBase.atomXtal('O1',(0.407,0.845,0.645),valence=-2)
			# <WyckoffSymbol>f</WyckoffSymbol>
		atomO2 = LatticeBase.atomXtal('O2',(0.25,0.183),0,valence=-2)
			# <WyckoffSymbol>e</WyckoffSymbol>
		atoms = (atomV,atomO1,atomO2)
		return Lattice('15:b3', (0.72727,0.50027,0.55432, 90,96.762,90), desc='V2O3 - LT',atoms=atoms)

	def make_V2O3_monoclinic(v_label):
		atomV = LatticeBase.atomXtal(v_label,(0.3449,0.009,0.2983), valence=3, WyckoffSymbol='f')
		atomO1 = LatticeBase.atomXtal('O1',(0.407,0.845,0.645), valence=-2, WyckoffSymbol='f')
		atomO2 = LatticeBase.atomXtal('O2',(0.25,0.183,0), valence=-2, WyckoffSymbol='e')
		atoms = (atomV,atomO1,atomO2)
		return Lattice('15:b3', (0.72727,0.50027,0.55432, 90,96.762,90), desc='V2O3, Divanadium(III) oxide - LT',atoms=atoms, databaseCodes=[('ICSD',95762)])

	def make_Cu3AuRT():
		atomCu = LatticeBase.atomXtal('Cu',(0.0,0.5,0.5))
		atomAu = LatticeBase.atomXtal('Au',(0.0,0.0,0.0))
		atoms = (atomCu,atomAu)
		return Lattice('221', (0.3749,0.3749,0.3749, 90,90,90), desc='Cu3Au Normal T',atoms=atoms)

	def make_Cu3AuHT():
		atomCu = LatticeBase.atomXtal('Cu',(0.0,0.0,0.0),occ=0.75)
		atomAu = LatticeBase.atomXtal('Au',(0.0,0.0,0.0),occ=0.25)
		atoms = (atomCu,atomAu)
		return Lattice('225', (0.3749,0.3749,0.3749, 90,90,90), desc='Cu3Au Hight T',atoms=atoms)

	def make_Ge_2D():
		atomGe = LatticeBase.atomXtal('Ge',(0.0,0.0), WyckoffSymbol='a')
		return Lattice('12', (0.56577974,0.56577974,90), desc='Ge surface',atoms=(atomGe,))

	silicon = make_Silicon()
	GaAs = make_GaAs()
	sapphireHex = make_SapphireHex()
	sapphireRhom = make_SapphireRhom()
	YBCO = make_YBCO()


	def test_FstructAllow(xtal, hkl, Ftest,dtest, keV=None, T_K=0, printIt=True):
		if xtal.allowedHKL(hkl):	strAllow = "    Allowed"
		else:					strAllow = "Not Allowed"

		Fc = xtal.Fstruct(hkl, keV=keV, T_K=T_K)
		d = xtal.dSpacing(hkl)

		if math.isinf(d) and math.isinf(dtest): deltaD = 0
		else: deltaD = math.fabs(d-dtest)

		if T_K > 0:	T_str = u',   T = %g%sK' % (T_K,degree)
		else:		T_str = u''
		if keV>0:	e_str = u', keV=%g' % (keV,)
		else:		e_str = u''

		if abs(Fc-Ftest)<1e-3 and deltaD<1e-6:
			if printIt: print (u'     %s  F("%s", %r%s) = |%.6f + %.6fj| = %.6f,   d=%g nm%s' % (strAllow,xtal.desc,hkl,e_str,Fc.real,Fc.imag,abs(Fc),d, T_str))
			return False
		else:
			if printIt: print (u'ERR  %s  F("%s", %r%s) = |%.6f + %.6fj| = %.6f,   d=%g nm,  should be F=%r, d=%g%s' % (strAllow,xtal.desc,hkl,e_str,Fc.real,Fc.imag,abs(Fc),d,Ftest,dtest,T_str))
			return True

	def test_Fe2O3_hex_rhom(hex, keV=10, printIt=True):
		H,K,L = hex					# hexagonal hkl
		h,k,l = float(2*H + K + L)/3.0, float(-H + K + L)/3.0, float(-H - 2*K + L)/3.0	# rhombohedral hkl

		Fe2O3h = Lattice(file='materials/Fe2O3h.xml',keV=keV)
		Fe2O3r = Lattice(file='materials/Fe2O3r.xml',keV=keV)
		Fe2O3h.Vibrate = Fe2O3h.haveDebyeT = False			# cannot use vibrations since they are different in the two files
		Fe2O3r.Vibrate = Fe2O3r.haveDebyeT = False

		Fh = Fe2O3h.Fstruct((H,K,L))
		Fr = Fe2O3r.Fstruct((h,k,l))
		errF = abs(Fh-3*Fr) > 2e-5			# F's must differ by factor of 3
		if errF:	errStrF = 'ERR - '
		else:		errStrF = '      '

		if min(H,K,L)==0 and max(H,K,L)==0: dh = 0
		else:	dh = Fe2O3h.dSpacing((H,K,L))
		if min(h,k,l)==0 and max(h,k,l)==0: dr = 0
		else:	dr = Fe2O3r.dSpacing((h,k,l))

		if math.isinf(dh) and math.isinf(dr): errd = False
		elif math.isinf(dh) or math.isinf(dr): errd = True
		elif math.isnan(dh+dr): errd = True
		else: errd = abs(dh-dr) > 2e-7		# d's must be the same
		if errd:	errStrd = errStrd = 'ERR - '
		else:		errStrd = '      '

		hexS = hkl2str((H,K,L))
		rhomS = hkl2str((h,k,l))
		if not (keV==10):	eneStr = '  (at %g keV)' % (keV)
		else:				eneStr = ''
		Delta = u'\u0394'					# str greek Delta

		if printIt:
			print (u'%sF_hex(%s) = (%.5f, %.5f),   3*F_rhom(%s) = (%.5f, %.5f),  |%sF| = %.4g%s' % (errStrF, hexS,Fh.real,Fh.imag,rhomS,3*Fr.real,3*Fr.imag,Delta, abs(Fh-3*Fr),eneStr))
			if dh or dr:
				print (u'%sd_hex(%s) = %.8f    d_rhom(%s) = %.8f  %sd = %.2g nm' % (errStrd, hexS,dh, rhomS,dr, Delta, dh-dr))
				print ('')
		return errF or errd

	def test_angleBetweenHKLs(xtal, hkl1, hkl2, test, printIt=True):
		angle = xtal.angleBetweenHKLs(hkl1, hkl2)
		if math.fabs(angle-test) < 1e-4:
			if printIt: print (u'     for "%s", %r ^ %r = %g%s' % (xtal.desc,hkl1, hkl2,angle,degree))
			return False
		else:
			if printIt: print (u'ERR  for "%s", %r ^ %r = %g%s,   it should be %g%s' % (xtal.desc,hkl1, hkl2,angle,test,degree))
			return True

	def test_findClosestHKL(xtal,d, dtest, printIt=True):
		l = xtal.findClosestHKL(d)

		if math.fabs(dtest - l[0]['dhkl']) < 1e-6:
			if printIt: print (u'     in "%s", closest d-spacing to %g nm, there are %d close:' % (xtal.desc, d, len(l)))
			err = False
		else:
			if printIt: print (u'ERR  in "%s", closest d-spacing to %g nm, there are %d close:' % (xtal.desc, d, len(l)))
			err = True

		if printIt:
			for d in l: print (d)
		return err

	def test_DW_factor_M(xtal,T,fromIgor,  printIt=True):
		DW = xtal.DW_factor_M(T,645.0,20)
		delta = DW-fromIgor
		if math.fabs(delta)<1e-7:
			if printIt: print ('     DW_factor_M(%g) = %r,  delta=%g' % (T, DW, delta))
			return False
		else:
			if printIt: print ('ERR  DW_factor_M(%g) = %r,  delta=%g' % (T, DW, delta))
			return True
		
	def test_Hex_Rhom_Conversions(printIt=True):
		xtal = make_SapphireHex()

		aTest = 0.512815510469192
		alphaTest = 55.2793424027957
		aHex = 0.4758
		cHex = 1.2991

		#  ************************ set xtal to Hexagonal values *************************
		xtal.desc = u"Al2O3 Sapphire (hexagonal)"
		xtal.a = aHex		;	xtal.b = aHex		;	xtal.c = cHex
		xtal.alpha = 90.0	;	xtal.beta = 90.0	;		xtal.gam = 120.0
		xtal.SpaceGroup = 167
		xtal.direct = np.matrix([ [0.4758,-0.2379,0.0], [0.0,0.41205488712064,0.0], [0.0,0.0,1.2991] ])

		xtal.N = 2
		xtal.atoms[0].name = 'Al'	;	xtal.atoms[0].Zatom = 13
		xtal.atoms[0].x = 0.0		;	xtal.atoms[0].y = 0.0	;	xtal.atoms[0].z = 0.3523
		xtal.atoms[0].mult = 12		;	xtal.atoms[0].occ = 1
		xtal.atoms[1].name = 'O'	;	xtal.atoms[1].Zatom = 8
		xtal.atoms[1].x = 0.3064	;	xtal.atoms[1].y = 0.0	;	xtal.atoms[1].z = 0.25
		xtal.atoms[1].mult = 18		;	xtal.atoms[1].occ = 1
		if printIt: print ('     Starting with Hexagonal :   a = %g nm,  c = %g nm' % (xtal.a,xtal.c))

		if printIt: print (' ')
		(a,alpha) = xtal.Hex2Rhom(xtal.a, xtal.c)
		if math.fabs(a-aTest + alpha-alphaTest) < 1e-7:
			if printIt: print (u'     Rhombohedral:   a = %g nm,  alpha = %g%s' % (a,alpha,degree))
		else:
			if printIt: print (u'ERR  Rhombohedral:   a = %g nm,  alpha = %g%s,   should have a=%g,  alpha=%g' % (a,alpha,degree, aTest,alphaTest))
			return True
		xtal.Hex2RhomFractional(printIt)				# *********************************


		# *********************** set xtal to Rhombohedral values ***********************
		xtal.a = xtal.b = xtal.c = 0.512815510469192
		xtal.alpha = xtal.beta = xtal.gam = 55.2793424027957
		xtal.direct = np.matrix([ [0.2379,-0.2379,0], [0.137351629040212,0.137351629040212,-0.274703258080424], [0.433033333333333,0.433033333333333,0.433033333333333] ])
		xtal.atoms[0].x = xtal.atoms[0].y = xtal.atoms[0].z = 0.3523
		xtal.atoms[1].x = 0.5564	;	xtal.atoms[1].y = 0.9436	;	xtal.atoms[1].z = 0.25
		xtal.atoms[1].y -= 1

		if printIt: print (' ')
		(a,c) = xtal.Rhom2Hex(xtal.a, xtal.alpha)
		if math.fabs(a-aHex + c-cHex) < 1e-7:
			if printIt: print ('     Hexagonal:   a = %g nm,  c = %g nm' % (a,c))
		else:
			if printIt: print ('ERR  Hexagonal:   a = %g nm,  c = %g nm,   should have a=%g,  c=%g' % (a,c, aHex,cHex))
			return True
		xtal.Rhom2HexFractional(printIt)				# *********************************
		if printIt: print ('     +++++ Still need to check that the fractional values close +++++')
		return False

	def test_ConvertSetting(printIt=True):
		import copy
		xtalHex = make_SapphireHex()		# hexagonal version of 167:H
		xtalRhom = make_SapphireRhom()		# rhombohedral version of 167:R
		xtal = copy.deepcopy(xtalHex)		# process this, starting as hex
		xtal._eq_desc = False

		if printIt: print (str(xtal))		# hex xtal
		xtal.ConvertSetting('167:R')		# change current (167:H) --> 167:R
		if printIt: print ("\n----------   Used self.ConvertSetting('167:R') to convert 167:H --> 167:R   ----------\n")
		if printIt: print (str(xtal))		# rhom xtal
		if xtal != xtalRhom:
			if printIt: print ('ERR 1st part: (Hex -> Rhom): ',xtal._neqStr)
			return True

		xtal.ConvertSetting('167:H')		# change current (167:R) --> 167:H
		if printIt: print ("\n----------   Used self.ConvertSetting('167:R') to convert 167:R --> 167:H   ----------\n")
		if xtal != xtalHex:
			if printIt: print (str(xtal))	# hex xtal again
			if printIt: print ('ERR 2nd part: (Rhom -> Hex): ',xtal._neqStr)
			return True

		if printIt: print ("\n----------   test conversion of silicon 227:1 --> 227:2   ----------")
		silicon_2_test = make_Silicon(2)	# this is for 227:2
		silicon_2 = copy.deepcopy(silicon)	# start as Si as 227:1, convert to 227:2
		if printIt: print (str(silicon))
		silicon_2.ConvertSetting('227:2')	# change current (227:1) --> 227:2
		if silicon_2 != silicon_2_test:
			if printIt:
				print ('ERR 2nd part: (silicon(227:1) -> silicon(227:2)): ',silicon_2._neqStr)
				print (str(silicon_2))
				print (" ")
				print (str(silicon_2_test))
			return True
		elif printIt: print ('\n' + str(silicon_2))

		if printIt: print ("\n----------   test conversion of silicon 227:2 --> 227:1   ----------")
		silicon_1 = make_Silicon(2)			# start as 227:2
		if printIt: print (str(silicon_1))
		silicon_1.ConvertSetting('227:1')	# change current (227:2) --> 227:1
		if silicon_1 != silicon:
			if printIt:
				print ('****\nERR 2nd part: (silicon(227:2) -> silicon(227:1)): ',silicon_1._neqStr)
				print (str(silicon_1))
				print (" ")
				print (str(silicon))
			return True
		elif printIt: print ('\n' + str(silicon_1))

		return False

	def test_Read_All_xtal_files(folderName, printIt=True):
		""" folderName is usually either 'test' or 'materials' """
		materials = os.path.join(os.path.dirname(__file__),folderName)

		if not os.path.isdir(materials):
			print ('\nERROR -- "%s" does not exist\n' % (materials,))
			return True

		folders = ['']
		for fileName in os.listdir(materials):
			if os.path.isdir(os.path.join(materials,fileName)): folders.append('/'+fileName)
		badFiles = []
		Nxml = Ncif = 0
		for folder in folders:
			folder = materials + folder
			# print '\n\ntesting in folder = "%s"\n' % (folder,)
			# print os.listdir(folder)
			for fileName in os.listdir(folder):
				if fileName.find('.cif') > 1: pass
				elif fileName.find('.xml') < 1: continue
				elif fileName.startswith('scanLog'): continue	# catches "scanLog.xml" and "scanLog original.xml"
				try:
					xtal = Lattice(file=os.path.join(folder,fileName))
					# print u'"%s"      desc = "%r"' % (fileName,xtal.desc)
					try:	fileChecking = xtal.fileChecking
					except:	fileChecking = None
					if fileChecking and printIt:
						print ('\n    Issue with %r (a non-fatal issue)' % (os.path.join(folder,fileName),))
						for line in fileChecking:
							try:	print (u'\t%s' % (line,))
							except:	print (u'\t%r' % (line,))				
						print ('')
					if fileName.find('.xml') > 0: Nxml += 1
					if fileName.find('.cif') > 0: Ncif += 1

					for atom in xtal.atoms:
						if not atom.WyckoffSymbol: raise ValueError('Missing Wyckoff symbol for atom %r' % (atom.label,))

				except Exception as e:
					if fileName.startswith('bad'):
						if printIt:
							print ('\n    Issue with %r (this file SHOULD fail)' % (os.path.join(folder,fileName),))
							print ('        '+str(e))

					else:
						print ('ERROR -- Failed checking file: "%s"' % (fileName,))
						print ('        exception = '+str(e))
						badFiles.append(fileName)

		err = len(badFiles)>0
		if printIt or err:
			print (' ')
			if Nxml>0 and Ncif>0:	print ('    successfully loaded & checked %d xml files and %d cif files.' % (Nxml,Ncif))
			elif Nxml>0:		print ('    successfully loaded & checked %d xml files.' % (Nxml,))
			elif Ncif>0:			print ('    successfully loaded & checked %d cif files.' % (Ncif,))
			elif Ncif>0:			print ('    successfully loaded & checked NO files.')
			if err:				print ('\nERROR -- Failed to process files: %s\n' % (badFiles,))
		return err


	def writeReadTest(xtalStart, tag, symOps=False, printIt=True):
		out = xtalStart.data2xml(symOps=symOps)
		fileName = 'writeOut/write_%s.xml' % (tag,)
		if printIt: print ('writing to:  "%s"' % (fileName,),)
		try:
			if len(out)<1: raise ValueError('ERROR -- Contents of file to write is empty')
			f = open(fileName, 'w')
			f.write(out.encode("utf-8"))
			f.close()
		except Exception as e:
			print ('ERROR -- Failed writing to file: "%s"        %s' % (fileName,str(e)))
			return True

		xtalFinal = Lattice(file=fileName)			# read back in the file that was just written
		match = xtalFinal == xtalFinal	
		if match:
			if printIt: print ('    \t-->  Write/Read matches')
		else:		print ('   \t-->  Write/Read MISMATCH')
		return not match					# not equals is an error


	if testing.doit('check FstructAllow(...)'):						#  2**0 = 1
		printIt = testing.unique
		err = False
		err |= test_FstructAllow(silicon, (0,0,0), complex(111.991,0),float('inf'), printIt=printIt)
		err |= test_FstructAllow(silicon, (0,0,0), complex(113.464,1.73038),float('inf'), keV=10.0, printIt=printIt)
		err |= test_FstructAllow(silicon, (1,1,1), complex(42.1461707, -42.1461707), 0.3135601, keV=float('nan'), printIt=printIt)
		err |= test_FstructAllow(silicon, (1,1,1), complex(43.7477554, -42.017378), 0.3135601, keV=10.0, printIt=printIt)
		err |= test_FstructAllow(silicon, (2,2,2), complex(0,0), 0.1567801, printIt=printIt)
		err |= test_FstructAllow(silicon, (4,4,2), complex(0,0), 0.0905170, printIt=printIt)
		err |= test_FstructAllow(silicon, (1,2,3), complex(0,0), 0.1451501, printIt=printIt)
		err |= test_FstructAllow(silicon, (2,2,0), complex(69.6736372,0), 0.1920156,keV=float('nan'), printIt=printIt)
		err |= test_FstructAllow(silicon, (2,2,0), complex(69.6736372,0), 0.1920156,keV=float('nan'), printIt=printIt)
		err |= test_FstructAllow(silicon, (0,0,4), complex(60.073065056,0),0.1357755, printIt=printIt)
		if printIt: print (' ')
		err |= test_FstructAllow(GaAs, (1,1,1), complex(106.4769283,-112.4842562), 0.3263992, printIt=printIt)
		err |= test_FstructAllow(GaAs, (1,1,1), complex(97.25001842,-103.8068503), 0.3263992, keV=10, printIt=printIt)
		err |= test_FstructAllow(GaAs, (2,2,2), complex(-4.933576684,0), 0.3263992/2, printIt=printIt)
		err |= test_FstructAllow(GaAs, (4,4,2), complex(-6.32666127,0), 0.09422333, printIt=printIt)
		err |= test_FstructAllow(GaAs, (1,2,3), complex(0,0), 0.15109347, printIt=printIt)
		err |= test_FstructAllow(GaAs, (2,2,0), complex(190.03682378,0), 0.19987787, printIt=printIt)
		err |= test_FstructAllow(GaAs, (0,0,4), complex(162.97451656,0), 0.141335, printIt=printIt)
		if printIt: print (' ')
		err |= test_FstructAllow(sapphireHex, (0,0,0), complex(284.31837,2.2860145), float('inf'), keV=10.0, printIt=printIt)
		err |= test_FstructAllow(sapphireHex, (0,0,3), complex(0,0), 1.2991/3, keV=10.0, printIt=printIt)
		err |= test_FstructAllow(sapphireHex, (0,0,5), complex(0,0), 1.2991/5, keV=10.0, printIt=printIt)
		err |= test_FstructAllow(sapphireHex, (0,0,6), complex(-12.120,1.085), 1.2991/6, keV=10.0, T_K=NormalTemp_K, printIt=printIt)
		if printIt: print (' ')
		err |= test_FstructAllow(sapphireRhom, (0,0,0), complex(94.7727915,0.76200482), float('inf'), keV=10.0, T_K=NormalTemp_K, printIt=printIt)
		err |= test_FstructAllow(sapphireRhom, (2,2,2), complex(-4.2326448,0.358806), 1.2991/6, keV=10, T_K=NormalTemp_K, printIt=printIt)

		if printIt: print (' ')
		muTest = 0.00626932
		mu = sapphireHex.mu(10)
		if printIt:
			if math.fabs(mu-muTest)<1e-7:
				print (u'     µ["%s", 10 keV] = %g (1/µm)  -->  absorption length %g (µm)' % (sapphireHex.desc,mu, 1.0/mu))
			else:
				print (u'ERR  µ["%s", 10 keV] = %g (1/µm),  it should be %g' % (sapphireHex.desc,mu, muTest))

		if err: testing.addErr()


	if testing.doit('check angleBetweenHKLs()'):					#  2**1 = 2
		printIt = testing.unique
		err  = test_angleBetweenHKLs(silicon, (1,0,0), (2,0,2), 45, printIt)
		err |= test_angleBetweenHKLs(silicon, (1,0,0), (0,2,2), 90, printIt)
		err |= test_angleBetweenHKLs(silicon, (1,1,1), (2,0,2), 35.2644, printIt)
		if printIt: print (' ')
		err |= test_angleBetweenHKLs(GaAs, (1,0,0), (2,0,2), 45, printIt)
		err |= test_angleBetweenHKLs(GaAs, (1,0,0), (0,2,2), 90, printIt)
		err |= test_angleBetweenHKLs(GaAs, (1,1,1), (2,0,2), 35.2644, printIt)
		if printIt: print (' ')
		err |= test_angleBetweenHKLs(YBCO, (1,0,0), (2,0,2), 18.1141, printIt)
		err |= test_angleBetweenHKLs(YBCO, (1,0,0), (0,2,2), 90, printIt)
		err |= test_angleBetweenHKLs(YBCO, (1,1,1), (2,0,2), 43.0555, printIt)
		if printIt: print (' ')
		err |= test_angleBetweenHKLs(sapphireHex, (1,0,0), (2,0,2), 17.6014, printIt)
		err |= test_angleBetweenHKLs(sapphireHex, (1,0,0), (0,2,2), 61.5370, printIt)
		err |= test_angleBetweenHKLs(sapphireHex, (1,1,1), (2,0,2), 29.9509, printIt)
		if err: testing.addErr()

	if testing.doit('check findClosestHKL()'):						#  2**2 = 4
		printIt = testing.unique
		err  = test_findClosestHKL(silicon,0.23, 0.1920156, printIt)
		err |= test_findClosestHKL(GaAs,0.23, 0.1998779, printIt)
		if err: testing.addErr()

	if testing.doit('check DW_factor_M()'):						#  2**3 = 8
		printIt = testing.unique
		err = test_DW_factor_M(silicon.atoms[0],645,0.016508709, printIt)
		err |= test_DW_factor_M(silicon.atoms[0],700,0.0178446, printIt)
		err |= test_DW_factor_M(silicon.atoms[0],1,0.00401676310870523, printIt)
		err |= test_DW_factor_M(silicon.atoms[0],2000,0.049963311, printIt)
		if err: testing.addErr()

	if testing.doit('set Lattice from a file  "test/YBCO.xml"'):			#  2**4 = 16
		YBCOfile = Lattice(file='test/YBCO.xml')
		if YBCO != YBCOfile:
			print (str(YBCOfile))
			print ('ERR  "'+YBCO._neqStr+'"   on check "test/YBCO.xml"')
			testing.addErr()
		elif testing.unique: print (str(YBCOfile))

	if testing.doit('set Lattice from a file  "test/GaAs.xml"'):			#  2**5 = 32
		GaAsfile = Lattice(file='test/GaAs.xml')
		if GaAs != GaAsfile:
			print (str(GaAsfile))
			print ('ERR  "'+GaAsfile._neqStr+'"   on check "test/GaAs.xml"')
			testing.addErr()
		elif testing.unique: print (str(GaAsfile))

	if testing.doit('set Lattice from a file  "materials/Pu-alpha.xml"'):		#  2**6 = 64
		Pu = make_Pu()
		PuAlphaFile = Lattice(file='materials/Pu-alpha.xml')
		if Pu != PuAlphaFile:
			print (str(PuAlphaFile))
			print ('ERR  "'+PuAlphaFile._neqStr+'"   on check "materials/Pu-alpha.xml"')
			testing.addErr()
		elif testing.unique: print (str(PuAlphaFile))

	if testing.doit('set Lattice from to a random Triclinic'):				#  2**7 = 128
		triclinic = Lattice(1, (.4,.5,.6,90,110,94), desc='random Triclinic')
		igorRecip = np.matrix([ [15.707963, 0, 0], [1.098408, 12.597056, 0], [5.747049, 0.320715, 11.147655] ] )
		delta = abs(igorRecip - triclinic.recip)
		if np.max(delta) > 1e-6:
			print (repr(triclinic))
			testing.addErr()
		elif testing.unique: print (str(triclinic))

	if testing.doit('set Lattice to "test/test_YBCO.xml"'):				#  2**8 = 256
		try:
			YBCOfile = Lattice(file='test/test_YBCO.xml')
			YBCOfile._eq_all = False
			equal = (YBCOfile == YBCO)
			errStr = YBCOfile._neqStr
		except:	errStr = 'Unable to read "test/test_YBCO.xml"'
		if not equal:
			print (str(YBCO.bonds))
			print (" ")
			print (str(YBCOfile.bonds))
			print ('ERR  "'+errStr+'"   on check "test/test_YBCO.xml"')
			testing.addErr()
		elif testing.unique: print (str(YBCO.bonds))

	if testing.doit('set Lattice from to "materials/Si.xml"'):				#  2**9 = 512
		SiFile = Lattice(file='materials/Si.xml')
		SiFile._eq_all = False
		if silicon == SiFile:
			print ('ERR  -- Temperatures should differ  on check "materials/Si.xml"')
			testing.addErr()
		SiFile.Temperature0 = NormalTemp_C				# now they should match
		SiFile.Temperature = NormalTemp_C				# now they should match
		if silicon != SiFile:
			print (str(SiFile))
			print ('ERR  "'+SiFile._neqStr+'"   on check "materials/Si.xml"')
			testing.addErr()
		elif testing.unique: print (str(SiFile))

	if testing.doit('set Lattice from to "test/PigeoniteJZT.cif"'):			#  2**10 = 1024
		Pigeonite = make_Pigeonite()
		testCIF = Lattice(file='test/PigeoniteJZT.cif')
		if testCIF != Pigeonite:
			print (str(testCIF))
			print ('ERR  "'+testCIF._neqStr+'"   on check "test/PigeoniteJZT.cif"')
			testing.addErr()
		elif testing.unique: print (str(testCIF))

	if testing.doit('set Lattice from to "materials/Autunite.xml"'):		#  2**11 = 2048
		Autunite = make_Autunite()
		testXMLfile = Lattice(file='materials/Autunite.xml')
		if testXMLfile != Autunite:
			print ("**** local Autunite")
			print (str(Autunite))
			print ('\n\n\n')
			print ("**** local from xml file")
			print (str(testXMLfile))
			print ('ERR  "'+testXMLfile._neqStr+'"   on check "materials/Autunite.xml"')
			testing.addErr()
		elif testing.unique: print (str(Autunite))

	if testing.doit('set Lattice from to "materials/PZT-Hex.xml"'):		#  2**12 = 4096
		PZT = make_PZT_hex()
		testXMLfile = Lattice(file='materials/PZT-Hex.xml')
		if testXMLfile != PZT:
			print (str(testXMLfile))
			print ('ERR  "'+testXMLfile._neqStr+'"   on check "materials/PZT-Hex.xml"')
			testing.addErr()
		elif testing.unique: print (str(PZT))

	if testing.doit('set Lattice from to "non_existant_file.xml"'):			#  2**13 = 8192
		try:
			testCIF = Lattice(file='non_existant_file.xml')
			testing.addErr()			# if you make it this far, something is wrong
		except:
			if testing.unique: print ('supposed to fail when reading "non_existant_file.xml"')

	if testing.doit('set Lattice from to "test/V2O3 Monoclinic.xml"'):		#  2**14 = 16384
		V2O3 = make_V2O3_monoclinic('V')
		V2O3File = Lattice(file='test/V2O3 Monoclinic.xml')
		V2O3File._eq_all = False
		errStr = ''
		if V2O3 != V2O3File: errStr = V2O3File._neqStr
		if test_FstructAllow(V2O3File, (0,0,0), complex(270.650607, 11.8952019),float('inf'), keV=10, printIt=testing.unique):
			errStr += '  also Fstruct error  '
		if len(errStr):
			print (' ')
			print (str(V2O3File))
			print ('ERR  "'+errStr+'"   on check "test/V2O3 Monoclinic.xml"')
			testing.addErr()
		elif testing.unique: print (str(V2O3File))

	if testing.doit('test Fstruct of "test/NiTi_Cubic.cif"'):				#  2**15 = 32768
		printIt = testing.unique
		NiTi = make_NiTi()
		NiTiFile = Lattice(file='test/NiTi_Cubic.cif')
		NiTiFile._eq_all = False
		errStr = ''
		if NiTiFile != NiTi: errStr = NiTiFile.neqStr
		if test_FstructAllow(NiTiFile, (0,0,0), complex(49.605328,4.1253809),float('inf'), keV=10, printIt=printIt):
			errStr += '  also Fstruct error  '

		if test_FstructAllow(NiTiFile, (1,0,0), complex(5.157,1.626),0.3016, keV=10, printIt=printIt):
			errStr += '  also Fstruct error  '

		if test_FstructAllow(NiTiFile, (2,0,0), complex(28.380,3.95),0.1508, keV=10, printIt=printIt):
			errStr += '  also Fstruct error  '

		if len(errStr):
			print (' ')
			print (str(NiTiFile))
			print ('ERR  "'+errStr+'"   on check "test/NiTi_Cubic.cif"')
			testing.addErr()
		elif printIt: print (str(NiTiFile))

	if testing.doit('test Fstruct of "materials/Cu3AuRT.xml" and "materials/Cu3AuHT.xml"'):	#  2**16 = 65536
		printIt = testing.unique
		Cu3AuRT = make_Cu3AuRT()
		Cu3AuHT = make_Cu3AuHT()
		Cu3AuRTFile = Lattice(file='materials/Cu3AuRT.xml')
		Cu3AuHTFile = Lattice(file='materials/Cu3AuHT.xml')
		Cu3AuRTFile._eq_all = False
		Cu3AuHTFile._eq_all = False
		errStr = ''
		if Cu3AuRTFile != Cu3AuRT: errStr = Cu3AuRTFile._neqStr
		if Cu3AuHTFile != Cu3AuHT: errStr += Cu3AuRTFile._neqStr
		if test_FstructAllow(Cu3AuRT, (0,0,0), complex(155.3772165,14.874146),float('inf'), keV=10, printIt=printIt):
			errStr += '  also Fstruct error RT 000 '
		if test_FstructAllow(Cu3AuRT, (0,0,0), complex(155.3772165,14.874146),float('inf'), keV=10, printIt=printIt):
			errStr += '  also Fstruct error HT 000 '

		if test_FstructAllow(Cu3AuRTFile, (1,0,0), complex(41.3414496,1.926023),0.3749, keV=10, printIt=printIt):
			errStr += '  also Fstruct error RT 100 '
		if test_FstructAllow(Cu3AuHTFile, (1,0,0), complex(0,0),0.3749, keV=10, printIt=printIt):
			errStr += '  also Fstruct error HT 100 '

		if test_FstructAllow(Cu3AuRTFile, (2,0,0), complex(114.3682,14.874146),0.3749/2, keV=10, printIt=printIt):
			errStr += '  also Fstruct error RT 200 '
		if test_FstructAllow(Cu3AuHTFile, (2,0,0), complex(114.3682,14.874146),0.3749/2, keV=10, printIt=printIt):
			errStr += '  also Fstruct error HT 200 '
		if len(errStr):
			print (' ')
			print (str(Cu3AuRT))
			print (' ')
			print (str(Cu3AuHT))
			print ('ERR  "'+errStr+'"   on check "materials/Cu3AuxT.xml"')
			testing.addErr()
		elif printIt: print (str(Cu3AuRTFile))

	if testing.doit('test Fstruct of "test/V2O3_Mono_95762.cif"'):		#  2**17 = 131072
		V2O3 = make_V2O3_monoclinic('V1')
		V2O3File = Lattice(file='test/V2O3_Mono_95762.cif')
		V2O3File._eq_all = False
		if V2O3File != V2O3:
			print (' ')
			print (str(V2O3))
			print (' ')
			print (str(V2O3File))
			print ('ERR  "'+V2O3File._neqStr+'"   on check "test/V2O3_Mono_95762.cif"')
			testing.addErr()
		elif testing.unique: print (str(V2O3))

	if testing.doit('check Hex <--> Rhom Conversions'):				#  2**18 = 262144
		if test_Hex_Rhom_Conversions(testing.unique): testing.addErr()

	if testing.doit('check ConvertSetting(), Hex --> Rhom --> Hex'):		#  2**19 = 524288
		if test_ConvertSetting(testing.unique): testing.addErr()

	if testing.doit('check Finding Wyckoff Positions using FindWyckoffSymbol()'):	#  2**20 = 1048576
		err = False
		printIt = testing.unique

		for atom in YBCO.atoms:
			mult0 = atom.mult						# save existing Wyckoff symbol & mltiplicity
			symbol0 = atom.WyckoffSymbol
			siteSym0 = atom.siteSymmetry
			atom.WyckoffSymbol = 'Zz'				# set to BAD values
			atom.mult = -3.1
			atom.siteSymmetry = 'abc'
			(symbol,mult,siteSym) = YBCO.FindWyckoffSymbol(atom)
			if (symbol,mult,siteSym) == (symbol0,mult0,siteSym0):	# compare found with existing
				if printIt: print ('     "%s",  "%s", mult = %r, siteSym = %r  Matches' % (atom.label,symbol,mult,siteSym))
			else:	print ('ERR  %r != %r' % ((symbol,mult,siteSym),(symbol0,mult0,siteSym0)))

		if printIt: print ('\n     Set all atom.WyckoffSymbol, atom.mult & atom.siteSymmetry to BAD values, then call SetWyckoffSymbols(force=True):')
		for atom in YBCO.atoms:
			atom.WyckoffSymbol = 'Zz'				# set to BAD values
			atom.mult = -3.1
			atom.siteSymmetry = 'abcxyz'
		YBCO.SetWyckoffSymbols(force=True)
		if printIt:
			for atom in YBCO.atoms: print ('     "%s",  "%s", mult = %r  siteSym = %r  Matches' % (atom.label,atom.WyckoffSymbol,atom.mult,atom.siteSymmetry))

		if err: testing.addErr()

	if testing.doit('test Fstruct for Fe2O3: Hexagonal vs. Rhombohedral'):	#  2**21 = 2097152
		printIt = testing.unique
		err = test_Fe2O3_hex_rhom((0,0,0), printIt=printIt)					# (000) same for hex & rhom
		err = test_Fe2O3_hex_rhom((0,0,0),keV=20, printIt=printIt)			#	and at 20 keV
		err = test_Fe2O3_hex_rhom((0,0,0),keV=0, printIt=printIt)			#	and at 0 keV
		err = err or test_Fe2O3_hex_rhom((0,0,6), printIt=printIt)			# (006 hex) == (222 rhom)
		err = err or test_Fe2O3_hex_rhom((0,0,6),keV=20, printIt=printIt)	#	and at 20 keV
		err = err or test_Fe2O3_hex_rhom((1,2,8), printIt=printIt)			# (006 hex) == (222 rhom)
		err = err or test_Fe2O3_hex_rhom((0,-1,4), printIt=printIt)			# (006 hex) == (222 rhom)
		if err: testing.addErr()


	if testing.doit('test single file: "%s"' % (file,)) and testing.unique:	#  2**22 = 4194304
		try:
			file = sys.argv[-1]					# always last argument
			if testing.testLog and (file.lower() in {'l','log'}): file = ''
		except:	file = ''
		if len(file):
#			xtal = Lattice(file=file)		# useful for testing to find bugs
			try:
				xtal = Lattice(file=file)
				# print repr(xtal)
				# print " "
				# print " "
				print (u"%s" % (str(xtal),))

				try:	fileChecking = xtal.fileChecking
				except:	fileChecking = []
				if len(fileChecking):
					print ('\n    Issue with %r (a non-fatal issue)' % (file,))
					for line in fileChecking:
						try:	print (u'\t%s' % (line,))
						except:	print (u'\t%r' % (line,))				
					print ('')

				for atom in xtal.atoms:
					if not atom.WyckoffSymbol: raise ValueError('Missing Wyckoff symbol for atom %r' % (atom.label,))

				if (xtal.dim == 2): hkl = (0,0)
				else: 				hkl = (0,0,0)
				print ('F%r = %r' % (hkl,xtal.Fstruct(hkl, keV=10)))
				if (xtal.dim == 2): hkl = (0,1)
				else: 				hkl = (0,1,1)
				print ('F%r = %r' % (hkl,xtal.Fstruct(hkl, keV=10)))
				if (xtal.dim == 2): hkl = (1,1)
				else: 				hkl = (1,1,1)
				print ('F%r = %r' % (hkl,xtal.Fstruct(hkl, keV=10)))
				if (xtal.dim == 2): hkl = (0,4)
				else: 				hkl = (0,0,4)
				print ('F%r = %r' % (hkl,xtal.Fstruct(hkl, keV=10)))

			except Exception as e:
				print (str(e))
				if str(e).find('input file') > 0 and str(e).find('does not exist') > 0:
					print ('\tDid you forget the leading "materials/" or "test/"  ?')
				testing.addErr()

	if testing.doit('test all of the *.xml & *.cif files in ./test/*'):			#  2**23 = 8388608
		if test_Read_All_xtal_files('test', testing.unique): testing.addErr()

	if testing.doit('test all of the *.xml & *.cif files in ./materials/*'):		#  2**24 = 16777216
		if test_Read_All_xtal_files('materials', testing.unique): testing.addErr()


	# to do the bond Calc testing, use:		2**25+2**26+2**27+2**28+2**29+2**30 = 2113929216


	if testing.doit('test finding Si bonds:'):							#  2**25 = 33554432
		bondSi = LatticeBase.bondType('Si','Si', 0.54310206*math.sqrt(3.0)/4.0)	# 0.54310206*math.sqrt(3.0)/4.0 = 0.23517
		errStr = silicon.bond_testing(bondSi, testing.unique)
		err = len(errStr)>0
		if len(errStr)>0:
			print ('\nERR, ',errStr)
			print (u'    the given Si bond is:',silicon.bonds[0])
			testing.addErr()

	if testing.doit('test finding GaAs bonds:'):						#  2**26 = 67108864
		bondsGaAs = LatticeBase.bondType('Ga001','As001',0.2448)
		errStr = GaAs.bond_testing(bondsGaAs, testing.unique)
		err = len(errStr)>0
		if len(errStr)>0:
			print ('\nERR, ',errStr)
			print (u'    the given GaAs bond is:',GaAs.bonds[0])
			testing.addErr()

	if testing.doit('test finding YBCO bonds:'):						#  2**27 = 134217728
		bondYBCO = make_YBCObonds()
		errStr = YBCO.bond_testing(bondYBCO, testing.unique)
		err = len(errStr)>0
		if len(errStr)>0:
			print ('\nERR, ',errStr)
			print (u'    the expected YBCO bonds are:',YBCO.bonds[0])
			testing.addErr()

	if testing.doit('test finding quartz bonds:'):						#  2**28 = 268435456
		quartz = Lattice(file='test/quartz_alpha.xml')
		bondsQuartz = LatticeBase.bondType('Si','O',0.16052)
		errStr = quartz.bond_testing(bondsQuartz, testing.unique)
		err = len(errStr)>0
		if len(errStr)>0:
			print ('\nERR, ',errStr)
			print (u'    the expected quartz bonds are:',quartz.bonds[0])
			testing.addErr()

	if testing.doit('test finding Saenger bonds:'):					#  2**29 = 536870912
		Saenger = Lattice(file='test/Saenger.cif')
		bond1  = LatticeBase.bondType('P1',  'O3', 0.1531)
		bond2  = LatticeBase.bondType('P1',  'O1', 0.1536)
		bond3  = LatticeBase.bondType('P1',  'O2', 0.1538)
		bond4  = LatticeBase.bondType('Ca2', 'O3', 0.2344)
		bond5  = LatticeBase.bondType('Ca2', 'O2', 0.2360)
		bond6  = LatticeBase.bondType('Ca2', 'O4', 0.2382)
		bond7  = LatticeBase.bondType('Ca1', 'O1', 0.2406)
		bond8  = LatticeBase.bondType('Ca1', 'O2', 0.2454)
		bond9  = LatticeBase.bondType('Ca2', 'O1', 0.2706)
		bond10 = LatticeBase.bondType('Ca1', 'O3', 0.2814)
		bond11 = LatticeBase.bondType('Ca2', 'P1', 0.3080)
		bondSaenger = (bond1,bond2,bond3,bond4,bond5,bond6,bond7,bond8,bond9,bond10,bond11)
		errStr = Saenger.bond_testing(bondSaenger, testing.unique)
		err = len(errStr)>0
		if len(errStr)>0:
			print ('\nERR, ',errStr)
			print (u'    the expected Saenger bonds are:',Saenger.bonds[0])
			testing.addErr()

	if testing.doit('test finding Chakraborty bonds:'):					#  2**30 = 1073741824
		Chakraborty = Lattice(file='test/Chakraborty.cif')
		bond1  = LatticeBase.bondType('P1',  'O3', 0.1551)
		bond2  = LatticeBase.bondType('P1',  'O1', 0.1578)
		bond3  = LatticeBase.bondType('P1',  'O2', 0.1533)
		bond4  = LatticeBase.bondType('Ca2', 'O3', 0.2322)
		bond5  = LatticeBase.bondType('Ca2', 'O2', 0.2362)
		bond6  = LatticeBase.bondType('Ca2', 'O4', 0.2382)
		bond7  = LatticeBase.bondType('Ca1', 'O1', 0.2395)
		bond8  = LatticeBase.bondType('Ca1', 'O2', 0.2452)
		bond9  = LatticeBase.bondType('Ca2', 'O1', 0.2671)
		bond10 = LatticeBase.bondType('Ca1', 'O3', 0.2808)
		bond11 = LatticeBase.bondType('Ca2', 'P1', 0.3084)
		bondChakraborty = (bond1,bond2,bond3,bond4,bond5,bond6,bond7,bond8,bond9,bond10,bond11)
#		bondChakraborty = (bond1,bond2,bond3,bond4,bond5,bond6,bond7,bond8,bond9,bond10)
		errStr = Chakraborty.bond_testing(bondChakraborty, testing.unique)
		err = len(errStr)>0
		if len(errStr)>0:
			print ('\nERR, ',errStr)
			print (u'    the %d expected Chakraborty bonds are:' % (len(bondChakraborty),))
			for bond in bondChakraborty: print (str(bond))
			testing.addErr()

	if testing.doit('check writing xml files'):						#  2**31 = 2147483648
		V2O3 = make_V2O3_monoclinic('V')
		Ge2D = make_Ge_2D()
		printIt = testing.unique
		err = False
		err = err or writeReadTest(silicon, 'SiNoSym', symOps=False, printIt=printIt)
		err = err or writeReadTest(silicon, 'SiSym', symOps=True, printIt=printIt)
		err = err or writeReadTest(GaAs, 'GaAs', symOps=True, printIt=printIt)
		err = err or writeReadTest(sapphireHex, 'SapHex', symOps=True, printIt=printIt)
		err = err or writeReadTest(sapphireRhom, 'SapRhom', symOps=True, printIt=printIt)
		err = err or writeReadTest(V2O3, 'V2O3', symOps=True, printIt=printIt)
		err = err or writeReadTest(Ge2D, 'Ge2D', symOps=True, printIt=printIt)
		err = err or writeReadTest(YBCO, 'YBCO', symOps=True, printIt=printIt)
		if err: testing.addErr()

	if testing.doit('test reading NdP5O14.xtal:'):				#  2**32 = 4294967296

		try:	NdP5O14 = Lattice(file='/Users/tischler/Documents/materials/NdP5O14.xtal')
		except:
			print ('\nERR, ',errStr)
			print (u'    unable to read "NdP5O14"')
			testing.addErr()
		print (str(NdP5O14))
		Fhkl = NdP5O14.Fstruct((0,0,8), keV=12.4)
		print ("F(008) =",Fhkl)


	testing.ending()
