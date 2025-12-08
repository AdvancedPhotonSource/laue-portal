#!/usr/bin/env python3
#
# srange.py
#
# $Id:    $
# $URL: $
#
# Part of the "pydiffract" package
#

import sys

__version__     =       "$Revision: $"
__author__      =       "Jon Tischler, <tischler@aps.anl.gov>" +\
                                "Christian M. Schlepuetz, <cschlep@aps.anl.gov>, " +\
                                "Argonne National Laboratory"
__date__        =       "$Date: $"
__id__          =       "$Id: $"


class srange:
        """
        String-range class.


        Updated to work with both python 2 & 3 (previously only 2) by JZT on June 12, 2020.
        Also a suite of tests are included at the end.
        with conversion to python3, also had to deal with i/j --> float, not int


        This class provides functions to convert a string representing integers and
        ranges of integers to an object which can be iterated over all the values
        contained in the string.  Also, a list of individual values or subranges can be
        retrieved.

        EXAMPLE::
                >>> sr = srange("1,3,4-5,8-11,12-13,20")
                >>> for val in sr:
                                        print("%d," % val),
                1, 3, 4, 5, 8, 9, 10, 11, 12, 13, 20,

        NOTE:
                String ranges can only contain integer numbers and must be strictly
                monotonically increasing. Multiple identical values are not allowed.
                addition of __resort_list() now allows for mis-ordered simple ranges,
                but they still must not overlap.

        TODO:
                The issues of the above note should be addressed to make the code more
                robust and forgiving. There is no reason one should not specify sub-
                ranges in arbitrary orders.

        The range is checked to be monotonic, it returns None if no more values
        last is the last number obtained from this range,
        use -Inf to get start of range, it returns the next

        variables and methods that you may be interested in

        ======================= ===================================================================================
        variables of interest     description
        ======================= ===================================================================================
        self.r                  the input string, after formatting and compacting
        self.previous_item      the previous value produced, initially set very low
        self.auto_reset         if True (default), then previous_item is reset to min at each call to __iter__
        ======================= ===================================================================================

        ======================= ===================================================================================
        methods of interest        action
        ======================= ===================================================================================
        next()                  returns next value, updates previous_item too
        reset_previous()        reset the iterator so it starts with the first value
        after(prev)             returns value that follows prev, without changing the current point in iteration
        first()                 returns the first number in the range, for self.r="3,5,9-20", self.first() returns 3
        last()                  returns the last number in the range, for self.r="3,5,9-20", self.last() returns 20
        len()                   returns number of points in the range, for self.r="3,5,9-20", self.len() returns 14
        is_in_range(m)          returns True if m is in self.r, otherwise False
        index(ipnt)             return the ipntth number from range, first number is ipnt==0,  returns None if ipnt negative or too big
        val2index(m)            returns index into r that corresponds to m. e.g. for r='3,5,9-20', m=5 returns 1.
        sub_range(start,n,...)  returns a new range that is a sub range of current one, setLast=False
        list(self)              returns a list where each element is a value in the range, CAUTION this can make a VERY big list
        ======================= ===================================================================================

        =====================   ======================= ===================================================================
        special methods          command                    result using: sr = srange('1-4')
        =====================   ======================= ===================================================================
        __getitem__(n)          print(sr[2])                3
        __len__()               print(len(sr))              4
        __str__()               print(str(sr))              1-4
        __repr__()              print(repr(sr))             srange('1-4', len=4, previous=0, auto_reset=True)
        =====================   ======================= ===================================================================
        """

        def __init__(self, r='', auto_reset=True):
                """
                Initialize the srange instance.
                """
                try:    self.intTypes = (int, long)             # long is only in python2, not 3
                except: self.intTypes = (int)
                try:    self.MAXINT = sys.maxint                # sys.maxint only exists in python2
                except: self.MAXINT = sys.maxsize               # for python3, maxsize is a good choice, = (2^63)-1

                # if a numpy array is passed for r, convert r to an integer array
                try:
                        if isinstance(r[0], numpy.integer):
                                r_int = []                                              # a new empty array
                                for i in r: r_int.append(int(i))# fill r_int with ints 
                                r = []                                                  # need to remake r[], do not want the name r_int
                                for i in r_int: r.append(i)             # now reset new r[] to input values (but all ints)
                except: pass

                # convert input to a list of tuples, each tuple is one simple dash range, e.g. "1-17:2"
                if isinstance(r,str):
                        if r.lower() == 'none': r = ''          # 'none' is same as empty string
                        self.l = self.__string_to_tuple_list(r)
                elif isinstance(r, self.intTypes):
                        r = int(r)
                        self.l = [(r,r,1)]
                        r = str(r)
                elif hasattr(r, '__iter__'):                    # this works for list and numpy.array, fails for strings
                        self.l = self.__list_to_srange(r)
                else:
                        raise TypeError("String list must be a string or (list of) integers.")

                if not self.__is_monotonic():
                        self.__resort_list()                            # try to sort the list to be monotonic
                        if not self.__is_monotonic():           # if still not monotonic, give up
                                raise ValueError("String range is unsortable.")

                try:    self.auto_reset = bool(auto_reset)
                except: raise TypeError("auto_reset must be boolean")

                self.reset_previous()                                   # set self.previous_item to number before first number in range
                self.l = self.__compact(self.l)                 # compactify the list
                self.r = self.__tuple_list_to_str(self.l)       # make a string representation of list

        def __iter__(self):
                """ The class iterator """
                if self.auto_reset:
                        self.reset_previous()                           # reset to start of range, changed July 24-2014 JZT
                return self

        def __repr__(self):
                """ Return string representation for srange. """
                try:    length = self.len()
                except: length = None
                return "srange('%s', len=%r, previous=%r, auto_reset=%r)" % (self.r, length, self.previous_item, self.auto_reset)

        def __str__(self):
                """ Return string value for srange. """
                return self.r

        def __getitem__(self, n):
                """ Return the n-th element in the string range. """
                return self.index(n)

        def __next__(self):                                                     # this is required for python3 iterator
                """ Return the n-th element in the string range. """
                return next(self)

        def __next__(self):                                                             # this is required for python2 iterator
                """ Return the next value in the string range. Also update self.previous_item. """

                if not self.l:
                        raise StopIteration
                for (lo, hi, stride) in self.l:
                        if self.previous_item < lo:                     # start of this simple range is big enough
                                self.previous_item = lo
                                return lo
                        elif self.previous_item >= lo and self.previous_item < hi:      # within this simple range
                                self.previous_item += stride - ((self.previous_item-lo) % stride)
                                return self.previous_item
#               self.reset_previous()                                   # removed July 21-2014 JZT, do NOT reset at end of range
                raise StopIteration

        def after(self, val):
                """
                Return the value or the element that follows after the given value.

                EXAMPLE::
                        >>> sr = srange("3,5,9-20")
                        >>> print(sr.after(5))
                        9
                """

                if not self.l:
                        return None
                previous_save = self.previous_item              # save self.previous_item for later resetting
                try:
                        self.previous_item = int(val)           # temporarily set self.previous_item to val
                except:
                        raise ValueError("argument to srange.after() must be a number")
                try:
                        after = next(self)
                except:
                        after = None
                self.previous_item = previous_save              # reset self.previous_item to original value
                return after

        def first(self):
                """
                Return the number of the first item in the range.
                This method uses but does not change any internal variables, e.g. no self.xxxx

                EXAMPLE::
                        >>> sr = srange("3,5,9-20")
                        >>> print(sr.first())
                        3
                """

                if not self.l:
                        raise ValueError("String range is empty.")
                return (self.l[0])[0]

        def last(self):
                """
                Return the value of the last item in the range.
                This method uses but does not change any internal variables, e.g. no self.xxxx

                EXAMPLE::
                        >>> sr = srange("3,5,9-20")
                        >>> print(sr.last())
                        20
                """

                if not self.l:
                        raise ValueError("String range is empty.")
                return (self.l[-1])[1]

        def len(self):
                """
                Return the number of items in the string range.
                This method uses but does not change any internal variables, e.g. no self.xxxx

                EXAMPLE::
                        >>> sr = srange("3,5,9-20")
                        >>> print(sr.len())
                        14
                """

                if not self.l:
                        return 0

                total = 0
                for (lo, hi, stride) in self.l:
#                       total += (hi-lo)/stride + 1                     # accumulate length of each simple range
                        total += int((hi-lo)/stride) + 1        # accumulate length of each simple range, python3 (/ --> float)
                return total

        def __len__(self):
                """ This is redundant with len(), you can use s.len(), or len(s).
                This method uses but does not change any internal variables, e.g. no self.xxxx
                """
                return self.len()

        def is_in_range(self, item):
                """
                Return True if item is in string range self.r, False otherwise.
                This method uses but does not change any internal variables, e.g. no self.xxxx
                """

                if not self.l:
                        return False
                if not isinstance(item, self.intTypes):
                        raise TypeError("Element must be integer number")

                for (lo, hi, stride) in self.l:
                        if lo <= item and item <= hi:
                                return (float(item-lo)/stride).is_integer()
                return False

        def index(self, n):
                """
                Return the n-th element from the string range.
                This method uses but does not change any internal variables, e.g. no self.xxxx
                """

                if not self.l:
                        raise ValueError('String range is empty.')
                elif not isinstance(n, self.intTypes):
                        raise TypeError('Element must be an integer number, not a '+str(type(n)))
                elif (n < 0):
                        raise ValueError('Index must be non-negative, not '+str(n))

                count = 0
                for (lo, hi, stride) in self.l:
#                       hi_count = count + (hi-lo)/stride       # count at hi
                        hi_count = count + int((hi-lo)/stride)  # count at hi, in python3 i/j --> float
                        if n <= hi_count:
                                return lo + (n-count)*stride
                        count = hi_count + 1
                return None

        def val2index(self, val):
                """
                Return the index into the srange that corresponds to val.
                This method uses but does not change any internal variables, e.g. no self.xxxx

                EXAMPLE::
                        >>> r = '3, 5, 9-20'
                        >>> print(val2index(5))
                        1
                """

                if not self.l:
                        raise ValueError("String range is empty.")
                elif not isinstance(val, self.intTypes):
                        raise TypeError('Value must be an integer, not a '+str(type(n)))

                index = 0
                for (lo, hi, stride) in self.l:
                        if lo <= val and val <= hi:                     # val is in this simple range
                                index += float(val-lo)/stride
                                if index.is_integer():
                                        return int(index)
                                else:
                                        return None
                        index += int(hi-lo+1) / int(stride)     # increment index for next simple range
                return None


        def sub_range(self, start, n, set_last=False):
                """
                Return a sub range from the original range as a new range string.

                The new range starts at with the value start and has up to n elements.
                If start is not an element in the range, then it begin with first element
                after start. If set_last is True, then self.previous_item is set to the new
                end, otherwise no change is made.
                This method only changes an internal variable "self.previous_item" when set_last is True.

                EXAMPLE::
                        >>> sr = srange('3,5,9-20')
                        >>> print(sr.sub_range(start = 5, n = 3))
                        5,9-10
                """

                if not self.l:
                        raise ValueError("String range is empty.")
                elif not isinstance(start, self.intTypes):
                        raise TypeError("Start value (start) must be an integer.")
                elif not isinstance(n, self.intTypes):
                        raise TypeError("Number of elements (n) must be an integer.")
                elif n < 0:
                        raise ValueError("Number of elements must be greater zero.")

                hi = self.last()                                                # in case hi not set in loop
                lout = []
                for (lo, hi, stride) in self.l:
                        if hi < start:                                          # try next simple range
                                continue
                        start = max(start,lo)
                        lo = start + ((start-lo) % stride)      # either start or first number after start
                        hi = min(lo + (n-1)*stride, hi)
                        if lo>hi:                                                       # nothing in this simple range
                                continue
#                       n -= (hi-lo)/stride + 1
                        n -= int((hi-lo)/stride) + 1            # in python3 i/j --> float
                        lout.append((lo,hi,stride))
                        if n < 1:
                                break

                if set_last:                                                    # set previous_item was requested
                        self.previous_item = hi

                lout = self.__compact(lout)                             # compactify the list
                return self.__tuple_list_to_str(lout)   # return the string



        def list(self):
                """
                Expand a string range into a standard python  list.
                This method uses but does not change any internal variables, e.g. no self.xxxx

                EXAMPLE::
                        >>> print(srange("3,5,9-13").list())
                        [3, 5, 9, 10, 11, 12, 13]

                CAUTION:
                        The following statement::

                                >>> list("1-100000",";")

                        will produce a list with 100000 elements!

                Max list length for a 32 bit system is (2^32 - 1)/2/4 = 536870912
                on my computer I get a MemoryError for lengths > 1e8, so limit to 1e7
                """

                if self.len() > 10000000:                               # 1e7, a big number
                        raise IndexError("Resulting list too large, > 1e7.")
                elif not self.l:
                        return []

                lout = []
                for (lo, hi, stride) in self.l:
                        lout.extend(list(range(lo,hi+1,stride)))
                return lout


        def reset_previous(self):
                """ Reset previous_item to the lowest possible integer value. """
                try:
                        l0 = self.l[0]
                        self.previous_item = int(l0[0]-1)       # in python2, the srange may need longs
                except:
                        self.previous_item = -self.MAXINT       # just set to most negative 32bit int


        def __list_to_srange(self, input_list):
                """
                Convert a python list to a string range, the tuple list.
                This method neither uses nor changes any internal variables, e.g. no self.xxxx
                Also this routine does NOT compact the returned list, you must do that.

                EXAMPLE::
                        >>> mylist = [3,5,9,10,11,12]
                        >>> sr = srange('')
                        >>> sr.__list_to_srange(mylist)
                        >>> print(sr)
                        '3,5,9-12'
                """

                if not all(isinstance(n, self.intTypes) for n in input_list):
                        raise ValueError("List elements must be integers.")

                new_tuple_list = []
                for item in input_list:
                        new_tuple_list.append((item,item,1))
                return new_tuple_list

        def __string_to_tuple_list(self,r):
                """
                Convert a string range to a list of simple ranges, tuples of the form (lo,hi,stride).
                r is the string, usually input at __init__(...)
                This routine does no compacting, just a simple translation
                Note, all values in the tuple list are integers.
                This method neither uses nor changes any internal variables, e.g. no self.xxxx
                """

                if not r:
                        return []

                if r.find('@') > 0:
                        raise ValueError("Invalid character ('@') in string range.")

                l = []
                singles = r.split(',')                                  # split string into a list of simple ranges
                for single in singles:
                        s = single.lstrip()

                        # look for a stride
                        lo,mid,hi = s.partition(":")
                        try:    val = float(hi)
                        except: val = 1.0                                       # default stride is 1
                        stride = int(val)
                        if not val.is_integer() or stride<=0:
                                raise ValueError("stride is not a positive integer in string range.")
                        s = lo

                        # A '-' after the first character indicates a contiguous range
                        # If it is first character, it means a negative number
                        # If no '-' is found, mid and hi will be empty strings
                        i = s[1:].find('-') + 1
                        if i > 0:
                                s = s[0:i] + '@' + s[i+1:]
                        lo,mid,hi = s.partition('@')
                        lo = lo.strip()
                        if lo.lower().find('-inf') >= 0:
                                lo = -self.MAXINT
                        elif lo.lower().find('inf') >= 0:
                                lo = self.MAXINT
                        try:
                                lo = int(lo)
                        except:
                                raise ValueError("Values in string range must be integers.")

                        if(hi):
                                hi = hi.strip()
                                if hi.lower().find('-inf') >= 0:
                                        hi = -self.MAXINT
                                elif hi.lower().find('inf') >= 0:
                                        hi = self.MAXINT
                                try:
                                        hi = int(hi)
                                        hi -= ((hi-lo) % stride)        # ensure that hi matches with stride, remove excess
                                except:
                                        raise ValueError("Values in string range must be integer.")
                        else:
                                hi = lo
                                stride = 1

                        l.append((lo, hi, stride))

                return l

        def __resort_list(self):
                """ Re-order the set of tuples in self.l to be montonic. """

                loVals = []                                                             # a list of the lo values
                for l in self.l:                                                # first produces the sorted indicies
                        loVals.append(l[0])
                ii = sorted(list(range(len(loVals))), key=loVals.__getitem__)

                lnew = []
                for i in ii:                                                    # rebuild a sorted list from indicies
                        lnew.append(self.l[i])
                self.l = lnew

        def __is_monotonic(self):
                """
                Return True if the tuple list self.l is monotonic, False otherwise.
                An empty range is assume to be monotonic.
                This method does not change any internal variables, e.g. no self.xxxx
                """

                try:    last_hi = int((self.l[0])[0]) - 1
                except: return True                                             # empty range is assumed monotonic.

                for (lo, hi, stride) in self.l:
                        if (hi < lo) or (stride < 1) or (last_hi >= lo):
                                return False
                        last_hi = hi
                return True

        def __tuple_list_to_str(self,l):
                """
                Convert a list of tuples to a string.
                This does NO compacting, just change the list l to a string.
                This method neither uses nor changes any internal variables, e.g. no self.xxxx

                EXAMPLE::
                        >>> print(self.__tuple_list_to_str([(0, 0, 1), (2, 3, 1), (4, 8, 2)]))
                        '0,2-3,4-8:2'
                """

                if not l: return ''

                range_string = ''
                for (lo, hi, stride) in l:
                        range_string += str(lo)
                        if hi>lo:                                                       # a lo-hi range
                                range_string += '-'+str(hi)
                                if stride>1:
                                        range_string += ':'+str(stride)
                        range_string += ','

                return range_string.rstrip(',')

        def __compact(self,l):
                """
                Return the most compact way of describing a string range.
                This method neither uses nor changes any internal variables, e.g. no self.xxxx

                EXAMPLE::
                        >>> ## sr = srange('0,2,3,4-8:2')
                        >>> l = self.__compact([(0, 0, 1), (2, 3, 1), (4, 8, 2)])
                        >>> print(l)
                        [(1, 4, 1), (6, 6, 1)]


                NOTE:
                        Compacting is always done during initialization.
                """
 
                if not l: return None

                # first, see if there are any single value runs of 3 or more that can be combined into a stride
                # only combine simple ranges when there are 3 numbers in a row with the same stride.
                lcombine = []                                                   # list or simple ranges to combine
                count = 0
                i = 0
                new_stride = -1
                for (lo, hi, stride) in l:
                        if not (lo==hi):                                        # reset for next search, start again
                                if count > 2:                                   # done with this run, save info
                                        lcombine.append((istart,istart+count-1,new_stride))
                                new_stride = -1
                                istart = -1
                                count = 0
                        elif count==1:
                                new_stride = lo - last_hi               # set the new stride
                                count = 2
                        elif count>1 and (lo-last_hi)==new_stride:
                                count += 1                                              # accumulate more in this stride
                        elif count > 2:                                         # done with this run, save info
                                lcombine.append((istart,istart+count-1,new_stride))
                                new_stride = -1                                 # reset for next search
                                count = 1
                                istart = i
                        else:                                                           # possibly start of a new stride
                                new_stride = -1                                 # reset for next search
                                count = 1
                                istart = i
                        i += 1
                        last_hi = hi

                if count > 2:                                                   # one more to append
                        lcombine.append((istart,istart+count-1,new_stride))

                ltemp = []                                                              # contains a shorter list using info in lcombine
                i0 = 0                                                                  # next one to do
                for (lc0, lc1, stride) in lcombine:             # move ranges from l to ltemp
                        for i in range(lc0-i0):                         # just copy [i0,lc0-1]
                                ltemp.append(l[i+i0])
                        lo = (l[lc0])[0]                               
                        hi = (l[lc1])[1]
                        ltemp.append((lo,hi,stride))
                        i0 = lc1+1

                for i in range(len(l)-i0):                              # move any remaining simple ranges from l to ltemp
                        ltemp.append(l[i+i0])

                # second, see if you can concatenate any simple ranges having the same stride
                # only combine ranges if one of them has hi>lo, do not combine two single number ranges.
                lnew = []
                (last_lo, last_hi, last_stride) = ltemp[0]
                last_single = last_lo==last_hi
                for (lo, hi, stride) in ltemp:
                        single = lo==hi
                        if lo==last_lo:                                                                                                 # the first one of ltemp[0], skip this
                                continue
                        elif single and (not last_single) and last_hi+last_stride == lo:# last complex joins current single
                                last_hi = hi
                        elif (not single) and last_single and last_hi+stride ==lo:              # last single joins current complex
                                last_hi, last_stride, last_single = (hi, stride, False)         # re-set last (last_lo not changed)
                        elif (not single) and (not last_single) and last_hi+stride==lo and stride==last_stride: # join two complex with same stride
                                last_hi = hi
                        else:
                                lnew.append((last_lo,last_hi,last_stride))                                      # append last
                                last_lo, last_hi, last_stride = (lo, hi, stride)                        # re-set last to current
                                last_single = last_lo==last_hi

                lnew.append((last_lo,last_hi,last_stride))                                                      # append the last one
                return lnew