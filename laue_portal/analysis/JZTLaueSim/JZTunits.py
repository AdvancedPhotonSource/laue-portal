#!/usr/bin/env python
# -*- coding: utf-8 -*-

import math
import copy
import string
basestring = str



__version__ = "$Revision: $"
__author__  = "Jon Tischler, <tischler@aps.anl.gov>" +\
              "Argonne National Laboratory"
__date__    = "$Date: $"
__id__      = "$Id: $"


is2019 = False

"""
SI base Units:  angle[rad], length,[m] mass[kg], time[s], current[A], Temperature[K], light[cd], quantity[mole]


Usage:
	>>> from JZTunits import UnitsJZTdefault as units
	>>> print units('5 Å','pm')			# this uses the __call__ so you don't need the ".convert"
	500 [pm]							# this is a PhQ()
	>>> print units('5 Å','pm').num		# this returns just a number
	500.0

or:
	>>> from JZTunits import unitConvert
	>>> unitConvert('0.12 kg m/s^2','kgf')
	PhQ<num=0.012236594555735138, ustr=kgf, dims=[0, 1, 1, -2, 0, 0, 0, 0], SIstr='m kg s^-2', scale=9.80665, dimType='force'>
	>>> print unitConvert('0.12 kg m/s^2','SI')
	0.12 [N]
 
or:
	>>> from JZTunits import UnitsJZT
	>>> units = UnitsJZT()
	>>> units.convert(5,'Å','nm')
	>>> units.convert('5 Å','nm')
	>>> units(5,'Å','nm')
	>>> print units('5 Å','nm')			# this uses the __call__ so you don't need the ".convert"
	0.5 [nm]

or:
	>>> from JZTunits import MakeStandardUnits, UnitsJZT
	>>> allUnits = MakeStandardUnits()		# you may substitute your own routine for MakeStandardUnits()
	>>> units = UnitsJZT(units=allUnits)
	>>> units.convert(5,'Å','nm')
	PhQ<num=0.5, ustr=nm, dims=[0, 1, 0, 0, 0, 0, 0, 0], SIstr='m', scale=1e-09, dimType='length'>
	>>> print units.convert('5 Å','pm')
	500 [pm]
	>>> print units('5 Å','pm')			# this uses the __call__ so you don't need the ".convert"
	500 [pm]

or:
	You can call from the command line as in one of these examples:
		$ ./JZTunits.py 1 '2 acres' hectare
		 2 [acres]  →  8093.71 [m^2](SI)  →  0.80937128448 [ha]

		$ ./JZTunits.py 1 "1.5 Å" "keV"
	     1.5 [Å]  →  1.3243e-15 [J](SI)  →  8.265613159±9.9e-08 [keV]

		$ ./JZTunits.py 1 '1e4 dyne' kg*m/s^2
		 10000 [dyne]  →  0.1 [N](SI)  →  0.1 [((kg) (m))/((s)^2)]

		$ ./JZTunits.py 1 '12 keV' 'Å'
		 12 [keV]  →  1.0332e-10 [m](SI)  →  1.033201645±1.2e-08 [Å]


NOTE:
	There are 22 unavoidable conflicts.
	some examples are:
		'min' is assumed to mean 'minute', but could be '0.001 inch' (but, 1 minch  is  0.0254 m)
		'hbar' is assumed to be 'h/2*PI', but it could be '100 bar' (but hectobar or mbar is a pressure)
		'cc' is assumed to mean 'cubic-centimer', but could be '0.01 * speed of light'
		'pc' is assumed to mean 'parsec', but could be '1e-12 * speed of light'
		'me' is assumed to mean 'mass of electron', but could be '0.001*e'(e is base of natural log)
			the reset are even more obscure. 
	you can see a full list by running:
		./JZTunits.py 2**20

	there are also some conflicts with multiple prefixes, e.g.  mps could also be "milli-pico-sec", but this assumes "meter/sec"

	Also: you only need to have JZTutil.py to run the testing.
	the only modules that are always imported are:
		math, copy, string
"""

global UnitsJZTdefault
UnitsJZTdefault = None

def unitConvert(first,middle,last=None):
	"""
	can be called as:
		unitConvert(5,'cm','inch')
		unitConvert('5 cm','inch')
		unitConvert('5 cm','','inch')
		unitConvert((5,'cm'),'','inch')
	the last argument is always the output unit
	the first is either a number or a number+unit
	the middle argument (if there are 3) is input unit (or more of the input unit)
	"""
	return UnitsJZTdefault.convert(first,middle,last)


def ConvertTemperatureUnits(Tin, unitIN, unitOUT=None, defaultUnit='Celsius'):
	"""
	This function is just for convineence and compatibility with some other programs
	converts Temperature[unitIN] --> Temperature[unitOUT]
	if unitIN is empty, then assume unitIN=defaultUnit
	"""
	if not unitIN: unitIN = defaultUnit
	if not unitOUT: unitOUT = defaultUnit
	if unitIN.lower()  in {'c','celsius'}: unitIN = 'Celsius'
	if unitOUT.lower() in {'c','celsius'}: unitOUT = 'Celsius'
	if unitIN.lower() == 'k': unitIN = 'Kelvin'
	if unitOUT.lower() == 'k': unitOUT = 'Kelvin'
	uuu = UnitsJZTdefault((Tin,unitIN), unitOUT)
	if uuu.dimType != 'Temperature': raise ValueError('ERROR -- ConvertTemperatureUnits(), both  %r  and  %r  must be Temperatures' % (unitIN,unitOUT))
	return uuu.num


SI_N = 8		# number of SI dims in SI system, [angle, length, mass, time, current, Temp, Lum, mole]


	# math constants
pi					= math.pi
ln10				= math.log(10)				# natural log of 10, ln(10)

	# physical constants
c					= 299792458.0				# exact speed of light (m/s)
me					= 9.10938356e-31			# mass of electron (kg)
GN					= 6.67408e-11				# Newton Gravity Constant (m^3 kg^-1 s^-2)

if is2019:			# for 2019 CODATA
	h				= 6.62607015e-34			# Planck Constant / 2pi (J s)  [Exact]
	e				= 1.602176634e-19			# Charge on electron (C)
	kB				= 1.380649e-23				# Boltzmann constant (J/K)
	NA				= 6.02214076e23				# Avogadro Number
	# Kcd is equal to 683 lumens per watt and helps to define the candela. 
	hbar			= h/(2*math.pi)				# Planck Constant / 2pi (J s)
	alpha			= c*e*e / hbar * 1e-7		# fine structure constant approx. 1/137,  = c*e*e / hbar * 1e-7	
	Rinf			= alpha*alpha*me*c / (2*h)	# Rydberg constant = Rinf [1/m]
	Rinf_hc			= Rinf*h*c					# Rydberg*hc (J)
	kB_eV			= kB/e						# Boltzmann constant (eV/K)

else:
	h				= 6.626070040e-34			# Planck Constant (J s)
	hbar			= 1.054571800e-34			# Planck Constant / 2pi (J s)
	kB				= 1.38064852e-23			# Boltzmann constant (J/K), updated March 2017
	e				= 1.6021766208e-19			# Charge on electron (C)
	NA				= 6.022140857e23			# Avogadro Number
	alpha			= 0.0072973525664			# fine structure constant approx. 1/137,  = c*e*e / hbar * 1e-7	
	kB_eV			= 8.6173303e-5				# Boltzmann constant (eV/K), updated March 2017
	Rinf			= 10973731.568508			# Rydberg constant = Rinf [1/m]
	Rinf_hc			= 2.179872325e-18			# Rydberg*hc (J)

	# length constants
inch				= 0.0254					# length of inch (m)
foot				= 12*inch					# 1 foot is 12 inches
mile				= 5280 * 12*inch			# length of mile (m),  5280 feet
kgPerPound			= 0.45359237				# 1 pound = 0.45359237 kgm [definition of pound]
gStd				= 9.80665					# std acceleration of gravity (m s^-2)

	# angle constants
degree				= 2.0*(math.pi) / 360.0		# number of radians in 1 degree
grad				= 2.0*(math.pi) / 400.0		# number of radians in 1 grad

	# time constants
tropicalYear		= 365.24219 * 24*3600		# seconds in a tropical year (NOT sidereal), there are 365.24219 days in 1 tropical year
julianYear			= 365.25 * 24*3600			# seconds in a Julian year, there are exactly 365.25 days in 1 Julian year
hour				= 3600.0					# seconds in 1 hour
day					= 24.0*hour					# seconds in 1 day
year				= tropicalYear				# seconds in 1 tropical year
siderealYear		= 365.256363004*day			# seconds in 1 sidereal year
siderealDay			= 23.9344699*hour			# seconds in 1 sidereal day
lunarMonth			= 29.530588*day				# seconds in 1 lunar month
PlanckTime			= math.sqrt(hbar*GN/(c**5))	# = 1.616199e-35 (s)

	# length constants
CuXunit				= 1.00207697e-13
MoXunit				= 1.00209952e-13
Xunit				= 1.002088e-13
Si220				= 1.920155716e-10			# Si(220) lattice constant
PlanckLength		= math.sqrt(hbar*GN/c/c/c)
AstronomicalUnit	= 149597870700.0			# IAU 2009,2012
parsec				= AstronomicalUnit * (180.0*3600.0) / math.pi	# = 3.08568025e16 (m), IAU 2015 definition
LightYear			= c * julianYear			# = 9460730472580800 m
if is2019:			# for 2019 CODATA
	BohrRadius		= hbar / (me*c*alpha)		# hbar / (me c alpha) = 4*pi*eps0*hbar^2 / (me e^2)
else:
	BohrRadius		= 0.52917721092e-10			# hbar / (me c alpha) = 4*pi*eps0*hbar^2 / (me e^2)

	# mass constants
PlanckMass			= math.sqrt(hbar*c/GN)		# = 2.1764702e-08
amu					= 1.66053904e-27
mSol				= 1.9891E30
mEarth				= 5.9722e24
muon				= 1.883531594e-28
#me					= 9.10938356e-31
mproton				= 1.672621898e-27
mneutron			= 1.674927471e-27
troy				= 5.760*0.06479891

	# Temperature constants
PlanckTemperature	= math.sqrt(hbar * c**5 / (GN * kB*kB))	# = 1.416833e32 (K)
CelsiusK			= 273.15					# 0 Celsius in Kelvin, you can access this as self.CelsiusK
NormalT_C			= 20						# Normal Temperature in Celsius, access this as self.NormalT_C
NormalT_K			= 20 + CelsiusK				# Normal Temperature in Kelvin, access this as self.NormalT_K
NormalT_F			= (1.8 * NormalT_C) + 32.0	# Normal Temperature in Fahrenheit, access this as self.NormalT_F
NormalT_eV			= NormalT_K * kB_eV			# Normal Temperature in eV, access this as self.NormalT_eV

	# area constants
ft_2				= foot*foot					# 1 square foot = (12*0.0254)**2 square meter

	# volume constants
liter				= 0.001						# 1 liter		= 0.001 meter^3
USpint				= 0.56826125 * liter		# 0.56826125 l	= 1 US pint
USfloz				= USpint/16 * liter			# 16 floz		= 1 US pint
ImpPint				= 0.473176473 * liter		# 0.473176473 l	= 1 Imperial pint
Impfloz				= ImpPint/20. * liter		# 20 Imp floz	= 1 Imp pint
ft_3				= foot*foot*foot			# 1 cubic foot	= (12*0.0254)**3 cubic m
in_3				= inch*inch*inch			# 1 cubic inch	= (0.0254)**3 cubic m

	# energy constants
BTU					= 1055.06					# 1 BTU				= 1055.06 J
PlanckEnergy		= math.sqrt(hbar*(c**5)/GN)	# Planck energy (J)	= 1.956113e9
cal					= 4.184						# 1 calorie is 4.184 J

	# power constants
HP					= 550*foot* kgPerPound*gStd	# 1 horse power

	# miscellaneous physical constants
comptonLength		= (2*pi*hbar)/(me*c)		# electron Compton wavelength = h/(me c)
sigma				= (pi**2)*(kB**4) / (60.0*(hbar**3)*(c**2))	# for Stefan-Boltzman


debug = depth = 0

# knownDimensions, each tuple is (dimsArray, SI_unit, name)		[rad,m,kg,sec,A,K,cd,mole]
# this lists all of the dimensions that are named, all defined dimensions are included here.
knownDimensions = [([0,0,0,0,0,0,0,0], '', 'pure number'),
	([1,0,0,0,0,0,0,0],  'rad', 'angle'), 				([2,0,0,0,0,0,0,0],   'rad^2', 'solid angle'),
	([0,1,0,0,0,0,0,0],  'm', 'length'),
	([0,0,0,1,0,0,0,0],  's', 'time'),					([0,0,0,-1,0,0,0,0],  's^-1', 'frequency'),
	([0,0,1,0,0,0,0,0],  'kg', 'mass'),
	([0,2,0,0,0,0,0,0],  'm^2', 'area'),				([0,3,0,0,0,0,0,0],   'm^3', 'volume'),
	([0,-1,0,0,0,0,0,0], 'm^-1', 'inverse length'),		([0,-2,0,0,0,0,0,0],  '1/m^2', 'fuel'),
	([0,1,0,-1,0,0,0,0], 'm/s', 'velocity'),			([0,1,0,-2,0,0,0,0],  'm s^-2', 'acceleration'),
	([0,3,0,-1,0,0,0,0], 'm^3/s', 'volume flow'),		([0,0,1,-1,0,0,0,0],  'kg/s', 'mass flow'),
	([1,0,0,-1,0,0,0,0], 'rad/s', 'angular velocity'),	([1,0,0,-2,0,0,0,0],  'rad/s^2', 'angular acceleration'),
	([0,-3,1,0,0,0,0,0], 'kg/m^3', 'density'),			([0,3,-1,0,0,0,0,0],  'm^3/kg', 'specific volume'),
	([0,-2,1,0,0,0,0,0], 'kg/m^2', 'area density'),		([0,-2,1,0,0,0,0,0],  'kg/m^2', 'areal density'),
	([0,-2,1,0,0,0,0,0], 'kg/m^2', 'surface density'),	([0,-1,1,0,0,0,0,0],  'kg/m', 'linear density'),
	([0,1,1,-2,0,0,0,0], 'N', 'force'),					([0,-1,1,-2,0,0,0,0], 'N/m^2', 'pressure'),
	([0,2,1,-2,0,0,0,0], 'J', 'energy'),				([0,2,1,-3,0,0,0,0],  'J/s', 'power'),
	([0,1,1,-1,0,0,0,0], 'kg m/s', 'momentum'),			([0,2,1,-1,0,0,0,0],  'J s', 'action'),
	([0,2,0,-2,0,0,0,0], 'J/kg', 'dose'),				([0,-1,1,-1,0,0,0,0], 'kg m^-1 s^-1', 'viscosity'),
	([0,0,1,-3,0,0,0,0], 'W m^-2', 'intensity'),		([0,0,1,-2,0,0,0,0],  'J m^-2', 'flux density'),	# kg s^-2
	([0,0,0,0,0,1,0,0],  'K', 'Temperature'),			([0,0,0,0,0,-1,0,0],  'K^-1', 'thermal expansion'),
	([0,1,0,-2,0,-1,0,0],'J/(kg K)', 'specific heat'),	([0,-2,1,-2,0,-1,0,0],'kg m^2 /(K s^2)', 'heat capacity'),
	([0,2,1,-2,0,-1,0,0],'J/K', 'entropy'),				([0,0,1,-3,0,-4,0,0], 'J s^-1 m^-2 K^-4', u'Stefan–Boltzmann'),
	([0,0,0,0,1,0,0,0],  'A', 'current'),				([0,0,0,1,1,0,0,0],   'C', 'charge'),
	([0,2,1,-3,-2,0,0,0],'V/A', 'resistance'),			([0,-2,-1,3,2,0,0,0], 'A/V', 'inverse resistance'),
	([0,3,1,-3,-2,0,0,0], 'A s m^-3', 'resistivity'),	([0,2,1,-3,-1,0,0,0], 'kg m^2 s^-2 C^-1',' voltage'),
	([0,-2,-1,4,2,0,0,0],'C/V', 'capacitance'), 		([0,-2,-1,2,2,0,0,0], 'kg^-1 m^-2 s^2 A^2', 'reluctance'),	
	([0,2,1,-2,-1,0,0,0],'Tesla m^2', 'magnetic flux'),	([0,0,1,-2,-1,0,0,0], 'm^-2 kg^-1 s^3 A^2', 'magnetic flux density'),
	([0,2,1,-2,-2,0,0,0],'kg m^2 s^-2 A^-2', 'inductance'),	([0,-1,0,0,1,0,0,0], 'kg m^2 s^-2 A^-2', 'magnetic H field'),
	([0,-3,-1,4,2,0,0,0],'m^-3,kg^-1,sec^2,C^2', 'permittivity'),	([0,1,1,-2,-2,0,0,0], 'V s A^-1 m^-1', 'magnetic constant'),
	([0,2,0,0,1,0,0,0],  'm^2 A', 'magnetic moment'),	([0,-2,0,0,1,0,0,0],  'A m^-2', 'current density'),
	([0,0,0,-1,0,0,0,1],'mole/s', 'catalytic activity'),([0,2,0,-1,0,0,0,0],'m^2 s^-1', 'diffusion'),
	([0,1,-1,2,0,0,0,0], 'm^2/N', 'compressibility '),	([0,2,1,-2,0,0,0,-1], 'J/mole', 'chemical potential'),	
	([0,3,-1,-2,0,0,0,0],'m^3 kg^-1 s^-2', 'gravity field'),
	([0,0,0,0,0,0,1,0],  'cd', 'luminous intensity'),	([2,0,0,0,0,0,1,0],   'cd steradian', 'luminous flux'),
	([0,-2,0,0,0,0,1,0], 'cd m^-2', 'luminance'),		([2,-2,0,0,0,0,1,0], 'cd steradian m^-2', 'illuminance'),
	([0,0,0,0,0,0,0,1],  'mole', 'quantity of matter'),	([0,-3,0,0,0,0,0,1],  'mole m^-3', 'concentration'),
	([0,2,1,0,0,0,0,0],  'kg m^2', 'moment of inertia'),([0,2,1,-1,0,0,0,0],  'kg m^2 s^-1', 'angular momentum'),
	([0,-4,1,-1,0,0,0,0],'Pa s m^-3', 'acoustic impedance'),	([0,-2,1,-1,0,0,0,0], 'Pa s/m', 'specific acoustic impedance'),
	([0,-3,0,1,1,0,0,0], 'A s m^-3', 'charge density'),	([0,2,1,-3,-1,-1,0,0],'V/K', 'thermopower')
	]

pluralExclude = ['inches','cos','mps','fps','s']	# do NOT consider these plurals, so do NOT remove trailing "s" from them



def SIunits2Str(dims):
	""" returns string with SI units from dims[SI_N], e.g. [0,2,1,-2,0,0,0,0] --> "kg m^2 s^-2 """
	out = ''
	SIunits = ['rad', 'm', 'kg', 's', 'A', 'K', 'cd', 'mole']
	try:
		for i in range(len(dims)):
			dim = dims[i]
			if dim==1: out += SIunits[i]+' '
			elif dim: out += SIunits[i]+'^'+str(dim)+' '
		return out.strip()
	except:	return u''



def expandSiprefixes(prefixes):
	SIdict = {'d':'deci', 'c':'centi', 'm':'milli', u'µ':'micro', 'n':'nano', 'p':'pico', 'f':'femto', 'a':'atto', 'z':'zepto', 'y':'yocto', \
		'h':'hecto', 'H':'hecto', 'k':'kilo', 'K':'kilo', 'M':'Mega', 'G':'Giga', 'T':'Tera', 'P':'Peta', 'E':'Exa', 'Z':'Zeta', 'Y':'Yotta'} 
	out = ''
	for ch in list(prefixes):
		out += SIdict[ch]+'-'
	return out



class PhQ(object):
	"""
	a Physical Quantity (PhQ for short), i.e. a value & units, a combination of a number and a unit
	This defines a physical quantity, this does NOT define a unit, e.g. 15[inch] is OK, do not use this to define an inch (use OneUnitDefine)

	User Methods:
		self.SI()			returns a PhQ with the SI value of self.
		self.SIrev(SIval)	returns a PhQ with the in units of self.ustr whose SI value is SIval

	NOTE:
		ustr a string with the units, e.g. 'mm', 'year', 'sec', 'kpc', ... (may or may not be SI)
		num is the value of this PhQ in terms of ustr
		scale converts ustr --> SI,  e.g. for inch: scale=0.0254,  for fermi: scale=1e-15,  for m: scale=1
		so, 15 [mm] --> num=15, scale=0.001, ustr='mm'
		scale converts ustr to SI, num is how many ustr you have.

		self.ustr		string with given units, e.g. 'mm',  if ustr='pure' or 'pure number', ustr-->''
		self.num		value in terms of self.ustr, a float or int

		self.SIstr		SI units of ustr, ustr='mm' --> SIstr='m'
		self.scale		used to convert ustr-->SIstr, e.g. ustr='mm' then scale=0.001, given num[ustr] == num*scale[SIstr]
		self.offset		OPTIONAL, (defaults to 0), value[unit] * scale + offset = SI, e.g. K = 1*C + 273.15 (offsett=273.15)
		self.err		OPTIONAL, relative error, default is 0 (no error)

		self.dims[8]	[rad,m,kg,sec,A,K,cd,mole] dimensions of ustr, area-->[0,2,0,0,0,0,0,0]
		self.dimType	string from knownDimensions[], e.g. dims=[0,2,0,0,0,0,0,0] --> dimType='area'

		self.desc		OPTIONAL, some piece of text used to describe this physical quantity

		if dims[] is all zero, then self.ustr MUST be ''
	"""
	def __init__(self, num, ustr, dims=None, scale=None, desc='', Units=None, offset=None, err=0):
		try:	numTest = float(num)
		except:	raise ValueError('ERROR -- counld not interpret %r as a number' % (num,))
		if type(num) is int:	self.num = num
		else:					self.num = float(num)

		if ustr is None: ustr = ''
		if isinstance(ustr, basestring): self.ustr = ustr.strip()
		else:	raise ValueError('ERROR -- counld not interpret %r as a units string' % (ustr,))
		if self.ustr.lower().startswith('pure num'): self.ustr=''
		elif self.ustr.lower() == 'pure': self.ustr=''

		self.isPure = False
		if dims and scale:
			self.dims = dims
			self.scale = scale
		elif self.ustr=='':
			self.dims = [0]*SI_N
			self.scale = 1
		else:
			self.dims = self.scale = None

		try:
			self.offset=float(offset)
			if self.offset.is_integer(): self.offset = int(self.offset)
		except:	self.offset = 0

		if Units:	self.Units = Units
		else:		self.Units = UnitsJZTdefault# UnitsJZTdefault is set after definition of UnitsJZT()

		if self.Units and (not self.dims):		# set the dims & scale from self.ustr (then used to set dimType & SIstr)
			OU = self.Units.processInput(self.ustr)
			self.dims = OU.dims[:]				# the [:] causes a copy, so self.dims is not just a reference
			self.scale = OU.scale * OU.num
			self.offset = OU.offset

		try:
			self.scale=float(self.scale)
			if self.scale.is_integer(): self.scale = int(self.scale)
		except:
			self.scale = None					# scale is ALWAYS a number, this will cause things to fail

		try:	self.err = abs(err)				# relative error is always positive
		except:	self.err = 0
		self.desc = desc

		self.cleanUpDims()						# try to set self.dimType, self.SIstr, and self.isPure  from self.dims

		if not self.ustr and self.dims and self.scale==1: self.ustr = self.SIstr

		return None


	def SI(self):
		"""
		return SI equivalent of this unit, using self.num
		for 10[mm], returns 0.01 [m]
		# if reverse=True:  self.num is assumed SI value, return value in [unit]
		This can be overridden for special conversions, e.g. the cos in angle units

		NOTE:
		consider self.num=2 and unit='mm' (scale=0.001)
		converting unit --> SI:  0.001 m
		converting SI --> unit:  0.001 [unit] = 1m
		the self.num is NOT part of the convert, it just hangs around
		"""
		new = self.copy()
		new.num = self.num * self.scale	# returns SI value of: self.num [ustr]
		new.ustr = self.SIstr
		new.scale = 1
		if self.offset:				# optionally apply the offset
			new.num += self.offset
			new.offset = 0
		return new

	def SIrev(self,SIval):
		"""
		like .SI(), but reverse
		returns value of num in units of self, this is a utility routine, user should not be calling this.
		If self is 10[mm], then self.SIrev(1)-->1000[mm] (i.e. 1m --> 1000mm), self.num is not used or changed
		This can be overridden for special conversions, e.g. the cos in angle units
		"""
		new = self.copy()
		new.num = float(SIval) / self.scale	# change SI value to [units of self]
		if self.offset:					# optionally apply the offset
			new.num -= float(self.offset)/self.scale
			new.offset = self.offset
		return new


	def __str__(self):
		""" Return string value for PhQ. """
		return unicode(self).encode('ascii', errors='backslashreplace')

	def __unicode__(self):
		""" Return printable unicode string for PhQ. """
		if self.isPure:
			out = u'%r [pure number]' % (self.num)
		else:
			sss = self.numErr(self.num, self.err)	# something like "123.41±0.12"
			try:	out = u'%s [%s]' % (sss,self.ustr)
			except:	out = u'%s [%r]' % (sss,self.ustr)

		if self.desc:					# optionally add desc
			try:	desc = ' "%s"' % (self.desc,)
			except:	desc = ' %r' % (self.desc,)
			out += desc

		return out

	def __repr__(self):
		""" Return string representation for PhQ. """
		try:	out = 'PhQ<num=%r, ustr="%s"' % (self.num, self.ustr)
		except:	out = 'PhQ<num=%r, ustr=%r' % (self.num, self.ustr)
		if self.dims: out += ', dims=%r' % (self.dims,)
		if self.SIstr: out += ', SIstr=%r' % (self.SIstr,)
		if self.scale: out += ', scale=%r' % (self.scale,)
		if self.offset: out += ', offset=%r' % (self.offset,)
		if self.dimType: out += ', dimType=%r' % (self.dimType,)
		if self.err>0: out += ', relative err=%r' % (self.err,)
		if self.desc: out += ', desc=%r' % (self.desc,)
		out += '>'
		out = unicode(out).encode('ascii', errors='backslashreplace')
		return out


	def prefixFormat(self, x, unitStr=None, places=6, noSpace=False):
		"""
		routine that formats with SI prefix
		e.g.   prefixFormat(1.2e4,"eV") --> "12 keV"
		"""
		if not unitStr:	unitStr = ''
		else:			unitStr = unitStr.strip()
		if noSpace:	space = ''
		else:		space = ' '

		x = float(x)
		absx = abs(x)
		if absx==0:
			factor = 1
			prefix = ''
		elif absx>1:
			i = int((math.log10(absx)/3.0))
			i = min(i,8)
			plus = ['', 'k','M','G','T','P','E','Z','Y']
			factor = 10**(-3*i)
			prefix = plus[i]
			if i<8:				# check when mantissa of x is real close to 1
				anum = round(x * factor * 1000 ) / 1000
				if anum == 1000.0:
					prefix = plus[i+1]
					x = factor = 1.0
		else:
			i = int(math.ceil(-math.log10(absx)/3.0))
			i = min(i,8)
			factor = 10**(3*i)
			minus = ['', 'm', u'µ', 'n', 'p', 'f', 'a', 'z', 'y']
			prefix = minus[i]

			if i>0:				# check when mantissa of x is real close to 1
				anum = round(x * factor * 1000 ) / 1000
				if anum == 1000.0:
					prefix = minus[i-1]
					x = factor = 1.0

		fmt = '%%.%dg%s%s%s' % (places, space, prefix, unitStr)
		return fmt % (x*factor,)


	#		https://docs.python.org/2/reference/datamodel.html
	def __mul__(self, other):
		""" return a new PhQ that is product of self and other """
		if type(other) is float or type(other) is int:
			new = self.copy()
			new.num *= other
		elif self == PhQ(1,''):					# just a multiply by one
			new = other.copy()
		elif other == PhQ(1,''):				# just a multiply by one
			new = self.copy()
		elif isinstance(other, PhQ):			# other is a PhQ or child of PhQ
			num = self.num * other.num
			scale = self.scale * other.scale
			new = PhQ(num, '', scale=scale, offset=0)
			if self.ustr and other.ustr:	new.ustr = '(%s) (%s)' % (self.ustr,other.ustr)
			elif other.ustr:				new.ustr = other.ustr
			elif self.ustr:					new.ustr = self.ustr
			else:							new.ustr = ''
			if self.dims and other.dims:
				new.dims = [0]*SI_N
				for i in range(SI_N): new.dims[i] = self.dims[i] + other.dims[i]
			else: new.dims = None

			new.err = new.err_multiply(self.err, other.err)
			new.cleanUpDims(desc='')			# reset dims & remove desc
		else:
			raise ValueError('ERROR -- cannot multiply a PhQ by %r' % (other,))
		return new

	def __rmul__(self, other):
		return self.__mul__(other)

	def __imul__(self, other):
		""" modify self to be self*other """
		if type(other) is float or type(other) is int:
			self.num *= other
		elif isinstance(other, PhQ):			# other is a PhQ
			self.num *= other.num
			self.scale *= other.scale
			if self.isPure:	self.offset = other.offset
			else:			self.offset = 0			# loose offset in multiplication
			if self.ustr and other.ustr:	self.ustr = '(%s) (%s)' % (self.ustr,other.ustr)
			elif other.ustr:				self.ustr = other.ustr
			elif self.ustr:					self.ustr = self.ustr
			if self.dims and other.dims:
				for i in range(SI_N): self.dims[i] += other.dims[i]
			else: self.dims = None

			self.err = self.err_multiply(self.err, other.err)
			self.cleanUpDims(desc='')			# reset dims & remove desc
		else:
			raise ValueError('ERROR -- cannot multiply a PhQ by %r' % (other,))
		return self


	def __div__(self, other):
		""" return a new PhQ that is division of self/other """
		if type(other) is float or type(other) is int:
			new = self.copy()
			new.num /= float(other)
		elif other == PhQ(1,''):				# just a divide by one
			new = self.copy()
		elif isinstance(other, PhQ):			# other is a PhQ or child of PhQ
			num = self.num / float(other.num)
			scale = self.scale / float(other.scale)
			new = PhQ(num, '', scale=scale, offset=0)	# loose the offset

			if self.ustr == other.ustr:		self.ustr = ''	# units cancel
			if self.ustr and other.ustr:	new.ustr = '(%s)/(%s)' % (self.ustr,other.ustr)
			elif other.ustr:				new.ustr = '(%s)^-1' % (other.ustr,)
			elif self.ustr:					new.ustr = self.ustr
			else:							new.ustr = ''

			if new.ustr=='':
				new.dims = [0]*SI_N
			elif self.dims and other.dims:
				new.dims = [0]*SI_N
				for i in range(SI_N): new.dims[i] = self.dims[i] - other.dims[i]
			else:
				new.dims = None
			new.err = new.err_multiply(self.err, other.err)
			new.cleanUpDims(desc='')		# reset dims & remove desc
		else:
			raise ValueError('ERROR -- cannot divide a PhQ by %r' % (other,))
		return new

	def __rdiv__(self, other):
		return self.__div__(other)

	def __idiv__(self, other):
		""" modify self to be self/other """
		if type(other) is float or type(other) is int:
			self.num /= float(other)
		elif isinstance(other, PhQ):			# other is a PhQ or child of PhQ
			self.num /= float(other.num)
			self.scale /= float(other.scale)
			if self.ustr == other.ustr:		self.ustr = ''
			elif self.ustr and other.ustr:	self.ustr = '(%s)/(%s)' % (self.ustr,other.ustr)
			elif other.ustr:				self.ustr = '(%s)^-1' % (other.ustr,)
			elif self.ustr:					self.ustr = self.ustr
			if self.dims and other.dims:
				for i in range(SI_N): self.dims[i] -= other.dims[i]
			else: self.dims = None
			self.err = self.err_multiply(self.err, other.err)
			self.cleanUpDims(desc='')		# reset dims & remove desc
		else:
			raise ValueError('ERROR -- cannot multiply a PhQ by %r' % (other,))
		return self


	def __add__(self, other):
		if type(other) is float or type(other) is int:
			o_num = o_SI = other
			o_err = 0
		else:
			o_num = other.num
			o_SI = other.SI().num
			o_err = other.err

		if self.unitsMatch(other):					# units are EXACTLY the same, e.g. 'cm s' and 'cm s', so can just add *.num's
			new = self.copy()
			new.num = self.num + o_num
			new.err = self.err_add(self.num,self.err,o_num,o_err)
		elif self.dimensionsMatch(other):			# dimensions match, but units DIFFER, e.g. 'cm' and 'inch', convert to SI, then add
			new = self.copy()						# copies, num, ustr, dims, scale, dimType, & SIstr
			self_SI = self.SI().num					# self num in SI units
			new.num = self_SI + o_SI				# add SI units
			new.err = self.err_add(self_SI,self.err,o_SI,o_err)
			new.scale = 1							# these are SI units, so scale is 1
			new.offset = 0							# no offset in SI units
			new.ustr = new.SIstr
		else:
			raise ValueError('ERROR -- cannot add, units of %r and %r,  they must match' %(self,other))

		new.desc = ''
		return new

	def __radd__(self, other):
		return self.__add__(other)

	def __iadd__(self, other):
		if type(other) is float or type(other) is int:
			o_num = o_SI = other
			o_err = 0
		else:
			o_num = other.num
			o_SI = other.SI().num
			o_err = other.err

		if self.unitsMatch(other):					# units are exactly the same, e.g. 'cm s' and 'cm s', just add *.num's
			self.err = self.err_add(self.num,self.err,o_num,o_err)
			self.num += o_num						# units are identical, just add *.num's
		elif self.dimensionsMatch(other):			# dimensions match, but units DIFFER, e.g. 'cm' and 'inch', convert other to units of self, then add
			SI_val = self.SIrev(o_SI)
			self.err = self.err_add(self.num,self.err,SI_val,o_err)
			self.num += SI_val						# add other in units of self
		else:
			raise ValueError('ERROR -- cannot iadd, units of   %r   and   %r,  they must match' %(self,other))
		self.desc = ''
		return self


	def __sub__(self, other):
		if type(other) is float or type(other) is int:
			o_num = o_SI = other
			o_err = 0
		else:
			o_num = other.num
			o_SI = other.SI().num
			o_err = other.err

		if self.unitsMatch(other):					# units are exactly the same, e.g. 'cm s' and 'cm s'
			new = self.copy()
			new.num = self.num - o_num				# units are identical, just subtract *.num's
			new.err = self.err_add(self.num,self.err,o_num,o_err)
			new.offset = 0							# you loose the offset when you subtract
		elif self.dimensionsMatch(other):			# dimensions match, but units differ, e.g. 'cm' and 'inch', convert to SI, then subtract
			new = self.copy()						# copies, num, ustr, dims, scale, dimType, & SIstr
			self_SI = self.SI().num					# self num in SI units
			new.num = self_SI - o_SI				# subtract SI units
			new.err = self.err_add(self_SI,self.err,o_SI,o_err)
			new.scale = 1							# these are SI units, so scale is 1
			new.offset = 0							# no offset in SI units
			new.ustr = new.SIstr
		else:
			raise ValueError('ERROR -- cannot subtract, units of %r and %r,  they must match' %(self,other))
		new.desc = ''
		return new

	def __rsub__(self, other):
		ss = self.__sub__(other)
		ss.num *= -1
		return ss

	def __isub__(self, other):
		if type(other) is float or type(other) is int:
			o_num = o_SI = other
			o_err = 0
		else:
			o_num = other.num
			o_SI = other.SI().num
			o_err = other.err

		if self.unitsMatch(other):					# units are exactly the same, e.g. 'cm s' and 'cm s'
			self.err = self.err_add(self.num,self.err,o_num,o_err)
			self.num -= o_num						# units are identical, just subtract *.num's
			self.offset = 0							# you loose the offset when you subtract
		elif self.dimensionsMatch(other):			# dimensions match, but units differ, e.g. 'cm' and 'inch', convert other to SI, then subtract
			SI_val = self.SIrev(o_SI)
			self.err = self.err_add(self.num,self.err,SI_val,o_err)
			self.num -= SI_val						# subtract off other in units of self
			self.offset = 0							# you loose the offset when you subtract
		else:
			raise ValueError('ERROR -- cannot isub, units of %r and %r,  they must match' %(self,other))
		self.desc = ''
		return self


	def __pow__(self, power):				# raise this PhQ() to a power
		if isinstance(power, PhQ):			# other is a PhQ or child of PhQ, try to change power to pure number
			if not power.isPure: raise ValueError('ERROR -- cannot raise to an exponent with units: power = %r' % (power,))
			power = power.num
		if not (type(power) is float or type(power) is int):	# yes, I need a number
			raise ValueError('ERROR -- cannot raise to an exponent of power = %r' % (power))
		if abs(power-round(power))<1e-7: power = int(round(power))	# close to an int, make it an int
		# power is now just a float or int

		if power==0:						# if power==0, self^power will be a pure 1, this is an unusual situation
			new = PhQ(1,'')
		elif power==1:						# if power==1, just return a copy of self
			new = self.copy(all=True)
		else:
			self.err *= math.sqrt(abs(power))
			new = self.copy()
			new.num = (self.num)**power
			new.scale = (self.scale)**power
			new.ustr = '(%s)^%g' % (self.ustr, power)
			if self.dims:
				for i in range(SI_N): new.dims[i] *= power
			new.cleanUpDims(desc='')		# updates dimType, SIstr, & desc, also remove desc
		return new


	def __neg__(self):
		""" process a unary minus """
		new = self.copy()
		new.num = -new.num
		new.desc = ''						# description is probably invalid
		return new

	def __pos__(self):
		""" process a unary plus """
		new = self.copy(all=True)			# nothing changes
		return new

	def __abs__(self):
		""" process an abs(x) """
		new = self.copy()
		new.num = abs(new.num)
		new.scale = abs(new.scale)			# this should not be needed, just in case
		try:	new.offset = abs(new.offset)
		except:	pass
		new.desc = ''						# description is probably invalid
		return new


	def __eq__(self, other):
		"""
		Override the default Equals behavior
		do not compare self.desc
		"""
		try:	delta = self - other
		except:	return False					# probably dimensions do not match
		err = max(delta.err, 1e-13)				# reasonable tolerance for python
		maxDiff = abs(self.SI().num) * err		# max expected difference of SI from zero
		return maxDiff > delta.SI().num			# is difference less than the error

	def __ne__(self, other):
		return not self.__eq__(other)


	def copy(self,all=False):
		""" note, this ALWAYS returns a PhQ() """
		new = PhQ(1,'')
		new.num = self.num
		new.ustr = self.ustr
		new.dims = self.dims[:]
		new.dimType = self.dimType
		new.scale = self.scale
		new.offset = self.offset
		new.err = self.err
		new.isPure = (set(self.dims) == set([0])) and self.scale==1		# isPure when all dims are 0, and scale is 1
		new.SIstr = self.SIstr
		new.Units = self.Units
		if all:	new.desc = self.desc
		else:	new.desc = ''
		return new


	def err_multiply(self,r1,r2):
		""" resulting relative error when two numbers are multiplied """
		r12 = math.sqrt(r1*r1 + r2*r2)
		return r12

	def err_add(self,a,ra,b,rb):
		"""
		resulting error when two numbers are added
		first number is a ± a*ra
		second number is b ± b*rb
		"""
		sum = float(abs(a)+abs(b))
		if sum == 0: sum = 1.0
		rab = math.sqrt( (a*ra)**2 + (b*rb)**2 )
		return rab/sum

	def numErr(self, num, err):
		"""
		return a string something like:  14.23±0.11
		num		the value
		err		the relative error, actual error = num*err
		the number of places shown depends upon err
		"""
		if err<=0: return '%.15g' % (num,)			# full precision, but only 15 digits
		log10err = abs(math.log(err)/ln10)
		ip = int(math.ceil(log10err)) + 2			# number of places to show
		ip = min(ip,15)								# never show more than 15 places
		fmt = u'%%.%dg±%%.2g' % (ip)
		sss = fmt % (num, num*err) 
		return sss


	def cleanUpDims(self,desc=None):
		"""
		set self.dimType & self.SIstr from knownDimensions
		if dims does not exist, sets dimType & SIstr to None
		in dims[], change floats like 2.0 to ints
		also can be used to set or remove desc
		"""
		try:
			for i in range(SI_N):				# first set numbers like 2.0 to ints, e.g. 2.0 --> 2
				try:
					if self.dims[i].is_integer(): self.dims[i] = int(self.dims[i])
				except: pass

			self.dimType = None
			for dim,uu,typ in knownDimensions:	# try to set dimType & SIstr from knownDimensions
				if self.dims == dim:			# found a match to dims array
					self.dimType = typ			# set dimType & SIstr
					self.SIstr = uu
					break
			if not self.dimType:				# did not find in knownDimensions
				self.dimType = SIunits2Str(self.dims)	# so dimType is just the SIstr
				self.SIstr = self.dimType
		except:									# end up here when dims[] is invalid
			self.dimType = None
			self.SIstr = SIunits2Str(self.dims)

		try:
			self.scale = float(self.scale)
			if self.scale.is_integer(): self.scale = int(self.scale)
		except:	self.scale = 1
		try:
			self.offset=float(self.offset)
			if self.offset.is_integer(): self.offset = int(self.offset)
		except:	self.offset = 0

		self.isPure = (set(self.dims) == set([0])) and self.scale==1		# isPure when all dims are 0, and scale is 1

		if type(desc) is string: self.desc = desc
		return


	def unitsMatch(self,other):
		""" check if units match, this includes .scale, does NOT include .num """
		equals = self.dimensionsMatch(other)	# the dimensions must match
		try:	scale = other.scale
		except:	scale = 1						# in case other is just a number
		try:	equals &= (self.scale == scale)	# scale must match too
		except:	equals = False			
		return equals

	def dimensionsMatch(self,other):
		"""
		check if dimensions match, i.e. dimension of 'm' and 'inch' match 'kg' & 's' do not
		self.dims[] and other.dims[] must always match
		if other is just a float or int, it will match when dims=8*[0]
		"""
		if type(other) is float or type(other) is int:	o_dims = [0]*SI_N
		else:
			try:	o_dims = other.dims
			except:	o_dims = None
		if not self.dims:	s_dims = [0]*SI_N
		else:				s_dims = self.dims
		return (s_dims == o_dims)

	def numEquals(self, x,y, tol=1e-15):
		"""
		returns equal of x and y
		tol is relative error
		"""
		try:
			if x == y: return True
		except: pass
		if type(x) is int and type(y) is int:
			return x==y
		elif x is None and y is None:		# both are None, None == None
			return True
		elif x is None or y is None:		# only one is None, None != anything else
			return False
		else:
			try:	x = float(x)
			except:	x = float('nan')
			try:	y = float(y)
			except:	y = float('nan')
			div = max(abs(x),abs(y))
			if div == 0.0: div = 1.0
			if (abs(x-y)/div) < tol: return True
		return False



class PhQcosine(PhQ):
	"""
	This is like PhQ, but allows cosine(angle)
	scale and offset are not used
	"""
	def __init__(self, num, desc='',Units=None):
		# scale & offset applicable to cos(angle),  also dims[] is known
		PhQ.__init__(self, num, 'cos', dims=[1,0,0,0,0,0,0,0], scale=1, desc=desc, Units=None, offset=0)
		self.SIstr = 'rad'


	def SI(self):
		""" returns angle[rad] for cos(angle[rad]) = self.num """
		new = PhQ.copy(self)
		num = self.num * self.scale
		new.num = math.acos(num)		# returns angle [rad] of this value
		new.scale = 1
		new.ustr = 'rad'
		return new


	def SIrev(self,SIval):
		"""
		SIval is an angle [rad]
		like .SI(), but reverse
		returns cos(SIval[rad])
		"""
		new = self.copy()
		new.num = math.cos(SIval)
		if self.scale: new.num /= float(self.scale)
		new.ustr = self.ustr
		return new


	def __str__(self):
		""" Return string value for PhQ. """
		return unicode(self).encode('ascii', errors='backslashreplace')

	def __unicode__(self):
		""" Return printable unicode string for PhQ. """
		sss = self.numErr(self.num, self.err)
		try:	out = u'%s [%s]' % (sss,self.ustr)
		except:	out = u'%s [%r]' % (sss,self.ustr)
		if self.desc:
			try:	ss = ' "%s"' % (self.desc,)
			except:	ss = ' %r' % (self.desc,)
			out += ss

		return out

	def __repr__(self):
		""" Return string representation for PhQ. """
		out = 'PhQcosine<num=%r, ustr=%r' % (self.num, self.ustr)
		if self.dims: out += ', dims=%r' % (self.dims,)
		if self.SIstr: out += ', SIstr=%r' % (self.SIstr,)
		if self.dimType: out += ', dimType=%r' % (self.dimType,)
		if self.desc: out += ', desc=%r' % (self.desc,)
		out += '>'
		return out


	#		https://docs.python.org/2/reference/datamodel.html
	def __mul__(self, other):
		""" return a new PhQ that is product of self and other """
		if type(other) is float or type(other) is int:
			new = self.copy()
			new.num *= other
		elif self == PhQ(1,''):					# just a multiply by one
			new = other.copy()
		elif other == PhQ(1,''):				# just a multiply by one
			new = self.copy()
		elif isinstance(other, PhQ):			# other is a PhQ, but NOT a PhQcosine()
			if not other.isPure: raise ValueError('ERROR -- cannot multiply a PhQcosine by %r' % (other,))
			new = self.copy()
			new.num *= other.num
		else:
			raise ValueError('ERROR -- cannot multiply a PhQ by %r' % (other,))
		return new

	def __imul__(self, other):
		""" modify self to be self*other """
		if type(other) is float or type(other) is int:
			self.num *= other
		elif isinstance(other, PhQ):			# other is a PhQ
			if not other.isPure: raise ValueError('ERROR -- cannot multiply a PhQcosine by %r' % (other,))
			self.num *= other.num
		else:
			raise ValueError('ERROR -- cannot multiply a PhQcosine by %r' % (other,))
		return self


	def __div__(self, other):
		""" return a new PhQ that is division of self/other """
		if type(other) is float or type(other) is int:
			new = self.copy()
			new.num /= float(other)
		elif other == PhQ(1,''):				# just a divide by one
			new = self.copy()
		elif isinstance(other, PhQ):			# other is a PhQ or child of PhQ
			if not other.isPure: raise ValueError('ERROR -- cannot divide a PhQcosine by %r' % (other,))
			new = self.copy()
			new.num /= float(other.num)
		else:
			raise ValueError('ERROR -- cannot divide a PhQcosine by %r' % (other,))
		return new

	def __idiv__(self, other):
		""" modify self to be self/other """
		if type(other) is float or type(other) is int:
			self.num /= float(other)
		elif isinstance(other, PhQ):			# other is a PhQ or child of PhQ
			if not other.isPure: raise ValueError('ERROR -- cannot divide a PhQcosine by %r' % (other,))
			self.num /= float(other.num)
		else:
			raise ValueError('ERROR -- cannot divide a PhQcosine by %r' % (other,))
		return self


	def __add__(self, other):
		if type(other) is float or type(other) is int:
			o_num = o_SI = other
		else:
			o_num = other.num
			o_SI = other.SI().num

		# for a cos(angle), can only add angles
		if not self.dimensionsMatch(other): raise ValueError('ERROR -- cannot add, units of %r and %r,  they must match' %(self,other))
		new = self.copy()						# copies, num, ustr, dims, scale, dimType, & SIstr
		new.num = self.SI().num + o_SI			# add SI units
		new.scale = 1							# these are SI units, so scale is 1
		new.offset = 0							# no offset in SI units
		new.SIstr = 'rad'
		new.ustr = 'rad'
		new.desc = ''
		return new

	def __iadd__(self, other):
		raise ValueError('ERROR -- cannot add a cos(angle) in place, e.g. cos(angle) -= [angle] does not work')
		return self


	def __sub__(self, other):
		if type(other) is float or type(other) is int:
			o_num = o_SI = other
		else:
			o_num = other.num
			o_SI = other.SI().num

		# for a cos(angle), can only subtract angles
		if not self.dimensionsMatch(other): raise ValueError('ERROR -- cannot sbutract, units of %r and %r,  they must match' %(self,other))
		new = self.copy()						# copies, num, ustr, dims, scale, dimType, & SIstr
		new.num = self.SI().num	 - o_SI			# subtract SI units
		new.scale = 1							# these are SI units, so scale is 1
		new.offset = 0							# no offset in SI units
		new.SIstr = 'rad'
		new.ustr = 'rad'
		new.desc = ''
		return new

	def __isub__(self, other):
		raise ValueError('ERROR -- cannot sbutract a cos(angle) in place, e.g. cos(angle) -= [angle] does not work')
		return self


	def __pow__(self, power):				# raise this PhQ() to a power
		if isinstance(power, PhQ):			# other is a PhQ or child of PhQ, try to change power to pure number
			if not power.isPure: raise ValueError('ERROR -- cannot raise to an exponent with units: power = %r' % (power,))
			power = power.num
		if not (type(power) is float or type(power) is int):	# yes, I need a number
			raise ValueError('ERROR -- cannot raise to an exponent of power = %r' % (power))
		if abs(power-round(power))<1e-7: power = int(round(power))	# close to an int, make it an int
		# power is now just a float or int

		if power==0:						# if power==0, self^power will be a pure 1, this is an unusual situation
			new = PhQ(1,'')
		elif power==1:						# if power==1, just return a copy of self
			new = self.copy(all=True)
		else:
			new = self.SI()**power
		return new


	def __neg__(self):
		""" process a unary minus """
		new = self.copy()
		new.num = -new.num
		new.desc = ''						# description is probably invalid
		return new

	def __pos__(self):
		""" process a unary plus """
		new = self.copy(all=True)			# nothing changes
		return new

	def __abs__(self):
		""" process an abs(x) """
		new = self.copy()
		new.num = abs(new.num)
		new.desc = ''						# description is probably invalid
		return new


	def copy(self,all=False):
		""" note, this ALWAYS returns a PhQcosine """
		if all:	desc = self.desc
		else:	desc = ''
		new = PhQcosine(self.num, desc=desc)
		return new





class OneUnitDefine(PhQ):
	"""
	**DEFINES** one unit. That means one call to this for meter, one for foot, etc.

	names			a list of names for this unit, e.g. ['m','meter','metre'] or [u'foot',u'feet',u'ft']
	strict			OPTIONAL, if True, then Inch not same as inch.  If False then Inch and inch are the same. This is used for interpeting a string
	specialReplace	OPTIONAL, a list of string replacements, e.g. specialReplace = [(u'Angstrom',u'Å'), (u'Ang',u'Å'), (u'µm','micron')]

	self.namesMatch[]	a list of names that will be used for comparing and matching
	self.namesFull[]	holds original names passed in, probably more human readable than namesMatch

		variables inherited from PhQ:
	dims[8]			dimensions array [angle, length, mass, time, current, Temperature, luminous_intensity, Quantity of Matter]
						SI base units are: [rad, m, kg, second, A, K, cd, mole]
						This is an array of SI_N numbers (all probably integers)
						[rad,m,kg,sec,A,K,cd,mole] dimensions of ustr, area-->[0,2,0,0,0,0,0,0]
	scale			used to convert ustr-->SI, e.g. for 'mm' then scale=0.001, for inch scale=0.0254 (if you don't provide this, then you probably want to override convert())
	offset			OPTIONAL, (defaults to 0), value[unit] * scale + offset = SI, e.g. K = 1*C + 273.15 (offsett=273.15)
	err				OPTIONAL, relative error, default is 0 (no error)
	dimType			name of dims, something like: "length", "area", "energy", "Temperature", ..., obtained from knownDimensions[]
	SIstr			SI units of ustr, ustr='mm' --> SIstr='m'
	ustr			a short string with the units, e.g. 'mm', 'year', 'sec', 'kpc', ... (can be set by last item in names[])
					if ustr is an int, then use ustr = names[ustr]
					NOTE, ustr MUST be in names[]
	desc			optional descriptive text
	num				NOT used by OneUnitDefine, self.num should always be 1

	Note, if the conversion is more than a simple linear eqn., then, don't use scale & offset, but override the convert()
	"""
	def __init__(self, names, dims, dimType='', scale=1.0, ustr=None, desc='', strict=False, specialReplace=[], offset=0, err=0):
		if isinstance(names, basestring): names = [names]
		if not hasattr(names, '__iter__'): raise TypeError('ERROR -- names = %r, it must be a list of strings).' % names)
		if not isinstance(dimType, basestring): TypeError('ERROR -- dimType = %r, it must be a strings).' % dimType)
		if not hasattr(dims, '__iter__'): raise TypeError('ERROR -- dims = %r, it must be a list of SI_N numbers).' % dims)
		if len(dims)!=SI_N: raise TypeError('ERROR -- dims = %r, it must be a list of SI_N numbers).' % dims)
		if not hasattr(specialReplace, '__iter__'): raise TypeError('ERROR -- specialReplace = %r, it must be a list of tuples).' % specialReplace)
		if not isinstance(desc, basestring): raise TypeError('ERROR -- desc = %r, it must be string).' % desc)

		if type(ustr) is int:
			try:	ustr = names[ustr]
			except:	ustr = None
		if not ustr: ustr = names[-1]				# ustr in not an int, try last one in names[]
		if not (ustr in names): raise ValueError('ERROR -- OneUnitDefine() ustr=%r is NOT in names=%r' % (ustr,names))

		PhQ.__init__(self, 1, ustr=ustr, dims=dims, scale=scale, desc=desc,Units=None,offset=offset, err=err)

		self.namesFull = names						# a list of names that will be used for printing and displaying
		try:	self.strict = bool(strict)
		except:	raise TypeError('ERROR -- OneUnitDefine() strict = %r, it must be boolean).' % strict)
		self.specialReplace = specialReplace
		self.SIstr = SIunits2Str(self.dims)

		self.namesMatch = []						# these are the names that will be used for comparing and matching
		for nn in names:
			nn = nn.replace(' ','')					# ignore spaces
			nn = nn.replace('_','')					# ignore '_'
			# remove all '-' unless it follows a '^', so keep '^-', i.e. in "m^-2", keep the minus
			nn = nn.replace('^-','_')				# '_' is used as a flag, since there aren't any '_'
			nn = nn.replace('-','')					# remove unwanted '-'
			nn = nn.replace('_','^-')				# reset the '_' --> '^-'
			if not self.strict: nn = nn.lower()
			for r0,r1 in specialReplace: nn = nn.replace(r0,r1)
			self.namesMatch.append(nn)
		self.namesMatch = set(self.namesMatch)		# only the unique ones
		return None


	def __unicode__(self):
		""" Return printable unicode string for OneUnitDefine. """
		if len(self.namesFull) < 1: full = False
		elif len(self.namesFull)==1 and len(self.namesFull[0])<1: full = False
		else: full = full = True

		sss = self.numErr(self.scale, self.err)
		if self.offset:	out = u'OneUnitDefine["%s", "%s"]:  value * %s + %r --> SI' % (self.dimType, self.SIstr, sss, self.offset)
		else:			out = u'OneUnitDefine["%s", "%s"]:  value * %s --> SI' % (self.dimType, self.SIstr, sss)
		if full:		out += '  {%r}' % (self.namesFull,)
		if self.desc:	out += '  %s' % (self.desc,)
		return out

	def __repr__(self):
		""" Return string representation for OneUnitDefine. """
		out = PhQ.__repr__(self)
		out = out.replace('PhQ','OneUnitDefine',1)
		out = out[:-1]				# trim off trailing ">"
		if self.offset: out += ', offset=%r' % (self.offset,)
		out += ', names=%r, strict=%r' % (self.namesFull,self.strict)
		if self.specialReplace: out += ', specialReplace=%r' % (self.specialReplace,)
		out += '>'
		return out


	def __eq__(self, other):
		"""
		Override the default Equals behavior
		do not compare:  {namesFull, desc, strict, specialReplace, SIstr, namesMatch, short}
		"""
		equals = isinstance(other, OneUnitDefine)			# must be a OneUnitDefine or child
		if not equals: return False							# can only compare two OneUnitDefine, or children
		equals &= PhQ.__eq__(self,other)					# compares SI values
		equals &= self.numEquals(self.scale, other.scale)	# scales must also match
		equals &= self.numEquals(self.num, other.num)		# *.num must match, should both be 1
		return equals


	def contains(self,test):
		""" returns True if test is a valid name for this unit, usese strict """
		if not self.strict: test = test.lower()
		return (test in self.namesMatch)


	def __isKnown_dimType(self):
		""" check that find self.dimType in knownDimensions, and check that dims match """
		for dim,uu,typ in knownDimensions:
			if self.dimType == typ:		# found the name dimType
				return self.dims == dim	# do the dim arrays match?
		return False					# no dimType found


	def phq(self):
		"""
		returns a PhQ for this unit
		e.g. for meter, it return PhQ(1,'m'), scale=1
		for inch, it returns PhQ(1,'inch'), scale=0.0254
		"""
		new = PhQ(1,'')					# start with a blank
		new.ustr = self.ustr
		new.dims = self.dims[:]
		new.dimType = self.dimType
		new.scale = self.scale
		new.offset = self.offset
		new.err = self.err
		new.SIstr = self.SIstr
		new.isPure = (set(self.dims) == set([0])) and self.scale==1		# isPure when all dims are 0, and scale is 1
		return new



class OneUnitDefineCosine(OneUnitDefine):
	"""
	This is like OneUnitDefine, but allows cosine(angle)
	"""
	def __init__(self, names, dims, dimType='', desc='', strict=False, specialReplace=[], num=1, err=0):
		OneUnitDefine.__init__(self, names=names, dims=dims, dimType=dimType, scale=1, ustr='cos', desc=desc, strict=strict, specialReplace=specialReplace, err=err)
		self.scale = 1				# not applicable to OneUnitDefine cos(angle)

	def __unicode__(self):
		""" Return printable unicode string for OneUnitDefineCosine. """
		if len(self.namesFull) < 1: full = False
		elif len(self.namesFull)==1 and len(self.namesFull[0])<1: full = False
		else: full = full = True
		out = u'OneUnitDefineCosine["%s", "%s"]:  cos(value) --> SI' % (self.dimType, self.SIstr)
		if full:		out += '  {%r}' % (self.namesFull,)
		if self.desc:	out += '  %s' % (self.desc,)
		return out

	def __repr__(self):
		""" Return string representation for OneUnitDefine. """
		sss = self.numErr(self.num, self.err)
		out = 'OneUnitDefineCosine<num=%s, ustr=%r' % (sss, self.ustr)
		if self.dims: out += ', dims=%r' % (self.dims,)
		if self.SIstr: out += ', SIstr=%r' % (self.SIstr,)
		if self.dimType: out += ', dimType=%r' % (self.dimType,)
		if self.err>0: out += ', relative error=%r' % (self.err,)
		if self.desc: out += ', desc=%r' % (self.desc,)
		out += ', names=%r, strict=%r' % (self.namesFull,self.strict)
		if self.specialReplace: out += ', specialReplace=%r' % (self.specialReplace,)
		out += '>'
		return out


	def __eq__(self, other):
		"""Override the default Equals behavior"""
		if self.__class__ != other.__class__: return False# require strict matching of classes
		return OneUnitDefine.__eq__(self,other)	

	def phq(self):
		""" returns a PhQcosine for this unit """
		new = PhQcosine(1,'')					# start with a blank PhQcosine
		new.dimType = 'angle'
		new.isPure = False
		new.err = self.err
		return new




class allUnitsData(object):
	"""
	this holds a list of OneUnitDefine() (or children)
	units is either a single OneUnitDefine(), or a list of them
	"""
	def __init__(self, units=None):
		if isinstance(units, OneUnitDefine):
			self.units = [units]
			self.N = 1
		elif hasattr(units, '__iter__'):
			self.units = units
			self.N = len(units)
		elif units is None:
			self.units = []
			self.N = 0
		else:
			raise TypeError('ERROR -- allUnitsData, type(units) = %r, shold be a list of OneUnitDefines().' % type(units))
		#print(self.N)
		#print(self.units[0])
		# if self.N>0:
		# 	if not isinstance(self.units[0], OneUnitDefine): 
		# 		raise TypeError('ERROR -- allUnitsData, type(units) = %r, shold be a list of OneUnitDefines().' % type(units))
		# self.buildCrossRef()				# always re-build after adding units


	def append(self, units):
		"""
		append more OneUnitDefine()'s to self.units
		"""
		if isinstance(units, OneUnitDefine):		# add a single OneUnitDefine()
			self.units.append(units)
			self.N += 1

		elif hasattr(units, '__iter__'):
			if len(units)>0:
				if isinstance(units[0], OneUnitDefine): self.units += units
				else: raise TypeError('ERROR -- allUnitsData.append(), type(units) = %r, shold be a list of OneUnitDefines().' % type(units))
				self.N = len(self.units)	# add a multiple instances OneUnitDefine()

		elif units is None:	pass
		else:				raise TypeError('ERROR -- allUnitsData.append(), type(units) = %r, shold be a list of OneUnitDefines().' % type(units))
		self.buildCrossRef()				# always re-build after adding units


	def find(self,input):
		"""
		returns the unit (a PhQ) that goes with input, note that input may contain a SI prefix(s), but not exponent or '/'
		This returns a PhQ from the OneUnitDefine(), so you can change it without altering the definitions.
		if allUnitsData() contains 'm', your can .find('cm'), but not .find('cm^2') or .find('m/s')
		"""
		index = -1
		inputLower = input.lower()
		for match,i,st in self.crossRef:	# for each registered unit name, crossRef[] = [(name,index,strict),...]
			plural = not (match.lower() in pluralExclude)
			if st:
				if plural and input.endswith(match+'s'):
					index = i
					match += 's'
					break
				if input.endswith(match):
					index = i
					break
			else:
				if plural and inputLower.endswith(match.lower()+'s'):
					index = i
					match += 's'
					break
				if inputLower.endswith(match.lower()):
					index = i
					break

		if index>=0:						# found a match
			pq = self.units[index].phq()
			j = len(match)
			if len(input)>j: pq.num *= self.SIprefix2factor(input[:-j])
			return pq

		return None


	def __str__(self):
		""" Return string value for allUnitsData. """
		return "allUnitsData() contains %d instances of OneUnitDefine()" % (self.N,)

	def __unicode__(self):
		""" Return unicode value for allUnitsData. """
		out = u"allUnitsData() contains %d instances of OneUnitDefine()" % (self.N,)
		return out

	def __repr__(self):
		""" Return string representation for allUnitsData. """
		out = 'allUnitsData<N=%d>' % (self.N,)
		return out

	def __len__(self):			# this is for len(allUnitsData), returns number of units stored
		return self.N

	def len(self):				# this is for allUnitsData.len(), returns number of units stored
		return self.N

	def __getitem__(self, n):	# this is for allUnitsData[i]
		"""
		Return the n-th unit, starting from 0.
		This returns a COPY of the OneUnitDefine(), so you can change it with impunity
		"""
		return copy.deepcopy(self.units[n])

	def __iter__(self):
		""" The class iterator """
		return iter(self.units)


	def findNoPrefix(self,input):
		"""
		returns the unit that goes with input, for this only unit, NO prefix
		This returns a COPY of the OneUnitDefine(), so you can change it with impunity
		This has only been used for testing, usually you will use self.find(input)
		"""
		inputLower = input.lower()
		for match,i,st in self.crossRef:	# for each registered unit name, crossRef[] = [(name,index,strict),...]
			if st:
				if input == match: return copy.deepcopy(self.units[i])
			else:
				if inputLower == match.lower(): return copy.deepcopy(self.units[i])
		return None


	def buildCrossRef(self):
		""" build the lists and cross-references needed to identify units """
		if self.units is None:
			self.crossRef = []
			return

		all0 = []							# an un-sorted list of ALL of the unit names
		names0 = []
		i = 0
		for uu in self.units:
			names0 += uu.namesMatch
			for nn in uu.namesMatch: all0.append((nn,uu.strict,i))
			i += 1

		if len(set(names0)) != len(names0):
			ltemp = list(names0)
			for name1 in set(names0): ltemp.remove(name1)
			raise ValueError ('ERROR -- units are not unique: %s' % (str(ltemp),))

		maxNameLenth = 0					# find maximum length of a unit name
		for uu in names0: maxNameLenth = max(len(uu),maxNameLenth)

		self.crossRef = []					# will be a list of (name,index,strict) sorted by name
		for N in range(maxNameLenth,0,-1):
			for nn,st,i in all0:
				if len(nn)==N and st:		# for each length, add the strict ones first
					self.crossRef.append((nn,i,True))
			for nn,st,i in all0:
				if len(nn)==N and not st:	# next add the non-strict ones for this length
					self.crossRef.append((nn,i,False))


	def listDimensions(self, dim):
		"""
		return a list of all defined unit names with the given dim
		dim may be either an array of 8 numbers, or a name, e.g. [0,2,0,0,0,0,0,0] or 'area'
		Note, if dim=='all', then returns all unit names
		if dim==None or '', then return an empty list
		"""
		out = []
		if dim=='all':
			print ('ss  dim = ',dim,'   len=',len(self.units))
			for uu in self.units: out.append(uu.namesFull)
		elif isinstance(dim, basestring):
			for uu in self.units:
				if uu.dimType==dim: out.append(uu.namesFull)
		elif hasattr(dim, '__iter__'):
			for uu in self.units:
				if uu.dims==dim: out.append(uu.namesFull)
		return out


	def SIprefix2factor(self,prefix):
		"""
		returns number corresponding to the SI prefix.
		Except for 'H' or 'K' this is case SENSITIVE.
		====   ====    ======    ====   ====    =============================
		char   num      name     char   num       name
		====   ====    ======    ====   ====    =============================
		 d     1e-1     deci
		 c     1e-2     centi      h     1e2      hecto (h or H) is acceptable)
		 m     1e-3     milli      k     1e3      kilo (k or K is acceptable)
		 µ     1e-6     micro      M     1e6      Mega
		 n     1e-9     nano       G     1e9      Giga
		 p     1e-12    pico       T     1e12     Tera
		 f     1e-15    femto      P     1e15     Peta
		 a     1e-18    atto       E     1e18     Exa
		 z     1e-21    zepto      Z     1e21     Zeta
		 y     1e-24    yocto      Y     1e24     Yotta
		====   ====    ======    ====    ====   =============================

		EXAMPLE::
			>>> SIprefix2factor('m')
					1e-3
			>>> SIprefix2factor('nK')
					1e-6
			>>> SIprefix2factor('Giga')
					1e9
		"""
		if not prefix: return 1
		if type(prefix) is str: prefix = prefix.decode('utf-8')	# ensure that prefix is unicode

		value = 1
		# first look for long names, and process them, (also remove long names from prefix).
		longNames = [('deci',0.1),('centi',0.01),('milli',1e-3),('micro',1e-6),('nano',1e-9),('pico',1e-12),('femto',1e-15),('atto',1e-18),('zepto',1e-21),('yocto',1e-24),
			('hecto',1e2), ('kilo',1e3), ('Kilo',1e3), ('Mega',1e6), ('Giga',1e9), ('Tera',1e12), ('Peta',1e15), ('Exa',1e18), ('Zeta',1e21), ('Yotta',1e24) ]
		for name,num in longNames:
			new = len(prefix)
			last = new + 1
			while new<last:
				prefix = prefix.replace(name,'',1)
				last = new
				new = len(prefix)
				if (new<last): value *= num

		prefix = ''.join(prefix.split())		# removes all whitespace from prefix
		# second look for individual character prefixes, and process them.
		keyVals = {'d': 0.1, 'c': 0.01, 'm': 1e-3, u'µ': 1e-6, 'n': 1e-9, 'p': 1e-12, 'f': 1e-15, 'a': 1e-18, 'z': 1e-21, 'y': 1e-24, \
			'h': 100., 'H': 100., 'k': 1e3, 'K': 1e3, 'M': 1e6, 'G': 1e9, 'T': 1e12, 'P': 1e15, 'E': 1e18, 'Z': 1e21, 'Y': 1e24}

		for ch in prefix:
			try:	value *= keyVals[ch]
			except:	raise ValueError('SIprefix2factor(): Unknown SI prefix character %r' % ch)

		return value



class UnitsJZT(allUnitsData):
	"""
	This is the main class, it provides the functionality needed to convert units.
	this holds an allUnitsData() with the list of OneUnitDefine()'s (or variants)
	units is either a single OneUnitDefine(), or a list of them
	if you do not initialize this class with a units, then it will use the built-in standard units
	when transform=True, then you can convert things like 'nm'-->'eV', or 'mass of electron'-->'keV'
	Normally valIN, uIN, uOUT are set later with a call to .convert(...)
	transform defaults to False

	uIN			OPTIONAL, the given input units
	valIN		OPTIONAL, number of uIN

	uOUT		OPTIONAL, esired output units
	units		OPTIONAL, an allUnitsData() containing all known units
	transform	OPTIONAL, if the dimensions of uIN and uOUT don't match, then try with powers of {h,c,e,kB}
	"""
	def __init__(self, valIN=1.0, uIN='SI', uOUT='SI', units='standard', transform=False):
		self.valIN = valIN
		self.uIN = uIN
		self.uOUT = uOUT
		self.transform = bool(transform)		# when converting units, consider adding factors of h,c,e,kB to make it work

		try:
			if units.lower() == 'standard':	units = MakeStandardUnits()
		except:	pass
		allUnitsData.__init__(self, units)

		self.SIvalue = None
		self.SIname = ''
		self.valOUT = None
		self.directSI = None			# this will be set if forcing


	def __call__(self,first,middle,last=None):
		"""
		allows you to call a UnitsJZT directly without the convert
		used as:
		>>> units = UnitsJZT()
		>>> units(5,'Å','nm')
		PhQ<num=0.5, ustr=nm, dims=[0, 1, 0, 0, 0, 0, 0, 0], SIstr='m', scale=1e-09, dimType='length'>
		>>> print units(5,'Å','nm')
		0.5 [nm]

		without this you would have to say
		>>> units.convert(5,'Å','nm')

		units(5,'cm','inch')
		units('5 cm','inch')
		units('5 cm','','inch')
		units((5,'cm'),'','inch')

 		the last argument is always the output unit
		the first is either a number or a number+unit
		the middle argument (if there are 3) is input unit (or more of the input unit)
 
		input is something like '100 acre' or '0.12 kg m/s^2'
		outUnit is just a unit, e.g. 'Newton' or 'g m s^-2' or 'dyn'
		Called when the instance is “called” as a function; if this method is defined, x(arg1, arg2, ...) is a shorthand for x.__call__(arg1, arg2, ...).
		"""
		return self.convert(first,middle,last)


	def __str__(self):			# Return string value for UnitsJZT.
		try:	return u'%g [%r]   -->   %g [%r](SI)   -->   %g [%r]' % (self.valIN,self.uIN, self.SIvalue,self.SIname, self.valOUT.num,self.uOUT)
		except:	return 'No conversions have taken place yet.     '+ allUnitsData.__str__(self)

	def __unicode__(self):
		""" Return unicode value for UnitsJZT. """
		try:
			if self.directSI:	return u'%g [%s]  \u2192  %s  \u2192  %g [%s](SI)  \u2192  %s' % (self.valIN,self.uIN, self.directSI, self.SIvalue,self.SIname, self.valOUT)
			else:				return u'%g [%s]  \u2192  %g [%s](SI)  \u2192  %s' % (self.valIN,self.uIN, self.SIvalue,self.SIname, self.valOUT)
		except:	return 'No conversions have taken place yet.     ' + allUnitsData.__unicode__(self)

	def __repr__(self):
		""" Return representation for UnitsJZT. """
		if self.SIvalue is None:	SIvalue = float('nan')
		else:						SIvalue = self.SIvalue
		if self.valOUT is None:	valOUT = float('nan')
		else:					valOUT = self.valOUT
		out = u'UnitsJZT<(%r, %r)  -->  SI(%r, %r)  -->  (%r, %r)   ' % (self.valIN,self.uIN, SIvalue,self.SIname, valOUT,self.uOUT)
		out += allUnitsData.__repr__(self) + ' >'
		return out.encode('ascii', errors='backslashreplace')


	def processInput(self,inStr):
		"""
		Take a string like "20 kg m /s^2' and convert to a PhQ()
		"""
		global debug, depth
		spaces = (depth-1)*'  - '
		if debug: print ('\n'+spaces+'processInput(%r)' % inStr)
		inStr = inStr.replace('[','(')			# internally only use parenthesis, not brackets
		inStr = inStr.replace(']',')')
		inStr = inStr.replace('{','(')			# only understand parenthesis, not braces
		inStr = inStr.replace('}',')')			#

		inStr = inStr.replace('**','^')			# use '^' for exponentiation, not '**'
		inStr = inStr.replace(' x ',' ')		# 'x' means multipy
		inStr = inStr.replace('*',' ')			# '*' means multipy
		inStr = inStr.replace('_','')
		inStr = self.__removeDashes(inStr)		# remove all 'joining' dashes, preserve unary & binary '-'
		inStr = self.__applyModifiers(inStr)	# change strings, e.g. 'electron mass' --> 'electronmass'
		if debug: print (spaces+'after __applyModifiers(), inStr =',inStr)
		inStr = inStr.replace('/',' / ')		# make sure that '/' is separated from neighbors

		unit = self.run_walkList(inStr)
		if debug: print (spaces+'after run_walkList,  unit = ',unicode(unit),'  ',unit.dims,unit.dimType)
		depth -= 1
		return unit


	def __removeDashes(self,inStr):
		"""
		remove all '-' that join two WORDS (not digits)
		this preserves minus signs (both unary and binary)
		while changing things like 'N-m' --> 'N m'
		"""
		inStr = inStr.replace('-per-','/')		# this is special
		nine = ord('9')							# = 57
		i = 0
		while i<len(inStr):
			try:
				i = inStr.find('-',i)
				if i<0: break
				ch0 = ord(inStr[i-1])
				ch1 = ord(inStr[i+1])
				if ch0>nine and ch1>nine:	inStr = inStr[:i] + inStr[i+1:] # removes character at i
			except:	pass
			i += 1
		return inStr


	def run_walkList(self,buf):
		""" first clean up text, and then send to __walkList """
		global depth

		if debug: print ('run_walkList(%r)  -->' % (buf,),)
		buf = buf.replace('**','^')								# internally use ^ for exponents
		buf = buf.replace('*',' ')
		buf = ' '.join(buf.split())								# change all multiple spaces --> single, also removes any other whitespace chars
		buf = buf.replace('(',' (')
		buf = buf.replace(')',') ')
		buf = buf.replace('^ (','^(')
		while buf.find('**')>-1: buf = buf.replace('**','*')	# change all double ** --> single *
		buf = ' '.join(buf.split())								# change all double spaces --> single

		ll,remain = self.__walkList([buf])
		if remain: raise ValueError('__walkList(%r)  -->  ll = %r,    remain=%r, should be empty.' % (buf,ll,remain))
		if debug: print ('  run_walkList(%r)  -->  %r' % (buf,ll))
		return ll


	def __walkList(self,llist):
		"""
		walk the list and process it, returns a PhQ()
		deals with binary operators: ('^','+','*',' ','/','-')		note, ' ' same as '*'
		It also recognizes parenthesis for grouping (NOT [] or {})
		precedence is '(',')', '^', '*', '/'		note that '-' is unary ONLY
		returns the tuple: (PhQ, buf_remaining)
		"""
		global depth, debug
		if not llist: return (None,None)
		depth += 1
		spaces = (depth-1)*'  - '

		ops = {'(',')', '^', '*', ' ', '/'}					# acutally not '*' will be left
		lout = []
		if not hasattr(llist, '__iter__'): llist = [llist]	# need a list

		if debug&4: print (spaces+'top of __walkList, llist = %r' % llist)
		for ll in llist:
			if debug&4: print('%s   looping, ll = %r' % (spaces,ll))
			if isinstance(ll, PhQ):							# already processed
				if debug&4: print (spaces+'      found a PA in ll = %r,  append and loop' % (ll,))
				lout.append(ll)
				continue

			elif hasattr(ll, '__iter__'):					# this may never occur
				if debug&4: print (spaces+'      found a list in ll = %r,  append and loop' % (ll,))
				if len(ll)>0: lout.append(ll)
				continue

			elif isinstance(ll, basestring):				# more string to process
				if debug&4: print (spaces+'      found a string in ll = %r' % (ll,))
				while len(ll):
					if debug&4: print (spaces+'          top of while loop, ll = %r' % (ll,),)
					nextOp = next((i for i, ch in enumerate(ll) if ch in ops), None)
					try:	op = ll[nextOp]
					except:	op = None
					if op=='(' or op==')':					# select the first one
						i1 = ll.find('(')
						if i1<0: i1 = len(ll)+1
						i2 = ll.find(')')
						if i2<0: i2 = len(ll)+1
						nextOp = min(i1,i2)
						try:	op = ll[nextOp]
						except:	op = None
					if debug&4: print (',   looking for op: ll[%r]=%r' % (nextOp,op))

					if op==None:
						if debug&4: print (spaces+'          no op found,  process string ll=%r, call __doSolitare() later' % ll)
						if ll=='' or ll is None: print ('an empty aa')
#						try:	lout.append(self.__doSolitare(ll))
#						except:	lout.append(ll)
						lout.append(ll)						# XXXXXXXXXXXX @@@@ ####
						ll = ''

					elif op=='(':
						if debug&4: print (spaces+'          found a ")", call __walkList(%r)' % (ll[nextOp+1:],))
						(ltemp,ll) = self.__walkList(ll[nextOp+1:])	# push, pass everything AFTER the '('
						if debug&4: print (spaces+'            returned from __walkList with (ltemp=%r, ll=%r)' % (ltemp,ll))
						if ltemp=='' or ltemp is None: print ('an empty bb')
						lout.append(ltemp)

					elif op==')':							# pop, return everything AFTER the ')'
						lpass = ll[:nextOp]
						if debug&4: print (spaces+'          found a ")", call __walkList(%r)' % (lpass,))
						(ltemp,lempty) = self.__walkList(lpass)
						if ltemp=='' or ltemp is None:	pass
						else:							lout.append(ltemp)
						try:	ll = ll[nextOp+1:]
						except:	ll = ''
						if debug&4: print (spaces+'  exiting __walkList, lout =',lout)
						break

					elif op=='^' or op=='/':				# multiplication is assumed unless "^" or "/"
						stemp = ll[:nextOp]					# everything before op
						if stemp: lout.append(stemp)
						lout.append(op.replace(' ','*'))
						try:	ll = ll[nextOp+1:]
						except:	ll = ''
						if debug&4: print (spaces+'          found op=%r at %r, lout -->%r' % (op,nextOp,lout))

					else:
						stemp = ll[:nextOp]					# everything before op
						if stemp: lout.append(stemp)
						try:	ll = ll[nextOp+1:]
						except:	ll = ''
						if debug&4: print (spaces+'          found op=%r at %r, lout -->%r, skip this, mult is implied' % (op,nextOp,lout))

		remain = ll.strip()
		if debug&4: print (spaces+'      done parsing in __walkList -->  (lout=%r, remain=%r)' % (lout,remain))

		# convert strings & numbers --> PhQ() types
		lp = []
		for ll in lout:
			try:	isOp = ll in {'^', '*', ' ', '/'}
			except:	isOp = False
			if isOp:	lp.append(ll)
			elif isinstance(ll, basestring): lp.append(self.__doSolitare(ll))
			else:		lp.append(ll)
		if debug&4: print (spaces+'   converted to PhQs, -->  %r' % (lp,))

		# process the "^", highest precedence
		i = 0
		lout = []
		while i<len(lp):
			try:
				if lp[i+1]=='^':
					val = lp[i] ** lp[i+2]
					i += 2
				else: val = lp[i]
			except:	val = lp[i]
			if not val==None: lout.append(val)
			else: print ('got a val = %r,   lp=%r' % (val, lp))
			i += 1
		if debug&4: print (spaces+'   after processing the "^", -->  %r' % (lout,))

		# process the multiplications & divisions, next precedence (there are no "+" or "-")
		try:
			ll = lout[0]
			if isinstance(ll, PhQ):
				new = ll.copy()							# set new to be a copy of lout[0], a PhQ type
				skipFirst = True
			else: raise			
		except:
			new = PhQ(1,'')								# start with a pure number 1
			skipFirst = False							#	so will need to process lout[0]

		isDivide = False
		for ll in lout:
			if skipFirst:
				skipFirst = False
				continue
			elif isinstance(ll, basestring):			# remaining operators are only multiply or divide
				try:	isDivide = (ll == '/')			# isDivide flags that the next PhQ should be divided
				except:	isDivide = False
			elif isinstance(ll, PhQ):
				if isDivide:
					new /= ll
					isDivide = False
				else:
					if type(ll) is PhQcosine:	new = ll * new	# special for cosine
					else:						new *= ll
			elif ll:
				raise ValueError('got ll = %r' % ll)	# if ll is None, I don't care

		if debug&4: print (spaces+'      exiting __walkList -->  (%r,  remain=%r)' % (new,remain))
		return (new,remain)


	def __doSolitare(self, in0):
		"""
		Process a SINGLE string containing NO spaces, brackets, separators, or BINARY operators ('^','+','*','/','-')
		Only contains either:
			a number (e.g. 3 or 1.3e5)
			a SINGLE unit with possible SI prefix (e.g. 'ns', 'm', or 'kmeter', ...)
		NO combinations: NOT '2m', NOT 'kg m', 'm^2', ...
		returns a PhQ(), or one of its children
		"""
		global depth, debug
		depth += 1
		spaces = (depth-1)*'     == '
		if debug&8: print (spaces+'top of __doSolitare, in0 = %r' % in0)

		prefixPower = 1
		if in0.find('inverse&')>=0:
			prefixPower *= -1
			in0 = in0.replace('inverse&','')
		if in0.find('sq&')>=0:
			prefixPower *= 2
			in0 = in0.replace('sq&','')
		if in0.find('cubic&')>=0:
			prefixPower *= 3
			in0 = in0.replace('cubic&','')

		specialReplace = [('Å','Angstrom')]							# this must always be first to deal with Mac extended ascii Angstrom
		specialReplace.append(('\xc3\x85','Angstrom'))
		specialReplace.append((u'\xc3\x85','Angstrom'))
		# '°' refers only to Angular degrees, never Temperature
		specialReplace += [ ('tera','T'), ('mega','M'), ('kiloton','ktonTNT'), ('metre','meter'), 
			(u'litre',u'liter'), ('Imperial','Imp'), ('barreloil','barrel'), ('oil barrel','barrel'), 
			(u'#',u'lb'), ('t.short','short'), ('t.long','long'), ('massof','mass'), ('masses','mass'), ('of',''), 
			(u'\u00b0F',u'F'),(u'\u00b0C',u'Celsius'),(u'\u00b0K',u'K'),(u'\u00b0R',u'Rankine'),		# u'°F', u'°C', u'°K', u'°R'
			(u'°F','F'), ('°C','Celsius'), ('°K','K'), ('°R','Rankine'), 
			(u'Angstrom',u'Å'), (u'Ang',u'Å'), (u'µm','micron')]	# use Å for Angstrom, no conflicts
		specialReplace.append((u'°',' degree'))						# this must always be last, these are only angle degrees
		specialReplace.append(('\xc2\xb0',' degree'))
		for r0,r1 in specialReplace:
			try:	in0 = in0.replace(r0,r1)
			except:	pass

		unit = self.find(in0)			# this is: [prefix_factor, PhQ(...)]
		if debug&8: print (spaces+'  self.find(%r)  -->  %r' % (in0,unit))
		if unit is None:
			try:	unit = PhQ(float(in0),'')						# maybe just a pure number
			except:	raise ValueError('ERROR -- Cannot interpret "%r"' % (in0,))

		if unit and prefixPower!=1:
			unit.num = (unit.num)**prefixPower
			unit.scale = (unit.scale)**prefixPower
			arr = unit.dims
			for i in range(len(arr)):	# multiply each element in dim array by prefixPower
				if arr[i]: arr[i] *= prefixPower

		if debug&8: print (spaces+'  returning from __doSolitare with:  %r' % (unit,))
		return unit


	def convert(self,first,middle,last=None, transform=None):
		"""
		Converts from one unit to another
		can be called as:
			abc.convert(5,'cm','inch')
			abc.convert('5 cm','inch')
 			abc.convert('5 cm','','inch')
 			abc.convert((5,'cm'),'','inch')
 		the last argument is always the output unit
		the first is either a number or a number+unit
		the middle argument (if there are 3) is input unit (or more of the input unit)
 
		outUnit is always output units string, it may be 'SI'

		check if unitIN,unitOUT compatible
		inUnit and outUnit are string units, e.g. "m/s" or 'ft'
		if first='32 F', then unitIN is ignored

		if transform is not given, then the current value of self.transform is used, it starts as False
		"""
		if not (transform is None):						# only set when transform is passed
			try:	self.transform = bool(transform)	# this changes the default for subsequent calls to convert()
			except:	pass

		if last:
			outUnit = last				# output unit is always the last arg, maybe middle
			last = None
		elif middle:
			outUnit = middle
			middle = None
		else:
			outUnit = 'SI'
		outUnit = outUnit.strip()
		if not outUnit: outUnit = 'SI'
		# outUnit is now set

		if middle:	inUnit = middle.strip()
		else:		inUnit = ''

		# process the first argument
		if hasattr(first, '__iter__'):	# first is tuple or list
			try:	num = float(first[0])
			except:	num = 1
			try:	inUnit = first[1].strip() + ' ' + inUnit
			except:	pass
			first = None

		elif isinstance(first, basestring):
			inlist = first.split()
			try:
				num = float(inlist[0])
				del inlist[0]
			except:
				num = 1

			first = ' '.join(inlist)
			inUnit = first.strip() + ' ' + inUnit
			first = None

		else:									# first must contain a number, NOT '1 m'
			try:	num = float(first)
			except:	num = 1
			first = None

		inUnit = inUnit.strip()
		if not inUnit: inUnit = 'SI'
		try:
			if num.is_integer(): num = int(num)
		except: pass
		self.valIN = num						# the number

		if not inUnit=='SI':	unitIN = self.processInput(inUnit)			# returns a PhQ (or a child of PhQ)
		if not outUnit=='SI':	unitOUT = self.processInput(outUnit)

		try:	inUnit = unicode(inUnit, 'utf-8')
		except:	inUnit = unicode(inUnit)
		try:	outUnit = unicode(outUnit, 'utf-8')
		except:	outUnit = unicode(outUnit)

		if outUnit=='SI' and inUnit=='SI':
			raise ValueError('ERROR -- Cannot convert "SI" --> "SI", you need to specify some units.')
		elif inUnit=='SI':
			unitIN = PhQ(1,'', dims=unitOUT.dims, scale=1)	# gives SI units for unitOUT
			inUnit = unitIN.ustr
		elif outUnit=='SI':
			unitOUT = PhQ(1,'', dims=unitIN.dims, scale=1)	# gives SI units for unitIN
			outUnit = unitOUT.ustr
		self.uIN = inUnit
		self.uOUT = outUnit

		misMatch = not unitIN.dimensionsMatch(unitOUT)
		recip = False
		self.directSI = None				# this will be set if forcing
		if self.transform and misMatch:		# units do not match, try to transform with powers of (h, c, kB, & e)
			(phq,recip) = self.transformUnit(unitIN, unitOUT)
			if recip:	unitIN = phq.SI() / unitIN.SI()
			else:		unitIN *= phq
		elif misMatch:
			raise ValueError('ERROR -- Cannot transform incompatible units: %r --> %r' % (SIunits2Str(unitIN.dims),SIunits2Str(unitOUT.dims)))

		if abs(unitOUT.num - 1) > 1e-7:		# num is not 1
			unitOUT.ustr = outUnit
			unitOUT.scale *= unitOUT.num	# want .num to be 1, put factor into .scale
			unitOUT.num = 1

		if recip and self.valIN==0:	unitIN.num = float('inf')
		elif recip:	unitIN.num /= self.valIN
		else:		unitIN.num *= self.valIN
		SIvalue = unitIN.SI().num
		valOUT = unitOUT.SIrev(SIvalue)
		valOUT.err = unitIN.err

		self.SIvalue = SIvalue
		self.SIname = self.SIunitStrFromDims(unitIN)
		self.valOUT = valOUT
		return valOUT


	def transformUnit(self, uIN, uOUT, recip=False):
		"""
		used to convert when uIN.dims doesn't match uOUT.dims, e.g. 'nm'-->'eV'
		uIN & uOUT are PhQ types
		returns (phq, recip), where phq is in SI units
		constStr is what you multiply uIN by to get uOUT, i.e. uIN * constSTtr <--> uOUT
		example: uIN=kg, uOUT=J, then constStr=c^2,  kg * c^2 <--> J
		if recip is True then you also need to take the reciprocal of input value
		Note: there are 6 dimensions that participate in the transform [m,kg,sec,A,K,mole],
			and only 5 constants [c,h,kB,e,NA].
			If you allow 6 constants then everything can transform, NOT good. E.g. transforming from length --> area would be bad.

		c	(m/s)		[0,1,0,-1,0,0,0,0]
		h	(J s)		[0,2,1,-1,0,0,0,0]
		kB	(J/K)		[0,2,1,-2,0,-1,0,0]
		e	(A s)		[0,0,0,1,1,0,0,0]
		NA	(mole)		[0,0,0,0,0,0,0,1]
						[rad,m,kg,sec,A,K,cd,mole]
		"""
		dimsOUT = uOUT.dims[:]
		dimsIN = uIN.dims[:]
		if recip:
			for i in range(SI_N): dimsIN[i] = -dimsIN[i]

		delta = 8*[0]
		for i in range(SI_N): delta[i] = dimsOUT[i] - dimsIN[i]
		# cannot transform rad or cd
		if delta[0] or delta[6]: raise TypeError('ERROR -- cannot transform %s --> %s' % (uIN.ustr,uOUT.ustr))

		#	rad, m, kg, s, A, K, cd, mole
		dc = [0,1,0,-1,0,0,0,0]						# c  velocity	(m/s)
		dh = [0,2,1,-1,0,0,0,0]						# h  action		(J s)
		dk = [0,2,1,-2,0,-1,0,0]					# kB entropy	(J/K)
		de = [0,0,0,1,1,0,0,0]						# e  charge		(A s)
		dN = [0,0,0,0,0,0,0,1]						# NA number		(mole)
		# want the [ac,ah,ak,ae,aN] that make: delta = ac*dc + ah*dh + ak*dk + ae*de + aN*dN,  if possible

		ak = delta[5]/dk[5]							# only kB has K, dk[5]=-1
		for i in range(SI_N): delta[i] -= ak*dk[i]	# subtract off the dk part
		ae = delta[4]/de[4]							# only e has A, de[4]=1
		for i in range(SI_N): delta[i] -= ae*de[i]	# subtract off the de part
		ah = delta[2]/dh[2]							# only h has kg, dh[2]=1
		for i in range(SI_N): delta[i] -= ah*dh[i]	# subtract off the de part
		ac = delta[1]/dc[1]							# dc[1]=1
		for i in range(SI_N): delta[i] -= ac*dc[i]	# subtract off the de part, delta should be 0
		aN = delta[7]								# only NA mole, dk[7]=1
		delta[7] = 0								# remove the dN part

		err = 0
		for dd in delta: err += abs(dd)
		if err < 1e-7:
			# now, delta = ac*dc + ah*dh + ak*dk + ae*de + aN*dN
			# so dimsOUT = dimsIN * c**ac * h**ah * kB**ak * e**ae * NA**aN
			constStr = ''
			if ah: constStr += 'h^%d ' % ah
			if ac: constStr += 'c^%d ' % ac
			if ak: constStr += 'kB^%d ' % ak
			if ae: constStr += 'e^%d ' % ae
			if aN: constStr += 'NA^%d ' % aN
			constStr = constStr.replace('^1 ',' ')
			constStr = constStr.strip()
			if len(constStr):
				phq = self.processInput(constStr).SI()	# phq is in SI units
				uuu = unicode(uIN.ustr)
				if recip: 	self.directSI = u'{('+constStr + u') / (' + uuu + u')}'	# only used for printout
				else: 		self.directSI = u'{('+constStr + u') * ' + uuu + u'}'
			else:
				phq = PhQ(1,'')
				self.directSI = None					# only used for printout
		elif not recip:									# this failed, try with recip=true
			(phq,recip) = self.transformUnit(uIN, uOUT, recip=True)
		else:
			phq = None

		if phq is None: raise TypeError('ERROR -- cannot transform %s --> %s' % (uIN.ustr,uOUT.ustr))
		return (phq,recip)


	def SIunitStrFromDims(self, uin):
		"""
		returns a string with SI name of a known dimension type
		e.g. if uin is an energy, returns 'J'
		Note, this can sometimes give funny looking (but accurate) answers.
		SIunitStrFromDims(c^2) --> dose, which has units of (J/kg == m^2/s^2)
		"""
		dim = uin.dims
		for dd,unit,name in knownDimensions:
			if self.dimsCompatible(dd,dim): return unit
		return SIunits2Str(dim)						# no match to known units, just use the SI units, e.g. 'm s^-1'

	def dimsCompatible(self,dim0,dim1):
		"""
		returns True if dim0.dims == dims1.dims
		allows for slight (i.e. <1e-7) differences
		"""
		err = 0.0
		for i in range(SI_N): err += abs(dim1[i]-dim0[i])
		return err<1e-7


	def __applyModifiers(self,inStr):
		"""
		change things like 'kilo ton' --> 'kiloton'
		change things like 'Planck mass' --> 'Planckmass'
		change things like 'troy ounce' --> 'troyounce'
		change things like 'cubic meter' --> 'cubic&meter'		this will cause it to be cubed
		change things like 'inverse meter' --> 'inverse&meter'	this will cause it to be inverted
		"""
		inStr = inStr.replace('Kilo','kilo')
		inStr = inStr.replace('Hecto','hecto')
		SImodifiers = ['deci', 'centi', 'milli', 'micro', 'nano', 'pico', 'femto', 'atto', 'zepto', 'yocto', 'hecto', 'kilo', 'Mega', 'Giga', 'Tera', 'Peta', 'Exa', 'Zeta', 'Yotta']
		for SI in SImodifiers: inStr = inStr.replace(SI+' ',SI)		# remove spaces between SI name and unit, 'milli sec' --> 'millisec'

		modifiers = [('Planck ','Planck'), ('astronomical ','astronomical'), ('Astronomical ','astronomical'), ('sidereal ','sidereal'), ('galactic ','galactic'),
			('metric ','metric'), (' power','power'), ('US ','US'), ('Imperial ','Imperial'), ('Imp ','Imp'), ('troy ','troy'), ('Troy ','troy'), 
			('solar ','solar'), ('electron ','electron'), ('Avogadros ','Avogadros'), ('Avogadro ','Avogadro'), ('nautical ','nautical'), 
 			('Bohr ','bohr'), ('bohr ','bohr'), ('Light ','light'), ('light ','light'), ('long ','long'), ('short ','short'), ('Lunar ','lunar'), ('lunar ','lunar'), 
			('board ','board'), ('arc ','arc'), (' per ','/'),
			('Inverse','inverse'), ('inverse ','inverse'), ('inverse','inverse&'), 
			('square ','sq&'),('square','sq&'), ('sq','sq&'),('sq ','sq&'), ('cubic ','cubic&'), ('cubic','cubic&'),
			('&&','&'), (' of ',''), (u'°',u' °')]

		for m0,m1 in modifiers:
			if m0.endswith(' '):
				mdash = m0.replace(' ','-')					# 1st try '-' as separator
				try:	inStr = inStr.replace(mdash,m1)		# can have errors with things like 'Å' or '°', when not unicode
				except:	pass
			try:	inStr = inStr.replace(m0,m1)			# 2nd try ' ' as separator
			except:	pass
		return inStr


	def InterpretEnergy(self, input, unitOut):				# returns energy [unitOut]
		"""
		****** DEPRECATED  ***  DEPRECATED  ***  DEPRECATED  ***  DEPRECATED  ***  DEPRECATED  ******

		This is Deprecated, just use the regular convert options, they will do this automatically when transform=True

		convert input to an energy, units of output are unitOut
		if input is just a number, then assume that it is units of unitOut (can be 10.0, 10, '10')
		if input is a known emission line name, convert to unitOut. Known vlaues are: CuKa1, CuKa2, MoKa1, MoKa2, CuKa, MoKa
		input can have units, things like '1e4 eV',  '0.1 nm',  (0.1, 'nm'),  or  [0.1, 'nm'] all work
		raises an exception if it fails to figure out the energy or if the energy is invalid, e.g. negative
		valid energies are >=0 and nan (inf is OK).
		"""
		self.transform = True
		try:
			num = float(input)
			if num.is_integer(): num = int(num)
			energy = UnitsJZTdefault(input,unitOut,unitOut).num
		except:
			energy = UnitsJZTdefault(input,'',unitOut).num
		# check if energy is valid (cannot be negative)
		if math.isnan(energy) or energy<0: raise ValueError('the input %r not a known wavelength or a valid non-negative energy' % (input,))
		return energy



def MakeStandardUnits():
	"""
	the standard list of known units
	if "ustr=n" is not present, then ustr will be the last item in names[]
	"""
	allUnits = allUnitsData()
	angleUnits = list()
	angleUnits.append( OneUnitDefine((u'radian',u'rad'), [1,0,0,0,0,0,0,0], 'angle', 1.0, strict=True, desc='SI base unit') )
	angleUnits.append( OneUnitDefine('circle', [1,0,0,0,0,0,0,0], 'angle', 2.0*(math.pi),desc=u'one circle 360° = 2*PI radians') )
	angleUnits.append( OneUnitDefine((u'degree',u'deg',u'°'), [1,0,0,0,0,0,0,0], 'angle', degree,desc='360 degree = one circle', specialReplace=[(u'°','deg')]) )
	angleUnits.append( OneUnitDefine((u'gradian',u'grad'), [1,0,0,0,0,0,0,0], 'angle', grad, strict=True, desc='400 grad = one circle') )
	angleUnits.append( OneUnitDefine((u'arcminute',u'arcmin',u"'"), [1,0,0,0,0,0,0,0], 'angle', degree/60.0, ustr=1, desc='60 arcminute = 1 degree') )
	angleUnits.append( OneUnitDefine((u'arcsecond',u'arcsec',u'"',u"''"), [1,0,0,0,0,0,0,0], 'angle', degree/3600.0, ustr=1, desc='60 arcsecond = 1 arcminute') )
	angleUnits.append( OneUnitDefineCosine((u'cosine',u'cos',u'co'), [1,0,0,0,0,0,0,0], 'angle', desc='cos(angle)') )
	angleUnits.append( OneUnitDefine((u'steradian',u'sterad',u'sr'), [2,0,0,0,0,0,0,0], 'solid angle', ustr=1, desc='radian^2') )
	allUnits.append(angleUnits)
	# for uu in angleUnits: print unicode(uu)
	# print (' ')

	lengthUnits = list()
	lengthUnits.append( OneUnitDefine((u'm',u'meter'), [0,1,0,0,0,0,0,0], 'length', 1.0, ustr=0, desc='SI base length unit') )
	lengthUnits.append( OneUnitDefine((u'Å',u'Angstrom',u'Ang'), [0,1,0,0,0,0,0,0], 'length', 1e-10, ustr=0, desc='the Angstrom 1e-10 m', strict=True) )
	lengthUnits.append( OneUnitDefine((u'micron',u'micrometer'), [0,1,0,0,0,0,0,0], 'length', 1e-6, ustr=0, desc=u'micron, µm, micrometer, micrometre') )
	lengthUnits.append( OneUnitDefine((u'fermi',), [0,1,0,0,0,0,0,0], 'length', 1e-15, desc=u'fermi, fm is the same') )
	lengthUnits.append( OneUnitDefine((u'CuXunit',u'CuXu',u'CuX'), [0,1,0,0,0,0,0,0], 'length', CuXunit, ustr=1, err=2.8e-7, desc=u'Copper K\u03b1, old') )
	lengthUnits.append( OneUnitDefine((u'MoXunit',u'MoXu',u'MoX'), [0,1,0,0,0,0,0,0], 'length', MoXunit, ustr=1,  err=5.3e-7, desc=u'Molybdenum K\u03b1, old') )
	lengthUnits.append( OneUnitDefine((u'Xunit',u'Xu'), [0,1,0,0,0,0,0,0], 'length', Xunit, ustr=0,  err=9e-7, desc=u'old x-ray Xunit') )
	lengthUnits.append( OneUnitDefine((u'inch',u'in',u'inches'), [0,1,0,0,0,0,0,0], 'length', inch, ustr=0, desc='1 inch = 25.4 mm') )
	lengthUnits.append( OneUnitDefine((u'foot',u'feet',u'ft'), [0,1,0,0,0,0,0,0], 'length', foot, ustr=0, desc='12 inches') )
	lengthUnits.append( OneUnitDefine((u'yard',u'yd'), [0,1,0,0,0,0,0,0], 'length', 3*foot, strict=True, desc='3 feet') )
	lengthUnits.append( OneUnitDefine(u'fathom', [0,1,0,0,0,0,0,0], 'length', 6*foot, desc='6 feet') )
	lengthUnits.append( OneUnitDefine(u'rod', [0,1,0,0,0,0,0,0], 'length', 16.5*foot, desc='16.5 feet, surveying') )
	lengthUnits.append( OneUnitDefine(u'chain', [0,1,0,0,0,0,0,0], 'length', 66*foot, desc='66 feet, surveying') )
	lengthUnits.append( OneUnitDefine(u'link', [0,1,0,0,0,0,0,0], 'length', 0.66*foot, desc='66/100 feet, surveying') )
	lengthUnits.append( OneUnitDefine(u'furlong', [0,1,0,0,0,0,0,0], 'length', 660*foot, desc='660 feet, surveying') )
	lengthUnits.append( OneUnitDefine(u'league', [0,1,0,0,0,0,0,0], 'length', 3*mile, desc='3 miles') )
	lengthUnits.append( OneUnitDefine((u'mile',u'mi'), [0,1,0,0,0,0,0,0], 'length', mile, ustr=0, desc='the US mile') )
	lengthUnits.append( OneUnitDefine(u'nautical mile', [0,1,0,0,0,0,0,0], 'length', 1852, desc='nautical mile') )
	lengthUnits.append( OneUnitDefine(u'mil', [0,1,0,0,0,0,0,0], 'length', 0.001*inch, desc='thousandth of an inch') )
	lengthUnits.append( OneUnitDefine(u'point', [0,1,0,0,0,0,0,0], 'length', inch/72, desc='point, (1/72 inch)') )
	lengthUnits.append( OneUnitDefine(u'pica', [0,1,0,0,0,0,0,0], 'length', foot/72, desc='pica, (1/72 foot)') )
	lengthUnits.append( OneUnitDefine((u'Bohr radius',u'ao',u'a0'), [0,1,0,0,0,0,0,0], 'length', BohrRadius, ustr=0, err=2.3e-10, desc=u'Bohr Radius = \u210F/(me c \u03b1)') )
	lengthUnits.append( OneUnitDefine((u'Planck length',u'lplanck'), [0,1,0,0,0,0,0,0], 'length', PlanckLength, ustr=0, err=2.3e-5, desc=u'PlanckLength  = sqrt(\u210F*GN/c^3)') )
	lengthUnits.append( OneUnitDefine((u'lightyear',u'ly'), [0,1,0,0,0,0,0,0], 'length', LightYear, desc='lightyear, ly = c * julianYear, IAU definition') )
	lengthUnits.append( OneUnitDefine((u'Astronomical Unit',u'au'), [0,1,0,0,0,0,0,0], 'length', AstronomicalUnit, desc='Astronomical Unit') )
	lengthUnits.append( OneUnitDefine((u'parsec',u'pc'), [0,1,0,0,0,0,0,0], 'length', parsec, strict=True, desc='parsec') )
	lengthUnits.append( OneUnitDefine(u'cubit', [0,1,0,0,0,0,0,0], 'length', 0.525, desc='cubit, (approximate)') )
	lengthUnits.append( OneUnitDefine((u'Rack',u'RackUnit'u'U'), [0,1,0,0,0,0,0,0], 'length', 1.75*inch, ustr=2,  desc=u'Rack mount height') )
	lengthUnits.append( OneUnitDefine(u'Li', [0,1,0,0,0,0,0,0], 'length', 500, strict=True, desc='Li, (Chinese mile, 500 m)') )
	# some special wavelengths
	lengthUnits.append( OneUnitDefine('CuKa1', [0,1,0,0,0,0,0,0], 'length', 0.154059318e-9, strict=True,  err=2.8e-7, desc='Cu Kalpha-1') )
	lengthUnits.append( OneUnitDefine('CuKa2', [0,1,0,0,0,0,0,0], 'length', 0.154441318e-9, strict=True,  err=2.8e-7, desc='Cu Kalpha-2') )
	lengthUnits.append( OneUnitDefine('CuKa',  [0,1,0,0,0,0,0,0], 'length', 0.154186651e-9, strict=True, err=2.8e-7, desc='(2*CuKa1 + CuKa2)/3') )
	lengthUnits.append( OneUnitDefine('MoKa1', [0,1,0,0,0,0,0,0], 'length', 0.0709317006e-9, strict=True,  err=5.3e-7, desc='Mo Kalpha-1') )
	lengthUnits.append( OneUnitDefine('MoKa2', [0,1,0,0,0,0,0,0], 'length', 0.0713600006e-9, strict=True, err=5.3e-7, desc='Mo Kalpha-2') )
	lengthUnits.append( OneUnitDefine('MoKa',  [0,1,0,0,0,0,0,0], 'length', 0.0710744673e-9, strict=True, err=5.3e-7, desc='(2*MoKa1 + MoKa2)/3') )
	lengthUnits.append( OneUnitDefine(('Si022','Si220'),  [0,1,0,0,0,0,0,0], 'length', Si220, strict=True, err=1.6e-8, desc='Si(220) d-spacing') )
	lengthUnits.append( OneUnitDefine('Si',  [0,1,0,0,0,0,0,0], 'length', Si220*math.sqrt(8), strict=True, err=1.6e-8, desc='Si lattice constant') )
	lengthUnits.append( OneUnitDefine('Si111',  [0,1,0,0,0,0,0,0], 'length', Si220*math.sqrt(8.0/3.0), strict=True, err=1.6e-8, desc='Si(111) d-spacing') )
	allUnits.append(lengthUnits)

	inv_lengthUnits = list()
	inv_lengthUnits.append( OneUnitDefine(u'wavenumber', [0,-1,0,0,0,0,0,0], 'inverse-length', 100, desc='1/cm, no SI base inverse-length unit') )
	inv_lengthUnits.append( OneUnitDefine((u'diopter',u'dioptre',u'dpt'), [0,-1,0,0,0,0,0,0], 'inverse-length', 1, ustr=0, desc='1/m, SI base inverse-length unit') )
	inv_lengthUnits.append( OneUnitDefine((u'Rydberg',u'Ry',u'Rinf',u'R\u221e'), [0,-1,0,0,0,0,0,0], 'inverse-length', Rinf, ustr=0, strict=True, err=5.9e-12, desc='"R\u221e", Rydberg = R(inf) * hc') )
	allUnits.append(inv_lengthUnits)

	areaUnits = list()
	areaUnits.append( OneUnitDefine(u'square-meter', [0,2,0,0,0,0,0,0], 'area', 1.0, desc='SI base area unit [m^2]') )
	areaUnits.append( OneUnitDefine(u'barn', [0,2,0,0,0,0,0,0], 'area', 1e-28, desc='barn = 1e-28 m^2') )
	areaUnits.append( OneUnitDefine((u'hectare',u'ha'), [0,2,0,0,0,0,0,0], 'area', 1e4, strict=True, desc='hectare, are, ha = 100m*100m') )
	areaUnits.append( OneUnitDefine(u'are', [0,2,0,0,0,0,0,0], 'area', 100, strict=True, desc='1 are = 100m^2 = (10 x 10m)') )
	areaUnits.append( OneUnitDefine(u'acre', [0,2,0,0,0,0,0,0], 'area', 43560*ft_2, desc='acre (= 66ft*660ft = 43,560 ft^2) = (furlong * chain)') )
	areaUnits.append( OneUnitDefine(u'tetrad', [0,2,0,0,0,0,0,0], 'area', 4e6, desc='tetrad, (= 2km * 2km)') )
	areaUnits.append( OneUnitDefine(u'hectad', [0,2,0,0,0,0,0,0], 'area', 1e8, desc='hectad (= 10km * 10km)') )
	areaUnits.append( OneUnitDefine(u'myriad', [0,2,0,0,0,0,0,0], 'area', 1e10, desc='myriad (100km x 100km)') )
	areaUnits.append( OneUnitDefine(u'section', [0,2,0,0,0,0,0,0], 'area', 27878400.0*ft_2, desc='section (= 640 acres = 640*66ft*660ft = 27878400 ft^2)') )
	areaUnits.append( OneUnitDefine((u'surveytownship',u'township'), [0,2,0,0,0,0,0,0], 'area', 36*mile*mile, desc='survey township = township = (6mi * 6mi) = (6*5280ft)^2') )
	areaUnits.append( OneUnitDefine(u'ngan', [0,2,0,0,0,0,0,0], 'area', 400) )
	areaUnits.append( OneUnitDefine(u'cent', [0,2,0,0,0,0,0,0], 'area', 435.6*ft_2, desc='cent (100 cent = 1acre)') )
	allUnits.append(areaUnits)

	volumeUnits = list()
	volumeUnits.append( OneUnitDefine((u'cubic m',u'cubicmeter',u'stere'), [0,3,0,0,0,0,0,0], 'volume', 1.0, desc='SI base volume unit [m^3]') )
	volumeUnits.append( OneUnitDefine((u'liter',u'litre',u'l'), [0,3,0,0,0,0,0,0], 'volume', 1e-3, desc='liter, litre, (defined = 0.001 meter^3)') )
	volumeUnits.append( OneUnitDefine(u'cc', [0,3,0,0,0,0,0,0], 'volume', 1e-6, strict=True, desc='cubic centimeter = 1cc = 1ml = 1e-3 liter') )
	volumeUnits.append( OneUnitDefine((u'gallon',u'gal'), [0,3,0,0,0,0,0,0], 'volume', 8*USpint, desc='8 USpints') )
	volumeUnits.append( OneUnitDefine((u'quart',u'qt'), [0,3,0,0,0,0,0,0], 'volume', 2*USpint, desc='2 USpints') )
	volumeUnits.append( OneUnitDefine((u'USpint',u'pint'), [0,3,0,0,0,0,0,0], 'volume', USpint, desc='1 USpint') )
	volumeUnits.append( OneUnitDefine(u'peck', [0,3,0,0,0,0,0,0], 'volume', USpint*16, desc='16 US pints') )
	volumeUnits.append( OneUnitDefine((u'bushel',u'bu'), [0,3,0,0,0,0,0,0], 'volume', 64*USpint, desc='64 US pints = 4 pecks') )
	volumeUnits.append( OneUnitDefine((u'barrel',u'bbl'), [0,3,0,0,0,0,0,0], 'volume', USpint*(8*42), desc='42 gallons (of oil)') )
	volumeUnits.append( OneUnitDefine((u'gill',u'gil'), [0,3,0,0,0,0,0,0], 'volume', USpint/4, desc='gill, gil = 1/4 USpint, about a teacup') )
	volumeUnits.append( OneUnitDefine(u'cup', [0,3,0,0,0,0,0,0], 'volume', USfloz*8, desc='1 cup = 8 US floz') )
	volumeUnits.append( OneUnitDefine((u'tablespoon',u'tbsp'), [0,3,0,0,0,0,0,0], 'volume', USfloz/2, desc='2 Tablespoon = 1 US floz') )
	volumeUnits.append( OneUnitDefine((u'teaspoon',u'tspn',u'tsp'), [0,3,0,0,0,0,0,0], 'volume', USfloz/6, desc='1 teaspoon = Tablespoon/3 = 1/6 US floz') )
	volumeUnits.append( OneUnitDefine(u'dram', [0,3,0,0,0,0,0,0], 'volume', USfloz/8, desc='8 dram = 1 USfloz') )
	volumeUnits.append( OneUnitDefine(u'minim', [0,3,0,0,0,0,0,0], 'volume', USfloz/480, desc='480 minim = 1 USfloz') )
	volumeUnits.append( OneUnitDefine((u'Imperialgallon',u'Imperialgal',u'Imp-gal',u'Imp-gallon'), [0,3,0,0,0,0,0,0], 'volume', 8*ImpPint, desc='Imperial gallon') )
	volumeUnits.append( OneUnitDefine((u'Imperialquart',u'Imperialqt',u'Imp-quart',u'Imp-qt'), [0,3,0,0,0,0,0,0], 'volume', 2*ImpPint, desc='2 Imperial Pints = 1 Imp quart') )
	volumeUnits.append( OneUnitDefine((u'Imperialpint',u'Imp-pint'), [0,3,0,0,0,0,0,0], 'volume', ImpPint, desc='1 Imperial Pint') )
	volumeUnits.append( OneUnitDefine((u'Imperialgill',u'Imperialgil',u'Imp-gill',u'Imp-gil'), [0,3,0,0,0,0,0,0], 'volume', ImpPint/4, desc='4 Imp gill = Imp pints') )
	volumeUnits.append( OneUnitDefine((u'Imperialpeck',u'Imp-peck'), [0,3,0,0,0,0,0,0], 'volume', ImpPint*16, desc='1 Imperial peck = 16 Imp pints') )
	volumeUnits.append( OneUnitDefine((u'Imperialbushel',u'Imp-bushel',u'Imp-bu'), [0,3,0,0,0,0,0,0], 'volume', ImpPint*64, desc='1 Imperial bushel = 64 Imp pints') )
	volumeUnits.append( OneUnitDefine((u'Imperialcup',u'Imp-cup'), [0,3,0,0,0,0,0,0], 'volume',8*Impfloz, desc='1 Imp cup = 8 Imp floz') )
	volumeUnits.append( OneUnitDefine((u'Imperialdram',u'Imp-dram'), [0,3,0,0,0,0,0,0], 'volume',Impfloz/8, desc='8 Imp dram = 1 Imp floz') )
	volumeUnits.append( OneUnitDefine((u'Imperialminim',u'Imp-minim'), [0,3,0,0,0,0,0,0], 'volume',Impfloz/480, desc='480 Imp minim = 1 Imp floz') )
	volumeUnits.append( OneUnitDefine(u'cord', [0,3,0,0,0,0,0,0], 'volume', 128*ft_3, desc='cord = (4ft*8ft * 4ft)') )
	volumeUnits.append( OneUnitDefine(u'acrefoot', [0,3,0,0,0,0,0,0], 'volume', 43560*ft_3, desc='acre-foot (= 66ft*660ft*1ft = 43,560 ft^3)') )
	volumeUnits.append( OneUnitDefine((u'boardfoot',u'FBM',u'BDFT',u'BF'), [0,3,0,0,0,0,0,0], 'volume', 144*in_3, desc='board foot, [1 ft^2 x 1 inch]') )
	volumeUnits.append( OneUnitDefine(u'sccs', [0,3,0,-1,0,0,0,0], 'volume flow', 1e-6, desc='cubic centimeter per second') )
	volumeUnits.append( OneUnitDefine(u'sccm', [0,3,0,-1,0,0,0,0], 'volume flow', 1e-6/60.0, desc='cubic centimeter per minute') )
	allUnits.append(volumeUnits)

	massUnits = list()
	massUnits.append( OneUnitDefine((u'kilogram',u'Kilogram',u'kg'), [0,0,1,0,0,0,0,0], 'mass', 1, strict=True, desc='SI base mass unit [kg]') )
	massUnits.append( OneUnitDefine((u'g',u'gram'), [0,0,1,0,0,0,0,0], 'mass', 1e-3, ustr=0, desc='1000 gram = 1 kg') )
	massUnits.append( OneUnitDefine((u'pound',u'lbm',u'lb',u'#'), [0,0,1,0,0,0,0,0], 'mass', kgPerPound, ustr=0, desc='Avoirdupois pound') )
	massUnits.append( OneUnitDefine((u'ounce',u'oz'), [0,0,1,0,0,0,0,0], 'mass', kgPerPound/16, desc='Avoirdupois ounce') )
	massUnits.append( OneUnitDefine((u'stone',u'st'), [0,0,1,0,0,0,0,0], 'mass', 14.0*kgPerPound, ustr=0, desc='14 pounds') )
	massUnits.append( OneUnitDefine(u'slug', [0,0,1,0,0,0,0,0], 'mass', kgPerPound*gStd/(12.0*inch), desc='1 pound force in ft-sec') )
	massUnits.append( OneUnitDefine((u'firkin',u'fir'), [0,0,1,0,0,0,0,0], 'mass', 90*kgPerPound, ustr=0, desc='90 pounds') )
	massUnits.append( OneUnitDefine((u'grain',u'gr'), [0,0,1,0,0,0,0,0], 'mass', kgPerPound/7000, ustr=0, strict=True, desc='1 grain = 1/7000 pounds') )
	massUnits.append( OneUnitDefine((u'carat',u'ct'), [0,0,1,0,0,0,0,0], 'mass', 2.0e-4, ustr=0, desc='1 metric carat = 200 mg)') )
	massUnits.append( OneUnitDefine((u'troy pound',u'Troy pound',u'tlb'), [0,0,1,0,0,0,0,0], 'mass', troy, ustr=0, strict=True, desc='troy pound') )
	massUnits.append( OneUnitDefine((u'troy ounce',u'Troy ounce',u'toz'), [0,0,1,0,0,0,0,0], 'mass', troy/12, ustr=0, strict=True, desc='troy ounce') )
	massUnits.append( OneUnitDefine((u'longton',u't.long',u'long'), [0,0,1,0,0,0,0,0], 'mass', 2240*kgPerPound, desc='long ton = 2240 pounds') )
	massUnits.append( OneUnitDefine((u'shortton',u'short',u't.short',u'ton'), [0,0,1,0,0,0,0,0], 'mass', 2000*kgPerPound, desc='short ton = 2000 pounds') )
	massUnits.append( OneUnitDefine((u'metric ton',u'tonne'), [0,0,1,0,0,0,0,0], 'mass', 1000, ustr=0, desc='metric ton = 1000 kg') )
	massUnits.append( OneUnitDefine((u'dalton',u'amu'), [0,0,1,0,0,0,0,0], 'mass', amu, err=1.2e-8, desc='atomic mass unit') )
	massUnits.append( OneUnitDefine((u'Planck mass',u'mass Planck',u'mPlanck'), [0,0,1,0,0,0,0,0], 'mass', PlanckMass, ustr=0, err=2.3e-5, desc=u'Planck Mass = sqrt(\u210F*cLight/GN)') )
	massUnits.append( OneUnitDefine((u'solar-mass',u'mass-sun',u'sun-mass',u'sun',u'sol'), [0,0,1,0,0,0,0,0], 'mass', mSol, err=3.5e-5, desc='solar mass') )
	massUnits.append( OneUnitDefine((u'earth-mass',u'mass-earth',u'earth'), [0,0,1,0,0,0,0,0], 'mass', mEarth, err=0.0001, desc='earth mass') )
	massUnits.append( OneUnitDefine((u'muon',u'mmu'), [0,0,1,0,0,0,0,0], 'mass', muon, desc='muon mass', err=2.5e-8, specialReplace=[('massof',''), ('masses',''), ('mass','')]) )
	massUnits.append( OneUnitDefine((u'electron-mass',u'mass-electron',u'me'), [0,0,1,0,0,0,0,0], 'mass', me, strict=True, err=1.2e-8, desc='electron mass') )
	massUnits.append( OneUnitDefine((u'proton',u'mp'), [0,0,1,0,0,0,0,0], 'mass', mproton, desc='proton mass', err=1.2e-8, specialReplace=[('massof',''), ('masses',''), ('mass','')]) )
	massUnits.append( OneUnitDefine((u'neutron',u'mn'), [0,0,1,0,0,0,0,0], 'mass', mneutron, strict=True, desc='neutron mass', err=1.2e-8, specialReplace=[('massof',''), ('masses',''), ('mass','')]) )
	allUnits.append(massUnits)

	timeUnits = list()
	timeUnits.append( OneUnitDefine((u'second',u'sec',u's'), [0,0,0,1,0,0,0,0], 'time', 1, desc='SI base time unit [s]') )
	timeUnits.append( OneUnitDefine((u'minute',u'min'), [0,0,0,1,0,0,0,0], 'time', 60, strict=True, desc='1 minute = 60 sec') )
	timeUnits.append( OneUnitDefine((u'hour',u'hr'), [0,0,0,1,0,0,0,0], 'time', hour, strict=True, desc='1 hour = 60 minute') )
	timeUnits.append( OneUnitDefine(u'beat', [0,0,0,1,0,0,0,0], 'time', 3.6, desc='1 beat = 3.6 seconds') )
	timeUnits.append( OneUnitDefine(u'day', [0,0,0,1,0,0,0,0], 'time', day, desc='24 hours') )
	timeUnits.append( OneUnitDefine((u'year',u'yr'), [0,0,0,1,0,0,0,0], 'time', year, strict=True, desc='tropical year') )
	timeUnits.append( OneUnitDefine((u'week',u'wk'), [0,0,0,1,0,0,0,0], 'time', 7*day, desc='1 week = 7 days') )
	timeUnits.append( OneUnitDefine(u'fortnight', [0,0,0,1,0,0,0,0], 'time', 14*day, desc='14 days = 2 weeks') )
	timeUnits.append( OneUnitDefine((u'lunar month',u'lune',u'moon',u'lunar'), [0,0,0,1,0,0,0,0], 'time', lunarMonth, desc='1 lunar month') )
	timeUnits.append( OneUnitDefine(u'olympiad', [0,0,0,1,0,0,0,0], 'time', 4*year, desc='4 years') )
	timeUnits.append( OneUnitDefine(u'lustrum', [0,0,0,1,0,0,0,0], 'time', 5*year, desc='5 years') )
	timeUnits.append( OneUnitDefine(u'indiction', [0,0,0,1,0,0,0,0], 'time', 15*year, desc='15 years') )
	timeUnits.append( OneUnitDefine(u'decade', [0,0,0,1,0,0,0,0], 'time', 10*year, desc='10 years') )
	timeUnits.append( OneUnitDefine(u'century', [0,0,0,1,0,0,0,0], 'time', 100*year, desc='100 years') )
	timeUnits.append( OneUnitDefine(u'millennium', [0,0,0,1,0,0,0,0], 'time', 1000*year, desc='1000 years') )
	timeUnits.append( OneUnitDefine(u'jiffy', [0,0,0,1,0,0,0,0], 'time', 1e-15/c, desc='jiffy = 1 fm/c = 1e-15/c') )
	timeUnits.append( OneUnitDefine(u'shake', [0,0,0,1,0,0,0,0], 'time', 1e-8, desc='shake = 10 ns') )
	timeUnits.append( OneUnitDefine((u'Planck time',u'tPlanck'), [0,0,0,1,0,0,0,0], 'time', PlanckTime, ustr=0, err=2.3e-5, desc=u'Planck time = sqrt(\u210F*GN/c^5)') )
	timeUnits.append( OneUnitDefine(u'Svedberg', [0,0,0,1,0,0,0,0], 'time', 1e-13, desc='Svedberg   (do NOT use Sv for abbreviation since Sv is a Sievert)') )
	timeUnits.append( OneUnitDefine(u'galactic year', [0,0,0,1,0,0,0,0], 'time', 230e6*year, desc='230e6 year') )
	timeUnits.append( OneUnitDefine(u'sidereal day', [0,0,0,1,0,0,0,0], 'time', siderealDay, desc='Sidereal Day') )
	timeUnits.append( OneUnitDefine(u'sidereal year', [0,0,0,1,0,0,0,0], 'time', siderealYear, desc='Sidereal Year') )
	timeUnits.append( OneUnitDefine(u'helek', [0,0,0,1,0,0,0,0], 'time', 3.0+(1/3.0), desc='3+1/3 sec') )
	timeUnits.append( OneUnitDefine(u'pahar', [0,0,0,1,0,0,0,0], 'time', 3*hour, desc='3 hours') )
	# inverse time
	timeUnits.append( OneUnitDefine((u'Hertz',u'Hz'), [0,0,0,-1,0,0,0,0], 'frequency', 1, strict=True, desc='once per second') )
	timeUnits.append( OneUnitDefine((u'Becquerel',u'Bq'), [0,0,0,-1,0,0,0,0], 'frequency', 1, desc='1 decay/sec') )
	timeUnits.append( OneUnitDefine((u'Curie',u'Ci'), [0,0,0,-1,0,0,0,0], 'frequency', 3.7E+10, ustr=0, strict=True, desc='3.7e10 decay/sec') )
	timeUnits.append( OneUnitDefine((u'Rutherford',u'Ru'), [0,0,0,-1,0,0,0,0], 'frequency', 1e6, ustr=0, strict=True, desc='1e6 decay/sec') )
	allUnits.append(timeUnits)

	forceUnits = list()
	forceUnits.append( OneUnitDefine((u'Newton',u'N'), [0,1,1,-2,0,0,0,0], 'force', 1, strict=True, desc='SI base force unit [kg m s^-2] = [N]') )
	forceUnits.append( OneUnitDefine((u'dyne',u'dyn'), [0,1,1,-2,0,0,0,0], 'force', 1e-5, desc='1dyne = 1 [g cm s^-2] = 1e-5 N') )
	forceUnits.append( OneUnitDefine((u'kilogramforce', u'kgf'), [0,1,1,-2,0,0,0,0], 'force', gStd, desc='force of 1kg at earth surface') )
	forceUnits.append( OneUnitDefine(u'kip', [0,1,1,-2,0,0,0,0], 'force', 1000*kgPerPound*gStd, desc='1000 pounds of force') )
	forceUnits.append( OneUnitDefine((u'poundforce',u'lbf'), [0,1,1,-2,0,0,0,0], 'force', kgPerPound*gStd, ustr=0, desc='1 pound of force') )
	forceUnits.append( OneUnitDefine((u'poundal',u'pdl'), [0,1,1,-2,0,0,0,0], 'force', 0.138254954376, ustr=0, desc='1 poundal = 1 ft-lb/s^-2') )
	allUnits.append(forceUnits)

	velocityUnits = list()
	velocityUnits.append( OneUnitDefine((u'meters per second',u'meters per sec',u'mps'), [0,1,0,-1,0,0,0,0], 'velocity', 1, desc='SI base velociay unit [m/s]') )
	velocityUnits.append( OneUnitDefine((u'kilometers per hour',u'kph'), [0,1,0,-1,0,0,0,0], 'velocity', 1.0/3.6, strict=True, desc='kilometers per hour, kph, [km/hr] 3600/1000') )
	velocityUnits.append( OneUnitDefine(u'miles per sec', [0,1,0,-1,0,0,0,0], 'velocity', mile, desc='miles per sec, [mi/s] = 1609.344 m/s') )
	velocityUnits.append( OneUnitDefine((u'feet per sec',u'fps'), [0,1,0,-1,0,0,0,0], 'velocity', foot, desc='feet per sec, [ft/s]') )
	velocityUnits.append( OneUnitDefine((u'miles per hour',u'mph'), [0,1,0,-1,0,0,0,0], 'velocity', mile/3600, strict=True, desc='miles per hour, mph, [mi/hr]') )
	velocityUnits.append( OneUnitDefine((u'knot',u'kt'), [0,1,0,-1,0,0,0,0], 'velocity', 1852.0/3600.0, ustr=0, strict=True, desc='nautical miles per hour') )
	velocityUnits.append( OneUnitDefine(u'mach', [0,1,0,-1,0,0,0,0], 'velocity', 340, desc='Mach number Mach 1 = 340 m/s') )
#	velocityUnits.append( OneUnitDefine((u'speed light','c'), [0,1,0,-1,0,0,0,0], 'velocity', c, strict=True, specialReplace=[('speedof','')], desc='speed of light in vacuum = 299792458 m/s') )
	velocityUnits.append( OneUnitDefine((u'speed light','c'), [0,1,0,-1,0,0,0,0], 'velocity', c, specialReplace=[('speedof','')], desc='speed of light in vacuum = 299792458 m/s') )
	allUnits.append(velocityUnits)

	energyUnits = list()
	energyUnits.append( OneUnitDefine((u'Joule',u'J'), [0,2,1,-2,0,0,0,0], 'energy', 1, strict=True, desc='SI base energy unit [kg m^2 s^-2] = [N*m]') )
	energyUnits.append( OneUnitDefine(u'erg', [0,2,1,-2,0,0,0,0], 'energy', 1e-7, desc='erg = [g cm^2 s^-2] = [dyn*cm]') )
	energyUnits.append( OneUnitDefine((u'calorie',u'cal'), [0,2,1,-2,0,0,0,0], 'energy', cal, desc='Thermochemical calorie') )
	energyUnits.append( OneUnitDefine(u'BTU', [0,2,1,-2,0,0,0,0], 'energy', BTU, strict=True, desc='1 BTU = 1055.06 J') )
	energyUnits.append( OneUnitDefine((u'kWh',u'kiloWatthour'), [0,2,1,-2,0,0,0,0], 'energy', 3.6e6, desc='1 kW for 1 hour') )
	energyUnits.append( OneUnitDefine((u'electron Volt',u'electron volt',u'eV'), [0,2,1,-2,0,0,0,0], 'energy', e, strict=True, desc='1 electron-volt') )
	energyUnits.append( OneUnitDefine((u'Rydberg hc',u'Ry hc',u'Rinf hc',u'R\u221e hc'), [0,2,1,-2,0,0,0,0], 'energy', Rinf_hc, ustr=0, strict=True, err=5.9e-12, desc='"R\u221ehc", R(inf) * hc') )
	energyUnits.append( OneUnitDefine((u'Hartree',u'Ha'), [0,2,1,-2,0,0,0,0], 'energy', 2*Rinf_hc, strict=True, err=1.2e-8, desc='1 Hartree = 2 Rydberg*hc') )
	energyUnits.append( OneUnitDefine((u'foot pound',u'ftlb',u'ftlbf'), [0,2,1,-2,0,0,0,0], 'energy', (foot*kgPerPound*gStd), ustr=1, desc='1 pound force over 1 foot') )
	energyUnits.append( OneUnitDefine(u'therm', [0,2,1,-2,0,0,0,0], 'energy', 1e5*BTU, desc='1 therm = 1e5 BTU') )
	energyUnits.append( OneUnitDefine(u'quad', [0,2,1,-2,0,0,0,0], 'energy', 1e15*BTU, desc='1 quad = 1e15 BTU') )
	energyUnits.append( OneUnitDefine((u'watt year',u'wyr'), [0,2,1,-2,0,0,0,0], 'energy', tropicalYear, ustr=0, desc=' Watt-year = (days in tropical year) * (seconds in day)') )
	energyUnits.append( OneUnitDefine(u'gtnt', [0,2,1,-2,0,0,0,0], 'energy', cal, desc='gram of TNT') )
	energyUnits.append( OneUnitDefine((u'MgTNT',u'tontnt',u'tonoftnt'), [0,2,1,-2,0,0,0,0], 'energy', 1e9*cal, ustr=0, desc='1 metric ton of TNT') )
	energyUnits.append( OneUnitDefine((u'Planck energy',u'ePlanck'), [0,2,1,-2,0,0,0,0], 'energy', PlanckEnergy, ustr=0, err=2.3e-5, desc=u'Planck energy = sqrt(\u210F * c^5 / GN) = 1.956113e9 J') )
	energyUnits.append( OneUnitDefine((u'Bethe',u'foe'), [0,2,1,-2,0,0,0,0], 'energy', 1e44, ustr=0, strict=True, desc='foe, Bethe = 1e51 ergs = 1e44 J') )
	allUnits.append(energyUnits)

	powerUnits = list()
	powerUnits.append( OneUnitDefine((u'Watt',u'W'), [0,2,1,-3,0,0,0,0], 'power', 1, strict=True, desc='SI base power unit [kg m^2 s^-3] = [J/s]') )
	powerUnits.append( OneUnitDefine((u'horse power',u'hp'), [0,2,1,-3,0,0,0,0], 'power', HP, desc='horse power = 550 ft*lbf') )
	allUnits.append(powerUnits)

	pressureUnits = list()
	pressureUnits.append( OneUnitDefine(('Pascal','Pa'), [0,-1,1,-2,0,0,0,0], 'pressure', 1, strict=True, desc='SI base pressure unit [kg m^-1 s^-2] = [N/m^2]') )
	pressureUnits.append( OneUnitDefine('bar', [0,-1,1,-2,0,0,0,0], 'pressure', 1e5, desc='10^5 Pa, almost 1 atm') )
	pressureUnits.append( OneUnitDefine(('atmosphere','atm'), [0,-1,1,-2,0,0,0,0], 'pressure', 101325, desc='1 standard atmosphere = 101325 Pa') )
	pressureUnits.append( OneUnitDefine(('Torricelli','mmHg','Torr','torr'), [0,-1,1,-2,0,0,0,0], 'pressure', 101325.0/760.0, strict=True, desc='760 Torr = 760 mm Hg = 1 atm') )
	pressureUnits.append( OneUnitDefine(('inches of Water','inches water','inches of H2O','inchesH2O','inH2O'), [0,-1,1,-2,0,0,0,0], 'pressure', 249.08891, ustr=0, desc='406.7824617322385 inches of H2O = 1 atm') )
	pressureUnits.append( OneUnitDefine('psi', [0,-1,1,-2,0,0,0,0], 'pressure', kgPerPound*gStd/(inch*inch), strict=True, desc='1 pound / in^2') )
	allUnits.append(pressureUnits)

	TemperatureUnits = list()
	TemperatureUnits.append( OneUnitDefine((u'Kelvin',u'K'), [0,0,0,0,0,1,0,0], 'Temperature', 1, strict=True, desc='SI base Temperature unit [K]') )
	TemperatureUnits.append( OneUnitDefine((u'Celsius',u'Centigrade',u'centigrade'), [0,0,0,0,0,1,0,0], 'Temperature', 1, ustr=0, strict=True, desc='Kelvin = Celsius + 273.15', offset=CelsiusK) )
	TemperatureUnits.append( OneUnitDefine(u'Rankine', [0,0,0,0,0,1,0,0], 'Temperature', 1.8, strict=True, desc='Kelvin = 1.8 * Rankine,  1.8 = 9/5') )
	TemperatureUnits.append( OneUnitDefine((u'Fahrenheit',u'F'), [0,0,0,0,0,1,0,0], 'Temperature', 1/1.8, ustr=0, strict=True, desc='Kelvin = (Fahrenheit-32)/1.8 + 273.15', offset=CelsiusK-32.*5./9.) )
	TemperatureUnits.append( OneUnitDefine((u'Planck Temperature',u'TPlanck',u'TP'), [0,0,0,0,0,1,0,0], 'Temperature', PlanckTemperature, ustr=0, strict=True, desc=u'Planck Temperature = sqrt(\u210F * c^5 / (GN * kB^2))') )
	# kT type units are taken care of by the transformUnit()
	allUnits.append(TemperatureUnits)

	luminousUnits = list()
	# 1 candela is 1/683 Watt per steradian.
	luminousUnits.append( OneUnitDefine((u'candela',u'cd'), [0,0,0,0,0,0,1,0], 'luminous', 1, desc='SI base luminous intensity unit [cd]') )
	allUnits.append(luminousUnits)
	#	https://en.wikipedia.org/wiki/Candela#Relationships_between_luminous_intensity,_luminous_flux,_and_illuminance

	lightFluxUnits = list()
	lightFluxUnits.append( OneUnitDefine((u'Lumen',u'lm'), [2,0,0,0,0,0,1,0], 'lightFlux', 1, ustr=0, desc='SI base light flux unit [cd * steradian]') )
	allUnits.append(lightFluxUnits)

	LuminanceUnits = list()
	LuminanceUnits.append( OneUnitDefine((u'nit'), [0,-2,0,0,0,0,1,0], 'luminance', 1, ustr=0, desc='SI base luminance [candela / m^2]') )
	LuminanceUnits.append( OneUnitDefine((u'Lux',u'lx'), [2,-2,0,0,0,0,1,0], 'illuminance', 1, ustr=0, desc='SI base light illuminance [lumen / m^2]') )
	LuminanceUnits.append( OneUnitDefine((u'Phot',u'phot',u'ph'), [2,-2,0,0,0,0,1,0], 'illuminance', 1e4, ustr=0, strict=True, desc='light illuminance [lumen / cm^2]') )
	LuminanceUnits.append( OneUnitDefine((u'foot-candle',u'ftc'), [2,-2,0,0,0,0,1,0], 'illuminance', foot**-2, ustr=0, desc='lumen / sq-ft') )
	allUnits.append(LuminanceUnits)

	QuantityUnits = list()
	QuantityUnits.append( OneUnitDefine((u'mole',u'mol'), [0,0,0,0,0,0,0,1], 'Quantity', 1, desc='SI base quantity of matter') )
	QuantityUnits.append( OneUnitDefine((u'Avogadro-Number',u'Avogadros-Number',u'NA'), [0,0,0,0,0,0,0,1], 'Quantity', 1, strict=True, err=1.2e-8, desc='Avogadro Number, number of atoms in a mole') )
	QuantityUnits.append( OneUnitDefine(('atom','molecule'), [0,0,0,0,0,0,0,1], 'Quantity', 1/NA, ustr=0, err=1.2e-8, desc='one atom, there are NA in a mole') )
	allUnits.append(QuantityUnits)

	ElectricalUnits = list()
	ElectricalUnits.append( OneUnitDefine((u'Coulomb',u'Cb',u'C'), [0,0,0,1,1,0,0,0], 'charge', 1, strict=True, err=6.2e-9, desc='SI base quantity of Electrical Charge A s') )
	ElectricalUnits.append( OneUnitDefine((u'elementary charge',u'qe',u'q'), [0,0,0,1,1,0,0,0], 'charge', e, ustr=1, strict=True, err=6.1e-9, desc='charge on an electron') )
	ElectricalUnits.append( OneUnitDefine((u'Franklin',u'statcoulomb',u'Fr'), [0,0,0,1,1,0,0,0], 'charge',  0.1/c, ustr=1, strict=True, desc='unit of charge in cgs system') )
	ElectricalUnits.append( OneUnitDefine((u'Ampere',u'Amp',u'A'), [0,0,0,0,1,0,0,0], 'current', 1, strict=True, desc='SI base quantity of Electrical current') )
	ElectricalUnits.append( OneUnitDefine((u'Biot',u'Bi'), [0,0,0,0,1,0,0,0], 'current', 10, ustr=0, strict=True, desc='1 Biot = 10 Amp') )
	ElectricalUnits.append( OneUnitDefine((u'Gilbert',u'Gi'), [0,0,0,0,1,0,0,0], 'current', 2.5*pi, ustr=0, strict=True, desc='1 Gilbert = (1/4pi) Biot') )
	ElectricalUnits.append( OneUnitDefine(u'Farad', [0,-2,-1,4,2,0,0,0], 'capacitance', 1, strict=True, desc='1 Coulomb / Volt') )
	ElectricalUnits.append( OneUnitDefine((u'Volt',u'V'), [0,2,1,-3,-1,0,0,0], 'voltage', 1, strict=True, desc='1 Joule/Coulomb') )
	ElectricalUnits.append( OneUnitDefine((u'Ohm',u'\u03A9'), [0,2,1,-3,-2,0,0,0], 'resistance', 1, strict=True, desc='1 Volt/Amp') )
	ElectricalUnits.append( OneUnitDefine(u'Siemen', [0,-2,-1,3,2,0,0,0], 'inverse resistance', 1, strict=True, desc='1/Ohm') )
	ElectricalUnits.append( OneUnitDefine((u'Henry',u'H'), [0,2,1,-2,-2,0,0,0], 'inductance', 1, ustr=0, strict=True, desc='1 Weber/Amp') )
	ElectricalUnits.append( OneUnitDefine((u'Gauss',u'G'), [0,0,1,-2,-1,0,0,0], 'magnetic flux density', 1e-4, strict=True, desc='cgs unit of magnetic flux density') )
	ElectricalUnits.append( OneUnitDefine(u'Tesla', [0,0,1,-2,-1,0,0,0], 'magnetic flux density', 1, strict=True, desc='SI unit of magnetic flux density') )
	ElectricalUnits.append( OneUnitDefine((u'Weber',u'Wb'), [0,2,1,-2,-1,0,0,0], 'magnetic flux', 1, ustr=0, strict=True, desc='SI unit of magnetic flux = Tesla*m^2') )
	ElectricalUnits.append( OneUnitDefine((u'Maxwell',u'Mx'), [0,2,1,-2,-1,0,0,0], 'magnetic flux', 1e-8, ustr=0, strict=True, desc='cgs unit of magnetic flux = Gauss*cm^2') )
	ElectricalUnits.append( OneUnitDefine((u'Oersted',u'Oe'), [0,-1,0,0,1,0,0,0], 'magnetic H field', 250.0/pi, ustr=0, strict=True, desc='cgs unit of magnetic flux = Gilbert/cm') )
	allUnits.append(ElectricalUnits)

	MiscUnits = list()
	MiscUnits.append( OneUnitDefine(u'one', [0,0,0,0,0,0,0,0], '', 1, desc='the number 1') )
	MiscUnits.append( OneUnitDefine((u'pi',u'π'), [0,0,0,0,0,0,0,0], '', math.pi, desc=u'"π", ratio of circumference/diameter') )
	MiscUnits.append( OneUnitDefine('e', [0,0,0,0,0,0,0,0], '', math.e, desc='"e", base of natrual log') )
	MiscUnits.append( OneUnitDefine(('alpha',u'\u03b1'), [0,0,0,0,0,0,0,0], '', alpha, strict=True, err=2.3e-10, desc=u'"\u03b1", fine structure constant ~1/137') )
	if is2019:
		MiscUnits.append( OneUnitDefine(('hbar',u'\u210F'), [0,2,1,-1,0,0,0,0], 'action', hbar, strict=True, desc=u'"\u210F", reduced Planck constant [J s]') )
		MiscUnits.append( OneUnitDefine('h', [0,2,1,-1,0,0,0,0], 'action', h, strict=True, desc=u'"h", Planck constant [J s]') )
	else:
		MiscUnits.append( OneUnitDefine(('hbar',u'\u210F'), [0,2,1,-1,0,0,0,0], 'action', hbar, strict=True, err=1.2e-8, desc=u'"\u210F", reduced Planck constant [J s]') )
		MiscUnits.append( OneUnitDefine('h', [0,2,1,-1,0,0,0,0], 'action', h, strict=True, err=1.2e-8, desc=u'"h", Planck constant [J s]') )

	MiscUnits.append( OneUnitDefine(('eps0',u'\u03B50',u'\u03F50'), [0,-3,-1,4,2,0,0,0], 'permittivity', 1e7/(4*pi*c*c), strict=True, desc=u'\u03F50, permittivity of free space Coulomb/(Volt meter)') )
	MiscUnits.append( OneUnitDefine('gN', [0,1,0,-2,0,0,0,0], 'acceleration', gStd, strict=True, desc='"g", std acceleration of gravity (m/s^2) on earth') )
	MiscUnits.append( OneUnitDefine('kB', [0,2,1,-2,0,-1,0,0], 'entropy', kB, strict=True, err=5.7e-7, desc='"kB", Boltzmann Constant, J/K') )
	MiscUnits.append( OneUnitDefine(('Gravity','Big G'), [0,3,-1,-2,0,0,0,0], 'gravity field', GN, ustr=0, err=4.7e-5, desc='"GN", Newton Gravity Constant (m^3 kg^-1 s^-2)') )

	MiscUnits.append( OneUnitDefine((u'mu0',u'µ0'), [0,1,1,-2,-2,0,0,0], 'magnetic constant', 4*pi*1E-7, strict=True, desc=u'"µ\u2080", vacuum permeability 4π*1e-7 (tesla m Amp^-1)') )
	MiscUnits.append( OneUnitDefine((u'muB',u'µB'), [0,2,0,0,1,0,0,0], 'magnetic moment', e*hbar/(2*me), strict=True, err=6.2e-9, desc=u'"µB", Bohr magneton = e*\u210F/(2*me)') )
	MiscUnits.append( OneUnitDefine((u'phi0',u'Phi0',u'\u03d50',u'\u03C60'), [0,2,1,-2,-1,0,0,0], 'magnetic flux', hbar*2*pi/(2*e), strict=True, err=6.1e-9, desc=u'"\u03C6\u2080", magnetic flux quantum = h/(2e)') )
	MiscUnits.append( OneUnitDefine((u'sigma',u'\u03c3'), [0,0,1,-3,0,-4,0,0], 'Stefan-Boltzmann', sigma, strict=True, err=2.3e-6, desc=u'"\u03c3", Stefan-Boltzmann constant = π^2 kB^4 / (60*\u210F^3 c^2) [Watt m^-2 K^-4]') )

	MiscUnits.append( OneUnitDefine((u'Gray',u'Gy'), [0,2,0,-2,0,0,0,0], 'dose', 1, ustr=0, strict=True, desc='SI base quantity of dose 1 J/kg') )
	#	MiscUnits.append( OneUnitDefine((u'Roentgen',u'R'), [0,0,-1,1,1,0,0,0], 'x-ray exposure', 2.58E-4, strict=True, desc='258 µCoulomb/kg') )
	MiscUnits.append( OneUnitDefine((u'Rad',u'R'), [0,2,0,-2,0,0,0,0], 'dose', 0.01, ustr=0, strict=True, desc='dose of 0.01 J/kg') )
	MiscUnits.append( OneUnitDefine((u'Sievert',u'Sv'), [0,2,0,-2,0,0,0,0], 'dose', 1, ustr=0, strict=True, desc='dose of (Quality Factor) * 1 J/kg') )
	MiscUnits.append( OneUnitDefine((u'Banana', u'banana', u'BED'), [0,2,0,-2,0,0,0,0], 'dose', 98.0e-9, ustr=0, strict=True, desc='dose of 1 Banana = 98 nano-Sv, ~15 Bq') ) # Wikipedia, "Banana equivalent dose"

	MiscUnits.append( OneUnitDefine(('miles per gallon','mpg'), [0,-2,0,0,0,0,0,0], 'fuel', mile/(8*USpint), desc='Miles per USgallon') )
	MiscUnits.append( OneUnitDefine(('kilometers per liter','kpl'), [0,-2,0,0,0,0,0,0], 'fuel', 1e6, desc='kilometers per liter') )
	MiscUnits.append( OneUnitDefine(('Jansky','Jy'), [0,0,1,-2,0,0,0,0], 'flux density', 1e-26, ustr=0, strict=True, desc='10e-26 Watt/(m^2 Hz)') )	# kg/sec^2
	MiscUnits.append( OneUnitDefine(('Langley','Ly'), [0,0,1,-2,0,0,0,0], 'flux density', 41840, ustr=0, strict=True, desc='1 Thermochemical calorie/cm^2') )
	MiscUnits.append( OneUnitDefine(('stoke','St'), [0,-1,1,-1,0,0,0,0], 'viscosity', 1e-4, ustr=0, strict=True, desc='1 cm^2/sec') )
	MiscUnits.append( OneUnitDefine(('Poise','Po'), [0,-1,1,-1,0,0,0,0], 'viscosity', 0.1, ustr=0, strict=True, desc='Pascal second') )
	MiscUnits.append( OneUnitDefine((u'kat',u'katal'), [0,0,0,-1,0,0,0,1], 'catalytic activity', 1.0, ustr=0, desc='SI unit of catalytic activity') )
	MiscUnits.append( OneUnitDefine(('rayl','Rayleigh'), [0,-2,1,-1,0,0,0,0], 'specific acoustic impedance', 1.0, ustr=0, desc='specific acoustic impedance') )
	MiscUnits.append( OneUnitDefine('denier', [0,-1,1,0,0,0,0,0], 'linear density', 1/9e6, ustr=0, desc='linear density of fiber, 1 denier = 1g/9km') )
	MiscUnits.append( OneUnitDefine('tex', [0,-1,1,0,0,0,0,0], 'linear density', 1e-6, ustr=0, desc='linear density of fiber, 1 tex = 1g/km') )
	allUnits.append(MiscUnits)

	return allUnits


UnitsJZTdefault = UnitsJZT(units='standard')




"""	============================================================================
	================================= Run Testing ==================================
"""
if __name__ == '__main__':
	"""
	Main function for JZTunits.py.
	Test cases for units conversion to verify correct behavior.
	"""
	import sys
	from JZTutil import JZTtesting

	""" =========================== Units Test Routines ============================ """
	def test_SIprefixes():
		def differ(a,b):
			if a==b: return False
			elif abs((a-b)/a) < 1e-15: return False
			return True

		def test_1SIprefix(cc,prefix, answer, bad=False):
			try:
				value = cc.SIprefix2factor(prefix)
				if differ(value,answer): raise ValueError('wrong number, should be %r' % (answer,))
				try:	print (u'     %s  -->  %.2g' % (prefix, cc.SIprefix2factor(prefix)))
				except:	print (u'     %r  -->  %.2g' % (prefix, cc.SIprefix2factor(prefix)))
				return False
			except Exception as e:
				if bad:	errStr = '     '
				else:	errStr = 'ERR  '
				print (u'%sINVALID -- %r  -->  %r' % (errStr,prefix, e))
				return not bad

		err = False
		cc = UnitsJZTdefault
		preVals = [('h',100),('k',1000),('M',1e6),('G',1e9),('T',1e12),('P',1e15),('E',1e18),('Z',1e21),('Y',1e24)]
		for prefix,val in preVals: err |= test_1SIprefix(cc,prefix,val)

		print (' ')
		preVals = [('d',0.1),('c',0.01),('m',0.001),('µ',1e-6),(u'µ',1e-6),('n',1e-9),('p',1e-12),('f',1e-15),('a',1e-18),('z',1e-21),('y',1e-24)]
		for prefix,val in preVals: err |= test_1SIprefix(cc,prefix,val)

		print (' ')
		preVals = [('deci',0.1),('centi',0.01),('milli',1e-3),('micro',1e-6),('nano',1e-9),('pico',1e-12),('femto',1e-15),('atto',1e-18),('zepto',1e-21),('yocto',1e-24)]
		for prefix,val in preVals: err |= test_1SIprefix(cc,prefix,val)

		print (' ')
		preVals = [ ('hecto',1e2), ('kilo',1e3), ('Kilo',1e3), ('Mega',1e6), ('Giga',1e9), ('Tera',1e12), ('Peta',1e15), ('Exa',1e18), ('Zeta',1e21), ('Yotta',1e24) ]
		for prefix,val in preVals: err |= test_1SIprefix(cc,prefix,val)

		print (' ')
		err |= test_1SIprefix(cc,'nK',1e-6, bad=True)
		err |= test_1SIprefix(cc,'knK',1e-3, bad=True)
		err |= test_1SIprefix(cc,'nGiga',1, bad=True)
		err |= test_1SIprefix(cc,'nGigaK',1e3, bad=True)

		print (' ')
		err |= test_1SIprefix(cc,'x',1.0, bad=True)
		err |= test_1SIprefix(cc,'xn',1.0, bad=True)
		err |= test_1SIprefix(cc,'MEGA',1.0, bad=True)
		err |= test_1SIprefix(cc,'m',1.0, bad=True)
		return err


	def test_ConvertGeneric(valueIN, unitIN, unitOUT, expected=None, explanation='', tol=None, transform=False):
		""" returns False if no error """
		ValueOut = float('nan')
		try:
			ValueOut = UnitsJZTdefault.convert(valueIN, unitIN, unitOUT, transform=transform)
			if tol is None:
				try:	tol = max(1e-15,ValueOut.err)
				except:	tol = 1e-15

			if not (expected is None):
				if fractionalError(ValueOut.num,expected) > tol: raise ValueError('computed != expected')
			try:	unitIN = unicode(unitIN, 'utf-8')
			except:	unitIN = unicode(unitIN)
			try:	unitOUT = unicode(unitOUT, 'utf-8')
			except:	unitOUT = unicode(unitOUT)
			try:	print ('     %r (%s) --> (%s)  ==>  %s' % (valueIN,unitIN,unitOUT,unicode(ValueOut)))
			except:	print ('     %r (%r) --> (%r)  ==>  %r' % (valueIN,unitIN,unitOUT,ValueOut))
			return False
		except Exception as e:
			if explanation:	errStr = '     '
			else:			errStr = 'ERR  '
			if expected is None:
				print ('%sINVALID -- %r (%r)  -->  %r     %r     %r' % (errStr,valueIN,unitIN, unitOUT, e,explanation))
			else:
				print ('%sINVALID -- %r (%r)  -->  %r     %r     should be %r[%s]  NOT  %s' % (errStr,valueIN,unitIN, unitOUT, e,expected,unitOUT, unicode(ValueOut)))
			return len(explanation)<1

	def fractionalError(a,b):
		try:
			a = float(a)
			b = float(b)
			if a==0.0:				# a is zero, b is zero or not zero
				return abs(b)
			elif b==0.0:			# b is zero, a is not zero
				return abs(a)
			else:
				return math.fabs(b-a)/b
		except:
			return 1				# not numbers, a big error


	def test_LengthUnits():
		inOut = [('m','m'),('ft','m'),('foot','m'),('mm','m'),('mm^2','m^2'),('m^2','mm^2'),(u'µm^1/2','m^1/2'),(u'µm^0.5','m^0.5'),('inch','m'),
			('CuKa1','Å'),('CuKa1','nm'),('CuKa2','Å'),('CuKa','Å'),('MoKa1','Å'),('MoKa2','Å'),('MoKa','Å'), ('Si022','Å'),('Si220','Å'),('Si','Å'),
			('CuXunit','Å'),('CuXu','Å'),('CuX','Å'),('MoXunit','Å'),('MoXu','Å'),('MoX','Å'),('Xunit','Å'),('Xu','Å'),
			(u'Å','m'),(u'Å','m'),(u'Å^2','m^2'),('Ang^2','m^2'),(u'Å^-1','m^-1'), ]
		err = False
		for uin,out in inOut:	err |= test_ConvertGeneric(1,uin,out)
		print ('  ')

		err |= test_ConvertGeneric(1,'metre','inch', 1/0.0254)
		err |= test_ConvertGeneric(1,u'µm','m', 1e-6)
		err |= test_ConvertGeneric(1,u'µm','m', 1e-6)
		err |= test_ConvertGeneric(1,u'Angstrom','m', 1e-10)
		err |= test_ConvertGeneric(1,'fermi','m', 1e-15)
		err |= test_ConvertGeneric(1,'inch','mm', 25.4)
		err |= test_ConvertGeneric(1,'U','mm', 1.75*25.4)
		err |= test_ConvertGeneric(1,'mil','inch', 0.001)
		err |= test_ConvertGeneric(1,'foot','inch', 12)
		err |= test_ConvertGeneric(1,'yd','feet', 3)
		err |= test_ConvertGeneric(1,'mile','feet', 5280)
		err |= test_ConvertGeneric(1,'nauticalmile','m', 1852)
		err |= test_ConvertGeneric(1,'nautical mile','m', 1852)
		err |= test_ConvertGeneric(1,'foot','pica', 72)
		err |= test_ConvertGeneric(1,'inch','point', 72)
		err |= test_ConvertGeneric(1,'fathom','feet', 6)
		err |= test_ConvertGeneric(1,'chain','feet', 66)
		err |= test_ConvertGeneric(1,'link','feet', 0.66)
		err |= test_ConvertGeneric(1,'rod','feet', 16.5)
		err |= test_ConvertGeneric(1,'furlong','feet', 660)
		err |= test_ConvertGeneric(1,'league','mile', 3)
		err |= test_ConvertGeneric(1,'Xunit','pm', 0.1002088)
		err |= test_ConvertGeneric(1,'CuXunit','pm', 0.100207697)
		err |= test_ConvertGeneric(1,'CuX','pm', 0.100207697)
		err |= test_ConvertGeneric(1,'MoXu','pm', 0.100209952)
		err |= test_ConvertGeneric(1,'Si022',u'Å', 1.920155714)
		err |= test_ConvertGeneric(1,'Si','pm', 543.1020504)
		err |= test_ConvertGeneric(1,'cubit','m', 0.525)
		err |= test_ConvertGeneric(1,'Li','m', 500)
		err |= test_ConvertGeneric(1,'a0',u'Å', 0.52917721092)
		err |= test_ConvertGeneric(1,'Planck Length','m', 1.6162283729742848e-35)
		err |= test_ConvertGeneric(1,'Planck-Length','m', 1.6162283729742848e-35)
		err |= test_ConvertGeneric(1,'PlanckLength','m', 1.6162283729742848e-35)
		err |= test_ConvertGeneric(1,'au','Gm', 149.5978707)
		err |= test_ConvertGeneric(1,'astronomical unit','mile', 92955807.27302554)
		err |= test_ConvertGeneric(1,'parsec','au', 206264.80624709633)
		err |= test_ConvertGeneric(1,'parsec','lightyear', 3.2615637771674333)

		print ('\n    check all spellings')
		testLengths = [u'µm','micron','microns','micrometer','micrometre','CuXunit','CuXu','MoXunit','MoXu','Xunit','Xu','fermi', \
			'foot','feet','ft','yard','yd','nauticalmile','mile','mi','mil','point','pica','lightyear','ly','au','astronomicalunit', \
			'parsec','pc','a0','ao','BohrRadius','PlanckLength','RackUnit','fathom','chain','link','rod','furlong','league','cubit','Li', \
			'inch','in','inches','m','meter','metre',u'Å','Angstrom','Ang']
		for tl in testLengths: err |= test_ConvertGeneric(1,tl,'m')

		print (' ')
		err |= test_ConvertGeneric(1,'mm^2','m^2')
		err |= test_ConvertGeneric(1,'m^2','cm^2')
		inOut =  [('pc','m'),('mpc','m'),('Mpc','m'),(u'µm^1/2','m^1/2'),(u'µm^1/2.','m^1/2.'),('yd','m'),('dyd','m')]
		for uin,out in inOut:	err |= test_ConvertGeneric(1,uin,out)

		print (' ')
		err |= test_ConvertGeneric(1,'PC', 'm', explanation='parsec is case sensitive')
		err |= test_ConvertGeneric(1,'', 'm', explanation='no unit given')
		err |= test_ConvertGeneric(1,'xx', 'm', explanation='"xx" not valid length unit')
		err |= test_ConvertGeneric(1,'mxx', 'm', explanation='"mxx" not valid length unit')
		err |= test_ConvertGeneric(1,'xm', 'm', explanation='"xm" not valid length unit')
		err |= test_ConvertGeneric(1,'xx', 'm', explanation='"x" not valid length unit')
		err |= test_ConvertGeneric(1,'s', 'm', explanation='"s" is not valid length unit')
		print (' ')
		err |= test_ConvertGeneric(1,'microns','m',1e-6)
		err |= test_ConvertGeneric(1,'meters','m', 1)
		return err


	def test_AreaUnits():
		err = False
		err |= test_ConvertGeneric(1,'squareinch','m^2')
		err |= test_ConvertGeneric(1,'square_inch','SI')
		err |= test_ConvertGeneric(1,'square-meter','SI')

		err |= test_ConvertGeneric(1,'barn','m^2')
		err |= test_ConvertGeneric(1,'ha','SI')
		err |= test_ConvertGeneric(1,'ha','m^2')
		err |= test_ConvertGeneric(1,'m^2','cm^2')
		err |= test_ConvertGeneric(1,'pm^2','nm^2')

		print ('\n    check all spellings')
		testAreas = ['acre', 'ha', 'are', 'hectare', 'barn', 'hectad','myriad','tetrad', \
			'section', 'survey-township', 'surveytownship','township', 'ngan', 'cent']
		for tA in testAreas: err |= test_ConvertGeneric(1,tA,'SI')

		print (' ')
		testAreas = ['squareinch','in^2', 'sqinch', 'inch^2', 'sqin', 'squaremil','mil^2', 'sqmil', \
			'squarekm', 'km^2', 'squaremetre', 'sqmetre', 'squaremeter', 'sqmeter', 'sqm', 'sqmm', \
			'squareyard','yard^2', 'sqyard','yd^2', 'squaremile', 'sqmile', 'sqmi']
		for tA in testAreas: err |= test_ConvertGeneric(1,tA,'SI')
		return err


	def test_VolumeUnits():
		err = False
		err |= test_ConvertGeneric(1,'liter','m^3')
		err |= test_ConvertGeneric(1,'pm^2','nm^2')

		print (' ')
		err = False
		inOut = [ ('stere','m^3'), ('cubic meters','m^3'),('liter','m^3'), ('liter','m^3'), ('litre','m^3'), ('l','m^3'), ('cc','m^3'), 
			('pint','m^3'), ('USpint','m^3'), ('ImperialPint','m^3'), ('gal','m^3'), ('gallon','m^3'), ('qt','m^3'), ('quart','m^3'), 
			('ImperialQuart','m^3'), ('impqt','m^3'), ('gill','m^3'), ('gil','m^3'), ('Imperialgill','m^3'), ('impgil','m^3'), ('peck','m^3'), 
			('bushel','m^3'), ('bu','m^3'), ('cup','m^3'), ('tablespoon','m^3'), ('Tbsp','m^3'), ('tbsp','m^3'), ('barrel','gal'),  
			('teaspoon','m^3'), ('tsp','m^3'), ('tspn','m^3'), ('dram','m^3'), ('minim','m^3'), ('cord','m^3'), 
			('acre foot','m^3'), ('acre foot','m^3'), ('acre*foot','m^3'), ('board foot','m^3'), ('FBM','m^3'), ('BDFT','m^3'), ('BF','m^3')]
		for uin,out in inOut:	err |= test_ConvertGeneric(1,uin,out)
		print ('  ')

		print ('\n    check all spellings')
		testVolumes = ['liter', 'litre', 'pint', 'ImperialPint', 'ImperialPint', 'gal', 'gallon', 'qt', 'quart', 'ImperialQuart', 'impqt', 'gill', 'gil', 'Imperialgill', 'impgil', 'peck', 
			'bushel', 'bu', 'cup', 'tablespoon', 'Tbsp', 'tbsp', 'teaspoon', 'tsp', 'tspn', 'dram', 'minim', 'cord', 'acrefoot', 'acrefoot', 'board foot', 'FBM', 'BDFT', 'BF', 
			'Imperial peck','Imppeck','Imppeck', 'Imperial bushel','Impbushel','Impbushel', 'Imperial bu','Impbu','Impbu', 'barrel of oil','barrel', 'bbl', 
			'Imperial gill','Impgill','Impgill', 'Imperial gil','Impgil','Impgil', 'Imperial gallon','Impgallon','Impgallon',
			'Imperial gal','Impgal','Impgal', 'Imperial quart','Impquart','Impquart', 'Imperial qt','Impqt','Impqt', 'Imperial pint','Imppint','Imppint', 
			'Imperial cup','Impcup','Impcup', 'Imperial dram','Impdram','Impdram', 'Imperial minim','Impminim','Impminim' ]
		for tl in testVolumes: err |= test_ConvertGeneric(1,tl,'m^3')
		print ('\n\t*** Check cubic-length type volumes ***')
		testVolumes = ['cubic cm', 'cubic centimeter', 'cubic m', 'cubic m', 'cubic mm', 'cubicmm', 'cubic-mm', 'cubic yd', 'cubic mi', 'cubicmi', 'cubic-mi', 'cubic furlong', 'cubic-furlong', 'cubicfurlong', 
			'cubicparsec', 'cubic-parsec', 'cubic parsec', 'cubicLi', 'cubic Li', 'cubic-Li', 'cubic Xu', 'cubic rod', 'cubic a0', 'cubic ao']
		for tl in testVolumes: err |= test_ConvertGeneric(1,tl,'m^3')
		return err


	def test_Qunits():
		err = False
		err |= test_ConvertGeneric(1.5,'Angstrom^-1', 'nm^-1', 15)
		err |= test_ConvertGeneric(1.5,u'Å^-1', 'nm^-1', 15)
		err |= test_ConvertGeneric(15,'nm^-1', u'Å^-1', 1.5)
		err |= test_ConvertGeneric(1.5,u'Å^-1', 'pm^-1', 0.015)
		err |= test_ConvertGeneric(1.5,u'Å^-1', 'cm^-1', 1.5e8)
		err |= test_ConvertGeneric(1.5,u'Å^-1', 'ypc^-1')
		err |= test_ConvertGeneric(1.5,u'Å^-1', '1/nm')
		print (' ')
		err |= test_ConvertGeneric(1,u'wavenumber','SI')
		err |= test_ConvertGeneric(2,u'wavenumber','1/cm')
		err |= test_ConvertGeneric(3,'1/cm',u'wavenumber')
		err |= test_ConvertGeneric(4,'cm^-1','wavenumber')
		err |= test_ConvertGeneric(3,'1/(cm^1)',u'wavenumber')
		print (' ')
		err |= test_ConvertGeneric(3,'Rydberg',u'SI')
		err |= test_ConvertGeneric(3,'Ry',u'SI')
		err |= test_ConvertGeneric(3,'Rinf',u'SI')
		err |= test_ConvertGeneric(3,u'R\u221e',u'SI')
		print (' ')
		err |= test_ConvertGeneric(1,u'inverse-m','SI')
		err |= test_ConvertGeneric(1,u'Inverse m','SI')
		return err


	def test_AngleUnits():
		err = False
		for ch in [u'°','deg','degree','degree','rad','grad','arc min','arc sec','arcmin','arcsec','"',"''","'",'mcos','Cosine']:
			err |= test_ConvertGeneric(0.5,ch,'degree')

		print (' ')
		for ch in [u'°','deg','degree','degree','rad','grad',"'",'"',"''",'mcos','Cosine']:
			err |= test_ConvertGeneric(2,'degree',ch)

		print (' ')
		err |= test_ConvertGeneric(0.0005,'cos','degree', 89.9713521090498)
		err |= test_ConvertGeneric(0.5,'mcos','degree', 89.9713521090498)

		print (' ')
		err |= test_ConvertGeneric(0.01,'deg','cos')
		acos89 = 0.017452406437283376
		err |= test_ConvertGeneric(89.,'deg','cos',acos89, tol=1e-13)
		err |= test_ConvertGeneric(89.,'deg','mcos',acos89*1000, tol=1e-13)
		err |= test_ConvertGeneric(89.,'deg','Cosine',acos89, tol=1e-13)
		print (' ')
		err |= test_ConvertGeneric(.05,'cos','deg')
		err |= test_ConvertGeneric(50,'mcos','deg')
		err |= test_ConvertGeneric(0.01,u'mCosine',u'mdegree')
		err |= test_ConvertGeneric(89999.42704220486,u'mdegree',u'Cosine',1e-5, tol=1e-11)
		err |= test_ConvertGeneric(89999.42704220486,u'mdegree',u'mCosine',0.01, tol=1e-11)
		print (' ')
		err |= test_ConvertGeneric(180.,'','rad', explanation='no input unit')			# no unitIN, empty
		err |= test_ConvertGeneric(180.,'rad','', explanation='no output unit')			# no unitOUT, empty
		err |= test_ConvertGeneric(0.05,'s','deg', explanation='"s" is not an angular unit')
		return err


	def test_TimeUnits():
		testTimes = ['second','sec','s','minute','min','hour','hr','day','week','wk','fortnight','lunarmonth','lunar','lune','moon',\
			'year','yr','olympiad','lustrum','indiction','decade','century','millennium','jiffy','shake','beat','Plancktime',\
			'Svedberg','galactic year','sidereal day','sidereal year','helek','pahar']
		for ch in testTimes:	test_ConvertGeneric(1,ch,'sec')
		print (' ')
		err = test_ConvertGeneric(1,'min','sec', 60)
		err |= test_ConvertGeneric(1,'hour','minute', 60)
		err |= test_ConvertGeneric(1,'hour','sec', 3600)
		err |= test_ConvertGeneric(1,'day','sec', 24*3600)
		err |= test_ConvertGeneric(1,'day','hour', 24)
		err |= test_ConvertGeneric(1,'week','day', 7)
		err |= test_ConvertGeneric(1,'fortnight','day', 14)
		err |= test_ConvertGeneric(1,'lune','day', 29.530588)
		err |= test_ConvertGeneric(1,'year','day', tropicalYear/(24.0*3600.0))
		err |= test_ConvertGeneric(1,'olympiad','year', 4)
		err |= test_ConvertGeneric(1,'lustrum','year', 5)
		err |= test_ConvertGeneric(1,'indiction','year', 15)
		err |= test_ConvertGeneric(1,'decade','year', 10)
		err |= test_ConvertGeneric(1,'century','year', 100)
		err |= test_ConvertGeneric(1,'millennium','year', 1000)
		err |= test_ConvertGeneric(1,'beat','sec', 3.6)
		err |= test_ConvertGeneric(1,'Svedberg','sec', 1e-13)
		err |= test_ConvertGeneric(1,'sidereal-day','hour', 23.9344699)
		err |= test_ConvertGeneric(1,'sidereal-year','day', 365.256363004)
		err |= test_ConvertGeneric(1,'helek','sec', 10./3.)
		err |= test_ConvertGeneric(1,'pahar','hour', 3)
		err |= test_ConvertGeneric(1,'galactic-year','year', 230e6)
		err |= test_ConvertGeneric(1,'shake','sec', 1e-8)

		print (' ')
		for ch in ['wk','WK','mwk','Mwk']:	err |= test_ConvertGeneric(1,ch,'day')
		for ch in ['hr','hhr','dhr']:		err |= test_ConvertGeneric(1,ch,'min')
		err |= test_ConvertGeneric(1,'Es','sec')
		err |= test_ConvertGeneric(1,'s','sec')

		for ch in ['day^1/2',u'µday^1/2.']:
			err |= test_ConvertGeneric(1,ch,'sec^1/2')

		print (' ')
		err |= test_ConvertGeneric(1,'abc','sec', explanation='not a valid time unit')
		err |= test_ConvertGeneric(1,'','sec', explanation='input units not provided')
		err |= test_ConvertGeneric(1,'sec','', explanation='output units not provided')
		err |= test_ConvertGeneric(1,'mxx','sec', explanation='not a valid time unit')
		err |= test_ConvertGeneric(1,'xs','sec', explanation='not a valid time unit')
		err |= test_ConvertGeneric(1,'xx','sec', explanation='not a valid time unit')
		return err


	def test_MassUnits():
		testMasses = ['kg','g','carat','ct','gr','grain','firkin','fir','#','lb','lbm','pound','oz','ounce','slug','st','stone', 
			'tonne','metric-ton','t.short','short-ton','ton','t.long','long-ton','troy-pound','tlb','troy-ounce','toz','amu','Dalton', 
			'mP','Planck-Mass','sun','sol','solar-mass','mass of sun','earth-mass','mass of earth','earth',
			'me','mass-of-electron','mp','proton','mn','neutron','mmu','muon']
		err = False
		for ch in testMasses:	err |= test_ConvertGeneric(1,ch,'kg')

		print (' ')
		err |= test_ConvertGeneric(1,'troy-pound','kg', 0.3732417216)
		err |= test_ConvertGeneric(1,'Troy-pound','kg', 0.3732417216)
		err |= test_ConvertGeneric(1,'troy pound','kg', 0.3732417216)
		err |= test_ConvertGeneric(1,'Troy pound','kg', 0.3732417216)
		err |= test_ConvertGeneric(1,'troypound','kg', 0.3732417216)
		err |= test_ConvertGeneric(1,'Troypound','kg', 0.3732417216)

		err |= test_ConvertGeneric(1,'troy-ounce','kg', 0.3732417216/12)
		err |= test_ConvertGeneric(1,'Troy-ounce','kg', 0.3732417216/12)
		err |= test_ConvertGeneric(1,'troy ounce','kg', 0.3732417216/12)
		err |= test_ConvertGeneric(1,'Troy ounce','kg', 0.3732417216/12)
		err |= test_ConvertGeneric(1,'Troyounce','kg', 0.3732417216/12)
		err |= test_ConvertGeneric(1,'troyounce','kg', 0.3732417216/12)
		err |= test_ConvertGeneric(1,'metric-ton','kg', 1000)
		err |= test_ConvertGeneric(1,'solar-mass','kg', 1.9891e+30)
		err |= test_ConvertGeneric(1,'solar-masses','kg', 1.9891e+30)
		err |= test_ConvertGeneric(1,'Mass_of_sun','kg', 1.9891e+30)
		err |= test_ConvertGeneric(1,'Mass of SUN','kg', 1.9891e+30)
		err |= test_ConvertGeneric(1,'Mass of EARTH','kg', mEarth)
		err |= test_ConvertGeneric(1,'mass_of_electron','kg', 9.10938356e-31)
		err |= test_ConvertGeneric(1,'electron_mass','kg', 9.10938356e-31)
		err |= test_ConvertGeneric(1,'Planck_mass','kg', 2.1764701954906432e-08)
		err |= test_ConvertGeneric(1,'PlanckMass','kg', 2.1764701954906432e-08)

		print (' ')
		err |= test_ConvertGeneric(1,'mass-of_sun','kg', explanation='badly formed name')
		err |= test_ConvertGeneric(1,'abc','kg', explanation='not a valid mass unit')
		err |= test_ConvertGeneric(1,'','kg', explanation='no input mass unit given')
		err |= test_ConvertGeneric(1,'xx','kg', explanation='not a valid mass unit')
		err |= test_ConvertGeneric(1,'mxx','kg', explanation='not a valid mass unit')
		err |= test_ConvertGeneric(1,'xs','kg', explanation='not a valid mass unit')
		err |= test_ConvertGeneric(1,'','kg', explanation='no input mass unit given')
		err |= test_ConvertGeneric(1,'xx','kg', explanation='not a valid mass unit')
		return err


	def test_TemperatureUnits():
		err = test_ConvertGeneric(1,u'°C','Celsius', 1)
		err |= test_ConvertGeneric(1,'K','Kelvin', 1)
		err |= test_ConvertGeneric(1,'F','Fahrenheit', 1, tol=1e-13)
		err |= test_ConvertGeneric(1,u'°R','Rankine', 1)
		err |= test_ConvertGeneric(1,u'°R','Kelvin', 1.8)
		err |= test_ConvertGeneric(1,u'°F','Fahrenheit')
		print (' ')
		err |= test_ConvertGeneric(0,'Kelvin',u'°C')
		err |= test_ConvertGeneric(0,'Celsius','K')
		err |= test_ConvertGeneric(0,'Centigrade','K')
		err |= test_ConvertGeneric(273.15,'K','Celsius', 0)
		err |= test_ConvertGeneric(272.15,'K','Celsius', -1)
		err |= test_ConvertGeneric(300,'K','F', -1)
		err |= test_ConvertGeneric(98.6,'F','Celsius', 37)
		err |= test_ConvertGeneric(1,'K','Planck-Temperature')
		err |= test_ConvertGeneric(1,'K','Planck_Temperature')
		err |= test_ConvertGeneric(1,'K','PlanckTemperature')
		err |= test_ConvertGeneric(1,'K','TPlanck')
		err |= test_ConvertGeneric(1,'K','TP')
		print (' ')
		err |= test_ConvertGeneric(300,'K*kB','eV')
		err |= test_ConvertGeneric(1,'(1/40) (eV/kB)','F')
		err |= test_ConvertGeneric(300,'K','eV', transform=True)
		err |= test_ConvertGeneric(300,'K','kB K', transform=True)
		err |= test_ConvertGeneric(300,'K','kB °C', transform=True)
		err |= test_ConvertGeneric(300,'K','J', transform=True)
		err |= test_ConvertGeneric(300,'K','kB*K', transform=True)
		err |= test_ConvertGeneric(300,'K','meV', transform=True)
		err |= test_ConvertGeneric(3e5,'mK','meV', transform=True)
		err |= test_ConvertGeneric(300,'K','(eV)', transform=True)
		err |= test_ConvertGeneric(300,'K','(meV)', transform=True)
		err |= test_ConvertGeneric(300,'kB*K','meV')
		print (' ')
		err |= test_ConvertGeneric(32,'F',u'°C', 0)
		err |= test_ConvertGeneric(-40,'F','Celsius', -40)
		err |= test_ConvertGeneric(-40,'Celsius','F', -40)
		err |= test_ConvertGeneric(0,'Celsius','F', 32)
		print (' ')
		err |= test_ConvertGeneric(1,'Kelvin','K', 1)
		err |= test_ConvertGeneric(1,'Kelvin','Celsius', -272.15)
		print (' ')
		print ('     milli')
		err |= test_ConvertGeneric(1,'milliK','K', 0.001)
		err |= test_ConvertGeneric(1,'mK','K', 0.001)
		err |= test_ConvertGeneric(1,'K','mK', 1000)
		print (' ')
		err |= test_ConvertGeneric(1,u'°F','fahrenheit',explanation='fahrenheit invalid, must use Fahrenheit')
		err |= test_ConvertGeneric(300,'K','kT(eV)',explanation='"kT" or "eV" is OK, but not "kT(eV)"')
		err |= test_ConvertGeneric(-40,'c','F', -40,explanation='C is case sensitive')
		err |= test_ConvertGeneric(1,'F','fahrenheit', 1, tol=1e-13, explanation='Fahrenheit is case sensitive')
		err |= test_ConvertGeneric(1,'R','RANKINE', 1, explanation='Rankine is case sensitive')
		return err


	def test_EnergyUnits():
		err = False
		ftlb = 1.3558179483314003			#  = (0.0254*12) * (0.45359237*9.80665)
		testEnergies = [('J',1), ('Joule',1), ('erg',1e-7), ('cal',4.184), ('calorie',4.184), ('BTU',1055.06), 
			('kWh',3.6e6), ('kilowattHour',3.6e6), ('eV',1.6021766208e-19), ('electron-volt',1.6021766208e-19), 
			('Rinf_hc',2.179872325e-18), ('Ry_hc',2.179872325e-18), ('Rydberg_hc',2.179872325e-18), (u'R\u221e_hc',2.179872325e-18), ('Ha',4.35974465e-18), ('Hartree',4.35974465e-18), 
			('ftlb',ftlb), ('ft_lbf',ftlb), ('foot_pound',ftlb), 
			('Wyr',31.556925216e6), ('wattyear',31.556925216e6), ('TWyr',31.556925216e18), ('terawattyear',31.556925216e18), 
			('therm',1055.06e5), ('quad',1055.06e15), ('MgTNT',4.184e9), ('gTNT',4.184), ('ton_of_TNT',4.184e9), 
			('Planck_Energy',1956113859.5635495), ('foe',1e44), ('Bethe',1e44)]
		for (unit,expected) in testEnergies:	err |= test_ConvertGeneric(1,unit,'J',expected)

		print (' ')
		err |= test_ConvertGeneric(1,'ton_of_TNT','J')
		err |= test_ConvertGeneric(1,'tonTNT','J')
		err |= test_ConvertGeneric(1,'ton-of-TNT','J')
		err |= test_ConvertGeneric(1,'k_ton_of_TNT','J')
		err |= test_ConvertGeneric(1,'ktonTNT','J')
		err |= test_ConvertGeneric(1,'kiloton','J')
		err |= test_ConvertGeneric(1,'PetaJ','J',expected=1e15)
		err |= test_ConvertGeneric(1,'PetaKWh','J',expected=3.6e21)

		print (' ')
		err |= test_ConvertGeneric(1,'abc','J', explanation='not a valid energy unit')
		err |= test_ConvertGeneric(1,'m','J', explanation='not a valid energy unit')
		err |= test_ConvertGeneric(1,'s','J', explanation='not a valid energy unit')
		err |= test_ConvertGeneric(1,'xx','J', explanation='not a valid energy unit')
		err |= test_ConvertGeneric(1,'mxx','J', explanation='not a valid energy unit')
		err |= test_ConvertGeneric(1,'xs','J', explanation='not a valid energy unit')
		return err


	def test_PowerUnits():
		testPowers = [('W',1), ('Watt',1), (u'horse power',HP), (u'horse_power',HP), (u'horsepower',HP), (u'hp',HP),(u'HP',HP)]
		err = False
		for (unit,expected) in testPowers:	err |= test_ConvertGeneric(1,unit,'W',expected)
		print (' ')
		err |= test_ConvertGeneric(1,'BTU/hr','W')
		err |= test_ConvertGeneric(1,'BTU/s','W')
		return err


	def test_PressurUnits():
		err = False
		testPressures = ['Pascal','Pa','bar','atmosphere','atmospheres','atm','Torricelli','mmHg','Torr','inches of Water','inches of H2O','inH2O','psi']
		for tp in testPressures: err |= test_ConvertGeneric(1,tp,'Pa')

		testPressures = [('Pascal',1), ('bar',1e5), (u'atm',101325), (u'atmosphere',101325), ('Torr',101325.0/760.0), ('mmHg',101325.0/760.0), ('inH2O',249.08891),('psi',6894.757293168361)]
		for (unit,expected) in testPressures:	err |= test_ConvertGeneric(1,unit,'Pa',expected)
		return err


	def test_VelocityUnits():
		testVelocity = [('mps',1), ('fps',foot), (u'feet per second',foot), (u'foot per second',foot), (u'foot-per-second',foot), 
			(u'mph',mile/3600), (u'mi per hr',mile/3600), (u'miles per hour',mile/3600), (u'miles-per-hour',mile/3600), (u'miles per sec',mile), 
			('fathom/sec',6*foot), ('fathom per sec', 6*foot), (u'speed of light',299792458), ('c',299792458)]
		err = False
		for (unit,expected) in testVelocity:	err |= test_ConvertGeneric(1,unit,'m/s',expected)
		print (' ')
		err |= test_ConvertGeneric(1,'speed of light','m/s',expected=299792458)
		err |= test_ConvertGeneric(1,'speedlight','m/s')
		err |= test_ConvertGeneric(1,'speed light','m/s',explanation='either "speed of light", or "speedlight", NOT "speed light"')
		err |= test_ConvertGeneric(1,'Speed of Light','m/s',explanation='capitalization is strict, "speed of light", not "Speed of Light"')
		return err


	def test_ForceUnits():
		testForces = [('N',1), ('Newton',1), ('kg m/s^2',1), (u'dyne',1e-5), (u'dyn',1e-5), (u'kgf',gStd), (u'kilogramforce',gStd), 
			('kip',1000*kgPerPound*gStd), ('poundforce',kgPerPound*gStd), (u'lbf',kgPerPound*gStd), 
			(u'poundal', 0.138254954376), (u'pdl', 0.138254954376) ]
		err = False
		for (unit,expected) in testForces:	err |= test_ConvertGeneric(1,unit,'N',expected)
		return err


	def test_LightUnits():
		#	https://en.wikipedia.org/wiki/Candela#Relationships_between_luminous_intensity,_luminous_flux,_and_illuminance
		fc = foot**-2
		err = False
		testLuminous = [ ('Candela',1), ('candela',1), ('cd',1) ]
		for (unit,expected) in testLuminous:	err |= test_ConvertGeneric(1,unit,'cd',expected)
		print (' ')
		testLightFlux = [ ('lumen',1), ('lm',1) ]
		for (unit,expected) in testLightFlux:	err |= test_ConvertGeneric(1,unit,'lumen',expected)
		print (' ')
		testLuminance = [ ('ftc',fc), ('footcandle',fc), ('footcandles',fc), ('Footcandle',fc), ('Footcandles',fc), ('lumen/foot^2',fc), 
			('lx',1), ('lux',1), ('Lux',1), ('lumen/m^2',1), ('ph',1e4), ('phot',1e4), ('Phot',1e4), ('lumen/cm^2',1e4) ]
		for (unit,expected) in testLuminance:	err |= test_ConvertGeneric(1,unit,'Lux',expected)
		return err


	def test_Quantity():
		testQuantity = [ ('mole',1), ('mol',1), ('NA',1), ('Avogadros-Number',1), ('Avogadro-Number',1), ('Avogadro Number',1), ('atom',1/NA), ('molecule',1/NA) ]
		err = False
		for (unit,expected) in testQuantity:	err |= test_ConvertGeneric(1,unit,'mole',expected)
		err |= test_ConvertGeneric(1,'1e23 atoms','mole',1/6.022140857)
		err |= test_ConvertGeneric(1.0e23,'atoms','mole',1/6.022140857)
		return err


	def test_Miscelaneous():
		err = False
		testMisc = [ ('one',1) , ('pi',math.pi), (u'π',math.pi), ('e',math.e)]
		for (unit,expected) in testMisc:	err |= test_ConvertGeneric(1,unit,'one',expected)

		print (' ')
		testMisc = [ (u'ℏ',1.0545718e-34), ('h',6.626070040e-34), (u'ϵ0',8.854187817e-12), ('gN',gStd), ('kB',kB), ('kB',1.38064852e-23), ('Gravity',6.67408e-11), ('BigG',6.67408e-11), (u'µ0',12.566370614e-7), (u'µB',927.4009994e-26), (u'φ0',2.067833831e-15), (u'σ',sigma) ]
		for (unit,expected) in testMisc:	err |= test_ConvertGeneric(1,unit,'SI',expected, tol=1e-8)

		print (' ')
		def check_find(ss):
			uu = UnitsJZTdefault.find(ss)
			print (u'    ',unicode(ss),u' 	is  ',unicode(uu),uu.dimType)
		flist = ['one', 'pi', 'e', 'hbar', 'h', u'\u210F', u'ℏ', 'eps0', u'\u03B50', u'\u03F50', u'ϵ0', 'gN', 'kB', 'Gravity', 'mu0', u'µ0', 'muB', u'µB', u'phi0', u'Phi0', u'\u03d50', u'\u03C60', u'φ0', u'\u03c3', u'sigma']
		for ss in flist: check_find(ss)

		print (' ')
		testMisc = [ (u'Gray',1) ,(u'Gy',1), (u'Rad',0.01),(u'R',0.01) ]
		for (unit,expected) in testMisc:	err |= test_ConvertGeneric(1,unit,'J/kg',expected)
		#	MiscUnits.append( OneUnitDefine((u'Roentgen',u'R'), [0,0,-1,1,1,0,0,0], 'x-ray exposure', 2.58E-4, strict=True, desc='258 µCoulomb/kg') )
		print (' ')
		err |= test_ConvertGeneric(1,'kpl','1/m^2',1e6)
		err |= test_ConvertGeneric(1,'km/l','1/m^2',1e6)
		err |= test_ConvertGeneric(1,'mpg','1/m^2',mile/(8*USpint))
		print (' ')
		err |= test_ConvertGeneric(1,'Jansky','Watt/(m^2 * Hz)',1e-26)
		err |= test_ConvertGeneric(1,'Jy','Watt m^-2 Hz^-1',1e-26)
		err |= test_ConvertGeneric(1,'Jansky','W s/(m^2)',1e-26)
		err |= test_ConvertGeneric(1,'Jansky','J/m^2',1e-26)
		err |= test_ConvertGeneric(1,'Langley','J/m^2',41840)
		err |= test_ConvertGeneric(1,'Ly','J/m^2',41840)
		print (' ')
		err |= test_ConvertGeneric(1,'stoke','kg m^-1 s^-1',1e-4)
		err |= test_ConvertGeneric(1,'St','kg m^-1 s^-1',1e-4)
		err |= test_ConvertGeneric(1,'Poise','kg m^-1 s^-1',0.1)
		err |= test_ConvertGeneric(1,'Po','kg m^-1 s^-1',0.1)
		print (' ')
		err |= test_ConvertGeneric(1,'kat','mol/s',1)
		err |= test_ConvertGeneric(1,'katal','mole/s',1)
		err |= test_ConvertGeneric(1,'rayl','Pa s/m',1)
		err |= test_ConvertGeneric(1,'Rayl','Pa s/m',1)
		err |= test_ConvertGeneric(1,'Rayleigh','Pa s/m',1)
		print (' ')
		err |= test_ConvertGeneric(1,'denier','kg/m',1/9e6)
		err |= test_ConvertGeneric(1,'tex','kg/m',1e-6)
		return err


	def test_InterpretEnergy():
		def testEnergy(input, unitOut, desired, fail=False):
			energy = None
			deltaErr = False
			try:
				energy = UnitsJZTdefault.InterpretEnergy(input, unitOut)
				if energy==float(desired):	deltaErr = False
				else:						deltaErr = fractionalError(energy,desired)>1e-7
				if deltaErr: raise ValueError(u'%r should convert to %r (%s), but got %r' % (input, desired, unitOut,energy))
				try:		print (u'   ',unicode(input),)
				except:	print ('%r' % (input,),)
				try:		print  (' --> '+'%r (%s)' % (energy,unitOut))
				except:	print  (' --> '+'%r (%r)' % (energy,unitOut))
				return False
			except Exception as e:
				if fail:	pre = '    '			# no real error is fail=True
				else:		pre = '**  '			# flag as a real error
				if deltaErr:
					print (pre+'Error -- '+str(e))
				else:
					print ('%sError -- could not convert %r --> (%s)  %s' % (pre,input,unitOut,e))
				return not fail

		err = False
		err |= testEnergy(10.0, 'keV', 10)					# just energy as a number
		err |= testEnergy(10.0, 'eV', 10)
		err |= testEnergy(10, 'keV', 10)
		err |= testEnergy('10', 'keV', 10)
		err |= testEnergy(5, 'keV', 5)

		err |= testEnergy('CuKa1', 'keV', 8.04782203372)	# Emission lines
		err |= testEnergy('CuKa2', 'keV', 8.02791629828)
		err |= testEnergy('CuKa', 'keV', 8.04117584667)
		err |= testEnergy('CuKa1', 'eV', 8047.82203307)
		err |= testEnergy('MoKa1', 'keV', 17.4793775338)
		err |= testEnergy('MoKa2', 'keV', 17.374466977)
		err |= testEnergy('MoKa', 'keV', 17.4442668514)

		err |= testEnergy('10 keV', 'keV', 10)				# energy with units
		err |= testEnergy('10000 eV', 'keV', 10)
		err |= testEnergy('10 eV', 'keV', 1e-2)
		err |= testEnergy('10000 eV', 'eV', 10e3)
		err |= testEnergy([1e4, 'eV'], 'keV', 10)
		err |= testEnergy((1e4, 'eV'), 'keV', 10)
		err |= testEnergy((0.1, 'keV'), 'eV', 100)
		err |= testEnergy((100, 'eV'), 'eV', 100)
		err |= testEnergy((12), 'keV', 12)
		err |= testEnergy((12, ' keV '), 'keV', 12)
		err |= testEnergy((12, ' keV ', 'abc'), 'keV', 12)

		err |= testEnergy('0.1 nm', 'keV', 12.398419739)	# wavelength with units
		err |= testEnergy('1 Å', 'keV', 12.398419739)
		err |= testEnergy(u'1 Å', 'keV', 12.398419739)
		err |= testEnergy('1 Angstrom', 'keV', 12.398419739)
		err |= testEnergy('1e-10 m', 'keV', 12.398419739)
		err |= testEnergy('0.1 nm', 'eV', 12398.419738)
		err |= testEnergy(u'1.5 Å', 'keV', 8.265613159)

		err |= testEnergy(0, 'keV', 0)						# zero of inf energy
		err |= testEnergy('0 keV', 'keV', 0)
		err |= testEnergy('0 keV', 'eV', 0)
		err |= testEnergy(float('inf'), 'keV', float('inf'))
		err |= testEnergy(u'Inf Å', 'keV', 0)
		err |= testEnergy('Inf pc', 'keV', 0)
		err |= testEnergy('Inf keV', 'eV', float('inf'))

		err |= testEnergy('10', 'keV', 10.1, fail=True)		# ***  Intentional Errors  ***
		err |= testEnergy('10 xeV', 'keV', 10, fail=True)
		err |= testEnergy('1e-15 J', 'keV', 10, fail=True)
		err |= testEnergy('', '', 'keV', fail=True)
		err |= testEnergy('ten', 'keV', 10, fail=True)
		err |= testEnergy('10keV', 'keV', 10, fail=True)
		err |= testEnergy('{}', 'keV', '', fail=True)
		err |= testEnergy({}, 'keV', '', fail=True)
		err |= testEnergy(float('nan'), 'keV', float('nan'), fail=True)
		err |= testEnergy(-5, 'keV', -5, fail=True)
		err |= testEnergy('-5e3 eV', 'keV', -5, fail=True)
		err |= testEnergy(5, 'm', 5, fail=True)
		err |= testEnergy(5, u'Å', 5, fail=True)

		print (' ')
		print ('		****** Now the same tests, but using direct calls, bypassing InterpretEnergy() ******')
		print (' ')
		test_transformUnit()
		return err


	def test_OneUnit():
		radian = OneUnitDefine((u'radian',u'rad'), [1,0,0,0,0,0,0,0], 'angle', 1.0, desc='SI base unit')
		chain = OneUnitDefine(u'chain', [0,1,0,0,0,0,0,0], 'length', 66*foot, desc='66 feet, surveying')
		barn = OneUnitDefine(u'barn', [0,2,0,0,0,0,0,0], 'area', 1e-28, desc='barn = 1e-28 m^2')
		Fahrenheit = OneUnitDefine((u'Fahrenheit',u'F'), [0,0,0,0,0,1,0,0], 'Temperature', 1/1.8,offset=CelsiusK-32.*5./9., strict=True, desc='Kelvin = (Fahrenheit-32)/1.8 + 273.15')
		Kelvin = OneUnitDefine((u'Kelvin',u'K'), [0,0,0,0,0,1,0,0], 'Temperature', 1, desc='SI base Temperature unit [K]')

		all = allUnitsData([radian,chain])
		all.append([Fahrenheit,barn,Kelvin])
		# print 'all.crossRef =',all.crossRef
		print ('    all =',all)
		print ('    find = ',all.find('radian'))
		print ('    find = ',all.find('F'))
		print ('    find = ',all.find('kF'))
		print ('    find = ',all.find('kK'))
		print ('    find = ',all.find('mkK'))
		print ('    find = ',all.find('mmK'))
		print ('    find = ',all.find('mrad'))
		# print 'all.crossRef =',all.crossRef
		print (' ')
		uu = MakeStandardUnits()
		print ('    all =',uu)
		print ('   ',unicode(uu[0]))
		print ('   ',unicode(uu[1]))
		print ('   ',unicode(uu[2]))
		print ('   ',unicode(uu[-21]))
		print ('   ',unicode(uu[-20]))
		print ('   ',unicode(uu[-19]))
		print ('   ',unicode(uu[-18]))
		print ('   ',unicode(uu[-17]))
		print ('    find = ',uu.find('one'))
		print ('    find = ',unicode(uu.find('pi')),uu.find('pi').ustr)
		print ('    find = ',uu.find('e'))
		print ('    find = ',unicode(uu.find('alpha')),uu.find('alpha').ustr)
		print ('    find = ',unicode(uu.find('hbar')),uu.find('hbar').ustr)

		return False


	def checkPrefixConflicts(aunits):
		"""
		the only conflict is with min (time) and min (inch/1000)
		but, since it will search for 'min' before 'in' we are OK
		"""
		SIset = set(['d','c','m',u'µ','n','p','f','a','z','y',  'h','H','k','K','M','G','T','P','E','Z','Y'])
		print ("    running:  checkPrefixConflicts(), checking %d unit names, with all %d SI prefixes" % (len(aunits.crossRef),len(SIset)))
		conflicts = 0
		for name,ii,ss in aunits.crossRef:				# one of the known names,  crossRef[(name,index,strict),...]
			for otherName,ii2,ss2 in aunits.crossRef:	# loop over all other names
				if name.endswith(otherName):	# check preceeding chars to see if they are all valid prefixes
					prefixes = name[:-len(otherName)]
					sprefixes = set(prefixes)
					if sprefixes < SIset and len(sprefixes):
						oneunit = aunits.findNoPrefix(name)
						if prefixes=='k' and otherName=='g': continue	# 'k g' and 'kg' are the same
						conflicts += 1
						prefixes = expandSiprefixes(prefixes)
						if name == oneunit.namesFull[0]:
							print ('**  Conflicts between: "%s%s"  and  %s,  uses: %s' % (prefixes,otherName, name, name))
						else:
							print ('**  Conflicts between: "%s%s"  and  %s,  uses: %s (= %s)' % (prefixes,otherName, name, name, oneunit.namesFull[0]))
		print (' found %d conflicts' % (conflicts,))

		# day is never abbreviated with 'd', so 'cd' or 'yd', do not produce overlaps with 'day'
		#
		# important overlaps occur for:
		#	min		is assumed to be minute, but it could be '0.001 inch' (min is never used for arcmin)
		#	hbar	is assumed to be 'h/2*PI', but it could be '100 bar' (but hectobar or mbar is a pressure)
		#	cc		is assumed to mean 'cubic-centimer', but could be '0.01 * speed of light'
		#	pc		is assumed to mean 'parsec', but could be '1e-12 * speed of light'
		#	me		is assumed to mean 'mass of electron', but could be '0.001*e'(e is base of natural log)
		#
		#	there are also a few more complicated conflicts, e.g. mps could also be milli-pico-sec, but this assumes meter/sec
		#
		#	the reset are even more obscure. 
		#	you can see a full list by running:
		#		./JZTunits.py 2**20

		print ('\n\tcheck for plurals: (%d names), look for names ending in "s"' % (len(aunits.crossRef),))
		extraS = []
		knownPlurals = []
		for nn,ii,ss in aunits.crossRef:			# a list of (name,index,strict), only using nn here
			if nn.endswith('s') or nn.endswith('S') or nn.endswith('es'):
				if nn in pluralExclude: knownPlurals.append(nn)
				else:		 extraS.append(nn)
		print ('    units ending in "s"', extraS)
		print ('    knownPlurals =',knownPlurals)
		return False


	def test_listDimensions():
		def printUnitNames(ll):
			out = ''
			for name in ll: out += '"'+unicode(name)+'",  '
			out = out.strip().strip(', ')
			return '    '+out

		print ('	UnitsJZTdefault.listDimensions("velocity"):')
		out = UnitsJZTdefault.listDimensions('velocity')
		for name in out: print (printUnitNames(name))

		print ('\n	UnitsJZTdefault.listDimensions([0,2,0,0,0,0,0,0]):  (this is m^2 == "area")')
		out = UnitsJZTdefault.listDimensions([0,2,0,0,0,0,0,0])
		for name in out: print (printUnitNames(name))

		print ('\n	UnitsJZTdefault.listDimensions("action"):')
		out = UnitsJZTdefault.listDimensions('action')
		for name in out: print (printUnitNames(name))

		print ('\n    UnitsJZTdefault.listDimensions(None) --> ',UnitsJZTdefault.listDimensions(None))
		print ('    UnitsJZTdefault.listDimensions("") --> ',UnitsJZTdefault.listDimensions(''))
		print ('    UnitsJZTdefault.listDimensions("abc") --> ',UnitsJZTdefault.listDimensions('abc'))
		return False


	def test_processInput():
		err = False

		def test_removeDashes(ss,expected):
			stemp = UnitsJZTdefault._UnitsJZT__removeDashes(ss)
			err = not (stemp == expected)
			if err:	errStr = '**  '
			else:	errStr = '    '
			try:	print ('%sremoveDashes(%s) --> %s' % (errStr,ss, stemp))
			except:	print ('%sremoveDashes(%r) --> %r' % (errStr,ss, stemp))
			return err
		err |= test_removeDashes('abc-xyz','abcxyz')
		err |= test_removeDashes('abc - xyz','abc - xyz')
		err |= test_removeDashes(u'abc-xyz','abcxyz')
		err |= test_removeDashes(u'µ-xyz',u'µxyz')
		err |= test_removeDashes('3','3')
		err |= test_removeDashes('-3','-3')
		err |= test_removeDashes('','')
		err |= test_removeDashes('3-2','3-2')
		err |= test_removeDashes('-3-2','-3-2')
		err |= test_removeDashes('abc 1e-4','abc 1e-4')
		err |= test_removeDashes('abc-1e-4','abc-1e-4')
		err |= test_removeDashes('abc-xyz -3','abcxyz -3')
		err |= test_removeDashes('abc-xyz 2-3', 'abcxyz 2-3')
		err |= test_removeDashes('-3-abc-xyz', '-3-abcxyz')
		err |= test_removeDashes('2-3 abc-xyz 2-3', '2-3 abcxyz 2-3')
		err |= test_removeDashes(u'Å-xyz', u'Åxyz')
		err |= test_removeDashes(u'abc-Å-xyz', u'abcÅxyz')
		err |= test_removeDashes(u'°-xyz', u'°xyz')
		err |= test_removeDashes(u'abc-°-xyz', u'abc°xyz')
		err |= test_removeDashes(u'Å-xyz', u'Åxyz')
		err |= test_removeDashes(u'abc-Å-xyz', u'abcÅxyz')
		err |= test_removeDashes(u'°-xyz', u'°xyz')
		err |= test_removeDashes(u'abc-°-xyz', u'abc°xyz')
		print (' ')


		def test_Solitare(input, fail=False):
			failed = False
			try:	ppp = UnitsJZTdefault._UnitsJZT__doSolitare(input)
			except Exception as e:
				excp = e
				failed = True

			if not failed and not fail:
				try:	print ('    doSolitare("%s")  -->  "%s"' % (input,unicode(ppp)),'   --   dims=%r,  scale=%r * num -->  %r [SI]' % (ppp.dims,ppp.scale,ppp.scale*ppp.num))
				except:	print ('    doSolitare("%r")  -->  "%r"' % (input,ppp),'   --   dims=%r,  scale=%r * num -->  %r [SI]' % (ppp.dims,ppp.scale,ppp.scale*ppp.num))
				err = False
			elif failed and fail:
				print ('    doSolitare("%s") is supposed to fail, it failed with exception: "%s' % (input,e))
				err = False
			elif failed and not fail:
				print ('**  Error -- could not convert %r    %s' % (input,e))
				err = True
			elif not failed and fail:
				print ('**  doSolitare("%s")  -->  %s   but is SUPPOSED to fail' % (input,ppp),'   ',ppp.dims)
				err = True
			return err
		err |= test_Solitare('-1')
		err |= test_Solitare('3')
		err |= test_Solitare('1.3e5')
		err |= test_Solitare('ns')
		err |= test_Solitare('mg')
		err |= test_Solitare('inch')
		err |= test_Solitare('m')
		err |= test_Solitare('meter')
		err |= test_Solitare('kmeter')
		err |= test_Solitare(u'µinch')
		err |= test_Solitare(u'Å')
		err |= test_Solitare('Å')
		err |= test_Solitare(u'°')
		err |= test_Solitare('°')
		print (' ')
		err |= test_Solitare('2m', fail=True)

		print (' ')
		def test_one(input, expected):
			ppp = UnitsJZTdefault.processInput(input)
			err = not (ppp == expected)
#			print type(ppp),'  ',type(expected),'   err =',err
#			print 'ppp      = ',repr(ppp)
#			print 'expected = ',repr(expected)
			if err:	errStr = '**  '
			else:	errStr = '    '
			print ("%sprocessInput('%s')  -->  %s" % (errStr,input,unicode(ppp)),'   ',ppp.dims,'  ',ppp.dimType,'   scale=',ppp.scale,'    SI=',unicode(ppp.SI()))
			if err: print ('		expected=',expected, repr(expected),'    ',expected.SI())
			return err

		err |= test_one('2 (m)', PhQ(2,'', dims=[0,1,0,0,0,0,0,0], scale=1))
		err |= test_one('2(m)', PhQ(2,'m', dims=[0,1,0,0,0,0,0,0], scale=1))
		err |= test_one('2 m', PhQ(2,'m', dims=[0,1,0,0,0,0,0,0], scale=1))
		print (' ')
		err |= test_one('inch', PhQ(1,'inch'))
		err |= test_one('mg inch', PhQ(0.001,'g inch'))

		err |= test_one('-3/m^4', PhQ(-3,'m^-4', [0,-4,0,0,0,0,0,0], 1))
		err |= test_one('pl', PhQ(1,'pl', [0,3,0,0,0,0,0,0], scale=1e-15))
		err |= test_one('pl', PhQ(1e-15,'m^3', [0,3,0,0,0,0,0,0], scale=1))
		err |= test_one('pl', PhQ(1e-12,'l', [0,3,0,0,0,0,0,0], scale=0.001))
		err |= test_one('-3/m^4 pl', PhQ(-3,'m^-1', [0,-1,0,0,0,0,0,0], scale=1e-15))
		err |= test_one('cc', PhQ(1,'m^3', [0,3,0,0,0,0,0,0], scale=1e-6))
		err |= test_one('cc/s', PhQ(1,'m^3', [0,3,0,-1,0,0,0,0], scale=1e-6))
		err |= test_one('N', PhQ(1,'', [0,1,1,-2,0,0,0,0], scale=1))
		err |= test_one('3 N', PhQ(3,'kg m/s^-2', [0,1,1,-2,0,0,0,0], scale=1))
		err |= test_one('mN', PhQ(1,'mN', [0,1,1,-2,0,0,0,0], scale=0.001))
		err |= test_one('cN', PhQ(1,'mN', [0,1,1,-2,0,0,0,0], scale=0.01))
		err |= test_one('cN', PhQ(0.01,'N', [0,1,1,-2,0,0,0,0], scale=1))
		err |= test_one('(cm)(kg)', PhQ(1,'', [0,1,1,0,0,0,0,0], scale=0.01))
		err |= test_one('(cm)(kg)', PhQ(0.01,'m kg', [0,1,1,0,0,0,0,0], scale=1))
		err |= test_one('((cm)(kg))', PhQ(0.01,'m kg', [0,1,1,0,0,0,0,0], scale=1))
		err |= test_one('cm^2', PhQ(1,'m^2', [0,2,0,0,0,0,0,0], scale=1e-4))
		err |= test_one('(kg)/(cm)', PhQ(100,'kg/m', [0,-1,1,0,0,0,0,0], scale=1))
		err |= test_one('((kg)/(cm^2))', PhQ(1e4,'kg m^-2', [0,-2,1,0,0,0,0,0], scale=1,))
		err |= test_one('((kg)(cm)^-2)',PhQ(1e4,'kg m^-2', [0,-2,1,0,0,0,0,0], scale=1,))
		err |= test_one('((kg)/(cm)^2)', PhQ(1e4,'kg m^-2', [0,-2,1,0,0,0,0,0], scale=1,))
		err |= test_one('(cm^2)^2', PhQ(1e-8,'m^4', [0,4,0,0,0,0,0,0], scale=1))
		err |= test_one('1/(cm^2)', PhQ(1e4,'m^-2', [0,-2,0,0,0,0,0,0], scale=1))

		err |= test_one('[3/((cm)(kg))]^2', PhQ(9e4,'m^-2 kg^-2', [0,-2,-2,0,0,0,0,0], scale=1))
		err |= test_one('{3/((cm)(kg))}^2', PhQ(9e4,'m^-2 kg^-2', [0,-2,-2,0,0,0,0,0], scale=1))

		print (' ')
		err |= test_one('3/m s', PhQ(3,'m^-1 s', [0,-1,0,1,0,0,0,0], scale=1))
		err |= test_one('3/(m s)', PhQ(3,'m^-1 s^-1', [0,-1,0,-1,0,0,0,0], scale=1))
		err |= test_one('kg m', PhQ(1,'kg m', [0,1,1,0,0,0,0,0], scale=1))

		print ('\n	more parsing tests:')
		err |= test_one('kg m s', PhQ(1,'', [0,1,1,1,0,0,0,0], scale=1))
		err |= test_one('kg m^2', PhQ(1,'', [0,2,1,0,0,0,0,0], scale=1))
		err |= test_one('4 kg m^2', PhQ(4,'', [0,2,1,0,0,0,0,0], scale=1))
		err |= test_one('4 kg m^2 s', PhQ(4,'', [0,2,1,1,0,0,0,0], scale=1))
		err |= test_one('4 kg m^(2*3) s', PhQ(4,'', [0,6,1,1,0,0,0,0], scale=1))
		err |= test_one('4*kg*m^2*s', PhQ(4,'', [0,2,1,1,0,0,0,0], scale=1))

		print (' ')
		err |= test_one('g', PhQ(1e-3,'kg', [0,0,1,0,0,0,0,0], scale=1))
		err |= test_one('mg', PhQ(1e-6,'', [0,0,1,0,0,0,0,0], scale=1))
		err |= test_one('mg', PhQ(1,'mg', [0,0,1,0,0,0,0,0], scale=1e-6))
		err |= test_one('mg', PhQ(1,'mg', [0,0,1,0,0,0,0,0]))
		err |= test_one('mg', PhQ(1,'mg'))
		err |= test_one('m s', PhQ(1,'m s', [0,1,0,1,0,0,0,0], scale=1))
		err |= test_one('cm', PhQ(1,'cm', [0,1,0,0,0,0,0,0]))
		err |= test_one('mg kg mm*ps^-2 C inch 1/m/mK^2', PhQ(2.54e+19,'m kg^2 s^-1 A K^-2', [0,1,2,-1,1,-2,0,0]))
		print (' ')
		err |= test_one('((cm))', PhQ(0.01,'m', [0,1,0,0,0,0,0,0], scale=1))
		err |= test_one('(3/((cm)(kg)))^2', PhQ(9,'cm^-2 kg^-2', [0,-2,-2,0,0,0,0,0], scale=1e4))
		err |= test_one('m/s', PhQ(1,'', [0,1,0,-1,0,0,0,0], scale=1))
		err |= test_one('3 kg m^2)', PhQ(3,'', [0,2,1,0,0,0,0,0], scale=1))
		err |= test_one('3 kg m^(1/2)', PhQ(3,'', [0,0.5,1,0,0,0,0,0], scale=1))
		err |= test_one('3 kg m^(-1/2)', PhQ(3,'', [0,-0.5,1,0,0,0,0,0], scale=1))
		err |= test_one('kg s^-2', PhQ(1,'', [0,0,1,-2,0,0,0,0], scale=1))
		err |= test_one('kg/s^-2', PhQ(1,'', [0,0,1,2,0,0,0,0], scale=1))
		err |= test_one('Watt/(m^2 Hz)', PhQ(1,'', [0,0,1,-2,0,0,0,0], scale=1))
		err |= test_one('Watt m^-2 Hz^-1', PhQ(1,'', [0,0,1,-2,0,0,0,0], scale=1))

		err |= test_one('kg/(m s)', PhQ(1,'', [0,-1,1,-1,0,0,0,0], scale=1))
		err |= test_one('kg/(s m)', PhQ(1,'', [0,-1,1,-1,0,0,0,0], scale=1))
		err |= test_one('F', PhQ(1,'F', [0,0,0,0,0,1,0,0], scale=1.0/1.8, offset=(CelsiusK-32.*5./9.)))
		print ('\n	check parsing equations again:')
		err |= test_one('(m s) (m s)', PhQ(1,'', [0,2,0,2,0,0,0,0], scale=1))
		err |= test_one('1/(m s)', PhQ(1,'', [0,-1,0,-1,0,0,0,0], scale=1))
		err |= test_one('(m s)^-1', PhQ(1,'', [0,-1,0,-1,0,0,0,0], scale=1))

		print ('\n\n\n	check PhQ operations:')
		one = PhQ(1,'pure number')
		print ('    one = ',one,'		',repr(one))
		if one != 1:
			print ('**  Error -- Does not match expected value')
			err = True

		a = PhQ(9,'N m')
		a.desc = 'my energy'
		print ('    a =',a,'		',repr(a))
		if a != PhQ(9,'N m'):
			print ('**  Error -- Does not match expected value')
			err = True

		print (' ')
		print ('    2*a =',2*a)
		if 2*a != PhQ(18,'N m'):
			print ('**  Error -- Does not match expected value')
			err = True
		print ('    a*3 =',a*3)
		if 3*a != PhQ(27,'N m'):
			print ('**  Error -- Does not match expected value')
			err = True

		print (' ')
		c = (a*2)**2
		print ('    a =',a,'    18**2=',18**2)
		print ('    (a*2)**2 =',c)
		if c != PhQ(324,'N^2 m^2'):
			print ('**  Error -- Does not match expected value')
			err = True

		print (' ')
		d = a**0.5
		print ('    a = ',a)
		print ('    a**0.5 =',d)
		if d != PhQ(3,'N^0.5 m^0.5'):
			print ('**  Error -- Does not match expected value')
			err = True

		print (' ')
		print ('    a = ',a)
		d = (9*a)**0.5
		print ('    (9*a)**0.5 =',d)
		if d != PhQ(9,'N^0.5 m^0.5'):
			print ('**  Error -- Does not match expected value')
			err = True

		print ('\n	test unary, -a and +a')
		print ('    a =',a)
		print ('    -a = ',-a)
		if -a != PhQ(-9,'N m'):
			print ('**  Error -- Does not match expected value')
			err = True
		print ('    +a = ',+a)
		c = -a
		print ('    c =',c,'   |c| =',abs(c),'     c=',c)
		if abs(c) != PhQ(9,'N m'):
			print ('**  Error -- Does not match expected value')
			err = True

		print ('\n	test *= and /=')
		a = PhQ(4,'N m')
		b = PhQ(2,'kg s')
		print ('    a =',a)
		print ('    b =',b)
		a *= 3
		print ('    after a *= 3,  a =',a)
		if a != PhQ(12,'N m'):
			print ('**  Error -- Does not match expected value')
			err = True
		a *= b
		print ('    after a *= b,  a =',a)
		if a != PhQ((4*3)*2,'N m kg s'):
			print ('**  Error -- Does not match expected value')
			err = True
		a = PhQ(4,'N m')
		b = PhQ(2,'N m')
		print ('    a =',a, '		b =',b,'    then calc a /= b')
		a /= b
		print ('    after a /= b,  a =',a)
		if a != 2:
			print ('**  Error -- Does not match expected value')
			err = True

		print ('\n	test -= and +=')
		a = PhQ(4,'N m')
		b = PhQ(2,'N m')
		print ('    a =',a,'		b =',b,'    then calc a += b')
		a += b
		print ('    after a+= b,  a =',a)
		if a != PhQ(2+4,'N m'):
			print ('**  Error -- Does not match expected value')
			err = True

		a = PhQ(4,'N m')
		b = PhQ(2,'N m')
		print ('    a =',a,'		b =',b,'    then calc a -= b')
		b -= a
		print ('    after b -= a,  b =',b)
		if b != PhQ(-2,'N m'):
			print ('**  Error -- Does not match expected value')
			err = True

		a = PhQ(4,'N m')
		b = PhQ(2,'N m')
		print ('    a =',a,'		b =',b,'    then calc c = a+b')
		c = a+b
		print ('    after c = a+b,  c =',c)
		if c != PhQ(4+2,'N m'):
			print ('**  Error -- Does not match expected value')
			err = True

		c = a-b
		print ('    after c = a-b,  c =',c)
		if c != PhQ(4-2,'N m'):
			print ('**  Error -- Does not match expected value')
			err = True

		c = b-a
		print ('    after c = b-a,  c =',c)
		if c != PhQ(2-4,'N m'):
			print ('**  Error -- Does not match expected value')
			err = True

		print ('\n	test extensions:')
		a = PhQ(3,'mm', desc='my short length')
		print ('    a =',a,'		',repr(a))
		ss = a.SI()
		print ('    a.SI() -->',ss,'		',repr(ss))
		if ss != PhQ(0.003,'m'):
			print ('**  Error -- Does not match expected value')
			err = True

		return err


	def test_convertUnits():
		def test_one(valIN,in0,in1,expected):		# allows for direct user input
			result = UnitsJZTdefault.convert(valIN,in0,in1)
			if fractionalError(result.num,expected) < 1e-12:
				print ('    ',unicode(UnitsJZTdefault))
				return False
			else:
				print ('ERR ',unicode(UnitsJZTdefault),'    should have gotten: %r [%s]' % (expected,in1))
				print ('		got: ',repr(result))
				return True

#		#***********************************************
#		# err |= test_one(32,'F','SI', 273.15)
#		# err |= test_one(u'1 Å^-1','','1/nm', 10)
#		global debug
#		debug = 1
#		print u'test convert 1 Å^-1 --> 1/nm'
#		result = UnitsJZTdefault.convert(1,u'Å^-1','1/nm')
#		print 'result = ',repr(result)
##		test_one(32,'F','SI', 273.15)
#		debug = 0
#		exit(1)
#		#***********************************************

		err = False
		print ('	try convertUnits:')
		err |= test_one(32,'F','F', 32)
		err |= test_one(32,'F',u'°C', 0)
		err |= test_one(32,'F','SI', 273.15)
		err |= test_one(1e6,'mm^2','m^2', 1)
		err |= test_one(1e7,'mm^2','m^2', 10)
		err |= test_one(1,'pm^2','Angstrom^2', 0.0001)
		err |= test_one(1,'pm^2',u'Å^2', 0.0001)
		err |= test_one(1,'pm^-2',u'Å^-2', 1e4)

		print ('\n	fancy:')
		err |= test_one('32 F','',u'°C', 0)
		err |= test_one(100,'cm','SI', 1)
		err |= test_one('100 cm','','SI', 1)
		err |= test_one('1e4 cm^2','','ft^2', 10.763910416709725)
		err |= test_one(u'1 Å^-1','','1/nm', 10)
		err |= test_one('5 N m','','ft lbf', 3.6878107463863277)
		err |= test_one('5 (N m)','','(ft)(lbf)', 3.6878107463863277)
		err |= test_one('5 (2 N m)','','(ft)(lbf)', 7.375621492772655)
		err |= test_one('2 (m)','','ft', 6.561679790026248)
		err |= test_one('2(m)','','ft',6.561679790026248)
		err |= test_one('0.12 kg m/s^2','','SI',0.12)
		err |= test_one('4 N m','','SI',4)
		err |= test_one('4 N mm','','SI',0.004)
		err |= test_one('4 mN mm','','SI',4e-6)
		print (' ')
		print ('    units[0] =',UnitsJZTdefault[0])
		print ('    units[1] =',unicode(UnitsJZTdefault[1]))
		print ('    units[-1] =',UnitsJZTdefault[-1])
		print (' ')
		print ('	uu = UnitsJZT()')
		uu = UnitsJZTdefault
		print ("    uu('0.12 kg m/s^2','SI')  -->  ",uu('0.12 kg m/s^2','SI'))
		print ("    unitConvert('0.13 kg m/s^2', 'SI')  -->  ",unitConvert('0.13 kg m/s^2', 'SI'))
		print (' ')
		print (u"    UnitsJZTdefault.convert(5,'Å','pm')  -->  ",UnitsJZTdefault.convert(5,'Å','pm'))
		print (u"    UnitsJZTdefault.convert('5 Å','','pm') -->  ",UnitsJZTdefault.convert('5 Å','','pm'))
		print (u"    uu('5 Å','pm')  -->  ",uu('5 Å','pm'))
		return err


	def test_transformUnit():
		def test_transformUnitOne(uIN,uOUT,fails=False):
			lead = '%s-->%s:' % (uIN.dimType,uOUT.dimType)
			n = 19-len(lead)
			lead += n*' '+'\t'
			try:	phq,recip = UnitsJZTdefault.transformUnit(uIN,uOUT)
			except Exception as e:
				if fails:	errStr = '     '
				else:		errStr = '**   '
				print (u'%sINVALID %s --> %s    %r' % (errStr, uIN,uOUT, e))
				return not fails
			if recip:	print ('     %s(%s)  /  (uIN=%s)   --> [%s]' % (lead,unicode(phq),unicode(uIN),unicode(uOUT.ustr)))
			else:		print ('     %s(%s)  *  (uIN=%s)   --> [%s]' % (lead,unicode(phq),unicode(uIN),unicode(uOUT.ustr)))
			return False

		hc = hbar*2*pi*c			# hc [J m]
		print ('	Note:	1 J/kg == 1 (m^2 s^-2)  same units as c^2')
		print ('		hc =  %.10g [J m]' %(hc,))
		print ('		only uses powers of {c, h, kB, e}, and a possible reciprocal\n')
		length = PhQ(1,'m')
		Qlen = PhQ(1,'1/m')
		mass = PhQ(1,'kg')
		energy = PhQ(1,'J')
		time = PhQ(1,'s')
		Temperature = PhQ(1,'K')
		err = False
		err |= test_transformUnitOne(mass,energy)
		err |= test_transformUnitOne(mass**0.5,energy**0.5)
		err |= test_transformUnitOne(Qlen,energy)
		err |= test_transformUnitOne(length,energy)
		err |= test_transformUnitOne(energy,Qlen)
		err |= test_transformUnitOne(energy,length)
		err |= test_transformUnitOne(time,length)
		err |= test_transformUnitOne(length,time)
		err |= test_transformUnitOne(Qlen,length)
		err |= test_transformUnitOne(Temperature,energy)
		err |= test_transformUnitOne(mass**2,energy,True)
		err |= test_transformUnitOne(mass**0.5,energy,True)

		print (' ')
		hc_keVAng = hbar*2*pi*c  *  1e7/e		# hc [keV Å]
		print (u'     hc = %.8g [keV Å],    kB = %.6g [eV/K]    c = %d [m/s]' % (hc_keVAng,kB_eV,c))
		err |= test_ConvertGeneric(1, u'me', 'eV', transform=True, expected=me*c*c/e)
		err |= test_ConvertGeneric(1, u'me', 'keV', transform=True, expected=me*c*c/e/1000)
		err |= test_ConvertGeneric(1.0, u'Å', 'keV', transform=True, expected=hc_keVAng)
		err |= test_ConvertGeneric(1.5, u'Å', 'keV', transform=True, expected=8.26561315867013)
		err |= test_ConvertGeneric(0.10, 'nm', 'keV', transform=True, expected=hc_keVAng)
		err |= test_ConvertGeneric(0.15, 'nm', 'keV', transform=True, expected=8.26561315867013)
		err |= test_ConvertGeneric(1.5, u'Å', 'keV', transform=True, expected=8.26561315867013)
		err |= test_ConvertGeneric(8, 'keV', 'Å', expected=hc_keVAng/8, transform=True)
		# the following should fail
		err |= test_ConvertGeneric(1.5, u'Å', 'keV', explanation="transform was set to False")
		err |= test_ConvertGeneric(10, 'keV', 'nm', explanation="transform was set to False")
		err |= test_ConvertGeneric(1, 'm', 'm^2', transform=True, explanation="impossible to transform length to area")

		print (' ')
		print ('	****** The following tests came from InterpretEnergy() testing')
		err |= test_ConvertGeneric(1, 'CuKa1', 'keV', expected=8.04782203372, transform=True)	# Emission lines
		err |= test_ConvertGeneric(1, 'CuKa2', 'keV', expected=8.02791629828,transform=True)
		err |= test_ConvertGeneric(1, 'CuKa', 'keV', expected=8.04117584667, transform=True)
		err |= test_ConvertGeneric(1, 'CuKa', 'eV', expected=8041.17584667, transform=True)
		err |= test_ConvertGeneric(1, 'MoKa1', 'keV', expected= 17.4793775338, transform=True)
		err |= test_ConvertGeneric(1, 'MoKa2', 'keV', expected=17.374466977, transform=True)
		err |= test_ConvertGeneric(1, 'MoKa', 'keV', expected=17.4442668514, transform=True)
		print (' ')
		err |= test_ConvertGeneric(1, '0.1 nm', 'keV', 12.398419739, transform=True)	# wavelength with units
		err |= test_ConvertGeneric(1, '1 Å', 'keV', 12.398419739, transform=True)
		err |= test_ConvertGeneric(1, u'1 Å', 'keV', 12.398419739, transform=True)
		err |= test_ConvertGeneric(1, '1 Angstrom', 'keV', 12.398419739, transform=True)
		err |= test_ConvertGeneric(1, '1e-10 m', 'keV', 12.398419739, transform=True)
		err |= test_ConvertGeneric(1e-10, 'm', 'keV', 12.398419739, transform=True)
		err |= test_ConvertGeneric(0.1, 'nm', 'eV', 12398.419738, transform=True)
		err |= test_ConvertGeneric(1.5, 'Å', 'keV', 8.265613159, transform=True)
		print (' ')
		err |= test_ConvertGeneric(float('inf'), 'keV', 'eV', float('inf'))				# zero and inf
		err |= test_ConvertGeneric(1, 'Inf keV', 'eV', float('inf'))
		err |= test_ConvertGeneric(float('inf'), 'keV', 'eV', float('inf'))
		err |= test_ConvertGeneric(0, 'nm', 'm', 0)
		err |= test_ConvertGeneric(0, 'keV', 'keV', 0)
		err |= test_ConvertGeneric(1, '0 keV', 'keV', 0)
		err |= test_ConvertGeneric(1, '0 keV', 'eV', 0)
		err |= test_ConvertGeneric(1, '-5 keV', 'keV', -5, explanation=' ')
		err |= test_ConvertGeneric(1, '-5e3 eV', 'keV', -5, explanation=' ')
		err |= test_ConvertGeneric(float('inf'), 'pc', 'm', float('inf'))
		err |= test_ConvertGeneric(float('inf'), u'Å', 'keV', 0, transform=True)
		err |= test_ConvertGeneric(float('inf'), 'pc', 'keV', 0, transform=True)
		err |= test_ConvertGeneric(float('inf'), 'm', 'keV', 0, transform=True)
		err |= test_ConvertGeneric(0, 'm', 'keV', float('inf'), transform=True)
		print (' ')
		err |= test_ConvertGeneric(1, '10', 'keV', 10.1, explanation=' ')			# ***  Intentional Errors  ***
		err |= test_ConvertGeneric(1, '10 xeV', 'keV', 10, explanation=' ')
		err |= test_ConvertGeneric(1, '1e-15 J', 'keV', 10, explanation=' ')
		err |= test_ConvertGeneric(1, '', '', 'keV', explanation=' ')
		err |= test_ConvertGeneric(1, 'ten', 'keV', 10, explanation=' ')
		err |= test_ConvertGeneric(1, '10keV', 'keV', 10, explanation=' ')
		err |= test_ConvertGeneric(1, '{}', 'keV', '', explanation=' ')
		err |= test_ConvertGeneric(1, {}, 'keV', '', explanation=' ')
		err |= test_ConvertGeneric(1, float('nan'), 'keV', float('nan'), explanation=' ')
		err |= test_ConvertGeneric(1, '5 m', u'Å', 5, explanation=' ')
		return err

	""" =========================== End of Individual Units Test Routines ============================ """


	def countTests():
		f = open(__file__, 'r')
		buf = f.read()
		f.close()
		i = buf.find("if __name__ == '__main__':")
		n = 0
		while i>-1:
			i = buf.find('.doit(', i+6)
			if i>0:	n += 1			# found another, increment count
			else:	break
		return n

	ntest = countTests()			# number of tests, last one is 2**(ntest-1)
	ntest -= 1						# need this because countTests() is in here
	testing = JZTtesting(__file__, last=2**(ntest-1))
#	testing.setQuietEnd((testing.testGroup == 1) or (testing.testGroup == testing.last))	# suppress printout for 1 and last

	if testing.doit('check a generic conversion testing():'):	#  2**0 = 1
		Narg = len(sys.argv)
		if Narg > 3:					# special for user input
			if Narg==5:
				arg1 = sys.argv[-3]
				arg2 = sys.argv[-2]
				transform = sys.argv[-1].lower().strip('-').startswith('t')
			else:
				arg1 = sys.argv[-2]
				arg2 = sys.argv[-1]
				transform = False

			try:
				arg1 = arg1.decode('utf-8', errors='backslashreplace')
				arg2 = arg2.decode('utf-8', errors='backslashreplace')
				con = UnitsJZTdefault.convert(arg1,'',arg2,transform=transform)
				print ('    ',unicode(UnitsJZTdefault))
			except Exception as e:
				print ('**  Error -- could not convert %r --> %r    %s' % (arg1,arg2,e))
				testing.addErr()
			testing.setQuietEnd()		# suppress printout when user gave input
		elif not testing.errMask:
			print ("\n\t\tfor user input, try something like:")
			print ("	./JZTunits.py 1 '2 acres' hectare")
			print ("	./JZTunits.py 1 '100 cm^2' SI")
			print ("	./JZTunits.py 1 '100 SI' cm^2")
			print ("	./JZTunits.py 1 '5 Newton' 'kg m s^-2'")
			print ("	./JZTunits.py 1 '1e4 dyne' kg*m/s^2")
			print (u"	./JZTunits.py 1 '12 keV' 'Å' transform")
			print (u"	./JZTunits.py 1 '1.5 Å' 'keV' T")
			print ("	./JZTunits.py 1 '1e4 cm^2' kg     # this SHOULD fail!")

	if testing.doit('check Many SI Prefixes:'):			#  2**1 = 2
		if test_SIprefixes(): testing.addErr()

	if testing.doit('check Length Units:'):				#  2**2 = 4
		if test_LengthUnits(): testing.addErr()

	if testing.doit('check Area Units:'):				#  2**3 = 8
		if test_AreaUnits(): testing.addErr()

	if testing.doit('check Volume Units:'):				#  2**4 = 16
		if test_VolumeUnits(): testing.addErr()

	if testing.doit('check Inverse Length (i.e. Q):'):	#  2**5 = 32
		if test_Qunits(): testing.addErr()

	if testing.doit('check Angle Units:'):				#  2**6 = 64
		if test_AngleUnits(): testing.addErr()

	if testing.doit('check Time Units:'):				#  2**7 = 128
		if test_TimeUnits(): testing.addErr()

	if testing.doit('check Mass Units:'):				#  2**8 = 256
		if test_MassUnits(): testing.addErr()

	if testing.doit('check Temperature Units:'):		#  2**9 = 512
		if test_TemperatureUnits(): testing.addErr()

	if testing.doit('check Energy Units:'):				#  2**10 = 1024
		if test_EnergyUnits(): testing.addErr()

	if testing.doit('check Power Units:'):				#  2**11 = 2048
		if test_PowerUnits(): testing.addErr()

	if testing.doit('check Velocity Units:'):			#  2**12 = 4096
		if test_VelocityUnits(): testing.addErr()

	if testing.doit('check Force Units:'):				#  2**13 = 8192
		if test_ForceUnits(): testing.addErr()

	if testing.doit('check Pressure Units:'):			#  2**14 = 16384
		if test_PressurUnits(): testing.addErr()

	if testing.doit('check all Light Units:'):			#  2**15 = 32768
		if test_LightUnits(): testing.addErr()

	if testing.doit('check Quantity of Matter Units:'):	#  2**16 = 65536
		if test_Quantity(): testing.addErr()

	if testing.doit('check Miscelaneous Units:'):		#  2**17 = 131072
		if test_Miscelaneous(): testing.addErr()

	if testing.doit('check InterpretEnergy():'):		#  2**18 = 262144
		if test_InterpretEnergy(): testing.addErr()

	if testing.doit('check OneUnit class:'):			#  2**19 = 524288
		if test_OneUnit(): testing.addErr()

	if testing.doit('check for Conflicts & Plurals:'):	#  2**20 = 1048576
		allUnits = MakeStandardUnits()
		if checkPrefixConflicts(allUnits): testing.addErr()

	if testing.doit('check listDimensions:'):			#  2**21 = 2097152
		if test_listDimensions(): testing.addErr()

	if testing.doit('check processInput():'):			#  2**22 = 4194304
		if test_processInput(): testing.addErr()

	if testing.doit('check test_convertUnits():'):		#  2**23 = 8388608
		if test_convertUnits(): testing.addErr()

	if testing.doit('check transformUnit():'):			#  2**24 = 16777216
		if test_transformUnit(): testing.addErr()

	if testing.doit('check crrent issue:'):				#  2**25 = 33554432
#		#***********************************************
#		global debug
#		debug = 1+4
#		print "test processInput('mm^2')"
#		result = UnitsJZTdefault.processInput('mm^2')
#		print 'result = ',result,'  ',repr(result)
#		exit(1)
#		result = UnitsJZTdefault.processInput('1/nm')
#
#		result = UnitsJZTdefault.convert(1,u'Å^-1','1/nm')
#		print 'result = ',repr(result)
#		exit(1)
#		#***********************************************

		testing.setQuietEnd(testing.unique)				# suppress printout when this is the only one called
		pass
#		testing.addErr()

	testing.ending()

	if not testing.quietEnd:
		print ('\n\n')
#		print '+++++++++++++++++++  deal with the plurals, the trailing s  +++++++++++++++++++\n'
#		print '+++++++++++++++++++  put in substitutions, especially for metre --> meter  +++++++++++++++++++\n'
#		print '+++++++++++++++++++  put in substitutions, also for "mass-of" +++++++++++++++++++\n'
#		print '+++++++++++++++++++  put in substitutions, also for "Troy" --> troy  +++++++++++++++++++\n'
#		print '+++++++++++++++++++  add tests for Luminous  +++++++++++++++++++\n'
#		print '+++++++++++++++++++  add tests for Quantity of Mater  +++++++++++++++++++\n'
#		print '+++++++++++++++++++  deal with braces, brakckets, parenthesis  +++++++++++++++++++'
#		print '+++++++++++++++++++  check: "°", still a problem with     ./JZTunits.py 1 "89.9°" rad  +++++++++++++++++++'
#		print '+++++++++++++++++++  check how to use:  units.convert("100 SI","","cm^2")  +++++++++++++++++++'
#		print '+++++++++++++++++++  make UnitsJZT callable, removes separate def unitConvert(...)  +++++++++++++++++++'
#		print '+++++++++++++++++++  add more testing for the units that were recently added in test_processInput()  +++++++++++++++++++'
#		print '+++++++++++++++++++  do the transformUnit, for mass<-->energy, wavelength<-->energy,... see test 512  +++++++++++++++++++'
		print ('+++++++++++++++++++  check: "kton", "kiloton", "k-ton of TNT", & MgTNT  +++++++++++++++++++')
		print ('+++++++++++++++++++  see:    https://en.wikipedia.org/wiki/Natural_units  +++++++++++++++++++')
		print ('+++++++++++++++++++  https://en.wikipedia.org/wiki/Avoirdupois_system  +++++++++++++++++++\n')
