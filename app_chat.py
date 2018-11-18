from library_client import *

def Main():
    print "------------------------------------"
    print "Get directory service info "
    address = raw_input("Address: ")
    port = int(raw_input("Port: "))
    grp_setdir(address, port)
    print "------------------------------------"
    #print Menu
    print " -----MENU----  "
    print "join groupname multicast_address multicast_port username ) "
    print "leave groupname"
    print "send groupname your_message"
    print "recv groupname"
    print "------------------------------------"
    print " "
        
    while True:
        command = raw_input("-> ")
        command = command.split(" ")
        
        if command[0] == "join": 
            if command[4] == "you":
                print "give another name "
                continue
            check=grp_join(command[1], command[2] , int(command[3]),command[4])
            if check == "Error":
                print "give another name "
                continue
        elif command[0] == "leave":
            grp_leave(command[1])
        elif command[0] == "send":
            message = ""
            for i in range(len(command)):
                if i>=2:
                    message = message + command[i]+" "
            grp_send(command[1] , message , 1024)
        elif command[0] == "recv": #app will call grp_recv multiple times utnil storage is empty
            mtype = 0 
            while mtype != -1:
                (mtype,mess) = grp_rcv(command[1],1024)
                if mtype == -1:
                    print "No messages"
                elif mtype == 0:
                    print "New group info :" + mess
                else:
                    print mess
        else:
            print " "
            print "-----------------------------------------------"
            print " Please give your command again"
 
    
if __name__ == "__main__":
    Main()
