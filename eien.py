import sys, time
# CONSTANTS THAT DEFINES THE TYPES/DEBUG MODES #
VERSION_STR         ='1.0-eien-alpha'

# !! PARSING INFORMATION && DATA !!
TAB_REPLACEMENT     = ' '*2

# !! DEBUG MODES ENUM !!
DEBUG_MODE_NORM=0
DEBUG_MODE_WARN=1
DEBUG_MODE_FAIL=2

# !! RUNTIME SAFE_EXEC !!
LIMIT_MEMORY_USAGE  = 104857600

# !! MACHINE STATES !!
VM_NINIT    =0 
VM_RUNNING  =1
VM_FINISHED =2
VM_SLEEP    =3
VM_DIED     =4

# !! DEBUG REPORTING TOOL !!
class en_debug:
    def __init__(self, en: bool, lc: str, enablell=False):
        self.enablell, self.enabled=enablell, en    ;   self.dcolor=False
        self.location=lc    ;   self.outputs=[[1, sys.stdout]]
    def addOutput(self, output: any, enableColor=0):    self.outputs.append([enableColor, output])
    def write(self, s: str, mode=0):
        if self.enabled:
            begin=( ('--','??','!!')[mode] if (0<=mode<=DEBUG_MODE_FAIL) else '--')
            color=( ('','\033[1;33m','\033[1;31m')[mode] if not self.dcolor and (0<=mode<=DEBUG_MODE_FAIL) else'')
            for target in self.outputs: target[1].write("%s (%s): %s%s%s\n"% (begin, self.location, (color if target[0] else ''), s, ('\033[0m' if target[0] else '')))
    def warn(self, s: str):     self.write(s,mode=DEBUG_MODE_WARN)
    def fail(self, s: str):     self.write(s,mode=DEBUG_MODE_FAIL)
    def ll(self, s: str):
        if self.enablell:       self.write("++ "+s)

# !! EN THREAD BEGINS HERE !!
class en_thread_err(Exception):
    def __init__(self, msg: str):
        self.message=msg    ;   super().__init__(self.message)

class en_thread:
    def __init__(self, file: str, ilabel=str('main'), debug=bool(False), low_level_debug=bool(True)):
        # internal values #
        self.name  = self.__generate_thread_name()
        self.debug = en_debug(debug, 'en_thread', enablell=low_level_debug)
        self.reset_thread(ilabel=ilabel)    ;   self.set_default_opcodes()
        # init the file.
        if file != None:    self.file_target=self.__load_file(file) ;   self.code   =self.__format_code(self.file_target)
        else:               self.debug.ll("not loading files...")
        # configuration
        self.enable_safe_exec=True
        self.limit_callstack =999
    def __generate_thread_name(self, size=32):
        import random as __random
        RANGES, acc=( (ord('a'), ord('z')), (ord('A'), ord('Z')), (ord('0'), ord('9')) ), ""
        for index in range(0, size):    crange=__random.choice(RANGES);acc+=chr(__random.randint(crange[0],crange[1]))
        del __random    ;   return acc
    ## reset thread ##
    def set_default_opcodes(self):
        """set_default_opcodes: case you messed up the opcodes."""
        # set all the opcodes to the default
        self.syscall_table={}
        self.opcode_table={
            'move':	[self.p_move, 2],       'stki': [self.p_stki, 1],   
            'push': [self.p_push, 1],       'cmpr':	[self.p_cmpr, 2], 	
            'cli' : [self.p_cli, 0], 	    'halt': [self.p_halt, 0],   
            'jump':	[self.p_jump, 1], 	    'call': [self.p_call, 1],   
            'retn': [self.p_retn, 0],       'je':	[self.p_je, 1], 	
            'jne':  [self.p_jne, 1], 	    'jge': [self.p_jge, 1], 	
            'jle': [self.p_jle, 1],         'ce':	[self.p_ce, 1], 	
            'cne':  [self.p_cne, 1],	    'cge': [self.p_cge, 1], 	
            'cle': [self.p_cle, 1],         'sysc': [self.p_sysc, 1],   
            'point':[self.p_point,1],       'inc':  [self.p_inc, 1],    
            'dec': [self.p_dec, 1],         'add': [self.p_add, 2],     
            'sub': [self.p_sub, 2],         'mul':  [self.p_mul, 2],    
            'div':  [self.p_div, 2],        'data':[self.p_data, 2],    
            'sat': [self.p_sat, 2],         'smgr': [self.p_smgr, 2],   
            'slen': [self.p_slen,2],        'list': [self.p_list, 1],
            'lpush':[self.p_lpush, 2],      'lpop':[self.p_lpop, 2],    
            'lmgr': [self.p_lmgr, 2],       'lat':  [self.p_lat, 2],    
            'global':[self.p_global, 2],    'tsysc':[self.p_tsysc, 1],
            'tglobal':[self.p_tglobal, 1],  'tvar': [self.p_tvar, 1]
        }
    def reset_thread(self, ilabel=str('main')):
        """reset_thread: reset the thread for a new execution."""
        self.at_label,  self.call_stack, self.inc_pc=ilabel, [], True
        self.registers, self.stack, self.vars, self.global_vars =[0 for regid in range(0, 10+1)], [], {}, {}
        self.sp, self.pc    =0, 0
        self.eq, self.gt    =False, False
        self.state, self.at_tick, self.sleep_until=VM_RUNNING, 0, 0
    ## utility functions ##
    def __format_code(self, buffer: list) -> list:
        """__format_code: make the code better to read for the intepreter."""
        organized_code=self.organize_code(buffer)   ; self.make_sure(organized_code.get(self.at_label),"impossible to find initial label: %s" % self.at_label)
        for at_key in organized_code.keys():
            points,code={},organized_code.get(at_key)['code']
            code_length=len(organized_code.get(at_key)['code'])
            for token_idx in range(0,code_length):
                if code[token_idx]=='point':
                    self.make_sure(token_idx+1<code_length,"malformed point, expected <name>.") ;   point_name=code[token_idx+1]
                    points[point_name]=token_idx
            organized_code[at_key]['points']=points
        return organized_code
    def __load_file(self, name: str) -> list:
        """__load_file: loads a file."""
        file_ptr=open(name,'r') ; lines = [ line.replace('\n','').replace('\t',TAB_REPLACEMENT) for line in file_ptr ]
        file_ptr.close()        ; return self.tokenize(lines)
    def load_lines(self, lines: list):
        """load the code by lines provided."""
        self.code=self.__format_code(self.tokenize(lines))
    def make_sure(self, eval: bool, at_error: str) -> None: 
        if not eval:	raise en_thread_err( ("(%s) "%self.name if self.debug.enablell else '') + at_error)
    def qdebug(self):
        self.debug.write("STATE: %d (%s) -- PC: %d"%(self.state, ('not initialized','running','finished','sleep','died')[self.state],self.pc))
        self.debug.write("at label: %s, opcode: %s"%(self.at_label, self.code[self.at_label]['code'][self.pc]))
    ## code analysis ##
    def tokenize(self, lines: list) -> list:
        """tokenize: tokenize the string, duh."""
        self.debug.ll("tokenize(%s)"%str(lines))
        line_index,line_counter=0,len(lines)    ;   parsed_lines=[]
        def decide_append(a: str, l: list): 
            if len(a)>0: l.append(a)
        while line_index < line_counter:
            line                        = lines[line_index]
            token_index, token_counter  = 0, len(line)
            in_string, in_string_ch     = False, ' '
            acc, tokens                 = "", []
            while token_index < token_counter:
                token = line[token_index]
                if token == ' ' and not in_string:      decide_append(acc,tokens)   ;   acc = ""
                elif token == ',' and not in_string:    decide_append(acc,tokens)   ;   acc = ""
                elif token == ';' and not in_string:    decide_append(acc,tokens)   ;   break
                elif token in ("'", '"') and not in_string: decide_append(acc,tokens)   ;   acc, in_string_ch, in_string = token, token, True
                elif token in ("'", '"') and in_string and token == in_string_ch:   decide_append(acc+token,tokens) ;   in_string, in_string_ch, acc = False, ' ', ''
                else:   acc += token
                token_index += 1
            if in_string:       raise en_thread_err("not closed string in line %d" % (line_index + 1))
            decide_append(acc,tokens)   ;   decide_append(tokens,parsed_lines)
            line_index += 1
        return parsed_lines
    def organize_code(self, buf: list) -> dict:
        """organize_code: split the code in sections in order to make easy to intepret."""
        self.debug.ll("organize_code(%s)"%str(buf))
        sectioned_code,at_section={},None
        for line in buf:
            index,length=0,len(line)
            while index<length:
                token=line[index]
                if token[len(token)-1]==':':
                    label_name=token[0:len(token)-1]
                    if sectioned_code.get(label_name):  raise en_thread_err("label already defined: %s"%label_name)
                    sectioned_code[label_name]={'code':[],'points':{}}	;	at_section=label_name
                    self.debug.write("label opened: %s"%label_name)
                else:	sectioned_code[at_section]['code'].append(token)
                index+=1
        return sectioned_code
    ## code parsing and execution ##
    def __test_decimal(self, value: str):
        # XXX: python doesn't have a method to check if a string contains a decimal number.
        # so that is probably the best option?!
        try:    float(value)    ; return True
        except: return False
    def get_data(self, token: str):
        """get_data: adquire (return) data by given token."""
        self.debug.ll("get_data(token: %s)"%(token))
        if 	token[0] in ('"',"'"):      return token[1:len(token)-1]
        elif    (token[0]=='%'):        v_name=token[1:len(token)]  ; return self.get_var(v_name)
        elif    (token[0]=='@'):        v_name=token[1:len(token)]  ; return self.get_global_var(v_name)
        elif 	(token[0]=='r' and token[1:len(token)].isdigit()) or token in ('sp','pc'):
            if token[0]=='r':
                register_idx=int(token[1:len(token)])   ;   self.make_sure(0<=register_idx<=10,"invalid register indexing: %d"%register_idx)
                return self.registers[register_idx]
            elif token in ('pc','sp'):  return (self.pc if token=='pc' else self.sp)
        elif	(token.isdigit() or token[1:len(token)].isdigit()): return int(token)
        elif    self.__test_decimal(token): return float(token)
        else:   raise en_thread_err("invalid data: %s"%token)
    def set_data(self, value: any, dest: str):
        """set_data: write/define data by the token in a destination."""
        self.debug.ll("set_data(value: %s, dest: %s)"%(str(value), dest))
        if	dest[0]in('"',"'"): pass
        elif    (dest[0]=='%'): v_name=dest[1:len(dest)]    ;   self.set_var(v_name, value)
        elif    (dest[0]=='@'): v_name=dest[1:len(dest)]    ;   self.set_global_var(v_name, value)
        elif	(dest[0]=='r' and dest[1:len(dest)].isdigit()) or dest in ('sp','pc'):
            if dest[0]=='r':
                register_idx=int(dest[1:len(dest)])     ;   self.make_sure(0<=register_idx<=10,"invalid register indexing: %d"%register_idx)
                self.registers[register_idx]=value
            elif dest=='sp':self.sp=value
            elif dest=='pc':self.pc=value
        else:   raise en_thread_err("invalid destination: %s"%dest)
    def goto(self, token: str, save_stack=False, allow_points=True):
        """goto: set the code based on the token give, keywords are: save_stack and allow_points."""
        # NOTE: each time the code pointer moves, the var list resets.
        self.debug.ll("goto(token: %s, save_stack=%s)"%(token,str(save_stack))) ;   self.qdebug()
        if token[0] == '&':
            self.make_sure(allow_points, "invalid use of points: %s"%token)
            name=token[1:len(token)]    ;   self.make_sure(self.code[self.at_label]['points'].get(name)!=None,"unknown label: %s"%name)
            self.pc = self.code[self.at_label]['points'].get(name)
        else:
            self.pc += 1                                # NOTE: jump the address [opcode, <address>]
            if save_stack:  self.call_stack.append([self.at_label, self.pc, self.vars])
            self.make_sure(self.code.get(token)!=None,"label not found: %s"%token)
            self.at_label, self.pc, self.inc_pc, self.vars = token, 0, False, {}
    def get_stack(self, index: int) -> any:
        """get_stack: get from the stack some data by it's index."""
        self.make_sure(index<len(self.stack),"stack was not initialized at index %d"%index)
        return self.stack[index]
    def set_stack(self, index: int, value: any) -> any:
        """set_stack: set on the stack some data."""
        self.make_sure(index<len(self.stack),"stack was not initialized at index %d"%index)
        self.stack[index]=value ;   return self.stack[index]
    ## TODO: mark to remove this functions as they are basically the same thing...
    def set_global_var(self, var_name: str, value: any):
        """set_global_var: defines globally a variable.""" 
        self.global_vars[var_name] = value
    def get_global_var(self, var_name: str):
        """get_global_var: returns a global variable""" 
        self.make_sure(var_name in self.global_vars, "not defined global variable: %s"%var_name)
        return self.global_vars[var_name]
    def set_var(self, var_name: str, value: any):
        """set_var: define a new variable."""
        self.vars[var_name] = value
    def get_var(self, var_name: str):
        """get_var: define the variable."""          
        self.make_sure(var_name in self.vars, "not defined variable: %s"%var_name)  ;   return self.vars[var_name]
    ## -- ALL THE FUNCTIONS THAT ARE ALMOST THE SAME THING... --
    def p_tsysc(self, args: list):
        self.registers[0]=int(not self.get_data(args[0]) in self.syscall_table)
    def p_tvar(self, args: list):
        self.registers[0]=int(not self.get_data(args[0]) in self.vars)
    def p_tglobal(self, args: list):
        self.registers[0]=int(not self.get_data(args[0]) in self.global_vars)
    def p_global(self, args: list):
        self.global_vars[args[0]]=self.get_data(args[1])
    def p_lat(self, args: list):
        self.make_sure(isinstance(self.registers[0],int),"lat expects INT got: %s"%str(self.registers[0]))  ;   self.make_sure(0<=self.registers[0]<len(self.vars[args[0]]),"Out of Range: %d"%self.registers[0])
        self.set_data(self.vars[args[0]][self.registers[0]],args[1])
    def p_lmgr(self, args: list):
        self.make_sure(args[0] in self.vars, "list not found: %s"%args[0])  ;   self.make_sure(isinstance(self.vars[args[0]], list), "lmgr expects LIST, got: %s"%str(self.vars[args[0]]))
        self.make_sure(args[1] in self.vars, "list not found: %s"%args[1])  ;   self.make_sure(isinstance(self.vars[args[1]], list), "lmgr expects LIST, got: %s"%str(self.vars[args[1]]))
        self.vars[args[1]]=self.vars[args[0]] + self.vars[args[1]] 
    def p_lpush(self, args: list):
        self.make_sure(args[1] in self.vars, "list not found: %s"%args[1])  ;   self.vars[args[1]].append(self.get_data(args[0]))
    def p_lpop(self, args: list):
        self.make_sure(args[0] in self.vars, "list not found: %s"%args[1])  ;   self.set_data(args[1],self.vars[args[0]].pop())
    def p_list(self, args: list):
        ## NOTE: lists can only be vars ##
        self.set_var(args[0],[])
    def p_sat (self, args: list):
        the_string=self.get_data(args[0])       ;    self.make_sure(isinstance(the_string, str),"sat expected STRING, got: %s"%the_string)
        self.make_sure(isinstance(self.registers[0],int),"sat expects INT at register R0, got: %s"%str(self.registers[0]))
        self.make_sure(self.registers[0]<=len(the_string),"sat couldn't index %d, out of bounds."%self.registers[0])
        self.set_data(the_string[self.registers[0]],args[1])
    def p_slen(self, args: list):   self.set_data(len(self.get_data(args[0])),args[1])
    def p_smgr(self, args: list):   self.set_data(self.get_data(args[1])+self.get_data(args[0]),args[1])
    def p_data(self, args: list):   v_name,v_data=args[0],self.get_data(args[1])    ;   self.set_var(v_name, v_data)
    def p_div(self, args: list):
        source_v=self.get_data(args[0]) ;   target_v=self.get_data(args[1])
        self.make_sure(isinstance(source_v,int) and isinstance(target_v,int) and (0 in (source_v, target_v)),"div expects INT, got: %s/%s"%(str(source_v),str(target_v)))
        self.set_data(target_v/source_v,args[1])
    def p_mul(self, args: list):
        source_v=self.get_data(args[0]) ;   target_v=self.get_data(args[1])
        self.make_sure(isinstance(source_v,int) and isinstance(target_v,int),"mul expects INT, got: %s/%s"%(str(source_v),str(target_v)))
        self.set_data(target_v*source_v,args[1])
    def p_sub(self, args: list):
        source_v=self.get_data(args[0]) ;   target_v=self.get_data(args[1])
        self.make_sure(isinstance(source_v,int) and isinstance(target_v,int),"sub expects INT, got: %s/%s"%(str(source_v),str(target_v)))
        self.set_data(target_v-source_v,args[1])
    def p_add(self, args: list):
        # !! NOTE: ex: add R0, R1:  R1=R1+R0 !!
        source_v=self.get_data(args[0]) ;   target_v=self.get_data(args[1])
        self.make_sure(isinstance(source_v,int) and isinstance(target_v,int),"add expects INT, got: %s/%s"%(str(source_v),str(target_v)))
        self.set_data(target_v+source_v,args[1])
    def p_dec(self, args: list):
        source_v=self.get_data(args[0]) ;   self.make_sure(isinstance(source_v,int),"inc expects INT, got: %s"%str(type(source_v)))
        self.set_data(source_v-1, args[0])
    def p_inc(self, args: list):
        source_v=self.get_data(args[0]) ;   self.make_sure(isinstance(source_v,int),"inc expects INT, got: %s"%str(type(source_v)))
        self.set_data(source_v+1, args[0])
    def p_point(self, args: list):
        # do nothing, ignore.
        pass
    def p_stki(self, args: list):
        source=self.get_data(args[0])   ;   self.make_sure(isinstance(source,int),"stack initialization requires int.")
        self.stack=[0 for index in range(0,source+1)]
    def p_cli(self, args: list):
        self.eq, self.gt = False, False
    def p_sysc(self, args: list):
        source=self.get_data(args[0])   ; self.make_sure(self.syscall_table.get(source)!=None,"unknown syscall: %s"%str(source))
        self.syscall_table.get(source)(self)
    def p_retn(self, args: list):
        self.make_sure(len(self.call_stack)>0,"unable to perform return!")
        self.at_label, self.pc, self.vars=self.call_stack.pop()
    def p_cle(self, args: list):
        if not self.gt: self.goto(args[0],save_stack=True, allow_points=False)
    def p_cge(self, args: list):
        if self.gt:     self.goto(args[0],save_stack=True, allow_points=False)
    def p_cne(self, args: list):
        if not self.eq: self.goto(args[0],save_stack=True, allow_points=False)
    def p_ce(self, args: list):
        if self.eq:     self.goto(args[0],save_stack=True, allow_points=False)
    def p_jle(self, args: list):
        if not self.gt: self.goto(args[0])
    def p_jge(self, args: list):
        if self.gt: self.goto(args[0])
    def p_jne(self, args: list):
        if not self.eq: self.goto(args[0])
    def p_je(self, args: list):
        if self.eq: self.goto(args[0])
    def p_call(self, args: list):   self.goto(args[0],save_stack=True, allow_points=False)
    def p_jump(self, args: list):   self.goto(args[0])
    def p_halt(self, args: list):   self.state=VM_FINISHED
    def p_cmpr(self, args: list):
        cmp0, cmp1 = self.get_data(args[0]), self.get_data(args[1])
        self.eq = (cmp0 == cmp1)
        # NOTE: allow (this exception only) because it may be int-string comparation?
        try:    self.gt = (cmp0 > cmp1)
        except: pass
    def p_push(self, args: list):   self.set_stack(self.sp,self.get_data(args[0]))  ; self.sp+=1
    def p_move(self, args: list):   source, target=args	;	self.set_data(self.get_data(source),target)
    ## code execution ##
    def set_sleep_until(self, until: int):  self.state, self.sleep_until=VM_SLEEP, (time.time()+until)
    def __sleep_routine(self):
        if time.time()>=self.sleep_until:   self.state=VM_RUNNING   ;   return False
        else:                               return True
    def __safe_locks(self):
        # TODO: smarter safe-locks!
        if      sys.getsizeof(self.call_stack)>LIMIT_MEMORY_USAGE:  self.state=VM_DIED  ;   raise en_thread_err("stack has been using too much memory: %d"%sys.getsizeof(self.call_stack))
        if      len(self.call_stack)>self.limit_callstack:          self.state=VM_DIED  ;   raise en_thread_err("call stack has reached limit size: %d"%len(self.call_stack))
        elif    len(self.call_stack)==self.limit_callstack//2:      self.debug.warn("Call stack has reach 1/2 of limit.")
    def step(self) -> int:
        self.debug.ll("call_stack=%d, global_vars=%d, vars=%d, at=%s"%(len(self.call_stack), len(self.global_vars), len(self.vars), self.at_label))
        label_length=len(self.code[self.at_label]['code'])
        if self.state == VM_SLEEP:   
            if self.__sleep_routine():  return self.state
            else: pass
        elif self.state != VM_RUNNING:      return self.state
        if self.pc>=label_length:	self.state=VM_FINISHED	;	return
        if self.enable_safe_exec:   self.__safe_locks()
        opcode=self.code[self.at_label]['code'][self.pc]	;	self.make_sure(isinstance(opcode,str),"invalid reading: %s"%str(opcode))
        mtable=self.opcode_table.get(opcode)		        ;	self.make_sure(mtable!=None,"invalid opcode: %s"%opcode)
        # begin loading the real opcode from the opcode table.
        invoke=mtable[0]	;	self.make_sure(invoke!=None,"invalid opcode call: %s"%opcode)
        arg_number=mtable[1];	self.make_sure(((self.pc+1)+arg_number)<=label_length,"opcode %s requires %d args."%(opcode,arg_number))
        args=self.code[self.at_label]['code'][(self.pc+1):(self.pc+1)+arg_number]
        try:	                invoke(args)
        except Exception as E:	raise en_thread_err("error at opcode %s: %s"%(opcode,str(E)))
        if self.inc_pc: self.pc+=(1)+arg_number
        else:           self.inc_pc = True
        # increment the tick
        self.at_tick+=1     ;   return self.state
    def run(self):
        while self.state == VM_RUNNING:
            self.debug.write("tick: %0.8x"%self.at_tick)
            self.step()
