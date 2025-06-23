import socket
import threading
import math
import struct
import os
import uuid
#importando constanntes que não são definidas aqui
from utils_constants import BUFFER_SIZE, HEADER_SIZE, MAX_SIZE_DATA, TYPE_HI, TYPE_BYE, TYPE_SEGMENT, TYPE_COMPLETE


#classe para armazenar o contexto do cliente
class ClientContext:

    def __init__(self):

        self.client_socket = None
        self.username = ""
        self.connected = False
        self.client_ip = "0.0.0.0"
        self.client_port = 0
        #dicionario para reconstruir as mensagens que vem fragmentadas do servidor
        #{ message_hash_id: {parts, received_count, total_seg } }
        self.segments_from_server_buffer = {}

        self.SERVER_HOST = '127.0.0.1' #localhost, servidor e clientes na  mesma maquina
        self.SERVER_PORT = 65432 #porta alta, para eviter conflitos

context_client = ClientContext() #instância para acessar as variáveis globais


#funcoes de envio

def send_packet(bytes_data, message_hash_id, num_seg, total_seg, type_msg):
    #empacota os dados com um cabeçalho simples e envia para o servidor

    header = struct.pack(
        '!BIIL',
        type_msg, #1 byte - tipo da mensagem
        num_seg, #4 bytes - numero do fragmento
        total_seg, #4 bytes - total de fragmentos
        message_hash_id #4 bytes - hash do ID da mensagem
    )
    packet = header+bytes_data
    
    context_client.client_socket.sendto(packet, (context_client.SERVER_HOST, context_client.SERVER_PORT))


def send_to_chat(content_message):
    #converte a mensagem para um arquivo .txt temporário
    #depois lê seu conteúdo, fragmenta e envia para o servidor.

    if not context_client.connected:
        print("antes de se conversar, é preciso se conectar com o comando 'hi, meu nome eh <nome>'")
        return

    #gera uma sequencia aleatória e praticamente única de 128 bits, mas o hex conerte em haxadecial
    tempfile_name = f"temp_client_msg_{uuid.uuid4().hex}.txt"
    
    with open(tempfile_name, "w") as f:
        f.write(content_message)
    with open(tempfile_name, "r") as f:
        file_content = f.read()

    bytes_full_message = file_content.encode()
    message_hash_id = uuid.uuid4().int % (2**32 - 1) #gera um identificador para a mensagem completa

    if len(bytes_full_message) <= MAX_SIZE_DATA:
        send_packet(bytes_full_message, message_hash_id, 0, 1, TYPE_COMPLETE)
        print("mensagem enviada sem fragmentação")

    else:
        #determinar quantos segmentos são necessários
        num_fragments = math.ceil(len(bytes_full_message)/MAX_SIZE_DATA)

        #forma os pacotes de dados fragmentados
        for i in range(num_fragments):
            start = i*MAX_SIZE_DATA
            end = min((i+1) * MAX_SIZE_DATA, len(bytes_full_message))
            bytes_fragment = bytes_full_message[start:end]
            
            send_packet(bytes_fragment, message_hash_id, i, num_fragments, TYPE_SEGMENT)
      
    #limpa o arquivo temporario     
    if os.path.exists(tempfile_name):
        os.remove(tempfile_name)

#funcao de recebimento

def receive_messages():

    while context_client.connected:

        #para receber os dados que vem do servidor
        packet, _ = context_client.client_socket.recvfrom(BUFFER_SIZE)
        
        #desempacota o cabeçalho do pacote recebido
        type_msg = struct.unpack('!B', packet[0:1])[0]
        num_seg = struct.unpack('!I', packet[1:5])[0]
        total_seg = struct.unpack('!I', packet[5:9])[0]
        message_hash_id = struct.unpack('!L', packet[9:HEADER_SIZE])[0]

        #extrai apenas a parte util (mensagem) do pacote
        data_bytes = packet[HEADER_SIZE:]

        #verifica se o tipo da mensagem é válido
        if type_msg == TYPE_HI:
            print(data_bytes.decode())

        elif type_msg == TYPE_BYE:
            print(data_bytes.decode())

        elif type_msg == TYPE_SEGMENT or type_msg == TYPE_COMPLETE:

            #se a mensagem for fragmentada ou completa, armazena no buffer
            if message_hash_id not in context_client.segments_from_server_buffer:
                context_client.segments_from_server_buffer[message_hash_id] = {
                    "parts": [None] * total_seg,
                    "received_count": 0,
                    "total_seg": total_seg
                }
            
            #adiciona o fragmento recebido no buffer e evita duplicacao
            if context_client.segments_from_server_buffer[message_hash_id]["parts"][num_seg] is None:
                context_client.segments_from_server_buffer[message_hash_id]["parts"][num_seg] = data_bytes.decode()
                context_client.segments_from_server_buffer[message_hash_id]["received_count"] += 1

            #se for o pacote completo, imprime a mensagem completa
            if context_client.segments_from_server_buffer[message_hash_id]["received_count"] == total_seg:
                full_content_message = "".join(context_client.segments_from_server_buffer[message_hash_id]["parts"])
                print(full_content_message)
                #remove a entrada no dicionario
                del context_client.segments_from_server_buffer[message_hash_id]
