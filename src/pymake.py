# coding: utf-8
'''
Created on 2014年8月5日

@author: lunatic
'''
import json
import os
import hashlib
import logging
import sys
from settings import COMPILER, OUTPUT, INPUT, TARGET
import ConfigParser


'''
规则是：
1）如果这个工程没有编译过，那么我们的所有C 文件都要编译并被链接。
2）如果这个工程的某几个C 文件被修改，那么我们只编译被修改的C 文件，并链接目标程序。
3）如果这个工程的头文件被改变了，那么我们需要编译引用了这几个头文件的C 文件，并链接目标程序。


更详细的说：
        编译所有存在更新的源文件和受引用更新文件的源文件
        如果文件已经编译并且没有再更新过  什么也不做
        如果文件已经编译但有新的更新 重新编译
        如果文件没有编译过 （即.o文件不存在），不管是否更新 编译
'''



MAKE_FILE = '.mk'

FILE_PINS = {}
# HEAD_REGEX = r'^#include "(\w+.h)"$'

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
ch.setLevel(logging.DEBUG)
logger.addHandler(ch)

class Config:
    parser = ConfigParser.ConfigParser()
    parser.read('build.cfg')
    @classmethod
    def get(cls, section, option):
        return cls.parser.get(section, option)
    @classmethod
    def sections(cls):
        return cls.parser.sections()
    @classmethod
    def options(cls, section):
        return cls.parser.options(section)
    
class Recorder(object):

    def write(self, data={}):
        with open(MAKE_FILE, "w") as f:
            f.write(json.dumps(data));
            
    def update(self, data={}):
        _data = self.read()  
        _data.update(data)
        self.write(_data)
        
    def read(self):
        if not os.path.exists(MAKE_FILE):
            return dict()
        with open(MAKE_FILE, "r") as f:
            return json.loads(f.read())    

def get_content(fn):
    with open(fn, "r") as f:
        content = f.read()
    return content

        
class HeadSet(object):
    '''
     头文件特殊处理：
    为每个头文件建立一个set set里面放入所有包含了该头文件的文件 如果其中有头文件包含了该头文件 递归的求包含该头文件的源文件 代替头文件本身返回
    '''
    def __init__(self):
        self.table = dict()
    
    def add_refs(self, fn, relfns_iter):
        self.table[fn] = set(relfns_iter)
    
    def adjust_refs(self):
        '''
        调整该结构使得所有的set都不包含头文件 
        '''
        self.passed = set()
        for doth in self.table.keys():
            self.passed.clear()
            self.table[doth] = self.__adjust(doth)
            
    def __adjust(self, doth):
        '''
        获取包含该头文件的所有源文件
        '''
        # check processed return empty list 
        # logger.debug(doth, self.passed
        if doth in self.passed:
            return list()
        refs = self.search_refs(doth)
        # maybe sytanx error!
        if refs.__len__() == 0:
            return list()
        dotcc = filter(lambda it: it.endswith('.cc'), refs)
        doths = filter(lambda it: it.endswith('.h'), refs)
        # add passed
        self.passed.add(doth)
        if doths.__len__():
            for ls in [self.__adjust(doth) for doth in doths]:
                dotcc.extend(ls)
        # return set(dotcc)  # filter distinct
        return dotcc
        
    def search_refs(self, fn):
        refs = self.table.get(fn)
        return refs if refs else set()
        
        
    
def get_diffs(origin={}, _dir=INPUT):
    '''
     获取指定目录下所有更新的源文件以及包含更新源文件的源文件
    '''
    logger.debug('Dir: %s', ' '.join(os.listdir(_dir)))
    name_conts = [(name, get_content(os.path.join(_dir, name))) for name in os.listdir(_dir) if name.endswith('.h') or name.endswith('.cc')]
    logger.debug('List of files: %s' % str(zip(*name_conts)[0]))
        
    prints = {name: hashlib.sha1(cont).hexdigest() for name, cont in name_conts}
    global FILE_PINS
    FILE_PINS.update(prints)
    # 比对原始和最新的指纹 过滤出所有变化的文件
    eq = lambda (name, pin): origin.get(name) != pin
    diff_pins = filter(eq, prints.items())
    if diff_pins.__len__() == 0:
        logger.debug('ret empty list')
        return []
    
    diff_files = zip(*diff_pins)[0]
    logger.debug('List of changed files: %s', ' '.join(diff_files))
    
    compiles = list(filter(lambda name: name.endswith('.cc'), diff_files))
    diff_hfiles = filter(lambda name: name.endswith('.h'), diff_files)
    # 找出所有更新的头文件的所有关联文件
    hs = HeadSet()
    for hf in diff_hfiles:
        include = '#include "%s"' % hf
        rels = filter(lambda (name, cont): cont.find(include) != -1, name_conts)
        if rels.__len__() == 0:
            continue
        relfs = zip(*rels)[0]
        # logger.debug('rels', relfs
        hs.add_refs(hf, relfs)
    hs.adjust_refs()
    logger.debug('adjust: %s' % str(hs.table))
    
    for difls in [hs.search_refs(hf) for hf in diff_hfiles]:
        compiles.extend(difls)
        
    logger.debug('List of affected files: %s', ''.join(set(compiles)))
    return {}.fromkeys(compiles).keys()

    
class CommandBuilder(object):
    # g++ -O0 -g3 -Wall -c -fmessage-length=0 
    COMPILE_CMD = '%(name)s -O%(opt)s -g%(debug)s %(warn)s -c %(other)s -o %(out)s %(input)s'
    LINK_CMD = '%(name)s -o %(target)s %(inputs)s'
    def __init__(self):
        self.command = {}
        self.command['name'] = COMPILER['name']
        
        opt = COMPILER.get('optimization')
        deb = COMPILER.get('debugging')
        warn = COMPILER.get('warning')
        other = COMPILER.get('other')
        
        self.command['opt'] = opt if opt else 0
        self.command['debug'] = deb if deb else 0
        self.command['warn'] = '-Wall' if warn and warn == True else ''
        self.command['other'] = other if other else ''
        
        
    def build_commands(self, diffs, target):
        comps = self.__merge(diffs, target)
        out = lambda arg: os.path.join(OUTPUT, arg.split('.')[0] + '.o')
        _in = lambda arg: os.path.join(INPUT, arg)
        tasks = []
        for fn in comps:
            dots = _in(fn)
            if not os.path.exists(dots):
                raise Exception('File Not Found "%s"' % dots)
            doto = out(fn)
            self.command['out'] = doto
            self.command['input'] = dots
            tasks.append(self.COMPILE_CMD % self.command)
        
        for fn, deps in target.items():
            self.command['inputs'] = ' '.join(map(out, deps))
            self.command['target'] = fn
            tasks.append(self.LINK_CMD % self.command)
            
        return tasks;
    
    
    def __merge(self, diffs, target):
        '''
        合并受更新影响的文件和编译依赖文件
        依赖文件编译要求： 如果依赖文件没有受到更新影响 而且.o文件存在则什么也不做 否则编译依赖文件
        '''
        comps = diffs
        logger.debug('merge diff and depends')
        depends = set(reduce(lambda x, y: x + y, target.values()))
        logger.debug('depends: %s', ' '.join(depends))
        out = lambda arg: os.path.join(OUTPUT, arg.split('.')[0] + '.o')
        logger.debug('comps: %s', ' '.join(comps))
        comps.extend([dep for dep in depends if dep not in diffs and not os.path.exists(out(dep))])
        logger.debug('extend comps: %s', ' '.join(comps))
        return comps        
            

def execute(tasks=[]):
    # doit = lambda task: os.popen(task).read()
    doit = lambda x:x
    return '\n'.join(map(doit, tasks))    

def say(x):
    print x
    return x

def main(*args, **kwargs):
    """
    1.提取所有原始文件指纹信息
    2.和当前目录的文件指纹进行对比找到更新的文件
    3.通过引用关系推断出直接或间接受到影响的文件
    4.合并编译所需的依赖文件和受到影响的文件
    5.生成编译器命令
    6.执行生成的命令
    7.将最新的指纹信息保存到文件
    """
    recorder = Recorder()
    builder = CommandBuilder()

    origin = recorder.read()
    diffs = get_diffs(origin)
    
    tasks = builder.build_commands(diffs, TARGET)
    # tasks, upfiles = CommandBuilder().__get_comand(diffs, *TARGET['hello.exe'], target='hello.exe')
    rv = execute(tasks)
    print 'rv:\n', rv, '\n'
    recorder.update(FILE_PINS)

if __name__ == '__main__':
    main()
    logger.debug('end')
    
