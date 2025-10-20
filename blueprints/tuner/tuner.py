import math
from common.common import write_log

def calc_shh_coefficients(t1, t2, t3, r1, r2, r3, units='F'):
	try: 
		if units=='F':
			# Convert Temps from Fahrenheit to Kelvin
			t1 = ((t1 - 32) * (5 / 9)) + 273.15
			t2 = ((t2 - 32) * (5 / 9)) + 273.15
			t3 = ((t3 - 32) * (5 / 9)) + 273.15
		else:
			# Convert Temps from Celsius to Kelvin
			t1 = t1 + 273.15
			t2 = t2 + 273.15
			t3 = t3 + 273.15

		# https://en.wikipedia.org/wiki/Steinhart%E2%80%93Hart_equation

		# Step 1: L1 = ln (R1), L2 = ln (R2), L3 = ln (R3)
		l1 = math.log(r1)
		l2 = math.log(r2)
		l3 = math.log(r3)

		# Step 2: Y1 = 1 / T1, Y2 = 1 / T2, Y3 = 1 / T3
		y1 = 1 / t1
		y2 = 1 / t2
		y3 = 1 / t3

		# Step 3: G2 = (Y2 - Y1) / (L2 - L1) , G3 = (Y3 - Y1) / (L3 - L1)
		g2 = (y2 - y1) / (l2 - l1)
		g3 = (y3 - y1) / (l3 - l1)

		# Step 4: C = ((G3 - G2) / (L3 - L2)) * (L1 + L2 + L3)^-1
		c = ((g3 - g2) / (l3 - l2)) * math.pow(l1 + l2 + l3, -1)

		# Step 5: B = G2 - C * (L1^2 + (L1*L2) + L2^2)
		b = g2 - c * (math.pow(l1, 2) + (l1 * l2) + math.pow(l2, 2))

		# Step 6: A = Y1 - (B + L1^2*C) * L1
		a = y1 - ((b + (math.pow(l1, 2) * c)) * l1)
	except:
		event = 'ERROR: Failed to calculate Steinhart-Hart coefficients.'
		write_log(event)
		a = 0
		b = 0
		c = 0
	return(a, b, c)


def calc_shh_chart(a, b, c, units='F', temp_range=220, tr_points=[]):
	'''
	Based on SHH Coefficients determined during tuning, show Temp (x) vs. Tr (y) chart
	'''

	labels = []

	for label in range(0, temp_range, temp_range//20):
		labels.append(label)

	chart_data = []

	for T in labels:
		R = temp_to_tr(T, a, b, c, units=units)
		if R != 0:
			chart_data.append({'x': int(T), 'y': int(R)})
		else:
			# Error/Exception occurred calculating the temperature, break and return
			chart_data = []
			break

	return labels, chart_data

def temp_to_tr(temp, a, b, c, units='F'):
	'''
	# Not recommended for use, as it commonly produces a complex number
	'''

	try: 
		if units == 'F':
			temp_k = ((temp - 32) * (5 / 9)) + 273.15
		else:
			temp_k = temp + 273.15

		# https://en.wikipedia.org/wiki/Steinhart%E2%80%93Hart_equation
		# Inverse of the equation, to determine Tr = Resistance Value of the thermistor

		x = (a - (1 / temp_k)) / c
		y1 = math.pow((b/(3*c)), 3) 
		y2 = ((x*x)/4)
		y = math.sqrt(y1+y2)  # If the result of y1 + y2 is negative, this will throw an exception
		Tr = math.exp(math.pow(y - (x/2), (1/3)) - math.pow(y + (x/2), (1/3)))
	except: 
		Tr = 0

	return int(Tr)

def tr_to_temp(tr, a, b, c, units='F'):
	try:
		#Steinhart Hart Equation
		# 1/T = A + B(ln(R)) + C(ln(R))^3
		# T = 1/(a + b[ln(ohm)] + c[ln(ohm)]^3)
		ln_ohm = math.log(tr) # ln(ohms)
		t1 = (b * ln_ohm) # b[ln(ohm)]
		t2 = c * math.pow(ln_ohm, 3) # c[ln(ohm)]^3
		temp_k = 1/(a + t1 + t2) # calculate temperature in Kelvin
		temp_c = temp_k - 273.15 # Kelvin to Celsius
		temp_f = temp_c * (9 / 5) + 32 # Celsius to Fahrenheit
	except:
		temp_c = 0.0
		temp_f = 0
	if units == 'F': 
		return int(temp_f) # Return Calculated Temperature and Thermistor Value in Ohms
	else:
		return temp_c