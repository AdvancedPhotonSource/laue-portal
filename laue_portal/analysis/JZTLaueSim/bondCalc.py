#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# bondCalc.py
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
import math
import numpy as np
#from Lattice import Lattice
from JZTLaueSim.LatticeBase import bondType
from JZTLaueSim.atomGeneral import elementInfo

Lattice_minBondLen = 0.050		# 0.050 nm = 50 pm, minimum possible distance between atoms (smallest known bond is 74 pm)
Lattice_maxBondLen = 0.310		# 0.310 nm = 310 pm, maximum possible bond distance between atoms



class bondCalc(object):
	"""
	A Class that the defines a crystal lattice with all of its atoms.
	It can load all the information from a file
	All parameters are forced to be consistent with the space group number.
	It can also calculate the structure factor F(hkl)
	"""
	def __init__(self):
		# Initialize this bondCalc instance.
		self.unbondedAtoms = self.unassociated = None	# gets set later
		return None


	def ComputeBonds(self, overwrite=False):
		# actually calculated the bonds

		try:	overwrite = bool(overwrite)
		except:	ValueError('ERROR --  bondCalc(), overwrite must be boolean, not \"%r\"' % (overwrite,))
		if self.bonds is None: overwrite = False
		if len(self.bonds)>0 and (not overwrite): return None	# do not replace existing bonds

		Natom = len(self.atoms)
		Eneg = list()
		extend = list()
		for atom in self.atoms:
			Eneg.append( elementInfo(int(atom.Z)).electroneg)	# electronegativity
			xyz = self.ExtendFractional(atom.xyz, 0.5)
			xyz = np.asarray(xyz)								# need a numpy array for the next line, the xyz.T
			xyz = np.dot(self.direct, xyz.T).T					# convert xyz[Nxyz][3] from fractional coords --> real lengths (nm)
			extend.append(xyz)

		useValence = (max(Eneg)-min(Eneg)) > 0.7				# if useValence, then take into account the ElectroNegativity

		bondAll = list()
		blen = list()
		j = 0
		for atom0 in self.atoms:
			xyzC = self.FindCentralAtom(atom0.xyz)
			xyzC = np.dot(self.direct, xyzC.T).T				# convert xyz[Nxyz][3] from fractional coords --> real lengths (nm)
			for i in range(j,Natom):
				atom1 = self.atoms[i]
				blenTest = self.FindClosestAtomDistance(xyzC, extend[i])
				if useValence and atom0.Z==atom1.Z: continue	# skip if using valence and atoms have same Z
				if blenTest<Lattice_minBondLen or Lattice_maxBondLen<blenTest: continue	# skip this too
				blen.append(blenTest)
				bondAll.append((blenTest,atom0,atom1))
			j += 1

		index = np.argsort(blen)
		self.bonds = list()
		for i in index:
			(bl,atom0,atom1) = bondAll[i]
			self.bonds.append(bondType(atom0.label, atom1.label, bl))
		self.unbondedAtoms = self.UnBondedAtomsList()
		self.unassociated = len(self.unbondedAtoms)
		return self.bonds


	def UnBondedAtomsList(self):
		# returns a list of atom labels that are not in a bond
		labels = list()
		for atom in self.atoms: labels.append(atom.label)	# list of all labels
		for bt in self.bonds:
			try:	labels.remove(bt.label0)		# remove this labeled atom from labels[]
			except:	pass
			try:	labels.remove(bt.label1)		# remove this labeled atom from labels[]
			except:	pass
		return labels


	def FindClosestAtomDistance(self, xyz0IN, xyzIN):
		# returns a direction vector to the atom in xyzIN[N][3] that is closest to xyz0IN[3]
		# xyz0IN[3]				reference location
		# xyzIN[N][3]			set of atom positions (nm),  NOT fractional
		if type(xyzIN) is list:		xyz = np.asarray(xyzIN, dtype=np.double)
		elif type(xyzIN) is tuple:	xyz = np.asarray(xyzIN, dtype=np.double)
		else:						xyz = xyzIN

		if type(xyz0IN) is list:	xyz0 = np.asarray(xyz0IN, dtype=np.double)
		elif type(xyz0IN) is tuple:	xyz0 = np.asarray(xyz0IN, dtype=np.double)
		else:						xyz0 = xyz0IN

		min2 = Lattice_minBondLen*Lattice_minBondLen
		dmag2 = np.sum(np.square(xyz - xyz0.T),axis=1)
		dmag2[dmag2 < min2] = np.Inf	# ignore atoms that are too close
		blen2 = dmag2[dmag2.argmin()]	# bond length squared
		return math.sqrt(float(blen2))	# return a simple float, not a numpy.double


	def FindCentralAtom(self, xyzIN):
		# return xyz0 the single position in xyzIN that is most closely represents the central atom in xyzIN
		# xyzIN is usually an atoms[i].xyz
		if type(xyzIN) is list:		NPxyz = np.asarray(xyzIN, dtype=np.double)
		elif type(xyzIN) is tuple:	NPxyz = np.asarray(xyzIN, dtype=np.double)
		else:						NPxyz = xyzIN
		Natom = len(NPxyz)
		avg = NPxyz.sum(axis=0)/Natom
		dxyz2 = np.sqrt(np.sum(np.square(NPxyz - avg),axis=1))
		center = xyzIN[dxyz2.argmin()]
		center = np.array([float(center[0]), float(center[1]), float(center[2])])
		return center


	def ExtendFractional(self,xyz0,delta):
		# return a new set of [xyz] extend by ±delta in fractional coordinates
		# xyz0 (fractional coords) covering only 1 cell, also want to include ±delta in x, y, & z
		# xyz0 is usually an atoms[i].xyz
		N0 = len(xyz0)
		delta = abs(float(delta))
		xyz = list(xyz0)						# copy xyz --> xyz0 (an actual copy), contains one cell, i.e. all {x,y,z} in [0,1)
		offsets = [[-1,-1,-1], [0,-1,-1], [1,-1,-1], [-1,0,-1], [0,0,-1], [1,0,-1], [-1,1,-1], [0,1,-1], [1,1,-1], [-1,-1,0], 
				[0,-1,0], [1,-1,0], [-1,0,0], [1,0,0], [-1,1,0], [0,1,0], [1,1,0], [-1,-1,1], [0,-1,1], [1,-1,1], [-1,0,1], 
				[0,0,1], [1,0,1], [-1,1,1], [0,1,1], [1,1,1]]

		for offset in offsets:					# for each of the 26 offsets, add atoms to xyz
			xyzTest = xyz0 + np.full([N0,3], offset)
			flagX = np.logical_and(np.greater(xyzTest[:,0],-delta), np.greater(1+delta, xyzTest[:,0]))
			flagY = np.logical_and(np.greater(xyzTest[:,1],-delta), np.greater(1+delta, xyzTest[:,1]))
			flagZ = np.logical_and(np.greater(xyzTest[:,2],-delta), np.greater(1+delta, xyzTest[:,2]))
			flags = np.logical_and(np.logical_and(flagX,flagY),flagZ)	# flags is 1 if x, y, & z are all in range (-delta, 1+delta)
			Nadd = flags.sum()					# number of points in xyzTest that I will add to xyz
			if Nadd > 0:
				xyzTemp = np.full([Nadd,3], 0)
				m = 0
				for i in range(N0):				# for each position in xyzTest[i][3] with flags[i] True: add to xyz[i][3]
					if flags[i]:
						xyzTemp[m,:] = xyzTest[i,:]
						m += 1
				xyz = np.concatenate([xyz,xyzTemp], axis=0)

		return xyz


#	def __str__(self):
#		if not self.bonds: return 'NO Computed bonds\n'
#
#		out = 'Computed %r bonds:\n' % (len(self.bonds))
#		for bond in self.bonds: out += str(bond) + '\n'
#
#		if self.unassociated:				# print list of those atoms not associated with a bond
#			out += 'The following atom types do not have any bonds: '+str(self.unbondedAtoms)
#		else:
#			out += '    All atom types are associated with a bond.'
#		return out


	def bond_testing(self, bondsExpected, printIt=True):
		cb = self.ComputeBonds(overwrite=True)
		errStr = cb[0].bondListsDiffer(bondsExpected, cb)
		if printIt:
			print ('     ******************  %r calculated bonds:' % (len(cb),))
			for bond in cb: print (bond)
			print ('     ****************** end of calculated bonds')
		if len(errStr)>0:
			nbonds = 0
			if bondsExpected:
				try: nbonds = len(bondsExpected)
				except:	nbonds = 1
			print ('     ******************  %r expected bonds:' % (nbonds,))
			if nbonds==1: print (bondsExpected)
			elif nbonds>1:
				for bond in bondsExpected: print (bond)
			print ('     ****************** end of expected bonds')
		return errStr



#	def makeArrays(self):
#		# make arrays Zs[], Types[], xyz[][3]	when done, xyz are real coordinates in nm
#
#		Ntypes = len(self.lattice.atoms)			# number of atom types
#		# fractional coords of atom[m] in 1 cell are already in: self.lattice.atoms[m].xyz
#
#		# Make/N=(1,3)/D/FREE xyz					# remember, these xyz are in fractional coordinates
#		# Make/N=(1)/D/FREE Zs						# start small will be redimensioned as atoms are added
#		# Make/N=(1)/T/FREE Types
#
#		xyz = np.empty([0,3], dtype=np.double)
#		Zs = np.empty([0], dtype=np.double)
#		Types = []
#
#		Natom = lo = 0
#		for atom in self.lattice.atoms:
#			occupyi = atom.occ
#			Zi = atom.Z
#			label = atom.label
#			Ni = len(atom.xyz)
#			if Ni<1 or occupyi<0.1: continue		# not fatal, but does not deserve a bond
#			Natom += Ni
#			xyz = np.concatenate([xyz,atom.xyz], axis=0)
#
#			Ztemp = np.full([Ni], Zi)
#			Zs = np.concatenate([Zs,Ztemp], axis=0)
#
#			TypesTemp = [label] * Ni
#			Types += TypesTemp
#
##		print len(Zs), Zs
##		print len(Types), Types
##		print len(xyz), xyz
#
#
#		# xyz (fractional coords) only covers 1 cell, also want to include ±0.5 in x, y, & z
#		offsets = [[-1,-1,-1], [0,-1,-1], [1,-1,-1], [-1,0,-1], [0,0,-1], [1,0,-1], [-1,1,-1], [0,1,-1], [1,1,-1], [-1,-1,0], 
#				[0,-1,0], [1,-1,0], [-1,0,0], [1,0,0], [-1,1,0], [0,1,0], [1,1,0], [-1,-1,1], [0,-1,1], [1,-1,1], [-1,0,1], 
#				[0,0,1], [1,0,1], [-1,1,1], [0,1,1], [1,1,1]]
#
#		xyz0 = list(xyz)						# contains one cell, i.e. all {x,y,z} in [0,1)
#		Nxyz = Natom							# Nxyz is number of points in xyz[Nxyz][3], this will be > Natom
#
##		print "Natom =",Natom
#		for offset in offsets:					# for each of the offsets, add atoms to xyz, Zs, & Types
#			xyzTest = xyz0 + np.full([Natom,3], offset)
#			flagX = np.logical_and(np.greater(xyzTest[:,0],-0.5), np.greater(1.5,xyzTest[:,0]))
#			flagY = np.logical_and(np.greater(xyzTest[:,1],-0.5), np.greater(1.5,xyzTest[:,1]))
#			flagZ = np.logical_and(np.greater(xyzTest[:,2],-0.5), np.greater(1.5,xyzTest[:,2]))
#			flags = np.logical_and(np.logical_and(flagX,flagY),flagZ)	# flags is 1 if x, y, & z are all in range (-0.5, 1.5)
#			Nadd = flags.sum()					# number of points in xyzTest that I will add to xyz
#
#			if Nadd > 0:
#				TypesTemp = [""] * Nadd
#				ZTemp = [0] * Nadd
#				xyzTemp = np.full([Nadd,3], 0)
#				m = 0
#				for i in range(Natom):				# for each position in xyzTest[i][3] with flags[i] True: add to xyz[i][3]
#					if flags[i]:
#						xyzTemp[m,:] = xyzTest[i,:]
#						ZTemp[m] = Zs[i]
#						TypesTemp[m] = Types[i]
#						m += 1
#
#				xyz = np.concatenate([xyz,xyzTemp], axis=0)
#				Zs = np.concatenate([Zs,ZTemp], axis=0)
#				Types += TypesTemp
#				Nxyz += Nadd
#
##		print "Nxyz =",Nxyz
#		xyz = np.dot(self.lattice.direct, xyz.T).T	# convert xyz[Nxyz][3] from fractional coords --> real lengths (nm)
#
#		self.xyz = xyz
#		self.Zs = Zs
#		self.Types = Types
#
#		self.FindBonds()							# find bonds using xyz[Nxyz][3], Zs[Nxyz], & Types[Nxyz]
#
#
#	def FindBonds(self):
#		"""
#		Uses:
#		xyz			xyz[N][3] positions of atoms
#		Zs			Zs[N] atomic number of each atom
#		Types		Types[N] atom type for each atom
#		"""
#
#		N = self.Zs.shape[0]						# number of atoms given, also dim of Zs[N] and Types[N]
#
#		atomTypes = list(set(self.Types))			# remove all duplicates
#		NatomTypes = len(atomTypes)					# number of unique atom types
##		print 'N = ',N,'   atomTypes = ',atomTypes, atomTypes[0]
#
#		# get index into atomTypes for each atom in xyz, itypes[N]
#		itypes = [-1]*N
#		m = 0
#		for name in atomTypes:						# itypes[N] is integer corresponding to the atom type (faster to compare numbers)
#			for i in range(N):						# set itypes[] only for those atom.name matching each Types[i]
#				if name == self.Types[i]: itypes[i] = m
#			m += 1
#
##		print 'itypes =',itypes
#		# get the Z of each atom in atomTypes
#		ZatomTypes = [-1.0]*NatomTypes
#		for ity in range(NatomTypes):
#			i = np.equal(itypes,ity).argmax()
#			ZatomTypes[ity] = self.Zs[i]
#
##		print 'ZatomTypes =',ZatomTypes
#
#		# now have atomTypes[NatomTypes] & ZatomTypes[NatomTypes]
#		# also have itypes[N], this id's the atom type for each atom
#
#		ElectroNeg = [100.0] * NatomTypes
#		covRad = [0.0] * NatomTypes
#		for i in range(NatomTypes):
#			eInfo = elementInfo(int(ZatomTypes[i]))
#			ElectroNeg[i] = eInfo.electroneg		# electronegativity
#			covRad[i] = eInfo.covRadius / 10.0		# radius in nm
#
#		metalic = (max(ElectroNeg)-min(ElectroNeg)) < 0.7	# if metalic, then do not worry about ElectroNegativity
#
#		NbAll = N*(N-1)/2							# number of atom pairs
#		blenAll = np.full(NbAll, Lattice_maxBondLen+1)
#		type1All = np.full(NbAll, -1, dtype=np.int32)
#		type2All = np.full(NbAll, -1, dtype=np.int32)
#		Z1All = np.full(NbAll, -1.0)
#		Z2All = np.full(NbAll, -1.0)
#
#		# Find ALL inter-atomic distances
#		m = 0
#		for j in range(N-1):
#			xyzj = self.xyz[j,:]					# for each atom[j], compare atom[j] to all of the others
#			typej = itypes[j]
#			dxyz = np.sqrt(np.sum(np.square(self.xyz - xyzj),axis=1))
#			mLast = m + N-j-2
#
#			for i in range(m, mLast):
#				ddd = dxyz[i-m+j+1,0]
#				if Lattice_minBondLen < ddd and ddd < Lattice_maxBondLen:
#					blenAll[i] = ddd				# append dxyz[j+1,Inf] to blen, dxyz[0,j] have already been included
#					type1All[i] = typej				# 	and the types of both of the atoms involved
#					type2All[i] = itypes[i-m+j+1]
#			m = mLast + 1
#
#		for i in range(NbAll):
#			Z1All[i] = ZatomTypes[type1All[i]]
#			Z2All[i] = ZatomTypes[type2All[i]]
#
#		if not metalic:
#			for i in range(NbAll):
#				# cannot have an atom type bonded to itself,  or  have two elements of same Z bonded together
#				if type1All[i]==type2All[i] or Z1All[i]==Z2All[i]: blenAll[i] = Lattice_maxBondLen+1
#
#
#		#	Sort blenAll, blenAll,type1All,type2All,Z1All,Z2All
#		isort = np.argsort(blenAll)
#		blenAll = np.array(blenAll)[isort]
#		type1All = np.array(type1All)[isort]
#		type2All = np.array(type2All)[isort]
#		Z1All = np.array(Z1All)[isort]
#		Z2All = np.array(Z2All)[isort]
##		print "blenAll =",blenAll
#
#		nn = NbAll
#		NbAll = 0
#		for i in range(nn):
#			if blenAll[i] < Lattice_maxBondLen: NbAll += 1
#
#		blenAll.resize(NbAll)
#		type1All.resize(NbAll)
#		type2All.resize(NbAll)
#		Z1All.resize(NbAll)
#		Z2All.resize(NbAll)
#		# blenAll is sorted list of all lengths in range [0.05, 0.31]nm
#
#		for j in range(NbAll):						# ensure that type1All <= type2All
#			if type2All[j] < type1All[j]:
#				i = type1All[j]						# swap values
#				type1All[j] = type2All[j]
#				type2All[j] = i
#
#		blen = np.full(NbAll, -1.0)
#		type1 = np.full(NbAll, -1, dtype=np.int32)
#		type2 = np.full(NbAll, -1, dtype=np.int32)
#		Z1 = np.full(NbAll, -1.0)
#		Z2 = np.full(NbAll, -1.0)
#
#		NbUnique = 0								# number of unique atom pairs
#		for j in range(NbAll):						# remove duplicate bonds & bonds with wildly wrong lengths
#			t1j = type1All[j]
#			t2j = type2All[j]
#			dist = covRad[t1j] + covRad[t2j]		# predicted covalent bond length
#			dupFlag = np.any( np.logical_and(np.equal(type1,t1j), np.equal(type2,t2j)) )
#
#			if (not dupFlag and 0.7*dist < blenAll[j] and blenAll[j] < 1.3*dist):	# not a duplicate, and radius not too far off
#				blen[NbUnique] = blenAll[j]
#				type1[NbUnique] = type1All[j]
#				type2[NbUnique] = type2All[j]
#				Z1[NbUnique] = Z1All[j]
#				Z2[NbUnique] = Z2All[j]
#				NbUnique += 1
#
##		print 'NbUnique =',NbUnique
#		blen.resize(NbUnique)
#		type1.resize(NbUnique)
#		type2.resize(NbUnique)
#		Z1.resize(NbUnique)
#		Z2.resize(NbUnique)
#
#
#		valence = np.full(NatomTypes, 0, dtype=np.int32)
#		if not metalic:								# not metalic, set the valences to ±1
##			Variable v1,v2, iv
#			for m in range(NbUnique):
#				v1 = valence[type1[m]]
#				v2 = valence[type2[m]]
#				if v1 and v2:						# both have been set
#					continue
#				elif v1:							# v1 was set, v2=-v1
#					valence[type2[m]] = -v1
#				elif v2:							# v2 was set, v1=-v2
#					valence[type1[m]] = -v2
#				else:								# neither valence has been set, set both using electronegativity
#					if ElectroNeg[type1[m]] > ElectroNeg[type2[m]]: iv = -1
#					else:	iv = 1
#					valence[type1[m]] = iv
#					valence[type2[m]] = -iv
#
#			# remove bonds where both atoms have same valence or it is 0 (this is not metalic)
#			for m in range(NbUnique):
#				if valence[type1[m]] * valence[type2[m]] >= 0:	# the same or zero
#					blen = np.delete(blen,m)
#					type1 = np.delete(type1,m)
#					type2 = np.delete(type2,m)
#					Z1 = np.delete(Z1,m)
#					Z2 = np.delete(Z2,m)
#					m -= 1
#					NbUnique -= 1
#
#			blen.resize(NbUnique)
#			type1.resize(NbUnique)
#			type2.resize(NbUnique)
#			Z1.resize(NbUnique)
#			Z2.resize(NbUnique)
#
#
##		atomTypes = list(set(self.Types))			# remove all duplicates
#		self.used = np.full(NatomTypes, 0, dtype=np.int32)
#		for m in range(NatomTypes):
#			if m in type1: self.used[m] = 1
#			if m in type2: self.used[m] = 1
#
#		self.unassociated = NatomTypes - np.sum(self.used)
#
#		self.atomTypes = atomTypes
#		self.ZatomTypes = ZatomTypes
#		self.NatomTypes = NatomTypes
#		self.Nbonds = NbUnique
#		self.blen = blen
#		self.type1 = type1
#		self.type2 = type2
#		self.Z1 = Z1
#		self.Z2 = Z2
#		self.valence = valence


#	def __str__(self):
#		out = 'Computed %d bonds:\n' % (self.Nbonds,)
#		for i in range(self.Nbonds):
#			i1 = self.type1
#			i2 = self.type2
#
#			if self.valence[i1] < 0: s1 = '-'
#			elif self.valence[i1] > 0: s1 = '+'
#			else: s1 = ''
#			if self.valence[i2] < 0: s2 = '-'
#			elif self.valence[i2] > 0: s2 = '+'
#			else: s2 = ''
#			z1 = self.Z1[i1]
#			z2 = self.Z1[i2]
#			out += "     %s%s(%d)  <-->  %s%s(%d):  %.4g" % (s1,self.atomTypes[i1],z1,s2,self.atomTypes[i2],z2,self.blen[i])
#			if i==0: out += ' (nm)'
#			out += '\n'
#
#		if self.unassociated:						# print list of those atoms not associated with a bond
#			out += "The following atom types do not have any bonds:"
#			for m in range(self.NatomTypes):
#				if not self.used[m]:
#					if self.valence[i1] < 0: s1 = '-'
#					elif self.valence[i1] > 0: s1 = '+'
#					else: s1 = ''
#					out += "   %s%s(%d)\r",s1,self.atomTypes[m],self.ZatomTypes[m]
#		else:
#			out += "    All atom types are associated with at least 1 bond."
#		return out

def listShape(ll):
	try:	return ll.shape
	except:	pass

	shape = ()
	ltest = ll
	while True:
		try:
			i = len(ltest)
			if i<2: break
			shape += (i,)
			ltest = ltest[0]
		except:
			break
	return shape

if __name__ == '__main__':
	"""
	Main function for bondCalc.py.

	Test cases for bondCalc class to verify correct behavior.
	"""
	from JZTutil import JZTtesting
	testing = JZTtesting(__file__)

	"""
	atomSi = atomXtal('Si',(0,0,0))
	bondSi = bondType('Si','Si',  0.54310206*math.sqrt(3.0)/4.0)	# 0.54310206*math.sqrt(3.0)/4.0 = 0.23517
	silicon = Lattice(227, 0.54310206,0,0, 0,0,0, desc='Silicon', atoms=(atomSi,), bonds=(bondSi,))
	"""


	"""
	def make_Sapphire():
		atomAl = atomXtal('Al1',(0,0,0.3523),valence=+3,DebyeT=1047)
		atomO = atomXtal('O1',(0.3064,0,0.25),valence=-2,DebyeT=1047)
		return Lattice(167, 0.4758,0,1.2991, 90,90,120, desc='Al2O3 Sapphire (hexagonal)',atoms=(atomAl,atomO))

	def make_SapphireRhom():
		atomAl = atomXtal('Al1',(0.3523,0.3523,0.3523),valence=+3,DebyeT=1047)
		atomO = atomXtal('O1',(0.5564,0.9436,0.25),valence=-2,DebyeT=1047)
		return Lattice('167:R', 0.5128155,0.5128155,0.5128155, 55.27934,55.27934,55.27934, desc='Al2O3 Sapphire (Rhombohedral)',atoms=(atomAl,atomO))

	sapphire = make_Sapphire()
	sapphireRhom = make_SapphireRhom()
	"""


	"""
	def test_findClosestHKL(xtal,d, dtest):
		l = xtal.findClosestHKL(d)

		if math.fabs(dtest - l[0]['dhkl']) < 1e-6:
			print '     in "%s", closest d-spacing to %g nm, there are %d close:' % (xtal.desc, d, len(l))
			err = False
		else:
			print 'ERR  in "%s", closest d-spacing to %g nm, there are %d close:' % (xtal.desc, d, len(l))
			err = True

		for d in l: print d
		return err
	"""


	atomsDiamond = [(0, 0, 0), (0.25, 0.25, 0.25), (0, 0.5, 0.5), (0.25, 0.75, 0.75), (0.5, 0, 0.5), (0.75, 0.25, 0.75), (0.5, 0.5, 0), (0.75, 0.75, 0.25)]

	if testing.doit('test ExtendFractional():'):		#  2**0 = 1
		err = False
		cb = bondCalc()

		xyz = [[0.1, 0.2, 0.3]]
		print ('     before: xyz0 =',xyz,'  extended it becomes:\n',cb.ExtendFractional(xyz, 0.5))

		xyz = [[0.7, 0.8, 0.9]]
		print (' ')
		print ('     before: xyz0 =',xyz,'  extended it becomes:\n',cb.ExtendFractional(xyz, 0.5))

		xyz = [[0.1, 0.2, 0.3], [0.7, 0.8, 0.9]]
		print (' ')
		print ('     before: xyz0 =',xyz,'  extended it becomes:\n',cb.ExtendFractional(xyz, 0.5))
		if err: testing.addErr()


	if testing.doit('test FindCentralAtom():'):			#  2**1 = 2
		cb = bondCalc()
		xyz0 = cb.FindCentralAtom(atomsDiamond)
		print ('     for diamond structure, central most atom is:  ',xyz0)
		desired = [0.25, 0.25, 0.25]
		c = (np.array(xyz0) == np.array(desired))
		err = np.sum(c) < 3
		if err: testing.addErr()


	if testing.doit('test FindClosestAtomDistance():'):	#  2**2 = 4
		cb = bondCalc()
		xyz0 = cb.FindCentralAtom(atomsDiamond)
		dxyz = cb.FindClosestAtomDistance(xyz0, atomsDiamond)
		print ('     using central most atom =',xyz0,'  nearest neighbor distance = ',dxyz)
		err = abs(dxyz-0.433012701892)>1e-12
		if err:
			print ('ERR  nearest neighbor distance is off by %g:' % (dxyz-0.433012701892,))
			testing.addErr()


	if testing.doit('test listShape():'):	#  2**3 = 8
		err = False

		ll = [1,2,3]
		sh = listShape(ll)
		err = err or (sh != (3,))
		print ('err = %r\t%r --> %r' % (err,ll,sh))

		ll = [[1,2,3],[5,6,7]]
		sh = listShape(ll)
		err = err or (sh != (2,3))
		print ('err = %r\t%r --> %r' % (err,ll,sh))

		print ('\nnow trying with numpy:')
		lnp = np.array([1,2,3])
		sh = listShape(lnp)
		err = err or (sh != (3,))
		print ('err = %r\t%r --> %r' % (err,lnp,sh))

		lnp = np.array([[1,2,3],[5,6,7]])
		sh = listShape(lnp)
		err = err or (sh != (2, 3))
		print ('err = %r\t%r --> %r' % (err,lnp,sh))

		if err:
			print ('ERR  problem in listShape()')
			testing.addErr()


	"""
	if testing.doit('test finding Si bonds:'):
		cb = bondCalc(silicon, overwrite=True)
		errStr = bondSi.bondsDiffer((bondSi,), cb.bonds)
		print cb
		if len(errStr)>0:
			print '\nERR, ',errStr
			print '    the given Si bond is:',silicon.bonds[0]
			testing.addErr()


	if testing.doit('test finding GaAs bonds:'):
		GaAs = Lattice(0, 0,0,0,0,0,0,file='test/GaAs.xml')
		cb = bondCalc(GaAs, overwrite=True)
		errStr = bondSi.bondsDiffer(GaAs.bonds, cb.bonds)
		print cb
		if len(errStr)>0:
			print '\nERR, ',errStr
			print 'specified bonds:'
			for bond in GaAs.bonds: print bond
			testing.addErr()


	if testing.doit('test finding YBCO bonds:'):
		YBCOfile = Lattice(0, 0,0,0,0,0,0,file='test/test_YBCO.xml')
		cb = bondCalc(YBCOfile, overwrite=True)
#		errStr = bondSi.bondsDiffer(YBCOfile.bonds, cb.bonds, lenTol=1e-4)
		errStr = bondSi.bondsDiffer(YBCOfile.bonds, cb.bonds)
		print cb
		if len(errStr)>0:
			print '\nERR, ',errStr
			print 'specified bonds:'
			for bond in YBCOfile.bonds: print bond
			testing.addErr()


	if testing.doit('test finding quartz bonds:'):
		quartz = Lattice(0, 0,0,0,0,0,0,file='test/quartz_alpha.xml')
		cb = bondCalc(quartz, overwrite=True)
		# errStr = bondSi.bondsDiffer(quartz.bonds, cb.bonds)
		errStr = ''
		print cb
		if len(errStr)>0:
			print '\nERR, ',errStr
			print 'specified bonds:'
			for bond in quartz.bonds: print bond
			testing.addErr()


	if testing.doit('test finding Saenger bonds:'):
		Saenger = Lattice(0, 0,0,0,0,0,0,file='test/Saenger.cif')
		cb = bondCalc(Saenger, overwrite=True)
		# errStr = bondSi.bondsDiffer(Saenger.bonds, cb.bonds)
		errStr = ''
		print cb
		if len(errStr)>0:
			print '\nERR, ',errStr
			print 'specified bonds:'
			for bond in Saenger.bonds: print bond
			testing.addErr()


	if testing.doit('test finding Chakraborty bonds:'):
		errStr = ''
		Chakraborty = None
		try:
			Chakraborty = Lattice(0, 0,0,0,0,0,0,file='test/Chakraborty.cif')
			cb = bondCalc(Chakraborty, overwrite=True)
			# errStr = bondSi.bondsDiffer(Chakraborty.bonds, cb.bonds)
			errStr = ''
			print cb
		except:
			errStr = 'Cannot read the file  "test/Chakraborty.cif"'
		if len(errStr)>0:
			print '\nERR, ',errStr
			if Chakraborty:
				print 'specified bonds:'
				for bond in Chakraborty.bonds: print bond
			testing.addErr()
	"""



	testing.ending()
