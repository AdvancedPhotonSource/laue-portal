import re

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
	try:	sBytes = s.encode()	# sBytes is unused
	except:	raise TypeError('The input s = %r, is not a string' % s)
	s = re.sub('[ \t,;]',' ',s)	# change all separators to a space
	s = s.lower()
	s = s.replace("e+","e")		# "e+" is redundant
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