import socket
import threading
import math
import struct
import uuid
import os
from utils_common import get_current_time, calculate_checksum, verify_checksum

#configuracoes comuns
BUFFER_SIZE = 1024

# Tamanho do cabeçalho expandido para RDT 3.0
# 21 bytes = 1 byte tipo, 4 bytes hash_id, 4 bytes num_frag, 4 bytes total_frag,
#           4 bytes seq_num, 2 bytes checksum, 1 byte ack_flag, 1 byte is_ack
HEADER_SIZE = 21
#tamanho maximo dos dados que podem ser enviados em uma mensagem
MAX_DATA_SIZE = BUFFER_SIZE - HEADER_SIZE

#tipos de mensagens, para o cabecalho
#respectivamente - conectar, desconectar, msg fragmentada, msg toda
TYPE_HI = 0
TYPE_BYE = 1
TYPE_SEGMENT = 2
TYPE_COMPLETE = 3

# timeouts e limites
TIMEOUT_SECONDS = 2.0
MAX_RETRIES = 5

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
        # RDT para cada cliente
        self.rdt_senders = {} # {client_addr: RDTSender}
        self.rdt_receiver = None
        self.shutdown_flag = False  # Flag para controlar o encerramento gracioso

context_server = ServerContext() #instância para acessar as variaveis globais

def cleanup_server():
    """Função para fazer cleanup gracioso do servidor"""
    print("[SERVER] Iniciando cleanup...")
    
    # Sinaliza para threads pararem
    context_server.shutdown_flag = True
    
    # Limpa todos os RDT senders
    for client_addr, sender in context_server.rdt_senders.items():
        sender.cleanup()
    context_server.rdt_senders.clear()
    
    # Fecha o socket se ainda estiver aberto
    if context_server.server_socket:
        try:
            context_server.server_socket.close()
        except:
            pass
    
    print("[SERVER] Cleanup concluído.")

#funcoes auxiliares

def format_message(ip, port, username, content_message):
    #pegar o tempo para colocar na mensagem
    timestamp = get_current_time()
    #formatar a mensagem para o formato pedido no trabalho
    return f"{ip}:{port}/~{username}: {content_message} {timestamp}"

#funciona da mesma maneira que o do cliente
def send_to_client(data_bytes, client_ad, message_hash_id, num_seg, total_seg, type_msg):
    #similar a do utils.client
    #envia dados para o cliente usando RDT 3.0
    # Cria ou recupera RDTSender para este cliente
    if client_ad not in context_server.rdt_senders:
        context_server.rdt_senders[client_ad] = RDTSender(
            context_server.server_socket,
            client_ad
        )
    
    rdt_sender = context_server.rdt_senders[client_ad]
    rdt_sender.send_reliable(data_bytes, message_hash_id, num_seg, total_seg, type_msg)
    
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
    """Trata pacotes recebidos com processamento RDT 3.0"""
    # Inicializa RDTReceiver se necessário
    if not context_server.rdt_receiver:
        context_server.rdt_receiver = RDTReceiver(context_server.server_socket)
    
    # Processa pacote com RDT 3.0
    result = context_server.rdt_receiver.process_packet(packet_data, client_ad)
    
    if result is None:
        return
        
    if result['type'] == 'ack':
        # Processa ACK
        sender_addr = result['sender_addr']
        if sender_addr in context_server.rdt_senders:
            context_server.rdt_senders[sender_addr].handle_ack(
                result['seq_num'], 
                result['checksum_ok']
            )
        return
    
    # Processa dados normalmente
    type_msg = result['type_msg']
    msg_hash_id = result['msg_hash_id']
    num_seg = result['num_seg']
    total_seg = result['total_seg']
    data_bytes = result['data']

    # Verifica o tipo da mensagem
    if type_msg == TYPE_HI:
        # Decodifica a mensagem para pegar o nome do usuário e o IP/porta do cliente
        parts = data_bytes.decode().split('|', 2)
        username = parts[0]
        client_ip = parts[1]
        client_port = int(parts[2])
        # Adiciona o cliente ao dicionário de clientes conectados 
        context_server.connected_clients[client_ad] = username
        # Avisa que o usuário entrou na sala
        alert_msg = f"{username} entrou na rodinha de conversa"
        broadcast_message(alert_msg.encode(), client_ad)

    elif type_msg == TYPE_BYE:
        leaving_user = data_bytes.decode()
        client_full_ad = None
        # Para achar o endereço completo do cliente que está saindo
        for ad, uname in list(context_server.connected_clients.items()):
            if uname == leaving_user:
                client_full_ad = ad
                break
        # Avisa que o usuário saiu da sala
        if client_full_ad:
            del context_server.connected_clients[client_full_ad]            
            alert_msg = f"{leaving_user} disse tchau tchau."
            broadcast_message(alert_msg.encode(), client_full_ad)

    elif type_msg == TYPE_SEGMENT or type_msg == TYPE_COMPLETE:
        current_user = context_server.connected_clients.get(client_ad)
        client_buffer_key = client_ad
        
        # Reconstroi a mensagem se precisar
        if client_buffer_key not in context_server.segments_from_client_buffer or context_server.segments_from_client_buffer[client_buffer_key]['msg_id_hash'] != msg_hash_id:
            context_server.segments_from_client_buffer[client_buffer_key] = {
                'msg_id_hash': msg_hash_id,
                'parts': [None] * total_seg,
                'received_count': 0,
                'total_seg': total_seg
            }

        # Adiciona o fragmento recebido no buffer, evitando duplicação
        if context_server.segments_from_client_buffer[client_buffer_key]['parts'][num_seg] is None:
            context_server.segments_from_client_buffer[client_buffer_key]['parts'][num_seg] = data_bytes.decode()
            context_server.segments_from_client_buffer[client_buffer_key]['received_count'] += 1

        # Se todos os fragmentos foram recebidos, reconstroi a mensagem completa
        if context_server.segments_from_client_buffer[client_buffer_key]['received_count'] == total_seg:
            full_content_message = "".join(context_server.segments_from_client_buffer[client_buffer_key]['parts'])
            del context_server.segments_from_client_buffer[client_buffer_key]

            # Processa mensagem completa
            tempfile_name = f"server_recv_msg_{uuid.uuid4().hex}.txt"
            with open(tempfile_name, "w") as f:
                f.write(full_content_message)
            with open(tempfile_name, "r") as f:
                read_content = f.read()
                # Formata a mensagem para enviar aos clientes           
                formatted_message_clients = format_message(client_ad[0], client_ad[1], current_user, read_content)
                broadcast_message(formatted_message_clients.encode('utf-8'), client_ad)
            # Limpa o arquivo temporário
            if os.path.exists(tempfile_name):
                os.remove(tempfile_name)
    
class RDTSender:
    def __init__(self, socket_obj, dest_addr):
        self.socket = socket_obj
        self.dest_addr = dest_addr
        self.seq_num = 0
        self.waiting_for_ack = False
        self.current_packet = None
        self.timeout_timer = None
        self.retry_count = 0
        
    def send_reliable(self, data, message_hash_id, num_seg, total_seg, type_msg):
        # envia pacote com RDT 3.0
        print(f"[RDT SERVER] Enviando pacote para {self.dest_addr} seq={self.seq_num}")
        
        # Cria o cabeçalho
        header_data = struct.pack('!B', type_msg) + \
                      struct.pack('!I', message_hash_id) + \
                      struct.pack('!I', num_seg) + \
                      struct.pack('!I', total_seg) + \
                      struct.pack('!I', self.seq_num)
    
       # Calcula checksum dos dados + cabeçalho parcial (sem checksum e flags)
        packet_for_checksum = header_data + data
        checksum = calculate_checksum(packet_for_checksum)
        
        # Completa cabeçalho com checksum e flags
        full_header = header_data + struct.pack('!H', checksum) + \
                     struct.pack('!B', 0) + struct.pack('!B', 0)  # ack_flag=0, is_ack=0
        
        self.current_packet = full_header + data
        self.waiting_for_ack = True
        self.retry_count = 0
        
        self._send_packet()
        self._start_timeout()
        
    def _send_packet(self):
        # Envia o pacote atual
        if self.retry_count > 0:
            print(f"[RDT SERVER] Retransmitindo para {self.dest_addr} seq={self.seq_num} (tentativa {self.retry_count})")
        
        self.socket.sendto(self.current_packet, self.dest_addr)
        self.retry_count += 1
        
    def _start_timeout(self):
        # inicia o timer de timeout
        if self.timeout_timer:
            self.timeout_timer.cancel()
        self.timeout_timer = threading.Timer(TIMEOUT_SECONDS, self._handle_timeout)
        self.timeout_timer.start()
        
    def _handle_timeout(self):
        # trata o timeout, retransmitindo o pacote se necessário
        if self.waiting_for_ack and self.retry_count < MAX_RETRIES:
            print(f"[RDT SERVER] Timeout! Retransmitindo para {self.dest_addr} seq={self.seq_num}")
            self._send_packet()
            self._start_timeout()
        elif self.retry_count >= MAX_RETRIES:
            print(f"[RDT SERVER] Máximo de tentativas atingido para {self.dest_addr} seq={self.seq_num}")
            self.waiting_for_ack = False

    def handle_ack(self, ack_seq_num, checksum_ok):
        # trata o recebimento de um ACK
        if not checksum_ok:
            print(f"[RDT SERVER] ACK corrompido recebido de {self.dest_addr}, ignorando")
            return
            
        if ack_seq_num == self.seq_num and self.waiting_for_ack:
            print(f"[RDT SERVER] ACK válido recebido de {self.dest_addr} para seq={self.seq_num}")
            self.waiting_for_ack = False
            if self.timeout_timer:
                self.timeout_timer.cancel()
            self.seq_num = 1 - self.seq_num  # Alterna entre 0 e 1
        else:
            print(f"[RDT SERVER] ACK duplicado ou inválido de {self.dest_addr} (esperado: {self.seq_num}, recebido: {ack_seq_num})")
    
    def cleanup(self):
        # Limpa recursos do sender
        if self.timeout_timer:
            self.timeout_timer.cancel()
            self.timeout_timer = None
        self.waiting_for_ack = False

class RDTReceiver:
    def __init__(self, socket_obj):
        self.socket = socket_obj
        self.expected_seq = {}  # {client_addr: expected_seq_num}
        
    def send_ack(self, seq_num, dest_addr):
        # envia ACK para sequencia especifica
        print(f"[RDT SERVER] Enviando ACK para {dest_addr} seq={seq_num}")
        
        # Monta ACK com cabeçalho simplificado
        ack_header = struct.pack('!B', TYPE_COMPLETE) + \
                    struct.pack('!I', 0) + \
                    struct.pack('!I', 0) + \
                    struct.pack('!I', 0) + \
                    struct.pack('!I', seq_num)
        
        checksum = calculate_checksum(ack_header)
        full_ack = ack_header + struct.pack('!H', checksum) + \
                  struct.pack('!B', seq_num) + struct.pack('!B', 1)  # ack_flag=seq, is_ack=1
        
        self.socket.sendto(full_ack, dest_addr)
 
    def process_packet(self, packet, sender_addr):
        # processa pacote recebido com RDT 3.0
        if len(packet) < HEADER_SIZE:
            print(f"[RDT SERVER] Pacote muito pequeno de {sender_addr}, descartando")
            return None
            
        # Extrai cabeçalho
        type_msg = struct.unpack('!B', packet[0:1])[0]
        msg_hash_id = struct.unpack('!I', packet[1:5])[0]
        num_seg = struct.unpack('!I', packet[5:9])[0]
        total_seg = struct.unpack('!I', packet[9:13])[0]
        seq_num = struct.unpack('!I', packet[13:17])[0]
        received_checksum = struct.unpack('!H', packet[17:19])[0]
        ack_flag = struct.unpack('!B', packet[19:20])[0]
        is_ack = struct.unpack('!B', packet[20:21])[0]
        
        data = packet[HEADER_SIZE:]
        
        # Verifica checksum - CORREÇÃO: usar a mesma estrutura do envio
        packet_for_checksum = packet[:17] + data  # header_data + data (sem checksum e flags)
        checksum_ok = verify_checksum(packet_for_checksum, received_checksum)
            
        if is_ack:
            # É um ACK
            return {'type': 'ack', 'seq_num': ack_flag, 'checksum_ok': checksum_ok, 'sender_addr': sender_addr}
        
        # Inicializa sequência esperada para novo cliente
        if sender_addr not in self.expected_seq:
            self.expected_seq[sender_addr] = 0
            
        if not checksum_ok:
            print(f"[RDT SERVER] Pacote corrompido de {sender_addr}, enviando ACK duplicado")
            # Envia ACK do último pacote válido
            self.send_ack(1 - self.expected_seq[sender_addr], sender_addr)
            return None
            
        if seq_num == self.expected_seq[sender_addr]:
            print(f"[RDT SERVER] Pacote válido de {sender_addr} seq={seq_num}")
            self.send_ack(seq_num, sender_addr)
            self.expected_seq[sender_addr] = 1 - self.expected_seq[sender_addr]
            
            return {
                'type': 'data',
                'type_msg': type_msg,
                'msg_hash_id': msg_hash_id,
                'num_seg': num_seg,
                'total_seg': total_seg,
                'data': data,
                'sender_addr': sender_addr
            }
        else:
            print(f"[RDT SERVER] Pacote fora de ordem de {sender_addr} (esperado: {self.expected_seq[sender_addr]}, recebido: {seq_num})")
            # Envia ACK duplicado
            self.send_ack(1 - self.expected_seq[sender_addr], sender_addr)
            return None