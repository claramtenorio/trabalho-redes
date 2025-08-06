import socket
import threading
import math
import struct
import os
import uuid
from utils_common import calculate_checksum, verify_checksum
#configurações comuns
BUFFER_SIZE = 1024
#tamanho do cabecalho
#21 bytes = 1 byte de tipo da mensagem, 4 bytes do hash do id da mensagem,
#4 bytes para o num fragmento, 4 bytes para indicar o total de fragmento
#4 bytes para o seq_num, 2 bytes para o check_sum, 1 byte para o ack_flag
# e 1 byte para o is_ack
HEADER_SIZE = 21
#tamanho maximo dos dados que podem ser enviados em uma mensagem
MAX_DATA_SIZE = BUFFER_SIZE - HEADER_SIZE
#tipos de mensagens, para o cabecalho
#respectivamente - conectar, desconectar, msg fragmentada, msg toda
TYPE_HI = 0
TYPE_BYE = 1
TYPE_SEGMENT = 2
TYPE_COMPLETE = 3

TIMEOUT_SECONDS = 2.0
MAX_RETRIES = 5


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
        self.rdt_sender = None
        self.rdt_receiver = None

context_client = ClientContext() #instância para acessar as variáveis globais


#funcoes de envio

def send_packet(bytes_data, message_hash_id, num_seg, total_seg, type_msg):
    # # #empacota os dados com um cabeçalho simples e envia para o servidor

    # envio de pacote com RDT3.0
    if not context_client.rdt_sender:
        context_client.rdt_sender = RDTSender(
            context_client.client_socket, 
            (context_client.SERVER_HOST, context_client.SERVER_PORT)
        )
        
    context_client.rdt_sender.send_reliable(
        bytes_data, 
        message_hash_id, 
        num_seg, 
        total_seg, 
        type_msg
    )


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

    if len(bytes_full_message) <= MAX_DATA_SIZE:
        send_packet(bytes_full_message, message_hash_id, 0, 1, TYPE_COMPLETE)
        print("mensagem enviada sem fragmentação")

    else:
        #determinar quantos segmentos são necessários
        num_fragments = math.ceil(len(bytes_full_message)/MAX_DATA_SIZE)

        #forma os pacotes de dados fragmentados
        for i in range(num_fragments):
            start = i*MAX_DATA_SIZE
            end = min((i+1) * MAX_DATA_SIZE, len(bytes_full_message))
            bytes_fragment = bytes_full_message[start:end]
            
            send_packet(bytes_fragment, message_hash_id, i, num_fragments, TYPE_SEGMENT)
      
    #limpa o arquivo temporario     
    if os.path.exists(tempfile_name):
        os.remove(tempfile_name)

#funcao de recebimento

def receive_messages():

    if not context_client.rdt_receiver:
        context_client.rdt_receiver = RDTReceiver(context_client.client_socket)
        
    while True:
        try:
            #para receber os dados que vem do servidor
            packet, sender_addr = context_client.client_socket.recvfrom(BUFFER_SIZE)

            #processa o pacote recebido com RDT3.0
            rdt_result = context_client.rdt_receiver.process_packet(packet, sender_addr)
            
            if rdt_result is None:
                continue
            
            if rdt_result['type'] == 'ack':
                #processa o ACK recebido
                if context_client.rdt_sender:
                    context_client.rdt_sender.handle_ack(
                        rdt_result['seq_num'], 
                        rdt_result['checksum_ok']
                    )
                continue
            
            #se for um pacote de dados, extrai as informações
            type_msg = rdt_result['type_msg']
            message_hash_id = rdt_result['msg_hash_id']
            num_seg = rdt_result['num_seg']
            total_seg = rdt_result['total_seg']
            data_bytes = rdt_result['data']

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
        except OSError:
            # Socket has been closed, so we can exit the loop.
            break

class RDTSender:
    def __init__(self, socket_obj, dest_addr):
        self.socket = socket_obj
        self.dest_addr = dest_addr
        self.seq_num = 0
        self.waiting_for_ack = False
        self.current_packet = None
        self.timeout_timer = None
        self.retry_count = 0
        
    def send_reliable(self, data, msg_hash_id, num_seg, total_seg, type_msg):
        # Envia pacotes com garantia de entrega usando RDT3.0
        print(f"[RDT] Enviando pacote seq={self.seq_num}")
        
        # Monta o cabeçalho expandido
        header_data = struct.pack('!B', type_msg) + \
                    struct.pack('!I', msg_hash_id) + \
                    struct.pack('!I', num_seg) + \
                    struct.pack('!I', total_seg) + \
                    struct.pack('!I', self.seq_num)

        # Calcula o checksum dos dados + cabeçalho parcial
        packet_for_checksum = header_data + data
        checksum = calculate_checksum(packet_for_checksum)
        
        # Completa o cabeçalho com o checksum e flags
        full_header = header_data + struct.pack('!H', checksum) + \
                      struct.pack('!B', 0) + struct.pack('!B', 0) # ack_flag=0, is_ack=0
            
        self.current_packet = full_header + data
        self.waiting_for_ack = True
        self.retry_count = 0
        
        self._send_packet()
        self._start_timeout()
        
    def _send_packet(self):
        
        # envia o pacote atual
        if self.retry_count > 0:
            print(f"[RDT] Reenviando pacote seq={self.seq_num}, tentativa {self.retry_count + 1}")
            
        self.socket.sendto(self.current_packet, self.dest_addr)
        self.retry_count += 1
        
    def _start_timeout(self):
        # Inicia o timer de timeout
        if self.timeout_timer:
            self.timeout_timer.cancel()

        self.timeout_timer = threading.Timer(TIMEOUT_SECONDS, self._handle_timeout)
        self.timeout_timer.start()
        
    def _handle_timeout(self):
        # lida com timeout - retransmite se necessário
        if self.waiting_for_ack and self.retry_count < MAX_RETRIES:
            print(f"[RDT] Timeout! Tentando reenviar seq={self.seq_num}")
            self._send_packet()
            self._start_timeout()
        elif self.retry_count >= MAX_RETRIES:
            print(f"[RDT] Máximo de tentativas atingido para seq={self.seq_num}.")
            self.waiting_for_ack = False
            
    def handle_ack(self, ack_seq_num, checksum_ok):
        # Processa ACK recebido
        if not checksum_ok:
            print(f"[RDT] ACK  corrompido recebido, ignorando.")
            return
        if ack_seq_num == self.seq_num and self.waiting_for_ack:
            print(f"[RDT] ACK válido recebido para seq={self.seq_num}.")
            self.waiting_for_ack = False
            if self.timeout_timer:
                self.timeout_timer.cancel()
            self.seq_num = 1 - self.seq_num  # Alterna entre 0 e 1
        else:
            print(f"[RDT] ACK duplicado ou inválido recebido (esperado: {self.seq_num}, recebido: {ack_seq_num}).")
            
class RDTReceiver:
    def __init__(self, socket_obj):
        self.socket = socket_obj
        self.expected_seq_num = 0
        
    def send_ack(self, seq_num, dest_addr):
        # Envia ACK para sequência específica
        print(f"[RDT] Enviando ACK para seq={seq_num}")
        
        # Monta ACK com cabeçalho simplificado
        ack_header = struct.pack('!B', TYPE_COMPLETE) + \
                    struct.pack('!I', 0) + \
                    struct.pack('!I', 0) + \
                    struct.pack('!I', 0) + \
                    struct.pack('!I', seq_num)
                    
        checksum = calculate_checksum(ack_header)
        full_ack = ack_header + struct.pack('!H', checksum) + \
                struct.pack('!B', seq_num) + struct.pack('!B', 1)  # ack_flag=1, is_ack=1

        self.socket.sendto(full_ack, dest_addr)
        
    def process_packet(self, packet, sender_addr):
        # Processa o pacote recebido com RDT3.0
        if len(packet) < HEADER_SIZE:
            print("[RDT] Pacote recebido é muito pequeno, ignorando.")
            return None
        
        # Extrai o cabeçalho
        type_msg = struct.unpack('!B', packet[0:1])[0]
        msg_hash_id = struct.unpack('!I', packet[1:5])[0]
        num_seg = struct.unpack('!I', packet[5:9])[0]
        total_seg = struct.unpack('!I', packet[9:13])[0]
        seq_num = struct.unpack('!I', packet[13:17])[0]
        received_checksum = struct.unpack('!H', packet[17:19])[0]
        ack_flag = struct.unpack('!B', packet[19:20])[0]
        is_ack = struct.unpack('!B', packet[20:21])[0]
        
        data = packet[HEADER_SIZE:]
    
        # verifica o checksum - CORREÇÃO: usar a mesma estrutura do envio
        packet_for_checksum = packet[:17] + data  # header_data + data (sem checksum e flags)
        checksum_ok = verify_checksum(packet_for_checksum, received_checksum)

        if is_ack:
            return {'type': 'ack', 'seq_num': ack_flag, 'checksum_ok': checksum_ok}
        
        if not checksum_ok:
            print(f"[RDT] Pacote corrompido recebido, enviando ACK duplicado.")
            # envia ack do útltimo pacote válido
            self.send_ack(1 - self.expected_seq_num, sender_addr)
            return None
        
        if seq_num == self.expected_seq_num:
            print(f"[RDT] Pacote válido recebido seq={seq_num}")
            self.send_ack(seq_num, sender_addr)
            self.expected_seq_num = 1 - self.expected_seq_num
            
            return {
                'type': 'data',
                'type_msg': type_msg,
                'msg_hash_id': msg_hash_id,
                'num_seg': num_seg,
                'total_seg': total_seg,
                'data': data
            }
        else:
            print(f"[RDT] Pacote fora de ordem recebido (esperado: {self.expected_seq_num}, recebido: {seq_num})")
            # envia ack duplicado
            self.send_ack(1 - self.expected_seq_num, sender_addr)
            return None
