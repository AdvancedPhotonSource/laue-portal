#!/usr/bin/env python
# -*- coding: utf-8 -*-


__version__ = "$Revision: $"
__author__  = "Jon Tischler, <tischler@aps.anl.gov>" +\
              "Argonne National Laboratory"
__date__    = "$Date: $"
__id__      = "$Id: $"


import string
import os
basestring = str



nan = float('nan')

""" ============================================================================
	========================== Start of Igor 1D Wave ===========================
"""
class Wave1D(object):
	"""
	a class that emulates an Igor 1D wave

	name			string describing wave
	array			list of values in the wave, or a list of tuples for multiple columns, i.e.
					array = [1,2,3,4,5]						# a single column
					array = ([(1,10),(2,11),(3,12),(4,13)]	# two columns
	x0				start of x scaling
	dx				step size of x scaling
	units			units name of dx and x0
	xLo				first x value, same as x0
	xHi				scaled x value of last point in array
	note			wave note a string

	When initializing, you should not give both dx and xHi
	If array is a list of tuples, then each tuple must have the same length (all rows have same length)
	"""
	def __init__(self, name, array, x0=0, dx=1.0, xHi=None, units='', ymin=0, ymax=0, yunits='', note=''):
		if not isinstance(name, basestring): raise TypeError('the "name" is not a string')
		if len(name)<1: raise TypeError('the "name" is empty')
		self.name = name

		# get the name for a wave (when saving to *.itx file) an Igor safe wave name
		self.wname = self.name2IgorWave(name)

		if not isinstance(array, (list,)):	raise TypeError('the "array" is not a list')
		N = len(array)
		if N<1: raise ValueError('Wave1D, the wave(s) are empty')
		self.N = N

		cols = 1
		if isinstance(array[0], (tuple,)):		# multiple columns, a list of tuples
			cols = len(array[0])
			if cols < 1: raise ValueError('Wave1D, there are 0 columns, wave empty')
			for row in array:					# all tuples must have same length
				if cols != len(row): raise TypeError('the rows in "array" do not all have the same length')
		self.columns = cols
		self.array = array

		try:
			dx = float(dx)
			dxOK = (dx == dx)
		except:
			dxOK = False

		try:
			xHi = float(xHi)
			xHiOK = (xHi == xHi)
		except:
			xHiOK = False

		if xHiOK:	self.setScaleEnds(x0, xHi, units=units)
		elif dxOK:	self.setScaleStep(x0, dx, units=units)
		else:		self.setScaleStep(x0, 1.0, units=units)
		self.setYscale(ymin, ymax, yunits)
		self.setNote(note)


	def __str__(self):
		""" Return string value for a Wave1D. """
		return unicode(self).encode('ascii', errors='backslashreplace')

	def __unicode__(self):
		""" Return unicode value for a Wave1D. """
		out = u'Wave1D: '
		out += 'name = "%s",  len=%d' % (self.name,self.N)
		if not(self.x0==0 and self.dx==1 and self.units==''):
			out += ',   x=[%g, %g] "%s" dx=%g' % (self.x0,self.xHi, self.units, self.dx)
		ystr = ''
		if not(self.ymin==0 and self.ymax==0):	ystr += '[%g, %g] ' % (self.ymin,self.ymax)
		if len(self.yunits):					ystr += '"%s"' % (self.yunits,)
		if len(ystr): ystr = ',   y=' + ystr
		out += ystr
		return out


	def __repr__(self):
		""" Return long string value for a Wave1D. """
		out = 'Wave1D: ['
		out += 'name = %r,  len=%r' % (self.name,self.N)
		out += ',   x=[%r, %r] %r dx=%r' % (self.x0,self.xHi, self.units, self.dx)
		out += ',   y=[%r, %r] %r' % (self.ymin,self.ymax,self.yunits)
		if len(self.note):	out += '\nnote = %r\n' % self.note
		out += ']'
		return out


	def __len__(self):
		""" This allows use of   len(Wave1D) syntax """
		return self.N


	def setScaleStep(self, x0=0, dx=1, units=''):
		"""
		Sets the internal x scaling using the starting position and step size.
		This can be called after the wave was created.
		"""
		try:	self.x0 = float(x0)
		except:	raise ValueError('x0 = "%r", it must be a number' % (x0,))

		try:	self.dx = float(dx)
		except:	raise ValueError('dx = "%r", it must be a number' % (dx,))

		if not isinstance(units, basestring): raise TypeError('the "units" is not a string')
		self.units = units

		self.recalcEnds()


	def setScaleEnds(self, x0=0, xHi=None, units=None):
		"""
		Sets the internal x scaling using scaled values of the first and last points.
		This can be used after the wave was created.
		"""
		try:	self.x0 = float(x0)
		except:	raise ValueError('xLo = "%r", it must be a number' % (x0,))

		try:	self.xHi = float(xHi)
		except:	raise ValueError('xHi = "%r", it must be a number' % (xHi,))
		if self.xHi <= self.x0: raise ValueError('xLo >= xHi, %r >= %r' % (x0,xHi))
		if isinstance(units, basestring): self.units = units

		self.dx = (self.xHi - self.x0) / (self.N - 1)
		self.recalcEnds()


	def setYscale(self, ymin=0, ymax=0, yunits=''):
		"""
		Sets the internal ymin, ymax, and yunits scaling.
		This can be used after the wave was created.
		"""
		try:	self.ymin = float(ymin)
		except:	raise ValueError('ymin = "%r", it must be a number' % (ymin,))

		try:	self.ymax = float(ymax)
		except:	raise ValueError('ymax = "%r", it must be a number' % (ymax,))

		if not isinstance(yunits, basestring): raise TypeError('the "yunits" is not a string')
		self.yunits = yunits


	def setNote(self, note):
		"""
		Set the WaveNote to note. Same as Igor Note/K wave, note
		This can be used after the wave was created.
		"""
		if not isinstance(note, basestring): raise TypeError('the "note" is not a string')
		self.note = note


	def appendNote(self, noteAdd,sep=';'):
		"""
		Append noteAdd to the WaveNote with an appropriate separator.
		This can be used after the wave was created.
		"""
		if not isinstance(noteAdd, basestring): raise TypeError('the additional "note" is not a string')
		if not isinstance(sep, basestring): raise TypeError('the additional separator is not a string')
		if len(sep):
			if self.note.endswith(sep) and noteAdd.startswith(sep):
				self.note += noteAdd[1:]
			elif self.note.endswith(sep) or noteAdd.startswith(sep):
				self.note += noteAdd
			else:
				self.note += ';'+noteAdd
		else:
			self.note += ';'+noteAdd


	def addSubClass(self, subClass):
		"""
		Add subClass to the 'waveClass=class;' class part.
		This routine is not generic Igor, but more specific to JZT.
		"""
		if not isinstance(subClass, basestring): raise TypeError('the additional "subClass" is not a string')

		subClass = subClass.strip()
		subClass = subClass.strip(',;')
		subClass = subClass.strip()
		if len(subClass)<1: return			# subClass is empty

		note = ';'+self.note+';'
		i0 = note.find(';waveClass=')
		if i0<0: return						# no waveClass present

		if i0>0:	before = note[0:i0]
		else:		before = ''

		i1 = note.find(';',i0+1)
		after = note[i1:]
		wclass = note[i0+11:i1]				# just the class value
		wclass = wclass.strip(';,')
		wclass += ','+subClass

		# reassemble the note
		note = before + 'waveClass=' + wclass + after
		self.note = note.strip(';')+';'


	def p(self, pval):
		""" Equivalent to the Igor wave[i] expression."""
		if self.N < 1: return nan

		try:	px = float(p)
		except:	raise ValueError('p = "%r", it must be a number' % (pval,))
		px = min(self.pMax, max(0,px))		# truncate to allowed integer range

		if px.is_integer(): return self.array[int(px)]

		p0 = int(px)						# index to bottom of interval
		y0 = self.array[p0]					# value at bottom
		if p0 >= self.pMax: return y1[self.N-1]
		return y0 + (px-p0)*(self.array[p0+1]-y0)


	def x(self, xval):
		""" Equivalent to the Igor wave(x) expression."""
		if self.N < 1: return nan
		try:	pval = int( (xval - self.x0) / self.dx )
		except:	return nan
		return self.p(pval)


	def p2x(self, pval):
		""" returns the scaled x value fron the point number."""
		return pval * self.dx + self.x0


	def x2p(self, xval):
		""" returns the point from the scaled x value (returned may not be integer)."""
		return (xval-self.x0) / self.dx


#	def setArray(self, array):
#		""" Set the wave.array to passed the passed array, also updates N."""
#		if not isinstance(array, (list, tuple)): raise TypeError('the "array" is not a list or tuple')
#		self.array = list(array)
#		self.N = len(self.array)
#		self.recalcEnds()								# find xHi, (assuming x0 and dx constant)


	def recalcEnds(self):
		""" Recalculate the max and min scaled values."""
		# self.plo = 0
		self.pMax = max(self.N -1, 0)
		self.xLo = self.x0
		self.xHi = self.pMax * self.dx + self.x0


	def IgorTextWave(self):
		""" Create contents of an Igor text wave from this object
		You can write the output to an *.itx file and easily load into Igor.
		"""
		note = self.note.replace('"', "''")				# change double-quote to 2 single quotes

		if self.columns == 1:
			out = "IGOR\rWAVES	%s\rBEGIN\r" %(self.wname,)
			for i in range(self.N): out += str(self.array[i])+'\r'
		else:
			out = "IGOR\rWAVES/N=(%d,%d)	%s\rBEGIN\r" % (self.N,self.columns,self.wname)
			for row in self.array:
				line = ''
				for val in row: line += '\t' + str(val)		# iterate over the tuple
				out += line + '\r'

		out += "END\r"
		out += 'X SetScale/P x %g,%g,"%s", %s; SetScale y %g,%g,"%s", %s\r' % (self.x0,self.dx,self.units,self.wname,self.ymin,self.ymax,self.yunits, self.wname)
		out += 'X Note %s, "%s"\r' % (self.wname,note)
		out += '\r'

		return out


	def name2IgorWave(self, wname, unknown='UnknownWave'):	# returns a valid Igor wave name
		try:
			wname = wname.strip()							# ensure an Igor friendly wave name
			wname = wname.replace(' ', '_')					# remove spaces
			wname = wname.replace('-', '_')					# remove dashes
			wname = wname[0:31]								# truncate to 31 characters
			if len(wname) < 2: raise
		except:
			wname = unknown

		return wname

	def write(wave, fname=None, moreIgor=None):
		# call IgorTextWave and write it to a file
		# if fname not given, then automatically generate the file name
		if isinstance(fname, basestring) and len(fname) > 1: FullFilePath = fname
		else:	FullFilePath = os.path.join(os.getcwd(),wave.name.strip()+'.itx')

		try:
			out = wave.IgorTextWave()
			if isinstance(moreIgor, basestring): out += '\r' + moreIgor + '\r'
			f = open(FullFilePath, 'w')
			if f:
				f.write(out)
				f.close()
			print ('wrote to: ',FullFilePath)
		except:
			raise IOError('Could not write to "%s"' % (FullFilePath,))

""" =========================== End of Igor 1D Wave ============================
	============================================================================
"""




""" ============================================================================
	===================== Start of Simple Peak Parameters ======================
"""
class SimplePeakShape(object):
	"""
	self.x0 = self.dx0			center of peak & the error
	self.FWHM = self.dFWHM		Full Width Half Max & the error
	self.amp = self.damp		amplitude & the error
	self.bkg = self.dbkg		background value & the error
	self.net = self.dnet		net area of peak (background subtracted) & the error
	self.area = self.darea		the integral (no bkg subtracted)
	self.COM = self.dCOM		center of mass & the error
	self.type = ''				type of shape, e.g. "Simple;Lorentzian;Gaussian;Voigt;PearsonVII"
	self.xunits					x and y units
	self.yunits
	self.min					min value
	self.max					max value
	self.maxLocP				location of point with max
	self.maxLocX				scaled x-value of maxLocP
	self.minLocP				location of point with min
	self.minLocX				scaled x-value of minLocP
	#	self.shape = self.dshape	# optional shape parameter (usually only for Voigt or PearsonVII) & the error
	#	self.shape1 = self.dshape1	# optional extra shape parameter, porbably not used & the error
	"""

	def __init__(self, wave, useBkg=False):

		if not hasattr(wave.array,'__iter__'):	# this works for list and numpy.array, but fails for strings
			raise TypeError('The input wave = %r, this is not iterable (it is usually a ).' % wave)

		self.useBkg = bool(useBkg)
		self.wave = wave

		self.x0 = self.dx0 = nan		# center of peak & the error
		self.FWHM = self.dFWHM = nan	# Full Width Half Max & the error
		self.amp = self.damp = nan		# amplitude & the error
		self.bkg = 0; self.dbkg = nan	# background value & the error
		self.sumY = nan					# sum of points in arrray
		if self.useBkg: self.dbkg=0
		self.net = self.dnet = nan		# net area of peak (background subtracted) & the error
		self.area = self.darea = nan	# the integral (no bkg subtracted)
		self.COM = self.dCOM = nan		# center of mass & the error
		self.type = ''					# type of shape, e.g. "Simple;Lorentzian;Gaussian;Voigt;PearsonVII"
		#	self.shape = self.dshape = nan	# optional shape parameter (usually only for Voigt or PearsonVII) & the error
		#	self.shape1 = self.dshape1 = nan	# optional extra shape parameter, porbably not used & the error

		self.xunits = wave.units
		self.yunits = wave.yunits
		try:	self.WaveStats()
		except:	raise ValueError('Unable to calculate WaveStats() from wave %r' % (self.wave.name,))

		try:	self.SimpleShape()
		except:	raise ValueError('Unable to calculate SimpleShape() from wave %r' % (self.wave.name,))


	def __str__(self):
		""" Return string value for a SimplePeakShape. """
		return unicode(self).encode('ascii', errors='backslashreplace')

	def __unicode__(self):
		""" Return unicode value for a SimplePeakShape. """
		out = u''
		out += self.type + ' Peak: '
		out += 'x0=%g,  FWHM=%g,  amp=%g,  bkg=%g,  sum=%g,  area=%g,  net=%g,  COM=%g' % (self.x0,self.FWHM, self.amp, self.bkg, self.sumY, self.area, self.net, self.COM)
		return out


	def __repr__(self):
		""" Return long string value for a SimplePeakShape. """
		out = self.type + ' Peak: ['
		out += 'x0=%r,  FWHM=%r,  amp=%r,  bkg=%r,  sum=%r,  area=%r,  net=%r,  COM=%r' % (self.x0,self.FWHM, self.amp, self.bkg, self.sumY, self.area, self.net, self.COM)
		out += ']'
		return out


	def WaveStats(self):
		maxVal = float('-inf')
		minVal = float('inf')
		imax = 0
		imin = 0
		sumY = sumXY = com = 0.0
		for i in range(self.wave.N):
			yi = self.wave.array[i]
			sumY += yi
			sumXY += yi * self.wave.p2x(i)
			if yi > maxVal:
				imax = i
				maxVal = yi
			if yi < minVal:
				imin = i
				minVal = yi

		self.sumY = sumY
		if self.useBkg:	self.bkg = wave.array[0] + wave.array[self.wave.pMax]
		else:			self.bkg = 0.0
		width = abs( self.wave.p2x(0) - self.wave.p2x(self.wave.pMax) )
		self.area = self.sumY * self.wave.dx
		self.net = self.area - self.bkg * width
		self.min = minVal
		self.max = maxVal
		self.minLocP = imin
		self.maxLocP = imax
		self.minLocX = self.wave.p2x(imin)
		self.maxLocX = self.wave.p2x(imax)
		self.COM = sumXY / sumY


	def SimpleShape(self):
		self.type = 'Simple'			# type of shape, e.g. Simple, Lorentzian, Gaussian, Voigt, PearsonVII
		imax = self.maxLocP
		self.amp = self.max - self.bkg
		HM = 0.5 * self.amp + self.bkg			# level for HM
		N = self.wave.N
		dx = self.wave.dx
		xlo = xhi = None

		for i in range(imax-1,-1,-1):			# first walk to the left
			if self.wave.array[i] <= HM:
				slope = (self.wave.array[i+1] - self.wave.array[i]) / dx
				xlo = self.wave.p2x(i) + (HM - self.wave.array[i])/slope
				break
		if xlo is None: xlo = self.wave.p2x(0)	# did not find HM, use first point

		for i in range(imax+1,N):				# second walk to the right
			if self.wave.array[i] <= HM:
				slope = (self.wave.array[i] - self.wave.array[i-1]) / dx
				xhi = self.wave.p2x(i-1) + (HM - self.wave.array[i-1])/slope
				break
		if xhi is None: xhi = self.wave.p2x(N-1)# did not find HM, use last point

		self.x0 = (xlo+xhi)/2
		self.FWHM = abs(xhi-xlo)


""" ====================== End of Simple Peak Parameters =======================
	============================================================================
"""




if __name__ == '__main__':
	"""
	Main function for DynamicalDiffraction.py.
	Test cases for DynamicalDiffraction class to verify correct behavior.
	"""
	import math
	import sys
	import os
	from JZTutil import JZTtesting

	testing = JZTtesting(__file__)

	if testing.doit('write itx file with 1 column:'):	#  2**0 = 1
		note = 'waveClass=testing;X=10;Y=20;Z=32;'
		HW = 10
		Npnts = 21
		x0 = -HW
		dx = 2*HW / (Npnts-1)
		gaussian = []
		for i in range(Npnts):
			angle = x0 + i*dx
			gaussian.append( math.exp(-0.1*angle**2) )
		wave = Wave1D('testWave', gaussian, x0=-HW, xHi=HW, units='arcsec', note=note, ymax=1, yunits='reflectivity')
		print (wave)
		wave.write()


	if testing.doit('write itx file with 2 columns:'):	#  2**0 = 1
		note = 'waveClass=testing;X=10;Y=20;Z=32;'
		HW = 10
		Npnts = 21
		x0 = -HW
		dx = 2*HW / (Npnts-1)
		gaussian = []
		for i in range(Npnts):
			angle = x0 + i*dx
			y = math.exp(-0.1*angle**2)
			gaussian.append((angle+5,y))
		wave = Wave1D('testWave2', gaussian, x0=-HW, xHi=HW, units='arcsec', note=note, ymax=1, yunits='reflectivity')
		print (wave)
		wave.write()


	if testing.doit('test SimplePeakShape() for a wave:'):	#  2**2 = 4
		array = [0,0,4,3,3]
		wave = 	Wave1D('testWave', array, x0=-1, dx=0.5, units='mm', yunits='counts')
		print (wave, array)
		sp = SimplePeakShape(wave)
		print (sp)


	testing.ending()

