from abc import ABC, abstractmethod
import argparse 
import socket
import json
import threading 
import sys
import time 
import os


##################################################################################
# Classes
##################################################################################


class MenuInterface():
    def __init__(self, menu_name, menu_text, menu_action, options):
        self.menu_name = menu_name
        self.menu_text = menu_text
        self.menu_action = menu_action
        self.options = options


    # TODO - make this threaded, with an easy way to pause (back) OR quit (exit)
    def loop(self, args, conn, options, available_commands):
        # start with clear screen
        clear_screen()
        # print some sort of message / menu
        print(self.menu_text)
        # get input
        user_input = input(self.options['prompt'])
        # somewhat sanitize input
        user_input = user_input.strip().lower()
        # continuously accept input until user exits
        while user_input not in ('back', 'exit'):
            # execute whatever action has been defined
            self.menu_action(args, conn, options, available_commands, user_input)
            # get new input
            user_input = input(self.options['prompt'])
        # exit the menu
        print(f'~Exiting the {self.menu_name} menu~')


class ChatLoop():
    def __init__(self, name, args, conn, options, available_commands):
        self.name = name 
        self.args = args
        self.conn = conn 
        self.options = options 
        self.available_commands = available_commands
        # start the listener
        self.listener = Listener(args, conn, options)
        # create sub-menu objects from the menu class
        menus = self.__chat_menus(options)
        # define the chat loop actions
        def chat_loop(args, conn, options, available_commands, user_input):
            # avoid errors by ignoring 0-length inputs
            if len(user_input) > 0:
                # parse message for commands
                if user_input[0] == '!':
                    command = user_input[1:].split()
                    # help message
                    if command[0] == 'help':
                        clear_line()
                        print('I need to come back and fill this in')                        
                    # chat menus
                    for menu in menus.keys():
                        if command[0] == menu:
                            # TODO -- send appropriate signal to listener callbacks
                            menus[menu].loop(args, conn, options, available_commands)
                    # all other available commands
                    for cmd in available_commands:
                        if command[0] == cmd:
                            send_message(conn, available_commands[cmd])
                # if no command given, send message
                else:
                    msg = {'message':user_input}
                    for opt in ['mode', 'to']:
                        msg[opt] = options[opt]
                    send_message(conn, msg)
        self.interface = \
            MenuInterface(
                menu_name=f'{self.name} chat',
                menu_text= \
                    '\n'.join(
                        [
                            f'You are now in the {self.name} chat',
                            'Type \'!help\' for help'
                        ]
                    ),
                menu_action=chat_loop,
                options=options
            )

    
    def __chat_menus(self, options):
        # create dict to hold menu objects -- 
        # menu class created at top of file
        menus = {}
        # 1. options/settings menu
        # 1.a. define the menu action
        def options_action(args, conn, options, available_commands, user_input):
            cmd = user_input.split()
            try:
                options[cmd[1]] = cmd[2]
            except:
                print(cmd)
                print(f'Error executing \'{cmd}\'')
        # 1.b. define submenu options
        submenu_options = options.copy()
        submenu_options['prompt'] = f'options [{self.name}] > '
        # 1.c. declare the menu object
        options_menu = MenuInterface(
            # name 
            menu_name='Options',
            # display text
            menu_text='\n'.join(
                [
                    'These are your currently selected options:',
                    *[f'\t{key} : {val},' for key,val in options.items()],
                    'To change an option, type \'set [option] [value]',
                    'To return to the chat, type \'back\'',
                ]
            ),
            menu_action = options_action,
            options=submenu_options
        )
        # 1.d. add to dict
        menus['options'] = options_menu
        return menus

    
    def start(self):
        # run the menu loop
        self.interface.loop(self.args, self.conn, self.options, self.available_commands)
        # if the menu thread exits, also exit the listener thread
        self.listener.interthread_callbacks['exit_chat'] = True
        # join the listener thread to the current thread
        self.listener.thread.join() 


class Listener():
    def __init__(self, args, conn, options):
        self.args = args 
        self.conn = conn 
        self.options = options
        # create a dict for communication between threads
        self.interthread_callbacks = {
            'exit_chat' : False,        # tell the listener thread to exit
            'hold_messages' : False,    # receive messages, but don't display them (yet)
            'passthru_mode' : False,    # receive messages, but only display those with the key
            'passthru_key' : None,      # pass-thru messages containing this key
        }
        self.check_callbacks = lambda: self.interthread_callbacks
        # create the listening thread
        self.thread = threading.Thread(target=self.recv)
        # start the thread
        self.thread.start()


    def recv(self):
        # sleep for a second so that the input function 
        # can print its prompt before the listener runs
        time.sleep(1)
        incoming_buffer = []
        while True:
            try:
                data = self.conn.recv(self.args.buffer)
                incoming_buffer.append(data)
                callbacks = self.check_callbacks()
                if callbacks['exit_chat']:
                    break
                elif callbacks['hold_messages']:
                    pass 
                elif callbacks['passthru_mode']:
                    output = json.loads(incoming_buffer[-1])
                    if callbacks['passthru_key'] in output.keys():
                        print_msg(self.args, incoming_buffer.pop(), self.options)
                else:
                    for _ in incoming_buffer:
                        print_msg(self.args, incoming_buffer.pop(0), self.options)
            except socket.timeout as e:
                callbacks = self.check_callbacks()
                if callbacks['exit_chat']:
                    break


##################################################################################
# Functions
##################################################################################


def parse_args():
    parser = argparse.ArgumentParser(
        description='This client allows you to connect to a chat server and send/receive messages'
    )
    # TO-DO -- input validation
    parser.add_argument('-H', dest='rhost', type=str, help='server-ip', required=True)
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


def clear_screen():
    os.system('cls||clear')


def print_msg(args, data, options):
    # TO-DO -- handle all types of message, not just the primary chat
    clear_line()
    try:
        msg = json.loads(data.decode('utf-8'))
        sys.stdout.write(f"{msg['timestamp']} {msg['from']}: {msg['message']}\n")
        sys.stdout.write(options['prompt'])
        sys.stdout.flush()
    except:
        print('Received improperly formatted message...')    


def send_message(conn, msg): 
    message = json.dumps(msg)
    conn.send(bytearray(message, 'utf-8'))





def main():
    # parse arguments
    args = parse_args()
    # create a dict to hold all chat loops
    chats = {}
    # start main loop
    user_input = ''
    while user_input != 'exit':
        clear_screen()
        # print a welcome message
        print( \
            '\n'.join(
                [
                    '## Simple-Chat Client -- Main Menu ##',
                    '',
                    'Available commands:',
                    '\texit\t:\tclose the simple-chat client'
                ]
            )
        )
        # connect & register to server
        conn = init_connection(args)      
        # define options and such
        chat_name = len(chats)
        options = {
            'prompt':f's-chat [{chat_name}] >> ',    # prompt to show in main chat interface
            'mode':'broadcast',                     # alt: unicast
            'to':'all'                              # alt: specific user/group of users
        }
        # TO-DO -- implement a server-side function to return all available commands
        # then, when a client connects, it requests the list, and makes those commands
        # available to the user on the client-side
        # format of dictionary -- cmd name : (cmd message format, reply message format)
        available_commands = {
            'list': {
                'command':'list'
            }
        }
        # create ChatLoop instance -- MenuInterface wrapper class
        new_chat = ChatLoop(
            chat_name,         
            args, 
            conn, 
            options, 
            available_commands
        )
        chats[chat_name]  = new_chat
        # start the chat
        new_chat.start()
        # if chat exits, accept new input
        user_input = input('> ')
    

if __name__ == '__main__':
    main()