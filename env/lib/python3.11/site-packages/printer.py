def print_lol(list1,level=0,i_tab=False):
	for target in list1:
		raw_input("Do you want a tabe to be beatiful?Y/N")
		if isinstance(target,list):
			print_lol(target,level+1)
		else:
			for tab_stop in range(level):
				print("\t",end='')
			print(target)