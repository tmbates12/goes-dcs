import sys
import re
import binascii
import datetime
import codecs



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
def odd_parity6(num):
	one_count = 0
	for i in range(0,5):
		one_count += (ascii6 >> i) & 0b1
	even_parity = one_count & 0b1 
	return int(not even_parity)

def do_nothing(): # We don't need to encode messages
	pass

def pseudo_decode(binary: bytes) -> str: # Discard the Parity Bit, it's just ASCII
	return ''.join(chr((x & 0x7F) ) for x in binary), len(binary)

	
def pseudo_search_func(encoding_name):
    return codecs.CodecInfo(do_nothing, pseudo_decode, name='pesudo-binary')




def dcpblock(block_data):
	blk_id = int.from_bytes(block_data[0x00:0x01],byteorder='little')
	if blk_id == 1:
		bauds = ['Undefined','100','300','1200']
		platforms = ['CS1', 'CS2']
		modulation_indicies = ['Unknown','Normal','High','Low']
		scids = ['Unknown','GOES-East','GOES-West','GOES-Central','GOES-Test'] # Spacecraft ID's

		blk_len = int.from_bytes(block_data[0x01:0x03],byteorder='little')
		seq_num = int.from_bytes(block_data[0x03:0x06],byteorder='little')
		
		flags = block_data[0x06]
		baud = bauds[(flags & 0b111)]                 # B0 of flags defines the DCP Data Rate
		platform = platforms[(flags & 0b1000) >> 3]   # B1 is the platform type
		rx_parity = bool((flags & 0b10000) >> 4)      # Presence of Parity Errors in DCP Data

		arm_flags = block_data[0x07] # Abnormal Received Messages Flags
		arm_text = parse_arm(arm_flags)

		corrected_addr = hex(int.from_bytes(block_data[0x08:0x0C],byteorder='little'))
		carr_start = block_data[0x0C:0x13]
		msg_start = block_data[0x13:0x1A]
		
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
		calc_crc = binascii.crc_hqx(block_data[0x0:-0x02],0xFFFF)

		print('\n----------[ DCP Block ]----------')
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
		print('    Message End: {}'.format(bcd_to_date(msg_start)))
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
			print('    Block CRC: OK\n')
		else:
			print('    CRC: FAILED\n')
		print('Data (Pseudo-Binary): \n{}'.format(dcp_data_pseudo))


def main():
	print('DCS Decoder - Taylor Bates\n')

	# Open the file
	with open(sys.argv[1],'rb') as file:
		file_data = bytes(file.read())
		locs = []

	# Strip the HRIT Header
	for loc in re.finditer(b'pH',file_data):
		locs.append(loc.start())
	file_data = file_data[locs[1]:]

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
		dcpblock(file_data[block_offset:block_offset+block_length])
		block_offset = block_offset + block_length

if __name__ == '__main__':
    main()


	



