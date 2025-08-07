import datetime
import zlib

def get_current_time():
    #para pegar a data e a hora e colocar ela na mensagem
    return datetime.datetime.now().strftime("%H:%M:%S %d/%m/%Y")

def calculate_checksum(data):
    return zlib.crc32(data) & 0xFFFF

def verify_checksum(data, received_checksum):
    calculated = calculate_checksum(data)
    return calculated == received_checksum
