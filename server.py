from socket import *
import subprocess
from struct import *

groups = {} #keeps track of what groups were created and who is in them

def join(data,client):
    global groups
    
    grpname = data[1]
    ipaddress = data[2]
    port = int(data[3])
    id_name = data[4]
    
    if grpname not in groups: #if this client was the first to join
        #Create group
        groups[grpname] = [[],[]]
        groups[grpname][0].append(id_name)
        groups[grpname][1].append(client)
        print "New group"
        print grpname +" : "+ ipaddress + ", " + str(port)
        print "==================="

        #Send OK to user
        message = "!!1:"+grpname + ":" + "joined_by you" #sequencer flag
        payload = pack('!{}s'.format(len(message)), message)
        client[0].send(payload)
    elif id_name not in groups[grpname][0]: #if this client is not the firs and has not joined beforethe same group/mulicast
        #Inform other members in group
        message = "!!0:"+grpname + ":"+"joined_by " + id_name
        payload = pack('!{}s'.format(len(message)), message)
        for c in groups[grpname][1]:
            c[0].send(payload)

        #infrorm client about the other members in group
        for c in groups[grpname][0]:
            message = "!!0:"+grpname + ":"+"joined_by " + c
            payload = pack('!{}s'.format(len(message)), message)
            client[0].send(payload)

        #Insert new member in group
        groups[grpname][0].append(id_name)
        groups[grpname][1].append(client)
        #Send OK to user
        message = "!!2:"+grpname + ":"+"joined_by you"
        payload = pack('!{}s'.format(len(message)), message)
        client[0].send(payload)
    #if id_name already exists
    else:
        message = "!!ERROR:"+""
        payload = pack('!{}s'.format(len(message)), message)
        client[0].send(payload)

def leave(data, client):
    global groups

    grpname = data[1]
    id_name = data[2]
    groups[grpname][0].remove(id_name)
    groups[grpname][1].remove(client)
    
    #Inform other members in group
    message = "!!-1:"+grpname + ":"+"left_by " + id_name
    payload = pack('!{}s'.format(len(message)), message)
    for c in groups[grpname][1]:
        c[0].send(payload)

    #Send OK to user
    message = "!!-1:"+grpname + ":"+"left_by you"
    payload = pack('!{}s'.format(len(message)), message)
    client[0].send(payload)
  

def Main():
    clients = [] #storage for clients

    #find my address
    arg='ip route list'
    p=subprocess.Popen(arg,shell=True,stdout=subprocess.PIPE)
    data = p.communicate()
    sdata = data[0].split()
    my_address = sdata[ sdata.index('src')+1 ]
    #open tcp connection listening 5 clients
    s_tcp = socket()
    s_tcp.bind((my_address, 0))
    port = s_tcp.getsockname()[1]
    s_tcp.settimeout(0.5)
    s_tcp.listen(5) 
    #give my info
    print "========================="
    print "Port Number: ", port
    print "IP Address: ", my_address
    print "========================="
    #first listening
    c_tcp=None
    while c_tcp == None:
        try:
            c_tcp, addr = s_tcp.accept() #accept a connection
            c_tcp.settimeout(0.5)
            clients.append([c_tcp, addr])#every new client appends on clients
        except timeout:
            pass
            
    #Start receiving requests
    while True:
        for client in clients:#for every one that is connected
            try:
                data = client[0].recv(1024)
                if data:
                    (data,) = unpack('!{}s'.format(len(data)), data)
                    data_del= data.split(',')
                    for  i in data_del:
                        i.decode('utf-8')
                    #if a join request is received
                    if data_del[0] == "JOIN":
                        join(data_del,client)
                    #if a leave request is received
                    elif data_del[0] == "LEAVE":
                        leave(data_del, client)
            except timeout:
                pass
        #try to connect with a new user
        try:
            c_tcp, addr = s_tcp.accept() #accept a connection
            c_tcp.settimeout(0.5)
            if c_tcp not in clients:
                clients.append([c_tcp,addr])
        except timeout:
            pass
    
    #Close connections with all users
    for client in clients:
        client[0].close()
    
if __name__ == '__main__' :
    Main()
    