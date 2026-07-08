#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# LauePattern.py
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
import time
import numpy as np
from JZTLaueSim.JZTunits import UnitsJZTdefault as units, ConvertTemperatureUnits
from JZTLaueSim.JZTutil import hkl2str, JZTtesting, niceDeltaDateTime
# from symrange import symrange
import JZTLaueSim.LatticeBase as LatticeBase
import JZTLaueSim.Lattice as Lattice
from JZTLaueSim.IgorSupport import Wave1D

NaN = float('nan')
NA = 6.022140857e23					# Avagadro's number
hc_keVnm = 1.2398419739				# h*c (keV-nm)
re_nm = 2.8179403227e-06			# Thompson, classical electron radius (nm)
NormalTemp_C = 20					# Normal Temperature (C), the default temperature
NormalTemp_K = NormalTemp_C + 273.15# Normal Temperature (K), the default temperature
Absolute0_C = -273.15				# absolute 0°C



class LauePattern(object):
    """ A Class that the defines a crystal lattice with all of its atoms.
        All parameters are forced to be consistent with the space group number.
        It can also calculate the structure factor F(hkl)
    """

    def __init__(self, Lattice, detector, hkl0=None, recip=None):
        """
        Initialize the Lattice instance.
        either include hkl0[] or recip[3][3], not both
            hkl0		np.matrix([h,k,l])
        recip		np.matrix([ [as0, bs0, cs0], [as1, bs1, cs1], [as2, bs2, cs2] ] ),  not Lattice.recip
        """

        if Lattice is None: raise ValueError('"Lattice" is None')
        try:dim = Lattice.dim
        except:	raise ValueError('Could not get Lattice.dim, or it is not 3')
        self.Lattice = Lattice

        if detector is None: raise ValueError('"detector" is None')
        self.detector = detector

        try:
            if recip.shape != (3,3): recip = None
        except: recip = None
        try:
            if hkl0.shape != (1,3): hkl0 = None
        except: hkl0 = None

        if not recip is None:		# orient using recip and calculate hkl0 (recip has precedence over hkl0)
            self.recip = recip		# recip is given

            ki = np.matrix([0,0,1])
            kf = detector.XYZcenter
            kfLen = np.linalg.norm(kf)
            kf = kf / kfLen

            qhat = (kf - ki)
            qLen = np.linalg.norm(qhat)
            qhat = qhat / qLen
            self.hkl0 = np.linalg.inv(recip).dot(qhat.T).T	# recip x hkl0 = q

        elif not hkl0 is None:		# no recip, calculate self.recip from hkl0
            self.hkl0 = hkl0
            raise ValueError('have not yet implemented calculating recip from hkl0')

        else:						# you need to specify orientation somehow
            raise ValueError('You must pass either a valid hkl0 or recip, both are None')

        self.Elo = 5
        self.Ehi = 30
        self.Emax = None
        self.Emin = None
        self.executionTime = None	# execution time (sec)
        self.cleanUpHKL()			# set self.hklClean
        self.spots = []
        self.hmax = self.kmax = self.lmax = None	# gets set in self.calc()


    def calc(self, ELO=None, EHI=None, hklMax=None, Nmax=200):
#if ELO >= 0: 
        self.Elo = ELO
        self.Ehi = EHI
    #		self.Elo = 5
    #		self.Ehi = 30
        #if EHI >= 0: self.Ehi = EHI
        ki = np.matrix([0,0,1.0])

        if not hklMax is None:
            try:
                hmax = hklMax[0]
                kmax = hklMax[1]
                lmax = hklMax[2]
            except: 
                raise ValueError('hklMax not a list or tuple, hklMax = %r' % (hklMax,))
        else:
            XYZ = self.detector.pixel2XYZ((self.detector.Nx-1)/2, self.detector.Ny-1)	# leading edge of detector
            thMax = math.atan2(XYZ.item((0,1)), XYZ.item((0,2))) / 2
            #print (self.Ehi)# 'thMax =',thMax * 180/math.pi,'   ',XYZ
            Qmax = 4*math.pi * math.sin(thMax) * self.Ehi/hc_keVnm	# Q = 4π sin(theta) / lambda
            # print 'Qmax =',Qmax
            hmax = int( math.floor( Qmax / (2*math.pi / self.Lattice.a)) )
            kmax = int( math.floor( Qmax / (2*math.pi / self.Lattice.b)) )
            lmax = int( math.floor( Qmax / (2*math.pi / self.Lattice.c)) )
    #			print 'h = ±%d, k = ±%d, l = ±%d,  (total = %d)' % (hmax,kmax,lmax,(2*hmax+1)*(2*kmax+1)*(2*lmax+1))

        self.hmax = hmax
        self.kmax = kmax
        self.lmax = lmax

        all_spots = []
        Natoms = len(self.Lattice.atoms)			# number of atoms
        Fmin = len(self.Lattice.atoms) * self.Lattice.allowed_F_N	# allowed, more than 0.01 electron/atom
        self.Emax = 0
        self.Emin = float('inf')
        N = m = 0
        done = False
        start = time.time()
        for l in range(-lmax,lmax+1):
            for k in range(-kmax,kmax+1):
                for h in range(-hmax,hmax+1):
                    m += 1
                    hkl = np.matrix([h,k,l])
                    qvec = self.recip.dot(hkl.T).T	# convert hkl --> qvec
                    qLen = np.linalg.norm(qvec)
                    if qLen == 0: continue

                    qhat = qvec / qLen
                    dot = qhat.item((0,2))
                    kf = ki - 2 * dot * qhat		# kf^ = ki^ - 2*(ki^ . q^)*q^
                    pixel = self.detector.XYZ2pixel(kf)	# convert kf --> (px,py)
                    if pixel is None: continue

                    sinTheta = -qhat.item((0,2))	# check energy
                    E = qLen*hc_keVnm / (4*math.pi * sinTheta)		# Q = 4π sin(theta)/lambda
                    if not (self.Elo<E and E<self.Ehi): continue	# E outside [Elo,Ehi]

                    d = 2*math.pi / qLen
                    FH = self.Lattice.Fstruct((h,k,l), keV=E)
                    Fmag = cmath.polar(FH)[0]
                    if not( Fmag > Fmin): continue					# skip if not allowed

                    F2 = Fmag*Fmag
                    EwPo = self.Lattice.EwPoCalc(d, F2, E)			# Kinematic Bragg, extended face,  Warren pg. 46, eqn 4.7
                    self.Emin = min(self.Emin,E)
                    self.Emax = max(self.Emax,E)

                    spot = LaueSpot(qhat, hkl, pixel, E, EwPo)
                    if not (spot is None): all_spots.append(spot)

                    N += 1
                    if N >= Nmax:
                        done = True
                        break

                if done: break						# leaves k loop
            if done: break							# leaves l loop
        self.executionTime = time.time() - start

        outSet = sorted(all_spots, reverse=True, key=lambda x: x.EwPo)	# set() removes duplicate spots
        out = list(outSet)

        self.spots = sorted(out, reverse=True, key=lambda x: x.EwPo)		# sort by decreasing EwPo
    #		print "\nend:  tested %d hkl's,   found %d initial spots   E in [%g, %g] keV  with %d unique spots in %s" % (m, N,self.Emin,self.Emax, len(self.spots), niceDeltaDateTime(self.executionTime))
        return self.spots							# return list of LaueSpot's


    def write(self, spots=None, fname=None):
        if spots is None: spots = self.spots
        outArray = []
        for spot in spots:
            ll = list(spot.pixel)
            ll.append(spot.keV)
            ll.append(spot.EwPo)
            outArray.append(tuple(ll))

        try:
            name = self.Lattice.desc
            if len(name) < 2: raise
        except:
            name = 'LauePattern'

        hstr = '%g,%g,%g' % (self.hklClean[0],self.hklClean[1],self.hklClean[2])
        note = self.Lattice.desc + ';' + 'Nx=2048;Ny=2048;pixel=200e-6;dist=0.511;tth=90;Erange=%g,%g' % (self.Elo, self.Ehi)
        note += ';hklMax=%d,%d,%d;hklCenter=%s' % (self.hmax, self.kmax, self.lmax, hstr)
        note += ';executionTime='+str(self.executionTime)
        wave = Wave1D(name, outArray, note=note)
        wname = wave.wname
        moreIgor  = 'X Display %s[*][1] vs %s[*][0]\r' % (wname,wname)
        moreIgor += 'X ModifyGraph width={Aspect,1}, mode=3, marker=19, tick=2, mirror=1, minor=1, lowTrip=0.001\r'
        moreIgor += 'X SetAxis left 0,2047\r'
        moreIgor += 'X SetAxis bottom 0,2047\r'
        moreIgor += 'X SetDimLabel 1,0,px,%s\r' % (wname,)
        moreIgor += 'X SetDimLabel 1,1,py,%s\r' % (wname,)
        moreIgor += 'X SetDimLabel 1,2,keV,%s\r' % (wname,)
        moreIgor += 'X SetDimLabel 1,3,EwPo,%s' % (wname,)
        wave.write(fname=fname, moreIgor=moreIgor)
    def writetxt(self, spots=None, fname=None):
        file1 = open("pythonSim_temp.txt","w")#append mode
        for ii in range(len(spots)):
            file1.write(str(spots[ii]) + '\n')

        file1.close()

    def __str__(self):
        """ Return string value for Lattice. """
        return str(self).encode('ascii', errors='backslashreplace')

    def __unicode__(self):
        name = self.Lattice.desc
        if len(name) < 1: name = 'unknown'
        det = self.detector.name
        if len(det) < 1: det = 'detector'
        out = 'Laue Pattern of "%s"  centered on  (%s)  trying [%g, %g]keV' % (name,hkl2str(self.hklClean,maxMag=1e-8), self.Elo,self.Ehi)
        out += u'\n' + str( self.detector )
        if not self.hmax is None:
            pmu = u'\u00B1'						# str greek ± symbol
            hklTotal = (2*self.hmax+1)*(2*self.kmax+1)*(2*self.lmax+1)
            out += '\nh = %s%d, k = %s%d, l = %s%d,  (total = %d)\n\n' % (pmu,self.hmax, pmu,self.kmax, pmu,self.lmax,hklTotal)
            if len(self.spots):
                out += ' hkl       pixlel    E(keV)       EwPo\n'
                for spot in self.spots: out += str(spot) + '\n'
                out += "\nend:  tested %d hkl's,   E in [%g, %g] keV  found %d unique spots in %s" % (hklTotal, self.Emin,self.Emax, len(self.spots), niceDeltaDateTime(self.executionTime))

        return out

    def cleanUpHKL(self):
        h = self.hkl0[0,0]
        k = self.hkl0[0,1]
        l = self.hkl0[0,2]
        hh = abs(h)
        kk = abs(k)
        ll = abs(l)
        if hh < 1e-6: hh = 1e12		# remove almost zeros
        if kk < 1e-6: kk = 1e12
        if ll < 1e-6: ll = 1e12
        fmin = min(hh,kk,ll)
        h /= fmin
        k /= fmin
        l /= fmin
        if abs(h-round(h)) < 1e-6: h = round(h)	# make almost integer an int
        if abs(k-round(k)) < 1e-6: k = round(k)
        if abs(l-round(l)) < 1e-6: l = round(l)
        self.hklClean = [h,k,l]



class LaueSpot(object):
    def __init__(self, qhat, hkl, pixel, keV, EwPo):
        try:
            if qhat.shape != (1,3): return None
            if hkl.shape != (1,3): return None
            if len(pixel) != 2: return None
            if keV <= 0: return None
            if EwPo <= 0: return None
        except: return None
        self.qhat = qhat
        self.hkl = hkl
        self.pixel = pixel
        self.keV = keV
        self.EwPo = EwPo


    def __hash__(self):
        """Override the default hash behavior"""
        qx = int( self.qhat.item(0,0) * 1e5 )
        qy = int( self.qhat.item(0,1) * 1e5 )
        qz = int( self.qhat.item(0,2) * 1e5 )
        return hash( (qx,qy,qz) )

    def __eq__(self,other):
        """checking equality"""
        if isinstance(other, self.__class__): return self.__hash__() == other.__hash__()
        return NotImplemented

    def __ne__(self, other):
        """checking inequality"""
        if isinstance(other, self.__class__): return not self.__eq__(other)
        return NotImplemented


    def __str__(self):
        """ Return string value for LaueSpot. """
        return str(self).encode('ascii', errors='backslashreplace')

    def __unicode__(self):
        out = '(' + hkl2str([self.hkl.item(0,0), self.hkl.item(0,1), self.hkl.item(0,2)]) + ')'
        out += u'  [%d, %d]' % self.pixel
    #		out += u',  %g keV,  EwPo=%g' % (self.keV, self.EwPo)
        out += u',  %g,   %g' % (self.keV, self.EwPo)
        return out



class detectorType(object):
    """ A Class that the defines a 2D detector.
        (Nx, Ny)	is number of pixels in x and y
        (dx, dy)	size of a pixel (m)
        dist		distance of detector from sample (m)
        tth			2θ of detector center (degree)
    """

    def __init__(self, Nx, Ny, dx, dy, R, P, name=''):
        try:
            if Nx <= 2: raise ValueError('Nx = ' + repr(Nx))
            if Ny <= 2: raise ValueError('Ny = ' + repr(Ny))
            Nx = round(Nx)
            Ny = round(Ny)

            if dx <= 0: raise ValueError('dx = ' + repr(dx))
            if dy <= 0: raise ValueError('dy = ' + repr(dy))

            #if dist <= 0: raise ValueError('dist = ' + repr(dist))
            #if tth < 0 or tth > 180: raise ValueError('tth = ' + repr(tth))
        except:
            return None

        self.name = name
        self.Nx = Nx
        self.Ny = Ny
        self.dx = dx
        self.dy = dy
        self.P = np.asarray([P[0],P[1],P[2]])
        #print(self.P)

        #c2th = math.cos(tth * math.pi/180)
        #s2th = math.sin(tth * math.pi/180)
        #self.rot = np.matrix([ [1,0,0], [0,c2th,s2th], [0,-s2th,c2th] ])	# used in pixel2XYZ()


        rotang = np.linalg.norm(R)#/np.pi*180; # in degrees
        #print(rotang)
        rotvect = R/np.linalg.norm(R);
        self.rot = np.matrix([[math.cos(rotang)+(1-math.cos(rotang))*(rotvect[0]**2), (1-math.cos(rotang))*rotvect[0]*rotvect[1]-math.sin(rotang)*rotvect[2], (1-math.cos(rotang))*rotvect[0]*rotvect[2]+math.sin(rotang)*rotvect[1]],
                              [(1-math.cos(rotang))*rotvect[1]*rotvect[0]+math.sin(rotang)*rotvect[2], math.cos(rotang)+(1-math.cos(rotang))*(rotvect[1]**2),  (1-math.cos(rotang))*rotvect[1]*rotvect[2]-math.sin(rotang)*rotvect[0]],
                              [(1-math.cos(rotang))*rotvect[2]*rotvect[0]-math.sin(rotang)*rotvect[1], (1-math.cos(rotang))*rotvect[2]*rotvect[1]+math.sin(rotang)*rotvect[0], math.cos(rotang)+(1-math.cos(rotang))*(rotvect[2]**2)]
                              ]);


        #print(self.rot)
        
        self.pCenter = ((self.Nx-1)/2, (self.Ny-1)/2)	# center of detector (pixels)
        
        self.XYZcenter = self.pixel2XYZ(self.pCenter[0], self.pCenter[1])	# center of detector in beam-line corrdinates
        
        #print ('self.pCenter =',self.pCenter)
        #print ('self.XYZcenter =',self.XYZcenter)


    def pixel2XYZ(self, px, py):					# given (px,py), compute beam-line coords XYZ
        try:
            px = double(px)
            py = double(py)
        except:
            ValueError('cannot interpret pixel:' + repr(px) + '  ' + repr(py))
        if px < 0 or px >= self.Nx: return None		# must lie on detector
        if py < 0 or py >= self.Ny: return None

        # x' and y' (requiring z'=0), detector starts centered on origin and perpendicular to z-axis
        xp = (px - 0.5*(self.Nx-1)) * self.dx		# (x' y' z'), position on detector
        yp = (py - 0.5*(self.Ny-1)) * self.dy
        # print 'pixel (%g, %g)  -->  xp = %g,  yp = %g' % (px,py,xp,yp)

        xp += self.P[0]								# translate by P
        yp += self.P[1]
        zp =  self.P[2]
        xyz = np.matrix([xp,yp,zp])					# position in detector frame
        XYZ = self.rot.dot(xyz.T).flatten()
        return XYZ


    def XYZ2pixel(self, XYZ):						# given np.matrix([x,y,z]) in beam-line coords, compute pixel on detector it points to
        try:
            if XYZ.shape != (1,3): return None
        except: return None
        xyz = np.linalg.inv(self.rot).dot(XYZ.T).T	# un-rotate

        z = xyz.item(0,2)
        if z <= 0: return None						# does not point to detector
        scale = self.P[2] / z						# scale xyz so that z = dist
        xyz = xyz * scale

        xp = xyz.item(0,0) - self.P[0]				# un-translate by P[]
        yp = xyz.item(0,1) - self.P[1]

        px = xp / self.dx + 0.5*(self.Nx-1) 		# (x' y' z') position on detector --> pixel
        py = yp / self.dy + 0.5*(self.Ny-1)

        if px < 0 or px >= (self.Nx-1): return None	# must land on detector
        if py < 0 or py >= (self.Ny-1): return None

        return (px, py)


    def __str__(self):
        """ Return string value for Lattice. """
        return str(self).encode('ascii', errors='backslashreplace')

    def __unicode__(self):
        degree = u'\u00B0'					# unicode degree symbol
        Gmu = u'\u03Bc'						# unicode greek µ symbol
        Gtheta = u'\u03B8'					# unicode greek µ symbol
        out = "Detector: "
        if len(self.name):	out += '"' + self.name + u'"  '
        else:				out += u''
        out += u'(%d, %d)pixels,  ' % (self.Nx, self.Ny)
        out += u'(%g, %g)%sm,   ' % (self.dx * 1e6, self.dy * 1e6, Gmu)
        out += u'at %g mm  and centered at 2%s = %g%s' % (self.dist*1e3, Gtheta, self.tth, degree)
        return out




if __name__ == '__main__':
    """
    Main function for Lattice.py.

    Test cases for Lattice class to verify correct behavior.
    """
    testing = JZTtesting(__file__)

    atomSi = LatticeBase.atomXtal('Si', (0,0,0), DebyeT=645)
    SiXtal = Lattice.Lattice('227:1', (0.54310206,0,0, 0,0,0), desc='Silicon',atoms=(atomSi,))


    if testing.doit('check class detectorType{ }'):						#  2**0 = 1
        printIt = testing.unique
        detector = detectorType(Nx=2048, Ny=2048, dx=200e-6, dy=200e-6, dist=0.511, tth=90, name='Perkn-Elmer')
        print (unicode(detector))

        XYZ = detector.pixel2XYZ(1000,1001)
        print ('for pixel (1000,1001) --> XYZ =',XYZ)
        pixel = detector.XYZ2pixel(XYZ)
        print ('and back to pixel =',pixel)

        print (' ')
        XYZ = detector.pixel2XYZ(2000,0)
        print ('for pixel (2000,0) --> XYZ =',XYZ)
        pixel = detector.XYZ2pixel(XYZ)
        print ('and back to pixel =',pixel)

        print (' ')
        XYZ = detector.pixel2XYZ(0,2000)
        print ('for pixel (0,2000) --> XYZ =',XYZ)
        pixel = detector.XYZ2pixel(XYZ)
        print ('and back to pixel =',pixel)

        print (' ')
        XYZ = detector.pixel2XYZ(0,0)
        print ('for pixel (0,0) --> XYZ =',XYZ)
        pixel = detector.XYZ2pixel(XYZ)
        print ('and back to pixel =',pixel)


    if testing.doit('check class LauePattern{ }'):						#  2**1 = 2
        printIt = testing.unique
        P_ = np.array([-0.144183, 0.026808, 0.402341])
        R_ = np.array([-1.74964147, -0.72538764, -1.7707796])
        detector = detectorType(Nx=1024, Ny=1024, dx=200e-6, dy=200e-6, R=R_, P=P_, name='Perkn-Elmer')
        astar = 2*math.pi / SiXtal.a
        recip = np.identity(3) * astar
        LP = LauePattern(SiXtal, detector=detector, recip=recip)
        spots = LP.calc()
        print (' ')
        print (unicode(LP))
        #LP.write(spots)
        LP.writetxt(spots)
    #		LP.write(spots, wname="LauePatternSi")
    #		LP = LauePattern(SiXtal, detector=detector, hkl0=np.matrix([0,2,2]))
    #		print LP


    if testing.doit('check class LauePattern{ }'):						#  2**2 = 4
        printIt = testing.unique
        detector = detectorType(Nx=2048, Ny=2048, dx=200e-6, dy=200e-6, dist=0.511, tth=90, name='Perkin-Elmer')
        NdP5O14 = Lattice.Lattice(file='./materials/NdP5O14.xtal')
        recip = NdP5O14.recip

        # calculated hklMax = 52 35 36  from Ehi

        LP = LauePattern(NdP5O14, detector=detector, recip=recip)
        spots = LP.calc(ELO=5, EHI=16, Nmax=2000)
        print (unicode(LP))
        print (' ')
        LP.write(spots)


    testing.ending()
