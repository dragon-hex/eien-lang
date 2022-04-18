from eien       import VM_RUNNING, en_thread, en_thread_err, VERSION_STR
from os.path    import isfile, abspath
from sys        import argv
class eien_app:
    def __init__(self):
        self.thread=None
        self.file_target=None
        self.program_arguments=None
        self.debugging=False
        self.low_level_debug=False
        self.init_label='main'
        self.limit_cstack=999
    def __quit(self, reason: str):
        exit(print("*** stopped: %s ***"%reason) or 0)
    def __make_sure(self, eval: bool, at_error: str):
        if not eval: self.__quit("(MSF) "+at_error)
    def __load_user_arguments(self):
        self.__make_sure(len(argv)>1,"nothing to do...")
        index, length=1, len(argv)
        while index<length:
            arg=argv[index]
            if      arg in ("-d","-debug"):         self.debugging=True
            elif    arg in ("-li","-label-init"):   self.__make_sure(index+1<length,"%s requires <label> argument."%arg)        ;   self.init_label, index = argv[index+1], index + 1
            elif    arg in ("-ss","-stack-size"):   
                self.__make_sure(index+1<length,"%s requires <stack size> argument."%arg)   ;   self.__make_sure(argv[index+1].isdigit(),"%s requires integer as argument."%arg)
                self.limit_cstack, index = int(argv[index+1]), index+1
            elif    arg in ("-h","-help"):
                exit(
                    print(
                        ("Version: %s\n"%VERSION_STR),
                        "-d/-debug:                 enables debug.\n",
                        "-h/-help:                  show this >.<\n",
                        "-li/-init-label:           requires <label>, set the init label (default: 'main')."
                    ,sep='') or 0
                )
            else:
                if not self.file_target:
                    self.__make_sure(isfile(arg),"invalid argument/file: %s"%arg)   ;   self.file_target=abspath(arg)
                    break
            index+=1
        self.__make_sure(self.file_target!=None,"no file inputed, nothing to do.")
        self.program_arguments=argv[index:length]
    ## system calls ##
    def __syscall_print(self, instance: en_thread, args: list):
        print(instance.registers[0])
    def __syscall_show_stack(self, instance: en_thread, args: list):
        print("Stack Length: %0.8d, Stack Pointer: %0.8d"%(len(instance.stack),instance.sp))
        for index in range(0, len(instance.stack)): print("[%s] %0.4d:   %s"%(('*' if index == instance.sp else ' '),index,str(instance.stack[index])))
    ## init & loop functions ##
    def __load_thread(self):
        self.thread = en_thread(self.file_target,ilabel=self.init_label,debug=self.debugging)
        self.thread.limit_callstack=self.limit_cstack
        self.thread.syscall_table['print']=self.__syscall_print
        self.thread.syscall_table['debug_stack']=self.__syscall_show_stack
    def init(self):
        self.__load_user_arguments()
        self.__load_thread()
    def loop(self):
        while True:
            state = self.thread.step()
            if self.thread.state!=VM_RUNNING: break
    def run(self):
        self.init()
        self.loop()
eien_app().run()