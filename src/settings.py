# coding: utf-8
'''
Created on 2014年8月5日

@author: lunatic
'''
Compiler = {'name': 'gcc',
           'optimization':0,
           'debugging':3,
           'warning': True,
           'other': '-fmessage-length=0'}

Target = {'hello.exe': ('main.cc', 'lexer.cc', 'engine.cc', 'alarm.cc'),
          'test.exe': ('', '', '', ''),
          'test1.exe': ('', '', '', '')}

Input = 'src'
Output = 'debug'