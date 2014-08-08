# coding: utf-8
'''
Created on 2014年8月8日

@author: lunatic
'''
import unittest
from pymake import Config
import ConfigParser
import collections


class Config(object):
    BASIC = 'basic'
    COMPILER = 'compiler'
    def __init__(self):
        parser = ConfigParser.ConfigParser()
        parser.read('build.cfg')
        
        self.INPUT = parser.get(self.BASIC, 'input')
        self.OUTPUT = parser.get(self.BASIC, 'output')
        suffix = parser.get(self.BASIC, 'exesuff')
        
        self.COMPILER = {opt: parser.get('compiler', opt) for opt in parser.options('compiler')}
        
        self.BUILD = {opt + '.' + suffix: parser.get('build', opt).split('|') for opt in parser.options('build')}
        

class Test(unittest.TestCase):



    def testName(self):
        parser = ConfigParser.ConfigParser()
        parser.read('build.cfg')
        secs = parser.sections()
        print '' ==  parser.get('compiler', 'lflags')
        print [(sec, parser.options(sec)) for sec in secs]


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
