#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import datetime
import subprocess
import re
import socket
import inspect
if sys.version_info[0]<3: import codecs


__version__ = "$Revision: $"
__author__  = "Jon Tischler, <tischler@aps.anl.gov>" +\
              "Argonne National Laboratory"
__date__    = "$Date: $"
__id__      = "$Id: $"


"""	============================================================================
	=============================== Old $key value files ==============================
"""

def checkFileTypeLine(lineIn,typeLIstIn):
	""" typeListIn is either a list of strings or just a string """
	if len(typeLIstIn)<1 or len(lineIn)<2: return False
	line = lineIn
	if (line[0] != '$'): return False			# always have to start with a '$'
	ic = line.find('//')					# remove any comment if present
	if ic>0:	line = line[0:ic]

	line = line.replace('\r','\n')
	i = line.find('\n')
	if (i>0): line = line[0:i]

	line = line.replace('\r',' ')
	line = line.replace('\n',' ')
	line = line.replace('\t',' ')
	line = line.rstrip()					# remove any trailing white space
	while (line.find('  ') >= 0):			# change space runs to single space
		line = line.replace('  ',' ')		# double space to single space
	line = line.replace(',',' ')			# also change commas and semcolons to space
	line = line.replace(';',' ')
	flist = line.split(' ')					# first is tag, others are file types

	if isinstance(typeLIstIn,str):			# if only a string is passed, make it a list
		typeLIst = [typeLIstIn]
	elif isinstance(typeLIstIn,list):
		typeLIst = typeLIstIn
	else:
		return False

	#first check for the old (deprecated) way of doing things with the type in the tag
	tag = flist[0]
	if (tag[1:] in typeLIst): return True		# found it (note, does not include the '$' in the tag)

	# now check for the new way starting with a '$filetype' tag
	if (tag != r'$filetype'): return False		# does not have correct tag
	for type in flist:
		if (type in typeLIst): return True

	return False
#
def checkFileType(filename,typeLIstIn):
	""" check if a file is of a specified type """
	if len(typeLIstIn)<1: return False
	if (not os.path.isfile(filename)): return False
	try:	f = open(filename,mode='rt')
	except:	return False
	line = f.readline(200)
	f.close()
	return checkFileTypeLine(line,typeLIstIn)


def KeyValuesFromBuffer(buf):			# buf is the contents of a tagged file
	""" for a bunch of lines of tagged values, returns a dictionay of tag/value pairs """
	buf = buf.replace('\r\n','\n')
	buf = buf.replace('\n\r','\n')
	buf = buf.replace('\r','\n')
	buf = buf.replace('\t',' ')
	keyList = buf.split('\n')

	keyVals = {}
	for line in keyList:
		# find the key
		line = line.strip()
		if len(line)<1: continue		# skip blank lines
		if line[0] != '$': continue		# all keys must start with a '$'
		i = line.find(' ')
		if i<0:							# just a key, no value
			keyVals[line[1:]] = ''
			continue

		key = line[1:i]
		# remove comment if present, and get value
		ic = line.find('//')
		if ic>0:	value = line[i:ic]
		else:		value = line[i:]
		value = value.strip()

		value = value.strip("'")		# remove quotes, both kinds
		value = value.strip('"')
		value = value.strip("'")
		keyVals[key] = value
#		keyVals[key] = value.strip()

	return keyVals
#
def KeyValuesFromFile(filename):
	""" read a file of tagged values, and convert contents to a dictionary """
	if (not os.path.isfile(filename)): return {}
	try:	f = open(filename,mode='rt')
	except:	return {}
	buf = f.read(200000)
	f.close()

	return KeyValuesFromBuffer(buf)



"""	============================================================================
	============================== Start of useful functions ===========================
"""
def splitComment(s,comID):
	"""
	split s into part before comID and part after comID, does not return anything past a new line
	comID is the identifier for the comments.  e.g. comID = '//' returns a tuple with part before 
	comID and part after comID, comID is not returned.
	if s or comID are not strings, then just return s as it is is first part of tuple.
	"""
	if not (type(s) is str): return (s,'')
	i = s.find('\n')							# consider nothing past new line
	if i>=0: s = s[0:i]
	if not (type(comID) is str): return (s,'')		# comID is not string, nothing to strip
	if len(comID)<1: return (s,'')				# empty comID

	i = s.find(comID)						# points to start of comment
	if i<0: return (s,'')						# no comment, so just return everything

	if i>0: s1 = s[0:i]						# part before comment
	else: s1 = ''
	s2 = s[i+len(comID):]						# part after comment
	return (s1,s2)


def str2bool(v):
	""" returns TRUE or FALSE based on value of string """
	return v.lower() in ['yes', 'true', 't', 'y', '1', '-1']


def any2bool(v):
	""" returns TRUE or FALSE based on value of input, accepts string, numeric, boolean, & None """
	if (type(v) is bool):	return v
	try:	return bool(long(v))				# v is an int, or a long, or a string that looks like one
	except:	pass
	try:	return bool(float(v))				# v is a float or a string that looks like one
	except:	pass
	if (type(v) is str):
		try: return v[0].lower() in ('y', 't')	# first char is y or t
		except: return False
	return False						# not numeric, string, boolean, so return False


def findGCF(numsIN):
	""" returns Greatest Common Factor (GCF) in a list of integers (or floats that are integers) """
	nums = []
	for i in numsIN:						# fill nums[]
		if not (type(i) is int):
			if not i.is_integer(): return 1	# this routine requires integer values
			else: i = int(i)
		nums.append(abs(i))

	nMin = min(nums)
	for gcf in range(nMin, 0, -1):			# takes values [nMin, nMin-1, nMin-2, ... 2, 1]
		sumMods = 0
		for num in nums: sumMods += (num % gcf)
		if sumMods==0: break			# gcf is the biggest number to divide evenly into all values in numAbs

	return gcf


"""	============================================================================
	================================ Start of nice I/O ===============================
"""
def niceDeltaDateTime(dt):
	""" returns a nice string for printing a delta datetime
		dt can be passed as either a timedelta or seconds
	"""
	try:	dt = datetime.timedelta(seconds=float(dt))
	except:	pass

	if not(type(dt) is datetime.timedelta): return '?'
	if dt < datetime.timedelta(seconds=1.5):
		return str(float(dt.seconds) + float(dt.microseconds)*1e-6)+'s'
	micro = dt.microseconds
	dt = datetime.timedelta(dt.days,dt.seconds)
	if micro > 500000: dt += datetime.timedelta(0,1,0)	# round seconds
	return str(dt)


def niceDateTime(dt):
	""" returns a nice string for printing a datetime """
	if not(type(dt) is datetime.datetime): return 'ERROR -- not datetime.datetime type, (is: '+str(type(dt))+')'

	oneDay = datetime.timedelta(1)					# one day
	now = datetime.datetime.now()

	midnight0 = datetime.datetime(now.year,now.month,now.day)	# midnight at start of today
	midnight1 = midnight0 + oneDay
	midnight2 = midnight1 + oneDay
	midnightN1 = midnight0 - oneDay

	if (dt>=midnight0) and (dt<midnight1):			# today
		return dt.strftime('%I:%M:%S%p')
	elif dt>=midnight1 and dt<midnight2:				# tomorrow
		return dt.strftime('Tomorrow, %I:%M:%S%p')
	elif dt>=midnightN1 and dt<midnight0:			# yesterday
		return dt.strftime('Yesterday, %I:%M:%S%p')
	return dt.strftime('%a, %B %d, %Y %I:%M:%S%p')


def cmplx2str(zz, pow=0, places=float('nan')):
	if not(pow==pow): pow = 0

	if places==places:
		places = int(round(places))
		places = max(places,0)
		places = min(places,20)
		fmt1 = '%.'+str(places)+'g'
	else:
		fmt1 = '%g'

	zr = zz.real
	if zz.imag < 0:	sign = '-'
	else:			sign = '+'
	zi = abs(zz.imag)

	if not pow:				# pow is zero
		fmt = "%s %s %si" % (fmt1, sign, fmt1)
		strOut = fmt % (zr,zi)
	else:					# pow not zero
		if pow==1:		powStr = ""
		else:			powStr = "^"+str(pow)
		powValue = abs(zz)**pow
		fmt = "| %s %s %si |%%s = %s" % (fmt1,sign,fmt1, fmt1)
		strOut = fmt % (zr,zi, powStr, powValue)
	return strOut


def compressVertically(s):
	while '\t\n' in s:
		s = s.replace('\t\n','\n')
	while ' \n' in s:
		s = s.replace(' \n','\n')
	while '\n\n' in s:
		s = s.replace('\n\n','\n')
	return s


def indent1Tab(lines):
	""" add 1 tab to the start of each line in lines """
	lines = '\t'+lines
	lines = lines.replace('\n', '\n\t')
	lines = lines.rstrip('\t')
	return lines


def str2hkl(s,Nmin=3,Nmax=3):
	"""
	Take the string s and extract the h,k,l as a list
	insists on at least Nmin items, and no more than Nmax items
	This is mainly used to interpret a string containing an hkl which
	is why Nmin and Nmax default to 3.
	raises a TypeError or ValueError on error

	EXAMPLE::
		>>> str2hkl('1 1e-2 3')
		[1.0, 0.01, 3.0]

		>>> str2hkl('1 10 3')
		[1, 10, 3]

		>>> str2hkl('-103')
		[-1, 0, 3]

		>>> str2hkl('002')
		[0, 0, 2]

		>>> str2hkl('0024',Nmax=4)
		[0, 0, 2, 4]
	"""
	try:	s = s.encode()
	except:	raise TypeError('The input s = %r, is not a string' % s)
	s = re.sub('[ \t,;]',' ',s)	# change all separators to a space
	s = s.lower()
	s = s.replace("e+","e")	# "e+" is redundant
	s = s.replace("e-","e_")	# temporarily change "e-" to "e_"
	s = s.replace('-',' -')		# ensure a space separator
	s = s.replace('+',' +')		# ensure a space separator
	s = s.replace("e_","e-")	# change "e_" back to "e-"
	s = s.strip(' {[()]}')		# in case hkl was enclosed in "()", "[]", or "{}"
	while s.find('  ')>=0:
		s = s.replace("  "," ")	# no double spaces

	shkl = s.split(' ')
	if len(shkl)<Nmin:		# need to split some numbers, e.g. '12' -> '1','2'
		shkl2 = []
		for ss in shkl:
			if len(ss)<2 or len(ss)==2 and not (ss[0].isdigit()):
				shkl2.append(ss)
			else:
				i0 = 0
				i1 = 1
				if not ss[0].isdigit(): i1 += 1
				while i1<=len(ss):
#					print 'adding ss[%d:%d] = "%s"' % (i0,i1, ss[i0:i1])
					shkl2.append(ss[i0:i1])
					i0 = i1
					i1 = i0+1
		shkl = shkl2

	if len(shkl)<Nmin or len(shkl)>Nmax:
		raise ValueError('Found %d items in %r, but number of items must be in range [%d, %d]' % (len(shkl),s,Nmin,Nmax))
	hkl = []
	isfloat = False
	for x in shkl:
		try:
			x = float(x)	# yes they must be numbers
			isfloat = isfloat or not x.is_integer()
			hkl.append(x)
		except:
			raise TypeError("Elements must be integer or float, not"+str(type(x)))

	if not isfloat: hkl = [int(i) for i in hkl]
	return hkl


def hkl2str(hklIN,maxMag=1e-14):
	"""
	Format [h,k,l] into a string of acceptable minimal length.
	Return the value or the element that follows after the given value.
	raises a ValueError or ValueError on error

	EXAMPLE::
		>>> hkl2str([1, 2, 3])
		"123"

		>>> hkl2str([1.1, 2, 3])
		"1.1, 2, 3"

		>>> hkl2str([1, 20, 3])
		"1 20 3"
	"""
	if not hasattr(hklIN, '__iter__'):		# this works for list and numpy.array, but fails for strings
		raise TypeError('The input = %r, this is not iterable (the input is ususally a list).' % hklIN)
	try:
		if len(hklIN)<1: raise ValueError('input list is empty')
	except:
		raise TypeError('Could not determine the length of the input list = %r, probably not a list' % hklIN)

	hkl = []
	for x in hklIN:
		try:	x = float(x)
		except:	TypeError('from the input, %r is not a number' % x)
		if abs(x)<maxMag: x = 0
		elif x.is_integer(): x = int(x)
		hkl.append(x)

	allSingle = allInt = True
	for x in hkl:
		allSingle = allSingle and (abs(x)<10) and (type(x) is int)
		allInt = allInt and (type(x) is int)

	out = ''
	for x in hkl:					# assemble the output string
		if allSingle: out += str(x)		# only integers in range [-9,-8,...0,...8,9]
		elif allInt: out += str(x)+' '		# only integers, but some >=10 or <=-10
		else: out += str(x)+', '		# contains floats
	out = out.strip(', ')
	return out












def __SuperScriptNumberstr(inStr):
	"""
	Convert the characters '0 1 2 3 4 5 6 7 8 9 + - e' to str super-script.
	any other character just gets passed unchanged.
	"""
	converts = { '0':u'\u2070', '1':u'\u00B9', '2':u'\u00B2', '3':u'\u00B3', '4':u'\u2074', '5':u'\u2075', '6':u'\u2076', '7':u'\u2077', '8':u'\u2078', '9':u'\u2079', '+':u'\u207A', '-':u'\u207B', 'e':u'\u1D49' }
	out = ''
	for letter in inStr:
		try:	out += converts[letter]
		except:	out += letter
	return out

def __SubScriptNumberstr(inStr):
	"""
	Convert the characters '0 1 2 3 4 5 6 7 8 9 + - e' to str sub-script.
	any other character just gets passed unchanged.
	"""
	converts = { '0':u'\u2080', '1':u'\u2081', '2':u'\u2082', '3':u'\u2083', '4':u'\u2084', '5':u'\u2085', '6':u'\u2086', '7':u'\u2087', '8':u'\u2088', '9':u'\u2089', '+':u'\u208A', '-':u'\u208B', 'e':u'\u2091' }
	out = ''
	for letter in inStr:
		try:	out += converts[letter]
		except:	out += letter
	return out

def float2str(dec, fmt='%g'):
	""" Convert a decimal number of form '4.33e-3' to '4.33 x 10⁻³' """
	multiply = u'\u00D7'						# str multiply sign (sort of an 'x')
	try:
		if not isinstance(dec, basestring): dec = str(fmt) % float(dec)	# not a string, make it a string
		s12 = dec.split('e')					# try to split at the 'e', e.g. '4.1e3' --> ['4.1','3']
		if len(s12)<2:	out = dec				# no 'e', we are done
		else:			out = s12[0]+multiply+u'10'+__SuperScriptNumberstr(s12[1])
	except:	ValueError('Cannot interpret %r as a decimal number with format %r' % (dec,fmt))
	return out
	"""
	see:		https://en.wikipedia.org/wiki/str_subscripts_and_superscripts
	plusMinus = u'\u00B1'					# regular +/-
	degree = u'\u00B0'					# degree sign

	Aring = u'\u00C5'					# Aring, Angstrom sign
		text = text.replace('Angstrom', Aring)

	other super-script letters
	207D		(
	207E			)

	other sub-script letters
	2090		a
	2092		O
	2093		x
	2094		theta
	208D'		(
	208E'		)
	"""



"""	============================================================================
	============================== Start of system info ==============================
"""
def getCPUtype():
	""" returns type of CPU, on my Mac is gives 'x86_64' """
	return os.uname()[4]

def getNcores(queueName):
	""" return the number of cores present, returns a minimum of 1 """
	try:	useQueue = isCluster() and (type(queueName) is str) and len(queueName)>0
	except:	useQueue = False
	if useQueue:
		cmd = ['qstat', '-g', 'ct', '-q', queueName]
		proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, )
		stdout_value, stderr_value = proc.communicate('through stdin to stdout')
		if len(stderr_value)>0:
			print >> sys.stderr, 'ERROR --',repr(stderr_value)
			return 1							# in case of error, assume 1 core
		result = repr(stdout_value)[1:-3]			# trim of leading quote and trailing return quote

		i = result.find(queueName)
		if i<0: return 1
		result = result[i+len(queueName):-1].split()
		try:	Ncores = int(result[3])
		except:	Ncores = 1

	elif os.name is 'posix':							# works for both Linux & Darwin
		try:	Ncores = int(os.sysconf("SC_NPROCESSORS_ONLN"))
		except:	Ncores = 1
	elif os.name is 'nt':							# here for Windows
		try:	Ncores = int(os.environ['NUMBER_OF_PROCESSORS'])
		except:	Ncores = 1
	else:										# unknown platform
		Ncores = 1

	Ncores = max(1,Ncores)
	return Ncores


def isCluster():
	"""
	return True if this is a cluster at the APS, a Sun Grid Engine,
	on that computer, the environment variable SGE_CELL is 'orthros'
	"""
	return os.getenv('SGE_CELL') in ['orthros','blacklab']


def getLoginEnvValue(name):
	""" really get environment variables """
	if len(name)<1: return ''
	cmd = '/bin/bash -c "source ~/.bashrc ; /usr/bin/env"'
	proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, )
	stdout_value, stderr_value = proc.communicate('through stdin to stdout')
	if len(stderr_value)>0:
		print >> sys.stderr, 'ERROR --',repr(stderr_value)
		return 1								# in case of error, assume 1 core
	result = repr(stdout_value)[1:-3]				# trim off leading quote and trailing return quote

	find = '\\n'+name+'='
	i0 = result.find(find)
	if i0<0: return ''
	i0 += len(find)								# move to start of value

	i1 = result.find('\\n',i0)
	if i1<i0: i1 = len(result)						# might be at end
	return result[i0:i1]


def fullHostName():
	""" returns the full host name """
	if socket.gethostname().find('.')>=0:
		fullName = socket.gethostname()
	else:
		fullName = socket.gethostbyaddr(socket.gethostname())[1]
		if type(fullName) is list: fullName = str(fullName[0])
	return fullName


def whichCommand(name, flags=os.X_OK):
	"""
	Search PATH for executable files with the given name. Similar to
	the Linux which command.

	On newer versions of MS-Windows, the PATHEXT environment variable will be
	set to the list of file extensions for files considered executable. This
	will normally include things like ".EXE". This fuction will also find files
	with the given name ending with any of these extensions.

	On MS-Windows the only flag that has any meaning is os.F_OK. Any other
	flags will be ignored.

	@type name: C{str}
	@param name: The name for which to search.

	@type flags: C{int}
	@param flags: Arguments to L{os.access}.

	@rtype: C{list}
	@param: A list of the full paths to files found, in the
	order in which they were found.
	"""
	result = []
	exts = filter(None, os.environ.get('PATHEXT', '').split(os.pathsep))
	path = os.environ.get('PATH', None)
	if path is None:
		return []
	for p in os.environ.get('PATH', '').split(os.pathsep):
		p = os.path.join(p, name)
		if os.access(p, flags):
			result.append(p)
		for e in exts:
			pext = p + e
			if os.access(pext, flags):
				result.append(pext)
	return result



"""	===================================================================================
	============================= Start of module testing =============================
"""
class JZTtesting(object):
	"""
		A Class that the does testing on a file
		If you do not pass testGroup, then it will get obtained from the command line args
		if you set last to an int and call for testGroup='last', you will get the last one
			actually you will get whatever is the value of last
	"""
	def __init__(self, name='', testGroup=None, last=None, quietEnd=False, log=None):
		self.name = str(name)
		self.last = last

		try:
			if (sys.argv[1].lower() == 'last'): testGroup = last
			self.testGroup = int(testGroup)	# perhaps a testGroup was passed in
		except:								# testGroup was not passed look to command line
			try:	self.testGroup = int(eval(sys.argv[1], {'__builtins__':None}, {}))
			except:	raise ValueError('./%s testGroup,  testGroup must be a bit mask, (e.g. a combo of 1-65536), use -1 for all' % (self.name,))

		try:	self.quietEnd = bool(quietEnd)
		except:	self.quietEnd = False

		try:
			s2 = sys.argv[2].lower()		# keyboard overrides all
			log = s2.startswith('l')		# use log file is an 'l' is found
		except:
			try:	log = bool(log)			# perhaps the log flag was passed in as an argument
			except:	log = False				# default is NO

		if log:								# set up the log file
			fname = self.name.replace('.py','')
			fname = fname.replace('./','')
			fname = fname.replace('/','_')
			self.testLog = JZTlog(fname,'.')
		else:	self.testLog = None

		single2 = 0							# this will be >=0 if testGroup == 2**single2, otherwise single2=-1
		while self.testGroup>>single2 > 1: single2 += 1
		if 2**single2 != self.testGroup: single2 = -1
		self.single2 = single2				# this is uset for the printout

		if self.single2<0:	print ('showing testGroup(s) == %r (= %r)' % (self.testGroup,bin(self.testGroup)))
		else:				print ('showing testGroup(s) == %r = 2**%d (= %r)' % (self.testGroup,self.single2,bin(self.testGroup)))

		self.mask = self.errMask = self.tested = 0
		self.unique = False					# this is not used here, but can be used by the calling routines
		self.errList = []
		self.head = ''


	def doit(self, desc):
		""" returns True if this test should be done, desc is something like 'check DW_factor_M()' """
		if not self.mask:	self.mask = 1
		else:			self.mask = self.mask << 1
		self.unique = self.mask == self.testGroup		# this is the only  in testGroup
		if self.testGroup & self.mask:
			self.tested |= self.mask
			if self.mask == self.last:	self.head = '---testGroup (last)  %d  %s' % (self.mask,desc)
			else:						self.head = '---testGroup %d  %s' % (self.mask,desc)
			print ('\n\n\n ***************************************\n',self.head,'\n')
			return True
		return False


	def addErr(self):
		""" Flag this test as in ERROR """
		self.errMask |= self.mask
		self.errList.append(self.head)

	def setQuietEnd(self,quietEnd=True):
		""" used to set self.quietEnd after the instance of testing is created """
		try:	self.quietEnd = bool(quietEnd)
		except:	pass


	def ending(self):
		""" Call after all tests to show results """
		if  not self.quietEnd:
			testList = self.binMaskToList(self.tested)
			if self.single2<0: print ('\n\n\n********************** Tested with testGroup = %r (= %r = %r) **********************' % (self.testGroup, bin(self.tested),testList))
			else:				print ('\n\n\n********************** Tested with testGroup = %r = 2**%d (= %r = %r) **********************' % (self.testGroup, self.single2, bin(self.tested),testList))
			if self.errMask:
				print ('************************* Errors found in = %r (= %r) *************************' % (self.binMaskToList(self.errMask),self.errMask))
				for line in self.errList: print ('  ',line)	
			elif self.tested:	print ('  ---------------------- NO errors, All tests passed OK -------------------------')
			else:				print ('        ************************ NOTHING Tested ************************')
		if self.testLog: self.testLog.atEnd(self.errMask)	# finish and close the log file


	def binMaskToList(self,mask):
		""" takes a mask and returns the bits, e.g. self.binMaskToList(11) --> [1,2,8] """
		i = 1
		l = []
		while i <= mask:
			if i & mask: l.append(i)
			i = i << 1
		return l


	def __repr__(self):
		""" Return string representation for JZTtesting. """
		out = 'JZTtesting <name=%r,  mask=%r,  errMask=%r,  testGroup=%r,  tested=%r' % (self.name,self.mask,self.errMask,self.testGroup,self.tested)
		if len(self.errList):	out += '\r' + str(self.errList)
		else:					out += ', errList=[]'
		out += '>'
		return out

	def __str__(self):
		""" Return string value for JZTtesting. """
		return str(self).encode('ascii', errors='backslashreplace')

	def __str__(self):
		""" Return str value for JZTtesting. """
		out = u'Testing:'
		if len(self.name): out += u' "'+self.name+'", '
		if self.errMask:	out += u' checking testGroup = %d,  found errors in %d.' % (self.testGroup, self.errMask)
		else:				out += u' checking testGroup = %d,  NO errors found.' % (self.testGroup,)
		if len(self.errList): out += u'\n'+self.errList
		return out
"""	============================== End of module testing ==============================
	===================================================================================
"""	



"""	==================================================================================
	=============================== Start of statusBuf ===============================
"""
class statusBuf(object):

	def __init__(self, name='', bufMax=100, indentStep=2, showRepeats=False):
		"""
		================== ==============================================================
		input parameters                  description
		================== ==============================================================
		name                                optional name of the status buf, a sort of title
		bufMax                              max number of entries in the status buffer
		indentStep                         number of spaces to indent each level (default is 2)
		showRepeats                      in self.add, optionally do not add if line == the last line
		================== ==============================================================

		Note, you can call self.add(anotherStatusBuf)
		So you can set a statusBuf at the top level of your program, and collect the statusBuf's
		from all of the calls, and just add them in.

		methods:           using:   sb = statusBuf()

		sb.clear()          Clears the status buffer, do not reset bufMax, indentStep, or showRepeats.
		sb.add()            Adds a line or sub statusBuf
		str(sb)             returns nice string, suitable for printing
		repr(sb)            returns less nice string with more info
		sb.len() or len(sb) returns number of top level items in statusBuf
		sb.Print            basically the same as str(sb)
		"""
		try:	self.bufMax = int(bufMax)
		except:	raise ValueError('bufMax = %r, it must be an integer' % bufMax)

		try:	indentStep = int(indentStep)
		except:	raise ValueError('indentStep = %r, it must be a positive integer' % indentStep)
		if (indentStep<0): indentStep = 2
		self.indentStep = indentStep				# number of spaces for each indent
		try:	self.showRepeats = bool(showRepeats)
		except:	raise ValueError('showRepeats = %r, it must be a boolean' % showRepeats)
		try:	self.name = str(name)
		except:	self.name = None
		self.buf = list()							# ring buffer to hold status messages
		self.start = datetime.datetime.now()
		self.finish = self.start
		self.duration = datetime.timedelta(0,0,0)


	def __repr__(self):
		""" Return string representation for statusBuf. """
		return 'statusBuf(bufMax=%r, indentStep=%r, buf=%r)' % (self.bufMax,self.indentStep,self.buf)


	def __str__(self):
		""" Return string value for statusBuf. """
		return str(self).encode('ascii', errors='backslashreplace')

	def __str__(self):
		""" Return str value for statusBuf. """
		return str(self.buf2str())


	def __len__(self):
		""" Allows use of len(statusBuf) syntax """
		return len(self.buf)


	def len(self):
		""" Allows use of statusBuf.len() syntax """
		return len(self.buf)


	def clear(self):
		""" Clear the status buffer, do not reset bufMax, indentStep, or showRepeats. """
		self.buf = list()


	def add(self,line,out=None):
		"""
		Add to the status buffer, a ring buffer of lenth bufMax.
		The parameter 'line' may be another statusBuf, they can be nested.
		"""
		try:	Nbuf = len(self.buf)
		except:	return 0
		if not line: return Nbuf				# line is empty, nothing to add

		if type(line) is str or type(line) is str:
			if line.find('ERROR') >= 0:			# for errors, add file name and line number where addToStatusBuf() was called
				frame = inspect.currentframe()
				try:
					ll = inspect.getouterframes(frame)[1]
					place = '"%s" -- line %g,  ' % (ll[1], ll[2])
					del ll
				except:
					place = ''
				finally:
					del frame
				line += place

		try:	lastLine = self.buf[-1]				# get lastLine to check for repeats
		except:	lastLine = ''

		if self.showRepeats or (lastLine != line):	# skip adding if line is a repeat
			if len(self.buf)>(self.bufMax-1):		# trim off oldest entry
				self.buf = self.buf[1:]
			self.buf.append(line)				# if we are adding another statusBuf or just a line
			if type(out) is file: print >> out, line 	# also print the line, but don't print repeats

		self.finish = datetime.datetime.now()
		self.duration = self.finish - self.start
		return len(self.buf)


	def Print(self, out=None, indentLevel=0):
		"""
		Print the contents of self.buf in a nice way
		In general, do not use this, just call print statusBuf, the __str__ is almost the same.
		"""
		sout = self.buf2str(indentLevel=indentLevel)
		if sout:
			if out:	print >> out, sout
			else:	print (sout)


	def buf2str(self, sb=None, indentLevel=0):
		"""
		Returns printable string of status buffer. Usually called by Print()
		Do NOT specify buf or indentLevel when you call this. They are only for recursive use.
		"""
		top = sb is None							# used on first entry
		if top: sb = self
		indent = u''.ljust(indentLevel * self.indentStep)	# set indent to number of spaces
		is_sb = type(sb)

		out = indent
		if sb.name:	out = indent + u'"%s"   ' % (sb.name,)
		out = out + u'[%s - %s],  \N{GREEK CAPITAL LETTER DELTA}=%s\n' % (niceDateTime(self.start), niceDateTime(self.finish),niceDeltaDateTime(self.duration))
		for line in sb.buf:
			if is_sb==type(line): out += self.buf2str(sb=line, indentLevel=(indentLevel+1))
			else: out += indent+str(line)+'\n'

		if top: out = out.rstrip('\n')				# need to remove final LF so print works correct.
		return out

"""	=============================== End of statusBuf ================================
	=================================================================================
"""



"""	================================================================================
	================================ Start of JZTlog ===============================
"""
class JZTlog(object):
	""" set up a log file for this client """
	def __init__(self, projectName, logDir=None, fresh=False):
		"""
		init, open the log file, and write in header part 
		logDir	OPTIONAL, specify folder where the log file goes
		fresh	OPTIONAL, if True, then overwrite existing file, otherwise append
		"""
		try:
			if fresh:	code = 'w'
			else:		code = 'a'
		except:
			raise ValueError('ERROR -- fresh = %r, not interpretable as a True/False,' % fresh)

		try:
			projectName = projectName.encode('ascii','ignore')	# ensure ascii (not str or something else)
			projectName = projectName.strip()
			projectName = projectName.replace(' ','-')
			projectName = projectName[:32]
			self.name = projectName
		except:
			raise ValueError('ERROR -- Given an invalid project name: "%r",' % projectName)

		try:
			if logDir==None: logDir = ''
			logDir = logDir.encode('ascii','ignore')	# ensure ascii (not str or something else)
		except:
			raise ValueError('ERROR -- Unable to create directory for Log file = "%r",' % logDir)

		if len(logDir)<1:								# no logDir passed, set it
			if sys.platform == 'darwin':				# for Mac OSX, put logs into offical Logs location
				logDir = os.path.expanduser('~/Library/Logs/gov.anl.aps.SSM/')
				if not os.path.isdir(logDir):
					try:
						os.makedirs(logDir)
					except:
						raise ValueError('ERROR -- Unable to create directory for Log file = "%r",' % logDir)
						sys.exit(1)
			else:
				logDir = os.path.expanduser('~')

		try:
			if not os.path.isdir(logDir): raise			# given path is not a valid directory
		except:
			raise ValueError('ERROR -- Unable to find given directory for Log file = "%r",' % logDir)

		self.clientLogName = os.path.join(logDir,self.name+'.log')

		startStr = self.name+':   '+datetime.datetime.now().strftime('%a, %B %d, %Y %I:%M:%S%p')
		if sys.version_info[0]<3:
			try:	self.clientLog = codecs.open(self.clientLogName,code, encoding='utf-8')
			except:
				print ('ERROR, cannot open client log file "'+self.clientLogName+'"\n')
				sys.exit(1)
		else:
			try:	self.clientLog = open(self.clientLogName,code,1)	# open as an existing file for appending & line buffered
			except:
				print ('ERROR, cannot open client log file "'+self.clientLogName+'"\n')
				sys.exit(1)
		print (startStr)
		print ('	redirecting stdout & stderr to log file', self.clientLogName)

		self.saveout = sys.stdout						# save in case I want to un-redirect stdout
		sys.stdout = self.clientLog						# re-direct stdout to clientLog file
		sys.stderr = self.clientLog						# re-direct stderr to clientLog file
		print ('\n\n******************************************************************************')
		print ('******************************************************************************')
		print ('******************************************************************************')
		print (startStr)
		print ('python version  =  '+sys.version+'\n\n')


	def atEnd(self, app_exec):
		"""
		called at end
		app_exec is app.exec_() or the exit code, (an integer)
		"""
		if type(self.clientLog) is file:
			doneStr = '\n'+self.name+' Ended:   '+datetime.datetime.now().strftime('%a, %B %d, %Y %I:%M:%S%p')+'\n'
			print (doneStr)
			self.clientLog.close()
			sys.stdout = self.saveout					# re-direct stdout to original stream
			sys.stderr = self.saveout					# re-direct stderr to original stream
			print (doneStr)								# prints to console, not log file
		sys.exit(app_exec)


	def __str__(self):
		""" Return string value for statusBuf. """
		return str(self).encode('ascii', errors='backslashreplace')

	def __str__(self):
		""" Return str value for JZTlog. """
		return u'JZTlog of: "%s"  -->  "%s"' % (self.name, self.clientLogName)
		# self.clientLog = open(self.clientLogName,'a',1)	# open as an existing file for appending & line buffered

	def __repr__(self):
		""" Return string representation for ConvertUnitGeneric. """
		return 'JZTlog <name=%r, filePath=%r,  file=%r>' % (self.name, self.clientLogName, self.clientLog)

"""	================================================================================
	================================= End of JZTlog ================================
"""



"""	============================================================================
	================================= Run Testing =================================
"""
if __name__ == '__main__':
	"""
	Main function for JZTutil.py.
	"""
	def test_hkl2str():
		err = test1_hkl2str([1.1,2,3])
		err |= test1_hkl2str([1,20,3])
		err |= test1_hkl2str([1,-20,3])
		err |= test1_hkl2str([2])
		err |= test1_hkl2str([0,0,2])
		err |= test1_hkl2str([1,2,3,4,5,6])
		print (' ')
		# the following should produce an exception
		err |= test1_hkl2str([], explanation='no string given')
		err |= test1_hkl2str(None, explanation='input not a string (or iterable thing)')
		err |= test1_hkl2str('abc', explanation='input not iterable list of hkl')
		err |= test1_hkl2str('1 2 4', explanation='not an iterable list')
		err |= test1_hkl2str(5.5, explanation='just a single number')
		return err

	def test_str2hkl():
		err = test1_str2hkl('1 1e-2 3')
		err |= test1_str2hkl('1+2+3')
		err |= test1_str2hkl('1 10 3')
		err |= test1_str2hkl('-103')
		err |= test1_str2hkl('002')
		err |= test1_str2hkl('0024',Nmax=4)
		print (' ')
		err |= test1_str2hkl('0', explanation='only one digit')
		err |= test1_str2hkl('01234', explanation='more than 3 digits')
		err |= test1_str2hkl(1.2, explanation='only a number')
		return err

	def test1_hkl2str(listIn,maxMag=1e-14, explanation=''):
		try:
			print ('     hkl2str(%s) = "%s"' % (repr(listIn),hkl2str(listIn,maxMag=maxMag)))
			return False
		except Exception as e:
			if explanation:	errStr = '     '
			else:			errStr = 'ERR  '
			print ('%shkl2str(%r) FAILED,  %r     %r' % (errStr,listIn, e,explanation))
			return len(explanation)<1

	def test1_str2hkl(s,Nmin=3,Nmax=3, explanation=''):
		try:
			print ('     str2hkl(%s) = "%s"' % (repr(s),str2hkl(s,Nmin=Nmin,Nmax=Nmax)))
			return False
		except Exception as e:
			if explanation:	errStr = '     '
			else:			errStr = 'ERR  '
			print ('%shkl2str(%r) FAILED,  %r     %r' % (errStr,s, e, explanation))
			return len(explanation)<1


	def test_super(pre,inStr):
		print (u'     "%s","%s"  -->  %s' % (pre,inStr, pre+__SuperScriptNumberstr(inStr)))

	def test_sub(pre,inStr):
		print (u'     "%s","%s"  -->  %s' % (pre,inStr, pre+__SubScriptNumberstr(inStr)))

	def test_float2str(dec, fmt=None):
		if fmt:	out = u'float2str(%r, "%s")  -->  %s' % (dec, fmt, float2str(dec,fmt))
		else:	out = u'float2str(%r)  -->  %s' % (dec, float2str(dec))
		if fmt and isinstance(dec, basestring): out += '\t\t# fmt is ignored when a string is passed'
		print ('     '+out)



	testing = JZTtesting(__file__)

	if testing.doit('check hkl2str()'):				#  2**0 = 1
		if test_hkl2str(): testing.addErr()

	if testing.doit('check str2hkl()'):				#  2**1 = 2
		if test_str2hkl(): testing.addErr()

	if testing.doit('check system info commands'):	#  2**2 = 4
		try:
			print ('     CPU type =',getCPUtype())
			print ('     isCluster =',isCluster())
			print ('     getLoginEnvValue("TERM") =',getLoginEnvValue('TERM'))
			print ('     getLoginEnvValue("VERSIONER_PYTHON_PREFER_32_BIT") =',getLoginEnvValue('VERSIONER_PYTHON_PREFER_32_BIT'))
			print ('     fullHostName =',fullHostName())
			print ('     whichCommand("xmllint") =',whichCommand('ls'))
		except:
			testing.addErr()

	if testing.doit('check statusBuf (status buffer contains ERROR lines, that is OK)'):	#  2**3 = 8
		try:
			sb = statusBuf(name='top level testing')
			print (repr(sb))
			print ('')
			sb.add('step 1')
			sb.add('ERROR -- step 2')
			sb.add('step 3')
			sb.add('step 3')
			sb.add('step 3')
			sb.add('step 4')

			subSub = statusBuf(name='sub process 1')
			subSub.add('sub1 line A')
			subSub.add('sub1 line B')
			sb.add(subSub)

			sb.add('step 5')

			subSub = statusBuf(name='sub process 2')
			subSub.add('ERROR -- sub2 line X')
			subSub.add('sub2 line Y')
			sb.add(subSub)

			sb.add('step 6, the last step')
			print (str(sb))

			file = 'test_statusBuf.txt'
			if sys.version_info[0]<3:	f = codecs.open(file,'w', encoding='utf-8')
			else:						f = open(file,'w')
			f.write(str(sb))
			f.close()
		except Exception as e:
			testing.addErr()
			testing.errList.append(str(e))

	if testing.doit('check str'):				#  2**4 = 16
		print ('\t\tsuper-scripts:')
		test_super('A',u'+1234567890e-2')
		test_super('A',u'-1234567890e+3')
		test_super('nm','-1')
		test_super('s','2')
		test_super('3','4')
		test_super('10','-6')
		test_super('4.33 x 10','-3')

		print ('\n\t\tsub-scripts:')
		test_sub('A',u'+123456789e-4')
		test_sub('A',u'-123456789e+5')
		test_sub(u'\u00C5','+5')

		print ('\n\t\ttest float2str:')
		test_float2str(+4.33e-23)
		test_float2str(-4.33)
		test_float2str('4.12', "%d")
		test_float2str('+4.12e20', "%d")
		test_float2str(+20)
		test_float2str(+4.33123456789977e+17)
		test_float2str(+4.33123456789977e+17, '%r')
		test_float2str(+4.33123456789977e+17, '%g')
		test_float2str(+4.33123456789977e+17, '%d')
		test_float2str("+4.33123456789977aabbe+17")
		test_float2str(float('nan'))
		test_float2str(-float('inf'))

	if testing.testLog is None:
		if testing.doit('check log file'):			#  2**5 = 32
			logClass = JZTlog('JZTutil_test','.',fresh=True)
			print ('projectName =',logClass.name)
			print (logClass)
			print (repr(logClass))
			print ('this is some text that has been redirected')
			logClass.atEnd(None)					# done with log file
			print ('This should only print to console')


	testing.ending()

