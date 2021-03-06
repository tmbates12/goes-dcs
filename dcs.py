import sys
import re
import binascii
import datetime
import codecs
import argparse



# https://dcs1.noaa.gov/documents/HRIT%20DCS%20File%20Format%20Rev1.pdf - Page 5 - 3.3.1.4.
def bcd_to_date(data):
	year = format(data[6],'02x')                                     # Last 2 Digits of Year
	day = format(data[5],'x') + format(data[4] >> 4,'x')             # Julian Day
	hour = format(data[4] & 0xF, 'x') + format(data[3] >> 4, 'x') 
	minute = format(data[3] & 0xF, 'x') + format(data[2] >> 4, 'x')
	seconds = format(data[2] & 0xF,'x') + format(data[1] >> 4, 'x')
	milsec =  format(data[1] & 0xF, 'x') + format(data[0], '02x')    # Fractions of a second
	date = datetime.datetime.strptime(year+day,'%y%j').date()        # Convert to date object to parse Julian Day
	date_str = date.strftime('%m/%d/%Y')
	return '{} {}:{}:{}.{} UTC'.format(date_str,hour,minute,seconds,milsec)

# Abnormal Received Messages Flags
# https://dcs1.noaa.gov/documents/HRIT%20DCS%20File%20Format%20Rev1.pdf - Page 5 - 3.3.1.2.
def parse_arm(flag_byte): 
		text = ''
		if flag_byte & 0b1: # Address Corrected
			text += 'A' 
		if (flag_byte & 0b10) >> 1: # Bad/Non-Correctable Address
			text += 'B'
		if (flag_byte & 0b100) >> 2: # Address Invalid
			text += 'I'
		if (flag_byte & 0b1000) >> 3: # PDT Incomplete
			text += 'N'
		if (flag_byte & 0b10000) >> 4: # Overlapping Time Error
			text += 'T'
		if (flag_byte & 0b100000) >> 5: # Unexpected Message
			text += 'U'
		if (flag_byte & 0b1000000) >> 6: # Wrong Channel
			text += 'W'
		if 'M' not in text:
			text += 'G'
		return text


# NOAA DCS Pseudo-binary encoding: https://www.noaasis.noaa.gov/DCS/docs/DCPR_CS2_final_June09.pdf

def do_nothing(): # We don't need to encode messages
	pass

def pseudo_decode(binary: bytes) -> str: # Discard the Parity Bit, it's just ASCII
	return ''.join(chr((x & 0x7F) ) for x in binary), len(binary)

	
def pseudo_search_func(encoding_name):
    return codecs.CodecInfo(do_nothing, pseudo_decode, name='pesudo-binary')




def dcp_block(block_data,verbose):
	bauds = ['Undefined','100','300','1200']
	platforms = ['CS1', 'CS2']
	modulation_indicies = ['Unknown','Normal','High','Low']
	scids = ['Unknown','GOES-East','GOES-West','GOES-Central','GOES-Test'] # Spacecraft ID's

	blk_len = int.from_bytes(block_data[0x01:0x03],byteorder='little')
	seq_num = int.from_bytes(block_data[0x03:0x06],byteorder='little')
		
	flags = block_data[0x06]
	baud = bauds[(flags & 0b111)]                 # B0-B2 of flags defines the DCP Data Rate
	platform = platforms[(flags & 0b1000) >> 3]   # B3 is the platform type
	rx_parity = bool((flags & 0b10000) >> 4)      # Presence of Parity Errors in DCP Data

	arm_flags = block_data[0x07] # Abnormal Received Messages Flags
	arm_text = parse_arm(arm_flags)

	corrected_addr = hex(int.from_bytes(block_data[0x08:0x0C],byteorder='little'))
	carr_start = block_data[0x0C:0x13]
	msg_end = block_data[0x13:0x1A]
		
	sig_strength = int.from_bytes(block_data[0x1A:0x1C],byteorder='little') & 0x03FF
	freq_offset = int.from_bytes(block_data[0x1C:0x1E],byteorder='little')  & 0x3FFF
	if freq_offset > 8191: # 2's complement conversion
		freq_offset = freq_offset - 16384

	phs_noise = int.from_bytes(block_data[0x1E:0x20],byteorder='little')  & 0x01FFF
	mod_index = modulation_indicies[(int.from_bytes(block_data[0x1E:0x20],byteorder='little')  & 0x0C000) >> 14]
	good_phs = int.from_bytes(block_data[0x20:0x21],byteorder='little')
		
	channel  = int.from_bytes(block_data[0x21:0x23],byteorder='little') & 0x03FF
	spacecraft = int.from_bytes(block_data[0x21:0x23],byteorder='little') >> 12
	source_code = block_data[0x23:0x25].decode('ascii')
	source_sec = block_data[0x25:0x27].decode('ascii')
		
	codecs.register(pseudo_search_func)
	dcp_data_pseudo = codecs.decode(block_data[0x27:-2],encoding='pseudo-binary')
	dcp_crc16 = int.from_bytes(block_data[-2:],byteorder='little')
	calc_crc = binascii.crc_hqx(block_data[:-2],0xFFFF)


	print('\n----------[ DCP Block ]----------')
	if verbose:
		print('Header:')
		print('    Size: {} Bytes ({} Bytes of Data)'.format(blk_len,blk_len-41)) # 39 Bytes for Header, 2 Bytes for CRC
		print('    Seqeuence Number: {}'.format(seq_num))
		print('    Flags:')
		print('        Data Rate: {} Baud'.format(baud))
		print('        Platform: {}'.format(platform))
		print('        Parity Error? {}'.format(rx_parity))	
		print('    ARM Flags: {}'.format(arm_text))
		print('    Corrected Address: {}'.format(corrected_addr))
		print('    Carrier Start: {}'.format(bcd_to_date(carr_start)))
		print('    Message End: {}'.format(bcd_to_date(msg_end)))
		print('    Signal Strength: {}dBm EIRP'.format(sig_strength/10))
		print('    Frequency Offset: {}Hz'.format(freq_offset/10))
		print('    Phase Noise: {}° RMS'.format(phs_noise/100))
		print('    Modulation Index: {}'.format(mod_index))
		print('    Good Phase: {}%'.format(good_phs/2))
		print('    Channel: {}'.format(channel))
		print('    Spacecraft: {}'.format(scids[spacecraft]))
		print('    Source Code: {}'.format(source_code))
		print('    Source Secondary: {}'.format(source_sec))
		if dcp_crc16 == calc_crc:
				print('Block CRC: OK\n')
		else:
				print('CRC: FAILED\n')
	else:
		print('Corrected Address: {}'.format(corrected_addr))

	print('Data (Pseudo-Binary): \n{}'.format(dcp_data_pseudo))

def missed_block(block_data):
	bauds = ['Undefined','100','300','1200']
	scids = ['Unknown','GOES-East','GOES-West','GOES-Central','GOES-Test'] # Spacecraft ID's

	blk_len = int.from_bytes(block_data[0x01:0x03],byteorder='little')
	seq_num = int.from_bytes(block_data[0x03:0x06],byteorder='little')

	flags = block_data[0x06]
	baud = bauds[(flags & 0b111)]

	platform_addr = hex(int.from_bytes(block_data[0x07:0x0B],byteorder='little'))
	window_start = block_data[0x0B:0x12]
	window_end = block_data[0x12:0x19]

	channel  = int.from_bytes(block_data[0x21:0x23],byteorder='little') & 0x03FF
	spacecraft = int.from_bytes(block_data[0x21:0x23],byteorder='little') >> 12

	msg_crc16 = int.from_bytes(block_data[-2:],byteorder='little')
	calc_crc = binascii.crc_hqx(block_data[:-2],0xFFFF)

	print('\n-------[ Missed DCP Block ]-------')
	print('Header:')
	print('    Seqeuence Number: {}'.format(seq_num))
	print('    Flags:')
	print('        Data Rate: {} Baud'.format(baud))
	print('    Platform Address: {}'.format(platform_addr))
	print('    Window Start: {}'.format(bcd_to_date(window_start)))
	print('    Window End: {}'.format(bcd_to_date(window_end)))
	print('    Channel: {}'.format(channel))
	print('    Spacecraft: {}'.format(scids[spacecraft]))

	if msg_crc16 == calc_crc:
			print('Block CRC: OK\n')
	else:
			print('CRC: FAILED\n')


def main():

	argparser = argparse.ArgumentParser()
	argparser.add_argument("LRIT_File", help="An LRIT File containing a DCS Payload")
	argparser.add_argument("-v","--verbose", help="Prints all header and data information",action="store_true")
	args = argparser.parse_args()


	# Open the file
	with open(args.LRIT_File,'rb') as file:
		file_data = bytes(file.read())

	# Check LRIT File type
	assert (file_data[0x03] == 130),"Non-DCS LRIT File!"

	# Strip the HRIT Header
	locs = []
	for loc in re.finditer(b'pH',file_data):
		locs.append(loc.start())
	file_data = file_data[0x36:]

	# DCS File Header
	filename = file_data[0x0:0x20].decode('ascii')
	file_size = int(file_data[0x20:0x28].decode('ascii'))
	file_source = file_data[0x28:0x2C].decode('ascii')
	file_type = file_data[0x2C:0x30].decode('ascii')

	print('----------[ DCS Header Info ]----------')
	print('Filename: {}'.format(filename))
	print('File Size: {} Bytes'.format(file_size))
	print('File Source: {}'.format(file_source))
	print('File Type: {}'.format(file_type))
	if binascii.crc32(file_data[0x0:0x3C]) == int.from_bytes(file_data[0x3C:0x40],byteorder='little'):
		print('CRC: OK\n')
	else:
		print('CRC: FAILED\n')


	block_offset = 0x40
	while block_offset < file_size-0x04:
		block_length = int.from_bytes(file_data[block_offset+1:block_offset+3],byteorder='little')
		block_bytes = file_data[block_offset:block_offset+block_length]
		block_id = int.from_bytes(block_bytes[0x00:0x01],byteorder='little')
		
		if block_id == 1:
			dcp_block(block_bytes,args.verbose)
		if block_id == 2 and args.verbose:
			missed_block(block_bytes)


		block_offset += block_length

if __name__ == '__main__':
    main()


	



