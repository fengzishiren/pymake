# coding: utf-8
'''
Created on 2014年8月5日

@author: lunatic
'''
COMPILER = {'name': 'gcc',
           'optimization':0,
           'debugging':3,
           'warning': True,
           'other': '-fmessage-length=0'}

TARGET = {'hello.exe': ('main.cc', 'lexer.cc', 'engine.cc', 'alarm.cc'),
          'test.exe': ('', '', '', ''),
          'test1.exe': ('', '', '', '')}

INPUT = '../src'
OUTPUT = '../debug'