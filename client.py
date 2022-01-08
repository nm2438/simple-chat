import argparse 
import socket
import json
import threading 
import sys


def parse_args():
    parser = argparse.ArgumentParser(
        description='This client allows you to connect to a chat server and send/receive messages'
    )
    # TO-DO -- input validation
    parser.add_argument('-s', dest='rhost', type=str, help='server-ip', required=True)
    parser.add_argument('-p', dest='rport', type=int, help='server port', required=True)
    parser.add_argument('-u', dest='user', type=str, help='your username', required=True)
    parser.add_argument('-b', dest='buffer', type=int, help='buffer size. default=1024', default=1024)
    return parser.parse_args() 


def init_connection(args):
    # create the socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # connect to the server
    sock.connect((args.rhost, args.rport))
    # send registration, wait for success msg reply
    msg = json.dumps({'registration':args.user})
    sock.send(bytearray(msg, 'utf-8'))
    # TO-DO -- timeout
    reply = json.loads(sock.recv(args.buffer))
    # validate success
    if reply['registration']==True:
        print(f'Successfully connected to {args.rhost}:{args.rport}')
    else:
        print('Registration was not successful')
    sock.settimeout(1)
    return sock


def clear_line():
    sys.stdout.write('\r')
    sys.stdout.flush()


def print_msg(args, data):
    clear_line()
    try:
        msg = json.loads(data.decode('utf-8'))
        sys.stdout.write(f"{msg['timestamp']} {msg['from']}: {msg['message']}\n")
        sys.stdout.write(f'{args.user} >> ')
        sys.stdout.flush()
    except:
        print('Received improperly formatted message...')    


def print_cmd(data):
    clear_line()
    try:
        msg = json.loads(data.decode('utf-8'))
        sys.stdout.write(f"server: \'{msg['command']}\' --> {msg['result']}\n")
        sys.stdout.flush()
    except:
        print('Could not parse command result...')


def recv(args, conn, stop, pause, commandmode):
    incoming_buffer = []
    while True:
        try:
            data = conn.recv(args.buffer)
            incoming_buffer.append(data)
            if pause():
                pass
            elif commandmode():
                output = json.loads(incoming_buffer[-1])
                if 'result' in output.keys():
                    print_cmd(incoming_buffer.pop())
            else:
                for _ in incoming_buffer:
                    print_msg(args, incoming_buffer.pop(0))
        except socket.timeout as e:
            if stop():
                break
        

def chat_menu(args, options):
    clear_line()
    print(
        'These are your currently selected options:',
        *[f'\t{key} : {val},' for key,val in options.items()],
        'To change an option, type \'set [option] [value]',
        'To return to the chat, type \'back\'',
        sep='\n'
    )
    user_input = input(f'chat_menu > ')
    while user_input != 'back':
        cmd = user_input.split()
        try:
            options[cmd[1]] = options[cmd[2]]
        except:
            print(f'Error setting option \'{cmd[1]}\'')
    print('~Returning to the chat~')    


def send_command(conn, cmd):
    message = {'command' : cmd}
    msg = json.dumps(message)
    conn.send(bytearray(msg, 'utf-8'))


def cmd_menu(args, conn, options):
    clear_line()
    print(
        'These are the available commands:',
        '\tlist',
        'To execute a command, type \'[cmd]\'',
        'To return to the chat, type \'back\'',
        sep='\n'
    )
    user_input = ''
    while user_input != 'back':
        user_input = input(f'cmd_menu > ')
        send_command(conn, user_input)
    print('~Returning to the chat~')


def send_message(args, conn, options, message): 
    msg = {'message':message}
    for opt in options:
        msg[opt] = options[opt]
    message = json.dumps(msg)
    conn.send(bytearray(message, 'utf-8'))


def chatloop(args, conn, options):
    user_input = ''
    # start the listener
    stopper = False
    pauser = False
    command_mode = False 
    listener = threading.Thread(target=recv, args=(args, conn, lambda: stopper, lambda: pauser, lambda: command_mode))
    listener.start()
    # start the loop
    while True:
        user_input = input(f'{args.user} >> ')
        if user_input != 'exit':
            if user_input == 'menu':
                pauser = True
                chat_menu(args, options)
                pauser = False
            elif user_input == 'command':
                command_mode = True
                cmd_menu(args, conn, options)
                command_mode = False
            else:
                send_message(args, conn, options, user_input)
        else:
            stopper = True
            listener.join()
            quit()


def main():
    # parse arguments
    args = parse_args()
    # connect & register to server
    conn = init_connection(args)
    # declare the menu options dict
    options = {
        'mode':'broadcast',  # alt: direct
        'to':'all'           # alt: specific user or group of users
    }
    # enter into main execution loop -- send/receive until user exits
    chatloop(args, conn, options)
    

if __name__ == '__main__':
    main()