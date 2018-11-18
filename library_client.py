from socket import *
from struct import *
import subprocess
import time
from threading import *
import copy

groups = {} #every key references to a specific group  and as values there are its udp sock , members etc
#0->udp sock, 1->multicast address,2->listen_thread, 3->thread_setting, 4->members, 5->storage:messages to be read
#6->username, 7->flag for sequencer , 8->sequence number (only for sequencer),9->what was previous seq-mumber received
join_lock = Lock() 
leave_lock = Lock()
dir_service = None
join_flag = 0
c_tcp = None
thread_setting_tcp = True
thread_listen_tcp = None
wait_acks = {} #for every message in to_send i keep the group members that im waiting for their answers
to_send = {} #storage for sequencer , holds messages to be resent
mutex_lock = Lock()
sending_thread = None
mess_storage = [] #storage for messages to be sent  to the sequencer 
#0->packet,1->grpname,2->timestamp,3->message in packet
storage_mutex = Lock()
send_mutex = Lock()

#thread that saves and resend messages if their total acks never arrived on time  
def send_storage():
        while True:
		storage_mutex.acquire()
		for i in mess_storage: #(mess storage = saves packets for sending)
                        #if timeout has passed ,resend( timeout =5 seconds)
                        if time.time() - i[2] >= 5:
				groups[i[1]][0].sendto(i[0], groups[i[1]][1])
				#give new time stamp to packet
				i[2] = time.time()
		storage_mutex.release()

#thread that listens for a specific udp multicast socket, meaning in this case a specific group chat
def udp_listen(grpname):
	global wait_acks 
	global to_send
	global groups
	t= time.time()

	while groups[grpname][3]: #if we haven't left the chat-multicast  and this setting was changed
		data = None
		try:
			data = groups[grpname][0].recv(1024) #receive from socket
		except timeout:
			pass

		if data and data != "" and data != " ":
			(data,) = unpack('!{}s'.format(len(data)), data)
			data = data.decode('utf-8')
			
			#see if it is the whole message using delimeters for the start and end of the message
			data = data.split("@@@")
			if len(data) >2 :
				continue
			data = data[1].split("###")
			if len(data) > 2:
				continue
			data = data[0]
			
			#check from whom this message has arrived
			data = data.split("!!")
			if data[0] == "SEQ":  #if it is from sequencer 
				data_id = int(data[1])
				if data_id not in groups[grpname][5]: #if this messages is new (has a new sequence number)
					mutex_lock.acquire()
					groups[grpname][5][data_id] = data[2] #put it in my message-storage so i can receive it later
					mutex_lock.release()
					
					(id_name, m) = data[2].split(":") #separate sender from message  
					if id_name == groups[grpname][6]: #if message was sent by me,
                                                #it means that i got my ack and seq number from the sequencer
						for j in mess_storage:
							if j[3] == data[2] and grpname == j[1]: #if this message is in my storage for this group ,
                                                                #now that i got my ack i can remove it
								storage_mutex.acquire()
								mess_storage.remove(j)
								storage_mutex.release()
								break
				
				#Send ack to everybody 
				msg = "@@@"+"ACK2SEQ!!" + str(data_id) + "!!" + groups[grpname][6]+"###"
				msg = msg.encode('utf-8')
				packet = pack('!{}s'.format(len(msg)), msg)
				groups[grpname][0].sendto(packet, groups[grpname][1])

                        #methods only if i am the sequencer-client
			if groups[grpname][7] == True:
				if data[0] == "SEND": #somebody wants to send a message
					flag = False
					send_mutex.acquire()
					for k in to_send:
						if data[1] in to_send[k]: #if you have already got this message ignore it ,you have it on storage
							flag = True
							break
					send_mutex.release()
					if flag == False: #if it was the first time you got this message ,sequencer must give a sequence number
						payload1 = "@@@"+"SEQ!!"+str(groups[grpname][8]) +"!!"+ data[1]+"###"
						payload1 = payload1.encode('utf-8')
						packet = pack('!{}s'.format(len(payload1)), payload1)
						groups[grpname][0].sendto(packet, groups[grpname][1])
						to_send[groups[grpname][8]] = [packet, time.time(), data[1]] #keeps messages until he receive acks from all
						newlist = list(groups[grpname][4])
						wait_acks[groups[grpname][8]] = newlist
						groups[grpname][8] +=1
                                elif data[0] == "ACK2SEQ": #if sequencer got an ack
					data_id = int(data[1])
					if data_id in wait_acks:#if the ack is for a message that is still in to_send
						if data[2] in wait_acks[data_id]: #if sequencer still waits an ack from this user
							wait_acks[data_id].remove(data[2]) #remove user
							if wait_acks[data_id] == []: #if he was the last one , delete message ,sending was successful
								del wait_acks[data_id]
								del to_send[data_id]
					
				if time.time()-t>=0.5: #sequencer must check for timeouts and resend messages
					send_mutex.acquire()
					for l in to_send:
						if time.time() - to_send[l][1] >= 0.5:
							groups[grpname][0].sendto(to_send[l][0], groups[grpname][1])
							to_send[l][1] = time.time()
                                        send_mutex.release()
					t = time.time()
					
#thread that listens to tcp connection aka the directory service
def tcp_listen():
	global c_tcp, thread_setting_tcp, join_flag
	global groups
	
	tcp_counter = -1
	
	while thread_setting_tcp:
                try:
                    data = c_tcp.recv(1024) #receive data from direcotry service
                    if data:
                            (data,) = unpack('!{}s'.format(len(data)), data)
                            list_of_mess = data.split('!!')
                            list_of_mess[0].replace("!!", "")
                            list_of_mess.remove(list_of_mess[0])
                            
                            for m in list_of_mess:
                                (seq, grpname,message) = m.split(':')
                                if seq == "1": #directory service declared me as the sequencer
                                    groups[grpname][7]= True
                                if grpname == "ERROR": #error in join ,wrong name
                                        join_flag = 1
                                        join_lock.release()
                                else: #else directory service has informed for changes in group i put this message in my storage to receive it later
                                	mutex_lock.acquire()
                                	groups[grpname][5][tcp_counter] = message	#negative numbers are the mtype of messages from server
                                	mutex_lock.release()
                                	tcp_counter -= 1
                                	
                                	(mess, user) = message.split(' ')
                                	if mess == "joined_by":#manage join info
                                		if user=="you":
                                			join_lock.release() #successful join
                                		else:
                                			groups[grpname][4].append(user) #put other user in my group-members
                                	else:#manage leave info
                                		if user == "you":
                                			leave_lock.release() #successful leave
                                		else:
                                			if user in groups[grpname][4]: #remove other user from group-members
                                				groups[grpname][4].remove(user)
                except timeout:
                    pass

#Initialize directory service
def grp_setdir(ipaddr, port):
    global dir_service, thread_listen_tcp
    global c_tcp

    #Initialize semaphores
    join_lock.acquire()
    leave_lock.acquire()

    #Set directory service's address
    dir_service = (ipaddr, port)

    #Create connection with server
    c_tcp = socket()
    c_tcp.connect((dir_service))
    c_tcp.settimeout(0.5)
    thread_listen_tcp = Thread(target=tcp_listen)
    thread_listen_tcp.start()
    #start thread
    sending_thread = Thread(target=send_storage)
    sending_thread.start()

    return 1 #for success
    
def grp_leave(gsocket):
	global groups
	#Create and send request to server
	payload = "LEAVE," + gsocket + "," + groups[gsocket][6]
	payload = payload.encode('utf-8')
	packet = pack('!{}s'.format(len(payload)), payload)
	c_tcp.send(packet)
	leave_lock.acquire()
	
	#Wait for all previous messages to be sent in this group
	counter = 1
	while counter != 0:
		counter = 0
		for n in mess_storage:
			if n[1] == gsocket:
				counter += 1

	#Close thread, connection and delete group
	groups[gsocket][3] = False
	groups[gsocket][2].join()
	
	groups[gsocket][0].close()
	del groups[gsocket]


def grp_join(grpname,ipaddr, port,myid):
	global c_tcp, join_flag
        global groups
	c_udp = None
	thread_listen = None
        seq=0
        
	groups[grpname] = [c_udp, (ipaddr, port),  thread_listen, True, [], {}, myid, False, seq,0]
	
	#Create and send request to server
	payload = "JOIN,"+grpname+","+ipaddr+","+str(port)+","+myid
	payload = payload.encode('utf-8')
	packet = pack('!{}s'.format(len(payload)), payload)
	c_tcp.send(packet)

	#wait to get answer in tcp_listen thread
	join_lock.acquire()
	#id already exists in the group
	if join_flag == 1 :
		del groups[grpname]
		print "This id name already exists in the group" 
		join_flag = 0
		return "Error"

	join_flag = 0
	
	#put me in group-members
	groups[grpname][4].append(myid)
	#open udp socket for this chat/multicast
        sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP)
        sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        sock.bind((ipaddr, port))
        mreq = pack("=4sl", inet_aton(ipaddr), INADDR_ANY)
        sock.setsockopt(IPPROTO_IP, IP_ADD_MEMBERSHIP, mreq)
        sock.setsockopt(IPPROTO_IP, IP_MULTICAST_TTL, 2)
        sock.settimeout(0.5)
	groups[grpname][0] = sock

	#Create thread to listen in the multicast socket of the group
	groups[grpname][2] = Thread(target=udp_listen, args=(grpname,))
	groups[grpname][2].start()

	return grpname


def grp_send(gsocket, msg, mlen):
    global to_send
    global wait_acks
    #conaccatenate my username with the message
    msg = groups[gsocket][6]+ ":" + msg
    
    #if i am the sequencer
    if groups[gsocket][7]==True:
        #give next sequence number to your message and send it to all (there is no need to put it in the mess_storage buffer)
        payload = "@@@"+"SEQ!!"+str(groups[gsocket][8]) +"!!"+ msg+"###"
        payload = payload.encode('utf-8')
        packet = pack('!{}s'.format(len(payload)), payload)
        groups[gsocket][0].sendto(packet ,groups[gsocket][1])

        send_mutex.acquire()
        to_send[groups[gsocket][8]] = [payload, time.time(), msg]
        send_mutex.release()

        newlist = list(groups[gsocket][4])
        wait_acks[groups[gsocket][8]] = newlist
        groups[gsocket][8] +=1
    else:
        #i need to send my message  to sequencer so it will take a seq number 
        payload = "@@@"+"SEND!!"+msg+"###"
        payload = payload.encode('utf-8')
        packet = pack('!{}s'.format(len(payload)), payload)

        groups[gsocket][0].sendto(packet, groups[gsocket][1])
        t = time.time()
        #i put it in my storage in case it needs to be resent
        storage_mutex.acquire()
        mess_storage.append([packet,gsocket,t,msg])
        storage_mutex.release()
       
#receives one message at a time 
def grp_rcv(gsocket, mlen):
    global groups
    #directory servce messages have priority
    mtype = 0  #type for messages from server
    msg_id = -10000
    mutex_lock.acquire()
    for x in groups[gsocket][5]: #find negative but maximum seq number , this is the first one message from dir serv that i have to receive
        if x<0 and x>msg_id:
            msg_id = x
    mutex_lock.release()
    if msg_id != -10000: #if message id isnt the end of my iteration, i found a dir srvice message
        msg = groups[gsocket][5][msg_id]
        del groups[gsocket][5][msg_id]
        return mtype, msg
    
    #else if i havent found a dir service message i can receive a multicast message
    mtype = 1
    #if the next message im wating for is in storage ill receive it
    if groups[gsocket][9] in groups[gsocket][5]:
        msg = groups[gsocket][5][groups[gsocket][9]]
        del groups[gsocket][5][groups[gsocket][9]]
        groups[gsocket][9] += 1
        
        return mtype, msg
    
    return -1, "error" #there were no messages
