import socket
import threading
import math
import struct
import uuid
import os

#configuracoes comuns
BUFFER_SIZE = 1024

#tamanho do cabecalho
#13 bytes = 1 byte de tipo da mensagem, 4 bytes do hash do id da mensagem,
#4 bytes para o nem fragmento e 4 bytes para indicar o total de fragmento
HEADER_SIZE = 13
#tamanho maximo dos dados que podem ser enviados em uma mensagem
MAX_DATA_SIZE = BUFFER_SIZE - HEADER_SIZE

#tipos de mensagens, para o cabecalho
#respectivamente - conectar, desconectar, msg fragmentada, msg toda
TYPE_HI = 0
TYPE_BYE = 1
TYPE_SEGMENT = 2
TYPE_COMPLETE = 3

#para conseguir o timestamp atual
from utils_common import get_current_time

#contexto do servidor
class ServerContext:
    def __init__(self):
        self.server_socket = None
        #dicionário que irá armazenar os clientes conectados
        #{ (client_ip, client_port): nome_usuario }
        self.connected_clients = {}
        #dicionario para reconstruir as mensagens que vem fragmentadas dos clientes
        self.segments_from_client_buffer = {}
        self.SERVER_HOST = '0.0.0.0'
        self.SERVER_PORT = 65432

context_server = ServerContext() #instância para acessar as variaveis globais

#funcoes auxiliares

def format_message(ip, port, username, content_message):
    #pegar o tempo para colocar na mensagem
    timestamp = get_current_time()
    #formatar a mensagem para o formato pedido no trabalho
    return f"{ip}:{port}/~{username}: {content_message} {timestamp}"

#funciona da mesma maneira que o do cliente
def send_to_client(data_bytes, client_ad, message_hash_id, num_seg, total_seg, type_msg):
    #similar a do utils.client
    header = struct.pack(
        '!BIIL',
        type_msg,
        num_seg,
        total_seg,
        message_hash_id
    )
    packet = header+data_bytes
    
    if len(packet) > BUFFER_SIZE:
        print(f"Aviso: Pacote para {client_ad} excede BUFFER_SIZE ({len(packet)} > {BUFFER_SIZE})")

    context_server.server_socket.sendto(packet, client_ad)

def broadcast_message(content_message, sender_ad):
    #se for preciso, fragmenta a mensagem e a envia para os clientes em seguida
    broadcast_hash_id = uuid.uuid4().int % (2**32 - 1) #mesmo que o que foi feito em utils.client
    num_fragments = math.ceil(len(content_message)/MAX_DATA_SIZE)

    #percorre todos os clientes conectados
    for client_ad, _ in list(context_server.connected_clients.items()):
        #para não enviar a mensagem de volta para o remetente
        if client_ad == sender_ad:
            continue
        #para enviar todos os fragmentos
        for i in range(num_fragments):
            start = i*MAX_DATA_SIZE
            end = min((i+1)*MAX_DATA_SIZE, len(content_message))
            data_seg = content_message[start:end]
            type_msg = TYPE_SEGMENT if num_fragments > 1 else TYPE_COMPLETE
            send_to_client(data_seg, client_ad, broadcast_hash_id, i, num_fragments, type_msg)


#para tratar as mensgens que sao enviadas pelos clientes
def treat_received_packets(packet_data, client_ad):

    #desempacota, assim como em utils.client
    type_msg = struct.unpack('!B', packet_data[0:1])[0]
    num_seg = struct.unpack('!I', packet_data[1:5])[0]
    total_seg = struct.unpack('!I', packet_data[5:9])[0]
    message_hash_id = struct.unpack('!L', packet_data[9:HEADER_SIZE])[0]
    data_bytes = packet_data[HEADER_SIZE:]

    #verifica o tipo da mensagem
    #mensagem de conexao
    if type_msg == TYPE_HI:
        #decodifica a mensagem para pegar o nome do usuário e o IP/porta do cliente
        parts = data_bytes.decode().split('|', 2)
        username = parts[0]
        client_ip = parts[1]
        client_port = int(parts[2])
        #cria a tupla para o endereço completo do cliente
        client_full_ad = (client_ip, client_port) 
        #adiciona o cliente ao dicionário de clientes conectados 
        context_server.connected_clients[client_ad] = username
        #avisa que o usuário entrou na sala
        alert_msg = f"{username} entrou na rodinha de conversa"
        broadcast_message(alert_msg.encode(), client_ad)

    #mensagem de saida
    elif type_msg == TYPE_BYE:
        leaving_user = data_bytes.decode()
        client_full_ad = None
        #para achar o endereço completo do cliente que está saindo
        for ad, uname in list(context_server.connected_clients.items()):
            if uname == leaving_user:
                client_full_ad = ad
                break
        #avisa que o usuário saiu da sala
        del context_server.connected_clients[client_full_ad]            
        alert_msg = f"{leaving_user} disse tchau tchau."
        broadcast_message(alert_msg.encode(), client_full_ad)

    #mensagem fragmentada ou completa
    elif type_msg == TYPE_SEGMENT or type_msg == TYPE_COMPLETE:

        current_user = context_server.connected_clients.get(client_ad)
        client_buffer_key = client_ad
        
        #assim como em utils.client, reconstroi a mensagem se precisar
        if client_buffer_key not in context_server.segments_from_client_buffer or context_server.segments_from_client_buffer[client_buffer_key]['msg_id_hash'] != message_hash_id:
            context_server.segments_from_client_buffer[client_buffer_key] = {
                'msg_id_hash': message_hash_id,
                'parts': [None] * total_seg,
                'received_count': 0,
                'total_seg': total_seg
            }

        #adiciona o fragmento recebido no buffer, evitando duplicação
        if context_server.segments_from_client_buffer[client_buffer_key]['parts'][num_seg] is None:
            context_server.segments_from_client_buffer[client_buffer_key]['parts'][num_seg] = data_bytes.decode()
            context_server.segments_from_client_buffer[client_buffer_key]['received_count'] += 1

        #se todos os fragmentos foram recebidos, reconstroi a mensagem completa
        if context_server.segments_from_client_buffer[client_buffer_key]['received_count'] == total_seg:
            full_content_message = "".join(context_server.segments_from_client_buffer[client_buffer_key]['parts'])
            del context_server.segments_from_client_buffer[client_buffer_key]

            #similar ao que ocorre em utils.clients
            tempfile_name = f"server_recv_msg_{uuid.uuid4().hex}.txt"
            with open(tempfile_name, "w") as f:
                f.write(full_content_message)
            with open(tempfile_name, "r") as f:
                read_content = f.read()
                #formata a mensagem para enviar aos clientes           
                formatted_message_clients = format_message(client_ad[0], client_ad[1], current_user, read_content)
                broadcast_message(formatted_message_clients.encode('utf-8'), client_ad)
            #limpa o arquivo temporário
            if os.path.exists(tempfile_name):
                os.remove(tempfile_name)
