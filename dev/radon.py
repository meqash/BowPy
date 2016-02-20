import numpy
import numpy as np
from numpy import dot
import math
from math import pi
import scipy as sp
from scipy import sparse

"""
 This program is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published
 by the Free Software Foundation, either version 3 of the License, or
 any later version.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details: http://www.gnu.org/licenses/
"""

def radon_inverse(t,delta,M,p,weights,ref_dist,line_model,inversion_model,hyperparameters):
	"""
	This function inverts move-out data to the Radon domain given the inputs:
	 -t        -- vector of time axis.
	 -delta    -- vector of distance axis.
	 -M        -- matrix of move-out data, ordered size(M)==[length(delta),length(t)].
	 -p        -- vector of slowness axis you would like to invert to.
	 -weights  -- weighting vector that determines importance of each trace.
	              set vector to ones for no preference.
	 -ref_dist -- reference distance the path-function will shift about.
	
	 -line_model, select one of the following options for path integration:
	     'linear'     - linear paths in the spatial domain (default)
	     'parabolic'  - parabolic paths in the spatial domain.
	
	 -inversion model, select one of the following options for regularization schema:
	     'L2'       - Regularized on the L2 norm of the Radon domain (default)
	     'L1'       - Non-linear regularization based on L1 norm and iterative
	                  reweighted least sqaures (IRLS) see Sacchi 1997.
	     'Cauchy'   - Non-linear regularization see Sacchi & Ulrych 1995
	
	 -hyperparameters, trades-off between fitting the data and chosen damping.
	
	Output radon domain is ordered size(R)==[length(p),length(t)].
	
	Known limitations:
	 - Assumes evenly sampled time axis.
	 - Assumes move-out data isn't complex.
	
	
	 References: Schultz, R., Gu, Y. J., 2012. Flexible Matlab implementation
	             of the Radon Transform.  Computers and Geosciences [In Preparation]
	
	             An, Y., Gu, Y. J., Sacchi, M., 2007. Imaging mantle 
	             discontinuities using least-squares Radon transform. 
	             Journal of Geophysical Research 112, B10303.
	
	 Author: R. Schultz, 2012
	 Translated to Python by: S. Schneider, 2016
	"""

	# Check for Data type of variables.
	if not type(t) == numpy.ndarray and type(delta) == ndarray:
		print( "Wrong input type of t or delta, must be numpy.ndarray" )
		raise TypeError
	
	if not type(hyperparameters) == list:
		print( "Wrong input type of mu, must be list" )
		raise TypeError

	# Define some array/matrices lengths.
	it=t.size
	iF=int(math.pow(2,nextpow2(it)+1)) # Double length
	iDelta=delta.size
	ip=len(p)
	iw=len(weights)

	#Exit if inconsistent data is input.
	if not M.shape == (iDelta, it):
		print("Dimensions inconsistent!\nShape of M is not equal to (len(delta),len(t)) \nShape of M = (%i , %i)\n(len(delta),len(t)) = (%i, %i) \n" % (M.shape[0],  M.shape[1], iDelta, it) )
		R=0
		return(R)
	if not iw == iDelta:
		print("Dimensions inconsistent!\nlen(delta) ~= len(weights)\nlen(delta) = %i\nlen(weights) = %i\n" % (iDelta, iw))
		R=0
		return(R)

	#Exit if improper hyperparameters are entered.
	if inversion_model == "L1" or inversion_model == "Cauchy":
		if not len(hyperparameters == 2):
			print("Improper number of trade-off parameters\n")
			R=0
			return(R)
	else: #The code's default is L2 inversion.
		if not len(hyperparameters) == 1:
			print("Improper number of trade-off parameters\n")
			R=0
			return(R)

	#Preallocate space in memory.
	R=np.zeros((ip,it)) #ok<NASGU>
	Rfft=np.zeros((ip,iF)) + 0j
	A=np.zeros((iDelta,ip)) + 0j
	Tshift=A
	AtA=np.zeros((ip,ip)) + 0j
	AtM=np.zeros((ip,1)) + 0j
	Ident=np.identity(ip)

	#Define some values
	Dist_array=delta-ref_dist
	dF=1./(t[0][0]-t[0][1])
	Mfft=np.fft.fft(M,iF,1)
	W=sparse.spdiags(weights.conj().transpose(), 0, iDelta, iDelta).A
	
	dCOST=0.
	COST_curv=0.
	COST_prev=0.

	#Populate ray parameter then distance data in time shift matrix.
	for j in range(iDelta):
		if line_model == "parabolic":
			Tshift[j]=p
		else: #Linear is default
			Tshift[j]=p
	
	for k in range(ip):
		if line_model == 'parabolic':
			Tshift[:,k]=(2. * ref_dist * Tshift[:,k] * Dist_array.conj().transpose()) + (Tshift[:,k] * (Dist_array**2).conj().transpose())
		else: #Linear is default
			Tshift[:,k]=Tshift[:,k] * Dist_array[0].conj().transpose()

	# Loop through each frequency.
	for i in range( int(math.floor((iF+1)/2)) ):

		# Make time-shift matrix, A.
		f = ((float(i)/float(iF))*dF)
		A = np.exp( (0.+1j)*2*pi*f * Tshift )

		# M = A R ---> AtM = AtA R
		# Solve the weighted, L2 least-squares problem for an initial solution.
		AtA = dot( dot(A.conj().transpose(), W), A )
		AtM = dot( A.conj().transpose(), dot( W, Mfft[:,i] ) )
		mu = abs(np.trace(AtA)) * hyperparameters[0]
		Rfft[:,i] = sp.linalg.solve((AtA + mu*Ident), AtM)

		#Non-linear methods use IRLS to solve, iterate until convergence to solution.
		if inversion_model == "Cauchy" or inversion_model == "L1":
			
			#Initialize hyperparameters.
			b=hyperparameters[1]
			lam=mu*b

			#Initialize cost functions.
			dCOST = float("Inf")
			if inversion_model == "Cauchy":
				COST_prev = np.linalg.norm( Mfft[:,i] - dot(A,Rfft[:,i]), 2 ) + lam*sum( np.log( abs(Rfft[:,i]**2 + b) ) )
			elif inversion_model == "L1":
				COST_prev = np.linalg.norm( Mfft[:,i] - dot(A,Rfft[:,i]), 2 ) + lam*np.linalg.norm( abs(Rfft[:,i]+1), 1 )
			itercount=1
			
			#Iterate until negligible change to cost function.
			while dCost > 0.001 and itercount < 10:
				
				#Setup inverse problem.
				if inversion_model == "Cauchy":
					Q = sparse.spdiags( 1./( abs(Rfft[:,i]**2) + b), 0, ip, ip).A
				elif inversion_model == "L1":
					Q = sparse.spdiags( 1./( abs(Rfft[:,i]) + b), 0, ip, ip).A
				Rfft[:,i]=sp.linalg.solve( ( lam * Q + AtA ), AtM )
				
				#Determine change to cost function.
				if inversion_model == "Cauchy":
					COST_cur = np.linalg.norm( Mfft[:,i]-A*Rfft[:,i], 2 ) + lam*sum( np.log( abs(Rfft[:,i]**2 + b )-np.log(b) ) )
				elif inversion_model == "L1":
					COST_cur = np.linalg.norm( Mfft[:,i]-A*Rfft[:,i], 2 ) + lam*np.linalg.norm( abs(Rfft[:,i]+1) + b, 1 )
				dCOST = 2*abs(COST_cur - COST_prev)/(abs(COST_cur) + abs(COST_prev))
				COST_prev = COST_cur
				
				itercount += 1

			#Assuming Hermitian symmetry of the fft make negative frequencies the complex conjugate of current solution.
		if not i == 0:
			Rfft[:,iF-i] = Rfft[:,i].conjugate()

	R = np.fft.ifft(Rfft, iF)
	R = R[:,0:it]

	return(R)

def radon_forward(t,p,R,delta,ref_dist,line_model):
	"""
	This function applies the time-shift Radon operator A, to the Radon 
	domain.  Will calculate the move-out data, given the inputs:
	 -t        -- vector of time axis.
	 -p        -- vector of slowness axis you would like to invert to.
	 -R        -- matrix of Radon data, ordered size(R)==[length(p),length(t)].
	 -delta    -- vector of distance axis.
	 -ref_dist -- reference distance the path-function will shift about.

	 -line_model, select one of the following options for path integration:
		 'linear'     - linear paths in the spatial domain (default)
		 'parabolic'  - parabolic paths in the spatial domain.

	Output spatial domain is ordered size(M)==[length(delta),length(t)].

	Known limitations:
	 - Assumes evenly sampled time axis.
	 - Assumes Radon data isn't complex.


	 References: Schultz, R., Gu, Y. J., 2012. Flexible Matlab implementation 
		         of the Radon Transform.  Computers and Geosciences [In Preparation]

		         An, Y., Gu, Y. J., Sacchi, M., 2007. Imaging mantle 
		         discontinuities using least-squares Radon transform. 
		         Journal of Geophysical Research 112, B10303.

	 Author: R. Schultz, 2012
	 Translated to Python by: S. Schneider, 2016
	"""

	# Check for Data type of variables.
	if not type(t) == numpy.ndarray and type(delta) == ndarray:
		print( "Wrong input type of t or delta, must be numpy.ndarray" )
		raise TypeError
	
	if not type(hyperparameters) == list:
		print( "Wrong input type of mu, must be list" )
		raise TypeError

	it=t.size
	iF=int(math.pow(2,nextpow2(it)+1)) # Double length
	iDelta=delta.size
	ip=len(p)
	iw=len(weights)

	#Exit if inconsistent data is input.
	if not R.shape == (ip, it):
		print("Dimensions inconsistent!\nShape of M is not equal to (len(delta),len(t)) \nShape of M = (%i , %i)\n(len(delta),len(t)) = (%i, %i) \n" % (M.shape[0],  M.shape[1], iDelta, it) )
		M=0
		return(M)

	#Preallocate space in memory.
	Mfft = np.zeros((iDelta, iF))
	A = np.zeros((iDelta, ip))
	Tshift = A

	#Define some values.
	Dist_array=delta-ref_dist
	dF=1./(t[0][0]-t[0][1])
	Rfft=np.fft.fft(R,iF,1)

	#Populate ray parameter then distance data in time shift matrix.
	for j in range(iDelta):
		if line_model == "parabolic":
			Tshift[j]=p
		else: #Linear is default
			Tshift[j]=p
	
	for k in range(ip):
		if line_model == 'parabolic':
			Tshift[:,k]=(2. * ref_dist * Tshift[:,k] * Dist_array.conj().transpose()) + (Tshift[:,k] * (Dist_array**2).conj().transpose())
		else: #Linear is default
			Tshift[:,k]=Tshift[:,k] * Dist_array[0].conj().transpose()

	# Loop through each frequency.
	for i in range( int(math.floor((iF+1)/2)) ):

		# Make time-shift matrix, A.
		f = ((float(i)/float(iF))*dF)
		A = np.exp( (0.+1j)*2*pi*f * Tshift )
		
		# Apply Radon operator.
		Mfft[:,i]=dot(A, Rifft[:,i])

		# Assuming Hermitian symmetry of the fft make negative frequencies the complex conjugate of current solution.
		if not i == 0:
			Mfft[:,iF-i] = Mfft[:,i].conjugate()

	M = np.fft.ifft(Mfft, iF)
	M = M[:,0:it]		

	return(M)



def nextpow2(i):
	#See Matlab documentary
	n = 1
	count = 0
	while n < abs(i):
		n *= 2
		count+=1
	return count