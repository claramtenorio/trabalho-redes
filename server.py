import socket
import threading
import os
import utils_server #importando as funcoes auxiliares do cliente
#importando constanntes que não são definidas aqui
from utils_constants import BUFFER_SIZE, HEADER_SIZE, MAX_SIZE_DATA, TYPE_HI, TYPE_BYE, TYPE_SEGMENT, TYPE_COMPLETE

def server_main():

    #configuracao do servidor
    utils_server.conext_server.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    utils_server.conext_server.SERVER_HOST = SERVER_HOST
    utils_server.conext_server.SERVER_PORT = SERVER_PORT
    utils_server.conext_server.server_socket.bind((SERVER_HOST, SERVER_PORT))

    while True:
        #escuta e recebe pacotes
        datapacket, client_ad = server_socket.recvfrom(BUFFER_SIZE)
        #threads para processar os pacotes recebidos de usuarios diferentes
        threading.Thread(target=treat_packets_received, args=(datapacket, client_ad)).start()

server_main()
