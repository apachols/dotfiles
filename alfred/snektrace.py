import sys
import subprocess

query = sys.argv[1]


def write_to_clipboard(output):
    process = subprocess.Popen(
        'pbcopy', env={'LANG': 'en_US.UTF-8'}, stdin=subprocess.PIPE)
    process.communicate(output.encode('utf-8'))


out = ''
for line in query.split('\n'):
    if 'File' in line:
        line = line.replace('File ', '').replace(' line ', '\n\t\t\t\t\t\t\t\t\t\t')
    else:
        line = '\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t' + line
    out += line + '\n'

write_to_clipboard(out)
