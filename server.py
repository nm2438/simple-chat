#!/usr/bin/python
import argparse
import socket
import _thread
import json
import datetime

clients=[] #list of {'name':'jim','socket':s}
def connection_thread(client, addr):
    #registration
    try:
        msg=client.recv(1024)
        decoded_msg=msg.decode('utf-8').strip()
        #first message is registration name
        print(f'received raw reg msg {decoded_msg}')
        reg=json.loads(decoded_msg)
    
        #was the message structured correctly
        if 'registration' in reg.keys():
            client_name=reg['registration']
            new_client={'name':client_name, 'socket':client}
            clients.append(new_client)
            #send back success
            print(f'successful registration {addr[0]}:{client_name}')
            client.sendall('{"registration":true}'.encode('utf-8'))
            reg_bcast={}
            reg_bcast['timestamp']=datetime.datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
            reg_bcast['from']="server"
            reg_bcast['registration']=client_name
            reg_bcast['message']=f'{client_name} registered'
            broadcast(reg_bcast,new_client)
        else:
            #send back fail
            client.sendall('{"registration":false}'.encode('utf-8'))
    except:
        print('FAIL registration' )
    #message listen loop
    while True:
        msg=client.recv(1024)
        decoded_msg=msg.decode('utf-8').strip()
        #print(f'raw chat: {decoded_msg}')
        if len(decoded_msg) > 0:
            chat=json.loads(decoded_msg) #{"message":"hello"}
            if 'command' in chat.keys():
                print(f'received command from {client_name}')
                command_processor(chat, client)
            else: #consider it a message
                chat['timestamp']=datetime.datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
                chat['from']=client_name
                if 'to' in chat.keys():
                    chat['mode']='unicast'
                    print(f'sending DM to {chat["to"]}')
                    for client in clients:
                        if client['name'] == chat['to']:
                            client['socket'].send(json.dumps(chat).encode('utf-8'))
                else:
                    chat['mode']='broadcast'
                    broadcast(chat,client)
    
        
        
        #send chat dict to all other threads

def command_processor(msg, requestor):
    cmd = msg['command']
    if cmd=='list': #list all users
        users = []
        for client in clients:
            users.append(client['name'])
        msg['result']=users
        requestor.send(json.dumps(msg).encode('utf-8'))

def broadcast(chat, from_client):
    #chat_message=f'[{chat["timestamp"]}]({chat["from"]}): {chat["message"]}'
    print(f'broadcasting {json.dumps(chat)}')
    for client in clients:
        if client['socket'] != from_client:
            try:
                client['socket'].send(json.dumps(chat).encode('utf-8'))
            except:
                remove(client)

def remove(dead_client):
    if dead_client in clients:
        clients.remove(dead_client)

def main():
    #grab arguments
    parser=argparse.ArgumentParser(description="Chat Server")
    parser.add_argument('port', type=str,help='The port to listen on')
    args = parser.parse_args()    
    #accept connections
    with socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM) as s:
        host='0.0.0.0'
        port=int(args.port)
        s.bind((host,port))
        listener=s.listen()
        print(f'listening on {host}:{port}')
        while True:
            conn, remote_addr = s.accept()
            print(f'{remote_addr[0]}:{remote_addr[1]} connected')
            _thread.start_new_thread(connection_thread,(conn, remote_addr))

    #register connected users by some identifier
    #{"registration":"ben"}
    #{"registration":"true|false"}
    #listen for messages
    #{"message":"hello"}
    #mass messages to all connected/registered users
    pass

if __name__ == "__main__":
    main()