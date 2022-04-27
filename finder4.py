#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, glob, re, sys, itertools, copy

from sources import *

####GLOBAL VARIABLES#####
matches = []

####HELPER FUNCTIONS#####
def usage_message():
    return '''
        Usage:
        finder4.py [-d] query1, query2, ...

        Options:
            -d search dictionary instead of corpus

        Query syntax:
            <toolbox.identifier>:<search.term>(:<numerator>)

            toolbox.identifier:
                tx      raw rext
                mb      morphemes
                ge      gloss
                ps      part of speech
            WARNING: mb, ge, ps are synchronised, tx should not be used in
            combination

            search.term:
                regular expression (incl. bru orthography)
            WARNING no colons may be used

            numerator:
                None    exactly one
                x       exactly x
                x,y     between x and y, inclusive
            WARNING No spaces between x and y

            counter can be advanced relative to mb line by given amount via
            query ::<numerator> (ie. null query will always return match
            with any string). This is useful for searching syntagms, for example:

                text: "goodbye cruel world"

                query: mb:goodbye ::1 mb:world

                >>> "goodbye cruel world"

                text: "goodbye cruel world"

                query: mb:goodbye ::2 mb:world

                >>> None

    '''

def parse_numerator(s):
    if s == '':
        return (1,)
    t = tuple(map(int,s.split(',')))
    if len(t) > 1:
        return tuple(range(t[0],t[1]+1))
    return t

def get_query(q):
    ###Parsing numerator only queries:
    m = re.match('::(.*)',q)
    if m:
        return ('mb',None,parse_numerator(m.group(1)))

    p = q.split(':')
    if default_tbx:
        if len(p) == 1:
            return (default_tbx,*p,(1,))
        elif len(p) == 2:
            if re.match(r'\d',p[1]):
                return (default_tbx,p[0],parse_numerator(p[1]))
            else:
                return (p[0],p[1],(1,))
        elif len(p) == 3:
            return (p[0],p[1],parse_numerator(p[2]))
    else:
        if len(p) == 2:
            return (*p,(1,))
        return (p[0],p[1],parse_numerator(p[2]))

def parse_refs(fh):
    '''takes a file handle object and returns a list of refs'''
    refs = []
    chunkstart = 0
    lines = fh.readlines()
    for i, line in enumerate(lines):
        if line.startswith('\\ref'):
            refs.append(lines[chunkstart:i])
            chunkstart = i
    if chunkstart != len(lines):
        refs.append(lines[chunkstart:])
    return refs

def single_line_ref(ref):
    lines = {'tx':[],'mb':[],'ge':[],'ps':[],'ft':[]}
    for line in ref:
        try:
            lines[line[1:3]] += re.split(r'\s+',line[3:].lstrip().rstrip())
        except KeyError:
            continue
    return lines

def evaluate_match(token,term):
    global exact
    if term == None:
        return True
    if exact:
        return True if token == term else False
    m = re.search(term,token)
    if m:
        return True
    return False

def format_output(lines,ref,filename):
    if gb4e:
        newref = '\\begin{exe}\n\t\\textname{%s}\n\t\ex '%filename
        for tb,line in lines.items():
            if tb in ['mb','ge']:
                line = re.sub(r' -','-',' '.join(line))
                line = re.sub(r'- ','-',line)
                newref += '%s%s %s\\\\\n' % (
                    '\t\t' if tb == 'ge' else '',
                    '\\gll' if tb == 'mb' else '',
                    line,
                )
            elif tb == 'ft':
                newref += "\t\\trans\t`%s'\n"%' '.join(line)
        return newref+'\end{exe}'
    return ref


#found an error when searching mb:ntrow ps:dem, where a proper noun with
#space in lexeme causes an error with alignment of mb and ps line.
#fix is to replace spaces with underscores in text, or maybe break by tab?
def recursive_search(j,ref,lines,queries,filename,consumed=0):
    if queries == []:
        newlines = copy.deepcopy(lines)
        for i in range(consumed):
            newlines['mb'][j-i-1] = '\\textbf{%s}'%lines['mb'][j-i-1]
        return [format_output(newlines,ref,filename)]
    tbx_id,searchterm,numer = get_query(queries[0])
    result = []
    for slice_length in numer:
        if slice_length == 0:
            result.append(recursive_search(
                j,ref,lines,queries[1:],filename,consumed=consumed
            ))
        elif j+slice_length > len(lines[tbx_id]):
            break
        else:
            m = [
                evaluate_match(token,searchterm) for
                    token in lines[tbx_id][j:j+slice_length]
            ]
            if m != [] and all(element == True for element in m):
                result.append(
                    recursive_search(
                        j+slice_length,
                        ref,
                        lines,
                        queries[1:],
                        filename,
                        consumed=consumed+slice_length,
                    )
                )
    return result

def recursive_unpack(l):
    if l == []:
        return []
    if isinstance(l[0],list):
        return recursive_unpack(l[0] + recursive_unpack(l[1:]))
    return l[:1] + recursive_unpack(l[1:])

def scan_file(fh,filename):
    global matches
    refs = parse_refs(fh)
    for i,ref in enumerate(refs):
        lines = single_line_ref(ref)
        j = 0
        while j < max(len(line) for line in lines.values()):
            for m in recursive_search(j,ref,lines,queries,filename):
                m = recursive_unpack(m)
                if m != []:
                    matches.append(m)
            j += 1

####MAIN####

#Reading options from argv
dict_mode = False
default_tbx = None
gb4e = False
queries = sys.argv[1:]
exact = False

try:
    while True:
        if queries[0] == '-d':
            dict_mode = True
            queries = queries[1:]
        elif queries[0] == '-mb':
            default_tbx = 'mb'
            queries = queries[1:]
        elif queries[0] == '-ps':
            default_tbx = 'ps'
            queries = queries[1:]
        elif queries[0] == '-ge':
            default_tbx = 'ge'
            queries = queries[1:]
        elif queries[0] == '-tx':
            default_tbx = 'tx'
            queries = queries[1:]
        elif queries[0] == '--output-gb4e':
            gb4e = True
            queries = queries[1:]
        elif queries[0] == '-exact':
            exact = True
            queries = queries[1:]
        else:
            break
except IndexError:
    sys.exit(usage_message())
if not queries:
    sys.exit(usage_message())

if path:
    for filename in os.listdir(path):
        if re.match('AW\d+',filename):
            fh = open(path + filename, 'r')
            scan_file(fh,filename)
            fh.close()
elif corpus_file:
    fh = open(corpus_file,'r')
    scan_file(fh,filename)
    fh.close()




for match in matches:
    sys.stdout.write(''.join(match)+'\n')
    sys.stdout.write('-'*60+'\n')


# print(get_query('mb:hello'))
# print(get_query('mb:hello:1'))
# print(get_query('mb:hello:1,4'))
# print(get_query('::2,3'))
# print(get_query('::'))

# def find_at_j(j,ref,lines,queries):
#     global matches
#     iq = iter(queries)
#     while True:
#         try:
#             tbx_id,searchterm,numer = get_query(next(iq))
#             for slice_length in numer:
#                 try:
#                     m = [
#                         evaluate_match(token,searchterm) for
#                             token in lines[tbx_id][j:j+slice_length]
#                     ]
#                     if m[0] and all(element == m[0] for element in m):
#                 except IndexError:
#                     break
#             if found:
#                 j += longest_slice
#             else:
#                 return
#         except StopIteration:
#             matches.append(ref)
#             break
