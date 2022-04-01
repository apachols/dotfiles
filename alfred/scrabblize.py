import sys
import subprocess

query = sys.argv[1]


def write_to_clipboard(output):
    process = subprocess.Popen(
        'pbcopy', env={'LANG': 'en_US.UTF-8'}, stdin=subprocess.PIPE)
    process.communicate(output.encode('utf-8'))


out = ''
glue = '::scrabble'
if query[0] == '+':
    glue = ':  +:scrabble'
    query = query[1:]
    out += '+'

for word in query.split(' '):
    out += ':scrabble' + glue.join(list(word)) + ': '

write_to_clipboard(out)
