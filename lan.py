


import socket, subprocess

def get_local_ip_address(target):
	ipaddr = ''
	try:
		s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		s.connect((target, 8000))
		ipaddr = s.getsockname()[0]
		s.close()
	except:
		ipaddr = None
	return ipaddr 

def get_lan_machines(lan_ip):
	index = lan_ip.rfind('.')
	if index > -1:
		lan_space = lan_ip[0:index]
	else:
		#print "given ip is not valid"
		return []
	arp_table = subprocess.Popen('arp -a',shell=True,stdout=subprocess.PIPE)
	list = []
	for line in arp_table.stdout:
		if line.find(lan_ip) > -1:
			primary = True
			continue
		if not line.strip():
			primary = False
		if primary and line.count('.') == 3 and line.split()[0].find(lan_space) > -1:
			list.append(line.split()[0])
	return list		
